---
phase: 15-pure-calc-validation-core-scoring-profiles
plan: 03
subsystem: testing
tags: [crash-isolation, import-smoke, score_calc, flask, rbt-08, scc-02]

# Dependency graph
requires:
  - phase: 15-01
    provides: "segugio.ui.score_calc — the pure-stdlib validate()/compute() scoring authority"
provides:
  - "segugio.ui.score_calc on the crash-isolated PHASE1_SURFACE (heavy-deps-absent parametrized import)"
  - "An executable RBT-08 gate: POST /score round-trip resolves with torch/cv2/ultralytics/numpy/cyndilib/obsws absent"
affects: [16-shared-entry-component, 17-console-modal, 18-rich-data-model]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Crash-isolation surface extended by appending a module to PHASE1_SURFACE (auto-parametrized) + an in-gate import + route round-trip under the forced-absent block"

key-files:
  created: []
  modified:
    - "tests/test_imports.py"

key-decisions:
  - "POST /score assertion tolerates 200/204 so Phase 16 making the route authoritative does not break the crash-isolation gate"
  - "POST round-trip placed AFTER client = app.test_client() (client is built mid-function), not before"

patterns-established:
  - "A new segugio.ui module joins crash-isolation by a single PHASE1_SURFACE entry; route-level isolation proven by a test_client round-trip inside the CONSOLE_HEAVY_MODULES (heavy+numpy+cv2) forced-absent block"

requirements-completed: [RBT-08, SCC-02]

# Metrics
duration: 6min
completed: 2026-06-22
---

# Phase 15 Plan 03: Crash-Isolation Import-Smoke Gate for score_calc + POST /score Summary

**`segugio.ui.score_calc` added to the heavy-deps-absent import surface and the console gate extended with an `import segugio.ui.score_calc` plus a `POST /score` round-trip that resolves with the entire heavy AI stack + numpy + cv2 forced absent — RBT-08 and SCC-02 are now executable gates.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-22T13:30:00Z
- **Completed:** 2026-06-22T13:36:20Z
- **Tasks:** 1
- **Files modified:** 1 (test-only)

## Accomplishments
- Appended `"segugio.ui.score_calc"` to `PHASE1_SURFACE`, so `test_phase1_surface_imports_with_heavy_deps_absent` parametrizes the pure scoring authority under the `HEAVY_MODULES`-absent block automatically.
- Extended `test_console_resolves_with_heavy_stack_and_numpy_absent` with `import segugio.ui.score_calc` (proves the compute brain needs no heavy dep) and a `client.post("/score", ...)` round-trip asserting `status_code in (204, 200)`, both inside the `CONSOLE_HEAVY_MODULES` (heavy + numpy + cv2) forced-absent block.
- `tests/test_imports.py` is fully green (26 passed); existing `/overlay-json` + `/overlay` assertions preserved intact.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add score_calc to PHASE1_SURFACE + extend the heavy-absent gate with a POST /score round-trip** - `9eef57e` (test)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS)

## Files Created/Modified
- `tests/test_imports.py` - Added the `segugio.ui.score_calc` PHASE1_SURFACE entry; extended the console heavy-absent gate with an in-gate `import segugio.ui.score_calc` and a `POST /score` round-trip (200/204 tolerant).

## Decisions Made
- POST /score assertion tolerates both 204 (today's display-only return) and 200 so Phase 16 making the route authoritative does not turn this gate red.
- The POST round-trip was placed AFTER `client = app.test_client()` (the client is constructed mid-function, not at the top), correcting an initial placement that referenced `client` before assignment.

## Deviations from Plan

None - plan executed exactly as written. (The POST placement after `client = app.test_client()` is the plan's intent — the plan text noted the client is built at the existing `/overlay-json` line; the assertion order follows that.)

## Issues Encountered
- First edit placed the `POST /score` block before `client` was defined → `UnboundLocalError`. Resolved by moving the POST round-trip to after the existing `client = app.test_client()` construction. Re-ran the suite green.
- The plan's source assertion `grep -c 'client.post("/score"'` expects a single-line call; the initial multi-line `client.post(` formatting matched 0. Reformatted the call to one line (with `# noqa: E501`) so the literal acceptance grep returns 1.

## Out-of-Scope (Deferred)
5 pre-existing test failures (`test_ndi_mock_sender`, `test_ndi_source`, `test_ui_explainability`, `test_ui_scv_unification`, `test_ui_tablet_layout`) were re-confirmed present on baseline commit `aeaba3d` via `git stash` — they fail identically with this plan's edit stashed and are unrelated to the crash-isolation gate. Logged in `deferred-items.md`; not fixed (SCOPE BOUNDARY).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The crash-isolation guard the rest of v1.3 inherits is now executable. Phase 16 (`POST /score` authoritative, shared entry component) can rely on this gate to catch any heavy import sneaking into `score_calc` or the `/score` route.
- No blockers.

## Self-Check: PASSED
- `tests/test_imports.py` — FOUND
- `15-03-SUMMARY.md` — FOUND
- Commit `9eef57e` — FOUND

---
*Phase: 15-pure-calc-validation-core-scoring-profiles*
*Completed: 2026-06-22*
