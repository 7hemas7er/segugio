---
phase: 16
slug: shared-entry-component-dedicated-page-server-authoritative-p
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 16-RESEARCH.md `## Validation Architecture`. Per-task IDs are finalized when PLAN.md files exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ Flask test client; `node` subprocess for JS↔Python parity) |
| **Config file** | `tests/conftest.py` (`file_channel` fixture: `dir`/`score`/`overlay` paths) |
| **Quick run command** | `pytest tests/test_ui_score_authoritative.py tests/test_ui_score_calc_js.py -x` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (node parity test adds a subprocess; skipped if `node` absent) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_ui_score_authoritative.py tests/test_ui_score_calc_js.py -x` (the two SCC gates)
- **After every plan wave:** `pytest tests/ -q` (full suite, incl. crash-isolation + legacy round-trips)
- **Before `/gsd-verify-work`:** Full suite green, **with `node` present** so the drift-guard actually runs (not skipped)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Plan/Wave (TBD at plan) | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------------------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Wave 1 | SCC-01 | V5 / Tampering | Invalid input → 400 AND nothing written (prev on-air `score.json`/`overlay.txt` byte-untouched) | integration | `pytest tests/test_ui_score_authoritative.py::test_invalid_post_400_writes_nothing -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCC-01 | V5 | Valid input → server recomputes Decimal total → atomic `score.json` + `overlay.txt` | integration | `pytest tests/test_ui_score_authoritative.py::test_valid_post_recomputes_and_writes -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCC-01 / WR-03 | DoS(timer) | A `/score` write bumps `gen` but preserves `running`/`started_at` | integration | `pytest tests/test_ui_score_authoritative.py::test_score_preserves_run_state -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCC-01 (acceptance) | — | form total === `overlay.txt` line === `/overlay-json` total for same inputs | integration | `pytest tests/test_ui_score_authoritative.py::test_round_trip_total_equality -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCC-03 / D-09 | — | `score-calc.js .compute` === `score_calc.compute` (best-N, 0.5 bonus, freestyle cap, agility ceil, elimination, "false"/"on" flags) | unit (node) | `pytest tests/test_ui_score_calc_js.py::test_compute_byte_parity_with_python -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCC-03 | — | `score-calc.js .validate` === `score_calc.validate` (error fields match) | unit (node) | `pytest tests/test_ui_score_calc_js.py::test_validate_parity -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCE-01 | — | `score-entry.js` exports `mount` on `window` AND `module.exports`; `/score-entry` host page has NO `<input>`/calc logic of its own | unit (served-JS) | `pytest tests/test_ui_score_entry.py::test_dual_export_and_thin_host -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCE-02 | V5 / Tampering | `/score-entry` renders disc-dog → T&F+Freestyle (agility config → Agility only); fields driven by injected profile | integration | `pytest tests/test_ui_score_entry.py::test_disciplines_from_profile -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCE-02 / SCE-05 | V14 / XSS | No `innerHTML` sink for operator values (`nome`); values via `textContent` | unit (served-JS) | `pytest tests/test_ui_score_entry.py::test_no_innerhtml_sink -x` | ❌ W0 | ⬜ pending |
| Wave 1 | SCE-03 | — | Live total updates IN PLACE on input (advisory, labeled non-authoritative) | unit (node DOM, optional) | `pytest tests/test_ui_score_entry.py::test_live_total_advisory -x` | ❌ W0 | ⬜ pending |
| Wave 1 | crash-isolation (inherited RBT-08) | — | console + authoritative `POST /score` import/resolve with torch/cv2/numpy/cyndilib/obsws absent | integration | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ✅ verify green | ⬜ pending |
| Wave 1 | regression (Open Q1) | — | legacy display-only round-trips survive the authoritative transition | integration | `pytest tests/test_ui_score.py -x` | ✅ may need compat task | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui_score_authoritative.py` — SCC-01 stubs (400-write-nothing, recompute, run-state preserve, round-trip equality)
- [ ] `tests/test_ui_score_calc_js.py` — SCC-03 node byte-parity of `compute`/`validate`; clone the `_run_node` UTF-8 helper + `_requires_node` skip from `tests/test_ui_overlay_render.py`
- [ ] `tests/test_ui_score_entry.py` — SCE-01/02/05 stubs (dual export, thin host, disciplines-from-profile, no-innerHTML sink)
- [ ] Shared fixture: a `PROFILE_JSON` constant (CSEN profile as decimal-string JSON) reused by the parity test and the authoritative route test
- [ ] Decision task for Open Q1 (legacy console form transition) with its own acceptance test

*Framework install: none — pytest + Flask test client + `node` already in use. Existing `conftest.py` `file_channel` fixture covers channel paths.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator UX feel (live total cadence, on-blur error timing, persistent publish banner) | SCE-03 / SCE-05 / D-05 | Subjective interaction timing on a real tablet/field; covered structurally by automated tests but "feels right" is human | Open `/score-entry`, type a disc T&F throw list, confirm the running total updates live and the publish banner stays visible until next action |

*All correctness-bearing behaviors have automated verification; only subjective UX feel is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
