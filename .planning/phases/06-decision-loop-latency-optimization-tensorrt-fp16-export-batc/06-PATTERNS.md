# Phase 6: Decision-loop latency optimization (TensorRT FP16 + batched inference) - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 7 (5 modified, 2 new)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/tracking/detector.py` (MODIFY) | service (inference wrapper) | request-response (per-frame) | itself (`PerCameraTracker`) — extend `__init__`/`track` | exact (self) |
| `src/segugio/tracking/reid_check.py` (MODIFY) | utility (startup gate) | request-response (one-shot assert) | itself (`assert_native_reid_engaged`) | exact (self) |
| `tools/build_engine.py` (NEW) | config / build tool (CLI) | batch (one-time export) | `src/segugio/orchestrator/runtime.py` (lazy-import builder pattern) | role-match |
| `src/segugio/tracking/export_engine.py` (NEW, optional) | utility (export helper) | batch (one-time) | `detector.py` `__init__` (lazy `from ultralytics import YOLO`) | role-match |
| `src/segugio/tracking/batched.py` (NEW, optional Track B) | service (batched detect adapter) | transform / batch | `detector.py` `track()` + `loop.py` `_fan_out` | role-match |
| `src/segugio/orchestrator/runtime.py` (MODIFY) | provider / factory | request-response | itself (`_default_tracker_factory`) | exact (self) |
| `tests/test_latency.py` (MODIFY) | test | request-response | itself (`test_loop_latency_p95_under_budget`) | exact (self) |

**Not modified (read-only consumers):** `src/segugio/orchestrator/loop.py` `_fan_out`/`run_measured` — the latency probe and per-camera independence contract; new code must preserve these shapes. `trackers/botsort_dog.yaml` — the ReID contract source.

## Pattern Assignments

### `src/segugio/tracking/detector.py` (service, per-frame request-response)

**Analog:** itself — `PerCameraTracker` is the ONLY YOLO inference site. Extend `__init__` (engine-aware load + fallback) and `track` (unchanged contract).

**Model-load site to extend** (`detector.py:130-148`, `PerCameraTracker.__init__`):
```python
def __init__(self, model_path, dog_idx: int, tracker_yaml) -> None:
    from ultralytics import YOLO  # lazy — heavy import INSIDE the constructor
    self.tracker_yaml = _resolve_tracker_yaml(tracker_yaml)
    self.model = YOLO(str(model_path))  # own predictor.trackers state per camera
    self.dog_idx = int(dog_idx)
```
- This is the single point where `.pt` → `.engine` swap + Pattern-3 graceful fallback lands. Currently NO engine awareness — `self.model` is a plain `YOLO(.pt)`.
- The engine-backed flag (research Pattern 3 returns `(model, is_engine)`) must be stored as e.g. `self.is_engine` so the loop's ReID gate can consult it (see reid_check below).

**Per-camera track call site to PRESERVE** (`detector.py:150-182`, `track`):
```python
results = self.model.track(
    frame, persist=True, classes=[self.dog_idx],
    tracker=self.tracker_yaml, end2end=False,  # CRITICAL: native ReID (TRK-02)
    verbose=False,
)
...
return results[0]
```
- Load-bearing fail-safe (`detector.py:168, 179-181`): `None`/zero-size frame → `return None`; any exception → `logger.warning(...)` + `return None`. Never crash (RBT-04). New batched/engine code MUST keep this no-crash degrade-to-coast contract.
- `end2end=False` is the ReID-engaging flag — keep it on the eager path; on an `.engine` it does NOT restore native ReID (research Pitfall 1), it only preserves the standard Detect output shape.

**Lazy-import boundary to honor** (`detector.py:26-37, 143`): `ultralytics`/`torch` imported INSIDE methods, `loguru` at top. `import segugio.tracking.detector` must succeed with the heavy stack absent (`tests/test_tracking_import_smoke.py`). Any new `tensorrt`/`torch.cuda` reference goes inside a method body.

