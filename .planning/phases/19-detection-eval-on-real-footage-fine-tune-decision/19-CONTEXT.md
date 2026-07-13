# Phase 19: Detection Eval on Real Footage & Fine-tune Decision - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Measure the SHIPPED detector's real recall AND precision on the hard field conditions, then make a motivated `yolo26s` fine-tune go/no-go decision. Desk work on the dev box (CUDA GPU via `venv312`), against real disc-dog footage the owner already holds. This phase produces the **measurement + the decision + a fine-tune spec if "go"** — it does NOT run the training or ship a fine-tuned weight.

Requirements: DET-01, DET-02, DET-03, DET-04.

**Scope narrowing decided in discussion:** the eval is **disc-only for v1.4**. The committed corpus is owner disc footage (FIDASC `gara_full.mp4` + per-condition cuts); there is no real agility footage and no `midfield_equidistant`/`tunnel_contact_occlusion` agility coverage. Agility eval is **explicitly deferred** to a future milestone/phase when real agility footage exists (see Deferred Ideas). DET-01's "disc AND agility" is therefore satisfied as **disc across the hard conditions**, with agility carried forward — the planner should scope DET-01/DET-03 to disc and note the agility carry-forward, not synthesize fake agility coverage.
</domain>

<decisions>
## Implementation Decisions

### Footage source & corpus scope (DET-01)
- **D-01:** Eval runs on the owner's real **disc** footage only for v1.4 — `gara_full.mp4` (FIDASC, single fixed cam, ~10h, 1080p50) plus the existing ~30s per-condition cuts (`sprint_blur`, `handler_close`, `distant`, `crowd_distractor`, `warm_jump`, `dusk_distant`). No CC0 supplementation needed for disc.
- **D-02:** **Agility is deferred, not sourced.** Do NOT pull CC0 agility clips to fake coverage. The condition matrix for v1.4 covers the disc-reachable cells; agility cells (esp. `tunnel_contact_occlusion`, `midfield_equidistant` on agility) are marked carried-forward in the coverage report, not filled.
- **D-03:** The existing corpus infrastructure is reused as-is — `tools/catalog_clips.py`, the `<clip>.tags` sidecar convention, `clip_manifest.yaml`, and `segugio.fixtures.select_clips`/`coverage_report`. If `gara_full.mp4` lacks a hard condition (e.g. `multi_dog`, `midfield_equidistant`), cut a new ~30s disc slice from it and tag it, rather than importing outside footage.

### Ground-truth labeling approach (DET-02)
- **D-04:** Build a **lightweight internal bbox-labeling tool** — zero external dependencies (no CVAT/Roboflow, no SAM/auto-label), consistent with the project's no-heavy-runtime-dep constraint. It samples frames **sparsely** (every N-th frame per clip), lets the operator draw/confirm the in-competition dog bbox, and writes ground-truth in a simple committed format (per-clip GT sidecar, opencv-decoded — mirrors the `catalog_clips.py` opencv-only pattern).
- **D-05:** **Rejected auto-labeling** (pre-labeling with a big YOLO/SAM then correcting) — it risks inheriting the exact distant-dog miss bias this eval is trying to measure. Ground-truth must be independent of the detector under test.
- **D-06:** Label **~a few hundred frames total**, sampled to cover each hard condition (not a dense per-frame label of `gara_full`). Volume is "enough to make per-condition recall/precision statistically meaningful," not exhaustive.
- **D-07:** "In-competition dog" definition = the single subject the **competitor-lock** is meant to grab (zone ∧ motion, the dog actually running the course/routine) — NOT bystander dogs, NOT the handler. When multiple dogs are present, only the in-competition dog gets a GT box; other dogs are ignored (they are what precision must NOT false-lock onto).

