---
phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
plan: 03
subsystem: tracking
tags: [tensorrt, engine, fp16, yolo, botsort, reid, latency, rbt-05, rbt-04]

# Dependency graph
requires:
  - phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
    plan: 01
    provides: engine-aware assert_native_reid_engaged (is_engine kwarg), ModelConfig.engine_path/use_fp16 keys, .gitignore *.engine, venv312 GPU env
  - phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
    plan: 02
    provides: batched FP16 _fan_out path, PerCameraTracker.update()/is_engine, measured ~210ms FP16+batch p95 (the gate that AUTHORIZED this plan)
provides:
  - tools/build_engine.py — one-time cached TensorRT FP16 engine build CLI (lazy ultralytics, on the deploy GPU)
  - engine-aware PerCameraTracker loader — loads .engine when configured+on-disk (is_engine True), graceful eager .pt fallback on ANY failure/missing file (RBT-04, never crash)
  - direct-build BOTSORT for the engine path (a static batch=N engine rejects the single-frame track() warmup)
  - is_engine threaded from tracker → loop → reid gate; engine path WARNS-not-raises (Q1 Option (a)), eager path keeps the HARD raise
  - MEASURED engine-path 4-cam p95 ≈ 193–195ms → STILL ≥ 150ms (RBT-05 NOT met on this RTX 4000 Ada Laptop GPU)
affects: [decision-loop-latency, rbt-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "engine build is a one-time GPU-specific cached artifact (tools/build_engine.py): YOLO(.pt).export(format=engine, half=True, batch=4, imgsz=640, end2end=False, device=0); .engine gitignored, rebuilt per rig"
    - "engine-aware load with graceful eager fallback: engine_path set+on-disk → YOLO(engine), is_engine True; ANY load failure or missing file → warning + eager .pt, is_engine False (RBT-04)"
    - "engine Track-B warmup: a static batch=N engine REJECTS the single-frame track() warmup, so the per-camera BOTSORT is built DIRECTLY (mirrors on_predict_start, cls-ReID fallback) — batched predict([N]) drives detection, the directly-built BOTSORT drives association"
    - "engine-aware reid gate: is_engine downgrades the predictor-None AND empty-predictor.trackers raises to warnings (the engine's detection-only predict sets predictor but no predictor.trackers)"

key-files:
  created:
    - tools/build_engine.py
    - tests/test_engine_loader_fallback.py
  modified:
    - src/segugio/tracking/detector.py
    - src/segugio/tracking/reid_check.py
    - src/segugio/orchestrator/runtime.py
    - tests/test_fan_out_batched.py
    - tests/test_latency.py
    - tests/test_orchestrator_runtime.py
    - docs/run.md

key-decisions:
  - "Q1 Open Question RESOLVED → Option (a): accept the cls-ReID fallback on the engine path; the engine loads the FULL .track()/predict; assert_native_reid_engaged WARNS-not-raises when is_engine=True. Rationale: Segugio tracks a SINGLE dog (RESEARCH A2 → cheap cls-ReID sufficient); Option (a) is simplest and stays within this plan's file set. Authorizing 06-02 p95 ≈ 213ms (FAIL) gated this plan. Option (b) (eager-tracking, engine-detection-only) remains the documented fallback if competitor-lock continuity regresses on curated multi-dog footage."
  - "tools/build_engine.py exports a STATIC batch=4 engine (matches the 4-cam fan-out; the loop pads dead slots with a blank frame); --dynamic is the escape hatch for reduced-camera operation"
  - "RBT-04 graceful fallback: a missing/incompatible engine is the staleness signal (no metadata schema) — the loader degrades to eager .pt rather than crashing the live director"

requirements-completed: []  # RBT-05 NOT met — engine-path p95 ≈ 194ms ≥ 150ms (see verdict below)

# Metrics
duration: 55min
completed: 2026-06-13
---

# Phase 6 Plan 3: TensorRT FP16 engine build (the engine track) Summary

**The one-time cached TensorRT FP16 engine build CLI + an engine-aware `PerCameraTracker` (graceful eager fallback, RBT-04) + the `is_engine` reid-gate thread-through — the engine was BUILT on the RTX 4000 Ada and the 4-cam loop MEASURED p95 ≈ 193–195ms, which STILL does NOT clear the 150ms RBT-05 budget. The engine genuinely engaged (cls-ReID fallback WARNS, no crash — Q1 Option (a)), but the static-batch engine on this Laptop GPU only shaved ~210ms → ~194ms. RBT-05 stays OPEN; the next lever is surfaced (not silently applied).**

## Q1 Decision (Open Question — RESOLVED → Option (a))

**Selected: Option (a) — accept the cls-ReID fallback on the engine path; the engine loads the FULL track; the reid gate WARNS-not-raises when `is_engine=True`.**

- **Rationale:** Segugio tracks a SINGLE dog (RESEARCH assumption A2), so the cheap `yolo26n-cls.pt` cls-ReID encoder is sufficient — native-feature ReID's competitor-disambiguation value is marginal for one subject. Option (a) is the simplest plumbing (one model object, the engine accelerates the full detection→association path) and stays within this plan's file set. Option (b) (keep tracking on an eager `.pt`, engine-accelerate only detection) would have required splitting detect/track across the batched adapter and two model objects — out of this plan's scope — and is kept as the **documented fallback** if competitor-lock continuity regresses on curated multi-dog footage.
- **Authorizing gate:** 06-02's measured FP16+batch rung p95 ≈ **213ms** (recorded as 211.4ms then 209.5ms; the SUMMARY's "≈210ms", FAIL ≥ 150ms) — that over-budget result is what authorized building the engine.

