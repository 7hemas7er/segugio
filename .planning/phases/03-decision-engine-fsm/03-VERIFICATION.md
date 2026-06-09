---
phase: 03-decision-engine-fsm
verified: 2026-06-09T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm WR-01 liveness model change is the intended contract"
    expected: "A camera the alive map reports alive but that sends no CameraScore row this tick is treated as live-but-not-eligible-challenger (not a dead feed). The alive map is the sole liveness authority; score-row absence does NOT trigger feed_emergency."
    why_human: "WR-01 fix changed the semantic source of truth for feed-death from score-row presence to the alive map. The engine's own docstring claims this is correct, and all 167 tests pass, but the boundary between Phase-2 scorer output and Phase-3 liveness input is not formally specified anywhere. A developer must confirm the new liveness-vs-eligibility split matches the Phase-2 -> Phase-3 contract before it is inherited by Phase-5 wiring."
  - test: "Confirm WR-03 hold-cap semantics: inclusive <= means exactly cap suppressed ticks"
    expected: "action_hold_age increments to 1 on the first held tick; the <= cap test keeps the hold active for ages 1..cap (exactly cap suppressed ticks); the cut fires at age cap+1. This is claimed to be symmetric with the occlusion path. Confirm this is the intended cap meaning and not off-by-one relative to how cap will be configured in production."
    why_human: "The fix deliberately REJECTED the review's suggested < change on empirical grounds. Two engineers now hold different readings of the boundary semantics. A developer must confirm the chosen 'cap = suppressed ticks' (not 'max age index') interpretation is intentional and will be documented for Phase-5 callers."
  - test: "Confirm WR-05 feed_emergency source change: override source dropped, in-override reconciliation owns forced-but-dead"
    expected: "While in OVERRIDE mode, a dying forced camera is handled by the per-tick forced-but-dead reconciliation branch in tick() (lines 559-571), not by the feed_emergency transition. The feed_emergency transition now declares source=[\"auto\"] only. Confirm this matches the intended architecture — that in-override feed-death is always reconciled in-place (D-03) rather than by a state-machine edge."
    why_human: "This is a state-machine edge and call-site logic change. The full suite passes including the override+feed-death combined scenarios, but the reachability of the override source was vestigial per the review. A developer should confirm the intended reachability matches the design intent before Phase-5 wires the override command path."
---

# Phase 3: Decision Engine FSM Verification Report

