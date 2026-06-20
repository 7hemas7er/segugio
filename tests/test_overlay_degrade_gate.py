"""Two-stage degrade + gen re-anchor gates for the shared overlay renderer (plan 14-01).

These node fake-DOM gates pin the RBT-06 acceptance behavior added in 14-01:

  SC#1 — two-stage stale -> dead degrade:
    * a SHORT stale (past STALE_MS, under DEAD_MS) with the console STILL answering
      only DIMS the lower-third (is-stale) and keeps isDead() False (transient WiFi
      hiccups never hard-hide);
    * a console DEATH (no successful poll past DEAD_MS) fully HIDES the lower-third
      by reusing the existing is-exiting exit animation, loses is-live/is-stale, and
      STOPS the rAF loop — so no frozen score airs from the OBS browser source.

  Pitfall-1 regression guard — a LIVE console answering polls with a FLAT gen, with
  the clock advanced past DEAD_MS, is NEVER dead (response-recency keying, NOT
  gen-age; the 260615-tsi guard, the load-bearing "idle-but-live is never dead").

  SC#2 — gen re-anchor, no phantom jump:
    * after a LAN drop (fetch rejects → timer stops, degrade applies) and a resume
      with the SAME started_at and a BUMPED gen, currentElapsed() re-anchors
      CONTINUOUS with the TRUE wall-clock elapsed (NOW/1000 - started_at), NOT
      inflated by the outage duration (no phantom jump equal to the drop length).

The harness (node helper, fake DOM, controllable clock/fetch, microtask pump) is
copied verbatim from ``tests/test_ui_overlay_render.py`` — node executes the served
renderer module and reads ``module.exports`` (project memory ``overlay-bugs-sandbox-repro``:
reproduce /overlay behavior in a node fake-DOM sandbox, never POST to the live console).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import pytest

_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "segugio",
    "ui",
    "static",
    "overlay-render.js",
)


def _read_file_js():
    with open(_JS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for behavior test")


# ---------------------------------------------------------------------------
# shared fake-DOM harness preamble (copied from test_ui_overlay_render.py:321-409)
# ---------------------------------------------------------------------------

_HARNESS_PREAMBLE = r"""
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

// Drain pending microtasks so the await fetch / await r.json() chain settles.
async function drain() {
  for (let i = 0; i < 5; i++) await new Promise((res) => setImmediate(res));
}
"""


def _run_node(driver_src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver_src)
        path = fh.name
    try:
        # Decode node's stdout as UTF-8 explicitly: on Windows the default locale
        # encoding (cp1252) would mangle non-ASCII, breaking byte-parity.
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


# ---------------------------------------------------------------------------
# SC#1 — two-stage stale -> dead degrade
# ---------------------------------------------------------------------------


@_requires_node
def test_two_stage_stale_then_dead_hides_lower_third():
    """SC#1 (RBT-06 / T-14-degrade): a SHORT stale only DIMS (is-stale), a sustained
    DEATH past DEAD_MS fully HIDES (is-exiting) and stops the rAF loop.

    Stage 1 (DIM) — drive successful live polls, then advance NOW past STALE_MS but
    UNDER DEAD_MS with the console STILL answering one more poll. isStale() must be
    True, isDead() False, and the lower-third must carry is-stale but NOT is-exiting.

    Stage 2 (HIDE) — stop answering (fetchMode="down"), advance NOW past DEAD_MS, poll
    (rejects → lastResponseAt stalls). isDead() must be True, the lower-third gained
    is-exiting and lost is-live/is-stale, and the rAF loop must STOP (invoke the stored
    frame and assert it does not re-arm).
    """
    js = _read_file_js()
    harness = _HARNESS_PREAMBLE + r"""
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

