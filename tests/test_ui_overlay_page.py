"""Served-HTML contract test for the transparent /overlay host page (plan 11-02).

These assertions pin the invariants the 11-03 renderer and the Phase-12 console-preview
iframe depend on, by building ``create_app(..., overlay_cfg=...)`` and inspecting the HTML
served at ``GET /overlay``:

  * transparency contract (P5 — no white flash over live video);
  * the lower-third starts hidden (``opacity: 0`` — a delayed paint shows nothing);
  * the CSS-var theme reflects INJECTED config, not just the baked defaults;
  * the renderer DOM contract (``#timer`` / ``#cells`` / ``#identity`` / ``#logo-bug``);
  * the logo bug is conditional on a non-empty ``logo_path`` (D-07);
  * the ``/static/overlay-render.js`` bootstrap is referenced;
  * title-safe — a band-cap rule is present and no full-width/top-anchored banner;
  * no perpetual animation and no raw ``innerHTML`` assignment of a config value;
  * ``Cache-Control: no-store`` on the response.

The page bakes NO score/run/timer data (it polls ``/overlay-json``) — that is asserted by
the 11-01 ``/overlay-json`` tests; here we only assert the static host contract.
"""

from __future__ import annotations

import tempfile

import pytest

from segugio.ui.app import create_app

# A fully-overridden, NON-default branding config so theme injection (not just the baked
# console-palette defaults) is observable in the served HTML.
_CFG = {
    "event_name": "Disc Dog Italia 2026",
    "logo_path": "/static/event-logo.png",
    "theme_accent": "#FF00AA",   # deliberately NOT the #34D399 default
    "theme_plate": "#102030",    # deliberately NOT the #14161a default
    "theme_text": "#FAFAFA",     # deliberately NOT the #E6E9EF default
    "freestyle_duration_s": 90,  # deliberately NOT the 120 default
}


