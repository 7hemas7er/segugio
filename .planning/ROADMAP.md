# Roadmap: Segugio

## Milestones

- ✅ **v1.0 MVP** — Phases 1–6 (shipped 2026-06-13) — operator-less multi-camera auto-director, software-complete on synthetic data
- ✅ **v1.1 Console Regia** — Phases 7–9 (shipped 2026-06-14) — live-visibility operator console: see the cameras, understand *why*, override informed
- ✅ **v1.2 Overlay Grafico Broadcast** — Phases 10–14 (shipped 2026-06-20) — animated graphical OBS browser-source score overlay served by the crash-isolated console, client-side run timer, curated OBS scene collection — director never touched

> Full phase detail for shipped milestones is archived in `.planning/milestones/` (`v1.1-ROADMAP.md` captures the Phase 1–9 history; `v1.2-ROADMAP.md` captures Phases 10–14).

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
| 10. Overlay Data Contract & Run-Timestamp Publish | v1.2 | 4/4 | Complete | 2026-06-14 |
| 11. Shared Graphical Renderer, /overlay Page & Branding | v1.2 | 3/3 | Complete | 2026-06-15 |
| 12. SCV-01 Unification | v1.2 | 3/3 | Complete | 2026-06-16 |
| 13. OBS Scene Collection & Setup Docs | v1.2 | 2/2 | Complete | 2026-06-16 |
| 14. Fallback Coexistence & Degrade Hardening | v1.2 | 3/3 | Complete | 2026-06-20 |
