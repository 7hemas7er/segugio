# Phase 19: Detection Eval on Real Footage & Fine-tune Decision - Research

**Researched:** 2026-07-14
**Domain:** Object-detection evaluation (recall/precision@IoU0.5) on the shipped FP16 batched YOLO path + opencv GT-labeling tooling + a metrics-backed fine-tune decision doc
**Confidence:** HIGH (this is a codebase-grounded phase; nearly every load-bearing finding was read directly from the repo)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Eval runs on the owner's real **disc** footage only for v1.4 — `gara_full.mp4` (FIDASC, single fixed cam, ~10h, 1080p50) plus the existing ~30s per-condition cuts (`sprint_blur`, `handler_close`, `distant`, `crowd_distractor`, `warm_jump`, `dusk_distant`). No CC0 supplementation for disc.
- **D-02:** **Agility is deferred, not sourced.** Do NOT pull CC0 agility clips. Agility cells (esp. `tunnel_contact_occlusion`, `midfield_equidistant` on agility) are marked carried-forward in the coverage report, not filled.
- **D-03:** Reuse existing corpus infra as-is (`tools/catalog_clips.py`, `<clip>.tags`, `clip_manifest.yaml`, `segugio.fixtures.select_clips`/`coverage_report`). If `gara_full.mp4` lacks a hard condition (`multi_dog`, `midfield_equidistant`), cut a new ~30s disc slice from it and tag it, rather than importing outside footage.
- **D-04:** Build a **lightweight internal bbox-labeling tool** — zero external deps (no CVAT/Roboflow, no SAM/auto-label). Samples frames **sparsely** (every N-th), operator draws/confirms the in-competition dog bbox, writes a simple committed GT sidecar, opencv-only (mirrors `catalog_clips.py`).
- **D-05:** **Rejected auto-labeling.** Ground-truth MUST be independent of the detector under test.
- **D-06:** Label **~a few hundred frames total**, sampled to cover each hard condition — "enough to be statistically meaningful," not exhaustive.
- **D-07:** "In-competition dog" = the single subject the competitor-lock is meant to grab (zone ∧ motion). NOT bystander dogs, NOT the handler. When multiple dogs present, only the in-competition dog gets a GT box; other dogs are ignored (they are what precision must NOT false-lock onto).
- **D-08:** Report **recall AND precision per condition** at **IoU 0.5**, measured on the **FP16 batched shipped path** (`segugio.tracking.batched`), NOT the eager FP32 serial `track()` (P04 UAT), and NOT the `lock_held_fraction` proxy. Extend `run_clip_eval` (or a sibling) to consume GT sidecars and emit true recall/precision. **MUST first confirm whether today's `run_clip_eval` runs the batched shipped path or the eager path — if eager, wire the eval onto `batched.py`.**
- **D-09:** Precision matters as a **false-lock guard** — count detections that land on handler/shadow/bystander. A fine-tune that lifts distant recall must not regress this.
- **D-10:** **Fine-tune trigger rule = absolute distant-dog recall with a precision guard.** Starting threshold: **distant-dog recall@IoU0.5 < 0.70 → fine-tune** (tunable default). The decision is a rule, not a vibe.
- **D-11:** Phase 19 **stops at the go/no-go decision + a fine-tune spec if "go".** It does NOT run training or produce a weight. If "go," it specifies dataset/approach so a later effort can execute. Preserve the drop-in-via-config-`path` contract.
- **D-12:** A "no-go" (COCO `dog` is good enough) is a valid, first-class outcome — the deliverable is the evidence that shipping COCO `dog` as-is is defensible on real footage.

### Claude's Discretion
- The exact sampling stride N, the GT sidecar file format, and the labeling-tool UX (opencv-only, no external service, committed re-readable GT format).
- Whether recall/precision are added to `run_clip_eval`'s return dict or a new sibling eval function — pick the cleaner seam.
- The precise structure of the decision doc / report artifact.

### Deferred Ideas (OUT OF SCOPE)
- **Agility detection eval** (tunnel/contact occlusion, midfield-equidistant, agility multi-dog) — deferred until real agility footage with consent exists. Coverage report flags these carried-forward. Update REQUIREMENTS.md/ROADMAP.md notes at plan/verify time.
- **Running the actual fine-tune training + shipping a weight** — deferred to a follow-up effort gated on a "go" decision.
- **CC0 (Pexels/Pixabay/`yt-dlp`) footage sourcing** — not needed for disc v1.4.
- **Framing/tracking seed calibration on real footage** — that is Phase 20 (CAL-01/02). Keep seed-tuning out of Phase 19.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-01 | A real multi-venue corpus is catalogued via `tools/catalog_clips.py` with a condition checklist (disc **and** agility). Scoped in discussion to **disc across hard conditions**; agility carried-forward. | Corpus infra fully exists (`fixtures.py`, `catalog_clips.py`, manifest). 6 disc slices already tagged; §"Corpus Scoping" lists the 1-2 disc slices still to cut from `gara_full` (`multi_dog`, `midfield_equidistant`) and the agility carry-forward reporting. |
| DET-02 | A representative subset has ground-truth (in-competition dog bbox) to measure real recall/precision. | §"GT Sidecar Format" + §"Labeling Tool" define a `tools/label_clips.py` (opencv `cv2.selectROI`, zero deps) writing a committed `<clip>.gt.yaml` sidecar keyed by emitted tick. |
| DET-03 | Recall **and** precision on the **FP16 batched shipped path** (not eager FP32; not the `lock_held` proxy) — distant recall + handler/shadow false-lock, per condition. | §"CRITICAL FINDING: eval runs the EAGER path today" pinpoints the exact rewire; §"Recall/Precision Algorithm" gives IoU + single-subject matching; §"Metrics on the shipped forward" specifies the identical `model.predict` kwargs. |
| DET-04 | A motivated `yolo26s` fine-tune decision (go/no-go) from DET-03 metrics; if go, weight is drop-in via config `path` with no code change. | §"Fine-tune Decision Rule & Spec" gives the threshold rule (D-10), the precision guard (D-09), the decision-doc structure, and the fine-tune-spec contents that preserve `ModelConfig.path` + resolve-dog-BY-NAME. |
</phase_requirements>

## Summary

This is a **desk-work measurement + decision phase**, almost entirely grounded in existing code — no new runtime packages, no training. The corpus, manifest, fixture-query API, clip decoder, per-camera tracker, batched-detect adapter, and a GPU-gated eval skeleton all already exist. The phase adds three things: (1) a **GT-labeling tool** (`tools/label_clips.py`, opencv `cv2.selectROI`, zero deps), (2) a **recall/precision harness** that runs the **FP16 batched detection forward the live loop actually ships** and matches detections to a committed GT sidecar at IoU 0.5, and (3) a **metrics-backed fine-tune decision doc** (+ a fine-tune spec if "go").

