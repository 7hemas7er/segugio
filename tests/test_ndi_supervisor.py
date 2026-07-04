"""Fix #2 (T-9l5-05) — the NDI receiver survives a transient fault + the tick loop supervises it.

PURE-FAKE tests (NOT marked ``gpu``/``ndi``/``obs``): they drive the headless seams with light
fakes, so they run under ``pytest -m "not gpu and not ndi and not obs"`` with cyndilib/cv2 ABSENT.
They assert the two Fix #2 guarantees:

  (a) a transient exception inside ``NdiFrameSource._run_receiver``'s per-iteration BODY is caught,
      logged (throttled), and COASTED — the loop does not propagate the exception and the daemon
      thread would survive to re-attempt next iteration (before this, one stray fault killed the
      thread and the camera was silently lost for the whole event);
  (b) ``NdiFrameSource.start()`` is idempotent and RESTARTS a dead/missing receiver thread — the
      supervisor hook the orchestrator ``run()`` loop calls every ``_SOURCE_SUPERVISE_INTERVAL_TICKS``.

Both are BOUNDED (they set ``_stop`` after a fixed number of sleeps, or join the thread) so a
regression that reintroduces a tight-spin or a propagated fault would hang/fail, never silently pass.
"""

from __future__ import annotations

from loguru import logger

from segugio.ndi import ndi_source
from segugio.ndi.ndi_source import NdiFrameSource, _RECEIVER_POLL_INTERVAL_S


class _ZeroResFrame:
    """A video_frame whose xres/yres are 0 → the NDI-03 guard skips frame work (no cv2 needed)."""

    xres = 0
    yres = 0


class _FaultyThenOkReceiver:
    """Always-connected receiver whose capture_video() raises ONCE, then behaves.

    Models a transient cyndilib/cv2 decode hiccup on the first connected pass. ``frame_sync`` is
    ``self`` so ``receiver.frame_sync.capture_video()`` routes here.
    """

    def __init__(self, fault_on_pass: int = 1) -> None:
        self.frame_sync = self
        self._pass = 0
        self._fault_on = fault_on_pass
        self.captures = 0

    def is_connected(self) -> bool:
        return True

    def capture_video(self) -> None:
        self._pass += 1
        if self._pass == self._fault_on:
            raise RuntimeError("transient decode hiccup (mid-reconnect finder call)")
        self.captures += 1

    def set_source(self, source) -> None:  # pragma: no cover - not hit on the connected path
        pass


def test_receiver_body_fault_coasts_and_thread_survives(monkeypatch):
    """A transient fault in the receiver body is caught + coasted — never propagated (thread lives)."""
    src = NdiFrameSource(cameras=[])

    # Bound the loop: stop after the 2nd sleep (fault-coast sleep #1, then the healthy pace sleep
    # #2). A regression that PROPAGATED the fault would escape _run_receiver before any sleep here.
    sleeps = {"n": 0}

    def _record_sleep(dt):
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            src._stop.set()

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)

    captured: list[str] = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="WARNING")

    receiver = _FaultyThenOkReceiver(fault_on_pass=1)
    try:
        # If the fault were re-raised, THIS call would raise (a propagated RuntimeError) → the
        # daemon thread would die. It must return normally instead (the thread survives).
        src._run_receiver(
            "cam_wide", "PHONE-WIDE (NDI)", finder=None, receiver=receiver,
            video_frame=_ZeroResFrame(), cv2=None,
        )
    finally:
        logger.remove(sink_id)

    # (a) The loop reached the SECOND (healthy) pass — the fault did not kill it.
    assert receiver.captures == 1, "the receiver must re-attempt after a transient fault"
    # (b) The coast was logged (throttled) — the operator sees the fault, not a silent dead thread.
    assert any("fault" in m and "coasting" in m for m in captured), (
        f"expected a throttled 'body fault (coasting; thread survives)' log, got {captured}"
    )


def _one_camera():
    """Build a single ndi_source-bearing Camera (the supervisor keys threads by Camera.id)."""
    from segugio.config import Role
    from segugio.config.models import Camera, Zone

    return Camera(
        id="cam_wide",
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        ndi_source="PHONE-WIDE (NDI)",
        zones=[Zone(name="field", rect=[0.0, 0.0, 1.0, 1.0])],
    )


def test_supervisor_restarts_dead_receiver(monkeypatch):
    """start() is idempotent and RESTARTS a dead receiver thread (the run()-loop supervisor hook)."""
    # A receiver loop that returns immediately → the spawned thread dies at once.
    monkeypatch.setattr(
        NdiFrameSource, "_receiver_loop", lambda self, cam_id, source_name: None
    )

    src = NdiFrameSource([_one_camera()])
    src.start()
    t1 = src._threads["cam_wide"]
    t1.join(timeout=2.0)
    assert not t1.is_alive(), "the no-op receiver thread should have finished (dead)"

    # The supervisor hook: re-invoke the idempotent start() — it must create a NEW thread for the
    # dead cam_id (a still-alive thread would be left untouched; a dead one is restarted).
    src.start()
    t2 = src._threads["cam_wide"]
    assert t2 is not t1, "start() must create a NEW Thread object to restart a dead receiver"

    src.stop()  # clean teardown (t2 also returns immediately via the no-op loop)


