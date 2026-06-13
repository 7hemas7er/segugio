# Roadmap: Segugio

## Overview

Segugio v1 delivers an operator-less multi-camera auto-director for dog sports (disc dog + agility), **software-complete on synthetic data** — recorded clips as pseudo-cameras and a mock NDI source, no hardware. The journey is a strict dependency chain of unit-testable layers: a central config contract plus a curated multi-condition clip set front-load the de-risk; a pure framing scorer turns per-detection signals into per-camera scores; a decision FSM becomes the single source of truth on "which camera is live" with no flicker and no dead-feed cuts; YOLO + one-tracker-per-camera proves subject selection against the hardest clips; and a final integration phase wires NDI mock, orchestrator, OBS control, watchdog, and the manual score UI end-to-end, closing the milestone. Each phase is independently verifiable on the dev box before integration near the end.

**Milestone v1.1 — Console Regia (live visibility, Phases 7–9).** v1.1 turns the blind Flask control panel into a live oversight console: the operator *sees* every camera, understands *why* the auto-director chose the live cam, and issues *informed* overrides — without touching the crash-isolation guarantee that keeps the v1.0 director reliable (the console still imports only `Flask + segugio.opcomm`, never the orchestrator). This is a publish-and-render problem, not a compute one: the orchestrator already computes the per-camera scores, dog bbox, and FSM reason every tick and already holds the decoded frames; v1.0 simply discards them. The work is a strict dependency chain forced by one new boundary — a frame/thumbnail publishing channel off the director's critical tick. Phase 7 builds and gates that channel (RBT-05 p95 unchanged with preview ON; console crash-isolation proven by an import test with torch/cv2 absent). Phase 8 makes the console serve and render the live multiview, lands the `threaded=True`/Waitress server fix as a safety control (override POSTs must never be blocked), caps preview bandwidth so it degrades before the NDI feeds do, and re-evaluates the threat model now that live competitor video sits behind the endpoint. Phase 9 adds the explainability layer — per-camera score bars, the plain-Italian reason, the dog-lock bbox overlay, the "auto wants vs aired" hint, the switch-history strip, the live score-overlay preview — plus informed clickable-tile overrides, the tablet-first responsive restyle, and the long-run leak/sleep/freshness hygiene. Nothing the operator sees can render before the channel exists, so Phase 7 gates everything.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation, Config & Curated Clip Set** - Project scaffolding, validated central YAML config (the contract every module consumes), the multi-condition clip set, and synthetic stream generators (completed 2026-06-09)
- [x] **Phase 2: Framing Scorer (pure logic)** - Resolution-independent per-camera framing score with EMA, zone-gating, lead-room, coast/TTL and per-camera confidence normalization — pure and unit-testable (completed 2026-06-09)
- [x] **Phase 3: Decision Engine FSM** - The single source of truth on "which camera is live": hysteresis, dwell, debounce, cooldown, feed-alive guard, action-hold, occlusion-hold, tiebreaker, override + auto-resume (completed 2026-06-09)
- [x] **Phase 4: YOLO + Per-Camera Tracking on Recorded Clips** - Pre-trained YOLO on CUDA with one BoT-SORT tracker per camera (native ReID), competitor-lock and plausibility gate, validated on the curated clips (completed 2026-06-09)
- [x] **Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI** - End-to-end wiring with no hardware: mock NDI ingest, feed watchdog + fallback, OBS controller, manual score-entry UI, orchestrator tick + fault isolation, latency measurement (verification 2026-06-11: 4/5 — gaps found, CR-01 startup fault-sink) (completed 2026-06-11)
- [x] **Phase 6: Decision-loop latency optimization** - TensorRT FP16 export + batched/parallel per-camera inference to bring the 4-camera decision loop under the **<300ms** p95 budget (RBT-05, budget rivisto da <150ms 2026-06-13). Phase 05 UAT Test 5 measured 231–247ms p95 with eager-FP32 yolo26s. Canonical path = FP16+batch **eager** (ReID nativa) ~256ms cool; TensorRT engine ~197ms come leva opzionale a più margine (completed 2026-06-13; RBT-05 MET <300ms on RTX 4000 Ada Laptop — see 06-VERIFICATION.md)

### Milestone v1.1 — Console Regia (live visibility)