(async () => {
  const STALE_MS = _m.STALE_MS;
  const DEAD_MS = _m.DEAD_MS;
  const r = _m.createRenderer(document, {});
  r.start();           // immediate first poll + registers intervalCb
  await drain();       // first successful poll → lastResponseAt=NOW, everResponded=true
  intervalCb(); await drain();

  // STAGE 1 (DIM): advance past STALE_MS but UNDER DEAD_MS, console STILL answers one
  // more poll (response stamps NOW). The console then "goes quiet" — but because the
  // last response is past STALE_MS at the next observation, isStale flips while isDead
  // stays False. To exercise the dim-only window we observe BEFORE the dead threshold:
  // advance just past STALE_MS with no answer, observe.
  fetchMode = "down";
  NOW += STALE_MS + 50;       // past STALE_MS, well under DEAD_MS (3000)
  intervalCb(); await drain();          // rejects → lastResponseAt stalls; post-catch degrade
  const dimIsStale = r.isStale();
  const dimIsDead = r.isDead();
  const dimHasStaleClass = lowerThird.classList.contains("is-stale");
  const dimHasExiting = lowerThird.classList.contains("is-exiting");

  // STAGE 2 (HIDE): advance past DEAD_MS, poll (still down).
  NOW += DEAD_MS;             // total elapsed since last response now > DEAD_MS
  intervalCb(); await drain();
  const deadIsDead = r.isDead();
  const deadHasExiting = lowerThird.classList.contains("is-exiting");
  const deadHasLive = lowerThird.classList.contains("is-live");
  const deadHasStaleClass = lowerThird.classList.contains("is-stale");
  // Invoke the stored frame: tick() sees isDead() → applyDead(), rafId=null, no re-arm.
  if (rafCb) { const cb = rafCb; rafCb = null; cb(); }
  const deadRafStopped = rafCb === null;

  process.stdout.write(JSON.stringify({
    dimIsStale, dimIsDead, dimHasStaleClass, dimHasExiting,
    deadIsDead, deadHasExiting, deadHasLive, deadHasStaleClass, deadRafStopped,
  }));
})();
"""
    out = json.loads(_run_node(js + "\n" + harness))
    # Stage 1: DIM only — stale True, dead False, is-stale present, NOT hidden.
    assert out["dimIsStale"] is True
    assert out["dimIsDead"] is False
    assert out["dimHasStaleClass"] is True
    assert out["dimHasExiting"] is False
    # Stage 2: HIDE — dead True, is-exiting present, is-live/is-stale gone, rAF stopped.
    assert out["deadIsDead"] is True
    assert out["deadHasExiting"] is True
    assert out["deadHasLive"] is False
    assert out["deadHasStaleClass"] is False
    assert out["deadRafStopped"] is True


# ---------------------------------------------------------------------------
# Pitfall-1 regression guard — a live idle run (flat gen) is NEVER dead
# ---------------------------------------------------------------------------


@_requires_node
def test_live_idle_run_is_not_dead():
    """Pitfall-1 (T-14-falsehide / 260615-tsi): a LIVE console answering polls with a
    FLAT gen, NOW advanced past DEAD_MS, then ONE MORE successful poll, is NEVER dead.

    This is the load-bearing "idle-but-live is never dead" assertion — isDead() is keyed
    on response-recency (lastResponseAt), NOT gen-age, so a normal live run with no new
    score (flat gen) must keep the overlay shown (no is-exiting, isDead() False).
    """
    js = _read_file_js()
    harness = _HARNESS_PREAMBLE + r"""
// ---- stubbable async fetch with a STATIC gen (console keeps answering) ----
let fetchMode = "ok";
global.fetch = () => {
  if (fetchMode === "down") return Promise.reject(new Error("down"));
  return Promise.resolve({
    json: async () => ({
      gen: 7,                       // STATIC — never advances across polls
      discipline: "agility",
      running: true,
      started_at: NOW / 1000 - 5,
      server_now: NOW / 1000,
    }),
  });
};

