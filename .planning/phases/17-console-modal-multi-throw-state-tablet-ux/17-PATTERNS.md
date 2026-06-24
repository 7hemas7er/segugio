# Phase 17: Console Modal, Multi-throw State & Tablet UX - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 6 (1 new + 4 modified + 1 verify) + 1 drift-guard reference
**Analogs found:** 6 / 6 (every file is an in-repo continuation — no greenfield)

> This phase is almost entirely **modify-in-place**. The "analog" for each modified
> file is the file itself (the proven Phase-16 / Phase-9 shape it extends), so the
> excerpts below are the EXACT in-repo lines the planner edits, not a stand-in.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/ui/templates/_score-entry-form.html` (NEW) | template partial | request-response (host markup) | `src/segugio/ui/templates/score-entry.html` lines 81-93 (the `#score-cfg` blob + `#score-entry-root` + `#publish-banner` + 2 `<script>` tags) | exact (extract-from-source) |
| `src/segugio/ui/static/score-entry.js` (MODIFY) | served JS module | event-driven (DOM) + request-response (POST) | itself (the `mount(root, cfg)` factory; in-session `throwRows`; `submit()`; banner fallback) | exact (in-place extension) |
| `src/segugio/ui/templates/score-entry.html` (MODIFY) | served page template | request-response | itself; the `{% include %}` mechanic mirrors how `console.html` reuses no partial today (new include site) | exact |
| `src/segugio/ui/templates/console.html` (MODIFY) | served page template | event-driven (poll loop) + request-response | itself: retire `#form-score` (262-302) + submit JS (320-348); the readout/poll pattern is the existing `pollStatus`/`pollPreview` loop (624-799); modal CSS reuses the `.sidebar-block` card chrome (78-79) | exact |
| `src/segugio/ui/app.py` (MODIFY) | Flask route factory | request-response | itself: retire `_is_legacy_score_post` (139-153) + its branch in `post_score` (364-382); reuse factory-time `_score_cfg` (252-256) + `/overlay-json` (441-463) | exact |
| `tests/test_imports.py` (VERIFY/EXTEND) | test (crash-isolation gate) | batch (import smoke) | itself: `test_console_resolves_with_heavy_stack_and_numpy_absent` (88-150) — esp. the POST /score round-trip at 125-129 | exact |
| `src/segugio/ui/static/score-calc.js` | served JS module (UNCHANGED) | transform (pure calc) | n/a — drift-guard reference only | — |

## Pattern Assignments

### `src/segugio/ui/templates/_score-entry-form.html` (NEW — template partial, D-08)

**Analog (extraction source):** `score-entry.html` lines 81-93 — the host markup is
already isolated to exactly four nodes + two script tags. The partial is a verbatim
cut of these; BOTH `score-entry.html` and `console.html`'s `<dialog>` `{% include %}` it.

**Markup to extract** (`score-entry.html:81-93`):
```html
<!-- The active scoring profile + valid-discipline list, injected as decimal STRINGS (D-07). -->
<script type="application/json" id="score-cfg">{{ score_cfg | tojson }}</script>

<!-- The component mounts its entire field set here. The host carries no form field of its own. -->
<div id="score-entry-root"></div>

<!-- Persistent publish banner (D-05) ... -->
<div id="publish-banner"></div>

<!-- Advisory calc port first (defines window.SEGUGIO_SCORE_CALC), then the component. -->
<script src="/static/score-calc.js"></script>
<script src="/static/score-entry.js"></script>
```

**Critical constraint (D-08/D-10):** the `score_cfg | tojson` filter and the two
`/static/...` relative script paths must be IDENTICAL in both hosts — that is the
whole anti-drift point. Both templates receive `score_cfg` from the same factory
blob (see app.py assignment below). The partial adds ZERO new external/CDN asset (D-10).

**`{% include %}` site pattern:** there is no existing partial-include in the repo;
the include is a net-new Jinja directive. Plain `{% include "_score-entry-form.html" %}`
resolves from the same `templates/` dir Flask already serves (`render_template` in app.py).

---

### `src/segugio/ui/static/score-entry.js` (MODIFY — served JS module)

**Analog:** itself. All three P17 additions go INSIDE the one `mount(root, cfg)`
closure — NO fork, NO second module (the SCV-02 one-renderer rule).

