# Research Summary -- v1.2 Overlay Grafico Broadcast

**Project:** Segugio
**Domain:** Animated broadcast score overlay (lower-third) as OBS browser-source, served by the crash-isolated Flask console
**Researched:** 2026-06-14
**Confidence:** HIGH

## Executive Summary

v1.2 is a **publish-and-render extension** of the existing opcomm-over-files pattern, identical in shape to the v1.1 preview channel. The console gains two GET routes (/overlay -> transparent HTML, /overlay-json -> JSON data) and a new console-owned file (overlay_run.json) carrying the run-start timestamp. Zero new Python runtime dependencies. Zero director touches. The console still imports only Flask + segugio.opcomm.

The single most consequential design decision is the **clock-skew cancellation scheme**. RunState carries no run_started_at today. When it is added, the console must also publish server_now alongside it in every /overlay-json response. The client computes skew = server_now - Date.now()/1000 once per poll and counts locally -- never a raw Date.now() - started_at across two machines. This is the highest-risk new behavior and must be solved at the first timer phase, not later. All other decisions are low-risk applications of patterns already proven in v1.1.

The second load-bearing decision is **where** the run-start timestamp lives. It must NOT go into runstate.json (the director reads that every tick); instead, POST /run side-writes a new console-owned overlay_run.json (OverlayRun record), keeping director-never-touched literally true. SCV-01 unification collapses the existing byte-exact Python-to-JS mirror by making the console preview load the same /overlay route as OBS (iframe reuse), structurally eliminating the drift class the mirror was guarding against.

---

## Key Findings

### Recommended Stack

Zero new Python runtime deps. Flask 3.1.3 (already pinned) adds two routes via render_template and jsonify. The web side is **vanilla HTML5 + CSS3 + ES2020 JS** with no build step, no framework, no CDN. Animations are pure CSS. Target renderer is **CEF 6533 / Chromium 127** (OBS Studio 31.0+, current 32.1.2). Every feature the overlay needs has been stable in Chromium for 8+ years and needs no polyfills.

**Core technologies:**
- **Flask 3.1.3** (already pinned): two new routes inside create_app; crash-isolation invariant preserved; no version change
- **Vanilla HTML/CSS/JS** (target Chromium 127): overlay page, per-discipline layout, client-side timer, animations, freshness logic -- no build step
- **overlay_run.json / OverlayRun record**: new console-owned opcomm file; mirrors PreviewDoc exactly; director never reads it
- **Self-hosted .woff2 font** (optional): bundled as Flask static/ asset; font-display: block + document.fonts.ready reveal gate; no CDN on a field LAN

**Hard rejections:**
- SSE / text/event-stream: holds a Flask worker thread -- same UXT-02 starvation risk the v1.1 MJPEG/WebSocket rejection was designed to prevent
- WebSocket: needs a new Python dep (breaks crash-isolation) AND worker starvation; project already rejected this
- Any new Python runtime dependency: breaks the HARD crash-isolation invariant
- CDN fonts/scripts: network stall at OBS scene-load = blank overlay on air

### Expected Features

**Must have (table stakes -- v1.2 launch):**
- Transparent OBS browser-source overlay (GET /overlay + GET /overlay-json) served by the crash-isolated console
- Per-discipline lower-third layout: disc T&F: Prese/Zona/Totale; disc freestyle: Nome/Timer; agility: Tempo/SCT/Faults
- Self-counting run timer from NEW run_started_at + running: T&F and freestyle count **down** (T&F from 60s, freestyle from config-driven 90s/120s); agility counts **up** vs operator-typed SCT
- Show/hide tied to run start/stop via existing just_started/just_stopped edges, with subtle enter/exit animation
- Score-change pulse (brief CSS highlight when gen advances)
- Legible compositing: semi-opaque plate, contrast, title-safe lower band (bottom 5-20% of frame -- never over the field action area)
- overlay.txt fallback retained (SCR-01)
- Unified renderer (SCV-01): console preview iframes /overlay instead of a byte-exact JS mirror

**Should have (v1.2.x after validation):**
- Event + competitor/dog identity line for T&F/agility
- Branding/logo + config-driven CSS theme
- Curated OBS scene collection with browser-source pre-wired in every scene
- Staleness/freshness guard on score values reusing the gen-advance isStale() watchdog from v1.1

**Defer to v2+:**
- SCT-relative agility visual (under/over-time color bar)
- Automatic adjudication/scoring (SCR-04): **hard OUT** -- the judge is authoritative; overlay shows operator-typed values verbatim, never computes

