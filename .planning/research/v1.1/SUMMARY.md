# Project Research Summary — v1.1 Console Regia (live visibility)

**Project:** Segugio — v1.1 "Console Regia — visibilità live"
**Domain:** Live-visibility operator console for a crash-isolated auto-director (multi-camera disc dog / agility)
**Researched:** 2026-06-13
**Confidence:** HIGH

---

## Executive Summary

v1.1 transforms the bare Flask control panel into a live oversight console where the operator can see all cameras, understand why the auto-director chose the live cam, and issue informed overrides — without dismantling the crash-isolation guarantee that makes the v1.0 director reliable. The single most important insight from the combined research is that **this milestone is largely a publish-and-render problem, not a compute problem**: the orchestrator already calculates all the "why" data (per-camera framing scores, dog bbox, FSM reason) every tick — v1.0 simply discards it. The frame pixels are also already decoded inside the orchestrator. v1.1 exposes what is already there over a new off-tick file channel, and renders it in a vanilla-JS multiview.

The recommended transport is **polling per-camera JPEG thumbnails over the existing atomic-file opcomm channel** — zero new runtime dependencies on either side, reusing the proven `temp → fsync → os.replace` primitive with a new binary sibling (`atomic_write_bytes`). Publishing happens on a dedicated daemon thread via a latest-only single-slot mailbox so the director's critical tick (already measured at p95 ~256 ms) is never touched. The per-camera "why" data (scores, tracking state, FSM reason) travels in a new `preview.json` sidecar — NOT bloated into the safety-critical `status.json` — and the frontend renders it with vanilla JS and CSS Grid, no build chain. Two near-free quick wins are available immediately from existing code: `reason` rendered in plain Italian (already in `DirectorStatus`) and a score/overlay preview using the already-importable `render_overlay_text`.

The dominant risks are all on the integration boundary: encoding frames on the tick thread (busts the RBT-05 budget), importing `cv2`/`numpy` into the Flask process (breaks RBT-04 crash isolation), letting preview traffic compete with NDI HX3 on the saturated WiFi (feeds appear to die), and a latent bug in the current entrypoint where `app.run()` runs without `threaded=True` (a stream or long request would freeze override POSTs — a safety control). These risks are well-characterized and each has a concrete prevention strategy; none requires architectural invention, just disciplined application of the patterns the v1.0 system already established.

---

## Key Findings

### Recommended Stack

The v1.1 stack adds **no new runtime dependencies to either process**. The orchestrator already has `opencv-python 4.13.0.92` (for `cv2.imencode`) and `numpy`; it gains a publisher thread and a new `atomic_write_bytes` primitive (stdlib-only). The console stays at `Flask 3.1.3 + segugio.opcomm`; it gains two new routes and an updated template. The only new optional dependency is `waitress==3.0.2` as a deploy extra for the console — a pure-Python Windows-native WSGI server that handles concurrent short GETs cleanly. It must NOT be adopted if the MJPEG fallback is ever chosen (Waitress buffers full responses and does not support streaming).

MJPEG multipart-over-HTTP was evaluated as a fallback and rejected as the default: it holds one thread per stream, breaks under Waitress, and its push-latency advantage is imperceptible at the 5–10 fps cadence an operator monitor needs. WebSocket (flask-sock + simple-websocket) was rejected outright: two new deps on the crash-isolated console for push-latency a human monitor cannot perceive. OBS MULTIVIEW embed was rejected: the console cannot open an obs-websocket connection, and OBS multiview cannot be natively embedded in a browser.

**Core technologies (new or changed):**
- `atomic_write_bytes` (new, stdlib-only, `opcomm/atomic.py`) — binary sibling of the proven atomic write; atomicity YES, fsync optional for ephemeral previews
- `PreviewPublisher` (new daemon thread, `orchestrator/preview.py`) — latest-only mailbox + resize/encode/atomic-write at ~5 fps, never on the tick thread
- `PreviewDoc` / `preview.json` sidecar (new, `opcomm/records.py` + `channel.py`) — typed per-camera scores + tracking snapshot; keeps `status.json` unchanged
- Flask `send_from_directory` with whitelisted cam id (existing Flask, new route) — console serves JPEG bytes without decoding them
- Vanilla JS `Image()` preload + src swap, CSS Grid `repeat(auto-fit, minmax())`, `clamp()` — flicker-free multiview, no build chain
- `waitress==3.0.2` (optional deploy extra) — Windows-native WSGI; polling-only; NOT for MJPEG

