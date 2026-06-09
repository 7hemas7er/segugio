---
phase: 02-framing-scorer-pure-logic
plan: 02
subsystem: scoring
tags: [framing-scorer, ema, lead-room, zone-gating, conf-norm, stateful, numpy, fail-safe]

# Dependency graph
requires:
  - phase: 02-framing-scorer-pure-logic
    provides: "02-01: frozen DetectionSignal/CameraScore/ScorerStatus, 8 pure terms (gaussian_centeredness/gaussian_size_band/base_score/lead_room_target/zone_of/gate/conf_norm_step/plausibility_ok), ScorerParams (incl. eps/vel_window/beta/z_clip/warmup), detection_stream generator, scorer_params fixture"
provides:
  - "CameraScorer stateful per-camera object (present-detection path) — composes the 8 pure terms into a fixed-alpha EMA-smoothed CameraScore (segugio.framing.scorer)"
  - "CameraScorer re-exported from segugio.framing"
  - "Green FRM-02/03/04/06 behavior tests (test_framing_{ema,zone,leadroom,confnorm}.py) driving the real CameraScorer"
affects: [02-03-coast-ttl, 02-04-purity-gate, 03-fsm-switching, 04-yolo-tracker-wiring]

# Tech tracking
tech-stack:
  added: []   # no new packages — numpy + stdlib (collections/math) only
  patterns:
    - "Stateful per-camera scorer object composing pure free functions; deterministic given the input stream (no rng, no clock — FRM-07)"
    - "Cold-start EMA seed s_0=raw_0 (D-05); fixed-alpha read once at construction as the D-07 motion-adaptive-alpha hook"
    - "Finite-difference velocity over a bounded deque(maxlen=vel_window+1); track-id swap clears history → speed 0 (D-06)"
    - "Fail-safe scorer: NaN/inf detection (math.isfinite guard) treated as no-detection → coast; np.clip on exit; never raises on validated data"
    - "Behavior tests compose the same pure terms independently to verify the gated/EMA output exactly (==/approx), not just shape"

key-files:
  created:
    - src/segugio/framing/scorer.py
  modified:
    - src/segugio/framing/__init__.py
    - tests/test_framing_ema.py
    - tests/test_framing_zone.py
    - tests/test_framing_leadroom.py
    - tests/test_framing_confnorm.py

key-decisions:
  - "D-05 fixed-alpha EMA read once at construction; cold start seeds s_0=raw_0 (not 0) — proven by test_ema (first score == hand-composed raw_0; smaller alpha lags more on a step input)"
  - "D-06 lead-room ideal shifts TOWARD motion via finite-difference velocity over vel_window history; track-id swap clears history (speed 0); proven by test_target_shifts_toward_motion + the end-to-end positive-velocity test"
  - "D-07 motion-adaptive alpha deferred — only the single fixed-alpha path shipped; the construction seam is the clean hook. Phase-3 cross-dependency (alpha tuned jointly with debounce_N/min_dwell/hysteresis_margin) flagged for the Phase-3 planner"
  - "Coast/TTL else-branch is a minimal hold-last placeholder marked '# 02-03: coast/TTL' — the full TTL countdown is 02-03's scope (D-04 boundary; never feed raw=0 into the EMA)"
  - "zone_of called WITH framing_weights so overlap resolves highest-weight (coincides with first-match on the non-overlapping example configs)"

patterns-established:
  - "Stateful CameraScorer.update() present-detection composition: conf_norm → finite-diff velocity → lead-shifted ideal → centeredness/size base → zone gate → fixed-alpha EMA → clipped CameraScore"
  - "_is_finite_detection() NaN/inf guard delegating to the coast branch (threat T-2-01 mitigation)"
  - "FRM behavior test: drive the real CameraScorer + independently re-compose the expected value from the pure terms → assert exact equality (not approximate shape)"

requirements-completed: [FRM-02, FRM-03, FRM-04, FRM-06]

# Metrics
duration: 9min
completed: 2026-06-09
---

# Phase 2 Plan 02: CameraScorer present-detection path Summary

**Stateful per-camera `CameraScorer` composing the eight pure 02-01 terms into a fixed-alpha EMA-smoothed `CameraScore` — cold-start `s_0=raw_0`, lead-room ideal shifting toward motion via finite-difference velocity, zone-gating × `framing_weights[role][zone]`, and per-camera confidence z-score — fail-safe (NaN/inf → coast), clock-free, RNG-free; with the four FRM-02/03/04/06 behavior tests turned green.**

## Performance

