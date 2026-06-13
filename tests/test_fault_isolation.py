"""RBT-04 — a thrown error in any stage → loop coasts to SAFE, never crashes.

The orchestrator's hard live-robustness contract ("nessun crash ammesso", threat T-05-06-01):
a raised exception in ANY tick stage (frame pull / track / scorer / engine / OBS cut / channel)
is caught → logged → the loop coasts to SAFE and keeps ticking; the process NEVER exits. On
shutdown the orchestrator cuts to SAFE explicitly, stops the source, and closes OBS.

These run HEADLESS against light fakes (no cyndilib / obsws / cv2 / ultralytics): the
orchestrator depends only on the injected interfaces, and the per-camera trackers are injected
fakes so YOLO never loads.
"""

from __future__ import annotations

import pytest

from segugio.orchestrator.loop import Orchestrator


class _ThrowingFrameSource:
    """A FrameSource whose every read raises — the harshest ingest fault."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def latest(self, cam_id: str):
        raise RuntimeError("boom: decode failure")

    def last_frame_ts(self, cam_id: str):
        raise RuntimeError("boom: ts read failure")

    def stop(self) -> None:
        self.stopped = True


class _ThrowingObs:
    """An ObsController that raises on cut but records connect/close (websocket-drop sim)."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect",))

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut-attempt", scene_name))
        raise RuntimeError("boom: websocket dropped")

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        self.calls.append(("close",))