## RBT-05 Latency Gate — MEASURED RESULT (the engine path)

- **Measured 4-cam loop total p95 ≈ 193–195ms** (two consecutive runs: **194.5ms** then **193.3ms**) on the **TensorRT FP16 engine** path.
- **VERDICT: FAIL (engine p95 ≈ 194ms ≥ 150ms) — RBT-05 NOT met.** The engine shaved the loop only marginally from the 06-02 eager FP16+batch rung (~210ms → ~194ms). The static batch=4 engine on the RTX 4000 Ada **Laptop** GPU does not cross the budget.
- **Engine genuinely engaged (NOT a fabricated pass):**
  - Startup log: `loaded TensorRT engine yolo26s.engine (is_engine=True)` on all 4 trackers.
  - Q1 Option-(a) behavior confirmed: `engine-backed model has empty predictor.trackers (detection-only batched predict; association on per-camera BOTSORTs) — accepting cls-ReID fallback.` — a **WARNING, not a crash**; the loop ticked through all warmup + measurement ticks.
  - The engine ran real batched `predict([4 frames])` (matching the static batch=4 input shape `(4,3,640,640)`) and the directly-built per-camera BOTSORTs drove association — no batch-mismatch coast.
- **Env:** `venv312` (Python 3.12.10, torch 2.12.0+cu126, ultralytics 8.4.62, tensorrt-cu12 10.16.1.11), RTX 4000 Ada Generation **Laptop** GPU, driver 596.36. **AC power confirmed (Win32_Battery BatteryStatus = 2)** — not throttled (project memory `dev-box-perf-on-ac.md`).
- **Harness:** `pytest tests/test_latency.py -m gpu -x -k test_loop_latency_p95_under_budget`, 20-tick warmup (engine spin-up — Pitfall 5) + 100-tick window, `_p95` nearest-rank, synthetic 360×640 BGR frames.
- **Engine artifact:** `C:\Users\mirko\Documents\GitHub\segugio\yolo26s.engine` (22.3 MB, FP16, static input `(4,3,640,640)`), built via `tools/build_engine.py` in ~340s; gitignored (verified `git check-ignore`), never committed.

## Next lever (surfaced, NOT silently applied)