**Re-mountable mount + clear-without-innerHTML** (`score-entry.js:96-109`) — the
console modal calls this SAME factory on dialog-open (D-09):
```js
function mount(root, cfg) {
  if (!root) return null;
  ...
  // Clear any prior mount (re-mountable for the P17 modal) WITHOUT innerHTML.
  while (root.firstChild) root.removeChild(root.firstChild);
  // In-session throw list for disc T&F (D-01a — in memory only, NO localStorage).
  const throwRows = []; // [{ row, zoneSel, midair, corridor }]
```
P17 (D-02/D-03): `throwRows` gains localStorage persistence — write the draft on
every `addThrowRow`/remove/`input` mutation; restore it at the END of `mount()`
(silent auto-restore) by replaying saved rows through `addThrowRow`.

**Banner element resolution — host-or-self fallback** (`score-entry.js:181-187`) —
already works in BOTH hosts (modal has no host `#publish-banner` → component owns one):
```js
const banner =
  (typeof document !== "undefined" && document.getElementById("publish-banner")) ||
  (function () { const b = el("div", { id: "publish-banner" }); root.appendChild(b); return b; })();
```
D-09 keeps ONE banner resolution; do not add a second path.

**The publish button + click handler** (`score-entry.js:172-177`) — P17 (D-05)
replaces the single always-fires click with the **two-step confirm** (morph to a
`button.danger` "Conferma invio", auto-revert timer, only 2nd tap calls `submit`):
```js
const publishBtn = el("button", { type: "button" }, "Manda in onda");
publishBtn.addEventListener("click", submit);   // P17: wrap in arm→confirm gate
```
Use the `button.danger` token already defined in console.html:41 (`background: #9b2c2c`).
The button stays ALWAYS enabled (Phase-16 D-04) — the confirm is the gate, never a disable.

**submit() — clear draft ONLY on 2xx** (`score-entry.js:496-531`) — P17 (D-04):
in the `resp.ok` branch (line 507-510) add the localStorage clear; the 400 and
`.catch()` branches KEEP the draft (nothing lost on a rejected/failed submit):
```js
.then((resp) => {
  if (resp.ok) {
    setBanner("✓ In onda", "success");   // P17: localStorage.removeItem(DRAFT_KEY) HERE only
    return null;
  }
  // 400 / network error branches: KEEP the draft (D-04) ...
```

**Enter-suppression (D-06):** add a `keydown` guard in `mount()` (Enter never reaches
`submit` / never arms-or-confirms). No existing handler binds Enter today, so this is
additive — a single `root.addEventListener("keydown", e => { if (e.key === "Enter") e.preventDefault(); })`
scoped to text inputs, never the publish path.

**Never-raise reader discipline (D-02):** the restore read mirrors the server-side
`read_overlay_run`/`read_score` safe-default boundary — wrap `JSON.parse(localStorage.getItem(...))`
in try/catch → empty draft, exactly like the existing `autoMount` cfg parse (`score-entry.js:558-564`):
```js
try { cfg = JSON.parse(el2.textContent); } catch (_e) { cfg = {}; }
```

**XSS discipline (D-10):** every new value still reaches the DOM via `textContent`/
`createElementNS` — the served-JS test forbids `innerHTML` outright (file header lines 15-20).
The localStorage draft holds operator-typed strings; on restore they flow back through
the same `el()`/`textContent` sinks, never a markup string.

---

### `src/segugio/ui/templates/score-entry.html` (MODIFY — served page template)

**Analog:** itself. Lines 81-93 (the host markup) are CUT into the new partial and
replaced by a single `{% include "_score-entry-form.html" %}`. The page keeps its
`<style>` token set (lines 11-72) and `<h1>`/`.page` wrapper (75-89) — that CSS stays
on the dedicated page; the partial carries only the four host nodes + scripts.

The auto-mount on `DOMContentLoaded` stays for `/score-entry` (D-09) — it lives in
score-entry.js (572-578), not the template, so no template change is needed for it.

---

### `src/segugio/ui/templates/console.html` (MODIFY — served page template)

**Analog:** itself (Phase-9 tablet console).

**RETIRE: legacy inline `#form-score`** (`console.html:262-302`) — the whole `<form
id="form-score">` fieldset (discipline `<select>` + 3 `.campi` fieldsets + the
manual `totale` input + submit button) is removed and replaced by the D-07 readout +
modal button inside the `.side-col` Punteggio card.

**RETIRE: legacy submit + discipline-toggle JS** (`console.html:320-348`):
```js
const sel = document.getElementById("disciplina");
function showFields() { ... }            // retire — modal owns discipline toggle now
sel.addEventListener("change", showFields); showFields();
...
document.getElementById("form-score").addEventListener("submit", e => {  // retire whole block
  e.preventDefault();
  const data = { discipline: sel.value };
  ... post("/score", data);              // the urlencoded legacy POST — gone (D-11)
});
```
NOTE: the `post(url, data)` helper (331-335) and the `.run-btn` binding (351-352)
that REUSE it must STAY — only the `#form-score` submit listener is removed.

