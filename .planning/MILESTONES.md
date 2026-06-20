# Milestones

## v1.2 Overlay Grafico Broadcast (Shipped: 2026-06-20)

**Phases completed:** 5 phases (10–14), 15 plans · ~99 commits, +13,635 / −485 across 98 files (2026-06-14 → 2026-06-20)
**Delivered:** The text-on-file score overlay became an animated graphical broadcast lower-third — a transparent OBS browser-source served by the crash-isolated console with a clock-skew-safe client timer, two-stage freshness degrade, a unified-renderer console preview, and a curated OBS scene-collection — with the director never imported or touched.

**Key accomplishments:**

- **Phase 10 — Overlay data contract:** a NEW console-owned `overlay_run.json` run-edge stamp + boundary-safe `GET /overlay-json` carrying the `server_now` clock anchor and a monotonic `gen`; `runstate.json` (director-read every tick) untouched, zero HTML, crash-isolation re-verified (OVD-01/02/03, RBT-07).
- **Phase 11 — Shared graphical renderer & /overlay page:** a transparent FOUC-free per-discipline lower-third with a self-counting run timer correct across machine clock skew (offset-cancellation via `server_now`, never raw `Date.now() − started_at`), a freshness degrade, event-only animations, and config logo/theme + identity line (OVL-01..04, TMR-01..04, BRD-01/02).
- **Phase 12 — SCV-01/02 unification:** the console preview became `<iframe src="/overlay?preview=1">` reusing the one renderer OBS loads; the byte-exact Python↔JS mirror + `/score/preview` drift-guard deleted — console↔OBS drift structurally impossible (SCV-02).
- **Phase 13 — Curated OBS scene-collection:** a transparent `Score Overlay` browser-source wired top-of-z-order into all 7 scenes (CEF `shutdown:false`/`refresh-on-activate:false`), with `Score Text` retained as the always-wired hidden text fallback (RBT-06); `tests/test_scene_template.py` lockstep guard + `docs/obs-setup.md` (SCN-01/02).
- **Phase 14 — Live-robustness hardening:** a `DEAD_MS` second degrade stage that fully *hides* the lower-third on a real console death (no frozen score airs), `overlay.txt` single-writer coexistence, an `/overlay-json` poll storm that never starves `POST /command`, and HTML-sink escaping — each a named per-criterion gate (RBT-06).

