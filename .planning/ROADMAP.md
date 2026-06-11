# Roadmap: Segugio

## Overview

Segugio v1 delivers an operator-less multi-camera auto-director for dog sports (disc dog + agility), **software-complete on synthetic data** — recorded clips as pseudo-cameras and a mock NDI source, no hardware. The journey is a strict dependency chain of unit-testable layers: a central config contract plus a curated multi-condition clip set front-load the de-risk; a pure framing scorer turns per-detection signals into per-camera scores; a decision FSM becomes the single source of truth on "which camera is live" with no flicker and no dead-feed cuts; YOLO + one-tracker-per-camera proves subject selection against the hardest clips; and a final integration phase wires NDI mock, orchestrator, OBS control, watchdog, and the manual score UI end-to-end, closing the milestone. Each phase is independently verifiable on the dev box before integration near the end.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation, Config & Curated Clip Set** - Project scaffolding, validated central YAML config (the contract every module consumes), the multi-condition clip set, and synthetic stream generators (completed 2026-06-09)
- [x] **Phase 2: Framing Scorer (pure logic)** - Resolution-independent per-camera framing score with EMA, zone-gating, lead-room, coast/TTL and per-camera confidence normalization — pure and unit-testable (completed 2026-06-09)
- [x] **Phase 3: Decision Engine FSM** - The single source of truth on "which camera is live": hysteresis, dwell, debounce, cooldown, feed-alive guard, action-hold, occlusion-hold, tiebreaker, override + auto-resume (completed 2026-06-09)
- [x] **Phase 4: YOLO + Per-Camera Tracking on Recorded Clips** - Pre-trained YOLO on CUDA with one BoT-SORT tracker per camera (native ReID), competitor-lock and plausibility gate, validated on the curated clips (completed 2026-06-09)
- [ ] **Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI** - End-to-end wiring with no hardware: mock NDI ingest, feed watchdog + fallback, OBS controller, manual score-entry UI, orchestrator tick + fault isolation, latency measurement

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

**Plans**: 6 plans (Wave 1: 05-01 · Wave 2 parallel: 05-02, 05-03, 05-04, 05-05 · Wave 3: 05-06)
**UI hint**: yes

Plans:

**Wave 1**

- [x] 05-01-PLAN.md — Foundation: full Wave-0 test scaffold + conftest fixtures + `ndi`/`obs` markers + Flask dep; the atomic-file `opcomm` channel (atomic write + frozen records + boundary-safe channel, SCR-01); additive `ActionHoldParams` config (D-08 seeds); `FrameSource`/`ObsController` interfaces; additive `CompetitorLock.locked_motion_energy()` accessor [Wave 1]

**Wave 2** *(parallel; blocked on Wave 1 — zero file overlap)*

- [x] 05-02-PLAN.md — NDI ingest: in-process clip-replay mock `FrameSource` + empty-frame guard (NDI-03); real cyndilib `FrameSource` (supervised per-camera threads, last-NEW-frame liveness, NDI-01); mock NDI `Sender` publishing named sources (NDI-02, E2E-only) [Wave 2]
- [x] 05-03-PLAN.md — OBS controller: `RecordingObsController` fake (camera→scene mapping + cached PIP id, OBS-01/02) + real obsws-python v5 controller (cut/PIP/overlay/reconnect/EventClient, OBS-01/02/03/05) + scene-collection template (OBS-04) [Wave 2]
- [ ] 05-04-PLAN.md — Feed watchdog: pure last-NEW-frame `FeedWatchdog` liveness on injected timestamps (RBT-01) + feed-death fallback + guarded rejoin against the locked `DecisionEngine` (RBT-02) [Wave 2]
- [ ] 05-05-PLAN.md — Score manager + UI: pure per-discipline overlay renderer (display-only, SCR-04) + Flask operator console (separate process, score/run/override POSTs + status poll, SCR-02/03, D-09/10/11) + Italian console page [Wave 2]

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 05-06-PLAN.md — Orchestrator: action-hold from motion energy (D-08) + fixed-rate fault-isolated tick (the grown-up `run_clip_eval`) + SAFE shutdown + D-11 status write (RBT-04) + decision-loop latency harness (RBT-05) [Wave 3]

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Config & Curated Clip Set | 4/4 | Complete   | 2026-06-09 |
| 2. Framing Scorer (pure logic) | 4/4 | Complete   | 2026-06-09 |
| 3. Decision Engine FSM | 4/4 | Complete   | 2026-06-09 |
| 4. YOLO + Per-Camera Tracking on Clips | 4/4 | Complete   | 2026-06-09 |
| 5. Integration — NDI Mock, Orchestrator, OBS & Score UI | 3/6 | In Progress|  |
