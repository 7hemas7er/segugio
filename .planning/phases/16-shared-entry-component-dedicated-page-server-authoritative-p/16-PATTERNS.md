# Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 7 (3 new JS/HTML, 1 modified Python, 3 new tests) + 1 verify-only test
**Analogs found:** 7 / 7 (every file has a strong in-repo analog — zero new patterns to invent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/ui/static/score-entry.js` | component (vanilla-JS mount factory) | event-driven (input/blur/submit → POST) | `src/segugio/ui/static/overlay-render.js` | role-match (served-JS dual-export + DOM-build + textContent sink) |
| `src/segugio/ui/static/score-calc.js` | utility (advisory calc port) | transform (raw inputs → total) | `src/segugio/ui/static/overlay-render.js` (`gsd:scv01-mirror` block) ↔ ports `src/segugio/ui/score_calc.py` | exact (the mirror+drift-guard precedent) |
| `src/segugio/ui/templates/score-entry.html` | template (thin Jinja host) | request-response (GET render) | `src/segugio/ui/templates/console.html` + `overlay.html` | role-match (`cam_ids \| tojson` inline-injection + CSS tokens) |
| `src/segugio/ui/app.py` (`GET /score-entry`) | route | request-response | `app.py:index` / `app.py:get_overlay` | exact |
| `src/segugio/ui/app.py` (`post_score` REWRITE) | controller | CRUD (validate→compute→atomic write) | `app.py:post_score` (current) + `post_run` | exact (same write path; new validate-before-write ordering) |
| `tests/test_ui_score_calc_js.py` | test (node parity) | event-driven | `tests/test_ui_overlay_render.py` | exact (`_run_node` + `_requires_node`) |
| `tests/test_ui_score_authoritative.py` | test (Flask client round-trip) | request-response | `tests/test_ui_score.py` + `file_channel` fixture | exact |
| `tests/test_ui_score_entry.py` | test (served-JS asserts) | static-analysis | `tests/test_ui_overlay_render.py` (Task 1 asserts) | exact |

## Pattern Assignments

### `src/segugio/ui/static/score-entry.js` (component, event-driven) — NEW

**Analog:** `src/segugio/ui/static/overlay-render.js`

**IIFE + dual-export + auto-mount skeleton** (overlay-render.js:30, 510-549) — copy verbatim shape:
```js
(function () {
  "use strict";
  function mount(root, cfg) { /* build fields from cfg.profile, wire input/blur/submit */ }
  function autoMount() {
    if (typeof document === "undefined") return null;            // node-test guard
    const el = document.getElementById("score-cfg");
    const cfg = el ? JSON.parse(el.textContent) : {};
    return mount(document.getElementById("score-entry-root"), cfg);
  }
  const api = { mount };
  if (typeof window !== "undefined") window.SEGUGIO_SCORE_ENTRY = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", autoMount);
    else autoMount();
  }
})();
```
Note overlay-render.js uses `window.OVERLAY_CFG` (a window global); D-07 prefers the inlined `<script id="score-cfg">` JSON blob read via `JSON.parse(el.textContent)` — the `cam_ids | tojson` precedent (console.html:355), not a window global.

**textContent-only sink + in-place update** (overlay-render.js:98-119 `fillCell`) — the XSS-safe DOM pattern to copy for EVERY operator value (freestyle `nome`, error chips, the live total):
```js
if (labelEl.textContent !== label) labelEl.textContent = label;
const changed = valueEl.textContent !== clean;
if (changed) valueEl.textContent = clean;   // textContent in place, NEVER innerHTML / node rebuild
```
The advisory total recompute (D-02) must update `textContent` in place (overlay-render.js:351 `paintTimer` precedent), never rebuild the node — the same FOUC/flicker discipline.

**Static-icon innerHTML allowance:** console.html uses an `icon()`/`ICONS` pattern with STATIC SVG markup; that is the ONLY acceptable `innerHTML` (static, no operator data). The served-JS test (below) forbids `innerHTML` for operator values.

**Inline discipline-toggle precedent** (console.html:266-298 `#form-score`): `<select name="discipline">` + `.campi[data-disc=...]` show/hide fieldsets. The component reproduces this toggle in JS (D-06: options come from `cfg.disciplines`, not the hardcoded 3-option list). The legacy `#form-score` itself is NOT removed in P16.

