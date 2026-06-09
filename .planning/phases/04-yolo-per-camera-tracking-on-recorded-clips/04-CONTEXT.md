# Phase 4: YOLO + Per-Camera Tracking on Recorded Clips - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 wires a **pre-trained YOLO model on CUDA** with **one BoT-SORT tracker per camera (native-feature ReID)** over recorded clips run as pseudo-cameras, and turns each frame into the **normalized per-detection signals** the Phase-2 scorer already expects — plus a **robustly selected competitor track** (the dominant project risk, proven in software). Delivers TRK-01..05.

- Pre-trained YOLO on CUDA, **one `model.track(persist=True)` per camera** (never a frame-list, #13107), class filtered to `dog` resolved by **name** from `model.names` at startup (TRK-01)
- BoT-SORT with **native ReID** (`with_reid: True, model: auto`) + extended `track_buffer`; **startup verifies native ReID actually engaged** and logs confirmation, never silently falls back to a downloaded model (TRK-02)
- Per-frame normalized signals (`cx/cy, w/h, conf, track_id`) filtered to the dog class, mapping unchanged into the existing frozen `DetectionSignal` (TRK-03)
- **Competitor-lock**: pick the in-competition dog over handler's dog / bystander dogs — not the largest/most-central blob (TRK-04)
- **Plausibility gate**: reject implausible track switches (teleport / size-jump) on the locked track (TRK-05)
- Exercised on the curated multi-condition clips, demonstrating subject continuity through frame-exit/re-entry

**NOT in this phase:**
- **No FSM / switching** — that is the Phase-3 engine (already built). Phase 4 produces `DetectionSignal`s; it does not decide which camera is live.
- **No NDI / OBS / orchestrator / watchdog** — Phase 5. Phase 4 reads clips directly (opencv), not via NDI.
- **No wiring of detection signals into the live loop** (frame→YOLO→score→FSM→OBS) — Phase 5 integration. Phase 4 ends at "emits the per-camera locked-subject `DetectionSignal` stream" + an offline eval over clips.
- **No detection-in-occlusion-zone → FSM `occlusion_hold` wiring** — deferred to Phase 5 (the orchestrator wires signals into the FSM hold inputs).
- **No disc/frisbee detection, no pose, no custom/fine-tuned dog model** — v2.
- **No numeric threshold tuning as a deliverable** — seeds live in config; calibration is opportunistic on clips, not a gate.

</domain>

<decisions>
## Implementation Decisions

### Pseudo-cameras from the available footage (TRK-01)
- **D-01: Spatial crops of the wide shot.** The committed corpus is **single-camera, disc-dog only** — one FIDASC clip (`gara_full.mp4`, 1080p**50**) cut into ~30s condition slices. Build the "N cameras" by cropping the 1080p wide clip into **overlapping windows** (e.g. left / center / right) → genuinely *simultaneous* different framings of the **same dog at the same instant**. This gives real per-camera pixel isolation, a realistic multi-camera interface for Phase 5 to plug into, and — for free — **frame-exit/re-entry** (the dog leaves a crop and reappears), which is exactly what `track_buffer: 60` + native ReID exist to survive. Some crops naturally won't contain the dog (a realistic "this camera doesn't see it" case). No real parallax — accepted (the only way to get same-scene multi-view from one fixed cam).
- **D-02: Validate disc-dog now; flag the gaps, no fake footage.** Run TRK-01..05 fully on the available disc-dog slices (`handler_close_01` + `crowd_distractor_01` give a prominent handler/bystander context for competitor-lock; crops give re-entry; `sprint_blur` for blur; `distant`/`dusk_distant` for small/low-light recall). **Explicitly log as UNVERIFIED**: agility-tunnel-occlusion and a clean *two-similar-dogs-crossing* swap — the corpus has neither. The code paths still exist; they are simply not clip-proven in Phase 4. Revisit when real agility / multi-dog footage is provided. **Do not** pull random CC0 stock to paper over the checklist.

### Competitor-lock (TRK-04) — the dominant project risk
- **D-03: Signals = zone-gate AND motion-energy.** A candidate dog track must be (a) inside the field/course zones (the config normalized-rect zones) **and** (b) have the most cumulative motion over a short window. Zone excludes ringside/adjacent-ring/crowd dogs; motion excludes a standing/waiting dog or a calm dog at the start line. Because the detector filters to the **dog class only**, persons/handlers are never candidates — competitor-lock only disambiguates *among dog tracks*. **Autonomous** — no manual run-start signal exists on clips (that is SCR-03, Phase 5), so acquisition runs on zone+motion alone.
- **D-04: Sticky continuity; re-acquire only on loss.** Once locked to a track ID, **keep it while alive** — prefer continuity over per-frame score (PITFALLS Pitfall 2). Re-run the zone+motion selection **only** when the locked track is genuinely lost (`track_buffer: 60` expired) or the plausibility gate flags a swap. This is what prevents ping-ponging the lock between dogs mid-run. (Do **not** re-pick the best candidate every tick.)
- **D-05: Per-camera, independent lock (derived from scope).** Each camera independently locks its own in-field/most-active dog. A *global* cross-camera "this is THE dog" identity would require cross-camera ReID, which PROJECT explicitly defers as "heavy ReID." Cross-camera agreement is **emergent** (it's the same dog), not enforced.

### Plausibility gate (TRK-05)
- **D-06: Hold the locked track, mark "uncertain" → coast.** When the locked track teleports or size-jumps (a likely ID swap), **reject the suspect box** — do not trust it. Mark the subject `uncertain` and emit the **coast path** (no `DetectionSignal` this tick → the scorer's existing FRM-05 coast/TTL holds the last EMA; the FSM does not cut on a suspect track). Re-acquire (zone+motion) only after a genuine loss. The gate's thresholds (`max_displacement_per_tick`, `max_size_ratio`) are **config seeds**.
- **D-07: TRK-05 is a NEW inter-frame gate, distinct from the Phase-2 detection guard.** Phase 2 already ships an *intra-frame* per-detection plausibility guard (conf-floor / min-area / aspect — "is this box a plausible dog at all"). TRK-05 is the *inter-frame track-continuity* gate ("is this the same dog as last frame"). They are different concepts — do not conflate. Add the new seeds additively to config (same pattern Phase 2 used for `ScorerParams`); exact sub-model placement is the planner's call.

### Verification & deliverable
- **D-08: Both debug-overlay video AND logged metrics.** Render boxes / track IDs / locked-subject highlight / zone overlays over each clip to **eyeball** (an auto-director's correctness is ultimately visual), **plus** log per-clip metrics as a regression net: locked-subject **ID-switch count**, **% frames lock-held**, **coast/uncertain counts**, and a signal dump. Human judgment establishes correctness; metrics catch regressions.
- **D-09: Split test architecture — pure-logic deterministic + GPU-gated integration.** The **competitor-lock and plausibility-gate LOGIC** is tested on **synthetic track/detection inputs** — deterministic, CPU-only, reusing `synth` + `conftest`, exactly like the Phase-2 scorer and Phase-3 FSM. The **real YOLO-on-clips** path is a **separate GPU-gated eval run** (e.g. `@pytest.mark.gpu`, skipped when no CUDA or no weights). This keeps the "brain" unit-testable on any box and isolates heavy I/O at the edge (consistent with the lazy-import boundary). YOLO inference is GPU/weights-dependent and is **not** expected to run in normal CPU CI.

### Claude's Discretion (planner/research decide the details)
- **Module layout** — likely a new `src/segugio/tracking/` package (detector wrapper + per-camera tracker manager + competitor-lock/subject-selector + plausibility gate + a clip/crop frame source). Exact shape is the planner's call; honor the lazy-import boundary (no `torch`/`ultralytics`/`cv2` at the package top level so `import segugio.tracking` works CPU-only / heavy-deps-absent).
- **`botsort_dog.yaml` location** — the custom tracker YAML must live where Ultralytics `check_yaml` finds it (a `trackers/` dir or an absolute path). Planner's call; the override values are already specified in STACK.md.
- **50fps vs ~30Hz tick** — the footage is 1080p**50** but the AI tick is ~30 Hz. Whether to stride/sample frames to ~30 fps or decode every frame is the planner's call; keep `tick` an injected frame index (no wall-clock), consistent with the determinism convention.
- **Crop window geometry** — number of crops, overlap, and aspect are the planner's call; map each crop to a `cam_id` and the per-camera config zones.
- **Motion-energy / zone-gate exact formulation** — cumulative displacement window length, in-zone test (center-in-rect vs IoU), and how the two combine into a single "competitor score" are the planner's call. Principle locked (zone AND motion, sticky); constants are config seeds.
- **`model.names` class resolution** — map `dog` by **name** → index at startup; warn/fail if the configured `class_index` disagrees with the resolved index (custom mono-class model ≈ 0, not COCO 16).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-4 scope & requirements
- `.planning/ROADMAP.md` §"Phase 4: YOLO + Per-Camera Tracking on Recorded Clips" — goal, the 5 success criteria, and the 4 plan stubs (04-01 YOLO load + class resolution + per-camera trackers · 04-02 `botsort_dog.yaml` native-ReID + startup verification · 04-03 normalized signal extraction · 04-04 competitor-lock + plausibility gate).
- `.planning/REQUIREMENTS.md` — TRK-01..05 (this phase). Also FRM-01..07 / DEC-01..07 for the downstream consumer contract (scorer + FSM that these signals feed).

### Domain research (the WHY behind every tracker/subject-selection decision)
- `.planning/research/STACK.md` — **the load-bearing Phase-4 doc**: YOLO26s + `dog=16`, BoT-SORT `with_reid:True/model:auto` native-ReID (zero extra weights), `track_buffer:60`, the full `botsort_dog.yaml` override, one-tracker-per-camera (#13107), the "verify native ReID actually engages on yolo26s, else it silently downloads a fallback" warning, ByteTrack latency fallback, and the version-compatibility caveats.
- `.planning/research/PITFALLS.md` — Pitfall 1 (locks onto handler/bystander → competitor-lock = first-class), Pitfall 2 (ID swap → tracker ID is advisory, plausibility/teleport gate, single-competitor prior), Pitfall 3 (motion-blur dropped detections → coast, don't over-filter the locked track's low-conf continuation), Pitfall 4 (small-at-distance), Pitfall 10 (per-camera lighting/confidence bias). The "Looks Done But Isn't" checklist is the Phase-4 acceptance lens.
- `.planning/research/ARCHITECTURE.md` — camera roles, the normalized field-zone model the zone-gate consumes.

### Project decisions & scope
- `.planning/PROJECT.md` — model pin (yolo26s/dog=16), native-ReID-in-v1 / heavy-ReID-deferred, competitor-lock + zone-gating as first-class, two-budget latency, the curated clip set as the decisive de-risk.

### Phase-1/2 contracts Phase 4 consumes/produces verbatim (read directly)
- `src/segugio/framing/signals.py` — **`DetectionSignal(tick:int, cam_id:str, cx, cy, w, h, conf, track_id)`** — the EXACT output contract Phase 4 fills (a YOLO+BoT-SORT result row maps here unchanged; `None` = no dog this cam this tick → coast). Frozen, normalized [0,1], `tick` is an injected frame index.
- `src/segugio/framing/scorer.py` — `MultiCamScorer.update(dets_by_cam, tick) -> list[CameraScore]` — the immediate downstream consumer (Phase 5 wires it; Phase 4 must produce a shape it accepts: a `DetectionSignal | None` per camera per tick).
- `src/segugio/config/models.py` — `ModelConfig(path=Path("yolo26s.pt"), class_index=16)`, `Camera{id, role, obs_scene, is_safe, zones}`, normalized `Zone` rects, `Thresholds.track_buffer` (=60), `Role`. Read `model.names` at startup and reconcile with `class_index`.
- `config.example.yaml` / `config.agility.example.yaml` — `model.path/class_index`, `thresholds.track_buffer: 60`, the per-camera `zones` the zone-gate uses.
- `src/segugio/synth/detection_stream.py` — the raw `DetectionSignal` synthetic generator (frozen-dataclass + injected `Generator` + injected tick) — the substrate for the **pure-logic** competitor-lock / plausibility-gate tests (D-09).
- `tests/conftest.py` — reuse `seeded_rng` / `valid_config_dict`; add a tracking/crop fixture.
- `tests/fixtures/clip_manifest.yaml` + `tests/fixtures/README.md` — the actual corpus (query via `segugio.fixtures.select_clips(...)`); confirms single-camera disc-dog only, the per-condition slices, and the provenance/consent table.

### Prior phase context
- `.planning/phases/02-framing-scorer-pure-logic/02-CONTEXT.md` — the scorer's input/output contract and the per-detection (intra-frame) plausibility guard that TRK-05 must NOT be confused with.
- `.planning/phases/03-decision-engine-fsm/03-CONTEXT.md` — the FSM (downstream consumer) + the note that detection-in-occlusion-zone → `occlusion_hold` wiring is Phase 4/5, here confirmed as **Phase 5**.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`segugio.framing.signals.DetectionSignal` (Phase 2):** the exact output contract — Phase 4 constructs these from tracker rows, no shape change.
- **`segugio.framing` (Phase 2):** `MultiCamScorer` is the downstream consumer; the coast path (`None` detection → FRM-05 coast/TTL) is precisely how the plausibility gate's "uncertain → coast" (D-06) is realized — no new coast logic needed downstream.
- **`segugio.config` (Phase 1):** `ModelConfig`, per-camera normalized `Zone` rects (zone-gate input), `Thresholds.track_buffer`. New TRK-05 seeds extend config additively (no breaking change).
- **`segugio.synth.detection_stream` (Phase 2):** the deterministic raw-signal generator for the CPU-only competitor-lock / plausibility tests (D-09).
- **`segugio.fixtures` (Phase 1):** opencv-free manifest query API (`select_clips` / `coverage_report` / `resolve_clip_path`) to pick the disc-dog slices for the GPU eval run.
- **`pyproject.toml`:** `pythonpath=["src"]`, `testpaths=["tests"]` — src-layout editable install auto-discovers a new `segugio/tracking/` package (verify with one import).

### Established Patterns
- **Lazy-import boundary (01-01 smoke test):** `import segugio.tracking` must succeed with `torch`/`ultralytics`/`cv2`/`cyndilib`/`obsws` **absent**. Heavy deps load only inside the detector/clip-reader functions, never at module top level. The pure subject-selection logic runs CPU-only.
- **Determinism convention:** frozen dataclasses for `==` assertions; time = injected `tick`; randomness only via an injected `Generator` in the synth generator. The competitor-lock/plausibility LOGIC must be deterministic on synthetic inputs (mirrors FRM-07 / DEC-07).
- **Run tests via `.venv/bin/python -m pytest`** — system `python3` does not see numpy.

### Integration Points
- **Input:** recorded clip frames → opencv decode → spatial crops → per-camera `model.track(frame, persist=True, classes=[dog])`. One tracker instance per `cam_id`.
- **Output (Phase 4 → Phase 2 scorer, wired in Phase 5):** per camera per tick, the **locked competitor's** `DetectionSignal` (or `None` when uncertain/lost → coast). Plus the offline eval artifacts (overlay video + metrics) for human verification.

</code_context>

<specifics>
## Specific Ideas

- **The clip set's "looks done but isn't" trap is the whole point of Phase 4.** A single clean clip will make the tracker look perfect; the value is proving competitor-lock on `handler_close_01` / `crowd_distractor_01` (handler + bystander context) and surviving the blur (`sprint_blur_01`) and re-entry (crop exit/return). Test against the hard slices, not a clean one.
- **Tracker ID is advisory, never authoritative** (PITFALLS Pitfall 2). The locked-subject identity is the competitor-lock's, layered *on top* of the tracker ID — the plausibility gate is the enforcement that the tracker ID hasn't silently jumped to a bystander.
- **Startup ReID-engagement check is a hard gate, not a nicety** (TRK-02): yolo26 is NMS-free/end-to-end, and the native-ReID forward-hook needs a standard `Detect` head — if it's end2end, Ultralytics silently swaps in a downloaded cls model. The startup check must **confirm native ReID actually engaged** (and log it), or the whole "zero-extra-weights ReID" premise is silently false.
- **Don't over-filter the locked track's low-confidence continuation** (PITFALLS Pitfall 3): keep a high confidence floor for *new* tracks but a low floor for *continuing* the locked track through a blur dip — this is what keeps the subject alive through the climax.

</specifics>

<deferred>
## Deferred Ideas

- **Agility-tunnel-occlusion + two-similar-dogs-crossing validation** — the corpus has no agility and no clean two-competing-dogs-crossing clip. The code paths exist; they are flagged UNVERIFIED and revisited when real footage is provided. (D-02)
- **Detection-in-occlusion-zone → FSM `occlusion_hold` wiring** — Phase 5 (the orchestrator wires detection signals into the FSM hold inputs); not Phase 4.
- **Cross-camera ReID / global subject identity** — "heavy ReID," deferred per PROJECT; v1 competitor-lock is per-camera. (D-05)
- **Disc/frisbee detection** (`classes=[16,29]`, lead-the-dog prediction) — v2 differentiator.
- **Pose model** (`yolo26s-pose`, heading/intent for action-hold) — v2.
- **Custom / fine-tuned dog model** — only if eval shows COCO `dog` misses too often (backlit/dusk/mid-air); measure now, decide later.
- **ByteTrack latency fallback / TensorRT FP16 export** — only if the AI loop blows budget; export belongs to the hardware milestone (GPU-specific engines).
- **Numeric threshold calibration** (`max_displacement_per_tick`, `max_size_ratio`, motion-window length, crop geometry) — config seeds, tuned opportunistically on clips, not a Phase-4 gate.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 04-yolo-per-camera-tracking-on-recorded-clips*
*Context gathered: 2026-06-10*
