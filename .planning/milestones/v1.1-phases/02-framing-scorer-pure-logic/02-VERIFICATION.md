---
phase: 02-framing-scorer-pure-logic
verified: 2026-06-09T19:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 2: Framing Scorer (Pure Logic) Verification Report

**Phase Goal:** A pure, I/O-free framing scorer turns per-detection signals into a smoothed,
resolution-independent per-camera score that already encodes the domain's hardest framing
decisions (zone-gating, size target-band, lead-room, coast/TTL, confidence normalization),
provably correct on synthetic detection sequences before any detector is wired in.

**Verified:** 2026-06-09T19:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Identical normalized detection signals at two different resolutions return the same base score; EMA-smoothed per-camera score with alpha from config | ✓ VERIFIED | `test_resolution_invariant` (base.py:104-117) proves byte-identical term outputs from the same normalized sequence. EMA uses `self.alpha` read at construction from `Thresholds.alpha`. `test_ema::test_ema` verifies cold-start and lag. |
| 2 | High-weight zone outscores low-weight zone for identical detection; outside-field detection gated down — score = base × framing_weights[role][zone] | ✓ VERIFIED | `test_zone_multiplier` (zone.py:73-114) drives the real `CameraScorer` and asserts `raw_far == approx(base × 1.6)`, `raw_mid == approx(base × 1.1)`, `raw_out == approx(base × oob)` and `raw_out > 0` (never hard-zero). `gate()` terms verified. |
| 3 | During short detection dropout, score coasts (TTL hold) instead of collapsing to zero; once TTL expires subject is marked lost; CR-01 fix: re-acquisition after `lost` cold-starts at raw_0 not alpha*raw | ✓ VERIFIED | `test_coast_then_lost` (coast.py:69-107): coasting status + exact held value for TTL-1 ticks, score=0.0+lost at expiry, never-collapse invariant. `test_new_track_after_lost_cold_starts` (purity.py:254-292): `assert out.score == pytest.approx(cold)` AND `assert out.score != pytest.approx(ALPHA * cold)` — the CR-01 regression guard. scorer.py:219 resets `self.ema = None` on TTL expiry. |
| 4 | Ideal shifts TOWARD dog's motion direction (lead-room); per-camera confidence normalization prevents brightness bias | ✓ VERIFIED | `test_target_shifts_toward_motion` (leadroom.py:52-81): `ideal_x > 0.5` for `vx > 0`; zero-speed → `(0.5, 0.5)`; clamp at `lead_max`. `test_brightness_anti_bias` (confnorm.py:69-88): `abs(bright - dim) < 1e-6` after warmup; intra-camera spike still raises conf_norm. |
| 5 | Entire scorer module performs no I/O; full behavior exercised by unit tests on synthetic detection sequences | ✓ VERIFIED | `test_no_io_imports_in_framing` (purity.py:122-155): regex grep over all `src/segugio/framing/*.py` finds zero banned patterns. `test_framing_imports_with_heavy_absent`: `import segugio.framing` succeeds with torch/ultralytics/cyndilib/obsws_python forced absent. `segugio.framing` in `PHASE1_SURFACE` (test_imports.py:25). Full suite: 124 passed, 0 skipped. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/framing/signals.py` | Frozen `DetectionSignal`, `CameraScore`, `ScorerStatus` | ✓ VERIFIED | 77 lines, 3 classes, stdlib-only imports (`dataclasses`, `enum`). Frozen dataclasses with `==` determinism semantics. |
| `src/segugio/framing/params.py` | `ScorerParams` with 19 bounded fields incl. `eps` | ✓ VERIFIED | 85 lines. All 19 fields present: `sigma_c`, `ideal_size`, `sigma_s`, `w_c`, `w_s`, `w_conf`, `lead_max`, `v_deadzone`, `vel_window`, `ttl_seconds`, `beta`, `z_clip`, `warmup`, `eps`, `conf_floor`, `min_area`, `aspect_lo`, `aspect_hi`, `out_of_bounds_factor`. `eps = Field(gt=0.0)` validated. `@model_validator` enforces `w_c+w_s+w_conf == 1`. |
| `src/segugio/framing/terms.py` | 8 pure term functions, no I/O | ✓ VERIFIED | 204 lines. All 8 functions present: `gaussian_centeredness`, `gaussian_size_band`, `base_score`, `lead_room_target`, `zone_of`, `gate`, `conf_norm_step`, `plausibility_ok`. `conf_norm_step` takes `eps` as parameter (never hardcoded). No banned imports at runtime. |
| `src/segugio/framing/scorer.py` | `CameraScorer` + `MultiCamScorer` + `ttl_ticks_from_seconds` | ✓ VERIFIED | 278 lines. `CameraScorer.update()` composes all 8 terms. Coast/TTL branch sets `self.ema = None` (not 0.0) on TTL expiry (CR-01 fix at line 219). `MultiCamScorer` fans out per-tick dict to N scorers. No `hold_length_s`, no `time`, no `np.random`. |
| `src/segugio/synth/detection_stream.py` | Deterministic `DetectionSignal | None` generator | ✓ VERIFIED | `detection_stream(rng, cam_id, n_ticks, ...)` with `dropout=(start, end)` emitting `None` for the coast substrate. Injected rng is the only randomness. Re-exported from `segugio.synth`. |
| `tests/test_framing_purity.py` | FRM-07: determinism + no-I/O grep + import smoke | ✓ VERIFIED | 7 tests, all passing. `test_purity_determinism` asserts byte-identical `list[CameraScore]` from two fresh scorers on same sequence. `test_new_track_after_lost_cold_starts` has strengthened assertion: `out.score == approx(cold)` AND `out.score != approx(ALPHA * cold)`. |
| `tests/test_framing_coast.py` | FRM-05: coast, lost, recovery, MultiCamScorer | ✓ VERIFIED | 6 tests covering coast timeline, recovery (parametrized over gap=1 and gap=TTL-1), MultiCamScorer fan-out, missing-camera coast, `ttl_ticks_from_seconds`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scorer.py` | `terms.py` | `from .terms import` (line 49) | ✓ WIRED | All 8 term functions imported and called in `update()`. |
| `scorer.py` | `ScorerStatus.coasting` / `ScorerStatus.lost` | TTL countdown in absent branch | ✓ WIRED | Lines 215, 220 set correct statuses; `self.ema = None` on lost (CR-01 fix). |
| `config/models.py` | `framing/params.py` | `scoring: ScorerParams = Field(default_factory=ScorerParams)` (models.py:120) | ✓ WIRED | `Config.scoring` exposed. An omitted `scoring:` block validates via `default_factory`. |
| `test_imports.py` | `segugio.framing` | `PHASE1_SURFACE` list (line 25) | ✓ WIRED | `"segugio.framing"` in the parametrized heavy-absent import test. |
| `synth/detection_stream.py` | `framing/signals.py` | `from segugio.framing.signals import DetectionSignal` | ✓ WIRED | Correct one-way dependency (synth UP onto framing, never reverse). |