class _OkObs:
    """A recording ObsController that succeeds (for the shutdown-SAFE assertion)."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect",))

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut", scene_name))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        self.calls.append(("close",))


class _FakeTracker:
    """A per-camera tracker stand-in returning no detections (so the loop coasts cleanly)."""

    def track(self, frame):
        return None


def _build(cfg, source, obs, file_channel, trackers=None, preview=None):
    """Construct an Orchestrator with the light collaborators wired from the fixtures.

    Uses the ``from_config`` convenience factory (it builds the scorer/engine/watchdog/deriver
    from the validated Config internally) and injects the fake trackers so YOLO never loads.
    An optional ``preview`` collaborator is threaded through for the publisher-fault-coast test.
    """
    if trackers is None:
        trackers = {cam.id: _FakeTracker() for cam in cfg.cameras}
    return Orchestrator.from_config(
        config=cfg,
        source=source,
        obs=obs,
        channel_paths=file_channel,
        trackers=trackers,
        fps=30.0,
        preview=preview,
    )


def test_thrown_error_coasts_to_safe(make_config, file_channel):
    """A throwing FrameSource at every read → the loop coasts to SAFE and keeps ticking."""
    cfg = make_config()
    source = _ThrowingFrameSource()
    obs = _OkObs()
    orch = _build(cfg, source, obs, file_channel)

    # Drive a bounded number of ticks — the loop must NOT raise.
    orch.run_measured(n_ticks=5)

    # The source was started; despite every read raising, the loop survived all 5 ticks.
    assert source.started is True
    # Each coast wrote/aired SAFE — the SAFE scene is the is_safe camera's obs_scene.
    safe_scene = next(c.obs_scene for c in cfg.cameras if c.is_safe)
    cut_scenes = [c[1] for c in obs.calls if c[0] == "cut"]
    assert cut_scenes, "the loop must have aired at least one scene"
    assert all(s == safe_scene for s in cut_scenes), "every fault tick must coast to SAFE"


def test_obs_cut_failure_does_not_crash(make_config, file_channel):
    """An ObsController.cut that raises → caught, logged, loop keeps ticking (Pitfall 4)."""
    cfg = make_config()
    from segugio.ndi.clip_source import ClipReplayFrameSource

    # A source that produces nothing (always None) but never raises — isolates the OBS fault.
    def _empty_iter():
        for tick in range(10):
            yield (tick, {})

    source = ClipReplayFrameSource(frames_iter=_empty_iter())
    obs = _ThrowingObs()
    orch = _build(cfg, source, obs, file_channel)

    orch.run_measured(n_ticks=5)  # must not raise even though every cut throws

    assert any(c[0] == "cut-attempt" for c in obs.calls), "the loop attempted to cut"


def test_safe_on_shutdown(make_config, file_channel):
    """On shutdown the orchestrator cuts to SAFE, stops the source, and closes OBS (RBT-04)."""
    cfg = make_config()
    from segugio.ndi.clip_source import ClipReplayFrameSource

    def _empty_iter():
        for tick in range(10):
            yield (tick, {})

    source = ClipReplayFrameSource(frames_iter=_empty_iter())
    obs = _OkObs()
    orch = _build(cfg, source, obs, file_channel)

    orch.run_measured(n_ticks=3)
    orch.shutdown()

    safe_scene = next(c.obs_scene for c in cfg.cameras if c.is_safe)
    # The FINAL cut on shutdown is to SAFE.
    cut_scenes = [c[1] for c in obs.calls if c[0] == "cut"]
    assert cut_scenes[-1] == safe_scene, "shutdown must cut to SAFE"
    assert ("close",) in obs.calls, "shutdown must close OBS"


def test_loop_never_calls_track_with_a_frame_list(make_config, file_channel):
    """Per-camera independence (#13107): each tracker is called with ONE frame, never a list."""
    cfg = make_config()
    from segugio.ndi.clip_source import ClipReplayFrameSource

    captured: dict[str, list] = {cam.id: [] for cam in cfg.cameras}

    class _CapturingTracker:
        def __init__(self, cam_id: str) -> None:
            self.cam_id = cam_id

        def track(self, frame):
            captured[self.cam_id].append(frame)
            return None

    # A source publishing a simple non-empty per-camera "frame" object (.size > 0 so the
    # NDI-03 guard publishes it).
    class _Frame:
        size = 1

    def _iter():
        for tick in range(4):
            yield (tick, {cam.id: _Frame() for cam in cfg.cameras})

    source = ClipReplayFrameSource(frames_iter=_iter())
    obs = _OkObs()
    trackers = {cam.id: _CapturingTracker(cam.id) for cam in cfg.cameras}
    orch = _build(cfg, source, obs, file_channel, trackers=trackers)

    orch.run_measured(n_ticks=4)

    for cam in cfg.cameras:
        # Each tracker saw single frames (never a list of frames in one call).
        assert captured[cam.id], f"tracker {cam.id} was driven"
        assert all(not isinstance(f, list) for f in captured[cam.id])


class _RaisingPreview:
    """A PreviewPublisher stand-in whose ``offer()`` ALWAYS raises (start/stop are no-ops).

    Proves the hot-path catch specifically: the offer is the ONLY new tick-path call (it rides
    inside the existing RBT-04 try in ``_tick_once``), so a raising offer must coast there — not
    crash the tick. start/stop never raise (the lifecycle is also guarded).
    """

    def __init__(self) -> None:
        self.offer_calls = 0
        self.started = False
        self.stopped = False

    def offer(self, frames, scores, dets, decision, cuts) -> None:
        self.offer_calls += 1
        raise RuntimeError("boom: preview offer fault")

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_preview_offer_fault_coasts(make_config, file_channel):
    """PRV-01 criterion 5 / SC5: a raising preview ``offer()`` does NOT crash the tick.

    The guarded offer rides inside the existing ``_tick_once`` RBT-04 try (loop L534), so a
    publisher fault coasts via the same catch — the tick still completes AND ``status.json`` is
    still written. Drives 5 ticks with a frame-emitting source (so offer() is actually reached)
    and a publisher whose offer always raises, then asserts the ticks completed (offer WAS called,
    proving we reached it) and ``read_status`` returns a valid ``DirectorStatus``.
    """
    from segugio.ndi.clip_source import ClipReplayFrameSource
    from segugio.opcomm.channel import read_status
    from segugio.opcomm.records import DirectorStatus

    cfg = make_config()

    class _Frame:
        size = 1

    def _iter():
        for tick in range(10):
            yield (tick, {cam.id: _Frame() for cam in cfg.cameras})

    source = ClipReplayFrameSource(frames_iter=_iter())
    obs = _OkObs()
    preview = _RaisingPreview()
    orch = _build(cfg, source, obs, file_channel, preview=preview)

    # Must NOT raise even though every offer() throws — the offer rides inside the RBT-04 try.
    orch.run_measured(n_ticks=5)

    assert preview.started is True, "the publisher lifecycle start() was driven"
    assert preview.offer_calls >= 1, "offer() WAS reached (so the coast is the hot-path catch)"
    # status.json was still written — the tick completed past the coasted offer.
    status = read_status(str(file_channel["status"]))
    assert isinstance(status, DirectorStatus)


def test_partial_connect_does_not_crash():
    """A partial ObsWsController.connect() (id-cache fails) coasts — connect must NOT raise (CR-01).

    OBS just came up: the clients build but ``get_scene_item_id`` raises while resolving PIP ids.
    ``_cache_pip_ids`` is guarded INSIDE connect() so the controller still marks itself connected
    and stays usable for the per-tick reconnect (ids re-cache via the EventClient / first op).
    """
    from segugio.obs.obsws_controller import ObsWsController

    class _IdRaisingReq:
        def get_scene_item_id(self, scene, source):
            raise ConnectionError("OBS just came up — id not resolvable yet")

        def disconnect(self):
            pass

    class _FakeEvt:
        class _CB:
            def __init__(self) -> None:
                self.registered: list = []

            def register(self, fn):
                self.registered.append(fn)

        def __init__(self) -> None:
            self.callback = _FakeEvt._CB()

        def disconnect(self):
            pass

    def factory(host, port, password):
        return _IdRaisingReq(), _FakeEvt()

    # A non-empty pip_sources so _cache_pip_ids actually runs and hits the raising get id.
    ctrl = ObsWsController(
        pip_sources=[("PIP", "cam_wide")], client_factory=factory
    )

    # connect() must NOT raise despite _cache_pip_ids failing on the id resolve.
    ctrl.connect()

    assert ctrl._connected is True  # the partial connect coasted; controller stays usable