(async () => {
  const DEAD_MS = _m.DEAD_MS;
  const r = _m.createRenderer(document, {});
  r.start();
  await drain();
  intervalCb(); await drain();

  // Advance time well past DEAD_MS, then fire ONE MORE successful poll. The console is
  // still answering (lastResponseAt = NOW each poll), so a flat gen must NOT make it dead.
  NOW += 3 * DEAD_MS;
  intervalCb(); await drain();
  const liveIsDead = r.isDead();
  const liveHasExiting = lowerThird.classList.contains("is-exiting");
  const liveRafAlive = rafCb !== null;   // rAF loop still armed (timer counting)

  process.stdout.write(JSON.stringify({ liveIsDead, liveHasExiting, liveRafAlive }));
})();
"""
    out = json.loads(_run_node(js + "\n" + harness))
    assert out["liveIsDead"] is False
    assert out["liveHasExiting"] is False
    assert out["liveRafAlive"] is True


# ---------------------------------------------------------------------------
# CR-01 regression — dead -> recovery RE-SHOWS the lower-third
# ---------------------------------------------------------------------------


@_requires_node
def test_dead_then_recover_reshows_lower_third():
    """CR-01 / WR-01: after a console DEATH (>DEAD_MS, lower-third hidden via is-exiting)
    during a STILL-RUNNING run, a RECOVERY (successful poll, SAME started_at, BUMPED gen,
    running:true) must RE-SHOW the lower-third — is-exiting cleared AND is-live restored.

    This is the dangerous half of the live failure mode that the shipped two-stage gate
    never exercised: it asserted death HIDES but never drove a resume, so a one-way hide
    (no recovery counterpart) shipped green. wasRunning stays true across the outage, so
    the resume payload is running true→true and animateRunEdge's run-START edge (false→true
    only) never fires — the fix re-shows on a live payload consumed while is-exiting.

    Drive: live polls → fetchMode="down", NOW past DEAD_MS, poll (assert is-exiting, isDead)
    → fetchMode="ok", bump gen, poll → assert is-live present and is-exiting cleared. This
    fails against the pre-fix renderer (plate stays hidden) and passes once CR-01 is fixed.
    """
    js = _read_file_js()
    harness = _HARNESS_PREAMBLE + r"""
// started_at is the persisted run anchor — FIXED in wall-clock terms across the outage.
const STARTED_AT = NOW / 1000;

let fetchMode = "ok";
let gen = 7;
global.fetch = () => {
  if (fetchMode === "down") return Promise.reject(new Error("down"));
  return Promise.resolve({
    json: async () => ({
      gen: gen,
      discipline: "agility",
      running: true,                 // STILL running across the death and recovery
      started_at: STARTED_AT,        // SAME anchor before and after the outage
      server_now: NOW / 1000,
    }),
  });
};

