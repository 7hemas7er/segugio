# Phase 6: Decision-loop latency optimization — TensorRT FP16 + batched/parallel inference - Research

**Researched:** 2026-06-13
**Domain:** GPU inference optimization (Ultralytics YOLO26 + TensorRT FP16) and multi-camera tracker concurrency
**Confidence:** HIGH on the inference-path mechanics and the engine↔ReID incompatibility; MEDIUM on the exact TensorRT/torch wheel matrix (must be confirmed by building on the RTX 4000 Ada rig)

## Summary

Phase 05 UAT Test 5 proved the decision loop is **inference-bound**: 4× `yolo26s.pt` running eager torch FP32, serialized one `model.track()` per camera per tick, measured **231–247ms p95** against the 150ms budget, with YOLO ≈100% of the loop and ingest/score/fsm/obs summing to ~0.5ms. `yolo26n` did not help on the GPU. So the two documented levers are exactly the right ones: (1) **TensorRT FP16 export** of the detector (eager FP32 is the slow path — the prod path is a compiled `.engine`), and (2) **batch or parallelize** the four currently-serialized per-camera inferences. Wiring overhead is already negligible, so neither lever risks the rest of the loop.

The single most important — and non-obvious — finding is a **hard conflict between a TensorRT engine and the project's locked native-feature BoT-SORT ReID** (TRK-02). Native ReID (`with_reid: True, model: auto`) engages ONLY when Ultralytics can register a forward-pre-hook on an in-graph `Detect` head that is an `nn.Module` with `end2end=False` (verified in the installed `ultralytics==8.4.62` at `trackers/track.py:45-59`). A `.engine` loads through `AutoBackend`/`TensorRTBackend` — it is **not** an `nn.Module` graph exposing `.model[-1]` — so the hook condition is False and BoT-SORT **silently downloads `yolo26n-cls.pt`** as a fallback ReID encoder. Segugio's existing HARD gate `assert_native_reid_engaged` (`src/segugio/tracking/reid_check.py`) would then **raise at startup**. This means "swap `yolo26s.pt` → `yolo26s.engine`" is NOT a drop-in — it changes the ReID contract. The plan must explicitly decide the ReID story for the engine path (Decision needed — see Open Questions Q1).

