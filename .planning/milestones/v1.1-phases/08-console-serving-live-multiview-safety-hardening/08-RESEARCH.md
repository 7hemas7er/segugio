# Phase 8: Console Serving, Live Multiview & Safety Hardening - Research

**Researched:** 2026-06-13
**Domain:** Crash-isolated Flask console serving polling-JPEG multiview + two safety controls (`threaded=True`, config-time bandwidth cap) + a written threat re-eval
**Confidence:** HIGH

## Summary

Phase 8 is a **publish-and-render / serve problem, not a compute one**, and the load-bearing decisions are already settled by three converging sources: the locked v1.1 milestone research (`STACK.md`/`PITFALLS.md`/`ARCHITECTURE.md` — Phase 8 is explicitly its build-order steps 5–6), the detailed CONTEXT.md (D-01…D-09 locked), and the actual Phase-7 code seams which are already in place and tested. Phase 7 already writes per-camera JPEGs and a `preview.json` sidecar into `opcomm/preview/`; Phase 8 adds **two GET routes + a template grid + a server-entrypoint fix + a config validator + a docs file** — and nothing else. The console's import surface stays `Flask + segugio.opcomm` only, so the crash-isolation invariant (D-03/RBT-04) is preserved *by construction* (the console only `send_file`s bytes off disk and `read_preview`s JSON — it never decodes, never imports `cv2`/`numpy`/`torch`).

The two safety controls are the real engineering content. (1) `threaded=True` on the dev-server entrypoint (with Waitress as an optional deploy extra) so a preview GET can never pin the lone Werkzeug worker and stall the safety-critical `/command` override POST — this is the documented latent bug in `ui/app.py:143`. (2) A **static engineered bandwidth ceiling** (D-01): a config-time validator that computes total preview bitrate from `fps × width × height × jpeg_quality × N_cams` and rejects any over-cap config at startup via the existing fail-fast `SystemExit(2)` loader — there is NO runtime throttle. Phase 8's acceptance for the cap is a headless computed-budget assertion + over-cap-rejection test; the real-WiFi false-death validation is explicitly deferred to a hardware milestone (D-02).

The single most load-bearing implementation detail surfaced by reading the code: **the publisher writes `cam_{cam_id}.jpg`** (`preview.py:283`), so for a camera whose id is `cam_wide` the on-disk file is literally **`cam_cam_wide.jpg`**. The new `GET /preview/<cam>.jpg` route MUST map a whitelisted camera id to this exact `cam_{id}.jpg` filename, never use the URL segment as a raw path (path-traversal mitigation, T-05-05-01).

**Primary recommendation:** Extend `ui/app.py` with `GET /preview` (thin `read_preview` wrapper) + `GET /preview/<cam>.jpg` (whitelist `<cam>` against `config.cameras` ids → `send_file(preview_dir/cam_{id}.jpg)` with `Cache-Control: no-store`); extend `console.html` with a CSS-Grid `<img>` multiview (preload-`Image()` swap, `?t=<gen>` cache-bust) ON TOP of the existing controls; fix the entrypoint to `threaded=True` (Waitress optional extra inside the entrypoint); add a `Config` model-validator that rejects over-cap preview bitrate; write the threat re-eval as a new `docs/security.md`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The cap is a STATIC engineered ceiling, not a runtime-adaptive throttle. The Phase-7 `PreviewParams` defaults (fps × max_width × jpeg_quality) are chosen so the **computed** total preview bitrate for N cameras is provably ≤ the configured ceiling. A startup / config-validation check **rejects any config whose computed preview bitrate exceeds the cap** (fail-fast, same posture as the central config contract). No per-frame feedback loop, no dynamic fps/quality drop. The hard ceiling value (≤ 5–8 Mbps total) and the exact computed-bitrate formula are research/planner detail — anchor on the research budget; surface the ceiling as a config value.
- **D-02:** Phase-8 acceptance bar for the cap = a headless computed-budget assertion + an explicit documented deferral. A unit/headless test asserts the configured fps×res×quality yields ≤ the ceiling bitrate AND that an over-cap config is rejected. The real WiFi-with-phones false-death-rate-unchanged validation is **explicitly documented as a hardware-milestone carry-forward**. Do NOT build a synthetic network-contention harness.
- **D-03:** On-air tile emphasis = red border + LIVE badge + "ON AIR: CAM X" banner, driven by `status.live_cam`. Triple-redundant. The banner stays minimal; the plain-Italian *reason* render is Phase 9 (WHY-01).
- **D-04:** A tile reads "MORTO" (dead) when `status.alive[cam]` is false OR the preview is stale. Belt-and-suspenders. The deeper "never show a frozen frame as live" staleness *overlay* hygiene stays Phase 9 (UXT-03) — Phase 8 ships only the basic freshness gate for tile marking.
- **D-05:** Preview-staleness window = ~2–3× the publish interval, computed FROM the configured fps (not a hardcoded ms). At ~5 fps publish (~200 ms interval) that is ~0.6–1 s of no-new-frame before a tile flips to MORTO. Freshness is judged from the preview's own generation/tick token or JPEG mtime (Claude/planner picks the exact source).
- **D-06:** Page composition = multiview grid ON TOP, existing controls BELOW. Extend the existing single `console.html` page — do NOT reframework it.
- **D-07:** Phase 8 ships a MINIMAL responsive grid only; tiles are strictly display-only. CSS-Grid `repeat(auto-fit, minmax(...))` that reflows 1→2→4 columns by viewport, with the LIVE/dead marking — and nothing more. The existing blind text override buttons keep working.
- **D-08:** `threaded=True` is the in-code safety control; Waitress is an OPTIONAL deploy extra, never a hard console dep. Phase 8 lands `threaded=True` at minimum. The console must still run on the bare Flask dev server with only Flask importable. Transport stays polling JPEG files, NOT MJPEG. Prove "override served promptly while a preview stream is active" with a test that POSTs `/command` while preview GETs are in flight.
- **D-09:** The written v1.1 threat re-eval ACCEPTS the LAN-as-trust-boundary and mandates AP client-isolation — no new auth/code. Reaffirms v1.0's stance (T-05-05-04), ADDS the new exposure (live competitor video behind `0.0.0.0`), makes AP client-isolation + no-internet-bridge a HARD operational requirement. No configurable bind / basic-auth / shared-token in v1.1. Phase 7's `preview.enabled` already acts as the source-side off-switch.