---

### Data-Flow Trace (Level 4)

Not applicable — this is a pure-computation module. There is no database, API, or external data source. All data flows from injected synthetic `DetectionSignal` sequences through deterministic term functions to `CameraScore` outputs. The scorer itself is the data pipeline under test, and its flows are verified by behavioral unit tests.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite 124 tests pass | `.venv/bin/pytest -v` | 124 passed, 0 skipped, 0 failed, 0.49s | ✓ PASS |
| CR-01 cold-start-after-lost | `test_new_track_after_lost_cold_starts` passes in full suite | `out.score == approx(cold)` AND `!= approx(ALPHA * cold)` | ✓ PASS |
| No banned imports in framing | `test_no_io_imports_in_framing` | Zero regex matches across all 5 framing `*.py` files | ✓ PASS |
| Heavy-absent import | `test_framing_imports_with_heavy_absent` | `segugio.framing` imports cleanly with torch/ultralytics/cyndilib/obsws_python blocked | ✓ PASS |
| segugio.framing coverage | `--cov=segugio.framing --cov-report=term-missing` | `__init__.py` 100%, `scorer.py` 100%, `signals.py` 100%, `terms.py` 100%, `params.py` 97% (line 80: `raise ValueError` in the weight-sum validator — intentionally uncovered defensive branch, unreachable with valid config) | ✓ PASS |

