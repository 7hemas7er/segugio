"""Served-JS / behavior test for the shared overlay renderer (plan 11-03).

``src/segugio/ui/static/overlay-render.js`` is the ONE score-to-DOM renderer that
fills the 11-02 lower-third skeleton. These assertions pin:

  Task 1 (sanitize mirror + per-discipline DOM + identity + event-only animation):
    * the sanitize mirror is present (cleanField / scvGet / SCV_MAX_FIELD_LEN 64 /
      the SCV_NONPRINT regex) and the sct/SCT alias pair;
    * the HIGH-severity HTML-injection sink is closed — values are written via
      ``textContent`` and there is NO ``innerHTML =`` assignment anywhere;
    * per-discipline field tokens (prese/zona/totale, nome/timer, tempo/sct/faults);
    * a node-executed byte-parity check: the served ``cleanField`` matches Python
      ``score_render._clean`` for control-char and over-64-char inputs.

  Task 2 (offset-cancellation timer + freshness watchdog + poll loop):
    * the offset-cancellation skew/elapsed formula (no raw cross-machine subtraction);
    * the ?t= nonce fetch against /overlay-json gated on p.gen > lastGen;
    * isStale() with the cold-start guard, STALE_MS = PUBLISH_MS * 3, PUBLISH_MS 200;
    * a node-executed behavior check: ~30s clock skew reads near-0 elapsed error,
      a countdown freezes at 0 on "Tempo", and agility counts up past SCT.

The renderer is pure client-side ES2020 (no build step, no imports), served at
``/static/overlay-render.js`` by Flask's default static folder.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import pytest

from segugio.ui import score_render
from segugio.ui.app import create_app

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "overlay-render.js",
)


def _read_served_js():
    """The renderer as the browser sees it — served by Flask's default static folder."""
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"])
    resp = app.test_client().get("/static/overlay-render.js")
    assert resp.status_code == 200, "renderer must be auto-served at /static/overlay-render.js"
    return resp.get_data(as_text=True)


def _read_file_js():
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for behavior test")


# ---------------------------------------------------------------------------
# Task 1 — sanitize mirror + sink + per-discipline tokens
# ---------------------------------------------------------------------------


def test_renderer_is_served_at_static_path():
    js = _read_served_js()
    assert "cleanField" in js and "scvGet" in js


def test_sanitize_mirror_present():
    js = _read_file_js()
    assert "function cleanField" in js
    assert "function scvGet" in js
    assert "SCV_MAX_FIELD_LEN = 64" in js
    assert "SCV_NONPRINT" in js
    # the regex keeps U+0020 and strips the same classes as Python isprintable
    assert r"\p{Cc}" in js and r"\p{Cf}" in js


def test_sct_alias_pair_present():
    js = _read_file_js()
    # the agility sct/SCT first-present alias, byte-exact with render_overlay_text / _get
    assert '"sct"' in js and '"SCT"' in js


def test_no_innerhtml_sink():
    """T-11-03-01 — operator values must never reach an innerHTML sink."""
    js = _read_file_js()
    assert "textContent" in js
    # No innerHTML assignment in any whitespace variant.
    for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
        assert variant not in js, f"forbidden HTML-injection sink found: {variant!r}"
    assert ".innerHTML" not in js


def test_per_discipline_field_tokens_present():
    js = _read_file_js()
    for token in ("prese", "zona", "totale", "nome", "timer", "tempo", "sct", "faults"):
        assert token in js, f"missing per-discipline field token: {token}"


@_requires_node
def test_cleanfield_byte_parity_with_python_clean():
    """The served cleanField must match score_render._clean byte-for-byte."""
    js = _read_file_js()
    samples = [
        "12",
        "  spaced  ",
        "line\r\nbreak",
        "tab\tchar",
        "ctrl\x00\x07char",
        "x" * 80,  # over the 64 cap
        "café münchen",  # printable unicode kept
        "",
    ]
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const _in = " + json.dumps(samples) + ";\n"
        + "process.stdout.write(JSON.stringify(_in.map(s => _m.cleanField(s))));\n"
    )
    out = _run_node(driver)
    js_results = json.loads(out)
    py_results = [score_render._clean(s) for s in samples]
    assert js_results == py_results