**Anti-pattern guard already documented here** (`detector.py:1-20`): NEVER a frame list to one `.track()` (one tracker per `cam_id`, #13107). Track B's `batched.py` must do ONE batched `detect()` then dispatch to N per-camera tracker objects — not `model.track([frames])`.

---

### `src/segugio/tracking/reid_check.py` (utility, one-shot startup gate)

**Analog:** itself — `assert_native_reid_engaged`. Extend to be engine-aware (warn-not-raise when model is engine-backed, per research Pitfall 1 Option (a)).

**The HARD-raise to make conditional** (`reid_check.py:75-79`):
```python
if isinstance(enc, ReID):
    raise RuntimeError(
        "native ReID FELL BACK to a downloaded cls model (yolo26n-cls.pt). "
        "Pass end2end=False to model.track() so the standard Detect head engages."
    )
```
- On an `.engine`-backed model, native feats are structurally impossible (research: `track.py:45-59` hook needs an in-graph `nn.Module` Detect head; `.engine` loads via `AutoBackend`/`TensorRTBackend`). So this raise must downgrade to a `logger.warning(...)` IFF the model is engine-backed — and ONLY then.
- Current signature: `def assert_native_reid_engaged(model) -> None`. Decision needed (Open Q1): either add an `is_engine: bool` param (callers pass `tracker.is_engine`) or detect engine-ness from the predictor backend type inside the function. Prefer an explicit param so the eager path keeps the HARD raise unchanged.

**Caller site 1 — the live loop** (`loop.py:269-273`, in `_fan_out`):
```python
if not self._reid_checked and results is not None and hasattr(tracker, "model"):
    from ..tracking.reid_check import assert_native_reid_engaged
    assert_native_reid_engaged(tracker.model)  # RAISES on cls fallback (TRK-02)
    self._reid_checked = True
```

**Caller site 2 — the GPU eval harness** (`eval.py:330`, in `run_clip_eval`, guarded by `if not reid_checked and results is not None:`):
```python
assert_native_reid_engaged(tracker.model)  # RAISES on cls fallback (TRK-02)
reid_checked = True
```
- There are TWO runtime callers (`loop.py:272` and `eval.py:330`), both passing only `tracker.model`. If the gate gains an `is_engine` param, BOTH call sites update. (Test fixtures also reference the symbol: `tests/conftest_tracking.py`, `tests/test_yolo_clips_eval.py` — confirm with grep before editing.)

**Lazy-import boundary** (`reid_check.py:69`): `from ultralytics.trackers.bot_sort import ReID` is imported INSIDE the function. Keep it there.

---

### `tools/build_engine.py` (NEW — CLI build tool, one-time batch)

**Analog:** `src/segugio/orchestrator/runtime.py` — the lazy-import factory module pattern. There is no existing `tools/` script; follow runtime.py's conventions (module docstring explaining the one-time/cached nature, lazy heavy imports inside function bodies).

**Lazy heavy-import builder pattern to copy** (`runtime.py:94-98`):
```python
def _default_tracker_factory(model_path, class_index, tracker_yaml):
    from ..tracking.detector import PerCameraTracker  # LAZY heavy import
    return PerCameraTracker(model_path, class_index, tracker_yaml)
```
- Mirror this: `from ultralytics import YOLO` INSIDE the build function, never at module top.

**Export call** (research Code Examples, CITED docs.ultralytics.com/integrations/tensorrt):
```python
YOLO(weights).export(
    format="engine", half=True, batch=4, imgsz=640,
    device=0, end2end=False,  # static batch=4; add dynamic=True if cam count varies
)
```
- Source weights come from `config.model.path` (`ModelConfig.path`, default `yolo26s.pt`, `models.py:91`). Writes `yolo26s.engine` beside the weights.
- Build ONCE on the deploy RTX 4000 Ada; the artifact is GPU/driver-specific (research Pitfall 3). gitignore `*.engine`/`*.onnx`.

---

### `src/segugio/tracking/batched.py` (NEW, optional Track B — batched-detect adapter)

**Analog:** `detector.py` `track()` (single-frame inference + degrade-to-None) + `loop.py` `_fan_out` (per-camera dispatch loop, `loop.py:242-293`).

**Per-camera dispatch shape to preserve** (`loop.py:253-266`):
```python
for cam in self.cameras:
    cam_id = cam.id
    tracker = self.trackers[cam_id]
    frame = self.source.latest(cam_id)
    ...
    results = tracker.track(frame)
```
- Track B inverts this: ONE batched `model.predict([f0..f3], classes=[dog_idx], verbose=False)` (detection only), THEN dispatch each camera's detections to its OWN persistent BoT-SORT tracker (`tracker[cam].update(dets, frame)`). The load-bearing rule (`detector.py:1-20`): one tracker object per `cam_id`; batching is detection-only. Never `model.track([frames])` (#13107).
- Preserve the `None`/empty → coast degrade contract from `track()` (`detector.py:168, 179-181`) for each camera slot.
- Pitfall 4: a static `batch=4` engine needs exactly 4 frames — pad a dead camera's slot with a blank frame (the loop already coasts blanks) or build `dynamic=True`.

---

### `src/segugio/orchestrator/runtime.py` (provider / factory)

**Analog:** itself — `_default_tracker_factory` and `build_orchestrator`. If `PerCameraTracker.__init__` gains engine/fallback params, the factory threads them.

**Factory to extend** (`runtime.py:94-98`, shown above) and its call site (`runtime.py:159-162`):
```python
trackers = {
    cam.id: tracker_factory(config.model.path, config.model.class_index, _TRACKER_YAML)
    for cam in config.cameras
}
```
- The `tracker_factory` is INJECTABLE (default real, override with fakes in tests) — keep this seam. If engine-vs-eager selection is config-driven, it stays inside the default factory body so `import segugio.orchestrator.runtime` keeps succeeding heavy-stack-absent (`runtime.py:28-32`).
- `_TRACKER_YAML = "botsort_dog.yaml"` (`runtime.py:65`) — unchanged.

---

### `tests/test_latency.py` (test, GPU integration + headless unit)

**Analog:** itself — the existing 4-cam harness IS the phase pass/fail gate.

**The GPU budget assertion to re-run** (`test_latency.py:142-188`, `test_loop_latency_p95_under_budget`):
```python
trackers = {
    cam.id: PerCameraTracker(cfg.model.path, cfg.model.class_index, "botsort_dog.yaml")
    for cam in cfg.cameras
}
...
orch.run_measured(n_ticks=20)          # warmup (first inference = model/engine spin-up)
timings = orch.run_measured(n_ticks=100)
total_p95_ms = _p95(timings["total"]) * 1000.0
assert total_p95_ms < 150.0, ...
```
- Warmup is at `test_latency.py:184` (20 ticks); measurement window 100 ticks. Engine spin-up belongs in the warmup (research Pitfall 5). Run on AC power.
- `_p95` (`test_latency.py:26-34`): nearest-rank, `ceil(0.95*n)-1`. p95 over `timings["total"]`.
- The engine variant: build `yolo26s.engine` first (tools/build_engine.py), then this test loads it via the engine-aware `PerCameraTracker`. New headless unit tests needed: (a) engine-aware `assert_native_reid_engaged` (warn-not-raise when engine-backed), (b) Track B per-camera state isolation with fake detection arrays (#13107 regression guard, no GPU).

**Mock-timed regression tests to keep GREEN** (`test_latency.py:101-139`): `_FixedCostTracker` (`test_latency.py:60-75`) feeds a deterministic per-call cost; `test_mock_timed_wiring_overhead_p95_under_bound` asserts wiring p95 < 50ms; `test_mock_timed_fixed_inference_cost_is_attributed_to_yolo` asserts the fan-out cost lands in the `yolo` stage. Any probe/loop change must keep these passing.

## Shared Patterns

### Lazy heavy-import boundary
**Source:** `detector.py:26-37, 143`; `runtime.py:28-32, 81-98`; `reid_check.py:20-22, 69`
**Apply to:** ALL new/modified files touching `ultralytics`/`torch`/`tensorrt`
```python
def __init__(self, model_path, ...):
    from ultralytics import YOLO  # lazy — INSIDE the function body
```
`loguru` is the only heavy-ish dep imported at module top. `import segugio.tracking.*` and `import segugio.orchestrator.runtime` MUST succeed with the GPU stack absent (`tests/test_tracking_import_smoke.py`). Put every `import tensorrt` / `torch.cuda` reference inside a method.

### Graceful no-crash degrade (RBT-04, "nessun crash ammesso")
**Source:** `detector.py:167-181` (per-frame), `loop.py:436-442` (per-tick), `runtime.py` factory
**Apply to:** engine load (`detector.__init__`), batched detect, build CLI
```python
try:
    m = YOLO(str(engine))
    return m, True   # engine-backed → ReID policy differs (Pitfall 1)
except Exception as exc:  # noqa: BLE001 — incompatible engine must not crash
    logger.warning("engine load failed ({}) — falling back to eager {}", exc, weights_path)
return YOLO(str(weights_path)), False
```
A missing/incompatible `.engine` is the staleness signal — try-load-then-fallback, never crash. Eager FP32 is the fallback.

### One tracker per camera (#13107) — never a frame list
**Source:** `detector.py:1-20` (docstring contract), `loop.py:13-17, 253-266`, `runtime.py:159-162`
**Apply to:** `batched.py`, the engine path
Batching is DETECTION-ONLY: ONE `predict([frames])` forward, then dispatch per-camera detections into N persistent tracker objects. `model.track([f0..f3])` is FORBIDDEN (mixes IDs). CLAUDE.md "What NOT to Use" reinforces this.

### Injectable factory seam (headless testability)
**Source:** `runtime.py:101-137` (`*_factory` params default real, override with fakes)
**Apply to:** any new construction path (engine-vs-eager selection, build CLI invoked from tests)
Defaults import heavy deps lazily inside the builder body; tests pass fakes. Mirrors `ObsWsController.client_factory` / `NdiFrameSource._run_receiver`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase-6 file has a strong in-repo analog: the 4 modified files are extensions of themselves; the 2 new files (build CLI, batched adapter) closely follow `runtime.py`'s lazy-factory and `detector.py`'s inference-wrapper patterns. |

## Metadata

**Analog search scope:** `src/segugio/tracking/`, `src/segugio/orchestrator/`, `src/segugio/config/`, `trackers/`, `tests/`, `tools/` (absent)
**Files scanned:** detector.py, reid_check.py, loop.py, runtime.py, test_latency.py, botsort_dog.yaml, config/models.py
**Pattern extraction date:** 2026-06-13
