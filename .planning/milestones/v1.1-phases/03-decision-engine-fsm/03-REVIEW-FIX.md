---
phase: 03-decision-engine-fsm
fixed_at: 2026-06-09T00:00:00Z
review_path: .planning/phases/03-decision-engine-fsm/03-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-06-09
**Source review:** .planning/phases/03-decision-engine-fsm/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01 blocker + WR-01..WR-05)
- Fixed: 6
- Skipped: 0

Scope was `critical_warning`: the CR-01 blocker plus the five warnings. The four Info findings
(IN-01..IN-04) were intentionally NOT addressed this pass.

Verification: every fix passed Tier-1 (re-read) and Tier-2 (`ast.parse` syntax check), and the
FULL suite was run green after every commit. Baseline was 164 passed / 0 skipped; the final
suite is **167 passed / 0 skipped** (three new regression tests were added — CR-01, WR-01,
WR-04). DEC-07 byte-reproducible determinism and the two hard safety invariants (never air a
dead feed; no unguarded switch) still hold.

## Fixed Issues

### CR-01: SAFE fallback sets a spurious cooldown that blocks re-acquisition for ~1s after a blackout

**Files modified:** `src/segugio/decision/engine.py`, `tests/test_decision_feeddeath.py`
**Commit:** 520849c
**Status:** fixed
**Applied fix:** Exempted SAFE from the cooldown gate in `cooldown_clear()` — `if self.target
== SAFE_TARGET: return True` — mirroring the existing SAFE exemption in `dwell_elapsed_ok()`.
SAFE is a fallback with no incumbent to protect, so it must carry no cooldown just as it carries
no dwell. This lets a recovered camera re-acquire the instant it qualifies, instead of lingering
on SAFE for ~cooldown_ticks-1 ticks.

Added a regression test `test_recovery_out_of_safe_reacquires_promptly` reproducing
"total blackout → SAFE → single camera recovers → re-acquisition fires promptly". I verified the
ordering empirically: against the buggy code the test FAILED with re-acquisition delayed to i=29
(`cooldown_ticks-1`); after the fix it PASSES with re-acquisition at i=2 (`debounce_N-1`), inside
the asserted `< debounce_N+1` prompt window.

### WR-01: An alive camera with no score row this tick is mistaken for a dead feed and emergency-cut

**Files modified:** `src/segugio/decision/engine.py`, `tests/test_decision_feeddeath.py`
**Commit:** 4f3d085
**Status:** fixed: requires human verification
**Applied fix:** Decoupled liveness from score-row presence. Added a separate `self._alive` set
computed directly from the alive map (or all `cam_ids` when no map is supplied), independent of
`_score_by_cam`, and re-keyed `live_feed_dead()` off `self._alive` instead of `_alive_eligible`.
A camera the map reports alive but that lacks a finite `CameraScore` row this tick is now treated
as live-but-not-an-eligible-challenger, not as a dead feed. `has_alive_candidate()` and the
emergency/argmax selection still use the score-bearing `_alive_eligible`.

Added `test_live_incumbent_with_no_score_row_is_not_emergency_cut`. I confirmed via a
monkeypatched reproduction that the OLD logic emergency-cut the live-but-unscored incumbent
(`target=cam_b, reason=feed_emergency`) while the fixed logic keeps `cam_a` on air.

**Human-verification note:** this changes the engine's liveness model (the semantic source of
truth for feed-death). All 167 tests pass, but a developer should confirm the new
liveness-vs-eligibility split matches the intended Phase-2 → Phase-3 contract.

### WR-02: Engine emits `reason="override_dead_fallback"` but the Decision contract never declares it

**Files modified:** `src/segugio/decision/signals.py`
**Commit:** 387e27e
**Status:** fixed
**Applied fix:** Added `"override_dead_fallback"` to the documented `Decision.reason` legal set
in the dataclass field comment, with a short note that it is the forced-but-dead / snap-back
reconciliation reason (distinct from a plain `"override"`) so a Phase-5 orchestrator that maps
reasons → OBS actions can handle it explicitly. Documentation-only; the engine already emits it
and `test_decision_scenarios.py` already allows it.

