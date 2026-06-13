"""SCV-01 — POST /score/preview pure render route (the server-side drift-guard).

Exercised via the Flask test client (no server, no heavy deps). ``POST /score/preview`` returns
``render_overlay_text(ScoreDoc(...))`` as ``text/plain`` and writes NOTHING — it is the source of
truth the client-side JS overlay mirror (09-03) asserts ``server === client`` against on
blur/submit. The per-discipline assertions below are BYTE-EXACT (note the double spaces from the
renderer f-strings) and double as the Wave-0 parity reference for the JS mirror.

Distinct from ``POST /score`` (test_ui_score.py): /score writes score.json + overlay.txt; this
route writes neither (test_score_preview_writes_no_file proves it).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(file_channel):
    """A Flask test client wired to a tmp_path opcomm dir (no server, no heavy deps)."""
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel


# --- byte-exact per-discipline render (SCV-01) ------------------------------- #


def test_score_preview_disc_tf(client):
    """disc Toss&Fetch → exactly 'Prese: 5  Zona: 3  Totale: 12' (double spaces, no file)."""
    c, _ = client
    resp = c.post(
        "/score/preview",
        data={"discipline": "disc_tf", "prese": "5", "zona": "3", "totale": "12"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    assert resp.get_data(as_text=True) == "Prese: 5  Zona: 3  Totale: 12"


def test_score_preview_disc_freestyle(client):
    """disc Freestyle → exactly 'Rex & Anna  Timer: 01:30' (name + double-space + Timer)."""
    c, _ = client
    resp = c.post(
        "/score/preview",
        data={"discipline": "disc_freestyle", "nome": "Rex & Anna", "timer": "01:30"},
    )
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "Rex & Anna  Timer: 01:30"


def test_score_preview_agility(client):
    """agility → exactly 'Tempo: 34.5 / SCT: 40.0  Faults: 5' (the slash + double-space layout)."""
    c, _ = client
    resp = c.post(
        "/score/preview",
        data={"discipline": "agility", "tempo": "34.5", "sct": "40.0", "faults": "5"},
    )
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "Tempo: 34.5 / SCT: 40.0  Faults: 5"


def test_score_preview_byte_reference(client):
    """The CANONICAL Wave-0 byte-parity reference for the 09-03 JS mirror.

    These exact strings (including every double space) are what the client-side JS
    render mirror MUST produce; the JS drift-check asserts server === client against
    this endpoint. If the renderer layout changes, this test and the JS mirror move
    together — this is the single contract both sides are pinned to.
    """
    c, _ = client
    cases = [
        (
            {"discipline": "disc_tf", "prese": "7", "zona": "2", "totale": "9"},
            "Prese: 7  Zona: 2  Totale: 9",
        ),
        (
            {"discipline": "disc_freestyle", "nome": "Fido", "timer": "02:00"},
            "Fido  Timer: 02:00",
        ),
        (
            {"discipline": "agility", "tempo": "31.2", "sct": "38.0", "faults": "0"},
            "Tempo: 31.2 / SCT: 38.0  Faults: 0",
        ),
    ]
    for data, expected in cases:
        resp = c.post("/score/preview", data=data)
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == expected, data


# --- boundary + purity (T-09-01-01 / T-09-01-03) ----------------------------- #


def test_score_preview_unknown_discipline_rejected(client):
    """An out-of-enum discipline is whitelisted at the boundary → 400, nothing rendered."""
    c, ch = client
    resp = c.post("/score/preview", data={"discipline": "../../etc", "prese": "1"})
    assert resp.status_code == 400
    assert "disciplina sconosciuta" in resp.get_data(as_text=True)
    # No file written (the pure route never writes anyway, but assert the channel stays clean).
    assert not ch["score"].exists()
    assert not ch["overlay"].exists()


def test_score_preview_writes_no_file(client):
    """After a POST /score/preview, score.json and overlay.txt do NOT exist (pure render).

    This is what distinguishes /score/preview from /score — the drift-guard NEVER touches the
    channel the orchestrator reads; it only reflects the operator's typed values back.
    """
    c, ch = client
    resp = c.post(
        "/score/preview",
        data={"discipline": "disc_tf", "prese": "5", "zona": "3", "totale": "12"},
    )
    assert resp.status_code == 200
    assert not ch["score"].exists()
    assert not ch["overlay"].exists()
