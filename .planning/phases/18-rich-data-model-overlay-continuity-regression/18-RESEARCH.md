# Phase 18: Rich Data Model & Overlay-Continuity Regression - Research

**Researched:** 2026-06-27
**Domain:** Additive enrichment of an already-shipped, server-authoritative score data model + regression-hardening of every overlay contract (`/overlay`, `/overlay-json`, `overlay.txt`, HTML sink). Pure in-repo Python + vanilla-JS; zero new runtime dependency.
**Confidence:** HIGH (every claim grounded in the current source read this session — file:line cited inline).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Add dog/handler as free-text that feeds the overlay's **existing** `competitor` identity line (`overlay-render.js` already renders a competitor/event identity band — NOT a new visible overlay element). Judges ride in `score.json` + the entry form **only** — NOT shown on the single-score broadcast overlay. How dog + handler combine into one identity display string is a renderer/planning detail.
- **D-02:** Every new free-text field is carried additively through the write path and is subject to the same XSS sink discipline as the existing identity values (see D-07).
- **D-03:** `compute()` emits the structured subkeys **server-authoritatively** as Decimal **strings** (never float):
  - disc T&F: `throws[]` gains a **per-throw computed score** alongside the already-surviving raw `{zone, midair, corridor}` entries.
  - freestyle: a `criteria{}` subkey holding the **per-category snapped values** (today only flat `totale` is emitted).
  - agility: a `faults_breakdown{}` subkey splitting `{course, time}` faults (today `time_faults` is computed internally but never exposed).
- **D-04:** **Strictly additive** — every existing flat summary key (`prese`, `zona`, `totale`, `faults`, `result`, `nome`, `timer`, …) stays byte-identical in name and value. No rename, no removal, no reshaping. Phase-16 round-trip equality (form total === `overlay.txt` line === `/overlay-json` total) must still hold.
- **D-05:** Automated **golden-snapshot** test that freezes the `/overlay-json` legacy key set so a future rename/removal **fails CI** (lands in / extends `tests/test_ui_overlay_json.py`).
- **D-06:** Automated `overlay.txt` regression: still a **single non-empty line**, length-bounded per field, after a rich `POST /score` (extends `tests/test_ui_overlay_render.py` / `test_overlay_fallback_gate.py`). `/overlay` host page proven to still bake in **no** score data (`test_ui_overlay_page.py`).
- **D-07 (XSS — both guards):** (a) extend the existing no-`innerHTML` served-JS grep guard to the new templates/fields, AND (b) add a **DOM-level crafted-`<script>` render assertion** proving the value renders as inert escaped text on **both** the `/overlay` lower-third AND the entry-form preview (`score-entry.js` `nomeEcho`); confirm Jinja **autoescape** on any server-rendered free-text and that `overlay.txt`'s `_clean` still strips control chars.
- **D-08:** A **non-blocking, documented** real-OBS read-from-file rig checklist is carried forward — automated tests gate sign-off; the physical rig check is recorded but does not block phase completion.
- **D-09:** The console import surface stays `Flask + segugio.opcomm + score_calc` (pure stdlib). No new import, no config import at module top. The heavy-absent import-smoke gate (`test_imports.py`) must stay green, and a rich `POST /score` round-trip must resolve with the heavy stack absent.

### Claude's Discretion
- Exact JSON key names / nesting for `criteria{}` and `faults_breakdown{}`, and the per-throw score field name (D-03/D-04 fix the shape *intent*, not the literal key strings).
- Display formatting of the combined dog/handler identity string in the renderer.

### Deferred Ideas (OUT OF SCOPE)
- **Judges on the overlay** — deferred to SCM-F1 (multi-judge freestyle).
- **Blocking real-OBS rig UAT** — the rig checklist is carried forward as non-blocking (D-08).
- Roster/standings (SCM-F2), multi-judge freestyle (SCM-F1), any new *computed* judging/adjudication.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RBT-09 | The degraded `overlay.txt` fallback and the `/overlay` + `/overlay-json` contracts stay invariant (regression-verified); new free-text fields (dog/handler/judges) are HTML-escaped at the overlay sink. | Exact current `/overlay-json` key set + per-discipline flat `fields` keys frozen below (D-05); `overlay.txt` single-line invariant traced to `render_overlay_text`/`_clean` (D-06); existing `textContent`/`createTextNode` sinks + Jinja autoescape located for extension (D-07); subkey-emit sites in `compute()` identified for additive change (D-03/D-04). |
</phase_requirements>

## Summary

This is a **mechanical, additive** phase with the work split roughly 30% code / 70% regression proof. The data model already flows through a fully-wired, server-authoritative path: client POSTs raw inputs → `post_score` validates → `score_calc.compute()` recomputes Decimal totals → `_write_score_doc` writes `score.json` (structured) + `overlay.txt` (rendered) → `get_overlay_json` echoes `s.fields` **verbatim** → `overlay-render.js` renders via `textContent`/`createTextNode`. Three additive subkeys (`throws[].score`, freestyle `criteria{}`, agility `faults_breakdown{}`) slot into `compute()` next to the existing flat keys, plus new free-text identity fields (dog/handler/judges) ride through `_parse_structured_inputs` → `compute()` passthrough → `score.json`/`/overlay-json` with zero route change (the route echoes the dict verbatim).