**Anti-features (hard OUT):**
- Automatic scoring/CV adjudication (SCR-04)
- Over-animation (constant motion, looping shimmer, per-tick animation)
- Overlay covering the action area (full-width banner, top-center scorebar)
- Anything requiring director compute

### Architecture Approach

v1.2 is additive. POST /run side-writes overlay_run.json after the existing write_runstate call. GET /overlay serves the transparent HTML. GET /overlay-json assembles {discipline, fields, running, started_at, server_now, gen} from two opcomm reads with Cache-Control: no-store and a ?t=<gen> nonce. The overlay page counts the timer locally using the offset-cancellation formula. The console preview becomes an iframe of /overlay, retiring the JS mirror. render_overlay_text (Python) survives as the overlay.txt fallback renderer only.

**Major components:**
1. opcomm/records.py :: OverlayRun -- new frozen record (started_at: float|None, running: bool, gen: int); mirrors PreviewDoc exactly
2. opcomm/channel.py :: write_overlay_run / read_overlay_run -- atomic write + safe-default never-raise read; director never reads this file
3. ui/app.py :: POST /run (modified) -- side-writes overlay_run.json with time.time() on start edge, nulls it on stop edge
4. ui/app.py :: GET /overlay (new) -- render_template overlay.html
5. ui/app.py :: GET /overlay-json (new) -- pure read of two opcomm files; Cache-Control: no-store; includes server_now
6. ui/templates/overlay.html + ui/static/overlay-render.js (new) -- transparent lower-third; client timer with offset-cancellation; gen-advance freshness watchdog; CSS animations
7. ui/templates/console.html (modified) -- live preview becomes iframe of /overlay?preview=1; byte-exact JS mirror retired (SCV-01)
8. obs/segugio-scene-collection.json (modified) -- Score Overlay browser source in every scene; shutdown_source_when_not_visible: false
9. ui/score_render.py :: render_overlay_text (unchanged) -- overlay.txt fallback renderer only

**Key patterns to follow:**
- Console-owned side-file for derived state (never extend runstate.json)
- Mirror the PreviewDoc record contract for OverlayRun
- gen-strictly-advances freshness watchdog (reuse isStale() from console.html verbatim)
- One renderer, hosted twice (iframe reuse -- structurally eliminates drift)
- ?t=<gen> nonce + Cache-Control: no-store on every data fetch

### Critical Pitfalls

1. **Run-timer clock skew across machines (HIGHEST RISK)** -- naive Date.now() - started_at injects the two-machine clock offset into the displayed time. Prevention: publish BOTH started_at AND server_now (both on the console clock) in every /overlay-json response; client computes skew = server_now - Date.now()/1000 once per poll and renders (Date.now()/1000 + skew) - started_at. Re-measure skew each poll. Test with machine clocks set 30s apart.

2. **OBS browser-source CEF caching** -- Refresh cache of current page is just F5 and does not evict sub-resources. Prevention: Cache-Control: no-store on /overlay and /overlay-json; ?t=<gen> nonce on every poll URL; document the real cache-clear procedure (%appdata%/obs-studio/plugin_config/obs-browser/cache) in docs/obs-setup.md.

3. **Breaking crash-isolation by importing something heavy** -- adding any Python runtime dep silently breaks the import-isolation guarantee. Prevention: stdlib + Flask only; pass config-derived data into create_app as plain args; add the overlay route module to the crash-isolation import test as a success criterion of Phase 10.

4. **Stale/disconnected data shown as live (UXT-03 analogue)** -- if the console dies, a ticking CSS timer looks authoritative but is wrong. Prevention: publish a monotonically advancing gen; reuse isStale() from console.html; on stale past STALE_MS, **stop the client timer** and degrade visually. A frozen-but-ticking timer is the worst broadcast failure.

5. **started_at added to runstate.json instead of a new file** -- the director reads runstate.json every tick. Prevention: stamp started_at in the new console-owned overlay_run.json only; POST /run side-writes it AFTER write_runstate.

6. **file:// browser-source URL** -- a local HTML file fetching /overlay-json is a cross-origin request from file://; CEF blocks it silently and the overlay never updates. Prevention: browser-source URL must be http://<console-LAN-IP>:8080/overlay.

7. **OBS source settings left at defaults (shutdown_source_when_not_visible: true)** -- destroys the overlay page on every CAM cut, causing re-initialization flash and lost timer state. Prevention: set shutdown_source_when_not_visible: false and refresh_when_scene_is_active: false in the scene-collection JSON.

---

## Implications for Roadmap

The build order is strictly determined by dependency chains: (a) data contract before renderer; (b) renderer before SCV-01 unification; (c) renderer before OBS wiring; (d) robustness testing after the assembled path. Phases numbered continuing from v1.1 (project is at Phase 10).