- [x] **Phase 7: Off-tick Frame-Publishing Channel** - The GATING foundation for every v1.1 visual feature: an orchestrator-side `PreviewPublisher` daemon thread + `atomic_write_bytes` + `preview.json` sidecar publish downscaled per-camera JPEG thumbnails and the per-camera "why" data off the director's critical tick — proven not to regress RBT-05 and to keep the console crash-isolated (PRV-01/02/03) (completed 2026-06-13)
- [x] **Phase 8: Console Serving, Live Multiview & Safety Hardening** - The console consumes the channel: a responsive multiview grid of all cameras with LIVE/tally and dead-feed marking, plus the `threaded=True`/Waitress server fix (override POSTs never blocked — a safety control), a preview-bandwidth cap so the preview degrades before NDI feeds, and a written threat re-evaluation now that competitor video sits behind the endpoint (MVW-01/02/03, UXT-02) (completed 2026-06-13)
- [ ] **Phase 9: Explainability, Informed Override & Tablet UX** - The "e perché" layer + informed override + tablet polish: per-camera score bars, plain-Italian reason, dog-lock bbox overlay, "auto wants vs aired" hint, switch-history strip, live score-overlay preview, clickable-tile overrides, tablet-first responsive restyle, and long-run leak/sleep/freshness hygiene (MVW-04/05, WHY-01/02/03/04, SCV-01, UXT-01/03)

## Phase Details

### Phase 1: Foundation, Config & Curated Clip Set

**Goal**: The config contract and test substrate every later module depends on exist and validate — a central YAML schema plus the curated multi-condition clip set and synthetic stream generators that make all downstream work hardware-free and pitfall-revealing.
**Depends on**: Nothing (first phase)
**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04, TST-01, TST-02
**Success Criteria** (what must be TRUE):

  1. Loading a malformed `config.yaml` fails fast at startup with a clear validation error; a well-formed one parses cameras+roles, per-camera normalized zone rects, `framing_weights[role][zone]`, all switching thresholds (alpha, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer), and the YOLO model path + class index
  2. Switching the `discipline` selector (disc dog / agility) in config changes overlay field set and framing defaults with zero code edits
  3. `tests/fixtures/` contains the curated clip set spanning multi-dog, handler-prominent, tunnel/contact occlusion, jump/sprint blur, distant, backlit/dusk and midfield-equidistant conditions for both disc dog and agility, with a license README
  4. Synthetic generators produce deterministic score-stream and feed-death sequences that the scorer, FSM and watchdog can be unit-tested against without any clip or hardware

**Plans**: 4 plans (Wave 1: 01-01 · Wave 2 parallel: 01-02, 01-03, 01-04)

Plans:

- [x] 01-01-PLAN.md — Package scaffolding (`src/segugio/`), pinned `requirements.txt` + `pyproject.toml`, loguru bootstrap, pytest substrate (conftest fixtures), lazy-import smoke test [Wave 1]
- [x] 01-02-PLAN.md — Central config contract: pydantic v2 models (cameras/roles, normalized zones, `framing_weights[role][zone]`, thresholds, model path/class), discipline discriminated-union swap, fail-fast loader, disc+agility example configs [Wave 2]
- [x] 01-03-PLAN.md — Curated clip-set substrate: opencv cataloguer (footage path at execution time), queryable manifest + condition-coverage gap report, `tests/fixtures/README.md` license/consent, external-dir + committed-manifest pattern [Wave 2]
- [x] 01-04-PLAN.md — Deterministic synthetic generators: seeded score-stream (ping-pong/tie/dropout/recovery) + feed-death timelines for hardware-free unit testing of scorer/FSM/watchdog [Wave 2]

### Phase 2: Framing Scorer (pure logic)

**Goal**: A pure, I/O-free framing scorer turns per-detection signals into a smoothed, resolution-independent per-camera score that already encodes the domain's hardest framing decisions (zone-gating, size target-band, lead-room, coast/TTL, confidence normalization), provably correct on synthetic detection sequences before any detector is wired in.
**Depends on**: Phase 1
**Requirements**: FRM-01, FRM-02, FRM-03, FRM-04, FRM-05, FRM-06, FRM-07
**Success Criteria** (what must be TRUE):

  1. Given identical normalized detection signals at two different resolutions, the scorer returns the same base score (centeredness + size target-band + confidence), and feeding a detection stream produces an EMA-smoothed per-camera score with alpha read from config
  2. A detection inside a high-weight field zone outscores an identical detection in a low-weight zone, and a detection outside the field bounds is gated down — `score = base × framing_weights[role][zone]` is observable in unit tests
  3. During a synthetic short detection dropout (blur burst), the score coasts (TTL hold) instead of collapsing to zero; once TTL expires the subject is marked lost
  4. The ideal framing target shifts toward the dog's motion direction (lead-room), and per-camera confidence normalization prevents a uniformly brighter camera from winning on confidence alone
  5. The entire scorer module performs no I/O and its full behavior is exercised by unit tests on synthetic detection sequences (FRM-07)