The regression surface is the real deliverable. `score.json` serialization (`write_score`) is `json.dumps` over a free-form `fields` dict, so nested dicts/lists round-trip natively — the ONLY hard constraint is that **every new subkey value is a Decimal *string***, because `json.dumps` cannot serialize a raw `Decimal` (it raises → 500). `render_overlay_text` reads only the flat scalar keys via `_get`, so the new dict/list subkeys never reach `_clean` and `overlay.txt` stays single-line by construction — but D-06 requires *proving* this, not assuming it. The XSS story is already correct (every sink is `textContent`/`createTextNode`/`createElementNS`, Jinja `| tojson` for the config blob, no `| safe` anywhere); the work is *extending the guards to the new fields*, not building escaping.

**Primary recommendation:** Make the three subkeys additive inside `compute()`'s existing per-discipline helpers (the snapped/per-throw/time-fault values are *already computed and discarded* — just attach them as `str(Decimal)`); add the new free-text fields to `_parse_structured_inputs`' passthrough lists and `overlay-render.js`'s `renderIdentity`; then freeze the legacy contract with a golden-snapshot test and extend the four regression gates. Touch no route, no `write_score`, no flat key.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Emit additive subkeys (per-throw score, `criteria{}`, `faults_breakdown{}`) | Pure compute (`score_calc.compute`) | — | Server is the sole compute authority (keystone); subkeys are Decimal-strings produced where the raw values already exist. |
| Carry new free-text fields (dog/handler/judges) through the write path | API (`app._parse_structured_inputs` → `compute` passthrough) | — | Raw input collection; `compute` carries them verbatim via `out = dict(fields)`; route echoes verbatim. |
| Serialize structured `fields` to `score.json` | Storage (`opcomm.channel.write_score`) | — | Free-form `json.dumps`; nested dict/list already supported — no change, but values must be JSON-safe strings. |
| Render the new identity free-text on the broadcast lower-third | Browser (`overlay-render.js` `renderIdentity`) | — | Client owns layout/aliases (D-08 verbatim-echo contract); `createTextNode` sink. |
| Render the `overlay.txt` text fallback | Pure render (`score_render.render_overlay_text`) | — | Display-only, reads flat scalar keys only; single-line + `_clean` bound preserved. |
| HTML-escape free-text at the form preview | Browser (`score-entry.js` `nomeEcho`) | — | `textContent` sink already correct; extend to new fields. |
| Freeze the contract / prove regression | Tests (pytest + node behavior harness) | — | The actual phase deliverable; gates sign-off (D-05/06/07). |

## Standard Stack

