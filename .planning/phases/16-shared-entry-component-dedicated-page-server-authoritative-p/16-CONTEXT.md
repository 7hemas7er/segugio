# Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the ONE shared vanilla-JS score-entry component and prove it on a dedicated full-screen
`/score-entry` page, with **live advisory** feedback (running total + per-field validation errors),
and make `POST /score` the **sole authority** that validates RAW inputs and recomputes the on-air
total in Python before writing atomically. The Phase-15 `score_calc` authority + scoring profiles are
the engine this phase finally wires to a UI.

**In scope (Phase 16):**
- ONE shared vanilla-JS `score-entry.js` — a `mount(root, cfg)` factory (dual export), mounted FIRST
  on the dedicated `/score-entry` page (SCE-01). NOT an iframe, NOT a hand-mirrored copy.
- Rich per-discipline structured fields rendered from the **active scoring profile** injected by the
  server (SCE-02) — disc Toss&Fetch, disc Freestyle, agility.
- `score-calc.js` — a byte-exact ADVISORY client port of `score_calc.compute` for the live total,
  with a **drift-guard test** (node-vs-Python shared fixtures) enforcing parity (SCC-03). Advisory only.
- Live advisory running total + per-field validation errors (SCE-03 / SCE-05).
- `POST /score` made AUTHORITATIVE (SCC-01): validate RAW inputs → **400 + write NOTHING** on invalid
  (previous on-air score untouched) → recompute totals in Python (`decimal`) → atomic `score.json`
  + `overlay.txt`, preserving `running`/`started_at` (WR-03), gen-bump (not a run edge).
- The round-trip acceptance test (form total === `overlay.txt` line === `/overlay-json`-rendered total).

**Out of scope (Phase 17 — redirect here, do NOT pull in):**
- The console native `<dialog>` modal mount + the single `{% include %}` Jinja form partial (SCE-04 part).
- Multi-throw/round **progressive total + reload-safe in-progress STATE** (localStorage restore + any
  server-side in-progress persistence) (SCC-05). NOTE: multi-throw *entry* IS in Phase 16 (see D-01);
  only the persistence/restore/progressive-across-reload state is deferred.
- Explicit danger-styled publish action + full tablet contract (≥16px anti-zoom inputs, focus-trap,
  offline/no-CDN assets) (SCE-04).

**Out of scope (later milestones):**
- Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression (Phase 18).
- Roster/standings, multi-judge combiners beyond `sum`, CV auto-scoring.
</domain>

<decisions>
## Implementation Decisions

### Disc Toss&Fetch entry shape (the Phase 16/17 boundary)
- **D-01:** The dedicated page renders a **repeatable throw list** (a throw row = zone band +
  `midair` + `corridor` bonus checkboxes), and the component computes the **best-5-of-N** total LIVE
  via `score_calc`'s `throws[]` + `count_best_n` contract (already built in Phase 15). Submission posts
  the full throw list at once. This makes disc T&F genuinely usable after Phase 16.