**The single most important finding for the planner:** today's `run_clip_eval` (`src/segugio/tracking/eval.py:296-321`) runs the **eager FP32 serial `PerCameraTracker.track()` path** — NOT the batched FP16 shipped path. It constructs `PerCameraTracker(...)` and calls `tracker.track(crop)` per camera per tick. DET-03 requires the measurement land on `segugio.tracking.batched.batched_detect_dispatch`, which is what the production loop uses (`orchestrator/loop.py:399-428`, `_batched_inference`). The eval must be rewired to the batched forward. The cleanest seam is a **new sibling function** in `eval.py` (D-08 discretion allows this) that mirrors `loop._batched_inference`'s forward, because the recall/precision shape (full-frame detector output vs a single GT box) is structurally different from `run_clip_eval`'s crop→track→lock→gate→overlay pipeline.

**Second key finding:** the fine-tune decision is about the **detector**, so recall/precision should be computed on the **raw detection boxes** from `model.predict(..., half=True, end2end=False, classes=[dog_idx])` (the exact forward `batched.py` runs), NOT on BoT-SORT-confirmed tracks. BoT-SORT confirmation thresholds are separately tuned in Phase 20 (CAL-02); folding them in would understate raw detector recall and confound the fine-tune decision.

**Primary recommendation:** Add `tools/label_clips.py` (opencv `selectROI`, writes `<clip>.gt.yaml`), a pure `iou`/`match_detections` module (CPU-unit-testable), and a `run_detection_eval(clip, gt_sidecar, model_cfg, use_fp16=True)` sibling in `eval.py` that reuses `ClipFrameSource` with a single full-frame "camera" at the GT's stride and runs the shipped FP16 forward. Gate the harness `@pytest.mark.gpu` (runs from `venv312`). Emit a per-condition recall/precision table into a decision doc applying the D-10 rule.

## Architectural Responsibility Map

This phase is a pipeline of stages, not application tiers. The map records which stage owns each capability so tasks land in the right module.

| Capability | Primary Stage (module) | Secondary | Rationale |
|------------|------------------------|-----------|-----------|
| Clip cataloguing + condition tags | `tools/catalog_clips.py` (dev tool) + `src/segugio/fixtures.py` (query API) | — | Already exists; DET-01 reuses it. New disc slices re-run the cataloguer. |
| Cutting new disc slices from `gara_full` | dev tool (opencv `VideoWriter`, existing pattern per README) | — | D-03; opencv-only, no ffmpeg. |
| Ground-truth labeling (human draws bbox) | **NEW** `tools/label_clips.py` (dev tool, opencv `selectROI`) | — | D-04; must be detector-independent (D-05), so it lives OUTSIDE the inference stack. |
| GT persistence format | committed `<clip>.gt.yaml` sidecar (tracked; references local binary) | — | Mirrors `.tags` convention but tracked (not gitignored). |
| Frame decode | `src/segugio/tracking/frame_source.py` (`ClipFrameSource`) | — | Reused by BOTH the label tool and the eval so frame indexing is identical. |
| Shipped detection forward (FP16 batched) | `src/segugio/tracking/batched.py` numerics (`model.predict(half, end2end=False, classes)`) | `detector.PerCameraTracker.model` | DET-03 requires the SHIPPED path; `loop._batched_inference` is the production reference. |
| IoU + single-subject GT↔detection matching | **NEW** pure module (e.g. `tracking/detection_metrics.py`, CPU-unit-testable) | — | Deterministic, cv2-free — mirrors the `compute_metrics` "pure above the boundary" pattern. |
| Recall/precision harness (drives forward + metric) | **NEW** sibling `run_detection_eval` in `eval.py` (below the lazy-import boundary) | `fixtures.select_clips`/`resolve_clip_path` | D-08; heavy edge, `@pytest.mark.gpu`, runs from `venv312`. |
| Fine-tune go/no-go decision + spec | **NEW** decision doc artifact (markdown under the phase dir) | — | DET-04/D-11; pure writing, no training. |

## Standard Stack

