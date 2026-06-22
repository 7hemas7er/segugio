---
phase: 15-pure-calc-validation-core-scoring-profiles
reviewed: 2026-06-22T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/segugio/ui/score_calc.py
  - src/segugio/config/discipline.py
  - tests/test_score_calc.py
  - tests/test_score_profiles.py
  - tests/test_imports.py
findings:
  critical: 3
  critical_resolved: 3
  critical_open: 0
  warning: 5
  info: 3
  total: 11
status: issues_found
fix_iteration: 1
fix_status: criticals_resolved
---

# Phase 15: Code Review Report

**Reviewed:** 2026-06-22
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the pure scoring authority (`score_calc.py`), the config-tier pydantic profile + adapter (`discipline.py`), and the three test modules. The architecture is sound: the RBT-08 import boundary holds (verified `import segugio.ui.score_calc` succeeds with torch/cv2/numpy/flask/ultralytics/cyndilib/obsws forced absent, and it pulls in no `segugio.config`), all scoring arithmetic is `decimal.Decimal` with no float coercion, the config→UI adapter imports `score_calc` lazily, and pydantic v2 idioms are clean (no `class Config`, `@validator`, or `parse_obj`). YAML float literals (`0.5`, `0.01`) convert cleanly to `Decimal` via pydantic v2's repr-based path, so D-09 holds end-to-end through the loader. All 13 scoring/profile tests pass.

However, the adversarial pass surfaced real correctness gaps that the test suite does not cover, all centered on **untrusted input shapes** (form/JSON strings, misconfigured federation profiles). The compute brain is the keystone every later phase consumes (SCC-02), and Phase 16 makes `/score` authoritative — these defects will silently air **wrong or impossible totals** the moment real string-typed form data and operator-authored profiles flow through. The three Critical findings are: string `"false"` bonus flags scoring as truthy, and two missing fail-fast constraints (`count_best_n`, `per_throw_cap`) that let a malformed profile compute a wrong/negative total instead of exiting 2.

## Critical Issues

> **RESOLVED (fix iteration 1, 2026-06-22):** All 3 Criticals fixed with regression tests.
> CR-01 → commit `f80d2ae`, CR-02/CR-03 → commit `1437c4b`. Full phase suite green
> (`tests/test_score_calc.py tests/test_score_profiles.py tests/test_imports.py`, 44 passed).
> The 5 Warnings and 3 Info findings below remain OPEN (advisory debt). See
> `15-REVIEW-FIX.md` for the fix report.

### CR-01: [RESOLVED] Bonus flags use bare truthiness — string `"false"`/`"0"` inflate the on-air score

**File:** `src/segugio/ui/score_calc.py:274-276`
**Issue:** In `_compute_disc_tf`, bonuses are applied with `if throw.get(key):`. Form posts and JSON bodies deliver flags as **strings**, so `throw.get("midair") == "false"` is truthy and the +0.5 bonus is added; `"0"` and `"no"` are likewise truthy. `validate()` never checks the bonus-flag types at all, so this passes validation and silently inflates a broadcast total. Verified:
```
compute(disc_tf, {"throws":[{"zone":1,"midair":"false","corridor":"false"}]}, CSEN)
  -> totale "2.0"   # expected 1.0 — both +0.5 bonuses wrongly applied
```
The existing tests only pass Python `True`/`False` booleans (`test_csen_tf_best5`), which masks the defect. The `/score` route (`app.py:206`) builds `fields` straight from `request.form.items()` (all strings), and Phase 16 wires this into `compute()` per the `test_imports.py` RBT-08 comment — so the impossible-total guard the module docstring promises (lines 18-20) is defeated by real input.
**Fix:** Normalize the flag to a strict boolean before scoring, and reject ambiguous strings in `validate()`:
```python
def _is_truthy_flag(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "on"}
    return bool(v)
...
for key, value in profile.bonuses:
    if _is_truthy_flag(throw.get(key)):
        score += value
```

### CR-02: [RESOLVED] `count_best_n` has no lower-bound constraint — a negative value silently drops throws

