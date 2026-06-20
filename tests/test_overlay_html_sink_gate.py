"""RBT-06 SC#4 — the broadcast overlay never reaches an HTML-injection sink.

Operator-entered score values + branding cross from the console into the CEF browser-source
overlay (untrusted text → broadcast HTML). The T-14-xss mitigation is two-pronged:

  1. JS sink — ``overlay-render.js`` writes operator score values via ``textContent`` and
     NEVER via ``innerHTML`` (a pure source assertion, no node needed).
  2. Jinja sink — the STATIC branding (``event_name`` / ``logo_path``) rendered into
     ``overlay.html`` is Jinja-autoescaped, so a crafted ``<script>`` in ``event_name`` is
     served ESCAPED (``&lt;script&gt;``), never raw.

Both are REGRESSION assertions over already-shipped behavior (Phase 11/13), made into a
named per-criterion gate (D-03) so a regression in either sink cannot pass silently.
Flask test_client only — no heavy import (RBT-07 crash-isolation stays green).
"""

from __future__ import annotations

import os
import tempfile

from segugio.ui.app import create_app

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "overlay-render.js",
)


def _read_file_js() -> str:
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def test_no_innerhtml_sink():
    """SC#4 (T-14-xss) — operator values must never reach an innerHTML sink in the renderer."""
    js = _read_file_js()
    assert "textContent" in js, "the renderer must write score values via textContent"
    # No innerHTML assignment in any whitespace variant.
    for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
        assert variant not in js, f"forbidden HTML-injection sink found: {variant!r}"
    assert ".innerHTML" not in js


def test_overlay_jinja_autoescapes_branding():
    """SC#4 (T-14-xss) — a crafted event_name renders ESCAPED on GET /overlay, never raw.

    ``event_name`` is injected into the ``#identity`` div via Jinja (``{{ event_name }}``),
    autoescape ON. A crafted ``<script>x</script>`` must be served as ``&lt;script&gt;`` and
    must NOT appear raw — proving the branding sink cannot inject markup into the broadcast.
    """
    tmp = tempfile.mkdtemp()
    payload = "<script>x</script>"
    app = create_app(tmp, cam_ids=["cam_wide"], overlay_cfg={"event_name": payload})
    resp = app.test_client().get("/overlay")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # The raw <script> must NOT survive into the served overlay HTML.
    assert payload not in html, "raw <script> reached the overlay — Jinja autoescape is OFF (T-14-xss)"
    # The escaped form proves autoescape ran at the identity sink.
    assert "&lt;script&gt;x&lt;/script&gt;" in html, "event_name was not Jinja-autoescaped"
