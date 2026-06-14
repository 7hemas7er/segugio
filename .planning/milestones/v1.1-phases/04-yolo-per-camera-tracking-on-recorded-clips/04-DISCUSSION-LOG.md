# Phase 4: YOLO + Per-Camera Tracking on Recorded Clips - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 4-yolo-per-camera-tracking-on-recorded-clips
**Areas discussed:** Pseudo-cameras from clips, Competitor-lock strategy (TRK-04), Plausibility gate behavior (TRK-05), Tracking verification / deliverable

---

## Pseudo-cameras from clips

### Q1 — How to build "multiple cameras" from single-camera footage?

| Option | Description | Selected |
|--------|-------------|----------|
| Spatial crops of the wide shot | Overlapping crop windows = simultaneous framings of the same dog; real per-camera pixel isolation; crops yield frame-exit/re-entry for free | ✓ |
| Distinct condition slices as cameras | sprint_blur=cam1, distant=cam2…; proves isolation but cameras show different moments | |
| Both: crops + slices | Crops for same-scene, slices for pure isolation | |
| Single-cam now, defer multi-cam to Phase 5 | One tracker on one clip; true multi-cam waits for the NDI mock | |

**User's choice:** Spatial crops of the wide shot
**Notes:** Crops also give frame-exit/re-entry for free — exactly what `track_buffer:60` + native ReID exist to survive. Competitor-lock is fundamentally a single-camera operation (pick the right track within one frame); multi-camera only matters for the no-ID-mixing isolation proof and Phase-5 cross-camera selection.

### Q2 — Handle the missing agility + two-dog-crossing footage?

| Option | Description | Selected |
|--------|-------------|----------|
| Validate disc-dog now, flag the rest | Run TRK-01..05 on available disc-dog slices; log agility-occlusion + two-dog-crossing as UNVERIFIED; no fake footage | ✓ |
| Supplement with CC0 stock clips | Pull Pexels/Pixabay agility-tunnel + multi-dog clips to fill the checklist | |
| Engineer crossings from crops | Synthesize crossing/occlusion-like events from overlapping crop windows | |

**User's choice:** Validate disc-dog now, flag the rest
**Notes:** Corpus is single-camera disc-dog only. `handler_close_01` + `crowd_distractor_01` cover handler/bystander for competitor-lock. No fake/stock footage; code paths exist but aren't clip-proven for agility/crossings.

---

## Competitor-lock strategy (TRK-04)

### Q1 — What makes a dog track "the competitor"?

| Option | Description | Selected |
|--------|-------------|----------|
| Zone-gate + motion-energy | In-field (config zones) AND most cumulative motion; autonomous; matches PITFALLS Pitfall 1 | ✓ |
| Zone-gate only | In-field dog wins; no motion discriminator (standing bystander could win) | |
| Motion-energy only | Most-moving dog; no spatial gate (running bystander could steal lock) | |
| Largest/most-central dog | The naive "best blob" anti-pattern PITFALLS warns against | |

**User's choice:** Zone-gate + motion-energy
**Notes:** Detector filters to dog class only, so persons/handlers are never candidates — lock disambiguates among dog tracks. No run-start signal on clips (SCR-03 is Phase 5), so acquisition is autonomous.

### Q2 — How is the lock maintained?

| Option | Description | Selected |
|--------|-------------|----------|
| Sticky continuity, re-acquire only on loss | Keep the locked ID while alive; re-select only on loss (track_buffer expired) or plausibility-flagged swap | ✓ |
| Re-evaluate best candidate every tick | Pick best zone+motion dog each frame; flips to bystander on brief out-motion | |
| Sticky + periodic re-confirm | Stick but periodically re-check; catches a wrong initial lock at cost of churn | |

**User's choice:** Sticky continuity, re-acquire only on loss
**Notes:** Prevents ping-ponging the lock mid-run (PITFALLS Pitfall 2 — continuity over per-frame score).

### Q3 — Per-camera or global subject identity? (derived, not asked)

**Derived decision:** Per-camera independent lock. A global cross-camera identity needs cross-camera ReID, which PROJECT defers as "heavy ReID." Cross-camera agreement is emergent (same dog), not enforced. (User given the chance to object; none raised.)

---

## Plausibility gate behavior (TRK-05)

### Q1 — On teleport/size-jump of the locked track, what does the selector do?

| Option | Description | Selected |
|--------|-------------|----------|
| Hold locked track + mark uncertain → coast | Reject the suspect box; mark uncertain; emit coast (no DetectionSignal → scorer FRM-05 coast/TTL) | ✓ |
| Drop detection entirely → scorer coasts | Same coast outcome, simpler, no "uncertain" state tracked | |
| Immediately re-acquire by zone+motion | Instantly re-run selection; risks oscillation if the jump was a real fast move | |

**User's choice:** Hold locked track + mark uncertain → coast
**Notes:** Dovetails with the scorer's existing FRM-05 coast path. Flagged for planner: TRK-05 is a NEW inter-frame track-continuity gate, distinct from Phase-2's intra-frame detection guard; adds config seeds `max_displacement_per_tick` + `max_size_ratio` (additive placement).

---

## Tracking verification / deliverable

### Q1 — Prove tracking works with no ground-truth labels?

| Option | Description | Selected |
|--------|-------------|----------|
| Both: debug-overlay video + logged metrics | Render overlays to eyeball + log ID-switch count, % lock-held, coast/uncertain counts, signal dump | ✓ |
| Debug-overlay video only | Eyeball, no asserted numbers; no regression safety | |
| Logged metrics only | Numbers asserted, no video; can't see if lock is on the right dog | |
| Hand-label a small GT subset | Real recall/ID-switch/MOTA numbers; real labor, likely overkill for v1 | |

**User's choice:** Both: debug-overlay video + logged metrics

### Q2 — Test structure given YOLO needs GPU + weights?

| Option | Description | Selected |
|--------|-------------|----------|
| Split: pure-logic deterministic + GPU-gated integration | Competitor-lock/plausibility LOGIC on synthetic inputs (CPU/deterministic); YOLO-on-clips GPU-gated/skipped | ✓ |
| Everything as GPU integration tests | All tests run real YOLO; nothing runs in CPU CI; breaks the pure-logic pattern | |
| You decide | Defer to planner | |

**User's choice:** Split: pure-logic deterministic + GPU-gated integration
**Notes:** Keeps the brain unit-testable on any box; isolates heavy I/O at the edge (matches the lazy-import boundary, mirrors FRM-07/DEC-07).

---

## Claude's Discretion

- Module layout (likely `src/segugio/tracking/`), honoring the lazy-import boundary
- `botsort_dog.yaml` location (where `check_yaml` finds it)
- 50fps-vs-~30Hz frame sampling/striding (keep `tick` an injected frame index)
- Crop window geometry (count, overlap, aspect → `cam_id` + zones)
- Motion-energy / zone-gate exact formulation (window length, in-zone test, combination)
- `model.names` class resolution + reconcile with configured `class_index`

## Deferred Ideas

- Agility-tunnel-occlusion + two-similar-dogs-crossing validation — until real footage is provided
- Detection-in-occlusion-zone → FSM `occlusion_hold` wiring — Phase 5
- Cross-camera ReID / global subject identity — heavy ReID, deferred per PROJECT
- Disc/frisbee detection, pose model, custom/fine-tuned dog model — v2
- ByteTrack latency fallback / TensorRT FP16 export — only if loop blows budget / hardware milestone
- Numeric threshold calibration (gate thresholds, motion window, crop geometry) — config seeds, opportunistic
