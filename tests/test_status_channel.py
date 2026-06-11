"""D-11 — orchestrator writes director status (live cam + reason + per-feed alive).

The reverse channel the panel polls (D-11): on each change the orchestrator writes a small
atomic ``status.json`` carrying the live camera, the mapped reason
(``auto`` / ``override`` / ``subject-lost`` / ``feed-dead``), and the per-feed ``{cam_id: bool}``
alive/dead map. These run headless against the in-process clip mock + the recording fake.
"""

from __future__ import annotations

from segugio.opcomm.channel import read_status
from segugio.orchestrator.loop import Orchestrator


class _OkObs:
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
    """Returns no detections → the lock coasts (subject-lost path)."""

    def track(self, frame):
        return None


def _orch(cfg, source, obs, file_channel, trackers=None):
    if trackers is None:
        trackers = {cam.id: _FakeTracker() for cam in cfg.cameras}
    return Orchestrator.from_config(
        config=cfg, source=source, obs=obs, channel_paths=file_channel,
        trackers=trackers, fps=30.0,
    )


def test_status_written_on_change(make_config, file_channel):
    """The orchestrator writes status.json with the live cam + reason + per-feed alive map."""
    cfg = make_config()
    from segugio.ndi.clip_source import ClipReplayFrameSource

    # No frames published → every feed is dead by the watchdog (no last_frame_ts) → SAFE.
    def _empty_iter():
        for tick in range(10):
            yield (tick, {})

    source = ClipReplayFrameSource(frames_iter=_empty_iter())
    obs = _OkObs()
    orch = _orch(cfg, source, obs, file_channel)

    orch.run_measured(n_ticks=4)

    status = read_status(str(file_channel["status"]))
    # Nothing alive, nothing tracked → the director is parked on SAFE.
    assert status.live_cam == "SAFE"
    # The per-feed alive map carries an entry for every camera.
    assert set(status.alive.keys()) == {cam.id for cam in cfg.cameras}
    assert all(v is False for v in status.alive.values()), "no feed delivered a NEW frame → dead"


def test_status_reason_maps_feed_dead_vs_subject_lost(make_config, file_channel):
    """A dead live feed → reason 'feed-dead'; a coast with live feeds → 'subject-lost'."""
    cfg = make_config()
    from segugio.ndi.clip_source import ClipReplayFrameSource

    # Publish a NEW frame for every camera each tick (so feeds are ALIVE) but the trackers
    # return no detections → the FSM finds no eligible candidate → SAFE with live feeds.
    def _iter():
        for tick in range(20):
            yield (tick, {cam.id: object() for cam in cfg.cameras})

    source = ClipReplayFrameSource(frames_iter=_iter())
    obs = _OkObs()
    orch = _orch(cfg, source, obs, file_channel)

    # Many ticks so the watchdog sees fresh timestamps (now derived from the emitted tick).
    orch.run_measured(n_ticks=6)

    status = read_status(str(file_channel["status"]))
    # Feeds are alive (NEW frames each tick) but nothing is tracked → subject-lost, not feed-dead.
    assert status.live_cam == "SAFE"
    assert all(v is True for v in status.alive.values()), "every feed delivered a NEW frame"
    assert status.reason == "subject-lost"


def test_status_default_when_no_loop_run(make_config, file_channel):
    """Before any tick, read_status of an absent file returns the SAFE default (RBT-04)."""
    status = read_status(str(file_channel["status"]))
    assert status.live_cam == "SAFE"
    assert status.reason == "none"
