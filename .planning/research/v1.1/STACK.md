# Technology Stack — v1.1 Console Regia (live visibility)

**Project:** Segugio — operator-less multi-camera auto-director
**Milestone:** v1.1 "Console Regia — visibilità live"
**Researched:** 2026-06-13
**Scope:** ONLY the NEW live-visibility features (camera preview/multiview in the crash-isolated Flask console, frame transport orchestrator→console, JPEG encoding, tablet-friendly frontend). Existing v1.0 stack is NOT re-researched — see `.planning/research/STACK.md` for the v1.0 domain stack.

---

## TL;DR (the decision)

**Primary approach: polling JPEG thumbnail files written by the orchestrator, served as static files by the console, swapped flicker-free by vanilla JS in a CSS-Grid multiview.**

- **ZERO new runtime deps in the crash-isolated console.** The console keeps importing only `Flask` + `segugio.opcomm` (D-03/RBT-04 preserved verbatim).
- The orchestrator already has `opencv-python` (`cv2.imencode`) and `numpy` and the BGR frames — it gains the *publisher* role with no new dependency.
- Frame transport reuses the **existing atomic-file IPC** (temp + `fsync` + `os.replace`, Windows `MoveFileEx` retry) the channel is already built on. A JPEG is just another atomically-swapped file in (a subdir of) the opcomm dir.
- Frontend stays **vanilla JS + modern CSS** (CSS Grid `auto-fit`/`minmax`, `clamp()`), no build chain, no SPA, no npm.

**Fallback (only if the poll cadence proves visibly choppy in UAT): MJPEG multipart-over-HTTP** via a plain Flask streaming `Response` generator — still no new console dep, but it does change the process model (one held thread per stream). See the comparison and the explicit caveat below.

**Rejected: WebSocket (flask-sock / simple-websocket).** It adds runtime deps to the crash-isolated console for a problem the file channel already solves, and its push-latency advantage is irrelevant for a ~5–10 fps operator monitor. See "What NOT to Use".

---

## The crash-isolation constraint drives every choice

The console (`src/segugio/ui/app.py`) imports **only** `Flask` + `segugio.opcomm` (stdlib + loguru leaf). A UI exception can never reach the director; the *only* coupling is atomic files in the opcomm dir. Frames live as `numpy` BGR arrays **inside the orchestrator process** — the console has no `cv2`, no `numpy`, no access to those arrays.