**Plans**: 4 plans (Wave 1: 02-01 · Wave 2: 02-02 · Wave 3: 02-03 · Wave 4: 02-04)

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Substrate: frozen DetectionSignal/CameraScore/ScorerStatus, pure term functions, additive ScorerParams config sub-model, NEW detection_stream generator, Wave-0 test scaffold; FRM-01 base + shadow guard green [Wave 1]

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — CameraScorer present-detection path: base score + EMA + zone-gating + lead-room + per-camera conf-normalization (FRM-02/03/04/06) [Wave 2]

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Coast/TTL dropout path (hold-then-lost, never collapse to 0) + MultiCamScorer fan-out (FRM-05) [Wave 3]

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-04-PLAN.md — Purity/determinism gate + lazy-import-boundary extension + coverage (FRM-07) [Wave 4]

### Phase 3: Decision Engine FSM

**Goal**: A `transitions`-based finite state machine becomes the sole authority on which camera is live — consuming per-camera scores and feed-liveness events to emit guarded, jitter-free switching decisions that never double-cut, never flicker, never select a dead feed, hold through climaxes and expected occlusions, and support manual override with automatic resume.
**Depends on**: Phase 2
**Requirements**: DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07, RBT-03
**Success Criteria** (what must be TRUE):

  1. No switch command is ever emitted outside a guarded FSM transition; replaying a synthetic score stream, the FSM applies two-threshold hysteresis + min_dwell + debounce_N + cooldown so that ping-pong and equidistant-score noise produce zero spurious cuts
  2. A feed-death event on the live camera triggers a transition to a live alternative or the SAFE scene, and a camera marked dead is never selected as live or as challenger (DEC-06)
  3. During a synthetic "action in progress" or marked expected-occlusion window, the FSM holds the current camera instead of cutting; near-tied scores resolve by a deterministic tiebreaker with no oscillation
  4. A manual override forces a specific camera; after the override is released and the auto candidate has won full hysteresis + dwell, the FSM resumes automatic selection (RBT-03)
  5. The full FSM is unit-tested against synthetic score + feed-death streams covering ping-pong, tie, dropout, recovery, override and occlusion scenarios (DEC-07)

**Plans**: 4 plans (Wave 1: 03-01 · Wave 2: 03-02 · Wave 3: 03-03 · Wave 4: 03-04 — strictly serial; each plan extends the shared `engine.py`/`signals.py` of the prior)

Plans:

**Wave 1**

- [x] 03-01-PLAN.md — Wave-0 setup (reclassify `transitions` to light deps, create `segugio/decision/` package, conftest fixtures + `_as_camera_scores` adapter) + the `Decision`/`HoldInput`/`OverrideCmd`/`Mode` contracts + `ticks_from_seconds` + core `DecisionEngine`: guarded transitions, two-threshold hysteresis + min_dwell + debounce_N + cooldown (DEC-01, DEC-02) [Wave 1]

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Feed-alive guard + feed-death emergency cut (DEC-06), action-hold + occlusion-hold with mandatory max-caps (DEC-03/DEC-04), deterministic tiebreaker (DEC-05) [Wave 2]

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — Manual override + auto-resume: force (immediate), forced-but-dead fallback, manual-release-only, resume requires full hysteresis+min_dwell (RBT-03) [Wave 3]

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-04-PLAN.md — DEC-07 determinism gate over synthetic score + feed-death streams + combined high-value cross-scenario suite (force→release→resume, hold-through-occlusion→release, live-feed-death-mid-hold) with the two hard safety invariants as shared assertions [Wave 4]

### Phase 4: YOLO + Per-Camera Tracking on Recorded Clips

