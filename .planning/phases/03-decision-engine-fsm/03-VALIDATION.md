---
phase: 3
slug: decision-engine-fsm
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `03-RESEARCH.md` §Validation Architecture. Task IDs are assigned during planning (§Per-Task Verification Map filled by planner/executor).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (+ pytest-cov 7.1.0) — already in `.venv` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`) — already present |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_decision_*.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ --cov=segugio.decision --cov-report=term-missing` |
| **Estimated runtime** | ~5 seconds (pure CPU unit tests, no heavy deps) |

> Run via `.venv/bin/python -m pytest` — system `python3` does not see numpy.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_decision_*.py -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ --cov=segugio.decision --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite green + high `segugio.decision` coverage (pure module → approach 100%)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Requirement-level map (task IDs `03-PP-TT` assigned during planning). Every requirement below MUST land on at least one task with an `<automated>` verify.

| Requirement | Plan | Wave | Behavior to sample | Threat Ref | Test Type | Automated Command | File Exists | Status |
|-------------|------|------|--------------------|------------|-----------|-------------------|-------------|--------|
| DEC-01 | 03-01 | 1 | Live target changes ONLY via a guarded transition; a failed guard is a silent no-op (target unchanged when guard predicate false) | — | unit | `.venv/bin/python -m pytest tests/test_decision_invariants.py::test_no_decision_outside_guard -x` | ❌ W0 | ⬜ pending |
| DEC-02 | 03-01 | 1 | Replay `ping_pong` → transition count ≤ 1 after warm-up; replay `tie` → ≤ 1 (zero-spurious-cut) | — | unit | `.venv/bin/python -m pytest tests/test_decision_hysteresis.py::test_no_chase_pingpong -x` | ❌ W0 | ⬜ pending |
| DEC-02 | 03-01 | 1 | Challenger must exceed incumbent by `hysteresis_margin` AND sustain `debounce_N` ticks; cut blocked while `dwell_elapsed < min_dwell` and during `cooldown` | — | unit | `.venv/bin/python -m pytest tests/test_decision_hysteresis.py::test_dwell_debounce_cooldown -x` | ❌ W0 | ⬜ pending |
| DEC-03 | 03-02 | 2 | While `action_hold` set, no auto-switch fires even if a challenger qualifies; max-cap forces release after the cap | T-3-02 | unit | `.venv/bin/python -m pytest tests/test_decision_holds.py::test_action_hold_suppresses_and_caps -x` | ❌ W0 | ⬜ pending |
| DEC-04 | 03-02 | 2 | `occlusion_hold` suppresses switching, auto-expires after `hold_length_s`-derived ticks (disc 2.5 / agility 1.5), and is max-capped | T-3-02 | unit | `.venv/bin/python -m pytest tests/test_decision_holds.py::test_occlusion_hold_bounded -x` | ❌ W0 | ⬜ pending |
| DEC-05 | 03-02 | 2 | Near-tie inside dead-band → incumbent wins; no incumbent → first camera in config declaration order | — | unit | `.venv/bin/python -m pytest tests/test_decision_tiebreak.py -x` | ❌ W0 | ⬜ pending |
| DEC-06 | 03-02 | 2 | A camera with `alive=False` is NEVER emitted as target and NEVER counted as challenger; live-feed-death cuts to best-alive (or SAFE) bypassing dwell/cooldown | T-3-01 | unit | `.venv/bin/python -m pytest tests/test_decision_feeddeath.py::test_dead_never_live_nor_challenger -x` | ❌ W0 | ⬜ pending |
| DEC-07 | 03-04 | 3 | Same seed + same scenario → byte-identical `list[Decision]` (determinism); all four `SCENARIOS` + override + occlusion drive without error | — | unit | `.venv/bin/python -m pytest tests/test_decision_determinism.py -x` | ❌ W0 | ⬜ pending |
| RBT-03 | 03-03 | 2 | force → (cam dies → SAFE/best-live, mode stays OVERRIDE) → recovers (snaps back) → release → auto-resume only after full hysteresis + min_dwell | T-3-03 | unit | `.venv/bin/python -m pytest tests/test_decision_override.py::test_force_death_recover_release_resume -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Two Hard Safety Invariants (assert explicitly, in every scenario)

1. **Never emit a decision outside a guarded transition (DEC-01):** in every test, assert the target only ever changes on a tick where a named guard passed; expose the firing transition's name in `Decision.reason` and assert `reason != "none"` on exactly the ticks where `target` changed.
2. **Never air a dead feed (DEC-06):** in every scenario that includes `feed_death`, assert `alive[decision.target] is True OR decision.target == "SAFE"` for **all** ticks — including override scenarios (the forced-but-dead case).

---

## Wave 0 Requirements

- [ ] `src/segugio/decision/__init__.py`, `signals.py`, `engine.py`, `clocks.py` — the module under test (stub surface)
- [ ] `pyproject.toml` — move `transitions==0.9.3` to light `dependencies`; `pip install` into `.venv`
- [ ] `tests/test_imports.py` — add `"segugio.decision"` to `PHASE1_SURFACE`; keep `transitions` OUT of `HEAVY_MODULES`
- [ ] `tests/conftest.py` — add a `thresholds`/`decision_config` fixture (reuse `valid_config_dict`, `seeded_rng`); an `fps` constant; a `_as_camera_scores(samples, status_default)` adapter helper
- [ ] `tests/test_decision_invariants.py`, `test_decision_hysteresis.py`, `test_decision_holds.py`, `test_decision_tiebreak.py`, `test_decision_feeddeath.py`, `test_decision_override.py`, `test_decision_determinism.py` — test files (stubs for the requirements above)
- [ ] No framework install needed — pytest/pytest-cov already in `.venv`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| (none) | — | — | — |

*All phase behaviors have automated verification — the FSM is pure, tick-driven, and deterministic, so every requirement is unit-testable on synthetic streams.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