---

### `src/segugio/ui/static/score-calc.js` (utility, transform) — NEW

**Analog (test+sentinel mechanics):** `src/segugio/ui/static/overlay-render.js` `gsd:scv01-mirror` block (lines 33-66).
**Analog (the Python source it ports byte-exact):** `src/segugio/ui/score_calc.py` — `compute` (264) + `validate` (185).

**Sentinel block pattern** (overlay-render.js:33, 66) — wrap the ported functions:
```js
// ===== gsd:score-calc-mirror:start =====
// BYTE-EXACT with segugio.ui.score_calc.compute/validate. Decimal-equivalence via a
// fixed-scale integer helper — NEVER Number float math (Pitfall 1 / D-09).
... ported compute/validate ...
// ===== gsd:score-calc-mirror:end =====
```

**Exact ops to mirror from score_calc.py (port each, do NOT re-derive the rules):**
- `_is_truthy_flag` (score_calc.py:103-118): a string flag is truthy ONLY for `{"true","1","yes","on"}` after `.strip().lower()`; a real bool returns itself. CR-01 — a checkbox posts `"on"`/`"true"`; an unchecked hidden `"false"`/`"0"` must NOT score. The JS port uses the identical set.
- `_compute_disc_tf` (282-309): per-throw = `_zone_points` + each truthy bonus Decimal; `min(score, per_throw_cap)`; `sorted(per_throw, reverse=True)[:count_best_n]`; `sum`. Emits flat `prese`/`zona`/`totale` strings.
- `_compute_freestyle` (312-327): `value.quantize(inc, ROUND_HALF_UP)` per category → sum → cap at `freestyle_max` → minus `adjustment`. Mirror ROUND_HALF_UP as scaled-integer round-half-up.
- `_compute_agility` (330-357): elimination FIRST (`elimination_sentinel`); else `_time_faults = ceil(rate * max(0, run - sct))` (ROUND_CEILING) with `_parse_time_seconds` mm:ss(.cc) → centisecond integer math; `count_up` vs `deduct_from_100` per `agility_model`.
- `_parse_time_seconds` (149-163) + `_TIME_RX = ^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$` (58): port the anchored regex verbatim.

**Decimal-equivalence (the hard part):** port with a fixed-scale integer/string decimal helper — Python stringifies verbatim (`"19.0"`, `"40"`), JS `Number` would drift (`0.1+0.2`). Compare on the FLAT summary keys (`totale`/`prese`/`zona`/`faults`/`result`).

---

### `src/segugio/ui/templates/score-entry.html` (template, request-response) — NEW

**Analog:** `src/segugio/ui/templates/console.html` (CSS tokens + injection) and the thin-host discipline of `overlay.html`.

**Inline JSON blob injection** (console.html:355 `const CAMS = {{ cam_ids | tojson }};`) — mirror as:
```html
<script type="application/json" id="score-cfg">{{ score_cfg | tojson }}</script>
<div id="score-entry-root"></div>
<script src="/static/score-calc.js"></script>
<script src="/static/score-entry.js"></script>
```