No new packages. The entire phase is buildable on the already-present, already-verified stack.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `decimal` | (stdlib) | Decimal-string subkeys (D-03) | Already the compute authority; `str(Decimal)` is the serialization shape (`app._profile_to_json` precedent). `[VERIFIED: src/segugio/ui/score_calc.py]` |
| Python stdlib `json` (via `opcomm.atomic`) | (stdlib) | `score.json` write of nested `fields` | `write_score` already `json.dumps`-es a free-form dict; nested dict/list round-trips. `[VERIFIED: src/segugio/opcomm/channel.py:114-134]` |
| Flask | installed | `/score`, `/overlay-json`, `/overlay` routes | Imported INSIDE `create_app` (crash-isolation); **no route change needed** for the subkeys. `[VERIFIED: src/segugio/ui/app.py:203-211]` |
| Vanilla ES2020 (no build) | — | `overlay-render.js` identity render; `score-entry.js` form preview | `textContent`/`createTextNode`/`createElementNS` sinks already in place. `[VERIFIED: src/segugio/ui/static/overlay-render.js:143-163]` |
| `node` (dev only) | v24.16.0 (per v1.3 SUMMARY) | JS behavior / fake-DOM tests | `subprocess`-driven, gated by `shutil.which("node")`; the DOM-level XSS render assertion (D-07b) reuses this harness. `[CITED: .planning/research/v1.3/SUMMARY.md]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | installed | Golden-snapshot + regression gates | All D-05/06/07 tests. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `str(Decimal)` subkey values | raw `Decimal` objects | **Rejected** — `json.dumps` raises `TypeError` on a raw `Decimal` → unhandled 500 on `write_score`. Decimal-string is the locked transport shape (D-03). |
| New top-level keys for per-throw score | `throws[i]["score"]` co-located on the throw entry | Co-located keeps `throws[]` self-describing and avoids a parallel array that can desync. |

**Installation:** None. `npm install` / `pip install` not required — zero new runtime dependency (D-09).

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages (D-09 forbids any new runtime dependency; dev tooling `node`/`pytest` already present). No registry verification required.

## Current Contract Ground Truth (the literal freeze targets)

### `/overlay-json` top-level response key set — D-05 freeze target #1
`get_overlay_json` (`src/segugio/ui/app.py:402-424`) returns **exactly these 6 keys**, already pinned by `tests/test_ui_overlay_json.py::test_overlay_json_payload_shape` (line 119):

```
discipline, fields, running, started_at, server_now, gen
```

- `fields` is `s.fields` echoed **verbatim** — no server-side alias resolution (D-08). New subkeys flow through with **zero route change**. `[VERIFIED: src/segugio/ui/app.py:415-419]`
- `Cache-Control: no-store` on every response. `read_score`/`read_overlay_run` are never-raise safe-default readers; a torn/absent file → safe-default payload, never a 500. **Do not add `json.load`/`open` in the route.** `[VERIFIED: src/segugio/ui/app.py:410-423]`

### Per-discipline flat `fields` keys `compute()` currently emits — D-05 freeze target #2
`compute()` does `out = dict(fields or {})` then layers flat keys (`src/segugio/ui/score_calc.py:270-363`). The **exact** keys per discipline (these are the byte-identical-forever set per D-04):

| Discipline | `compute()` helper | Raw keys surviving from input | Flat summary keys emitted | Notes |
|------------|--------------------|------------------------------|---------------------------|-------|
| `disc_tf` | `_compute_disc_tf` (288-315) | `throws` (raw list) | `prese`, `zona`, `totale` | `_parse_structured_inputs` passes only `throws` for disc_tf (app.py:137-141). |
| `disc_freestyle` | `_compute_freestyle` (318-333) | `team`,`dog`,`player`,`catch`,`adjustment`,`nome`,`timer` (those present) | `totale` (+ `setdefault` `nome`,`timer`) | Raw category keys survive but are NOT grouped today (D-03 adds `criteria{}`). |
| `agility` count_up | `_compute_agility` (336-363) | `tempo`,`sct`,`course_faults`,`eliminated` (those present) | `faults`, `tempo`(str), `sct`(str) | `time_faults` computed at line 346 but **never exposed** (D-03 adds `faults_breakdown{}`). |
| `agility` deduct_from_100 | `_compute_agility` | `tempo`,`sct`,`course_deductions` | `result`, `totale`, `faults`, `tempo`, `sct` | `faults` carries time-faults only. |
| `agility` eliminated | `_compute_agility` (339-342) | `eliminated` | `result`=`"E"`, `totale`=`"E"` | Short-circuits BEFORE any math. |

### `overlay.txt` single-line contract — D-06 freeze target
`render_overlay_text` (`src/segugio/ui/score_render.py:57-86`) reads ONLY flat scalar keys via `_get`:
- disc_tf → `prese` / `zona` / `totale`
- disc_freestyle → `nome` / `timer`
- agility → `tempo` / `sct`(+`SCT` alias) / `faults`

`_clean` (lines 32-46) strips CR/LF + non-printable control chars and caps each field at `_MAX_FIELD_LEN = 64`. **The new dict/list subkeys are never read by `render_overlay_text`, so `overlay.txt` stays single-line by construction** — but D-06 requires proving it after a rich POST, not assuming it.

### XSS sinks — D-07 freeze targets (all already correct)
- `overlay-render.js` `renderIdentity` (lines 143-163): competitor via `document.createTextNode(...)`; separator `span.textContent`. `fillCell` (98-119) writes values via `valueEl.textContent`. **No `innerHTML` anywhere.** `[VERIFIED]`
- `score-entry.js` `nomeEcho.textContent = nome.value` (line 425); `el()` helper writes all text via `node.textContent` (line 59); icons via `createElementNS` (63-80). **No `innerHTML` anywhere.** `[VERIFIED]`
- `overlay.html`: identity event half via `{{ event_name | default('', true) }}` (line 244, Jinja autoescaped); config blob via `{{ score_cfg | tojson }}` in `_score-entry-form.html:11`. **No `| safe`, no `{% autoescape false %}` anywhere in `src/segugio/ui`** (grep confirmed). `[VERIFIED]`

## Recommended Additive Subkey Contract (Claude's Discretion — D-03)

> These are the recommended literal key strings. The planner may adjust, but the shape intent (Decimal-string, additive, co-located) is locked.

### disc T&F — per-throw score on each `throws[]` entry
`_compute_disc_tf` already builds `per_throw: list[Decimal]` (line 290) and **discards** it after summing. Attach it:

```python
# Source: src/segugio/ui/score_calc.py _compute_disc_tf (recommended additive change)
throws = out.get("throws") or []
new_throws = []
per_throw: list[Decimal] = []
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
    # ADDITIVE: rebuild each throw dict with the per-throw computed score (Decimal STRING).
    new_throws.append({**throw, "score": str(score)})  # NEW subkey
out["throws"] = new_throws  # raw {zone,midair,corridor} preserved, +score added
# ... best-N sum unchanged → prese/zona/totale byte-identical
```

- **Recommended field name:** `score` (co-located on the throw entry). Raw `{zone, midair, corridor}` keys preserved byte-identical via `{**throw, ...}`.
- **Why rebuild the list:** `out = dict(fields)` is a *shallow* copy — the `throws` list and its dicts are shared with the caller's input. Mutating them in place would mutate the input and risk leaking into the advisory-mirror parity. Build new dicts.

### freestyle — `criteria{}` of per-category snapped values
`_compute_freestyle` already snaps each category (`snapped = value.quantize(inc, ...)`, line 323) and **discards** the per-category value. Collect them:

```python
# Source: src/segugio/ui/score_calc.py _compute_freestyle (recommended additive change)
total = Decimal("0")
criteria = {}  # NEW
for name, _cmin, _cmax, inc in profile.freestyle_cats:
    value = _to_decimal(out.get(name)) or Decimal("0")
    snapped = value.quantize(inc, rounding=ROUND_HALF_UP) if inc != 0 else value
    total += snapped
    criteria[name] = str(snapped)  # NEW: Decimal STRING
