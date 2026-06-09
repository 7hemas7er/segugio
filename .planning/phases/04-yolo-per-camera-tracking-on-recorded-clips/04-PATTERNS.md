# Phase 4: YOLO + Per-Camera Tracking on Recorded Clips - Pattern Map

**Mapped:** 2026-06-10
**Files analyzed:** 13 new + 3 modified
**Analogs found:** 16 / 16

> Every new Phase-4 file has a strong in-repo analog. This codebase is internally
> consistent (frozen dataclasses, injected `tick`, lazy-import boundary, additive pydantic
> sub-models, source-grep purity gates) — the planner should clone these patterns rather
> than invent. The only genuinely new shapes are the two thin heavy-edge wrappers
> (`detector.py`, `frame_source.py`), and even those have a precedent in `fixtures.py`'s
> "package-side, opencv-free, lazy" discipline.

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/segugio/tracking/__init__.py` | package surface | — | `src/segugio/framing/__init__.py` | exact |
| `src/segugio/tracking/signals_map.py` | utility (pure) | transform | `src/segugio/framing/terms.py` | exact (pure-fn module) |
| `src/segugio/tracking/competitor_lock.py` | service (pure) | event-driven (per-tick state) | `src/segugio/framing/scorer.py` (`CameraScorer`) | exact (stateful pure class) |
| `src/segugio/tracking/plausibility.py` | service (pure) | event-driven (per-tick state) | `src/segugio/framing/scorer.py` + `terms.plausibility_ok` | exact |
| `src/segugio/tracking/params.py` | config / model | — | `src/segugio/framing/params.py` (`ScorerParams`) | exact |
| `src/segugio/tracking/detector.py` | service (heavy edge) | request-response (frame→Results) | `src/segugio/fixtures.py` (lazy, package-side edge) | role-match (no YOLO analog exists) |
| `src/segugio/tracking/reid_check.py` | utility (heavy edge, startup) | request-response | (no analog — new) | no analog |
| `src/segugio/tracking/frame_source.py` | service (heavy edge) | file-I/O (clip decode→crops) | `src/segugio/fixtures.py` (`resolve_clip_path`) + `synth/detection_stream.py` (injected `tick`) | role-match |
| `src/segugio/tracking/eval.py` | service (heavy edge + pure counters) | batch / file-I/O | `src/segugio/fixtures.py` (clip query) + `scorer.MultiCamScorer` (fan-out) | role-match |
| `trackers/botsort_dog.yaml` | config | — | `config.example.yaml` (committed YAML) | role-match (external-tool yaml) |
| `tests/test_tracking_import_smoke.py` | test | — | `tests/test_decision_imports.py` / `tests/test_framing_purity.py` | exact |
| `tests/test_signals_map.py` | test (pure) | — | `tests/test_framing_*` (synthetic-input unit) | exact |
| `tests/test_competitor_lock.py` | test (pure) | — | `tests/test_framing_purity.py` (determinism) + `test_decision_scenarios.py` | exact |
| `tests/test_plausibility_gate.py` | test (pure) | — | `tests/test_framing_coast.py` style | exact |
| `tests/test_tracking_metrics.py` | test (pure counters) | — | `tests/test_framing_*` | exact |
| `tests/test_yolo_clips_eval.py` | test (GPU-gated integration) | file-I/O | (no analog — first `@pytest.mark.gpu` test) + `test_fixtures_catalogue.py` (skip on absent fixture) | role-match |

### Modified files (additive only)

| Modified File | Change | Closest Analog (how it was done before) |
|---------------|--------|------------------------------------------|
| `src/segugio/config/models.py` | add `tracking: TrackingParams = Field(default_factory=...)` to `Config` | how `scoring: ScorerParams` was added (`models.py:120`) |
| `pyproject.toml` | register `gpu` marker under `[tool.pytest.ini_options]` | the existing `[tool.pytest.ini_options]` block (`pyproject.toml:39-42`) |
| `tests/conftest.py` | add `tracking_params` + crop-geometry fixtures (mirror `scorer_params`) | `scorer_params` fixture (`conftest.py:123-132`) |
| `tests/test_imports.py` | add `"segugio.tracking"` to `PHASE1_SURFACE` | the list already grew for framing/decision (`test_imports.py:20-27`) |

---

## Pattern Assignments

### `src/segugio/tracking/signals_map.py` (utility, pure transform — TRK-03)

**Analog:** `src/segugio/framing/terms.py` (pure-function module, numpy + stdlib only, `from __future__ import annotations`, `__all__`, `TYPE_CHECKING`-only imports of the frozen records).

**Output contract — emit `DetectionSignal` UNCHANGED.** The mapper's whole job is to fill the frozen record at `src/segugio/framing/signals.py:41-61`. Do not re-define it, do not add fields:
```python
@dataclass(frozen=True)
class DetectionSignal:
    tick: int
    cam_id: str
    cx: float   # normalized bbox center x ∈ [0,1]
    cy: float
    w: float
    h: float
    conf: float
    track_id: int
