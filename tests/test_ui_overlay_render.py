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


# The per-discipline (discipline → field key lists) the value cross-check compares.
# These mirror render_overlay_text's _get key lists EXACTLY (incl. the sct/SCT alias),
# expressed as the JS-side scvGet calls via DISCIPLINE_CELLS[discipline]. The cross-check
# compares the sanitized VALUES the two renderers compute for these keys — NOT the
# f-string layout (JS fills DOM cells, Python builds a line); the value is the shared
# contract the Phase-12 iframe reuse depends on (D-07).
_CROSSCHECK_PAYLOAD = [
    # disc_tf: a control char (dropped), an over-64-char value (capped identically), plain.
    {
        "discipline": "disc_tf",
        "fields": {"prese": "12", "zona": "x" * 80, "totale": "7\x00"},
        "keys": {"prese": ["prese"], "zona": ["zona"], "totale": ["totale"]},
    },
    # disc_freestyle: a UTF-8 value (café preserved — the _run_node UTF-8 decode is load-bearing).
    {
        "discipline": "disc_freestyle",
        "fields": {"nome": "café", "timer": "2:00"},
        "keys": {"nome": ["nome"], "timer": ["timer"]},
    },
    # agility: the sct/SCT first-present alias resolves identically on both sides.
    {
        "discipline": "agility",
        "fields": {"tempo": "31.4", "SCT": "45", "faults": "5"},
        "keys": {"tempo": ["tempo"], "sct": ["sct", "SCT"], "faults": ["faults"]},
    },
]


@_requires_node
def test_value_crosscheck():
    """D-07 VALUE cross-check: served scvGet == Python score_render._get per discipline.

    The Phase-12 SCV-01 unification reuses the ONE ``/overlay`` renderer in the console
    preview iframe, retiring the byte-exact Python↔JS mirror. This test is the safety
    proof the reuse rests on: the served (FROZEN) renderer's ``scvGet`` and the UNCHANGED
    Python ``render_overlay_text``'s ``_get`` must agree on the SANITIZED VALUE for every
    field, across all three disciplines — incl. the agility ``sct``/``SCT`` first-present
    alias, a control-char value (dropped), and an over-64-char value (capped). It compares
    the value, NOT the f-string layout (JS fills DOM cells; Python builds a line).

    It runs the frozen renderer against the unchanged Python renderer, so it PASSES
    immediately (the Phase-11 byte-parity already holds) — it is NOT xfail.
    """
    js = _read_file_js()
    # Node side: for each payload entry, compute scvGet(fields, *keys) for every key set.
    driver = (
        js
        + "\nconst _m = module.exports;\n"
        + "const _payload = " + json.dumps(_CROSSCHECK_PAYLOAD) + ";\n"
        + """
        const out = _payload.map(entry => {
          const vals = {};
          for (const [name, keys] of Object.entries(entry.keys)) {
            vals[name] = _m.scvGet(entry.fields, ...keys);
          }
          return vals;
        });
        process.stdout.write(JSON.stringify(out));
        """
    )
    js_results = json.loads(_run_node(driver))

    # Python side: the SAME key lists through score_render._get over the same fields.
    py_results = []
    for entry in _CROSSCHECK_PAYLOAD:
        vals = {
            name: score_render._get(entry["fields"], *keys)
            for name, keys in entry["keys"].items()
        }
        py_results.append(vals)

    assert js_results == py_results
    # Spot-assert the load-bearing cases explicitly so a regression names itself.
    assert js_results[0]["totale"] == "7"          # control char dropped
    assert js_results[0]["zona"] == "x" * 64       # capped at 64
    assert js_results[1]["nome"] == "café"         # UTF-8 preserved
    assert js_results[2]["sct"] == "45"            # sct/SCT alias resolved


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
    # the nonce is PER-REQUEST unique (++reqSeq) so CEF's URL-keyed cache cannot
    # serve a stale body between gen advances and mask the next gen bump.
    assert "reqSeq" in js
    assert '?t=" + (++reqSeq)' in js
    assert "lastGen" in js
    assert "> lastGen" in js  # gen-strictly-advances gate (unchanged)


def test_freshness_watchdog_present():
    """The watchdog keys on CONSOLE RESPONSE RECENCY, not gen-age.

    `gen` advances only on /run and /score writes (locked Phase 10 contract — no
    heartbeat), so it legitimately stays flat during a live run; staleness must key
    on the last successful poll (lastResponseAt) with everResponded as the cold-start
    guard. The removed gen-age guard (lastGenAt) must not silently return.
    """
    js = _read_file_js()
    assert "PUBLISH_MS = 200" in js
    assert "STALE_MS = PUBLISH_MS * 3" in js
    assert "function isStale" in js
    # response-recency watchdog: everResponded && (Date.now() - lastResponseAt) > STALE_MS
    assert "everResponded" in js
    assert "lastResponseAt" in js
    # the buggy gen-age guard is fully removed and cannot silently return.
    assert "lastGenAt" not in js


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