**Primary recommendation:** Pursue the latency budget in two independent, separately-measured tracks. **Track A (TensorRT FP16):** export `yolo26s.engine` with `half=True, batch=4, end2end=False`, build it ON the RTX 4000 Ada rig as a cached one-time artifact, load via `YOLO("yolo26s.engine")`, and resolve the native-ReID conflict by EITHER accepting the cheap `yolo26n-cls.pt` ReID fallback on the engine path (relaxing the HARD gate to a logged warning when the model is engine-backed) OR keeping ReID-bearing tracking on an eager model while only the detection forward pass is engine-accelerated. **Track B (batching/parallelism):** the *correct* way to batch detection while preserving per-camera tracker state is one batched `predict()`/`detect()` forward over the 4 frames, then feed each camera's detections into its OWN persistent `tracker.update()` — never a frame *list* to one `model.track()` (that builds ONE tracker and mixes IDs, #13107, which CLAUDE.md already forbids). Both tracks feed the existing `tests/test_latency.py -m gpu` harness, re-run after each change.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detector forward pass (the 58–62ms cost) | GPU / inference backend | — | This is the dominant cost; TensorRT FP16 + batched forward owns the win |
| Per-camera tracker state (BoT-SORT, ReID, persist) | Orchestrator (per-camera Python objects) | inference backend (feats for native ReID) | Must stay one-tracker-per-camera (#13107); the engine path breaks the feats source |
| Engine build / artifact lifecycle | Build-time tooling (one-time, cached) | filesystem (`.engine` artifact, gitignored) | GPU-specific binary; built once on the deploy GPU, not at runtime |
| Latency measurement | Test harness (`run_measured` + `test_latency.py`) | orchestrator probe | Already exists; re-used as the phase's pass/fail gate |
| Graceful fallback (engine missing/incompatible) | Model loader / `PerCameraTracker` / `build_orchestrator` | orchestrator (per-tick coast) | Live-robustness: never crash → degrade to eager FP32 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ultralytics` | `8.4.62` (already pinned) `[VERIFIED: installed venv + requirements.txt]` | `model.export(format="engine")` + `YOLO("*.engine")` load + tracking | The locked stack; its exporter wraps TensorRT; no new API to learn |
| `torch` | CUDA build (cu12x) — current venv is `2.12.0+cpu` `[VERIFIED: venv probe]` | GPU tensor backend; required for CUDA inference AND for the export step | A CUDA-enabled torch is mandatory; the current py3.14 venv has CPU-only torch (cannot run any GPU path) |
| `tensorrt` | `10.x` (latest `10.16.x` on PyPI; pip wheel bundles its CUDA runtime) `[CITED: pypi pip index versions]` | The TensorRT runtime Ultralytics' engine exporter/loader links against | Ultralytics auto-uses it when `format="engine"`; install the matching wheel for the deploy CUDA |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `onnx` / `onnxslim` | current | Intermediate graph the engine export passes through | Auto-pulled by the export path; only relevant if export fails and you debug the ONNX stage |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TensorRT FP16 `.engine` | Eager torch FP16 (`model.half()` / `half=True` at predict) | Far simpler, no build step, no engine↔ReID conflict — but typically a smaller speedup than TensorRT. Worth measuring as a cheap first rung BEFORE the full engine build (it may already clear 150ms with FP16 + batching alone). |
| TensorRT FP16 | TensorRT INT8 | Bigger speedup but needs calibration data AND must export on the exact deploy GPU; accuracy risk on a small/distant dog. Defer — FP16 is the documented target (RBT-05 / ROADMAP). |
| `yolo26s` | `yolo26n` | UAT proved nano does NOT help on this GPU (the loop is not compute-throughput-bound at nano's scale) — degradation-ladder rung 1 is a dead end here. |
| One batched `detect()` + per-camera `tracker.update()` | `model.track(source=[...], stream=True)` multi-stream mode | Ultralytics' stream mode DOES build N trackers (`track.py:61-67`, one per `dataset.bs` when `mode=="stream"`), but it is built around video-source iterators, not a per-tick push of 4 in-memory NDI frames — awkward to drive from the fixed-rate orchestrator. The manual batched-detect + per-camera-update path fits the existing loop shape exactly. |

**Installation (on the deploy rig, in a py3.12 venv):**
```bash
# 1. Create a py3.12 venv (the current py3.14 venv has NO cu12x torch wheel AND no tensorrt cp314 wheel)
py -3.12 -m venv venv312
venv312\Scripts\activate
# 2. Install Segugio's pinned stack
pip install -r requirements.txt
# 3. Install a CUDA-enabled torch (NOT the +cpu wheel) matching the deploy CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu126   # confirm channel on the rig
# 4. Install the TensorRT runtime wheel (pulls its own CUDA libs)
pip install tensorrt
# 5. Verify the GPU path is live BEFORE attempting an export
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

**Version verification (run on the rig — training-data versions are stale):**
```bash
pip index versions tensorrt        # confirm a 10.x wheel exists for the chosen CUDA + py3.12
python -c "import tensorrt; print(tensorrt.__version__)"
python -c "import ultralytics; print(ultralytics.__version__)"   # expect 8.4.62
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `ultralytics` | PyPI | mature (already pinned 8.4.62) | (API returned null) | github.com/ultralytics/ultralytics | OK (seam said SUS on `unknown-downloads`/`too-new` re: latest publish) | Approved — already locked; official repo, in use since Phase 4 |
| `torch` | PyPI | mature | (API returned null) | pytorch.org | OK (seam SUS on `unknown-downloads` only) | Approved — already a transitive dep of the locked `ultralytics` |
| `tensorrt` | PyPI | publisher NVIDIA; latest publish recent | (API returned null) | github.com/nvidia/tensorrt | OK (seam SUS on `too-new`/`unknown-downloads`) | Approved — official NVIDIA package; cited from Ultralytics TensorRT integration docs |

**Note on the SUS verdicts:** all three are `SUS` ONLY because the PyPI downloads endpoint returned `null` (the seam's `unknown-downloads` signal) and the *latest* release publish date is recent (rolling releases). They are the canonical NVIDIA / PyTorch / Ultralytics packages with authoritative source repos, and `ultralytics`+`torch` are ALREADY locked and in production use in this repo. The `tensorrt` recommendation is `[CITED: docs.ultralytics.com/integrations/tensorrt]`. Treat these as approved; no `checkpoint:human-verify` needed beyond the normal "build on the rig and confirm versions" step the phase requires anyway.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `tensorrt` (false-positive: official NVIDIA package, cited from Ultralytics docs — the planner may add a light verify step that simply confirms `import tensorrt` + version on the rig, which Track A already includes).

## Architecture Patterns

### System Architecture Diagram

```
                       per tick (fixed-rate, owns the clock)
                                     │
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Orchestrator._tick_once / _fan_out  (src/segugio/orchestrator/loop.py)│
   └─────────────────────────────────────────────────────────────────────┘
        │ source.latest(cam_id) × N        (ingest ~0ms, O(1) on mock/receiver)
        ▼
   ┌──────────── TODAY (slow path, 231–247ms p95) ─────────────┐
   │  for cam in cameras:                                       │
   │     tracker[cam].track(frame)   ← ONE model.track() each   │  ← serialized
   │       (eager FP32 yolo26s, end2end=False, BoT-SORT+ReID)   │     N× ~58–62ms
   └───────────────────────────────────────────────────────────┘
        │  Results → _arrays_from_results → signals_from_boxes
        ▼
   CompetitorLock → PlausibilityGate → MultiCamScorer → FeedWatchdog
        ▼
   DecisionEngine.tick → ObsController.cut → atomic status write
        │
        ▼  probe: {ingest, yolo, score, fsm, obs, total} → test_latency.py p95


   ┌──────────── PHASE 6 TARGET (inference path only) ─────────┐
   │  Track A: yolo26s.engine (TensorRT FP16, built on rig)    │
   │  Track B: ONE batched detect() over [f0..f3]              │
   │           → split detections per camera                   │
   │           → tracker[cam].update(dets_cam, frame_cam) ×N   │  ← per-cam state kept
   │     (engine breaks native-ReID feats → ReID decision Q1)  │
   └───────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (additive — minimal new surface)
```
src/segugio/tracking/
├── detector.py          # PerCameraTracker — EXTEND: accept .engine path + ReID-on-engine policy
├── reid_check.py        # assert_native_reid_engaged — EXTEND: engine-aware (warn vs raise)
├── export_engine.py     # NEW (dev/build tool): export_yolo_engine(weights, imgsz, batch) → .engine
└── batched.py           # NEW (optional, Track B): batched detect() + per-camera tracker.update()
tools/
└── build_engine.py      # NEW (CLI): one-time cached engine build on the deploy GPU
```

### Pattern 1: One-time cached TensorRT FP16 engine build (build-time, not runtime)
**What:** Export the `.engine` ONCE on the deploy GPU and cache the artifact; load it at runtime. Never export inside the live loop (export takes minutes and is GPU/driver-specific).
**When to use:** Track A, as a `tools/build_engine.py` step run once per GPU/driver/TensorRT combo.
**Example:**
```python
# Source: https://docs.ultralytics.com/integrations/tensorrt  [CITED]
from ultralytics import YOLO

model = YOLO("yolo26s.pt")
model.export(
    format="engine",
    half=True,        # FP16 — the RBT-05 target precision
    batch=4,          # max concurrent images = the 4-camera canonical config (Track B)
    imgsz=640,        # match the AI-path inference size used in the loop
    device=0,         # build ON the deploy GPU (RTX 4000 Ada) — engine is hardware-specific
    end2end=False,    # ◀ keep the standard Detect head (NMS post-process), NOT the NMS-free head
    # dynamic=False   # static batch=4 is fastest; set dynamic=True only if cam count varies
)
# → writes yolo26s.engine next to the weights; load it back identically:
engine_model = YOLO("yolo26s.engine")
```
**Why `end2end=False` on the engine:** Segugio's tracking contract is built around the standard Detect head (the per-frame `Results.boxes` with class filtering and the BoT-SORT update). `end2end=True` bakes NMS into the graph and changes the output shape to `(N, 300, 6)`. Also note the documented FP16 caveat: with `half=True, end2end=True` some outputs come back FP32 (issue #23645) — another reason to keep `end2end=False`. **Caveat:** `end2end=False` does NOT restore native ReID on an engine — see Pitfall 1; it only keeps the detection output shape Segugio expects.

### Pattern 2: Batched detection + per-camera tracker update (preserve per-camera state)
**What:** Run ONE forward pass over a stacked batch of the 4 camera frames, then dispatch each camera's detections to its OWN persistent BoT-SORT tracker. This collapses 4 serial forwards into 1 (the dominant win) WITHOUT mixing track IDs across cameras.
**When to use:** Track B. This is the correct interpretation of "batch the per-camera inferences" given the #13107 hazard.
**Example (shape — confirm exact Ultralytics surface on the rig):**
```python
# Conceptual — the load-bearing rule is one tracker object per camera. [ASSUMED exact API]
# Detection batched in ONE call:
results_list = model.predict([f_cam0, f_cam1, f_cam2, f_cam3], classes=[dog_idx], verbose=False)
# Then per-camera tracking on each camera's OWN persistent tracker:
for cam_id, results in zip(cam_ids, results_list):
    dets = results.boxes  # this camera's detections only
    trackers[cam_id].update(dets, frame_by_cam[cam_id])   # per-camera BoT-SORT state
```
**Anti-pattern this avoids:** `model.track([f0,f1,f2,f3], persist=True)` — builds ONE tracker, mixes IDs across cameras (#13107). CLAUDE.md "What NOT to Use" already forbids this; the batched-detect path is the latency win WITHOUT that hazard.

### Pattern 3: Graceful engine→eager fallback at load time (live robustness)
**What:** The model loader tries the `.engine`; on any failure (missing file, incompatible TensorRT/driver, wrong GPU) it logs and falls back to the eager `.pt`. Never crash (the live "nessun crash ammesso" constraint, RBT-04).
**When to use:** In `PerCameraTracker.__init__` / `build_orchestrator`'s tracker factory.
**Example:**
```python
# Pattern, not verified API — fits PerCameraTracker.__init__ (detector.py:130). [ASSUMED]
def _load_model(weights_path):
    engine = Path(weights_path).with_suffix(".engine")
    if engine.is_file():
        try:
            m = YOLO(str(engine))
            logger.info("loaded TensorRT engine {}", engine)
            return m, True  # engine-backed → ReID policy differs (Pitfall 1)
        except Exception as exc:  # noqa: BLE001 — incompatible engine must not crash
            logger.warning("engine load failed ({}) — falling back to eager {}", exc, weights_path)
    return YOLO(str(weights_path)), False
```

### Anti-Patterns to Avoid
- **Exporting the engine at runtime / in the loop:** export is slow and GPU-specific; build once, cache, load.
- **Passing a frame list to one `model.track()`:** one tracker, mixed IDs (#13107) — forbidden by CLAUDE.md.
- **Assuming `yolo26s.engine` is a drop-in for `yolo26s.pt` in the tracker:** it silently disables native ReID (Pitfall 1) and trips `assert_native_reid_engaged`.
- **Committing the `.engine` binary:** it is large and GPU/driver-specific — gitignore it; rebuild per rig.
- **Exporting on a different GPU than the deploy GPU:** an engine is tied to the GPU/driver/TensorRT it was built on; build on the RTX 4000 Ada.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FP16 GPU inference graph | A custom CUDA/cuDNN kernel pipeline | `model.export(format="engine", half=True)` | Ultralytics + TensorRT do layer fusion, precision calibration, kernel autotuning for you |
| Multi-frame batching | A manual `torch.stack` + raw forward + manual NMS | Ultralytics `predict([frames])` (batched) | Handles letterbox, NMS, class filter, `Results` construction; you only split per-camera afterward |
| Per-stream tracker state | A bespoke ID-disambiguation layer over one shared tracker | One `BoT-SORT`/`model.track(persist=True)` object PER camera | The project already does this (`PerCameraTracker`); keep it — batching is detection-only |
| Engine artifact versioning | Hand-rolled "is this engine current?" logic | Filesystem presence + try-load-then-fallback (Pattern 3) | A failed load IS the staleness signal; no metadata schema needed |

**Key insight:** Every part of this phase is configuration of the locked Ultralytics/TensorRT stack — the only genuinely new code is a one-time build CLI, a load-time fallback, and (for Track B) a thin batched-detect→per-camera-update adapter. The risk is NOT writing inference code; it is the **engine↔ReID interaction** and **getting a working CUDA+TensorRT py3.12 env on the rig**.

## Runtime State Inventory

> This is a code/perf phase, not a rename/migration. Included briefly because it introduces a cached binary artifact and a new env.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore keys change. | none |
| Live service config | None — OBS/NDI config untouched. | none |
| OS-registered state | None. | none |
| Secrets/env vars | None. | none |
| Build artifacts | **NEW: `yolo26s.engine`** (TensorRT binary, GPU/driver-specific) will be produced. Plus `yolo26s.onnx` intermediate. The auto-downloaded `yolo26s.pt` already lives in the ultralytics cache. | gitignore `*.engine` and `*.onnx`; document the rebuild step in `docs/run.md`; the engine is NOT portable across GPUs/drivers |

**Verified by:** reading `requirements.txt`, `config/models.py` (`ModelConfig.path`), and `detector.py` — the model is referenced purely by a config path; swapping `.pt`↔`.engine` is a config-path + loader concern, no stored state.

## Common Pitfalls

### Pitfall 1: TensorRT engine SILENTLY disables native-feature BoT-SORT ReID (the phase's central trap)
**What goes wrong:** Loading `yolo26s.engine` and tracking with `with_reid: True, model: auto` does NOT use native features. Ultralytics falls back to downloading `yolo26n-cls.pt` as the ReID encoder, and Segugio's `assert_native_reid_engaged` HARD gate (`reid_check.py:71-84`) RAISES at startup → the orchestrator's once-before-loop gate (`loop.py:269-273`) fails.
**Why it happens:** `[VERIFIED: ultralytics==8.4.62 trackers/track.py:45-59]` the native-ReID hook engages ONLY if `isinstance(predictor.model.model, torch.nn.Module) and isinstance(predictor.model.model.model[-1], Detect) and not …end2end`. A `.engine` loads through `AutoBackend`/`TensorRTBackend` (`nn/autobackend.py:87,146`) — it is not the in-graph `nn.Module` whose `.model[-1]` is a `Detect` head, so the condition is False, `cfg.model` is reassigned to `"yolo26n-cls.pt"` (`track.py:53`), and the forward-pre-hook that captures `Detect` input feats (`track.py:56-59` → consumed at `models/yolo/detect/predict.py:70-78`) is never registered. No feats → no native ReID.
**How to avoid:** Decide the ReID story for the engine path BEFORE planning tasks (Open Question Q1). Two viable options: (a) **Accept the `yolo26n-cls.pt` fallback ReID on the engine path** — make `assert_native_reid_engaged` engine-aware (downgrade to a logged warning when the model is engine-backed, since native feats are structurally impossible there) and verify single-dog tracking is still robust with the cheap cls-ReID; or (b) **keep tracking on an eager `.pt` model and only accelerate the detection forward pass with the engine**, dispatching engine detections into the existing eager-model trackers' `update()`. Option (a) is simpler and may well suffice for a single subject; option (b) preserves native ReID but is more plumbing.
**Warning signs:** Startup log "native ReID FELL BACK to a downloaded cls model" or a `RuntimeError` from `assert_native_reid_engaged`; an unexpected `yolo26n-cls.pt` download.

### Pitfall 2: Wrong Python / torch / TensorRT combo — nothing GPU runs at all
**What goes wrong:** The current `venv` is **py3.14 with `torch 2.12.0+cpu`** `[VERIFIED: venv probe]` — `torch.cuda.is_available()` is False, so EVERY gpu-marked test SKIPs and no engine can be built or run. Additionally, **TensorRT pip wheels ship for py3.8–3.13 only (no cp314)** `[CITED: NVIDIA install docs]`.
**Why it happens:** No cu12x torch wheel and no tensorrt wheel exist for cp314; this is already logged in project memory (`gpu-torch-cpu-only-py314.md`).
**How to avoid:** Stand up a **py3.12 venv** with a CUDA-enabled torch and `tensorrt`. Confirm `torch.cuda.is_available()` and `tensorrt.__version__` BEFORE any export. The system has CUDA toolkit 13.1 and driver 596.36 with an RTX 4000 Ada `[VERIFIED: nvidia-smi/nvcc]`; the pip `tensorrt`/`torch` wheels bundle their own CUDA runtime, so the deploy choice is the *wheel's* CUDA (cu12x), not the system toolkit — but confirm driver ≥ the wheel's minimum on the rig.
**Warning signs:** `gpu eval skipped: torch.cuda.is_available() is False` in pytest output; `pip install tensorrt` resolving no wheel on py3.14.

### Pitfall 3: Engine built on the wrong GPU / not cached → slow or broken at runtime
**What goes wrong:** A TensorRT engine is tied to the GPU architecture + driver + TensorRT version it was built with; using it elsewhere fails or silently rebuilds. Building inside the loop adds minutes of latency.
**Why it happens:** TensorRT specializes kernels for the target SM; the artifact is not portable.
**How to avoid:** Build ONCE on the deploy RTX 4000 Ada via `tools/build_engine.py`; cache `yolo26s.engine` on disk (gitignored); load it read-only at runtime; Pattern 3 fallback handles an incompatible/missing engine.
**Warning signs:** Long first-tick stalls; TensorRT "deserialization" / version-mismatch warnings; engine load raising.

### Pitfall 4: `dynamic=False, batch=4` engine cannot run a single frame (or N≠4)
**What goes wrong:** A static `batch=4` engine expects exactly 4 images per forward; feeding 1 (a degraded single-camera scenario) or 3 (a dead feed) errors.
**Why it happens:** Static-batch engines fix the batch dimension at build time.
**How to avoid:** Either always pad the batch to 4 (feed a blank frame for a dead camera — the loop already coasts blank frames to "no detection"), or build with `dynamic=True` (accepts 1..batch at a small perf cost). Given the degradation ladder may reduce cameras, **padding-to-4 or `dynamic=True` is required** — decide in the plan.
**Warning signs:** Shape-mismatch errors when a camera feed drops and the batch shrinks.

### Pitfall 5: Measuring on battery / cold engine → misleading p95
**What goes wrong:** Latency inflated by CPU/GPU throttling on battery, or the first few ticks include engine/model spin-up.
**Why it happens:** Project memory `dev-box-perf-on-ac.md` — battery throttles hard. The harness already warms up 20 ticks (`test_latency.py:184`) before measuring.
**How to avoid:** Run the gpu latency test **on AC power**, keep the existing warmup, measure over the sustained 100-tick window already in the harness.
**Warning signs:** p95 varying wildly between runs; first-tick outliers dominating.

## Code Examples

### Export the engine (the one-time build CLI)
```python
# Source: https://docs.ultralytics.com/integrations/tensorrt  [CITED]
# tools/build_engine.py — run ONCE on the deploy GPU (py3.12 + cu12x torch + tensorrt).
from ultralytics import YOLO

def build(weights="yolo26s.pt", imgsz=640, batch=4):
    YOLO(weights).export(
        format="engine", half=True, batch=batch, imgsz=imgsz,
        device=0, end2end=False,  # static batch; add dynamic=True if cam count varies
    )
    # → yolo26s.engine written beside the weights.
```

### Re-run the latency gate after each change (the phase's pass/fail)
```bash
# The 4-cam canonical config + warmup + 100-tick window already live in the harness.
# On the py3.12 GPU venv, on AC power:
pytest tests/test_latency.py -m gpu -x
# test_loop_latency_p95_under_budget asserts total p95 < 150ms (test_latency.py:188).
```

### Native-ReID engine-awareness (the reid_check extension shape)
```python
# Extend assert_native_reid_engaged to not RAISE on a structurally-engine-backed model. [ASSUMED]
# An engine cannot expose the in-graph Detect head, so native feats are impossible BY DESIGN —
# treat that as a logged downgrade (cls-ReID fallback accepted) rather than a startup crash,
# IFF the plan chooses Option (a) in Pitfall 1.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Eager FP32 `.pt` inference (Phase 4/5 baseline) | TensorRT FP16 `.engine` for prod | This phase | The documented prod path; eager FP32 is explicitly the slow path (231–247ms) |
| Serial per-camera `model.track()` | Batched detect + per-camera tracker update | This phase | Collapses N serial forwards into 1; the second lever |
| NMS-in-postprocess Detect head | YOLO26 NMS-free `end2end=True` head | YOLO26, Sep 2025 | Faster/cleaner export — but Segugio must use `end2end=False` to keep its tracking/ReID contract |

**Deprecated/outdated:**
- `yolo26n` as the latency lever — UAT-disproven on this GPU; do not pursue rung 1 of `_DEGRADATION_LADDER`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact batched `predict()` → per-camera `tracker.update()` surface (Pattern 2) works as sketched in 8.4.62 | Architecture Patterns | If the public surface differs, Track B needs a different adapter (e.g., driving `mode="stream"`); detection-only batching still holds, only the wiring changes |
| A2 | Accepting the `yolo26n-cls.pt` cls-ReID fallback on the engine path yields acceptable single-dog tracking | Pitfall 1, Open Q1 | If cls-ReID degrades competitor-lock continuity, Option (b) (eager tracking + engine detection) is required |
| A3 | The pip `tensorrt` 10.x cu12x wheel runs against driver 596.36 / RTX 4000 Ada | Standard Stack, Pitfall 2 | If the driver is too old for the wheel's CUDA, must pick an older TensorRT or update the driver |
| A4 | Padding a dead camera's slot with a blank frame keeps a static `batch=4` engine valid (the loop already coasts blanks) | Pitfall 4 | If padding misbehaves, `dynamic=True` is the fallback (small perf cost) |
| A5 | FP16 (TensorRT) does not materially hurt small/distant-dog recall vs FP32 | Standard Stack | If recall drops on the hard slices (Phase 4 already flagged distant=0.04), may need to keep FP32 detection or accept the tradeoff — measure on the curated clips |

## Open Questions

1. **ReID story for the engine path (the blocking decision).**
   - What we know: a `.engine` structurally cannot use native-feature ReID; `assert_native_reid_engaged` would raise (`[VERIFIED: track.py:45-59]`).
   - What's unclear: whether to (a) accept the cheap `yolo26n-cls.pt` ReID fallback on the engine and relax the gate to a warning, or (b) keep tracking on an eager `.pt` and engine-accelerate only the detection forward.
   - Recommendation: **plan Track A around Option (a)** (simplest, likely sufficient for one subject) but keep Option (b) as a documented fallback if competitor-lock continuity regresses on the curated multi-dog clips. This is a `checkpoint:human-verify` candidate.

2. **Is FP16 + batching ALONE (eager, no engine) already under 150ms?**
   - What we know: the loop is inference-bound; FP16 roughly halves compute, batching collapses 4 forwards into 1.
   - What's unclear: whether the cheaper eager-FP16 + batched path clears 150ms without the engine's complexity (and WITHOUT the ReID conflict — an eager FP16 model keeps native ReID).
   - Recommendation: **measure eager `half=True` + batched detect FIRST** as a cheap rung; it may meet the budget AND preserve native ReID, sidestepping Pitfall 1 entirely. Only build the engine if that misses.

3. **Static `batch=4` vs `dynamic=True` for the engine.**
   - What we know: degradation may reduce active cameras; a dead feed shrinks the batch.
   - Recommendation: pad-to-4 with blank frames (loop already coasts blanks) OR `dynamic=True`. Decide based on whether reduced-camera operation must run on the engine.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| NVIDIA GPU (CUDA) | All GPU inference | ✓ | RTX 4000 Ada, driver 596.36 `[VERIFIED: nvidia-smi]` | — |
| CUDA toolkit (system) | informational (wheels bundle their own) | ✓ | 13.1 `[VERIFIED: nvcc]` | wheel-bundled CUDA used at runtime |
| Python 3.12 | cu12x torch + tensorrt wheels | ✗ (only py3.14 present) | — | **none — must create a py3.12 venv** (no cp314 torch-CUDA or tensorrt wheels) |
| CUDA-enabled `torch` | any GPU path + export | ✗ (venv is `2.12.0+cpu`) | — | **none — must install cu12x torch in the py3.12 venv** |
| `tensorrt` | engine export/load (Track A) | ✗ (not installed) | — | **Track A blocked until installed**; Track B (eager FP16 + batching) can proceed without it |
| `ultralytics` 8.4.62 | everything | ✓ (in py3.14 venv; reinstall in py3.12) | 8.4.62 `[VERIFIED]` | — |

**Missing dependencies with no fallback:**
- **py3.12 venv + cu12x torch** — hard prerequisite for ANY GPU work this phase (and already a known blocker from Phase 5 UAT).

**Missing dependencies with fallback:**
- **`tensorrt`** — only Track A needs it; Track B (eager FP16 + batched detect) is a viable, ReID-preserving path that can be measured first.

## Validation Architecture

> `workflow.nyquist_validation` is not explicitly false in config → section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 `[VERIFIED: requirements.txt]` |
| Config file | `pyproject.toml` (markers `gpu`/`ndi`/`obs` registered there; skip hook in `tests/conftest.py`) |
| Quick run command | `pytest tests/test_latency.py -x` (mock-timed, headless — no GPU) |
| Full suite command | `pytest -q` (headless 314+ tests) |
| GPU gate command | `pytest tests/test_latency.py -m gpu -x` (py3.12 GPU venv, on AC) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RBT-05 | 4-cam decision loop total p95 < 150ms | gpu integration | `pytest tests/test_latency.py::test_loop_latency_p95_under_budget -m gpu -x` | ✅ (`test_latency.py:142`) |
| RBT-05 | wiring overhead stays sub-budget (regression) | unit (headless) | `pytest tests/test_latency.py::test_mock_timed_wiring_overhead_p95_under_bound -x` | ✅ |
| RBT-05 | per-stage attribution intact after changes | unit (headless) | `pytest tests/test_latency.py::test_mock_timed_fixed_inference_cost_is_attributed_to_yolo -x` | ✅ |
| TRK-02 | native-ReID gate behavior on engine vs eager (no silent disable) | gpu / unit | NEW — engine-aware `assert_native_reid_engaged` test | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_latency.py -x` (headless mock-timed — fast, proves no wiring regression).
- **Per wave merge:** `pytest -q` (full headless suite — no GPU needed for the 314 logic tests).
- **Phase gate:** `pytest tests/test_latency.py -m gpu -x` GREEN on the py3.12 GPU venv (RTX 4000 Ada, on AC) with measured p95 < 150ms.

### Wave 0 Gaps
- [ ] **py3.12 GPU venv** with cu12x torch (+ `tensorrt` for Track A) — without it every gpu test SKIPs and nothing is measurable. This is the gating Wave-0 setup task.
- [ ] Engine-aware variant of `assert_native_reid_engaged` (warn-not-raise when engine-backed) + its unit test — needed before Track A can run end to end.
- [ ] (Track B) a headless unit test for the batched-detect → per-camera-`update()` adapter using fake detection arrays (no GPU), proving per-camera state isolation (#13107 regression guard).

## Security Domain

> `security_enforcement` is not configured false. This is a local GPU/inference performance phase with no new external input surface (no new network endpoints, no new auth, no user-supplied data — the model weights/engine come from the locked config path and the trusted Ultralytics asset cache).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no new auth surface) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | minimal | The `.engine`/`.pt` path is config-validated (`ModelConfig.path` is a `pathlib.Path`, no shell interpolation — existing path-injection guard, `config/models.py:91`) |
| V6 Cryptography | no | — (never hand-rolled here) |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted model/engine artifact loaded | Tampering / Elevation | Build the engine yourself on the rig from the trusted `.pt`; gitignore + never download a `.engine` from an untrusted source |
| Engine build/load failure crashes the live director | Denial of Service | Pattern 3 graceful fallback to eager FP32 (RBT-04 "nessun crash") — the dominant robustness concern for this phase |

## Sources

### Primary (HIGH confidence)
- `ultralytics==8.4.62` installed source — `trackers/track.py:45-59` (native-ReID hook condition), `trackers/bot_sort.py:186-192` (encoder lambda vs `ReID`), `nn/autobackend.py:87,146` (engine → `AutoBackend`/`TensorRTBackend`), `models/yolo/detect/predict.py:53-78` (`_feats` → `r.feats`) — the engine↔ReID incompatibility is verified against shipped code.
- `tests/test_latency.py`, `src/segugio/orchestrator/loop.py`, `src/segugio/tracking/detector.py`, `src/segugio/tracking/reid_check.py`, `src/segugio/config/models.py`, `tests/conftest.py`, `tests/conftest_tracking.py`, `trackers/botsort_dog.yaml` — the concrete files the plan modifies.
- `nvidia-smi` / `nvcc` / venv torch probe — RTX 4000 Ada, driver 596.36, CUDA 13.1, py3.14 `torch 2.12.0+cpu`.

### Secondary (MEDIUM confidence)
- https://docs.ultralytics.com/integrations/tensorrt — `model.export(format="engine", half=True, batch=, imgsz=, device=, dynamic=)` and `YOLO("*.engine")` load.
- https://docs.ultralytics.com/modes/export — full export argument semantics (`half`, `int8`, `dynamic`, `simplify`, `workspace`, `batch`, `nms`).
- https://docs.ultralytics.com/guides/end2end-detection — `end2end` output shapes; FP16+end2end FP32-output caveat (issue #23645).
- `pip index versions tensorrt` — `tensorrt` 10.x latest on PyPI; NVIDIA install docs — wheels py3.8–3.13 only (no cp314).

### Tertiary (LOW confidence)
- WebSearch on multi-stream tracking / CUDA-stream parallelism (Ultralytics Academy, issues #13107/#19288/#14953) — corroborates "one tracker per stream; batch detection, not tracking"; exact batched-`update()` surface to be confirmed on the rig.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — ultralytics/torch already locked and verified in-repo; tensorrt cited from official docs and confirmed on PyPI.
- Architecture / engine↔ReID conflict: HIGH — verified against the installed 8.4.62 source, not just docs.
- Env prerequisites: HIGH on the blocker (py3.14 CPU-only torch verified); MEDIUM on the exact cu12x/tensorrt wheel that runs against driver 596.36 (confirm on rig).
- Batched-detect API surface (Pattern 2): MEDIUM — the principle is verified (#13107 / stream-mode builds N trackers), the exact public call to confirm on the rig.

**Research date:** 2026-06-13
**Valid until:** 2026-07-13 (Ultralytics releases roll fast; re-confirm the export args + tensorrt wheel matrix if the phase starts after this date)
