# Phase 14: Fallback Coexistence & Degrade Hardening - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 9 (4 NEW tests, 1 NEW doc, 1 JS edit, 1 template ref, 3 config/docs edits)
**Analogs found:** 9 / 9 (every file has a near-verbatim in-repo analog)

This is a **validation + hardening** phase. Nearly every file copies an existing harness/pattern; the planner should treat the analogs as templates, not inspiration. No new dependency, no director change, crash-isolation (RBT-07) preserved on every `segugio.ui` edit.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/test_overlay_degrade_gate.py` (NEW) | test (node fake-DOM) | event-driven (clock/poll sim) | `tests/test_ui_overlay_render.py::test_live_idle_run_not_stale_but_console_down_is_stale` | exact (copy harness) |
| `tests/test_overlay_fallback_gate.py` (NEW) | test (Flask test_client) | file-I/O | `tests/test_ui_overlay_render.py::_read_served_js` + `conftest.file_channel` | role-match |
| `tests/test_overlay_poll_storm.py` (NEW) | test (live threaded server) | request-response (concurrency) | `tests/test_preview_concurrency.py` | exact (copy fixture+helpers) |
| `tests/test_overlay_html_sink_gate.py` (NEW) | test (JS src + Flask render) | transform/regression | `tests/test_ui_overlay_render.py::test_no_innerhtml_sink` | exact (extend) |
| `src/segugio/ui/static/overlay-render.js` (EDIT) | component (client renderer) | event-driven (watchdog) | self — extends `isStale()`/`poll()` in place | self-pattern |
| `src/segugio/ui/templates/overlay.html` (READ-ONLY ref) | template | — | self — `.is-exiting`/`.is-stale` hooks already present | self-pattern |
| `docs/HUMAN-UAT.md` (NEW) | doc | — | (no prior in repo; Phase 5/7 field-UAT disposition) | no analog (doc) |
| `docs/obs-setup.md` (EDIT) | doc | — | self — lines 103-135 coexistence section | self-pattern |
| `config.example.yaml` (EDIT) | config | — | `config.agility.example.yaml` + `obs/segugio-scene-collection.json` | exact (align string) |

## Pattern Assignments

### `tests/test_overlay_degrade_gate.py` (NEW — SC#1 two-stage stale→dead, SC#2 gen re-anchor)

**Analog:** `tests/test_ui_overlay_render.py` — copy the entire `_run_node` helper + the fake-DOM harness from `test_live_idle_run_not_stale_but_console_down_is_stale` (lines 305-454).

**Node helper to copy verbatim** (`tests/test_ui_overlay_render.py:462-478`) — UTF-8 decode is load-bearing on Windows:
```python
def _run_node(driver_src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver_src); path = fh.name
    try:
        proc = subprocess.run([_NODE, path], capture_output=True, timeout=30)
        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert proc.returncode == 0, f"node failed: {stderr}"
        return proc.stdout.decode("utf-8")
    finally:
        os.unlink(path)
```

**Skip gate + JS-path constants to copy** (`tests/test_ui_overlay_render.py:39-64`):
```python
_JS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "src", "segugio", "ui", "static", "overlay-render.js")
_NODE = shutil.which("node")
_requires_node = pytest.mark.skipif(_NODE is None, reason="node not available for behavior test")
```

**Fake-DOM harness to copy + EXTEND** (`tests/test_ui_overlay_render.py:321-444`): the `makeEl()`/`makeClassList()` fake DOM, `global.Date.now = () => NOW`, the stubbable `global.fetch` with a STATIC gen, the captured `intervalCb`/`rafCb`, and the `drain()` microtask pump.
- **SC#1 extension:** after the existing "console down → isStale True" block, advance `NOW += DEAD_MS` further and assert the NEW `isDead()` is True, the lower-third lost `is-live`/gained the exit/hidden state, and `rafId === null`. KEEP the existing "live idle run is NOT dead" assertion (mirror the `liveIsStale === False` shape) — this is the Pitfall-1 regression guard.
- **SC#2 extension:** drive `running → fetchMode="down" (reject) → fetchMode="ok"` with the SAME `started_at` and a BUMPED `gen`; assert `currentElapsed()` is continuous with true wall-clock elapsed, NOT a jump equal to the outage. The fetch stub already returns `started_at: NOW/1000 - 5` — vary `gen` across the resume to exercise the `p.gen > lastGen` re-render gate.

**Critical:** key `isDead()` on `everResponded && Date.now() - lastResponseAt > DEAD_MS` (response-recency), NEVER gen-age — see Anti-Pattern below.

---

### `tests/test_overlay_fallback_gate.py` (NEW — SC#1 `overlay.txt` on-disk persistence)

**Analog:** Flask `test_client` write path + `conftest.file_channel` fixture.

**App build pattern** (`tests/test_ui_overlay_render.py:51-54`):
```python
app = create_app(tmp, cam_ids=["cam_wide"])
client = app.test_client()
```

**Channel paths fixture** (`tests/conftest.py:422-445`) — `file_channel` already exposes the `overlay` key:
```python
return {"dir": d, "score": d / "score.json", ..., "overlay": d / "overlay.txt",
        "overlay_run": d / "overlay_run.json"}