**Goal**: A pre-trained YOLO model running on CUDA, with one BoT-SORT tracker per camera using native-feature ReID, produces normalized per-detection signals and a robustly selected competitor track — proven against the curated multi-condition clips so subject selection (the dominant project risk) is validated in software, feeding real signals into the Phase 2 scorer shape.
**Depends on**: Phase 1 (clips + config), Phase 2 (scorer signal contract)
**Requirements**: TRK-01, TRK-02, TRK-03, TRK-04, TRK-05
**Success Criteria** (what must be TRUE):

  1. Recorded videos run as pseudo-cameras with one independent `model.track(persist=True)` tracker per camera (no shared frame list / no ID mixing), filtering on the dog class resolved from `model.names` at startup
  2. Startup verifies native ReID is actually engaged (BoT-SORT `with_reid: True, model: auto`, extended `track_buffer`) and logs confirmation rather than silently falling back
  3. For each frame the system emits normalized signals (cx/cy, w/h, confidence, track id) filtered to the dog class, consumable directly by the framing scorer
  4. On multi-dog / handler-prominent clips the competitor-lock selects the in-competition dog rather than the largest/most-central blob, and a plausibility (teleport/size-jump) gate rejects implausible track switches
  5. Detection + tracking is exercised on the curated multi-dog, pairs, occlusion and distance clips, demonstrating subject continuity through crossings and re-entries

**Plans**: 4 plans (Wave 1: 04-01 · Wave 2 parallel: 04-02, 04-03 · Wave 3: 04-04)

Plans:

**Wave 1**

- [x] 04-01-PLAN.md — Substrate: lazy-import `segugio.tracking` package, additive `TrackingParams` sub-model (TRK-04/05 seeds), PURE `signals_from_boxes` mapper (TRK-03), multi-track `detection_stream` extension, Wave-0 infra (gpu marker, conftest fixtures, import-smoke + signals-map tests) [Wave 1]

**Wave 2** *(parallel; blocked on Wave 1 — zero file overlap)*

- [x] 04-02-PLAN.md — The brain: PURE `CompetitorLock` (TRK-04: zone-gate AND motion-energy, sticky, per-camera) + `PlausibilityGate` (TRK-05: inter-frame teleport/size-jump → coast), unit-tested on synthetic multi-track streams [Wave 2]
- [x] 04-03-PLAN.md — The heavy edge: `PerCameraTracker` (TRK-01: one `model.track(persist=True)` per cam, dog-by-name) + `assert_native_reid_engaged` HARD gate (TRK-02, `end2end=False`) + `ClipFrameSource` crops (D-01) + `botsort_dog.yaml` + gpu-skip + gpu eval skeleton [Wave 2]

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-04-PLAN.md — The eval (D-08): PURE metric counters (ID-switch / %lock-held / coast) + heavy-edge overlay render + the clip eval driver wiring the full TRK-01..05 pipeline + UNVERIFIED logging (D-02) [Wave 3]

### Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI

**Goal**: Everything wires together end-to-end with no hardware, closing the v1 milestone: a mock NDI source feeds clips through cyndilib ingest, a timestamp-based watchdog drives automatic fallback, an OBS controller cuts scenes and PIP and updates overlays, a manual score-entry UI writes atomically to an OBS read-from-file text source, and a fault-isolated orchestrator ticks the full frame→YOLO→score→FSM→OBS loop within the latency budget and shuts down to SAFE without ever crashing.
**Depends on**: Phase 3 (FSM authority), Phase 4 (detection/tracking signals)
**Requirements**: NDI-01, NDI-02, NDI-03, OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, SCR-01, SCR-02, SCR-03, SCR-04, RBT-01, RBT-02, RBT-04, RBT-05
**Success Criteria** (what must be TRUE):

  1. A mock NDI source publishes recorded clips as named NDI sources; cyndilib ingest (Finder/Receiver/FrameSync) delivers numpy BGR frames per camera via supervised threads, guarding against empty first frames — all on the dev box with no phones
  2. The OBS controller, against the provided scene-collection template (`CAM *`, `SAFE`, `MULTIVIEW`/`PIP`), cuts the program scene, toggles PIP via cached numeric `sceneItemId`, reconnects on drop, and an EventClient observes manual scene changes
  3. The feed watchdog deduces liveness from the last-*new*-frame timestamp (never NDI source state); cutting/freezing a mock feed triggers automatic fallback to SAFE or a live camera with no crash, and the feed only rejoins after it is live and wins full hysteresis + dwell
  4. The manual score-entry UI offers the discipline selector and the three per-discipline field sets plus run start/stop; entries are written atomically (temp + `os.replace`) and appear in the OBS read-from-file overlay — the system displays scores and never adjudicates
  5. The orchestrator runs a fixed-rate tick wiring all modules with fault isolation (try/except + supervised restarts), shuts down to the SAFE scene, never crashes the process, and the measured frame→YOLO→score→FSM→OBS decision loop stays under ~150ms (target <80ms)

