---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
plan: 02
subsystem: tracking
tags: [trk-04, trk-05, competitor-lock, plausibility-gate, pure, tdd, deterministic, fail-safe]

# Dependency graph
requires:
  - phase: 04-yolo-per-camera-tracking-on-recorded-clips
    plan: 01
    provides: "TrackingParams seeds (motion_window/motion_deadzone/max_displacement_per_tick/max_size_ratio) + multi_track_stream synthetic substrate + linear_left crossing path + tracking_params fixture"
  - phase: 02-framing-scorer-pure-substrate
    provides: "frozen DetectionSignal input contract + terms.zone_of point-in-rect (reused) + terms.plausibility_ok intra-frame guard (the distinct-from analog) + scorer fail-safe convention + FRM-05 coast branch (None -> hold EMA)"
provides:
  - "CompetitorLock (TRK-04) — PURE stateful in-competition-dog selector: zone-gate AND motion-energy acquire (D-03), sticky continuity (D-04), per-camera independence (D-05), NaN fail-safe; one instance per cam_id"
  - "PlausibilityGate (TRK-05) — PURE stateful inter-frame teleport/size-jump gate: reject -> None (coast, D-06) without poisoning prev, reset() for re-acquire, distinct from Phase-2 intra-frame guard (D-07), non-finite fail-safe"
  - "Two green pure test suites (14 tests) covering the seven must-have truths each, on the synthetic multi-track substrate"
