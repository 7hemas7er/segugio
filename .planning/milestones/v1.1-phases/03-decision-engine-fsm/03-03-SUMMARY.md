---
phase: 03-decision-engine-fsm
plan: 03
subsystem: decision-fsm
tags: [transitions, fsm, override, force-release, feed-death, auto-resume, operator-in-the-loop]

# Dependency graph
requires:
  - phase: 03-decision-engine-fsm
    plan: 01
    provides: DecisionEngine (transitions.Machine wrapper), guarded-target mutation (DEC-01), hysteresis+dwell+debounce+cooldown clocks (DEC-02), OverrideCmd frozen contract + tick(scores, alive, holds, override) seam, the `override` state declared
  - phase: 03-decision-engine-fsm
    plan: 02
    provides: feed-death emergency cut + best-alive/SAFE selection (DEC-06) reused by the forced-but-dead fallback, the fixed-priority tick() firing order with the documented OVERRIDE insertion point, action/occlusion holds, deterministic tiebreaker
  - phase: 01-foundation
    provides: synth feed_death(death_at, recover_after) liveness timeline, conftest fixtures (SEED, FPS, thresholds)
provides:
  - OVERRIDE operational mode (RBT-03) — `force`/`release` guarded transitions as the TOP-priority tier above feed-death emergency; sticky `override_cam` attribute distinct from the aired `target`
  - Immediate force (D-05) — `_apply_force` airs the forced camera at once, bypassing min_dwell/debounce_N/cooldown; forcing a DEAD camera enters OVERRIDE + sets override_cam but airs SAFE/best-live, never the dead feed
  - Forced-but-dead fallback + snap-back (D-03) — per-tick reconciliation airs override_cam while alive else best-alive-or-SAFE WITHOUT leaving OVERRIDE; snaps back the instant the forced feed recovers
  - Manual-release-only (D-04) + non-flickery auto-resume (D-06) — `_begin_resume_qualification` clears override_cam, zeroes the challenger streak, and re-enters AUTO without snapping to argmax; the next cut reuses the full auto_switch guard
  - RBT-03 combined-scenario + focused-unit override suite green, both hard safety invariants asserted every tick
