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
