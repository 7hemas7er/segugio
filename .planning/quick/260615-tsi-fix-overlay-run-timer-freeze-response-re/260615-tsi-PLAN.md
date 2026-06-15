---
phase: quick-260615-tsi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/segugio/ui/static/overlay-render.js
  - tests/test_ui_overlay_render.py
autonomous: true
requirements: [OVD-03]
must_haves:
  truths:
    - "During a live run with no new score for >STALE_MS, the run timer keeps counting and the overlay stays bright (not stale) as long as the console answers polls"
    - "When the console stops answering polls (fetch rejects), the timer stops and the overlay dims (.is-stale) after STALE_MS — OVD-03 / UAT item 3 preserved"
    - "isStale() keys on console RESPONSE recency (last successful poll), never on gen-age"
    - "A cold load (before any successful poll) is NOT stale"
  artifacts:
    - path: "src/segugio/ui/static/overlay-render.js"
      provides: "Response-recency freshness watchdog (lastResponseAt/everResponded) replacing the gen-age watchdog (lastGenAt)"
      contains: "function isStale"
    - path: "tests/test_ui_overlay_render.py"
      provides: "Updated watchdog assertion + node-executed regression test pinning live-idle-not-stale and console-down-stale"
      contains: "everResponded"
  key_links:
    - from: "poll() successful fetch + r.json()"
      to: "lastResponseAt / everResponded"
      via: "set BEFORE the p.gen > lastGen gate on every successful response"
      pattern: "lastResponseAt = Date.now"
    - from: "isStale()"
      to: "lastResponseAt"
      via: "everResponded && Date.now() - lastResponseAt > STALE_MS"
      pattern: "everResponded.*lastResponseAt"
---

<objective>
Fix the overlay run-timer freeze discovered in Phase 11 UAT: during a live run the score cells update but the run TIMER freezes and the overlay dims, even though the console is alive and answering every 200ms poll.

Root cause: the freshness watchdog `isStale()` keys on gen-age (`lastGen >= 0 && Date.now() - lastGenAt > STALE_MS`), and `lastGenAt` advances ONLY when the monotonic `gen` advances. Per the locked Phase 10 contract there is NO gen heartbeat — `gen` advances ONLY on `/run` and `/score` writes. So during a live run with no new score for >STALE_MS (600ms), `gen` stays flat, `isStale()` returns true, the rAF `tick()` stops the timer and `.is-stale` dims the overlay.

The fix: base staleness on CONSOLE RESPONSE RECENCY (a successful poll), not gen-age. A live console answering polls is never stale even with a flat gen; a dead/unreachable console stops answering → stale after STALE_MS → timer stops + dim, PRESERVING OVD-03 / UAT item 3 (kill-console degrade).

Purpose: keep the run timer counting during a normal live run while preserving the OVD-03 degrade-on-console-death behavior.
Output: a response-recency watchdog in overlay-render.js, an updated watchdog assertion test, and a node-executed regression test pinning both behaviors.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/segugio/ui/static/overlay-render.js
@tests/test_ui_overlay_render.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace the gen-age freshness watchdog with a console-response-recency watchdog</name>
  <files>src/segugio/ui/static/overlay-render.js</files>
  <action>
In createRenderer (state vars ~256-275, isStale ~276-282, tick ~316-326, poll ~389-407), convert the freshness watchdog from gen-age to console-response recency. SCOPE: edit ONLY overlay-render.js. Do NOT touch app.py, overlay.html, .planning/config.json, or 10-PATTERNS.md.

1. State vars: Replace the single line `let lastGenAt = Date.now();` with two response-recency state vars: `let lastResponseAt = Date.now();` and `let everResponded = false;`. KEEP `let lastGen = -1;` exactly as-is — it still feeds the gen-advance RENDER gate `p.gen > lastGen` in poll(); do NOT change that gate.