**Phase Goal:** A `transitions`-based finite state machine becomes the sole authority on which camera is live — consuming per-camera scores and feed-liveness events to emit guarded, jitter-free switching decisions that never double-cut, never flicker, never select a dead feed, hold through climaxes and expected occlusions, and support manual override with automatic resume.
**Verified:** 2026-06-09T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No switch fires outside a guarded FSM transition (DEC-01) | ✓ VERIFIED | `self.target` assigned only in 5 named callbacks (_set_target_safe, _emergency_cut, _promote_challenger, _apply_force, in-override reconciliation). `test_no_decision_outside_guard` asserts target changes == reason!="none" ticks across 40 ticks. 100% engine.py coverage. |
| 2 | Ping-pong and tie score streams produce <= 1 transition after warm-up (DEC-02) | ✓ VERIFIED | `test_no_chase_pingpong` and `test_no_chase_tie` / `test_tie_stream_no_oscillation` all pass. Hysteresis margin + debounce_N + min_dwell + cooldown gates verified individually in `test_dwell_debounce_cooldown`. |
| 3 | A dead feed is never the live target or challenger; dying live feed triggers immediate emergency cut to best-alive or SAFE (DEC-06) | ✓ VERIFIED | `test_dead_never_live_nor_challenger`, `test_live_feed_death_emergency_cuts_immediately`, `test_all_cameras_dead_cuts_to_safe`, `test_recovery_out_of_safe_reacquires_promptly` (CR-01 regression) all pass. Hard invariant `alive[target] is True OR target == "SAFE"` asserted in every scenario. |
| 4 | Action-hold and occlusion-hold suppress switching while set, each bounded by mandatory max-cap; death wins over hold (DEC-03, DEC-04) | ✓ VERIFIED | `test_action_hold_suppresses_and_caps`, `test_occlusion_hold_bounded`, `test_occlusion_cap_bounds_a_long_hold_length`, `test_agility_occlusion_bound_is_shorter`, `test_feed_death_wins_over_hold` all pass. `holding` guard is on `auto_switch` only — NOT on `feed_emergency` (verified by source). |
| 5 | Near-tied scores resolve to incumbent; no incumbent resolves to first config-declaration camera; no role-priority (DEC-05) | ✓ VERIFIED | `test_incumbent_wins_near_tie`, `test_no_incumbent_resolves_config_order`, `test_no_incumbent_config_order_is_independent_of_score_argument_order`, `test_tie_stream_no_oscillation` all pass. No role-priority concept exists in engine.py (grep confirmed). |
| 6 | Manual override forces a camera immediately (bypasses dwell/debounce/cooldown); persists through feed-death of forced cam; ends only on explicit release; auto-resume requires full qualification (RBT-03) | ✓ VERIFIED | `test_force_is_immediate`, `test_force_dead_camera_shows_safe_not_dead`, `test_no_auto_expire`, `test_release_does_not_snap_to_argmax`, `test_force_death_recover_release_resume` all pass. `override_cam` sticky attribute confirmed. |
| 7 | Same seed + scenario produces byte-identical list[Decision] across four SCENARIOS; full input contract (scores+alive+holds+override) is deterministic (DEC-07) | ✓ VERIFIED | `test_purity_determinism` and `test_purity_determinism_full_input_contract` both pass across all four SCENARIOS. `test_all_scenarios_drive_without_error` parametrized — 4 scenarios, no exceptions. |
| 8 | Combined high-value interactions: force+release+resume, hold-through-occlusion, feed-death-mid-hold (death wins) all pass with both hard safety invariants asserted | ✓ VERIFIED | `test_force_release_resume`, `test_hold_through_occlusion_then_release`, `test_live_feed_death_mid_hold_death_wins` all pass. `assert_no_decision_outside_guard` and `assert_never_airs_dead_feed` applied to every combined scenario. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/decision/signals.py` | Frozen Decision/HoldInput/OverrideCmd records + Mode str-Enum | ✓ VERIFIED | All four records present, frozen=True dataclasses, Mode(str,Enum) with safe/auto/override. `override_dead_fallback` added to Decision.reason docstring (WR-02 fix). OverrideCmd.__post_init__ rejects ambiguous force+release (WR-04 fix). |
| `src/segugio/decision/clocks.py` | ticks_from_seconds(seconds, fps) -> int | ✓ VERIFIED | Exact clone of Phase-2 precedent. Returns ceil(seconds*fps) >= 1. Verified: (2.0,30)=60, (1.0,30)=30, (0.001,30)=1. |
| `src/segugio/decision/engine.py` | DecisionEngine: transitions.Machine wrapper + tick() loop + all guards | ✓ VERIFIED | 167 lines, 100% coverage, `from transitions import Machine` at top, Machine constructed with _STATES/_TRANSITIONS, all guard predicates implemented, full priority ladder. |
| `src/segugio/decision/__init__.py` | Barrel re-exporting DecisionEngine, Decision, Mode, HoldInput, OverrideCmd, ticks_from_seconds | ✓ VERIFIED | All 6 symbols exported in `__all__`. 100% coverage. |
| `tests/test_decision_determinism.py` | DEC-07 determinism gate over synthetic score + feed-death streams | ✓ VERIFIED | 6 tests, all pass. Covers bare scores and full input contract (alive+holds+override) across all 4 SCENARIOS. |
| `tests/test_decision_scenarios.py` | Combined high-value cross-scenario suite + shared safety invariant assertions | ✓ VERIFIED | 4 tests, all pass. Both shared helpers (`assert_no_decision_outside_guard`, `assert_never_airs_dead_feed`) applied in every combined scenario. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml dependencies` | `transitions==0.9.3` | Light runtime dependencies list | ✓ WIRED | Line 17: `"transitions==0.9.3"` in `[project.dependencies]` (not in heavy group). `test_imports.py` parametrized test includes `segugio.decision` and passes. |
| `tests/test_imports.py PHASE1_SURFACE` | `segugio.decision` | Added to lazy-import surface list | ✓ WIRED | Line 26: `"segugio.decision"` in PHASE1_SURFACE with inline comment. All 15 test_imports.py tests pass. |
| `src/segugio/decision/engine.py` | `transitions.Machine` | Module-top-level import + Machine construction | ✓ WIRED | Line 66: `from transitions import Machine`. Machine constructed at line 256 with model=self, states, transitions, initial="safe". |
| `engine.py tick()` | alive map | eligible-candidate filter excludes dead feeds before argmax | ✓ WIRED | Lines 455-459: `self._alive` computed from alive map (not score presence, WR-01 fix). Lines 485-490: `score_by_cam` additionally gated by `alive.get(cs.cam_id, False)`. |
| `engine.py` | `ticks_from_seconds(hold_length_s, fps)` | occlusion-hold bound derived from per-discipline hold_length_s | ✓ WIRED | Line 205: `self.occlusion_hold_ticks = ticks_from_seconds(hold_length_s, fps)`. Constructor parameter `hold_length_s: float = 2.5`. |
| `engine.py` | `override_cam` attribute | sticky forced id separate from aired target | ✓ WIRED | Line 234: `self.override_cam: str | None = None`. Set in `_apply_force` (line 404), cleared in `_begin_resume_qualification` (line 422). Used in per-tick forced-but-dead reconciliation (lines 561-571). |