**CSS tokens to reuse verbatim** (console.html `<style>`, D-10) — do NOT invent a token set:
- `:root { color-scheme: dark; }` (line 16)
- Type system: `h1` 1.25rem/700/1.2 (22); `label` 0.875rem/700 `#b9b9b9` (26); `input,select` `padding:16px; font-size:1rem; font-weight:400; border-radius:6px` (29); `button` (34); `.hint` 0.75rem/400 `#b9b9b9` (49). 4 sizes, weights 400+700 ONLY.
- `.row` flex layout (used in `#form-score` rows) for the throw-row cells; `.campi[data-disc]` + `.hidden` for the discipline toggle.
- Italian copy precedent: "Disciplina", "Disc — Toss & Fetch", "usa il punto (.) per i decimali" (console.html:265-298).

The host page carries NO `<input>` / calc logic of its own (overlay.html thin-host discipline) — the served-JS test asserts this.

---

### `src/segugio/ui/app.py` — `GET /score-entry` route (NEW) + `create_app` signature (MODIFIED)

**Analog:** `app.py:index` (185-191) and `app.py:get_overlay` (286-307); the `cam_ids`/`overlay_cfg` plain-arg precedent (98-131).

**Additive `create_app` arg** — mirror the `cam_ids=()` / `overlay_cfg=None` plain-arg discipline (app.py:98). Default to `CSEN_DISC_PROFILE` so existing single-/triple-arg callers stay green:
```python
def create_app(channel_dir, cam_ids=(), overlay_cfg=None, profile=None, sport="disc_dog"):
    from .score_calc import CSEN_DISC_PROFILE   # lazy/in-factory — stdlib-only, crash-isolation safe
    profile = profile or CSEN_DISC_PROFILE
```

**The new GET route** — mirror `index`/`get_overlay`. Build the `score_cfg` dict (decimal-as-STRING via a stdlib `_profile_to_json` helper) and the valid-discipline list (D-06: `disc_dog` → `["disc_tf","disc_freestyle"]`, `agility` → `["agility"]`):
```python
@app.get("/score-entry")
def score_entry():
    return render_template("score-entry.html", score_cfg=_score_cfg)
```

**Crash-isolation rule:** `adapt_scoring_profile` lives in the heavy config tier — resolve it LAZILY in `__main__` ONLY (mirror the `load_config` lazy import at app.py:364-366), pass the resulting plain dataclass into `create_app`. NEVER `from ..config...` at module top.

---

### `src/segugio/ui/app.py` — `post_score` REWRITE (MODIFIED, ~line 193)

**Analog:** the CURRENT `post_score` (app.py:193-214) + `post_run` (216-237) + the `_bump_score_gen` write path (167-181).

**Current display-only body to RETIRE** (app.py:206-213):
```python
fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS and v.strip()}  # trusts manual totale
doc = ScoreDoc(discipline=discipline, fields=fields)
write_score(_path(_SCORE_FILE), doc)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))
_bump_score_gen()
return ("", 204)
```

**New authoritative body** — keep the existing `Discipline(raw)` 400-boundary (app.py:197-201) and the write path (`write_score` / `atomic_write_text` / `_bump_score_gen`), insert validate-before-write:
```python
raw = request.get_json(silent=True) or request.form   # JSON body carries throws[] (wire format A)
try:
    discipline = Discipline(raw.get("discipline", Discipline.disc_tf.value))
except ValueError:
    return ("disciplina sconosciuta", 400)
fields = _parse_structured_inputs(discipline, raw)
errors = score_calc.validate(discipline, fields, profile)
if errors:
    return (jsonify({"errors": errors}), 400)    # ★ NO write — prev on-air byte-untouched (D-05/WR-03)
computed = score_calc.compute(discipline, fields, profile)
doc = ScoreDoc(discipline=discipline, fields=computed)
write_score(_path(_SCORE_FILE), doc)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))
_bump_score_gen()                                  # gen++ only; PRESERVES running/started_at (WR-03)
return ("", 204)
```

**`_bump_score_gen` is UNCHANGED** (app.py:167-181) — it already advances `gen` from in-memory `_state` and preserves `running`/`started_at` (WR-03). Do not touch it; just keep calling it.