```
`Results.boxes.xywhn` is already `(cx,cy,w,h)` normalized to the crop → maps with no math. `float()`/`int()`-cast at construction so a `numpy.float64` never leaks into the frozen `==` (the convention enforced in `signals.py:11-12` and every `terms.py` return).

**Module-header / import pattern** (clone from `terms.py:26-45`):
```python
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
if TYPE_CHECKING:                       # type-only — no runtime cost
    from segugio.framing.signals import DetectionSignal
__all__ = ["signals_from_boxes"]
```
Note: the actual `DetectionSignal` import for *construction* is a runtime import — keep it a normal `from segugio.framing.signals import DetectionSignal` (light, stdlib-only module; safe under the lazy boundary). `terms.py` only needs it for typing, but this module constructs it.

**Core pattern** (RESEARCH.md Pattern 3 — pure: numpy arrays in, list out, `None`-id guarded):
```python
def signals_from_boxes(xywhn, ids, confs, tick, cam_id):   # PURE
    out = []
    if ids is None:                      # no confirmed tracks this frame → empty (coast)
        return out
    for (cx, cy, w, h), tid, conf in zip(xywhn, ids, confs):
        out.append(DetectionSignal(
            tick=int(tick), cam_id=cam_id,
            cx=float(cx), cy=float(cy), w=float(w), h=float(h),
            conf=float(conf), track_id=int(tid),
        ))
    return out
```

---

### `src/segugio/tracking/competitor_lock.py` (service, pure stateful — TRK-04)

**Analog:** `src/segugio/framing/scorer.py` `CameraScorer` (lines 89-227) — the exact "one stateful pure object per camera, driven by `update(..., tick)` once per tick, deterministic given its input stream" shape. Clone:
- the **module docstring discipline** (`scorer.py:1-38`): state the locked decisions (D-03/04/05) it honors, declare "Clock-free and RNG-free; imports only numpy + stdlib".
- **constructor seam** (`scorer.py:110-131`): take `camera` (for `camera.zones`) + `params` (the new `TrackingParams`), initialize `self.locked_id: int | None = None` and a bounded `deque` history exactly like `self.hist: deque = deque(maxlen=...)` at `scorer.py:128`.
- the **velocity / finite-difference-over-history** idiom (`scorer.py:133-147`) is the template for `_motion_energy` (cumulative displacement over a window).

**Sticky-continuity core** (RESEARCH.md "Competitor-lock skeleton" + D-04 — keep locked id while alive; re-acquire only on genuine loss):
```python
def select(self, candidates, tick):           # candidates: list[DetectionSignal] (dog, this cam, this tick)
    self._update_history(candidates, tick)
    alive_ids = {c.track_id for c in candidates}
    if self.locked_id in alive_ids:            # D-04 sticky: keep while present
        return self._by_id(candidates, self.locked_id)
    in_field = [c for c in candidates if self._in_any_zone(c)]   # D-03 zone gate
    if not in_field:
        self.locked_id = None
        return None                            # nothing in-field → coast
    best = max(in_field, key=lambda c: self._motion_energy(c.track_id))  # D-03 motion
    self.locked_id = best.track_id
    return best
