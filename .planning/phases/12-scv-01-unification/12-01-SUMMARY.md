---
phase: 12-scv-01-unification
plan: 01
subsystem: testing
tags: [overlay, flask, parity-test, scv, pytest, node, xfail]

# Dependency graph
requires:
  - phase: 11-shared-graphical-renderer-overlay-page-branding
    provides: "the FROZEN /static/overlay-render.js (scvGet/cleanField/DISCIPLINE_CELLS) + /overlay host page the cross-check and preview=1 tests run against"
  - phase: 09-explainability-informed-override-tablet-ux
    provides: "the original SCV-01 byte-exact Python<->JS mirror + POST /score/preview drift-guard this phase retires"
provides:
  - "tests/test_ui_scv_unification.py — structural unification contract (iframe embed, mirror-symbols-gone, surviving-wiring, /score/preview 404), RED-by-design via xfail until 12-02/12-03"
  - "tests/test_ui_overlay_render.py::test_value_crosscheck — D-07 node-vs-Python sanitized-value parity per discipline (green against the frozen renderer)"
  - "tests/test_ui_overlay_page.py::_serve_preview + 4 preview=1 page assertions (body.preview class, shared DOM/script, force-visible rule, no-store), RED-by-design until 12-02"
  - "tests/test_score_preview.py DELETED (its route is removed in 12-02, D-05)"
affects: [12-02-server-overlay-preview-flag-route-removal, 12-03-console-iframe-rewrite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-0 RED-by-design test contract: xfail(strict=False) so the suite stays green pre-implementation and flips to PASS without an XPASS-fail during a partial mid-wave (the 10-01 precedent)"
    - "Value cross-check (not byte-layout): the node renderer's scvGet is compared to Python score_render._get on sanitized VALUES per discipline, decoupled from the f-string layout — the parity contract the iframe reuse rests on"

key-files:
  created:
    - tests/test_ui_scv_unification.py
  modified:
    - tests/test_ui_overlay_render.py
    - tests/test_ui_overlay_page.py
  deleted:
    - tests/test_score_preview.py

key-decisions:
  - "Surviving-wiring + shared-DOM/no-store preview assertions XPASS today (those properties already hold) but stay xfall(strict=False) so they cannot XPASS-fail a partial 12-02/12-03 wave — exactly the plan's strict=False guidance"
  - "test_value_crosscheck is NOT xfail — it runs the frozen Phase-11 renderer against the unchanged render_overlay_text, so it must (and does) pass immediately"

patterns-established:
  - "Pattern 1: _serve_console() / _serve_preview() helpers mirror the existing _serve(overlay_cfg) shape — one served-HTML fetch per route, no server, no heavy deps"
  - "Pattern 2: every deleted identifier is asserted ABSENT (Pitfall 1) via a single _MIRROR_SYMBOLS_GONE tuple so a partial deletion fails the contract"

requirements-completed: [SCV-02]

# Metrics
duration: 3min
completed: 2026-06-15
---

# Phase 12 Plan 01: SCV-01 Unification Test Contract Summary

**Wave-0 parity/structural test contract for the Phase-12 console-preview-as-iframe unification: a RED-by-design structural unification test, a node-vs-Python value cross-check that passes against the frozen renderer, extended preview=1 page assertions, and the obsolete `test_score_preview.py` deleted.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-15T22:24:12Z
- **Completed:** 2026-06-15T22:27:30Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 2 modified, 1 deleted)

## Accomplishments
- New `tests/test_ui_scv_unification.py` with the four structural assertions (iframe embed + D-02 on-air copy; every mirror/drift symbol + `/score/preview` absent; surviving `post("/score")`/run-buttons/`showFields` wiring intact; `POST /score/preview` → 404/405), all xfail RED-by-design until 12-02/12-03.
- `test_value_crosscheck` (D-07): runs the served frozen renderer's `scvGet` in node and compares to Python `score_render._get` per discipline — incl. the agility `sct`/`SCT` first-present alias, a control-char value (dropped → `"7"`), a UTF-8 value (`café` preserved), and an over-64-char value (capped at 64). Passes immediately (Phase-11 byte-parity holds).
- `_serve_preview()` helper + four preview=1 page assertions (`body.preview` class threaded, shared four DOM ids + renderer script, `body.preview #lower-third { opacity: 1 }` force-visible rule, 200 + `Cache-Control: no-store`), RED-by-design until 12-02.
- Deleted obsolete `tests/test_score_preview.py` (route removed in 12-02, D-05); its byte-exact references are subsumed by the value cross-check.

## Task Commits

Each task was committed atomically:

1. **Task 1: New structural unification test + delete test_score_preview.py** - `aa620ac` (test)
2. **Task 2: Value cross-check + preview=1 page assertions** - `fcc5632` (test)

## Files Created/Modified
- `tests/test_ui_scv_unification.py` (created) - Four xfail structural tests asserting the iframe embed, every deleted mirror symbol absent, surviving operator wiring intact, and `/score/preview` unregistered.
- `tests/test_ui_overlay_render.py` (modified) - Added `_CROSSCHECK_PAYLOAD` + `test_value_crosscheck` on the existing `_read_file_js`/`_run_node`/`module.exports` harness; `test_no_innerhtml_sink` unchanged and green.
- `tests/test_ui_overlay_page.py` (modified) - Added `pytest` import, `_serve_preview()` helper, and four preview=1 page assertions (xfail until 12-02).
- `tests/test_score_preview.py` (deleted) - The route it exercised is removed in 12-02 (D-05).

## Decisions Made
- Kept all 12-02/12-03-dependent tests at `xfail(strict=False)` (never `strict=True`) so a partial mid-wave implementation cannot XPASS-fail the suite — the explicit plan guidance.
- `test_value_crosscheck` deliberately compares sanitized field VALUES (not the f-string overlay layout) because JS fills DOM cells while Python builds a line; the shared parity contract is the value, which is what the iframe reuse depends on.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Two preview-page tests (`test_preview_shares_dom_and_script`, `test_preview_no_store`) and the structural `test_surviving_console_wiring_intact` report **XPASS** rather than xfail: the shared DOM/script, the no-store header on `/overlay?preview=1` (the route currently ignores the query param but already sets no-store + 200), and the surviving console wiring are all properties that already hold today. With `strict=False` these XPASSes do not fail the run (exit 0) and they correctly stay PASS after 12-02/12-03 land — this is the intended, plan-sanctioned behavior, not a defect.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The Phase-12 graded contract now exists: 12-02 (server: thread `?preview=1` body.preview flag + force-visible CSS, remove `POST /score/preview`) and 12-03 (console: embed `<iframe src="/overlay?preview=1">`, delete the `gsd:scv01-mirror` block + every mirror/drift symbol) have a verifiable RED target. As each lands, the xfail tests flip to PASS.
- The value cross-check (D-07) guarantees the frozen renderer and `render_overlay_text` agree on sanitized values, so the iframe reuse is provably drift-free before any console edit.
- No blockers. Test-only plan; no new runtime surface, no new dependency, crash-isolation untouched.

## Self-Check: PASSED

- Files: FOUND `tests/test_ui_scv_unification.py`, `tests/test_ui_overlay_render.py`, `tests/test_ui_overlay_page.py`; `tests/test_score_preview.py` confirmed DELETED.
- Commits: FOUND `aa620ac`, FOUND `fcc5632`.

---
*Phase: 12-scv-01-unification*
*Completed: 2026-06-15*
