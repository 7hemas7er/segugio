"""OVD-01 / OVD-02 — GET /overlay-json contract + run-edge overlay_run stamping + gen monotonicity.

The console publishes the overlay's whole data contract over the existing opcomm-over-files
channel (publish-and-render, the v1.1 precedent — the director is NEVER touched). This file is the
route surface named in 10-VALIDATION.md:

  - POST /run start/stop stamps the NEW console-owned ``overlay_run.json`` (running/started_at/gen)
    AFTER the unchanged ``write_runstate`` — the byte-for-byte runstate invariant (D-03) is the HARD
    director-never-touched proof.
  - GET /overlay-json returns boundary-safe ``{discipline, fields, running, started_at, server_now,
    gen}`` with ``Cache-Control: no-store`` (D-04 safe-default; D-08 verbatim fields).
  - ``server_now`` (the clock-skew anchor) + a monotonic ``gen`` are in the contract from the first
    commit; gen bumps on every /run and /score; gen seeds from disk on restart (D-02 — never
    reset to 0); started_at persists across restart (D-02 re-anchor).

RED-by-design: the /overlay-json route, the gen bump, and the overlay_run side-write do not exist
until Plan 10-04 (and OverlayRunDoc/read_overlay_run/write_overlay_run until Plan 10-02). The
lands-later tests are ``@pytest.mark.xfail(strict=False)`` and import the not-yet-existing symbols
INSIDE their bodies so collection stays green (an ImportError under xfail is an expected fail, not a
collection error). Plan 10-04 creates the route + bump and REMOVES those markers.

The single EXCEPTION is ``test_runstate_byte_for_byte_unchanged`` — a "stays-true" regression guard,
NOT a lands-later behavior. It passes today (post_run already calls the unchanged write_runstate) and
must KEEP passing through Plan 10-04; it carries no xfail so a regression surfaces as a real failure.

Heavy imports (numpy/cv2/torch) are intentionally absent — Flask + opcomm + stdlib only.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(file_channel):
    """Flask test client over the file_channel tmp opcomm dir (verbatim from test_ui_run.py)."""
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel


# --- run-edge overlay_run stamping (OVD-02) ---------------------------------- #


def test_run_start_stamps_overlay_run(client):
    """POST /run start → overlay_run.running True + started_at a Unix-epoch float (Pitfall 3)."""
    from segugio.opcomm.channel import read_overlay_run

    c, ch = client
    resp = c.post("/run", data={"action": "start"})
    assert resp.status_code in (200, 204)
    ovr = read_overlay_run(str(ch["overlay_run"]))
    assert ovr.running is True
    assert isinstance(ovr.started_at, float)
    # > 1e9 proves a Unix wall-clock epoch, NOT seconds-since-boot (Pitfall 3 guard).
    assert ovr.started_at > 1_000_000_000


def test_run_stop_nulls_overlay_run(client):
    """POST start then stop → overlay_run.running False + started_at None."""
    from segugio.opcomm.channel import read_overlay_run

    c, ch = client
    c.post("/run", data={"action": "start"})
    resp = c.post("/run", data={"action": "stop"})
    assert resp.status_code in (200, 204)
    ovr = read_overlay_run(str(ch["overlay_run"]))
    assert ovr.running is False
    assert ovr.started_at is None


def test_runstate_byte_for_byte_unchanged(client, tmp_path):
    """runstate.json bytes are IDENTICAL to a baseline write_runstate (D-03, HARD invariant).

    The director reads runstate.json every tick — Phase 10 must not change a single byte of it.
    Baseline the exact bytes write_runstate produces for the start/stop edge, then assert POST /run
    produces byte-identical files.

    NOT xfail: this is a "stays-true" regression guard, not a lands-later behavior. The invariant
    holds TODAY (post_run already calls the unchanged write_runstate) and MUST keep holding after
    Plan 10-04 appends its overlay_run side-write strictly AFTER write_runstate. A future failure
    here = Phase 10 leaked into the director-read runstate.json (the exact thing D-03 forbids).
    """
    from segugio.opcomm.channel import write_runstate
    from segugio.opcomm.records import RunState

    c, ch = client

    # START edge.
    baseline_start = tmp_path / "baseline_start.json"
    write_runstate(
        str(baseline_start),
        RunState(action="start", just_started=True, just_stopped=False),
    )
    c.post("/run", data={"action": "start"})
    assert ch["runstate"].read_bytes() == baseline_start.read_bytes()

    # STOP edge.
    baseline_stop = tmp_path / "baseline_stop.json"
    write_runstate(
        str(baseline_stop),
        RunState(action="stop", just_started=False, just_stopped=True),
    )
    c.post("/run", data={"action": "stop"})
    assert ch["runstate"].read_bytes() == baseline_stop.read_bytes()


# --- GET /overlay-json contract (OVD-01) ------------------------------------- #


@pytest.mark.xfail(reason="impl lands in Plan 10-04", strict=False)
def test_overlay_json_payload_shape(client):
    """GET /overlay-json → 200, exact 6 keys, Cache-Control: no-store."""
    c, _ = client
    resp = c.get("/overlay-json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {
        "discipline",
        "fields",
        "running",
        "started_at",
        "server_now",
        "gen",
    }
    assert resp.headers["Cache-Control"] == "no-store"


@pytest.mark.xfail(reason="impl lands in Plan 10-04", strict=False)
def test_overlay_json_safe_default_when_absent(client):
    """Fresh channel (no files) → 200 + the safe-default payload (D-04)."""
    c, _ = client
    resp = c.get("/overlay-json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["running"] is False
    assert data["fields"] == {}
    assert data["discipline"] == "disc_tf"
    assert data["server_now"] is not None
    assert data["gen"] is not None


@pytest.mark.xfail(reason="impl lands in Plan 10-04", strict=False)
def test_overlay_json_safe_default_on_corrupt(client):
    """Torn score.json AND overlay_run.json → still 200, blank fields/running:false, server_now+gen present (D-04)."""
    c, ch = client
    ch["score"].write_text("{torn", encoding="utf-8")
    ch["overlay_run"].write_text("{torn", encoding="utf-8")
    resp = c.get("/overlay-json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["running"] is False
    assert data["fields"] == {}
    assert data["server_now"] is not None
    assert data["gen"] is not None


@pytest.mark.xfail(reason="impl lands in Plan 10-04", strict=False)
def test_overlay_json_fields_verbatim(client):
    """fields echoes operator-typed keys+values with NO server-side alias resolution (D-08)."""
    c, _ = client
    # An operator types an alias-cased key (SCT) + a sibling lowercase key (sct). The contract
    # echoes BOTH verbatim — the renderer (client) resolves aliases, never the console.
    c.post("/score", data={"discipline": "agility", "SCT": "42.0", "faults": "5"})
    resp = c.get("/overlay-json")
    assert resp.status_code == 200
    fields = resp.get_json()["fields"]
    assert fields.get("SCT") == "42.0"
    assert fields.get("faults") == "5"


@pytest.mark.xfail(reason="impl lands in Plan 10-04", strict=False)
def test_server_now_and_gen_present(client):
    """server_now is a float and gen is an int on every GET (the always-set clock + monotonic counter)."""
    c, _ = client
    for _ in range(2):
        data = c.get("/overlay-json").get_json()
        assert isinstance(data["server_now"], float)
        assert isinstance(data["gen"], int)


# --- gen monotonicity + restart re-anchor (OVD-02 / D-02) -------------------- #


def test_gen_bumps_on_run_and_score(client):
    """gen strictly increases on each /run and /score (the no-store ?t=<gen> nonce source)."""
    c, _ = client
    gen0 = c.get("/overlay-json").get_json()["gen"]
    c.post("/run", data={"action": "start"})
    gen1 = c.get("/overlay-json").get_json()["gen"]
    assert gen1 > gen0
    c.post("/score", data={"discipline": "disc_tf", "points": "10"})
    gen2 = c.get("/overlay-json").get_json()["gen"]
    assert gen2 > gen1


def test_gen_seeds_from_disk_on_restart(client):
    """A FRESH create_app seeds gen from the persisted overlay_run.json — never resets to 0 (D-02, Pitfall 2)."""
    from segugio.opcomm.channel import write_overlay_run
    from segugio.opcomm.records import OverlayRunDoc
    from segugio.ui.app import create_app

    _, ch = client
    write_overlay_run(
        str(ch["overlay_run"]),
        OverlayRunDoc(running=False, started_at=None, gen=7),
    )
    app2 = create_app(str(ch["dir"]))
    app2.config.update(TESTING=True)
    c2 = app2.test_client()
    c2.post("/run", data={"action": "start"})
    gen = c2.get("/overlay-json").get_json()["gen"]
    assert gen >= 8  # seeded from gen=7, bumped by the /run start — never reset to 0/1


def test_started_at_persists_across_restart(client):
    """started_at survives a console restart — a FRESH create_app re-anchors from disk (D-02)."""
    from segugio.ui.app import create_app

    c, ch = client
    c.post("/run", data={"action": "start"})
    started = c.get("/overlay-json").get_json()["started_at"]

    app2 = create_app(str(ch["dir"]))
    app2.config.update(TESTING=True)
    c2 = app2.test_client()
    data = c2.get("/overlay-json").get_json()
    assert data["running"] is True
    assert data["started_at"] == started
