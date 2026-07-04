"""Fix #5 (T-9l5) — obs_connected reaches status.json, GET /status, and the console badge.

A down OBS makes obs.cut a throttled no-op (_safe_call coasts), but before this fix _status_for
never signalled it, so the operator saw "auto" while nothing was actually switching. These tests
prove the reachability flag end-to-end:

  (a) the orchestrator publishes DirectorStatus.obs_connected from obs.connected;
  (b) it round-trips through status.json and is exposed by GET /status;
  (c) the console template carries the obs-health render hook.
"""

from __future__ import annotations

from segugio.opcomm.channel import read_status, write_status
from segugio.opcomm.records import DirectorStatus
from segugio.orchestrator.loop import Orchestrator


class _ObsWithHealth:
    """A fake OBS exposing a `connected` property (like ObsWsController) + the control surface."""

    def __init__(self, connected: bool) -> None:
        self.connected = connected

    def connect(self) -> None:
        pass

    def cut(self, scene_name: str) -> None:
        pass

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        pass


class _Frame:
    size = 1


class _FakeTracker:
    def track(self, frame):
        return None


def _orch(cfg, obs, file_channel):
    from segugio.ndi.clip_source import ClipReplayFrameSource

    def _iter():
        for tick in range(20):
            yield (tick, {cam.id: _Frame() for cam in cfg.cameras})

    source = ClipReplayFrameSource(frames_iter=_iter())
    trackers = {cam.id: _FakeTracker() for cam in cfg.cameras}
    return Orchestrator.from_config(
        config=cfg, source=source, obs=obs, channel_paths=file_channel,
        trackers=trackers, fps=30.0,
    )


def test_orchestrator_publishes_obs_connected_false(make_config, file_channel):
    """A fake OBS with connected=False makes the published status.obs_connected False."""
    cfg = make_config()
    orch = _orch(cfg, _ObsWithHealth(connected=False), file_channel)
    orch.run_measured(n_ticks=4)

    status = read_status(str(file_channel["status"]))
    assert status.obs_connected is False


def test_orchestrator_publishes_obs_connected_true(make_config, file_channel):
    """A fake OBS with connected=True makes the published status.obs_connected True."""
    cfg = make_config()
    orch = _orch(cfg, _ObsWithHealth(connected=True), file_channel)
    orch.run_measured(n_ticks=4)

    status = read_status(str(file_channel["status"]))
    assert status.obs_connected is True


def test_obs_connected_round_trips_through_status_json(file_channel):
    """DirectorStatus.obs_connected survives write_status → read_status (default True on absent)."""
    write_status(str(file_channel["status"]), DirectorStatus(live_cam="cam_wide", obs_connected=False))
    got = read_status(str(file_channel["status"]))
    assert got.obs_connected is False
    # A default DirectorStatus (and a legacy file with no obs_connected key) reads as True.
    assert DirectorStatus().obs_connected is True


def test_status_route_exposes_obs_connected(file_channel):
    """GET /status returns obs_connected in its JSON payload (the console poll source)."""
    from segugio.ui.app import create_app

    write_status(str(file_channel["status"]), DirectorStatus(live_cam="cam_wide", obs_connected=False))
    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("obs_connected") is False


def test_console_template_has_obs_health_hook(file_channel):
    """The rendered console page carries the obs-health render hook (badge element)."""
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]), cam_ids=["cam_wide"])
    app.config.update(TESTING=True)
    client = app.test_client()

    html = client.get("/").get_data(as_text=True)
    assert "obs-health" in html, "the console must render an OBS-health badge hook"
