---
phase: 15-pure-calc-validation-core-scoring-profiles
verified: 2026-06-22T18:30:00Z
status: passed
status_history:
  - status: human_needed
    note: "Initial verifier verdict — 5/5 goal must-haves verified; 2 non-blocking human items flagged."
score: 5/5 must-haves verified
overrides_applied: 0
human_verification_resolution:
  - item: "Confirm FIDASC scoring profile fixture numbers"
    resolved: "accepted-as-stub"
    note: "User resolved the Task 2 checkpoint:human-verify during execution as 'stub accepted for v1.3'. FIDASC numbers remain [ASSUMED] by design (PDF 503s to automated fetch); CSEN 2026 (fully pinned) carries scoring correctness. Future FIDASC events: flip [ASSUMED]→[VERIFIED] with no code change (D-13 ordered-band-list)."
  - item: "Confirm REQUIREMENTS.md traceability for SCP-01 and SCP-02"
    resolved: "fixed"
    note: "Orchestrator updated REQUIREMENTS.md (commit f956032): SCP-01/SCP-02 marked [x] Complete (15-02) in both the requirement list and the Traceability table, with plan references. Implementation + tests were already green; this closed the documentation lag."
human_verification:
  - test: "Confirm FIDASC scoring profile fixture numbers"
    expected: >
      Open https://www.fidasc.it/en/cinofilia-sportiva/discdog/regolamenti-discdog/5699-discdog-2025/file.html
      and verify each [ASSUMED] value in config.fidasc.example.yaml: 5 zones on 45m field
      (9/18/27/36/45m, points 1/2/3/4/5), single +1 corridor bonus only in zone 5, 60s round,
      no best-N cap. For FIDASC Freestyle: source the official category list + per-category scale
      and replace the stub, OR explicitly re-accept it as a clearly-marked stub for v1.3.
      On confirmation flip [ASSUMED] to [VERIFIED]; on mismatch correct the values (D-13
      ordered-band-list needs no code change).
    why_human: >
      The FIDASC PDF returned HTTP 503 to automated fetch. The Task 2 checkpoint:human-verify
      gate was resolved by the user as "stub accepted for v1.3" before phase sign-off — the
      [ASSUMED] markers remain and the human-verify item is carried forward. CSEN (fully
      [VERIFIED]) carries scoring correctness for the milestone; this item is informational
      for future FIDASC events.
  - test: "Confirm REQUIREMENTS.md traceability for SCP-01 and SCP-02"
    expected: >
      SCP-01 and SCP-02 in .planning/REQUIREMENTS.md should be marked [x] Complete (not [ ] Pending),
      and the Traceability table rows for SCP-01/SCP-02 should read "Complete" with plan references,
      consistent with SCC-02/SCC-04/RBT-08 which were updated. Implementation exists and tests pass,
      but the requirements file was not updated to reflect completion.
    why_human: >
      The REQUIREMENTS.md file shows SCP-01 and SCP-02 as "- [ ]" (Pending) and the Traceability
      table shows "Pending" for both. SCC-02, SCC-04, and RBT-08 were correctly marked Complete.
      This is a documentation inconsistency — the code and tests are fully implemented and green —
      but it requires a human decision: either accept the documentation lag, or manually update
      REQUIREMENTS.md to mark them complete.
---

# Phase 15: Pure Calc + Validation Core & Scoring Profiles — Verification Report

