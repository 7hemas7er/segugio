---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
plan: 03
subsystem: tracking
tags: [yolo, botsort, native-reid, percamera-tracker, cv2, clip-decode, crops, gpu-marker, lazy-import]

# Dependency graph
requires:
  - phase: 04-yolo-per-camera-tracking-on-recorded-clips
    plan: 01
    provides: "lazy-import segugio.tracking surface + signals_from_boxes (TRK-03) + TrackingParams + crop_geometry/tracking_params fixtures + gpu marker registered"
  - phase: 01-config-and-substrate
    provides: "segugio.fixtures (resolve_clip_path/select_clips, traversal-safe) + lazy-import smoke harness (HEAVY_MODULES/_force_heavy_absent) + ModelConfig(path, class_index)"
provides:
  - "PerCameraTracker (TRK-01): one persistent YOLO().track(persist=True, end2end=False, classes=[dog_idx], tracker=botsort_dog.yaml) per cam_id — never a frame list (#13107)"
  - "resolve_dog_index (CFG-04): dog index resolved BY NAME from model.names, reconciled with config class_index (warns on mismatch); never hardcodes 16"
  - "assert_native_reid_engaged (TRK-02): HARD startup gate that RAISES on the silent yolo26n-cls.pt cls fallback (encoder is a ReID / no forward hook), logs on success"
  - "trackers/botsort_dog.yaml: BoT-SORT native-ReID override (with_reid:True, model:auto, track_buffer:60) where Ultralytics check_yaml resolves it"
  - "ClipFrameSource (D-01): cv2 decode + overlapping L/C/R spatial crops as pseudo-cameras, injected emitted-frame tick, empty-frame guard, stride sampling"
  - "gpu autouse-skip wired in tests/conftest.py (probe in conftest_tracking.gpu_available) — every @pytest.mark.gpu test SKIPs when torch/CUDA/ultralytics absent (D-09)"
  - "GPU eval skeleton (test_native_reid_engaged TRK-02 + test_per_camera_isolation TRK-01) — SKIPs here, 04-04 fills the overlay+metrics eval"
