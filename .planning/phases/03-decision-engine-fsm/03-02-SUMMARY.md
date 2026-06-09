---
phase: 03-decision-engine-fsm
plan: 02
subsystem: decision-fsm
tags: [transitions, fsm, feed-death, emergency-cut, holds, max-cap, tiebreaker, safety-guards]

# Dependency graph
requires:
  - phase: 03-decision-engine-fsm
    plan: 01
    provides: DecisionEngine (transitions.Machine wrapper), guarded-transition target mutation (DEC-01), hysteresis+dwell+debounce+cooldown (DEC-02), HoldInput/OverrideCmd frozen contracts, ticks_from_seconds, eligible-candidate filter + tick(scores, alive, holds, override) seam
  - phase: 02-framing-scorer
    provides: frozen CameraScore/ScorerStatus input contract
  - phase: 01-foundation
    provides: synth feed_death/score_stream, conftest fixtures (SEED, FPS, thresholds, _as_camera_scores), Config.field.framing_defaults.hold_length_s
provides:
  - Feed-death emergency cut (DEC-06) — two feed_emergency guarded transitions (best-alive dest=auto / no-alive dest=safe), fired ABOVE auto_switch; live_feed_dead/has_alive_candidate guards; _emergency_cut resets the new target's clocks (D-01 re-protection)
  - Action + occlusion holds (DEC-03/DEC-04) — holding() predicate wired as unless on auto_switch ONLY (never on feed_emergency); occlusion bound = ticks_from_seconds(hold_length_s, fps); EVERY hold has a mandatory tick max-cap (action_hold_cap_ticks/occlusion_hold_cap_ticks); effective occlusion bound = min(bound, cap)
  - Deterministic tiebreaker (DEC-05) — incumbent-wins inside the hysteresis dead-band; no-incumbent → first camera in config declaration order; no role-priority concept
  - DEC-03/04/05/06 test suites green (feeddeath/holds/tiebreak)