### Metrics & fine-tune threshold (DET-03/DET-04)
- **D-08:** Report **recall AND precision per condition** at **IoU 0.5**, measured on the **FP16 batched shipped path** (`segugio.tracking.batched`), NOT the eager FP32 serial `track()` the P04 UAT used, and NOT the `lock_held_fraction` proxy the current `run_clip_eval` returns. The existing `run_clip_eval` must be **extended** to consume the GT sidecars and emit true recall/precision alongside (or replacing) the proxy. **Research/planner MUST first confirm whether today's `run_clip_eval` runs the batched shipped path or the per-camera eager path — if eager, wire the eval onto `batched.py` so the measurement reflects what actually ships.**
- **D-09:** Precision matters specifically as a **false-lock guard** — count detections that land on the handler / a shadow / a bystander dog. A fine-tune that lifts distant recall must not regress this.
- **D-10:** **Fine-tune trigger rule = absolute distant-dog recall with a precision guard.** Starting threshold: **distant-dog recall@IoU0.5 < 0.70 → fine-tune** (the `distant`/`dusk_distant` conditions are the decisive wide-cam case). The exact 0.70 number is **tunable** — captured here as the default; the operator can move it once the real numbers land. The decision is a rule, not a vibe: the eval report states the measured distant recall against the threshold.

### Fine-tune boundary (DET-04)
- **D-11:** Phase 19 **stops at the go/no-go decision + a fine-tune spec if "go".** It does NOT run the training or produce a weight. Deliverable = a written, metrics-backed decision doc; if "go," it also specifies the dataset/approach (e.g. auto-label owner footage + Roboflow dog sets) so a later effort can execute the training. This keeps the phase desk-sized and matches the roadmap wording ("decision documented" + "drop-in via config `path`").
- **D-12:** If the decision is "no-go" (COCO `dog` recall is good enough), that is a valid, first-class outcome — the deliverable is the evidence that shipping COCO `dog` as-is is defensible on real footage.