### Expected Features

**Must have (table stakes for v1.1 launch):**
- **Multiview thumbnails of all cameras** — the gating feature; operator cannot issue informed overrides blind
- **LIVE / tally indicator on the live tile** — universal broadcast convention; data already in `status.live_cam`
- **Dead-feed indication on tiles** — already in `status.alive`; promote onto the multiview tile (grey-out / "MORTO" overlay)
- **Reason rendered in plain Italian** — already in `DirectorStatus.reason`; near-free; the "understand" half of the console
- **Informed override = clickable tiles** — multiview tile IS the force-cam button; fold existing `/command` logic onto tiles
- **Per-camera framing-score bars** — the honest "why" leaderboard; data already computed by Phase 2 scorer, just publish and render; the defining differentiator vs a dumb thumbnail wall
- **Score / overlay preview** — `render_overlay_text` already importable in the console; no orchestrator round-trip needed
- **Tablet responsive restyle** — listed in PROJECT.md; CSS Grid + touch targets; no backend change

**Should have (v1.x, after validation):**
- Dog-lock bbox overlay on tiles — `DetectionSignal` cx/cy/w/h already in the sidecar; CSS/SVG overlay, no image processing in Flask
- "Auto wants vs aired" divergence hint — the FSM already knows the auto-candidate while override is held; publish it
- Switch-history / recent-cuts strip — ring buffer in `DirectorStatus`; helps field-tune hysteresis

**Defer (v2+):**
- Embed OBS MULTIVIEW scene — requires bypassing the obs-websocket boundary the console is forbidden to cross
- Pose/disc-aware framing visualization — depends on later-milestone differentiators not yet built

**Anti-features (explicitly rejected):**
- Full PGM video monitor in the console — duplicates OBS; demands full-rate video; tempts heavy imports
- Auto-scoring CV — explicitly out-of-scope (SCR-04)
- Live director-tuning panel from the console — new write channel into the decision core; contradicts crash-isolated read-mostly design
- WebSocket push for everything — stateful channel for marginal gain on a 5-fps oversight UI

### Architecture Approach

The architecture is a strict extension of the v1.0 atomic-file IPC pattern. The orchestrator gains a `PreviewPublisher` daemon thread that reads a latest-only single-slot mailbox populated by the tick (a non-blocking locked dict assignment costing negligible time vs YOLO), downscales and JPEG-encodes each camera frame, and atomically writes `opcomm/preview/cam_<id>.jpg` + `opcomm/preview/preview.json`. The console gains two new Flask routes that `send_file` those bytes and serve the sidecar JSON, without importing any imaging library. The crash-isolation invariant — provable by the console's import set — is unchanged.

**Major components:**
1. **PreviewPublisher** (`orchestrator/preview.py`) — daemon thread; owns the encode/write loop; faults coast (never raise to tick); droppable frames by design
2. **Tick to publisher mailbox** (`loop.py`, ~6 lines) — `offer(frames, scores, dets)` after `_apply()`; last-writer-wins; the tick never waits
3. **`atomic_write_bytes` + `PreviewDoc`** (`opcomm/atomic.py`, `opcomm/records.py`, `opcomm/channel.py`) — the binary atomic primitive and the typed sidecar record; the shared contract
4. **Console preview routes** (`ui/app.py`) — `GET /preview/<cam>.jpg` (whitelisted `send_file`) + `GET /preview` (sidecar JSON); console import set unchanged
5. **Multiview frontend** (`ui/templates/console.html`) — CSS Grid tiles refreshed via `Image()` preload at ~5 fps; score bars + reason from `/preview`; score-overlay preview from existing `render_overlay_text`