**REUSE: card chrome for the new readout** (`console.html:78-79`):
```css
.sidebar-block { background: #1a1d22; border: 1px solid #333; border-radius: 8px; padding: 16px; }
.sidebar-block h2 { font-size: 0.875rem; font-weight: 700; margin: 0 0 8px; color: #b9b9b9; }
```
The net-new read-only on-air readout (D-07: discipline + total) sits in the
`.side-col` Punteggio card using this existing card style.

**REUSE: the existing poll loop for the readout source (D-07a)** — model the
`/overlay-json` readout poll on the established named-interval pattern:
```js
// console.html:748-756 — startPolling/stopPolling, NAMED handles, idempotent
function startPolling() {
  stopPolling();
  previewTimer = setInterval(pollPreview, PUBLISH_MS);
  statusTimer = setInterval(pollStatus, 1000);
}
```
and the safe-coast fetch shape (`console.html:721-741`, `pollStatus`): wrap in
try/catch, `textContent` the result, `/* coast — a poll error never breaks the page */`.
Poll `/overlay-json` (app.py:441-463 — already serves `discipline` + `fields` + `gen`).

**NEW: native `<dialog>` modal (D-09/D-10)** — host the partial inside a
`<dialog id="score-dialog">{% include "_score-entry-form.html" %}</dialog>`; open it
from the "Inserisci / modifica punteggio" button with `dialog.showModal()` (native
focus-trap + Escape, no hand-rolled trap). Mount the component on the `dialog` open
event (D-09), NOT on page load (guard the score-entry.js auto-mount from firing into a
hidden dialog — the auto-mount targets `#score-entry-root`, so the dialog's root must
be populated on open, e.g. by calling `SEGUGIO_SCORE_ENTRY.mount(dialogRoot, cfg)`).

**Inject `score_cfg` into console.html:** the `index()` route must pass `score_cfg`
(see app.py change) so the included partial's `{{ score_cfg | tojson }}` resolves — same
blob as `/score-entry`.

---

### `src/segugio/ui/app.py` (MODIFY — Flask route factory)

**Analog:** itself.

**RETIRE: the legacy detector** (`app.py:139-153`) — delete `_is_legacy_score_post`
entirely (and the now-unused `_NON_SCORE_KEYS`/`_STRUCTURED_KEYS` helpers if nothing
else references them — verify with a grep before removing):
```python
def _is_legacy_score_post(raw, is_json: bool) -> bool:
    ...
    keys = set(raw.keys()) - _NON_SCORE_KEYS
    return not (keys & _STRUCTURED_KEYS)
```

**RETIRE: the branch in `post_score`** (`app.py:364-382`) — the whole
`if _is_legacy_score_post(raw, is_json):` block (the urlencoded display-only
round-trip) is removed; the authoritative path (384-393) becomes the only path:
```python
# AUTHORITATIVE path (SCC-01): validate-BEFORE-write → 400 + write NOTHING on any error
fields = _parse_structured_inputs(discipline, raw, is_json)
errors = score_calc.validate(discipline, fields, profile)
if errors:
    return (jsonify({"errors": errors}), 400)
computed = score_calc.compute(discipline, fields, profile)
_write_score_doc(ScoreDoc(discipline=discipline, fields=computed))
return ("", 204)
```

**REUSE: factory-time `_score_cfg` for BOTH hosts (D-08)** (`app.py:252-256`) — the
console route must pass the SAME blob the `/score-entry` route already passes:
```python
_score_cfg = {
    "sport": sport,
    "disciplines": _disciplines_for_sport(sport),
    "profile": _profile_to_json(profile),
}
```
The `index()` route (`app.py:315-321`) currently renders `console.html` with only
`cam_ids`; ADD `score_cfg=_score_cfg` so the included partial resolves. Mirror the
existing `/score-entry` injection (`app.py:331`):
```python
return render_template("score-entry.html", score_cfg=_score_cfg)   # the precedent to copy
```

**REUSE: `/overlay-json` as the readout source (D-07a)** (`app.py:441-463`) — no
new route; the console readout polls this existing endpoint (serves `discipline`,
`fields`, `running`, `started_at`, `server_now`, `gen` with `Cache-Control: no-store`).

---

### `tests/test_imports.py` (VERIFY/EXTEND — crash-isolation gate)