**File:** `src/segugio/config/discipline.py:104` (and consumed at `score_calc.py:282-283`)
**Issue:** `count_best_n: int | None = None` carries no `Field(ge=...)` constraint, so a config with `count_best_n: -2` passes pydantic validation and the loader's fail-fast (SCP-02 claims malformed profiles exit 2 — this one does not). It then reaches `sorted(per_throw, reverse=True)[: profile.count_best_n]`, where Python's negative-slice semantics **drop throws from the end** instead of keeping the best N, producing a wrong total with no error. Verified:
```
ScoringProfile(zones=[{band:1,points:1}], count_best_n=-2) -> accepted
compute(disc_tf, 3x zone-1 throws) -> totale "1"  # should keep best 3 -> "3"
```
Zero (`count_best_n: 0`) is also accepted and would score every round as 0.
**Fix:** Constrain at the config tier so it fails fast:
```python
count_best_n: Annotated[int, Field(ge=1)] | None = None
```

### CR-03: [RESOLVED] `per_throw_cap` has no lower-bound constraint — a negative cap airs a negative total

**File:** `src/segugio/config/discipline.py:103` (and consumed at `score_calc.py:278-279`)
**Issue:** `per_throw_cap: Decimal | None = None` has no `ge` constraint, so `per_throw_cap: -5` passes validation and reaches `score = min(score, profile.per_throw_cap)`, capping every throw at `-5` and airing a negative round total. SCP-02 promises a malformed profile exits 2; this slips through. Verified:
```
ScoringProfile(zones=[{band:1,points:1}], per_throw_cap=Decimal("-5")) -> accepted
compute(disc_tf, [{zone:1}]) -> totale "-5"
```
**Fix:** Constrain at the config tier:
```python
per_throw_cap: Annotated[Decimal, Field(gt=0)] | None = None
```

## Warnings

### WR-01: Impossible (negative) totals can air — the "impossible total can never air" guarantee is only float-deep

**File:** `src/segugio/ui/score_calc.py:303-308` (freestyle), `330-333` (deduct_from_100)
**Issue:** The module docstring (lines 18-20) states a float-drifted *impossible total can never air*. The implementation guards drift but never floors any total at 0. Freestyle subtracts `adjustment` with no floor; `deduct_from_100` subtracts deductions + time-faults with no floor. Verified:
```
compute(disc_freestyle, sum=1, adjustment=50) -> totale "-49.00"
compute(agility deduct, course_deductions=200) -> result/totale "-100"
```
A negative broadcast score is an impossible total per the domain. `validate()` accepts a negative `adjustment` (line 209 only checks parseability) and large deductions.
**Fix:** Decide the contract explicitly. Either floor totals (`total = max(Decimal("0"), total)`) where a negative score is impossible for the discipline, or document that totals may legitimately go negative and tighten the docstring. If flooring, add a regression test pinning the floored value.

### WR-02: Negative `adjustment` accepted by validate, then subtracted — adds points instead of deducting

**File:** `src/segugio/ui/score_calc.py:208-210` (validate), `303-304` (compute)
**Issue:** `validate()` only rejects an `adjustment` that fails to parse; a negative `adjustment` (e.g. `"-100"`) passes. `compute` then does `total - adjustment`, so a negative adjustment *increases* the total — the inverse of the D-08 "deduction" intent. Verified: `validate(disc_freestyle, {..., "adjustment":"-100"})` returns `[]`.
**Fix:** Reject negative adjustment in `validate()`:
```python
adj_d = _to_decimal(adj)
if adj is not None and adj != "" and (adj_d is None or adj_d < 0):
    errors.append({"field": "adjustment", "message": "Aggiustamento non valido."})
```

### WR-03: Fractional `course_faults`/`course_deductions` pass validate, then `int()` silently truncates