- **D-01a:** ONLY the **reload-safe / progressive persistent state** is deferred to Phase 17 (SCC-05) —
  localStorage restore, atomic in-progress persistence, progressive total across reloads. Phase 16's
  throw list is **in-memory for the session** (lost on reload — that's acceptable; 17 fixes it).
  The planner must NOT build localStorage persistence here, and must NOT defer throw *entry* to 17.

### Live advisory feedback UX (SCE-03 / SCE-05)
- **D-02:** The **advisory running total recalculates live** as the operator types (immediate feedback),
  explicitly labeled/treated as non-authoritative.
- **D-03:** Per-field validation errors appear **on blur** (per field), not on every keystroke — quiet
  while typing, immediate enough to catch before publish. Re-validate on submit-attempt.
- **D-04:** The publish/submit button is **always enabled** — the server is the real authority and 400s
  if truly invalid; never hard-block the operator client-side. (Phase 17 layers the explicit
  danger-styled publish on top; do not add a disabled/gated state here.)

### Publish result feedback (SCC-01)
- **D-05:** A **persistent inline banner** on the page reports the publish result:
  - On 2xx → a clear success confirmation ("✓ In onda").
  - On 400 → render the server's **per-field errors** mapped onto the fields PLUS an explicit
    "punteggio precedente invariato" (previous on-air score unchanged) note.
  - The banner stays visible until the next action (not a transient toast — a live operator on a busy
    field must not miss it).
- **D-05a:** The server (authoritative) is the source of the displayed errors on a 400; the client
  advisory validation is a UX pre-filter, never the gate.

### Discipline selection on /score-entry (SCE-02)
- **D-06:** The page derives its discipline options from the **configured sport** (the injected active
  profile): a **disc-dog** config offers **Toss&Fetch + Freestyle** (both served by the one
  `DiscDogProfile.scoring` — zones drive T&F, `freestyle_cats` drive Freestyle); an **agility** config
  offers **Agility** only (from `AgilityProfile.scoring`). The active scoring profile therefore always
  matches the selected discipline — no "which profile for which discipline" ambiguity, no fallback
  profile needed. NOT a free 3-way selector (would require an agility+disc profile coexistence story
  the config discriminated-union does not support).

### Claude's Discretion (locked technical choices)
- **D-07 — Profile + discipline options reach the client via server injection**, mirroring the proven
  `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` plain-arg injection (and the way `console.html`
  derives its CAMS list from the injected whitelist). The active scoring profile (adapted to plain
  data) + the valid-discipline list are handed to the `/score-entry` template / `mount(root, cfg)` cfg.
  Exact transport (inlined JSON blob vs a small GET) is a planning detail — keep it crash-isolation-safe
  (no heavy imports; the console still imports only `Flask + segugio.opcomm + score_calc`).
- **D-08 — `POST /score` accepts RAW structured inputs** (e.g. `throws[]` for T&F, the 4 categories +
  manual `adjustment` for Freestyle, time/SCT/faults-or-deductions + elimination for agility) — NOT a
  client-computed total. The server runs `score_calc.validate` → 400 (write nothing) on errors →
  `score_calc.compute` → atomic write. This REPLACES the current display-only `post_score`
  (`app.py:193`, which trusts a manual `totale` field) — that manual-total path is retired for the
  structured path.
- **D-09 — `score-calc.js` is a byte-exact advisory port** of `score_calc.compute`, kept honest by the
  node-vs-Python shared-fixture drift-guard (the `tests/test_ui_overlay_render.py` / `overlay-render.js`
  precedent). It must NEVER become a second authority — Pitfall 2 (double source of truth) is the named
  risk. Decimal-equivalence in JS (avoid float drift) is part of the drift-guard's job.
- **D-10 — Reuse the existing console CSS/markup conventions** for the dedicated page baseline; full
  tablet-first hardening (≥16px inputs, focus-trap, offline assets) is Phase 17. The dedicated page in
  16 should be clean and usable, not pixel-polished. A `/gsd-ui-phase 16` UI-SPEC may refine this
  (ROADMAP "UI hint: yes").
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior-phase context (read first — the engine this phase consumes)
- `.planning/phases/15-pure-calc-validation-core-scoring-profiles/15-CONTEXT.md` — the score_calc /
  scoring-profile decisions (D-01..D-13): zone band list, bonuses list, best-N, freestyle cats,
  agility models, validate-before-compute contract, profile injection (D-10), decimal-not-float.
- `.planning/phases/15-pure-calc-validation-core-scoring-profiles/15-REVIEW.md` — open advisory debt;
  esp. CR-01 (string bonus-flag truthiness, now fixed) — Phase 16 is where REAL form-string data flows
  into `compute()`, so the strict-flag handling must hold end-to-end.

### Phase research (v1.3 — already produced)
- `.planning/research/v1.3/SUMMARY.md` — keystone (server-authoritative wins unconditionally), build
  order, the named pitfalls.
- `.planning/research/v1.3/ARCHITECTURE.md` — component layout, `score-entry.js` / `score-calc.js`
  contracts, `POST /score` authoritative flow.
- `.planning/research/v1.3/PITFALLS.md` — esp. #1 crash-isolation, #2 double source of truth,
  #3 client-only validation bypassable by a direct LAN POST.
- `.planning/research/v1.3/FEATURES.md` — per-discipline field sets / federation variance.
- `.planning/research/v1.3/STACK.md` — zero-new-dependency confirmation.

### In-repo code the phase extends / must not break
- `src/segugio/ui/app.py` — `create_app` plain-arg injection precedent (D-07); the CURRENT display-only
  `post_score` (~line 193) this phase makes authoritative (D-08); `_bump_score_gen` / `write_score` /
  `atomic_write_text` / `render_overlay_text` write path; `/overlay-json` (the round-trip read side).
- `src/segugio/ui/score_calc.py` — the `validate()` + `compute()` authority + `ScoringProfile` shape
  the server calls and `score-calc.js` ports.
- `src/segugio/config/discipline.py` — `adapt_scoring_profile` (pydantic→stdlib) + the
  `DiscDogProfile | AgilityProfile` sport union that decides the valid-discipline list (D-06).
- `src/segugio/ui/score_render.py` — `render_overlay_text` display-only invariant (must stay dumb).
- `src/segugio/ui/templates/console.html` — the EXISTING inline `#form-score` (selector + 3 fieldsets,
  manual `totale`) being superseded; its discipline-toggle JS + CSS conventions to reuse (D-10).
- `src/segugio/ui/static/overlay-render.js` + `tests/test_ui_overlay_render.py` — the node-vs-Python
  byte-exact drift-guard PRECEDENT for the new `score-calc.js` drift-guard (SCC-03 / D-09).
- `tests/test_imports.py` — `PHASE1_SURFACE` + heavy-absent gate; the `POST /score` route stays
  crash-isolation-safe (the Phase-15 gate must remain green after the route becomes authoritative).

### Pinned rule tables (correctness reference)
- `https://discdogcsen.it/media/documents/RegolamentoDiscDogCsen2026.pdf` — CSEN 2026 (pinned default
  profile; the round-trip/acceptance totals are validated against it).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Plain-arg injection** (`app.py:create_app`, `console.html` CAMS-from-whitelist): the exact mechanism
  to hand the active scoring profile + valid-discipline list to `/score-entry` / `mount(root, cfg)` (D-07).
- **`score_calc.validate`/`compute` + `adapt_scoring_profile`** (Phase 15): the server-side authority the
  authoritative `POST /score` calls; `score-calc.js` ports `compute` for advisory UX.
- **node-vs-Python drift-guard** (`overlay-render.js` ↔ `test_ui_overlay_render.py`): the proven test
  shape for the `score-calc.js` parity guard (SCC-03).
- **Existing `#form-score`** (`console.html`): discipline selector + per-discipline fieldset toggle JS +
  CSS to reuse for the dedicated page baseline (D-10); the manual-`totale` path is retired (D-08).

### Established Patterns
- **Server-authoritative write path**: only `POST /score` → Python → `atomic_write_*` changes what airs;
  gen-bump on a score write preserves `running`/`started_at` (it is NOT a run edge).
- **Crash-isolation allowlist** (`tests/test_imports.py`): the route + new modules must import clean with
  the heavy stack absent — HARD gate inherited from Phase 15.
- **One renderer, two mounts (SCV-02 lesson)** applied to a form: one `score-entry.js`, mounted on the
  dedicated page now and the console modal in Phase 17 — drift structurally impossible.

### Integration Points
- `POST /score` consumes `score_calc.validate`/`compute` with the injected active profile; writes
  `score.json` + `overlay.txt`; `/overlay-json` is the round-trip read side for the acceptance test.
- `/score-entry` is a NEW GET route serving the page that mounts `score-entry.js`.
</code_context>

<specifics>
## Specific Ideas

- The operator films Italian CSEN/FIDASC disc-dog events live on a field — the dedicated page is the
  primary, calmer entry surface (the console modal in Phase 17 is for in-the-flow use). Favor clarity
  over density.
- Disc T&F is the headline discipline: the throw-list + live best-5 (D-01) is the feature that makes
  the auto-calc tangible. Get that interaction right.
- "Previous on-air score untouched on a rejected submit" (D-05) is a broadcast-integrity guarantee, not
  a nicety — the operator must be able to trust that a bad entry never blanks/garbles what's airing.
</specifics>

<deferred>
## Deferred Ideas

- **Reload-safe / progressive multi-throw STATE** (localStorage restore, atomic in-progress persistence,
  progressive total across reloads) — Phase 17 (SCC-05). Phase 16 entry is in-session only (D-01a).
- **Console `<dialog>` modal mount + single Jinja form partial** — Phase 17 (SCE-04).
- **Explicit danger-styled publish + full tablet contract** (≥16px anti-zoom, focus-trap, offline/no-CDN
  assets) — Phase 17 (SCE-04).
- **Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression** — Phase 18.
- **Multi-judge combiners beyond `sum`, per-category overlay breakdown, more federation profiles,
  roster/standings** — post-v1.3.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 16-shared-entry-component-dedicated-page-server-authoritative-post*
*Context gathered: 2026-06-22*