**No new packages.** Every dependency this phase needs is already in the locked stack (CLAUDE.md) and already imported in the repo.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ultralytics` (`YOLO`) | already installed in `venv312` (`>=8.3.x`, YOLO26-aware) | The `yolo26s.pt` detector; `model.predict(...)` is the shipped detection forward | Locked stack; `PerCameraTracker`/`batched.py` already use it `[VERIFIED: codebase]` |
| `torch` (+cu126) | `venv312` only (py3.12) | FP16 inference on the CUDA GPU | Locked; py3.14 `.venv` is CPU-only and SKIPs `-m gpu` `[CITED: docs/run.md]` |
| `opencv-python` (`cv2`) | already installed | Frame decode (`ClipFrameSource`), slice cutting, and `cv2.selectROI` labeling UI | opencv-only corpus-tooling constraint `[VERIFIED: codebase]` |
| `numpy` | already installed | Box arrays, IoU vectorization | Locked |
| `pyyaml` (`yaml.safe_dump`/`safe_load`) | already installed | GT sidecar read/write + manifest | Used by `fixtures.py` + `catalog_clips.py` `[VERIFIED: codebase]` |
| `pytest` (+ `@pytest.mark.gpu`) | already configured | Harness runner; gpu marker gate | `tests/test_yolo_clips_eval.py` skeleton exists `[VERIFIED: codebase]` |
| `loguru` | already installed | Structured logging (light dep, top-level OK) | Used across the package |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `cv2.selectROI` for labeling | Custom `cv2` window + `setMouseCallback` drag | `selectROI` is a built-in one-liner drag-box with ENTER-confirm/`c`-cancel; a custom callback is more code for the same result. Use `selectROI`; only hand-roll if you need multi-box or keyboard nudging (you don't — single box, D-07). |
| YAML GT sidecar | JSON GT sidecar | YAML matches `clip_manifest.yaml` and pyyaml is already a dep; either is fine (discretion). Recommend YAML for consistency. |
| Reuse `batched_detect_dispatch` verbatim | A thin `model.predict()` mirror | `batched_detect_dispatch` returns BoT-SORT-*confirmed* tracks (understates raw detector recall). For a DETECTOR fine-tune decision, compute on raw `predict` boxes with identical FP16 kwargs. See Open Question 1. |

**Installation:** None. Confirm `venv312` has the heavy stack (`ultralytics`, `torch`+cu126) and `yolo26s.pt` resolves before the GPU harness run.

## Package Legitimacy Audit

**Not applicable — this phase installs NO external packages.** D-04 mandates zero external dependencies for the labeling tool; the eval reuses the already-locked, already-installed stack (`ultralytics`, `torch`, `opencv-python`, `numpy`, `pyyaml`, `pytest`, `loguru`). No registry verification required because nothing new is added.

## Architecture Patterns

### System Architecture Diagram

```
                       (dev tool, one-time at ingest)
  owner footage ──► tools/catalog_clips.py ──► clip_manifest.yaml (tracked)
  (local, gitignored)   │  opencv probe + .tags          │
                        │                                 ▼
   gara_full.mp4 ──► [cut ~30s disc slices for            segugio.fixtures.select_clips
   (opencv VideoWriter) multi_dog / midfield_equidistant] │  (query by condition+discipline)
                        └───────────► re-catalog ─────────┘
                                                          │
                                                          ▼
                       (dev tool, human-in-loop — DETECTOR-INDEPENDENT, D-05)
   clip binary ──► tools/label_clips.py ──► ClipFrameSource(stride=N) ──► cv2.selectROI
                                                          │  (operator draws 1 dog box / frame,
                                                          │   or SKIP = dog absent → null)
                                                          ▼
                                          <clip>.gt.yaml  (TRACKED sidecar:
                                          stride N + per-tick normalized bbox|null)
                                                          │
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  @pytest.mark.gpu harness  (venv312, CUDA)  — run_detection_eval(...)          │
   │                                                                                │
   │  clip ─► ClipFrameSource({"full":[0,0,1,1]}, stride=N)  ─► full frame per tick │
   │                              │                                                 │
   │                              ▼                                                 │
   │        SHIPPED FP16 forward: model.predict([frame], classes=[dog_idx],         │
   │                              end2end=False, half=True, verbose=False)          │
   │                              │  (identical kwargs to batched.py step 2)         │
   │                              ▼                                                 │
   │        raw detections (xywhn, conf)  ──►  IoU vs GT box @ 0.5                   │
   │                              │            (pure detection_metrics: TP/FP/FN)    │
   │                              ▼                                                 │
   │        per-condition recall + precision table                                  │
   └──────────────────────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
                       apply D-10 rule (distant recall < 0.70 → fine-tune)
                       + D-09 precision guard  ──►  DECISION DOC (go/no-go)
                                                     └─► if "go": fine-tune SPEC
```

### CRITICAL FINDING: `run_clip_eval` runs the EAGER path today

`[VERIFIED: codebase]` `src/segugio/tracking/eval.py`:
- Line 296: `trackers[cam.id] = PerCameraTracker(model_cfg.path, model_cfg.class_index, "botsort_dog.yaml")` — constructed with **no `use_fp16`** (defaults `False`, `detector.py:205`) and **no `engine_path`**.
- Line 321: `results = tracker.track(crop)` → `PerCameraTracker.track` (`detector.py:276-309`) calls `self.model.track(frame, ..., half=self.use_fp16=False, end2end=False)` — **eager FP32 serial `.track()`, one call per camera per tick.**

This is exactly the P04 path DET-03 rejects. The production loop instead uses the batched forward:
- `[VERIFIED: codebase]` `orchestrator/loop.py:399-428` `_batched_inference` → `batched_detect_dispatch(model, frames_by_cam, self.trackers, dog_idx, tick, use_fp16=self.config.model.use_fp16)`.
- `[VERIFIED: codebase]` `batched.py:128-134` runs `model.predict(batch_frames, classes=[int(dog_idx)], end2end=False, half=bool(use_fp16), verbose=False)` — the ONE shipped detection forward.

**Seam to wire the eval onto the shipped path** (for the recall/precision harness): call `model.predict()` with the batched.py kwargs directly (recommended — see Open Question 1), or call `batched_detect_dispatch` if you also want tracker-confirmed numbers. The FP16 numerics (`half=True`) are the load-bearing part DET-03 cares about; `end2end=False` + `classes=[dog_idx]` must match verbatim.

### Pattern 1: Pure metric above the lazy-import boundary
`eval.py` already splits **pure counters** (`compute_metrics`, top of file, stdlib-only, cv2-free, CPU-unit-tested) from the **heavy driver** (`run_clip_eval`, `import cv2` inside the function). Follow this exactly:
- Put `iou()` and `match_detections()` (and per-condition aggregation) in a **pure module** (`tracking/detection_metrics.py` or below the eval boundary) — no cv2/torch, deterministic, CPU-unit-tested.
- Put the GPU driver (`run_detection_eval`) below the lazy-import boundary with heavy imports **inside** the function.

**Example (pure IoU + single-subject match):**
```python
# Pure — no cv2/torch. Boxes are normalized CORNER form [x0, y0, x1, y1] in [0,1].
def iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0

def score_frame(gt_box, det_boxes, thr=0.5):
    """Single in-competition dog per frame (D-07). Returns (tp, fp, fn)."""
    if gt_box is None:                       # dog genuinely absent this labeled frame
        return 0, len(det_boxes), 0          # every detection is a false-lock (FP), no FN possible
    if not det_boxes:
        return 0, 0, 1                       # dog present, nothing detected → FN
    ious = [iou(d, gt_box) for d in det_boxes]
    best = max(range(len(ious)), key=lambda i: ious[i])
    if ious[best] >= thr:
        tp, matched = 1, best                # the matched detection is the true dog
    else:
        tp, matched = 0, None                # nothing overlapped the dog → FN
    fn = 0 if tp else 1
    fp = sum(1 for i in range(len(det_boxes)) if i != matched)  # everything else = false-lock
    return tp, fp, fn