- **Duration:** ~9 min
- **Completed:** 2026-06-09
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments
- `CameraScorer` (segugio.framing.scorer, 190 lines) implements the **present-detection branch** of `update(det, tick)`: on a plausible, finite detection it composes conf-norm → finite-difference velocity → lead-shifted ideal → centeredness/size base → zone gate → fixed-alpha EMA, seeds the TTL, and marks `tracking`. A missing / implausible / NaN-inf detection falls through to a minimal coast placeholder (hold last EMA; the full TTL countdown is 02-03).
- Cold start seeds `s_0 = raw_0` (D-05); the fixed `alpha` is read once at construction (the D-07 hook — no velocity-coupled alpha computed here).
- Lead-room (D-06): `_velocity()` is a finite difference over `deque(maxlen=vel_window+1)` of the LOCKED track, guarded for `< 2` samples and a non-positive tick span; a `track_id` change clears history (speed 0 until rebuilt).
- Fail-safe (threat T-2-01): `_is_finite_detection()` treats a NaN/inf detection as no-detection → coast; the emitted EMA is `np.clip`-ed to `[0,1]`; never raises on data the validated `Config` already passed.
- `CameraScorer` re-exported from `segugio.framing`.
- Four behavior tests turned green driving the real `CameraScorer`: `test_ema` (cold start + lag), `test_zone_multiplier` (in/out-of-zone gate), `test_target_shifts_toward_motion` (lead-room sign + clamp + zero-speed + end-to-end velocity), `test_brightness_anti_bias` (conf-norm washes out a +0.2 bias; intra-camera spike still registers).
- Full suite: **110 passed, 2 skipped** (up from the 105/6 baseline; the 2 remaining skips are 02-03 coast and 02-04 purity). No regression.

## Task Commits

Each task was committed atomically:

1. **Task 1: CameraScorer present-detection path composing pure terms** — `d4a5c6c` (feat)
2. **Task 2: Green FRM-02/03/04/06 behavior tests against CameraScorer** — `d6003ff` (test)

_TDD note: Task 1's `CameraScorer` was written to satisfy the four behavior tests authored in Task 2 (the RED→GREEN pair for this plan). Task 1 verified GREEN at its own commit via the 02-01 base/shadow tests staying green + the importability/negative-grep acceptance gates; Task 2 then drove the new behaviors GREEN. The plan's `tdd="true"` tasks are a tightly-coupled implementation+test pair rather than two separate RED/GREEN commits, because the behavior tests target the class created in Task 1._

## Files Created/Modified
- `src/segugio/framing/scorer.py` — **created.** `CameraScorer` present-detection path + `_velocity()` finite-difference + `_is_finite_detection()` NaN/inf guard; coast else-branch is a 02-03 seam.
- `src/segugio/framing/__init__.py` — re-export `CameraScorer` (added to imports + `__all__`).
- `tests/test_framing_ema.py` — FRM-02: cold-start `s_0=raw_0` (vs hand-composed raw_0) + smaller-alpha-lags-more on a step input.
- `tests/test_framing_zone.py` — FRM-03: in-zone `raw == base × weight`, out-of-zone `base × out_of_bounds_factor` (not 0), higher-weight-zone-wins via the `gate` term on a fixed base.
- `tests/test_framing_leadroom.py` — FRM-04: lead-room sign + clamp + zero/deadzone-speed + end-to-end positive velocity through the scorer.
- `tests/test_framing_confnorm.py` — FRM-06: +0.2 conf bias washes out after warmup (within 1e-6) + intra-camera spike registers + flat baseline normalizes to ~0.5.

