---
phase: 03-decision-engine-fsm
plan: 04
subsystem: testing
tags: [determinism, fsm, decision-engine, pytest, coverage, synthetic-substrate, dec-07]

# Dependency graph
requires:
  - phase: 03-decision-engine-fsm
    plan: 01
    provides: DecisionEngine (transitions.Machine wrapper), guarded-target mutation (DEC-01), hysteresis+dwell+debounce+cooldown clocks (DEC-02), the tick(scores, alive, holds, override) seam, frozen Decision/HoldInput/OverrideCmd contracts
  - phase: 03-decision-engine-fsm
    plan: 02
    provides: feed-death emergency cut (DEC-06), action/occlusion holds with mandatory tick max-caps (DEC-03/04), deterministic config-order tiebreaker (DEC-05)
  - phase: 03-decision-engine-fsm
    plan: 03
    provides: OVERRIDE mode (RBT-03) — immediate force, forced-but-dead SAFE/best-live fallback + snap-back, manual-release-only, qualified non-flickery auto-resume
  - phase: 01-foundation
    provides: synth score_stream (ping_pong/tie/dropout/recovery) + feed_death(death_at, recover_after) substrates; conftest SEED/FPS/_as_camera_scores/thresholds seams
provides:
  - DEC-07 determinism gate — same seed + scenario → byte-identical list[Decision], proven across all four SCENARIOS over the FULL tick(scores, alive, holds, override) input contract (not just bare scores)
  - The three combined high-value cross-scenarios no single earlier plan owns — force→release→resume (override × auto-resume), hold-through-occlusion→release (holds × auto-switch), live-feed-death-mid-hold (feed-death × holds, death wins)
  - Two reusable hard-safety-invariant assertions (assert_no_decision_outside_guard DEC-01, assert_never_airs_dead_feed DEC-06) applied across every combined scenario
  - segugio.decision pure-module coverage closed to 100% (the carried-over live_feed_dead SAFE-state guard regression-locked)