def test_supervisor_leaves_alive_receiver_untouched(monkeypatch):
    """start() is a no-op for a still-alive receiver — the supervisor never churns a healthy feed."""
    import threading

    # A receiver loop that blocks on a per-instance event so the thread stays ALIVE until released.
    release = threading.Event()
    monkeypatch.setattr(
        NdiFrameSource,
        "_receiver_loop",
        lambda self, cam_id, source_name: release.wait(timeout=5.0),
    )

    src = NdiFrameSource([_one_camera()])
    src.start()
    t1 = src._threads["cam_wide"]
    assert t1.is_alive()

    # A supervise pass while the thread is alive must NOT replace it (idempotent-per-camera).
    src.start()
    assert src._threads["cam_wide"] is t1, "an alive receiver must be left running (not restarted)"

    release.set()
    src.stop()


class _AlwaysFaultyReceiver:
    """Always-connected receiver whose capture_video() raises EVERY pass (a persistent fault)."""

    def __init__(self) -> None:
        self.frame_sync = self
        self.passes = 0

    def is_connected(self) -> bool:
        return True

    def capture_video(self) -> None:
        self.passes += 1
        raise RuntimeError("persistent connected-path fault")

    def set_source(self, source) -> None:  # pragma: no cover - not hit on the connected path
        pass


def test_receiver_persistent_fault_backs_off(monkeypatch):
    """WR-02: a PERSISTENT body fault backs off to the disconnected interval, not the 2ms poll pace.

    A one-off transient re-attempts promptly (one poll interval); a stuck connected-path fault must
    NOT churn ~500 exceptions/sec/camera on the box running the <300ms AI loop.
    """
    from segugio.ndi.ndi_source import _RECEIVER_DISCONNECTED_SLEEP_S

    src = NdiFrameSource(cameras=[])

    durations: list[float] = []

    def _record_sleep(dt):
        durations.append(dt)
        # Bound: stop after 3 fault-coast sleeps so we can inspect the backoff schedule.
        if len(durations) >= 3:
            src._stop.set()

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)

    sink_id = logger.add(lambda msg: None, level="WARNING")  # quiet the throttled warning
    try:
        src._run_receiver(
            "cam_wide", "PHONE-WIDE (NDI)", finder=None,
            receiver=_AlwaysFaultyReceiver(), video_frame=_ZeroResFrame(), cv2=None,
        )
    finally:
        logger.remove(sink_id)

    # First fault (streak==1): prompt re-attempt at the poll pace. Every subsequent fault (streak>1):
    # back off to the longer disconnected interval.
    assert durations[0] == _RECEIVER_POLL_INTERVAL_S, "first transient fault re-attempts promptly"
    assert durations[1] == _RECEIVER_DISCONNECTED_SLEEP_S, "a persistent fault backs off"
    assert durations[2] == _RECEIVER_DISCONNECTED_SLEEP_S, "the backoff holds while the fault persists"


def test_receiver_setup_fault_logs_and_exits_cleanly(monkeypatch):
    """WR-01: a receiver SETUP fault is caught + logged through loguru (not a raw stderr traceback),
    the thread exits cleanly, and the per-camera setup-fault streak increments (throttle across
    the supervisor's ~1Hz respawns)."""
    # Force the FIRST setup step to raise. It runs BEFORE the lazy cyndilib/cv2 imports, so the test
    # stays headless (no cyndilib needed) and models the NDI base<->HX plugin pairing gotcha.
    def _boom() -> None:
        raise RuntimeError("NDI base<->HX plugin pairing failed")

    monkeypatch.setattr(ndi_source, "_prefer_system_ndi_runtime", _boom)

    src = NdiFrameSource(cameras=[])

    captured: list[str] = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="ERROR")
    try:
        # Must NOT raise: a raw traceback would kill the thread AND escape the loguru sink.
        src._receiver_loop("cam_wide", "PHONE-WIDE (NDI)")
    finally:
        logger.remove(sink_id)

    assert any("SETUP fault" in m for m in captured), (
        f"a setup fault must be logged through loguru, got {captured}"
    )
    assert src._setup_faults["cam_wide"] == 1

    # A second respawn attempt increments the streak (drives the cross-respawn throttle).
    sink_id2 = logger.add(lambda msg: None, level="ERROR")
    try:
        src._receiver_loop("cam_wide", "PHONE-WIDE (NDI)")
    finally:
        logger.remove(sink_id2)
    assert src._setup_faults["cam_wide"] == 2