**Round-trip read side is UNCHANGED:** `/overlay-json` (app.py:262-284) echoes `s.fields` verbatim → the acceptance test asserts `computed["totale"] == overlay.txt line == /overlay-json fields.totale`.

**FLAGGED MISMATCH (Pitfall 4):** the legacy `console.html` `#form-score` posts manual flat keys `prese`/`zona`/`totale` (console.html:275-277) and manual `faults` (295) — these do NOT match the `score_calc` contract (`throws[]`; `course_faults`/`course_deductions` + `tempo`/`sct`/`eliminated`). After this rewrite the legacy form's POSTs will 400. The planner MUST resolve Open Q1: (a) a thin back-compat branch in `post_score` for legacy flat keys until P17 retires the form, OR (b) repoint `console.html` now. RESEARCH recommends (a). `tests/test_ui_score.py` (current, posts manual flat keys) WILL break under the rewrite — it is the explicit REVIEW target.

---

### `tests/test_ui_score_calc_js.py` (test, node parity) — NEW

**Analog:** `tests/test_ui_overlay_render.py` — clone wholesale.

**Copy verbatim:** the `_JS_PATH`/`_read_file_js` helper (39-60), `_NODE = shutil.which("node")` + `_requires_node` skip (63-64), and the `_run_node` UTF-8 helper (462-478) — the `.decode("utf-8")` stdout is load-bearing on Windows (cp1252 would mangle non-ASCII). Point `_JS_PATH` at `static/score-calc.js`.

**Driver shape** (clone of `test_cleanfield_byte_parity_with_python_clean`, 110-132):
```python
driver = js + "\nconst _m = module.exports;\n" + "const _in = " + json.dumps(fixtures) + ";\n" \
    + "const _p = " + json.dumps(PROFILE_JSON) + ";\n" \
    + "process.stdout.write(JSON.stringify(_in.map(f => _m.compute(f.discipline, f.fields, _p))));\n"
js_out = json.loads(_run_node(driver))
py_out = [score_calc.compute(f["discipline"], f["fields"], score_calc.CSEN_DISC_PROFILE) for f in fixtures]
for j, p in zip(js_out, py_out):
    assert j["totale"] == p["totale"]
```
Fixtures must cover: best-5-of-N, a `0.5` bonus, a `"false"`/`"0"` flag (CR-01), freestyle cap at `freestyle_max`, agility ceil, elimination sentinel. Add a parallel `test_validate_parity` (clone `test_value_crosscheck`, 164-211) comparing the `{field,message}` error lists.

---

### `tests/test_ui_score_authoritative.py` (test, Flask client round-trip) — NEW

**Analog:** `tests/test_ui_score.py` + the `file_channel` fixture (conftest.py:422-445).

**Copy the client fixture** (test_ui_score.py:19-27):
```python
@pytest.fixture
def client(file_channel):
    from segugio.ui.app import create_app
    app = create_app(str(file_channel["dir"]))   # default profile = CSEN_DISC_PROFILE
    app.config.update(TESTING=True)
    return app.test_client(), file_channel
```
`file_channel` provides `dir`/`score`/`overlay`/`overlay_run` Paths (conftest.py:437-444). Use `read_score(str(ch["score"]))` (test_ui_score.py:15,40) and `ch["overlay"].read_text(...)` for assertions.

**Tests to write (per RESEARCH test map):**
- `test_invalid_post_400_writes_nothing` — POST a bad zone → 400 AND `not ch["score"].exists()` (the `test_post_score_unknown_discipline_rejected` "nothing written" assert, test_ui_score.py:83, generalized: seed a valid score first, then assert the file is byte-unchanged on a rejected submit).
- `test_valid_post_recomputes_and_writes` — POST `throws[]` JSON → `doc.fields["totale"]` equals the Python `compute` result.
- `test_score_preserves_run_state` — start a run, POST a score, assert `read_overlay_run` `running`/`started_at` preserved and `gen` bumped (WR-03; the `_bump_score_gen` contract).
- `test_round_trip_total_equality` — form total === `overlay.txt` line === `GET /overlay-json` `fields.totale`.