**Key build-order constraint:** `atomic_write_bytes` + `PreviewDoc` foundation must exist before the publisher, which must exist before the tick wiring, which must be gated by RBT-05 re-measurement. Console routes must be gated by the crash-isolation import test. Only then does the frontend have something to consume.

### Critical Pitfalls

1. **Frame encoding on the director's tick** — adds 5–20 ms per camera per tick to a budget already at p95 ~256 ms; avoid by routing all encode/write work to the `PreviewPublisher` daemon thread; gate with `run_measured` asserting p95 unchanged.
2. **`cv2`/`numpy`/any heavy import in the Flask process** — silently breaks RBT-04 crash isolation; encode orchestrator-side, console serves raw bytes; add a CI canary test: console imports/starts with the heavy stack uninstalled.
3. **`app.run()` without `threaded=True` (latent bug)** — a single long-lived request pins the lone Werkzeug worker, blocking all subsequent requests including override POSTs; fix immediately when any streaming endpoint is added; prefer `waitress` as the production server.
4. **Preview traffic competing with NDI HX3 on the saturated WiFi** — 3–4 phones already push 60–200 Mbps NDI; uncapped preview bitrate causes feed-watchdog false-deaths; enforce a hard bitrate ceiling (<=5–8 Mbps total preview) via low fps (5–10), small resolution (~320–480 px), JPEG quality ~55.
5. **Bloating `status.json` with per-camera scores** — the safety-critical, write-on-change reverse channel becomes a per-tick rewrite, widening the torn-write surface; use a separate `preview.json` sidecar instead (the house pattern: independent atomic swaps for independent concerns).
6. **JPEG files in the same opcomm dir as control files** — high-rate binary IO starves `score.json`/`command.json`/`status.json` writes on slow flash; use a separate `opcomm/preview/` subdir; fixed-filename overwrite-in-place (never timestamped); drop fsync for ephemeral preview frames.
7. **Security blast-radius expansion** — `bind 0.0.0.0:8080 no-auth` was accepted for a control panel; v1.1 puts live video of competitors behind the same endpoint; re-evaluate the threat model explicitly, harden the AP (WPA2/3, no internet bridge), and document the LAN isolation requirement.

---

## Implications for Roadmap

Based on the combined research, the suggested phase shape for v1.1 is three phases:

### Phase A: Off-tick frame-publishing channel

**Rationale:** Every v1.1 visual feature depends on this channel existing and being provably off the critical tick and crash-isolation-safe. This is the gating foundation — nothing the operator sees can ship before the channel exists, and the channel must be proven not to regress RBT-05 before any UI is built on top of it.

**Delivers:**
- `atomic_write_bytes` (stdlib-only leaf, `opcomm/atomic.py`)
- `PreviewDoc` record + `read_preview`/`write_preview` (`opcomm/records.py`, `opcomm/channel.py`)
- `PreviewPublisher` daemon thread (`orchestrator/preview.py`) — resize, encode, atomic-write, fault-coast
- Tick wiring: `offer(...)` in `_tick_once` + publisher start/stop in `runtime.py`
- Separate `opcomm/preview/` media directory; fixed-filename overwrite; fsync dropped for preview JPEGs
- `gen.txt` generation counter (monotonic, for browser cache-busting)

**Hard gates (acceptance criteria):**
- RBT-05 `run_measured` p95 unchanged (within noise) with publisher running
- Crash-isolation import test: `import segugio.ui` resolves with `cv2`/`torch`/`numpy`/`cyndilib` uninstalled

**Addresses pitfalls:** 1 (off-tick encoding), 2 (crash isolation), 4 (torn JPEG reads), 5 (opcomm-dir bloat)

**Research flag:** Standard patterns — no deeper research needed.

---

### Phase B: Console serving + multiview frontend + threaded server + bandwidth cap + security re-eval

**Rationale:** Once the channel is gated, the console can consume it. The `threaded=True` / Waitress fix and the bandwidth cap are safety controls (override cannot be blocked; NDI feeds cannot be starved) and must land in the same phase as the first streaming endpoint. Security re-evaluation is an acceptance criterion here because this is the phase that first puts video behind the 0.0.0.0 endpoint.

