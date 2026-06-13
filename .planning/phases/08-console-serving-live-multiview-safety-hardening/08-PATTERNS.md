# Phase 8: Console Serving, Live Multiview & Safety Hardening - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 7 (3 modify, 3 create tests, 1 create doc — plus `tests/conftest.py` fixture extension and `pyproject.toml` optional-extra)
**Analogs found:** 7 / 7 (all seams already exist in-repo — Phase 8 is a wiring phase)

This phase builds almost no new mechanism: every primitive (atomic write, safe-default `read_preview`, fail-fast `@model_validator`, the status poll, the Flask factory, the test_client harness) already ships and is tested. The work is **two routes + a template section + an entrypoint flag + a validator + a docs file + three tests**. Resist inventing transport (MJPEG/WebSocket) or a runtime throttle — the milestone research rejected both.

---

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `src/segugio/ui/app.py` | MODIFY | route / Flask controller | request-response + file-I/O (`send_file`) | the EXISTING `GET /status` route + `create_app` factory + `_path` helper (same file) | exact (same file, same factory) |
| `src/segugio/ui/templates/console.html` | MODIFY | view / template | client-side polling (request-response) | the existing inline-CSS/JS page + `#stato`/`#feeds` `pollStatus` loop (same file) | exact (same file) |
| `src/segugio/config/models.py` | MODIFY | config / model | transform (validation) | the existing `Config._zones_are_weighted` `@model_validator` + `PreviewParams` sub-model (same file) | exact (same file, same pattern) |
| `tests/test_preview_serving.py` | CREATE | test | request-response (test_client) | `tests/test_ui_run.py` (Flask `test_client` + `file_channel`) | exact-shape |
| `tests/test_preview_concurrency.py` | CREATE | test | concurrency / event-driven | `tests/test_ui_run.py` POST shape + a real ephemeral-port server (new shape) | role-match (new test shape) |
| `tests/test_preview_bitrate_cap.py` | CREATE | test | transform (config-validation) | config validator tests + `valid_config_dict` fixture | role-match |
| `tests/conftest.py` (`preview_channel` fixture) | MODIFY | test fixture | file-I/O | the `file_channel` fixture (`conftest.py:422`) | exact (extend) |
| `docs/security.md` | CREATE | docs | n/a | `docs/obs-setup.md`, `docs/run.md` (existing docs layout) + T-05-05-* docstrings in `app.py` | partial (new file, content cross-refs docstrings) |
| `pyproject.toml` (`[project.optional-dependencies].console`) | MODIFY | config / packaging | n/a | existing optional-deps block | n/a |

---

## Pattern Assignments

### `src/segugio/ui/app.py` (route, request-response + file-I/O) — MODIFY

**Analog:** the same file — the existing `GET /status` route, the `create_app` factory, the `_path(name)` helper, and the `__main__` entrypoint.

**CRITICAL crash-isolation contract (D-03 / RBT-04):** the console imports ONLY `flask` + `segugio.opcomm` (+ `score_render`, a light leaf). Flask is imported INSIDE `create_app` (NOT at module top) so `import segugio.ui` stays Flask-free. Do NOT add `cv2`/`numpy`/`torch`/`segugio.config`. The cam-id whitelist must be PASSED IN (constructor arg), not obtained by importing config. Gated by `tests/test_imports.py` (`segugio.ui` in `PHASE1_SURFACE`, heavy stack forced absent).

**Module-top import block to extend** (lines 30-44) — opcomm-only, add `read_preview`:
```python
from ..opcomm.channel import (
    read_status,
    read_preview,       # ADD — the new GET /preview route is a thin wrapper
    write_command,
    write_runstate,
    write_score,
)
```

**Constant-filename pattern to mirror** (lines 48-54) — add the preview sub-dir constant:
```python
_STATUS_FILE = "status.json"
# ADD:
_PREVIEW_SUBDIR = "preview"          # <channel_dir>/preview/ — where Phase 7 writes (runtime.py:83)
_PREVIEW_FILE = "preview/preview.json"
```

**Factory signature change** (line 60) — add the whitelist as a plain arg (Assumption A2, Pitfall 5):
```python
def create_app(channel_dir: str, cam_ids=()):   # cam_ids: a plain list/set of configured camera ids
```
> Default `cam_ids=()` keeps existing `create_app(dir)` callers (e.g. `test_ui_run.py:19`) working — but the preview-JPEG route 404s every cam until ids are passed. The entrypoint resolves real ids from config/env.