### Claude's Discretion

- Preview-route shape: `GET /preview/<cam>.jpg` (whitelisted `send_file`) + `GET /preview` (`read_preview` sidecar). Exact route signatures, camera-id whitelist source (config cameras), and 404 behavior on unknown/absent cam are planner's call. The whitelist is the path-traversal mitigation.
- Cache-bust mechanism: in-sidecar `gen`/`tick` token vs `Date.now()`. Prefer the in-sidecar token if it avoids drift.
- Freshness source for D-05: preview `gen`/`tick` field vs served JPEG mtime. Pick whichever is cheapest and most reliable.
- `Image()` preload-swap cadence: the refresh fps the browser polls at (independent of publish fps; bounded by it). Start at publish cadence (~5 fps); tune in UAT.
- Where the `threaded=True`/Waitress entrypoint logic lives: keep the WSGI-server import inside the entrypoint to preserve the lazy import boundary.
- Threat re-eval doc location: existing security/threat-model doc vs a new `docs/` file. Cross-reference the v1.0 T-05-05-* threats.

### Deferred Ideas (OUT OF SCOPE)

- Clickable-tile informed override (MVW-04) — Phase 9. Phase 8 tiles are display-only.
- Explainability render (WHY-01..04, MVW-05) — Phase 9. All data already in `preview.json`.
- Live client-side score-overlay preview (SCV-01) — Phase 9.
- Full tablet-first restyle (UXT-01) — Phase 9. Phase 8 ships only the minimal responsive grid.
- Long-run hygiene: multi-hour soak, sleep/wake resume, deep staleness overlay, live kill-switch (UXT-03) — Phase 9.
- Runtime-adaptive bandwidth throttle — declined (D-01 static ceiling instead).
- Synthetic network-contention harness — declined (D-02).
- MJPEG / WebSocket transport — evidence-gated fallback only.
- In-code auth / configurable bind / shared-token gate — declined for v1.1 (D-09).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MVW-01 | Responsive CSS-Grid multiview of all cameras, flicker-free refresh via `Image()` preload + swap | `GET /preview/<cam>.jpg` route + `GET /preview` sidecar route; CSS Grid `repeat(auto-fit, minmax())` (STACK.md); preload-`Image()`-`onload`-swap pattern (STACK.md "Vanilla JS `Image()` preload + `src` swap"); `?t=<gen>` cache-bust from `PreviewDoc.gen` (already published, `preview.py:_build_doc`) |
| MVW-02 | LIVE/tally on the on-air tile (red border/badge + "ON AIR: CAM X"), from `status.live_cam` | Existing `GET /status` already returns `live_cam` (`app.py:128`); client compares each tile's cam id to `status.live_cam` and toggles a CSS class + renders the banner. D-03. |
| MVW-03 | Dead/stale feed marking from `status.alive` + preview freshness | `status.alive` already returned by `GET /status`; freshness from `PreviewDoc.gen`/`tick` advancing in `preview.json` (D-05). Tile flips to "MORTO" when `alive[cam]==false` OR no-new-frame within ~2–3× publish interval. D-04. |
| UXT-02 | `threaded=True`/Waitress server fix — override POST never blocked while serving thumbnails | The latent single-threaded `app.run()` at `app.py:143` (Pitfall 7). Fix: `threaded=True` minimum; Waitress optional extra inside the entrypoint. Concurrency test POSTs `/command` while preview GETs are in flight. D-08. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JPEG encode/downscale | Orchestrator (heavy) | — | Already done by Phase-7 `PreviewPublisher` off-tick; console never encodes (D-03 crash-isolation). NOT this phase. |
| Serve JPEG bytes | Console / API (Flask) | — | `send_file` of bytes off disk — no decode, no image lib. Phase 8 adds this route. |
| Serve "why"/freshness JSON | Console / API (Flask) | — | Thin `read_preview` wrapper; `preview.json` already written by Phase 7. |
| Multiview render + LIVE/dead marking | Browser / Client (tablet) | — | Pure client-side CSS + vanilla JS in `console.html`; tiles display-only this phase (D-07). |
| Cache-bust + flicker-free swap | Browser / Client | — | `Image()` preload + `?t=<gen>` swap — browser-native, no library. |
| Bandwidth cap enforcement | Config loader (startup, fail-fast) | — | A `Config` model-validator computes bitrate and rejects over-cap at `model_validate` time (D-01); NOT a runtime tier. |
| Override-never-blocked | Console / API server (WSGI) | — | `threaded=True` / Waitress at the entrypoint; a serving concern, not application logic (D-08). |
| Threat re-eval | Docs (project docs) | — | A written `docs/` file; operational mitigation (AP isolation), no code (D-09). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 (already pinned) | `send_file` / `send_from_directory` for JPEG bytes; `jsonify` for the sidecar; `threaded=True` on `app.run` | Already the only console framework; `send_file` is stdlib-path, no decode, no new dep `[CITED: STACK.md L46]` |
| `segugio.opcomm` | in-repo | `read_preview` (sidecar reader) — the only data dependency the new routes need | Already exists (`channel.py:202`), safe-default never-raise reader `[VERIFIED: codebase channel.py]` |
| CSS Grid `repeat(auto-fit, minmax())` + `clamp()` | native (all modern tablet browsers 2024+) | Responsive 1→2→4-col multiview without media-query thickets | 2026 query-light fluid-layout standard; CSS Grid L2 shipped all major browsers by late 2024 `[CITED: STACK.md L172 — MEDIUM/HIGH]` |
| Vanilla JS `Image()` preload + `src`-swap + `fetch`/`setInterval` | native (already used in `console.html`) | Flicker-free `<img>` refresh + status/preview polling | The page is already vanilla; same shape as the existing `pollStatus` loop `[CITED: STACK.md L47]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `waitress` | 3.0.2 | Pure-Python Windows-native WSGI server for the field deploy; long-lived GETs and control POSTs don't fight a dev-server worker | OPTIONAL deploy extra ONLY (D-08). Import kept INSIDE the entrypoint. Console must still run on bare Flask with only Flask importable. Compatible with polling (plain GETs); do NOT pair with MJPEG (Waitress buffers, no streaming) `[VERIFIED: npm/PyPI — see Package Legitimacy Audit; CITED: STACK.md L158]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Polling JPEG files | MJPEG `multipart/x-mixed-replace` | Holds a worker thread per stream; breaks under Waitress; bigger per-tile failure blast radius. Evidence-gated fallback ONLY (adopt only if polling cadence proves visibly choppy in UAT AND higher fps is genuinely wanted) `[CITED: STACK.md L84, REQUIREMENTS.md L140]` |
| Polling JPEG files | WebSocket (flask-sock + simple-websocket) | 2 new deps on the crash-isolated console for push-latency a 5–10 fps operator monitor cannot perceive. Rejected for v1.1 `[CITED: STACK.md L74, REQUIREMENTS.md L140]` |
| `?t=<gen>` cache-bust (in-sidecar token) | `?t=${Date.now()}` | `Date.now()` works but the in-sidecar `gen` is already published and is monotonic per publish — using it means the URL only changes when there is genuinely a new frame, which is also the freshness signal. Recommend `gen`. |