### Claude's Discretion
- The exact sampling stride N, the GT sidecar file format, and the labeling-tool UX (as long as it's opencv-only, no external service, and produces a committed, re-readable GT format).
- Whether recall/precision are added to `run_clip_eval`'s return dict or a new sibling eval function — the planner picks the cleaner seam.
- The precise structure of the decision doc / report artifact.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 19" — goal, success criteria, dependency notes.
- `.planning/REQUIREMENTS.md` — DET-01..04 full text + the v2 PRED/POSE deferrals.

### Existing eval & corpus infrastructure (reuse/extend — do NOT rebuild)
- `tests/fixtures/README.md` — the corpus contract: condition checklist (`multi_dog`, `handler_prominent`, `tunnel_contact_occlusion`, `jump_sprint_blur`, `distant`, `backlit_dusk`, `midfield_equidistant`), drop-location convention, `.tags` sidecars, ingest procedure, license/consent table.
- `tools/catalog_clips.py` — the opencv-only cataloguer that writes `clip_manifest.yaml`.
- `tests/fixtures/clip_manifest.yaml` + `clip_manifest.example.yaml` — the manifest schema.
- `src/segugio/fixtures/` (`select_clips`, `coverage_report`, `resolve_clip_path`, `FixtureNotPresentError`) — the committed-manifest query API.
- `src/segugio/tracking/eval.py` — `run_clip_eval` (line ~230): the current eval returning the `lock_held_fraction` proxy + `id_switch_count`/`coast_count`; the extension target for real recall/precision.
- `src/segugio/tracking/batched.py` — the **FP16 batched shipped detect path** DET-03 must measure on.
- `src/segugio/tracking/frame_source.py` — `ClipFrameSource` (opencv decode → per-camera crops).
- `src/segugio/tracking/detector.py` — `PerCameraTracker`, `resolve_dog_index` (dog class resolved BY NAME from `model.names`, CFG-04).
- `tests/test_yolo_clips_eval.py` — the `@pytest.mark.gpu` eval skeleton (D-08 metrics keys, GPU-gated); `tests/test_batched_detect.py`, `tests/test_latency.py` (item-1 fix drove the latency harness with real dog frames — precedent for real-frame GPU harness).

### Domain research (already in-repo — read the relevant rows)
- `CLAUDE.md` → "Detection model" + "Datasets & Test Fixtures" + "What NOT to Use" (COCO `dog`=16 verified; `yolo26s` v1 default; Pexels/Pixabay/`yt-dlp` sourcing; fine-tune only after eval proves COCO misses).
- `.planning/research/STACK.md` → "Datasets & Test Fixtures" (if present) — CC0 sourcing detail (only relevant later, agility deferred).

### Environment
- `docs/run.md` — GPU work runs from `venv312/` (py3.12 + cu126 torch + tensorrt-cu12). The py3.14 `.venv` is CPU-only and SKIPs `-m gpu`.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_clip_eval` (`tracking/eval.py`) already wires decode→crop→track→lock→signal + writes a debug-overlay `.mp4` and returns a per-camera metrics dict — extend it to compute GT-based recall/precision rather than building a new pipeline.
- `segugio.fixtures.select_clips` / `coverage_report` — query clips by condition+discipline from the committed manifest; the coverage matrix already models `{condition × discipline}` cells (use it to show which cells are covered vs agility-deferred).
- `tools/catalog_clips.py` — opencv-only metadata probe + `.tags` reader; the labeling tool should mirror its opencv-only, argument-driven-path style.
- `ClipFrameSource` — the existing clip→frame decoder the labeling sampler and the eval both build on.

### Established Patterns
- **opencv-only, no ffmpeg/ffprobe, no external services** — the corpus tooling constraint the new labeling tool must honor.
- **Footage stays local & un-committed; only manifest + GT sidecars + README are tracked** — `tests/fixtures/**` is gitignored with README/manifest negated back in. GT sidecars must follow the same tracked-vs-local rule (GT metadata tracked; it references local binaries).
- **GPU tests are `@pytest.mark.gpu`, SKIPped off the CUDA box** — the new recall/precision measurement is a GPU-gated harness run from `venv312`, not CI-default.
- **Dog class resolved BY NAME** from `model.names` (never hardcode 16 on a custom weight) — matters if a fine-tuned mono-class weight is later dropped in (DET-04 spec must note this).

### Integration Points
- Manifest/coverage (`fixtures`) → eval clip selection → `run_clip_eval` (batched detect) → GT sidecars → recall/precision report → decision doc.
- The decided-upon fine-tune weight (if "go", later) drops in via the config `path` key (`ModelConfig.path`, CFG-04) with zero code change — the spec must preserve that contract.
</code_context>

<specifics>
## Specific Ideas

- The `distant` and `dusk_distant` conditions are the decisive cases — the measured weak spot (04-HUMAN-UAT: `lock_held` 0.035 distant, 0.155 crowd on the eager FP32 path). The whole point of DET-03 is to re-measure this on the batched FP16 shipped path with real recall/precision, because FP16 may shift small/low-light recall either way.
- The eval report should make the P04-vs-shipped delta explicit: prior numbers were eager FP32 serial + `lock_held` proxy; these are batched FP16 + GT recall/precision. Don't compare them as if apples-to-apples.
</specifics>

<deferred>
## Deferred Ideas

- **Agility detection eval** (tunnel/contact occlusion, midfield-equidistant, agility multi-dog) — deferred until real agility footage with consent exists. Belongs in a future milestone/phase; the coverage report flags these cells as carried-forward, not filled. This is a scope reduction of DET-01/DET-03 agreed in discussion — update REQUIREMENTS.md/ROADMAP.md notes accordingly at plan/verify time.
- **Running the actual fine-tune training + shipping a fine-tuned weight** — deferred to a follow-up effort gated on a "go" decision from this phase (D-11). If "go," this phase produces the spec; a later phase/effort executes it.
- **CC0 (Pexels/Pixabay/`yt-dlp` CC) footage sourcing** — not needed for disc v1.4; relevant only when the deferred agility eval is picked up.
- **Framing/tracking seed calibration on the real footage** — that is Phase 20 (CAL-01/02), which depends on this phase's detector outcome. Keep seed-tuning out of Phase 19.

### Reviewed Todos (not folded)
None — the 2 pending security todos match Phase 21, not this phase.
</deferred>

---

*Phase: 19-detection-eval-on-real-footage-fine-tune-decision*
*Context gathered: 2026-07-14*
