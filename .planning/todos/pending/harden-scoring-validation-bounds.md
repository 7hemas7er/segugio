---
id: harden-scoring-validation-bounds
status: pending
created: 2026-06-27
source: .planning/phases/15-pure-calc-validation-core-scoring-profiles/15-SECURITY.md
priority: medium
tags: [security, hardening, scoring, validation]
---

# Harden score_calc / scoring-profile validation bounds

Two correctness gaps surfaced by the Phase 15 adversarial security audit (2026-06-27),
**accepted as documented residual risks for v1.3** and deferred to a future hardening pass.
Both are below `block_on: high` (trusted operator/config input, no untrusted-attacker vector),
but each can air a wrong score.

## 1. Bound the freestyle `adjustment` (T-15-01 / AR-15-01)

- **File:** `src/segugio/ui/score_calc.py` (`_compute_freestyle` ~L333-336, `validate()` freestyle branch ~L216-234)
- **Gap:** `adjustment` has no sign/range bound at the `validate()` boundary, and `_compute_freestyle`
  applies the `freestyle_max` cap (40) **before** `total = total - adjustment`. An all-10 entry with
  `adjustment="-50"` passes `validate()` clean and airs `totale = 90` (> federation max 40).
- **Fix options:** validate `adjustment` sign/range at the input boundary, **or** apply the
  `freestyle_max` cap **after** subtracting the adjustment so the final aired total can never exceed max.
- **Test:** add a regression asserting all-10 + `adjustment="-50"` either errors at `validate()` or caps at `freestyle_max`.

## 2. Bound the unbounded profile scalars (T-15-06 / AR-15-02)

- **File:** `src/segugio/config/discipline.py` (`ScoringProfile.freestyle_max` L109, `time_fault_rate` L111, `fault_value` L113)
- **Gap:** these three Decimals are unbounded; a negative value loads **without** `SystemExit(2)` and flows
  through `adapt_scoring_profile` into the live `score_calc` consumer — the same harm class `CR-02/CR-03`
  already bounded for the sibling fields `per_throw_cap` (`Field(gt=0)`) and `count_best_n` (`Field(ge=1)`).
- **Fix:** add the symmetric `Field(ge=0)` (or `gt=0` where zero is nonsensical) to all three.
- **Test:** extend `tests/test_score_profiles.py::test_malformed_profile_fails_fast` to assert a negative
  `freestyle_max`/`time_fault_rate`/`fault_value` triggers `SystemExit(2)`.

## Optional (T-15-09 / AR-15-03)

Emit a runtime "FIDASC numbers UNVERIFIED" banner when `config.fidasc.example.yaml` (`[ASSUMED]` stub) is
loaded as the active profile — closes the documentation-only residual. Low priority; CSEN is the verified
default and `config.example.yaml` (the shipped default) carries no FIDASC scoring numbers.