**Phase Goal:** Build the stdlib-only `score_calc` authority (validate + compute for disc Toss&Fetch / freestyle / agility) plus config-driven scoring profiles, and add it to the crash-isolation import gate BEFORE any UI consumes it — the gating authority every later v1.3 phase inherits.
**Verified:** 2026-06-22T18:30:00Z
**Status:** passed (initial verdict human_needed; both non-blocking human items resolved — see `human_verification_resolution` in frontmatter)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Given raw inputs for any of the three disciplines, the module returns correctly auto-calculated totals — disc T&F sums throws×zone (+ bonus), freestyle sums single-judge criteria, agility applies configured model + time-faults vs SCT | ✓ VERIFIED | `test_csen_tf_best5`, `test_decimal_exactness`, `test_csen_freestyle_sum`, `test_agility_count_up`, `test_agility_deduct`, `test_agility_elimination` all pass; `compute()` is 412 lines of pure Decimal arithmetic with `grep -c "float("` == 0 |
| 2 | Given invalid inputs (out-of-range, missing required, malformed `mm:ss` time), the module reports per-field validation errors rather than computing | ✓ VERIFIED | `test_validation_errors` passes covering: zone band 9 not in CSEN zones 1-4, missing `throws`, off-increment 8.005, out-of-range 11>10, malformed times `99:60`/`2:5`/`01:30.4`; `validate()` returns `[{field, message}]`; `compute()` not called on error |
| 3 | Swapping the active scoring profile (CSEN → FIDASC) changes the computed result with NO code change; a malformed profile fails fast at config-load with a clear error | ✓ VERIFIED | `test_profile_swap_changes_result`: CSEN total `"23.5"` != FIDASC total; structural divergence asserted (4 vs 5 zones, 2 vs 1 bonuses, best-5 vs no-best-N); `test_malformed_profile_fails_fast` and CR-02/CR-03 regression tests assert `SystemExit(2)` for negative zone points / negative `count_best_n` / negative `per_throw_cap` |
| 4 | The console import-smoke gate passes with the full heavy stack + numpy ABSENT while now covering `score_calc` — a `POST /score` round-trip resolves with torch/cv2/ultralytics/numpy/cyndilib/obsws unavailable | ✓ VERIFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` passes with `import segugio.ui.score_calc` and `client.post("/score", ...)` both inside the `CONSOLE_HEAVY_MODULES` forced-absent block; `test_phase1_surface_imports_with_heavy_deps_absent[segugio.ui.score_calc]` passes |
| 5 | The module is pure-stdlib only — imports `decimal/re/dataclasses/enum` + `opcomm.records.Discipline`, never `segugio.config`/numpy/cv2/torch | ✓ VERIFIED | `grep -nE "^(import|from) " src/segugio/ui/score_calc.py` shows only `__future__`, `dataclasses`, `decimal`, `enum`, `re`, `..opcomm.records import Discipline` — no config, no heavy deps; `segugio.ui.score_calc` imports clean (`python -c "import segugio.ui.score_calc"` exits 0) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/score_calc.py` | Pure-stdlib ScoringProfile + validate + compute | ✓ VERIFIED | 412 lines; `def compute` present; `def validate` present; `AgilityModel` Enum; `CSEN_DISC_PROFILE` + `FCI_AGILITY_PROFILE` builtin constants; `_TIME_RX` strict regex; no `float(` in source |
| `tests/test_score_calc.py` | Per-discipline validate/compute unit tests vs CSEN tables | ✓ VERIFIED | 13 tests including `test_csen_tf_best5`, `test_csen_freestyle_sum`, `test_agility_count_up`, `test_agility_deduct`, `test_agility_elimination`, `test_validation_errors`, `test_decimal_exactness`; CR-01 regression tests (`test_csen_tf_string_falsey_flags_no_bonus`, `test_csen_tf_string_truthy_flags_add_bonus`); 13 passed |
| `src/segugio/config/discipline.py` | Pydantic ScoringProfile sub-model on CFG-03 union + stdlib adapter | ✓ VERIFIED | Contains `class ZoneBand`, `class Bonus`, `class FreestyleCategory`, `class ScoringProfile` (pydantic v2); `DiscDogProfile.scoring` + `AgilityProfile.scoring` additive via `Field(default_factory=ScoringProfile)`; `adapt_scoring_profile()` with lazy `from ..ui import score_calc` import; CR-02/CR-03 constraints `Annotated[int, Field(ge=1)]` / `Annotated[Decimal, Field(gt=0)]` present |
| `config.csen.example.yaml` | CSEN 2026 default disc-dog scoring profile | ✓ VERIFIED | Contains `scoring:` block with 4 zones `[VERIFIED]`, two +0.5 bonuses `[VERIFIED]`, `per_throw_cap: 5`, `count_best_n: 5`, 4 freestyle cats each min/max/increment; loads via `load_config` → adapter prints `5 5` |
| `config.fidasc.example.yaml` | FIDASC alternate scoring profile | ✓ VERIFIED (structure) / ⚠ STUB (numbers) | Exists; 5 zones + single +1 corridor bonus + no per_throw_cap/count_best_n; loads through the fail-fast loader; all numeric values tagged `[ASSUMED]`; FIDASC Freestyle is a clearly-marked empty-list stub — intentional per human-verify gate resolved as "stub accepted for v1.3" |
| `config.agility.example.yaml` | Generic FCI agility scoring profile | ✓ VERIFIED | Contains `scoring:` block with `agility_model: count_up`, `time_fault_rate: 1`, `fault_value: 5`, `elimination_sentinel: "E"`; loads via `load_config` |
| `tests/test_score_profiles.py` | Profile-swap (SCP-01) + malformed fail-fast (SCP-02) tests | ✓ VERIFIED | Contains `test_profile_swap_changes_result` and `test_malformed_profile_fails_fast`; CR-02/CR-03 regression tests `test_count_best_n_negative_or_zero_fails_fast` (parametrized -2/0) and `test_per_throw_cap_negative_fails_fast`; 5 tests pass |
| `tests/test_imports.py` | PHASE1_SURFACE extended with score_calc + heavy-absent gate | ✓ VERIFIED | `grep -c "segugio.ui.score_calc"` returns 3 (PHASE1_SURFACE entry at line 37 + in-gate import at line 114 + comment); `grep -c 'client.post("/score"'` returns 1 (line 128); 26 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/segugio/ui/score_calc.py` | `segugio.opcomm.records.Discipline` | `from ..opcomm.records import Discipline` | ✓ WIRED | Present at line 35; the only non-stdlib import |
| `src/segugio/ui/score_calc.py` | `score_render` flat keys (`prese/zona/totale`, `nome/timer/totale`, `tempo/sct/faults/result`) | `compute()` output keys | ✓ WIRED | Confirmed in `_compute_disc_tf` (lines 306-308), `_compute_freestyle` (lines 324-326), `_compute_agility` (lines 332-356) |
| `src/segugio/config/discipline.py` | `segugio.ui.score_calc.ScoringProfile` | `adapt_scoring_profile()` lazy `from ..ui import score_calc` | ✓ WIRED | Line 193; lazy in-body import preserves crash-isolation boundary (D-10/RBT-08); confirmed by `python -c "from segugio.config.discipline import adapt_scoring_profile; ..."` printing `5 5` |
| `tests/test_score_profiles.py` | `segugio.config.loader.load_config` | `load_config(path)` → `SystemExit(2)` | ✓ WIRED | `test_malformed_profile_fails_fast` exercises this path; 5 tests pass |
| `tests/test_imports.py` | `segugio.ui.score_calc` | PHASE1_SURFACE entry + in-gate `import` | ✓ WIRED | Line 37 (list) + line 114 (in-gate import under `CONSOLE_HEAVY_MODULES` forced-absent block) |
| `tests/test_imports.py` | `POST /score` | `client.post("/score", ...)` under heavy-absent block | ✓ WIRED | Line 128; assertion `resp.status_code in (204, 200)` passes |

### Data-Flow Trace (Level 4)

`score_calc.py` is a pure-computation module (no UI rendering, no DB queries). All inputs are injected via function parameters; all outputs are returned as plain dicts. Data-flow check not applicable — there is no upstream data source to trace (this IS the source, driven by injected `ScoringProfile` from the config tier).

For the config-tier adapter: `load_config(yaml) → pydantic ScoringProfile → adapt_scoring_profile() → plain score_calc.ScoringProfile`. Verified end-to-end by the profile-swap test and the `adapt_scoring_profile` spot-check producing `5 5`.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CSEN T&F best-5 correct | `pytest tests/test_score_calc.py::test_csen_tf_best5 -x -q` | 1 passed | ✓ PASS |
| Decimal exactness — best-5 == `"19.0"` | `pytest tests/test_score_calc.py::test_decimal_exactness -x -q` | 1 passed | ✓ PASS |
| Agility 52.40 vs 50.00 → 3 time-faults | `pytest tests/test_score_calc.py::test_agility_count_up -x -q` | 1 passed | ✓ PASS |
| Elimination → sentinel string `"E"` | `pytest tests/test_score_calc.py::test_agility_elimination -x -q` | 1 passed | ✓ PASS |
| CSEN → FIDASC swap changes total | `pytest tests/test_score_profiles.py::test_profile_swap_changes_result -x -q` | 1 passed | ✓ PASS |
| Malformed profile → SystemExit(2) | `pytest tests/test_score_profiles.py::test_malformed_profile_fails_fast -x -q` | 1 passed | ✓ PASS |
| Import clean (score_calc stdlib-only) | `python -c "import segugio.ui.score_calc; print('OK')"` | `OK` | ✓ PASS |
| CSEN config loads + adapter works | `python -c "from segugio.config.loader import load_config; c=load_config('config.csen.example.yaml'); from segugio.config.discipline import adapt_scoring_profile; p=adapt_scoring_profile(c.field.scoring); print(p.count_best_n, p.per_throw_cap)"` | `5 5` | ✓ PASS |
| Full phase suite green | `venv312/Scripts/python.exe -m pytest tests/test_score_calc.py tests/test_score_profiles.py tests/test_imports.py -q` | 44 passed | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared for this phase. Step 7c: N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| SCC-02 | 15-01, 15-03 | Pure `score_calc` module (stdlib only) on crash-isolated import surface | ✓ SATISFIED | Module exists, stdlib-only imports verified, `PHASE1_SURFACE` entry at line 37 of `test_imports.py`; REQUIREMENTS.md marked `[x] Complete` |
| SCC-04 | 15-01 | Auto-calculated totals for all three disciplines (Decimal-exact) | ✓ SATISFIED | `compute()` covers disc T&F / freestyle / agility both models; 13 unit tests pass; REQUIREMENTS.md marked `[x] Complete` |
| SCP-01 | 15-02 | Config-driven scoring rules — swap federation without code change | ✓ SATISFIED | `test_profile_swap_changes_result` passes: CSEN total `"23.5"` ≠ FIDASC total; structural divergence verified; REQUIREMENTS.md still shows `[ ] Pending` — documentation lag (see Human Verification section) |
| SCP-02 | 15-02 | Sensible default profile ships; malformed profile fails fast at config-load | ✓ SATISFIED | CSEN 2026 default ships as `config.csen.example.yaml`; `test_malformed_profile_fails_fast` + CR-02/CR-03 regression tests all assert `SystemExit(2)`; REQUIREMENTS.md still shows `[ ] Pending` — documentation lag |
| RBT-08 | 15-03 | Crash-isolation preserved; import-smoke gate extended; POST /score resolves heavy-free | ✓ SATISFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` passes with score_calc import + POST /score round-trip; REQUIREMENTS.md marked `[x] Complete` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `config.fidasc.example.yaml` | multiple | `[ASSUMED]` on every numeric value; `freestyle_cats: []` | ℹ Info | Intentional — accepted as stub per human-verify gate resolved "stub accepted for v1.3"; does NOT affect CSEN correctness or the profile-swap SCP-01 proof (structural divergence is real); FIDASC events should not use this fixture until numbers are confirmed |
| `tests/test_score_calc.py` | 76 | `assert "19.000" not in out["totale"]` | ℹ Info | Weak guard (IN-03 from review, advisory debt — the preceding `assert out["totale"] == "19.0"` on line 75 is the real guarantee; line 76 is redundant but not harmful) |
| `src/segugio/ui/score_calc.py` | 303-308, 330-333 | No floor at 0 for freestyle/deduct totals | ⚠ Warning | WR-01/WR-02 from review — negative `adjustment` or large deductions can air a negative total (impossible domain value). Advisory debt, not yet fixed. Phase 16 POST /score validation will be the enforced boundary; does not block phase 15 goal |
| `src/segugio/ui/score_calc.py` | 345 | `int(course_faults)` silently truncates fractional faults | ⚠ Warning | WR-03 from review — `"2.5"` → `2` with no error. Advisory debt. Phase 16 validation layer is the mitigation surface |
| `src/segugio/ui/score_calc.py` | 270 | `throw.get("zone")` raises `AttributeError` if `throws` contains non-dict | ⚠ Warning | WR-04 from review — unreachable when `validate()` runs first (D-11 contract), but no defensive guard. Advisory debt |
| `src/segugio/ui/score_calc.py` | 325-328 | `count_up` branch emits no `totale`/`result` key | ⚠ Warning | WR-05 from review — a consumer reading `out["totale"]` uniformly will `KeyError` for count_up agility. Advisory debt; the score_render flat-key contract documents this asymmetry |