**The `_path` helper to reuse** (lines 71-72) — already joins under `channel_dir`; preview files live under the `preview/` subdir, so `_path("preview/cam_cam_wide.jpg")` resolves correctly:
```python
def _path(name: str) -> str:
    return os.path.join(channel_dir, name)
```

**Existing `GET /status` route — the template to copy** (lines 128-135):
```python
@app.get("/status")
def get_status():
    status = read_status(_path(_STATUS_FILE))   # safe-default reader, never raises (RBT-04)
    return jsonify(
        {"live_cam": status.live_cam, "reason": status.reason, "alive": status.alive}
    )
```

**NEW routes to add (Pattern 1 — whitelist is the path-traversal mitigation, T-05-05-01):**
```python
from flask import send_file, abort   # add to the in-factory import (line 67)

@app.get("/preview/<cam>.jpg")
def get_preview_jpg(cam: str):
    if cam not in cam_ids:                       # whitelist — unknown id → 404, never a raw path
        abort(404)
    # LOAD-BEARING: the publisher writes cam_{cam_id}.jpg (preview.py:283) →
    # for id "cam_wide" the file is literally cam_cam_wide.jpg. Build from a FIXED prefix.
    path = _path(os.path.join(_PREVIEW_SUBDIR, f"cam_{cam}.jpg"))
    if not os.path.exists(path):                 # publisher not yet written → 404 (browser placeholder)
        abort(404)
    resp = send_file(path, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store"   # belt-and-suspenders with the JS ?t=<gen> cache-bust
    return resp

@app.get("/preview")
def get_preview():
    doc = read_preview(_path(_PREVIEW_FILE))     # safe-default reader (channel.py:202), never raises
    return jsonify({"gen": doc.gen, "tick": doc.tick,
                    "auto_candidate": doc.auto_candidate, "cams": doc.cams})
```

**Entrypoint fix (Pattern 4 — UXT-02 / D-08), replacing lines 140-143:**
```python
if __name__ == "__main__":  # pragma: no cover
    _dir = os.environ.get("SEGUGIO_OPCOMM_DIR", os.path.join(os.getcwd(), "opcomm"))
    cam_ids = ...   # resolve from config or SEGUGIO_* env — keep config import OUT of module top
    app = create_app(_dir, cam_ids=cam_ids)
    try:
        from waitress import serve            # OPTIONAL extra — import kept INSIDE the entrypoint
        serve(app, host="0.0.0.0", port=8080)
    except ImportError:
        app.run(host="0.0.0.0", port=8080, threaded=True)   # threaded=True is the MINIMUM safety control
```
> `threaded=True` is the HARD requirement; Waitress is optional. Keeping the `app.run(..., threaded=True)` fallback means the import guard still passes with `waitress` absent. The `waitress` import MUST stay inside the entrypoint to preserve the lazy boundary.

**Docstring (lines 17-27) is the basis for `docs/security.md` (D-09):** the `0.0.0.0` / LAN-trust-boundary / T-05-05-01..04 notes already live here — the threat re-eval cross-references them.

---

### `src/segugio/ui/templates/console.html` (view, client-side polling) — MODIFY

**Analog:** the same file — the existing `<style>` block, the override `.force-btn` cam ids (lines 85-88), and the `pollStatus` loop (lines 133-150).

**D-06 composition:** the multiview grid goes ON TOP (first viewport); the existing score/run/override/status fieldsets scroll BELOW. Extend the one inline-CSS/JS page — NO framework, NO bundler, NO new dep.

**Cam ids already hardcoded in the override buttons** (lines 85-88) — the same id set the grid iterates and the route whitelists:
```html
<button type="button" class="force-btn" data-cam="cam_wide">Forza CAM Wide</button>
<button type="button" class="force-btn" data-cam="cam_long">Forza CAM Long</button>
<button type="button" class="force-btn" data-cam="cam_low">Forza CAM Low</button>
<button type="button" class="force-btn" data-cam="cam_handler">Forza CAM Handler</button>
```
> These `cam_<role>` ids match the Phase-5 config and map to on-disk `cam_cam_wide.jpg` etc. (Pitfall 3).

