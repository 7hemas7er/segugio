"""SCR-03 / D-09 — run start/stop writes runstate; START flags lock-reset, STOP flags SAFE-park.

Plus D-10 override (POST /command, force XOR release) and D-11 reverse channel (GET /status).
All via the Flask test client against a tmp_path opcomm dir.
"""

from __future__ import annotations

import pytest

from segugio.opcomm.channel import read_command, read_runstate, write_status
from segugio.opcomm.records import DirectorStatus


@pytest.fixture
def client(file_channel):
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel


# --- POST /run (D-09) -------------------------------------------------------- #


def test_run_start_flags_lock_reset(client):
    c, ch = client
    resp = c.post("/run", data={"action": "start"})
    assert resp.status_code in (200, 204)
    run = read_runstate(str(ch["runstate"]))
    assert run.action == "start"
    assert run.just_started is True  # D-09 START → lock-reset edge


def test_run_stop_flags_safe_park(client):
    c, ch = client
    resp = c.post("/run", data={"action": "stop"})
    assert resp.status_code in (200, 204)
    run = read_runstate(str(ch["runstate"]))
    assert run.action == "stop"
    assert run.stopped is True  # D-09 STOP → orchestrator parks on SAFE
    assert run.just_stopped is True


def test_run_invalid_action_rejected(client):
    c, ch = client
    resp = c.post("/run", data={"action": "pause"})
    assert resp.status_code == 400
    assert not ch["runstate"].exists()


# --- POST /command (D-10 force XOR release) ---------------------------------- #


def test_command_force_cam(client):
    c, ch = client
    resp = c.post("/command", data={"force_cam": "cam_long"})
    assert resp.status_code in (200, 204)
    cmd = read_command(str(ch["command"]))
    assert cmd is not None
    assert cmd.force_cam == "cam_long"
    assert cmd.release is False


def test_command_release(client):
    c, ch = client
    resp = c.post("/command", data={"release": "1"})
    assert resp.status_code in (200, 204)
    cmd = read_command(str(ch["command"]))
    assert cmd is not None
    assert cmd.release is True
    assert cmd.force_cam is None


def test_command_contradictory_rejected(client):
    """force + release in one POST is contradictory → 400, never written (T-05-05-03)."""
    c, ch = client
    resp = c.post("/command", data={"force_cam": "cam_low", "release": "1"})
    assert resp.status_code == 400
    assert not ch["command"].exists()


# --- GET /status (D-11 reverse channel) -------------------------------------- #


def test_status_poll_returns_director_status(client):
    c, ch = client
    # The orchestrator wrote a status the panel polls.
    write_status(
        str(ch["status"]),
        DirectorStatus(live_cam="cam_long", reason="auto", alive={"cam_long": True}),
    )
    resp = c.get("/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["live_cam"] == "cam_long"
    assert data["reason"] == "auto"
    assert data["alive"]["cam_long"] is True


def test_status_default_when_absent(client):
    """No status file yet → a safe default (SAFE) status, never an error (RBT-04)."""
    c, _ = client
    resp = c.get("/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["live_cam"] == "SAFE"