```

**The single-writer proof to assert:** `POST /score` (form-encoded `discipline` + fields) → the route writes `overlay.txt` via `atomic_write_text` (the SOLE writer, `src/segugio/ui/app.py:209-210`):
```python
write_score(_path(_SCORE_FILE), doc)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # last score persists on disk
```
Assert pattern: POST a score → read `<dir>/overlay.txt`, assert it holds the rendered line → simulate "death" (stop touching the app / no further write) → re-read the file → assert the LAST score is STILL on disk (no second writer cleared it). Use `client.post("/score", data={...})` and assert `204`.

---

### `tests/test_overlay_poll_storm.py` (NEW — SC#3 `/overlay-json` storm vs `POST /command` < 1.0s)

**Analog:** `tests/test_preview_concurrency.py` — copy the `live_server` fixture + `_get`/`_post_command` helpers DIRECTLY; retarget the GET to `/overlay-json`.

**Live threaded server fixture to copy** (`tests/test_preview_concurrency.py:27-41`) — MANDATORY real server, NOT `test_client` (Pitfall 2):
```python
@pytest.fixture
def live_server(preview_channel):
    from segugio.ui.app import create_app
    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    server = make_server("127.0.0.1", 0, app, threaded=True)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", preview_channel
    finally:
        server.shutdown(); thread.join(timeout=5)
```

**Helpers to copy** (`tests/test_preview_concurrency.py:44-60`): `_get(base, path)` and `_post_command(base, force_cam)` (urllib + `time.perf_counter()`).

**Test body to copy + retarget** (`tests/test_preview_concurrency.py:63-81`): keep the `ThreadPoolExecutor(max_workers=n+1)`, the `< 1.0` bar, and the `read_command(...).force_cam == "cam_long"` write check — only replace the N concurrent `"/preview/cam_wide.jpg"` GETs with N concurrent `"/overlay-json"` GETs:
```python
get_futures = [pool.submit(_get, base, "/overlay-json") for _ in range(n)]
code, elapsed = pool.submit(_post_command, base, "cam_long").result(timeout=10)
assert code == 204
assert elapsed < 1.0, f"override POST took {elapsed:.3f}s — starved by /overlay-json (UXT-02/SC#3)"
```

---

### `tests/test_overlay_html_sink_gate.py` (NEW — SC#4 `textContent` sink + Jinja autoescape)

**Analog:** `tests/test_ui_overlay_render.py::test_no_innerhtml_sink` (lines 93-101) for the JS half:
```python
js = _read_file_js()
assert "textContent" in js
for variant in ("innerHTML =", "innerHTML=", "innerHTML  ="):
    assert variant not in js, f"forbidden HTML-injection sink found: {variant!r}"
assert ".innerHTML" not in js
```

**Jinja autoescape half (NEW assertion, same test_client render style):** render `GET /overlay?...` with a crafted `event_name="<script>x</script>"` and assert the served HTML contains the ESCAPED `&lt;script&gt;`, proving autoescape is on at the `#identity[data-event]` + identity text + `<img src>` sinks. The template sinks are read-only references (`src/segugio/ui/templates/overlay.html:244` identity, `:255` logo):
```html
<div id="identity" data-event="{{ event_name | default('', true) }}">{{ event_name | default('', true) }}</div>
<img id="logo-bug" src="{{ logo_path }}" alt="">
```
Note: `event_name`/`logo_path` are injected at `create_app` time — confirm how the analog passes branding into `create_app` (cam_ids signature in `tests/test_ui_overlay_render.py:53`) and extend that call to thread the crafted branding.