```

**Zone test reuses the EXISTING point-in-rect** from `terms.zone_of` (`terms.py:111-131`) — do NOT hand-roll: `z.rect[0] <= cx <= z.rect[2] and z.rect[1] <= cy <= z.rect[3]`. `camera.zones` are the validated normalized `Zone` rects from `config/models.py:49-66`.

**Fail-safe, not fail-loud** (clone `scorer.py:30-37`): never raise on data the validated `Config` passed; a NaN candidate → treat as absent → coast (`None`). Mirror `_is_finite_detection` at `scorer.py:78-86`.

---

### `src/segugio/tracking/plausibility.py` (service, pure stateful — TRK-05)

**Analog:** `src/segugio/framing/scorer.py` (stateful `prev`-carrying object) — and CRITICALLY, the **distinct-from** analog is `terms.plausibility_ok` (`terms.py:186-203`). D-07: TRK-05 is the *inter-frame* gate; `plausibility_ok` is the *intra-frame* guard. Keep them in **different modules with different signatures** so they never get conflated (PITFALLS Pitfall 5).

**What NOT to reuse — the intra-frame guard (`terms.py:186-203`)** stays where it is and keeps its meaning ("is this box a plausible dog at all"). The new gate is stateful across ticks and takes the *previous accepted locked box* + the *current candidate*:
```python
class PlausibilityGate:
    def __init__(self, params):
        self.p = params                        # max_displacement_per_tick, max_size_ratio (config seeds)
        self.prev = None                       # previous ACCEPTED locked DetectionSignal
    def check(self, det):
        if det is None:
            return None                        # genuine miss → coast
        if self.prev is not None:
            disp = math.hypot(det.cx - self.prev.cx, det.cy - self.prev.cy)
            area, prev_area = det.w * det.h, self.prev.w * self.prev.h
            ratio = (area / prev_area) if prev_area > 0 else float("inf")
            r = self.p.max_size_ratio
            if disp > self.p.max_displacement_per_tick or not (1.0 / r <= ratio <= r):
                return None                    # D-06: suspect swap → uncertain → coast
        self.prev = det                        # accept; NOT updated on reject (no poison)
        return det
```

**The coast mechanism is FREE — emit `None`.** Do not build any new coast/TTL logic. Returning `None` flows straight into the existing `CameraScorer.update` coast branch at `scorer.py:196-220` (FRM-05 holds the last EMA, status `coasting`). This is exactly how `detection_stream` already emits `None` in a dropout window (`detection_stream.py:77-79`). Divisor guard (`prev_area > 0`) mirrors the guards throughout `terms.py` / `scorer.py:145`.

---

### `src/segugio/tracking/params.py` (config sub-model — TRK-05 seeds, D-07)

**Analog:** `src/segugio/framing/params.py` `ScorerParams` (the whole file) — the **additive pydantic sub-model** pattern. Clone verbatim:
```python
from __future__ import annotations
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field   # add model_validator only if a cross-field invariant exists
__all__ = ["TrackingParams"]
Norm = Annotated[float, Field(ge=0.0, le=1.0)]      # params.py:27

class TrackingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")        # params.py:41 — typo'd keys fail fast
    # --- TRK-05 inter-frame gate seeds (D-06) ---
    max_displacement_per_tick: Annotated[float, Field(gt=0.0)] = ...   # normalized units/tick
    max_size_ratio: Annotated[float, Field(gt=1.0)] = ...              # area ratio band [1/r, r]
    # --- TRK-04 competitor-lock seeds (D-03) ---
    motion_window: Annotated[int, Field(ge=1)] = ...                   # K-tick displacement window
    # --- crop geometry / class resolution as appropriate (Claude's Discretion) ---