Therefore the design question is **not** "how does the console grab frames" (it can't) but **"how does the orchestrator publish frames so the console can serve bytes it never has to decode."** The answer that respects the contract with the least new surface is: **the orchestrator JPEG-encodes (it already has `cv2`) and writes the bytes to a file; the console serves those bytes verbatim.** The console never decodes, never imports an imaging library, and adds no dependency.

| Process | New role in v1.1 | New runtime deps |
|---------|------------------|------------------|
| **Orchestrator** (heavy side: cv2/numpy/torch already present) | JPEG-encode + downscale the framing-annotated BGR frame per camera; atomic-write to `opcomm/preview/<cam>.jpg`; extend `status.json` with per-camera score/track reason | **NONE** — `cv2.imencode` + `numpy` already installed (`opencv-python==4.13.0.92`) |
| **Console** (light side: Flask + opcomm only) | Serve `preview/<cam>.jpg` as static bytes; render CSS-Grid multiview; poll-refresh `<img>` via vanilla JS | **NONE** for the primary approach |

---

## Recommended Stack (NEW capabilities)

### Frame transport: polling thumbnail files (PRIMARY)

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| **Existing `opcomm.atomic.atomic_write_*`** | in-repo | Orchestrator publishes each camera's JPEG thumbnail to `opcomm/preview/<cam>.jpg` via the same temp→fsync→`os.replace` swap already proven on Windows (MoveFileEx + retry) | Reuses the *exact* IPC the crash-isolation contract is built on. No new transport, no new server mode, no new dep on either side. A torn read is impossible by the same guarantee `score.json`/`status.json` already rely on. |
| **`cv2.imencode(".jpg", frame, [IMWRITE_JPEG_QUALITY, q])`** | `opencv-python==4.13.0.92` (already pinned) | Orchestrator-side JPEG encoding of the downscaled annotated frame | Already available in the orchestrator; no new dep. Returns a `numpy` buffer (`.tobytes()`) ready to write. Add a binary `atomic_write_bytes` sibling to the existing `atomic_write_text`/`atomic_write_json` (trivial, stdlib-only, stays in `opcomm`). |
| **Flask `send_file` / `send_from_directory`** | Flask 3.1.3 (already pinned) | Console serves the published JPEG bytes with no decode | Stdlib-path, no new dep. Set `Cache-Control: no-store` (or rely on the JS cache-buster) so the tablet always fetches the freshest swap. |
| **Vanilla JS `Image()` preload + `src` swap** | n/a (browser built-in) | Flicker-free near-live refresh of each `<img>` at a fixed cadence (e.g. 5–10 fps) | Load the next JPEG into an off-DOM `new Image()`; on its `onload`, assign its `src` to the visible `<img>`. The visible tile never shows a half-loaded frame → no flicker, no double-buffer library needed. Cache-bust with `?t=${Date.now()}`. |

**Cadence:** the operator monitor does not need 30 fps. 5–10 fps per tile is ample to "see the camera and pick an override" and keeps both the orchestrator encode cost and the tablet/WiFi load low. The orchestrator only needs to re-encode a given camera when it has a fresh frame (it already tracks last-new-frame timestamps for the feed watchdog — reuse that to avoid re-encoding stale repeats).

### "Camera live + reason" data: extend the existing reverse channel

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| **Extend `status.json` (`DirectorStatus`)** | in-repo `opcomm.records` | Add per-camera framing score + dog-track state/reason alongside the existing `live_cam`/`reason`/`alive` map (D-11) | The reverse channel already exists and the console already polls `GET /status` every 1s. Adding fields to `DirectorStatus` is a typed, validated, backward-compatible change (its readers already default-on-missing). This is the structured "why this camera" data the thumbnails are annotated against — no new transport. |

This keeps **structured state** (small JSON, 1 Hz poll, already wired) separate from **pixels** (JPEG files, 5–10 Hz refresh). Two channels, both file-based, both atomic, both already in the trust model.

### Frontend: vanilla JS + modern CSS (no build chain)

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| **CSS Grid `repeat(auto-fit, minmax(...))`** | native (all modern tablet browsers 2024+) | Responsive multiview that reflows 1→2→4 columns by viewport without media-query thickets | Query-light fluid layout is the 2026 standard; one rule handles phone-portrait through landscape-tablet. The current `console.html` is already a single inline-CSS page — extend it, don't reframework it. |
| **`clamp()` fluid typography / tile sizing** | native | Score/overlay-preview text and tiles scale smoothly across tablet sizes | No JS, no breakpoints to maintain. |
| **Vanilla `fetch` + `setInterval`** | native (already used in `console.html`) | Drive both the existing `/status` poll and the new per-tile JPEG refresh | The page already does exactly this for status; the new code is the same shape. No framework, no bundler, no transpile. |
| **Overlay-preview = reuse `render_overlay_text`** | in-repo `ui.score_render` | Show the score "as it will appear on the OBS overlay" by rendering the same text the console already writes to `overlay.txt`, styled in a preview box | The render function already exists and is imported by the console. The preview is a pure client-side restyle of a string the console already produces — zero new dep. |

---

## Comparison: the three frame-transport options

| Criterion | **Polling JPEG files (PRIMARY)** | **MJPEG multipart-over-HTTP (FALLBACK)** | **WebSocket (flask-sock/simple-websocket)** |
|-----------|----------------------------------|------------------------------------------|---------------------------------------------|
| New console runtime dep | **None** | **None** (plain Flask `Response` generator) | **flask-sock 0.7.0 + simple-websocket 1.1.0** (2 new deps on the light side) |
| Respects atomic-file IPC | **Yes — IS the file channel** | Partially — the console can only read the *published* files, so MJPEG would just re-stream those same files (added complexity for the same pixels) | No — pushes bytes over a socket; the console would still only have the published files to push |
| Process model on Werkzeug dev server | Normal short request/response — **no held threads** | **One thread held for the entire connection lifetime per stream/viewer.** 4 tiles × N tablets can exhaust the dev-server thread pool and block other routes (incl. POSTs). Needs `threaded=True` and careful worker budgeting. | One held connection per socket; flask-sock works on the dev server but each socket occupies a worker for its lifetime |
| Production server compatibility | Works under **Waitress** (the natural pure-Python Windows WSGI choice) — plain GET of a static file | **Breaks under Waitress** — Waitress buffers full responses and does **not** support streaming; would force gevent/gunicorn-gevent, dragging async machinery into the deploy | Needs a WS-capable server; flask-sock avoids gevent but still complicates the deploy story |
| Latency for an operator monitor | ~one refresh interval (100–200 ms at 5–10 fps) — **more than adequate** | Lower (continuous push) | Lowest (continuous push) — but the difference is invisible at monitor cadence |
| Per-tile independence / partial failure | **Excellent** — each tile is an independent file/GET; a stale or missing tile shows a placeholder, others unaffected | A dropped multipart stream kills that whole tile's connection | A dropped socket can take the multiplexed view with it unless carefully per-tile |
| Implementation + test surface | Smallest; reuses proven atomic write + existing poll pattern | Medium; streaming generator + threading caveats | Largest; protocol, framing, reconnect, server compat |

**Recommendation:** **polling JPEG files.** It is the only option that (a) adds zero deps to the crash-isolated console, (b) reuses the already-proven atomic-file channel verbatim, (c) keeps the deploy on plain Waitress, and (d) has the smallest test surface. Its only "cost" — refresh cadence instead of push — is irrelevant for a human override monitor.

**Fallback trigger:** if UAT shows the polling cadence is visibly choppy *and* a higher fps is genuinely wanted, switch to **MJPEG via a plain Flask streaming `Response`** (still no new dep) — but accept the held-thread process model and that the deploy must then run a streaming-capable server (NOT Waitress; use the threaded dev server with a bounded viewer count, or gevent). Do this only with evidence; do not pre-optimize into it.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Frame transport | Polling JPEG files | WebSocket (flask-sock + simple-websocket) | 2 new deps on the crash-isolated console for push-latency a human monitor can't perceive; the pixels still come from published files either way |
| Frame transport | Polling JPEG files | MJPEG multipart | Holds a thread per stream, breaks under Waitress (no streaming), bigger failure blast radius per tile — keep as evidence-gated fallback only |
| Production server | Waitress (pure-Python, Windows-native, threaded) | gevent / gunicorn-gevent | Async monkey-patching machinery is overkill for a single-operator LAN tool; only needed *if* MJPEG fallback is adopted |
| Binary publish helper | Add `atomic_write_bytes` to `opcomm.atomic` | Pillow / imageio in console | Console must not gain an imaging lib; encoding stays orchestrator-side with the already-present `cv2`; the console only writes/serves raw bytes |
| Multiview source | Orchestrator-published per-camera JPEGs | Embed OBS MULTIVIEW output in the console | Couples the console to OBS/video output (new dep + network path) and loses per-tile framing annotations the orchestrator can draw; OBS multiview embed stays a later option, not v1.1 |
| Frontend | Vanilla JS + CSS Grid/clamp | htmx / Alpine.js / Preact | The page is already vanilla and tiny; a micro-lib buys nothing here and adds a script asset to ship/serve. Avoid until a real need appears |
| Frontend | Vanilla JS + CSS Grid/clamp | React/Vue + Vite build chain | A build chain for one Italian page is pure overhead; violates the "no heavy build chain" constraint outright |

---

## Installation (NEW deps)

```bash
# CONSOLE (crash-isolated, light side): NOTHING NEW.
#   Stays: Flask==3.1.3 + segugio.opcomm  (D-03/RBT-04 preserved)

# ORCHESTRATOR (heavy side): NOTHING NEW.
#   cv2.imencode comes from the already-pinned opencv-python==4.13.0.92; numpy already present.

# DEPLOY (optional, recommended for the field): pure-Python WSGI server for the console
pip install "waitress==3.0.2"   # serve console.html + static JPEGs on Windows, no streaming needed
#   ^ Deploy-only, console-side; pure-Python, stdlib-only deps, Windows-native.
#     Compatible with the polling approach (plain GETs). Do NOT adopt if you later switch to MJPEG.

# DO NOT INSTALL (rejected for v1.1):
#   flask-sock / simple-websocket  — push transport the file channel already obviates
#   Pillow / imageio               — no imaging lib in the crash-isolated console
#   gevent / eventlet              — async server machinery, only relevant to the MJPEG fallback
#   any npm/Vite/React/Vue toolchain — no build chain for one page
```

> Add `waitress` as an **optional deploy extra** (e.g. a `console`/`serve` extra in `pyproject.toml`), NOT a hard console runtime dep — the console must still run on the bare Flask dev server with only `Flask` importable, to keep the crash-isolation surface auditable.

---

## Integration points with the existing opcomm channel

1. **New publish dir:** `opcomm/preview/` (subdir of the existing `channel_dir`). The orchestrator writes `<cam>.jpg` there with a new `atomic_write_bytes(path, buf)` added to `opcomm.atomic` (same temp→fsync→`os.replace`→MoveFileEx-retry primitive; stdlib-only; stays a leaf). The console serves from the same subdir via `send_from_directory` with a fixed server-side path (path-traversal mitigation T-05-05-01 preserved — the cam id is whitelisted against the known camera set, never used raw as a path).
2. **Extended `status.json`:** add per-camera `score` and `track_reason` fields to `DirectorStatus` (`opcomm.records`), with default-on-missing readers (backward compatible). Console's existing 1 Hz `/status` poll surfaces them next to each tile.
3. **Overlay preview:** reuse the already-imported `ui.score_render.render_overlay_text` to show the score exactly as `overlay.txt` will render in OBS — pure client-side restyle of a string the console already produces.
4. **No new orchestrator→console coupling beyond files.** Pixels and structured state both cross the boundary only as atomically-swapped files. The crash-isolation contract is unchanged: kill the console and the director never notices; crash the director and the console shows stale tiles + a dead-feed placeholder (the `alive` map already drives that UX).

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `flask-sock` / `simple-websocket` in the console | New runtime deps on the crash-isolated side for push-latency a 5–10 fps operator monitor cannot perceive; the pixels still originate as published files | Polling JPEG files over the existing atomic-file channel |
| Any imaging lib (`Pillow`, `imageio`, `cv2`) in the console | Bloats and *contaminates* the auditable "Flask + opcomm only" surface (D-03/RBT-04) | Encode orchestrator-side with the already-present `cv2`; console serves raw bytes only |
| **Waitress + MJPEG together** | Waitress buffers full responses and does **not** support streaming → MJPEG never flushes frames | Polling files under Waitress; or, only if MJPEG is truly needed, the threaded dev server / gevent (and accept the held-thread model) |
| MJPEG as the *default* transport | One held thread per stream × tiles × viewers can exhaust the Werkzeug worker pool and block POSTs; breaks the clean Waitress deploy | Polling files by default; MJPEG only as an evidence-gated fallback |
| Raw camera id used as a filesystem path for `send_from_directory` | Path-traversal (T-05-05-01) | Whitelist the cam id against the known camera set; build the path from a fixed server-side prefix + the validated id |
| `<img src>` swap without preload | Visible flicker / half-loaded frames during refresh | Preload into `new Image()`, swap `src` on `onload` |
| Re-encoding stale repeated frames | Wastes orchestrator CPU inside the latency budget; publishes identical bytes | Gate encode on the feed watchdog's "last NEW frame" timestamp (already tracked) |
| React/Vue/Vite/npm build chain | Heavy toolchain for one Italian page; violates the no-build-chain constraint | Vanilla JS + CSS Grid `auto-fit`/`minmax` + `clamp()` |
| Embedding OBS MULTIVIEW in the console for v1.1 | Couples the console to OBS/video output (new network path/dep) and loses orchestrator-drawn per-tile framing annotations | Orchestrator-published per-camera annotated JPEGs |

---

## Version Compatibility

| Package | Version | Notes |
|---------|---------|-------|
| Flask | 3.1.3 (already pinned) | Streaming `Response` generator (MJPEG fallback) and `send_from_directory` (primary) are both stdlib-path; no upgrade needed |
| opencv-python | 4.13.0.92 (already pinned, orchestrator side) | `cv2.imencode(".jpg", ...)` returns a `numpy` buffer; `.tobytes()` for the atomic byte write |
| waitress | 3.0.2 | Pure-Python, CPython Unix+Windows 3.9+, stdlib-only deps; **no streaming** (fine for polling, fatal for MJPEG) |
| flask-sock | 0.7.0 (Oct 2023) — **NOT recommended** | Works on the Flask dev server without gevent; rejected on dependency-surface grounds |
| simple-websocket | 1.1.0 (Oct 2024) — **NOT recommended** | flask-sock's transport dep; rejected for the same reason |

---

## Sources

- Flask deployment / Waitress docs (flask.palletsprojects.com, latest + 3.1.x) — Waitress is the pure-Python Windows WSGI server; **buffers responses, no streaming support** — **HIGH**
- waitress PyPI + Pylons/waitress GitHub — pure-Python, CPython 3.9+ Unix+Windows, stdlib-only deps, "does not support streaming requests" — **HIGH**
- flask-sock PyPI/GitHub (miguelgrinberg) — v0.7.0 (2023-10-02), works on Flask dev server without greenlet server — **HIGH**
- simple-websocket PyPI (miguelgrinberg) — v1.1.0 (2024-10-10), MIT, Python ≥3.6 — **HIGH**
- Miguel Grinberg "Video Streaming with Flask" + "Revisited" + flask-video-streaming issues #11/#16 — MJPEG holds a worker thread per stream; dev server needs `threaded=True`; gevent recommended for many concurrent MJPEG clients — **HIGH/MEDIUM** (authoritative author, cross-checked across posts/issues)
- Web consensus (Cloudinary, nickhuber.ca, mjpeg-relay #11) — browser plays native motion-JPEG; any non-MJPEG push (WebSocket/base64) needs a custom client player — **MEDIUM**
- MDN / 2026 CSS-Grid responsive-layout consensus (multiple 2025–2026 guides) — `repeat(auto-fit, minmax())` + `clamp()` = query-light fluid layout, current standard; CSS Grid L2 in all major browsers by late 2024 — **MEDIUM/HIGH**
- In-repo verification (read 2026-06-13): `src/segugio/ui/app.py` (Flask+opcomm-only imports), `opcomm/atomic.py` (temp+fsync+os.replace+MoveFileEx retry), `opcomm/records.py` (`DirectorStatus` default-on-missing), `requirements.txt`/`pyproject.toml` (opencv-python 4.13.0.92, Flask 3.1.3 already pinned) — **HIGH**