**Installation:**
```bash
# CONSOLE (crash-isolated, light side): NOTHING NEW. Stays Flask==3.1.3 + segugio.opcomm.
# ORCHESTRATOR: NOTHING NEW (encode already done in Phase 7).
# DEPLOY (optional extra, NOT a hard dep) — pyproject.toml [project.optional-dependencies]:
#   console = ["waitress==3.0.2"]   # or "serve"; import kept inside the entrypoint
```

**Version verification:** `waitress` 3.0.2 is the version already cited and pinned in the milestone STACK.md (verified 2026-06-13 against PyPI per that doc's sources). Flask 3.1.3 and opencv-python 4.13.0.92 are already in `requirements.txt`/`pyproject.toml` — no upgrade needed for this phase.

## Package Legitimacy Audit

> Phase 8 installs **no new mandatory runtime package**. The only candidate is `waitress` as an **optional** deploy extra.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `waitress` | PyPI | ~12 yrs (Pylons project) | ~10M+/wk | github.com/Pylons/waitress | OK | Approved as OPTIONAL extra only |
| `flask` | PyPI | already installed (3.1.3) | very high | github.com/pallets/flask | OK | Already pinned — no install |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

`waitress` is a long-established, high-trust Pylons-project package already vetted and pinned in the v1.1 milestone STACK.md `[CITED: STACK.md L167]`. It is NOT a hard console dependency — the planner should add it as `[project.optional-dependencies].console` (or `serve`) and keep the import inside the `__main__`/serve entrypoint so the crash-isolation import test still passes with `waitress` absent. No legitimacy checkpoint needed (well-known package, optional, no postinstall).

## Architecture Patterns

### System Architecture Diagram

```
                         opcomm/ DIRECTORY (the ONLY coupling — atomic files, written by Phase 7)
                         ┌──────────────────────────────────────────────────────────────┐
   ORCHESTRATOR  ──────► │  status.json   (live_cam / reason / alive)   ◄ existing         │
   (Phase 7, off-tick)   │  preview/preview.json   (gen / tick / cams / auto_candidate)    │
                         │  preview/cam_<id>.jpg   × N   (e.g. cam_cam_wide.jpg)           │
                         └───────────────┬──────────────────────────────────┬─────────────┘
                                         │ read_status()        read_preview()│  send_file()
   CONSOLE PROCESS (Flask + segugio.opcomm ONLY — crash-isolated, D-03)      │
   ┌─────────────────────────────────────────────────────────────────────────────────────┐
   │  GET /status            → read_status(status.json)        → {live_cam, reason, alive}  │  (existing)
   │  GET /preview           → read_preview(preview/preview.json) → {gen, tick, cams, ...}  │  (NEW)
   │  GET /preview/<cam>.jpg → whitelist <cam> → send_file(preview/cam_<cam>.jpg)           │  (NEW)
   │  POST /command /run /score                                                             │  (existing)
   │  entrypoint: app.run(host=0.0.0.0, port=8080, threaded=True)  | waitress.serve(...)    │  (UXT-02 FIX)
   └───────────────┬───────────────────────────────────────────────────────┬─────────────┘
                   │  HTTP                                                    │  HTTP (img)
   ┌───────────────▼───────────────────────────────────────────────────────▼─────────────┐
   │  TABLET BROWSER — console.html (one inline-CSS/JS Italian page)                        │
   │   • CSS-Grid multiview (repeat(auto-fit, minmax)) ON TOP (D-06)                        │
   │   • per-cam <img>: new Image(); onload→swap src=/preview/<cam>.jpg?t=<gen>  (~5 fps)   │
   │   • LIVE tile  : cam == status.live_cam → red border + LIVE badge + "ON AIR: CAM X"    │
   │   • MORTO tile : status.alive[cam]==false OR gen not advancing within ~2–3× interval   │
   │   • existing score / run / override controls BELOW (display-only tiles, D-07)          │
   └───────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (the delta — Phase 8 touches only these)
```
src/segugio/
├── ui/
│   ├── app.py            # + GET /preview, GET /preview/<cam>.jpg, + threaded=True/waitress entrypoint (MODIFIED)
│   └── templates/
│       └── console.html  # + CSS-Grid multiview ON TOP + Image()-swap JS + LIVE/MORTO marking (MODIFIED)
├── config/
│   └── models.py         # + Config model-validator: reject over-cap preview bitrate (D-01) (MODIFIED)
docs/
└── security.md           # NEW — v1.1 threat re-eval (D-09); cross-refs T-05-05-* docstrings
pyproject.toml            # + [project.optional-dependencies].console = ["waitress==3.0.2"] (MODIFIED)
```

### Pattern 1: Whitelisted preview route (path-traversal mitigation, T-05-05-01)
**What:** `GET /preview/<cam>.jpg` maps a URL camera id to a FIXED server-side filename — never uses the URL segment as a raw path.
**When to use:** Any time a client-supplied token selects a server file.
**Example:**
```python
# ui/app.py — inside create_app, after the existing routes.
# The whitelist is the set of configured camera ids. create_app currently takes ONLY
# channel_dir; the planner must pass the cam-id set in (e.g. create_app(channel_dir, cam_ids))
# or read it from config — keep the import set Flask + opcomm only (NO config heavy import).
from flask import send_file, abort

_PREVIEW_SUBDIR = "preview"

@app.get("/preview/<cam>.jpg")
def get_preview_jpg(cam: str):
    if cam not in cam_ids:                 # whitelist — unknown id → 404, never a path
        abort(404)
    # On-disk filename is cam_<id>.jpg (preview.py:283) → e.g. cam_cam_wide.jpg
    path = _path(os.path.join(_PREVIEW_SUBDIR, f"cam_{cam}.jpg"))
    if not os.path.exists(path):           # publisher not yet written this cam → 404 (browser shows placeholder)
        abort(404)
    resp = send_file(path, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store"   # belt-and-suspenders alongside the JS ?t= cache-bust
    return resp

@app.get("/preview")
def get_preview():
    doc = read_preview(_path(os.path.join(_PREVIEW_SUBDIR, "preview.json")))
    return jsonify({"gen": doc.gen, "tick": doc.tick,
                    "auto_candidate": doc.auto_candidate, "cams": doc.cams})
```
> **Load-bearing:** the file is `cam_{cam_id}.jpg`. With ids like `cam_wide`, the file is `cam_cam_wide.jpg`. Verify the exact id set against `config.cameras` at plan time — the existing `console.html` hardcodes `cam_wide`/`cam_long`/`cam_low`/`cam_handler` in the override buttons (`console.html:85-88`), which matches the Phase-5 config `cam_<role>` ids.

### Pattern 2: Flicker-free `Image()` preload + swap (MVW-01)
**What:** Load the next JPEG into an off-DOM `new Image()`; on its `onload`, assign that `src` to the visible `<img>`. The visible tile never shows a half-loaded frame.
**Example:**
```javascript
// console.html <script> — one refresher per camera tile.
function refreshTile(cam, gen) {
  const img = new Image();
  img.onload = () => { document.getElementById("tile-" + cam).src = img.src; };
  img.src = `/preview/${cam}.jpg?t=${gen}`;   // gen from /preview poll → only changes on a new frame
}
```
**Cadence:** drive refresh from the `/preview` poll. Poll `/preview` at ~the publish fps (~5 Hz); each poll yields a `gen` — if `gen` advanced, refresh all tiles with the new `gen`. This couples refresh to genuine new frames AND gives the freshness signal for D-05 in one round-trip (cheapest, most reliable — see Open Question resolution).

### Pattern 3: Config-time bandwidth ceiling (D-01, fail-fast)
**What:** A `Config` `@model_validator(mode="after")` computes the worst-case preview bitrate and raises `ValueError` (→ aggregated into the loader's `SystemExit(2)`) if it exceeds a configured ceiling.
**Example:**
```python
# config/models.py — add a ceiling field to PreviewParams and a Config-level validator.
# PreviewParams gains: max_total_mbps: Annotated[float, Field(gt=0.0)] = 8.0   # the hard ceiling (D-01)
@model_validator(mode="after")
def _preview_bitrate_within_cap(self) -> "Config":
    p = self.preview
    if not p.enabled:
        return self
    n = len(self.cameras)
    # Worst-case computed bitrate. JPEG size scales ~ width*height*quality_factor; height from a
    # typical 16:9 thumbnail (h = max_width * 9/16). bytes_per_frame ≈ width*height*bpp(quality).
    # Anchor the formula + bpp constant in the validator with a documented comment (see formula below).
    est_bytes = _estimate_jpeg_bytes(p.max_width, p.jpeg_quality)
    total_mbps = est_bytes * 8 * p.fps * n / 1_000_000
    if total_mbps > p.max_total_mbps:
        raise ValueError(
            f"preview computed bitrate {total_mbps:.1f} Mbps exceeds cap "
            f"{p.max_total_mbps} Mbps (fps={p.fps}, width={p.max_width}, "
            f"q={p.jpeg_quality}, cams={n}); lower fps/width/quality or raise the cap")
    return self
```
> The formula and bpp constant are the planner's calibration point — see "The hard ceiling value & formula" in Open Questions. The Phase-7 defaults (5 fps / 384 px / q55 / 4 cams) already produce ~0.3–0.8 MB/s = ~2.4–6.4 Mbps `[CITED: 07-CONTEXT D-05 / ARCHITECTURE.md L219]`, comfortably under an 8 Mbps ceiling — so default configs validate, and the test asserts both that pass AND that a deliberately-cranked config (e.g. 30 fps / 1920 px / q100) is rejected.

### Pattern 4: `threaded=True` / Waitress entrypoint (UXT-02, D-08)
**What:** Serving a preview GET must never pin the lone Werkzeug worker and stall `/command`.
**Example:**
```python
# ui/app.py — the __main__ block (and/or a serve() function). Import waitress INSIDE so the
# lazy boundary holds (bare Flask still runs with waitress absent).
if __name__ == "__main__":
    _dir = os.environ.get("SEGUGIO_OPCOMM_DIR", os.path.join(os.getcwd(), "opcomm"))
    app = create_app(_dir, cam_ids=...)            # cam_ids resolved from config or env
    try:
        from waitress import serve                  # optional deploy extra (import inside entrypoint)
        serve(app, host="0.0.0.0", port=8080)
    except ImportError:
        app.run(host="0.0.0.0", port=8080, threaded=True)   # dev-server fallback — threaded=True is the MINIMUM safety control
```
> The `threaded=True` is the **hard requirement** (UXT-02); Waitress is the optional preference. Keeping `app.run(..., threaded=True)` as the fallback means the crash-isolation import test (which runs with the heavy stack absent and only Flask importable) still passes whether or not `waitress` is installed.

### Anti-Patterns to Avoid
- **Using `<cam>` as a filesystem path** — path-traversal (T-05-05-01). Always whitelist against `config.cameras` ids and build `cam_{id}.jpg` from a fixed prefix.
- **Importing `config`/`cv2`/`numpy` into `ui/app.py`** — breaks D-03 crash-isolation. Pass the cam-id whitelist in as a plain list/set (a constructor arg or env), not by importing the heavy config machinery. (`segugio.config` is light, but the cleanest contract is to pass the ids in.)
- **`app.run()` without `threaded=True`** — the latent Pitfall-7 bug; one slow GET freezes the override POST.
- **MJPEG / WebSocket for v1.1** — explicitly out of scope (REQUIREMENTS.md L140); polling JPEG files only.
- **A runtime bitrate throttle** — D-01 is a config-time guarantee, not a feedback loop. Adding dynamic fps/quality drop overlaps Phase-9 UXT-03 and adds moving parts to the never-crash side.
- **Reframeworking `console.html`** — D-06: extend the one inline-CSS/JS page; no SPA, no bundler.
- **Rendering Phase-9 payload** — the `preview.json` `cams` carry score/box/track_id/energy, but Phase 8 renders ONLY the tile set + LIVE/MORTO marking. Do not draw score bars/bbox/reason (Phase 9).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Serving JPEG bytes with correct headers/range/etag | A manual `open().read()` + `Response` | Flask `send_file(path, mimetype="image/jpeg")` | Handles conditional/range/mimetype correctly, stdlib-path, no decode `[CITED: STACK.md L46]` |
| Atomic JPEG/sidecar reads | A retry/lock read loop | Already done: Phase-7 `atomic_write_bytes` writer + `read_preview` safe-default reader | Tear-free by construction; `read_preview` never raises (`channel.py:202`) `[VERIFIED: codebase]` |
| Flicker-free image refresh | A double-buffer canvas / blob-URL churn | `new Image()` + `onload` `src`-swap | Browser-native double-buffer; no `URL.createObjectURL` leak (the Phase-9 soak hazard) `[CITED: STACK.md L47, PITFALLS.md Pitfall 8]` |
| Responsive 1→2→4 col grid | Media-query breakpoints | CSS Grid `repeat(auto-fit, minmax(...))` | One rule, query-light, current standard `[CITED: STACK.md L63]` |
| Multi-request serving | Threaded loop / async event machinery | `app.run(threaded=True)` or `waitress.serve` | Standard WSGI concurrency; do not invent a worker pool `[CITED: PITFALLS.md Pitfall 7]` |
| Config bitrate enforcement | A runtime monitor | A pydantic `@model_validator` → `SystemExit(2)` at load | Fail-fast at startup, same posture as every other config invariant (CFG-01) `[VERIFIED: codebase loader.py]` |

**Key insight:** Phase 8 builds almost no new mechanism — every primitive (atomic write, safe-default read, fail-fast validation, the status poll, the page) already exists and is tested. The work is wiring two routes, a template section, an entrypoint flag, a validator, and a docs file. Resist inventing transport or throttle machinery the milestone research already rejected.

## Common Pitfalls

### Pitfall 1: Single-threaded server freezes the override (UXT-02 — the headline pitfall)
**What goes wrong:** `app.run()` defaults to single-threaded; a preview GET (or several, 4 tiles × tablets) pins the lone worker so `/command` cannot be served — the operator hits "Forza CAM2" and nothing happens.
**Why it happens:** v1.0 only had short handlers, so single-threaded was invisible; adding preview GETs exposes it. Silent in single-tab dev testing.
**How to avoid:** `threaded=True` minimum (D-08); Waitress for the field deploy. Prove with a POST-`/command`-during-active-preview-GETs concurrency test.
**Warning signs:** override/status feels frozen exactly while preview is on screen `[CITED: PITFALLS.md Pitfall 7]`.

### Pitfall 2: Path traversal via the `<cam>` URL segment
**What goes wrong:** Using `<cam>` directly in a path lets `../../etc/...` style requests escape the preview dir.
**How to avoid:** Whitelist `<cam>` against the configured camera ids; `abort(404)` on anything else; build the filename from a fixed `cam_{id}.jpg` prefix `[CITED: STACK.md L144, T-05-05-01]`.

### Pitfall 3: Wrong JPEG filename (the `cam_cam_<id>.jpg` trap)
**What goes wrong:** Assuming the file is `cam_wide.jpg` when the publisher writes `cam_{cam_id}.jpg` = `cam_cam_wide.jpg` (`preview.py:283`) → every preview GET 404s, tiles silently never load.
**How to avoid:** Map whitelisted id → `cam_{id}.jpg`. Add a test that asserts the route serves bytes for a file written at exactly `preview/cam_{id}.jpg` `[VERIFIED: codebase preview.py:283]`.

### Pitfall 4: Frozen-frame-shown-as-live (D-04/D-05 freshness)
**What goes wrong:** Publisher pauses/crashes; the last JPEG sits on disk and the tile keeps showing a frozen image that looks live — the operator overrides on a lying UI.
**How to avoid:** Drive the MORTO marking from `status.alive[cam]==false` OR `gen`/`tick` not advancing within ~2–3× the publish interval (D-05). Phase 8 ships only this basic gate; the deeper "reconnecting" overlay is Phase 9 `[CITED: PITFALLS.md Pitfall 4, CONTEXT D-04/D-05]`.

### Pitfall 5: Crash-isolation regression from a stray import
**What goes wrong:** Pulling `cv2`/`numpy`/heavy config into `ui/app.py` to "just get the cam ids" silently breaks the D-03 invariant; the import test (heavy stack absent) goes red.
**How to avoid:** Pass the cam-id whitelist in as a plain list (constructor arg or env). Keep the console import set Flask + `segugio.opcomm`. The Phase-7 crash-isolation import test (`test_imports.py`, heavy modules forced absent) is the regression gate — keep `segugio.ui` in scope and green `[CITED: ARCHITECTURE.md L317, test_imports.py]`.

### Pitfall 6: Computed bitrate formula too loose or too tight
**What goes wrong:** A bitrate formula that wildly over- or under-estimates either rejects valid configs or lets over-budget ones through, defeating D-01's guarantee.
**How to avoid:** Anchor the formula on the documented Phase-7 measurement (5 fps / 384 px / q55 / 4 cams ≈ 0.3–0.8 MB/s) and pick a bpp constant that reproduces that range, then set the ceiling at ≤ 8 Mbps. Document the constant. Test asserts both the default passes AND a cranked config fails `[CITED: 07-CONTEXT D-05, PITFALLS.md Pitfall 1]`.

## Runtime State Inventory

> Phase 8 is additive (new routes/template/validator/docs); it renames/migrates nothing. Inventory included for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `preview.json` + `cam_*.jpg` already produced by Phase 7; Phase 8 only reads them. | None |
| Live service config | None — no external service config changes. | None |
| OS-registered state | None — no Task Scheduler / service registration. | None |
| Secrets/env vars | `SEGUGIO_OPCOMM_DIR` already read by the entrypoint (`app.py:142`); unchanged. No new secrets (D-09: no auth/token). | None |
| Build artifacts | If `waitress` is added as an optional extra, the `console`/`serve` extra must be declared in `pyproject.toml`; no rebuild of installed package state required for the bare console. | Declare optional extra only |

**Nothing found in category:** Stored data, live service config, OS-registered state — None (verified by reading the seams: Phase 8 is read-only against the Phase-7 channel + adds template/route/validator/docs).

## Code Examples

See Patterns 1–4 above — every example is grounded in the actual seams (`app.py`, `console.html`, `channel.py:read_preview`, `models.py`, `preview.py:283`). No external-doc code is needed; the milestone STACK.md already verified the Flask/CSS-Grid/`Image()` idioms against official sources `[CITED: STACK.md Sources]`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Media-query breakpoint grids | CSS Grid `repeat(auto-fit, minmax())` + `clamp()` | CSS Grid L2 in all major browsers by late 2024 | One rule for 1→2→4 col reflow; no breakpoint maintenance `[CITED: STACK.md L172]` |
| MJPEG / WebSocket "live" video in browser | Polling JPEG thumbnails for an operator monitor | v1.1 milestone decision | Zero new console deps, reuses atomic channel, smallest test surface, runs on Waitress `[CITED: STACK.md TL;DR]` |

**Deprecated/outdated:**
- Single-threaded `app.run()` with any non-trivial concurrent load: the latent UXT-02 bug — superseded by `threaded=True`/Waitress.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The hard ceiling is **8 Mbps** (top of the research's 5–8 Mbps band) and a single bpp constant calibrated to the Phase-7 0.3–0.8 MB/s measurement reproduces realistic JPEG sizes | Pattern 3 / Open Questions | Validator could reject valid configs (too tight) or pass over-budget ones (too loose). Mitigated: test asserts default-passes + cranked-fails. The exact value is surfaced as a config field, so it's tunable, not baked. |
| A2 | The camera-id whitelist source is `config.cameras` ids, passed into `create_app` as a plain list (e.g. `create_app(channel_dir, cam_ids)`) to preserve the import boundary | Pattern 1/4, Pitfall 5 | If the planner instead reads config inside the console, must confirm `segugio.config` stays light (it is) and the import test still passes. Low risk. |
| A3 | The threat re-eval doc lives at a NEW `docs/security.md` (no standalone SECURITY.md / threat-model file exists today; T-05-05-* live as docstrings in `ui/app.py` + `loop.py`) | Open Questions / Validation | None material — criterion 5 only requires the doc "exists in the project docs." Confirmed no `SECURITY.md`/`THREAT_MODEL.md` exists (Glob returned none). |
| A4 | The on-disk JPEG name is `cam_{cam_id}.jpg` (→ `cam_cam_wide.jpg`) and the cam ids are `cam_wide/cam_long/cam_low/cam_handler` | Pattern 1, Pitfall 3 | VERIFIED in code (`preview.py:283`, `console.html:85-88`, conftest `_PHASE5_CONFIG`) — not actually an assumption, listed for visibility. |

## Open Questions (RESOLVED)

1. **Exact preview-route signatures, whitelist source, 404 behavior**
   - What we know: `GET /preview/<cam>.jpg` whitelisted `send_file`; `GET /preview` → `read_preview`. File is `cam_{id}.jpg`.
   - Recommendation: whitelist `<cam>` against the cam-id set passed into `create_app`; `abort(404)` on unknown id AND on not-yet-written file (browser shows a placeholder/`onerror` tile, which doubles as the "no frame yet" state). `Cache-Control: no-store` on the JPEG response in addition to the `?t=<gen>` JS cache-bust.

2. **Cache-bust: in-sidecar `gen`/`tick` vs `Date.now()`**
   - Recommendation: use the in-sidecar **`gen`** token from `/preview`. It only advances on a genuine new publish, so the `<img>` URL only changes when there is a new frame — which doubles as the freshness signal (one poll serves both refresh and MORTO logic). `Date.now()` would refetch every interval even when nothing changed (wasted bytes on contended WiFi — counter to D-01's spirit).

3. **Freshness source for D-05: `gen`/`tick` field vs JPEG mtime**
   - Recommendation: use the **`gen`** field from the `/preview` poll, client-side. The client remembers the last `gen` and the wall-clock time it last changed; if `gen` has not advanced for > ~2–3× the publish interval, mark all tiles (or per-cam if a per-cam token is later added) stale → MORTO. Cheapest (no extra server call, no `os.stat`), most reliable (mtime can be misleading across atomic replace + Windows clock granularity). NOTE: `gen` is currently a single global token (one `preview.json`), so freshness is whole-channel, not per-cam — combined with per-cam `status.alive[cam]`, this satisfies D-04's belt-and-suspenders for Phase 8. (A per-cam freshness token is a Phase-9 UXT-03 refinement, not needed here.)

4. **`Image()` preload-swap cadence vs publish fps**
   - Recommendation: poll `/preview` at ~the configured publish fps (~5 Hz); refresh tiles only when `gen` advances. Start at 5 fps; tune in UAT. Bounded by publish fps by construction (no point polling faster than new frames appear).

5. **Where the `threaded=True`/Waitress entrypoint logic lives**
   - Recommendation: in the `__main__` block (and optionally a `serve()` function), with `from waitress import serve` INSIDE the block. `app.run(..., threaded=True)` as the fallback. Preserves the lazy import boundary; bare Flask still runs.

6. **The hard ceiling value & computed-bitrate formula**
   - Recommendation: ceiling = **8 Mbps** (config field `preview.max_total_mbps`, default 8.0). Formula: `total_mbps = est_bytes_per_frame(width, quality) × 8 × fps × N_cams / 1e6`, with `est_bytes_per_frame` derived from a documented bpp constant calibrated so the Phase-7 defaults (5/384/q55/4) land in the measured 0.3–0.8 MB/s (~2.4–6.4 Mbps) band. Surface the constant + ceiling with a comment citing the Phase-7 measurement.

7. **Threat re-eval doc location**
   - Recommendation: NEW `docs/security.md` (project already has `docs/obs-setup.md`, `docs/run.md`). Cross-reference the T-05-05-* threats documented in `ui/app.py`'s and `loop.py`'s docstrings. Content per D-09: reaffirm LAN-as-trust-boundary (T-05-05-04), add the new live-video-behind-`0.0.0.0` exposure, make AP client-isolation + no-internet-bridge a HARD operational requirement, note `preview.enabled` as the source-side off-switch, state explicitly that no auth/configurable-bind/token is added in v1.1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Flask | console serving | ✓ (pinned) | 3.1.3 | — |
| `segugio.opcomm` | `read_preview` | ✓ (in-repo) | — | — |
| Phase-7 publisher output (`preview/*.jpg`, `preview.json`) | the routes serve these | ✓ (Phase 7 complete) | — | route 404s gracefully if absent → tile placeholder |
| `waitress` | optional field deploy | optional | 3.0.2 (target) | `app.run(threaded=True)` dev server |
| A web browser / tablet | rendering | ✓ (operator-side) | modern (CSS Grid L2) | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `waitress` (optional) → `app.run(threaded=True)`; Phase-7 output absent at runtime → routes 404 and tiles show a placeholder (graceful, by design).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing suite; `tests/` ~60 files) |
| Config file | pytest config in `pyproject.toml` (existing) |
| Quick run command | `python -m pytest tests/test_preview_serving.py tests/test_imports.py -x -q` |
| Full suite command | `python -m pytest -q` |

> All Phase-8 tests are HEADLESS and CPU-only — no GPU, no cv2, no real network. They use the existing `file_channel` fixture (tmp_path-backed opcomm dir, `conftest.py:422`) and the Flask `test_client` pattern (`test_ui_run.py`). The planner should add a `preview` sub-dir + sample `cam_<id>.jpg` + `preview.json` to a fixture (extend `file_channel` or add a `preview_channel` fixture).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MVW-01 | `GET /preview/<cam>.jpg` serves the bytes at `preview/cam_<id>.jpg` (200, `image/jpeg`); `GET /preview` returns the sidecar JSON (gen/tick/cams) | unit (Flask test_client) | `pytest tests/test_preview_serving.py -k serve -x` | ❌ Wave 0 |
| MVW-01 | unknown cam id → 404; `<cam>` cannot path-traverse (e.g. `../status`) → 404, never reads outside preview dir | unit (security) | `pytest tests/test_preview_serving.py -k whitelist -x` | ❌ Wave 0 |
| MVW-02 | given `status.live_cam`, the client marks the matching tile LIVE — *render logic is client-side*; test the DATA contract: `/status` exposes `live_cam`, `/preview` exposes `cams` keyed by the same ids | unit (contract) | `pytest tests/test_preview_serving.py -k live_contract -x` | ❌ Wave 0 |
| MVW-03 | MORTO marking inputs present: `/status` returns `alive[cam]`; `/preview` returns a monotonic `gen` that advances on new publish and is stable when none → the freshness signal exists | unit (contract) | `pytest tests/test_preview_serving.py -k freshness -x` | ❌ Wave 0 |
| UXT-02 | a POST `/command` returns promptly (no freeze) WHILE concurrent `/preview/<cam>.jpg` GETs are in flight | concurrency | `pytest tests/test_preview_concurrency.py -x` | ❌ Wave 0 |
| D-01/D-02 | the default `PreviewParams` (5/384/q55) × N cams yields computed bitrate ≤ ceiling (passes validation); an over-cap config (cranked fps/width/quality) raises `ValidationError` / `SystemExit(2)` at load | unit (config) | `pytest tests/test_preview_bitrate_cap.py -x` | ❌ Wave 0 |
| D-03 (regression) | `import segugio.ui` + `create_app(...)` start-check resolve with `torch`/`cv2`/`numpy`/`cyndilib`/`obsws` forced absent, AFTER the new routes are added | import guard | `pytest tests/test_imports.py -x` | ✅ exists (extend) |

**Notes on MVW-02/03 testing:** the LIVE/MORTO *visual* marking is pure client-side CSS/JS (display-only, D-07). The provable server-side assertion is the **data contract** that drives it: `/status` exposes `live_cam` + `alive`, and `/preview` exposes a monotonic `gen`. A JS-DOM render test is NOT required for Phase 8 (deferred to manual UAT / Phase-9 tablet validation). The concurrency test (UXT-02) is the one genuinely new test shape — use `threading`/`concurrent.futures` to fire N preview GETs against the test client while timing a `/command` POST; assert the POST completes well under a threshold (e.g. < 1 s) and is written. Because the Flask `test_client` does not exercise the WSGI server's threading, the planner should EITHER run a real `app.run(threaded=True)`/`waitress` server on a background thread + bind to an ephemeral port for this one test, OR document that the test asserts the entrypoint sets `threaded=True` (inspect the call) plus an integration-style check. Prefer the real-server-on-ephemeral-port approach for a true concurrency proof.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_preview_serving.py tests/test_preview_bitrate_cap.py tests/test_imports.py -x -q`
- **Per wave merge:** `python -m pytest tests/test_preview_serving.py tests/test_preview_concurrency.py tests/test_preview_bitrate_cap.py tests/test_imports.py tests/test_ui_run.py -q`
- **Phase gate:** full suite green (`python -m pytest -q`) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_preview_serving.py` — covers MVW-01/02/03 (serve, whitelist/404, live+freshness data contracts)
- [ ] `tests/test_preview_concurrency.py` — covers UXT-02 (override POST not blocked during preview GETs)
- [ ] `tests/test_preview_bitrate_cap.py` — covers D-01/D-02 (default passes, over-cap rejected)
- [ ] `tests/conftest.py` extension — a `preview_channel` fixture (preview sub-dir + sample `cam_<id>.jpg` + `preview.json`); reuse the existing `file_channel`
- [ ] `tests/test_imports.py` — extend the existing crash-isolation guard to re-assert after the new routes (already in `PHASE1_SURFACE`; confirm `create_app` + new routes import clean with heavy stack absent)

### Explicitly Deferred to a Hardware Milestone (D-02)
- Real-WiFi-with-phones false-death-rate-unchanged: requires 3–4 real NDI phones on the dedicated AP + the console open; cannot be validated headless. Documented as a carry-forward, NOT a Phase-8 test. No synthetic contention harness is built (rejected, D-02).

## Security Domain

> `security_enforcement` is not disabled — included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Crash-isolation boundary (D-03): console imports only Flask + opcomm; the documented LAN trust boundary (T-05-05-04) re-evaluated in `docs/security.md` (D-09) |
| V2 Authentication | no (accepted) | NONE — single-operator dedicated-LAN field tool; no-auth is an ACCEPTED, documented decision (D-09 / T-05-05-04), with AP client-isolation as the operational mitigation. NOT an oversight. |
| V4 Access Control | no | LAN is the trust boundary; no per-user access control by design (D-09) |
| V5 Input Validation | yes | `<cam>` whitelisted against config ids → path-traversal mitigation (T-05-05-01); over-cap config rejected fail-fast (D-01) |
| V6 Cryptography | no | No secrets, no tokens, no TLS in v1.1 (D-09 declines auth/token) |
| V12 Files/Resources | yes | `send_file` against a fixed server-side path built from a whitelisted id; no client-supplied path; preview frames ephemeral (overwrite-in-place, no retention surface) `[CITED: PITFALLS.md Pitfall 6]` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `<cam>` URL segment | Tampering / Info-disclosure | Whitelist cam id against config; fixed `cam_{id}.jpg` filename; `abort(404)` otherwise (T-05-05-01) |
| Live competitor video exposed to anyone on/near the LAN (blast-radius grew from "panel" to "video") | Information Disclosure | D-09 written re-eval: HARD requirement of AP client-isolation + no internet/guest bridge; ephemeral frames only (no on-disk history); `preview.enabled` source-side off-switch `[CITED: PITFALLS.md Pitfall 6]` |
| A preview GET blocking the safety-critical override POST | Denial of Service (of the control plane) | `threaded=True`/Waitress (UXT-02/D-08) so control endpoints stay answerable; polling transport (no held-thread streams) |
| Torn/malicious sidecar read raising into the console | Tampering | `read_preview` safe-default never-raise reader (`channel.py:202`); atomic writes (Phase 7) `[VERIFIED: codebase]` |

## Sources

### Primary (HIGH confidence)
- In-repo code (read 2026-06-13): `src/segugio/ui/app.py` (routes, crash-isolation contract, `0.0.0.0` no-auth T-05-05-* docstring, single-threaded `app.run`), `ui/templates/console.html` (the page to extend, existing cam ids + poll loop), `opcomm/channel.py` (`read_preview` safe-default reader), `opcomm/records.py` (`PreviewDoc` gen/tick/cams), `opcomm/atomic.py` (`atomic_write_bytes`), `orchestrator/preview.py` (the `cam_{id}.jpg` filename + gen token + fps period), `orchestrator/runtime.py` (`preview_dir`/`preview.json` paths), `config/models.py` (`PreviewParams`, `Config` model_validator pattern), `config/loader.py` (fail-fast `SystemExit(2)`), `tests/conftest.py` (`file_channel`), `tests/test_ui_run.py` (Flask test_client pattern), `tests/test_imports.py` (crash-isolation guard) — **HIGH**
- `.planning/research/v1.1/STACK.md` — serving decision (`send_file`, `Image()` swap, CSS Grid, polling-over-MJPEG, Waitress optional extra) — **HIGH**
- `.planning/research/v1.1/ARCHITECTURE.md` — data-flow + build-order steps 5–6 + crash-isolation-by-construction invariant + bitrate estimate (~0.3–0.8 MB/s) — **HIGH**
- `.planning/research/v1.1/PITFALLS.md` — Pitfall 1 (bandwidth cap ≤5–8 Mbps) + Pitfall 7 (`threaded=True`) + Pitfall 4 (freshness) + Pitfall 6 (0.0.0.0 video exposure) — **HIGH**
- `.planning/phases/08-.../08-CONTEXT.md` — locked D-01…D-09 — **HIGH**
- `.planning/REQUIREMENTS.md` (MVW/UXT, MJPEG explicitly out of scope) + `.planning/ROADMAP.md` (Phase 8 goal + 5 success criteria) — **HIGH**

### Secondary (MEDIUM confidence)
- STACK.md / PITFALLS.md external citations (Flask/Waitress docs, CSS-Grid 2026 consensus, NDI HX3 bandwidth, miguelgrinberg MJPEG threading) — already verified in the milestone docs against official sources; carried forward — **MEDIUM/HIGH**

### Tertiary (LOW confidence)
- The exact 8 Mbps ceiling value + bpp constant (A1) — calibration choice, surfaced as a tunable config field, gated by the default-passes/cranked-fails test — **LOW** (tunable, not authoritative)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every primitive already in-repo and tested; serving idioms verified in milestone STACK.md against official docs.
- Architecture: HIGH — Phase 8 is the milestone ARCHITECTURE.md's explicit build-order steps 5–6; all seams read directly.
- Pitfalls: HIGH — grounded in actual code (`app.py:143` single-thread, `preview.py:283` filename) + milestone PITFALLS.md.
- Bandwidth ceiling value: LOW — a tunable calibration anchored on the Phase-7 measurement; not an authoritative figure.

**Research date:** 2026-06-13
**Valid until:** 2026-07-13 (stable — in-repo seams + locked decisions; no fast-moving external deps)
