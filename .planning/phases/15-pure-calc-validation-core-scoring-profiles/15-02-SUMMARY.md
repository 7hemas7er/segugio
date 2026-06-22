---
phase: 15-pure-calc-validation-core-scoring-profiles
plan: 02
subsystem: config + scoring
tags: [scoring-profiles, pydantic, config-driven, SCP-01, SCP-02, CSEN, FIDASC, FCI]
requires:
  - "segugio.ui.score_calc.ScoringProfile + compute/validate (15-01)"
  - "segugio.config.loader.load_config fail-fast SystemExit(2) (01-02)"
  - "CFG-03 DiscDogProfile|AgilityProfile discriminated union (01-02)"
provides:
  - "Pydantic ScoringProfile sub-model (ZoneBand/Bonus/FreestyleCategory) on the CFG-03 union"
  - "adapt_scoring_profile() pydantic->stdlib adapter (D-10, lazy score_calc import)"
  - "config.csen.example.yaml (pinned CSEN 2026 default), config.fidasc.example.yaml (alternate, [ASSUMED] stub-accepted), config.agility.example.yaml (generic FCI)"
  - "tests/test_score_profiles.py — profile-swap (SCP-01) + malformed fail-fast (SCP-02)"
affects:
  - "Phase 16 POST /score (adapts the active profile at the entrypoint)"
tech-stack:
  added: []
  patterns:
    - "Additive pydantic sub-model via Field(default_factory=...) so extra='forbid' configs without a scoring: block still validate (OverlayParams precedent)"
    - "pydantic->stdlib adapter with lazy in-body import keeps score_calc config-free (D-10/RBT-08)"
    - "Stub-aware swap test: assert STRUCTURAL divergence + pinned-side correctness, not the [ASSUMED] side's exact numbers"
key-files:
  created:
    - tests/test_score_profiles.py
    - config.csen.example.yaml
    - config.fidasc.example.yaml
  modified:
    - src/segugio/config/discipline.py
    - config.agility.example.yaml
decisions:
  - "[Phase 15 / 15-02]: FIDASC human-verify gate resolved as 'stub accepted for v1.3' — numbers stay [ASSUMED] (not flipped to [VERIFIED]); CSEN (pinned) carries scoring correctness; FIDASC verifiable later with no code change (D-13 ordered-band-list)"
metrics:
  duration: "~20min across two executor sessions (paused at the human-verify checkpoint)"
  completed: "2026-06-22"
  tasks: 3
  files: 5
---

# Phase 15 Plan 02: Config-Driven Scoring Profiles Summary

Scoring rules are now config-driven (SCP-01) with fail-fast validation (SCP-02): a pydantic `ScoringProfile` sub-model rides the CFG-03 discriminated union, an `adapt_scoring_profile` adapter bridges it into the plain stdlib `score_calc.ScoringProfile` (D-10, no config import leaking into the crash-isolated console), three YAML fixtures ship (CSEN pinned default, FIDASC alternate, generic FCI agility), and a CSEN -> FIDASC swap demonstrably changes the computed total with zero code change.

## What Was Built

- **Task 1 (commit 4937c33):** Pydantic `ZoneBand` / `Bonus` / `FreestyleCategory` / `ScoringProfile` sub-models on `discipline.py` with `extra="forbid"` + `Annotated[Decimal, Field(ge=0)]` constraints, attached additively to `DiscDogProfile` / `AgilityProfile` via `Field(default_factory=...)`, plus a `@model_validator` requiring zones when a disc profile declares scoring rules. `adapt_scoring_profile` maps the validated pydantic lists into the dataclass's immutable tuples with a lazy in-body `score_calc` import (D-10/RBT-08). Shipped `config.csen.example.yaml` (pinned CSEN 2026) and a generic FCI `config.agility.example.yaml`.
- **Task 2 (commit f4e8cd5):** `config.fidasc.example.yaml` written from the snippet-corroborated `[ASSUMED]` FIDASC numbers — structurally divergent from CSEN (5 zones on 45m / single +1 corridor bonus / 60s / no best-N), FIDASC Freestyle shipped as a clearly-marked stub. Then PAUSED at the blocking `checkpoint:human-verify` gate.
- **Task 3 (commit 2b0a725):** `tests/test_score_profiles.py` — `test_profile_swap_changes_result` (SCP-01) and `test_malformed_profile_fails_fast` (SCP-02). Both green; all three fixtures load through the existing loader.

