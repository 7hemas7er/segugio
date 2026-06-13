---
phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
plan: 01
subsystem: tracking
tags: [tensorrt, fp16, yolo, botsort, reid, batched-inference, pydantic, latency]

# Dependency graph
requires:
  - phase: 04-yolo-per-camera-tracking
    provides: assert_native_reid_engaged HARD gate, PerCameraTracker, ModelConfig, lazy-import boundary
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    provides: Orchestrator _fan_out per-camera dispatch + _arrays_from_results consumer shape, run_measured latency probe, gpu marker
provides:
  - engine-aware assert_native_reid_engaged (is_engine kwarg — warn-not-raise on engine, eager HARD raise unchanged)
  - ModelConfig.engine_path + ModelConfig.use_fp16 additive keys (default to eager-FP32 .pt)
  - batched_detect_dispatch — Track-B one-forward → N-tracker-update adapter (#13107-safe)
  - docs/run.md GPU latency env section + engine-rebuild caveat
  - .gitignore *.engine / *.onnx (GPU-specific build artifacts)
affects: [06-02-eager-fp16-batching, 06-03-engine-build, decision-loop-latency]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "engine-aware downgrade: is_engine kwarg downgrades a structural HARD raise to a warning only on engine-backed models"
    - "Track-B batched detect: ONE predict([frames]) then per-camera tracker.update(), never model.track([frames]) (#13107)"
    - "static-batch padding (Pitfall 4): dead None slot padded with a blank frame, result coasts to None"

key-files:
  created:
    - src/segugio/tracking/batched.py
    - tests/test_reid_check_engine_aware.py
    - tests/test_batched_detect.py
    - tests/test_config_engine_keys.py
  modified:
    - src/segugio/tracking/reid_check.py
    - src/segugio/config/models.py
    - docs/run.md
    - .gitignore

key-decisions:
  - "Open Q1 Option (a): on an engine-backed model the cls-ReID fallback is ACCEPTED (logged warning), not raised — native feats are structurally impossible via AutoBackend (Pitfall 1)"
  - "engine_path/use_fp16 are additive config keys defaulting to today's eager-FP32 behavior — no existing config affected, extra=forbid preserved"
  - "batched.py is detection-only batching with per-camera association (one tracker per cam_id) — the only #13107-safe way to batch"

patterns-established:
  - "is_engine kwarg threads engine-ness explicitly so the eager .pt HARD gate keeps its raise byte-for-byte at the default"
  - "batched_detect_dispatch returns the {cam_id: Results|None} consumer map matching _arrays_from_results"

requirements-completed: []  # RBT-05 NOT complete — gated on Task 1 (GPU env) + Wave 1/2 measurement

# Metrics
duration: 18min
completed: 2026-06-13
---

# Phase 6 Plan 1: Wave-0 latency substrate Summary

**Engine-aware ReID gate (warn-not-raise on engine, eager HARD raise preserved) + additive ModelConfig engine_path/use_fp16 keys + a #13107-safe batched-detect adapter — the headless seams every later latency task depends on, all landed without touching the live inference path.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-13
- **Completed:** 2026-06-13
- **Tasks:** 3 of 4 completed (Task 1 is a human-only GPU-env checkpoint — see below)
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments
- `assert_native_reid_engaged` is now engine-aware: an `is_engine=True` model downgrades the cls-fallback / missing-hook would-be `RuntimeError` to a `logger.warning` and returns; `is_engine=False` (default) keeps the eager `.pt` TRK-02 HARD gate byte-for-byte. Call sites untouched (default arg keeps them green).
- `ModelConfig` gained two additive keys — `engine_path: Path | None = None` and `use_fp16: bool = False` — defaulting to today's eager-FP32 `.pt` behavior, with `extra="forbid"` preserved.
- `src/segugio/tracking/batched.py` provides `batched_detect_dispatch` — ONE `model.predict([frames])` detection forward then per-camera `tracker.update()`, never a frame list to one tracker (#13107). Dead slots pad to a blank frame for a static batch (Pitfall 4) and coast to `None` (RBT-04). Proven headless with fakes (no GPU).
- `docs/run.md` documents the py3.12 cu12x-torch + tensorrt env stand-up, both probe commands, the AC-power requirement, and the "engine is GPU-specific, rebuild per rig" caveat. `.gitignore` excludes `*.engine`/`*.onnx`.

## Task Commits

Each task was committed atomically (TDD tasks have test → feat pairs):

1. **Task 2 (RED): failing engine-aware reid tests** — `7c3d2d8` (test)
2. **Task 2 (GREEN): engine-aware assert_native_reid_engaged** — `198a3b5` (feat)
3. **Task 3 (RED): failing config-keys + batched-adapter tests** — `9c3d99c` (test)
4. **Task 3 (GREEN): ModelConfig keys + batched.py adapter** — `08e46a7` (feat)
5. **Task 4: docs/run.md GPU env + gitignore engine artifacts** — `7079422` (docs)

**Plan metadata:** (this commit — docs: complete plan)

## Files Created/Modified
- `src/segugio/tracking/reid_check.py` — added `is_engine: bool = False` kwarg; engine-backed models warn-not-raise on cls fallback / missing hook; eager path raise unchanged
- `src/segugio/config/models.py` — added additive `engine_path` + `use_fp16` keys to `ModelConfig`
- `src/segugio/tracking/batched.py` (NEW) — Track-B `batched_detect_dispatch`: one detection forward → N per-camera tracker updates, #13107-safe, lazy-import boundary held
- `tests/test_reid_check_engine_aware.py` (NEW) — 4 behaviors: eager raise / engine warn / native pass / default-arg gate
- `tests/test_batched_detect.py` (NEW) — #13107 isolation, coast contract, static-batch padding (fake model + fake trackers)
- `tests/test_config_engine_keys.py` (NEW) — additive defaults, extra=forbid, explicit parse
- `docs/run.md` — "GPU latency env (Phase 6)" section
- `.gitignore` — `*.engine` / `*.onnx`

## Decisions Made
- **Open Q1 → Option (a):** accept the cheap `yolo26n-cls.pt` cls-ReID fallback on the engine path (logged warning) rather than failing the live loop — a TensorRT `.engine` loads via AutoBackend and structurally cannot expose the in-graph Detect head the native-ReID hook attaches to (RESEARCH Pitfall 1). The explicit `is_engine` param keeps the eager path's HARD raise unchanged.
- Batching is **detection-only** with per-camera association — the only way to batch the forward while preserving one BoT-SORT tracker per `cam_id` (#13107). Never `model.track([frames])`.
- The two config keys are **additive and inert** at their defaults so no existing config changes behavior; the engine load + graceful-fallback wiring is deferred to Wave 2 (06-03).

## Deviations from Plan

None - plan executed exactly as written for the three headless tasks (2, 3, 4). Task 1 is a human-only GPU-env checkpoint that the executor cannot perform (no rig access) — surfaced as a checkpoint, not deviated.

## Issues Encountered
None. Full headless suite green after each task; the lazy-import boundary held (`import segugio.tracking.batched` / `reid_check` / `config.models` all succeed with the heavy stack absent). The GPU/NDI/OBS-gated tests SKIP on this CPU box as expected.

## User Setup Required

**A one-time GPU environment stand-up is required on the RTX 4000 Ada rig (Task 1, blocking-human checkpoint).** The current py3.14 venv has CPU-only torch and no `tensorrt` cp314 wheel, so every `-m gpu` measurement test SKIPs and nothing is measurable. See `docs/run.md` → "GPU latency env (Phase 6)" for the exact commands. On AC power, in a new py3.12 venv, confirm:
1. `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → `True` + RTX 4000 Ada
2. `python -c "import tensorrt; print(tensorrt.__version__)"` → `10.x`
3. `python -c "import ultralytics; print(ultralytics.__version__)"` → `8.4.62`
4. `pytest tests/test_latency.py -m gpu --co -q` → the gpu latency test is COLLECTED

## Next Phase Readiness
- The three headless seams are ready: the engine-aware ReID gate (Wave 2 threads `is_engine` from `tracker.is_engine`), the two config keys (Wave 1 uses `use_fp16`, Wave 2 uses `engine_path`), and the batched adapter (Wave-B latency path).
- **Blocked on Task 1:** every GPU measurement task (eager FP16, engine build, the RBT-05 `<150ms` latency gate) is dead until the py3.12 cu12x-torch + tensorrt env is confirmed live on the rig. RBT-05 is NOT complete.

## Self-Check: PASSED

All created/modified files exist on disk and all 5 task commits are present in git history:
- Files: `batched.py`, `test_reid_check_engine_aware.py`, `test_batched_detect.py`, `test_config_engine_keys.py`, `docs/run.md`, `.gitignore`, `reid_check.py`, `config/models.py` — all FOUND.
- Commits: `7c3d2d8`, `198a3b5`, `9c3d99c`, `08e46a7`, `7079422` — all FOUND.

---
*Phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc*
*Completed: 2026-06-13 (Tasks 2-4; Task 1 awaiting human GPU-env stand-up)*