affects: [03-04-decision-determinism-suite, 05-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OVERRIDE is the TOP-priority tier in tick(): a force/release command (or a held-override reconciliation) is evaluated ABOVE feed-death emergency and normal auto_switch (RESEARCH §Pattern 3)"
    - "Two-attribute override model (Pitfall 5): `override_cam` = the operator's sticky forced id (cleared only on release); `target` = what is actually aired (follows liveness). They are NEVER conflated"
    - "Forced-but-dead fallback REUSES the 03-02 DEC-06 best-alive/SAFE selection (_best_eligible) — a dead feed is never selected, so alive-or-SAFE holds by construction even under override"
    - "Auto-resume REUSES the normal auto_switch guard (no special-case resume): release zeroes the challenger streak so a candidate must win hysteresis + debounce_N + min_dwell fresh (Pitfall 6, no argmax snap)"
    - "force/release callbacks take the OverrideCmd via the arg-less-trigger exception: `self.force(cmd)` passes `cmd` to `_apply_force(cmd)` under send_event=False; the other callbacks stay arg-less"

key-files:
  created: []
  modified:
    - src/segugio/decision/engine.py
    - src/segugio/decision/signals.py
    - tests/test_decision_override.py

key-decisions:
  - "OVERRIDE evaluated ABOVE feed-death emergency in tick(): when a force/release fires OR a held override reconciles its target, the lower tiers are skipped (the override tier already enforces the alive-or-SAFE invariant) — one decision per tick"
  - "After `release` the FSM falls through to the auto tiers (release does NOT short-circuit them), but the resume cannot fire on the release tick because _begin_resume_qualification just zeroed the challenger streak — the qualification restarts fresh"
  - "reason strings under override: `override` for a force / snap-back / re-force, `override_dead_fallback` for a forced-but-dead SAFE/best-live tick, `auto_switch` once auto-resume finally qualifies — all `!= none` exactly on target-change ticks (DEC-01)"
  - "OverrideCmd shape from 03-01 confirmed sufficient (force_cam vs release cleanly discriminates) — NO extension needed; only a docstring note added"
  - "mode_is_override convenience property added (state == 'override') for readable tick-loop branching + tests"

patterns-established:
  - "Pattern: operator-intent tier sits at the top of the fixed-priority trigger order; the held-mode reconciliation is a separate per-tick branch that keeps the aired target consistent with liveness without a transition"
  - "Pattern: sticky-intent vs aired-state two-attribute split for any mode where the operator's choice must survive a transient liveness failure"

requirements-completed: [RBT-03]

# Metrics
duration: 7min
completed: 2026-06-09
---

# Phase 3 Plan 03: Manual Override + Auto-Resume Summary

**OVERRIDE is a guarded third operational mode: an operator force airs a camera immediately (bypassing dwell/debounce/cooldown), the override persists through that camera's feed-death (airing SAFE/best-live while dead, never the dead feed, snapping back on recovery), it ends only on explicit release, and auto-resume reuses the normal-switch guard so no flicker is re-introduced.**

## Performance

- **Duration:** ~7 min
- **Tasks:** 2 (Task 1 TDD: RED → GREEN; Task 2 test suite, delivered as the RED-gate artifact)
- **Files modified:** 3 (1 source engine, 1 source contracts-docstring, 1 test body filled)

## Accomplishments

- **RBT-03 (immediate force, D-05):** Added two guarded transitions — `force` (`source="*"`, `dest="override"`, `before="_apply_force"`) and `release` (`source="override"`, `dest="auto"`, `before="_begin_resume_qualification"`). `_apply_force` records the forced id in the sticky `self.override_cam`, airs it immediately if alive (resetting its clocks so it is then normally protected), and — crucially — airs best-alive-or-SAFE (never the dead feed) if the forced camera is dead while still entering OVERRIDE and keeping `override_cam`. A force bypasses min_dwell/debounce_N/cooldown by design (it is operator intent, not auto-switch noise).
- **Override-through-feed-death (D-03, the subtle one — Pitfall 5):** The OVERRIDE tier is the TOP priority in `tick()`, above feed-death emergency. With no new command while in OVERRIDE, a per-tick reconciliation airs `override_cam` while it is alive, else best-alive-or-SAFE — all WITHOUT leaving OVERRIDE. This is what produces the forced-but-dead SAFE/best-live fallback AND the snap-back to the forced camera the instant its feed recovers. The two-attribute split (`override_cam` sticky vs `target` aired) is the mechanism; the fallback reuses the 03-02 DEC-06 best-alive/SAFE selection so the dead-feed invariant holds by construction.
- **Manual-release-only (D-04) + non-flickery auto-resume (D-06 — Pitfall 6):** `release` is the only exit (no auto-expire); `_begin_resume_qualification` clears `override_cam`, zeroes the challenger streak, and re-enters AUTO without setting `target` from argmax. The last aired target (or SAFE) holds until a candidate wins the full `auto_switch` guard (hysteresis + debounce_N + min_dwell) fresh — literally reusing the normal-switch transition, no special-case resume logic.
- **RBT-03 proven end-to-end:** `test_force_death_recover_release_resume` drives the full force → die → recover → release → qualified-resume sequence on the synthetic `feed_death` substrate, asserting both hard safety invariants on EVERY tick. Focused units cover force-is-immediate, force-dead-shows-safe, no-auto-expire, and release-does-not-snap-to-argmax.

## Task Commits

1. **Task 1: OVERRIDE mode (force/release, forced-but-dead fallback, qualified auto-resume)** — RED `462b5af` (test) → GREEN `eb60eed` (feat). TDD cycle: the failing override suite, then the engine implementation that turns it green.
2. **Task 2: RBT-03 combined-scenario + focused-unit test suite** — delivered in `462b5af` (the same test file was the natural TDD RED-gate artifact for Task 1; it is complete and green against the Task-1 GREEN implementation — see Deviations).

**Plan metadata:** final docs commit (this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md).

## Files Created/Modified

- `src/segugio/decision/engine.py` — `force`/`release` transitions; sticky `self.override_cam` attribute; `mode_is_override` property; `_best_alive_or_safe` helper (reuses `_best_eligible`); `_apply_force` (immediate force / dead-cam fallback) + `_begin_resume_qualification` (clears override_cam, zeroes streak, no argmax snap) callbacks; the OVERRIDE tier wired as the top-priority block in `tick()` with the held-mode reconciliation branch; `reason` derivation extended to `override`/`override_dead_fallback`; RBT-03 traceability added to the module docstring.
- `src/segugio/decision/signals.py` — `OverrideCmd` docstring note: the 03-01 force-vs-release shape was confirmed sufficient for the 03-03 edges (no extension needed).
- `tests/test_decision_override.py` — RBT-03 suite (replaces the 03-01 skip stub): `test_force_death_recover_release_resume` (full combined scenario on `feed_death`), `test_force_is_immediate`, `test_force_dead_camera_shows_safe_not_dead`, `test_no_auto_expire`, `test_release_does_not_snap_to_argmax`; a `_assert_safety_invariants` helper enforcing BOTH hard invariants (DEC-01 target-changes-only-on-reason + DEC-06 alive-or-SAFE) on every tick.

## Decisions Made

- **OVERRIDE evaluated above feed-death emergency; lower tiers skipped when override owns the tick** (one decision per tick). After `release` the FSM falls through to the auto tiers (so an already-qualified candidate could in principle resume), but the resume cannot fire on the release tick itself because the challenger streak was just zeroed — the qualification restarts fresh (D-06).
- **`reason` strings under override:** `override` for a force / snap-back, `override_dead_fallback` for a forced-but-dead fallback tick, `auto_switch` once auto-resume qualifies. All are `!= "none"` exactly on the ticks the aired target changes — the DEC-01 invariant the safety helper asserts.
- **`OverrideCmd` shape confirmed, not extended** — `force_cam: str | None` vs `release: bool` already cleanly discriminates force-vs-release; the 03-01 stub was sufficient, so only a clarifying docstring line was added.
- **`mode_is_override` convenience property** (`state == "override"`) added for readable tick-loop branching and test assertions.

## Deviations from Plan

The plan split the work into Task 1 (the override implementation, `tdd="true"`) and Task 2 (the RBT-03 test suite). Because Task 1 is a TDD task and its `<verify>` runs `tests/test_decision_override.py`, the **natural RED-gate artifact for Task 1 was the full override test suite** — the same file Task 2 specifies as its sole deliverable. The complete suite (combined scenario + all focused units required by Task 2's acceptance criteria) was therefore authored and committed in the RED commit `462b5af`, then validated green against the GREEN implementation `eb60eed`.

- **No separate Task-2 source commit was made** because there was no remaining un-committed Task-2 work: the test file was already in its final, complete state. Manufacturing an empty/no-op commit to mirror the two-task split would have been dishonest. All of Task 2's acceptance criteria are met and verified:
  - `test_force_death_recover_release_resume` passes the full force→die→recover→release→resume sequence;
  - `test_force_is_immediate`, `test_force_dead_camera_shows_safe_not_dead`, `test_no_auto_expire` all pass;
  - both hard safety invariants are asserted on every tick (including the forced-but-dead window);
  - auto-resume is verified to fire only after the full hysteresis + min_dwell qualification (asserted both via the dedicated release-tick test and the combined scenario's resume-timing assertion).

No deviation rules (1–4) were triggered — no bugs, missing critical functionality, blockers, or architectural changes surfaced. The implementation extends the 03-01/03-02 foundation without rewriting it, exactly as the dependency context required.

**Total deviations:** 0 auto-fixed. 1 process note (TDD RED-gate naturally subsumed the Task-2 test deliverable into the Task-1 RED commit).
**Impact on plan:** None on scope or correctness — both tasks' acceptance criteria are fully satisfied; the only difference is commit topology (one test commit instead of two).

## Threat Surface

Both plan threat-register mitigations are implemented and tested:
- **T-3-03** (forced-but-dead availability) — D-03 design: a forced-but-dead camera airs SAFE/best-live (never the dead feed) while retaining OVERRIDE; snaps back on recovery; manual release is the only exit. Asserted by `test_force_dead_camera_shows_safe_not_dead` and the death/recovery window of the combined scenario.
- **T-3-01** (dead feed on air under override) — the forced-but-dead fallback reuses the DEC-06 best-alive/SAFE selection; `alive[target] is True OR target == "SAFE"` is asserted on EVERY tick across the whole override scenario by `_assert_safety_invariants`.

No new security surface: the override command is a typed, in-process, pure-local input (no I/O, no network, no PII). The orchestrator/UI gating is Phase 5.

## Issues Encountered

- **Skipping feed-emergency when the override tier owns the tick:** the initial firing block let `feed_emergency` re-fire from the `override` state during a held-override reconciliation, which would double-handle the dead-feed cut and confuse the `reason` derivation. Resolved by guarding the emergency tier with `not forced_this_tick and not in_override_no_command` — the override tier already enforces the alive-or-SAFE invariant for ticks it owns, so the emergency tier only runs in plain AUTO. Verified: `test_feed_death_wins_over_hold` and all 03-02 feed-death tests still green, and the combined override scenario holds the invariant through the death window.

## Next Phase Readiness

- RBT-03 is green and locked. The engine now has all three operational modes (SAFE/AUTO/OVERRIDE) and the full guard set (DEC-01/02 from 03-01, DEC-03/04/05/06 from 03-02, RBT-03 here).
- **For 03-04 (determinism suite):** the override path is deterministic (verified: two engines fed an identical force→die→recover→release timeline produce byte-identical `list[Decision]`) — ready for the DEC-07 byte-identical-replay assertions and the combined high-value cross-scenarios (force→release→resume is the RBT-03 row).
- Decision-module coverage 99% (the single uncovered line is the carried-over defensive `live_feed_dead` SAFE-state read from 03-02, unreachable because the priority guards never fire `feed_emergency` from `safe`). Full suite: 154 passed, 1 skipped (only the 03-04 determinism stub remains).

## Self-Check: PASSED

All 3 modified files verified present (`engine.py`, `signals.py`, `tests/test_decision_override.py`) plus this SUMMARY. Both task commits (`462b5af` test, `eb60eed` feat) verified in git log. must_haves markers present: `class OverrideCmd` (signals), `override_cam` + `force` transition (engine). Full suite: 154 passed, 1 skipped; `segugio.decision` coverage 99%. Override decision path verified byte-identical on replay (DEC-07-ready).

---
*Phase: 03-decision-engine-fsm*
*Completed: 2026-06-09*
