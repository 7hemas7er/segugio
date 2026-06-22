---
phase: 15-pure-calc-validation-core-scoring-profiles
fixed_at: 2026-06-22T00:00:00Z
review_path: .planning/phases/15-pure-calc-validation-core-scoring-profiles/15-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
scope_note: "CRITICAL ONLY (CR-01..CR-03). WR-* and IN-* deliberately left OPEN as advisory debt."
---

# Phase 15: Code Review Fix Report

**Fixed at:** 2026-06-22
**Source review:** 15-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (Critical only — CR-01, CR-02, CR-03)
- Fixed: 3
- Skipped: 0
- Out of scope (left open): 5 Warnings + 3 Info (advisory debt, untouched)

**Verification:** `venv312/Scripts/python.exe -m pytest tests/test_score_calc.py tests/test_score_profiles.py tests/test_imports.py -q` → 44 passed.
Invariant gate held: `grep -c "float(" src/segugio/ui/score_calc.py` == 0; `score_calc.py` stays pure stdlib + `opcomm.records.Discipline` (no config import, no numpy/cv2/torch); `discipline.py` stays pydantic v2 idiomatic (Annotated + Field).

## Fixed Issues

### CR-01: Bonus flags use bare truthiness — string `"false"`/`"0"` inflate the on-air score

**Files modified:** `src/segugio/ui/score_calc.py`, `tests/test_score_calc.py`
**Commit:** f80d2ae
**Applied fix:** Added a stdlib-only `_is_truthy_flag(v)` helper (bool→itself; str→affirmative-token set `{"true","1","yes","on"}` case/space-insensitive; else `bool(v)`) and used it in the `_compute_disc_tf` bonus loop in place of bare `if throw.get(key):`. The helper only gates whether the bonus Decimal is added — no arithmetic, no float. Regression tests pin: string falsey flags (`"false"`/`"0"`/`"no"`) add NO bonus (zone-1 throw → `"1"`, the exact verbatim Decimal of `Decimal("1")`), and string truthy flags (`"true"`/`"1"`) DO add the bonus (zone-1 → `"2.0"`).

**Note on expected value:** the review's reproduction wrote "expected 1.0", but the exact-Decimal verbatim-stringification contract (D-09) yields `"1"` for a bare `Decimal("1")` zone-points score (no fractional part is introduced when no `0.5` bonus is added). The test pins the true exact value `"1"`, which is the stronger guarantee and the correct behavior.

### CR-02: `count_best_n` has no lower-bound constraint — a negative value silently drops throws

**Files modified:** `src/segugio/config/discipline.py`, `tests/test_score_profiles.py`
**Commit:** 1437c4b
**Applied fix:** Constrained the config-tier field to `count_best_n: Annotated[int, Field(ge=1)] | None = None` so a non-positive value (`-2` hits negative-slice semantics; `0` empties the slice) fails fast at config-load. Regression test (`test_count_best_n_negative_or_zero_fails_fast`, parametrized `-2` and `0`) drives the loader path → `SystemExit(2)`, proving SCP-02.

### CR-03: `per_throw_cap` has no lower-bound constraint — a negative cap airs a negative total

**Files modified:** `src/segugio/config/discipline.py`, `tests/test_score_profiles.py`
**Commit:** 1437c4b
**Applied fix:** Constrained the config-tier field to `per_throw_cap: Annotated[Decimal, Field(gt=0)] | None = None` so a negative cap (which `min(score, cap)` would apply to every throw, airing a negative total) fails fast at config-load. Regression test (`test_per_throw_cap_negative_fails_fast`, `per_throw_cap: -5`) drives the loader path → `SystemExit(2)`, proving SCP-02.

## Skipped Issues

None — all in-scope (Critical) findings fixed.

## Out of Scope (intentionally left OPEN)

Per the fix objective, only Criticals were addressed. These remain tracked as advisory debt in 15-REVIEW.md:
- WR-01 (negative totals can air — no floor), WR-02 (negative adjustment adds points), WR-03 (fractional course faults truncate), WR-04 (AttributeError on non-dict throw), WR-05 (count_up emits no `totale`/`result` key)
- IN-01 (increment doesn't evenly divide range), IN-02 (`fault_value` unused in compute), IN-03 (weak `"19.000"` substring guard)

---

_Fixed: 2026-06-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
