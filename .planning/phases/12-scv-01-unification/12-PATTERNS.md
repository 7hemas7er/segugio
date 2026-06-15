# Phase 12: SCV-01 Unification - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 7 (3 src modify, 1 src preserve-verified, 3 test)
**Analogs found:** 7 / 7 (every touched file has an in-repo precedent — this is a reuse-and-delete phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/ui/app.py` — MODIFY `get_overlay()`, DELETE `post_score_preview()` | route (Flask) | request-response | `get_overlay()` itself (line 310) + `post_score()` (193) | exact (self-precedent) |
| `src/segugio/ui/templates/overlay.html` — ADD preview CSS + body class | template (host page) | request-response (Jinja render) | `overlay.html` existing animation/CSS-var blocks | exact (self-precedent) |
| `src/segugio/ui/templates/console.html` — REPLACE preview div w/ iframe, DELETE mirror | template (console page) | request-response | existing `#overlay-preview`/mirror block (the thing being deleted) | exact (self-precedent) |
| `src/segugio/ui/static/overlay-render.js` | renderer (frozen) | request-response (poll) | — PRESERVE byte-identical (D-04/sod/tsi) | n/a (no edit) |
| `src/segugio/ui/score_render.py` | utility (text render) | transform | — PRESERVE unchanged (D-06) | n/a (no edit) |
| `tests/test_ui_overlay_page.py` — EXTEND structural | test (served-HTML) | request-response | itself (`_serve` precedent) | exact |
| `tests/test_ui_overlay_render.py` — EXTEND value cross-check | test (served-JS/node) | transform | `test_cleanfield_byte_parity_with_python_clean` (line 110) | exact |
| `tests/test_ui_scv_unification.py` (NEW, optional) | test (served-HTML) | request-response | `test_ui_overlay_page.py::_serve` | role-match |
| `tests/test_score_preview.py` | test | — DELETE (route gone, D-05) | n/a | n/a |

## Pattern Assignments

### `src/segugio/ui/app.py` — `get_overlay()` (route, request-response)

**Analog:** the existing `get_overlay()` at lines 310-321 (modify in place). `request` and `make_response` are ALREADY imported in-factory (lines 118-126) — no new import (RBT-07/Pitfall 4).

**Current route to modify** (lines 310-321):
```python
@app.get("/overlay")
def get_overlay():
    resp = make_response(render_template("overlay.html", **overlay_cfg))
    resp.headers["Cache-Control"] = "no-store"
    return resp
```

**Pattern to apply** (Research Pattern 1 — server flag → body class; read `request.args`, thread a boolean):
```python
@app.get("/overlay")
def get_overlay():
    preview = request.args.get("preview") == "1"   # cosmetic flag; closed boolean, no heavy import
    resp = make_response(render_template("overlay.html", preview=preview, **overlay_cfg))
    resp.headers["Cache-Control"] = "no-store"
    return resp
```
Note: `overlay_cfg` is a dict folded over defaults at line 131; `preview` is a NEW separate kwarg, not a member of `overlay_cfg` (keeps static branding and the cosmetic flag distinct, matching the line 115 "STATIC config does NOT enter the poll payload" discipline).

**DELETE pattern:** remove the entire `post_score_preview()` route + decorator + docstring at **lines 216-238** (D-05). Its only caller is `driftCheck()` in console.html (also deleted). The KEEP-adjacent `post_score()` (193-214) and the `_NON_SCORE_KEYS`/empty-drop filter it shares stay untouched.

---

### `src/segugio/ui/templates/overlay.html` (template, request-response)

**Analog:** the template's own existing CSS conventions — animation state classes (lines 194-201), the `vh/vw` lower-third layout (49-59), and the `.is-stale` dim (201).

**Body class threading** (Pattern 1 — current `<body>` is bare at line 204; emit the flag):
```html
<body class="{{ 'preview' if preview else '' }}">
```
The DOM contract (lines 216-230: `#lower-third`, `#identity`, `#timer`, `#cells`, conditional `#logo-bug`) and the `window.OVERLAY_CFG` bootstrap (247-249) MUST stay byte-identical — do NOT add `preview` to the JS bootstrap (Anti-Pattern; Pitfall 3).

**Preview CSS, keyed on `body.preview`** (add to the `<style>` block; without `.preview` the cascade is byte-identical to OBS):
```css
/* neutral backdrop fills the iframe viewport (preview only) */
body.preview { background: #6b6f76 !important; }   /* mid-gray between plate #14161a and white */

/* force-visible plate: override ONLY the run-edge enter/exit, keep .pulse-once + .is-stale logic intact */
body.preview #lower-third { opacity: 1 !important; }
body.preview #lower-third.is-entering,
body.preview #lower-third.is-exiting { animation: none !important; }
```
**Critical:** scope `animation: none` to `.is-entering`/`.is-exiting` (NOT the whole element) so `.pulse-once` (line 197) still fires on a score change (Open Question 1 recommendation). Existing animation hooks the renderer toggles: `.is-entering` (194), `.is-live` (195), `.is-exiting` (196), `.pulse-once` (197), `.is-stale` (201).

The 16:9 framing box does NOT live here — it is in `console.html` around the iframe (Pattern 2). The lower-third already uses `left:4.5vw; bottom:6vh; max-height:18vh; font-size:5.2vh` (lines 51,52,54,117) so an iframe-sized 16:9 box reproduces placement+scale for free; NO `transform:scale`.

---

### `src/segugio/ui/templates/console.html` (template, request-response)

**Analog / target:** the existing preview+mirror region being replaced. Surviving wiring patterns to preserve: the `post()` helper (318-322), the `form-score` submit → `post("/score", ...)` (325-335), `showFields()` + `sel.addEventListener("change", showFields)` (310-316), run buttons (338-339), `CAMS`/`CAM_LABEL` (449-450), the `gsd:why-mirror` block (452+).

**REPLACE** lines 270-274 (the HTML comment + `<label>` + `#overlay-preview` + `#drift-warning`) with the iframe + on-air label (Pattern 4, D-02; copy is Italian to match conventions like "Anteprima overlay"/"Stato live"):
```html
<label>Anteprima overlay — come va in onda <span class="on-air-tag">● ON AIR</span></label>
<div class="overlay-preview-frame">
  <iframe src="/overlay?preview=1" title="Anteprima overlay live"></iframe>
</div>
```

**16:9 box CSS** (replace the deleted `#overlay-preview`/`#drift-warning` CSS at lines 153-159):
```css
.overlay-preview-frame { width: 100%; aspect-ratio: 16 / 9; border: 1px solid #333;
  border-radius: 6px; overflow: hidden; background: #6b6f76; }
.overlay-preview-frame iframe { width: 100%; height: 100%; border: 0; display: block; }
```

**DELETE inventory** (exact, from RESEARCH Safe Deletion Inventory — grep-prove zero leftover refs, Pitfall 1):
- CSS lines 153-159: the `#overlay-preview` + `#drift-warning` rules and the "SCV-01 ... + drift warning" comment.
- HTML lines 270-274: comment + `<label for="overlay-preview">` + `#overlay-preview` + `#drift-warning`.
- JS `gsd:scv01-mirror` block lines 341-391: `SCV_MAX_FIELD_LEN`, `SCV_NONPRINT`, `cleanField`, `scvGet`, `mirrorOverlayText`.
- JS lines 393-446: `scvCurrentFields`, `updateScorePreview`, `scvPreviewTimer`/`scheduleScorePreview`, `setDrift`, `driftCheck`, the `.campi input` forEach (438-441), `sel.addEventListener("change", updateScorePreview)` (443), the `updateScorePreview()` seed (445), and `form-score` submit→`driftCheck` (446).
- **DO NOT delete** `sel.addEventListener("change", showFields)` (315 — different second listener), the `form-score` submit→`post("/score",...)` (325-335), or anything in KEEP list above.

---

### `src/segugio/ui/static/overlay-render.js` (renderer — FROZEN, no edit)

**Constraint:** byte-identical. The two live fixes MUST survive verbatim:
- `quick-260615-sod` — per-request poll nonce `?t=" + (++reqSeq)` (line ~411; asserted by `test_poll_nonce_and_gen_gate_present`).
- `quick-260615-tsi` — response-recency watchdog `everResponded && (Date.now() - lastResponseAt) > STALE_MS`, `STALE_MS = PUBLISH_MS * 3`, `PUBLISH_MS = 200` (asserted by `test_freshness_watchdog_present`).

D-04 force-visible is achieved in CSS (overlay.html), NOT here. Resting timer values come from the frozen renderer: `formatCountdown` → `1:00` (T&F), freestyle `freestyleDurationS` (e.g. `2:00`), `formatAgility(0)` → `0.00` (do NOT add a preview placeholder — that is a content fork). Export surface for the value cross-check: `module.exports = api` (line 479) exposing `cleanField`, `scvGet`, `DISCIPLINE_CELLS` (76-86, 476).

---

### `tests/test_ui_overlay_page.py` — EXTEND (test, served-HTML)

**Analog:** its own `_serve(overlay_cfg)` helper (lines 39-44) returning `(html, resp)` from `create_app(tmp, cam_ids=[...], overlay_cfg=...).test_client().get("/overlay")`. The no-store assertion (47-52) is the precedent.

**Add** (D-07 structural — query both URLs via the test client):
```python
def _serve_preview():
    tmp = tempfile.mkdtemp()
    app = create_app(tmp, cam_ids=["cam_wide"], overlay_cfg=_CFG)
    resp = app.test_client().get("/overlay?preview=1")
    return resp.get_data(as_text=True), resp
```
Assert: `/overlay?preview=1` → 200 + `Cache-Control: no-store`; its HTML carries `class="preview"` / `body.preview` while bare `/overlay` does NOT; BOTH carry the four DOM-contract ids (`#lower-third`,`#identity`,`#timer`,`#cells`) and `/static/overlay-render.js`; the `body.preview #lower-third { opacity: 1` force-visible rule is present.

---

### `tests/test_ui_overlay_render.py` — EXTEND (test, served-JS / node transform)

**Analog:** `test_cleanfield_byte_parity_with_python_clean` (lines 110-132) — the EXACT harness to mirror. Reuse `_read_file_js()` (58-60), `_run_node(driver)` (383-399), the `module.exports` → `const _m = module.exports;` driver shape (123-128), and `@_requires_node` (64).

**Add `test_value_crosscheck`** (D-07 value — sanitized field values per discipline match Python):
```python
@_requires_node
def test_value_crosscheck():
    js = _read_file_js()
    # payloads: one per discipline incl. sct/SCT alias, control-char, over-64 inputs
    payloads = [
        {"discipline": "disc_tf", "fields": {"prese": "12", "zona": "x"*80, "totale": "7\x00"}},
        {"discipline": "disc_freestyle", "fields": {"nome": "café", "timer": "2:00"}},
        {"discipline": "agility", "fields": {"tempo": "31.4", "SCT": "45", "faults": "5"}},
    ]
    driver = (js + "\nconst _m = module.exports;\n"
        + "const _p = " + json.dumps(payloads) + ";\n"
        + "process.stdout.write(JSON.stringify(_p.map(p =>\n"
        + "  (_m.DISCIPLINE_CELLS[p.discipline]||[]).map(c => _m.scvGet(p.fields, ...c.keys)))));\n")
    js_cells = json.loads(_run_node(driver))
    # compare against Python _get over the same DISCIPLINE_CELLS key lists
    # (disc_tf: prese/zona/totale; freestyle: timer; agility: tempo/[sct,SCT]/faults)
```
Assert `js.scvGet(fields, *keys) == score_render._get(fields, *keys)` cell-by-cell (the value, not the f-string layout — JS fills DOM cells, Python builds a line). The `sct`/`SCT` first-present alias (renderer 76-86, Python `_get` 49-54) must resolve identically. The existing `test_no_innerhtml_sink` (93-100) stays green (re-asserts the HTML-injection mitigation).

For force-visible behavior verification, the `test_live_idle_run_not_stale_but_console_down_is_stale` fake-DOM harness (226-376) is the template: scenario (a) `liveHasStaleClass === false` under instant local polls proves the forced-visible plate is not dimmed by `.is-stale` (Validation Architecture §3; sandbox-first, never POST to live :8080).

---

### `tests/test_ui_scv_unification.py` (NEW, optional — test, served-HTML)

**Analog:** `test_ui_overlay_page.py::_serve`, but GET `/` (console) and POST `/score/preview`.
Assert: served `console.html` embeds `<iframe src="/overlay?preview=1">` + on-air copy; the strings `mirrorOverlayText`, `updateScorePreview`, `scheduleScorePreview`, `scvCurrentFields`, `driftCheck`, `setDrift`, `gsd:scv01-mirror`, `id="drift-warning"`, `id="overlay-preview"`, `/score/preview` are ABSENT; the surviving wiring (`post("/score"`, run buttons, `showFields`) is present (Pitfall 1); `client.post("/score/preview", ...)` returns 404/405 (D-05).

---

### `tests/test_score_preview.py` — DELETE

The whole file exercises the removed `POST /score/preview`. Its byte-exact reference strings are subsumed by the D-07 value cross-check against unchanged `render_overlay_text`.

## Shared Patterns

### Render-flag-without-config-import (server → template)
**Source:** `src/segugio/ui/app.py` `get_overlay()` (310-321) + in-factory imports (118-126); `render_template("overlay.html", **overlay_cfg)` (317).
**Apply to:** the `get_overlay()` modification.
The `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` entrypoint-arg pattern (folded over defaults at 131) is the precedent: config arrives as render args, NEVER `import segugio.config` at module top (Pitfall 3 / RBT-07). `preview` is a pure `request.args.get(...) == "1"` boolean — `request` already imported (124). No new import.

### no-store cache discipline
**Source:** `app.py` `get_overlay` (320), `get_overlay_json` (307), `get_preview_jpg` (337).
**Apply to:** the modified `/overlay` route (unchanged — keep the header) and the structural test assertion for `/overlay?preview=1`.
The iframe needs NO `?t=` nonce on its src; the cache-bust lives on the renderer's `/overlay-json` poll (Pitfall 2).

### Served-asset test harness (test client + node)
**Source:** `tests/test_ui_overlay_page.py::_serve` (39-44, served-HTML); `tests/test_ui_overlay_render.py::_read_file_js`/`_run_node`/`@_requires_node` (58-64, 383-399, served-JS via node `module.exports`).
**Apply to:** all three test changes. `_run_node` decodes stdout as UTF-8 explicitly (Windows cp1252 would mangle `café`) — reuse it verbatim for the value cross-check.

### Crash-isolation import gate (RBT-07)
**Source:** `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` (87-137) — forces heavy stack absent, builds `create_app`, GETs `/overlay` (135-137).
**Apply to:** must stay green; optionally add a `GET /overlay?preview=1` under the same heavy-absent block to prove the cosmetic flag adds no heavy import.

## No Analog Found

None. Every file in scope has an exact in-repo precedent (this is a surgical reuse-and-delete phase, not a build phase).

## Metadata

**Analog search scope:** `src/segugio/ui/` (app.py, templates/, static/, score_render.py), `tests/`
**Files scanned:** app.py (110-339), overlay.html (40-249), console.html (150-454), overlay-render.js (76-489), score_render.py (32-63), test_ui_overlay_render.py (1-400), test_ui_overlay_page.py (1-70), test_imports.py (85-137)
**Pattern extraction date:** 2026-06-15