**Quality gates:** the Phase-14 code review caught + fixed a broadcast-integrity blocker (CR-01: the dead-hide was one-way → the overlay would have stayed hidden after a console death+recovery mid-run; the SC#2 gate false-passed it by asserting only clock continuity, not visibility). Security verification closed 9/9 threats (`14-SECURITY.md`). 17/18 v1.2 requirements Complete; SCV-02 awaiting its deferred Phase-12 human-UAT sign-off.

**Known deferred items at close:** physical on-rig UAT — console-death auto-hide confirmed on rig; LAN-drop re-anchor + `overlay.txt` text-source coexistence deferred (non-blocking, D-02). Plus 2 already-executed quick-tasks flagged `unknown` (SUMMARYs present). See STATE.md → Deferred Items.

---

## v1.1 Console Regia (Shipped: 2026-06-14)

**Phases completed:** 3 phases (7–9), 11 plans, ~26 tasks
**Git range:** Phase 7 start (`1de3603`) → `474ec45` · 84 files changed, +12,623 / −181 (26 code files, +3,773 / −119 in `src`/`tests`)
**Delivered:** The operator console goes from a blind control panel to a true regia with live visibility — the operator *sees* every camera, understands *why* the auto-director chose the live one, and overrides from what they see — without touching the v1.0 crash-isolation guarantee (console still imports only Flask + `segugio.opcomm`, never the orchestrator).

**Known deferred items at close:** 7 (see STATE.md → Deferred Items) — all hardware/field-gated carry-forwards (P01/P04/P05 UAT, P01/P05/P07 human verification, 1 quick task already done but flagged `unknown`). Milestone audit status: `tech_debt`, `gaps: []`, 16/16 requirements satisfied in code.

**Key accomplishments:**

- **Off-tick frame-publishing channel (Phase 7, PRV-01/02/03):** a `PreviewPublisher` daemon thread with a single-slot latest-only mailbox (`offer()` never blocks the director's tick) does all resize/encode/IO off the critical path at ~1/fps, writing downscaled per-camera JPEGs via `atomic_write_bytes(fsync=False)` plus a `preview.json` "why" sidecar (framing score, tracking/coast/lost state, normalized dog bbox, FSM auto-candidate, recent-cuts ring). Crash-isolation proven by an import test with the full heavy stack (ultralytics/torch/numpy/cv2/cyndilib/obsws) absent — the console both imports and starts.
- **Live multiview console (Phase 8, MVW-01/02/03):** the crash-isolated Flask console serves the channel via a whitelisted `send_file` JPEG route + a sidecar JSON route, rendering a responsive CSS-Grid multiview of all cameras with flicker-free `Image()` preload-and-swap refresh, an unmistakable LIVE/tally indicator on the on-air tile, and at-a-glance dead/stale "MORTO" marking.
- **Streaming-endpoint safety hardening (Phase 8, UXT-02):** a `threaded=True`/Waitress server so a preview GET can never pin the lone worker and block the safety-critical `/command` override POST; a config-time preview-bandwidth ceiling (`PreviewParams.max_total_mbps`, fail-fast `@model_validator` → `SystemExit(2)`) so the preview degrades before the NDI feeds appear to die; and a written threat re-evaluation (`docs/security.md`) for live competitor video behind `0.0.0.0` with AP client-isolation as a HARD operational requirement.
- **Explainability layer (Phase 9, WHY-01/02/03/04, MVW-05):** a live per-camera framing-score leaderboard with tracking/coast/lost state, the current choice's reason in plain Italian (incl. the `fault` → "Errore sistema → SAFE" case fixed during the audit), a CSS/SVG dog-lock bbox drawn on the live tile (no image-processing in Flask), an "Auto vuole vs in onda" hint during overrides, and a switch-history strip from the cuts ring (newest-first).
- **Informed override + live score preview (Phase 9, MVW-04, SCV-01):** every multiview tile is a tap-to-force control (the blind text buttons removed), "Rilascia (auto)" kept as a distinct always-visible undo, and a byte-exact JS mirror of `render_overlay_text` shows the OBS score overlay as the operator types, with a one-shot `POST /score/preview` drift-guard (pure route, writes nothing).
- **Tablet-first UX + long-run hygiene (Phase 9, UXT-01/03):** a landscape Multiview-left + sidebar-right restyle with the iPad/Safari touch contract (viewport-fit, touch-action, ≥44/48px targets, safe-area); leak-free decode-swap refresh (one persistent off-DOM preloader per tile), a gen-age foreground freshness watchdog + staleness stamp guaranteeing a frozen frame is never shown "live", and `visibilitychange`/`pageshow` sleep-wake resume — accepted on a real iPad (iPadOS 26.x: memory flat, 200ms deferral confirmed).

---

## v1.0 MVP — Software-complete on synthetic data (Shipped: 2026-06-13)

**Phases completed:** 6 phases (1–6), 28 plans
**Delivered:** An operator-less multi-camera auto-director for dog sports (disc dog + agility), software-complete on synthetic data — recorded clips as pseudo-cameras and a mock NDI source, no hardware. A strict dependency chain of unit-testable layers proved subject selection, framing, switching, and end-to-end wiring on the dev box.

*(v1.0 was developed before the formal milestone-close workflow was first run; it is recorded here retroactively at the v1.1 close for a complete historical record. It was not separately git-tagged.)*

**Key accomplishments:**

- **Foundation, config & curated clip set (Phase 1, CFG-01..04, TST-01/02):** an installable `src/segugio/` package (torch-free pinned deps, lazy-import boundary proven by an import-smoke test), a typed pydantic v2 `Config` with a fail-fast `safe_load` loader and a `DiscDogProfile|AgilityProfile` discriminated union that swaps overlay fields + framing defaults with zero code edits, a clip-set cataloguer + opencv-free query API over a 7×2 condition checklist, and seedable synthetic `score_stream`/`feed_death` generators (byte-identical per seed).
- **Framing scorer — pure logic (Phase 2, FRM-01..07):** a pure, I/O-free, resolution-independent per-camera scorer composing 8 numpy-only terms (Gaussian centeredness, non-monotonic size band, EMA z-score confidence normalization, lead-room toward motion, zone-gating × `framing_weights[role][zone]`) with a coast/TTL dropout path that holds the EMA through blur gaps and never collapses to 0 mid-action — 124 tests, 99% coverage.
- **Decision engine FSM (Phase 3, DEC-01..07, RBT-03):** a `transitions`-based FSM as the sole authority on the live camera — guarded transitions only, two-threshold hysteresis + min_dwell + debounce_N + cooldown (zero spurious cuts on ping-pong/tie), feed-death emergency cut, action/occlusion holds with mandatory max-caps, deterministic tiebreaker, and manual override + auto-resume — byte-identical determinism, `segugio.decision` at 100% coverage.
- **YOLO + per-camera tracking (Phase 4, TRK-01..05):** one BoT-SORT tracker per camera with native-feature ReID (`with_reid: True, model: auto`, `end2end=False`), a HARD startup gate that raises on the silent `yolo26n-cls.pt` fallback, a pure `CompetitorLock` (zone ∧ motion, sticky, per-camera) + `PlausibilityGate` (teleport/size-jump → coast), and a PURE/HEAVY-split clip eval — validated in software on the curated multi-condition clips.
- **Integration — NDI mock, orchestrator, OBS & score UI (Phase 5, NDI/OBS/SCR/RBT):** end-to-end with no hardware — a mock NDI source + real cyndilib ingest (supervised per-camera threads, NEW-frame liveness), an obsws-python v5 controller (cut/PIP/overlay/reconnect/EventClient) against a scene-collection template, a `FeedWatchdog` deducing liveness from the last-new-frame timestamp, a crash-isolated Flask manual score-entry console (display-only, never adjudicates), and a fixed-rate fault-isolated orchestrator that shuts down to SAFE and never crashes — entry point `python -m segugio <config>`.
- **Decision-loop latency optimization (Phase 6, RBT-05):** ONE batched FP16 detection forward per tick replacing 4 serial `model.track()` calls (native ReID preserved) + an optional cached TensorRT FP16 engine with graceful eager fallback. Measured on the RTX 4000 Ada Laptop GPU: canonical FP16+batch eager ~256ms cool, engine ~197ms — both under the revised <300ms p95 budget (budget rivisto da <150ms after the on-rig measurement). ⚠ Thermal variance on the laptop GPU → prefer a desktop deploy GPU for sustained live.

---
