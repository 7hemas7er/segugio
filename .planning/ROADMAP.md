# Roadmap: Segugio

## Milestones

- ✅ **v1.0 MVP** — Phases 1–6 (shipped 2026-06-13) — operator-less multi-camera auto-director, software-complete on synthetic data
- ✅ **v1.1 Console Regia** — Phases 7–9 (shipped 2026-06-14) — live-visibility operator console: see the cameras, understand *why*, override informed
- ✅ **v1.2 Overlay Grafico Broadcast** — Phases 10–14 (shipped 2026-06-20) — animated graphical OBS browser-source score overlay served by the crash-isolated console, client-side run timer, curated OBS scene collection — director never touched
- ✅ **v1.3 Gestione Punteggi Avanzata** — Phases 15–18 (shipped 2026-06-28) — score-entry becomes a RICH, SHARED component (dedicated page + console modal) with server-authoritative auto-calc/validation, config-driven scoring profiles, multi-throw/round, single-judge multi-criteria freestyle — single on-air score only, console still crash-isolated, director never touched
- 🚧 **v1.4 Validazione sul Campo (Field Readiness)** — Phases 19–23 (started 2026-07-09) — from *software-complete* to *field-proven*: real-footage detection eval + `yolo26s` fine-tune decision, framing/tracking calibration on real clips, residual security hardening, a physical NDI-HX3-phone rig end-to-end on the deploy GPU, and closure of the deferred v1.1/v1.2 on-rig UATs — validation/hardening only, NO new user features; console stays crash-isolated, director never redesigned

> Full phase detail for shipped milestones is archived in `.planning/milestones/` (`v1.1-ROADMAP.md` captures the Phase 1–9 history; `v1.2-ROADMAP.md` captures Phases 10–14; `v1.3-ROADMAP.md` captures Phases 15–18). Requirements per milestone are archived alongside (`v1.X-REQUIREMENTS.md`). Detail for the ACTIVE milestone lives in `## Phase Details` below.

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–6) — SHIPPED 2026-06-13</summary>

- [x] **Phase 1: Foundation, Config & Curated Clip Set** (4/4 plans) — completed 2026-06-09 — package scaffolding, validated central YAML config contract, multi-condition clip set, synthetic stream generators
- [x] **Phase 2: Framing Scorer (pure logic)** (4/4 plans) — completed 2026-06-09 — resolution-independent per-camera framing score with EMA, zone-gating, lead-room, coast/TTL, confidence normalization — pure & unit-testable
- [x] **Phase 3: Decision Engine FSM** (4/4 plans) — completed 2026-06-09 — single source of truth on the live camera: hysteresis, dwell, debounce, cooldown, feed-alive guard, action/occlusion hold, tiebreaker, override + auto-resume
- [x] **Phase 4: YOLO + Per-Camera Tracking on Recorded Clips** (4/4 plans) — completed 2026-06-09 — pre-trained YOLO on CUDA, one BoT-SORT tracker per camera (native ReID), competitor-lock + plausibility gate, validated on curated clips
- [x] **Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI** (9/9 plans) — completed 2026-06-11 — end-to-end wiring with no hardware: mock NDI ingest, feed watchdog + fallback, OBS controller, manual score UI, fault-isolated orchestrator, latency harness
- [x] **Phase 6: Decision-loop latency optimization** (3/3 plans) — completed 2026-06-13 — TensorRT FP16 export + batched FP16 inference; RBT-05 met under the revised <300ms p95 budget on the RTX 4000 Ada Laptop GPU

</details>

<details>
<summary>✅ v1.1 Console Regia (Phases 7–9) — SHIPPED 2026-06-14</summary>

- [x] **Phase 7: Off-tick Frame-Publishing Channel** (4/4 plans) — completed 2026-06-13 — the GATING foundation: `PreviewPublisher` daemon + `atomic_write_bytes` + `preview.json` sidecar publish per-camera JPEG thumbnails + "why" data off the director's critical tick (PRV-01/02/03), crash-isolation proven
- [x] **Phase 8: Console Serving, Live Multiview & Safety Hardening** (3/3 plans) — completed 2026-06-13 — responsive multiview grid + LIVE/tally + dead-feed marking, `threaded=True`/Waitress safety fix, config-time bandwidth cap, written threat re-eval (MVW-01/02/03, UXT-02)
- [x] **Phase 9: Explainability, Informed Override & Tablet UX** (4/4 plans) — completed 2026-06-13 (on-device iPad acceptance 2026-06-14) — score bars, plain-Italian reason, dog-lock bbox overlay, "auto wants vs aired" hint, switch-history, live score preview, clickable-tile overrides, tablet-first restyle, leak/sleep/freshness hygiene (MVW-04/05, WHY-01..04, SCV-01, UXT-01/03)

