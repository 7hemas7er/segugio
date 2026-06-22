---
phase: 15
slug: pure-calc-validation-core-scoring-profiles
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `15-RESEARCH.md` → `## Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already the project framework; `tests/test_imports.py`, `tests/conftest.py` present) |
| **Config file** | existing pytest setup (`pyproject.toml`); GPU/heavy tests run from `venv312/`, but this phase is stdlib-only and runs from any venv |
| **Quick run command** | `python -m pytest tests/test_score_calc.py tests/test_score_profiles.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~5–15 seconds (pure stdlib unit tests + import-smoke gate) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_score_calc.py tests/test_score_profiles.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (full suite, incl. the extended heavy-absent import-smoke gate)
- **Before `/gsd-verify-work`:** Full suite must be green, including the extended crash-isolation gate
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

> Task IDs assigned by the planner; rows below are keyed by requirement → test until plans land.
> Every row maps to an `<automated>` command; FIDASC numeric rows additionally gate on the
> Manual-Only `checkpoint:human-verify` items below.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| SCC-04 | CSEN T&F best-5 sum + per-throw cap 5 + two +0.5 bonuses vs pinned table | unit | `python -m pytest tests/test_score_calc.py::test_csen_tf_best5 -x` | ❌ W0 | ⬜ pending |
| SCC-04 | CSEN Freestyle 4×(0–10, 0.01) sum to max 40 | unit | `python -m pytest tests/test_score_calc.py::test_csen_freestyle_sum -x` | ❌ W0 | ⬜ pending |
| SCC-04 | Agility `count_up`: course_faults + ceil(rate×max(0,run−SCT)) | unit | `python -m pytest tests/test_score_calc.py::test_agility_count_up -x` | ❌ W0 | ⬜ pending |
| SCC-04 | Agility `deduct_from_100`: 100 − deductions − time_faults | unit | `python -m pytest tests/test_score_calc.py::test_agility_deduct -x` | ❌ W0 | ⬜ pending |
| SCC-04 | Agility elimination flag → `"E"` sentinel (never a number) | unit | `python -m pytest tests/test_score_calc.py::test_agility_elimination -x` | ❌ W0 | ⬜ pending |
| SCC-04 / D-11 | Invalid input (out-of-range, missing required, malformed `mm:ss(.cc)`, off-increment) → per-field error, NO compute | unit | `python -m pytest tests/test_score_calc.py::test_validation_errors -x` | ❌ W0 | ⬜ pending |
| SCP-01 | Swapping CSEN→FIDASC profile changes the computed result with NO code change | unit | `python -m pytest tests/test_score_profiles.py::test_profile_swap_changes_result -x` | ❌ W0 | ⬜ pending |
| SCP-02 | Malformed profile fails fast at config-load with a clear error (`SystemExit(2)`) | unit | `python -m pytest tests/test_score_profiles.py::test_malformed_profile_fails_fast -x` | ❌ W0 | ⬜ pending |
| SCC-02 / RBT-08 | `score_calc` imports clean with the full heavy stack + numpy absent | import-smoke | `python -m pytest tests/test_imports.py -k score_calc -x` | ⚠️ extend | ⬜ pending |
| RBT-08 | `POST /score` round-trip resolves with the heavy stack + numpy absent | import-smoke | `python -m pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ⚠️ extend | ⬜ pending |
| D-09 | Totals are exact `Decimal` (no float drift; best-5 == `19.0` not `19.000…04`) | unit | `python -m pytest tests/test_score_calc.py::test_decimal_exactness -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_score_calc.py` — per-discipline validate/compute vs pinned CSEN rule tables (covers SCC-04, D-09, D-11)
- [ ] `tests/test_score_profiles.py` — profile-swap (SCP-01) + malformed-profile fail-fast (SCP-02)
- [ ] `tests/test_imports.py` — extend `PHASE1_SURFACE` with `segugio.ui.score_calc` + add `import segugio.ui.score_calc` and a `POST /score` round-trip to the heavy-absent gate (RBT-08, SCC-02)
- [ ] Shared fixtures: a CSEN profile fixture + a FIDASC profile fixture (in `conftest.py` or inline)
- [ ] No framework install needed (pytest already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FIDASC Distance zone table numbers (9/18/27/36→1/2/3/4, 5-zone 45m field, single +1 corridor bonus in zone 5, 60s, no best-N) | SCP-01 / D-04 / D-05 | Official FIDASC PDF returns HTTP 503 to all automated fetch paths; numbers are snippet-corroborated `[ASSUMED]`, not authoritatively pinned | Human opens the FIDASC disc-dog Distance regulation, confirms each zone band → points value, field length, bonus rule, round duration, and any best-N cap against the FIDASC profile fixture; flip `[ASSUMED]` markers once verified |
| FIDASC Freestyle categories + scale | SCP-01 / D-04 / D-05 | Not authoritatively pinnable (three conflicting judging systems cited); shipped as a clearly-marked stub | Human sources the official FIDASC Freestyle category list + per-category scale and replaces the stub; until then the stub must NOT claim correctness |

*CSEN 2026 (the active default) is fully pinned (D-02/D-03) and carries all per-discipline correctness automatically; the FIDASC manual items gate only the FIDASC-profile numeric assertions.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_score_calc.py`, `test_score_profiles.py`, import-smoke extension)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] FIDASC `checkpoint:human-verify` items resolved or explicitly accepted as stub
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
