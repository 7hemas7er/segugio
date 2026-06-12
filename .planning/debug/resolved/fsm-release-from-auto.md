---
status: resolved
slug: fsm-release-from-auto
trigger: "FSM throws transitions.core.MachineError 'Can't trigger event release from state auto!' every tick after an operator override release, wedging the director in SAFE (Phase 05 UAT Test 4 blocker)."
created: 2026-06-13
updated: 2026-06-13
severity: blocker
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
related: [watchdog-hx-feed-death]
---

## Diagnosis is COMPLETE — go straight to fix + regression test + verify + commit

This bug is **fully headless** (pure FSM + the loop's level-triggered command read). No GPU/NDI/OBS/rig
needed to reproduce or verify. Do NOT spend cycles re-deriving — confirm the root cause below with a
quick read, apply the fix, add the regression test, run the headless suite, commit, archive.

## Symptoms

1. **Expected:** An operator override RELEASE (`Rilascia`) returns the FSM to `auto` and the director
   resumes automatic selection — and KEEPS ticking without faulting on subsequent ticks (D-06
   auto-resume + the "nessun crash ammesso" / no-stuck-SAFE robustness constraint).
2. **Actual:** After `Avvia` (start) + `Rilascia` (release), the orchestrator throws EVERY tick:
   `transitions.core.MachineError: "Can't trigger event release from state auto!"`
   (segugio.orchestrator.loop:_tick_once:437 → SAFE coast), wedging the director permanently in SAFE
   so detection→cut is unreachable.
3. **Error:** `transitions.core.MachineError: "Can't trigger event release from state auto!"`
4. **Timeline:** Surfaced at the rig 2026-06-13 during Phase 05 UAT Test 4 (the first time the override
   release was exercised live against the running orchestrator).
5. **Reproduction (headless):** drive `DecisionEngine.tick(scores, alive, override=OverrideCmd(release=True))`
   for ≥2 consecutive ticks once the FSM is in `auto`. First tick: override→auto (or, if already auto,
   the bug fires immediately). The release trigger from `auto` raises MachineError. In the live loop the
   opcomm `command.json` PERSISTS `release=True` and `_read_run_and_override` re-reads it every tick
   (level-triggered), so the fault recurs forever.

## Current Focus

hypothesis: |
  In src/segugio/decision/engine.py tick() (~L553-557) the override tier fires
  `self.release(override)` whenever `override.release` is True, WITHOUT gating on FSM state. The
  `release` transition is defined with source='override' ONLY (engine.py ~L140-145). command.json
  persists release=True and the loop re-reads it each tick → after the first (valid) override→auto
  release, every subsequent tick fires `release` from `auto` → no matching transition → MachineError
  (the Machine is NOT constructed with ignore_invalid_triggers) → tick fault → permanent SAFE coast.
  The loop already guards `feed_emergency` on `self.state == "auto"` (~L588) for exactly this reason.
test: |
  Reproduce headlessly: build a DecisionEngine, drive it to `auto`, then call
  tick(..., override=OverrideCmd(release=True)) TWICE — assert the second call raises MachineError
  on the CURRENT code (red), and does NOT raise after the fix (green).
expecting: |
  Current code: second consecutive release-from-auto raises transitions.core.MachineError.
  After fix: no raise; FSM stays in `auto` (resume qualification), tick returns a Decision.
next_action: |
  Apply the fix (gate the release fire on self.mode_is_override), add the regression test, run the
  full headless suite (must stay green — was 323 passed), commit, archive the session.
reasoning_checkpoint:
  hypothesis: |
    tick() L556-558 fires self.release(override) on override.release==True WITHOUT a state
    guard. The `release` transition (L141-145) has source="override" ONLY, and the Machine is
    built without ignore_invalid_triggers (engine.py L256-263). command.json persists
    release=True and the loop re-reads it every tick (level-triggered), so after the first valid
    override→auto release, every subsequent tick fires `release` from `auto` → no matching
    transition → transitions.core.MachineError → tick fault → permanent SAFE coast.
  confirming_evidence:
    - "engine.py L141-145: release transition source='override' only — no auto/safe source edge."
    - "engine.py L256-263: Machine() has no ignore_invalid_triggers, so an invalid trigger RAISES."
    - "engine.py L556-558: release fire is ungated on state (unlike feed_emergency at L588, which is guarded on self.state == 'auto')."
    - "Live UAT Test 4: MachineError 'Can't trigger event release from state auto!' thrown every tick after Avvia+Rilascia."
  falsification_test: |
    Drive DecisionEngine to `auto`, then call tick(..., override=OverrideCmd(release=True)) for
    >=2 consecutive ticks. On CURRENT code the 2nd call (release-from-auto) must raise
    MachineError. If it does NOT raise, the hypothesis is wrong.
  fix_rationale: |
    Gate the release fire on self.mode_is_override (== state=="override"). A release while
    already in `auto` is a semantic no-op (override has already ended). This mirrors the existing
    feed_emergency state-guard and addresses the ROOT CAUSE (firing an invalid trigger), not a
    symptom. _begin_resume_qualification only matters when actually leaving override, so D-06 is
    unchanged. override_fired stays False on the no-op so the auto tiers run normally.
  blind_spots: |
    Must confirm override_fired stays False when release is requested-but-already-auto, so the
    feed_emergency/auto_switch tiers still run (a release tick from auto must not silently swallow
    auto-resume). The new regression test asserts each tick returns a Decision and the FSM stays
    in `auto` across the persistent-release run.

## RED/GREEN log

- before-fix (RED): `test_persistent_release_from_auto_never_faults` FAILED with
  `transitions.core.MachineError: "Can't trigger event release from state auto!"` at engine.py:557
  (1 failed, 1 passed — the force→release cycle test passed, proving the working path was intact).
- after-fix (GREEN): both new tests pass (2 passed). Full headless suite: 325 passed (was 323; +2
  new tests), 3 skipped, 6 deselected via `-m "not ndi and not obs and not gpu"`. The only failures
  in the unfiltered run are the two `@pytest.mark.ndi` live-NDI E2E tests (no live NDI sender on this
  box) — unrelated to the FSM fix, which touches only the pure decision engine.

## Fix (recommended — minimal, edge-correct)

Gate the release fire on being in OVERRIDE — a release when already in `auto` is a semantic no-op:

```python
elif override is not None and override.release and self.mode_is_override:
    self.release(override)  # manual release (D-06); begins resume qualification
```

`self.mode_is_override` == `self.state == "override"` (engine.py ~L380). This mirrors the existing
`feed_emergency` state-guard (~L588) and does NOT change D-06 semantics (`_begin_resume_qualification`
only matters when actually leaving override). Confirm the resume-tick path still works (a real
force→release cycle must still transition override→auto on the release tick).

Alternatives considered (prefer the guard above):
- (b) construct the Machine / `release` transition with `ignore_invalid_triggers=True` — broader,
  silently swallows OTHER invalid triggers too (less precise; could mask future bugs).
- (c) add a no-op `release` self-loop from `auto`/`safe` — works but adds graph edges for a no-op.

## Constraints

- FSM is PURE (engine.py imports only `transitions` + stdlib `math` + the pure `framing` surface) →
  fix + regression test are fully headless. No GPU/NDI/OBS/rig.
- MUST keep the existing headless suite green (was 323 passed). Run with the py3.14 venv:
  `venv\Scripts\python.exe -m pytest` (or `-m "not ndi and not obs and not gpu"`).
- MUST add a regression test: a persistent OverrideCmd(release=True) over MULTIPLE consecutive ticks
  from `auto` does NOT raise (and the FSM stays in auto / resuming). Also assert a normal force→release
  cycle still transitions override→auto on the release tick.
- Existing decision-engine / 03-03 override tests in tests/ must stay green (don't rewrite them).
- The fix is in src/segugio/decision/engine.py (tick override tier). FeedWatchdog / loop.py need NOT
  change — but a 1-line clarifying comment is fine.

## Evidence

- timestamp: 2026-06-13
  observation: "Live at rig (UAT Test 4): after Avvia + Rilascia, orchestrator threw every tick — transitions.core.MachineError 'Can't trigger event release from state auto!' (loop _tick_once:437 → SAFE coast). Director wedged in SAFE."
- timestamp: 2026-06-13
  observation: "Code read: engine.py tick() L553-557 fires self.release(override) on override.release ungated on state; the 'release' transition (L140-145) has source='override' only. command.json persists release=True; loop re-reads each tick (level-triggered) → release from 'auto' every tick after the first → MachineError. feed_emergency is already state-guarded at L588 for the same reason."

## Eliminated

(none yet)

## Resolution

root_cause: |
  In src/segugio/decision/engine.py tick() the override tier fired self.release(override) whenever
  override.release was True, WITHOUT gating on FSM state. The `release` transition is defined with
  source="override" ONLY and the Machine is built without ignore_invalid_triggers, so the trigger
  RAISES from any non-override source. The opcomm command.json PERSISTS release=True and the loop's
  _read_run_and_override re-reads it every tick (level-triggered), so after the first valid
  override→auto release, every subsequent tick fired `release` from `auto` → no matching transition
  → transitions.core.MachineError "Can't trigger event release from state auto!" → tick fault →
  permanent SAFE coast (Phase 05 UAT Test 4 blocker).
fix: |
  Gated the release fire on self.mode_is_override — `elif override is not None and override.release
  and self.mode_is_override:` — mirroring the existing feed_emergency state-guard. A release while
  already in `auto` is a semantic no-op (override has already ended); override_fired stays False on
  the no-op so the feed_emergency/auto_switch tiers still run normally. D-06 semantics unchanged
  (_begin_resume_qualification only matters when actually leaving override). Added a clarifying
  comment explaining the level-triggered command.json re-read and why the guard prevents the
  recurring MachineError. 1-line guard + comment; FeedWatchdog / loop.py untouched.
verification: |
  Test-first: added two regression tests to tests/test_decision_override.py.
  (1) test_persistent_release_from_auto_never_faults — drives the FSM to `auto`, then holds
  OverrideCmd(release=True) over 10 consecutive ticks; asserts no raise, FSM stays in `auto`, each
  tick returns a Decision (+ the two hard safety invariants). FAILED before the fix with the exact
  MachineError (RED), PASSES after (GREEN).
  (2) test_force_then_release_cycle_still_transitions — force cam_b → release transitions
  override→auto on the release tick, clears override_cam, no snap to argmax (D-06 unchanged).
  Full headless suite: 325 passed (was 323; +2 new), 3 skipped, 6 deselected via
  `-m "not ndi and not obs and not gpu"`. The only unfiltered failures are the two @pytest.mark.ndi
  live-NDI E2E tests (no live NDI sender on this box) — unrelated to this pure-FSM fix.
files_changed:
  - src/segugio/decision/engine.py (tick override tier: state-gated the release fire + comment)
  - tests/test_decision_override.py (two regression tests)
