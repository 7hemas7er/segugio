---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
plan: 01
subsystem: testing
tags: [yolo, botsort, tracking, pydantic, pytest, numpy, lazy-import, tdd]

# Dependency graph
requires:
  - phase: 02-framing-scorer-pure-substrate
    provides: "frozen DetectionSignal output contract (signals.py) + detection_stream synth substrate + ScorerParams additive sub-model pattern"
  - phase: 01-config-and-substrate
    provides: "lazy-import boundary + import-smoke harness (HEAVY_MODULES/_force_heavy_absent/PHASE1_SURFACE) + conftest fixtures (seeded_rng/SEED/FPS) + additive Config wiring"
provides:
  - "segugio.tracking lazy-import package surface (pure: re-exports TrackingParams + signals_from_boxes; cv2/heavy stay out of the top level)"
  - "TrackingParams additive pydantic sub-model (TRK-04/05 seeds: max_displacement_per_tick, max_size_ratio, motion_window, motion_deadzone), wired into Config.tracking"
  - "signals_from_boxes — the PURE TRK-03 mapper (Results-row arrays -> frozen DetectionSignal, float/int cast, ids=None coast)"
  - "multi_track_stream — deterministic N-track per-tick synthetic emitter + linear_left path (the 04-02 competitor-lock/crossing substrate)"
  - "gpu pytest marker registered; tracking_params + crop_geometry (L/C/R overlapping rects, D-01) conftest fixtures; two green pure tests"