**Delivers:**
- Console routes: `GET /preview/<cam>.jpg` (whitelisted `send_file`) + `GET /preview` (sidecar JSON)
- `console.html` multiview CSS Grid — `<img>` per camera refreshed ~5 fps via `Image()` preload + cache-bust
- LIVE/tally red border on the live tile (from `status.live_cam`)
- Dead-feed grey-out/overlay on tiles (from `status.alive`)
- `threaded=True` fix on `app.run()` (latent bug resolved); `waitress` as recommended production entrypoint
- Preview bitrate cap (configured fps + resolution + JPEG quality ceiling)
- Written v1.1 threat re-evaluation for live-video-behind-0.0.0.0 + AP isolation documented

**Gates:**
- POST `/command` (override) written promptly while a preview stream is active — no freeze
- Preview total bitrate stays under the configured cap; feed-watchdog false-death rate unchanged with phones live
- Written threat decision for v1.1 present in project docs

**Addresses pitfalls:** 3 (threaded freeze), 3/bandwidth (WiFi), 6 (security re-eval)

**Research flag:** Standard patterns (Flask threading, Waitress, CSS Grid). Security re-evaluation is a documentation task.

---

### Phase C: Camera-live-and-why, score bars, dog-lock overlay, override thumbnails, score preview, tablet restyle, leak/sleep hygiene

**Rationale:** These features all share the channel from Phase A and the serving infrastructure from Phase B. They are grouped because they share test infrastructure (long-run soak test, real-tablet sleep/wake test) and because the per-camera score bars + reason rendering are what differentiate Segugio's oversight UI from a dumb thumbnail wall.

**Delivers:**
- Per-camera framing-score bars rendered from `preview.json` sidecar (the "why" leaderboard)
- Reason rendered in plain Italian next to the live tile (from `DirectorStatus.reason`, near-free)
- Dog-lock bbox overlay on tiles as CSS/SVG box (from `DetectionSignal` box coords in sidecar)
- Informed override: clickable tiles fold the force-cam command onto the multiview tile
- Score/overlay preview rendered client-side via the already-importable `render_overlay_text`
- Tablet-first responsive restyle: large touch targets, always-visible live cam + reason, CSS Grid reflow
- Browser/tablet leak hygiene: `revokeObjectURL`, single-socket reconnect, history ring-buffer cap
- Tablet sleep/wake resume: `visibilitychange` forces fresh `/status` + preview re-establish; Screen Wake Lock request
- Freshness stamp + staleness overlay (frozen preview shown as stale, not live)
- Multi-hour soak test: tab memory + server thread count flat

**Gates:**
- Real-tablet sleep/wake tested on the actual operator device — no frozen "live" after wake
- Multi-hour soak: tab memory flatline, server thread count flatline
- All P1 features from FEATURES.md rendered and validated by an operator trial

**Addresses pitfalls:** 8 (browser/tablet leaks), 9 (tablet sleep/viewport)

**Research flag:** Needs `--research-phase` if targeting iOS Safari (MJPEG support gaps, background-tab suspension). Standard for Android Chrome / desktop.

---

### Phase Ordering Rationale

- **A before B:** the channel and its safety properties must be proven before any UI consumes it; the hard gates (RBT-05 unchanged, isolation import test) are preconditions for everything else
- **A before C:** score bars, bbox overlay, and informed override thumbnails all depend on the `preview.json` sidecar and JPEG files existing
- **B before C:** tablet restyle and long-run hygiene require the threaded WSGI and bandwidth cap to be in place
- **The `threaded=True` fix lands in B, not C:** it is a safety control (override must always work), not polish
- **Security re-eval lands in B, not deferred:** video goes behind the endpoint in B; the threat decision cannot be deferred

### Research Flags

Needs deeper research during planning:
- **Phase C (tablet transport):** iOS Safari MJPEG support and background-tab timer behavior need validation on the actual operator tablet model before the Phase C plan is finalized. Use `--research-phase C` if the target is iPad/Safari.