RBT-05 is still open after the engine. The documented levers, in order:
1. **Option (b)** — keep tracking on an eager `.pt`, engine-accelerate ONLY the detection forward, fed into a separate eager tracker's `update()`. Preserves native-feature ReID; engine speeds the dominant detection cost. **Requires a re-plan/split of 06-03** (two model objects, the batched adapter splits detect/track) — flagged to the orchestrator, NOT done in-place.
2. **`yolo26n` engine** — swap the source weights to the nano detector (config `model.path`) and rebuild the engine; trades recall for latency.
3. **Camera-reduction degradation ladder** (`run_measured` logs it) — reduce active cameras / lower AI-path imgsz/fps. This **defeats the multi-cam product value** (CLAUDE.md core value: "the camera giusta al momento giusto") — **flagged, NOT applied** without an explicit product decision.

The Phase-6 RBT-05 budget remains the open phase risk; this plan delivered the prod TensorRT path honestly and measured it does not yet meet budget on this Laptop-GPU rig (a desktop RTX would likely differ — re-measure on the actual deploy GPU before choosing a lever).

## Performance

- **Duration:** ~55 min
- **Started:** 2026-06-13
- **Completed:** 2026-06-13
- **Tasks:** 5 of 5 (Task 1 decision recorded; Tasks 2-4 shipped + TDD; Task 5 engine BUILT + gate RUN honestly on the rig — NOT a human pause, the orchestrator authorized running it on the live GPU env)
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments
- **`tools/build_engine.py`** — the one-time cached TensorRT FP16 engine build CLI. Lazy `from ultralytics import YOLO` inside `build_engine()` (imports with the heavy stack absent — verified); CITED export shape `format="engine", half=True, batch=4, imgsz=640, end2end=False, device=0`; argparse `weights/imgsz/batch/device` + `--dynamic` escape hatch (default static batch=4). Built `yolo26s.engine` on the rig in ~340s.
- **Engine-aware `PerCameraTracker` loader** — `__init__` accepts `engine_path`; loads `YOLO(engine)` when set + on-disk (`is_engine=True`); on ANY load failure or a missing engine file, logs a warning and falls back to the eager `.pt` (`is_engine=False`) — NEVER crashes (RBT-04). The `track()` degrade-to-None fail-safe + lazy ultralytics import preserved byte-for-byte.
- **Engine Track-B fix (Rule 1)** — a static batch=N engine REJECTS the single-frame `track()` warmup (`input (1,3,H,W) != max model size (4,3,H,W)`), so the original lazy warmup built no tracker and every camera coasted (the engine never actually tracked). The engine path now builds the per-camera `BOTSORT` DIRECTLY (mirroring `on_predict_start`, cls-ReID fallback — Q1 (a)); batched `predict([4])` drives detection, the directly-built BOTSORT drives association.
- **`is_engine` thread-through** — `_default_tracker_factory` + `build_orchestrator` thread `config.model.engine_path` + `use_fp16`; the loop's once-before-loop reid gate threads `is_engine`; `assert_native_reid_engaged` downgrades the predictor-None AND empty-`predictor.trackers` raises to warnings when `is_engine=True` (the engine's detection-only predict sets `predictor` but builds no `predictor.trackers`).
- **GPU gate armed for the engine** — `test_loop_latency_p95_under_budget` auto-detects `yolo26s.engine` beside the weights and points `engine_path` at it; loads via the engine-aware `PerCameraTracker`, graceful eager fallback when absent. Measured p95 ≈ 194ms (FAIL).

## Task Commits

1. **Task 2: ship tools/build_engine.py + docs/run.md** — `6b9b9e6` (feat)
2. **Task 3 (RED): failing engine-aware loader + graceful-fallback tests** — `512050b` (test)
3. **Task 3 (GREEN): engine-aware PerCameraTracker loader + factory threading** — `c344699` (feat)
4. **Task 4: is_engine reid-gate threading verification + engine-path gpu gate arm** — `d1e0b27` (test)
5. **Task 5 (Rule 1 fix found during the rig run): engine path actually tracks** — `5fa9a4b` (fix)

