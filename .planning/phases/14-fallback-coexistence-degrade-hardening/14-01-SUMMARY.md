---
phase: 14-fallback-coexistence-degrade-hardening
plan: 01
subsystem: ui
tags: [overlay, watchdog, degrade, broadcast, javascript, node-fake-dom, rbt-06]

# Dependency graph
requires:
  - phase: 11-shared-graphical-renderer
    provides: overlay-render.js isStale()/applyStale()/retrigger()/is-exiting exit primitive + response-recency watchdog
  - phase: 10-overlay-data-contract
    provides: /overlay-json contract (started_at, server_now, gen, running) + offset-cancellation skew
provides:
  - "DEAD_MS (~3000ms) full-hide threshold constant in overlay-render.js"
  - "isDead() response-recency watchdog (everResponded && now-lastResponseAt > DEAD_MS), exported on createRenderer()"
  - "applyDead() second degrade stage — fully hides the lower-third by reusing the existing is-exiting exit animation"
  - "tests/test_overlay_degrade_gate.py — SC#1 two-stage stale->dead + SC#2 gen re-anchor + Pitfall-1 guard (node fake-DOM)"
affects: [14-02, 14-03, verify-work, obs-setup-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-stage degrade: isStale() dims (is-stale), isDead() hides (is-exiting) — both response-recency keyed, never gen-age"
    - "Dead-hide reuses the existing exit primitive (is-exiting / @keyframes exit) — no new animation primitive"

key-files:
  created:
    - tests/test_overlay_degrade_gate.py
  modified:
    - src/segugio/ui/static/overlay-render.js

key-decisions:
  - "DEAD_MS = 3000ms (per D-05), MUST stay > STALE_MS — a short stale only dims, a sustained death hides"
  - "isDead() keyed on response-recency (lastResponseAt), NEVER gen-age — gen is flat during a live idle run (260615-tsi guard)"
  - "Dead-hide reuses the existing is-exiting / @keyframes exit primitive — no new keyframe added to overlay.html (D-04)"
  - "isDead() check precedes applyStale in both poll() and tick() degrade sites (isDead implies isStale)"

patterns-established:
  - "Two-stage degrade ladder: dim (is-stale) on transient hiccup, hide (is-exiting) on real death"
  - "Node fake-DOM gate harness reused verbatim from test_ui_overlay_render.py for the second-stage gates"

requirements-completed: [RBT-06]

# Metrics
duration: 5min
completed: 2026-06-20
---

# Phase 14 Plan 01: Two-Stage Degrade Hardening Summary

**Added a `DEAD_MS`/`isDead()` second degrade stage to the overlay client renderer that fully HIDES the lower-third (reusing the existing `is-exiting` exit animation) on a real console death — so no frozen score airs from the OBS browser source — with SC#1/SC#2/Pitfall-1 node fake-DOM gates.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-20T15:29Z
- **Completed:** 2026-06-20T15:33Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 edited)

## Accomplishments
- `DEAD_MS` (3000ms) full-hide threshold + `isDead()` response-recency watchdog added next to `STALE_MS`/`isStale()`, structurally identical (`everResponded && Date.now() - lastResponseAt > DEAD_MS`).
- `applyDead()` drives the second-stage hide by removing `is-live`/`is-stale` and re-triggering the EXISTING `is-exiting` exit animation — no new keyframe (D-04). Wired into both the `poll()` post-catch degrade site and the `tick()` stop edge (dead check precedes stale).
- `isDead` exported on the `createRenderer()` return object and `DEAD_MS` on the `api` object so node gates can assert them.
- `tests/test_overlay_degrade_gate.py` authored with three `@_requires_node` gates: SC#1 two-stage stale->dead (dim then hide + rAF stop), Pitfall-1 "live idle run is NOT dead" (flat-gen regression guard), SC#2 gen re-anchor (continuous elapsed across a bumped-gen resume, no phantom jump).
- RBT-07 crash-isolation gate (`test_imports.py`) stays green; full regression set (degrade + overlay-render + freshness + imports) green, zero regression.

## Task Commits

1. **Task 1: Add DEAD_MS + isDead() + dead-hide to overlay-render.js** - `84128c5` (feat)
2. **Task 2: Author tests/test_overlay_degrade_gate.py (SC#1 + SC#2 + Pitfall-1)** - `5d17c33` (test)

_Note: Task 1 was a `tdd="true"` source edit whose verification gate is `test_imports.py` (per the plan); the behavior gates are authored in Task 2 against the shipped surface._

## Files Created/Modified
- `src/segugio/ui/static/overlay-render.js` - Added `DEAD_MS` constant, `isDead()` watchdog, `applyDead()` hide; extended `poll()` + `tick()` degrade sites; exported `isDead`/`DEAD_MS`.
- `tests/test_overlay_degrade_gate.py` - NEW node fake-DOM gates: `test_two_stage_stale_then_dead_hides_lower_third` (SC#1), `test_live_idle_run_is_not_dead` (Pitfall-1), `test_gen_reanchor_no_phantom_jump` (SC#2).

## Decisions Made
- `DEAD_MS = 3000ms` (D-05), with an explicit comment that it MUST stay `> STALE_MS`.
- `isDead()` keyed strictly on response-recency, never gen-age — the source still contains no `lastGenAt` (260615-tsi anti-pattern stays absent, verified by grep).
- `isDead()` checked before `applyStale()` at both degrade sites because `isDead()` implies `isStale()`; the short-stale dim branch is unchanged.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
- The SC#1 fake-DOM timing required observing the dim stage with the console already non-responsive but the clock advanced only just past `STALE_MS` (under `DEAD_MS`), since the harness's static-`started_at` fetch keeps stamping `lastResponseAt` on every successful poll. Resolved by switching `fetchMode="down"` for the dim observation and advancing the clock in two steps (`STALE_MS+50`, then `+DEAD_MS`) — a harness-driving detail, not a renderer change.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The two-stage degrade is shipped and gated; the browser overlay now auto-hides on death, which 14-03's `docs/obs-setup.md` D-06 simplification depends on (the operator no longer manually hides `Score Overlay`).
- `isDead`/`DEAD_MS` are available as the downstream-consumable surface for 14-02 fallback/poll-storm/HTML-sink gates and verify-work.

## Self-Check: PASSED
- FOUND: src/segugio/ui/static/overlay-render.js
- FOUND: tests/test_overlay_degrade_gate.py
- FOUND commit: 84128c5
- FOUND commit: 5d17c33

---
*Phase: 14-fallback-coexistence-degrade-hardening*
*Completed: 2026-06-20*