</details>

<details>
<summary>✅ v1.2 Overlay Grafico Broadcast (Phases 10–14) — SHIPPED 2026-06-20</summary>

- [x] **Phase 10: Overlay Data Contract & Run-Timestamp Publish** (4/4 plans) — completed 2026-06-14 — NEW console-owned `overlay_run.json` + boundary-safe `GET /overlay-json` (`server_now` clock anchor + monotonic `gen`), zero HTML, crash-isolation re-verified (OVD-01/02/03, RBT-07)
- [x] **Phase 11: Shared Graphical Renderer, /overlay Page & Branding** (3/3 plans) — completed 2026-06-15 — transparent FOUC-free per-discipline lower-third, self-counting offset-cancellation timer (skew-safe), gen/response freshness degrade, event-only animations, config logo/theme + identity line (OVL-01..04, TMR-01..04, BRD-01/02)
- [x] **Phase 12: SCV-01 Unification** (3/3 plans) — completed 2026-06-16 — console preview becomes an `<iframe src="/overlay?preview=1">` reusing the one renderer OBS loads; byte-exact Python↔JS mirror + `/score/preview` drift-guard deleted — drift structurally impossible (SCV-02)
- [x] **Phase 13: OBS Scene Collection & Setup Docs** (2/2 plans) — completed 2026-06-16 — transparent browser-source wired into every scene (http LAN URL, shutdown/refresh-on-activate OFF) above the NDI source, `overlay.txt` text fallback retained, `docs/obs-setup.md` + security threat re-eval (SCN-01/02, RBT-06)
- [x] **Phase 14: Fallback Coexistence & Degrade Hardening** (3/3 plans) — completed 2026-06-20 — two-stage degrade (`DEAD_MS` auto-hide so no frozen score airs), `overlay.txt` single-writer coexistence, poll-storm never starves `/command`, HTML-sink escaping; live-robustness gate (RBT-06). Physical on-rig UAT (LAN-drop / overlay.txt) deferred as non-blocking carry-forward (D-02)

</details>

<details>
<summary>✅ v1.3 Gestione Punteggi Avanzata (Phases 15–18) — SHIPPED 2026-06-28</summary>

- [x] **Phase 15: Pure Calc + Validation Core & Scoring Profiles** (3/3 plans) — completed 2026-06-22 — the gating authority: a stdlib-only `score_calc` (validate + Decimal-exact compute for disc T&F / freestyle / agility) + config-driven scoring profiles (pydantic `ScoringProfile` on the CFG-03 union, CSEN default, fail-fast on malformed), added to the crash-isolation import gate before any UI consumes it (SCC-02/04, SCP-01/02, RBT-08)
- [x] **Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST** (2/2 plans) — completed 2026-06-23 — the ONE vanilla-JS `score-entry.js` component proven on the dedicated `/score-entry` page (rich per-discipline fields, live best-5-of-N advisory total, on-blur errors), the advisory `score-calc.js` pinned by a node-vs-Python drift-guard, and `POST /score` made authoritative (validate→400-write-nothing / Decimal-recompute→atomic write) (SCE-01/02/03/05, SCC-01/03)
- [x] **Phase 17: Console Modal, Multi-throw State & Tablet UX** (2/2 plans) — completed 2026-06-27 — the same component mounted in a native console `<dialog>` via ONE shared Jinja partial (drift structurally impossible), reload-safe localStorage draft, two-step danger-styled publish (Enter never publishes), legacy `#form-score` path retired; code-time tablet contract (≥16px inputs, focus-trap, zero CDN assets) (SCE-04, SCC-05)
- [x] **Phase 18: Rich Data Model & Overlay-Continuity Regression** (2/2 plans) — completed 2026-06-27 — structured `fields` (`throws[]`/`criteria{}`/`faults_breakdown{}`) carried additively as `str(Decimal)` through the write path + `/overlay-json` (6-key envelope + per-discipline legacy flat keys frozen by a golden snapshot), identity free-text wired XSS-inert via `createTextNode`/`textContent`, `overlay.txt` single-line + thin `/overlay` regression-verified (RBT-09)

