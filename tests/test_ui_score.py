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
    resp = c.post(
        "/score",
        data={"discipline": "disc_tf", "prese": "5", "zona": "3", "totale": "12"},
    )
    assert resp.status_code in (200, 204)
    # score.json holds the structured operator input.
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.disc_tf
    assert doc.fields.get("prese") == "5"
    assert doc.fields.get("totale") == "12"
    # overlay.txt holds the rendered Italian line for OBS (values verbatim).
    overlay = ch["overlay"].read_text(encoding="utf-8")
    assert "5" in overlay and "12" in overlay and "Prese" in overlay


def test_post_score_freestyle(client):
    c, ch = client
    resp = c.post(
        "/score",
        data={"discipline": "disc_freestyle", "nome": "Rex & Anna", "timer": "01:30"},
    )
    assert resp.status_code in (200, 204)
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.disc_freestyle
    assert doc.fields.get("nome") == "Rex & Anna"
    overlay = ch["overlay"].read_text(encoding="utf-8")
    assert "Rex & Anna" in overlay and "01:30" in overlay


def test_post_score_agility(client):
    c, ch = client
    resp = c.post(
        "/score",
        data={"discipline": "agility", "tempo": "34.5", "sct": "40.0", "faults": "5"},
    )
    assert resp.status_code in (200, 204)
    doc = read_score(str(ch["score"]))
    assert doc.discipline == Discipline.agility
    assert doc.fields.get("tempo") == "34.5"
    overlay = ch["overlay"].read_text(encoding="utf-8")
    assert "34.5" in overlay and "40.0" in overlay


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
    assert "Disciplina" in html
    assert "Avvia run" in html and "Ferma run" in html
    assert "Forza" in html and "Rilascia" in html
    assert "Stato live" in html
    # the 3 per-discipline field labels (SCR-02)
    assert "Prese" in html and "Zona" in html and "Totale" in html
    assert "Nome" in html and "Timer" in html
    assert "Tempo" in html and "SCT" in html and "Faults" in html


def test_app_imports_nothing_heavy(monkeypatch):
    """segugio.ui.app imports only Flask + segugio.opcomm — no heavy stack.

    Robust to a heavy-installed env (the `.[heavy]` venv / the rig): the old check asserted
    `heavy not in sys.modules`, but sys.modules is process-global and the conftest availability
    probes (ndi_available → import cyndilib, gpu_available → import torch, …) load the heavy
    stack at collection, so that check fails even though the UI app imports none of it. Instead
    FORCE every heavy dep to raise on import and assert `import segugio.ui.app` STILL succeeds —
    if it reached for any of them it would raise ImportError. (Same pattern as test_imports.py.)
    """
    import importlib
    import sys

    for heavy in ("ultralytics", "torch", "cyndilib", "obsws_python", "cv2"):
        monkeypatch.setitem(sys.modules, heavy, None)  # importing it now raises ImportError
    # drop any cached UI modules so the import actually re-runs under the block
    for cached in list(sys.modules):
        if cached == "segugio.ui" or cached.startswith("segugio.ui."):
            monkeypatch.delitem(sys.modules, cached, raising=False)

    importlib.import_module("segugio.ui.app")  # must NOT raise — proves no heavy import attempted
