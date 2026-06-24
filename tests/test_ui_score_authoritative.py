"""SCC-01 — POST /score is the SOLE authority (validate RAW → 400-write-nothing → Decimal recompute).

Exercised via the Flask test client (no server, no heavy deps). The authoritative route:

  * validates RAW structured inputs FIRST; on any error returns 400 with ``{"errors": [...]}``
    and writes NOTHING — a previously-aired ``score.json``/``overlay.txt`` stays byte-identical
    (D-05 "punteggio precedente invariato" / broadcast integrity, T-16-05);
  * on valid input recomputes the total in Python (``score_calc.compute`` → Decimal) and atomically
    writes — the operator can never air a client-computed total (T-16-01/T-16-03);
  * a /score write bumps ``gen`` but PRESERVES ``running``/``started_at`` (WR-03 — a score is not a
    run edge);
  * round-trip total equality: computed total === ``overlay.txt`` line === ``/overlay-json`` total.

Plus the Open-Q1 acceptance: the legacy ``console.html`` flat-key form keeps round-tripping until
P17 retires it (a thin back-compat branch on the one /score route).
"""

from __future__ import annotations

import pytest

from segugio.opcomm.channel import read_overlay_run, read_score
from segugio.ui import score_calc

from tests._score_fixtures import FIXTURES, INVALID_FIXTURES


@pytest.fixture
def client(file_channel):
    """A Flask test client wired to a tmp_path opcomm dir (default profile = CSEN_DISC_PROFILE)."""
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel


def _seed_valid_score(c):
    """Air a valid disc_tf score so the 'write nothing on reject' test has a prior on-air state."""
    resp = c.post(
        "/score",
        json={"discipline": "disc_tf", "throws": [{"zone": 4, "midair": "on", "corridor": "false"}]},
    )
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)


# --- SCC-01: invalid → 400 AND write nothing (prev on-air byte-untouched) ----- #


def test_invalid_post_400_writes_nothing(client):
    c, ch = client
    # Seed a valid score first so there is a prior on-air state to protect.
    _seed_valid_score(c)
    score_before = ch["score"].read_bytes()
    overlay_before = ch["overlay"].read_bytes()

    # Now POST an INVALID one (bad zone band not in the profile).
    resp = c.post(
        "/score",
        json={"discipline": "disc_tf", "throws": [{"zone": 99}]},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None and "errors" in body and body["errors"]

    # The previous on-air files are BYTE-identical — nothing was written.
    assert ch["score"].read_bytes() == score_before
    assert ch["overlay"].read_bytes() == overlay_before


# --- SCC-01: valid → server recomputes Decimal total → atomic write ----------- #


def test_valid_post_recomputes_and_writes(client):
    c, ch = client
    fx = FIXTURES[0]  # disc_tf best-5-of-N
    resp = c.post("/score", json={"discipline": fx["discipline"], **fx["fields"]})
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)

    doc = read_score(str(ch["score"]))
    # The written total equals the Python recompute for the SAME inputs (server is authoritative).
    py = score_calc.compute(fx["discipline"], fx["fields"], score_calc.CSEN_DISC_PROFILE)
    assert doc.fields.get("totale") == py["totale"]


# --- SCC-01 / WR-03: gen bumps, running/started_at preserved ------------------- #


def test_score_preserves_run_state(client):
    c, ch = client
    # Start a run → running=True, started_at set, gen bumped.
    assert c.post("/run", data={"action": "start"}).status_code in (200, 204)
    before = read_overlay_run(str(ch["overlay_run"]))
    assert before.running is True and before.started_at is not None

    # POST a valid score → gen bumps but running/started_at survive (a score is not a run edge).
    fx = FIXTURES[1]
    assert c.post("/score", json={"discipline": fx["discipline"], **fx["fields"]}).status_code in (
        200,
        204,
    )
    after = read_overlay_run(str(ch["overlay_run"]))
    assert after.gen == before.gen + 1
    assert after.running is True
    assert after.started_at == before.started_at


# --- SCC-01 acceptance: round-trip total equality ----------------------------- #


def test_round_trip_total_equality(client):
    c, ch = client
    fx = FIXTURES[0]
    assert c.post("/score", json={"discipline": fx["discipline"], **fx["fields"]}).status_code in (
        200,
        204,
    )
    computed = score_calc.compute(fx["discipline"], fx["fields"], score_calc.CSEN_DISC_PROFILE)
    total = computed["totale"]

    # 1) overlay.txt rendered line carries the total.
    overlay = ch["overlay"].read_text(encoding="utf-8")
    assert total in overlay

    # 2) /overlay-json echoes the same total verbatim.
    resp = c.get("/overlay-json")
    assert resp.status_code == 200
    assert resp.get_json()["fields"]["totale"] == total


# --- P17 (D-11): the legacy flat-key path is RETIRED — the authoritative path is the only one - #


def test_legacy_flat_keys_now_rejected(client):
    c, ch = client
    # P17 retired the legacy back-compat branch (D-11): the old console.html #form-score posted
    # urlencoded FLAT keys (prese/zona/totale) that do NOT match the score_calc structured contract.
    # With the branch gone, such a body has NO valid `throws` for disc_tf → the authoritative path
    # validates it, finds no throws, and returns 400 + writes NOTHING (no producer posts this shape
    # anymore; a direct LAN POST of the flat shape is now correctly rejected, not silently aired).
    resp = c.post(
        "/score",
        data={"discipline": "disc_tf", "prese": "5", "zona": "3", "totale": "12"},
    )
    assert resp.status_code == 400, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body is not None and "errors" in body and body["errors"]
    # Nothing was written — the on-air score is untouched.
    assert not ch["score"].exists()


# --- validate parity helper for invalid fixtures (server gate) ----------------- #


def test_invalid_fixtures_rejected(client):
    """Every INVALID_FIXTURES item is rejected with 400 by the server gate (no write)."""
    c, ch = client
    for fx in INVALID_FIXTURES:
        resp = c.post("/score", json={"discipline": fx["discipline"], **fx["fields"]})
        assert resp.status_code == 400, f"{fx['discipline']} {fx['fields']} should be rejected"
