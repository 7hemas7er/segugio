# Roadmap: Segugio

## Overview

Segugio v1 delivers an operator-less multi-camera auto-director for dog sports (disc dog + agility), **software-complete on synthetic data** — recorded clips as pseudo-cameras and a mock NDI source, no hardware. The journey is a strict dependency chain of unit-testable layers: a central config contract plus a curated multi-condition clip set front-load the de-risk; a pure framing scorer turns per-detection signals into per-camera scores; a decision FSM becomes the single source of truth on "which camera is live" with no flicker and no dead-feed cuts; YOLO + one-tracker-per-camera proves subject selection against the hardest clips; and a final integration phase wires NDI mock, orchestrator, OBS control, watchdog, and the manual score UI end-to-end, closing the milestone. Each phase is independently verifiable on the dev box before integration near the end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation, Config & Curated Clip Set** - Project scaffolding, validated central YAML config (the contract every module consumes), the multi-condition clip set, and synthetic stream generators
- [ ] **Phase 2: Framing Scorer (pure logic)** - Resolution-independent per-camera framing score with EMA, zone-gating, lead-room, coast/TTL and per-camera confidence normalization — pure and unit-testable
- [ ] **Phase 3: Decision Engine FSM** - The single source of truth on "which camera is live": hysteresis, dwell, debounce, cooldown, feed-alive guard, action-hold, occlusion-hold, tiebreaker, override + auto-resume
- [ ] **Phase 4: YOLO + Per-Camera Tracking on Recorded Clips** - Pre-trained YOLO on CUDA with one BoT-SORT tracker per camera (native ReID), competitor-lock and plausibility gate, validated on the curated clips
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
- [ ] 01-04-PLAN.md — Deterministic synthetic generators: seeded score-stream (ping-pong/tie/dropout/recovery) + feed-death timelines for hardware-free unit testing of scorer/FSM/watchdog [Wave 2]

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
**Plans**: TBD

Plans:
- [ ] 02-01: Base score (centeredness + size target-band + confidence) + per-camera EMA smoothing
- [ ] 02-02: Zone-gating via `framing_weights[role][zone]` multiplier + lead-room (velocity-biased target)
- [ ] 02-03: Coast/TTL on detection dropout + per-camera confidence normalization + shadow-FP guard
- [ ] 02-04: Unit-test suite over synthetic detection sequences proving purity and all behaviors

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
**Plans**: TBD

Plans:
- [ ] 03-01: Core FSM (states + guarded transitions) as single source of truth + hysteresis/min_dwell/debounce/cooldown
- [ ] 03-02: Feed-alive guard, action-suppression hold, expected-occlusion hold, deterministic tiebreaker
- [ ] 03-03: Manual override + auto-resume transition logic
- [ ] 03-04: Unit-test suite over synthetic score + feed-death streams (ping-pong/tie/dropout/recovery/override/occlusion)

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
**Plans**: TBD

Plans:
- [ ] 04-01: YOLO load on CUDA + class resolution via `model.names`; one tracker per camera over recorded pseudo-cameras
- [ ] 04-02: BoT-SORT native-ReID config (`botsort_dog.yaml`) + startup ReID-engagement verification
- [ ] 04-03: Normalized per-detection signal extraction (cx/cy, w/h, conf, id) feeding the scorer
- [ ] 04-04: Competitor-lock + plausibility/teleport gate, validated on multi-dog/handler/occlusion clips

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
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 05-01: NDI ingest via cyndilib (FrameSync → numpy BGR, supervised per-camera threads) + empty-frame guard
- [ ] 05-02: Mock/synthetic NDI source publishing recorded clips as named NDI sources
- [ ] 05-03: OBS controller (cut, PIP via cached sceneItemId, reconnect, EventClient) + scene-collection template + read-from-file overlay
- [ ] 05-04: Feed watchdog (last-new-frame timestamp) + automatic fallback + guarded rejoin
- [ ] 05-05: Score manager (atomic file write) + manual score-entry UI (discipline selector, 3 field sets, run start/stop)
- [ ] 05-06: Orchestrator tick + fault isolation + SAFE shutdown + decision-loop latency measurement

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Config & Curated Clip Set | 3/4 | In Progress|  |
| 2. Framing Scorer (pure logic) | 0/4 | Not started | - |
| 3. Decision Engine FSM | 0/4 | Not started | - |
| 4. YOLO + Per-Camera Tracking on Clips | 0/4 | Not started | - |
| 5. Integration — NDI Mock, Orchestrator, OBS & Score UI | 0/6 | Not started | - |
