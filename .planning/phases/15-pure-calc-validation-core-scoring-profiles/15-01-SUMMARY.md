---
phase: 15-pure-calc-validation-core-scoring-profiles
plan: 01
subsystem: scoring
tags: [decimal, stdlib, scoring, validation, disc-dog, agility, crash-isolation, tdd]

# Dependency graph
requires:
  - phase: 05-integration (SCR-01..04)
    provides: "score_render.py display-only flat-key contract + opcomm.records.Discipline enum + ScoreDoc"
provides:
  - "segugio.ui.score_calc — pure-stdlib ScoringProfile dataclass + AgilityModel enum"
  - "validate(discipline, fields, profile) -> list[{field, message}] (D-11 per-field error contract)"
  - "compute(discipline, fields, profile) -> dict (Decimal-exact totals for disc T&F / freestyle / agility)"
  - "CSEN_DISC_PROFILE default + generic FCI_AGILITY_PROFILE builtin constants"
  - "Strict _TIME_RX mm:ss(.cc) parser (D-12) reusable by later plans"
affects: [16-shared-component-server-authoritative-post, 17-console-modal-multithrow, 18-rich-data-model, score_calc, POST-score, scoring-profile-config]

# Tech tracking
tech-stack:
  added: []  # zero new dependency — stdlib decimal/re/dataclasses/enum + opcomm.records only
  patterns:
    - "Pydantic-validate-in-config, plain-inject-into-calc (D-10): score_calc takes an injected ScoringProfile, never imports segugio.config"
    - "Quantize sums, never bonuses (Pitfall 4): exact Decimal bonus constants + min() cap, quantize only the freestyle 0.01 grid"
    - "Validate-before-compute (D-11): per-field errors gate compute; elimination sentinel checked FIRST (Pattern 4)"
    - "Decimal-native ceil time-faults (D-06): to_integral_value(ROUND_CEILING), no float round-trip"

key-files:
  created:
    - src/segugio/ui/score_calc.py
    - tests/test_score_calc.py
  modified: []

key-decisions:
  - "score_calc is the SOLE compute authority; the renderer stays display-only (SCR-04). compute() emits the exact flat keys render_overlay_text reads (prese/zona/totale | nome/timer/totale | tempo/sct/faults/result)."
  - "All arithmetic is decimal.Decimal end-to-end (D-09); zero float coercion in source (grep -c 'float(' == 0). Best-5 == '19.0' exactly, never 19.000…04."
  - "ScoringProfile is a frozen stdlib dataclass with immutable tuple fields (D-13 ordered band list) — the pydantic config profile (plan 15-02) adapts INTO this shape and is injected (D-10), keeping the import surface stdlib + opcomm.records.Discipline only (RBT-08)."
  - "CSEN 2026 is the pinned default (D-01/D-02/D-03); a generic FCI agility example ships (D-07). Both agility models implemented (count_up + deduct_from_100)."

patterns-established:
  - "Per-field validation error contract: list[{field, message}], empty == valid; throws[i].zone indexing for array fields."
  - "Strict mm:ss(.cc) regex (^(\\d{1,2}):([0-5]\\d)(?:\\.(\\d{2}))?$): malformed time -> per-field error, never a coerced 0 (D-12/Pitfall 6)."

requirements-completed: [SCC-02, SCC-04]

# Metrics
duration: 10min
completed: 2026-06-22
---

# Phase 15 Plan 01: Pure Calc + Validation Core Summary

**Pure-stdlib `score_calc` scoring authority — Decimal-exact `compute()` + per-field `validate()` for disc Toss&Fetch (best-5/cap-5/two-bonus), freestyle (4×0.01 sum minus adjustment), and agility (count_up/deduct/elimination), driven by an injected `ScoringProfile`.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-22T13:15:41Z
- **Completed:** 2026-06-22T13:25:19Z
- **Tasks:** 2 (both `tdd="true"`)
- **Files created:** 2

## Accomplishments
- `segugio.ui.score_calc` — the single, pure-stdlib compute brain every later v1.3 phase consumes: `ScoringProfile` frozen dataclass, `AgilityModel` str-Enum, `validate()`, `compute()`.
- Disc Toss & Fetch (CSEN D-02): per-throw `zone_points + exact bonuses`, capped at 5 via `min()` (never quantized), round total = best-5-of-N. Pinned example computes to exact `Decimal("19.0")`.
- Disc Freestyle (CSEN D-03/D-08): 4 categories snapped to the 0.01 grid (`ROUND_HALF_UP`), summed (max 40), then the manual `adjustment` field subtracted.
- Agility (D-06): elimination flag short-circuits to the `"E"` sentinel string FIRST; otherwise `count_up` (`course_faults + ceil(rate·max(0,run−SCT))`) or `deduct_from_100` (`100 − deductions − time_faults`), with Decimal-native ceil time-faults (52.40 vs 50.00 → 3).
- `validate()` per-field error matrix (D-11): out-of-range zone band, missing required field, off-increment freestyle category (8.005), and strict `mm:ss(.cc)` parsing (rejects `99:60`, `2:5`, `01:30.4`).
- Crash-isolation preserved: imports only `decimal`/`re`/`dataclasses`/`enum` + `opcomm.records.Discipline`; no `config`/numpy/cv2/torch; zero `float(` in source.