Post JSON via `c.post("/score", json={"discipline": "disc_tf", "throws": [...]})` (wire format A).

---

### `tests/test_ui_score_entry.py` (test, served-JS asserts) — NEW

**Analog:** `tests/test_ui_overlay_render.py` Task-1 asserts (72-107).

**Copy:** `_read_served_js` (49-56, fetch `/static/score-entry.js` via the Flask test client) and the `_read_file_js` reader. Asserts to mirror:
- `test_dual_export_and_thin_host` — `"window.SEGUGIO_SCORE_ENTRY"` and `"module.exports"` present; the `/score-entry` host HTML contains NO `<input` of its own (thin host).
- `test_no_innerhtml_sink` — clone test_ui_overlay_render.py:93-101 verbatim: assert `"textContent"` present and every `innerHTML` variant absent for operator values.
- `test_disciplines_from_profile` — GET `/score-entry` with a disc-dog profile renders T&F + Freestyle; an agility config renders Agility only (D-06).

## Shared Patterns

### Crash-isolation (allowlist) — apply to `app.py` and both JS files
**Source:** `app.py` module docstring (1-28) + the lazy-import discipline (`create_app` imports Flask in-body at 118; `__main__` lazy-loads config at 364).
**Apply to:** `GET /score-entry`, `post_score`, `create_app`. NEVER `from ..config...` or `import numpy` at a `segugio.ui` module top. `adapt_scoring_profile` is resolved LAZILY in `__main__` only.
**Gate:** `tests/test_ui_score.py::test_app_imports_nothing_heavy` (106-147) + `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` must stay green (already tolerant of 200/204).

### Atomic write + gen-bump — apply to `post_score`
**Source:** `app.py` `write_score` / `atomic_write_text` / `_bump_score_gen` (167-181, 209-213).
**Apply to:** the authoritative write only. Never hand-roll `open().write()`. `_bump_score_gen` (NOT `_bump_overlay_run`) — a score is not a run edge; it preserves `running`/`started_at` (WR-03).

### Validate-before-write — apply to `post_score`
**Source:** `score_calc.validate` contract (score_calc.py:185, D-11: caller runs validate FIRST, writes nothing on a non-empty list).
**Apply to:** `post_score` — the route does NO write before `validate()` returns clean (SCC-01 broadcast-integrity, D-05 "punteggio precedente invariato").

### node-vs-Python drift-guard — apply to both JS test files
**Source:** `tests/test_ui_overlay_render.py` (`_run_node` UTF-8 helper:462, `_requires_node` skip:64, `gsd:scv01-mirror` sentinel asserts:77-85).
**Apply to:** `test_ui_score_calc_js.py` (compute/validate parity), `test_ui_score_entry.py` (sentinel + no-innerHTML asserts).

### Decimal-as-string profile transport — apply to `create_app` / template
**Source:** the `cam_ids | tojson` inline-blob precedent (console.html:355) + score_calc Decimal stringification (score_calc.py:306-308).
**Apply to:** `_profile_to_json(profile)` — emit every numeric (`per_throw_cap`, zone points, bonus values, freestyle min/max/inc, `freestyle_max`) as `str(Decimal)`, never float. Pin a unit test: `json.loads(blob)["per_throw_cap"] == "5"` (string).

## No Analog Found

None. Every file has a strong in-repo analog.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | — |

## Metadata

**Analog search scope:** `src/segugio/ui/{app.py,score_calc.py,score_render.py,static/,templates/}`, `src/segugio/config/discipline.py`, `tests/{test_ui_overlay_render.py,test_ui_score.py,conftest.py}`
**Files scanned:** 9 read in full/targeted + 2 grep sweeps
**Pattern extraction date:** 2026-06-23
