# Phase 4: YOLO + Per-Camera Tracking on Recorded Clips - Research

**Researched:** 2026-06-10
**Domain:** Ultralytics YOLO26 detect + per-camera BoT-SORT (native-feature ReID) over recorded clips run as pseudo-cameras; robust competitor-lock + inter-frame plausibility gate feeding the frozen `DetectionSignal` contract.
**Confidence:** HIGH (the load-bearing API facts — `model.track` signature, native-ReID engagement logic, the YOLO26 `end2end=True` default that breaks it, `Results.boxes.xywhn/id/conf`, the installed `8.4.62` source path — are Context7-verified against the shipped tracker code + official docs and cross-checked against the installed environment. Competitor-lock / plausibility-gate algorithm design is MEDIUM — principle is locked by CONTEXT, constants are config seeds.)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 — Pseudo-cameras = spatial crops of the wide shot.** The committed corpus is single-camera disc-dog only (`gara_full.mp4`, 1080p**50**, cut into ~30s condition slices). Build "N cameras" by cropping the 1080p wide clip into **overlapping windows** (e.g. left / center / right) → genuinely simultaneous different framings of the *same dog at the same instant*. Gives real per-camera pixel isolation, a realistic multi-camera interface for Phase 5, and — for free — **frame-exit/re-entry** (dog leaves a crop and reappears), the exact case `track_buffer: 60` + native ReID exist to survive. Some crops naturally won't contain the dog (a realistic "this camera doesn't see it" case). No real parallax — accepted.
- **D-02 — Validate disc-dog now; flag the gaps; no fake footage.** Run TRK-01..05 fully on the available disc-dog slices (`handler_close_01` + `crowd_distractor_01` for handler/bystander competitor-lock; crops for re-entry; `sprint_blur` for blur; `distant`/`dusk_distant` for small/low-light recall). **Explicitly log as UNVERIFIED:** agility-tunnel-occlusion and a clean two-similar-dogs-crossing swap — the corpus has neither. The code paths still exist; they are simply not clip-proven in Phase 4. Do **not** pull random CC0 stock to paper over the checklist.
- **D-03 — Competitor-lock signals = zone-gate AND motion-energy.** A candidate dog track must be (a) inside the field/course zones (config normalized rects) **and** (b) have the most cumulative motion over a short window. Zone excludes ringside/adjacent-ring/crowd dogs; motion excludes a standing/waiting dog. Detector filters to **dog class only**, so persons/handlers are never candidates — competitor-lock only disambiguates *among dog tracks*. **Autonomous** — no manual run-start signal on clips (that is SCR-03, Phase 5); acquisition runs on zone+motion alone.
- **D-04 — Sticky continuity; re-acquire only on loss.** Once locked to a track ID, **keep it while alive** — prefer continuity over per-frame score. Re-run zone+motion selection **only** when the locked track is genuinely lost (`track_buffer: 60` expired) or the plausibility gate flags a swap. Prevents ping-ponging the lock between dogs mid-run. Do **not** re-pick the best candidate every tick.
- **D-05 — Per-camera, independent lock.** Each camera independently locks its own in-field/most-active dog. A *global* cross-camera "this is THE dog" identity would require cross-camera ReID, deferred as "heavy ReID." Cross-camera agreement is **emergent**, not enforced.
- **D-06 — Hold the locked track, mark "uncertain" → coast.** When the locked track teleports or size-jumps (likely ID swap), **reject the suspect box** — do not trust it. Mark the subject `uncertain` and emit the **coast path** (no `DetectionSignal` this tick → the scorer's existing FRM-05 coast/TTL holds the last EMA; the FSM does not cut on a suspect track). Re-acquire (zone+motion) only after a genuine loss. The gate's thresholds (`max_displacement_per_tick`, `max_size_ratio`) are **config seeds**.
- **D-07 — TRK-05 is a NEW inter-frame gate, distinct from the Phase-2 detection guard.** Phase 2 already ships an *intra-frame* per-detection plausibility guard (`plausibility_ok`: conf-floor / min-area / aspect). TRK-05 is the *inter-frame track-continuity* gate ("is this the same dog as last frame"). Different concepts — do not conflate. Add the new seeds additively to config (same pattern as `ScorerParams`); exact sub-model placement is the planner's call.
- **D-08 — Both debug-overlay video AND logged metrics.** Render boxes / track IDs / locked-subject highlight / zone overlays over each clip to **eyeball** (an auto-director's correctness is ultimately visual), **plus** log per-clip metrics as a regression net: locked-subject **ID-switch count**, **% frames lock-held**, **coast/uncertain counts**, and a signal dump.
- **D-09 — Split test architecture: pure-logic deterministic + GPU-gated integration.** The **competitor-lock and plausibility-gate LOGIC** is tested on **synthetic track/detection inputs** — deterministic, CPU-only, reusing `synth` + `conftest`, exactly like the Phase-2 scorer and Phase-3 FSM. The **real YOLO-on-clips** path is a **separate GPU-gated eval run** (`@pytest.mark.gpu`, skipped when no CUDA or no weights). Keeps the "brain" unit-testable on any box; isolates heavy I/O at the edge. YOLO inference is GPU/weights-dependent and **not** expected to run in normal CPU CI.

### Claude's Discretion

- **Module layout** — likely a new `src/segugio/tracking/` package (detector wrapper + per-camera tracker manager + competitor-lock/subject-selector + plausibility gate + a clip/crop frame source). Exact shape is the planner's call; honor the lazy-import boundary (no `torch`/`ultralytics`/`cv2` at the package top level so `import segugio.tracking` works CPU-only / heavy-deps-absent).
- **`botsort_dog.yaml` location** — must live where Ultralytics `check_yaml` finds it (a `trackers/` dir or an absolute path). Planner's call; override values already specified in STACK.md.
- **50fps vs ~30Hz tick** — footage is 1080p**50**; AI tick is ~30 Hz. Whether to stride/sample frames to ~30 fps or decode every frame is the planner's call; keep `tick` an injected frame index (no wall-clock).
- **Crop window geometry** — number of crops, overlap, aspect are the planner's call; map each crop to a `cam_id` and the per-camera config zones.
- **Motion-energy / zone-gate exact formulation** — cumulative-displacement window length, in-zone test (center-in-rect vs IoU), how the two combine into a single "competitor score" are the planner's call. Principle locked (zone AND motion, sticky); constants are config seeds.
- **`model.names` class resolution** — map `dog` by **name** → index at startup; warn/fail if the configured `class_index` disagrees with the resolved index (custom mono-class model ≈ 0, not COCO 16).

### Deferred Ideas (OUT OF SCOPE)

- **Agility-tunnel-occlusion + two-similar-dogs-crossing validation** — corpus has neither; code paths flagged UNVERIFIED, revisited when real footage is provided (D-02).
- **Detection-in-occlusion-zone → FSM `occlusion_hold` wiring** — Phase 5.
- **Cross-camera ReID / global subject identity** — "heavy ReID," deferred (D-05).
- **Disc/frisbee detection** (`classes=[16,29]`) — v2.
- **Pose model** (`yolo26s-pose`) — v2.
- **Custom / fine-tuned dog model** — only if eval shows COCO `dog` misses too often; measure now, decide later.
- **ByteTrack latency fallback / TensorRT FP16 export** — only if the AI loop blows budget; export belongs to the hardware milestone.
- **Numeric threshold calibration** (`max_displacement_per_tick`, `max_size_ratio`, motion-window length, crop geometry) — config seeds, tuned opportunistically on clips, NOT a Phase-4 gate.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **TRK-01** | YOLO pre-trained on CUDA, **one tracker per camera** (`persist=True`), run on recorded video as pseudo-cameras | §"TRK-01: Per-Camera Tracking" — exact `model.track(...)` signature for 8.4.62, one-`YOLO()`-`.track()`-call-per-`cam_id` pattern, `persist=True` + per-instance state, `model.names` name→index resolution reconciled with `class_index`, the crop→cam_id pseudo-camera builder (D-01) |
| **TRK-02** | BoT-SORT **native ReID** (`with_reid:True, model:auto`) + extended `track_buffer`; startup **verifies** native ReID is active | §"TRK-02: Native-ReID Engagement Verification" — the **load-bearing finding**: `yolo26s.pt` defaults to `end2end=True`, which **fails** the native-ReID hook condition → silent `yolo26n-cls.pt` download. Fix = pass `end2end=False` to `.track()`. Runnable engagement check inspecting `BOTSORT.encoder` (lambda vs `ReID`) + `predictor._hook`. `botsort_dog.yaml` placement for `check_yaml`. |
| **TRK-03** | Per-detection normalized signals (cx/cy, w/h, conf, track_id) filtered to dog class | §"TRK-03: Normalized Signal Extraction" — `Results.boxes.xywhn` / `.id` / `.conf` row → `DetectionSignal` unchanged; per-camera per-tick → one locked `DetectionSignal \| None` |
| **TRK-04** | **Competitor-lock** — select the in-competition dog robustly to handler/bystander/persons | §"TRK-04: Competitor-Lock" — zone-gate AND motion-energy (D-03), sticky continuity (D-04), per-camera independent (D-05); concrete data structures + deterministic algorithm testable on synthetic tracks |
| **TRK-05** | Inter-frame plausibility gate (teleport / size-jump) rejects implausible track switches | §"TRK-05: Inter-Frame Plausibility Gate" — distinct from Phase-2 `plausibility_ok` (D-07); reject suspect box → uncertain → coast (None) → scorer FRM-05 holds last EMA; new config seeds |
</phase_requirements>

## Summary

This phase is the dominant project risk made software-provable. The existing project research (`STACK.md`, `PITFALLS.md`, `ARCHITECTURE.md`) already settled the **what**: YOLO26s detect + COCO `dog`, BoT-SORT with `with_reid:True`/`model:auto` for zero-extra-weight native ReID, `track_buffer:60`, one tracker per camera (#13107), zone-gate + motion-energy competitor-lock, an inter-frame plausibility gate. This document fills the **how** for the *installed* stack: the exact `model.track()` call in `ultralytics 8.4.62`, the precise runnable native-ReID engagement check, the `Results.boxes` → `DetectionSignal` mapping, and the test architecture.

The single most important finding — and a correction to a latent assumption in `STACK.md` — is **load-bearing for TRK-02**: in `ultralytics 8.4.x`, native-feature ReID engages **only when the Detect head is *not* end2end**, but `yolo26s.pt` runs with **`end2end=True` by default** in both `predict()` and `track()`. With the default call, the hook condition in `on_predict_start` is FALSE, so Ultralytics **silently swaps in `yolo26n-cls.pt`** as the ReID encoder — downloading a fallback model and discarding the "zero-extra-weights ReID" premise. **The fix is to pass `end2end=False` to `model.track()`**, which activates the standard one-to-many Detect head, satisfies the hook condition, and engages true native-feature ReID. Phase 4 must do this AND assert it at startup by inspecting the live tracker's `encoder` (a lambda when native, a `ReID` instance when fallen back) and the predictor's registered `_hook`. This converts STACK.md's "verify native ReID actually engages, else it silently downloads a fallback" warning from a vague caution into a concrete, testable gate with a known root cause and a known fix.

The competitor-lock and plausibility-gate are pure logic and must be designed exactly like the Phase-2 scorer / Phase-3 FSM: frozen-input, deterministic, CPU-only, unit-tested on `synth.detection_stream`. The heavy YOLO-on-clips path is GPU-gated (`@pytest.mark.gpu`) and will SKIP wherever `torch`/`ultralytics` (the `[heavy]` optional group) are not installed — including this `.venv` as configured and normal CI — exactly as D-09 intends. (A CUDA GPU **is** physically present on this WSL box — `nvidia-smi`: driver 596.36 / CUDA 13.2 — so installing `.[heavy]` + a CUDA torch build makes the GPU eval runnable locally.) `cv2 4.13.0` *is* installed in `.venv`, so the crop/frame-source plumbing can be exercised CPU-only, but it must still live behind the lazy-import boundary so `import segugio.tracking` succeeds with `cv2` absent too.

**Primary recommendation:** Build `segugio.tracking` as a lazy-import package whose pure brain (frame-source geometry, competitor-lock, plausibility gate, signal mapping) is fully unit-testable CPU-only on synthetic tracks, and whose only heavy edge is a thin detector/tracker wrapper that (1) calls `model.track(frame, persist=True, classes=[dog_idx], tracker="botsort_dog.yaml", end2end=False, verbose=False)` once per `cam_id`, (2) **asserts native-ReID engagement at startup with `end2end=False`** before any clip is processed, and (3) maps `Results.boxes` rows to the frozen `DetectionSignal` unchanged.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Decode clip frames + spatial crops → per-camera frames (D-01) | Heavy edge (`cv2`) | — | `cv2.VideoCapture` + numpy slicing; lazy-imported; the only I/O in Phase 4 |
| YOLO inference + BoT-SORT tracking per camera (TRK-01) | Heavy edge (`ultralytics`/`torch`/CUDA) | — | One `YOLO().track(persist=True)` per `cam_id`; GPU-bound; GPU-gated tests |
| Native-ReID engagement verification (TRK-02) | Heavy edge (startup, once) | — | Inspects the live `BOTSORT` tracker object after first `.track()` call; needs torch |
| `Results.boxes` → `DetectionSignal` mapping (TRK-03) | Pure logic | Heavy edge (reads `Results`) | The *mapping* is pure; the `Results` object comes from the edge. Extract numpy arrays at the edge, map in pure code |
| Competitor-lock: zone-gate + motion-energy + sticky continuity (TRK-04) | **Pure logic** | — | Operates on `DetectionSignal` lists + `Camera.zones`; zero heavy deps; CPU-only deterministic tests (D-09) |
| Inter-frame plausibility gate: teleport / size-jump (TRK-05) | **Pure logic** | — | Operates on consecutive locked-track boxes; zero heavy deps; CPU-only deterministic tests (D-09) |
| Per-camera locked-subject `DetectionSignal \| None` stream (output) | Pure logic | — | Feeds the Phase-2 `MultiCamScorer.update(dets_by_cam, tick)` shape (wired in Phase 5) |
| Debug-overlay video render + per-clip metrics (D-08) | Heavy edge (`cv2` draw + `VideoWriter`) | Pure logic (metric counters) | Metric counting is pure; rendering is `cv2` I/O at the edge |

**The pure/heavy split is the architecture.** Everything that decides *which dog* and *is this box trustworthy* is pure and CPU-testable; only frame decode, inference, and overlay render touch heavy deps. This mirrors Phase 2 (`framing` pure) and Phase 3 (`decision` pure).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ultralytics` | **8.4.62** (pinned in `pyproject.toml [heavy]`; PyPI latest 8.4.63) `[VERIFIED: PyPI registry — pip index versions]` | `YOLO(...).track(...)` detect+BoT-SORT; loads `yolo26s.pt` weights | Locked stack; the `YOLO()` API + integrated BoT-SORT tracker is the project-pinned detector. 8.4.62 knows YOLO26 and ships the native-ReID `on_predict_start` logic this phase depends on `[VERIFIED: Context7 /websites/ultralytics — bot_sort + track source]` |
| `torch` | (transitive via `ultralytics`; CUDA build installed on the deploy box only) `[CITED: pyproject.toml comment "CUDA build is Phase 4"]` | GPU inference backend | Locked; the `end2end` attribute lives on the torch `Detect` module the engagement check inspects |
| `opencv-python` | **4.13.0.92** (pinned `[heavy]`; **installed in `.venv` as cv2 4.13.0**) `[VERIFIED: .venv import + PyPI]` | Clip decode (`VideoCapture`), spatial crops (numpy slice), overlay render (`VideoWriter` + draw) | Locked stack; the only frame-I/O dep. Already importable CPU-only on this box |
| `numpy` | **2.4.6** (installed) `[VERIFIED: .venv import]` | Box-array math, crop slicing, normalization, motion-energy | Already a light dependency; the pure logic uses it like Phase 2 |
| `loguru` | **0.7.3** (installed) `[VERIFIED: .venv import]` | Startup ReID-engagement log line, per-clip metric dump | Locked stack; already used by `segugio.fixtures` |

> **No NEW packages are introduced by Phase 4.** Every dependency above is already declared in `pyproject.toml` (light deps installed; `ultralytics`/`opencv-python` in the `[heavy]` extra). The Package Legitimacy Audit below covers them anyway since this phase is the one that *exercises* the heavy group.

### Weights (auto-download, not pip packages)

| Weight | Trigger | Purpose | Notes |
|--------|---------|---------|-------|
| `yolo26s.pt` | First `YOLO("yolo26s.pt")` | The dog detector | Auto-downloads from Ultralytics assets on first use; path is `ModelConfig.path` (configurable, CFG-04) `[CITED: STACK.md + config.example.yaml]` |
| `yolo26n-cls.pt` | **UNWANTED** — auto-downloads *only if* native ReID falls back (end2end head) | Fallback ReID encoder | **This is the silent download TRK-02 must prevent.** Its presence/absence is the engagement signal `[VERIFIED: Context7 on_predict_start — `cfg.model = "yolo26n-cls.pt"`]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BoT-SORT native ReID (`model:auto`, `end2end=False`) | ByteTrack (`bytetrack.yaml`) | Only if AI loop blows budget AND you accept ID churn on re-entry; defer (STACK.md). Per-camera best-track selection papers over churn |
| `yolo26s.pt` | `yolo26n.pt` | Config swap if GPU can't hold `s` in budget; no code change |
| `end2end=False` (one-to-many head, enables native ReID) | `end2end=True` default (NMS-free) | end2end gives lower tail latency BUT **disables native ReID** (forces `yolo26n-cls.pt` fallback). For v1, ID persistence > marginal latency — use `end2end=False`. Revisit at the hardware/TensorRT milestone where the export path is re-verified |

**Installation:** No new install. The deploy/dev box needs the heavy extra: `pip install -e ".[heavy]"` (installs `ultralytics==8.4.62`, `opencv-python==4.13.0.92`, etc.). On this WSL box `torch`+`ultralytics` are NOT installed in `.venv` (the `[heavy]` group) → GPU-gated tests SKIP until the extra is installed (intended, D-09). **A CUDA GPU IS present** here (`nvidia-smi`: driver 596.36 / CUDA 13.2), so once `.[heavy]` + a CUDA torch build are installed, the GPU eval can run locally.

**Version verification (performed this session):**
- `pip index versions ultralytics` → 8.4.63 latest; **8.4.62 confirmed present** `[VERIFIED: PyPI]`
- `pip index versions opencv-python` → **4.13.0.92 confirmed** `[VERIFIED: PyPI]`
- `.venv/bin/python -c "import cv2,numpy,loguru"` → cv2 **4.13.0**, numpy **2.4.6**, loguru **0.7.3** `[VERIFIED: .venv]`
- `import ultralytics` / `import torch` in `.venv` → **ModuleNotFoundError** (heavy group not installed here) `[VERIFIED: .venv]`
- `nvidia-smi` → **GPU present** (NVIDIA driver 596.36 / CUDA 13.2 via WSL) `[VERIFIED: nvidia-smi]`. `torch.cuda.is_available()` could not be run (torch absent), but the hardware is there — installing `.[heavy]` + CUDA torch enables local GPU eval.
- `slopcheck install ultralytics opencv-python loguru` → **all 3 `[OK]`** on PyPI `[VERIFIED: slopcheck 0.6.1]`

> **STACK.md must-verify item ("confirm `YOLO("yolo26s.pt")` resolves in this version before committing"):** could **NOT** be executed in this session because `ultralytics`/`torch` are not installed in `.venv` (the GPU hardware itself **is** present). This is **carried forward as the first GPU-gated startup assertion** (see Open Questions Q1 and the Validation Architecture Wave-0 gap) and is a one-line `pip install -e ".[heavy]"` (+ CUDA torch) away from being runnable on this box. Not a blocker for *planning*.

## Package Legitimacy Audit

> Phase 4 introduces no new packages; all are pre-pinned in `pyproject.toml`. slopcheck `0.6.1` ran cleanly against the PyPI registry for the heavy group this phase exercises (the subsequent pip install failed only on PEP-668 externally-managed-environment, which is irrelevant — the legitimacy scan completed and returned verdicts first).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `ultralytics` | PyPI | 8+ yrs (8.x line mature) | ~tens of M/mo | github.com/ultralytics/ultralytics | **[OK]** | Approved (pinned 8.4.62) |
| `opencv-python` | PyPI | 10+ yrs | ~tens of M/mo | github.com/opencv/opencv-python | **[OK]** | Approved (pinned 4.13.0.92) |
| `loguru` | PyPI | 7+ yrs | ~tens of M/mo | github.com/Delgan/loguru | **[OK]** | Approved (pinned 0.7.3) |
| `torch` | PyPI | mature | very high | github.com/pytorch/pytorch | (transitive — not scanned directly) | Approved (CUDA build, deploy box) |
| `numpy` | PyPI | mature | very high | github.com/numpy/numpy | (light dep, already installed) | Approved (pinned 2.4.6) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

**postinstall / supply-chain note:** all are well-known, high-reputation OSS with public source repos; no suspicious install scripts. `ultralytics` auto-downloads model *weights* at runtime from `github.com/ultralytics/assets` — this is expected behavior, not a package-install script. The TRK-02 engagement check exists precisely to detect the *one* unwanted runtime auto-download (`yolo26n-cls.pt`).

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────────┐
 recorded clip            │  segugio.tracking — HEAVY EDGE (lazy-import) │
 (gara_full slice,        │  ┌─────────────────────────────────────────┐│
  1080p50)                │  │ ClipFrameSource (cv2.VideoCapture)        ││
      │                   │  │   • decode frame @ injected tick          ││
      ▼                   │  │   • optional 50→~30 stride (D-01 detail)  ││
 cv2 decode ──────────────┼─▶│   • spatial crop → {cam_id: frame}  (D-01)││
                          │  └───────────────┬───────────────────────────┘│
                          │                  │ per cam_id, one frame        │
                          │                  ▼                              │
                          │  ┌─────────────────────────────────────────┐  │
                          │  │ PerCameraTracker  (ONE per cam_id)        │  │
                          │  │   YOLO(model.path).track(                 │  │
                          │  │     frame, persist=True,                  │  │
                          │  │     classes=[dog_idx],                    │  │
                          │  │     tracker="botsort_dog.yaml",           │  │
                          │  │     end2end=False,   ◀── ENABLES native   │  │
                          │  │     verbose=False)        ReID (TRK-02)   │  │
                          │  │   ── startup: assert_native_reid(...) ────┼──┼─▶ loguru "native ReID engaged"
                          │  └───────────────┬───────────────────────────┘  │   (or RAISE if fallback)
                          │                  │ Results (per cam, per tick)   │
                          └──────────────────┼───────────────────────────────┘
                                             │  extract numpy: xywhn, id, conf, cls
                                             ▼
       ┌───────────────────────────────────────────────────────────────────┐
       │  segugio.tracking — PURE LOGIC BRAIN  (CPU-only, deterministic)     │
       │                                                                     │
       │  Results row ──▶ candidate DetectionSignal(s)  (TRK-03, dog-filtered)│
       │                          │                                           │
       │                          ▼                                           │
       │   ┌──────────────────────────────────────────────────────────────┐ │
       │   │ CompetitorLock (per cam_id; D-05 independent)        (TRK-04)  │ │
       │   │   if no lock OR locked-track lost:                             │ │
       │   │       acquire = argmax over (zone_gate AND motion_energy)(D-03)│ │
       │   │   else: KEEP locked track_id while alive       (sticky, D-04)  │ │
       │   └──────────────────────────┬───────────────────────────────────┘ │
       │                              │ locked candidate this tick            │
       │                              ▼                                       │
       │   ┌──────────────────────────────────────────────────────────────┐ │
       │   │ PlausibilityGate (inter-frame, on the LOCKED track) (TRK-05)   │ │
       │   │   teleport? (Δcenter > max_displacement_per_tick) OR           │ │
       │   │   size-jump? (area ratio outside [1/r, r])  → REJECT (D-06)    │ │
       │   │   reject → uncertain → emit None (coast); genuine-loss→re-acq  │ │
       │   └──────────────────────────┬───────────────────────────────────┘ │
       └──────────────────────────────┼───────────────────────────────────────┘
                                      │  per cam_id, per tick
                                      ▼
                    DetectionSignal | None   (frozen, normalized [0,1], injected tick)
                                      │
                       ┌──────────────┴───────────────┐
                       ▼                              ▼
        Phase-2 MultiCamScorer.update(       D-08 offline eval:
          dets_by_cam, tick)                  overlay video (cv2 draw) +
        (consumer SHAPE; wired Phase 5)        metrics (ID-switch, %lock-held,
                                               coast/uncertain counts)
```

**Trace the primary use case:** a 1080p50 clip frame is decoded, cropped into L/C/R pseudo-cameras (D-01); each crop goes to its *own* persistent `YOLO().track()` instance with `end2end=False` (native ReID, verified once at startup); dog-class `Results.boxes` rows become candidate `DetectionSignal`s; the per-camera `CompetitorLock` picks/keeps the in-field most-active dog (zone AND motion, sticky); the `PlausibilityGate` rejects teleport/size-jump on the locked track → uncertain → `None`; the per-camera `DetectionSignal | None` stream feeds the existing scorer shape and the offline overlay+metrics.

### Recommended Project Structure (Claude's Discretion — planner finalizes)

```
src/segugio/tracking/
├── __init__.py          # lazy-import surface: NO torch/ultralytics/cv2 at top level
├── frame_source.py      # ClipFrameSource: cv2 decode + spatial crops (D-01); lazy cv2
├── detector.py          # PerCameraTracker: YOLO().track wrapper; lazy ultralytics/torch
├── reid_check.py        # assert_native_reid(): the TRK-02 engagement gate
├── signals_map.py       # PURE: Results-row arrays -> DetectionSignal (TRK-03)
├── competitor_lock.py   # PURE: zone-gate + motion-energy + sticky continuity (TRK-04)
├── plausibility.py      # PURE: inter-frame teleport/size-jump gate (TRK-05)
├── params.py            # NEW pydantic sub-model: TrackingParams seeds (D-07)
└── eval.py              # D-08: overlay render (lazy cv2) + pure metric counters

trackers/                # botsort_dog.yaml lives here (or pass an absolute path)
└── botsort_dog.yaml     # the BoT-SORT override (STACK.md values + end2end note)

tests/
├── test_tracking_import_smoke.py   # import segugio.tracking with heavy deps absent
├── test_competitor_lock.py         # PURE, CPU-only (synth tracks)
├── test_plausibility_gate.py       # PURE, CPU-only (synth tracks)
├── test_signals_map.py             # PURE (fake Results-like arrays)
├── test_frame_source.py            # cv2 present here -> crop geometry (CPU-only ok)
└── test_yolo_clips_eval.py         # @pytest.mark.gpu — SKIP without CUDA/weights
```

### Pattern 1: One `model.track(persist=True)` instance per `cam_id` — NEVER a frame list
**What:** Construct one `YOLO(model.path)` *or* keep one `model` but maintain a separate persistent tracker per camera by calling `.track()` with a stable per-camera generator/stream; the safest and clearest is **one `YOLO` object per `cam_id`** so each owns its own `predictor.trackers` state.
**When to use:** Always, for multi-camera tracking. Passing a *list of frames* to one `.track()` builds ONE tracker and mixes IDs across cameras (Ultralytics #13107) and breaks per-camera native-ReID embeddings.
**Why:** `persist=True` makes `on_predict_start` early-return (`if hasattr(predictor,"trackers") and persist: return`) so the per-camera tracker state survives across ticks `[VERIFIED: Context7 on_predict_start]`. Per-camera isolation is what makes ReID and `track_buffer:60` meaningful (STACK.md, PITFALLS Pitfall 2).
**Example:**
```python
# Source: Context7 /websites/ultralytics modes/track + bot_sort; STACK.md "What NOT to Use"
# ONE tracker per camera (heavy edge, lazy-imported inside the method):
from ultralytics import YOLO            # lazy — inside the function, never module top
class PerCameraTracker:
    def __init__(self, model_path, dog_idx, tracker_yaml):
        self.model = YOLO(str(model_path))     # own predictor.trackers state per cam
        self.dog_idx = dog_idx
        self.tracker_yaml = str(tracker_yaml)
    def track(self, frame):                    # frame = ONE numpy BGR crop for THIS cam
        results = self.model.track(
            frame,
            persist=True,                      # keep this cam's tracker state across ticks
            classes=[self.dog_idx],            # dog only (resolved by NAME at startup)
            tracker=self.tracker_yaml,         # botsort_dog.yaml (check_yaml-resolvable)
            end2end=False,                     # ◀ CRITICAL: enables native ReID (TRK-02)
            verbose=False,
        )
        return results[0]                      # one Results for the single frame
```

### Pattern 2: Resolve `dog` by NAME → index at startup; reconcile with configured `class_index`
**What:** Read `model.names` (an `{index: name}` dict) after load; find the index whose name == "dog"; compare to `ModelConfig.class_index` (default 16). Warn or fail if they disagree (custom mono-class model ≈ 0, NOT 16).
**When to use:** Once at startup, before any tracking. This is CFG-04 + the STACK.md "What NOT to Use" first row.
**Why:** Hardcoding 16 on a custom model silently filters out every detection (STACK.md). The config carries the *configured* value; Phase 4 *verifies* it against the loaded model.
**Example:**
```python
# Source: STACK.md + config.models.ModelConfig; model.names is {idx: name}
names = model.names                              # e.g. {0: 'person', 16: 'dog', ...}
dog_indices = [i for i, n in names.items() if n == "dog"]
if not dog_indices:
    raise ValueError(f"model has no 'dog' class; names={names}")
resolved = dog_indices[0]
if resolved != cfg.model.class_index:
    logger.warning("configured class_index={} but model.names resolves 'dog'={} — "
                   "using resolved index", cfg.model.class_index, resolved)
dog_idx = resolved                               # name-resolved index wins
```

### Pattern 3: Pure mapping `Results.boxes` row → frozen `DetectionSignal` (TRK-03)
**What:** At the heavy edge, extract numpy arrays from `Results.boxes` (`.xywhn`, `.id`, `.conf`, `.cls`); pass plain Python floats/ints into a PURE mapper that builds `DetectionSignal(tick, cam_id, cx, cy, w, h, conf, track_id)`. Already-normalized `xywhn` matches the frozen contract's [0,1] fields with no extra math.
**When to use:** Every tick, per camera, after `.track()`.
**Why:** `Results.boxes.xywhn` is `(cx, cy, w, h)` already normalized to [0,1] — the exact `DetectionSignal` spatial-field semantics (`signals.py` docstring: "all spatial fields normalized [0,1]"). `.id` is the BoT-SORT track id (None on the first frame before a track is confirmed). Keeping the *mapping* pure lets it be unit-tested with fabricated arrays (no GPU).
**Example:**
```python
# Source: Context7 Results.boxes (xywhn/id/conf); src/segugio/framing/signals.py contract
def signals_from_boxes(xywhn, ids, confs, tick, cam_id):   # PURE: numpy arrays in, list out
    out = []
    if ids is None:                          # no confirmed tracks this frame
        return out
    for (cx, cy, w, h), tid, conf in zip(xywhn, ids, confs):
        out.append(DetectionSignal(
            tick=int(tick), cam_id=cam_id,
            cx=float(cx), cy=float(cy), w=float(w), h=float(h),
            conf=float(conf), track_id=int(tid),
        ))
    return out
```
**Note:** the crop is the camera frame, so `xywhn` is normalized to the **crop**, not the source — which is exactly right: zones are per-camera image-normalized (ARCHITECTURE Option A), and `DetectionSignal` is resolution-independent by construction.

### Pattern 4: Per-camera lazy frame source with spatial crops (D-01 pseudo-cameras)
**What:** `ClipFrameSource(clip_path, crops, stride)` opens a `cv2.VideoCapture`, yields `(tick, {cam_id: crop_frame})` where each crop is a numpy slice of the decoded 1080p frame defined by a normalized rect per `cam_id`; `tick` is the injected frame index (no wall-clock).
**When to use:** The Phase-4 eval driver; a realistic per-camera interface Phase 5's NDI mock plugs into.
**Why:** Overlapping crops give simultaneous multi-framing of the same instant + free frame-exit/re-entry. The crop rect → `cam_id` mapping aligns with the per-camera config zones.
**Trade-off:** No parallax (accepted, D-01). 50→~30 striding is the planner's call; keep `tick` the *emitted* frame index so determinism holds.

### Anti-Patterns to Avoid
- **Passing a frame list to one `.track()` for multi-cam:** mixes IDs (#13107), breaks per-camera ReID. Use one tracker per `cam_id` (Pattern 1).
- **Calling `.track()` with the default `end2end=True`:** silently downloads `yolo26n-cls.pt` and the "native ReID" is a lie. Always `end2end=False` (TRK-02).
- **Trusting the tracker `track_id` as the subject identity:** the ID is *advisory* (PITFALLS Pitfall 2). The locked-subject identity is the competitor-lock's, enforced by the plausibility gate.
- **Re-picking the best candidate every tick:** ping-pongs the lock between dogs mid-run. Re-acquire ONLY on genuine loss or a plausibility-gate swap flag (D-04).
- **Re-using Phase-2 `plausibility_ok` as the TRK-05 gate:** that is the *intra-frame* "is this a plausible dog box at all" guard; TRK-05 is the *inter-frame* "is this the same dog as last frame" gate (D-07). Different inputs (single det vs. consecutive locked boxes), different purpose.
- **Hardcoding crop rects / motion-window / gate thresholds in code:** they are config seeds (D-07, Claude's Discretion). Add a `TrackingParams` sub-model the same way `ScorerParams` was added.
- **Importing torch/ultralytics/cv2 at `segugio.tracking` top level:** breaks the lazy-import boundary; `import segugio.tracking` must succeed with all three absent (smoke test).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-object tracking / ID assignment / re-ID across frames | A custom Kalman/IoU/appearance tracker | `model.track(..., tracker="botsort_dog.yaml")` BoT-SORT | BoT-SORT ships Kalman + IoU + GMC + native-feature ReID + two-pass association; reimplementing is the exact failure mode (occlusion, blur, re-entry) the project can't afford (STACK.md, PITFALLS) |
| Frame-exit/re-entry survival | A custom "remember the box for N frames" buffer | BoT-SORT `track_buffer: 60` | Already the tuned mechanism for the ~2s tunnel/off-frame gap (STACK.md) |
| Appearance re-ID embeddings | Loading/training a separate ReID net | `with_reid:True, model:auto` native features (`end2end=False`) | Zero extra weights; the detector's own Detect-input features are the embedding (Context7-verified lambda encoder). Heavy ReID is explicitly deferred |
| Coast-through-blur / hold-last-EMA / drop-to-lost | A new coast mechanism in `tracking` | Emit `None` → Phase-2 `CameraScorer` FRM-05 coast/TTL | The scorer ALREADY holds the last EMA on `None` (D-06). The plausibility gate's "uncertain → coast" is realized for free by emitting `None`; no new downstream logic |
| Box-area / centroid / normalized-coord math | Manual pixel→normalized conversion | `Results.boxes.xywhn` | Ultralytics already returns normalized `(cx,cy,w,h)`; matches the `DetectionSignal` contract exactly |
| Per-camera tracker-config file discovery | A custom path resolver | Ultralytics `check_yaml` (place `botsort_dog.yaml` in a `trackers/` dir or pass an absolute path) | `on_predict_start` calls `check_yaml(predictor.args.tracker)` — let it resolve (Context7) |
| Reproducible synthetic track inputs for the pure tests | A new generator | `segugio.synth.detection_stream` (+ a small multi-track extension) | The deterministic raw-`DetectionSignal` generator already exists (D-09); extend its `path`/`track_id` knobs rather than writing a new one |

**Key insight:** Phase 4's only genuinely new code is the *subject-selection brain* (competitor-lock + inter-frame plausibility gate) and the *thin wrappers* (tracker call, ReID check, crop source, overlay). The tracking itself, the coast path, and the normalization are all already provided — by Ultralytics, by the Phase-2 scorer, and by `Results.boxes` respectively. Building any of them by hand is wasted effort and added risk.

## Runtime State Inventory

> Not a rename/refactor/migration phase — this section is informational for the *one* runtime side effect Phase 4 can trigger, which is the entire point of TRK-02.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 4 reads clips read-only; emits in-memory `DetectionSignal`s. The eval writes an overlay `.mp4` + a metrics log (new artifacts, no migration). | none |
| Live service config | None — no external service in Phase 4 (NDI/OBS are Phase 5). | none |
| OS-registered state | None. | none |
| Secrets/env vars | None. | none |
| Build artifacts / model downloads | **`yolo26s.pt`** auto-downloads to the Ultralytics cache on first use (expected). **`yolo26n-cls.pt`** auto-downloads ONLY if native ReID silently falls back (UNWANTED — the TRK-02 gate's job is to make this never happen and to fail loudly if it does). | TRK-02 startup assert: confirm `yolo26n-cls.pt` was NOT pulled in; confirm `BOTSORT.encoder` is the native lambda |

## Common Pitfalls

### Pitfall 1: Native ReID silently falls back to `yolo26n-cls.pt` (the TRK-02 trap) — HIGHEST PRIORITY
**What goes wrong:** You set `with_reid:True, model:auto` in `botsort_dog.yaml`, call `model.track(frame, persist=True, ...)` with defaults, and *believe* you have zero-extra-weight native ReID. You don't. `yolo26s.pt` runs `end2end=True` by default, the hook condition `not predictor.model.model.model[-1].end2end` is FALSE, Ultralytics sets `cfg.model = "yolo26n-cls.pt"`, downloads it, and uses a *separate classification model* for ReID — adding latency and silently negating the whole premise.
**Why it happens:** `on_predict_start` only registers the native-feature forward-hook when the Detect head is a standard (one-to-many) head AND `not end2end`. YOLO26's default `.pt` inference path is end2end `[VERIFIED: Context7 on_predict_start logic + docs.ultralytics.com/guides/end2end-detection "enabled by default in all YOLO26 models"]`.
**How to avoid:** Pass **`end2end=False`** to `model.track()`. This activates the one-to-many head, satisfies the hook condition, and engages the native lambda encoder. THEN assert it (Pitfall is only "avoided" if verified — see Validation Architecture TRK-02).
**Warning signs:** `yolo26n-cls.pt` appears in the Ultralytics weights cache; `tracker.encoder` is a `ReID` instance (not a lambda); `predictor._hook` is absent; inference is slower than the bare detector.

### Pitfall 2: Multi-camera ID mixing (#13107)
**What goes wrong:** Passing `[frame_camA, frame_camB]` to one `.track()` builds a single tracker; track IDs leak across cameras and ReID embeddings are polluted.
**Why it happens:** One `predictor.trackers` per `.track()` stream; a frame list is treated as a batch, not as independent cameras (`on_predict_start` builds `dataset.bs` trackers only in `mode=="stream"`).
**How to avoid:** One `YOLO().track(persist=True)` per `cam_id` (Pattern 1). Per-camera independent lock (D-05) reinforces this.
**Warning signs:** A track ID seen on cam_A reappears on cam_B; competitor-lock behaves coherently across cameras without any cross-camera code (it shouldn't — agreement must be emergent).

### Pitfall 3: Locking onto the handler's dog / a bystander (PITFALLS Pitfall 1)
**What goes wrong:** The largest/most-central dog box wins; on `handler_close_01`/`crowd_distractor_01` that can be a ringside or waiting dog, not the competitor.
**Why it happens:** Size+centeredness reward big-and-central; a calm bystander beats the small fast athlete on every naive signal.
**How to avoid:** Competitor-lock = zone-gate AND motion-energy (D-03). Zone excludes out-of-field dogs; motion excludes stationary ones. Persons never compete (dog-class filter). Then sticky continuity (D-04).
**Warning signs:** On the overlay, the highlighted locked subject sits on a stationary ringside box while the athlete runs; metrics show a high *flat* locked-track motion-energy.

### Pitfall 4: Cutting the lock loose on a momentary blur/miss (PITFALLS Pitfall 3)
**What goes wrong:** At a jump/sprint apex the detector drops the dog for a few frames; a naive lock declares "lost" and re-acquires, possibly onto a bystander.
**Why it happens:** Blur kills recall exactly at the climax; a hard "no detection → lost" rule mistakes a blur gap for a genuine loss.
**How to avoid:** The lock is "lost" only when `track_buffer:60` expires (BoT-SORT keeps the track alive through the gap) — NOT on a single missing frame. Don't over-filter the locked track's low-confidence continuation (keep a low continuation floor; PITFALLS Pitfall 3). The emitted-`None` coast already protects the scorer.
**Warning signs:** ID-switch count spikes at `sprint_blur_01`; %frames-lock-held dips at motion peaks.

### Pitfall 5: Conflating the two plausibility gates (D-07)
**What goes wrong:** TRK-05 is implemented by re-calling `plausibility_ok`, so it only re-checks "is this box a plausible dog at all" and never catches an ID swap that produces a perfectly plausible *bystander* box.
**Why it happens:** Both are called "plausibility"; the names collide.
**How to avoid:** TRK-05 takes the **previous locked box** and the **current candidate** and checks inter-frame *continuity* (displacement, size ratio). It is stateful across ticks; `plausibility_ok` is stateless per-detection. Keep them in different modules with different signatures.
**Warning signs:** A two-dogs-crossing test (synthetic, since the corpus lacks it) doesn't trigger the gate; the gate fires on a legitimately fast but continuous dog (thresholds too tight).

### Pitfall 6: Determinism leaks in the pure brain
**What goes wrong:** The competitor-lock/plausibility tests flake across runs/workers.
**Why it happens:** A wall-clock, a global RNG, or a numpy scalar leaking into a frozen `==`.
**How to avoid:** Mirror Phase 2/3 exactly: time = injected `tick`; randomness only via the injected `Generator` in `detection_stream`; `float()`/`int()`-cast at `DetectionSignal` construction (already enforced by the frozen dataclass). No heavy imports in the brain.
**Warning signs:** Same-seed runs differ; a `numpy.float64` appears in a `DetectionSignal` field.

## Code Examples

### The native-ReID engagement assertion (TRK-02 — the runnable check)
```python
# Source: Context7 /websites/ultralytics on_predict_start + BOTSORT.__init__ (8.4.x);
#         docs.ultralytics.com/guides/end2end-detection (end2end=True default).
# Run ONCE at startup, after the FIRST model.track(..., end2end=False) call on one warmup
# frame (the predictor + trackers only exist after the first track() call).
def assert_native_reid_engaged(model) -> None:
    """Raise if BoT-SORT native-feature ReID did NOT engage (silent fallback detected)."""
    predictor = model.predictor                     # exists only after first .track()
    trackers = getattr(predictor, "trackers", None)
    if not trackers:
        raise RuntimeError("no trackers on predictor — did .track() run with a botsort yaml?")
    bot = trackers[0]                               # one BOTSORT per stream (per camera)
    enc = getattr(bot, "encoder", None)
    # Native path: encoder is a bare lambda(feats, s) -> [f.cpu().numpy() ...]; NOT a ReID obj.
    from ultralytics.trackers.bot_sort import ReID
    if enc is None:
        raise RuntimeError("with_reid is False — native ReID not enabled in botsort_dog.yaml")
    if isinstance(enc, ReID):
        raise RuntimeError(
            "native ReID FELL BACK to a downloaded cls model (yolo26n-cls.pt). "
            "Pass end2end=False to model.track() so the standard Detect head engages."
        )
    # Belt-and-suspenders: the native path also registers a forward-pre-hook on Detect.
    if getattr(predictor, "_hook", None) is None:
        raise RuntimeError("native-ReID forward hook not registered — fallback likely.")
    logger.info("BoT-SORT native-feature ReID engaged (zero extra weights, end2end=False).")
```
**Confidence:** HIGH — every attribute (`predictor.trackers`, `BOTSORT.encoder` lambda-vs-`ReID`, `predictor._hook`) is read directly from the Context7-fetched 8.4.x source of `on_predict_start` and `BOTSORT.__init__`. The exact lambda signature and the `_hook` registration are quoted verbatim in Sources.

### `botsort_dog.yaml` (the override; STACK.md values)
```yaml
# Source: STACK.md custom BoT-SORT config; must live where check_yaml finds it
# (a trackers/ dir on the search path, or pass an absolute path to model.track(tracker=...)).
tracker_type: botsort
with_reid: True            # native-feature ReID
model: auto                # detector's own features as embeddings (engages ONLY with end2end=False)
track_buffer: 60           # survive ~2s occlusion / off-frame @ ~30Hz (Thresholds.track_buffer)
track_high_thresh: 0.25
track_low_thresh: 0.1
new_track_thresh: 0.25
match_thresh: 0.8
proximity_thresh: 0.5
appearance_thresh: 0.8
gmc_method: sparseOptFlow  # static crops: consider None to save CPU (no accuracy loss)
fuse_score: True
```
**Note:** `track_buffer` here duplicates `Thresholds.track_buffer` (=60). The planner should decide whether to template the yaml from config at startup (single source of truth) or document the two-place coupling. The yaml value is what BoT-SORT actually reads.

### Competitor-lock skeleton (TRK-04 — pure, deterministic)
```python
# Source: D-03/04/05 + PITFALLS Pitfall 1/2 + ARCHITECTURE zone model. PURE — numpy + stdlib.
class CompetitorLock:                              # ONE per cam_id (D-05 independent)
    def __init__(self, camera, params):            # camera.zones (config); params = TrackingParams seeds
        self.camera = camera
        self.p = params
        self.locked_id: int | None = None
        self.hist: dict[int, deque] = {}           # track_id -> recent (tick, cx, cy) for motion energy
    def select(self, candidates, tick):            # candidates: list[DetectionSignal] (dog-class, this cam, this tick)
        self._update_history(candidates, tick)
        alive_ids = {c.track_id for c in candidates}
        # D-04 sticky: keep the locked track while it is present.
        if self.locked_id in alive_ids:
            return self._by_id(candidates, self.locked_id)
        # genuine loss (locked id absent) OR no lock yet -> re-acquire on zone AND motion (D-03)
        in_field = [c for c in candidates if self._in_any_zone(c)]      # zone gate
        if not in_field:
            self.locked_id = None
            return None                            # nothing in-field -> coast
        best = max(in_field, key=lambda c: self._motion_energy(c.track_id))  # most cumulative motion
        self.locked_id = best.track_id
        return best
```
**Note:** `track_buffer:60` means a track ID survives the off-frame gap inside BoT-SORT, so `locked_id in alive_ids` stays True through the gap — the lock is sticky "for free" while the tracker holds the ID. Re-acquisition fires only after the buffer truly expires (the ID disappears from candidates). The `_in_any_zone` / `_motion_energy` exact formulation is the planner's call (Claude's Discretion).

### Inter-frame plausibility gate skeleton (TRK-05 — pure, distinct from Phase-2)
```python
# Source: D-06/07 + PITFALLS Pitfall 2 (teleport/size-jump). PURE; STATEFUL across ticks on the LOCKED track.
class PlausibilityGate:
    def __init__(self, params):
        self.p = params                            # max_displacement_per_tick, max_size_ratio (config seeds)
        self.prev = None                           # previous accepted locked DetectionSignal
    def check(self, det):                          # det = this tick's locked candidate (or None)
        if det is None:
            return None                            # genuine miss -> coast (scorer holds EMA)
        if self.prev is not None:
            disp = math.hypot(det.cx - self.prev.cx, det.cy - self.prev.cy)
            area, prev_area = det.w * det.h, self.prev.w * self.prev.h
            ratio = (area / prev_area) if prev_area > 0 else float("inf")
            r = self.p.max_size_ratio
            if disp > self.p.max_displacement_per_tick or not (1.0 / r <= ratio <= r):
                return None                        # D-06: suspect swap -> uncertain -> coast (None)
        self.prev = det                            # accept; becomes the next reference
        return det
```
**Note:** Returning `None` is the entire "uncertain → coast" mechanism — the Phase-2 scorer's FRM-05 holds the last EMA on `None` (no new downstream code, D-06). `self.prev` is NOT updated on a rejected box, so a teleport doesn't poison the reference.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "Native ReID = free, just set `model:auto`" (STACK.md premise) | Native ReID is free **only with `end2end=False`**; the YOLO26 default `end2end=True` silently forces a `yolo26n-cls.pt` fallback | YOLO26 made end2end the default (Sep 2025) `[CITED: docs.ultralytics.com/guides/end2end-detection]` | TRK-02 must pass `end2end=False` AND assert engagement — this is the phase's central correction |
| Heavy/external ReID `.pt` for re-ID | Native detector-feature ReID (lambda encoder over the Detect-layer input) | ultralytics 8.3.x+ shipped the native-feature path | Zero-extra-weight ReID for single-dog (STACK.md) — but only when the head isn't end2end |
| Trust tracker `track_id` as subject | Treat ID as advisory; layer competitor-lock + inter-frame plausibility gate | Project decision (PITFALLS Pitfall 2) | TRK-04/05 are first-class, not emergent |

**Deprecated/outdated:**
- Relying on the `STACK.md` `botsort_dog.yaml` alone to guarantee native ReID — **insufficient**; the `end2end=False` track-call argument is the missing half, now documented here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `yolo26s.pt`'s `model.model.model[-1]` is a `Detect` head with `end2end` toggled by the `end2end=False` track arg (so native ReID engages) | TRK-02, Pitfall 1 | If YOLO26's head class or the `end2end` plumbing differs in 8.4.62, the engagement check may need a different attribute. **Mitigated:** the runtime assert RAISES on fallback regardless, so a wrong assumption fails loudly at startup, not silently. Confirm on the deploy box (Q1). |
| A2 | `Results.boxes.xywhn` is `(cx, cy, w, h)` normalized to the *input frame* (the crop), matching `DetectionSignal` semantics directly | TRK-03, Pattern 3 | If `xywhn` were xyxy-normalized or pixel, the mapping would be wrong. **Low risk** — `xywhn` is the documented normalized center-wh form; verify with one printed row on the deploy box. |
| A3 | `Results.boxes.id` is `None` until a track is confirmed, then a per-stream track id; `.cls` already dog-only because `classes=[dog_idx]` filters at inference | TRK-03 | If `.id` semantics differ, the `None`-guard in Pattern 3 still prevents a crash; worst case is dropped first-frame detections (acceptable — coast). |
| A4 | COCO `dog`=16 holds for the *stock* `yolo26s.pt` (name-resolution makes this robust to custom models) | Pattern 2 | Name-resolution (Pattern 2) eliminates the risk by construction — it warns/uses the resolved index. |
| A5 | `gara_full.mp4` (the symlinked 1080p50 master) is reachable from the eval box; the committed ~30s slices (`*_01.mp4`, real local files) are the actual eval inputs | D-01, Validation | The slices are present as real files (45–88 MB each); `gara_full` is a symlink to a Windows path that may be absent on the CUDA box. **Use the slices, not the master**, for the eval (they are the per-condition cuts). |
| A6 | This box can run `YOLO("yolo26s.pt").track(...)` under 8.4.62 once `.[heavy]` + a CUDA torch build are installed (the GPU is present: driver 596.36 / CUDA 13.2) | Stack, Open Questions | `torch`/`ultralytics` not installed in `.venv` this session, so the actual `.track()` call is unverified — but the hardware is confirmed present. This is the STACK.md must-verify item, now a planned GPU-gated startup assertion (Q1). |

## Open Questions

1. **Does native ReID actually engage on `yolo26s.pt` with `end2end=False` in 8.4.62 on the deploy box?**
   - What we know: the `on_predict_start` logic (Context7) requires a non-end2end standard `Detect` head; `end2end=False` should provide it; the assert in Code Examples will confirm or RAISE.
   - What's unclear: whether YOLO26's specific head class registers as `ultralytics.nn.modules.head.Detect` (the exact isinstance check) under 8.4.62 — not yet tested (torch/ultralytics absent from `.venv`, though a CUDA GPU is present and `.[heavy]` install would make this runnable here).
   - Recommendation: make `assert_native_reid_engaged()` a **hard startup gate** (raise, don't warn) in the first GPU-gated eval task; if it raises with `end2end=False`, escalate to the user before proceeding (it would mean the YOLO26+8.4.62 combo can't do native ReID and ByteTrack-fallback or a YOLO11 head is the path — both in STACK.md's alternatives).

2. **Does the stock `yolo26s.pt` detector recall the dog adequately on `distant_01` / `dusk_distant_01`?**
   - What we know: COCO `dog` is well-trained; STACK.md says it's "sufficient for v1" but flags backlit/dusk/distant as the known recall-killers to *measure*.
   - What's unclear: actual recall on these specific slices — unmeasured (STATE.md Phase-4 concern).
   - Recommendation: the GPU eval must log per-clip detection recall on the distant/dusk slices; a low number is a *measurement to record*, not a Phase-4 failure (custom model is deferred). D-02.

3. **50fps→~30Hz: stride or decode-all?** (Claude's Discretion)
   - Recommendation: stride to ~30 fps (decode every ~1.65th frame) to match the AI tick and halve I/O; keep `tick` = emitted frame index. But this is a planner call; decode-all is fine for an offline eval where wall-clock doesn't matter.

## Environment Availability

| Dependency | Required By | Available (this box) | Version | Fallback |
|------------|------------|----------------------|---------|----------|
| `cv2` (opencv-python) | Clip decode, crops, overlay render | ✓ (in `.venv`) | 4.13.0 | — |
| `numpy` | Pure brain math | ✓ | 2.4.6 | — |
| `loguru` | ReID-engagement log, metrics | ✓ | 0.7.3 | — |
| `ultralytics` | YOLO + BoT-SORT (TRK-01/02/03) | ✗ (in `[heavy]`, not installed here) | (8.4.62 pinned) | GPU eval SKIPs (D-09); pure brain tests run regardless |
| `torch` (CUDA) | YOLO inference, `end2end` attr | ✗ (not installed in `.venv`) | (CUDA build) | GPU eval SKIPs; `pip install -e ".[heavy]"` + CUDA torch to enable |
| CUDA GPU | YOLO inference | **✓ (present)** | driver 596.36 / CUDA 13.2 (WSL) | — (hardware available; only torch/ultralytics install pending) |
| `yolo26s.pt` weights | Detector | auto-downloads on first use (deploy box) | YOLO26-S | `yolo26n.pt` config swap if GPU weak |

**Missing dependencies (for the GPU eval only):** `ultralytics`, `torch` are not installed in `.venv` — but this is **by design** (D-09): the GPU-gated eval SKIPs until they are installed. The CUDA GPU itself **is** present on this box, so a single `.[heavy]` + CUDA-torch install makes the GPU eval runnable here (it need not be deferred to a separate deploy box). It does **not** block the phase's pure-logic deliverables (TRK-04/05 logic, TRK-03 mapping), fully testable CPU-only now.

**Missing dependencies with fallback:** none needed — the split architecture is the fallback.

## Validation Architecture

> Nyquist validation is enabled (`workflow.nyquist_validation: true`). This section maps each requirement to an observation point, split into the CPU-only deterministic logic tests and the GPU-gated real-YOLO eval (D-09).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.3` + `pytest-cov 7.1.0` (`[project.optional-dependencies] dev`) `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"` |
| Quick run command | `.venv/bin/python -m pytest tests/test_competitor_lock.py tests/test_plausibility_gate.py -x` |
| Full suite command | `.venv/bin/python -m pytest` (GPU-marked tests SKIP automatically here) |
| GPU marker | **NEW** — register `gpu` marker in `pyproject.toml` `[tool.pytest.ini_options] markers` (Wave 0); skip via a `conftest` autouse `skipif` when `torch` import fails OR `torch.cuda.is_available()` is False OR weights absent |

> **Run tests via `.venv/bin/python -m pytest`** — system `python3` does not see numpy (conftest note, STATE.md).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRK-01 | One persistent tracker per `cam_id`; never a frame list; dog resolved by name | unit (mapping/structure) + **gpu** (real track) | `pytest tests/test_signals_map.py -x` ; `pytest -m gpu tests/test_yolo_clips_eval.py::test_per_camera_isolation` | ❌ Wave 0 |
| TRK-02 | Native ReID engaged with `end2end=False`; NO `yolo26n-cls.pt` fallback; logged | **gpu** (startup assert) | `pytest -m gpu tests/test_yolo_clips_eval.py::test_native_reid_engaged` | ❌ Wave 0 |
| TRK-03 | `Results.boxes` row → frozen `DetectionSignal` unchanged; dog-filtered; `None`-id safe | unit (PURE) | `pytest tests/test_signals_map.py -x` | ❌ Wave 0 |
| TRK-04 | Competitor-lock: zone+motion acquire; sticky continuity; per-camera independent | unit (PURE, synthetic tracks) | `pytest tests/test_competitor_lock.py -x` | ❌ Wave 0 |
| TRK-05 | Inter-frame teleport/size-jump gate; reject → None (coast); not Phase-2 guard | unit (PURE, synthetic tracks) | `pytest tests/test_plausibility_gate.py -x` | ❌ Wave 0 |
| (D-09 boundary) | `import segugio.tracking` succeeds with torch/ultralytics/cv2 ABSENT | unit (import smoke) | `pytest tests/test_tracking_import_smoke.py -x` | ❌ Wave 0 |
| (D-08 metrics) | Per-clip metric counters (ID-switch, %lock-held, coast/uncertain) are pure & correct | unit (PURE counters) + **gpu** (real overlay+metrics) | `pytest tests/test_tracking_metrics.py -x` ; `pytest -m gpu tests/test_yolo_clips_eval.py::test_overlay_and_metrics` | ❌ Wave 0 |

### CPU-only deterministic logic tests (run everywhere, every commit)
These prove the **brain** on synthetic inputs from `synth.detection_stream` (+ a multi-track extension) — exactly the Phase-2/3 pattern. Concrete observation points:
- **TRK-04 competitor-lock (PITFALLS Pitfall 1):**
  - Two synthetic dog tracks: one **in-zone, high motion** (athlete), one **out-of-zone, stationary** (bystander). Assert the lock selects the athlete's `track_id`, NOT the bystander, even when the bystander box is larger/more central.
  - **Sticky continuity (D-04):** once locked, feed a tick where a *different* in-zone track momentarily has higher motion; assert the lock does NOT switch (it re-picks only on loss). `assert lock.locked_id` unchanged.
  - **Genuine loss → re-acquire:** drop the locked track's `track_id` from candidates for > buffer; assert re-acquisition on zone+motion.
  - **Per-camera independence (D-05):** two `CompetitorLock` instances locking different IDs from different synthetic streams; assert no shared state.
- **TRK-05 plausibility gate (PITFALLS Pitfall 2):**
  - **Teleport:** feed a locked-track sequence with one frame jumping `Δcenter > max_displacement_per_tick`; assert `check()` returns `None` (coast) for that frame and `self.prev` is NOT updated to the teleported box.
  - **Size-jump:** area doubles/halves beyond `max_size_ratio`; assert `None`.
  - **Continuous fast dog (false-positive guard):** a fast-but-continuous run within thresholds is NOT rejected.
  - **Distinct-from-Phase-2 (D-07):** a box that PASSES `plausibility_ok` (plausible dog) but is a teleported bystander is still REJECTED by TRK-05 — proving the two gates are independent.
- **TRK-03 mapping:** fabricate `xywhn`/`ids`/`confs` numpy arrays → assert exact frozen `DetectionSignal` fields (incl. `None`-id → empty list); determinism: same arrays → byte-identical list.
- **Determinism gate (FRM-07/DEC-07 analogue):** same seed + scenario → byte-identical `list[DetectionSignal | None]` from the full select→gate pipeline on synthetic tracks.
- **Import smoke:** `import segugio.tracking` with `torch`/`ultralytics`/`cv2` forced absent (the established 01-01 pattern).
- **Sampling rate:** every task commit runs the quick command; every wave merge runs the full suite.

### GPU-gated real-YOLO eval (D-09; SKIPs here and in CI)
The heavy, human-judged half. Runs only on the CUDA box with weights present. Observation points + metric thresholds-as-seeds (NOT pass/fail gates — D-08 is eyeball + regression net, D-02 says calibration is not a Phase-4 gate):
- **TRK-02 (HARD gate, the exception):** `assert_native_reid_engaged()` RAISES on fallback. This is the one GPU test that is a true pass/fail — native ReID engagement is a correctness invariant, not a tuning number.
- **The hard clips to run (D-02):** `handler_close_01`, `crowd_distractor_01` (competitor-lock vs handler/bystander), `sprint_blur_01` (blur coast), `distant_01` + `dusk_distant_01` (small/low-light recall), `warm_jump_01` (jump blur + handler). Crops of each provide frame-exit/re-entry.
- **Per-clip metrics logged (D-08), as a regression net with seed thresholds:**
  - **Locked-subject ID-switch count** (seed expectation: low / 0 on `handler_close_01`; non-zero acceptable on `sprint_blur_01` — record, don't fail).
  - **% frames lock-held** (seed: high on clean stretches; dips at blur peaks expected).
  - **Coast count / uncertain count** (the plausibility gate's `None` emissions — non-zero at swaps/blur is correct behavior).
  - **Per-clip detection recall** on `distant`/`dusk_distant` (the COCO-dog measurement, Q2 — record for the deferred custom-model decision).
- **Overlay video (D-08):** render boxes + track IDs + locked-subject highlight + zone overlays per clip for human review (the auto-director's correctness is ultimately visual).
- **UNVERIFIED, logged explicitly (D-02):** agility-tunnel-occlusion and clean two-similar-dogs-crossing — corpus has neither. The code paths exist (and the synthetic two-track crossing test exercises the *logic*), but they are NOT clip-proven; the eval must emit an explicit "UNVERIFIED: <case> — no corpus footage" log line, not a silent pass.

### Wave 0 Gaps
- [ ] Register `gpu` pytest marker + autouse skip in `pyproject.toml` / a tracking-scope `conftest` (skip when torch/CUDA/weights absent)
- [ ] `tests/test_tracking_import_smoke.py` — lazy-import boundary (heavy deps forced absent)
- [ ] `tests/test_signals_map.py` — TRK-03 pure mapping
- [ ] `tests/test_competitor_lock.py` — TRK-04 pure logic on synthetic tracks
- [ ] `tests/test_plausibility_gate.py` — TRK-05 pure logic on synthetic tracks
- [ ] `tests/test_tracking_metrics.py` — D-08 pure metric counters
- [ ] `tests/test_yolo_clips_eval.py` — `@pytest.mark.gpu` real-YOLO eval (TRK-01/02 + overlay/metrics)
- [ ] Multi-track extension to `synth.detection_stream` (≥2 simultaneous tracks, per-track zone/motion/path) for the competitor-lock + crossing-swap tests
- [ ] `seeded_rng` reuse from `conftest`; add a `tracking_params` / crop-geometry fixture
- [ ] Framework install on deploy box: `pip install -e ".[heavy]"` + CUDA torch (NOT needed for CPU tests)

## Project Constraints (from CLAUDE.md)

- **Tech stack is imposed** — `ultralytics`+`torch`(+`tensorrt` prod) for YOLO, `obsws-python`/`cyndilib`/`transitions` for later phases. Phase 4 uses the YOLO/tracker half only. **Pinned: `yolo26s.pt`, dog class, BoT-SORT native ReID** (CLAUDE.md "Recommended Stack").
- **Performance:** AI loop < ~150ms (ideal <80ms). Phase 4 doesn't gate on this (offline eval), but the `end2end=False` choice trades a little latency for ID persistence — flag for the Phase-5 budget. ByteTrack/`yolo26n` are the documented latency fallbacks.
- **Robustness:** no crash; feed drop → degrade. Phase 4's fail-safe analogue: NaN/missing → `None` → coast (mirrors Phase-2 scorer); the tracker wrapper must not raise on an empty/blank frame.
- **"What NOT to Use" (CLAUDE.md table) — honored:** name-resolve `dog` (not hardcoded 16) ; one `model.track()` per camera (never a frame list) ; BoT-SORT native ReID (not ByteTrack default) ; `track_buffer:60` (not default 30) ; no external heavy ReID ; no disc/frisbee in v1 ; don't commit downloaded footage.
- **Global:** evidence > assumptions (every load-bearing claim here is tool-verified) ; build only what's asked (no FSM/NDI/OBS/disc/pose) ; complete what you start (no TODO stubs) ; feature branches ; validate after changes (`.venv/bin/python -m pytest`).
- **GSD enforcement:** all edits flow through a GSD command — the planner/executor handle this.

## Sources

### Primary (HIGH confidence)
- **Context7 `/websites/ultralytics`** — `on_predict_start` (native-ReID hook condition, `cfg.model = "yolo26n-cls.pt"` fallback, per-stream tracker list, `persist` early-return); `BOTSORT.__init__` (the `encoder` lambda-vs-`ReID` selection); `BOTSORT.init_track` / `ReID` class; `Results.boxes` (`xywhn`/`id`/`conf`); `modes/track` tracker args (`model: auto` → native features, "falling back to `yolo26n-cls.pt`"). The load-bearing TRK-01/02/03 facts.
- **docs.ultralytics.com/guides/end2end-detection** — "end-to-end is **enabled by default** in all YOLO26 models"; disable via `end2end=False` in `predict()`/`track()`. **The TRK-02 root-cause + fix.**
- **docs.ultralytics.com/models/yolo26** + arxiv 2509.25164 / 2606.03748 — YOLO26 dual-head NMS-free end2end-by-default architecture.
- **Installed environment (this session):** `.venv` imports (cv2 4.13.0, numpy 2.4.6, loguru 0.7.3; ultralytics/torch ABSENT from `.venv`); **CUDA GPU present** (`nvidia-smi` driver 596.36 / CUDA 13.2 via WSL); `pip index versions ultralytics`→8.4.62 present (latest 8.4.63); `opencv-python`→4.13.0.92; `slopcheck 0.6.1`→ all heavy-group packages `[OK]`.
- **Repo source (read directly):** `src/segugio/framing/signals.py` (frozen `DetectionSignal` contract), `scorer.py` (`MultiCamScorer.update` + FRM-05 coast path = the D-06 coast mechanism), `terms.py` `plausibility_ok` (the *intra-frame* guard TRK-05 must NOT be), `config/models.py` (`ModelConfig`, `Camera`/`Zone`, `Thresholds.track_buffer`), `synth/detection_stream.py` (the D-09 substrate), `fixtures.py` (`select_clips`/`resolve_clip_path`), `pyproject.toml`, `tests/conftest.py`, `tests/fixtures/clip_manifest.yaml` + `README.md`, `config.example.yaml`.

### Secondary (project research, already-settled — built upon, not re-derived)
- `.planning/research/STACK.md` — YOLO26s/dog, native-ReID rationale + the "verify it engages else silent fallback" warning (this doc supplies the *concrete* check + root cause), `track_buffer:60`, `botsort_dog.yaml` values, #13107, ByteTrack fallback, version caveats. **HIGH.**
- `.planning/research/PITFALLS.md` — Pitfalls 1 (handler/bystander lock), 2 (ID-swap/teleport gate), 3 (blur coast), 4 (small-at-distance), 10 (per-camera lighting) + the "Looks Done But Isn't" checklist (the Phase-4 acceptance lens). **MEDIUM-HIGH.**
- `.planning/research/ARCHITECTURE.md` — per-camera image-normalized zone model (Option A) the competitor-lock zone-gate consumes. **MEDIUM-HIGH.**

### Tertiary (LOW confidence — flagged)
- General community reports of `model:auto` fallback behavior corroborate the Context7 source but the Context7 source is authoritative; no LOW-only claims are load-bearing here.

## Metadata

**Confidence breakdown:**
- Standard stack / API calls (TRK-01/03): **HIGH** — Context7-verified against shipped 8.4.x source + installed-registry confirmation.
- TRK-02 native-ReID engagement + `end2end=False` fix: **HIGH** — exact `on_predict_start`/`BOTSORT.__init__` source + the official end2end-default doc; the only residual unknown (the precise `Detect` isinstance under 8.4.62 on a CUDA box) is covered by a hard runtime assert (Q1, A1).
- Competitor-lock / plausibility-gate algorithm (TRK-04/05): **MEDIUM** — principle locked by CONTEXT + PITFALLS; exact formulations are config seeds / planner discretion by design.
- Validation architecture: **HIGH** — the split (CPU pure + GPU-gated) is forced by D-09 and the verified environment (heavy deps absent here).

**Research date:** 2026-06-10
**Valid until:** ~2026-07-10 for the API specifics (ultralytics is fast-moving — 8.4.63 already shipped; the `end2end`/native-ReID logic is stable across 8.4.x but re-verify if the pin moves). Pure-logic design is stable indefinitely.
