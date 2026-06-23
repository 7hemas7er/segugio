"""SCE-01/02/03/05 — shared score-entry COMPONENT + dedicated /score-entry page (Plan 16-02).

STUBS landed in Wave 0 (Plan 16-01) so the gates EXIST for the component plan to turn green.
``src/segugio/ui/static/score-entry.js`` (the ONE ``mount(root, cfg)`` factory), the
``score-entry.html`` thin host, and the ``GET /score-entry`` route are all built in Plan 16-02 —
these tests ``pytest.skip("implemented in 16-02")`` until then so the file COLLECTS green now.

Clones the served-JS / node helper machinery from ``tests/test_ui_overlay_render.py``.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from segugio.ui.app import create_app

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "score-entry.js",
)

_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for behavior test")

# Plan 16-02 builds score-entry.js / score-entry.html / GET /score-entry. Until then, skip.
_PLAN_02 = pytest.mark.skip(reason="implemented in 16-02")


def _read_file_js():
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_served_js():
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().get("/static/score-entry.js")
    assert resp.status_code == 200, "score-entry.js must be auto-served at /static/score-entry.js"
    return resp.get_data(as_text=True)


# --- SCE-01: dual export + thin host ------------------------------------------ #


@_PLAN_02
def test_dual_export_and_thin_host():
    """score-entry.js exports mount on window AND module.exports; /score-entry host has no <input>."""
    js = _read_file_js()
    assert "window.SEGUGIO_SCORE_ENTRY" in js
    assert "module.exports" in js
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    assert "<input" not in html, "thin host must carry no <input> of its own (component builds them)"


# --- SCE-02: disciplines driven by the injected profile ----------------------- #


@_PLAN_02
def test_disciplines_from_profile():
    """disc-dog config → T&F + Freestyle; agility config → Agility only (D-06)."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    html = app.test_client().get("/score-entry").get_data(as_text=True)
    # disc-dog default offers both disc disciplines.
    assert "disc_tf" in html and "disc_freestyle" in html


# --- SCE-02 / SCE-05: no innerHTML sink for operator values ------------------- #


@_PLAN_02
def test_no_innerhtml_sink():
    """T-16 / XSS — operator values via textContent, never an innerHTML sink."""
    js = _read_file_js()
    assert "textContent" in js
    for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
        assert variant not in js, f"forbidden HTML-injection sink found: {variant!r}"


# --- SCE-03: live advisory total updates in place ----------------------------- #


@_PLAN_02
@_requires_node
def test_live_total_advisory():
    """The live advisory total recomputes IN PLACE on input (labeled non-authoritative)."""
    js = _read_file_js()
    assert "SEGUGIO_SCORE_CALC" in js or "compute" in js