</details>

### 🚧 v1.4 Validazione sul Campo (Field Readiness) — Phases 19–23 (ACTIVE, started 2026-07-09)

- [ ] **Phase 19: Detection Eval on Real Footage & Fine-tune Decision** — source & catalog a multi-venue real corpus, label ground-truth, measure recall AND precision on the FP16 batched *shipped* path, and write the motivated `yolo26s` fine-tune decision (DET-01..04) — *desk work: real footage + dev-box GPU*
- [ ] **Phase 20: Framing & Tracking Calibration on Real Clips** — retune framing seeds to the real distant-dog scale (2-5%, not 0.30) and tracking seeds to real tunnels/occlusions, config-only, no ID-churn (CAL-01/02) — *desk work; depends on the Phase 19 eval*
- [ ] **Phase 21: Residual Security Hardening** — close the P15 scoring-validation bounds + the P16 `/overlay-json` echo length-cap, crash-isolation preserved (SEC-01/02) — *desk work, independent (2 pre-specified pending todos)*
- [ ] **Phase 22: Hardware Rig Bring-up & Deploy-GPU Validation** — 3-4 NDI HX3 phones on dedicated WiFi 6 + OBS/DistroAV + orchestrator on the deploy GPU, end-to-end auto-switching, p95 confirmed on-rig, real-WiFi feed-drop robustness (RIG-01..04) — *REQUIRES THE PHYSICAL RIG*
- [ ] **Phase 23: On-Rig UAT Closure** — sign off the deferred v1.2 overlay UATs (console-death / LAN-drop / `overlay.txt`), the v1.1/P17 real-iPad tablet UX, and the preview-bandwidth false-death with real phones (UAT-01..03) — *REQUIRES THE PHYSICAL RIG*

## Phase Details

> Active milestone (v1.4) only. Shipped-milestone phase detail is archived in `.planning/milestones/v1.{1,2,3}-ROADMAP.md`.

### Phase 19: Detection Eval on Real Footage & Fine-tune Decision
**Goal**: Know the SHIPPED detector's real recall AND precision on the hard field conditions (distant/small dog, backlight, motion-blur, multi-dog, tunnel occlusion) and make a motivated `yolo26s` fine-tune decision — measured on the FP16 batched path that actually ships, not on the `lock_held` proxy or the eager FP32 serial `track()` of the P04 UAT.
**Depends on**: Nothing (first v1.4 phase). Desk work — real footage + the dev-box CUDA GPU (venv312); requires a real multi-venue corpus sourced first (today = one `gara_full.mp4`).
**Requirements**: DET-01, DET-02, DET-03, DET-04
**Success Criteria** (what must be TRUE):
  1. A multi-venue corpus covering BOTH disc dog and agility is cataloged via `tools/catalog_clips.py` with the condition checklist populated across all five hard cases (distant/small dog, backlight, motion-blur, multi-dog, tunnel occlusion) — no longer a single clip.
  2. A representative subset carries labeled ground-truth "in-competition" dog bboxes usable as the recall/precision reference.
  3. Recall AND precision are reported per condition — measured on the FP16 batched shipped path — including distant-dog recall and handler/shadow false-lock, not just the `lock_held` proxy.
  4. A written, metrics-backed fine-tune decision (fine-tune vs. ship COCO `dog` as-is) exists; if fine-tune, the produced weight loads drop-in via the config `path` key with zero code change.