No TBD/FIXME/XXX/HACK/PLACEHOLDER debt markers found in any modified source file (confirmed: the [ASSUMED] markers are YAML comments in a config fixture, not code debt markers, and they are explicitly intentional with a resolution path).

### Human Verification Required

#### 1. FIDASC Scoring Profile Numbers Confirmation

**Test:** Open https://www.fidasc.it/en/cinofilia-sportiva/discdog/regolamenti-discdog/5699-discdog-2025/file.html and verify each `[ASSUMED]` value in `config.fidasc.example.yaml` against the official FIDASC Disc Dog 2025 rulebook: zone bands (9/18/27/36/45m, points 1/2/3/4/5), single +1 corridor bonus only in the 5th zone, 60s round, no best-N cap. For FIDASC Freestyle: source the official category list + per-category scale and replace the empty-list stub, OR explicitly re-accept the stub for v1.3.
**Expected:** Either (a) numbers confirmed → flip `[ASSUMED]` to `[VERIFIED]` in `config.fidasc.example.yaml`, or (b) stub explicitly re-accepted for v1.3 → no file change needed (the warning banner already marks it).
**Why human:** The FIDASC PDF returned HTTP 503 to all automated fetch attempts. The Task 2 `checkpoint:human-verify` gate was already resolved by the user as "stub accepted for v1.3" during phase execution, so no code gap exists — this item is a carry-forward informational. CSEN (fully `[VERIFIED]`) carries the milestone's scoring correctness. Phase 15 goal is not blocked by this stub.

