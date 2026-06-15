---
phase: quick-260615-tsi
plan: 01
subsystem: ui-overlay
tags: [overlay, watchdog, freshness, robustness, OVD-03]
requires:
  - "src/segugio/ui/static/overlay-render.js (Phase 11-03 renderer + gen-age watchdog)"
provides:
  - "Response-recency freshness watchdog (lastResponseAt/everResponded) in overlay-render.js"
  - "Regression test pinning live-idle-not-stale + console-down-stale"
affects:
  - "Phase 11 /overlay live broadcast (run timer no longer freezes during a live idle run)"
tech-stack:
  added: []
  patterns:
    - "Liveness keyed on transport response recency (successful poll), not on a data-version counter that legitimately stays flat"
key-files:
  created: []
  modified:
    - "src/segugio/ui/static/overlay-render.js"
    - "tests/test_ui_overlay_render.py"
decisions:
  - "Staleness keys on console RESPONSE recency (last successful /overlay-json poll), never on gen-age — gen advances only on /run and /score writes (locked Phase 10 contract, no heartbeat), so it stays flat during a live run with no new score and must not signal liveness."
metrics:
  duration: ~12min
  completed: 2026-06-15
---

# Quick Task 260615-tsi: Fix overlay run-timer freeze (response-recency watchdog) Summary

Replaced the overlay freshness watchdog's gen-age trigger with console response-recency, so a live run with a flat `gen` (no new score) no longer freezes the run timer or dims the overlay, while a dead console still degrades after STALE_MS (OVD-03 preserved).

## What Changed

**Root cause (Phase 11 UAT):** `isStale()` keyed on gen-age (`lastGen >= 0 && Date.now() - lastGenAt > STALE_MS`), and `lastGenAt` advanced only when the monotonic `gen` advanced. Per the locked Phase 10 contract there is NO gen heartbeat — `gen` advances ONLY on `/run` and `/score` writes. During a live run with no new score for >STALE_MS (600ms), `gen` stays flat → `isStale()` returns true → the rAF `tick()` stops the timer and `.is-stale` dims the overlay, even though the console is alive and answering every 200ms poll.

**The fix:** Base staleness on console RESPONSE RECENCY (a successful poll), not gen-age.

### Task 1 — `src/segugio/ui/static/overlay-render.js`
- Replaced `let lastGenAt = Date.now();` with `let lastResponseAt = Date.now();` + `let everResponded = false;`. Kept `let lastGen = -1;` (still feeds the gen-advance render gate).
- `isStale()` now returns `everResponded && Date.now() - lastResponseAt > STALE_MS`. Cold-start guard is `everResponded` (false before the first successful poll).
- `poll()`: on EVERY successful response (immediately after `r.json()`, BEFORE the `p.gen > lastGen` gate) sets `lastResponseAt = Date.now(); everResponded = true;`. The `catch` (fetch/json error) does NOT update them, so a real outage still goes stale. Removed the now-unused `lastGenAt = Date.now();`. Kept `lastGen = p.gen;` and `applyPayload(p);` inside the gen gate, and the trailing post-catch `if (isStale()) { stopTimer(); applyStale(true); }`.
- Updated the constants-block, isStale, poll, Task-2 banner, and freshness-state comments to describe response-recency liveness, explicitly noting `gen` is an edit/score counter that legitimately stays flat during a live run and must not be the liveness signal.
- `_state` debug accessor now returns `{ lastGen, lastResponseAt, everResponded, skew, running }` (removed the dangling `lastGenAt` reference).
- Unchanged: PUBLISH_MS=200, STALE_MS=PUBLISH_MS*3, the `p.gen > lastGen` render gate, the `++reqSeq` nonce, the offset-cancellation timer, applyStale/startTimer/stopTimer, the public return surface, and the no-innerHTML invariant.

### Task 2 — `tests/test_ui_overlay_render.py`
- `test_freshness_watchdog_present`: kept PUBLISH_MS/STALE_MS/`function isStale` assertions; replaced the two buggy gen-age guard assertions with `everResponded` + `lastResponseAt`, and added `assert "lastGenAt" not in js` to pin the removal.
- Added `test_live_idle_run_not_stale_but_console_down_is_stale`: a node-executed regression that drives the REAL `createRenderer(...).start()` poll loop under a fake DOM + controllable clock (mocked `Date.now`, captured rAF/interval callbacks, stubbable async `fetch` with a STATIC gen). Asserts:
  - (a) LIVE IDLE RUN — console keeps answering, gen flat, time advanced 5×STALE_MS → `isStale() === false`, no `is-stale` class, rAF loop still armed.
  - (b) CONSOLE DOWN — fetch rejects, time advanced past STALE_MS → `isStale() === true`, `is-stale` applied, rAF loop stopped.

## Regression Proof

The new test genuinely reproduces the bug: run against the OLD gen-age watchdog (extracted from `HEAD~1`), the live-idle scenario yields `isStale=true`, `hasStaleClass=true`, `rafAlive=false` (timer frozen, overlay dimmed during a live run). Against the new response-recency watchdog it yields `false/false/true`. The test asserts the new values, so it fails on the old code and passes on the new.

## Verification

- `python -m pytest tests/test_ui_overlay_render.py -q` → 12 passed (all existing + the new regression).
- Full suite: 495 passed, 10 skipped, 4 failed. The 4 failures are all in `tests/test_fan_out_batched.py` (`ModuleNotFoundError: No module named 'ultralytics'`) — pre-existing and environmental (the heavy GPU stack lives in `venv312`; this CPU-only `venv` lacks ultralytics). They are unrelated to the two files touched here and not a regression.
- Scope: `git diff --stat HEAD~2 HEAD` shows only `overlay-render.js` and `test_ui_overlay_render.py` changed. The pre-existing uncommitted `.planning/config.json` and untracked `10-PATTERNS.md` were left untouched.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

- `f635f5c` fix(260615-tsi): base overlay freshness watchdog on console response recency
- `49019bb` test(260615-tsi): pin response-recency watchdog + live-idle/console-down regression

## Self-Check: PASSED

- FOUND: src/segugio/ui/static/overlay-render.js (modified)
- FOUND: tests/test_ui_overlay_render.py (modified)
- FOUND commit: f635f5c
- FOUND commit: 49019bb
