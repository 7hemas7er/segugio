# Phase 18: Rich Data Model & Overlay-Continuity Regression - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning

<domain>
## Phase Boundary

The richer structured score rides through the publish path **additively**, and every shipped
overlay contract is **regression-verified unbroken** (not assumed). Concretely:

- `compute()` emits new structured subkeys (`throws[]` per-throw score, freestyle `criteria{}`,
  agility `faults_breakdown{}`) into `score.json` / `/overlay-json` **alongside** the preserved
  flat summary keys — no legacy `/overlay-json` key renamed or removed.
- `overlay.txt` (OBS read-from-file fallback), `/overlay-json`, and the graphical `/overlay`
  renderer are all proven still-working after a rich `POST /score`.
- New free-text fields (dog/handler name, judges) are HTML-escaped at the sink — no `innerHTML`,
  no `| safe` — and verified inert against a crafted `<script>` payload.

**This is the last phase of v1.3 (closes RBT-09).** It is a *publish-and-render* extension: the
console still imports only `Flask + segugio.opcomm + score_calc`, the director is never touched,
transport stays fetch-polling, single on-air score only, zero new runtime dependency.

**NOT in this phase (scope guard):** roster/standings (SCM-F2), multi-judge freestyle (SCM-F1),
any new *computed* judging/adjudication. The data model grows; the product surface does not.

</domain>

<decisions>
## Implementation Decisions

### New Free-Text Fields (dog/handler name, judges)
- **D-01:** Add dog/handler as free-text that feeds the overlay's **existing** `competitor`
  identity line (`overlay-render.js` already renders a competitor/event identity band — this is
  NOT a new visible overlay element). Judges ride in `score.json` + the entry form **only** —
  they are NOT shown on the single-score broadcast overlay (showing judges would be new broadcast
  capability / clutter; deferred). How dog + handler combine into one identity display string is a
  renderer/planning detail.
- **D-02:** Every new free-text field is carried additively through the write path and is subject
  to the same XSS sink discipline as the existing identity values (see D-07).

### Structured Subkey Shape & Authority
- **D-03:** `compute()` emits the structured subkeys **server-authoritatively** as Decimal
  **strings** (keystone-consistent — the server is the sole compute authority, never float):
  - disc T&F: `throws[]` gains a **per-throw computed score** alongside the already-surviving raw
    `{zone, midair, corridor}` entries (today `out = dict(fields)` already carries raw `throws[]`).
  - freestyle: a `criteria{}` subkey holding the **per-category snapped values** (today only flat
    `totale` is emitted; the raw category keys survive but are not grouped).
  - agility: a `faults_breakdown{}` subkey splitting `{course, time}` faults (today `time_faults`
    is computed internally but never exposed).
- **D-04:** **Strictly additive** — every existing flat summary key (`prese`, `zona`, `totale`,
  `faults`, `result`, `nome`, `timer`, …) stays byte-identical in name and value. The new subkeys
  are added next to them; no rename, no removal, no reshaping of existing keys. The Phase-16
  round-trip equality (form total === `overlay.txt` line === `/overlay-json` total) must still hold.

### Regression Gate Strictness
- **D-05:** Automated **golden-snapshot** test that freezes the `/overlay-json` legacy key set so a
  future rename/removal **fails CI** (lands in / extends `tests/test_ui_overlay_json.py`).
- **D-06:** Automated `overlay.txt` regression: still a **single non-empty line**, length-bounded
  per field, after a rich `POST /score` (extends `tests/test_ui_overlay_render.py` /
  `test_overlay_fallback_gate.py`). `/overlay` host page proven to still bake in **no** score data
  (stays thin/poll-only — `test_ui_overlay_page.py`).
- **D-07 (XSS — both guards):** (a) extend the existing no-`innerHTML` served-JS grep guard to the
  new templates/fields, AND (b) add a **DOM-level crafted-`<script>` render assertion** proving the
  value renders as inert escaped text on **both** the `/overlay` lower-third AND the entry-form
  preview (`score-entry.js` `nomeEcho`); confirm Jinja **autoescape** on any server-rendered
  free-text and that `overlay.txt`'s `_clean` still strips control chars. (Builds on
  `tests/test_overlay_html_sink_gate.py`.)
- **D-08:** A **non-blocking, documented** real-OBS read-from-file rig checklist is carried forward
  (matches the prior-phase D-02 deferral pattern) — automated tests gate sign-off; the physical rig
  check is recorded but does not block phase completion.

### Crash-Isolation Invariant (inherited, must stay true)
- **D-09:** The console import surface stays `Flask + segugio.opcomm + score_calc` (pure stdlib).
  The additive subkeys are produced inside the existing pure `score_calc.compute()` — no new import,
  no config import at module top. The heavy-absent import-smoke gate (`test_imports.py`) must stay
  green, and a rich `POST /score` round-trip must resolve with the heavy stack absent.

### Claude's Discretion
- Exact JSON key names / nesting for `criteria{}` and `faults_breakdown{}`, and the per-throw
  score field name — pick the cleanest additive contract during research/planning (D-03/D-04 fix
  the shape *intent*, not the literal key strings).
- Display formatting of the combined dog/handler identity string in the renderer.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 18: Rich Data Model & Overlay-Continuity Regression" — the 4
  success criteria (additive subkeys + preserved flat keys / `overlay.txt` regression / thin
  `/overlay` / XSS-escaped free-text).