#### 2. REQUIREMENTS.md SCP-01 / SCP-02 Traceability Update

**Test:** Open `.planning/REQUIREMENTS.md` and verify whether SCP-01 and SCP-02 should be marked `[x]` (Complete) to match the codebase state.
**Expected:** Both requirements are implemented (pydantic sub-model + adapter in `discipline.py`, CSEN/FIDASC/FCI fixtures, `test_profile_swap_changes_result` + `test_malformed_profile_fails_fast` green). The traceability rows should read `Complete (15-02)` matching the pattern used for SCC-02, SCC-04, RBT-08. Update to `[x]` and add plan reference in the traceability table to close the documentation lag.
**Why human:** Documentation update only — no code change. Requires human decision on whether to update the REQUIREMENTS.md tracking document as a separate commit.

### Gaps Summary

No blocking gaps. All 5 roadmap success criteria are verified in the codebase. The 44-test suite (13 `test_score_calc` + 5 `test_score_profiles` + 26 `test_imports`) is green. The 3 Criticals from the code review (CR-01 bonus-flag truthiness, CR-02 count_best_n lower-bound, CR-03 per_throw_cap lower-bound) were fixed with regression tests in commits `f80d2ae` and `1437c4b`. The FIDASC stub and 5 Warnings + 3 Info items are tracked advisory debt (intentional or minor, non-blocking).

The `human_needed` status is due to:
1. The FIDASC human-verify carry-forward (pre-resolved as "stub accepted" but remains an open informational item)
2. A documentation traceability discrepancy: SCP-01 and SCP-02 are implemented and tested but remain `[ ] Pending` in REQUIREMENTS.md

---

_Verified: 2026-06-22T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
