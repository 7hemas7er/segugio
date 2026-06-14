---
phase: 2
slug: framing-scorer-pure-logic
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md → ## Validation Architecture`. The scorer is a pure,
> I/O-free module → every FRM behavior maps to an observable unit assertion on a
> seeded synthetic detection sequence. Coverage should approach 100%.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (+ pytest-cov 7.1.0) — already in `.venv` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`) — already present |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_framing_*.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ --cov=segugio.framing --cov-report=term-missing` |
| **Estimated runtime** | ~5 seconds (pure CPU unit tests, no heavy deps) |

> Run tests via `.venv/bin/python -m pytest` — system `python3` does not see numpy.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_framing_*.py -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ --cov=segugio.framing --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite green + high coverage of `segugio.framing` (pure module → should approach 100%)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Plan/Task IDs assigned by the planner (run next). Each requirement below MUST be
> claimed by at least one plan task whose `<acceptance_criteria>` runs the listed command.

| Requirement | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| FRM-01 | Same normalized sequence at two "resolutions" → identical scores; base ∈ [0,1] | T-2-01 | `np.clip` outputs to [0,1] (no throw on out-of-range) | unit | `.venv/bin/python -m pytest tests/test_framing_base.py::test_resolution_invariant -x` | ❌ W0 | ⬜ pending |
| FRM-01 | Size score PEAKS at `ideal_size`, lower for smaller AND larger (non-monotonic) | — | N/A | unit | `.venv/bin/python -m pytest tests/test_framing_base.py::test_size_band_peak -x` | ❌ W0 | ⬜ pending |
| FRM-01 | Centeredness max at ideal point, decays with distance | — | N/A | unit | `.venv/bin/python -m pytest tests/test_framing_base.py::test_centeredness -x` | ❌ W0 | ⬜ pending |
| FRM-02 | Cold start seeds `s_0 = raw_0` (not 0); smaller α lags more than larger α | — | N/A | unit | `.venv/bin/python -m pytest tests/test_framing_ema.py -x` | ❌ W0 | ⬜ pending |
| FRM-03 | In-zone `base × framing_weights[role][zone]`; outside-all → `base × out_of_bounds_factor` | T-2-03 | Missing weight defaults to neutral `1.0` | unit | `.venv/bin/python -m pytest tests/test_framing_zone.py::test_zone_multiplier -x` | ❌ W0 | ⬜ pending |
| FRM-04 | Dog moving right → `ideal_x > 0.5`; dog behind shifted ideal outscores dead-center; lead clamped at `lead_max` | T-2-01 | Guard divisor `speed≥v_deadzone` | unit | `.venv/bin/python -m pytest tests/test_framing_leadroom.py::test_target_shifts_toward_motion -x` | ❌ W0 | ⬜ pending |
| FRM-05 | Dropout holds score (status `coasting`) for `ttl_ticks`, then 0 (status `lost`); recovery before TTL resumes `tracking` w/o cold-start | — | Never feed `raw=0` into EMA; never collapse to 0 mid-window | unit | `.venv/bin/python -m pytest tests/test_framing_coast.py::test_coast_then_lost -x` | ❌ W0 | ⬜ pending |
| FRM-06 | Two cams identical framing, one +conf bias → score within ε after normalization; intra-cam spike still registers | — | N/A | unit | `.venv/bin/python -m pytest tests/test_framing_confnorm.py::test_brightness_anti_bias -x` | ❌ W0 | ⬜ pending |
| (guard) | Implausible aspect / sub-min-size / sub-conf-floor detection rejected → treated as no-detection (coast) | T-2-01 | NaN/inf treated as "no detection"; guard every divisor | unit | `.venv/bin/python -m pytest tests/test_framing_shadow.py -x` | ❌ W0 | ⬜ pending |
| FRM-07 | Same `DetectionSignal` seq → byte-identical `CameraScore` list; no `time`/`np.random`/I/O in `framing/`; imports with torch/cyndilib absent | — | N/A | unit + smoke | `.venv/bin/python -m pytest tests/test_framing_purity.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Threat refs map to `02-RESEARCH.md → ## Security Domain`: T-2-01 = NaN/inf propagation (DoS); T-2-03 = unvalidated scorer params reaching the live loop. Both LOW severity — none meet the `high` block threshold.*

---

## Wave 0 Requirements

- [ ] `src/segugio/framing/__init__.py`, `signals.py`, `terms.py`, `scorer.py`, `params.py` — the module under test
- [ ] `src/segugio/synth/detection_stream.py` + re-export in `synth/__init__.py` — NEW input generator (distinct from `score_stream`)
- [ ] `ScorerParams` pydantic sub-model added to `segugio.config` (+ defaults in `config.example.yaml`)
- [ ] `tests/test_framing_base.py`, `test_framing_ema.py`, `test_framing_zone.py`, `test_framing_leadroom.py`, `test_framing_coast.py`, `test_framing_confnorm.py`, `test_framing_shadow.py`, `test_framing_purity.py`
- [ ] `tests/conftest.py` — add a `scorer_params` fixture (seeded defaults); reuse `valid_config_dict` / `seeded_rng` from Phase 1
- [ ] No framework install needed — pytest/pytest-cov already in `.venv`

---

## Manual-Only Verifications

*None — all phase behaviors have automated unit verification on synthetic sequences (the phase's defining property: FRM-07).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
