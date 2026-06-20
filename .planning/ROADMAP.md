# Roadmap: Segugio

## Milestones

- ✅ **v1.0 MVP** — Phases 1–6 (shipped 2026-06-13) — operator-less multi-camera auto-director, software-complete on synthetic data
- ✅ **v1.1 Console Regia** — Phases 7–9 (shipped 2026-06-14) — live-visibility operator console: see the cameras, understand *why*, override informed
- 🚧 **v1.2 Overlay Grafico Broadcast** — Phases 10–14 (in progress) — animated graphical OBS browser-source score overlay served by the crash-isolated console, client-side run timer, curated OBS scene collection — director never touched

> Full phase detail for shipped milestones is archived in `.planning/milestones/v1.1-ROADMAP.md` (the v1.1 close snapshot captures the complete Phase 1–9 history).

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

### 🚧 v1.2 Overlay Grafico Broadcast (In Progress)

**Milestone Goal:** Replace the text-on-file score overlay with an animated graphical broadcast lower-third — rendered as an OBS browser-source served by the crash-isolated console — plus a curated OBS scene-collection. The console still imports ONLY `Flask + segugio.opcomm`; the director/orchestrator is never imported or modified; transport is fetch-polling (no WebSocket/MJPEG/SSE); the overlay is display-only (SCR-04, shows operator-typed values verbatim, never adjudicates). This is *publish-and-render* over the existing opcomm-over-files channel — the same shape proven by the v1.1 preview channel.

**Build order is dependency-forced:** data contract → renderer → SCV-01 unification → OBS wiring → live-robustness hardening. `server_now` (clock-skew anchor) must be in the contract from the first commit; the renderer can only be repointed/wired once it serves a live URL; cross-component degrade behavior can only be validated after the whole path is assembled.

- [x] **Phase 10: Overlay Data Contract & Run-Timestamp Publish** - New console-owned `overlay_run.json` + `GET /overlay-json` (boundary-safe, `server_now`+`gen`), zero HTML, crash-isolation re-verified (completed 2026-06-14)
- [x] **Phase 11: Shared Graphical Renderer, /overlay Page & Branding** - Transparent per-discipline lower-third, self-counting clock-skew-safe timer, freshness degrade, sober animations, config logo/theme + identity line
 (completed 2026-06-15)

- [x] **Phase 12: SCV-01 Unification** - Console preview reuses the same `/overlay` renderer (iframe); retire the byte-exact Python↔JS mirror + `/score/preview` drift-guard (completed 2026-06-16)
- [x] **Phase 13: OBS Scene Collection & Setup Docs** - Browser-source wired into every scene (http URL, shutdown/refresh-on-activate OFF), `overlay.txt` text fallback retained, `docs/obs-setup.md` updated (completed 2026-06-16)
- [ ] **Phase 14: Fallback Coexistence & Degrade Hardening** - End-to-end live-robustness gate: console-down/LAN-drop degrade, text fallback airs a score, poll-storm never starves `/command`, HTML-injection escaped

## Phase Details

### Phase 10: Overlay Data Contract & Run-Timestamp Publish

