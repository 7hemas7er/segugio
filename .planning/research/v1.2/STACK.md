# Stack Research — v1.2 OBS Browser-Source Score Overlay

**Domain:** Graphical animated transparent OBS browser-source score overlay, served by the existing crash-isolated Flask console (Segugio v1.2)
**Researched:** 2026-06-14
**Confidence:** HIGH

## TL;DR (the 5 decisions)

1. **(a) ZERO new Python runtime deps.** Flask already serves `console.html` via `render_template` and JSON via `jsonify`. The overlay is just two more routes (`GET /overlay` → an HTML template, `GET /overlay-json` → `jsonify`) reading the same `opcomm` files. Crash-isolation is preserved verbatim: the console still imports only `Flask + segugio.opcomm`. **No new pip package.**
2. **(b) Web side = vanilla HTML/CSS/JS, no build step, no framework, no CDN.** Same approach already proven in `console.html`. The overlay is a static template with inline `<style>`/`<script>`, served by Flask. Animations are pure CSS (`@keyframes` + transitions + CSS custom properties).
3. **(c) Fonts/icons = bundle locally as static files, `@font-face` with `font-display: block` + a JS `document.fonts.ready` gate before revealing the overlay.** Avoids FOUC/FOUT in CEF. Prefer inline SVG for icons (no icon-font, no extra request).
4. **(d) Data refresh = short-interval `fetch()` polling of `GET /overlay-json`.** NOT SSE, NOT WebSocket. A long-lived SSE/WS connection holds a Flask worker thread and re-introduces exactly the starvation risk the project's UXT-02 safety control and the v1.1 MJPEG/WebSocket rejection were built to avoid. The run **timer is purely client-side** (computed from `run_started_at` + `running`), so polling only needs to be fast enough to catch score changes (~500ms–1s), not to drive the clock.
5. **(e) Target CEF 6533 / Chromium 127** (OBS Studio 31.0, March 2025; unchanged through current 32.1.2, June 2026). Everything this overlay needs — CSS animations/transitions, `@keyframes`, `requestAnimationFrame`, `fetch`, `EventSource`, CSS custom properties, `@font-face`/`document.fonts`, `background: transparent` — has been stable in Chromium for years and is **safe to rely on** at Chromium 127. No polyfills, no `@supports` guards needed.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Flask** | `3.1.3` (already pinned in `pyproject.toml`) | Serve `GET /overlay` (HTML template) + `GET /overlay-json` (data) from the same crash-isolated console process | Already the console's only web framework. `render_template` + `jsonify` already in use (`app.py`). Adding two routes needs **zero new dependency** and keeps the import-guard (`Flask + opcomm` only) intact. |
| **Vanilla HTML5 + CSS3 + ES2020 JS** | Browser-native (target Chromium 127) | The overlay page itself: layout, animation, client-side timer, polling | No-build-step, no framework, no toolchain — identical philosophy to the existing `console.html`. Nothing to bundle, nothing to version-drift, nothing that can break crash-isolation. Chromium 127 supports every feature needed natively. |
| **CEF / Chromium (OBS browser source)** | **CEF 6533 = Chromium 127** (OBS 31.0+, current OBS 32.1.2) | The renderer the overlay runs inside | This is the deployment target, not a dependency you ship. Verified: OBS 31.0 (Mar 2025) bumped browser-source CEF to 127 (6533); OBS 32.0/32.1 release notes mention no further Chromium bump → **127 is the safe baseline floor.** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **(none — Python)** | — | — | Do NOT add any Python runtime dep for this milestone. |
| **(none — JS framework)** | — | — | Do NOT add React/Vue/Svelte/Alpine/htmx/jQuery. The overlay is a few hundred lines of vanilla JS at most; a framework adds a build step or a CDN fetch (network dependency at OBS load → FOUC/blank-overlay risk) for zero benefit. |
| Self-hosted web font (1 family) | bundle the `.woff2` file | Broadcast-grade lower-third typography | Bundle as a Flask `static/` asset (or base64-inline in the template). Use `font-display: block` + `document.fonts.ready` gate. See (c). Pick ONE variable or 2-weight family to keep bytes small. |
| Inline SVG icons | hand-authored, inline in the template | Discipline/score glyphs if desired (disc, timer, fault marker) | Inline `<svg>` paints with the first paint — no extra HTTP request, no icon-font FOUC. Preferred over any icon font. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| A normal Chromium/Chrome browser | Develop & preview the overlay at `http://<console-host>:8080/overlay` | Dev against Chrome ≥127 to match CEF. The transparent background shows as the page's default (checker/white) in a normal browser — that is expected; OBS composites the alpha. |
| OBS Studio 31.0+ (32.1.x current) | Final verification of transparency + animation in the real CEF | Add a Browser Source pointing at `http://<console-host>:8080/overlay`, set width/height, leave "Shutdown source when not visible" OFF for an always-on overlay. |
| (existing) `waitress==3.0.2` (optional `[console]` extra) / `app.run(threaded=True)` | Production/dev WSGI server for the console | **Already present.** `threaded=True` (UXT-02 safety control) is what lets the overlay's polling GETs coexist with the override POST without starving it — reinforces the poll-not-SSE choice (see What NOT to Use). |

