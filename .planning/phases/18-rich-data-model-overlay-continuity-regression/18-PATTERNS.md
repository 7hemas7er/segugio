# Phase 18: Rich Data Model & Overlay-Continuity Regression - Pattern Map

**Mapped:** 2026-06-27
**Files analyzed:** 10 (5 source MODIFY + 5 test EXTEND/NEW-case)
**Analogs found:** 10 / 10 (all in-repo; this is a MODIFY-existing + EXTEND-existing-tests phase — every analog is the file's own current code or a sibling test)

> **Reading note for the planner/executor:** this phase builds NO new machinery and creates NO new files. Every "analog" is either (a) the exact function being edited (the pattern to *preserve byte-identically* while adding subkeys), or (b) a sibling test whose harness is copy-adapted for the two Wave-0 new assertions. The literal additive code blocks are already drafted in `18-RESEARCH.md` lines 128-203 — treat those as the primary source; this file maps each to its in-file anchor and the surrounding pattern to keep intact.

## File Classification

| File (MODIFY / extend) | Role | Data Flow | Closest Analog (self / sibling) | Match Quality |
|------------------------|------|-----------|----------------------------------|---------------|
| `src/segugio/ui/score_calc.py` | service (pure compute) | transform | own `_compute_disc_tf`/`_compute_freestyle`/`_compute_agility` flat-key emit + `app._profile_to_json` Decimal-string precedent | exact (self) |
| `src/segugio/ui/app.py` | controller (route + parse) | request-response | own `_parse_structured_inputs` passthrough lists + `get_overlay_json` verbatim echo | exact (self) |
| `src/segugio/ui/score_render.py` | service (text render) | transform | own `render_overlay_text` flat-scalar `_get` reads + `_clean` (NO change expected — freeze target) | exact (self) |
| `src/segugio/ui/static/overlay-render.js` | component (DOM sink) | event-driven | own `renderIdentity` `createTextNode` band + `fillCell` `textContent` | exact (self) |
| `src/segugio/ui/static/score-entry.js` | component (form preview) | event-driven | own `nomeEcho.textContent` input echo + `el()` helper | exact (self) |
| `src/segugio/ui/templates/{overlay,_score-entry-form,score-entry}.html` | config (Jinja host) | request-response | own `{{ event_name \| default }}` autoescaped + `{{ score_cfg \| tojson }}` | exact (self) |
| `tests/test_score_calc.py` | test (unit) | transform | existing per-discipline `compute()` assertions | role-match |
| `tests/test_ui_overlay_json.py` | test (integration) | request-response | `test_overlay_json_payload_shape` (line 119, 6-key envelope) | exact |
| `tests/test_overlay_fallback_gate.py` / `test_ui_overlay_render.py` | test (integration) | file-I/O | `overlay.txt` single-line persistence assertions | role-match |
| `tests/test_overlay_html_sink_gate.py` (D-07a extend + D-07b NEW) | test (source-grep + node behavior) | event-driven | own `test_no_innerhtml_sink` (grep) + `test_ui_score_entry.py` `_FAKE_DOM` (148-256) + `test_ui_overlay_render.py` fake DOM (321-389) | exact |

## Pattern Assignments

### `src/segugio/ui/score_calc.py` (service, transform) — additive subkeys

**Analog:** the function being edited. The pattern to COPY is the existing flat-key emit — `str(Decimal)` every value, append to `out`, never touch the sum/best-N math.

**Flat-key emit pattern to mirror** (`_compute_disc_tf`, lines 288-315):
```python
def _compute_disc_tf(out: dict, profile: ScoringProfile) -> dict:
    throws = out.get("throws") or []
    per_throw: list[Decimal] = []          # ← already built, then DISCARDED (attach instead)
    band_total = Decimal("0")
    for throw in throws:
        zone_points = _zone_points(profile, throw.get("zone")) or Decimal("0")
        band_total += zone_points
        score = zone_points
        for key, value in profile.bonuses:
            if _is_truthy_flag(throw.get(key)):
                score += value
        if profile.per_throw_cap is not None:
            score = min(score, profile.per_throw_cap)
        per_throw.append(score)
    ...
    out["prese"] = str(len(throws))        # ← the str(...) discipline to copy for subkeys
    out["zona"] = str(band_total)
    out["totale"] = str(total)
    return out
```
**Additive change (from RESEARCH lines 132-158):** rebuild `new_throws.append({**throw, "score": str(score)})` and set `out["throws"] = new_throws`. **Rebuild dicts — do NOT mutate in place** (`out = dict(fields)` is shallow, line 277).

**Freestyle** (`_compute_freestyle`, 318-333): the loop already snaps each category (`snapped = value.quantize(...)`, line 323) and discards it. Collect `criteria[name] = str(snapped)`; set `out["criteria"] = criteria`. Keep `out["totale"]` byte-identical.

**Agility** (`_compute_agility`, 336-363): `time_faults` computed line 346, never exposed. Add `out["faults_breakdown"] = {"course": str(...), "time": str(time_faults)}` in BOTH the `count_up` and `deduct_from_100` branches. **OMIT it on the elimination short-circuit** (lines 339-342) — that branch returns before any time math (Assumption A2 — confirm with planner).

**Decimal-string precedent:** `app._profile_to_json` stringifies every numeric — same shape. **Anti-pattern (Pitfall 1):** a raw `Decimal` subkey → `json.dumps` `TypeError` → 500 on `write_score`.

---

### `src/segugio/ui/app.py` (controller, request-response) — free-text passthrough

**Analog:** `_parse_structured_inputs` (lines 128-157) — the per-discipline key allowlist. The route (`get_overlay_json`) echoes `s.fields` verbatim → **no route edit**.

**Passthrough pattern to extend** (lines 142-156):
```python
elif discipline == Discipline.disc_freestyle:
    for key in ("team", "dog", "player", "catch", "adjustment", "nome", "timer"):
        if key in raw:
            fields[key] = raw.get(key)
elif discipline == Discipline.agility:
    for key in ("tempo", "sct", "course_faults", "course_deductions", "eliminated"):
        if key in raw:
            fields[key] = raw.get(key)
```
**Additive change:** add identity keys `cane` / `conduttore` / `giudici` to ALL THREE discipline branches (D-01 identity is universal — Open Question 2 recommends a shared identity-key list applied regardless of discipline). **Do NOT name the dog field `dog`** — collides with the freestyle `dog` category key (RESEARCH line 199). `compute()` carries them verbatim via `out = dict(fields)` (line 277); the route echoes them — zero route change.

**Crash-isolation guard (D-09):** no new import at module top. Flask + score_calc are imported INSIDE `create_app` (lines 203-218); keep it that way.

---

### `src/segugio/ui/score_render.py` (service, transform) — FREEZE, do not enrich

**Analog / freeze target:** `render_overlay_text` (57-86) reads ONLY flat scalar keys via `_get`; `_clean` (32-46) strips CR/LF + non-printable, caps at `_MAX_FIELD_LEN = 64`.

```python
def _clean(value: object) -> str:
    text = "" if value is None else str(value)
    text = "".join(ch for ch in text if ch == " " or (ch.isprintable() and ch not in "\r\n"))
    text = text.strip()
    if len(text) > _MAX_FIELD_LEN:
        text = text[:_MAX_FIELD_LEN]
    return text
```
**Pattern to preserve (Pitfall 3):** never add a dict/list subkey to a `_get(...)` call list — `_clean` would `str()` the dict into the line. `overlay.txt` stays single-line *by construction*; D-06 proves it, the renderer is NOT edited.

---

### `src/segugio/ui/static/overlay-render.js` (component, event-driven) — identity sink

**Analog:** `renderIdentity` (143-163) — the dog/handler target; every value via `document.createTextNode(...)`.

```javascript
function renderIdentity(identityEl, fields) {
    if (!identityEl) return;
    const event = identityEl.getAttribute("data-event") || "";
    const competitor = scvGet(fields, "nome");           // ← extend: build from cane/conduttore
    while (identityEl.firstChild) identityEl.removeChild(identityEl.firstChild);
    if (competitor && event) {
        identityEl.appendChild(document.createTextNode(competitor));  // ← keep this sink for new fields
        const sep = document.createElement("span");
        sep.className = "sep";
        sep.textContent = "·";
        ...
```
**Additive change (D-01, RESEARCH line 201):** build `competitor` from `cane`/`conduttore` (Claude's discretion on format; fall back to `nome` for the freestyle routine name). EVERY value stays on the `scvGet → createTextNode` path. **`giudici` is data-only — MUST NOT be rendered on the lower-third** (deferred). Cell-value sink to mirror if needed: `fillCell` `valueEl.textContent` (113-117). **Anti-pattern (Pitfall 4):** any `innerHTML`/`insertAdjacentHTML` for the combine — the D-07a grep + D-07b DOM assertion catch it.

---

### `src/segugio/ui/static/score-entry.js` (component, event-driven) — form preview sink

**Analog:** the `nomeEcho` input echo (422-426) and the `el()` helper (textContent-only, line 59 per RESEARCH).

```javascript
const nomeEcho = el("div", { class: "nome-echo hint" });
wrap.appendChild(nomeEcho);
nome.addEventListener("input", () => {
    nomeEcho.textContent = nome.value;   // textContent in place — inert if it contains markup
});
```
**Additive change:** add `cane`/`conduttore`/`giudici` inputs via the same `el()` helper; any preview echo uses `textContent`. Icons via `createElementNS` (63-80). **No `innerHTML` anywhere** — the served-JS grep (D-07a) is being extended to THIS file.

---

### `src/segugio/ui/templates/*.html` (config, Jinja) — autoescape freeze

**Analog:** `overlay.html:244` `{{ event_name | default('', true) }}` (autoescaped) and `_score-entry-form.html:11` `{{ score_cfg | tojson }}`. **Pattern to preserve:** NO `| safe`, NO `{% autoescape false %}` anywhere in `src/segugio/ui` (grep-confirmed). Any new server-rendered free-text field uses plain `{{ value }}` (autoescaped).

## Shared Patterns

### XSS sink discipline (apply to all DOM-bound new fields)
**Source:** `overlay-render.js` `renderIdentity` (createTextNode) + `score-entry.js` `nomeEcho.textContent`.
**Apply to:** every new free-text field reaching the DOM. Route via `scvGet → createTextNode` / `textContent` only.

### Decimal-string serialization (apply to all subkeys)
**Source:** `score_calc.py` flat keys `out["totale"] = str(total)` + `app._profile_to_json`.
**Apply to:** `throws[].score`, `criteria{}` values, `faults_breakdown{}` values — `str(...)` every Decimal.

### Verbatim route echo (no route change)
**Source:** `get_overlay_json` echoes `s.fields` verbatim, 6-key envelope `{discipline, fields, running, started_at, server_now, gen}` (app.py:402-424).
**Apply to:** all new subkeys + free-text — they ride inside `fields`; NEVER add a top-level `/overlay-json` key.

### Crash-isolation import allowlist
**Source:** Flask + score_calc imported INSIDE `create_app` (app.py:203-218).
**Apply to:** all source edits — no new module-top import; `test_imports.py` stays green (D-09).

## Wave-0 New Test Cases → Analog to Copy-Adapt

### D-05 golden-snapshot key-set test → extends `tests/test_ui_overlay_json.py`
**Analog:** `test_overlay_json_payload_shape` (line 119) already asserts the 6-key envelope. Copy-adapt into a per-discipline subset assertion (RESEARCH lines 333-356):
```python
LEGACY_FLAT_KEYS = {
    "disc_tf": {"throws", "prese", "zona", "totale"},
    "disc_freestyle": {"nome", "timer", "totale"},
    "agility_count_up": {"tempo", "sct", "faults"},
}
def test_disc_tf_legacy_keys_preserved_and_subkey_added(client):
    c, _ = client
    c.post("/score", json={"discipline": "disc_tf", "throws": [{"zone": 4, "midair": True}]})
    fields = c.get("/overlay-json").get_json()["fields"]
    assert LEGACY_FLAT_KEYS["disc_tf"] <= set(fields)   # subset — removal/rename fails CI
    assert fields["throws"][0]["zone"] == 4             # raw throw preserved
    assert fields["throws"][0]["score"] == "4.5"        # NEW additive Decimal-string subkey
```
**Use the subset form** `LEGACY <= set(fields)` (catches removal/rename without blocking future additive growth — Open Question 1 recommendation).

### D-07b crafted-`<script>` DOM render assertion → extends `tests/test_overlay_html_sink_gate.py` (NEW node assertion)
**Analog (harness to copy):** `tests/test_ui_score_entry.py` `_FAKE_DOM` (lines 148-256) — self-contained fake DOM with the critical `textContent` getter that **concatenates child text nodes** (lines 172-178), so a crafted value landing as a single text node yields `textContent === payload` and `children.length === 0`. Secondary analog: `test_ui_overlay_render.py` fake DOM + `createTextNode` stub (321-389), and the `_run_node` subprocess driver gated by `shutil.which("node")` (`@_requires_node`).

**Two render targets to drive (RESEARCH lines 370-377):**
1. **Overlay lower-third:** call `renderIdentity(identityEl, {cane: "<script>x</script>", ...})`; assert `identityEl.textContent === payload` AND no child *element* (only text node).
2. **Form preview:** dispatch `'input'` with a `<script>` value on the `nome`/new field; assert `nomeEcho.textContent === payload` AND `nomeEcho.children.length === 0`.

**D-07a grep guard:** extend `test_no_innerhtml_sink` (lines 39-46) — currently reads only `overlay-render.js`; add a `score-entry.js` path read and assert the same `".innerHTML" not in js` / `textContent in js` over both files.

### D-06 overlay.txt single-line regression → extends `test_overlay_fallback_gate.py` / `test_ui_overlay_render.py`
**Analog:** existing `test_overlay_txt_persists_last_score_after_simulated_death`. Copy-adapt to POST a rich body (with `cane`/`conduttore` + multi-throw) then assert `line and "\n" not in line and "\r" not in line` per discipline (RESEARCH lines 358-368).

### D-03 subkey unit assertions → extends `tests/test_score_calc.py`
**Analog:** existing per-discipline `compute()` assertions + `tests/_score_fixtures.py` shared fixtures. Add `throws[i]["score"] == "4.5"`, `criteria["team"] == "8.50"`, `faults_breakdown == {"course": "5", "time": "5"}` while keeping the existing `totale=="19.0"` round-trip assertions (`test_csen_tf_best5`, `test_round_trip_total_equality`) green (Pitfall 2).

## No Analog Found

None. Every change extends an existing, currently-passing in-repo pattern. The only "new" artifacts are two assertions (D-05 snapshot, D-07b DOM render), both copy-adapted from sibling test harnesses listed above.

## Metadata

**Analog search scope:** `src/segugio/ui/` (score_calc, app, score_render, static/*.js, templates/*.html), `tests/` (overlay/score/import gates + fake-DOM harnesses).
**Files scanned:** 10 read this session (score_calc.py:260-389, app.py:120-219, score_render.py:28-87, overlay-render.js:90-169, score-entry.js:415-433, test_ui_score_entry.py:140-269, test_overlay_html_sink_gate.py:1-67, test_ui_overlay_render.py:300-389) + RESEARCH/CONTEXT.
**Pattern extraction date:** 2026-06-27