## Task Commits

Plan `type: tdd` — RED test gate then GREEN implementation:

1. **Task 1 + Task 2 (RED): failing scoring-authority unit tests** - `b7ca225` (test)
2. **Task 1 + Task 2 (GREEN): pure-stdlib scoring authority** - `aa422bb` (feat)

_Both plan tasks deliver behavior into the same two files (`score_calc.py` + `test_score_calc.py`). The 11 unit tests were written first (RED, module absent → ImportError), then the complete module made them green. Task 1 (T&F + freestyle + ScoringProfile + disc validate) and Task 2 (agility engine + full validate matrix) are one cohesive pure module; the GREEN commit covers both._

**Plan metadata:** committed separately with this SUMMARY + STATE/ROADMAP/REQUIREMENTS.

## TDD Gate Compliance

- RED gate present: `test(15-01): ...` (`b7ca225`) — tests failed with ImportError before the module existed.
- GREEN gate present: `feat(15-01): ...` (`aa422bb`) after RED — all 11 tests pass.
- REFACTOR: none needed beyond a docstring reword (folded into GREEN, see Deviations).

## Files Created/Modified
- `src/segugio/ui/score_calc.py` - Pure-stdlib `ScoringProfile` + `AgilityModel` + `validate()` + `compute()` + `_TIME_RX` + `CSEN_DISC_PROFILE` / `FCI_AGILITY_PROFILE` builtin profiles.
- `tests/test_score_calc.py` - 11 unit tests: CSEN T&F best-5, freestyle sum + adjustment, agility count_up/deduct/elimination, validation-error matrix, decimal-exactness, per-throw cap, validate-then-compute, public-surface sanity.

## Decisions Made
None beyond the plan — followed the pinned CSEN tables (D-02/D-03), D-06..D-13 technical choices, and the score_render flat-key contract exactly as specified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded two docstring mentions of `float(...)` so the source gate passes**
- **Found during:** Task 2 (acceptance criterion `grep -c "float(" src/segugio/ui/score_calc.py` must return 0)
- **Issue:** Two docstring lines described the D-09 invariant using the literal token `float(...)` / `float()`, so the literal `grep -c "float("` returned 2 despite there being no float coercion anywhere in the arithmetic path.
- **Fix:** Reworded both docstrings to "no float coercion" (same meaning, no `float(` token). The arithmetic path was already 100% Decimal-native.
- **Files modified:** src/segugio/ui/score_calc.py
- **Verification:** `grep -c "float(" src/segugio/ui/score_calc.py` → 0; all 11 tests still green.
- **Committed in:** aa422bb (GREEN feat commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, doc-only).
**Impact on plan:** Cosmetic doc reword to satisfy a literal source gate; no behavior change, no scope creep.

## Issues Encountered
- Full-suite run surfaced 5 PRE-EXISTING failures unrelated to this plan (`test_ndi_mock_sender`, `test_ndi_source` — NDI loopback/environmental; `test_ui_explainability`, `test_ui_scv_unification`, `test_ui_tablet_layout` — node/JS UI-harness/markup). These are known carry-forwards (MEMORY.md "2 environmental NDI-loopback CI failures" + node-env UI tests) and out of scope per the SCOPE BOUNDARY. Logged to `deferred-items.md`, not fixed. All 11 `test_score_calc.py` tests pass.

## User Setup Required
None - pure-logic module, no external service configuration.

## Next Phase Readiness
- The compute authority is built and proven STANDALONE, exactly as the milestone keystone requires (built before any UI consumes it).
- Plan 15-02 (config-driven scoring profiles): add the pydantic `ScoringProfile` sub-model to the CFG-03 discriminated union + the `pydantic → score_calc.ScoringProfile` adapter (D-10). `score_calc.ScoringProfile` field shape is the injection target.
- Plan 15-03 (crash-isolation gate): extend `PHASE1_SURFACE` with `segugio.ui.score_calc` + the heavy-absent `POST /score` round-trip (RBT-08).
- No blockers. FIDASC profile numbers (D-05) remain a `checkpoint:human-verify` item for the profile plan, not this one.

## Self-Check: PASSED
- `src/segugio/ui/score_calc.py` — FOUND
- `tests/test_score_calc.py` — FOUND
- Commit `b7ca225` (RED) — FOUND
- Commit `aa422bb` (GREEN) — FOUND
- 11/11 `test_score_calc.py` tests pass; import clean; `float(` count == 0; import allowlist = stdlib + opcomm.records only.

---
*Phase: 15-pure-calc-validation-core-scoring-profiles*
*Completed: 2026-06-22*