**Analog:** itself — `test_console_resolves_with_heavy_stack_and_numpy_absent`
(`test_imports.py:88-150`). The HARD gate that must stay green after the legacy
removal and the `index()`/console route touch.

**The POST /score smoke that changes meaning** (`test_imports.py:125-129`):
```python
# the display-only route today returns 204 on success ... tolerates 200/204 so Phase 16
# making the route authoritative does not break this crash-isolation gate.
resp = client.post("/score", data={"discipline": "disc_tf", "prese": "3", "zona": "2", "totale": "6"})
assert resp.status_code in (204, 200)
```
**ACTION (D-11):** with the legacy branch retired, this urlencoded flat-key POST no
longer hits a back-compat path — it now falls into `_parse_structured_inputs` for
`disc_tf` (empty `throws` for a form body) → `validate` may 400. The planner MUST
update this assertion to the new authoritative reality (e.g. POST a structured JSON
`{"discipline":"disc_tf","throws":[...]}` body, or accept a 400 for the now-invalid
flat keys). The GOAL is unchanged: the route resolves heavy-free without a 500.

**Stays untouched:** `PHASE1_SURFACE` (27-44) and the `CONSOLE_HEAVY_MODULES`
heavy-absent block (94-98) — no new module is added to the import surface (the partial
is a template, score-entry.js is served JS, neither is a Python import). `create_app`
must still build heavy-free (the `score_cfg` injection is pure stdlib `str(Decimal)`).

## Shared Patterns

### One renderer, two mounts (SCV-02) — the anti-drift spine
**Source:** `score-entry.js:11-13` (file header) + `score-entry.html:81-93` (host markup)
**Apply to:** the NEW partial + both host templates.
The SAME `mount(root, cfg)` module + the SAME Jinja partial across `/score-entry` and
the console `<dialog>` make drift structurally impossible. No second module, no copied calc.

### Never-raise reader discipline (applied client-side, D-02)
**Source (server precedent):** `app.py:441-463` (`/overlay-json` reads via never-raise
`read_score`/`read_overlay_run`, never `json.load` in the route).
**Source (client precedent):** `score-entry.js:558-564` (`try { JSON.parse } catch → {}`).
**Apply to:** the localStorage draft restore — corrupt/absent/torn value → empty draft,
NEVER throws (`localStorage.setItem` is atomic per key; the reader is try/caught).

### Server-authoritative write path (unchanged — must not regress)
**Source:** `app.py:333-393` (`_write_score_doc` + the authoritative `post_score`).
**Apply to:** nothing new writes what airs — localStorage holds ONLY the not-yet-published
draft; `POST /score` (JSON, RAW inputs) stays the sole authority; `/overlay-json` is read-only.

### XSS: textContent-only sinks, no innerHTML
**Source:** `score-entry.js:47-61` (`el()` helper, `textContent` always) + header 15-20.
**Apply to:** all P17 additions in score-entry.js (draft restore, confirm-button morph,
Enter guard). The served-JS test forbids any `innerHTML` sink in this file outright.

### Crash-isolation import allowlist (HARD gate)
**Source:** `tests/test_imports.py:88-150`.
**Apply to:** every app.py edit — `create_app` must still build with
torch/cv2/numpy/cyndilib/obsws forced absent; retiring the legacy branch and adding the
`score_cfg` render-arg to `index()` add NO module-top heavy import.

### Tablet contract — verify, don't rebuild (D-10)
**Source (reuse verbatim):** `console.html:29-39` (inputs `font-size: 1rem`/`min-height: 48px`/
`touch-action: manipulation`; buttons `min-height: 44px`; `button.danger` #9b2c2c at line 41)
and `score-entry.html:26-35` (the mirrored ≥16px input chrome).
**Apply to:** the partial + modal — add ZERO new external/CDN asset; icons stay inline SVG
(`staticIcon` in score-entry.js:63-80); focus-trap comes free from `dialog.showModal()`;
sleep/wake survival rides on the D-02/D-03 localStorage restore (no separate mechanism).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | None. Every file is an in-repo continuation; the partial extracts proven markup, the modal reuses native `<dialog>` + the existing poll/card patterns. |

## Metadata

**Analog search scope:** `src/segugio/ui/templates/`, `src/segugio/ui/static/`,
`src/segugio/ui/app.py`, `tests/test_imports.py` (the exact in-scope surface — this
phase modifies known files rather than creating greenfield ones, so a broad codebase
sweep was unnecessary).
**Files scanned:** 6 (full reads of score-entry.html, score-entry.js, console.html,
app.py, test_imports.py; header read of score-calc.js).
**Pattern extraction date:** 2026-06-24
