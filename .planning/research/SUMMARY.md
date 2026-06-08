# Project Research Summary

**Project:** Segugio
**Domain:** Operator-less multi-camera video direction (auto-director) for dog sports — disc dog & agility
**Researched:** 2026-06-09
**Confidence:** MEDIUM-HIGH (technical stack HIGH/locked; domain CV-framing MEDIUM-HIGH; scoring/rules HIGH; hardware-milestone bits MEDIUM)

## Executive Summary

Segugio is an automatic, no-operator video director for dog-sports competitions: 3-4 phones publish NDI HX3 feeds, OBS is the video hub, and a Python orchestrator tracks the dog with a pre-trained YOLO model on GPU, scores per-camera framing, and switches the live OBS scene smoothly via obs-websocket while overlaying competition scores. The **single core value is "the right camera at the right moment, automatically, smoothly"** — no flicker, never on a dead feed. The **technical stack is LOCKED** (see `TECHNICAL-RESEARCH.md`): Python + `ultralytics`/`torch` YOLO + `cyndilib` NDI ingest + OBS/DistroAV + `obsws-python` v5 + `transitions` FSM, with two deliberately decoupled pipelines — an accepted ~150-350ms glass-to-glass *video* path and a ~70-150ms *control* loop (the only one optimized, running on frames OBS already has).

**The v1 milestone is software-complete on SYNTHETIC data** (recorded clips as pseudo-cameras + a mock NDI source), preview-only output, manual score entry, manual override + auto-resume — **every phase through the milestone is hardware-free** and runs on the dev box (Linux/WSL2 + CUDA). The domain research adds the concrete weights and tuning the locked stack left generic: ship **`yolo26s.pt`** filtering **COCO `dog` = class 16**, with one **BoT-SORT tracker per camera** using **native-feature ReID** (`with_reid: True, model: auto`, `track_buffer: 60`). The architecture research supplies the load-bearing domain artifacts the locked modules consume: a **per-camera image-normalized field-zone model (no calibration in v1)**, **4 camera roles** (`main_wide`/`long`/`low`/`handler_side`), a **role×zone framing-weight multiplier**, and a concrete **OBS scene template**.

**The dominant risk is not technical — it is computer-vision subject-selection** under real dog-sports conditions (a prominent handler, bystander dogs, motion blur at the climax, occlusion, distance, harsh outdoor light). The decisive de-risking action is to **assemble a curated multi-condition clip set early** (multi-dog, handler-prominent, occlusion, blur, distant, backlit, midfield-equidistant) so these failures surface in software, not on the field. This research promotes two subject-selection features the original plan lacked — **competitor-lock** and **zone-gating** — to first-class scorer/decision concerns, and (notably) **relaxes the PROJECT.md "re-ID deferred" stance**, because native-feature ReID is essentially free.

## Key Findings

### Recommended Stack

The core stack is **locked and must not be re-researched** — the domain work only pins the generic "Ultralytics YOLO" to concrete weights, class indices, and tracker config (all YAML/config, no architecture change). The v1 pin is unambiguous and config-swappable.