**Plans**: 9 plans (Wave 1: 05-01 · Wave 2 parallel: 05-02, 05-03, 05-04, 05-05 · Wave 3: 05-06 · Gap Closure parallel: 05-07, 05-08, 05-09)
**UI hint**: yes

Plans:

**Wave 1**

- [x] 05-01-PLAN.md — Foundation: full Wave-0 test scaffold + conftest fixtures + `ndi`/`obs` markers + Flask dep; the atomic-file `opcomm` channel (atomic write + frozen records + boundary-safe channel, SCR-01); additive `ActionHoldParams` config (D-08 seeds); `FrameSource`/`ObsController` interfaces; additive `CompetitorLock.locked_motion_energy()` accessor [Wave 1]

**Wave 2** *(parallel; blocked on Wave 1 — zero file overlap)*

- [x] 05-02-PLAN.md — NDI ingest: in-process clip-replay mock `FrameSource` + empty-frame guard (NDI-03); real cyndilib `FrameSource` (supervised per-camera threads, last-NEW-frame liveness, NDI-01); mock NDI `Sender` publishing named sources (NDI-02, E2E-only) [Wave 2]
- [x] 05-03-PLAN.md — OBS controller: `RecordingObsController` fake (camera→scene mapping + cached PIP id, OBS-01/02) + real obsws-python v5 controller (cut/PIP/overlay/reconnect/EventClient, OBS-01/02/03/05) + scene-collection template (OBS-04) [Wave 2]
- [x] 05-04-PLAN.md — Feed watchdog: pure last-NEW-frame `FeedWatchdog` liveness on injected timestamps (RBT-01) + feed-death fallback + guarded rejoin against the locked `DecisionEngine` (RBT-02) [Wave 2]
- [x] 05-05-PLAN.md — Score manager + UI: pure per-discipline overlay renderer (display-only, SCR-04) + Flask operator console (separate process, score/run/override POSTs + status poll, SCR-02/03, D-09/10/11) + Italian console page [Wave 2]

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 05-06-PLAN.md — Orchestrator: action-hold from motion energy (D-08) + fixed-rate fault-isolated tick (the grown-up `run_clip_eval`) + SAFE shutdown + D-11 status write (RBT-04) + decision-loop latency harness (RBT-05) [Wave 3]

**Gap Closure** *(parallel; from 2026-06-11 verification 4/5 — zero file overlap; prior plans done)*

- [x] 05-07-PLAN.md — BLOCKER: fault-isolate `run()`/`run_measured()` startup (`source.start()`/`obs.connect()` in try/except → coast into the tick loop) + guard `_cache_pip_ids()` in `connect()` (CR-01, the FAILED truth, RBT-04); non-zero config-sourced anti-jitter `watchdog_grace` (WR-02); distinct non-"feed-dead" fault reason (WR-09); remove dead `live_cam` (WR-01); NEW headless startup-fault regression test that flips Truth #5 [Gap Closure]
- [x] 05-08-PLAN.md — IO/thread robustness: route `atomic_write_text` through the `_atomic_replace` retry (WR-04, Windows OBS sharing-violation) + de-busy-spin/auto-reconnect the NDI `_receiver_loop` (CR-02 code fix; real CPU/reconnect stays HARDWARE-deferred), each with a headless regression test [Gap Closure]
- [x] 05-09-PLAN.md — RUNNABLE ENTRY POINT (UAT gap, the half-met phase goal): `build_orchestrator(config, channel_dir)` factory (src/segugio/orchestrator/runtime.py) composing real NdiFrameSource + ObsWsController + per-camera PerCameraTracker + opcomm channel_paths -> `Orchestrator.from_config(...)` (heavy imports lazy, injectable seam for headless tests) + `python -m segugio <config>` (`__main__.py`: load -> build -> run, Ctrl-C -> shutdown SAFE coast, RBT-04) + docs/run.md (OBS-up/OBS-down launch) — unblocks D-07 UAT Tests 1-4 [Gap Closure]

