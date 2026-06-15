---
phase: quick-260615-sod
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/segugio/ui/static/overlay-render.js
  - tests/test_ui_overlay_render.py
autonomous: true
requirements:
  - OVD-03
  - OVL-02
user_setup: []

must_haves:
  truths:
    - "Each /overlay-json poll request uses a UNIQUE ?t= value, so OBS CEF cannot serve a stale cached response and the overlay updates live when scores/run state change"
    - "The gen-advance gate (p.gen > lastGen) is unchanged — score/run updates still apply exactly when the server's monotonic gen advances"
    - "All existing phase-11 renderer tests still pass (cleanField byte-parity, skew/freeze/overtime behavior, no-innerHTML sink)"
  artifacts:
    - path: "src/segugio/ui/static/overlay-render.js"
      provides: "Shared overlay renderer with a per-request cache-buster nonce in poll()"
      contains: "++reqSeq"
    - path: "tests/test_ui_overlay_render.py"
      provides: "Assertion that the poll nonce is per-request unique (++reqSeq)"
      contains: "reqSeq"
  key_links:
    - from: "src/segugio/ui/static/overlay-render.js poll()"
      to: "GET /overlay-json"
      via: "fetch with a per-request unique ?t= nonce"
      pattern: "overlay-json\\?t=\" \\+ \\(\\+\\+reqSeq\\)"
---

<objective>
Fix the OBS browser-source overlay live-update stall (Phase 11 UAT item 1, "non si refresha in automatico").

Root cause (confirmed by diagnosis, not hypothesis): the /overlay page polls GET /overlay-json every 200ms and updates the DOM in place, but the poll URL uses `?t=" + lastGen`. `lastGen` only changes when the server's monotonic `gen` advances, so between gen advances every poll request has an IDENTICAL URL. OBS's CEF (embedded Chromium) browser source ignores `Cache-Control: no-store` and caches by URL; once it caches `?t=N`, it keeps serving that cached body and never observes the next gen bump → the overlay stalls permanently. The server side is already verified correct (fresh no-store data on every request, gen advances on /run and /score). The fault is purely the client-side cache-buster being per-gen instead of per-request.

Fix: make the `?t=` nonce a monotonic per-request counter so every poll URL is unique and CEF cannot mask a gen advance. The gen-gate logic (`p.gen > lastGen`) and the freshness watchdog stay untouched — `?t=` is purely a cache-buster the server ignores, NOT the gen-advance gate.

Purpose: restore live overlay updates inside an OBS browser source without changing the gen-driven render gate or the offset-cancellation timer.
Output: a one-line nonce change in overlay-render.js + a comment correction + a test assertion that pins the per-request nonce.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

# The file to fix (poll loop ~lines 379-400, createRenderer state ~lines 256-275)
@src/segugio/ui/static/overlay-render.js

# The served-JS / node-behavior test that pins the nonce + gen-gate
@tests/test_ui_overlay_render.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Make the overlay poll nonce per-request unique to defeat OBS CEF URL caching</name>
  <files>src/segugio/ui/static/overlay-render.js, tests/test_ui_overlay_render.py</files>
  <action>
In src/segugio/ui/static/overlay-render.js, inside createRenderer (near the other renderer state vars `lastGen`, `lastGenAt`, `skew`, `startedAt` around lines 264-274), declare a monotonic per-request counter `let reqSeq = 0;`.

In the poll() function (around line 384), change the fetch URL from the current per-gen nonce `fetch("/overlay-json?t=" + lastGen, { cache: "no-store" })` to a per-request nonce `fetch("/overlay-json?t=" + (++reqSeq), { cache: "no-store" })`, so every poll request URL is unique. Pre-increment so the first request sends `?t=1`.

Update the comment block on/around that fetch line (currently around lines 379-381, referencing "?t=<lastGen> nonce (load-bearing in CEF — Pitfall 2)") so it accurately states the nonce is now UNIQUE PER REQUEST (`++reqSeq`) to defeat OBS CEF's URL-keyed caching that ignores Cache-Control: no-store — otherwise an identical repeated `?t=` URL is served from CEF cache and a gen advance is never observed (the live-stall bug). Keep the comment factually consistent with the per-request counter.

DO NOT change the gen-gate logic: `if (p.gen > lastGen) { ... }`, the `lastGen` / `lastGenAt` assignments inside it, the freshness watchdog (`isStale`, `STALE_MS`, `lastGenAt` age check), or the offset-cancellation timer. The `?t=` query param is purely a cache-buster the server ignores; it is NOT the gen-advance gate. Touch ONLY poll() and the new `reqSeq` declaration in this file.

In tests/test_ui_overlay_render.py, strengthen test_poll_nonce_and_gen_gate_present (around lines 151-157) so it still proves a cache-buster is present AND now pins the per-request nonce: keep the existing `assert "?t=" in js`, `assert "lastGen" in js`, and `assert "> lastGen" in js` (the gen-gate, unchanged); ADD assertions that the nonce is per-request — assert `"reqSeq"` is present in js and that the fetch URL uses the pre-increment expression (assert the substring `"?t=\" + (++reqSeq)"` appears, matching the new fetch). Do not weaken or remove the existing gen-gate assertions. Make no other test changes. Do NOT touch the server, the overlay.html template, the uncommitted .planning/config.json, or the untracked 10-PATTERNS.md.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ui_overlay_render.py -x -q</automated>
  </verify>
  <done>
overlay-render.js poll() fetches `/overlay-json?t=" + (++reqSeq)` (per-request unique nonce) with a `let reqSeq = 0;` declaration in createRenderer; the gen-gate `p.gen > lastGen`, `lastGen`/`lastGenAt`, the freshness watchdog, and the offset-cancellation timer are byte-for-byte unchanged; the fetch comment accurately describes the per-request CEF cache-buster; test_poll_nonce_and_gen_gate_present asserts `reqSeq` and the `(++reqSeq)` nonce expression while retaining the `?t=`, `lastGen`, and `> lastGen` assertions; and the full tests/test_ui_overlay_render.py suite (served-JS asserts + node-executed cleanField byte-parity + skew/freeze/overtime behavior + no-innerHTML sink) passes.
  </done>
</task>

</tasks>

<verification>
- Run `python -m pytest tests/test_ui_overlay_render.py -q` — all served-JS and node-behavior tests pass (cleanField byte-parity vs score_render._clean, skew/freeze/overtime, no-innerHTML sink, nonce + gen-gate).
- Confirm the diff touches ONLY src/segugio/ui/static/overlay-render.js and tests/test_ui_overlay_render.py via `git status --short` (no server, template, config.json, or 10-PATTERNS.md changes).
</verification>

<success_criteria>
- Every poll request to /overlay-json has a unique `?t=` value (`++reqSeq`), so an OBS CEF browser source cannot serve a stale cached body and the overlay updates live when the console publishes a new score or run-state edge.
- The gen-driven render gate (`p.gen > lastGen`), `lastGen`/`lastGenAt`, the gen-age freshness watchdog, and the offset-cancellation timer are unchanged.
- tests/test_ui_overlay_render.py passes in full and now pins the per-request nonce so a regression back to a per-gen nonce fails the suite.
</success_criteria>

<output>
Create `.planning/quick/260615-sod-fix-obs-browser-source-overlay-live-upda/260615-sod-SUMMARY.md` when done.
</output>