# ... freestyle_max clamp + adjustment unchanged → totale byte-identical
out["criteria"] = criteria  # NEW top-level subkey
```

- **Recommended key:** top-level `criteria` (dict of `{category_name: "<Decimal string>"}`).

### agility — `faults_breakdown{}` of `{course, time}`
`_compute_agility` computes `time_faults` (line 346) and **never exposes** it. Split:

```python
# Source: src/segugio/ui/score_calc.py _compute_agility (recommended additive change)
# (after the elimination short-circuit, which should NOT emit faults_breakdown)
time_faults = _time_faults(profile.time_fault_rate, run, sct)
if model == AgilityModel.count_up:
    course_faults = _to_decimal(out.get("course_faults")) or Decimal("0")
    out["faults"] = str(int(course_faults) + time_faults)
    out["faults_breakdown"] = {"course": str(int(course_faults)), "time": str(time_faults)}  # NEW
else:  # deduct_from_100
    course_deductions = _to_decimal(out.get("course_deductions")) or Decimal("0")
    # ... result/totale/faults unchanged
    out["faults_breakdown"] = {"course": str(course_deductions), "time": str(time_faults)}  # NEW
```

- **Recommended key:** top-level `faults_breakdown` = `{"course": "<str>", "time": "<str>"}`.
- **Elimination case:** OMIT `faults_breakdown` on elimination (the run short-circuits to `"E"` before any time math at lines 339-342) — there is no meaningful course/time split. Document this so the snapshot test does not assert it on the eliminated branch.

### New free-text identity fields (D-01)
- **Recommended keys:** `cane` (dog), `conduttore` (handler), `giudici` (judges) — Italian, matching the project language, and **collision-free**. ⚠️ Do NOT name the dog field `dog`: `dog` is already a **freestyle category key** (`profile.freestyle_cats` → `("dog", …)`, score_calc.py:391). Reusing it would collide.
- **Wiring:** add the new keys to the passthrough lists in `_parse_structured_inputs` (`src/segugio/ui/app.py:142-156`) for the relevant disciplines (identity applies to all three per D-01: "competitor for ALL disciplines" — overlay-render.js:138-142). `compute()` carries them verbatim via `out = dict(fields)`. The route echoes them verbatim.
- **Renderer (overlay-render.js `renderIdentity`, lines 143-163):** today `competitor = scvGet(fields, "nome")`. Extend to build the competitor string from `cane`/`conduttore` with a documented format (Claude's discretion — e.g. `cane` and `conduttore` joined, falling back to `nome` for the freestyle routine name). Every value MUST stay on the `scvGet → createTextNode` path.
- **Judges (`giudici`):** data-only — carried into `score.json`/`/overlay-json` `fields` but the renderer MUST NOT render it on the lower-third (D-01 / deferred). It surfaces only in the entry form.

## Architecture Patterns

### System Architecture Diagram

```
                          ENTRY FORM (score-entry.js)
   operator input ──► collectRaw() ──► POST /score (JSON, RAW inputs only)
        │                                      │
        │ (advisory mirror, score-calc.js)     ▼
        │                              app.post_score (app.py:317)
        │                                      │
        │                          _parse_structured_inputs  ◄── NEW free-text keys added here
        │                                      │   (cane/conduttore/giudici)
        │                                      ▼
        │                          score_calc.validate ── errors? ──► 400 (write NOTHING)
        │                                      │ valid
        │                                      ▼
        │                          score_calc.compute  ◄── NEW subkeys emitted here
        │                                      │   (throws[].score / criteria{} / faults_breakdown{})
        │                                      ▼
        │                          _write_score_doc (app.py:310)
        │                          ├─► write_score → score.json   (json.dumps, nested OK)
        │                          ├─► atomic_write_text → overlay.txt  (render_overlay_text, flat keys only)
        │                          └─► _bump_score_gen (gen++, run-state preserved)
        ▼                                      │
   nomeEcho (textContent)                      ▼
                                    GET /overlay-json (echo s.fields VERBATIM + 6-key envelope)
                                               │
                                               ▼
                                    overlay-render.js poll loop
                                    ├─► renderIdentity (createTextNode) ◄── NEW free-text sink
                                    ├─► renderCells (textContent, flat keys)
                                    └─► timer (rAF, no data baked into /overlay host page)
```

### Recommended Project Structure
No new files. Changes land in existing modules:
```
src/segugio/ui/
├── score_calc.py        # _compute_disc_tf / _compute_freestyle / _compute_agility — add subkeys
├── app.py               # _parse_structured_inputs — add free-text passthrough keys
└── static/
    ├── overlay-render.js # renderIdentity — combine cane/conduttore (createTextNode)
    └── score-entry.js    # add cane/conduttore/giudici inputs (el() helper, textContent)
