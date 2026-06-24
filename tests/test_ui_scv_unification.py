"""Phase-12 SCV-01 UNIFICATION structural contract (plan 12-01, Wave 0).

This is the failing-by-design structural target the implementation waves must satisfy:

  * 12-02 removes the ``POST /score/preview`` route + threads the ``?preview=1`` flag;
  * 12-03 rewrites ``console.html`` to EMBED ``<iframe src="/overlay?preview=1">`` and
    DELETE the byte-exact Python↔JS mirror (the ``gsd:scv01-mirror`` block and every
    ``mirror*/drift*/scvCurrentFields/updateScorePreview/scheduleScorePreview`` symbol).

The console preview becomes an iframe of the ONE ``/overlay`` route, so drift between the
console preview and the OBS overlay is structurally impossible (Milestone v1.2 decision):
``render_overlay_text`` survives ONLY as the ``overlay.txt`` fallback renderer.

These four tests are RED-by-design until 12-02/12-03 land (the 10-01 Wave-0 precedent):
each is ``xfail(strict=False)`` so the suite stays green pre-implementation and flips to
PASS — without an XPASS failure during a partial mid-wave implementation — once the work
ships. The value cross-check that proves the iframe is safe to share lives in
``test_ui_overlay_render.py::test_value_crosscheck`` (D-07).

The obsolete ``tests/test_score_preview.py`` (which exercised ONLY the now-removed
``POST /score/preview`` route, D-05) is deleted in this same plan; its byte-exact
reference strings are subsumed by the Task-2 value cross-check.
"""

from __future__ import annotations

import tempfile

import pytest

from segugio.ui.app import create_app

# Every identifier the 12-03 console rewrite DELETES — asserted ABSENT from the served
# console HTML so a partial deletion (a stray symbol left behind) fails the contract
# (Pitfall 1: assert every deleted symbol is gone, not just one).
_MIRROR_SYMBOLS_GONE = (
    "mirrorOverlayText",
    "updateScorePreview",
    "scheduleScorePreview",
    "scvCurrentFields",
    "driftCheck",
    "setDrift",
    "gsd:scv01-mirror",
    'id="drift-warning"',
    'id="overlay-preview"',
    "/score/preview",
)


def _serve_console():
    """Build the console app and return the served ``GET /`` HTML text.

    Mirrors the ``_serve`` helper in ``test_ui_overlay_page.py`` but fetches the operator
    console (``GET /``) instead of the overlay page — no server, no heavy deps.
    """
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().get("/")
    return resp.get_data(as_text=True)


def test_console_embeds_overlay_iframe():
    """The console preview is an IFRAME of the one /overlay route (drift impossible).

    SCV-01 unification: the served console embeds ``<iframe src="/overlay?preview=1">`` and
    carries the D-02 on-air label copy ("come va in onda" / "ON AIR") so the operator sees
    EXACTLY what OBS shows — one renderer, no mirror.
    """
    html = _serve_console()
    assert '<iframe src="/overlay?preview=1"' in html
    assert "come va in onda" in html
    assert "ON AIR" in html


def test_mirror_symbols_gone():
    """Every byte-exact Python↔JS mirror identifier is ABSENT from the served console.

    The whole drift-guard apparatus (the ``gsd:scv01-mirror`` block, the ``mirror*`` /
    ``updateScorePreview`` / ``scheduleScorePreview`` / ``scvCurrentFields`` / ``driftCheck``
    / ``setDrift`` symbols, the ``#drift-warning`` / ``#overlay-preview`` DOM, and the
    ``/score/preview`` route reference) is retired by the iframe reuse — assert each is gone.
    """
    html = _serve_console()
    for symbol in _MIRROR_SYMBOLS_GONE:
        assert symbol not in html, f"deleted mirror symbol still present: {symbol!r}"


def test_surviving_console_wiring_intact():
    """Load-bearing console wiring survives the mirror deletion (no over-deletion).

    The run start/stop buttons and the post() helper are NOT part of the mirror and must remain.
    P17 (D-11) retired the legacy inline #form-score (and its showFields discipline toggle + the
    direct post("/score") submit): score entry now lives in the shared modal component, opened by
    the "Inserisci / modifica punteggio" button. This test proves the deletion removed only the
    mirror + the retired legacy form, not the surviving operator controls.
    """
    html = _serve_console()
    assert "function post(" in html            # the post() helper survives (run controls reuse it)
    assert 'data-action="start"' in html
    assert 'data-action="stop"' in html
    assert "function showFields" not in html   # retired with the legacy #form-score (D-11)
    assert 'id="form-score"' not in html       # legacy inline score form retired
    assert "Inserisci / modifica punteggio" in html  # score entry moved into the shared modal


def test_score_preview_route_removed():
    """``POST /score/preview`` is unregistered → 404 or 405 (D-05).

    12-02 deletes the server-side drift-guard route entirely; the iframe needs no
    server round-trip, so the route is gone (not a redirect, not a 200).
    """
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().post("/score/preview", data={"discipline": "disc_tf"})
    assert resp.status_code in (404, 405)