affects: [04-yolo-tracking, 05-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DEC-07 determinism is the FSM analogue of the FRM-07 scorer gate: a fresh-engine _run(scenario, seed) driver over the shipped synthetic substrate, asserting == over two frozen list[Decision] (mirrors test_framing_purity.py _run / assert ==)"
    - "Safety invariants assert over (decision, alive_map) PAIRS, never over a tick-keyed dict — the alive map checked is the EXACT liveness the engine saw on that tick, removing absolute/relative tick-index aliasing when a death timeline is driven on a relative clock"
    - "Determinism is asserted over the FULL typed input surface (scores + alive + holds + override), with an explicit assertion the override stream actually engaged (a Mode.override decision is present) so the contract is non-vacuously exercised"

key-files:
  created:
    - tests/test_decision_scenarios.py
  modified:
    - tests/test_decision_determinism.py

key-decisions:
  - "Determinism is proven over the FULL input contract: a feed-death liveness timeline + an occlusion-hold window + a force/release override pair are layered onto each score stream, and the run asserts a Mode.override decision is present so the override path is non-vacuously exercised"
  - "The two hard safety invariants are reusable helpers taking (decision, alive_map) PAIRS — not a tick-keyed dict — so the liveness checked is exactly what the engine saw on each tick; this avoids the absolute/relative tick-index aliasing that a death timeline on a relative clock would otherwise introduce"
  - "The coverage-closing test (test_live_feed_dead_is_false_at_safe) asserts the defensive SAFE-is-never-dead branch directly as a pure predicate read: it is unreachable via the feed_emergency transition (source auto/override only) but is real, regression-worthy behavior — closing engine.py to 100%"
  - "No engine logic was rewritten — this is a test/determinism plan; the FSM from 03-01/02/03 passed every determinism and combined-scenario assertion as-is"

patterns-established:
  - "Pattern: the determinism gate for a pure tick-driven module is a fresh-instance _run(seed) driver over the deterministic synth substrate + == over two frozen output lists — the exact contract that makes the module unit-testable in isolation"
  - "Pattern: encode cross-cutting safety invariants as reusable assert_* helpers over (decision, observed-input) pairs and apply them in EVERY scenario, so each new scenario inherits the invariants for free"

requirements-completed: [DEC-07]

# Metrics
duration: 5min
completed: 2026-06-09
---

# Phase 3 Plan 04: Decision Determinism + Combined Scenarios Summary

**DEC-07 is locked: the same seed + scenario drives a freshly-constructed DecisionEngine to a byte-identical `list[Decision]` across all four SCENARIOS over the full `tick(scores, alive, holds, override)` contract, and the three high-value cross-mode scenarios (force→release→resume, hold-through-occlusion→release, live-feed-death-mid-hold) pass with both hard safety invariants asserted as reusable helpers — `segugio.decision` at 100% coverage.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-09T20:26:42Z
- **Completed:** 2026-06-09
- **Tasks:** 2 (both test-authoring; no engine changes)
- **Files modified:** 2 (1 determinism stub filled, 1 combined-scenario suite created)

## Accomplishments

- **DEC-07 determinism gate (Task 1):** Replaced the 03-01 skip stub in `tests/test_decision_determinism.py` with the real suite. `test_purity_determinism` asserts, for each of the four `SCENARIOS`, that the synth input is itself deterministic (`score_stream(SEED) == score_stream(SEED)`) AND that two fresh engines driven over it produce byte-identical `list[Decision]`. `test_purity_determinism_full_input_contract` extends the proof to the WHOLE typed input surface — layering a feed-death liveness timeline, an occlusion-hold window, and a force/release override pair onto each score stream — and asserts a `Mode.override` decision is present so the contract is non-vacuously exercised. `test_all_scenarios_drive_without_error` (parametrized over `SCENARIOS`) confirms each scenario drives to a complete `list[Decision]` of the expected length, with every `Decision.mode` a valid `Mode`, no exception (fail-safe T-3-04).
- **Combined high-value cross-scenarios (Task 2):** Created `tests/test_decision_scenarios.py` with the two shared hard-safety-invariant helpers — `assert_no_decision_outside_guard` (DEC-01: target changes only on a tick whose `reason != "none"`) and `assert_never_airs_dead_feed` (DEC-06: `alive[target] is True OR target == "SAFE"` every tick) — and the three combined scenarios that no single earlier plan owns: `test_force_release_resume` (override × auto-resume), `test_hold_through_occlusion_then_release` (holds × auto-switch), `test_live_feed_death_mid_hold_death_wins` (feed-death × holds — death wins over an active hold, never airs the dead feed). Both invariants assert across every combined run.
- **Pure-module coverage closed to 100%:** `test_live_feed_dead_is_false_at_safe` directly asserts the defensive SAFE-is-never-dead branch in `engine.py` `live_feed_dead` (the single line the 03-03 SUMMARY flagged as the last uncovered defensive read), taking `segugio.decision` from 99% → 100%.
- **Full suite green:** 164 passed, 0 skipped (up from the 154-passed/1-skipped baseline — the skip stub is gone); `segugio.decision` coverage 100% (`__init__`/`clocks`/`engine`/`signals` all 100%). The phase is ready for `/gsd:verify-work`.

## Task Commits

Each task was committed atomically:

1. **Task 1: DEC-07 determinism gate over the synthetic score + feed-death streams** — `30a1cee` (test)
2. **Task 2: Combined high-value cross-scenario suite + shared hard-safety-invariant assertions** — `055b967` (test)

**Plan metadata:** final docs commit (this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md).

## Files Created/Modified

- `tests/test_decision_determinism.py` — the DEC-07 suite (replaces the 03-01 skip stub): `test_purity_determinism` (byte-identical replay across all four SCENARIOS on the bare-score path), `test_purity_determinism_full_input_contract` (determinism over the full scores+alive+holds+override surface, asserting the override path engages), `test_all_scenarios_drive_without_error` (parametrized; complete decision list + valid Mode + fail-safe). Fresh-engine `_run_*` drivers reuse the shipped `score_stream`/`feed_death` substrates and `SEED`/`FPS`/`_as_camera_scores` from conftest.
- `tests/test_decision_scenarios.py` (NEW) — the combined cross-scenario suite: the two reusable invariant helpers (`assert_no_decision_outside_guard`, `assert_never_airs_dead_feed`), the three high-value combined scenarios, and the coverage-closing `test_live_feed_dead_is_false_at_safe`. Drives the shipped substrates with `np.random.default_rng(SEED)` and reuses the `_two_cameras`/`_sc`/`_acquire` builder precedent from the 03-02/03-03 single-concern suites.

## Decisions Made

- **Determinism asserted over the full input contract, non-vacuously:** rather than proving only the bare score path, the full-contract test layers feed-death + occlusion-hold + force/release onto each scenario and asserts a `Mode.override` decision is present — so a passing run genuinely exercised every input channel, not just scores.
- **Safety invariants over `(decision, alive_map)` pairs, not a tick-keyed dict:** the combined scenarios drive a feed-death timeline on a *relative* clock while `Decision.tick` carries the *absolute* tick, so a tick-keyed lookup would alias the wrong liveness map (this surfaced as a real test bug during authoring). The helpers now take the exact alive map the engine saw on each tick, which is both correct and clearer.
- **Coverage-closing test asserts a real defensive branch:** `live_feed_dead()` returning `False` at SAFE is unreachable through the `feed_emergency` transition (its `source` is `auto`/`override` only), but it is genuine, regression-worthy behavior; asserting the pure predicate directly closes the module to 100% without contorting the FSM.
- **No engine logic rewritten** — per the plan's mandate this is a test/determinism plan; the 03-01/02/03 engine passed every assertion as-is.

## Deviations from Plan

None — plan executed exactly as written. No deviation rules (1–4) were triggered: no engine bugs, no missing critical functionality, no blockers, no architectural changes. The FSM was already deterministic and correct across the full input contract and all three combined scenarios.

A single TEST-internal bug surfaced during authoring (the `assert_never_airs_dead_feed` helper initially indexed an alive map by `Decision.tick`, the absolute clock, while the feed-death timeline was keyed by the relative tick — aliasing the wrong liveness map). It was fixed before any commit by switching the helpers to take `(decision, alive_map)` pairs. This is ordinary test development, not an engine deviation, and no engine code changed.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None — both tasks' acceptance criteria are fully satisfied; scope unchanged.

## Issues Encountered

- **Absolute-vs-relative tick aliasing in the dead-feed invariant helper:** the first cut of `assert_never_airs_dead_feed` looked up the per-tick alive map by `Decision.tick` (the absolute tick from `CameraScore.tick`), but the combined scenarios drive a `feed_death` timeline on a separate relative clock (rel = 0..N). At a later absolute tick the relative-keyed map reported cam_b as dead even though the decision came from a tick where it was alive, raising a false DEC-06 failure. Resolved by having both safety helpers consume `(decision, alive_map)` pairs — the alive map recorded is exactly the liveness the engine consumed on that tick — eliminating the aliasing entirely. All scenarios green afterward.

## User Setup Required

None — no external service configuration required (pure synthetic-substrate tests, CPU-only, no GPU/NDI/OBS).

## Next Phase Readiness

- **DEC-07 is green and locked** — the FSM is proven byte-reproducible over the full `tick(scores, alive, holds, override)` contract across all four named SCENARIOS, the property Phase-4 (YOLO wiring) and Phase-5 (orchestrator) depend on to reason about the decision stream deterministically.
- **Phase 3 is feature- and test-complete:** all three operational modes (SAFE/AUTO/OVERRIDE) and the full guard set (DEC-01/02 from 03-01, DEC-03/04/05/06 from 03-02, RBT-03 from 03-03, DEC-07 here) are implemented and regression-locked; `segugio.decision` at 100% coverage; full suite 164 passed, 0 skipped. Ready for `/gsd:verify-work`.
- No blockers or concerns introduced. The pre-existing Phase-4 watch item (native-ReID engagement on yolo26s; COCO dog recall on real footage) is unaffected.

## Self-Check: PASSED

Both modified files verified present (`tests/test_decision_determinism.py`, `tests/test_decision_scenarios.py`) plus this SUMMARY. Both task commits (`30a1cee` test, `055b967` test) verified in git log. must_haves markers present: `test_purity_determinism` (determinism) and `def test_` + `feed_death` (scenarios). Full suite: 164 passed, 0 skipped; `segugio.decision` coverage 100%.

---
*Phase: 03-decision-engine-fsm*
*Completed: 2026-06-09*