tests/
├── test_ui_overlay_json.py        # + golden-snapshot of legacy key set (D-05)
├── test_ui_overlay_render.py      # + overlay.txt single-line after rich POST (D-06)
├── test_overlay_fallback_gate.py  # + rich-POST overlay.txt regression (D-06)
├── test_overlay_html_sink_gate.py # + DOM-level crafted-<script> render (D-07b)
├── test_score_calc.py             # + subkey unit assertions per discipline (D-03)
└── _score_fixtures.py             # reuse/extend FIXTURES with expected subkeys
```

### Pattern 1: Additive emit at the point the value already exists
**What:** Attach the discarded intermediate (snapped category / per-throw score / time-faults) as a `str(Decimal)` subkey, never recompute.
**When to use:** All three D-03 subkeys.
**Example:** see the three code blocks above — each reuses a value already computed in the existing loop.

### Pattern 2: Verbatim passthrough (no route change)
**What:** `compute()` does `out = dict(fields)`, the route echoes `s.fields` verbatim. New keys reach the client with zero route edit.
**Why it matters:** The 6-key `/overlay-json` envelope is frozen (D-05); enrichment happens entirely inside `fields`.

### Anti-Patterns to Avoid
- **Raw `Decimal` in a subkey:** `json.dumps` raises `TypeError` → 500 on `write_score`. Always `str(...)`. `[VERIFIED: opcomm.channel.write_score uses plain json]`
- **Mutating the input `throws` list in place:** `out = dict(fields)` is shallow; rebuild throw dicts (`{**throw, "score": ...}`).
- **Adding a new top-level `/overlay-json` key:** breaks the frozen 6-key envelope. Enrich inside `fields` only.
- **Naming the dog field `dog`:** collides with the freestyle `dog` category key.
- **Reading a subkey in `render_overlay_text`:** would risk passing a dict/list to `_clean` (which `str()`-es it into the line) — keep the text fallback on flat scalar keys only.
- **`json.load`/`open` in `get_overlay_json`:** bypasses the never-raise safe-default boundary (Pitfall 5 from v1.3 SUMMARY).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Decimal arithmetic for subkeys | float math / manual rounding | the existing `Decimal` values in `compute()` | Float drift re-introduces the exact bug v1.3 paid to retire (Pitfall 2). |
| HTML escaping of free-text | manual `.replace('<','&lt;')` | `textContent`/`createTextNode` (already in place) | DOM text nodes are inert by construction; manual escaping is bypassable. |
| JSON serialization of nested `fields` | custom encoder | `write_score` (`json.dumps`) | Already serializes free-form nested dict/list; just pass strings. |
| Single-line/length bound on overlay.txt | new sanitizer | `_clean` (caps 64, strips control chars) | Already the shipped T-05-05-02 mitigation. |
| Fake-DOM XSS render harness | a real browser / Playwright | the node fake-DOM in `tests/test_ui_score_entry.py:148-256` + `tests/test_ui_overlay_render.py:321` | Both harnesses already exercise `mount()`/`createRenderer()` headless; reuse for D-07b. |

**Key insight:** Everything this phase needs already exists and is already correct — the phase *grows the data* and *proves the contract*, it does not build new machinery.

## Runtime State Inventory

> Additive data-model phase (not a rename). Included for completeness because existing on-disk `score.json` predates the new subkeys.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing `score.json` on disk written by the pre-subkey `compute()` lacks `throws[].score`/`criteria{}`/`faults_breakdown{}`. | **None** — readers tolerate absent subkeys: `overlay-render.js` uses `scvGet`/`renderCells` over flat keys (subkeys are optional consumers); `render_overlay_text` reads flat keys only; `get_overlay_json` echoes whatever is on disk. No data migration. The next `POST /score` re-writes with subkeys. |
| Live service config | None — the only score state is `score.json`/`overlay.txt`/`overlay_run.json` in the opcomm dir. | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | None — no new field maps to a secret/env name. | None. |
| Build artifacts | None — no package rename, no egg-info, pure source edit. | None. |

**Nothing requires a data migration** — verified by tracing every reader (`render_overlay_text`, `get_overlay_json`, `overlay-render.js`) to confirm each defaults gracefully on an absent subkey.

## Common Pitfalls

### Pitfall 1: Raw Decimal leaks into a subkey
**What goes wrong:** `out["criteria"] = {name: snapped}` (Decimal object, not str) → `write_score` → `json.dumps` raises `TypeError: Object of type Decimal is not JSON serializable` → unhandled 500 (violates "nessun crash ammesso").
**Why it happens:** The flat keys are already `str(...)`; it's easy to forget the new subkeys need the same.
**How to avoid:** `str(...)` every Decimal subkey value. Mirror the `app._profile_to_json` precedent (every numeric stringified).
**Warning signs:** A `POST /score` returns 500 instead of 204; `test_imports.py` rich-POST round-trip fails.

### Pitfall 2: A flat key shifts value/format and breaks round-trip equality
**What goes wrong:** Refactoring `_compute_disc_tf` to build `new_throws` accidentally changes `zona`/`totale` string (e.g. quantizing) → Phase-16 round-trip equality test breaks.
**Why it happens:** Editing the loop that also computes `band_total`/best-N.
**How to avoid:** Keep the sum/cap/best-N logic byte-identical; only ADD the per-throw `score` and rebuild dicts. Run `test_score_calc.py` + `test_ui_score_authoritative.py::test_round_trip_total_equality` after the edit.
**Warning signs:** `test_round_trip_total_equality` or `test_csen_tf_best5` (`totale == "19.0"`) fail.

### Pitfall 3: overlay.txt gains a second line or a dict spills into it
**What goes wrong:** Someone adds a subkey to `render_overlay_text`'s `_get` call list, or the free-text combine introduces a newline.
**Why it happens:** Over-eager "show the rich data on the text fallback."
**How to avoid:** `render_overlay_text` stays flat-scalar-only; `_clean` already strips `\r\n`. D-06 test asserts `"\n" not in line` and non-empty after a rich POST per discipline.
**Warning signs:** `test_overlay_txt_persists_last_score_after_simulated_death` shows multi-line content.

### Pitfall 4: New free-text reaches the DOM via a non-textContent path
**What goes wrong:** A crafted `<script>` `cane`/`conduttore` value renders live because a contributor used `innerHTML`/`insertAdjacentHTML` for the new identity combine.
**Why it happens:** The combine is new code; the existing `renderIdentity` is safe but the extension might not be.
**How to avoid:** Route every new value through `scvGet → createTextNode`. D-07a grep guard + D-07b DOM render assertion catch it.
**Warning signs:** `test_no_innerhtml_sink` fails; the DOM render harness finds a child element instead of a single text node.

### Pitfall 5: Crash-isolation breach
**What goes wrong:** Importing `segugio.config` or a heavy module to resolve the new fields at module top.
**How to avoid:** The subkeys are produced entirely inside pure `score_calc.compute()`; the free-text fields are plain dict passthrough. No new import. `test_imports.py` (`PHASE1_SURFACE` + heavy-absent rich POST) stays green (D-09).
**Warning signs:** `test_console_resolves_with_heavy_stack_and_numpy_absent` fails.

## Code Examples

### Golden-snapshot of the legacy `/overlay-json` key set (D-05) — extends `tests/test_ui_overlay_json.py`
```python
# Pattern: POST a rich body per discipline, assert the legacy flat keys are a PRESERVED
# subset (rename/removal fails) AND the new subkeys are present alongside them.
LEGACY_FLAT_KEYS = {
    "disc_tf": {"throws", "prese", "zona", "totale"},
    "disc_freestyle": {"nome", "timer", "totale"},  # + raw category keys present
    "agility_count_up": {"tempo", "sct", "faults"},
}

