# Phase 17: Console Modal, Multi-throw State & Tablet UX - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Take the EXACT `score-entry.js` component proven on `/score-entry` in Phase 16 and:
1. Mount it inside a console `<dialog>` modal via ONE shared Jinja form partial (no duplicated
   calc/submit, no re-introduced mirror) — SCE-01 / SCE-04.
2. Make the disc-T&F repeatable throw list survive a tablet reload mid-run (reload-safe in-progress
   state) — SCC-05.
3. Make "go to air" a deliberate, fat-finger-proof action and meet the code-time tablet contract on
   an offline rig — SCE-04.

Requirements: **SCE-04** (explicit publish + tablet contract: ≥16px inputs, focus-trap, offline/no-CDN
assets) and **SCC-05** (multi-throw progressive total + reload-safe in-progress state).

**In scope (Phase 17):**
- ONE shared Jinja form partial (the `#score-cfg` blob + `#score-entry-root` + `#publish-banner` +
  the two `<script>` tags) `{% include %}`'d by BOTH `score-entry.html` AND the console `<dialog>`,
  so page and modal are byte-for-byte the same form (SCE-01).
- Console `<dialog>` modal hosting the same `mount(root, cfg)` module, opened from the console
  "Punteggio" card; the legacy inline `#form-score` (urlencoded prese/zona/totale) is RETIRED here
  (app.py:364 already flags this) and so is its legacy POST branch in `post_score`.
- Compact read-only current-on-air score readout in the console Punteggio card (polled, not baked) +
  an "Inserisci / modifica punteggio" button that opens the modal.
- Reload-safe in-progress throw list via **localStorage** (silent auto-restore on reload; cleared on
  successful 2xx publish only).
- Deliberate publish: a **two-step confirm** (danger-styled "Conferma invio") replacing the single
  always-fires tap; **Enter never publishes**.
- Code-time tablet contract: ≥16px inputs, native `<dialog>.showModal()` focus-trap, zero
  external/CDN assets, sleep/wake survival (rides on the localStorage restore).

**Out of scope (redirect here — do NOT pull in):**
- Rich additive `fields` subkeys (throws[]/criteria{}/faults_breakdown{}) through the write path +
  `/overlay-json` and the overlay-continuity regression — **Phase 18** (RBT-09).
- Any change to `score_calc` (Phase 15, locked) — the rounds model stays a flat best-N throw list
  (see D-01); no round-grouping entity.
- Server-side draft persistence — explicitly NOT chosen (D-04); localStorage only.
- Real-iPad rig UAT — deferred, non-blocking (success criterion 4 is code-time only).

**Out of scope (later milestones):**
- Roster/standings, multi-judge combiners beyond `sum`, per-category overlay breakdown, CV auto-scoring.
</domain>

<decisions>
## Implementation Decisions

### Rounds model (SCC-05) — the data-model anchor
- **D-01:** Disc Toss & Fetch scores from ONE flat set of throws — a single continuous list with the
  existing **best-5-of-N** rule and a live progressive running total. "Across N rounds" in the
  success criterion is loose wording for "the operator keeps adding throws over the run", NOT a
  round-grouping entity. **`score_calc` (Phase 15) is unchanged** and the wire shape stays the flat
  `throws[]` already built in Phase 16. This deliberately keeps the blast radius small.

### Reload-safe in-progress state (SCC-05)
- **D-02:** The in-progress (not-yet-published) throw list persists to **localStorage only** — no
  server-side draft file. Rationale: single-operator, single offline-rig tablet; zero new server
  route, zero crash-isolation/import-allowlist risk, instant and offline-native. The criterion's
  "written atomically with a never-raise reader" maps to the client: `localStorage.setItem` is
  atomic per key, and the restore reader is wrapped in try/catch so a corrupt/absent/torn value →
  empty draft and NEVER throws (the never-raise-reader discipline applied client-side).
- **D-03:** On reload mid-run the draft is **silently auto-restored** — the throw list simply
  reappears as the operator left it, no prompt, no extra tap. Matches "no lost throws" literally and
  the calm-flow goal.
- **D-04:** The draft is **cleared only on a successful publish (server 2xx/204)**. A 400 or a
  network error KEEPS the draft so nothing is ever lost on a rejected/failed submit (consistent with
  the Phase-16 "previous on-air score untouched" integrity guarantee). An explicit "svuota / nuovo
  punteggio" reset button and per-discipline/per-run draft keying were both on the table but NOT
  chosen — see Deferred Ideas.