### Phase 6: Decision-loop latency optimization

**Goal**: Bring the multi-camera decision loop within the **<300ms p95** budget (RBT-05; budget rivisto da <150ms il 2026-06-13 dopo la misura sul rig) via TensorRT FP16 export + batched/parallel per-camera inference, preserving native BoT-SORT ReID and the never-crash invariant.
**Depends on**: Phase 5 (the integrated orchestrator loop + `run_measured` latency harness + the gpu-marked `test_latency.py`)
**Requirements**: RBT-05
**Success Criteria** (what must be TRUE):

  1. The 4-camera frame→YOLO→score→FSM→OBS decision loop measures p95 < 300ms on the deploy GPU, recorded by re-running `tests/test_latency.py -m gpu`
  2. ONE batched FP16 detection forward per tick replaces the 4 serial `model.track()` calls, and native BoT-SORT ReID is confirmed still engaged on the batched path (no silent cls fallback)
  3. The engine-aware loader falls back gracefully to the eager `.pt` on any engine/build failure and never crashes the process (RBT-04)
  4. The TensorRT FP16 engine is available as an optional higher-margin lever (`tools/build_engine.py`, ~197ms p95) without becoming a hard runtime dependency

**Plans**: 3 plans (Wave 0: 06-01 · Wave 1: 06-02 · Wave 2: 06-03)

Plans:

**Wave 0** *(hard prerequisite — env + headless seams; blocks every measurement)*

- [x] 06-01-PLAN.md — Wave-0 substrate: confirm the py3.12 cu12x-torch + tensorrt GPU env on the rig (human checkpoint) + engine-aware `assert_native_reid_engaged` (warn-not-raise on engine, HARD-raise unchanged on eager) + additive `ModelConfig.engine_path`/`use_fp16` keys + the Track-B batched-detect adapter (`batched.py`) with a #13107 per-camera state-isolation guard + gitignore `*.engine`/`*.onnx` + docs/run.md env note [Wave 0]

**Wave 1** *(the cheap rung first — blocked on 06-01)*

- [x] 06-02-PLAN.md — Eager FP16 + batched detection (preserves native ReID): thread `half=True` through the batched forward + switch `_fan_out` to ONE batched forward per tick with per-camera tracker dispatch (every Phase-5 loop invariant preserved) + re-run the gpu latency gate and RECORD the 4-cam p95. **MEASURED p95 ~210ms (211.4/209.5 two runs) on the RTX 4000 Ada, AC power, batched FP16 path with native ReID confirmed engaged → FAIL (≥150ms) → 06-03 AUTHORIZED** [Wave 1]

**Wave 2** *(the engine track — AUTHORIZED: 06-02 measured ~210ms, still over the 150ms budget)*

- [x] 06-03-PLAN.md — TensorRT FP16 engine: `checkpoint:decision` resolving the engine↔ReID story (Open Q1, Option a/b) + `tools/build_engine.py` one-time cached build CLI + engine-aware `PerCameraTracker` loader with graceful eager fallback (RBT-04, never crash) + `is_engine` threaded into the reid gate + build the engine on the rig and confirm 4-cam p95 < 150ms (RBT-05 — the phase goal) [Wave 2]

### Phase 7: Off-tick Frame-Publishing Channel

**Goal**: A new off-tick publishing channel exposes what the orchestrator already computes — downscaled per-camera JPEG thumbnails plus a per-camera "why" sidecar (framing score, tracking state, dog bbox, FSM auto-candidate, recent-cuts ring) — to the crash-isolated console, built so it provably never steals time from the director's critical tick and never widens the console's import surface. This is the gating foundation: nothing the operator sees in v1.1 can render until this channel exists and is proven safe.
**Depends on**: Phase 6 (the latency-tuned orchestrator loop + `run_measured` RBT-05 harness it must not regress) and Phase 5 (the `opcomm` atomic-file channel, `DirectorStatus`/`status.json` reverse channel, and the crash-isolated Flask console it extends)
**Requirements**: PRV-01, PRV-02, PRV-03
**Success Criteria** (what must be TRUE):

  1. With the `PreviewPublisher` running, re-running the RBT-05 latency harness (`run_measured` / `test_latency.py -m gpu`) shows the 4-camera decision-loop p95 unchanged within noise — frame resize/JPEG-encode/atomic-write happen on a daemon thread fed by a latest-only mailbox, never on the tick (HARD gate: preview ON must not regress RBT-05)
  2. A crash-isolation import test proves `import segugio.ui` resolves and the console starts with the heavy stack (`ultralytics`/`torch`/`numpy`/`cv2`/`cyndilib`) uninstalled — the console still imports only Flask + `segugio.opcomm` (HARD gate)
  3. The orchestrator writes downscaled per-camera JPEG thumbnails and a `preview.json` sidecar into a separate, size-bounded `opcomm/preview/` media dir via fixed-filename atomic overwrite (`atomic_write_bytes`, no fsync for the ephemeral frames); a half-written JPEG or sidecar is never read torn
  4. The `preview.json` sidecar (`PreviewDoc`, frozen, safe-default reader that never raises) carries per-camera framing score + tracking state (tracking/coast/lost) + normalized dog bbox + the FSM auto-candidate + a ring of recent cuts — entirely separate from the unchanged safety-critical `status.json`
  5. A publisher fault (encode/IO error) coasts and is logged without perturbing the director or crashing the process (RBT-04 extended to the preview path)