def test_overlay_json_envelope_frozen(client):
    c, _ = client
    data = c.get("/overlay-json").get_json()
    assert set(data) == {"discipline", "fields", "running", "started_at", "server_now", "gen"}

def test_disc_tf_legacy_keys_preserved_and_subkey_added(client):
    c, _ = client
    c.post("/score", json={"discipline": "disc_tf", "throws": [{"zone": 4, "midair": True}]})
    fields = c.get("/overlay-json").get_json()["fields"]
    assert LEGACY_FLAT_KEYS["disc_tf"] <= set(fields)         # no legacy key removed/renamed → CI fails
    assert fields["prese"] == "1" and "totale" in fields      # values byte-identical to flat contract
    assert fields["throws"][0]["zone"] == 4                   # raw throw preserved
    assert fields["throws"][0]["score"] == "4.5"              # NEW additive per-throw score (Decimal str)
```

### overlay.txt single-line regression after a rich POST (D-06) — extends `test_overlay_fallback_gate.py`
```python
def test_overlay_txt_single_line_after_rich_post(file_channel):
    app = create_app(str(file_channel["dir"]), cam_ids=["cam_wide"])
    c = app.test_client()
    c.post("/score", json={"discipline": "disc_tf", "throws": [{"zone": 4}, {"zone": 3}],
                           "cane": "Rex", "conduttore": "Anna"})
    line = file_channel["overlay"].read_text(encoding="utf-8")
    assert line and "\n" not in line and "\r" not in line       # single non-empty line
    # each rendered field is length-bounded (<=64) by _clean — assert no field overflowed
```

### DOM-level crafted-`<script>` render assertion (D-07b) — extends `test_overlay_html_sink_gate.py`
```python
# Reuse the node fake-DOM (tests/test_ui_overlay_render.py:321 / test_ui_score_entry.py:148).
# Drive renderIdentity with a crafted free-text value and assert it lands as ONE text node
# (textContent === payload) with NO child element — inert escaped text on the lower-third.
# Mirror on score-entry.js: dispatch 'input' with a <script> nome and assert
# nomeEcho.textContent === payload AND nomeEcho.children.length === 0.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat-only `fields` (`totale`/`faults`/…) | Additive structured subkeys alongside flat keys | This phase (Phase 18) | Richer downstream consumers without breaking the frozen contract. |
| Legacy urlencoded flat-key `POST /score` | Authoritative structured JSON only | Phase 17 (D-11) | The flat shape is now rejected (`test_legacy_flat_keys_now_rejected`); only the structured body path exists — the subkeys ride it. |