## Decisions Made
- **`zone_of` is called WITH `framing_weights`** so an overlapping-rect config resolves to the highest-weight match (CONTEXT Claude's-Discretion); on the non-overlapping example configs this coincides with first-match. The 02-01 `zone_of` already supports the optional `framing_weights` arg.
- **`ttl_ticks` accepted directly at construction** (Open Q2 RESOLVED) — keeps the scorer clock-free; this plan only seeds `self.ttl = self.ttl_ticks` on a present detection, the countdown is 02-03.
- **The coast else-branch is a deliberate minimal placeholder** (`self.status = self.status`, hold last EMA) marked `# 02-03: coast/TTL`. It never feeds `raw=0` into the EMA. This honors the D-04 scope line: 02-02 ships only the tracking path; 02-03 replaces the whole else-branch with the coast/TTL logic. See Known Stubs.
- **`math.isfinite` (stdlib) used for the NaN/inf guard** rather than `np.isfinite` — avoids constructing a numpy array per tick in the hot path; still clock-free and rng-free.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `raw_far > raw_mid` assertion failed under [0,1] saturation in the zone test**
- **Found during:** Task 2 (test_framing_zone authoring)
- **Issue:** The plan's intent ("a high-weight zone outscores an identical detection in a low-weight zone") was first written as `raw_far > raw_mid` on two well-centered detections. Both `base × weight` products (`~1.0 × 1.6` and `~1.0 × 1.1`) clip to exactly `1.0` (the `gate` clips to `[0,1]`), so the comparison was `1.0 > 1.0` → False. The two centers also have different `cy` (different framing quality), confounding a pure weight comparison.
- **Fix:** Kept the exact multiplier-equality assertions on the real scorer (`raw == base × framing_weights[role][zone]`, the core FRM-03 behavior), and added a separate, unconfounded assertion on the pure `gate` term with one fixed modest base (`0.5`) and the two weights (`0.5×1.6=0.8 > 0.5×1.1=0.55`), so "higher-weight zone wins for identical framing" is proven without saturation or framing-quality confound.
- **Files modified:** tests/test_framing_zone.py
- **Verification:** `test_zone_multiplier` green; full suite green.
- **Committed in:** `d6003ff` (Task 2 commit)

**2. [Rule 1 - Bug] Lead-room behavioral-consequence assertion used a geometrically inconsistent dog position**
- **Found during:** Task 2 (test_framing_leadroom authoring)
- **Issue:** The plan/RESEARCH prose's example (`centeredness(cx=0.42, ideal_x=0.5+lead) > centeredness(cx=0.42, ideal=0.5)`) is mathematically false: a dog at `cx=0.42` is FURTHER from the right-shifted ideal `0.5+lead` than from center `0.5`, so it scores LOWER with lead, not higher. The RESEARCH prose conflates "dog behind center" with "dog scored higher against the lead-shifted ideal."
- **Fix:** Asserted the physically-consistent consequence instead: the dog positioned where it is heading (at `cx = 0.5 + lead`, the lead-shifted ideal) scores higher against the lead-shifted ideal than against the (wrong) centered ideal — i.e. lead-room rewards the dog that has empty lead room ahead in its direction of travel. The proven SIGN (`ideal_x > 0.5` for rightward motion) is asserted directly and unchanged; the clamp and zero/deadzone-speed cases are also asserted.
- **Files modified:** tests/test_framing_leadroom.py
- **Verification:** `test_target_shifts_toward_motion` green; the lead-room sign, clamp, and zero-speed behaviors all asserted.
- **Committed in:** `d6003ff` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs, both in test assertions). No scope change, no source-logic change. The FRM-03 multiplier behavior and the FRM-04 proven sign are asserted exactly as the plan intended; the two corrections fix internally-inconsistent assertion arithmetic in the plan/RESEARCH prose, not the scorer.

## Issues Encountered
None beyond the two auto-fixed test-assertion bugs above. The `CameraScorer` composed the 02-01 substrate cleanly; the 105-test baseline stayed green throughout.

## User Setup Required
None — no external service configuration. Phase 2 installs no new packages (all deps vetted in Phase 1).

## Threat Flags
None — no new network endpoints, auth paths, file access, or trust-boundary schema beyond the plan's `<threat_model>`. T-2-01 (NaN/inf poisoning) is mitigated by `_is_finite_detection()` + the velocity divisor guards + `np.clip` on exit; T-2-03 (bad params) is mitigated by reading only the Phase-1-validated `Config`/`ScorerParams`.

## Known Stubs
- **The coast/TTL else-branch in `CameraScorer.update()` is an intentional minimal placeholder** (holds the last EMA + status, no TTL countdown), marked `# 02-03: coast/TTL`. This is the plan's explicit scope: 02-02 ships only the present-detection (tracking) path; **02-03 owns FRM-05** and replaces the whole else-branch with the coast→lost TTL countdown. This is not a data-flow stub that blocks the plan's goal (the four present-path behaviors are fully wired and green); it is the documented wave boundary (`test_framing_coast.py` remains skip-scaffolded for 02-03). The scorer never feeds `raw=0` into the EMA, so the placeholder is safe to compose against.

## Next Phase Readiness
- 02-03 can implement FRM-05: it has the `CameraScorer` with `self.ttl`/`self.ttl_ticks`/`self.ema`/`self.status` state already seeded on the tracking path; it replaces the `# 02-03: coast/TTL` else-branch with the countdown (hold → `coasting` for `ttl_ticks`, then `ema=0.0` → `lost`; recovery before TTL resumes `tracking` without cold-start) and fills `test_framing_coast.py`.
- 02-04 fills `test_framing_purity.py` (determinism + no `time`/`np.random`/I-O in `framing/`) and adds `segugio.framing` (now incl. `CameraScorer`) to the import-smoke `PHASE1_SURFACE`. The lazy-import boundary already holds (scorer.py imports only numpy + stdlib + the framing records/terms).
- **Phase-3 cross-dependency flagged (D-07):** the fixed EMA `alpha` must be tuned jointly with the Phase-3 FSM `debounce_N` / `min_dwell` / `hysteresis_margin` (a smoother alpha permits a shorter debounce; a snappier alpha needs a longer one). The motion-adaptive-alpha hook is the `CameraScorer` construction seam.
- No blockers.

## Self-Check: PASSED

`src/segugio/framing/scorer.py` exists on disk (190 lines, `class CameraScorer`); both task commits (`d4a5c6c`, `d6003ff`) are in the git log. Full suite: 110 passed, 2 skipped (no regression of the 105-test baseline; the four 02-02 behavior tests green, 02-03/02-04 scaffolds still skip).

---
*Phase: 02-framing-scorer-pure-logic*
*Completed: 2026-06-09*