**CSS-Grid section to add to the `<style>` block** (Pattern, MVW-01 — `repeat(auto-fit, minmax())` reflows 1→2→4 cols):
```css
.multiview { display: grid; gap: 0.5rem; margin: 0 0 1rem;
             grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.tile { position: relative; border: 3px solid #333; border-radius: 8px; overflow: hidden; }
.tile img { width: 100%; display: block; background: #000; }
.tile.live { border-color: #b23b3b; }                 /* MVW-02 red border */
.tile.dead { opacity: 0.5; }                          /* MVW-03 */
.badge { position: absolute; top: 4px; left: 4px; padding: 0.1rem 0.4rem;
         border-radius: 4px; font-size: 0.8rem; }
.badge.live { background: #b23b3b; color: #fff; }     /* LIVE badge */
.badge.dead { background: #444; color: #e35d5d; }     /* MORTO badge */
.onair { font-weight: 700; margin: 0 0 0.5rem; }      /* "ON AIR: CAM X" banner */
```

**The existing `pollStatus` loop — the cadence/error-coast pattern to mirror** (lines 133-150). Note the `try/catch` "a poll error never breaks the page" — replicate it for the `/preview` poll:
```javascript
async function pollStatus() {
  try {
    const r = await fetch("/status");
    const s = await r.json();
    document.getElementById("live-cam").textContent = s.live_cam;
    // ...iterates s.alive {cam: bool} into .pill spans...
  } catch (e) { /* coast — a poll error never breaks the page */ }
}
pollStatus(); setInterval(pollStatus, 1000);
```