**Scope (v1.4)**: disc-only — the eval covers the owner's real disc footage; agility (and disc `tunnel_contact_occlusion`) is carried-forward/deferred until real agility footage with consent exists (D-01/D-02). DET-01/DET-03 are satisfied as disc across the hard conditions.
**Plans**: 5 plans (3 waves)
- [ ] 19-01-PLAN.md — Pure detection-metrics core (iou/score_frame/aggregate) + GT sidecar parse/validate + CPU tests [wave 1]
- [ ] 19-02-PLAN.md — Disc corpus scoping: new slices, re-catalogue, agility carry-forward + scope notes [wave 1]
- [ ] 19-03-PLAN.md — opencv GT labeling tool (cv2.selectROI, detector-independent) + labeled GT subset [wave 2]
- [ ] 19-04-PLAN.md — FP16 batched recall/precision harness (run_detection_eval) + gpu test [wave 2]
- [ ] 19-05-PLAN.md — Run the harness + write the metrics-backed fine-tune decision doc (19-DECISION.md) [wave 3]

### Phase 20: Framing & Tracking Calibration on Real Clips
**Goal**: Retune the framing and tracking seeds to the REAL distant-dog scale so the camera actually holds the small dog and the same track survives real tunnels/occlusions — replacing the synthetic-clip defaults, config-only.
**Depends on**: Phase 19 (you cannot calibrate framing/tracking seeds until the eval tells you the detector's real recall on the distant/small dog). Desk work — real clips + dev-box GPU.
**Requirements**: CAL-01, CAL-02
**Success Criteria** (what must be TRUE):
  1. Framing seeds (`ideal_size`, `motion_deadzone`, lead-room) are re-set to the real distant-dog scale (2-5% of frame, not 0.30) and demonstrably keep the dog in frame on real clips.
  2. Tracking seeds (`track_buffer`, `max_displacement`, plausibility gate) are tuned on real occlusion/tunnel clips so a dog that leaves and re-enters keeps the same track ID — no spurious ID-churn.
  3. The retuned seeds are captured entirely in config (no code change) — the recalibration is config-only.
**Plans**: TBD

### Phase 21: Residual Security Hardening
**Goal**: Close the two accepted P15/P16 security residuals so a crafted score input can neither air an out-of-federation total nor grow the `/overlay-json`/`score.json` payload unboundedly — without touching the console's crash-isolation.
**Depends on**: Nothing (independent desk work; both fixes are pre-specified in `.planning/todos/pending/`). Can run in parallel with Phases 19–20.
**Requirements**: SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. Out-of-range scoring input (e.g. freestyle all-10 + `adjustment="-50"`) is rejected under the 400 + write-nothing contract or capped after adjustment, so the on-air score is never touched — pinned by a regression test.
  2. Negative/unbounded profile scalars (`freestyle_max`, `time_fault_rate`, `fault_value`) fail-fast at config load with `SystemExit(2)`, symmetric with the already-bounded sibling fields.
  3. Echoed field values on `POST /score` → `/overlay-json`/`score.json` are length-capped (a `>N`-char numeric or free-text value is rejected/truncated and never reaches the payload), fixed in one general place.
  4. Console crash-isolation is preserved — import surface still `Flask + segugio.opcomm + score_calc`, the heavy-deps-absent import gate stays green.
**Plans**: TBD

### Phase 22: Hardware Rig Bring-up & Deploy-GPU Validation
**Goal**: Prove the auto-director runs end-to-end on the real physical rig — 3-4 NDI HX3 phones on dedicated WiFi 6 + OBS/DistroAV + orchestrator on the deploy GPU — switching the right camera without an operator, within budget, without crashing under real network contention.
**Depends on**: Phase 20 (runs the calibrated framing/tracking seeds) and Phase 19 (runs the decided model config). **REQUIRES THE PHYSICAL RIG** — 3-4 real phones, dedicated WiFi 6, OBS+DistroAV, the deploy GPU; carries on-rig human verification and CANNOT be closed at the dev desk.
**Requirements**: RIG-01, RIG-02, RIG-03, RIG-04
**Success Criteria** (what must be TRUE):
  1. The orchestrator decodes live NDI HX3 feeds from 3-4 real phones (NDICam iOS / NDI Camera Android, NDI 6.3.2 runtime), with liveness deduced from the last-NEW-frame timestamp — a stalled phone is detected as dead, never held "vivo".
  2. The full pipeline runs on the rig — phones → OBS+DistroAV (PROGRAM) + independent Python ingest (AI) → OBS scene switching via obs-websocket — auto-selecting the best camera with no operator.
  3. The decision-loop p95 is confirmed < 300ms on the deploy GPU under sustained load (no thermal throttle like the laptop); if the TensorRT engine is used it is exported on the target GPU.
  4. Under real WiFi contention with 3-4 competing feeds, dropping a feed degrades to SAFE / another live camera with no crash; the Ethernet-tether mitigation (USB-C/Lightning adapter) is documented.
**Plans**: TBD

### Phase 23: On-Rig UAT Closure
**Goal**: Close the deferred v1.1/v1.2 hardware-gated UATs on the real rig — the graphical overlay behaves correctly in real OBS, the console tablet-UX holds on a real iPad over a long session, and the preview-bandwidth cap protects real phone feeds.
**Depends on**: Phase 22 (the rig must be up before these UATs can run on it). **REQUIRES THE PHYSICAL RIG** — real OBS, a real iPad, real phones; carries the human-UAT sign-offs deferred from v1.1/v1.2 and CANNOT be closed at the dev desk.
**Requirements**: UAT-01, UAT-02, UAT-03
**Success Criteria** (what must be TRUE):
  1. In real OBS the deferred v1.2 overlay UATs are signed off — console-death auto-hides the lower-third (no frozen score airs), a LAN-drop re-anchors the run timer via `gen` on recovery, and the `overlay.txt` text-source coexists as the fallback.
  2. On a real iPad over a prolonged session the v1.1/P17 tablet UX is confirmed — multiview, tap-to-force override, and the score-entry modal are usable, memory stays flat, and sleep/wake resume works.
  3. With real phones the preview-bandwidth false-death is validated — the `max_total_mbps` cap degrades the preview BEFORE the NDI feeds appear dead.
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:** Phases executed in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22 → 23

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation, Config & Curated Clip Set | v1.0 | 4/4 | Complete | 2026-06-09 |
| 2. Framing Scorer (pure logic) | v1.0 | 4/4 | Complete | 2026-06-09 |
| 3. Decision Engine FSM | v1.0 | 4/4 | Complete | 2026-06-09 |
| 4. YOLO + Per-Camera Tracking on Clips | v1.0 | 4/4 | Complete | 2026-06-09 |
| 5. Integration — NDI Mock, Orchestrator, OBS & Score UI | v1.0 | 9/9 | Complete | 2026-06-11 |
| 6. Decision-loop latency optimization | v1.0 | 3/3 | Complete | 2026-06-13 |
| 7. Off-tick Frame-Publishing Channel | v1.1 | 4/4 | Complete | 2026-06-13 |
| 8. Console Serving, Live Multiview & Safety Hardening | v1.1 | 3/3 | Complete | 2026-06-13 |
| 9. Explainability, Informed Override & Tablet UX | v1.1 | 4/4 | Complete | 2026-06-13 |
| 10. Overlay Data Contract & Run-Timestamp Publish | v1.2 | 4/4 | Complete | 2026-06-14 |
| 11. Shared Graphical Renderer, /overlay Page & Branding | v1.2 | 3/3 | Complete | 2026-06-15 |
| 12. SCV-01 Unification | v1.2 | 3/3 | Complete | 2026-06-16 |
| 13. OBS Scene Collection & Setup Docs | v1.2 | 2/2 | Complete | 2026-06-16 |
| 14. Fallback Coexistence & Degrade Hardening | v1.2 | 3/3 | Complete | 2026-06-20 |
| 15. Pure Calc + Validation Core & Scoring Profiles | v1.3 | 3/3 | Complete | 2026-06-22 |
| 16. Shared Entry Component, Dedicated Page & Server-Authoritative POST | v1.3 | 2/2 | Complete | 2026-06-23 |
| 17. Console Modal, Multi-throw State & Tablet UX | v1.3 | 2/2 | Complete | 2026-06-27 |
| 18. Rich Data Model & Overlay-Continuity Regression | v1.3 | 2/2 | Complete | 2026-06-27 |
| 19. Detection Eval on Real Footage & Fine-tune Decision | v1.4 | 0/5 | Planned | - |
| 20. Framing & Tracking Calibration on Real Clips | v1.4 | 0/— | Not started | - |
| 21. Residual Security Hardening | v1.4 | 0/— | Not started | - |
| 22. Hardware Rig Bring-up & Deploy-GPU Validation | v1.4 | 0/— | Not started | - |
| 23. On-Rig UAT Closure | v1.4 | 0/— | Not started | - |
