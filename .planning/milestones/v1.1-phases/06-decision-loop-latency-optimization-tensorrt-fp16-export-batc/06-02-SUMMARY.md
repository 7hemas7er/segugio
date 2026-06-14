---
phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
plan: 02
subsystem: tracking
tags: [fp16, batched-inference, yolo, botsort, reid, latency, rbt-05]

# Dependency graph
requires:
  - phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
    plan: 01
    provides: ModelConfig.use_fp16/engine_path keys, batched_detect_dispatch adapter, engine-aware assert_native_reid_engaged, venv312 GPU env
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    provides: Orchestrator _fan_out per-camera dispatch + run_measured latency probe + gpu marker
provides:
  - batched FP16 _fan_out path — ONE detection forward per tick when trackers expose .model+.update (Track-B), serial fallback otherwise
  - batched_detect_dispatch(use_fp16) — half=use_fp16 + end2end=False threaded into the single forward (native ReID engageable under FP16)
  - PerCameraTracker.update(detections, frame) — drives its own persistent BoT-SORT tracker on pre-computed batched detections + native-ReID feats (#13107-safe)
  - PerCameraTracker.use_fp16 / is_engine attributes (FP16 toggle + engine-aware ReID gate seam)
  - MEASURED 4-cam p95 on the batched FP16 rung = ~210ms → 06-03 engine build AUTHORIZED
affects: [06-03-engine-build, decision-loop-latency]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Track-B batched _fan_out: ONE shared model.predict over all cams (half=use_fp16, end2end=False) then per-camera tracker.update() dispatch — never model.track([frames]) (#13107)"
    - "lazy warmup: PerCameraTracker.update() runs ONE model.track() warmup to register the native-ReID forward hook + build the persistent BoT-SORT tracker, then drives trackers[0].update() directly with the batched result's feats"
    - "capability gate (_supports_batched): batched path only when every tracker exposes .model+.update; .track-only trackers (mock-timed _FixedCostTracker) keep the serial path"

key-files:
  created:
    - tests/test_fan_out_batched.py
  modified:
    - src/segugio/tracking/batched.py
    - src/segugio/tracking/detector.py
    - src/segugio/orchestrator/loop.py
    - tests/test_batched_detect.py
    - tests/test_latency.py

key-decisions:
  - "FP16 is an eager predict kwarg (half=use_fp16) on the batched path — no engine, end2end=False preserved so the in-graph Detect head stays exposed and native-feature BoT-SORT ReID engages (verified on the rig: 'BoT-SORT native-feature ReID engaged')"
  - "PerCameraTracker.update() lazily warms ONE track() per camera to register the native-ReID hook + build the persistent BoT-SORT tracker, then drives it directly on the batched detection result.feats (the framework attaches per-camera feats when the hook is live)"
  - "_fan_out chooses batched vs serial via _supports_batched() so the mock-timed wiring/attribution latency tests (.track-only _FixedCostTracker) stay byte-for-byte green"

requirements-completed: []  # RBT-05 NOT met by the cheap rung — p95 ~210ms ≥ 150ms → 06-03 authorized

# Metrics
duration: 40min
completed: 2026-06-13
---

# Phase 6 Plan 2: Batched FP16 decision-loop (the cheap rung) Summary

**ONE batched FP16 detection forward per tick replacing the 4 serial `model.track()` calls — native-feature BoT-SORT ReID preserved (eager `half=True`, `end2end=False`) — measured on the RTX 4000 Ada at p95 ≈ 210ms, which does NOT clear the 150ms RBT-05 budget, so the engine build (06-03) is AUTHORIZED.**

## RBT-05 Latency Gate — MEASURED RESULT (the number that gates 06-03)

- **Measured 4-cam loop total p95 = ~210ms** (two consecutive runs: **211.4ms** then **209.5ms**) on the **batched FP16** `_fan_out` path.
- **Power state: AC (Win32_Battery BatteryStatus = 2)** — not battery-throttled (project memory `dev-box-perf-on-ac.md` honored).
- **Env:** `venv312` (Python 3.12.10, torch 2.12.0+cu126, ultralytics 8.4.62, tensorrt-cu12 10.16.1.11), RTX 4000 Ada Generation Laptop GPU, driver 596.36.
- **Harness:** `pytest tests/test_latency.py -m gpu -x -k test_loop_latency_p95_under_budget`, 20-tick warmup + 100-tick measurement window, `_p95` nearest-rank, real `yolo26s.pt` over synthetic 360×640 BGR frames.
- **Batched path verified ENGAGED, not a serial fallback:** `_supports_batched()` → True; instrumented predict-call count = ~1 batched forward per tick (11 predicts over 10 ticks incl. the per-camera warmups); `reid_checked` → True; the rig logged **"BoT-SORT native-feature ReID engaged (zero extra weights, end2end=False)"** — so FP16 preserved native ReID exactly as designed.

### VERDICT: **FAIL (p95 ≈ 210ms ≥ 150ms) → 06-03 (TensorRT engine build) is AUTHORIZED.**

The cheap rung improved the loop from the Phase-05 UAT baseline (**231–247ms** eager FP32 serial) to **~210ms** (eager FP16 + ONE batched forward per tick) — a real but insufficient gain. The RTX 4000 Ada Laptop GPU does not parallelize the 4-frame batch enough to cross the budget. This is the explicit, non-fabricated gate the plan requires: **the cheap rung did NOT meet RBT-05, so the engine build (06-03) is needed.**

**FP16 recall note (RESEARCH A5):** not separately spot-checked on a curated hard slice this run — the GPU gate uses synthetic random frames (the budget is about loop latency, not detection accuracy). 06-03 should weigh keeping FP32 detection if FP16 visibly regresses recall on real distant/dusk footage; the native-ReID-engaged log indicates the FP16 detect head is structurally intact.

## Performance

- **Duration:** ~40 min
- **Started:** 2026-06-13
- **Completed:** 2026-06-13
- **Tasks:** 3 of 3 (Tasks 1-2 TDD test→feat pairs; Task 3 measurement RUN on the rig — NOT a human checkpoint, the orchestrator authorized running it on the live GPU env)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `batched_detect_dispatch` gained a `use_fp16` flag → `half=use_fp16` on the single forward, with `end2end=False` now explicit on the batched path (native ReID engageable under FP16). `PerCameraTracker` gained a `use_fp16` ctor kwarg (`half` on the serial fallback `track()`).
- `Orchestrator._fan_out` reworked: `_supports_batched()` selects the Track-B batched path (ONE shared `model.predict` over all camera frames → per-camera `tracker.update()` dispatch) when trackers expose `.model`+`.update`, falling back to the serial `tracker.track()` path otherwise (keeps the mock-timed `_FixedCostTracker` wiring/attribution tests green). Every Phase-5 invariant preserved: dog-index-by-name (CR-02), once-before-loop HARD ReID gate now threading `is_engine`, CR-01 gate-reset-only-on-genuine-reacquire, locked-energy max, per-camera degrade-to-None coast (RBT-04).
- `PerCameraTracker.update(detections, frame)`: drives THIS camera's persistent BoT-SORT tracker on the pre-computed batched detection slice + the native-ReID `feats` carried on the result, folding track ids back onto the `Results`. A lazy warmup (`_ensure_persistent_tracker`) runs ONE `track()` per camera to register the native-ReID forward hook (so the subsequent batched `predict()` populates `result.feats`) and build the persistent tracker.
- The gpu latency gate (`test_loop_latency_p95_under_budget`) armed with `use_fp16=True` and RUN on the rig — recorded p95 ≈ 210ms, FAIL verdict gating 06-03.

## Task Commits

Each task committed atomically (TDD tasks have test → feat pairs):

1. **Task 1 (RED): failing FP16 half-thread + end2end-preserved tests** — `4672def` (test)
2. **Task 1 (GREEN): thread FP16 half + end2end=False through batched dispatch + PerCameraTracker** — `1589fb7` (feat)
3. **Task 2 (RED): failing loop-level batched _fan_out tests** — `6c48384` (test)
4. **Task 2 (GREEN): batched FP16 _fan_out path + PerCameraTracker.update()** — `bf01204` (feat)
5. **Task 3 (setup): arm use_fp16=True on the gpu latency gate** — `ccfd365` (test)

**Plan metadata:** (this commit — docs: complete plan)

## Files Created/Modified
- `src/segugio/tracking/batched.py` — `batched_detect_dispatch` gains `use_fp16` → `half=use_fp16`; `end2end=False` now explicit on the single forward
- `src/segugio/tracking/detector.py` — `PerCameraTracker` gains `use_fp16`/`is_engine`/`_bot`; `track()` threads `half=self.use_fp16`; NEW `update()` + `_ensure_persistent_tracker()` for the Track-B batched association
- `src/segugio/orchestrator/loop.py` — `_fan_out` split into `_batched_inference` (Track-B) / `_serial_inference` (legacy) via `_supports_batched()`; `_resolve_dog_idx_once` + `_maybe_reid_gate` (threads `is_engine`) extracted
- `tests/test_batched_detect.py` — +4 FP16 tests (half threaded, default FP32, end2end preserved, isolation+coast under FP16)
- `tests/test_fan_out_batched.py` (NEW) — loop-level batched dispatch: one forward / N updates / #13107 isolation / FP16 half / once-only is_engine ReID gate / None-frame coast / dog-index-by-name
- `tests/test_latency.py` — gpu gate armed with `use_fp16=True` + `PerCameraTracker(use_fp16=...)`

## Decisions Made
- **FP16 preserves native ReID (no engine, no conflict):** `half=True` is an eager predict kwarg; keeping `end2end=False` leaves the in-graph Detect head exposed so the native-feature BoT-SORT ReID lambda engages — confirmed live on the rig (`assert_native_reid_engaged` passed, hook registered). This sidesteps the engine↔ReID conflict (RESEARCH Pitfall 1) entirely — the whole point of the cheap rung.
- **Lazy warmup to bridge predict↔track:** the batched path runs `model.predict()` (detection only), which does NOT build the per-camera tracker nor register the ReID hook. `PerCameraTracker.update()` lazily runs ONE `model.track()` warmup per camera to register the hook (so the shared model's subsequent batched `predict()` attaches per-camera `result.feats`) and to construct the persistent `BOTSORT` it then drives directly. Verified on the rig: feats populate with batch dim = N when the hook is live.
- **Capability-gated path selection:** `_supports_batched()` keeps the legacy serial path for `.track`-only trackers so the mock-timed wiring/attribution latency tests stay byte-for-byte green (no GPU needed for the headless regression).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `PerCameraTracker` needed a real `.update()` for the batched loop path**
- **Found during:** Task 2
- **Issue:** The plan's Task 2 action calls `batched_detect_dispatch(model, frames_by_cam, self.trackers, ...)`, but the adapter dispatches via `tracker.update(detections, frame)` — which `PerCameraTracker` did NOT expose (it only had `.track()`). Without it the real GPU gate could not run the batched path.
- **Fix:** Added `PerCameraTracker.update()` + `_ensure_persistent_tracker()` (lazy `track()` warmup to register the native-ReID hook + build the persistent BoT-SORT tracker, then `trackers[0].update(det, frame, result.feats)` and fold ids back onto the `Results`). Mirrors Ultralytics' own `on_predict_postprocess_end` dispatch pattern.
- **Files modified:** `src/segugio/tracking/detector.py`
- **Commit:** `bf01204`

**2. [Rule 3 - Blocking] `is_engine` threaded into the loop's ReID gate**
- **Found during:** Task 2
- **Issue:** Plan Test 3 requires the HARD ReID gate to thread `is_engine` (`getattr(tracker, "is_engine", False)`); `PerCameraTracker` had no such attribute.
- **Fix:** Added `is_engine = False` to `PerCameraTracker.__init__` (eager `.pt` keeps the HARD raise; 06-03's engine-backed tracker sets it True). `_maybe_reid_gate` reads it.
- **Files modified:** `src/segugio/tracking/detector.py`, `src/segugio/orchestrator/loop.py`
- **Commit:** `bf01204`

### Plan note (not a deviation)
- The plan's Task 2 `verify` references `tests/test_orchestrator_tick.py`, which does not exist in the repo; the closest runtime regression is `tests/test_orchestrator_runtime.py` (run and GREEN). No behavior change.

### Task 3 executed (not paused)
- Task 3 is authored as `checkpoint:human-verify`, but the orchestrator explicitly authorized running it on the now-live GPU env (`venv312`, AC power). It was RUN, not paused — the measured p95 (~210ms, FAIL) is recorded above and gates 06-03.

## Issues Encountered
- Two NDI-marked tests (`test_ndi_mock_sender.py`, `test_ndi_source.py`) fail when the full suite runs without marker filtering — they require a LIVE NDI sender on the network (hardware-gated, out of scope for this plan). The headless suite (`-m "not ndi and not gpu and not obs"`) is fully GREEN. Logged, not fixed (SCOPE BOUNDARY).

## Next Phase Readiness
- **06-03 (TensorRT engine build) is AUTHORIZED:** the cheap rung's measured p95 (~210ms) exceeds the 150ms budget, satisfying the plan's explicit gate. The engine-aware `assert_native_reid_engaged` (`is_engine` already threaded through `_maybe_reid_gate`) and the `engine_path` config key (06-01) are the seams 06-03 builds on; `PerCameraTracker.is_engine` flips to True on the engine-backed tracker.
- The batched FP16 `_fan_out` stays as the eager fallback if the engine is missing/incompatible (live-robustness): `_supports_batched()` + the serial fallback already coast a `.track`-only tracker.

## Self-Check: PASSED

All created/modified files exist on disk and all 5 task commits are present in git history:
- Files: `test_fan_out_batched.py`, `batched.py`, `detector.py`, `loop.py`, `test_batched_detect.py`, `test_latency.py` — all FOUND.
- Commits: `4672def`, `1589fb7`, `6c48384`, `bf01204`, `ccfd365` — all FOUND.

---
*Phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc*
*Completed: 2026-06-13 (Tasks 1-2 TDD; Task 3 GPU gate RUN on the rig — p95 ~210ms, FAIL → 06-03 authorized)*