## Checkpoint Resolution

The Task 2 `checkpoint:human-verify` (blocking-human) gate on the FIDASC numbers was resolved by the user as: **"approved — ACCEPT the [ASSUMED] FIDASC stub for v1.3."**

Applied exactly per that decision:
- The FIDASC numbers in `config.fidasc.example.yaml` were **NOT** changed and **NOT** flipped to `[VERIFIED]`. They remain tagged `[ASSUMED]`; FIDASC Freestyle stays a clearly-marked stub. The user explicitly accepted the stub for v1.3 — CSEN (the pinned default) carries scoring correctness.
- The "if official numbers match, flip to [VERIFIED]" path of the `<how-to-verify>` did NOT apply; the user took the "explicitly accept the clearly-marked stub" path. The `[ASSUMED]` tags + the fixture's WARNING banner remain as the future-verification breadcrumb (FIDASC can be confirmed later with no code change — D-13 ordered-band-list).

## Decisions Made

- **FIDASC = stub accepted for v1.3 (numbers stay `[ASSUMED]`).** Scoring correctness is carried by the fully-pinned CSEN default; FIDASC's genuine structural divergence (5 vs 4 zones, single +1 vs two +0.5, no best-N vs best-5) is what proves SCP-01 regardless of its exact numbers.
- **Stub-aware swap assertion.** `test_profile_swap_changes_result` pins the STRUCTURAL divergence (zone count, bonus count, best-N presence, cap presence) + CSEN's exact numeric total (23.5) + that the two totals differ — but does NOT pin FIDASC's exact total (its numerics are `[ASSUMED]`). The divergence-driven inequality holds for any structurally-different FIDASC table, so the test stays valid whether or not FIDASC is later confirmed (plan Task 3 carry-forward).

## Deviations from Plan

None — the plan executed as written. Task 3 followed the plan's explicit stub-aware path (structural divergence + CSEN correctness, FIDASC numerics gated) because the human-verify gate resolved to "stub accepted" rather than "[VERIFIED]".

## Verification

- `python -m pytest tests/test_score_profiles.py -q` → **2 passed** (SCP-01 swap + SCP-02 SystemExit(2) fail-fast).
- `load_config('config.csen.example.yaml')`, `load_config('config.agility.example.yaml')`, `load_config('config.fidasc.example.yaml')` → all exit 0 (three fixtures validate through the existing fail-fast loader).
- Tests run via `./venv/Scripts/python.exe` (the system Python has no pytest; this suite is pure stdlib + pydantic, so the CPU `venv` is correct — no GPU `venv312` needed).

## Known Stubs

- **`config.fidasc.example.yaml` — all numeric values `[ASSUMED]`, FIDASC Freestyle categories an empty-list stub.** INTENTIONAL and explicitly accepted for v1.3 (human-verify gate resolved as "stub accepted"). CSEN (pinned, `[VERIFIED]`) is the default and carries the milestone's scoring correctness. The fixture's WARNING banner + `[ASSUMED]` tags are the breadcrumb to confirm FIDASC against the official PDF later with no code change. This stub does NOT block the plan's goal — SCP-01 is proven on the structural divergence, which holds independent of the exact FIDASC numbers.

## Self-Check: PASSED

- FOUND: tests/test_score_profiles.py
- FOUND: config.csen.example.yaml
- FOUND: config.fidasc.example.yaml
- FOUND: commit 4937c33 (Task 1)
- FOUND: commit f4e8cd5 (Task 2)
- FOUND: commit 2b0a725 (Task 3)