**Plan metadata:** (this commit — docs: complete plan)

## Files Created/Modified
- `tools/build_engine.py` (NEW) — the TensorRT FP16 engine build CLI (lazy import, CITED export shape, `--dynamic`)
- `tests/test_engine_loader_fallback.py` (NEW) — engine present→is_engine; load-raises→eager fallback; missing-file→eager; engine_path=None→eager; factory threads keys
- `src/segugio/tracking/detector.py` — engine-aware `__init__` (graceful fallback); `_ensure_persistent_tracker` engine branch + `_build_engine_botsort` (direct BOTSORT, no single-frame warmup)
- `src/segugio/tracking/reid_check.py` — `is_engine` downgrades the predictor-None AND empty-trackers raises to warnings (engine detection-only predict)
- `src/segugio/orchestrator/runtime.py` — `_default_tracker_factory` + `build_orchestrator` thread `engine_path` + `use_fp16`
- `tests/test_fan_out_batched.py` — +2 tests: engine path WARNS via the REAL gate (Q1 a), eager path HARD-raises on cls fallback
- `tests/test_latency.py` — gpu gate auto-detects `yolo26s.engine` → loads via engine-aware tracker, graceful eager fallback when absent
- `tests/test_orchestrator_runtime.py` — `_FakeTracker` + `tracker_factory` accept the new `engine_path`/`use_fp16` kwargs
- `docs/run.md` — `tools/build_engine.py` build invocation + GPU-specific/rebuild-per-rig/AC caveats + onnx export-dep note + "point the loop at the engine"