# Per condition: recall = ΣTP / (ΣTP + ΣFN);  precision = ΣTP / (ΣTP + ΣFP)
```

### Pattern 2: Frame-index alignment via a shared stride (the correctness lynchpin)
Both the label tool and the eval decode via **`ClipFrameSource`** (`frame_source.py`). `ClipFrameSource` emits every `stride`-th decoded frame and stamps `tick` = emitted-frame index (0,1,2,…) `[VERIFIED: codebase, frame_source.py:63-101]`.

Recommendation: **key the GT sidecar by `tick`, and store `stride` in the sidecar.** The label tool and the eval both open `ClipFrameSource(clip, {"full": [0,0,1,1]}, stride=N)` with the SAME N. The tool labels each emitted frame (draw box, or SKIP → null); the eval iterates and scores each tick against its GT entry. This guarantees exact alignment with zero seeking (avoids `cv2.CAP_PROP_POS_FRAMES` keyframe-seek inaccuracy) and fully reuses the existing decoder, exactly as CONTEXT.md asks ("the labeling sampler and the eval both build on `ClipFrameSource`").

### Pattern 3: Detection recall on the FULL frame, not the L/C/R crops
`run_clip_eval` splits the frame into overlapping L/C/R pseudo-cameras (`crop_geometry`) to *simulate* multi-cam from single-cam footage — that is a **tracking/framing** fixture artifact. For **detector** recall/precision (DET-03/04), use a **single full-frame "camera"** `{"full": [0,0,1,1]}`. `Results.boxes.xywhn` is then normalized to the full frame, matching a full-frame-normalized GT box. This is also more faithful to the shipped path, where the detector sees whole NDI phone frames, not crops.

### Anti-Patterns to Avoid
- **Measuring on the eager FP32 `track()` path** — the exact P04 mistake DET-03 forbids. Use the FP16 `predict` forward.
- **Auto-labeling GT with a bigger YOLO/SAM** — D-05 rejects it: it inherits the distant-dog miss bias being measured. (Auto-label is fine for the *training* set in the fine-tune spec — a different artifact — but never for the eval GT.)
- **Passing a frame list to one `model.track([frames])`** — Ultralytics #13107; mixes track IDs. (Not a risk if you use `model.predict` for detection-only recall, but keep it in mind if you touch tracking.)
- **Hardcoding dog class = 16** — resolve BY NAME via `resolve_dog_index(model, configured_index)` (`detector.py:155-189`); a fine-tuned mono-class weight has dog at index 0.
- **Comparing these numbers apples-to-apples with P04** — P04 was eager FP32 + `lock_held` proxy; these are FP16 + true GT recall/precision. The decision doc MUST state the delta is not directly comparable (D-08 specifics).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Frame decode + stride + blank-frame safety | A raw `cv2.VideoCapture` loop | `ClipFrameSource` (`frame_source.py`) | Already handles stride, blank-frame skip, deterministic tick, capture release, traversal-safe path |
| Clip path resolution | `os.path.join` on user strings | `fixtures.resolve_clip_path` | Traversal-guarded, typed `FixtureNotPresentError` for gitignored binaries |
| Clip selection by condition | Manual manifest parsing | `fixtures.select_clips` / `coverage_report` | The committed query API + the `{condition × discipline}` matrix |
| Dog-class index | Hardcode 16 | `resolve_dog_index` | Name-resolved (CFG-04); survives a mono-class fine-tuned weight |
| Native-ReID feats on batched predict | Re-derive the hook | `ensure_native_feats` (`detector.py:45`) | Only needed if you run BoT-SORT; NOT needed for raw-detection recall |
| Drag-a-box UI | Custom mouse callback | `cv2.selectROI` | Built-in drag+ENTER-confirm; single box matches D-07 |
| YAML read/write | `eval`/`pickle` | `yaml.safe_dump` / `yaml.safe_load` | Safe deserialization (already the manifest pattern) |

**Key insight:** ~90% of this phase's plumbing already exists. The genuinely new code is small: a labeling tool, a pure IoU/matching module, one GPU driver function, and a decision doc. Resist rebuilding the decode/select/resolve substrate.

## Runtime State Inventory

Not a rename/refactor/migration phase — **section omitted** (this is additive measurement + tooling; no stored keys/registrations to migrate).

## Common Pitfalls

### Pitfall 1: Measuring the wrong compute path (the headline risk)
**What goes wrong:** Extending `run_clip_eval` in place inherits its eager FP32 serial `track()` — silently reproducing the P04 path DET-03 rejects.
**Why it happens:** `run_clip_eval` looks like the natural extension point, but its trackers are FP32 (`use_fp16` defaults False) and serial.
**How to avoid:** New sibling `run_detection_eval` that runs `model.predict(..., half=True, end2end=False, classes=[dog_idx])` — the batched.py forward. Assert `half=True` in the call.
**Warning signs:** Latency/recall numbers that match the P04 `lock_held` figures; no FP16 in the predict kwargs.

### Pitfall 2: GT/eval frame misalignment
**What goes wrong:** GT labeled at frame indices that don't map to the frames the eval scores → garbage recall.
**Why it happens:** `cv2.CAP_PROP_POS_FRAMES` seeking is keyframe-inaccurate; mixing raw-decoded vs strided indices.
**How to avoid:** Both tool and eval use `ClipFrameSource(stride=N)` and key GT by `tick`. Store N in the sidecar; the eval reads N from the sidecar, never assumes it.
**Warning signs:** Recall near 0 on a clip where the dog is clearly present; off-by-a-few-frames box drift.

### Pitfall 3: Confusing detector recall with tracker-confirmed recall
**What goes wrong:** Computing recall on BoT-SORT-confirmed tracks understates raw detector recall (confirmation delay + `track_high_thresh:0.25`), skewing the fine-tune decision.
**Why it happens:** `batched_detect_dispatch` returns tracked `Results`; it's tempting to reuse verbatim.
**How to avoid:** Compute recall/precision on raw `predict` boxes. Optionally ALSO report tracker-confirmed recall as a secondary line, clearly labelled. See Open Question 1.
**Warning signs:** First-frame-of-appearance dogs counted as FN even though the detector clearly boxed them.

### Pitfall 4: Precision undercounting the false-lock case (D-09)
**What goes wrong:** Only counting FN (missed dog) and ignoring detections on handler/shadow/bystander → precision looks perfect, false-lock risk invisible.
**How to avoid:** In `score_frame`, every detection that is NOT the IoU-matched dog counts as FP (including all detections on frames where GT is `null` = dog absent). Deliberately include `handler_close`/`crowd_distractor`/`warm_jump` (handler-prominent) clips so FPs actually appear.
**Warning signs:** precision = 1.0 on crowd_distractor.

### Pitfall 5: Missing GPU environment (measurement blocked)
**What goes wrong:** Running the harness from the CPU `.venv` → every gpu-marked test SKIPs, nothing is measured.
**How to avoid:** Run from `venv312` (py3.12 + cu126 torch). Mark the harness `@pytest.mark.gpu`. Measure on AC power (battery throttling inflates latency — project memory `dev-box-perf-on-ac.md`).
**Warning signs:** All tests "skipped"; torch reports CPU-only.

### Pitfall 6: GT sidecar accidentally gitignored
**What goes wrong:** Choosing a `.tags`-style extension that matches the gitignore → GT never committed, corpus-reproducibility lost.
**How to avoid:** `[VERIFIED: .gitignore lines 51-64]` — `tests/fixtures/**` is NOT blanket-ignored; only `*.{mp4,mov,avi,mkv,m4v,webm}` and `*.tags` are ignored (README + `clip_manifest.yaml` negated). A `<clip>.gt.yaml` (or `.gt.json`) is tracked by default. Do NOT reuse the `.tags` extension.
**Warning signs:** `git status` doesn't show the new sidecar.

## GT Sidecar Format (recommended)

Committed next to each clip as `<clip>.gt.yaml` (e.g. `tests/fixtures/disc_dog/distant_01.gt.yaml`). Tracked automatically (Pitfall 6). References the local (gitignored) binary by manifest-relative path — same tracked-metadata/local-binary rule as the manifest.

```yaml
clip: disc_dog/distant_01.mp4     # manifest-relative path (matches clip_manifest.yaml 'file')
condition: distant                # the hard-condition cell this GT covers (for aggregation)
stride: 15                        # ClipFrameSource stride used when labeling — eval MUST reuse it
iou_thr: 0.5                      # the matching threshold these labels were designed for (D-08)
labels:                           # one entry per EMITTED tick that was labeled
  - tick: 0
    bbox: [0.412, 0.508, 0.447, 0.560]   # normalized CORNER [x0, y0, x1, y1], full-frame
  - tick: 1
    bbox: null                    # in-competition dog ABSENT this frame → any detection = FP, no FN
  - tick: 2
    bbox: [0.401, 0.511, 0.436, 0.559]
```

- **Normalized corner coords** (not pixels): resolution-independent and directly IoU-comparable to detector output (convert detector `xywhn` center+wh → corners once).
- **`bbox: null`** is a first-class value = the dog is genuinely not in frame (enables precision measurement on handler-only stretches — D-09).
- `condition` + `stride` + `iou_thr` make each sidecar self-describing so the harness needs no external config to score it.

## Labeling Tool (`tools/label_clips.py`) — recommended shape

Mirror `tools/catalog_clips.py`: dev-only, argparse, opencv lazy-imported inside functions, `segugio` importable via the `src/` sys.path insert. **Never imports `ultralytics`/`torch` (D-05 independence).**

- CLI: `python tools/label_clips.py <clip-relative-path> --stride 15 --out tests/fixtures/<clip>.gt.yaml` (footage path resolved via `fixtures.resolve_clip_path`, never a raw string).
- Decode via `ClipFrameSource(clip, {"full": [0,0,1,1]}, stride=N)`; for each emitted `(tick, {"full": frame})`:
  - `box = cv2.selectROI("label", frame, showCrosshair=True)` → returns `(x, y, w, h)` in **pixels**; ENTER confirms, `c` cancels.
  - Empty selection (`w==0 or h==0`) → `bbox: null` (dog absent / skip).
  - Convert pixel `(x,y,w,h)` → normalized corner `[x/W, y/H, (x+w)/W, (y+h)/H]`.
  - Allow a quit key to stop early and still write what's labeled (a few hundred frames total, D-06 — the operator need not label the whole clip; label a representative window per condition).
- Write the sidecar with `yaml.safe_dump(..., sort_keys=False)`.
- Sampling guidance: pick `stride` so the labeled window yields tens of frames per condition (≈ a few hundred total across 6-8 conditions — D-06). E.g. a 30s 1080p50 slice at stride 15 ≈ 100 emitted frames; label a ~30-50 frame window covering the dog's traversal.

**`cv2.selectROI` notes** `[CITED: docs.opencv.org — cv2.selectROI]`: blocking window, returns a single ROI tuple, ENTER/SPACE confirms, `c` cancels (returns zeros). Perfect for one-box-per-frame; no external service.

## Recall/Precision Harness — recommended shape

New sibling in `eval.py` (below the lazy-import boundary), `@pytest.mark.gpu`-driven from `tests/test_yolo_clips_eval.py`:

```python
def run_detection_eval(clip_path, gt_sidecar, model_cfg, use_fp16=True):
    """Detector recall/precision@IoU0.5 on the SHIPPED FP16 forward vs committed GT. HEAVY."""
    import cv2  # noqa: F401  (boundary parity; decode is via ClipFrameSource)
    import yaml
    from ultralytics import YOLO
    from .detector import resolve_dog_index
    from .frame_source import ClipFrameSource
    # 1. Load GT (safe_load), read stride + per-tick boxes.
    gt = yaml.safe_load(open(gt_sidecar, encoding="utf-8"))
    stride = int(gt["stride"]); labels = {l["tick"]: l["bbox"] for l in gt["labels"]}
    # 2. Load ONE model, resolve dog index BY NAME.
    model = YOLO(str(model_cfg.path))
    dog_idx = resolve_dog_index(model, model_cfg.class_index)
    # 3. Decode full-frame at the SAME stride; score only labeled ticks.
    src = ClipFrameSource(clip_path, {"full": [0.0, 0.0, 1.0, 1.0]}, stride=stride)
    tp = fp = fn = 0
    for tick, crops in src.frames():
        if tick not in labels:
            continue
        frame = crops["full"]
        # SHIPPED FP16 forward — identical kwargs to batched.py step 2.
        res = model.predict(frame, classes=[dog_idx], end2end=False,
                            half=bool(use_fp16), verbose=False)[0]
        det_boxes = _xywhn_to_corners(res)     # convert Results.boxes.xywhn → corner list
        t, f, n = score_frame(labels[tick], det_boxes)   # pure matcher
        tp += t; fp += f; fn += n
    recall = tp / (tp + fn) if (tp + fn) else None
    precision = tp / (tp + fp) if (tp + fp) else None
    return {"tp": tp, "fp": fp, "fn": fn, "recall": recall, "precision": precision,
            "condition": gt.get("condition"), "use_fp16": use_fp16}
```

Aggregate results per condition across the selected clips (`fixtures.select_clips(manifest, "disc_dog", [condition])`). Report a table: condition → recall, precision, TP/FP/FN, n_frames. The **decisive** rows are `distant` and `backlit_dusk`/`dusk_distant` (D-10); the **precision-guard** rows are `handler_prominent` (`crowd_distractor`, `handler_close`, `warm_jump`).

**Conf threshold:** `batched.py` passes no `conf` to `predict`, so the shipped path uses ultralytics' default (`conf=0.25`) `[VERIFIED: codebase, batched.py:128-134 has no conf kwarg]`. Measure at that default to match shipped behavior. Optionally sweep conf as a discretion extra (not required by D-08).

## Corpus Scoping (DET-01)

`[VERIFIED: clip_manifest.yaml]` Current committed disc slices and their tags:
| Clip | Conditions tagged |
|------|-------------------|
| `crowd_distractor_01` | handler_prominent |
| `distant_01` | distant |
| `dusk_distant_01` | distant, backlit_dusk |
| `handler_close_01` | handler_prominent |
| `sprint_blur_01` | jump_sprint_blur |
| `warm_jump_01` | jump_sprint_blur, handler_prominent |
| `gara_full.mp4` | (untagged master — never selected per-condition, by design) |

Disc condition cells still empty (per the 7-condition checklist in `fixtures.CONDITIONS`): **`multi_dog`**, **`midfield_equidistant`**, and `tunnel_contact_occlusion` (predominantly an agility case).
- Per D-03: cut new ~30s disc slices from `gara_full` for `multi_dog` and `midfield_equidistant` (opencv `VideoWriter`, the existing README pattern — no ffmpeg), write `.tags`, re-run `catalog_clips.py`.
- `tunnel_contact_occlusion` for disc: likely absent in disc footage → **carry-forward** (D-02), report as an uncovered cell, do not synthesize.
- Agility discipline: entire column **carried-forward** (D-02). The coverage report (`coverage_report`) already renders `{condition × discipline}`; annotate the agility column as deferred in the coverage artifact.

## Fine-tune Decision Rule & Spec (DET-04)

### Decision rule (D-10 + D-09)
```
distant_recall = min(recall[distant], recall[dusk_distant])   # decisive wide-cam case
IF distant_recall < 0.70 (tunable default):
    → GO (fine-tune), UNLESS precision on handler_prominent conditions is already so weak
      that fine-tuning for recall would be premature (note it; still a documented rule).
ELSE:
    → NO-GO (COCO 'dog' is defensible on real footage — D-12, a first-class outcome).
PRECISION GUARD (D-09): the decision doc records baseline precision on the false-lock
  conditions (handler_prominent) so a future fine-tune can be held to "recall up, precision
  not regressed."
```
The 0.70 threshold is the captured default; the doc states the measured `distant_recall` against it so the decision is a rule, not a vibe.

### Decision doc structure (deliverable, D-11)
Recommend a markdown artifact under the phase dir (e.g. `19-DECISION.md` or a section in the SUMMARY). Contents:
1. **Method** — clips + conditions labeled, frame counts, stride, IoU 0.5, FP16 batched forward, conf default, `venv312`/GPU/AC note.
2. **Results table** — per-condition recall/precision/TP-FP-FN.
3. **P04 delta caveat** — explicit statement that these (FP16 + GT recall/precision) are NOT comparable to P04's eager-FP32 `lock_held` 0.035 distant / 0.155 crowd proxy.
4. **Decision** — GO/NO-GO with the measured `distant_recall` vs threshold + the precision-guard baseline.
5. **Coverage caveats** — agility carried-forward; any uncovered disc cells.

### Fine-tune spec (only if "go")
Must preserve the drop-in contract and dog-by-name rule:
- **Drop-in contract:** the fine-tuned weight ships via `ModelConfig.path` (CFG-04) with ZERO code change `[VERIFIED: codebase — eval/loop pass model_cfg.path to YOLO()]`. `resolve_dog_index` resolves the class BY NAME, so a mono-class weight (dog=index 0) or a multi-class weight both work — the spec must require the weight to expose a class literally named `"dog"`.
- **Dataset/approach:** auto-label owner `gara_full` footage with a LARGER model (e.g. `yolo26m`/`yolo11x`) as a pre-labeler + Roboflow dog sets (CLAUDE.md "Datasets") + human correction. Note the D-05 caveat: auto-labeling is acceptable for the *training* set (it is corrected and is not the thing being measured) but NEVER for the *eval* GT (which stays hand-labeled and detector-independent).
- **Base + task:** fine-tune `yolo26s` from COCO-pretrained; emphasize distant/small + backlit/dusk dog crops (the measured weak spot). Keep the Ultralytics `YOLO(...).train(...)` API (locked stack).
- **Validation:** re-run THIS Phase-19 recall/precision harness on a held-out labeled subset; success = `distant_recall ≥ threshold` AND handler-prominent precision not regressed vs baseline.
- **Boundary:** training + weight production is a SEPARATE later effort (D-11) — the spec is a document, not executed here.

## Code Examples

### Convert detector `Results` → normalized corner boxes (for IoU)
```python
# Source: Ultralytics Results.boxes.xywhn (crop-normalized center+wh) — see signals_map.py docstring.
def _xywhn_to_corners(results, conf_min=0.0):
    boxes = getattr(results, "boxes", None)
    if boxes is None or getattr(boxes, "xywhn", None) is None:
        return []
    xywhn = boxes.xywhn.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    out = []
    for (cx, cy, w, h), c in zip(xywhn, confs):
        if c < conf_min:
            continue
        out.append([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
    return out
```

### The exact shipped detection forward (mirror of `batched.py:128-134`)
```python
# Source: src/segugio/tracking/batched.py:128-134 (the ONE shipped detection forward).
res = model.predict(frame, classes=[int(dog_idx)], end2end=False,
                    half=bool(use_fp16), verbose=False)[0]
```

## State of the Art

| Old Approach (P04) | Current Approach (Phase 19) | When Changed | Impact |
|--------------------|-----------------------------|--------------|--------|
| Eager FP32 serial `model.track()` | FP16 batched `model.predict()` | Phase 6 (Wave-B batched path shipped) | Must measure on the path that ships; FP16 may shift small/low-light recall either way |
| `lock_held_fraction` proxy | True recall/precision@IoU0.5 vs hand-labeled GT | Phase 19 | A defensible detector metric, not a proxy |
| Assumed "distant dog is weak" (0.035 lock_held) | Measured raw detector recall on the shipped path | Phase 19 | Turns a vibe into a rule-based go/no-go |

**Deprecated/outdated for THIS phase:** none — the stack is current (YOLO26 SOTA Jan 2026, BoT-SORT native ReID). No package is stale.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The shipped path uses ultralytics' default `conf≈0.25` (no `conf` kwarg in `batched.py`) so recall/precision should be measured there | Harness / conf threshold | If the live config sets a different conf elsewhere, the measured numbers use the wrong operating point. LOW — verified `batched.py` passes no conf; but confirm no conf is injected via model defaults/config. |
| A2 | `cv2.selectROI` behaves as a blocking single-ROI drag with ENTER-confirm / `c`-cancel in the installed opencv build | Labeling tool | If the build/headless opencv lacks HighGUI, `selectROI` fails; fallback = custom `setMouseCallback`. Verify `cv2.selectROI` works interactively in `venv312` before building the tool. |
| A3 | The fine-tune decision should be on RAW detector recall (not BoT-SORT-confirmed) | Open Question 1 / harness | If the planner/operator wants "what the lock actually receives," add tracker-confirmed recall as a secondary metric. This is a documented modelling choice, not a fact. |
| A4 | 0.70 distant-recall threshold is the operator's starting default (tunable) | Decision rule | Explicitly tunable per D-10 — not a hard fact; the doc states measured value vs threshold. |
| A5 | `gara_full` contains harvestable `multi_dog` / `midfield_equidistant` disc moments to cut new slices | Corpus scoping | If those moments don't exist in the ~10h footage, those disc cells also carry-forward. Confirm by scrubbing the footage before committing to cutting slices. |

## Open Questions

1. **Raw-detection recall vs tracker-confirmed recall.**
   - What we know: DET-04 is a DETECTOR fine-tune decision; fine-tuning changes detection, and BoT-SORT thresholds are separately tuned in Phase 20 (CAL-02). `batched_detect_dispatch` returns confirmed tracks.
   - What's unclear: whether the operator also wants the tracker-confirmed number (what the lock consumes) reported.
   - Recommendation: primary metric = **raw detector recall/precision** (measured on the FP16 `predict` boxes). Optionally report tracker-confirmed recall as a clearly-labelled secondary line. Flag in the decision doc.

2. **Extend `run_clip_eval` vs new sibling `run_detection_eval` (D-08 discretion).**
   - What we know: `run_clip_eval` is eager+crop+track+overlay; the recall/precision shape is full-frame+raw-detect+GT.
   - Recommendation: **new sibling** — cleaner separation, preserves the existing D-08 regression net, and matches the "pure metric above / heavy driver below" pattern. (Planner decides.)

3. **How many frames / which window per clip (D-06).**
   - What we know: ~a few hundred total, statistically meaningful, not exhaustive.
   - Recommendation: label a contiguous ~30-50-frame window per condition where the in-competition dog traverses the decisive region (distant/backlit). Record actual counts in the decision doc's Method section.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| CUDA GPU + `venv312` (py3.12) | The `@pytest.mark.gpu` recall/precision harness | ✓ (dev box, RTX 4000 Ada) | py3.12 + cu126 torch + tensorrt-cu12 | None — CPU `.venv` SKIPs gpu, nothing measurable |
| `ultralytics` + `yolo26s.pt` | Detection forward | ✓ (venv312) | YOLO26-aware `ultralytics` | None (locked) |
| `opencv-python` (`cv2` incl. HighGUI/`selectROI`) | Labeling tool, decode | ✓ (venv312) | installed | Custom `setMouseCallback` if `selectROI`/HighGUI unavailable (A2) |
| Owner footage (`gara_full.mp4` + slices) | All eval | ✓ local (gitignored) | 1080p50 | None — `FixtureNotPresentError` SKIPs cleanly |
| `pyyaml`, `numpy`, `loguru`, `pytest` | GT I/O, metrics, harness | ✓ | installed | None (locked) |

**Missing dependencies with no fallback:** none identified — all present on the dev box.
**Operational note:** measure on **AC power** (battery throttles and inflates latency/timing — project memory `dev-box-perf-on-ac.md`). Latency is not the DET-03 metric (that's RIG-03), but any timing captured incidentally must note AC.

## Validation Architecture

nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (with a custom `gpu` marker gated by `conftest_tracking`) |
| Config file | repo `pyproject.toml` / `conftest.py` (gpu-marker gate) |
| Quick run command | `pytest -m "not gpu" -q` (CPU: pure IoU/matcher + GT-parse unit tests) |
| Full suite command | `venv312\Scripts\python.exe -m pytest tests/test_yolo_clips_eval.py -m gpu` (GPU harness, from `venv312`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | New disc slices catalogued; coverage matrix reflects disc cells + agility carry-forward | unit (CPU) | `pytest tests/test_fixtures*.py -q` (extend for new slices) | ⚠️ extend existing |
| DET-02 | GT sidecar parses; label-tool writes valid normalized-corner YAML | unit (CPU) | `pytest tests/test_detection_gt.py -q` | ❌ Wave 0 |
| DET-02 | `iou()` + `score_frame()` correct (TP/FP/FN, null-GT, no-detect) | unit (CPU) | `pytest tests/test_detection_metrics.py -q` | ❌ Wave 0 |
| DET-03 | `run_detection_eval` runs the FP16 `predict` forward and returns recall/precision on a real slice | gpu | `pytest tests/test_yolo_clips_eval.py::test_detection_recall_precision -m gpu` (venv312) | ❌ Wave 0 (extend skeleton) |
| DET-04 | Decision doc exists, applies the D-10 rule, states P04-delta caveat | manual review | (doc review — not automatable) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -m "not gpu" -q` (pure metric + GT-parse units — fast, CPU).
- **Per wave merge:** the gpu harness from `venv312` on one real slice (proves the forward + metric end-to-end).
- **Phase gate:** full CPU suite green; gpu harness run + numbers captured into the decision doc before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_detection_metrics.py` — pure `iou`/`score_frame` (TP/FP/FN, null-GT precision, empty-detection FN) — covers DET-02/03 metric correctness
- [ ] `tests/test_detection_gt.py` — GT sidecar round-trip (safe_dump/safe_load, normalized-corner bounds, `bbox: null`) — covers DET-02
- [ ] Extend `tests/test_yolo_clips_eval.py` — add `test_detection_recall_precision` (`@pytest.mark.gpu`) asserting recall/precision keys + FP16 forward — covers DET-03
- [ ] `tools/label_clips.py` — the labeling tool (dev; a headless smoke test can exercise the pixel→normalized conversion + YAML write without a GUI)
- [ ] Framework install: none (pytest already configured)

## Security Domain

`security_enforcement` absent in config → treated as enabled. This is a **dev-only, local-footage, offline eval** with no network, no auth, no live-scoring surface. Attack surface is minimal.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | dev tool, no auth surface |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Clip paths via `resolve_clip_path` (traversal-guarded, `[VERIFIED: fixtures.py:190-215]`); GT sidecar via `yaml.safe_load` only |
| V6 Cryptography | no | no secrets/crypto in this phase |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via clip path / `--out` | Tampering | Resolve clip paths through `fixtures.resolve_clip_path`; keep the label-tool `--out` under `tests/fixtures/` |
| Unsafe YAML deserialization of a GT sidecar | Tampering / RCE | `yaml.safe_load` ONLY (never `yaml.load`) — the established `fixtures.py`/`catalog_clips.py` pattern |
| Redistributing copyrighted footage via git | Information disclosure | GT sidecars are tracked but reference gitignored binaries; footage stays local (README contract, `[VERIFIED: .gitignore]`) |

## Sources

### Primary (HIGH confidence — read directly this session)
- `src/segugio/tracking/eval.py` — `compute_metrics` (pure), `run_clip_eval` (eager FP32 `track()` at :296/:321), lazy-import boundary, `_arrays_from_results`
- `src/segugio/tracking/batched.py` — the shipped FP16 forward (`model.predict(..., end2end=False, half=use_fp16, classes=[dog_idx])`, :128-134)
- `src/segugio/tracking/detector.py` — `PerCameraTracker` (`use_fp16` default False), `resolve_dog_index` (dog BY NAME), `ensure_native_feats`, `update`
- `src/segugio/tracking/frame_source.py` — `ClipFrameSource` (stride, emitted-tick indexing, full-frame crop)
- `src/segugio/orchestrator/loop.py` — `_batched_inference` (:399-428), `_supports_batched`, `_serial_inference` (production reference for the shipped path)
- `src/segugio/fixtures.py` — `select_clips`, `coverage_report`, `resolve_clip_path`, `FixtureNotPresentError`, `CONDITIONS`
- `src/segugio/tracking/signals_map.py` + `framing/signals.py` — `DetectionSignal` fields, `xywhn` normalization
- `tools/catalog_clips.py` — opencv-only dev-tool pattern (argparse, lazy cv2, `.tags` reader)
- `tests/test_yolo_clips_eval.py`, `tests/test_batched_detect.py` — gpu-gated eval skeleton + headless dispatch-shape precedent
- `tests/fixtures/README.md`, `clip_manifest.yaml`, `clip_manifest.example.yaml` — corpus contract + schema
- `.gitignore` (lines 51-64) — `.tags` + video extensions ignored; README/manifest negated; `.gt.yaml` tracked by default
- `trackers/botsort_dog.yaml` — thresholds (`track_high_thresh:0.25`, native ReID)
- `.planning/config.json` — nyquist_validation on, commit_docs on
- `docs/run.md` — `venv312` (py3.12 + cu126) GPU env; gpu-marker SKIP on CPU `.venv`

### Secondary (MEDIUM confidence)
- `CLAUDE.md` — locked stack (YOLO26, BoT-SORT native ReID, COCO dog=16 by NAME, datasets for fine-tune), latency budget <300ms p95
- Project memory — `dev-box-perf-on-ac.md`, `gpu-torch-cpu-only-py314.md`, `batched-reid-detection-regression.md`

### Tertiary (LOW confidence)
- `cv2.selectROI` interactive behavior (A2) — CITED from opencv docs, not exercised in this session on `venv312`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all deps read as already-imported in the repo
- Architecture / seams: HIGH — every file-level seam (eager vs batched, ClipFrameSource, fixtures, resolve_dog_index) read directly
- Pitfalls: HIGH — derived from the actual code paths (eager `track()`, stride indexing, tracker-confirmed vs raw)
- GT format / labeling tool: MEDIUM-HIGH — format is a clean recommendation grounded in gitignore + manifest conventions; `selectROI` behavior is CITED (A2 to verify)
- Fine-tune spec: MEDIUM — decision rule is locked (D-10); training approach is CITED from CLAUDE.md datasets, not executed

**Research date:** 2026-07-14
**Valid until:** 2026-08-13 (30 days — stable; the only volatile item is the `venv312` GPU availability and `yolo26s.pt` resolution, which should be re-confirmed at execution)

## RESEARCH COMPLETE

**Phase:** 19 - Detection Eval on Real Footage & Fine-tune Decision
**Confidence:** HIGH

### Key Findings
- **`run_clip_eval` runs the EAGER FP32 serial `track()` path today** (`eval.py:296/:321`), NOT the batched FP16 shipped path. DET-03 requires rewiring onto `batched.py`'s forward (`model.predict(..., end2end=False, half=True, classes=[dog_idx])`, the exact call `loop._batched_inference` ships). Recommend a NEW sibling `run_detection_eval` rather than mutating `run_clip_eval`.
- **Measure recall/precision on RAW detector output, not BoT-SORT-confirmed tracks** — DET-04 is a detector decision; tracker thresholds are Phase-20 (CAL-02) territory. Flagged as Open Question 1.
- **Frame alignment is the correctness lynchpin:** key the GT sidecar by `ClipFrameSource` emitted `tick` and store `stride`; both the label tool and the eval reuse `ClipFrameSource` at that stride on a single full-frame "camera" `{"full":[0,0,1,1]}`. No `cv2.set` seeking.
- **GT sidecar `<clip>.gt.yaml` is tracked by default** — `.gitignore` only ignores video extensions + `.tags`; do NOT reuse `.tags`. Format: normalized corner boxes, `bbox: null` = dog-absent (enables D-09 precision).
- **~90% of the plumbing already exists** (fixtures query, decode, resolve-dog-by-name, batched forward, gpu skeleton). New code is small: `tools/label_clips.py` (opencv `selectROI`), a pure IoU/matcher module, one gpu driver, a decision doc. No new packages.

### File Created
`.planning/phases/19-detection-eval-on-real-footage-fine-tune-decision/19-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | No new packages; deps verified as already imported |
| Architecture / seams | HIGH | Eager-vs-batched, ClipFrameSource, fixtures all read directly |
| Pitfalls | HIGH | Derived from actual code paths |
| GT format / labeling | MEDIUM-HIGH | Format grounded in gitignore+manifest; `selectROI` behavior CITED (A2) |
| Fine-tune spec | MEDIUM | Rule locked (D-10); training approach CITED, not executed |

### Open Questions
1. Raw-detection recall vs tracker-confirmed recall as the primary metric (recommend raw; optional secondary).
2. Extend `run_clip_eval` vs new sibling (recommend sibling).
3. Frame count / labeling window per clip (recommend ~30-50-frame window per condition).

### Ready for Planning
Research complete. The planner can create PLAN.md files: Wave 0 test scaffolding (pure IoU/matcher + GT round-trip), the labeling tool, the corpus slices, the FP16 recall/precision harness, and the decision doc.