---

### `src/segugio/ui/static/overlay-render.js` (EDIT — add `DEAD_MS` + `isDead()` + hide-on-dead)

**Self-pattern — extend the EXISTING watchdog in place.** Three precise hook points (all verified):

**Hook 1 — add the constant** next to `STALE_MS` (after line 230):
```javascript
const PUBLISH_MS = 200;            // ~5 fps publish cadence
const STALE_MS = PUBLISH_MS * 3;   // dim+grayscale threshold (~600ms) — KEEP
// ADD (D-05):
// const DEAD_MS = 3000;           // full-hide threshold (~3s) — exits the lower-third
```

**Hook 2 — add `isDead()`** mirroring `isStale()` (after line 297), response-recency keyed:
```javascript
function isStale() {
  return everResponded && Date.now() - lastResponseAt > STALE_MS;
}
// ADD: function isDead() { return everResponded && Date.now() - lastResponseAt > DEAD_MS; }
```

**Hook 3 — drive the hide reusing the EXISTING exit animation.** Two existing degrade sites to extend (do NOT invent a new animation primitive):
- `poll()` post-catch degrade (`overlay-render.js:426-429`):
  ```javascript
  if (isStale()) { stopTimer(); applyStale(true); }
  // EXTEND: if (isDead()) { /* remove is-live/is-stale, retrigger("is-exiting") → plate slides out + stays hidden */ }
  ```
- `tick()` stop-condition (`overlay-render.js:334-338`) already calls `applyStale(isStale())` on the stale/stopped path — the dead-hide can hook the same edge.

The exit primitive ALREADY exists in `overlay.html`: `@keyframes exit` (lines 181-184) + `.lower-third.is-exiting { animation: exit 260ms ease-in forwards; }` (line 196). The dead state removes `is-live`/`is-stale` and adds `is-exiting` so the plate slides out to `opacity:0` and stays hidden — no new keyframe.

---

### `src/segugio/ui/templates/overlay.html` (READ-ONLY reference)

No edit expected — the JS hide reuses hooks already present:
- `.lower-third.is-exiting` + `@keyframes exit` (lines 181-184, 196) — the hide animation.
- `.lower-third.is-stale { opacity: 0.55; filter: grayscale(0.4); }` (line 201) — the SHORT-stale dim (D-04 stage 1).
- SC#4 sinks `event_name` (line 244), `logo_path` (line 255) — autoescape regression references only.

---

### `docs/obs-setup.md` (EDIT — D-06 simplified reveal, D-08 NDI-name note)

**Self-pattern — edit the coexistence section (lines 103-135).** D-06: in lines 109-112, DROP the now-redundant "(and, for a clean swap, toggles `Score Overlay` **hidden**)" instruction — the browser overlay auto-hides on death (`DEAD_MS`). Replace with: the operator's ONE manual step is revealing `Score Text`; the browser overlay auto-hides via `DEAD_MS`. Keep the `visible: false`-while-alive note (line 107). D-08: add an NDI-source-name note (~lines 42-44, 103-135) that the operator must byte-match the phone's published NDI name; cite the canonical example `"PHONE-WIDE (NDI HX3)"`.

---

### `config.example.yaml` (EDIT — D-08 align `cam_wide` `ndi_source`)

**Analog (canonical sources to match):** `obs/segugio-scene-collection.json:126` (`"ndi_source_name": "PHONE-WIDE (NDI HX3)"`) and `config.agility.example.yaml:24`.

Line 27 currently drifts:
```yaml
ndi_source: "LOCALHOST (iPhone Camera for OBS Studio App)"   # ← DRIFT
```
Align to the scene-JSON canonical name:
```yaml
ndi_source: "PHONE-WIDE (NDI HX3)"
```
This is the "OBS sees it but console blank" gotcha. Direction confirmed by RESEARCH A2 (the scene JSON + agility config are the canonical pair; the example config is the outlier).