**File:** `src/segugio/ui/score_calc.py:233` (validate), `327` (compute)
**Issue:** `validate()` accepts any non-negative Decimal for `course_faults` (count_up). `compute` then does `int(course_faults) + time_faults`, which truncates: `int(Decimal("2.5")) == 2`, dropping the `.5` with no error. Verified: `validate(agility, course_faults="2.5") -> []`; `compute(...) -> faults "2"`. Course faults are whole-number in both agility models, so a fractional input is operator error that should be rejected, not silently floored.
**Fix:** Reject non-integral course faults in `validate()` (reuse `_on_increment(value, Decimal("1"))`), or document the truncation.

### WR-04: `compute()` raises `AttributeError` on a non-dict throw — relies entirely on validate-first

**File:** `src/segugio/ui/score_calc.py:270` (and `184` in validate)
**Issue:** `compute` assumes `validate()` ran first (D-11), but a non-dict element in `throws` makes `throw.get("zone")` raise `AttributeError` rather than degrade. Verified: `compute(disc_tf, {"throws":["notadict"]})` raises `AttributeError`. The internal helpers are documented as "never raise into the caller" (line 99) and the live loop is no-crash (CLAUDE.md robustness). While the D-11 contract makes this unreachable in correct callers, a defensive guard mirrors the module's stated never-raise posture and protects against a future caller that skips validate.
**Fix:** Guard the loop: `if not isinstance(throw, dict): continue` (or skip with a zero score), consistent with how `validate()` already tolerates the non-dict case at line 184.

### WR-05: count_up agility emits no `totale`/`result` key — downstream renderer may read a missing key

**File:** `src/segugio/ui/score_calc.py:325-328`
**Issue:** The count_up branch sets only `out["faults"]` (plus pass-through `tempo`/`sct`); it never sets `totale` or `result`. The deduct and elimination branches both set `totale`. Verified keys for count_up: `['course_faults','faults','sct','tempo']` — no `totale`. The docstring (lines 14-16) does describe this asymmetry as intentional, but a renderer or aggregator that reads `out["totale"]` uniformly across disciplines will `KeyError` or show blank for count_up agility. Confirm `score_render`/Phase-16 consumers handle the absence, or set `out["totale"] = str(faults)` for symmetry.
**Fix:** Either set `out["totale"]` in the count_up branch for a uniform contract, or add a test pinning that the renderer tolerates a missing `totale` for count_up.

## Info

### IN-01: `FreestyleCategory` does not validate that `increment` evenly divides `(max - min)`

**File:** `src/segugio/config/discipline.py:69-84`
**Issue:** A config can declare `min:0, max:10, increment:0.03`, where no valid value lands exactly on `max`. `validate()` would then reject `10` as off-increment even though it is the declared ceiling. The `_min_le_max` validator exists but no grid-consistency check. Low impact (the shipped CSEN profile uses 0.01 which divides cleanly), but a misconfigured federation profile would surprise the operator.
**Fix:** Add a `model_validator` warning/error when `(max - min) % increment != 0`.

### IN-02: `fault_value` field is carried but never used in compute

**File:** `src/segugio/ui/score_calc.py:94`, `331`; `discipline.py:109`
**Issue:** `fault_value` is documented as "informational for count_up; reserved" and `deduct_from_100` hardcodes `Decimal(time_faults)` (1 point/fault) rather than using `fault_value`. This is dead/reserved config surface that an operator may set expecting it to take effect (e.g. `fault_value: 5` does nothing). Acceptable as a documented placeholder, but flag for clarity.
**Fix:** Either wire `fault_value` into the deduct math or mark it clearly as not-yet-honored in the config example comments.

### IN-03: `test_decimal_exactness` assertion `"19.000" not in out["totale"]` is a weak guard

**File:** `tests/test_score_calc.py:76`
**Issue:** The substring check `"19.000" not in out["totale"]` is a brittle proxy for "no float drift" — it would still pass on a drifted value like `"19.00004"` (no literal `"19.000"` prefix only if drift produced exactly that). The preceding exact assertions (`== "19.0"`, line 75) already fully pin the value, making this line redundant and potentially misleading.
**Fix:** Drop line 76; the `== "19.0"` assertion is the real guarantee.

---

_Reviewed: 2026-06-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