(async () => {
  const DEAD_MS = _m.DEAD_MS;
  const r = _m.createRenderer(document, {});
  r.start();
  await drain();                 // first successful poll → live, lastResponseAt=NOW
  intervalCb(); await drain();
  const liveHasLive = lowerThird.classList.contains("is-live");
  const liveHasExiting = lowerThird.classList.contains("is-exiting");

  // DEATH: console stops answering, advance past DEAD_MS, poll (rejects → response stalls).
  fetchMode = "down";
  NOW += DEAD_MS + 500;
  intervalCb(); await drain();
  const deadIsDead = r.isDead();
  const deadHasExiting = lowerThird.classList.contains("is-exiting");
  const deadHasLive = lowerThird.classList.contains("is-live");

  // RECOVERY: console answers again with the SAME started_at and a BUMPED gen (passes the
  // p.gen > lastGen re-render gate → applyPayload runs). running stays true (true→true).
  fetchMode = "ok";
  gen = 8;
  intervalCb(); await drain();
  const recIsDead = r.isDead();
  const recHasExiting = lowerThird.classList.contains("is-exiting");
  const recHasLive = lowerThird.classList.contains("is-live");

  process.stdout.write(JSON.stringify({
    liveHasLive, liveHasExiting,
    deadIsDead, deadHasExiting, deadHasLive,
    recIsDead, recHasExiting, recHasLive,
  }));
})();
"""
    out = json.loads(_run_node(js + "\n" + harness))
    # Baseline: shown live before the outage.
    assert out["liveHasLive"] is True
    assert out["liveHasExiting"] is False
    # Death: fully hidden via is-exiting, is-live gone, isDead True.
    assert out["deadIsDead"] is True
    assert out["deadHasExiting"] is True
    assert out["deadHasLive"] is False
    # Recovery: the plate is RE-SHOWN — is-exiting cleared, is-live restored, no longer dead.
    assert out["recIsDead"] is False
    assert out["recHasExiting"] is False, "CR-01: lower-third stayed hidden after recovery"
    assert out["recHasLive"] is True, "CR-01: lower-third did not regain is-live on recovery"


# ---------------------------------------------------------------------------
# SC#2 — gen re-anchor, no phantom jump
# ---------------------------------------------------------------------------


@_requires_node
def test_gen_reanchor_no_phantom_jump():
    """SC#2 (T-14-phantom): after a LAN drop and a resume with the SAME started_at and a
    BUMPED gen, currentElapsed() is CONTINUOUS with the TRUE wall-clock elapsed
    (NOW/1000 - started_at), NOT inflated by the outage duration.

    Drive: running (gen 7) → fetchMode="down" (fetch rejects, timer stops, degrade) →
    fetchMode="ok" again returning the SAME started_at (persisted run anchor) with a
    BUMPED gen (8, to pass the p.gen > lastGen re-render gate). started_at stays fixed in
    wall-clock terms; the elapsed after resume must equal NOW/1000 - started_at within a
    small tolerance — NOT a phantom jump equal to the drop length.
    """
    js = _read_file_js()
    harness = _HARNESS_PREAMBLE + r"""
// started_at is the persisted run anchor — FIXED in wall-clock terms across the outage.
const STARTED_AT = NOW / 1000;   // run starts now

let fetchMode = "ok";
let gen = 7;
global.fetch = () => {
  if (fetchMode === "down") return Promise.reject(new Error("down"));
  return Promise.resolve({
    json: async () => ({
      gen: gen,
      discipline: "agility",
      running: true,
      started_at: STARTED_AT,        // SAME anchor before and after the drop
      server_now: NOW / 1000,        // server clock == NOW (no skew in this harness)
    }),
  });
};

(async () => {
  const r = _m.createRenderer(document, {});
  r.start();
  await drain();                 // first poll at gen 7 → anchored at STARTED_AT

  // Run for a few seconds of live time.
  NOW += 5000;                   // +5s
  intervalCb(); await drain();

  // LAN DROP: fetch rejects across the outage. Timer stops; lastResponseAt stalls.
  fetchMode = "down";
  NOW += 8000;                   // 8s outage — the would-be phantom-jump magnitude
  intervalCb(); await drain();
  intervalCb(); await drain();

  // RESUME: console answers again with the SAME started_at and a BUMPED gen.
  fetchMode = "ok";
  gen = 8;                       // bump → passes the p.gen > lastGen re-render gate
  intervalCb(); await drain();

  const elapsed = r.currentElapsed();
  const trueElapsed = NOW / 1000 - STARTED_AT;   // 5 + 8 = 13s of real wall-clock

  process.stdout.write(JSON.stringify({ elapsed, trueElapsed }));
})();
"""
    out = json.loads(_run_node(js + "\n" + harness))
    # currentElapsed re-anchors continuous with TRUE wall-clock elapsed (~13s),
    # NOT inflated by the 8s outage and NOT collapsed to the pre-drop 5s.
    assert abs(out["elapsed"] - out["trueElapsed"]) < 0.05, (
        f"phantom jump: elapsed={out['elapsed']} vs true={out['trueElapsed']}"
    )
    # Sanity: continuous through the drop — well past the pre-drop 5s, ~13s.
    assert out["elapsed"] > 12.0
    assert out["elapsed"] < 14.0