---

### `docs/HUMAN-UAT.md` (NEW — on-rig physical-scenario checklist)

**No code analog** (doc artifact, disposition = Phase 5/7 deferred field UAT per D-02). Author a checklist covering the genuinely physical scenarios: real OBS browser-source blanking/auto-hide, real LAN-cable drop + console restart re-anchor, real `overlay.txt` airing the last score via OBS "read from file", and the simplified D-06 manual reveal walkthrough. Does NOT block phase completion (D-02).

## Shared Patterns

### Crash-isolation gate (RBT-07) — the invariant EVERY `segugio.ui` edit must preserve
**Source:** `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` (lines 87-137)
**Apply to:** the `overlay-render.js` edit and ALL new tests (run `test_imports.py` per task commit).
```python
CONSOLE_HEAVY_MODULES = HEAVY_MODULES + ["numpy", "cv2"]   # torch/ultralytics/cyndilib/obsws_python + numpy/cv2
for name in CONSOLE_HEAVY_MODULES:
    monkeypatch.setitem(sys.modules, name, None)
import segugio.ui
from segugio.ui.app import create_app
app = create_app(tmp, cam_ids=["cam_wide"])
resp = app.test_client().get("/overlay-json"); assert resp.status_code == 200
```
**Rule:** do NOT propose any heavy-dependency import into `segugio.ui`. The console imports only Flask (inside `create_app`) + `segugio.opcomm`. This test is already green and MUST stay green — it is re-asserted as an SC#4 sub-criterion.

### Node fake-DOM execution (the locked sandbox-repro method)
**Source:** `tests/test_ui_overlay_render.py` `_run_node` + fake-DOM harness
**Apply to:** `test_overlay_degrade_gate.py` (SC#1/SC#2) and the JS half of `test_overlay_html_sink_gate.py` (SC#4).
Project memory `overlay-bugs-sandbox-repro`: reproduce `/overlay` behavior in an alt-port sandbox + node fake-DOM; NEVER POST to the live `:8080` console.

### Real threaded-server concurrency proof (UXT-02)
**Source:** `tests/test_preview_concurrency.py` `live_server` fixture
**Apply to:** `test_overlay_poll_storm.py` (SC#3).
`make_server("127.0.0.1", 0, app, threaded=True)` on a daemon thread is MANDATORY — `test_client` does not exercise WSGI threading and yields a false green.

### Atomic single-writer `overlay.txt`
**Source:** `src/segugio/ui/app.py:209-210` (the SOLE writer)
**Apply to:** `test_overlay_fallback_gate.py` (SC#1). Do NOT add a second writer — the single-writer property is load-bearing (a dead console leaves the last score on disk). `runtime.py` declares the path for bundle completeness only; `loop.py` never writes it; `set_overlay_text` has zero callers.

## Anti-Patterns (regression-source — assert AGAINST these)

- **`DEAD_MS` keyed on gen-age** instead of response-recency → re-introduces the 260615-tsi bug (a flat-gen idle-but-live run false-hides). `isDead()` MUST be `everResponded && Date.now() - lastResponseAt > DEAD_MS`. The freshness test asserts `"lastGenAt" not in js` — do NOT reintroduce it.
- **A new animation primitive for the hide** → reuse `.is-exiting` / `@keyframes exit` (overlay.html 181-184, 196).
- **Poll-storm test via `test_client`** → false green; use the real `make_server(threaded=True)` harness.
- **A second `overlay.txt` writer** → would clear the last score on console death and break the SC#1 coexistence proof.

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `docs/HUMAN-UAT.md` | doc | No prior on-rig UAT checklist in repo; follows the Phase 5/7 deferred-field-UAT disposition (D-02). Author from the four success criteria. |

## Metadata

**Analog search scope:** `tests/`, `src/segugio/ui/`, `obs/`, `docs/`, `config.example.yaml`, `config.agility.example.yaml`
**Files scanned:** `test_ui_overlay_render.py`, `test_preview_concurrency.py`, `test_imports.py`, `conftest.py`, `overlay-render.js`, `overlay.html`, `app.py`, `config.example.yaml`, `segugio-scene-collection.json`, `obs-setup.md`
**Pattern extraction date:** 2026-06-20
```