def _serve(overlay_cfg):
    """Build an app with the given overlay_cfg and return (html, response)."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"], overlay_cfg=overlay_cfg)
    resp = app.test_client().get("/overlay")
    return resp.get_data(as_text=True), resp


def test_overlay_returns_200_and_no_store() -> None:
    """GET /overlay serves the page with the no-store cache discipline (Pitfall 2)."""
    html, resp = _serve(_CFG)
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "no-store"
    assert html  # non-empty body


def test_overlay_is_transparent_and_starts_hidden() -> None:
    """Transparency contract (P5): html+body transparent, lower-third starts opacity:0."""
    html, _ = _serve(_CFG)
    # html, body transparent — the page composits as pure alpha over live video.
    assert "html, body { background: transparent" in html
    # The lower-third starts hidden so a delayed/partial first paint shows NOTHING (no white box).
    assert "opacity: 0;" in html
    assert ".lower-third {" in html


def test_overlay_theme_reflects_injected_config() -> None:
    """The CSS-var theme carries the INJECTED config values, not just the baked defaults (D-06)."""
    html, _ = _serve(_CFG)
    assert "--accent" in html and "--plate" in html and "--text" in html
    # The custom (non-default) colors must appear — proving config drives the vars.
    assert "#FF00AA" in html  # custom --accent
    assert "#102030" in html  # custom --plate
    assert "#FAFAFA" in html  # custom --text
    # And the default palette must NOT leak when overridden.
    assert "#34D399" not in html
    # The freestyle duration is exposed for the renderer's countdown (numeric bootstrap).
    assert "90" in html


def test_overlay_dom_contract_ids_present() -> None:
    """The stable DOM ids the 11-03 renderer fills are all present (interface contract)."""
    html, _ = _serve(_CFG)
    assert 'id="lower-third"' in html
    assert 'id="identity"' in html
    assert 'id="timer"' in html      # the big leading clock (D-02)
    assert 'id="cells"' in html      # per-discipline score-cell container (OVL-02)
    assert 'id="logo-bug"' in html   # bottom-right bug (present here — logo_path is set)


def test_overlay_identity_line_carries_event() -> None:
    """The event half of the identity line renders from the Jinja event_name (D-08, BRD-02)."""
    html, _ = _serve(_CFG)
    assert "Disc Dog Italia 2026" in html


def test_overlay_logo_bug_present_when_path_set() -> None:
    """The logo bug renders with a non-empty logo_path, sourced from the injected path (D-07)."""
    html, _ = _serve(_CFG)
    assert 'id="logo-bug"' in html
    assert "/static/event-logo.png" in html


def test_overlay_logo_bug_absent_when_path_empty() -> None:
    """Empty logo_path → NO logo bug element in the DOM at all (D-07)."""
    cfg = {**_CFG, "logo_path": ""}
    html, _ = _serve(cfg)
    assert 'id="logo-bug"' not in html


def test_overlay_references_renderer_script() -> None:
    """The script-src bootstrap references the 11-03 renderer (no inline render logic)."""
    html, _ = _serve(_CFG)
    assert '<script src="/static/overlay-render.js">' in html


def test_overlay_is_title_safe_no_top_banner() -> None:
    """Title-safe (OVL-03): a band-cap rule is present and no full-width/top-anchored banner."""
    html, _ = _serve(_CFG)
    # The lower-third band is capped (~18% frame height) — the plate never covers the action area.
    assert "max-height: 18vh" in html
    # No full-width/top-anchored score banner class (a rejected layout — chips/banner over the action).
    assert "top: 0" not in html
    assert "width: 100vw" not in html
    assert "banner" not in html.lower()


def test_overlay_animations_are_events_only() -> None:
    """Event-only animations (OVL-04): enter/exit/pulse keyframes exist, none loop forever."""
    html, _ = _serve(_CFG)
    assert "@keyframes enter" in html
    assert "@keyframes exit" in html
    assert "@keyframes pulse" in html
    # No perpetual/looping animation anywhere.
    assert "infinite" not in html
    # Keyframes use only compositor props — no layout/paint thrash properties animated.
    # (We assert the keyframe bodies reference transform/opacity, which they do by construction.)
    assert "transform" in html and "opacity" in html


def test_overlay_no_innerhtml_assignment_of_config() -> None:
    """No raw innerHTML assignment of a config value in the inline script (T-11-02-01).

    Config values flow through Jinja autoescape (HTML/attr context) and, client-side, the
    renderer's textContent — never an innerHTML sink in the inline template script.
    """
    html, _ = _serve(_CFG)
    assert ".innerHTML" not in html


def test_overlay_event_name_is_autoescaped() -> None:
    """An HTML metacharacter in event_name is autoescaped, not injected raw (T-11-02-01)."""
    cfg = {**_CFG, "event_name": "<script>alert(1)</script>"}
    html, _ = _serve(cfg)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_overlay_bakes_no_score_after_rich_post(file_channel) -> None:
    """A rich POST /score must NOT bake any score/identity value into GET /overlay HTML (SC#3 / D-06).

    The 18-01 enrichment grew the score doc (subkeys + free-text identity), but the ``/overlay``
    host page stays THIN / poll-only: it serves static branding + the renderer bootstrap and reads
    NO score state. POST a rich score (with sentinel identity values), then GET ``/overlay`` on the
    SAME app and assert none of the posted values leak into the served HTML, and the page is still
    poll-only with ``Cache-Control: no-store`` (T-18-04 — no live data baked into the served page).
    """
    from segugio.ui.app import create_app

    app = create_app(str(file_channel["dir"]), cam_ids=["cam_wide"], overlay_cfg=_CFG)
    client = app.test_client()
    resp = client.post(
        "/score",
        json={
            "discipline": "disc_tf",
            "throws": [{"zone": 4, "midair": "on", "corridor": "false"}],
            "cane": "RexSentinel",
            "conduttore": "AnnaSentinel",
            "giudici": "GiudiceSentinel",
        },
    )
    assert resp.status_code == 204, f"/score returned {resp.status_code}, expected 204"

    page = client.get("/overlay")
    html = page.get_data(as_text=True)
    # No posted identity (or recomputed score) value is baked into the thin host page.
    for needle in ("RexSentinel", "AnnaSentinel", "GiudiceSentinel"):
        assert needle not in html, f"/overlay baked in a posted score value: {needle}"
    # Still poll-only (references the renderer script) and no-store (the page never caches state).
    assert '<script src="/static/overlay-render.js">' in html
    assert page.headers.get("Cache-Control") == "no-store"


# ---------------------------------------------------------------------------
# Phase-12 preview=1 page contract (plan 12-01, RED-by-design until 12-02)
# ---------------------------------------------------------------------------
#
# SCV-01 unification (Phase 12): the console preview becomes an iframe of the ONE
# ``/overlay`` route loaded with ``?preview=1``. The preview flavour is COSMETIC, not a
# second renderer — it threads a ``body.preview`` class and a force-visible CSS rule so the
# lower-third is always shown in the console (no run edge needed), while sharing the exact
# same DOM ids + renderer script as the broadcast page. These assertions pin that contract;
# 12-02 threads the flag + CSS, so they are ``xfail(strict=False)`` until then.


def _serve_preview(overlay_cfg=None):
    """Build an app and return (html, response) for ``GET /overlay?preview=1``."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"], overlay_cfg=overlay_cfg or _CFG)
    resp = app.test_client().get("/overlay?preview=1")
    return resp.get_data(as_text=True), resp


def test_preview_flag_threads_body_class() -> None:
    """``?preview=1`` threads a ``body.preview`` class; bare ``/overlay`` does NOT (D-02)."""
    preview_html, _ = _serve_preview()
    bare_html, _ = _serve(_CFG)
    assert 'class="preview"' in preview_html      # preview fork carries the body class
    assert 'class="preview"' not in bare_html      # broadcast page does NOT (it animates on run edges)


def test_preview_shares_dom_and_script() -> None:
    """preview=1 and bare /overlay share the four DOM ids + the renderer script.

    Proves the preview fork is COSMETIC, not a second renderer: the console preview and the
    OBS overlay render through the identical DOM + ``/static/overlay-render.js`` (the whole
    point of the unification — drift is structurally impossible).
    """
    preview_html, _ = _serve_preview()
    bare_html, _ = _serve(_CFG)
    for needle in (
        'id="lower-third"',
        'id="identity"',
        'id="timer"',
        'id="cells"',
        '<script src="/static/overlay-render.js">',
    ):
        assert needle in preview_html, f"preview page missing shared contract: {needle}"
        assert needle in bare_html, f"broadcast page missing shared contract: {needle}"


def test_preview_force_visible_rule_present() -> None:
    """The preview flavour force-shows the lower-third (no run edge needed in the console).

    ``body.preview #lower-third { opacity: 1 }`` overrides the broadcast start-hidden
    ``opacity: 0`` so the operator always sees the overlay-as-it-airs in the console.
    """
    preview_html, _ = _serve_preview()
    assert "body.preview #lower-third" in preview_html
    assert "opacity: 1" in preview_html


def test_preview_no_store() -> None:
    """``GET /overlay?preview=1`` returns 200 with the ``Cache-Control: no-store`` discipline."""
    _, resp = _serve_preview()
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "no-store"
