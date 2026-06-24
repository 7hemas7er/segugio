"""UXT-01 / MVW-04 / WHY-03 — served-HTML contracts for the tablet-first console restyle.

Exercised via the Flask test client (no server, no heavy deps), mirroring ``test_ui_score.py``.
The 09-02 plan restyles ``console.html`` to a landscape Multiview-LEFT + sidebar-RIGHT layout
(D-01), the iPad/Safari touch contract (UXT-01), the status palette + typography migration, the
5 grayscale-safe tile states (D-04), the tap-to-force gesture (MVW-04), and the per-tile dog-lock
bbox SVG scaffold (WHY-03). These assert every contract on the SERVED HTML.

Test selectors: ``-k viewport`` / ``-k touch`` / ``-k weight`` / ``-k force`` / ``-k tile_state``
/ ``-k bbox``.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(preview_channel):
    """A Flask test client wired to a tmp_path opcomm dir with a 2-cam whitelist (no server)."""
    from segugio.ui.app import create_app

    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    app.config.update(TESTING=True)
    return app.test_client(), preview_channel


def _html(client) -> str:
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


# --- viewport + touch contract (UXT-01, VERIFIED HIGH) ----------------------- #


def test_viewport_meta_is_tablet_safe(client):
    """Viewport carries ``viewport-fit=cover`` and FORBIDS ``user-scalable=no`` / ``maximum-scale``."""
    html = _html(client)
    assert "viewport-fit=cover" in html
    # FORBIDDEN: iOS ignores them AND they fail WCAG 1.4.4/1.4.10.
    assert "user-scalable=no" not in html
    assert "maximum-scale" not in html


def test_touch_action_and_targets(client):
    """Served HTML carries ``touch-action: manipulation`` and the five sidebar block ids."""
    html = _html(client)
    assert "touch-action: manipulation" in html
    # The five sidebar content blocks (D-01 order): reason → leaderboard → auto-wants →
    # switch-history → score form. The first four are scaffold containers (filled 09-03/09-04).
    for block_id in ('id="reason"', 'id="leaderboard"', 'id="auto-wants"', 'id="switch-history"'):
        assert block_id in html, block_id
    # P17 (D-07/D-11): the legacy inline #form-score was retired; the Punteggio card now carries the
    # read-only on-air readout + the modal-open button (score entry lives in the shared modal).
    assert 'id="onair-score"' in html  # the read-only on-air readout replaces the inline form
    assert "Inserisci / modifica punteggio" in html  # the modal-open button
    # The two-region layout + reflow exist.
    assert 'class="layout"' in html
    assert "@media" in html


def test_no_500_or_600_font_weight(client):
    """No ``font-weight: 500`` / ``600`` anywhere; ``legend`` is 700 (was 600)."""
    html = _html(client)
    assert "font-weight: 500" not in html
    assert "font-weight: 600" not in html
    assert "font-weight:500" not in html
    assert "font-weight:600" not in html
    # legend is an emphatic section label → 700.
    assert "legend { font-weight: 700" in html or "legend{font-weight:700" in html


def test_palette_migrated_to_status_hues(client):
    """The status hues appear and the legacy LIVE-red ``#b23b3b`` is retired for status."""
    html = _html(client)
    assert "#34D399" in html  # LIVE green
    assert "#F0B429" in html  # FORZATA amber
    assert "#56B4E9" in html  # auto-wants blue
    assert "#9b2c2c" in html  # migrated destructive (was #b23b3b)
    # #b23b3b is no longer used (retired for .tile.live / .danger).
    assert "#b23b3b" not in html


# --- tap-to-force gesture (MVW-04, D-02/D-03) -------------------------------- #


def test_force_buttons_removed_tile_is_force_target(client):
    """The blind ``Forza {cam}`` text buttons are gone; the whole tile is the force control."""
    html = _html(client)
    # No blind text-button label and no .force-btn elements.
    assert "Forza " not in html
    assert "force-btn" not in html
    # Each tile is a role="button" force target with the forceCam/post wiring present.
    assert 'role="button"' in html
    assert "forceCam" in html
    assert 'post("/command", { force_cam:' in html
    # FORBID touchstart/touchend synthetic-click handlers (double-fire live actions on iOS).
    assert "touchstart" not in html
    assert "touchend" not in html
    # Rilascia (auto) stays the large always-visible undo posting {release:"1"}.
    assert 'id="rilascia"' in html
    assert 'post("/command", { release: "1" }' in html


# --- 5-state tiles (D-04) ---------------------------------------------------- #


def test_tile_state_css_present(client):
    """The 5 grayscale-safe tile-state classes exist with distinct FORZATA vs LIVE treatments."""
    html = _html(client)
    # The new state classes (extending the existing .tile.live / .tile.dead).
    assert ".tile.forzata" in html
    assert ".tile.auto-wants" in html
    assert ".tile.stale" in html
    # FORZATA (amber + lock + ribbon) and LIVE (green + ●) are visually distinct, not the same.
    assert ".tile.live { border-color: #34D399" in html
    assert "border-color: #F0B429" in html  # FORZATA amber border
    assert "border-style: dashed" in html  # auto-wants dashed
    assert ".ribbon" in html  # FORZATA corner ribbon (3rd redundant channel)
    # The class dispatcher exists.
    assert "setTileState" in html


# --- dog-lock bbox SVG (WHY-03, zero JS letterbox math) ---------------------- #


def test_bbox_svg_per_tile(client):
    """One inline ``<svg viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet">`` per cam tile."""
    html = _html(client)
    # The two whitelisted cams each get one bbox SVG.
    assert html.count('viewBox="0 0 1 1"') == 2
    assert html.count('preserveAspectRatio="xMidYMid meet"') == 2
    # Non-scaling stroke rect (zero JS letterbox math) + the updateBbox helper.
    assert 'vector-effect="non-scaling-stroke"' in html
    assert "updateBbox" in html
    # The tile <img> uses object-fit:contain (load-bearing: meet-scaling == contain letterbox).
    assert "object-fit: contain" in html


def test_index_still_serves_italian_console(client):
    """No regression on the surviving Italian controls; P17 moved score entry into the modal.

    P17 (D-07/D-11) retired the legacy inline #form-score (the discipline selector + the 3
    per-discipline flat field sets: Prese/Zona, Nome, Tempo/SCT/Faults). Those fields now live in
    the shared score-entry component built client-side inside the modal, so they are NOT in the
    static console HTML. What remains on the page: the run/override controls, the live status, and
    the new read-only on-air readout (Disciplina + Totale) + the modal-open button.
    """
    html = _html(client)
    assert "Avvia run" in html and "Ferma run" in html
    assert "Rilascia" in html
    assert "Stato live" in html
    # The read-only on-air readout (D-07): discipline + total labels remain on the page.
    assert "Punteggio in onda" in html
    assert "Disciplina" in html and "Totale" in html
    # The modal-open button replaces the inline form.
    assert "Inserisci / modifica punteggio" in html
    # The retired legacy inline form fields are gone from the static console HTML.
    assert "Prese" not in html and "Zona" not in html
    assert "Faults" not in html