### Data-Flow Trace (Level 4)

Not applicable — this module is pure logic (no I/O, no database, no API). The `tick()` method takes typed inputs and returns a frozen record; there is no rendering or dynamic data source to trace.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 42 decision tests pass | `.venv/bin/python -m pytest tests/test_decision_*.py -q` | 42 passed in 0.46s | ✓ PASS |
| Full suite 167 tests pass | `.venv/bin/python -m pytest tests/ -q` | 167 passed in 1.67s | ✓ PASS |
| Decision module coverage 100% | `.venv/bin/python -m pytest tests/ --cov=segugio.decision --cov-report=term-missing` | engine.py 100%, signals.py 100%, clocks.py 100%, __init__.py 100% | ✓ PASS |
| Package imports with heavy deps absent | `test_imports.py` parametrized test for segugio.decision | 15 passed | ✓ PASS |
| ticks_from_seconds edge cases | `.venv/bin/python -c "from segugio.decision import ticks_from_seconds; ..."` | (2.0,30)=60, (1.0,30)=30, (0.001,30)=1 | ✓ PASS |

### Probe Execution

No probes declared in PLAN files; no conventional probe scripts found for this phase. Step 7c: SKIPPED (no probes declared).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEC-01 | 03-01 | FSM is sole authority; no OBS command outside a guarded transition | ✓ SATISFIED | `test_no_decision_outside_guard` + DEC-01 docstring tracing in engine.py. Target only changes in 5 named callbacks. |
| DEC-02 | 03-01 | Hysteresis dead-band + min_dwell + debounce_N + cooldown; no flicker | ✓ SATISFIED | `test_no_chase_pingpong`, `test_no_chase_tie`, `test_dwell_debounce_cooldown`. Both guards proven in invariants suite. |
| DEC-03 | 03-02 | Action-hold state: delay cut during action | ✓ SATISFIED | `test_action_hold_suppresses_and_caps`. `holding` guard on `auto_switch` unless clause. Max-cap asserted exactly. |
| DEC-04 | 03-02 | Occlusion-hold: don't cut during expected tunnel/contact; per-discipline hold_length_s | ✓ SATISFIED | `test_occlusion_hold_bounded`, `test_agility_occlusion_bound_is_shorter`. disc=75t, agility=45t both verified. |
| DEC-05 | 03-02 | Deterministic tiebreaker: incumbent-wins; config-order with no incumbent | ✓ SATISFIED | `test_incumbent_wins_near_tie`, `test_no_incumbent_resolves_config_order`, score-list-order independence test. |
| DEC-06 | 03-02 | Feed-alive guard: dead camera never live or challenger | ✓ SATISFIED | `test_dead_never_live_nor_challenger`, `test_live_feed_death_emergency_cuts_immediately`. Hard invariant `alive[target] OR SAFE` in all scenarios. CR-01 SAFE-cooldown regression test passes. |
| DEC-07 | 03-04 | FSM unit-testable on synthetic streams; deterministic replay | ✓ SATISFIED | `test_purity_determinism` (4 SCENARIOS) + `test_purity_determinism_full_input_contract` (full typed input surface). |
| RBT-03 | 03-03 | Manual override + auto-resume | ✓ SATISFIED | `test_force_death_recover_release_resume` (full locked sequence), `test_force_is_immediate`, `test_no_auto_expire`, `test_release_does_not_snap_to_argmax`. |