@_requires_node
def test_live_idle_run_not_stale_but_console_down_is_stale():
    """Regression (260615-tsi): the REAL createRenderer().start() poll loop under a
    fake DOM + controllable clock proves BOTH watchdog behaviors:

      (a) LIVE IDLE RUN — console keeps answering polls but `gen` stays FLAT (no new
          score). isStale() must be False, the lower-third must NOT carry is-stale,
          and the rAF timer loop must stay alive. This is the bug fixed here: the OLD
          gen-age watchdog (Date.now() - lastGenAt > STALE_MS) wrongly flips stale on
          a flat gen → stops the timer + dims the overlay during a normal live run.

      (b) CONSOLE DOWN — fetch rejects, so lastResponseAt stops advancing. After
          STALE_MS isStale() must be True, the post-catch stopTimer()/applyStale(true)
          must apply is-stale, and the rAF loop must stop (OVD-03 / UAT item 3).
    """
    js = _read_file_js()
    harness = r"""
const _m = module.exports;

// ---- controllable clock (override BEFORE createRenderer seeds lastResponseAt) ----
let NOW = 1000000;
global.Date.now = () => NOW;

// ---- minimal fake DOM ----
function makeClassList() {
  const set = new Set();
  return {
    add: (c) => set.add(c),
    remove: (c) => set.delete(c),
    contains: (c) => set.has(c),
    _set: set,
  };
}
function makeEl() {
  const el = {
    className: "",
    classList: makeClassList(),
    textContent: "",
    children: [],
    firstChild: null,
    getAttribute: () => "",
    appendChild: (c) => { el.children.push(c); el.firstChild = el.children[0]; return c; },
    removeChild: (c) => {
      const i = el.children.indexOf(c);
      if (i >= 0) el.children.splice(i, 1);
      el.firstChild = el.children[0] || null;
      return c;
    },
    // minimal class-selector lookup over descendants (renderCells/fillCell use it)
    querySelector: (sel) => {
      const cls = sel.replace(".", "");
      const find = (n) => {
        for (const ch of n.children || []) {
          if (ch.className === cls) return ch;
          const r = find(ch);
          if (r) return r;
        }
        return null;
      };
      return find(el);
    },
    offsetWidth: 0,
  };
  return el;
}
const lowerThird = makeEl();
const timer = makeEl();
const identity = makeEl();
const cells = makeEl();
const byId = { "#lower-third": lowerThird, "#timer": timer, "#identity": identity, "#cells": cells };
global.document = {
  querySelector: (sel) => byId[sel] || null,
  createElement: () => makeEl(),
  createTextNode: (t) => ({ textContent: t }),
};

// ---- controllable rAF (store, never auto-invoke → no recursion) ----
let rafCb = null;
global.requestAnimationFrame = (cb) => { rafCb = cb; return 1; };
global.cancelAnimationFrame = () => { rafCb = null; };

// ---- controllable interval (capture the poll callback) ----
let intervalCb = null;
global.setInterval = (cb) => { intervalCb = cb; return 1; };
global.clearInterval = () => { intervalCb = null; };

// ---- stubbable async fetch with a STATIC gen ----
let fetchMode = "ok";
global.fetch = () => {
  if (fetchMode === "down") return Promise.reject(new Error("down"));
  return Promise.resolve({
    json: async () => ({
      gen: 7,                       // STATIC — never advances across polls
      discipline: "agility",
      running: true,
      started_at: NOW / 1000 - 5,   // started 5s ago
      server_now: NOW / 1000,
    }),
  });
};

// Drain pending microtasks so the await fetch / await r.json() chain settles.
async function drain() {
  for (let i = 0; i < 5; i++) await new Promise((res) => setImmediate(res));
}

(async () => {
  const STALE_MS = _m.STALE_MS;
  const r = _m.createRenderer(document, {});
  r.start();           // fires the immediate first poll + registers intervalCb
  await drain();       // first successful poll → lastResponseAt=NOW, everResponded=true, applyPayload

  // A couple more polls, gen still flat (7). Console keeps answering.
  intervalCb(); await drain();
  intervalCb(); await drain();

  // SCENARIO (a) LIVE IDLE RUN: advance time well past STALE_MS, then fire ONE MORE
  // successful poll (console still answering). Flat gen must NOT make it stale.
  NOW += 5 * STALE_MS;
  intervalCb(); await drain();
  const liveIsStale = r.isStale();
  const liveHasStaleClass = lowerThird.classList.contains("is-stale");
  const liveRafAlive = rafCb !== null;   // rAF loop still armed (timer counting)

  // SCENARIO (b) CONSOLE DOWN: stop answering, advance past STALE_MS, poll (rejects).
  fetchMode = "down";
  NOW += 5 * STALE_MS;
  intervalCb(); await drain();           // catch coasts → lastResponseAt NOT updated
  const downIsStale = r.isStale();
  const downHasStaleClass = lowerThird.classList.contains("is-stale");
  // Invoke the stored frame: tick() sees isStale() → sets rafId=null → no re-arm.
  if (rafCb) { const cb = rafCb; rafCb = null; cb(); }
  const downRafStopped = rafCb === null;

  process.stdout.write(JSON.stringify({
    liveIsStale, liveHasStaleClass, liveRafAlive,
    downIsStale, downHasStaleClass, downRafStopped,
  }));
})();
"""
    driver = js + "\n" + harness
    out = json.loads(_run_node(driver))
    # (a) live idle run with a flat gen is NOT stale; timer keeps ticking.
    assert out["liveIsStale"] is False
    assert out["liveHasStaleClass"] is False
    assert out["liveRafAlive"] is True
    # (b) console down goes stale, dims, and stops the rAF loop (OVD-03 preserved).
    assert out["downIsStale"] is True
    assert out["downHasStaleClass"] is True
    assert out["downRafStopped"] is True


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