2. isStale(): Change the body to return `everResponded && Date.now() - lastResponseAt > STALE_MS;`. The cold-start guard is now `everResponded` (false before the first successful poll) instead of `lastGen >= 0`. Rationale to capture in the comment: a live console answering polls is never stale even with a flat gen; a dead/unreachable console stops answering, so lastResponseAt stops advancing and the overlay goes stale after STALE_MS.

3. poll(): On EVERY successful response — immediately AFTER `const p = await r.json();` and BEFORE the `if (p.gen > lastGen)` gate — set `lastResponseAt = Date.now(); everResponded = true;`. Inside the gen gate KEEP `lastGen = p.gen;` and `applyPayload(p);`, but REMOVE the now-unused `lastGenAt = Date.now();` line. The `catch (e)` (fetch/json error) MUST NOT update lastResponseAt or everResponded — so a real outage still goes stale. Leave the trailing post-catch `if (isStale()) { stopTimer(); applyStale(true); }` block as-is.

4. Comments: Update the freshness-constants block comment (~221-224), the isStale() comment (~277-279), and the poll() doc comment (~380-388) so they describe response-recency liveness (the console answering the poll) instead of gen-age. Explicitly note in at least one of these comments that `gen` is an edit/score counter that legitimately stays flat during a live run, so it MUST NOT be the liveness signal. Also update the Task-2 banner header comment (~217-218) and the createRenderer freshness-state comment (~263) that currently say "gen-age" / "lastGen<0 is NOT stale" to reflect the response-recency model.

5. The `_state` debug accessor at the bottom of createRenderer (~422) currently returns `{ lastGen, lastGenAt, skew, running }` — replace `lastGenAt` with `lastResponseAt` (and optionally add `everResponded`) so the returned closure references resolve (a dangling `lastGenAt` reference would be a ReferenceError). KEEP `lastGen` in the returned object.

KEEP UNCHANGED: PUBLISH_MS = 200; STALE_MS = PUBLISH_MS * 3; the gen-advance render gate `p.gen > lastGen`; the per-request `?t=" + (++reqSeq)` nonce; the offset-cancellation timer (currentElapsed/skew/paintTimer); applyStale/startTimer/stopTimer; the public return surface `{ start, stop, applyPayload, isStale, currentElapsed, paintTimer, _state }`. Do NOT introduce innerHTML anywhere (the no-innerHTML invariant test must stay green).
  </action>
  <verify>
    <automated>cd C:\Users\mirko\Documents\GitHub\segugio; node -e "const m=require('./src/segugio/ui/static/overlay-render.js'); const s=require('fs').readFileSync('./src/segugio/ui/static/overlay-render.js','utf8'); if(!s.includes('everResponded'))throw new Error('missing everResponded'); if(!s.includes('lastResponseAt'))throw new Error('missing lastResponseAt'); if(s.includes('lastGenAt'))throw new Error('lastGenAt still present'); if(!s.includes('> lastGen'))throw new Error('gen gate removed'); if(s.includes('.innerHTML'))throw new Error('innerHTML sink'); console.log('OK')"</automated>
  </verify>
  <done>overlay-render.js parses under node; isStale() keys on everResponded && lastResponseAt; lastGenAt is fully removed; the p.gen > lastGen render gate, the ++reqSeq nonce, PUBLISH_MS=200, and STALE_MS=PUBLISH_MS*3 are unchanged; no innerHTML sink introduced.</done>
</task>

<task type="auto">
  <name>Task 2: Update the watchdog assertion test and add a node-executed regression test pinning the fix</name>
  <files>tests/test_ui_overlay_render.py</files>
  <action>
SCOPE: edit ONLY tests/test_ui_overlay_render.py. Reuse the existing `_run_node` harness (~222-238) and the `_read_file_js()` / `@_requires_node` helpers already in the file.

