---
phase: 18-rich-data-model-overlay-continuity-regression
plan: 01
subsystem: api
tags: [score_calc, overlay-json, decimal, flask, regression, golden-snapshot]

# Dependency graph
requires:
  - phase: 15-pure-calc-validation-core
    provides: "score_calc.compute() flat-key authority (throws/prese/zona/totale, criteria total, faults)"
  - phase: 16-shared-entry-server-authoritative-post
    provides: "POST /score authoritative recompute + atomic score.json/overlay.txt write; /overlay-json verbatim echo"
provides:
  - "Additive Decimal-STRING subkeys in compute(): throws[].score (disc_tf), criteria{} (freestyle), faults_breakdown{} (agility count_up + deduct, omitted on elimination)"
  - "Free-text identity passthrough (cane/conduttore/giudici) on all three disciplines via _parse_structured_inputs"
  - "D-05 golden snapshot freezing the 6-key /overlay-json envelope + per-discipline legacy flat-key subset"
  - "Extended heavy-absent rich-POST crash-isolation gate (subkeys + identity round-trip, no 500)"
affects: [18-02, overlay-render, render_overlay_text, console-score-entry]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive enrichment: rebuild dicts (shallow copy + new subkey), never mutate input; flat keys byte-identical (D-04)"
    - "Every JSON-bound numeric is str(Decimal) — no raw Decimal reaches json.dumps (Pitfall 1)"
    - "Contract freeze via golden snapshot: == on the envelope, <= (subset) on legacy flat keys so additive growth stays allowed"

key-files:
  created: []
  modified:
    - src/segugio/ui/score_calc.py
    - src/segugio/ui/app.py
    - tests/test_score_calc.py
    - tests/test_imports.py
    - tests/test_ui_overlay_json.py

key-decisions:
  - "Per-throw score field named `score`, co-located on each throws[] dict (Claude's Discretion under D-03)"
  - "Identity keys are universal (all three disciplines, D-01); named cane/conduttore/giudici — NOT `dog` (freestyle category collision)"
  - "Elimination short-circuit OMITS faults_breakdown entirely (no run → no course/time split), keeping the snapshot deterministic"
  - "Legacy-key freeze uses subset (<=), not == over set(fields), so future additive keys never break CI (D-04 strictly additive)"

patterns-established:
  - "Additive subkey emit mirrors the existing flat-key emit; rebuild-not-mutate for throws[]"
  - "Identity allowlist applied AFTER per-discipline branches as a shared tuple copy from raw"

requirements-completed: [RBT-09]

# Metrics
duration: 11min
completed: 2026-06-27
---

# Phase 18 Plan 01: Rich Data Model & Overlay-Continuity Regression (data-model half) Summary

**compute() now emits throws[].score / criteria{} / faults_breakdown{} as Decimal STRINGS additively beside byte-identical flat keys, cane/conduttore/giudici pass through verbatim on all disciplines, and a golden snapshot freezes the 6-key /overlay-json envelope plus the per-discipline legacy flat-key set.**

## Performance

- **Duration:** ~11 min
- **Completed:** 2026-06-27
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Additive Decimal-STRING subkeys in all three compute helpers — `throws[i]["score"]` co-located on rebuilt (non-mutated) throw dicts, top-level `criteria{}` for freestyle, `faults_breakdown{course,time}` for agility count_up + deduct (omitted on the elimination short-circuit).
- Free-text identity keys `cane`/`conduttore`/`giudici` flow through `_parse_structured_inputs` on all three disciplines as plain dict copies — no new import, no edit to `compute()`/`validate()`/`get_overlay_json` (D-09 crash-isolation surface unchanged).
- D-05 golden snapshot: `test_overlay_json_envelope_frozen` (`==` 6-key envelope) + three per-discipline subset (`<=`) tests asserting legacy flat keys preserved AND the new additive subkeys present.
- Heavy-absent rich-POST gate extended: a rich body (subkey-producing throw + identity keys) round-trips heavy-free, proving no raw Decimal reaches `json.dumps` (Pitfall 1).

## Task Commits

Each task was committed atomically:

1. **Task 1: Additive Decimal-string subkeys + per-discipline unit assertions** - `996d6ac` (feat; TDD RED confirmed before GREEN)
2. **Task 2: Free-text identity passthrough + heavy-absent rich-POST gate** - `fe4f249` (feat)
3. **Task 3: D-05 golden snapshot freezing the legacy /overlay-json key set** - `d7bbea0` (test)

## Files Created/Modified
- `src/segugio/ui/score_calc.py` - Additive subkeys in `_compute_disc_tf` (rebuilt throws with `score`), `_compute_freestyle` (`criteria{}`), `_compute_agility` (`faults_breakdown{}` on both numeric branches).
- `src/segugio/ui/app.py` - Identity-key allowlist (`cane`/`conduttore`/`giudici`) applied after the per-discipline branches in `_parse_structured_inputs`.
- `tests/test_score_calc.py` - Four subkey unit assertions (per-throw score, criteria, faults_breakdown, elimination-omit).
- `tests/test_imports.py` - Heavy-absent rich-POST body upgraded to subkeys + identity, with verbatim `/overlay-json` echo assertions.
- `tests/test_ui_overlay_json.py` - `LEGACY_FLAT_KEYS` + envelope-frozen test + three per-discipline preserved-and-added tests.

## Decisions Made
- `score` chosen as the per-throw field name, co-located on the throw entry (D-03 discretion).
- Identity passthrough is universal across disciplines; `dog` deliberately avoided to prevent the freestyle `dog` category collision.
- Subset (`<=`) assertion for legacy flat keys so the contract freeze blocks renames/removals but not additive growth.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Initial `test_imports.py` rich-POST assertion expected `score == "2"` but the throw carried `midair: True` (+0.5) → corrected the expected value to `"2.5"` before the GREEN run. (Test-authoring fix within the task, not a source deviation.)
- `pytest` is absent from the system Python312 interpreter; ran the suite via the repo `venv/Scripts/python.exe` (pure-stdlib score path needs no heavy deps).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Data-model half of RBT-09 is closed: the richer score rides the publish path additively with the frozen `/overlay-json` envelope intact and Phase-16 round-trip equality preserved (full suite green: `test_score_calc.py`, `test_ui_overlay_json.py`, `test_imports.py`, `test_ui_score_authoritative.py`).
- Plan 18-02 owns the render half (render_overlay_text single-line summary, `/overlay` carries no score data, XSS-sink extension to the new free-text identity fields). The identity keys are present in `fields` but reach no text/HTML sink in this plan.
- Phase-level sign-off (mark phase complete, set RBT-09 Complete) is deferred to the orchestrator/verifier per scope guard.

## Self-Check: PASSED

- `18-01-SUMMARY.md` exists on disk.
- Task commits verified present: `996d6ac`, `fe4f249`, `d7bbea0`.

---
*Phase: 18-rich-data-model-overlay-continuity-regression*
*Completed: 2026-06-27*