### Phase 10 -- Data contract + run-timestamp publish

**Rationale:** Everything else depends on /overlay-json existing with the correct shape, especially server_now for clock-skew cancellation. Zero HTML in this phase -- pure channel + route.

**Delivers:**
- New OverlayRun(started_at, running, gen) frozen record + write_overlay_run/read_overlay_run (mirroring PreviewDoc)
- POST /run side-write of overlay_run.json on start/stop edge with time.time() + monotonic gen
- GET /overlay-json returning {discipline, fields, running, started_at, server_now, gen} with Cache-Control: no-store
- Crash-isolation import test re-verified green -- success criterion of this phase

**Addresses:** run-timestamp data gap (the one genuine data-model addition of the milestone)

**Avoids pitfalls:** P1 (server_now included from day one), P3 (crash-isolation gated here), P5 (runstate.json untouched)

**Research flag:** Standard -- PreviewDoc pattern is the exact template.

### Phase 11 -- Shared graphical renderer + /overlay page

**Rationale:** The renderer is the core deliverable. Building it on top of a tested data contract de-risks the visual and timer logic.

**Delivers:**
- ui/static/overlay-render.js -- ONE shared score-to-DOM renderer for per-discipline lower-third layout + client-side timer with offset-cancellation formula
- ui/templates/overlay.html -- transparent body (critical CSS inlined in head), poll loop, per-discipline timer direction, gen-advance freshness watchdog + degrade (timer stops on stale), enter/exit animation + score-change pulse
- Self-hosted font with font-display: block + document.fonts.ready reveal gate (eliminates FOUC in CEF)
- Timer formula: skew = server_now - Date.now()/1000; local requestAnimationFrame between polls; timer freezes on running === false and on stale

**Addresses:** transparent overlay, per-discipline layout, self-counting timer, show/hide on run edges, score-change pulse, legible compositing, freshness degradation

**Avoids pitfalls:** P1 (clock-skew formula here), P2 (no-store + nonce on fetch), P4 (stale -> timer stops), P5 (opacity:0 start -> no white flash)

**Research flag:** Standard.

### Phase 12 -- SCV-01 unification (retire the mirror)

**Rationale:** Once the shared renderer exists, the console preview can repoint to it. Verified before OBS wiring.

**Delivers:**
- console.html live preview changed to iframe of /overlay?preview=1 -- byte-exact JS mirror block retired
- /score/preview drift-guard retired (or downgraded to a parity sanity check for overlay.txt only)
- render_overlay_text (Python) survives unchanged as the overlay.txt fallback renderer

**Addresses:** SCV-01 unification -- drift structurally impossible (one URL, one renderer)

**Avoids pitfalls:** P6 (iframe reuse makes drift architecturally impossible)

**Research flag:** Standard.

### Phase 13 -- OBS scene-collection + docs

**Rationale:** Package the browser source into the scene collection and update operator docs. The URL must serve something before it can be wired.

**Delivers:**
- obs/segugio-scene-collection.json: Score Overlay browser source in every CAM/SAFE/MULTIVIEW/PIP scene; shutdown_source_when_not_visible: false; refresh_when_scene_is_active: false; layered above NDI and below Score Text text source
- docs/obs-setup.md: browser-source URL, cross-machine LAN-IP note, cache-clear procedure, Browser-primary/Text-fallback coexistence policy
- tests/test_scene_template.py extended: browser source present with agreed URL + transparency + shutdown=false
- One-paragraph threat re-evaluation appended to docs/security.md

**Addresses:** curated OBS scene collection, file:// vs http:// source choice, OBS source settings

**Avoids pitfalls:** P2 (cache-clear documented), P7 (http URL mandated), P9 (OBS settings in JSON)

**Research flag:** Standard.

### Phase 14 -- Fallback coexistence + degrade hardening

**Rationale:** End-to-end robustness testing of the assembled path before field acceptance. The live-robustness gate.

**Delivers:**
- Verified: console-down -> browser overlay degrades AND text source keeps last score; LAN-drop -> timer stops; restart -> re-anchors
- overlay.txt + Score Text text source verified still present (SCR-01)
- UXT-02 concurrency test extended: /overlay-json poll storm does not starve /command POST
- HTML injection check: score values HTML-escaped (Jinja autoescape ON or textContent not innerHTML)
- Acceptance criterion: killing the console freezes the timer within STALE_MS and degrades visually

**Addresses:** SCR-01 fallback retention, UXT-03 freshness discipline, live-robustness gate

**Research flag:** Standard -- validation of assembled behavior, all patterns from v1.1.