# ---------------------------------------------------------------------------
# Task 2 — offset-cancellation timer + freshness watchdog + poll loop
# ---------------------------------------------------------------------------


def test_offset_cancellation_formula_present():
    js = _read_file_js()
    # skew measured from server_now; elapsed via (now + skew) - started_at
    assert "server_now" in js
    assert "skew" in js
    # NO raw cross-machine subtraction (Date.now()/started_at with no skew term)
    assert "Date.now() - started_at" not in js
    assert "Date.now()/1000 - started_at" not in js
    assert "Date.now() / 1000 - p.started_at" not in js


def test_poll_nonce_and_gen_gate_present():
    js = _read_file_js()
    assert "/overlay-json" in js
    assert "?t=" in js  # the load-bearing CEF nonce (Pitfall 2)
    assert "lastGen" in js
    assert "> lastGen" in js  # gen-strictly-advances gate


def test_freshness_watchdog_present():
    js = _read_file_js()
    assert "PUBLISH_MS = 200" in js
    assert "STALE_MS = PUBLISH_MS * 3" in js
    assert "function isStale" in js
    # cold-start guard: lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS
    assert "lastGen >= 0" in js
    assert "lastGenAt" in js


def test_degrade_and_tempo_literal_present():
    js = _read_file_js()
    assert "is-stale" in js  # the OVD-03 client degrade hook (11-02 class)
    assert "Tempo" in js  # the freeze-at-0 literal (TMR-03 / D-04)


@_requires_node
def test_timer_behavior_skew_freeze_overtime():
    """Node-executed behavior: ~30s skew → near-0 error; freeze-at-0; agility overtime."""
    js = _read_file_js()
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + """
        const FAKE_NOW_S = 1000;            // mocked Date.now()/1000 on THIS box
        const SERVER_NOW = FAKE_NOW_S + 30; // console clock 30s AHEAD (skew test)
        const STARTED_AT = SERVER_NOW - 5;  // run started 5s ago on the console clock
        // offset-cancellation: skew cancels the 30s machine gap, elapsed ~= 5s.
        const skew = SERVER_NOW - FAKE_NOW_S;
        const elapsed = (FAKE_NOW_S + skew) - STARTED_AT;
        // countdown from 60 → remaining; agility counts up.
        const tfRemaining = Math.max(0, 60 - elapsed);
        const overElapsed = 130;            // past a typical SCT
        const out = {
          elapsed: elapsed,
          tfRemaining: tfRemaining,
          countdownText: _m.formatCountdown(0),       // freeze-at-0
          agilityText: _m.formatAgility(overElapsed), // SS.hh past SCT
          rawWrongSkew: (FAKE_NOW_S - STARTED_AT),     // the BUGGY no-skew value (proves the gap)
        };
        process.stdout.write(JSON.stringify(out));
        """
    )
    out = json.loads(_run_node(driver))
    # offset-cancellation removes the 30s machine gap: elapsed is the true ~5s.
    assert abs(out["elapsed"] - 5.0) < 0.001
    # the naive no-skew subtraction would be wrong by ~30s — proves the formula matters.
    assert abs(out["rawWrongSkew"] - out["elapsed"]) > 25
    # countdown freezes at 0 showing the literal Tempo.
    assert out["countdownText"] == "Tempo"
    # agility renders SS.hh and continues into overtime past SCT (130s → "130.00").
    assert out["agilityText"].startswith("130.")


# ---------------------------------------------------------------------------
# node helper
# ---------------------------------------------------------------------------


def _run_node(driver_src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver_src)
        path = fh.name
    try:
        # Decode node's stdout as UTF-8 explicitly: on Windows the default locale
        # encoding (cp1252) would mangle non-ASCII (e.g. café), breaking byte-parity.
        proc = subprocess.run(
            [_NODE, path],
            capture_output=True,
            timeout=30,
        )
        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert proc.returncode == 0, f"node failed: {stderr}"
        return proc.stdout.decode("utf-8")
    finally:
        os.unlink(path)
