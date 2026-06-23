"""SCC-03 / D-09 — node-vs-Python drift-guard for the ADVISORY ``score-calc.js`` port.

``src/segugio/ui/static/score-calc.js`` is a BYTE-EXACT advisory port of
``segugio.ui.score_calc.compute``/``validate`` for the live running-total UX. It must NEVER become a
second authority (Pitfall 2 / double source of truth) — this test pins it honest: for every shared
fixture, the served JS ``.compute``/``.validate`` returns results byte-identical to the Python
authority. Decimal-equivalence in JS (no ``Number`` float drift on ``0.5`` / best-N / ``0.01`` grid)
is part of what the guard catches.

Clones the proven ``tests/test_ui_overlay_render.py`` node-runner machinery (``_run_node`` UTF-8
helper, ``_requires_node`` skip). The ``.decode("utf-8")`` on node's stdout is load-bearing on
Windows (cp1252 would mangle non-ASCII like "Rex & Anna").
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from decimal import Decimal

import pytest

from segugio.ui import score_calc
from segugio.ui.app import create_app

from tests._score_fixtures import FIXTURES, INVALID_FIXTURES, PROFILE_JSON


def _profile_from_json(pj: dict) -> score_calc.ScoringProfile:
    """Build the Python ScoringProfile authority from a decimal-STRING JSON profile.

    Lets a fixture carry its own ``profile_json`` (WR-02: a ``deduct_from_100`` agility profile)
    so the node-vs-Python parity tests can exercise a compute branch the default count_up profile
    never reaches. Mirrors the decimal-string transport shape exactly — every numeric becomes a
    ``Decimal`` so the Python side stays float-free, matching the JS ``Dec``-from-string port.
    """
    return score_calc.ScoringProfile(
        units=pj["units"],
        zones=tuple((b, Decimal(p)) for b, p in pj["zones"]),
        bonuses=tuple((k, Decimal(v)) for k, v in pj["bonuses"]),
        per_throw_cap=(Decimal(pj["per_throw_cap"]) if pj["per_throw_cap"] is not None else None),
        count_best_n=pj["count_best_n"],
        freestyle_cats=tuple(
            (n, Decimal(lo), Decimal(hi), Decimal(inc)) for n, lo, hi, inc in pj["freestyle_cats"]
        ),
        freestyle_max=(Decimal(pj["freestyle_max"]) if pj["freestyle_max"] is not None else None),
        agility_model=pj["agility_model"],
        time_fault_rate=Decimal(pj["time_fault_rate"]),
        fault_value=Decimal(pj["fault_value"]),
        elimination_sentinel=pj["elimination_sentinel"],
    )


def _py_profile_for(fx: dict) -> score_calc.ScoringProfile:
    """The Python profile a fixture runs against — its own ``profile_json`` or the CSEN default."""
    pj = fx.get("profile_json")
    return _profile_from_json(pj) if pj is not None else score_calc.CSEN_DISC_PROFILE

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "score-calc.js",
)


def _read_file_js():
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_served_js():
    """score-calc.js as the browser sees it — served by Flask's default static folder."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().get("/static/score-calc.js")
    assert resp.status_code == 200, "score-calc.js must be auto-served at /static/score-calc.js"
    return resp.get_data(as_text=True)


_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for parity test")


def _run_node(driver_src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver_src)
        path = fh.name
    try:
        # Decode node's stdout as UTF-8 explicitly: on Windows the default locale encoding
        # (cp1252) would mangle non-ASCII, breaking byte-parity.
        proc = subprocess.run([_NODE, path], capture_output=True, timeout=30)
        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert proc.returncode == 0, f"node failed: {stderr}"
        return proc.stdout.decode("utf-8")
    finally:
        os.unlink(path)


# --- static-analysis asserts (no node needed) --------------------------------- #


def test_score_calc_served_and_sentinel_present():
    """The advisory port is served, dual-exported, sentinel-wrapped, and Number-free on totals."""
    served = _read_served_js()
    assert "window.SEGUGIO_SCORE_CALC" in served
    assert "module.exports" in served
    js = _read_file_js()
    assert "// ===== gsd:score-calc-mirror:start =====" in js
    assert "// ===== gsd:score-calc-mirror:end =====" in js
    assert "function compute" in js
    assert "function validate" in js
    # No float arithmetic on totals (drift-guard would catch it, but pin the house rule too).
    assert "parseFloat" not in js


# --- node parity: compute ----------------------------------------------------- #


@_requires_node
def test_compute_byte_parity_with_python():
    """score-calc.js .compute === score_calc.compute on the FLAT summary keys, all disciplines."""
    js = _read_file_js()
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const _in = " + json.dumps(FIXTURES) + ";\n"
        + "const _p = " + json.dumps(PROFILE_JSON) + ";\n"
        + "process.stdout.write(JSON.stringify(_in.map(f => _m.compute(f.discipline, f.fields, f.profile_json || _p))));\n"
    )
    js_out = json.loads(_run_node(driver))
    py_out = [
        score_calc.compute(f["discipline"], f["fields"], _py_profile_for(f))
        for f in FIXTURES
    ]
    assert len(js_out) == len(py_out)
    for j, p, fx in zip(js_out, py_out, FIXTURES):
        for key in ("totale", "prese", "zona", "faults", "result"):
            if key in p:
                assert j.get(key) == p[key], (
                    f"{fx['discipline']} key {key!r}: js={j.get(key)!r} py={p[key]!r}"
                )


# --- node parity: validate ---------------------------------------------------- #


@_requires_node
def test_validate_parity():
    """score-calc.js .validate === score_calc.validate (same {field} set) for invalid inputs."""
    js = _read_file_js()
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const _in = " + json.dumps(INVALID_FIXTURES) + ";\n"
        + "const _p = " + json.dumps(PROFILE_JSON) + ";\n"
        + "process.stdout.write(JSON.stringify(_in.map(f => _m.validate(f.discipline, f.fields, f.profile_json || _p))));\n"
    )
    js_out = json.loads(_run_node(driver))
    py_out = [
        score_calc.validate(f["discipline"], f["fields"], _py_profile_for(f))
        for f in INVALID_FIXTURES
    ]
    assert len(js_out) == len(py_out)
    for j, p, fx in zip(js_out, py_out, INVALID_FIXTURES):
        js_fields = [e["field"] for e in j]
        py_fields = [e["field"] for e in p]
        assert js_fields == py_fields, (
            f"{fx['discipline']}: js fields {js_fields} != py fields {py_fields}"
        )
        # The expected error field must surface on both sides.
        assert fx["error_field"] in py_fields
        assert fx["error_field"] in js_fields


# --- node parity: also confirm VALID fixtures produce NO validate errors ------- #


@_requires_node
def test_validate_parity_valid_fixtures_clean():
    """Every VALID fixture validates clean (empty list) on both sides."""
    js = _read_file_js()
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const _in = " + json.dumps(FIXTURES) + ";\n"
        + "const _p = " + json.dumps(PROFILE_JSON) + ";\n"
        + "process.stdout.write(JSON.stringify(_in.map(f => _m.validate(f.discipline, f.fields, f.profile_json || _p))));\n"
    )
    js_out = json.loads(_run_node(driver))
    py_out = [
        score_calc.validate(f["discipline"], f["fields"], _py_profile_for(f))
        for f in FIXTURES
    ]
    for j, p, fx in zip(js_out, py_out, FIXTURES):
        assert p == [], f"py: valid fixture {fx['discipline']} unexpectedly errored: {p}"
        assert j == [], f"js: valid fixture {fx['discipline']} unexpectedly errored: {j}"
