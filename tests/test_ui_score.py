"""SCR-02 — Flask POST /score writes expected file content per discipline (display-only).

Exercised via the Flask test client (no server, no heavy deps). The app factory
``create_app(channel_dir)`` injects a tmp_path file dir so each POST writes ``score.json``
(structured) AND ``overlay.txt`` (the rendered Italian line for OBS-05). Also asserts the
GET / page is served and carries the Italian console controls (Task 3 template).
"""

from __future__ import annotations

import json

import pytest

from segugio.opcomm.channel import read_score
from segugio.opcomm.records import Discipline


@pytest.fixture
def client(file_channel):
    """A Flask test client wired to a tmp_path opcomm dir (no server)."""
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel


# --- POST /score per discipline (SCR-02) ------------------------------------- #


def test_post_score_disc_tf(client):
    c, ch = client
    # P17 (D-11): the legacy flat-key path is retired — POST the AUTHORITATIVE structured JSON body
    # (one zone-3 throw with a midair bonus → 3 + 0.5 = 3.5 recomputed by the server).
    resp = c.post(
        "/score",
        json={"discipline": "disc_tf", "throws": [{"zone": 3, "midair": "on", "corridor": "false"}]},
    )
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)
    # score.json holds the SERVER-recomputed total (never a client-supplied one).
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.disc_tf
    assert doc.fields.get("totale") == "3.5"
    # overlay.txt holds the rendered Italian line for OBS (the recomputed total verbatim).
    overlay = ch["overlay"].read_text(encoding="utf-8")
    assert "3.5" in overlay and "Prese" in overlay


def test_post_score_freestyle(client):
    c, ch = client
    resp = c.post(
        "/score",
        json={
            "discipline": "disc_freestyle",
            "team": "10",
            "dog": "10",
            "player": "10",
            "catch": "10",
            "adjustment": "0",
            "nome": "Rex & Anna",
        },
    )
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.disc_freestyle
    # Four maxed categories sum to exactly freestyle_max (40, quantized to the 0.01 grid) — recomputed.
    assert doc.fields.get("totale") == "40.00"


def test_post_score_agility(client):
    c, ch = client
    resp = c.post(
        "/score",
        json={
            "discipline": "agility",
            "tempo": "00:34.50",
            "sct": "00:30.00",
            "course_faults": "5",
        },
    )
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.agility
    # count_up: over SCT by 4.5s → ceil = 5 time-faults; + 5 course faults = 10 (server-recomputed).
    assert doc.fields.get("faults") == "10"


def test_post_score_unknown_discipline_rejected(client):
    """An out-of-enum discipline is whitelisted at the boundary → 400 (T-05-05-01)."""
    c, ch = client
    resp = c.post("/score", data={"discipline": "../../etc", "prese": "1"})
    assert resp.status_code == 400
    # nothing written
    assert not ch["score"].exists()


# --- GET / page content (Task 3 template, exercised here) -------------------- #


def test_index_serves_italian_console(client):
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Italian console controls (D-04 four concerns on one page).
    assert "Avvia run" in html and "Ferma run" in html
    # MVW-04 (Phase 9 / 09-02): the blind "Forza {cam}" text buttons were REMOVED — the whole tile
    # is now the force control (asserted in test_ui_tablet_layout.py). "Rilascia (auto)" stays.
    assert "Rilascia" in html
    # P17 (D-07/D-08/D-11): the legacy inline #form-score (discipline selector + flat field labels)
    # is RETIRED. The Punteggio card now carries a read-only on-air readout + a modal-open button
    # that opens the native <dialog> mounting the SAME shared score-entry partial as /score-entry.
    assert 'id="form-score"' not in html  # legacy form gone
    assert "Inserisci / modifica punteggio" in html  # the modal-open button
    assert "_score-entry-form.html" not in html  # the include resolves (rendered, not literal)
    assert 'id="score-dialog"' in html  # the native dialog hosting the shared partial
    assert 'id="score-entry-root"' in html  # the component mount target (from the included partial)


def test_app_imports_nothing_heavy(monkeypatch, tmp_path):
    """HARD GATE 2 (D-09 gate 2): segugio.ui.app imports AND STARTS with no heavy stack.

    Robust to a heavy-installed env (the `.[heavy]` venv / the rig): the old check asserted
    `heavy not in sys.modules`, but sys.modules is process-global and the conftest availability
    probes (ndi_available → import cyndilib, gpu_available → import torch, …) load the heavy
    stack at collection, so that check fails even though the UI app imports none of it. Instead
    FORCE every heavy dep to raise on import and assert `import segugio.ui.app` STILL succeeds —
    if it reached for any of them it would raise ImportError. (Same pattern as test_imports.py.)

    numpy is in the heavy-block tuple (RESEARCH / Pitfall 2) — without it the gate could pass
    merely because numpy happens to be installed in the env (a false green); forcing it absent
    proves the console truly never reaches for it.

    This asserts the console STARTS, not merely imports (D-09 gate 2 = "console starts"): under
    the heavy-absent block we call create_app(tmp) → a real Flask app → a GET /status that
    returns 200. A request completing here proves the app started end-to-end with the entire
    orchestrator stack (ultralytics/torch/numpy/cv2/cyndilib/obsws_python) absent. This LOCKS the
    clean Flask + segugio.opcomm-only import surface as a regression gate BEFORE Phase 8 widens it
    with the GET /preview routes (T-07-02-01 / RBT-04 never-crash, high-severity if it regresses).
    """
    import importlib
    import sys

    for heavy in ("ultralytics", "torch", "cyndilib", "obsws_python", "cv2", "numpy"):
        monkeypatch.setitem(sys.modules, heavy, None)  # importing it now raises ImportError
    # drop any cached UI modules so the import actually re-runs under the block
    for cached in list(sys.modules):
        if cached == "segugio.ui" or cached.startswith("segugio.ui."):
            monkeypatch.delitem(sys.modules, cached, raising=False)

    app_mod = importlib.import_module("segugio.ui.app")  # must NOT raise — no heavy import attempted

    # START-check (not just import): create_app must build a Flask app and serve a request with
    # the whole heavy stack still absent. /status is the D-11 reverse-channel poll route; it
    # read_status-safe-defaults to SAFE on the absent file, so it returns 200 without any feed.
    app = app_mod.create_app(str(tmp_path))
    client = app.test_client()
    resp = client.get("/status")
    assert resp.status_code == 200  # the console STARTED and served under the heavy-absent block