### Deliberate publish (SCE-04)
- **D-05:** Publishing is a **two-step confirm**: the first tap on "Manda in onda" morphs the button
  into a distinct **danger-styled "Conferma invio"** (with a brief escape/auto-revert so a stray
  arm doesn't stay armed); only the second deliberate tap POSTs. This layers ON TOP of the Phase-16
  always-enabled button (D-04 of Phase 16) — the button is never disabled/gated, the confirm is the
  deliberate gate. Works for touch and keyboard, accessible.
- **D-06:** **Enter never publishes.** Enter in any field does not submit/POST (it may blur/advance,
  but it can never arm-and-fire or complete the confirm). This is the literal point of "a casual tap
  or Enter cannot put a half-entered score on air" — the only path to air is the two deliberate taps.

### Console surface (SCE-01)
- **D-07:** The retired inline `#form-score` is replaced in the console "Punteggio" card by a compact
  **read-only current-on-air score readout** (discipline + total) PLUS an **"Inserisci / modifica
  punteggio"** button that opens the `<dialog>` modal. The operator always sees what's airing at a
  glance; entry/edit happens in the popup. Verified: the console has NO existing score readout/iframe
  today, so this readout is net-new.
- **D-07a:** The readout's data source is a small poll of **`GET /overlay-json`** (same-origin,
  already serves discipline + total + `gen` — the exact data OBS renders). Reuse it; do NOT bake score
  data into `console.html` and do NOT add a new score-read route. Poll cadence/markup is a planning
  detail (align with the existing console poll loop).

### Claude's Discretion (locked technical choices — do not re-ask)
- **D-08 — One shared Jinja partial.** Extract the score-entry host markup into a single partial
  (e.g. `templates/_score-entry-form.html`) holding the `#score-cfg` JSON blob, `#score-entry-root`,
  `#publish-banner`, and the `score-calc.js` + `score-entry.js` script tags. `score-entry.html`
  `{% include %}`'s it; the console `<dialog>` `{% include %}`'s the SAME partial. One module, two
  hosts → drift structurally impossible (the SCV-02 lesson, already cited in Phase 16). The
  `score_cfg` is injected into both templates from the existing factory-time `_score_cfg` (D-07,
  Phase 16) — no per-host divergence.