---

### Probe Execution

No probes declared or applicable for this phase (pure-Python, no scripts/tests/probe-*.sh).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FRM-01 | 02-01 | Resolution-independent base score: centeredness + size band + confidence | ✓ SATISFIED | `gaussian_centeredness`, `gaussian_size_band`, `base_score` in terms.py. `test_centeredness`, `test_size_band_peak`, `test_resolution_invariant` all pass. |
| FRM-02 | 02-02 | EMA-smoothed per-camera score (alpha from config) | ✓ SATISFIED | `CameraScorer.update()` EMA recurrence at scorer.py:189-193. `test_ema` verifies cold-start and lag. |
| FRM-03 | 02-02 | Zone-gating with `framing_weights` | ✓ SATISFIED | `zone_of` + `gate` in terms.py; CameraScorer wires them. `test_zone_multiplier` passes. |
| FRM-04 | 02-02 | Lead-room: ideal shifts toward motion | ✓ SATISFIED | `lead_room_target` in terms.py; CameraScorer uses finite-difference velocity + `lead_gain`. `test_target_shifts_toward_motion` passes. |
| FRM-05 | 02-03 | Coast/TTL: short dropout does not collapse score | ✓ SATISFIED | Coast branch at scorer.py:196-220. `test_coast_then_lost`, `test_recovery_before_ttl`, MultiCamScorer tests all pass. |
| FRM-06 | 02-02 | Per-camera confidence normalization (brightness anti-bias) | ✓ SATISFIED | `conf_norm_step` in terms.py; CameraScorer passes `p.eps` at scorer.py:171. `test_brightness_anti_bias` passes. |
| FRM-07 | 02-04 | Pure module, no I/O, unit-testable on synthetic sequences | ✓ SATISFIED | Source-grep test + heavy-absent import test + `segugio.framing` in PHASE1_SURFACE. 124 tests all pass; framing coverage 99%. |

All 7 phase-2 requirements (FRM-01..07) satisfied. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/framing/params.py` | 80 | `raise ValueError` branch in `_weights_sum_to_one` not covered by tests | ℹ Info | Intentionally uncovered defensive validator branch — fires only on a bad-config startup error, not a live behavior. Documented in the SUMMARY as acceptable. |
| `tests/test_framing_purity.py` | 43 | `from tests.conftest import SEED` — requires the full test suite import context | ℹ Info | `test_framing_purity.py` fails to collect in isolation (`pytest tests/test_framing_purity.py` alone) with `ModuleNotFoundError: No module named 'tests'`. The module works only when pytest collects all tests together (other test modules load `conftest` first). This is a test-file fragility, not a production issue. Not a blocker — all 124 tests pass in the full run. |

No TBD/FIXME/XXX debt markers found in any phase-2 source files.
No stub anti-patterns (empty `return null`, `return {}`, `=> {}`) in any implementation file.
No hardcoded empty data in rendering paths.

---

### Human Verification Required

None. This is a pure-logic, I/O-free, deterministic module. All behaviors are provable via unit tests on synthetic sequences — no visual appearance, no real-time behavior, and no external services are involved.

---

### Gaps Summary

No gaps. All 5 observable truths verified. All 7 requirements satisfied. All artifacts exist, are substantive, and are wired. The full test suite passes (124/124). The one code-review BLOCKER (CR-01: re-acquisition after `lost` blended from stale `0.0`) is confirmed fixed: `scorer.py:219` resets `self.ema = None` on TTL expiry, and `test_new_track_after_lost_cold_starts` in `test_framing_purity.py` asserts `out.score == pytest.approx(cold)` AND `out.score != pytest.approx(ALPHA * cold)` — a genuine regression guard that would fail against the pre-fix behavior.

---

_Verified: 2026-06-09T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