affects: [04-03-heavy-edge-percamera-tracker, 04-04-clip-eval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PURE stateful selector cloning CameraScorer shape: per-track bounded deque(maxlen=motion_window) history, _is_finite fail-safe guard, cumulative-displacement motion energy over the window with deadzone floor"
    - "sticky-lock continuity: keep locked_id while present in alive_ids (do NOT recompute best each tick) -> re-pick only on genuine loss; max(in_field, key=motion_energy) on acquire"
    - "INTER-frame plausibility gate distinct from INTRA-frame guard by module+signature+state: check(det)->DetectionSignal|None stateful on self.prev vs plausibility_ok(det,p)->bool stateless; reject does NOT update prev (no poisoning), prev_area>0 divisor guard"
    - "coast is free: returning None IS the entire uncertain->coast mechanism, flowing into the existing FRM-05 hold-EMA branch — no new TTL/coast machinery"

key-files:
  created:
    - src/segugio/tracking/competitor_lock.py
    - src/segugio/tracking/plausibility.py
    - tests/test_competitor_lock.py
    - tests/test_plausibility_gate.py
  modified: []

key-decisions:
  - "CompetitorLock excludes NaN/inf candidates from history AND alive_ids AND in_field (not just history) so a poisoned box can neither steal the sticky lock nor be acquired — strictly fail-safe to coast"
  - "_motion_energy floors below motion_deadzone to 0.0 so a stationary handler/bystander scores zero and a genuinely moving athlete dominates the max — the D-03 standing-dog exclusion"
  - "Tests use a custom centered-field Camera (single [0.3,0.3]-[0.7,0.7] zone) for the zone-gate behaviors so an out-of-field bystander is genuinely outside ALL zones (the happy-path cam_wide zones span full width); the determinism test uses the real cam_wide + multi_track_stream"
  - "PlausibilityGate adds a non-finite det -> coast guard (action-specified fail-safe) beyond the RESEARCH skeleton; reject path leaves prev untouched so a teleport never becomes the reference"

patterns-established:
  - "Pattern: a per-camera PURE stateful brain object (lock/gate) is unit-tested entirely on the synthetic multi_track_stream substrate — the same discipline as the Phase-2 scorer / Phase-3 FSM, isolating subject-selection risk from GPU/clip variance"
  - "Pattern: the existence-guarded purity source-grep (test_tracking_import_smoke._PURE_MODULE_NAMES) automatically covers new pure modules the moment they are created — competitor_lock.py + plausibility.py picked up with zero test edits"

requirements-completed: [TRK-04, TRK-05]

# Metrics
duration: 6min
completed: 2026-06-10
---

# Phase 4 Plan 02: Competitor-Lock + Plausibility Brain Summary

**The subject-selection brain made software-provable: two PURE, deterministic, CPU-only stateful classes — `CompetitorLock` (TRK-04: picks the in-zone moving athlete over a larger/central stationary bystander, sticky until genuine loss, per-camera independent) and `PlausibilityGate` (TRK-05: rejects inter-frame teleport/size-jump → coast without poisoning the reference, provably distinct from the Phase-2 intra-frame guard) — unit-tested on the synthetic multi-track substrate with zero heavy deps.**

## Performance

- **Duration:** ~6 min (task-execution span)
- **Tasks:** 2 (both TDD: RED → GREEN, no refactor needed)
- **Files modified:** 4 (4 created, 0 modified)
- **Tests:** +14 (7 TRK-04 + 7 TRK-05); full suite 178 → 192, zero regressions

## Accomplishments

- **`CompetitorLock` (TRK-04)** — the dominant project risk (PITFALLS Pitfall 1) made a tested, deterministic pure object. With a larger/more-central but out-of-zone **stationary** bystander and an in-zone **moving** athlete, `select(...)` returns the athlete's `track_id` — zone∧motion (D-03) beats size/centeredness. Once locked it stays sticky (D-04): a momentarily-higher-motion in-zone competitor does NOT steal the lock; re-acquisition fires only on genuine loss (the locked id absent from candidates). Two instances over two streams lock different ids and share no state (D-05). A NaN-cx candidate is excluded from history/alive-ids/in-field → coast, never raises (T-04-02-03).
- **`PlausibilityGate` (TRK-05)** — the silent BoT-SORT ID-swap defense (PITFALLS Pitfall 2). A teleport (Δcenter > `max_displacement_per_tick`) or size-jump (area ratio outside `[1/r, r]`) → `check` returns `None` (coast, D-06), and `self.prev` is NOT updated so the suspect box never becomes the new reference. A continuous fast-but-within-threshold run is accepted every tick (false-positive guard). It is provably distinct (D-07) from the Phase-2 intra-frame `terms.plausibility_ok`: a box that PASSES that appearance guard but teleports relative to `prev` is STILL rejected — proven by a test that asserts both at once. `reset()` clears `prev` for a fresh continuity chain on re-acquire.
- **Coast is free** — returning `None` IS the entire "uncertain → coast" mechanism; it flows straight into the existing `CameraScorer.update` FRM-05 branch (hold last EMA), exactly as `detection_stream` already emits `None` in a dropout window. No new TTL/coast machinery was built.
- **Purity holds** — both modules are pure stdlib (`collections`/`math`), clock-free, rng-free; the existence-guarded source-grep purity gate (`test_tracking_import_smoke.py`) now covers `competitor_lock.py` + `plausibility.py` with zero test edits, and the lazy-import boundary (heavy deps + cv2 absent) is intact.

## Task Commits

Each task was committed atomically (TDD: test RED → feat GREEN):

1. **Task 1 (RED): failing TRK-04 CompetitorLock suite** — `f2b9054` (test)
2. **Task 1 (GREEN): implement PURE CompetitorLock** — `12ad0e4` (feat)
3. **Task 2 (RED): failing TRK-05 PlausibilityGate suite** — `d1e53df` (test)
4. **Task 2 (GREEN): implement PURE PlausibilityGate** — `8c9e193` (feat)

_Both tasks are TDD: test (RED) → feat (GREEN). No refactor commit — each GREEN implementation was clean as written._

## Files Created/Modified

- `src/segugio/tracking/competitor_lock.py` — PURE stateful `CompetitorLock` (TRK-04). Per-track `deque(maxlen=motion_window)` history; `select()` = update history → sticky keep `locked_id` while in `alive_ids` → else re-acquire `max(in_field, key=_motion_energy)`; `_in_any_zone` reuses `terms.zone_of` point-in-rect; `_motion_energy` = cumulative window displacement floored below `motion_deadzone`; `_is_finite` fail-safe.
- `src/segugio/tracking/plausibility.py` — PURE stateful `PlausibilityGate` (TRK-05). `check(det)` rejects teleport (`disp > max_displacement_per_tick`) or size-jump (ratio outside `[1/r, r]`) → `None` without updating `prev`; `prev_area > 0` divisor guard; non-finite det → coast; `reset()` clears `prev`.
- `tests/test_competitor_lock.py` — 7 TRK-04 tests (athlete-over-bystander, sticky continuity, genuine-loss re-acquire, nothing-in-field coast, per-camera independence, determinism, NaN fail-safe) on `multi_track_stream` + hand-built candidates with a centered-field Camera.
- `tests/test_plausibility_gate.py` — 7 TRK-05 tests (teleport+prev-not-poisoned, size-jump, continuous-fast accept, genuine-miss coast, distinct-from-Phase-2, determinism, reset recovery).

## Decisions Made

- **NaN exclusion is total in CompetitorLock:** a non-finite candidate is dropped from history, `alive_ids`, AND `in_field` — so it can neither preserve a sticky lock (it is not "alive") nor be acquired. Strictly fail-safe to coast (T-04-02-03), stronger than only skipping history.
- **`_motion_energy` deadzone floor:** cumulative window displacement below `motion_deadzone` returns `0.0`, so a stationary handler/bystander has zero motion energy and a moving athlete wins the `max` — the D-03 standing-dog exclusion, not just a tiebreaker.
- **Test substrate split:** the zone-gate behaviors use a custom centered-field Camera (single `[0.3,0.3]-[0.7,0.7]` zone) because the happy-path `cam_wide` zones span the full width (a left/right bystander would still be in-zone). The determinism test uses the real `cam_wide` + `multi_track_stream` to prove byte-identical selection over the shipped substrate.
- **PlausibilityGate non-finite guard:** added the action-specified `_is_finite(det) → coast` fail-safe beyond the RESEARCH skeleton; combined with the `prev_area > 0` divisor guard, the gate never raises and never poisons `prev` on a rejection.

## Deviations from Plan

None - plan executed exactly as written. Both classes, all four files, and all seven-plus-seven must-have-truth tests were implemented per the `<action>` specs and RESEARCH/PATTERNS skeletons; no auto-fixes (Rules 1-3) and no architectural decisions (Rule 4) were needed.

## Issues Encountered

None. Baseline suite was green (178) before and is green (192) after — every new test is additive, no Phase 1-3 / 04-01 regression. Both RED phases failed genuinely (`ModuleNotFoundError` on the not-yet-created module), and both GREEN phases passed on first implementation.

## Authentication Gates

None — all work is CPU-only and heavy-deps-absent (no YOLO weights, no GPU, no NDI). No external service configuration required.

## Next Phase Readiness

- **04-03 (heavy edge)** is unblocked: the pure `CompetitorLock` + `PlausibilityGate` brain is ready to be driven by real YOLO+BoT-SORT `DetectionSignal` candidates per camera. The `select(...) → check(...)` pipeline (lock then gate) composes into the existing scorer→FSM→OBS path; `None` from either stage coasts via FRM-05.
- The open Phase-4 concern (verify native-ReID engagement on `yolo26s` at startup with `end2end=False`; measure COCO dog recall on real footage) is the 04-03 heavy-edge work — unaffected by this pure plan.
- No blockers.

## Self-Check: PASSED

All created files exist and all four task commits are present (verified in the self-check step).

---
*Phase: 04-yolo-per-camera-tracking-on-recorded-clips*
*Completed: 2026-06-10*