**Core technologies (locked, from TECHNICAL-RESEARCH.md):**
- **Python orchestrator + `transitions` FSM** — single source of truth for "which camera is live"; tick at ~30Hz, fault-isolated, never crashes.
- **`ultralytics` + `torch` (CUDA)** — per-camera `model.track(frame, persist=True, classes=[...])`; one tracker per camera (NEVER a list of frames — issue #13107 mixes IDs).
- **`cyndilib` NDI ingest (+ mock source for v1)** — FrameSync always-latest; liveness from last-*new*-frame timestamp, never NDI source state (75-min false-liveness).
- **`obsws-python` v5** — `ReqClient` (sync) + `EventClient` (thread); cut via `SetCurrentProgramScene`; PIP via `SetSceneItemTransform`/`SetSceneItemEnabled` with cached numeric `sceneItemId`.
- **`opencv`, `numpy`, `pyyaml`, `loguru`, `watchdog`** — supporting libs.

**Concrete v1 stack pin (domain additions, from STACK.md):**
- **Model:** `yolo26s.pt` (YOLO26 small — current SOTA Jan 2026, NMS-free → lower tail latency). `n` is a config fallback for a weak GPU; `m` for measuring the recall ceiling only. Pin `ultralytics>=8.3.x` and verify `YOLO("yolo26s.pt")` resolves before committing.
- **Class filter:** COCO **`dog` = class 16** (0-indexed). Verified `frisbee`=29, `person`=0. **Always read `model.names` at startup** (a custom mono-class model is index 0, not 16).
- **Tracker:** **BoT-SORT** (`botsort_dog.yaml`) with **`with_reid: True, model: auto`** (native features = zero extra weights/near-zero cost), **`track_buffer: 60`** (~2s, survives tunnel/occlusion), `gmc_method: sparseOptFlow` (set `None` for locked tripods later). ByteTrack is the *latency-pressure* fallback only.
- **DECISION CHANGE — re-ID is now v1, not deferred.** PROJECT.md lists "re-ID pesante deferred / out of scope." Native-feature ReID is **not heavy** — it costs no extra download and dramatically improves ID persistence through jumps/tunnels/handler occlusion, which is exactly this domain's failure mode. **Recommendation: relax the PROJECT.md out-of-scope item and include native-ReID BoT-SORT in v1.** (Heavy *external* ReID `.pt` weights remain out of scope.)
- **Datasets/fixtures (v1):** no packaged disc-dog/agility *video* benchmark exists. Source 3-5 short clips from **Pexels/Pixabay (CC0)** as committed CI fixtures; optionally `yt-dlp` real competition clips kept **local/un-committed** (license each). Add `tests/fixtures/README.md`.
- **LATER (not v1):** disc detection (`classes=[16,29]`, needs fine-tuning), pose model + Dog-Pose dataset, NDI phone apps (NDICam iOS / official NDI Camera), custom dog model (only if eval proves COCO `dog` misses).

### Expected Features

The engine is **identical across disciplines**; what changes per sport is the **overlay field set** and **framing-bias defaults** — both config (see FEATURES.md). **Hard anti-feature line: the system DISPLAYS scores, it never ADJUDICATES** (no CV fault/catch/score detection — that is the judge's authoritative job).

**Must have (table stakes — all v1, all testable on synthetic data):**
- Subject always in frame; best-framed-camera selection (centeredness + size + confidence, EMA per camera).
- Smooth, non-flickering cuts (FSM hysteresis + min_dwell + debounce + cooldown) — the "works vs nauseating" differentiator.
- Never cut to a dead/frozen feed (watchdog on last-new-frame timestamp).
- Safe fallback scene when no good shot exists; manual override + auto-resume; no-crash fault isolation.
- Live discipline-aware score overlay via file (atomic write → OBS read-from-file); config-driven field/camera setup; AI loop <~150ms.

**Should have (cheap, high-value v1 differentiators):**
- **Competitor-lock + zone-gating** for subject selection (promoted from pitfalls — see Critical Pitfalls; the highest-value additions).
- **Lead-room toward motion** (velocity-biased framing target — cheap, big perceived-quality win).
- **Simple velocity-based predictive framing** (short linear horizon).
- **Manual run start/stop button** (doubles as the run-segmentation signal → overlay reset, timer, replay markers); **manual PIP toggle**; **manual timer**; **operator tally/state readout** ("on air" + AUTO/OVERRIDE).
- **Manual score-entry UI:** discipline selector (disc-toss-fetch / disc-freestyle / agility), 3 per-discipline field sets, big increment buttons for counters, name-card from start-list.

**Defer (v2+ / hardware / geometry milestones):**
- Real hardware (phones/NDI/field); recording/streaming output; external scoring API; CV score/fault/run detection.
- Course-geometry / homography; obstacle-aware framing (agility); catch-zone framing (disc); anticipatory camera selection; auto-PIP timing; shot-variety engine.
- Disc/frisbee anticipation; pose model; custom-trained model; PTZ; digital zoom; audio/graphics packages.

### Architecture Approach

The locked software modules are NOT redesigned. The architecture research (ARCHITECTURE.md) maps **physical sport → camera placement → field-zone config → framing weight → OBS scenes**, producing the concrete config schema and scene names the locked modules consume. The domain coupling is one small, declarative idea: **`score = base_framing × framing_weights[role][zone]`**, where zones are per-camera image-normalized rects (no calibration) and `main_wide` is a neutral-weighted, floored SAFE net.

**Major components / seeded artifacts:**
1. **Field-zone model (config.yaml)** — per-camera normalized rects `[x0,y0,x1,y1]` mapping image regions to logical zones (near/mid/far/stage). **Option A (per-camera image zones, no homography) for v1**; shared-plane homography is the documented LATER upgrade.
2. **Camera roles (4-role template, degrades to 3)** — `main_wide` (SAFE/default, neutral weights + `safe_min_score` floor), `long`/`end_zone` (wins when dog is far — primary for disc downfield catches), `low`/`hero` (near + airborne only, used sparingly), `handler_side` (freestyle stage / handler-side obstacles; the 4th camera).
3. **Role×zone weight multiplier** — the entire sport→scorer coupling; tunable from YAML, leaves FSM/EMA/OBS untouched. `field.sport`+`field.event` is a profile switch, not separate code paths.
4. **OBS scene template** — `CAM Wide` (doubles as SAFE) / `CAM Long` / `CAM Low` / `CAM Handler`, plus first-class `SAFE` scene and optional `MULTIVIEW`/`PIP` (idle/debug only in v1). Scene names are the config↔OBS contract; document in the setup README.

### Critical Pitfalls

The domain pitfalls (PITFALLS.md) carry almost the entire v1 risk and are **fully exercisable on recorded clips before any hardware**. The top five:

1. **Locks onto the handler / a bystander dog instead of the competitor** — size+centeredness reward the biggest, most-central, most-stable dog-shaped blob, which is often the handler-adjacent region or a calm ringside dog, not the small fast athlete. **Avoid:** make subject selection first-class — **competitor-lock** (anchor the track at run start, prefer continuity) + **zone-gate** (exclude detections outside the field/course bounds) + **motion energy** signal. *Single-dog clips hide this entirely.* (P1 scorer + P3 validate.)
2. **ID swap competitor↔handler-path↔second dog corrupts "which camera is live"** — similar dogs (border collies) crossing, pairs runs, occlusion re-entry. **Avoid:** treat track ID as advisory; add a **plausibility/teleport gate** (max per-frame displacement, max size-ratio change → hold, don't cut on a suspect track); exploit the one-dog-on-course prior. Native-ReID BoT-SORT mitigates this materially. (P3 + P2.)
3. **Motion blur / dropped detections at the climax → director cuts away from the moment** — the apex of a catch/jump is the most-blurred, most-missed frame, and a confidence-gated score collapses to zero. **Avoid:** **coast/TTL** (hold last-known subject 0.3-0.7s before "lost"); low *continuation* confidence floor; treat detection gaps during high motion as "action in progress, hold." Hard-gating score to 0 on a miss is **never** acceptable. (P1 + P2.)
4. **Cutting mid-climax & chasing jitter** — cutting mid-catch/mid-jump/mid-weave destroys the shot; equidistant-midfield score noise causes cut-storms. **Avoid:** FSM **action-suppression state** (raise switch threshold / freeze during a jump/catch/weave); **contention tiebreaker** (prefer current live cam, then the cam the dog moves toward); **motion-adaptive EMA + dead-zone** (a single fixed alpha either lags sprints or twitches at rest). (P1 + P2.)
5. **Small-at-distance, occlusion, and outdoor light bias** — a `w*h` size term punishes the camera that has the (small) real action; tunnels/A-frames/weaves break agility tracking; per-camera lighting variance glues the director to the brightest camera. **Avoid:** size as a *mild* preference with a target band (not monotonic), centeredness/lock-continuity over raw size; **expected-occlusion hold** at marked occluder zones; **per-camera confidence normalization** + shadow-FP heuristic. (P1 + P3 on varied clips.)

> **Disc-vs-agility split:** occlusion (tunnels/contacts) is primarily *agility*; disc/frisbee handling is *disc-dog-only* — keep disc logic optional and disc-scoped so it never misfires on agility footage.

## Implications for Roadmap

The PITFALLS phase map and the synthetic-data milestone constraint produce a clear hardware-free phase spine (P0-P4 = milestone v1). Phases 1-3 carry almost the entire domain-pitfall load.

### Phase 0: Scaffolding + Config + Curated Clip Set
**Rationale:** The single decisive de-risking action is sourcing the curated multi-condition clip set *first* — without it, every later phase looks done on single-dog midday clips while pitfalls lie dormant. Config schema is the contract every module consumes.
**Delivers:** Project structure; central `config.yaml` with validation (cameras, roles, **per-camera image-normalized zones**, `framing_weights[role][zone]`, switching thresholds, `safe_camera`/`safe_min_score`, EMA alpha); `tests/fixtures/` clip set (Pexels/Pixabay CC0) spanning **multi-dog, handler-prominent, tunnel/contact, jump/sprint-blur, distant, backlit/dusk, midfield-equidistant** for both disc dog and agility, with a license README.
**Addresses:** Config-driven field/camera setup (table stakes).
**Avoids:** "Looks done but isn't" — the curated clip set is the prerequisite for catching Pitfalls 1-5/8-10.

### Phase 1: Framing Scorer (pure, no I/O)
**Rationale:** Pure, unit-testable function; carries the largest share of domain-pitfall prevention. Must be right before the FSM consumes it.
**Delivers:** `base = f(centeredness, size, conf)` + **role×zone weight multiplier** + per-camera EMA; **coast/TTL**, **motion-energy signal**, **zone-gate**, **size target-band** (not monotonic), **lead-room (velocity-biased target)**, **motion-adaptive smoothing + dead-zone**, **per-camera confidence normalization**, shadow-FP guard.
**Implements:** Framing scorer (locked) + ARCHITECTURE zone multiplier.
**Avoids:** Pitfalls 1 (zone-gate/motion), 3 (coast/TTL), 4 (size-band), 8 (adaptive smooth), 9 (lead-room), 10 (conf-norm).

### Phase 2: Decision Engine FSM
**Rationale:** Consumes per-camera scores; the sole authority on "which camera is live." Depends on P1.
**Delivers:** FSM with hysteresis_margin + min_dwell + debounce_N + cooldown + feed-alive guard; **action-suppression state** (no cut mid-climax); **contention tiebreaker**; **expected-occlusion hold**; manual override + auto-resume; SAFE transition.
**Implements:** Decision engine (locked); never double-cut, never flicker, never cut on dead/suspect feed.
**Avoids:** Pitfalls 2 (consume plausibility gate), 4/7 (action-suppression, tiebreaker), 5 (expected-occlusion hold).

### Phase 3: YOLO + One-Tracker-Per-Camera on Recorded Clips
**Rationale:** Where subject-selection and tracking are *proven* against the curated clip set — the highest-value validation in the whole project.
**Delivers:** `yolo26s.pt` + COCO `dog`=16 (verified via `model.names`); **one BoT-SORT tracker per camera** with native-ReID `botsort_dog.yaml`; **competitor-lock**, **plausibility/teleport gate**, subject-track continuity feeding the FSM; recorded videos as pseudo-cameras.
**Uses:** STACK.md model/class/tracker pins.
**Avoids:** Pitfalls 1, 2, 5 validated here; multi-dog/handler/pairs/occlusion clips are mandatory test material.

### Phase 4: NDI-Mock + Orchestrator + OBS + Score UI (v1 milestone close)
**Rationale:** Wires everything end-to-end with no hardware; closes the software-complete-on-synthetic-data milestone.
**Delivers:** `obsws-python` controller against the **OBS scene template** (`CAM *`, `SAFE`, optional `MULTIVIEW`/`PIP`); **mock NDI source** + ingest; feed watchdog; **manual score-entry UI** (discipline selector, 3 field sets, run start/stop as segmentation signal, PIP/timer toggles, tally readout) → atomic file → OBS read-from-file; orchestrator tick, fault isolation, SAFE shutdown; local preview.
**Implements:** obs_controller, ndi_ingest+mock, score_manager, feed_watchdog, orchestrator (all locked).
**Avoids:** UX pitfalls (surface *why* SAFE: subject-lost vs feed-dead vs override); anti-feature line (manual scores only, system displays never adjudicates).

### Phases 5-7 (LATER — hardware / geometry, OUT of v1)
Real phones/NDI/field; NDI sender apps; TensorRT FP16 export on deploy GPU; homography/course-geometry config → obstacle-aware + catch-zone + anticipatory framing; auto run-detection (real timer); disc anticipation; recording/streaming; external scoring API.

### Phase Ordering Rationale
- **Dependencies:** config (P0) → pure scorer (P1) → FSM consuming scores (P2) → tracker feeding real subject selection (P3) → full wiring (P4). Each phase is independently testable.
- **Risk-first:** the curated clip set (P0) and scorer pitfall-prevention (P1) front-load the cheapest place to discover the expensive failures.
- **Hardware-free spine:** P0-P4 deliberately avoid all hardware; everything is exercisable on recorded clips + mock NDI on the dev box.

### Research Flags
Phases likely needing `--research-phase` during planning:
- **Phase 1:** the framing-scorer math is dense and novel for this domain (lead-room velocity model, motion-adaptive alpha, per-camera confidence normalization, size target-band, zone multiplier). Worth a focused planning pass.
- **Phase 3:** verify native-ReID actually engages on `yolo26s` in your `ultralytics` version (it silently falls back to a downloaded cls model if the head is end2end); validate competitor-lock + plausibility-gate design on the multi-dog clips.

Phases with standard patterns (skip research-phase):
- **Phase 0:** scaffolding/config + clip sourcing — mechanical, well-understood.
- **Phase 2:** FSM is fully specified in TECHNICAL-RESEARCH.md (guards, dead-band); only the action-suppression/tiebreaker/occlusion-hold additions are new and are small.
- **Phase 4:** obs-websocket v5 + score-file pattern are documented and pinned in TECHNICAL-RESEARCH.md; the score UI is straightforward CRUD over the field schema.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core locked; YOLO26 weights, class indices (COCO `dog`=16, `frisbee`=29), BoT-SORT params all verified via Ultralytics docs + Context7 + coco.yaml/botsort.yaml. Only NDI phone apps + fixture sourcing are MEDIUM (web-only, hardware-milestone). |
| Features | MEDIUM-HIGH | Scoring/overlay field sets HIGH (official rulebooks: Toss & Fetch, USDDN/Skyhoundz, AKC/UKC/USDAA). Auto-direction feature mapping MEDIUM — no off-the-shelf disc-dog/agility auto-director exists to benchmark; synthesized from sports-broadcast CV + cinematography. |
| Architecture | MEDIUM-HIGH | Sport dimensions/layout HIGH (rulebooks). Camera roles + zone weights MEDIUM — synthesized from broadcast convention + sport geometry; weights are heuristics needing tuning on real footage. |
| Pitfalls | MEDIUM-HIGH | CV failure modes verified against MOT/sports-tracking literature + automated-broadcast post-mortems; dog-sports specifics inferred from sport mechanics + analogous ball/soccer tracking. |

**Overall confidence:** MEDIUM-HIGH — technical path is locked and verified; the genuine uncertainty is in the *heuristics* (framing weights, scorer thresholds, EMA alpha), all of which are config-tunable and exercisable on the curated clip set before any hardware.

### Gaps to Address
- **Framing weights & scorer thresholds are heuristics** (role×zone table, EMA alpha, size band, lead-room clamp, TTL windows). Keep all in config; tune on the curated clip set in P1/P3; expect per-venue re-tuning later. Never hardcode.
- **COCO `dog` recall on real disc-dog/agility footage** is unmeasured (distance, motion-blur, mid-air contortion, dark coat on dark turf, backlight). Measure in P3; a custom/fine-tuned model is out of v1 scope but the measurement decides whether the wide cameras are usable and whether a later milestone needs it.
- **Native-ReID engagement on `yolo26s`** must be verified at startup (P3) — it silently downloads a fallback if the head is end2end.
- **Disc/frisbee as predictor vs distractor** — decide empirically on disc clips (P1/P3); default to ignoring the class if it's a net distractor. Disc-dog-scoped only.
- **No packaged video benchmark exists** — fixture quality depends on curation; the multi-condition checklist in PITFALLS.md is the acceptance bar.
- **Hardware-milestone assumptions** (NDI app latency settings, WiFi behavior with 3-4 phones, TensorRT export on the deploy GPU, homography for course-aware framing) are MEDIUM and validate only on real hardware (P5-P7) — out of v1.

## Sources

### Primary (HIGH confidence)
- `/websites/ultralytics` (Context7) + docs.ultralytics.com (YOLO26, BoT-SORT, tracking) — model sizes, NMS-free, native-ReID logic, tracker thresholds, Dog-Pose dataset.
- coco.yaml / botsort.yaml / bytetrack.yaml (raw GitHub) — verified class indices (`dog`=16, `frisbee`=29, `person`=0) and default tracker params.
- obs-websocket v5 + obsws-python docs — ReqClient/EventClient, scene/scene-item APIs (TECHNICAL-RESEARCH.md baseline).
- Official rulebooks — Toss & Fetch, USDDN/Skyhoundz (PAWS), UpDog, AKC/UKC/USDAA agility (scoring, obstacles, ring/field dimensions, timing).

### Secondary (MEDIUM confidence)
- MOT / sports-tracking literature (SportsTrack, Deep HM-SORT, ByteTrack/BoT-SORT, Ultralytics #7109/#19784/#13107) — ID-swap, motion-blur, occlusion failure modes.
- Automated-broadcast post-mortems (The Broadcast Bridge; Pixellot→Veo practitioner) — wrong-subject attribution, mid-climax cuts, need for human QC.
- Broadcast camera-role + cinematography convention (BoxCast, StreamGeeks, Sony PTZ auto-framing lead-room, rule-of-thirds/lead-room references) — camera roles, lead-room.
- NDI phone apps (ProVideo Coalition, ndi.video, Sienna NDICam), Pexels/Pixabay licenses, yt-dlp, Roboflow Universe frisbee/dog datasets — hardware-milestone + fixture sourcing.

### Tertiary (LOW confidence)
- Disc-dog / agility mechanics blogs (Pawsitive Vybe, SpiritDog, dogs4motion) — domain context (climax = the catch; tunnels as deliberate occluders), not CV evidence.

---
*Research completed: 2026-06-09*
*Ready for roadmap: yes*