### Phase Ordering Rationale

- Data before renderer: server_now must be in the contract from the first commit; retrofitting risks shipping a broken timer to air.
- Renderer before unification: SCV-01 can only repoint the preview to a URL that already exists.
- Renderer before OBS wiring: the browser source URL must be live before the scene-collection encodes it.
- Robustness last: tests the whole assembled path; no individual phase can validate cross-component degrade behavior.
- Crash-isolation re-verified at Phase 10 and re-asserted as a gate on each subsequent phase.

### Research Flags

Phases needing deeper research: **none** -- all patterns are direct extensions of proven v1.1 work. The clock-skew offset-cancellation formula is the only genuinely new behavior; its design is fully specified in the architecture research.

Phases with standard patterns (skip research-phase): **Phases 10-14** -- patterns are direct mirrors of existing opcomm records/readers, proven v1.1 watchdog/polling hygiene, or well-documented CEF/CSS behaviors verified against Chromium 127.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Technologies read directly from the existing codebase; Flask 3.1.3 pinned; CEF 6533 / Chromium 127 confirmed from OBS 31.0 official release notes |
| Features | HIGH | Discipline rules corroborated across 6+ official/domain sources; data model read directly from opcomm/records.py; RunState NO timestamp confirmed in source |
| Architecture | HIGH | All integration points read directly from app.py, loop.py, records.py, channel.py, console.html; runstate.json director-reads-every-tick verified in loop.py |
| Pitfalls | HIGH (system-specific) / MEDIUM (OBS/CEF) | System-specific pitfalls read from source; OBS/CEF behaviors from OBS forums corroborated across multiple threads |

**Overall confidence:** HIGH

### Gaps to Address

- **Freestyle round length config key:** 90s vs 120s is org-dependent; confirm the config key name during Phase 10 planning.
- **T&F/freestyle timer-at-zero behavior:** convention is freeze at 0:00; confirm with the user whether a visual TEMPO flash is wanted before Phase 11 implementation.
- **Agility over-SCT display treatment:** the timer counts up past SCT (over-time condition); confirm the visual treatment before Phase 11 implementation.
- **CEF border-radius transparency artifact:** a faint gray edge can appear at border-radius over full transparency; verify on the production OBS box and avoid hairline rounded borders if it surfaces.

---

## Sources

### Primary (HIGH confidence)
- src/segugio/ui/app.py -- existing routes, crash-isolation comment, threaded=True/Waitress, ?t=<gen> + Cache-Control: no-store on preview JPEG
- src/segugio/ui/templates/console.html -- SCV-01 byte-exact mirror block, isStale()/freshnessStamp()/pollPreview patterns, polling hygiene
- src/segugio/ui/score_render.py -- per-discipline label mapping/aliases, _clean/_MAX_FIELD_LEN, stdlib-only import contract
- src/segugio/opcomm/records.py -- ScoreDoc/RunState/Discipline/PreviewDoc; confirmed NO run_started_at/running on RunState
- src/segugio/orchestrator/loop.py -- proves director reads runstate.json every tick; new timestamp must go in a separate file
- obs/segugio-scene-collection.json, docs/obs-setup.md -- current scene structure
- .planning/PROJECT.md -- v1.2 goal, crash-isolation HARD constraint, cross-machine OBS deployment fact, SCR-04 boundary
- OBS Studio 31.0 Release Notes (obsproject.com) -- CEF bumped to Chromium 127 (6533), 2025-03-28
- OBS Studio 32.0/32.1 Release Notes -- no further Chromium bump; 32.1.2 current (2026-04-21)

### Secondary (MEDIUM confidence)
- OBS Forums / obs-browser issue trackers -- Refresh cache is just F5; real clear = %appdata%/obs-studio/plugin_config/obs-browser/cache; border-radius transparency artifact
- WP Reset + OBS Forum threads -- html, body must be transparent; OBS default custom CSS; white-flash from late stylesheet
- K9 Toss & Fetch League rules, Skyhoundz/Air Canines, SpiritDog/AKC agility docs -- T&F 60s countdown, freestyle 90s/2min, agility count-up vs SCT
- School of Motion, EBU R095, Larry Jordan, VeneraTech -- lower-third anatomy, title-safe lower band, animation philosophy
- Disc Dog University -- standard countdown cadence (30 ... 10 ... 5-4-3-2-1-Time)

### Tertiary (MEDIUM/LOW)
- obs-versions.com -- current stable OBS 32.1.2 (third-party tracker)
- General NTP-pattern / same-origin vs file:// CORS fetch behavior

---
*Research completed: 2026-06-14*
*Ready for roadmap: yes*