## Decisions Made
- **Q1 → Option (a)** (see the dedicated section above): accept cls-ReID fallback on the engine; gate warns-not-raises. Single-dog domain (A2) makes cheap cls-ReID sufficient; Option (b) is the documented fallback.
- **Static batch=4 engine** (not dynamic): matches the 4-cam fan-out; the loop pads dead slots with a blank frame, so a static batch is valid. `--dynamic` is the escape hatch for reduced-camera operation.
- **Direct BOTSORT construction on the engine path** (Rule 1 fix): the static-batch engine cannot run the single-frame `track()` warmup, so the per-camera tracker is built directly from the resolved `botsort_dog.yaml` (cls-ReID encoder, Q1 a) — discovered + fixed during the real rig run, not assumed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The engine path never actually tracked — single-frame warmup incompatible with a static batch=N engine**
- **Found during:** Task 5 (the real GPU gate run — the first run logged `track() degraded a frame to no-detection (coast): input size torch.Size([1, 3, 640, 640]) not equal to max model size (4, 3, 640, 640)` on EVERY tick).
- **Issue:** `PerCameraTracker.update()` → `_ensure_persistent_tracker()` ran a single-frame `self.track(frame)` warmup to build the per-camera BOTSORT. A static batch=4 engine REJECTS a 1-frame forward, so the warmup raised, `self._bot` stayed `None`, `update()` returned `None`, and every camera coasted — the engine ran detection-only forwards + failing warmups, never real tracking. The first "pass" was measuring fast failures, NOT engine inference (caught by reading the logs — exactly the fabricated-pass trap the orchestrator warned against).
- **Fix:** On the engine path, build the per-camera `BOTSORT` DIRECTLY (`_build_engine_botsort`, mirroring Ultralytics `on_predict_start`, cls-ReID fallback) instead of the single-frame warmup. The batched `predict([4 frames])` (matching the engine's batch) drives detection.
- **Files modified:** `src/segugio/tracking/detector.py`
- **Commit:** `5fa9a4b`

**2. [Rule 1 - Bug] The reid gate crashed the loop on the engine path (predictor-None / empty-trackers)**
- **Found during:** Task 5 (the second run logged `tick 0 failed → SAFE coast: no trackers on predictor — did .track() run with a botsort yaml?`).
- **Issue:** On the engine path the batched `model.predict()` sets `model.predictor` but builds NO `predictor.trackers` (those are detection-only forwards; association lives on each `PerCameraTracker._bot`). `assert_native_reid_engaged` raised on the empty `predictor.trackers` BEFORE reaching the `is_engine` downgrade, crashing the gate (swallowed by the tick's RBT-04 SAFE-coast, but the loop never tracked).
- **Fix:** Added the `is_engine` downgrade to BOTH the `predictor is None` and the empty-`predictor.trackers` branches — WARN + return on the engine path (the cls-ReID encoder lives on the per-camera `_bot`).
- **Files modified:** `src/segugio/tracking/reid_check.py`
- **Commit:** `5fa9a4b`

### Plan note (not a deviation)
- The plan's reid-gate threading (`is_engine` from `tracker.is_engine` into `assert_native_reid_engaged`) was ALREADY wired by 06-02 (`_maybe_reid_gate`); Task 4 verified it and the `reid_check.py` engine-aware warn-not-raise downgrade landed in 06-01. This plan's NEW reid_check work is the predictor-None / empty-trackers downgrades (Deviation #2) that 06-01 did not anticipate (06-01 assumed the eager warmup would always populate `predictor.trackers`).

### Task 1 + Task 5 executed (not paused)
- Task 1 (`checkpoint:decision`) was pre-decided by the orchestrator → Option (a), recorded here. Task 5 (`checkpoint:human-verify`) was RUN on the live `venv312` GPU env (AC power) per the orchestrator's authorization — the engine was built and the gate measured honestly (p95 ≈ 194ms, FAIL), NOT a human pause.

## Issues Encountered
- **RBT-05 NOT met on the engine path (~194ms ≥ 150ms).** The static-batch FP16 engine on the RTX 4000 Ada **Laptop** GPU only shaved ~210ms → ~194ms. The next lever (Option (b) / yolo26n engine / camera-reduction ladder) is surfaced above, NOT silently applied. Re-measure on the actual desktop deploy GPU before committing to a lever — a Laptop GPU under-parallelizes the batch.
- **Competitor-lock continuity on a multi-dog clip (RESEARCH A2)** — NOT verified this run: the gpu gate uses synthetic random frames and no curated multi-dog footage exists locally. DEFERRED manual check; did NOT block the p95 gate (as instructed). If single-dog cls-ReID continuity proves insufficient on real footage, Option (b) is the documented fallback.
- Two NDI-marked tests require a LIVE NDI sender (hardware-gated, out of scope); the headless suite (`-m "not ndi and not gpu and not obs"`) is fully GREEN. Logged, not fixed (SCOPE BOUNDARY).

## Next Phase Readiness
- **The prod TensorRT FP16 path is shipped and works** (engine builds, loads, tracks with graceful eager fallback — RBT-04) but does NOT meet RBT-05 on the Laptop GPU. RBT-05 remains the open Phase-6 risk.
- **Decision needed before the next latency plan:** which lever to pull (Option (b) eager-track/engine-detect re-plan, yolo26n engine swap, or — last resort, flagged — the camera-reduction ladder), and re-measure on the actual desktop deploy GPU. The seams are all in place: `is_engine` flows tracker→loop→gate, `engine_path`/`use_fp16` thread through the factory, the engine build CLI is documented in `docs/run.md`.

## Self-Check: PASSED

All created/modified files exist on disk and all 5 task commits are present in git history:
- Files: `tools/build_engine.py`, `tests/test_engine_loader_fallback.py`, `detector.py`, `reid_check.py`, `runtime.py`, `test_fan_out_batched.py`, `test_latency.py`, `test_orchestrator_runtime.py`, `docs/run.md` — all FOUND.
- Commits: `6b9b9e6`, `512050b`, `c344699`, `d1e0b27`, `5fa9a4b` — all FOUND.
- Engine artifact `yolo26s.engine` built (22.3 MB) + gitignored (verified `git check-ignore`).

---
*Phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc*
*Completed: 2026-06-13 (Q1 → Option (a); engine BUILT + gate RUN on the rig — p95 ≈ 194ms, FAIL → RBT-05 still open, next lever surfaced)*