```
Key facts to mirror from `ScorerParams` (`params.py:1-41`): docstring says "values are tuning *seeds*; the SCHEMA/bounds are what's locked", every field bounded so a bad value fails at config-load not in the hot loop, `ConfigDict(extra="forbid")`. If a cross-field invariant exists, use `@model_validator(mode="after")` exactly like `_weights_sum_to_one` (`params.py:71-84`).

**Light-import only** — `params.py:14-15`: "depends on nothing from `segugio.config`" (so the arrow points config → tracking, never reverse — this is why `ScorerParams` lives under `framing` not `config`). Decide where `TrackingParams` lives (likely `src/segugio/tracking/params.py`) so `config.models` imports UP from it, mirroring `from ..framing.params import ScorerParams` at `models.py:32`.

---

### `src/segugio/tracking/detector.py` (heavy edge — TRK-01 + TRK-02 call site)

**Analog:** `src/segugio/fixtures.py` (the only existing "package-side, lazy, edge" module) — clone its discipline: a module that *could* touch heavy I/O but keeps the import inside functions. There is **no YOLO analog in the repo** (first heavy-inference code), so the pattern is set by RESEARCH.md Pattern 1 + the lazy-import boundary.

**Lazy heavy import — INSIDE the method, never module top** (the load-bearing constraint; the import-smoke test enforces it). RESEARCH.md Pattern 1:
```python
class PerCameraTracker:                         # ONE instance per cam_id (#13107)
    def __init__(self, model_path, dog_idx, tracker_yaml):
        from ultralytics import YOLO            # ◀ lazy — inside, never module top
        self.model = YOLO(str(model_path))      # own predictor.trackers state per cam
        self.dog_idx = dog_idx
        self.tracker_yaml = str(tracker_yaml)
    def track(self, frame):                     # frame = ONE numpy BGR crop for THIS cam
        results = self.model.track(
            frame, persist=True,                # keep this cam's tracker state across ticks
            classes=[self.dog_idx],             # dog only (resolved BY NAME at startup)
            tracker=self.tracker_yaml,          # botsort_dog.yaml (check_yaml-resolvable)
            end2end=False,                      # ◀ CRITICAL: enables native ReID (TRK-02)
            verbose=False,
        )
        return results[0]
```

**Name-resolve `dog`, reconcile with `class_index`** (RESEARCH.md Pattern 2; the CLAUDE.md "What NOT to Use" first row). `model.names` is `{idx: name}`; the configured value comes from `ModelConfig(path, class_index)` at `config/models.py:81-91` (docstring there already says "re-verified against `model.names` at load time in Phase 4"):
```python
names = model.names
dog_indices = [i for i, n in names.items() if n == "dog"]
if not dog_indices: raise ValueError(...)
resolved = dog_indices[0]
if resolved != cfg.model.class_index:
    logger.warning("configured class_index={} but resolves dog={}", cfg.model.class_index, resolved)
dog_idx = resolved
```

**Logging:** use `loguru` exactly like `fixtures.py:35` (`from loguru import logger`), routed through `segugio.logging.configure_logging` (the idempotent sink, proven at `test_imports.py:71-93`).

**Anti-patterns (RESEARCH.md "Anti-Patterns to Avoid", lines 299-307) — enforce all:** never a frame-list to one `.track()`; never default `end2end=True`; never trust `track_id` as subject identity; one tracker per `cam_id`.

---

### `src/segugio/tracking/reid_check.py` (heavy edge, startup HARD gate — TRK-02)

**Analog:** none in-repo (first runtime-introspection startup assertion). The pattern is RESEARCH.md "Code Examples — native-ReID engagement assertion" (lines 374-402), verbatim runnable. **This is a HARD gate (raise, not warn)** per the Specific Ideas in CONTEXT and Open Question Q1.

**Core (RESEARCH.md lines 380-401), lazy-import `ReID` inside the function:**
```python
def assert_native_reid_engaged(model) -> None:
    predictor = model.predictor                 # exists only after first .track()
    trackers = getattr(predictor, "trackers", None)
    if not trackers: raise RuntimeError("no trackers — did .track() run with a botsort yaml?")
    bot = trackers[0]
    enc = getattr(bot, "encoder", None)
    from ultralytics.trackers.bot_sort import ReID   # ◀ lazy import inside the function
    if enc is None: raise RuntimeError("with_reid False — not enabled in botsort_dog.yaml")
    if isinstance(enc, ReID):
        raise RuntimeError("native ReID FELL BACK to yolo26n-cls.pt. Pass end2end=False.")
    if getattr(predictor, "_hook", None) is None:
        raise RuntimeError("native-ReID forward hook not registered — fallback likely.")
    logger.info("BoT-SORT native-feature ReID engaged (zero extra weights, end2end=False).")