**Deprecated/outdated:** none introduced; this phase removes nothing.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommended free-text key names `cane`/`conduttore`/`giudici` (Italian, collision-free). | Subkey Contract | Low — Claude's discretion (D-01); planner may rename. Only hard constraint: avoid `dog` (freestyle collision). |
| A2 | `faults_breakdown{}` is OMITTED on the agility elimination branch. | Subkey Contract | Low — a reasonable reading of D-03 (no run = no split); planner/snapshot test must agree on whether it appears as `{"course":"E","time":"E"}` or is absent. |
| A3 | Combined dog/handler display format in `renderIdentity` is unspecified (discretion). | Subkey Contract | Low — D-01 explicitly leaves formatting to the renderer. |

**If A2 matters:** confirm with the planner whether the eliminated agility doc should still carry `faults_breakdown` — it affects one snapshot assertion.

## Open Questions

1. **Should the per-discipline golden snapshot assert an EXACT `fields` key set, or a preserved-subset?**
   - What we know: D-05 says "rename/removal must fail CI." An exact-set assertion would ALSO fail on a future *additive* key (false positive); a subset assertion (`LEGACY <= set(fields)`) fails only on removal/rename.
   - Recommendation: assert `LEGACY_FLAT_KEYS[discipline] <= set(fields)` (catches removal/rename) PLUS explicit `assert "throws"/"criteria"/"faults_breakdown" in fields` for the new keys. This freezes the legacy set without blocking future additive growth — matching D-04's "strictly additive" intent.

2. **Do the new free-text fields apply to all three disciplines' `_parse_structured_inputs` branches, or only where an identity line shows?**
   - What we know: `renderIdentity` runs for ALL disciplines (overlay-render.js:138). D-01 says competitor identity is universal.
   - Recommendation: add `cane`/`conduttore`/`giudici` passthrough to all three branches of `_parse_structured_inputs` (or hoist a shared identity-key list applied regardless of discipline) so identity works on disc_tf/freestyle/agility uniformly.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + Flask + pytest | all tests/code | ✓ | installed | — |