### WR-03: Action-hold cap uses `<=`, so the force-release fires one tick LATER than the cap

**Files modified:** `src/segugio/decision/engine.py`, `tests/test_decision_holds.py`
**Commit:** 5ae9dd4
**Status:** fixed: requires human verification
**Applied fix:** I deliberately did NOT apply the review's suggested `<=` → `<` change. Measuring
both paths empirically, the CURRENT inclusive `<=` already yields EXACTLY `cap` suppressed ticks
and cuts at `i == cap`, which is symmetric with the occlusion path (armed to `bound`, suppresses
for exactly `bound` ticks, cuts at `i == bound`). The review's premise — that `<=` fires "one
tick later" — does not hold given that `action_hold_age` is incremented to 1 on the first held
tick; switching to strict `<` would make the action hold cap at `cap-1` suppressed ticks,
INTRODUCING a one-tick asymmetry with occlusion rather than removing it (verified: with cap=5,
`<` gives 4 suppressed ticks / cut at i=4 vs occlusion's 5 / i=5).

So the fix keeps `<=`, documents the boundary semantics in `holding()` (explaining why the
inclusive comparator is required for symmetry), and TIGHTENS
`test_action_hold_suppresses_and_caps` from the loose `cut_after_cap >= cap-1` to the exact
`suppressed_ticks == cap` and `cut_after_cap == cap` — locking the "exactly cap suppressed ticks"
contract the review asked for.

**Human-verification note:** this fix resolves WR-03 by rejecting the literal patch on empirical
grounds. A developer should confirm they agree the inclusive `<=` (exactly `cap` suppressed
ticks, symmetric with occlusion) is the intended cap semantics.

### WR-04: Ambiguous OverrideCmd (force_cam AND release both set) is resolved silently

**Files modified:** `src/segugio/decision/signals.py`, `tests/test_decision_override.py`
**Commit:** 1a3cd33
**Status:** fixed
**Applied fix:** Added `__post_init__` to the frozen `OverrideCmd` dataclass raising
`ValueError` when both `force_cam` is set and `release` is True. Validation is at the input
BOUNDARY (construction), so `tick()` remains exception-free (T-3-04: a malformed operator command
never reaches the FSM). Audited all existing `OverrideCmd(...)` constructions first — none set
both fields, so no existing test or determinism timeline is broken. Added
`test_ambiguous_override_cmd_rejected_at_construction` asserting the raise and that the two valid
shapes (and the no-op) still construct.

### WR-05: `feed_emergency` declares `source=["auto","override"]` but the `override` source is unreachable

**Files modified:** `src/segugio/decision/engine.py`
**Commit:** 02fc796
**Status:** fixed: requires human verification
**Applied fix:** Dropped `"override"` from the `source` list of BOTH `feed_emergency` transition
edges (now `["auto"]`), matching actual reachability — `tick()` only ever fires `feed_emergency`
from the `auto` state (while in OVERRIDE, the in-override reconciliation branch owns the
forced-but-dead → SAFE/best-live fallback). For defense-in-depth against a `transitions`
MachineError (which would violate T-3-04), also tightened the call-site condition from
`self.state in ("auto", "override")` to `self.state == "auto"`, making a non-source invocation
structurally impossible. The full suite — including the feed-death-during-override scenarios
(`test_live_feed_death_mid_hold_death_wins`, `test_force_death_recover_release_resume`) — stays
green, empirically confirming the `override` source was vestigial.

**Human-verification note:** this is a state-machine edge + call-site logic change. A developer
should confirm the intended reachability matches (feed-death is handled by the in-override
reconciliation, never by a `feed_emergency` trigger fired from OVERRIDE).

## Skipped Issues

None — all 6 in-scope findings were fixed.

---

_Fixed: 2026-06-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