```
Run ONCE at startup after the first `track(..., end2end=False)` warmup call. Assumption A1 (RESEARCH.md:486) is mitigated *because* this raises loudly — keep it a raise.

---

### `src/segugio/tracking/frame_source.py` (heavy edge — clip decode + spatial crops, D-01)

**Analog:** `src/segugio/fixtures.py` (opencv-free manifest query → use it to *select* clips) + `src/segugio/synth/detection_stream.py` (the injected-`tick` generator shape). There is no cv2-decode analog in-repo (`fixtures.py:6-8` deliberately avoids cv2), so this is the first module to lazy-import `cv2`.

**Lazy `cv2` import inside the function** (RESEARCH.md Pattern 4 + the boundary):
```python
def frames(self):                               # generator: yields (tick, {cam_id: crop})
    import cv2                                   # ◀ lazy — inside, never module top
    cap = cv2.VideoCapture(str(self.clip_path))
    ...
```

**Injected `tick`, no wall-clock** — clone the `detection_stream` contract (`detection_stream.py:15-19, 76`): `tick` is the emitted frame index; 50→~30 striding is the planner's call but `tick` stays the *emitted* index for determinism.

**Resolve clip paths via the existing API** — do NOT re-implement path handling. Use `segugio.fixtures.resolve_clip_path(file)` (`fixtures.py:166-215`) and `select_clips(load_manifest(), discipline="disc_dog", conditions=[...])` (`fixtures.py:108-136`). The committed disc-dog slices (`handler_close_01.mp4`, `crowd_distractor_01.mp4`, `sprint_blur_01.mp4`, `distant_01.mp4`, `dusk_distant_01.mp4`, `warm_jump_01.mp4`) are real 1920×1080 @ ~49.5 fps files in `tests/fixtures/disc_dog/`. **Use the slices, not `gara_full.mp4`** (A5: it is a 35769s symlink, likely absent on the CUDA box).

**Crop rect → `cam_id` maps to per-camera config zones** — each crop is a `Camera` with its own normalized `Zone` rects (`config/models.py:49-78`); the crop normalizes `xywhn` to the crop, which is exactly what the per-camera zone-gate consumes.

---

### `src/segugio/tracking/eval.py` (heavy edge render + pure metric counters — D-08)

**Analog:** `src/segugio/framing/scorer.py` `MultiCamScorer` (the per-camera fan-out, `scorer.py:230-277`) for the per-cam loop shape + `src/segugio/fixtures.py` for clip selection. The **metric counters are PURE** (split them out so they're unit-testable in `test_tracking_metrics.py` without cv2/GPU); only the overlay render (`cv2` draw + `VideoWriter`) is the heavy edge — lazy-import `cv2` inside the render function exactly like `frame_source.py`.

**Metrics to count (D-08):** locked-subject ID-switch count, % frames lock-held, coast/uncertain counts, signal dump. These are pure integer/ratio counters over the `DetectionSignal | None` stream — mirror the determinism of the pure brain.

---

### `trackers/botsort_dog.yaml` (external-tool config override)

**Analog:** `config.example.yaml` (a committed, hand-authored YAML the package reads). **Location matters** (D-01 Claude's Discretion + RESEARCH.md "Don't Hand-Roll"): must live where Ultralytics `check_yaml` resolves it (a `trackers/` dir on the search path, or pass an absolute path to `model.track(tracker=...)`). Content (RESEARCH.md lines 404-421):
```yaml
tracker_type: botsort
with_reid: True
model: auto                # engages native ReID ONLY with end2end=False
track_buffer: 60           # = Thresholds.track_buffer (config/models.py:108)
track_high_thresh: 0.25
track_low_thresh: 0.1
new_track_thresh: 0.25
match_thresh: 0.8
proximity_thresh: 0.5
appearance_thresh: 0.8
gmc_method: sparseOptFlow  # static crops: consider None to save CPU
fuse_score: True
```
Note the `track_buffer: 60` duplicates `Thresholds.track_buffer` (`config/models.py:108`, and seeded in `conftest.py:108`). Planner decides whether to template the yaml from config at startup (single source of truth) or document the two-place coupling.

---

## Shared Patterns

### Lazy-import boundary (the phase's structural invariant)
**Source:** `tests/test_imports.py:30-56` (`_force_heavy_absent` + `PHASE1_SURFACE`) and `tests/test_framing_purity.py:122-180` / `tests/test_decision_imports.py:39-101` (the per-package re-application).
**Apply to:** ALL `src/segugio/tracking/*.py`. `import segugio.tracking` must succeed with `torch`/`ultralytics`/`cv2`/`cyndilib`/`obsws_python` ABSENT. Heavy imports go INSIDE functions/methods (`detector.py`, `reid_check.py`, `frame_source.py`, `eval.py` render). The pure modules (`signals_map`, `competitor_lock`, `plausibility`, `params`) import nothing heavy at all.

`test_tracking_import_smoke.py` clones `test_decision_imports.py` directly — reuse the single-sourced harness:
```python
from tests.test_imports import HEAVY_MODULES, _force_heavy_absent   # test_decision_imports.py:28
```
and the source-grep purity gate (`test_decision_imports.py:67-100` / `test_framing_purity.py:122-156`) for the PURE submodules — assert NO `import time` / `np.random` / `os` / `socket` / `cv2` / heavy dep appears in `signals_map.py` / `competitor_lock.py` / `plausibility.py` / `params.py`. (The heavy-edge files `detector.py`/`frame_source.py`/`eval.py` are EXCLUDED from the cv2/heavy grep — they legitimately import them inside functions. Scope the grep to the pure modules, or grep only module-top-level via the `(?m)^\s*import` anchored regexes already used, which pass because the heavy imports are indented inside functions.)

### Determinism convention (frozen records, injected tick, injected RNG)
**Source:** `src/segugio/framing/signals.py:8-12` (frozen `==` is the determinism assertion), `src/segugio/synth/detection_stream.py:15-19` (injected `Generator` is the ONLY randomness; `tick` is the synthetic index), `tests/test_framing_purity.py:97-119` (`run(seq) == run(seq)` byte-identical).
**Apply to:** `competitor_lock.py`, `plausibility.py`, `signals_map.py` and all their tests. Same synthetic track input → byte-identical `list[DetectionSignal | None]`. `float()`/`int()`-cast at construction (no numpy scalar in a frozen field). Mirrors the FRM-07 / DEC-07 gates.

### Synthetic test substrate (extend, don't rewrite)
**Source:** `src/segugio/synth/detection_stream.py` (frozen-dataclass + injected `rng` + injected `tick`; `PATHS` vocabulary with a fail-fast typo guard at `detection_stream.py:72-73`).
**Apply to:** the competitor-lock + plausibility + crossing-swap tests. RESEARCH.md Wave-0 calls for a **multi-track extension** (≥2 simultaneous tracks, per-track zone/motion/path) — extend `detection_stream`'s `path`/`track_id` knobs (add a `track_id`-keyed multi-emitter) rather than writing a new generator. The `None`-in-dropout-window idiom (`detection_stream.py:77-79`) is already the coast substrate.

### Additive config (no breaking change)
**Source:** `src/segugio/config/models.py:120` (`scoring: ScorerParams = Field(default_factory=ScorerParams)`) — existing YAML omitting `scoring:` still validates. The same `default_factory` story is in `params.py:3-8`.
**Apply to:** wiring `TrackingParams` into `Config` as `tracking: TrackingParams = Field(default_factory=TrackingParams)`. Existing `config.example.yaml` / `config.agility.example.yaml` keep validating untouched. Import direction: `config.models` imports UP from `tracking.params` (mirror `from ..framing.params import ScorerParams` at `models.py:32`).

### Shared pytest fixtures (reuse, don't recreate)
**Source:** `tests/conftest.py` — `seeded_rng` (`conftest.py:31-38`), `valid_config_dict` (`conftest.py:117-120`), `scorer_params` (`conftest.py:123-132`, the in-body lazy-import pattern).
**Apply to:** add `tracking_params` mirroring `scorer_params` exactly (in-body `from segugio... import TrackingParams; return TrackingParams()`), and a crop-geometry fixture. The fixed `SEED = 1234` (`conftest.py:24`) and `FPS = 30.0` (`conftest.py:28`) are the determinism baseline to reuse.

### GPU marker + skip (new, modeled on the absent-fixture skip)
**Source:** there is no `gpu` marker yet — register it in `pyproject.toml` `[tool.pytest.ini_options]` (extend the block at `pyproject.toml:39-42` with a `markers = ["gpu: ..."]` list). The skip-when-resource-absent precedent is `tests/test_fixtures_catalogue.py` (skips on `FixtureNotPresentError`, the `fixtures.py:73-80` typed error). 
**Apply to:** `test_yolo_clips_eval.py` — `@pytest.mark.gpu`; a `conftest` autouse `skipif` when `torch` import fails OR `torch.cuda.is_available()` is False OR `yolo26s.pt`/weights absent. On THIS box `torch`/`ultralytics` are absent → these SKIP (intended, D-09). The ONE exception that is a hard pass/fail (not a tuning number) is `assert_native_reid_engaged()` — it RAISES.

### Module docstring discipline (every file)
**Source:** every module here opens with a substantial docstring naming the locked decisions it honors, the determinism/purity contract, and the import boundary (`scorer.py:1-38`, `terms.py:1-24`, `params.py:1-16`, `signals.py:1-18`, `detection_stream.py:1-24`, `fixtures.py:1-27`).
**Apply to:** all new modules. Name the TRK-id and the D-0x decisions; state "pure / heavy-edge" and the lazy-import stance explicitly. This is a strong, consistent house style — match it.

---

## No Analog Found

| File | Role | Data Flow | Reason / Pattern source instead |
|------|------|-----------|--------------------------------|
| `src/segugio/tracking/reid_check.py` | startup runtime-introspection gate | request-response | First YOLO/BoT-SORT introspection in the repo. Use RESEARCH.md "native-ReID engagement assertion" (lines 374-402) verbatim — it is runnable, Context7-verified. |
| `src/segugio/tracking/detector.py` (YOLO `.track()` call) | heavy inference edge | request-response | No prior `ultralytics`/`torch` code exists. Pattern is set by RESEARCH.md Pattern 1 + CLAUDE.md "What NOT to Use". Lazy-import discipline borrowed from `fixtures.py`. |
| `tests/test_yolo_clips_eval.py` (`@pytest.mark.gpu` real-YOLO) | GPU-gated integration | file-I/O | First GPU test. Skip-on-absent-resource pattern borrowed from `test_fixtures_catalogue.py`; the marker itself is new (register in `pyproject.toml`). |

> These three are the **only** "no-analog" cases and they are exactly the heavy edge the
> architecture isolates. Every pure-brain file and every test of it has an exact in-repo
> twin — the planner should clone aggressively there.

## Metadata

**Analog search scope:** `src/segugio/{framing,synth,config,decision}/`, `src/segugio/fixtures.py`, `tests/`, `pyproject.toml`, `tests/fixtures/clip_manifest.yaml`.
**Files scanned (full read):** `framing/signals.py`, `framing/scorer.py`, `framing/terms.py`, `framing/params.py`, `framing/__init__.py`, `synth/detection_stream.py`, `synth/__init__.py`, `config/models.py`, `config/__init__.py`, `fixtures.py`, `tests/conftest.py`, `tests/test_imports.py`, `tests/test_decision_imports.py`, `tests/test_framing_purity.py`, `pyproject.toml`, `tests/fixtures/clip_manifest.yaml`.
**Pattern extraction date:** 2026-06-10