**Plans**: 4 plans (Wave 1 parallel: 07-01, 07-02 · Wave 2: 07-03 · Wave 3: 07-04)
**UI hint**: no (Phase 7 writes files; serving/rendering is Phase 8/9)

Plans:

**Wave 1** *(parallel; zero file overlap)*

- [x] 07-01-PLAN.md — opcomm leaf primitives: atomic_write_bytes (D-04), PreviewDoc + read_preview/write_preview sidecar (D-03/D-07), PreviewParams additive config (D-05/D-06) [Wave 1]
- [x] 07-02-PLAN.md — HARD GATE 2: crash-isolation import test extended (add numpy block + create_app start-check) [Wave 1]

**Wave 2** *(blocked on 07-01)*

- [x] 07-03-PLAN.md — PreviewPublisher daemon: latest-only mailbox + off-tick resize/encode/atomic-write + the D-07 “why” PreviewDoc + RBT-04 coast (D-02) [Wave 2]

**Wave 3** *(blocked on 07-03)*

- [x] 07-04-PLAN.md — Wire into the real run path: guarded offer() in _tick_once + cuts ring + frames_by_cam surface + runtime preview_factory/preview dir + HARD GATE 1 (RBT-05 unchanged with preview ON) (D-06/D-08/D-09) [Wave 3]

### Phase 8: Console Serving, Live Multiview & Safety Hardening

**Goal**: The crash-isolated console consumes the new channel and renders the first thing the operator actually needs — a live, flicker-free multiview of every camera with an unmistakable LIVE/tally indicator and at-a-glance dead-feed marking — landing in the same phase the two safety controls that the streaming endpoint makes mandatory: the multi-threaded server so a preview stream can never block an override POST, and a hard preview-bandwidth cap so the preview degrades on contended WiFi before the NDI feeds ever appear to die. Because this is the phase that first puts live competitor video behind the `0.0.0.0` endpoint, a written threat re-evaluation is an acceptance criterion.
**Depends on**: Phase 7 (the publish channel, `preview.json` sidecar and `opcomm/preview/` JPEGs the console serves and renders)
**Requirements**: MVW-01, MVW-02, MVW-03, UXT-02
**Success Criteria** (what must be TRUE):

  1. The console serves and renders a responsive CSS-Grid multiview of all cameras — `<img>` per camera refreshed flicker-free (preload `Image()` + swap, cache-busted) at the configured cadence — via two new routes (`GET /preview/<cam>.jpg` whitelisted `send_file`, `GET /preview` sidecar JSON), the console import set still Flask + `segugio.opcomm` only
  2. The tile of the camera currently on air carries an unmistakable LIVE/tally indicator (red border/badge + "ON AIR: CAM X" banner) driven by `status.live_cam`, and any dead/stale feed is greyed-out/"MORTO"-marked on its tile from `status.alive` + preview freshness
  3. With a preview stream active, a POST `/command` override is served promptly with no freeze — the `threaded=True`/Waitress server fix is in place so serving thumbnails never pins the lone worker and blocks the safety-critical override control (UXT-02)
  4. Total preview traffic stays under a configured bitrate ceiling (fps + resolution + JPEG-quality cap); with phones live the feed-watchdog false-death rate is unchanged — the preview degrades first, the director's feeds never starve
  5. A written v1.1 threat re-evaluation for live-video-behind-`0.0.0.0` plus the LAN/AP isolation requirement exists in the project docs