All 8 requirements satisfied. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/decision/engine.py` | 78-86 | `to_safe` transition defined but `tick()` never calls `self.to_safe()` | ℹ️ Info (IN-01, unfixed) | Dead transition graph edge. All SAFE routing goes through `feed_emergency` SAFE edge and in-override reconciliation. No correctness impact; misleads graph readers. |
| `src/segugio/decision/engine.py` | 435-441 | tick() docstring says "only auto_switch this plan (override/feed-death/hold edges land in 03-02/03-03)" | ℹ️ Info (IN-02, unfixed) | Stale 03-01-scoped text in the fully-implemented engine. Misleads readers about what tick() does. |
| `src/segugio/decision/engine.py` | 443 | `tick_idx = scores[0].tick if scores else 0` | ℹ️ Info (IN-03, unfixed) | Empty scores list emits Decision(tick=0,...) regardless of real frame index. No correctness impact in current use (orchestrator always passes non-empty batches per Phase-2 contract), but corrupts tick in edge case. |
| `tests/test_decision_holds.py` | 24 | `from segugio.decision.signals import SAFE_TARGET, HoldInput` — SAFE_TARGET imported but not referenced in any test body | ℹ️ Info (IN-04, unfixed) | Minor lint noise; not a correctness issue. |

No `TBD`, `FIXME`, or `XXX` markers found in any decision module file. No blocker debt markers.

Note: IN-01 through IN-04 were explicitly scoped out of the review fix pass (03-REVIEW-FIX.md). They are documentation/minor quality issues with no correctness impact.

### Human Verification Required

Three items were flagged "requires human verification" in the code review fix report (03-REVIEW-FIX.md). All 167 tests pass, but a developer must confirm these semantic choices before Phase-5 wires the engine into the live orchestrator:

#### 1. WR-01 Liveness Model Change

**Test:** In the Phase-5 orchestrator, verify that a camera the alive map reports `alive=True` but that sends no CameraScore row on a given tick (a plausible coast gap or sparse batch) is treated as live-but-not-eligible-challenger, NOT as a dead feed triggering an emergency cut.
**Expected:** The engine keeps the live-but-unscored incumbent on air. The alive map is the sole liveness authority — `live_feed_dead()` reads `self._alive` (the alive map), not `_alive_eligible` (score-row presence). A missing score row means the camera is not a candidate this tick but is still live.
**Why human:** This changed the engine's liveness model. The fix is correct per the engine's own docstring, but the boundary contract between Phase-2 (scorer emits CameraScore per camera per tick, including `lost` status at score 0.0) and Phase-3 (FSM consumes liveness from the alive map) is not formally verified in integration. A developer must confirm the Phase-5 pipeline never produces a state where the alive map and score-row presence disagree in a way that reveals a gap in this model.

#### 2. WR-03 Hold-Cap Semantics

**Test:** Review the action hold cap semantics: with `action_hold_cap_ticks=5`, confirm the hold suppresses cuts for exactly 5 ticks (ages 1..5) and the cut fires on the 6th tick (age 6). Confirm this is symmetric with the occlusion hold (armed to `bound`, suppresses for exactly `bound` ticks).
**Expected:** Exactly `cap` suppressed ticks. The inclusive `<= cap` comparator is required for this (a strict `<` would cap at `cap-1`). The `test_action_hold_suppresses_and_caps` test now asserts `suppressed_ticks == cap` and `cut_after_cap == cap`.
**Why human:** The review suggested `< cap` (strict); the fix kept `<= cap` (inclusive) on empirical grounds. Two engineers reached different conclusions. A developer must confirm the "cap means suppressed ticks" interpretation (not "cap means max age index") is intentional and will be communicated to Phase-5 callers who configure `action_hold_cap_ticks`.

#### 3. WR-05 feed_emergency Source Restriction

**Test:** Confirm that while the engine is in OVERRIDE mode, a dying forced camera's feed-death is handled exclusively by the in-override reconciliation branch in `tick()` (lines 559-571) — i.e. the `feed_emergency` transition is NEVER fired from OVERRIDE. The `feed_emergency` source list now declares only `["auto"]`.
**Expected:** In OVERRIDE, the forced-but-dead camera's fallback is the in-place reconciliation (target = best-alive-or-SAFE, stays in OVERRIDE). The `feed_emergency` state-machine transition is never needed from OVERRIDE because the reconciliation handles it. The fix also tightened the `tick()` call-site from `self.state in ("auto","override")` to `self.state == "auto"`.
**Why human:** This is a state-machine edge + call-site logic change. All tests pass including `test_force_death_recover_release_resume` and `test_live_feed_death_mid_hold_death_wins`. A developer should confirm that the "OVERRIDE handles its own feed-death in-place, feed_emergency is auto-only" architecture is the intended design before Phase-5 relies on it.

### Gaps Summary

No gaps. All 8 must-have truths are VERIFIED. All 8 requirements (DEC-01 through DEC-07, RBT-03) are satisfied. The critical blocker (CR-01 spurious SAFE cooldown) was fixed and has a regression test. The five warnings were fixed. The module reaches 100% test coverage (167 tests / 42 decision tests, all green).

The three human verification items are architectural/semantic questions about fix choices made during the review cycle. They do not block the phase goal — the stated goal is fully achieved — but they must be answered before Phase-5 integration.

---

_Verified: 2026-06-09T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