affects: [04-04-clip-eval, 05-integration-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "heavy-edge wrapper: heavy deps (ultralytics/torch/cv2) imported INSIDE methods/generators; loguru (light) at module top — import boundary holds with all three absent"
    - "one YOLO().track(persist=True) instance per cam_id (never a frame list, #13107); end2end=False is the load-bearing arg that engages native-feature ReID"
    - "HARD startup gate that RAISES (not warns) — the one true pass/fail GPU check (native-ReID engagement is a correctness invariant, not a tuning metric)"
    - "injected emitted-frame tick (no wall-clock) cloned from detection_stream; stride decimation samples ~50fps→~30Hz while tick stays a stable reproducible index"
    - "gpu-skip hook MUST live in conftest.py (pytest only loads conftest.py as a plugin); the gate logic is isolated + import-guarded in a sibling module conftest.py imports from"

key-files:
  created:
    - src/segugio/tracking/detector.py
    - src/segugio/tracking/reid_check.py
    - src/segugio/tracking/frame_source.py
    - trackers/botsort_dog.yaml
    - tests/conftest_tracking.py
    - tests/test_frame_source.py
    - tests/test_yolo_clips_eval.py
  modified:
    - tests/conftest.py

key-decisions:
  - "gpu-skip hook relocated from conftest_tracking.py into tests/conftest.py: pytest only auto-loads files literally named conftest.py as plugins, so a pytest_collection_modifyitems hook in conftest_tracking.py never fires. The gate LOGIC stays isolated + import-guarded in conftest_tracking.gpu_available(); conftest.py imports it in-body and applies the skip marker."
  - "ClipFrameSource default stride=2 (sample ~every 2nd frame of the 1080p50 source toward the ~30Hz AI tick); tick counts EMITTED frames (0,1,2,...) so it is a stable reproducible index independent of source fps"
  - "PerCameraTracker.track() wraps inference in try/except → returns None (coast) on any blank/decode-failure frame, satisfying the live no-crash requirement (RBT analogue) without an upstream guard duplication"

requirements-completed: [TRK-01, TRK-02]

# Metrics
duration: 6min
completed: 2026-06-10
---

# Phase 4 Plan 03: Heavy-Edge Per-Camera Tracker Summary

**The GPU-side heavy edge — `PerCameraTracker` (TRK-01: one `YOLO().track(persist=True, end2end=False)` per cam_id), `assert_native_reid_engaged` (TRK-02: the HARD gate that RAISES on the silent `yolo26n-cls.pt` fallback), `ClipFrameSource` (D-01: cv2 decode + overlapping L/C/R pseudo-camera crops), and `botsort_dog.yaml` — every heavy dep isolated behind the lazy-import boundary, plus the `@pytest.mark.gpu` eval skeleton that SKIPs CPU-side.**

## Performance

- **Duration:** 6 min (task-execution span)
- **Started:** 2026-06-10T01:22:13+02:00
- **Completed:** 2026-06-10T01:27:19+02:00
- **Tasks:** 2
- **Files modified:** 8 (7 created, 1 modified)

## Accomplishments

- **`PerCameraTracker` (TRK-01):** one `YOLO()` per `cam_id` owning its own `predictor.trackers` state; `track(frame)` calls `model.track(frame, persist=True, classes=[dog_idx], tracker=botsort_dog.yaml, end2end=False, verbose=False)` — never a frame list to one tracker (#13107). Lazy `from ultralytics import YOLO` inside `__init__`; a blank/zero-size/decode-failure frame degrades to `None` (coast), never a crash (RBT analogue).
- **`resolve_dog_index` (CFG-04):** reads `model.names` (`{idx:name}`), resolves the `dog` index BY NAME, reconciles against the configured `class_index` (warns + uses resolved on mismatch), raises `ValueError` if the model has no `dog` class. Never hardcodes 16 — robust to custom mono-class models (index 0).
- **`assert_native_reid_engaged` (TRK-02):** the HARD startup gate. RAISES if no trackers exist, if `with_reid` is off, if the encoder is a `ReID` instance (the silent `yolo26n-cls.pt` cls fallback), or if `predictor._hook` is absent; logs `BoT-SORT native-feature ReID engaged` on success. Lazy `from ultralytics.trackers.bot_sort import ReID` inside the function. This is the phase's central correction made a true pass/fail check (Q1/A1: a wrong head/attribute assumption fails LOUDLY at startup).
- **`trackers/botsort_dog.yaml`:** the native-ReID override (`with_reid:True`, `model:auto`, `track_buffer:60` = `Thresholds.track_buffer`, plus the verified BoT-SORT defaults) in a top-level `trackers/` dir so Ultralytics `check_yaml` resolves the bare name. Header documents that `model:auto` engages native ReID ONLY with `end2end=False`, and the two-place `track_buffer` coupling.
- **`ClipFrameSource` (D-01):** lazy-`cv2` decode of a committed slice → overlapping L/C/R pseudo-camera crops; yields `(tick, {cam_id: crop})` where `tick` is the EMITTED-frame index (no wall-clock); `stride` decimates ~50fps toward ~30Hz; a failed `cap.read()` / zero-size frame is skipped (NDI-03 precursor); paths resolved only via `fixtures.resolve_clip_path` (traversal-safe, the slices not `gara_full`). Capture always released.
- **GPU gate + eval skeleton (D-09):** `conftest_tracking.gpu_available()` probes torch/CUDA/ultralytics (import-guarded so CPU collection never imports torch); the SKIP hook in `tests/conftest.py` marks every `@pytest.mark.gpu` item skipped when the gate is unmet. `test_yolo_clips_eval.py` ships `test_native_reid_engaged` (TRK-02 hard gate) + `test_per_camera_isolation` (TRK-01) — both SKIP here.
- **Suite:** 195 passed, 2 skipped (baseline 192 passed → +3 CPU frame-source tests, +2 gpu-skipped eval skeleton; zero regressions). The lazy-import boundary holds: `import segugio.tracking.{detector,reid_check,frame_source}` all succeed with `ultralytics`/`torch`/`cv2` forced absent.

## Task Commits

Each task was committed atomically (sequential executor, normal commits with hooks):

1. **Task 1: PerCameraTracker (TRK-01) + native-ReID hard gate (TRK-02) + botsort_dog.yaml** — `5c11cb9` (feat)
2. **Task 2: ClipFrameSource (D-01) + gpu autouse-skip + frame-source/gpu-eval tests** — `0756e56` (feat)

## Files Created/Modified

- `src/segugio/tracking/detector.py` — `PerCameraTracker` (TRK-01) + `resolve_dog_index` (CFG-04); lazy `ultralytics` import, `end2end=False` track call, blank-frame coast fail-safe.
- `src/segugio/tracking/reid_check.py` — `assert_native_reid_engaged` (TRK-02) HARD gate; lazy `ReID` import; RAISES on cls fallback, logs on success.
- `src/segugio/tracking/frame_source.py` — `ClipFrameSource` (D-01); lazy `cv2` inside `frames()`; overlapping crops, emitted-frame tick, empty-frame guard, stride.
- `trackers/botsort_dog.yaml` — BoT-SORT native-ReID override (`with_reid:True`, `model:auto`, `track_buffer:60`); header documents `end2end=False` coupling + the two-place `track_buffer` coupling.
- `tests/conftest_tracking.py` — isolated, import-guarded `gpu_available()` probe (torch + CUDA + ultralytics).
- `tests/conftest.py` — added the `pytest_collection_modifyitems` gpu-skip hook (imports `gpu_available` in-body, marks `@pytest.mark.gpu` items skipped when the gate is unmet).
- `tests/test_frame_source.py` — CPU-only crop geometry: cam_ids, rect-sized crops, L/C overlap shares pixels, deterministic tick sequence; skips on absent gitignored slice.
- `tests/test_yolo_clips_eval.py` — `@pytest.mark.gpu` eval skeleton (`test_native_reid_engaged` TRK-02, `test_per_camera_isolation` TRK-01); SKIPs here.

## Decisions Made

- **gpu-skip hook MUST live in `conftest.py`, not `conftest_tracking.py`:** pytest only auto-loads files literally named `conftest.py` as plugins. A `pytest_collection_modifyitems` hook in a `conftest_tracking.py` file is never invoked — the gpu tests would FAIL with `ModuleNotFoundError` instead of skipping. Resolution (honoring the plan's explicit "if a single shared conftest is preferred, add the hook to the existing tests/conftest.py"): keep the gate LOGIC isolated + import-guarded in `conftest_tracking.gpu_available()`, and put the thin session hook in `tests/conftest.py` (imports the probe in-body). See Deviations.
- **`stride=2` default for `ClipFrameSource`:** the source is 1080p50, the AI tick is ~30Hz; sampling ~every 2nd frame brings the effective rate toward 30fps. `tick` counts EMITTED frames (0,1,2,...) — a stable reproducible index regardless of source fps — preserving the `detection_stream` determinism contract.
- **`track()` fail-safe lives in the wrapper, not upstream:** `PerCameraTracker.track()` wraps inference in try/except → `None` on any blank/decode-failure frame. This satisfies the live no-crash requirement at the single inference site without duplicating a guard in every caller; `ClipFrameSource` ALSO skips blank frames at decode (defense in depth).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] gpu autouse-skip hook in `conftest_tracking.py` never fired → gpu tests FAILED instead of SKIPPING**
- **Found during:** Task 2 (verifying acceptance criterion "gpu eval reports SKIPPED, not errored/failed").
- **Issue:** The plan's primary path placed the `pytest_collection_modifyitems` skip hook in a new `tests/conftest_tracking.py`. pytest only auto-discovers and loads files literally named `conftest.py` as plugins, so a hook defined in `conftest_tracking.py` is never invoked. Result: both `@pytest.mark.gpu` tests ran their bodies, hit `from ultralytics import ...` inside `PerCameraTracker.__init__`, and FAILED with `ModuleNotFoundError` (heavy group absent) — violating the "SKIPPED not errored" acceptance criterion and the D-09 contract.
- **Fix:** Applied the plan's documented alternative ("if a single shared conftest is preferred, instead add the hook to the existing tests/conftest.py; keep the gpu-skip logic isolated and import-guarded"). `conftest_tracking.py` now exposes only the isolated, import-guarded `gpu_available() -> (ok, reason)` probe (torch + CUDA + ultralytics, each `try/except`-guarded so collection never imports torch on a CPU box). The thin `pytest_collection_modifyitems` session hook moved into `tests/conftest.py`, importing `gpu_available` in-body and attaching `pytest.mark.skip` to every `gpu`-marked item when the gate is unmet.
- **Files modified:** `tests/conftest_tracking.py` (converted hook → probe helper), `tests/conftest.py` (added the session hook).
- **Verification:** `.venv/bin/python -m pytest -m gpu tests/test_yolo_clips_eval.py -rs` → both tests SKIPPED with reason `gpu eval skipped: torch not installed (heavy group absent) (D-09)`; full suite 195 passed, 2 skipped, zero errors. The lazy-import boundary is preserved (the torch probe is `try/except ImportError`-guarded, so collection never imports torch).
- **Committed in:** `0756e56` (Task 2 commit).

---

**Total deviations:** 1 auto-fixed (1 Rule-1 bug — the plan's own fallback path was the fix; isolated gate logic + hook placement, no scope change).
**Impact on plan:** None on deliverables. All TRK-01/TRK-02/D-01 artifacts ship exactly as specified; only the gpu-skip plumbing was relocated (within the plan's stated options) so the skip actually fires.

## Issues Encountered

None beyond the deviation above. Baseline suite was green (192 passed) before and is green (195 passed, 2 skipped) after — every new CPU test is additive, the two gpu tests skip by design, no Phase 1-4 regression.

## Known Stubs

None. `test_yolo_clips_eval.py` is the GPU eval SKELETON the plan output spec calls for — it ships two complete, runnable `@pytest.mark.gpu` tests (`test_native_reid_engaged`, `test_per_camera_isolation`) that SKIP on this CPU box by design (D-09) and run for real on the CUDA box once `.[heavy]` is installed. It is NOT a placeholder: the test bodies fully exercise `PerCameraTracker` + `assert_native_reid_engaged` against a real committed slice. 04-04 ADDS the overlay+metrics eval on top (per the plan's "04-04 wires the overlay+metrics eval"); it does not complete this skeleton. The `detector`/`reid_check`/`frame_source` modules are complete implementations with no TODO/FIXME markers.

## User Setup Required

None for the CPU deliverables (all shipped + tested CPU-only). To RUN the GPU eval (04-04 / deploy box): `pip install -e ".[heavy]"` + a CUDA torch build (the CUDA GPU is present on this WSL box: driver 596.36 / CUDA 13.2). On first GPU run, `assert_native_reid_engaged()` is the hard gate that confirms native ReID actually engages on `yolo26s.pt` with `end2end=False` (STATE.md Phase-4 concern) — if it RAISES, escalate per Open Question Q1 (ByteTrack/YOLO11 fallback).

## Next Phase Readiness

- **04-04 (clip eval)** is unblocked: `PerCameraTracker` + `assert_native_reid_engaged` + `ClipFrameSource` + `botsort_dog.yaml` are the heavy edge it drives; the gpu marker + skip are wired; the eval skeleton (`test_native_reid_engaged`, `test_per_camera_isolation`) is the seam 04-04 extends with overlay render + per-clip metrics (ID-switch, %lock-held, coast/uncertain, recall on distant/dusk).
- The 04-02 pure brain (`CompetitorLock` / `PlausibilityGate`) consumes `signals_from_boxes` (04-01) output; the heavy edge now produces the `Results` rows those signals come from. Wiring the full per-camera `DetectionSignal | None` stream (edge → signals_map → brain → scorer shape) lands in 04-04 / Phase 5.
- STATE.md Phase-4 concern (verify native-ReID engagement on yolo26s at startup) is now MECHANIZED — `assert_native_reid_engaged` is the runnable hard gate; it executes on the first GPU run.
- No blockers.

## Self-Check: PASSED

All created files exist and both task commits are present (verified in the self-check step below).

---
*Phase: 04-yolo-per-camera-tracking-on-recorded-clips*
*Completed: 2026-06-10*