- `.planning/REQUIREMENTS.md` — **RBT-09** (the sole phase requirement: overlay.txt + `/overlay` +
  `/overlay-json` contracts unchanged & regression-verified; new free-text HTML-escaped at sink).
- `.planning/research/v1.3/SUMMARY.md` — v1.3 milestone research (publish-and-render channel,
  crash-isolation, additive-data-model rationale).

### Write path & data contract (where the additive change lands)
- `src/segugio/ui/score_calc.py` — `compute()` (`out = dict(fields)` + flat-key emit; the new
  `criteria{}` / `faults_breakdown{}` / per-throw subkeys are added here) and `validate()`.
- `src/segugio/ui/app.py` — `post_score` (authoritative validate→recompute→write), `_write_score_doc`,
  `get_overlay_json` (the `fields` verbatim echo + the legacy key contract to freeze).
- `src/segugio/ui/score_render.py` — `render_overlay_text` (the `overlay.txt` single-line renderer +
  `_clean` length/control-char bound — must stay single-line after enrichment).

### Render sinks (XSS-relevant)
- `src/segugio/ui/static/overlay-render.js` — the graphical overlay sink; **all `textContent` /
  `createTextNode`**, existing `competitor`/`event` identity line (the dog/handler target).
- `src/segugio/ui/static/score-entry.js` — the entry-form preview sink (`nomeEcho.textContent`);
  comment notes the served-JS test forbids any `innerHTML` sink outright.
- `src/segugio/ui/templates/overlay.html`, `_score-entry-form.html`, `score-entry.html` — Jinja
  hosts; confirm autoescape on any server-rendered free-text.

### Regression / XSS test precedents to extend
- `tests/test_ui_overlay_json.py` — `/overlay-json` contract (golden key-set snapshot lands here).
- `tests/test_ui_overlay_render.py`, `tests/test_overlay_fallback_gate.py` — `overlay.txt` fallback.
- `tests/test_ui_overlay_page.py` — `/overlay` host page stays thin (no baked score data).
- `tests/test_overlay_html_sink_gate.py` — the existing HTML-sink escaping / no-`innerHTML` gate.
- `tests/test_ui_score_authoritative.py`, `tests/test_score_calc.py`, `tests/_score_fixtures.py` —
  authoritative `POST /score` round-trip + `compute()` unit + shared drift-guard fixtures.
- `tests/test_imports.py` — crash-isolation heavy-absent import gate (must stay green).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `score_calc.compute()` already does `out = dict(fields or {})` then layers flat keys — the
  additive subkeys slot in with the same pattern, Decimal-string stringified like existing totals.
- The `/overlay-json` route already echoes `s.fields` **verbatim** (no server-side alias
  resolution), so new subkeys flow through to the client with zero route change.
- `overlay-render.js` already renders a `competitor`/`event` identity line via `createTextNode` —
  the dog/handler name target already exists and is already XSS-safe.
- `score-entry.js` already echoes the untrusted name via `nomeEcho.textContent` — the form-preview
  XSS sink is already correct; the work is *proving* it for the new fields, not building it.

### Established Patterns
- **Additive-only, server-authoritative, Decimal-never-float** (milestone keystone) — the client
  POSTs raw inputs; only Python `compute()` writes; the advisory `score-calc.js` mirror parity is
  enforced by the existing drift-guard, not trust.
- **Safe-default never-raise readers** (`read_score`, `read_overlay_run`) assemble `/overlay-json`
  — a torn/absent source yields a safe-default payload, never a 500. Don't add `json.load`/`open`
  in the route.
- **XSS sink discipline:** every operator value reaches the DOM via `textContent` /
  `createTextNode` / `createElementNS` — NO `innerHTML` anywhere; a served-JS test enforces it.

### Integration Points
- New subkeys: emitted in `score_calc.compute()` → written by `_write_score_doc` into `score.json`
  → echoed by `get_overlay_json` → consumed (optionally) by `overlay-render.js`.
- New free-text identity fields: entry form (`score-entry.js`/`_score-entry-form.html`) →
  `_parse_structured_inputs` (`app.py`) → `compute()` passthrough → `score.json` / `/overlay-json`
  → `overlay-render.js` identity line.

</code_context>

<specifics>
## Specific Ideas

- All four discussed areas resolved on the recommended (conservative, additive) option — the
  guiding instinct is "grow the data model, freeze the contract, prove the regression, don't expand
  the broadcast surface."
- Judges are explicitly **data-only** for v1.3 — recorded in `score.json`, never on the single-score
  overlay.

</specifics>

<deferred>
## Deferred Ideas

- **Judges on the overlay** — showing judge name(s) on the broadcast lower-third was considered and
  deferred (new visible capability; v1.3 stays single-score, uncluttered). Revisit with SCM-F1
  (multi-judge freestyle) if/when standings/multi-judge ship.
- **Blocking real-OBS rig UAT** — a hard rig gate before sign-off was considered and rejected to
  preserve the non-blocking-UAT pattern (D-08); the rig checklist is carried forward as
  non-blocking, consistent with the v1.2/v1.3 deferral history.

</deferred>

---

*Phase: 18-rich-data-model-overlay-continuity-regression*
*Context gathered: 2026-06-27*