## Installation

```bash
# (a) Python side: NOTHING new. The console already has Flask 3.1.3.
#     No pip install. No requirements.txt / pyproject.toml change for runtime deps.

# Web assets are bundled as static files served by Flask, e.g.:
#   src/segugio/ui/static/fonts/<family>.woff2     # one self-hosted web font
#   src/segugio/ui/templates/overlay.html          # the new overlay page (vanilla)
# (Flask serves src/segugio/ui/static/ automatically once the app has a static folder;
#  or reference assets relative to /overlay and add a small static route — no new dep.)
```

## Integration Points (exact, with the existing code)

- **`src/segugio/ui/app.py` → add two routes inside `create_app`** (keep Flask imported lazily inside the factory, as today):
  - `@app.get("/overlay")` → `return render_template("overlay.html")` (transparent lower-third page).
  - `@app.get("/overlay-json")` → read `score.json` (via a new `read_score` opcomm reader, or reuse existing readers) + `runstate.json`, then `jsonify({...})`. Mirror the safe-default never-raise pattern of `get_status`/`get_preview` (an absent/torn file → a valid default, never a 500). This route must be **pure** (no channel writes), exactly like `/score/preview`.
- **`overlay-json` payload** should expose the structured `ScoreDoc` (discipline + fields) AND the run-timer inputs so the client computes the clock itself:
  - `discipline`, `fields` (the raw `{label: value}` dict — let the HTML renderer format per-discipline, replacing the byte-exact JS mirror, SCV-01 unification),
  - `running` (bool) + `run_started_at` (an absolute epoch/ISO timestamp). **NOTE:** `RunState` today carries only `action`/`just_started`/`just_stopped` and the run timer is an operator-typed text field — to drive a self-counting client timer you need a real `run_started_at` timestamp on the channel. Stamping that timestamp is an **opcomm-record / console-write change inside the crash-isolated boundary** (it does NOT touch the director); flag this for the roadmap as the one genuine data-model addition.
  - a monotonic `gen`/`rev` token (like `PreviewDoc.gen`) so the client can detect "score changed" and fire the pulse animation without diffing every field.
- **`src/segugio/ui/score_render.py`** stays as the `overlay.txt` fallback renderer (SCR-01 degraded fallback) AND its per-discipline field mapping becomes the reference the HTML/CSS renderer mirrors. The v1.2 win (SCV-01 unified): the console preview iframes/embeds the SAME `/overlay` HTML instead of maintaining a separate byte-exact JS mirror of `render_overlay_text`.
- **`overlay.txt` write in `post_score` stays untouched** — it remains the robust fallback an OBS text source can read if the browser source is unavailable.

## Web-side detail — (b) minimal no-build choice

- **Layout & animation:** CSS Grid/Flexbox for the lower-third; `@keyframes` for enter/exit slide+fade; `transition` for score-change pulse; CSS custom properties (`--accent`, per-discipline theming) so the discriminated-union discipline swap (CFG-03) is a class toggle, not code. All native at Chromium 127.
- **Client-side run timer:** on each animation frame (or a 200ms `setInterval`), compute `elapsed = now - run_started_at` while `running`; format `mm:ss.d`. Zero director compute, matches the v1.2 requirement. Use `requestAnimationFrame` for smoothness, or a coarse `setInterval` if only `mm:ss` precision is shown (cheaper, easier).
- **Score-change pulse:** compare the polled `gen`/`rev`; on change, toggle a CSS class that runs a one-shot `@keyframes` pulse (use `animationend` to remove it).
- **Run start/stop edges:** when `running` flips true→show + play enter animation; false→play exit animation then hide.