- **D-09 — Mount lifecycle: mount on dialog-open.** The component is already re-mountable
  (`mount(root, cfg)` clears the root and rebuilds; the P16 file notes "re-mountable for the P17
  modal"). In the console, mount when the `<dialog>` opens rather than auto-mounting into a hidden
  dialog on page load; on `/score-entry` the existing DOMContentLoaded auto-mount stays. Guard
  against the auto-mount firing inside the console (e.g. the modal root is populated on open). Keep
  ONE banner element resolution working in both hosts (the file already falls back to a component-owned
  banner when `#publish-banner` is absent).
- **D-10 — Tablet contract is mostly already met; verify, don't rebuild.** Inputs are already
  1rem/≥48px and `touch-action: manipulation`; icons are inline SVG (no CDN); native
  `dialog.showModal()` supplies the focus-trap for free (no hand-rolled trap). The partial must add
  ZERO new external/CDN asset. Sleep/wake survival rides on the localStorage restore (D-02/D-03) —
  no separate mechanism. The served-JS no-`innerHTML` XSS guard from Phase 16 must remain green.
- **D-11 — Retire the legacy path fully.** Remove the console `#form-score` inline form + its
  urlencoded submit JS, AND retire the legacy back-compat branch in `post_score` (app.py ~line 364,
  `_is_legacy_score_post`) now that no producer posts the flat urlencoded shape. Keep the
  crash-isolation import-smoke gate (`tests/test_imports.py`) green and the authoritative JSON
  `POST /score` path unchanged.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior-phase context (read first — this phase is a direct continuation)
- `.planning/phases/16-shared-entry-component-dedicated-page-server-authoritative-p/16-CONTEXT.md` —
  the component contract this phase reuses verbatim: D-01/D-01a (throw list in-session, persistence
  deferred to 17), D-04 (button always enabled — 17 layers the confirm on top), D-07 (server
  injection of `_score_cfg`), D-08 (RAW structured POST), D-09 (advisory byte-exact calc, never a
  second authority), and the explicit "Out of scope (Phase 17)" list that defines THIS phase.
- `.planning/phases/15-pure-calc-validation-core-scoring-profiles/15-CONTEXT.md` — `score_calc`
  contract incl. `throws[]` + `count_best_n` (best-5-of-N) — the engine that stays UNCHANGED (D-01).

### Phase research (v1.3 — already produced)
- `.planning/research/v1.3/SUMMARY.md` — keystone (server-authoritative), build order, named pitfalls.
- `.planning/research/v1.3/ARCHITECTURE.md` — component layout, `score-entry.js`/`score-calc.js`
  contracts, authoritative `POST /score` flow.
- `.planning/research/v1.3/PITFALLS.md` — esp. #1 crash-isolation, #2 double source of truth,
  #3 client-only validation bypassable by a direct LAN POST, #5 XSS sink.
- `.planning/research/v1.3/STACK.md` — zero-new-dependency confirmation (vanilla JS + native
  `<dialog>`, stdlib + pydantic server-side).

### In-repo code the phase extends / must not break
- `src/segugio/ui/static/score-entry.js` — the shared `mount(root, cfg)` component (re-mountable;
  in-session `throwRows`; always-enabled `publishBtn` + `submit()`; banner fallback when
  `#publish-banner` absent; no-`innerHTML` XSS discipline). P17 adds localStorage persistence,
  the two-step confirm, and Enter-suppression INSIDE this one module — no fork.
- `src/segugio/ui/static/score-calc.js` — advisory byte-exact calc; UNCHANGED (drift-guard must stay green).
- `src/segugio/ui/templates/score-entry.html` — the dedicated-page host whose form markup gets
  extracted into the shared partial (D-08); its reused CSS token set (≥16px inputs, dark palette).
- `src/segugio/ui/templates/console.html` — the legacy `#form-score` (lines ~262–302) + its submit JS
  (lines ~320–348) RETIRED (D-11); the `.side-col` "Punteggio" card that gets the readout + modal
  button (D-07); the existing console poll loop the `/overlay-json` readout aligns with.
- `src/segugio/ui/app.py` — `create_app` plain-arg injection + factory-time `_score_cfg` (lines
  ~248–256) reused for both hosts; the authoritative `post_score` (~line 340) whose legacy
  back-compat branch (`_is_legacy_score_post`, ~line 364, already marked "RETIRED IN P17") is removed;
  `GET /overlay-json` as the readout source (D-07a); the `/score-entry` route (~line 323).
- `tests/test_imports.py` — `PHASE1_SURFACE` + heavy-absent crash-isolation gate; must stay green
  after the legacy branch removal and any route touch.

### Pinned rule tables (correctness reference)
- `https://discdogcsen.it/media/documents/RegolamentoDiscDogCsen2026.pdf` — CSEN 2026 (pinned default
  profile; the flat best-5-of-N Toss&Fetch model in D-01 reflects this).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`mount(root, cfg)` in `score-entry.js`** — already explicitly re-mountable and built for the P17
  modal; the modal mount calls the SAME factory. Persistence/confirm/Enter changes go inside it.
- **Factory-time `_score_cfg`** (`app.py`) — the single injected profile + discipline list, already
  fed to `/score-entry`; feed the SAME blob into the console template for the modal.
- **Native `<dialog>` + `showModal()`** — supplies focus-trap and Escape-to-close for free; no
  hand-rolled trap (D-10).
- **`GET /overlay-json`** — same data OBS renders (discipline + total + gen); the console readout polls it (D-07a).
- **Banner fallback already in `score-entry.js`** — when `#publish-banner` is absent the component
  appends its own; the modal can rely on this without a host-provided banner.

### Established Patterns
- **One renderer, many mounts (SCV-02)** applied to a form — one module + one Jinja partial across
  two hosts; the project's structural anti-drift pattern.
- **Server-authoritative write path** — only `POST /score` (JSON, RAW inputs) changes what airs;
  unchanged here. localStorage holds only the NOT-yet-published draft.
- **Never-raise reader discipline** — applied to the client localStorage restore (try/caught → empty
  draft), mirroring the server-side `read_overlay_run`/opcomm boundary.
- **Crash-isolation import allowlist** (`tests/test_imports.py`) — HARD gate; retiring the legacy
  branch must not perturb it.

### Integration Points
- Console "Punteggio" card → readout (poll `/overlay-json`) + button → opens `<dialog>` → mounts
  shared component → `POST /score` (authoritative) → on 2xx clears localStorage draft + readout updates.
- Both `score-entry.html` and `console.html` `{% include %}` the one shared form partial.
</code_context>

<specifics>
## Specific Ideas

- The console modal is the IN-THE-FLOW entry surface (vs the calmer dedicated page) — favor speed and
  glanceability: the always-visible readout means the operator never loses sight of what's on air
  while editing the next score.
- "No lost throws" is the felt promise of SCC-05: a tablet that sleeps/locks and wakes mid-run, or a
  reload, must bring the throw list back exactly — silently (D-03). This is the reliability the
  operator trusts in the field.
- The two-step confirm (D-05) is broadcast-integrity, not friction: a stray tap or Enter must never
  air a half-entered score, but a deliberate operator is still two quick taps from air.
</specifics>

<deferred>
## Deferred Ideas

- **Explicit "svuota / nuovo punteggio" reset button** + **per-discipline/per-run draft keying** —
  considered for the clear-draft behavior (D-04 options 2 & 3) but not chosen; revisit if
  multi-competitor flow without publishing-between proves awkward in the field.
- **Server-side in-progress draft file** (`score_draft.json`, atomic + never-raise) — considered for
  SCC-05 (D-02 option 2) but rejected for a single offline tablet; revisit only if cross-device or
  console-side draft continuity is ever needed.
- **Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression** — Phase 18 (RBT-09).
- **Multi-judge combiners beyond `sum`, per-category overlay breakdown, roster/standings, CV
  auto-scoring** — post-v1.3 (SCM-F1/F2, out of scope).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 17-console-modal-multi-throw-state-tablet-ux*
*Context gathered: 2026-06-24*