1. Update `test_freshness_watchdog_present` (~163-171): keep `assert "PUBLISH_MS = 200" in js`, `assert "STALE_MS = PUBLISH_MS * 3" in js`, and `assert "function isStale" in js`. REPLACE the two buggy gen-age guard assertions (`assert "lastGen >= 0" in js` and `assert "lastGenAt" in js`) with the new watchdog assertions: `assert "everResponded" in js` and `assert "lastResponseAt" in js`. Do NOT assert `lastGenAt` anymore (it is removed). Also add `assert "lastGenAt" not in js` to pin that the removed gen-age guard cannot silently return. Update the test docstring/comment to describe response-recency.

2. ADD a node-executed regression test (decorate with `@_requires_node`) that drives the REAL `createRenderer(...).start()` poll loop under a fake DOM and controllable clock, asserting BOTH behaviors. Build the driver as `js + "\nconst _m = module.exports;\n" + <harness>` and run it through `_run_node(driver)`, then `json.loads` the stdout and assert in Python. The harness (a `.cjs` string executed by node) must:
   - Define a controllable clock: `let NOW = 1000000; global.Date.now = () => NOW;` (override BEFORE calling createRenderer so the closure's `lastResponseAt = Date.now()` seeds from it).
   - Provide a minimal fake `document` with `querySelector(sel)` returning lightweight fake elements for `#lower-third`, `#timer`, `#identity`, `#cells` — each a plain object exposing `classList` (with `add`/`remove`/`contains` backed by a Set), `textContent`, `getAttribute` (returns ""), `children` (array), `appendChild`/`removeChild`/`querySelector`/`firstChild`/`createElement` as needed by renderOverlay/renderCells/renderIdentity. Keep it minimal — record `lower-third`'s classList Set so the test can read whether `is-stale` is applied. Provide `global.document` so node-side helpers resolve; createRenderer takes `root=document`.
   - Provide a controllable `requestAnimationFrame`: store the callback (`let rafCb = null; global.requestAnimationFrame = (cb) => { rafCb = cb; return 1; }; global.cancelAnimationFrame = () => { rafCb = null; };`) — DO NOT auto-invoke (avoid infinite recursion); invoke `rafCb` manually per simulated frame.
   - Provide a controllable interval: `global.setInterval = () => 1; global.clearInterval = () => {};` so `start()` does not spin a real timer (the test drives poll() manually instead, OR re-implement by capturing the interval callback — capturing is cleaner: `let intervalCb=null; global.setInterval=(cb)=>{intervalCb=cb; return 1;};` then call `intervalCb()` to simulate a poll tick).
   - Provide a stubbable async `global.fetch`: a module-level `let fetchMode = 'ok';` switch. When `'ok'`, resolve to `{ json: async () => ({ gen: 7, discipline: 'agility', running: true, started_at: NOW/1000 - 5, server_now: NOW/1000 }) }` with a STATIC gen (gen never advances across polls). When `'down'`, return `Promise.reject(new Error('down'))`.
   - Because `poll()` is async, drive it deterministically: call `r = createRenderer(document, {})`, then `r.start()` (fires the immediate first poll + registers the captured interval). Since fetch is async, AWAIT settlement by wrapping the scenario in an `async` IIFE and using a small `await new Promise(res => setImmediate(res))` (or `await Promise.resolve()` a couple of times / a microtask drain) after each simulated poll so the `await fetch` + `await r.json()` chain resolves before assertions. Keep it BOUNDED — no real wall-clock waits; advance time only by mutating `NOW`.
   - SCENARIO (a) LIVE IDLE RUN: `fetchMode='ok'`. Start the renderer, drain microtasks so the first successful poll sets `lastResponseAt=NOW` and `everResponded=true` and `applyPayload` runs (running=true → startTimer registers rafCb). Invoke a couple of `intervalCb()` polls (still gen=7, static) draining microtasks each time. Then advance `NOW += 5 * STALE_MS` (well past STALE_MS) WITHOUT a further successful poll having updated lastResponseAt... — NO: to prove the LIVE case, after advancing NOW also fire ONE more successful `intervalCb()` poll (console still answering) and drain. Assert `r.isStale() === false` and that `lower-third` does NOT have `is-stale`, and that invoking `rafCb` (a frame) calls paintTimer (timer textContent is a counting value, not frozen by a stale stop). Concretely: capture `document` `#timer`.textContent before/after a frame and assert the rAF loop is still alive (rafCb non-null after a tick). This is the regression that FAILS on the OLD gen-age watchdog (flat gen → stale → timer stop).
   - SCENARIO (b) CONSOLE DOWN: continue with the SAME renderer (or a fresh one that has already responded once). Set `fetchMode='down'`. Advance `NOW += 5 * STALE_MS`. Fire `intervalCb()` (fetch rejects → catch coasts, lastResponseAt NOT updated) and drain microtasks. Assert `r.isStale() === true`, that the post-catch `stopTimer(); applyStale(true)` ran so `lower-third` HAS `is-stale`, and that the rAF loop stopped (after the next `rafCb()` invocation `tick()` sees isStale() and sets rafId=null → rafCb becomes null / no re-arm). This proves OVD-03 degrade still works.
   - Emit `process.stdout.write(JSON.stringify({ liveIsStale, liveHasStaleClass, downIsStale, downHasStaleClass }))` and in Python assert: `liveIsStale is False`, `liveHasStaleClass is False`, `downIsStale is True`, `downHasStaleClass is True`.

   Drive lastResponseAt/everResponded/lastGen ONLY through the public surface (`start()`, `isStale()`, the fake DOM's classList, fetch + Date.now stubs) — do NOT reach into private closure state. Note the `_run_node` driver writes a `.cjs` file, so `require`/`module.exports`, async IIFE, and `setImmediate` are available; keep the harness deterministic and bounded (mock Date.now + manual callback invocation, no real sleeps).

3. ALL existing phase-11 renderer tests in this file MUST still pass unchanged (byte-parity, skew/freeze/overtime, no-innerHTML sink, poll nonce + gen gate, per-discipline tokens, offset-cancellation formula).
  </action>
  <verify>
    <automated>cd C:\Users\mirko\Documents\GitHub\segugio; python -m pytest tests/test_ui_overlay_render.py -x -q</automated>
  </verify>
  <done>test_freshness_watchdog_present asserts everResponded + lastResponseAt + "function isStale" + STALE_MS/PUBLISH_MS and asserts "lastGenAt" not in js; the new node-executed regression test passes proving (a) live-idle flat-gen is NOT stale and the timer keeps ticking, and (b) console-down goes stale with is-stale applied and the rAF loop stopped; the full tests/test_ui_overlay_render.py suite passes with zero regressions.</done>
</task>

</tasks>

<verification>
- `python -m pytest tests/test_ui_overlay_render.py -q` passes (all existing + the new regression test).
- Manual reasoning check against the locked Phase 10 contract: `gen` advances only on /run and /score; the new watchdog no longer treats a flat gen during a live run as stale.
- No edits outside src/segugio/ui/static/overlay-render.js and tests/test_ui_overlay_render.py (git status shows only those two tracked changes; .planning/config.json and 10-PATTERNS.md untouched).
</verification>

<success_criteria>
- isStale() keys on `everResponded && Date.now() - lastResponseAt > STALE_MS` (response recency), never on gen-age; `lastGenAt` fully removed.
- lastResponseAt/everResponded are set on EVERY successful poll (before the gen gate); the fetch-error catch never updates them.
- The p.gen > lastGen render gate, the ++reqSeq nonce, the offset-cancellation timer, PUBLISH_MS=200, and STALE_MS=PUBLISH_MS*3 are unchanged.
- A live console answering polls with a flat gen keeps the timer counting and the overlay bright (regression fixed).
- A down console goes stale after STALE_MS: timer stops + .is-stale dims (OVD-03 / UAT item 3 preserved).
- Full tests/test_ui_overlay_render.py suite green; no innerHTML sink introduced.
</success_criteria>

<output>
Create `.planning/quick/260615-tsi-fix-overlay-run-timer-freeze-response-re/260615-tsi-SUMMARY.md` when done
</output>