## Web-side detail — (c) fonts/icons & FOUC avoidance in CEF

1. **Self-host the font** as a static `.woff2` (never a Google Fonts / CDN `<link>` — a network stall at OBS scene-load = a blank or unstyled overlay on air). Optionally base64-inline it in the template to guarantee it's present with the HTML.
2. **`@font-face { font-display: block; }`** — `block` (not `swap`) keeps text invisible briefly rather than flashing a fallback face, which for a clean broadcast lower-third is the desired behavior (no FOUT flicker on air).
3. **Reveal-after-ready gate:** start the overlay container at `opacity: 0`; in JS, `await document.fonts.ready` (supported since Chromium ~35) then add a `ready` class that fades/slides the lower-third in. This guarantees the first painted frame OBS captures is already styled with the real font — no FOUC.
4. **Icons = inline SVG** in the template (paints with first paint, no extra request, no icon-font FOUC). Avoid icon fonts entirely.
5. Keep the font to ONE family / 1–2 weights to minimize bytes and decode time.

## Data refresh — (d) transport decision: short-interval POLLING

**Recommendation: short-interval `fetch()` polling of `GET /overlay-json` (~500ms–1000ms interval). NOT SSE, NOT WebSocket.**

Rationale, scored against this project's constraints:

| Transport | Pros | Cons (in THIS system) | Verdict |
|-----------|------|------------------------|---------|
| **Polling `fetch()`** (recommended) | Trivial, stateless, no new dep, no long-lived connection, fits the existing `pollStatus`/`pollPreview` pattern in `console.html` verbatim, degrades gracefully (a missed poll is a no-op), each request returns the worker thread immediately | Slightly higher request count (negligible: one tiny JSON GET per second on a trusted LAN) | **CHOSEN** |
| **SSE (`EventSource`)** | Push, auto-reconnect, lower latency on change | A `text/event-stream` response **holds a Flask worker/thread for the connection's entire lifetime.** With `app.run(threaded=True)` or Waitress's bounded thread pool, every always-on overlay connection permanently occupies a worker — exactly the starvation the **UXT-02 safety control** (override POST must never be blocked) and the **v1.1 MJPEG/WebSocket rejection** were designed to prevent. Also needs careful flush/no-buffer handling. | Rejected (re-introduces the rejected risk) |
| **WebSocket** | Bidirectional, low latency | Needs a new Python dep (Flask doesn't speak WS natively → `flask-sock`/`simple-websocket`/an async server) → **breaks the `Flask + opcomm`-only crash-isolation invariant.** Long-lived connection = same worker-starvation problem as SSE. The project **explicitly rejected WebSocket** for the preview channel for these reasons. | Rejected (breaks crash-isolation + worker starvation) |

**Why polling is sufficient here:** the only time-critical, continuously-changing value is the run clock, and that is computed **client-side** from `run_started_at` — the poll does NOT drive the timer. Polling only needs to be quick enough to reflect a manual score edit or a run start/stop edge, where ~0.5–1s latency is invisible on a broadcast overlay. This is the same trade-off (and the same `setInterval` + `visibilitychange` teardown pattern) the v1.1 preview channel already validated on-device.

**Polling hygiene to copy from `console.html`:** named interval handles + `startPolling`/`stopPolling`. For an always-on OBS source there is no human visibility lifecycle, so a simple unconditional `setInterval` is fine. Use `fetch(..., {cache: 'no-store'})` and/or a `?t=<gen>` cache-bust so CEF never serves a stale overlay JSON.

## (e) CEF/Chromium feature-safety matrix (target Chromium 127)

All VERIFIED safe at Chromium 127 (most stable for 8+ years of Chromium):

| Feature | Chromium baseline | Safe at 127? | Notes |
|---------|-------------------|--------------|-------|
| `background: transparent` / `rgba(...,0)` alpha | always | **YES** | OBS composites the page alpha. Set it on `html, body` (and avoid any opaque body bg). Known CEF quirk: `border-radius` over transparent can leave a faint gray edge artifact — antialias seam, cosmetic; mitigate by avoiding 1px hairline rounded borders over full transparency if it shows. |
| CSS animations / `@keyframes` / `transition` | Chrome 26/43 | **YES** | Core of the enter/exit + pulse. |
| `requestAnimationFrame` | Chrome 24 | **YES** | Smooth client-side timer. |
| `fetch()` | Chrome 42 | **YES** | The poll transport. |
| `EventSource` (SSE) | Chrome 6 | YES (works) | Works in CEF — but **not recommended** for server-side reasons above, not client support. |
| CSS custom properties (`--var`) | Chrome 49 | **YES** | Per-discipline theming via class toggle. |
| `@font-face` / WOFF2 | Chrome 36 | **YES** | Self-host woff2. |
| `document.fonts` / `document.fonts.ready` | Chrome 35 | **YES** | The FOUC gate. |
| `font-display` | Chrome 60 | **YES** | Use `block`. |
| CSS Grid / Flexbox | Chrome 57 / 29 | **YES** | Layout. |
| `:has()`, container queries, nesting | Chrome 105/106/120 | YES at 127 | Available but **not needed** — avoid relying on the bleeding edge so the overlay also renders in slightly older OBS installs (≥31.0). |

**Practical floor:** require OBS Studio ≥ 31.0 (CEF 6533 / Chromium 127). Document this in `docs/obs-setup.md`. Anything older than OBS 31.0 ships an older Chromium — but every feature above predates 127 by years, so even OBS 30.x (Chromium 103) would render this overlay fine; 127 is simply the verified current floor.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Vanilla JS, no framework | Alpine.js / htmx (tiny, no build) | If the overlay template grows unexpectedly complex with reactive bindings. Even then prefer vanilla — must be self-hosted (no CDN) to avoid an on-air network dependency. Not needed for a lower-third. |
| Polling `fetch()` | SSE `EventSource` | Only if you move the console behind an async server (e.g. an ASGI/uvicorn stack) that can hold many idle connections cheaply — which would itself violate the current `Flask + opcomm` crash-isolation invariant. Do not do this in v1.2. |
| Self-hosted `.woff2` | System font stack (`system-ui`) | If you want zero font bytes and accept the OS default look (this is what `console.html` does today). Acceptable fallback; a custom broadcast face is the differentiator. |
| Inline SVG icons | Icon font | Never prefer the icon font here — adds FOUC + an extra request for no benefit. |
| Client-side timer from `run_started_at` | Server-pushed timer value | Pushing the clock would require fast SSE/WS or fast polling and would put compute on a tick — explicitly rejected by the v1.2 requirement ("zero compute sul tick del director"). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any new Python runtime dependency | Breaks the HARD crash-isolation invariant (console imports only `Flask + segugio.opcomm`), proven by the import-guard test | Flask's existing `render_template` + `jsonify` |
| WebSocket (`flask-sock`, `simple-websocket`, async server) | Needs a new dep (breaks crash-isolation) AND a long-lived connection starves a Flask worker (breaks UXT-02); the project already rejected WS for preview | Polling `fetch()` |
| SSE / `text/event-stream` from this Flask app | A streaming response pins a worker thread for the connection lifetime → same starvation risk UXT-02/the MJPEG rejection guard against, on an always-on overlay | Polling `fetch()` |
| CDN `<link>`/`<script>` for fonts or JS libs (Google Fonts, unpkg, etc.) | A network stall at OBS scene-load = blank/unstyled overlay ON AIR; also a privacy/availability dep on a trusted-LAN-only box that may have no/limited internet | Self-host every asset as a Flask static file |
| React/Vue/Svelte (or any build step) | Adds a toolchain + bundle that can drift and complicates the single-process console; massive overkill for a lower-third | Vanilla HTML/CSS/JS |
| Icon fonts | FOUC + extra request before glyphs paint | Inline SVG |
| `font-display: swap` for a broadcast overlay | Flashes the fallback face on air (FOUT) | `font-display: block` + `document.fonts.ready` reveal gate |
| Driving the run clock from the server | Puts compute/latency on the director tick or needs a fast push transport | Client-side timer from `run_started_at` + `running` |
| Relying on `:has()`/container queries/CSS nesting | Newest-Chromium features; unnecessary and reduce portability to OBS < 31 | Grid/Flexbox + custom properties (all pre-Chromium-57) |

## Stack Patterns by Variant

**If the console and OBS run on DIFFERENT machines (documented deployment note):**
- The browser source URL is `http://<console-LAN-IP>:8080/overlay`, not `localhost`. Ensure the Flask bind (`0.0.0.0`, already the case) and the LAN/AP client-isolation posture (docs/security.md) allow OBS's host to reach it.
- Because OBS 32.1 "improved security of browser sources using local files," prefer the **HTTP URL** (served by the console) over a `file://` source — the HTTP route is the design anyway and sidesteps any local-file sandboxing change.

**If you want the absolute-minimal change set:**
- One new template `overlay.html` (vanilla, transparent, self-contained) + two routes + one `read_score` opcomm reader (or reuse) + a `run_started_at` timestamp added to the run-state write inside the console boundary. Nothing else.

**If a custom broadcast font is desired:**
- Add `src/segugio/ui/static/fonts/<family>.woff2`, `@font-face` with `font-display: block`, and the `document.fonts.ready` reveal gate. Keep to 1–2 weights.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Flask `3.1.3` (pinned) | the two new routes | No version change needed; `render_template`/`jsonify`/`send_file` all already used in `app.py`. |
| Overlay HTML/CSS/JS (target Chromium 127) | OBS Studio ≥ 31.0 (CEF 6533) | Every feature used predates Chromium 127 by years; even OBS 30.x (Chromium 103) would render it. 127 is the verified current floor (OBS 31.0 → 32.1.2). |
| `waitress 3.0.2` / `app.run(threaded=True)` | overlay polling + override POST | `threaded=True` (UXT-02) is what makes concurrent overlay polls + the override POST safe — the same control that makes SSE/WS unnecessary AND undesirable. |

## Sources

- OBS Studio 31.0 Release Notes (obsproject.com/blog/obs-studio-31-0-release-notes) — **"updated the browser source/docks CEF (Chromium) to version 127 (6533) on all platforms"**, published 2025-03-28 — **HIGH (official, verified)**
- OBS Studio 32.0 & 32.1 Release Notes (obsproject.com/blog) — no further Chromium/CEF version bump mentioned; 32.1 only "improved security of browser sources using local files" → Chromium 127 remains the floor through current 32.1.2 (June 2026) — **HIGH (official, verified)**
- OBS Versions (obs-versions.com/current-version) — current stable = OBS Studio 32.1.2, released 2026-04-21 — **MEDIUM (third-party tracker)**
- OBS Browser Source KB (obsproject.com/kb/browser-source) + forum threads on transparency — page must supply `background: transparent`; OBS composites alpha; `border-radius` gray-edge artifact noted — **HIGH/MEDIUM**
- obsproject/obs-browser (github.com) — confirms browser source is CEF-based; exact version in submodule not parsed (UNVERIFIED at file level, but release notes give 127 authoritatively) — **HIGH for the CEF-based fact**
- Chromium feature baselines (MDN/caniuse-class knowledge) for fetch/EventSource/`@keyframes`/custom-properties/`document.fonts`/`font-display`/Grid — all ≪ Chromium 127 — **HIGH**
- Repo files read: `src/segugio/ui/app.py` (routes, `render_template`/`jsonify`/`send_file`, crash-isolation comment, `threaded=True`/Waitress entrypoint), `src/segugio/ui/score_render.py` (display-only per-discipline renderer), `src/segugio/ui/templates/console.html` (existing vanilla polling + `visibilitychange` pattern, no framework), `src/segugio/opcomm/records.py` (`ScoreDoc`/`RunState` — `RunState` has NO `run_started_at` timestamp today), `requirements.txt`/`pyproject.toml` (Flask 3.1.3 pinned; no front-end deps) — **HIGH (direct source)**

---
*Stack research for: graphical animated transparent OBS browser-source overlay served by a crash-isolated Flask console*
*Researched: 2026-06-14*