**NEW preview poll + flicker-free swap (Pattern 2 — MVW-01/02/03):**
```javascript
const CAMS = ["cam_wide","cam_long","cam_low","cam_handler"];   // from the same id set as the buttons
let lastGen = -1, lastGenAt = 0;
const PUBLISH_MS = 200;                 // ~5 fps; staleness window = ~2-3x (D-05) → ~600ms
const STALE_MS = PUBLISH_MS * 3;

function refreshTile(cam, gen) {        // flicker-free: preload off-DOM, swap on onload
  const img = new Image();
  img.onload = () => { document.getElementById("tile-" + cam).src = img.src; };
  img.src = `/preview/${cam}.jpg?t=${gen}`;   // ?t=<gen> only changes on a genuine new frame
}

async function pollPreview() {
  try {
    const r = await fetch("/preview");
    const p = await r.json();
    if (p.gen !== lastGen) { lastGen = p.gen; lastGenAt = Date.now();
                             CAMS.forEach(c => refreshTile(c, p.gen)); }   // refresh only on new frame
  } catch (e) { /* coast */ }
}
setInterval(pollPreview, PUBLISH_MS);

// LIVE/MORTO marking driven by /status (live_cam + alive) and gen-freshness (D-04 belt-and-suspenders)
function markTiles(status) {
  const stale = (Date.now() - lastGenAt) > STALE_MS;   // gen not advancing → whole-channel stale
  CAMS.forEach(cam => {
    const tile = document.getElementById("tile-" + cam);
    const dead = (status.alive && status.alive[cam] === false) || stale;   // D-04: alive==false OR stale
    tile.classList.toggle("live", cam === status.live_cam && !dead);       // D-03 red border + badge
    tile.classList.toggle("dead", dead);                                   // D-03 MORTO
  });
}
```
> Freshness uses the in-sidecar `gen` (Open Q #3): `gen` is a single global token (one `preview.json`), so the freshness gate is whole-channel; combined with per-cam `status.alive[cam]` it satisfies D-04 for Phase 8. Per-cam freshness is a Phase-9 refinement. Cache-bust uses `gen` not `Date.now()` (Open Q #2) — the URL only changes on a real new frame, saving bytes on contended WiFi.

**Do NOT render** Phase-9 payload: the `/preview` `cams` carry score/box/track_id/energy, but Phase 8 draws ONLY the tile set + LIVE/MORTO. No score bars, no bbox, no reason text (anti-pattern, RESEARCH).

---

### `src/segugio/config/models.py` (config model, transform/validation) — MODIFY

**Analog:** the same file — the `PreviewParams` sub-model (lines 146-164) and the `Config._zones_are_weighted` `@model_validator(mode="after")` (lines 181-201). Same fail-fast posture (CFG-01): a bad value raises `ValueError` → aggregated `ValidationError` → loader `SystemExit(2)`.

**`PreviewParams` to extend** (lines 160-164) — add the ceiling field, mirroring the bounded-`Field` style:
```python
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    fps: Annotated[float, Field(gt=0.0, le=30.0)] = 5.0
    max_width: Annotated[int, Field(ge=64, le=1920)] = 384
    jpeg_quality: Annotated[int, Field(ge=1, le=100)] = 55
    # ADD (D-01): the hard preview-bandwidth ceiling, surfaced as a tunable config field.
    max_total_mbps: Annotated[float, Field(gt=0.0)] = 8.0   # ≤5-8 Mbps band (PITFALLS.md Pitfall 1)
```

**The validator pattern to copy** — `_zones_are_weighted` (lines 181-201) is the EXACT shape: `@model_validator(mode="after")`, iterate, `raise ValueError(descriptive msg)`, `return self`. Add a sibling `Config`-level validator (Pattern 3):
```python
    @model_validator(mode="after")
    def _preview_bitrate_within_cap(self) -> "Config":
        """D-01 fail-fast: reject any config whose computed preview bitrate exceeds the cap."""
        p = self.preview
        if not p.enabled:
            return self
        n = len(self.cameras)
        # est_bytes_per_frame ~ width*height*bpp(quality); h = width*9/16 (16:9 thumb).
        # Calibrate the bpp constant so the Phase-7 defaults (5fps/384px/q55/4cams) land in the
        # measured 0.3-0.8 MB/s (~2.4-6.4 Mbps) band [07-CONTEXT D-05 / ARCHITECTURE.md L219].
        est_bytes = _estimate_jpeg_bytes(p.max_width, p.jpeg_quality)
        total_mbps = est_bytes * 8 * p.fps * n / 1_000_000
        if total_mbps > p.max_total_mbps:
            raise ValueError(
                f"preview computed bitrate {total_mbps:.1f} Mbps exceeds cap "
                f"{p.max_total_mbps} Mbps (fps={p.fps}, width={p.max_width}, "
                f"q={p.jpeg_quality}, cams={n}); lower fps/width/quality or raise the cap")
        return self
```
> Both example YAMLs may need the new key only if the planner wants it explicit; it defaults in (additive sub-model, `extra="forbid"` tolerates absence). Add `_estimate_jpeg_bytes` as a module-level helper with a documented bpp constant (the LOW-confidence calibration point, A1 — tunable, gated by the default-passes/cranked-fails test).

---

### `tests/test_preview_serving.py` (test, request-response) — CREATE

**Analog:** `tests/test_ui_run.py` — copy the `client` fixture shape exactly (Flask `test_client` + `file_channel`), but pass `cam_ids`:
```python
@pytest.fixture
def client(preview_channel):
    from segugio.ui.app import create_app
    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide","cam_long"])
    app.config.update(TESTING=True)
    return app.test_client(), preview_channel
```
Mirror the assertion style of `test_status_poll_returns_director_status` (lines 87-99) and `test_command_contradictory_rejected` (404/non-write checks). Cover (RESEARCH test map):
- **serve:** `GET /preview/cam_wide.jpg` → 200, `image/jpeg`, bytes match the file written at `preview/cam_cam_wide.jpg` (Pitfall 3 — assert the exact `cam_{id}.jpg` mapping).
- **whitelist:** unknown id (`/preview/cam_bogus.jpg`) → 404; path-traversal (`/preview/..%2fstatus.jpg` etc.) → 404, never reads outside the preview dir (Pitfall 2).
- **sidecar:** `GET /preview` → `{gen, tick, auto_candidate, cams}` JSON.
- **live_contract:** `/status` exposes `live_cam`; `/preview` `cams` keyed by the same ids (MVW-02 data contract — render is client-side).
- **freshness:** `/preview` `gen` advances on a new `write_preview`, stable when none (MVW-03 signal).

### `tests/test_preview_concurrency.py` (test, concurrency) — CREATE

**Analog:** `test_ui_run.py` POST shape — but the Flask `test_client` does NOT exercise WSGI threading. Run a real `app.run(host="127.0.0.1", port=0, threaded=True)` (or `waitress.serve`) on a background thread bound to an ephemeral port, fire N concurrent `/preview/<cam>.jpg` GETs via `concurrent.futures`, time a `/command` POST, assert it completes well under threshold (e.g. < 1 s) and is written (UXT-02 / D-08, Pitfall 1). This is the one genuinely new test shape.

### `tests/test_preview_bitrate_cap.py` (test, config-validation) — CREATE

**Analog:** existing config-validator tests + the `valid_config_dict` fixture (`conftest.py`, used in `test_imports.py:134`). Build a `Config` from `valid_config_dict`:
- default `PreviewParams` (5/384/q55) × N cams → computed bitrate ≤ ceiling → `Config.model_validate(...)` SUCCEEDS.
- a cranked config (e.g. fps=30 / max_width=1920 / q=100) → `pydantic.ValidationError` (→ `SystemExit(2)` via the loader). Mirror the `pytest.raises(ValidationError)` style used elsewhere.

### `tests/conftest.py` — `preview_channel` fixture (extend) — MODIFY

**Analog:** the `file_channel` fixture (lines 422-439). Extend it: create the `preview/` sub-dir, write a sample `cam_<id>.jpg` (a few bytes — no cv2 needed) and a `preview.json` via `write_preview`:
```python
@pytest.fixture
def preview_channel(file_channel):
    pdir = file_channel["dir"] / "preview"
    pdir.mkdir()
    (pdir / "cam_cam_wide.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpeg")   # cam_{id}.jpg mapping
    from segugio.opcomm.channel import write_preview
    from segugio.opcomm.records import PreviewDoc
    write_preview(str(pdir / "preview.json"), PreviewDoc(tick=1, gen=1, cams={"cam_wide": {}}))
    file_channel["preview_dir"] = pdir
    file_channel["preview"] = pdir / "preview.json"
    return file_channel
```
> Keep imports in-body (the conftest stays heavy-import-free, like `_as_camera_scores`). All Phase-8 tests are headless/CPU-only — no GPU, no cv2, no real network (except the one ephemeral-port concurrency test).

### `tests/test_imports.py` — extend the crash-isolation guard — MODIFY (already exists)

`segugio.ui` is NOT currently in `PHASE1_SURFACE` (lines 20-35) — it is `segugio.opcomm`/`segugio.ndi`/`segugio.obs` that are listed, plus `segugio.__main__`. **Confirm whether `segugio.ui` belongs in the guard** (RESEARCH says it is "already in `PHASE1_SURFACE`" — it is NOT in the read of the current file; the planner must ADD `"segugio.ui"` if the intent is to gate `import segugio.ui` + `create_app` with the heavy stack absent). The `_force_heavy_absent` + delitem-recache machinery (lines 38-62) is reused as-is; the new routes must import clean with `torch`/`cv2`/`numpy`/`cyndilib`/`obsws_python` forced absent (Pitfall 5).

### `docs/security.md` — CREATE (D-09)

**Analog:** layout of existing `docs/obs-setup.md` / `docs/run.md`; content cross-references the T-05-05-* threats documented as docstrings in `src/segugio/ui/app.py` (lines 17-27) and `src/segugio/orchestrator/loop.py`. No standalone `SECURITY.md`/`THREAT_MODEL.md` exists today (confirmed via Glob — only `obs-setup.md`/`run.md`). Content per D-09: reaffirm LAN-as-trust-boundary (T-05-05-04); ADD the new exposure (live competitor video behind `0.0.0.0`); make AP client-isolation + no-internet/guest-bridge a HARD operational requirement; note `preview.enabled` as the source-side off-switch; state explicitly that no auth/configurable-bind/token is added in v1.1.

### `pyproject.toml` — optional extra — MODIFY

Add `[project.optional-dependencies]` `console = ["waitress==3.0.2"]` (or `serve`). NOT a hard console dep — the import stays inside the entrypoint so the import guard passes with `waitress` absent.

---

## Shared Patterns

### Crash-isolation import boundary (D-03 / RBT-04) — applies to `app.py` (and gated for all console code)
**Source:** `src/segugio/ui/app.py:8-11` docstring + `create_app` Flask-inside-factory (line 67); gate `tests/test_imports.py:38-62`.
The console imports ONLY `flask` + `segugio.opcomm` (+ light `score_render` leaf). Flask imported INSIDE the factory. Pass the cam-id whitelist as a plain arg — NEVER `import segugio.config`/`cv2`/`numpy`/`torch` into `app.py`.
```python
def create_app(channel_dir: str, cam_ids=()):
    from flask import Flask, jsonify, render_template, request, send_file, abort  # lazy, in-factory
```

### Safe-default never-raise readers (RBT-04) — applies to both new routes
**Source:** `src/segugio/opcomm/channel.py:202` (`read_preview`) + `:162` (`read_status`).
Both readers absorb absent/torn/malformed files → a default record, never raising into the request. The new `/preview` route is a thin `read_preview` wrapper; no new IO code, no locking (atomic writes guarantee tear-free reads).

### Whitelisted server-side paths (T-05-05-01) — applies to `GET /preview/<cam>.jpg`
**Source:** `src/segugio/ui/app.py:22-24,48-54` (constant filenames; discipline whitelisted to the enum at `:84-89`).
The new route extends this: `<cam>` whitelisted against `cam_ids`, mapped to a FIXED `cam_{id}.jpg` filename — the URL segment is NEVER a raw path. `abort(404)` on unknown id AND on not-yet-written file.

### Fail-fast config validation (CFG-01) — applies to `config/models.py`
**Source:** `src/segugio/config/models.py:181-201` (`_zones_are_weighted` `@model_validator(mode="after")` → `ValueError` → `SystemExit(2)` via loader).
The D-01 over-cap check joins this exact pattern: a sibling `Config` validator that computes the bitrate and raises — an over-budget preview config is a startup error, not a runtime surprise. No runtime throttle (anti-pattern).

### Flask test_client + file_channel harness — applies to all new tests
**Source:** `tests/test_ui_run.py:15-21` (`client` fixture) + `tests/conftest.py:422` (`file_channel`).
Inject a tmp_path opcomm dir; `app.test_client()`; assert response codes (200/204/400/404) and that the expected file was/was not written. The `preview_channel` fixture extends `file_channel` with the `preview/` sub-dir.

---

## On-disk layout the routes serve (verified from code)

```
<channel_dir>/                         # SEGUGIO_OPCOMM_DIR (entrypoint app.py:142; runtime.py base)
├── status.json                        # read_status   ← GET /status  (existing)
└── preview/                           # runtime.py:83 preview_dir = base/"preview"
    ├── preview.json                   # read_preview  ← GET /preview            (NEW)
    └── cam_<id>.jpg   × N             # send_file     ← GET /preview/<cam>.jpg  (NEW)
                                       #   preview.py:283 writes f"cam_{cam_id}.jpg"
                                       #   → for id "cam_wide" the file is cam_cam_wide.jpg
```
`_path("preview/cam_cam_wide.jpg")` and `_path("preview/preview.json")` resolve correctly because `_path` joins under `channel_dir` and the publisher writes under `channel_dir/preview/`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_preview_concurrency.py` (the real-server-on-ephemeral-port half) | test | concurrency | No existing test spins a real `app.run(threaded=True)`/`waitress` server on a background thread; all current UI tests use the in-process `test_client` (no WSGI threading). This is the one genuinely new test shape — build with `threading`/`concurrent.futures` + `port=0`. |
| `docs/security.md` (content) | docs | n/a | No standalone threat-model doc exists; the closest is the T-05-05-* docstrings in `app.py`/`loop.py`. New file; layout follows `docs/obs-setup.md`. |

---

## Metadata

**Analog search scope:** `src/segugio/ui/`, `src/segugio/opcomm/`, `src/segugio/config/`, `src/segugio/orchestrator/`, `tests/`, `docs/`
**Files scanned (read in full or targeted):** `ui/app.py`, `ui/templates/console.html`, `opcomm/channel.py`, `config/models.py` (PreviewParams+Config), `opcomm/records.py` (grep), `orchestrator/preview.py` (grep), `orchestrator/runtime.py` (grep), `tests/test_ui_run.py`, `tests/test_imports.py`, `tests/conftest.py` (file_channel)
**Key facts verified in code:** JPEG name `cam_{cam_id}.jpg` (`preview.py:283`); preview_dir = `base/preview` (`runtime.py:83`); `read_preview` never-raise (`channel.py:202`); `PreviewDoc.gen`/`tick`/`cams` (`records.py:190-193`); `DirectorStatus.live_cam`/`alive` (`records.py:147-149`); `create_app(channel_dir)` single-arg factory + single-threaded `app.run` (`app.py:60,143`); validator pattern (`models.py:181`); NO `docs/security.md` exists.
**Pattern extraction date:** 2026-06-13