| `node` | JS behavior + DOM-XSS render tests (D-07b) | ✓ (per v1.3 SUMMARY) | v24.16.0 | `@pytest.mark.skipif(shutil.which("node") is None)` — node-gated tests skip cleanly; the source-grep guards (D-07a) still run without node. |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** node-gated DOM render assertions degrade to skip if node is absent (existing `_requires_node` precedent) — but the pure-Python grep guards still enforce the sink discipline.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ node behavior harness via `subprocess`, gated by `shutil.which("node")`) |
| Config file | repo `pyproject.toml`/`pytest` config (existing) |
| Quick run command | `pytest tests/test_score_calc.py tests/test_ui_overlay_json.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req / SC | Behavior | Observable signal (proves it) | Test Type | Automated Command | File Exists? |
|----------|----------|-------------------------------|-----------|-------------------|-------------|
| D-03 disc_tf | per-throw `score` emitted as Decimal string alongside raw throw | `compute()` out `throws[i]["score"] == "4.5"`, raw `{zone,…}` intact | unit | `pytest tests/test_score_calc.py -k tf -x` | ✅ extend |
| D-03 freestyle | `criteria{}` per-category snapped values | `compute()` out `criteria["team"] == "8.50"` | unit | `pytest tests/test_score_calc.py -k freestyle -x` | ✅ extend |
| D-03 agility | `faults_breakdown{course,time}` | `compute()` out `faults_breakdown == {"course":"5","time":"5"}` | unit | `pytest tests/test_score_calc.py -k agility -x` | ✅ extend |
| D-04 / SC#1 | flat keys byte-identical; round-trip equality holds | `test_round_trip_total_equality` green; `totale=="19.0"` | integration | `pytest tests/test_ui_score_authoritative.py -x` | ✅ green, keep |
| D-05 / SC#1 | legacy `/overlay-json` key set frozen; rename/removal fails | golden-snapshot subset assertion + 6-key envelope | integration | `pytest tests/test_ui_overlay_json.py -x` | ✅ extend |
| D-06 / SC#2 | overlay.txt single non-empty line after rich POST | `"\n" not in line and line` per discipline | integration | `pytest tests/test_overlay_fallback_gate.py tests/test_ui_overlay_render.py -x` | ✅ extend |
| D-06 / SC#3 | `/overlay` host page bakes NO score data | `test_ui_overlay_page` assertions stay green | served-HTML | `pytest tests/test_ui_overlay_page.py -x` | ✅ green, keep |
| D-07a / SC#4 | no-`innerHTML` grep on overlay-render.js + score-entry.js | `".innerHTML" not in js`, `textContent` present | source grep | `pytest tests/test_overlay_html_sink_gate.py -k innerhtml` | ✅ extend to score-entry.js |
| D-07b / SC#4 | crafted `<script>` renders inert on lower-third AND form preview | node fake-DOM: `textContent === payload`, `children.length === 0` | node behavior | `pytest tests/test_overlay_html_sink_gate.py -k render` | ❌ Wave 0 (new node assertion) |
| D-09 | rich POST round-trips with heavy stack absent; subkeys need no new import | `test_console_resolves_with_heavy_stack_and_numpy_absent` green | import smoke | `pytest tests/test_imports.py -x` | ✅ green, keep |

### Sampling Rate
- **Per task commit:** `pytest tests/test_score_calc.py tests/test_ui_overlay_json.py -x -q`
- **Per wave merge:** `pytest tests/test_ui_overlay_render.py tests/test_overlay_fallback_gate.py tests/test_overlay_html_sink_gate.py tests/test_ui_score_authoritative.py tests/test_imports.py -q`
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] DOM-level crafted-`<script>` render assertion for the entry-form preview (`nomeEcho`) and the overlay lower-third (`renderIdentity`) — new node fake-DOM driver in `tests/test_overlay_html_sink_gate.py` (D-07b). The harness itself is a copy-adapt of the existing `tests/test_ui_score_entry.py:148-256` `_FAKE_DOM` and `tests/test_ui_overlay_render.py:321` fake DOM — no new framework.
- [ ] Golden-snapshot per-discipline key-set test in `tests/test_ui_overlay_json.py` (D-05).
- [ ] No framework install needed — pytest + node already present.

*(All other validation reuses existing, passing test infrastructure.)*

## Security Domain

> `security_enforcement` not explicitly `false` → included. The single live threat for this phase is HTML injection of operator free-text into the broadcast overlay (T-14-xss / RBT-06 SC#4).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `score_calc.validate` (per-field, server-authoritative, 400-write-nothing); free-text identity fields are display-only (no parsing) but pass through the same write path. |
| V5 Output Encoding / Injection | **yes (primary)** | `textContent`/`createTextNode`/`createElementNS` (JS sinks); Jinja autoescape + `| tojson` (server); `_clean` control-char strip + 64-cap (overlay.txt). NO `innerHTML`, NO `| safe`. |
| V2 Authentication | no | LAN trust boundary, no auth in v1 (documented, T-05-05-04) — unchanged. |
| V6 Cryptography | no | none. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Crafted `<script>` in dog/handler/judges free-text → broadcast HTML injection | Tampering / Elevation | `createTextNode` sink (overlay) + `textContent` (form preview); D-07a grep guard + D-07b DOM render assertion. |
| Operator value injects extra overlay.txt line / overflows OBS text source | Tampering | `_clean` strips `\r\n` + control chars, caps 64 (T-05-05-02); D-06 single-line regression. |
| Non-finite / non-dict torn `score.json` poisons `/overlay-json` | Denial of Service | never-raise readers + `parse_constant` reject + dict-guard (already shipped: `test_overlay_json_rejects_non_finite_started_at`, `test_overlay_json_non_dict_fields_safe_defaulted`). |
| Raw `Decimal` subkey → 500 on write | Denial of Service | `str(Decimal)` every subkey value (Pitfall 1). |

## Sources

### Primary (HIGH confidence — in-repo, read 2026-06-27)
- `src/segugio/ui/score_calc.py` — `compute()` flat-key emit sites, per-discipline helpers, discarded intermediates (`per_throw`/`snapped`/`time_faults`), `CSEN_DISC_PROFILE` field collisions.
- `src/segugio/ui/app.py` — `post_score`, `_parse_structured_inputs`, `_write_score_doc`, `get_overlay_json` (verbatim 6-key echo).
- `src/segugio/ui/score_render.py` — `render_overlay_text` flat-key reads, `_clean` 64-cap/control-strip.
- `src/segugio/ui/static/overlay-render.js` — `renderIdentity`/`fillCell` `textContent`/`createTextNode` sinks.
- `src/segugio/ui/static/score-entry.js` — `el()`/`nomeEcho`/`createElementNS` sinks.
- `src/segugio/ui/templates/overlay.html`, `_score-entry-form.html`, `score-entry.html` — Jinja autoescape + `| tojson`, no `| safe`.
- `src/segugio/opcomm/channel.py` (write_score/read_score) + `records.py` (`ScoreDoc.fields` free-form dict) — JSON round-trip of nested fields.
- `tests/test_ui_overlay_json.py`, `test_ui_overlay_render.py`, `test_overlay_fallback_gate.py`, `test_ui_overlay_page.py`, `test_overlay_html_sink_gate.py`, `test_ui_score_authoritative.py`, `test_score_calc.py`, `test_ui_score_entry.py`, `test_imports.py`, `_score_fixtures.py` — extension points + fake-DOM harness precedents.

### Secondary (MEDIUM confidence)
- `.planning/research/v1.3/SUMMARY.md` — additive-data-model rationale, crash-isolation invariant, node v24.16.0 dev runtime, Pitfalls 1/2/4/5.
- `.planning/REQUIREMENTS.md` (RBT-09) + `18-CONTEXT.md` (D-01..D-09).

## Metadata

**Confidence breakdown:**
- Current contract / freeze targets: HIGH — read from source this session with file:line.
- Additive subkey shape: HIGH (intent locked D-03) / key names MEDIUM (Claude's discretion).
- Pitfalls: HIGH — anchored to shipped tests + the JSON-serialization fact.
- Regression test patterns: HIGH — extend existing, passing precedents.

**Research date:** 2026-06-27
**Valid until:** ~2026-07-27 (stable; the only churn risk is further edits to `compute()`/the routes before the phase executes).