**Goal**: The console publishes everything the overlay needs as a boundary-safe JSON contract, with the run-start instant stamped into a NEW console-owned file — without touching the director or any director-read file. No HTML yet; pure channel + route.
**Depends on**: Phase 9 (v1.1 console + opcomm channel)
**Requirements**: OVD-01, OVD-02, OVD-03, RBT-07
**Success Criteria** (what must be TRUE):

  1. Starting a run stamps `run_started_at` + `running: true` into a NEW console-owned `overlay_run.json` (mirroring the PreviewDoc record contract); stopping a run nulls it — and `runstate.json`, read by the director every tick, is byte-for-byte unchanged
  2. `GET /overlay-json` returns `{discipline, fields (verbatim), running, started_at, server_now, gen}` with `Cache-Control: no-store`, and never raises when a source file is absent/torn/malformed (safe-default payload)
  3. `server_now` (the console's `time.time()` at response) and a monotonic `gen` (bumped on every `/run` and `/score` write, seeded from disk across restart) are present in every response
  4. The crash-isolation import test is green with the heavy stack absent (`torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws`) — the overlay route module imports only Flask + `segugio.opcomm`**Plans**: 4 plans (3 waves)

**Wave 1**

- [x] 10-01-PLAN.md — Wave 0: test scaffolds (opcomm/route/config) + `file_channel` overlay_run fixture key
- [x] 10-02-PLAN.md — Wave 1: `OverlayRunDoc` record + `write_overlay_run`/`read_overlay_run` channel helpers (OVD-01/02)
- [x] 10-03-PLAN.md — Wave 1: `OverlayParams` config section (`overlay.freestyle_duration_s=120`) + `config.example.yaml` (OVD-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10-04-PLAN.md — Wave 2: `GET /overlay-json` route + `/run`+`/score` gen wiring + crash-isolation gate (OVD-01/02/03, RBT-07)

### Phase 11: Shared Graphical Renderer, /overlay Page & Branding

**Goal**: A single shared HTML/CSS/JS renderer serves a transparent, broadcast-quality per-discipline lower-third with a self-counting run timer that is correct across machine clock skew, degrades when data goes stale, animates only on events, and carries configurable branding — all client-side, zero director compute, zero new Python dependency.
**Depends on**: Phase 10
**Requirements**: OVL-01, OVL-02, OVL-03, OVL-04, TMR-01, TMR-02, TMR-03, TMR-04, BRD-01, BRD-02
**Success Criteria** (what must be TRUE):

  1. `GET /overlay` serves a transparent (`html, body` transparent, critical CSS inlined) page that renders the correct per-discipline lower-third (disc T&F: Prese/Zona/Totale · freestyle: Nome+Timer · agility: Tempo/SCT/Faults) with operator-typed values shown verbatim and HTML-escaped — no white flash on load over bright or dark video, title-safe lower band only
  2. The run timer counts by itself client-side and reads ~0 error when the console and OBS machine clocks are deliberately set ~30s apart (offset-cancellation via `server_now`, never raw `Date.now() − started_at`); it counts down for T&F (60s) and freestyle (config-driven duration), counts up vs the typed SCT for agility, freezes at 0 showing "Tempo" for T&F/freestyle, and continues into overtime past SCT for agility
  3. When the data source goes stale (gen stops advancing past the staleness window, or the fetch fails), the timer STOPS and the overlay visibly degrades — a frozen run is never shown as live
  4. The lower-third animates only on events — enter on run start, exit on run stop, a brief pulse on a score-value change — with no perpetual motion, and a configurable logo + CSS-variable color theme plus a persistent identity line (cane/handler + event) render in the plate without ever covering the action area
  5. The crash-isolation import test stays green with the heavy stack absent (all timer/animation/branding logic is client-side; no new Python runtime dependency)

**Plans**: 3 plans (3 waves)

**Wave 1**

- [x] 11-01-PLAN.md — Backend: grow `OverlayParams` (logo/theme/event) + `GET /overlay` route + entrypoint branding injection + RBT-07 crash-isolation gate extended (OVL-01, BRD-01, BRD-02) — completed 2026-06-14

**Wave 2** *(blocked on Wave 1)*

- [x] 11-02-PLAN.md — Transparent FOUC-free `overlay.html`: left accent-bar lower-third skeleton (DOM/CSS-var contract), title-safe band, logo bug, identity line, event-only animation keyframes (OVL-01/02/03/04, BRD-01/02) — completed 2026-06-14

**Wave 3** *(blocked on Wave 2)*

- [x] 11-03-PLAN.md — Shared `overlay-render.js`: sanitize mirror + per-discipline render (textContent sink), offset-cancellation timer (down/up + freeze-at-0/Tempo + agility overtime), gen-age freshness watchdog + degrade (OVL-02/04, TMR-01/02/03/04, BRD-02) — completed 2026-06-14

**UI hint**: yes

### Phase 12: SCV-01 Unification

**Goal**: The console's live score preview renders through the exact same `/overlay` route that OBS loads, making console↔OBS drift structurally impossible and retiring the hand-maintained byte-exact Python↔JS mirror and its drift-guard.
**Depends on**: Phase 11 (the shared renderer/URL must exist first)
**Requirements**: SCV-02
**Success Criteria** (what must be TRUE):

  1. The console live preview loads `/overlay?preview=1` (iframe reuse) instead of the byte-exact JS mirror — both the console preview and the OBS overlay resolve to one renderer at one URL
  2. The byte-exact `render_overlay_text` JS mirror block and the `POST /score/preview` drift-guard are retired (or `/score/preview` downgraded to a parity check for `overlay.txt` only); `render_overlay_text` (Python) survives unchanged as the `overlay.txt` fallback renderer
  3. A parity check confirms the console preview and the OBS-served overlay share the same template + `/overlay-json` shape, and the crash-isolation import test stays green

**Plans**: 3 plans (2 waves)

**Wave 1**

- [x] 12-01-PLAN.md — Wave 0: structural unification test + value cross-check (node JS vs render_overlay_text) + delete test_score_preview.py (D-05/D-07)

**Wave 2** *(blocked on Wave 1)*

- [x] 12-02-PLAN.md — Server `preview=1` flag (get_overlay body-class) + overlay.html force-visible/backdrop CSS + DELETE POST /score/preview (D-03/D-04/D-05, RBT-07)
- [x] 12-03-PLAN.md — console.html: replace preview div with `<iframe src="/overlay?preview=1">` + on-air label; delete the gsd:scv01-mirror block + all wiring (D-01/D-02/D-05)

**UI hint**: yes

### Phase 13: OBS Scene Collection & Setup Docs

**Goal**: Package the transparent overlay browser-source into a curated OBS scene-collection wired into every scene with the correct CEF settings, keep the `overlay.txt` text source as the always-wired fallback, and document the operator setup including the cross-machine LAN URL and CEF cache procedure.
**Depends on**: Phase 11 (the browser-source URL must serve a live page)
**Requirements**: SCN-01, SCN-02, RBT-06
**Success Criteria** (what must be TRUE):

  1. `obs/segugio-scene-collection.json` wires a transparent "Score Overlay" browser-source (http console-LAN-IP URL, `shutdown_source_when_not_visible: false`, `refresh_when_scene_is_active: false`) into every CAM/SAFE/MULTIVIEW/PIP scene, layered above the NDI source — so the overlay never re-flashes or loses timer state on a cut
  2. The `overlay.txt` "read from file" text source remains wired in every scene as the degraded fallback (RBT-06/SCR-01), and `tests/test_scene_template.py` asserts both the browser source (URL + transparency + shutdown=false) and the text source are present in lockstep with the scene names
  3. `docs/obs-setup.md` documents the http browser-source URL, the cross-machine LAN-IP note, the real CEF cache-clear procedure, and the Browser-primary / Text-fallback coexistence policy; a one-paragraph threat re-evaluation is appended to `docs/security.md`

**Plans**: 2 plans (1 wave)

**Wave 1**

- [x] 13-01-PLAN.md — Score Overlay browser_source + per-scene wiring (z-order top, text fallback visible:false) + extended lockstep test (SCN-01, RBT-06)
- [x] 13-02-PLAN.md — docs/obs-setup.md browser-source section (URL/transparency/CEF cache/coexistence) + docs/security.md threat re-eval (SCN-02, RBT-06)

**UI hint**: yes

### Phase 14: Fallback Coexistence & Degrade Hardening

**Goal**: Validate the whole assembled live path under failure — the live-robustness gate before field acceptance — proving the broadcast never goes scoreless, never shows a stale timer as live, and the safety-critical override path is never starved.
**Depends on**: Phase 11 + Phase 13
**Requirements**: RBT-06
**Success Criteria** (what must be TRUE):

  1. Killing the console freezes the overlay timer within the staleness window and degrades the overlay visually, while the `overlay.txt` text source keeps airing the last score (Browser-primary / Text-fallback coexistence proven end-to-end)
  2. A LAN drop stops the timer (never a stale "live"), and a console restart re-anchors the timer via `gen` without a phantom jump
  3. An `/overlay-json` poll storm does not starve the safety-critical `/command` POST (the UXT-02 concurrency test extended to the new route)
  4. Operator-entered score values are HTML-escaped at the overlay HTML sink (Jinja autoescape on or `textContent` not `innerHTML`) — no injection into the broadcast overlay; the crash-isolation import test stays green

**Plans**: TBD

## Progress

**Execution Order:** Phases executed in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

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
| 10. Overlay Data Contract & Run-Timestamp Publish | v1.2 | 4/4 | Complete    | 2026-06-14 |
| 11. Shared Graphical Renderer, /overlay Page & Branding | v1.2 | 3/3 | Complete    | 2026-06-15 |
| 12. SCV-01 Unification | v1.2 | 3/3 | Complete    | 2026-06-16 |
| 13. OBS Scene Collection & Setup Docs | v1.2 | 2/2 | Complete    | 2026-06-16 |
| 14. Fallback Coexistence & Degrade Hardening | v1.2 | 0/TBD | Not started | - |