Standard patterns (no research phase needed):
- **Phase A:** atomic-file IPC + daemon-thread publisher is the established house pattern
- **Phase B:** Flask `send_from_directory`, Waitress, CSS Grid multiview — well-documented
- **Phase C (Android Chrome / desktop):** vanilla JS preload swap, `visibilitychange`, Wake Lock API — well-documented

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All claims grounded in repo code read directly + verified Flask/Waitress/opencv-python versions; no new deps to evaluate |
| Features | HIGH | Existing-system facts (what data already exists, what `DirectorStatus` already carries) read from source; feature-bar mapping to vMix/Visor conventions is MEDIUM but not load-bearing for the roadmap |
| Architecture | HIGH | Grounded in full read of `loop.py`, `opcomm/atomic.py`, `opcomm/channel.py`, `opcomm/records.py`, `ui/app.py`; the design question resolves cleanly from existing patterns |
| Pitfalls | HIGH | Critical pitfalls 1–7 grounded in actual repo code (tick budget measured, latent `app.run()` bug verified at `ui/app.py:143`, atomic pattern read from `opcomm/atomic.py`); browser/tablet pitfalls (8–9) are MEDIUM |

**Overall confidence:** HIGH

### Gaps to Address

- **MJPEG fallback on iOS Safari:** if the operator tablet is an iPad, validate that `<img>` refreshed via JS works correctly in Safari's background-tab suspension model before finalizing Phase C transport.
- **fsync drop for preview JPEGs:** the recommendation to drop `fsync` for ephemeral preview frames must be explicitly documented in the `atomic_write_bytes` implementation and not silently reverted.
- **Bandwidth measurement on field WiFi:** the <=5–8 Mbps preview budget is derived from NDI HX3 per-stream figures and is a conservative estimate; validate with phones live on the dedicated AP before Phase B acceptance.
- **BoT-SORT native ReID engagement on `yolo26s`:** flagged in v1.0 STACK research; if native ReID silently falls back to a small cls model, the sidecar's `track_id` stability degrades; verify at orchestrator startup before depending on `locked`/`track_id` in the Phase C bbox overlay.

---

## Sources

### Primary (HIGH confidence)
- v1.0 codebase (read 2026-06-13): `src/segugio/orchestrator/loop.py`, `src/segugio/opcomm/atomic.py`, `src/segugio/opcomm/channel.py`, `src/segugio/opcomm/records.py`, `src/segugio/ui/app.py`, `src/segugio/ui/templates/console.html`, `.planning/PROJECT.md` — tick structure, RBT-04/RBT-05 contracts, latent `app.run()` bug (line 143), atomic-file IPC pattern, crash-isolation boundary, `DirectorStatus` fields
- Flask 3.1.x + Waitress 3.0.2 docs — `send_from_directory`, streaming response threading, Waitress no-streaming constraint
- obs-websocket v5 protocol (`GetSourceScreenshot`) — verified the console cannot use it without importing obsws

### Secondary (MEDIUM confidence)
- Miguel Grinberg flask-video-streaming issues #11/#16 — MJPEG threaded-server requirement, one-worker-per-stream failure mode
- NDI HX3 bandwidth figures (docs.ndi.video + JEM Productions) — 20–50 Mbps per phone at 1080p HX3; x3–4 phones = 60–200 Mbps contended
- OBS forum threads — OBS multiview cannot be embedded in a browser natively without Spacedesk/screen-share
- MDN / 2025–2026 CSS Grid guides — `repeat(auto-fit, minmax())` + `clamp()` current standard; CSS Grid L2 in all major browsers by late 2024
- vMix / Blackmagic ATEM / Visor / SmartMix — switcher and AI-director UI conventions (tally, "what the AI wants next and why")

### Tertiary (LOW confidence — validate on hardware)
- iOS Safari MJPEG / background-tab behavior — cross-checked from web-platform documentation; must be validated on the actual operator tablet model before Phase C transport decision

---
*Research completed: 2026-06-13*
*Ready for roadmap: yes*