**Plans**: 3 plans (Wave 1 parallel: 08-01, 08-02, 08-03 — zero file overlap)
**UI hint**: yes

Plans:

**Wave 1** *(all parallel — no shared files)*

- [x] 08-01-PLAN.md — Serving routes (`GET /preview`, `GET /preview/<cam>.jpg` whitelisted send_file) + CSS-Grid multiview + LIVE/MORTO marking + `threaded=True`/Waitress safety fix + crash-isolation guard (MVW-01/02/03, UXT-02) [Wave 1]
- [x] 08-02-PLAN.md — Config-time preview-bandwidth cap: `PreviewParams.max_total_mbps` + over-cap-rejection `@model_validator` (fail-fast, D-01/D-02) [Wave 1]
- [x] 08-03-PLAN.md — `docs/security.md` v1.1 threat re-evaluation: live-video-behind-`0.0.0.0` + AP client-isolation hard requirement (D-09) [Wave 1]

### Phase 9: Explainability, Informed Override & Tablet UX

**Goal**: The console becomes a true regia — the operator not only sees the cameras but understands *why* the auto-director chose the live one and can override from what they see. This phase publishes-and-renders the explainability layer (per-camera score bars, the plain-Italian reason, the dog-lock bbox overlay, the "auto wants vs aired" hint, the switch-history strip), turns every multiview tile into an informed force-cam control, shows a live preview of how the score will appear on the OBS overlay as the operator types, restyles the whole console tablet-first, and adds the long-run hygiene that keeps a tablet on contended WiFi honest (no leaks, sleep/wake resume, and a freshness stamp so a frozen frame is never shown as "live").
**Depends on**: Phase 8 (the serving infrastructure, multiview grid, threaded server and bandwidth cap every feature here rides on)
**Requirements**: MVW-04, MVW-05, WHY-01, WHY-02, WHY-03, WHY-04, SCV-01, UXT-01, UXT-03
**Success Criteria** (what must be TRUE):

  1. The console renders the live "why": per-camera framing-score bars (a leaderboard with tracking/coast/lost state) from `preview.json`, the current choice's reason in plain Italian from `status.reason` ("Auto: miglior inquadratura" / "Override operatore" / "Soggetto perso → SAFE"), and a CSS/SVG dog-lock bbox drawn on the live tile from the sidecar box coords (no image processing in Flask)
  2. Override is informed and direct: clicking any multiview tile forces that camera (replacing the blind text buttons), "Rilascia (auto)" remains a distinct control, and during an override the console shows which camera the auto-director would pick right now ("auto vuole vs in onda") plus a switch-history strip of recent cuts + reasons from the sidecar ring — so the operator knows when it is safe to release
  3. As the operator types a score, the console shows a live client-side preview of exactly how it will look on the OBS overlay (reusing `render_overlay_text`, no orchestrator round-trip) (SCV-01)
  4. The whole console is responsive and tablet-first: the grid reflows, override targets are large touch targets, the live cam + reason stay visible, and the score form is usable one-handed (UXT-01)
  5. Long-run hygiene holds on the real operator tablet: a multi-hour soak keeps tab memory and server thread count flat (no leak), sleep/wake resumes a fresh preview, and a freshness stamp/staleness overlay guarantees a frozen frame is never shown as "live" — the preview degrades first, the director never (UXT-03)

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Config & Curated Clip Set | 4/4 | Complete   | 2026-06-09 |
| 2. Framing Scorer (pure logic) | 4/4 | Complete   | 2026-06-09 |
| 3. Decision Engine FSM | 4/4 | Complete   | 2026-06-09 |
| 4. YOLO + Per-Camera Tracking on Clips | 4/4 | Complete   | 2026-06-09 |
| 5. Integration — NDI Mock, Orchestrator, OBS & Score UI | 9/9 | Complete   | 2026-06-11 |
| 6. Decision-loop latency optimization | 3/3 | Complete    | 2026-06-13 |
| 7. Off-tick Frame-Publishing Channel | 4/4 | Complete   | 2026-06-13 |
| 8. Console Serving, Live Multiview & Safety Hardening | 3/3 | Complete   | 2026-06-13 |
| 9. Explainability, Informed Override & Tablet UX | 0/? | Not started | - |