affects: [04-02-competitor-lock-plausibility-brain, 04-03-heavy-edge-percamera-tracker, 04-04-clip-eval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "additive pydantic sub-model (clone of ScorerParams): ConfigDict(extra=forbid) + bounded Annotated Fields, config imports UP from the sub-model module (no cycle)"
    - "PURE Results-row -> frozen DetectionSignal mapper: numpy in / list out, mandatory float()/int() casts, ids=None -> [] coast guard"
    - "lazy-import boundary extended to a package that will lazy-import cv2: import-smoke test forces cv2 ABSENT alongside HEAVY_MODULES; source-grep purity scoped to pure modules only"
    - "deterministic multi-track synth: injected rng only (one normal draw per present detection), shared _path_cx vocabulary, per-track dropout coast, fail-fast unknown path"

key-files:
  created:
    - src/segugio/tracking/__init__.py
    - src/segugio/tracking/params.py
    - src/segugio/tracking/signals_map.py
    - tests/test_tracking_import_smoke.py
    - tests/test_signals_map.py
  modified:
    - src/segugio/config/models.py
    - src/segugio/synth/detection_stream.py
    - src/segugio/synth/__init__.py
    - pyproject.toml
    - tests/conftest.py
    - tests/test_imports.py

key-decisions:
  - "Task 1 ships signals_map.py as a NotImplementedError stub so segugio.tracking imports; Task 2 (TDD) replaces it with the real pure mapper — keeps the RED phase genuinely failing"
  - "multi_track_stream takes a list-of-dict track specs and returns list[list[DetectionSignal]] (present detections per tick); a track in its dropout window contributes nothing (per-track coast)"
  - "linear_left path (cx 0.8->0.2) added so two tracks cross; _path_cx is the single shared path vocabulary for detection_stream + multi_track_stream"

patterns-established:
  - "Pattern: a package destined to lazy-import cv2 proves its purity by an import-smoke test that forces cv2 absent AND a source-grep over only the pure modules (heavy-edge modules excluded)"
  - "Pattern: a frozen-record mapper float()/int()-casts every field so a numpy scalar never leaks into the dataclass =="

requirements-completed: [TRK-03]

# Metrics
duration: 4min
completed: 2026-06-10
---

# Phase 4 Plan 01: Tracking Substrate Summary

**Lazy-import `segugio.tracking` package + additive `TrackingParams` config sub-model + PURE `signals_from_boxes` (TRK-03) mapper + deterministic multi-track synth substrate + Wave-0 test infra (gpu marker, fixtures, import-smoke + signals-map tests).**

## Performance

- **Duration:** 4 min (task-execution span)
- **Started:** 2026-06-10T01:07:50+02:00
- **Completed:** 2026-06-10T01:11:13+02:00
- **Tasks:** 2
- **Files modified:** 11 (5 created, 6 modified)

## Accomplishments

- `segugio.tracking` package imports CPU-only with `torch`/`ultralytics`/`cv2` ALL forced absent — the lazy-import boundary holds, proven by a new import-smoke test that adds `cv2` to the absent set (this package is the first to lazy-import cv2 in the 04-03 heavy edge).
- `TrackingParams` additive sub-model (TRK-04/05 seeds) wired into `Config.tracking` via `default_factory` — existing YAML omitting a `tracking:` block still validates; a typo'd or out-of-range seed fails fast at config-load (`ConfigDict(extra="forbid")` + bounded `Field`s, T-04-01-01).
- `signals_from_boxes` — the PURE TRK-03 mapper: numpy Results-row arrays in, `list[DetectionSignal]` out, every field `float()`/`int()`-cast (no numpy scalar leaks into the frozen `==`), `ids=None` coasts to `[]` without raising (T-04-01-02).
- `multi_track_stream` — a deterministic N-track per-tick synthetic emitter (the 04-02 competitor-lock/crossing substrate): two tracks cross via the new `linear_left` path, per-track dropout coasts, same seed → byte-identical output.
- Wave-0 infra: `gpu` pytest marker registered (so 04-03's `@pytest.mark.gpu` does not warn), `tracking_params` + `crop_geometry` (D-01 L/C/R overlapping rects) conftest fixtures, two green pure tests. Full suite 178 passed (was 167; +11, zero regressions).

## Task Commits

Each task was committed atomically:

1. **Task 1: scaffold segugio.tracking package + TrackingParams + gpu marker** - `97b6be1` (feat)
2. **Task 2 (RED): failing TRK-03 signals_map + multi-track tests** - `9d9b035` (test)
3. **Task 2 (GREEN): implement signals_map + multi-track substrate + fixtures** - `7d58693` (feat)

_Task 2 is TDD: test (RED) → feat (GREEN). No refactor commit — the GREEN implementation was clean as written._

## Files Created/Modified

- `src/segugio/tracking/__init__.py` - Lazy-import package surface; re-exports only `TrackingParams` + `signals_from_boxes` (heavy-edge modules deliberately NOT re-exported).
- `src/segugio/tracking/params.py` - `TrackingParams` pydantic sub-model (4 bounded TRK-04/05 seeds), light-import-only so `config` imports UP from it.
- `src/segugio/tracking/signals_map.py` - PURE TRK-03 `signals_from_boxes` mapper (Results-row arrays → frozen `DetectionSignal`).
- `src/segugio/config/models.py` - Added `from ..tracking.params import TrackingParams` + `tracking: TrackingParams = Field(default_factory=TrackingParams)` (additive).
- `src/segugio/synth/detection_stream.py` - Added `multi_track_stream` + `linear_left` path; extracted shared `_path_cx` (detection_stream behavior unchanged).
- `src/segugio/synth/__init__.py` - Re-export `multi_track_stream`.
- `pyproject.toml` - Registered the `gpu` marker under `[tool.pytest.ini_options]`.
- `tests/conftest.py` - Added `tracking_params` + `crop_geometry` fixtures.
- `tests/test_imports.py` - Appended `"segugio.tracking"` to `PHASE1_SURFACE`.
- `tests/test_tracking_import_smoke.py` - Import-smoke (cv2 forced absent) + pure-module source-grep purity test.
- `tests/test_signals_map.py` - TRK-03 mapping + None-id coast + multi-row + determinism + multi-track substrate tests.

## Decisions Made

- **signals_map.py ships as a stub in Task 1, real impl in Task 2 (TDD):** `segugio.tracking.__init__` re-exports `signals_from_boxes`, so the module must exist for Task 1 to import. A `NotImplementedError` stub satisfies the import while keeping Task 2's RED phase a genuine failure (the stub raises). Task 2 GREEN replaced it with the pure mapper.
- **`multi_track_stream` shape:** list-of-dict track specs in, `list[list[DetectionSignal]]` out (present detections per tick). A track inside its dropout window contributes nothing that tick — the per-track coast substrate the 04-02 brain tests need.
- **`linear_left` + shared `_path_cx`:** added `linear_left` (cx 0.8→0.2) so two tracks cross; refactored the path→cx computation into one `_path_cx` helper used by both `detection_stream` and `multi_track_stream` (single source of truth for the path vocabulary), leaving the existing `detection_stream` output byte-identical.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Acceptance-criterion literal form `import segugio.synth.detection_stream as d; d.multi_track_stream` is unsatisfiable due to a pre-existing module/function name collision**
- **Found during:** Task 2 (verifying the multi_track_stream acceptance criterion)
- **Issue:** `segugio.synth.__init__` does `from .detection_stream import detection_stream`, which binds the package attribute `segugio.synth.detection_stream` to the **function** (not the submodule). So `import segugio.synth.detection_stream as d` resolves `d` to the function, and `d.multi_track_stream` raises `AttributeError`. This is a pre-existing collision (function name == module name) that has always made `detection_stream` the module unreachable via that attribute-access form — not introduced by this plan.
- **Fix:** No code change to the collision (renaming the Phase-2 module/function would be a breaking change, Rule 4 territory and unnecessary). Added `multi_track_stream` to `segugio.synth.__all__`/re-exports for discoverability. The substantive criterion ("`multi_track_stream` exists and the same seed produces byte-identical output") is fully verified via the canonical `from segugio.synth.detection_stream import multi_track_stream` import, which the test uses and which is green.
- **Files modified:** src/segugio/synth/__init__.py
- **Verification:** `from segugio.synth.detection_stream import multi_track_stream` works; same-seed output is byte-identical; `tests/test_signals_map.py` (multi-track determinism + dropout + fail-fast) all green.
- **Committed in:** `7d58693` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 Rule-1 bug — verification-form-only, no behavior gap).
**Impact on plan:** None on functionality. The criterion's intent is fully met via the canonical import path; only the literal attribute-access form was unsatisfiable due to a pre-existing Phase-2 naming collision. No scope creep.

## Issues Encountered

None beyond the deviation above. Baseline suite was green (167) before and is green (178) after — every new test is additive, no Phase 1-3 regression.

## User Setup Required

None - no external service configuration required. All work is CPU-only and heavy-deps-absent (no YOLO weights, no GPU, no NDI involved in this plan).

## Next Phase Readiness

- **04-02 (the brain)** is unblocked: `TrackingParams`, the `DetectionSignal` output contract via `signals_from_boxes`, and the deterministic `multi_track_stream` substrate (two-dogs / crossing / dropout) are all in place; `tracking_params` + `crop_geometry` fixtures are available.
- **04-03 (heavy edge)** is unblocked: the `gpu` marker is registered (its autouse skip conftest lives alongside the GPU test in 04-03), the lazy-import boundary is proven to survive cv2 absent, and `crop_geometry` (D-01) is ready for the `ClipFrameSource` crops.
- No blockers. STATE.md carries the open Phase-4 concern (verify native-ReID engagement on yolo26s at startup; measure COCO dog recall) — that work lands in 04-03.

## Self-Check: PASSED

All created files exist and all task commits are present (verified below in the self-check step).

---
*Phase: 04-yolo-per-camera-tracking-on-recorded-clips*
*Completed: 2026-06-10*
