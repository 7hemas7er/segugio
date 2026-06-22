# Roadmap: Segugio

## Milestones

- ✅ **v1.0 MVP** — Phases 1–6 (shipped 2026-06-13) — operator-less multi-camera auto-director, software-complete on synthetic data
- ✅ **v1.1 Console Regia** — Phases 7–9 (shipped 2026-06-14) — live-visibility operator console: see the cameras, understand *why*, override informed
- ✅ **v1.2 Overlay Grafico Broadcast** — Phases 10–14 (shipped 2026-06-20) — animated graphical OBS browser-source score overlay served by the crash-isolated console, client-side run timer, curated OBS scene collection — director never touched
- 🚧 **v1.3 Gestione Punteggi Avanzata** — Phases 15–18 (started 2026-06-21) — score-entry becomes a RICH, SHARED component (dedicated page + console modal) with server-authoritative auto-calc/validation, config-driven scoring profiles, multi-throw/round, single-judge multi-criteria freestyle — single on-air score only, console still crash-isolated, director never touched

> Full phase detail for shipped milestones is archived in `.planning/milestones/` (`v1.1-ROADMAP.md` captures the Phase 1–9 history; `v1.2-ROADMAP.md` captures Phases 10–14).

## Phases

### v1.3 Gestione Punteggi Avanzata (Phases 15–18) — ACTIVE

- [ ] **Phase 15: Pure Calc + Validation Core & Scoring Profiles** — the stdlib-only `score_calc` authority (validate + compute for disc T&F / freestyle / agility) + config-driven scoring profiles, added to the crash-isolation import gate before any UI consumes it
- [ ] **Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST** — the ONE vanilla-JS score-entry component proven on the dedicated `/score-entry` page, advisory client calc with a drift-guard, and `POST /score` made authoritative (validate→400 / recompute→atomic write)
- [ ] **Phase 17: Console Modal, Multi-throw State & Tablet UX** — the same component mounted in a native `<dialog>` modal (single Jinja partial), multi-throw/round progressive total with reload-safe in-progress state, explicit publish action + offline-asset/≥16px/focus-trap tablet contract
- [ ] **Phase 18: Rich Data Model & Overlay-Continuity Regression** — structured `fields` (throws[]/criteria{}/faults_breakdown{}) carried additively through the write path + `/overlay-json`, with `overlay.txt` / `/overlay` / OBS fallback and the XSS sink verified unchanged

## Phase Details

### Phase 15: Pure Calc + Validation Core & Scoring Profiles
**Goal**: The single authoritative scoring brain exists and is crash-isolation-safe — one pure stdlib module computes and validates every discipline's score, driven by config-driven profiles, before any UI can consume it.
**Depends on**: Nothing (first v1.3 phase; builds on the shipped v1.2 console/opcomm surface)
**Requirements**: SCC-02, SCC-04, SCP-01, SCP-02, RBT-08
**Success Criteria** (what must be TRUE):
  1. Given raw inputs for any of the three disciplines, the module returns a correctly auto-calculated total — disc T&F sums throws×zone (+ bonus), freestyle sums single-judge criteria, agility applies the configured model (count-up faults OR deduct-from-100) plus time-faults vs SCT (verifiable by unit tests against the pinned per-federation rule tables).
  2. Given invalid inputs (out-of-range, missing required field, malformed `mm:ss` time), the module reports per-field validation errors rather than computing a result.
  3. Swapping the active scoring profile (zones/points, fault table, freestyle criteria/scale, agility model) changes the computed result with NO code change; a malformed profile fails fast at config-load with a clear error.
  4. The console import-smoke gate passes with the full heavy stack and numpy ABSENT while now also covering `score_calc` — i.e. the new module imports clean and a `POST /score` round-trip resolves with torch/cv2/ultralytics/numpy/cyndilib/obsws unavailable.
**Plans**: 3 plans
  - [ ] 15-01-PLAN.md — pure-stdlib score_calc.py (ScoringProfile + validate + compute for all 3 disciplines) + unit tests vs pinned CSEN tables
  - [ ] 15-02-PLAN.md — config-driven scoring-profile pydantic sub-model + pydantic→stdlib adapter + CSEN/FIDASC/FCI fixtures + swap/malformed tests (FIDASC numbers human-verify gated)
  - [ ] 15-03-PLAN.md — crash-isolation gate extension (score_calc → PHASE1_SURFACE + heavy-absent POST /score round-trip)

### Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST
**Goal**: An operator can enter a score on a dedicated full-screen page using ONE shared component with live advisory feedback, and the server is the sole authority that validates and recomputes what airs.
**Depends on**: Phase 15
**Requirements**: SCE-01, SCE-02, SCE-03, SCE-05, SCC-01, SCC-03
**Success Criteria** (what must be TRUE):
  1. The operator opens the dedicated `/score-entry` page, picks a discipline, and sees the rich per-discipline structured fields from the active scoring profile.
  2. As the operator types, a running total updates live (advisory) and per-field validation errors appear before publishing.
  3. Submitting POSTs RAW inputs only; the server validates (returns 400 and writes NOTHING on invalid input, leaving any previous on-air score untouched) and recomputes the total in Python before writing atomically.
  4. For the same inputs, the form-displayed total equals the value the server writes — proven both by the round-trip acceptance test (form total === `overlay.txt` line === `/overlay-json`-rendered total) and by the JS↔Python drift-guard test (the advisory client calc never becomes a second authority).
**Plans**: TBD
**UI hint**: yes

### Phase 17: Console Modal, Multi-throw State & Tablet UX
**Goal**: The operator can enter and publish a score from inside the console via a popup that reuses the exact same component, accumulate multi-throw/round entries without losing them, and do it all reliably on the offline-rig tablet.
**Depends on**: Phase 16
**Requirements**: SCE-04, SCC-05
**Success Criteria** (what must be TRUE):
  1. The operator opens a console `<dialog>` modal and enters a score using the SAME component as the dedicated page — both hosts share one Jinja form partial and one JS module, so the page and the modal are byte-for-byte the same form (no duplicated calc/submit logic, no re-introduced mirror).
  2. For multi-throw disc T&F the operator adds/edits throws across N rounds and sees a correct progressive running total; reloading the tablet mid-run restores the in-progress entry (no lost throws), and any persisted in-progress state is written atomically with a never-raise reader.
  3. Publishing to air is a deliberate, visually distinct action — a casual tap or Enter cannot put a half-entered score on air.
  4. The new page and modal load with ZERO external/CDN assets, all inputs are ≥16px (no iOS focus-zoom), and the modal traps focus and survives sleep/wake — code-time tablet contract met (real-iPad rig UAT deferred, non-blocking).
**Plans**: TBD
**UI hint**: yes

### Phase 18: Rich Data Model & Overlay-Continuity Regression
**Goal**: The richer structured score rides through the publish path additively, and every shipped overlay contract — graphical `/overlay`, `/overlay-json`, the `overlay.txt` text fallback, and the HTML sink — is verified unbroken.
**Depends on**: Phases 15–17
**Requirements**: RBT-09
**Success Criteria** (what must be TRUE):
  1. After a rich `POST /score`, `score.json` and `/overlay-json` carry the structured subkeys (throws[]/criteria{}/faults_breakdown{}) ALONGSIDE all preserved flat summary keys; no legacy `/overlay-json` key is renamed or removed.
  2. `overlay.txt` is still written on every publish as a single non-empty line (length-bounded per field), and the OBS read-from-file text fallback shows the current score — regression-verified, not assumed.
  3. The `/overlay` graphical renderer still displays the score from the flat keys, and the host page bakes in NO score data (stays thin/poll-only).
  4. New free-text fields (dog/handler name, judges) are HTML-escaped at the sink — no `innerHTML`, no `| safe`; a crafted `<script>` name renders as inert escaped text both on the overlay and in any form preview.
**Plans**: TBD
**UI hint**: yes

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

## Progress

**Execution Order:** Phases executed in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18

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
| 15. Pure Calc + Validation Core & Scoring Profiles | v1.3 | 0/3 | Planned | - |
| 16. Shared Entry Component, Dedicated Page & Server-Authoritative POST | v1.3 | 0/? | Not started | - |
| 17. Console Modal, Multi-throw State & Tablet UX | v1.3 | 0/? | Not started | - |
| 18. Rich Data Model & Overlay-Continuity Regression | v1.3 | 0/? | Not started | - |