affects: [03-03-decision-override, 03-04-decision-determinism-suite, 05-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fixed-priority trigger order in tick(): feed-death emergency ABOVE normal auto_switch (one decision per tick; emergency_fired short-circuits auto_switch)"
    - "transitions guards read per-tick scratch on the model (_alive_eligible/_score_by_cam/_action_held_this_tick) — `transitions` callbacks take no args"
    - "Death wins over hold: the `holding` unless-guard is on auto_switch only, NEVER on the feed_emergency transitions"
    - "Every hold mandatorily tick-capped: action counts age UP (force-release at cap), occlusion counts DOWN from min(hold_length_s ticks, cap) armed on a rising edge"
    - "Emergency cut bypasses dwell/cooldown on the cut, then _on_target_change resets both for the new target (D-01 re-protection, Pitfall 4)"

key-files:
  created: []
  modified:
    - src/segugio/decision/engine.py
    - tests/test_decision_feeddeath.py
    - tests/test_decision_holds.py
    - tests/test_decision_tiebreak.py

key-decisions:
  - "feed_emergency fired in tick() only when self.state in (auto, override); emergency_fired short-circuits the normal auto_switch so a tick emits exactly one decision"
  - "Hold tick caps chosen as constructor args (defaults action=90, occlusion=90 @ ~3s/30fps): generous enough for a catch/jump or tunnel, but bound a stuck signal; tests inject short caps to exercise the force-release"
  - "hold_length_s injected as a constructor argument (mirrors fps; orchestrator/test supplies Config.field.framing_defaults.hold_length_s) — Phase-3 stays config-schema-change-free"
  - "Action `holding` predicate active while action_hold_age <= cap (force-release fires on the tick age would exceed the cap) so the suppressed window is exactly `cap` ticks"
  - "DEC-05 incumbent-wins falls out of the 03-01 hysteresis dead-band (strict > margin); made explicit in source comments + asserted, no behavior change"

requirements-completed: [DEC-03, DEC-04, DEC-05, DEC-06]

# Metrics
duration: 9min
completed: 2026-06-09
---

# Phase 3 Plan 02: Decision Guards — Feed-Death, Holds, Tiebreaker Summary

**The four broadcast-protecting guards on the core FSM: a dead live feed emergency-cuts to best-alive-or-SAFE bypassing dwell/cooldown then re-protects the new target (DEC-06), action/occlusion holds suppress switching while set — each bounded by a mandatory tick max-cap so a stuck signal can never freeze the show (DEC-03/04), and near-tied scores resolve deterministically to the incumbent or config-declaration order (DEC-05).**

## Performance

- **Duration:** ~9 min
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 4 (1 source, 3 test bodies filled)

## Accomplishments

- **DEC-06 (feed-death emergency cut):** Added two `feed_emergency` guarded transitions to the Machine — `source=["auto","override"] dest="auto"` (`conditions=[live_feed_dead, has_alive_candidate]`, `before=_emergency_cut`) and `dest="safe"` (`unless=[has_alive_candidate]`, `before=_set_target_safe`). Fired in the tick loop's fixed priority order ABOVE the normal `auto_switch`. The guard predicates read per-tick scratch (`_alive_eligible`/`_score_by_cam`) since `transitions` callbacks take no args. `_emergency_cut` cuts to the already-computed config-order best-alive candidate, then resets `dwell_elapsed=0` and `cooldown_remaining=cooldown_ticks` for the new target (D-01 / Pitfall 4 re-protection). Dead/poisoned cameras were already excluded from candidacy + challenger in 03-01. The hard invariant `alive[target] is True OR target == "SAFE"` holds on every tick of the ping_pong+feed-death scenario.
- **DEC-03/DEC-04 (holds with mandatory max-caps):** The constructor now takes `hold_length_s` + `action_hold_cap_ticks`/`occlusion_hold_cap_ticks`. The occlusion bound is `ticks_from_seconds(hold_length_s, fps)` (disc_dog 2.5s→75 ticks / agility 1.5s→45 ticks); the effective occlusion bound is `min(bound, cap)` — the cap bounds even a `hold_length_s` longer than the cap. Added the `holding()` predicate (action-active while `age <= cap` → force-release at the cap; occlusion-active while the rising-edge-armed countdown `> 0`), wired as `unless=["holding"]` on `auto_switch` ONLY — NEVER on the `feed_emergency` edges (death wins over hold, verified). Hold clocks advance at the top of `tick()`; a hold-suppressed otherwise-qualified cut reports `reason="hold"`.
- **DEC-05 (deterministic tiebreaker):** Made the two tiebreak rules explicit in source comments + assertions: (1) incumbent-wins — the strict `> incumbent_score + hysteresis_margin` dead-band test means a near-exact tie retains the incumbent (no cut); (2) no incumbent — the strict-max over `self.cam_ids` resolves an exact tie to the first config-declared camera, independent of the per-tick scores list order. No role-priority concept. The `tie` score stream replays with ≤1 transition after warm-up (no oscillation). These fell out of the 03-01 logic and passed RED without engine behavior change — only documentation + tests were added.

## Task Commits

Each task followed RED (failing test) → GREEN (implementation), committed atomically:

1. **Task 1: Feed-death emergency cut (DEC-06)** — RED `60fb277` (test) → GREEN `78b8f8a` (feat)
2. **Task 2: Action + occlusion holds with max-caps (DEC-03/04)** — RED `06adfa2` (test) → GREEN `8e51d91` (feat)
3. **Task 3: Deterministic tiebreaker (DEC-05)** — `2a6afea` (feat — tests + explicit source comments; passed RED without behavior change)

**Plan metadata:** final docs commit (this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md).

## Files Created/Modified

- `src/segugio/decision/engine.py` — two `feed_emergency` transitions + `live_feed_dead`/`has_alive_candidate`/`holding` guards + `_emergency_cut` callback; constructor `hold_length_s`/cap args; hold clocks (`action_hold_age`/`occlusion_hold_remaining`/`_prev_occlusion`) advanced at the top of `tick()`; fixed-priority emergency-above-auto_switch firing; `reason` derivation extended to `feed_emergency`/`hold`; explicit DEC-05 tiebreak comments.
- `tests/test_decision_feeddeath.py` — DEC-06: dead-never-live-nor-challenger (hard invariant over ping_pong+feed-death), immediate emergency cut (dwell/cooldown bypassed), emergency target normally protected (no instant steal), all-dead → SAFE.
- `tests/test_decision_holds.py` — DEC-03/04: action hold suppress+force-release-at-cap, occlusion hold bounded by hold_length_s then auto-expire, cap bounds a longer hold_length_s, agility (45) vs disc_dog (75) bound difference, feed-death wins over hold, hold reason reporting.
- `tests/test_decision_tiebreak.py` — DEC-05: incumbent-wins near-tie, no-incumbent → config order, config-order independent of scores-list order, tie stream ≤1 transition.

## Decisions Made

- **`feed_emergency` fired only from `auto`/`override` states; `emergency_fired` short-circuits `auto_switch`** so each tick emits exactly one decision (one target change). From `safe`/cold-start `live_feed_dead` is False anyway (SAFE is never a dead feed).
- **Hold tick caps are constructor args** (defaults action=90 / occlusion=90 @ ~3s, FPS=30): generous for a real catch/jump or tunnel, but bound a stuck signal. Tests inject short caps to deterministically exercise the force-release without 90-tick loops.
- **Action `holding` active while `action_hold_age <= cap`** (force-release on the tick age would exceed the cap) so the suppressed window is exactly `cap` ticks and the force-released cut fires immediately after.
- **`hold_length_s` injected as a constructor argument** (mirrors the 03-01 `fps` decision, RESEARCH A2) — keeps Phase-3 config-schema-change-free; the orchestrator/test passes `Config.field.framing_defaults.hold_length_s`.
- **DEC-05 incumbent-wins is the 03-01 hysteresis dead-band** (strict `> margin`); this plan made it explicit in source + asserted it rather than adding new logic.

## Deviations from Plan

None requiring deviation rules. The plan correctly anticipated that DEC-05 incumbent-wins "likely already falls out of the 03-01 hysteresis logic" — the tiebreak tests passed RED, so Task 3 added documentation + assertions only (no engine behavior change), exactly as the `<action>` directed ("make it explicit and assert it").

## Threat Surface

All three plan threat-register mitigations are implemented and tested:
- **T-3-01** (dead feed on air) — `feed_emergency` + the eligible-candidate filter; hard invariant `alive[target] is True OR target == "SAFE"` asserted every scenario.
- **T-3-02** (stuck-hold freeze) — mandatory per-hold tick max-caps + the occlusion `hold_length_s` bound; force-release/auto-expiry asserted.
- **T-3-04** (poisoned score) — carried from 03-01 (NaN/inf/out-of-range → ineligible); `tick()` never raises.

No new security surface introduced (pure local logic, no I/O, no network, no PII).

## Issues Encountered

- An off-by-one between "force-release AT the cap" and the action-hold test window: the cut fired one tick early relative to the test's `cut_while_held` window. Resolved by making the `holding` action predicate active while `action_hold_age <= cap` (rather than `<`), so the suppressed window is exactly `cap` ticks and the force-released cut fires on the tick the age would exceed the cap. No test was loosened — the semantics were tightened to match.

## Next Phase Readiness

- DEC-03/04/05/06 are green and locked. The engine now has the full guard set (DEC-01/02 from 03-01 + the four guards here).
- **Seams left for 03-03 (override):** the `override` state is declared; the `force`/`release` edges and the `OverrideCmd` input (accepted by `tick()` but still unused) are the hooks. The fixed-priority firing order in `tick()` has a clear insertion point for the override tier ABOVE feed-death emergency (RESEARCH §Pattern 3: override → emergency → hold → normal-switch).
- **For 03-04 (determinism suite):** the four new guards are deterministic (integer clocks, config-order tiebreak, no wall-clock/RNG) — ready for the byte-identical-replay DEC-07 assertions.
- Engine coverage 99% (the single uncovered line is the defensive `live_feed_dead` SAFE-state read, reachable only if `feed_emergency` were fired from `safe`, which the priority guard prevents). Full suite: 149 passed, 2 skipped (the remaining skips are 03-03 override + 03-04 determinism stubs).

## Self-Check: PASSED

All 4 modified files verified present. All 5 task commits (`60fb277`, `78b8f8a`, `06adfa2`, `8e51d91`, `2a6afea`) verified in git log. Full suite: 149 passed, 2 skipped; `segugio.decision` coverage 99%. must_haves markers present: `feed_emergency` (engine), `class HoldInput` (signals), `hold_length_s`/`alive` (engine key-links).

---
*Phase: 03-decision-engine-fsm*
*Completed: 2026-06-09*
