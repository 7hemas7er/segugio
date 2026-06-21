# Research Summary -- v1.3 "Gestione Punteggi Avanzata"

**Project:** Segugio -- automated multi-camera director for disc-dog and agility events
**Domain:** Richer, shared, auto-calculating, server-validated score entry on the crash-isolated Flask console
**Researched:** 2026-06-21
**Confidence:** HIGH

---

## Keystone Decision (Conflict Resolution)

> **FEATURES.md said:** "all calc client-side, publish the result."
> **ARCHITECTURE.md + PITFALLS.md + STACK.md said:** "server-authoritative: the client POSTs RAW inputs,
> `POST /score` validates (400 on invalid) and RE-COMPUTES totals, then writes `overlay.txt`/`score.json`
> -- client live-calc is ADVISORY only."
>
> **Resolution: SERVER-AUTHORITATIVE wins, unconditionally.**
>
> Rationale: (1) The opcomm file channel is the exclusive write path to the broadcast overlay -- only
> `POST /score` -> Python -> `atomic_write_*` is allowed to change what airs. A client that posts its own
> computed total can drift silently from what the renderer displays, which is the exact Pitfall 2 the project
> already paid to diagnose in v1.2. (2) Client-side validation alone is bypassable from any LAN POST (stale
> tab, second device, curl) -- the server MUST reject invalid inputs with 400 and write nothing (Pitfall 3).
> (3) The server is the only actor that can guarantee `decimal.Decimal` arithmetic, the per-discipline rule
> set, and the `_clean`/sanitize pipeline all stay on the same code path. The client JS port (`score-calc.js`)
> exists solely for live UX feedback -- it is advisory, never trusted, and its parity with `score_calc.py` is
> enforced by a drift-guard test, NOT by trust.

---

## Executive Summary

v1.3 layers a rich, multi-discipline score-entry subsystem onto the crash-isolated Flask console that Segugio
has shipped since v1.1. The core product need is an operator-friendly entry tool -- touchscreen-first, for use
live on a competition field -- that auto-calculates running totals (multi-throw disc T&F), validates
per-discipline rules (zones, faults, freestyle increments), and publishes a single on-air score to the existing
overlay pipeline without touching the AI director. The architecture is almost entirely determined by
project-owned constraints already proved in production: crash-isolation (no heavy stack on the UI process),
publish-and-render over the opcomm file channel (atomic writes + gen-bump), the SCV-02 shared-renderer lesson
(one renderer, two mount points, drift structurally impossible), and the RBT-06 `overlay.txt` degraded fallback.

The recommended approach introduces zero new runtime dependencies. All new server logic (`score_calc.py`) is
stdlib-only (`decimal`, `re`, `dataclasses`) -- or optionally uses the already-installed pydantic 2.13.4 for
declarative per-discipline schemas -- making it console-import-safe by construction. The entire scoring domain
is config-driven: federation variance is large enough (zone bands, fault values, scoring models, freestyle
category counts and scales all differ per federation) that hard-coding any ruleset would be immediately wrong
for any event using a different federation. A per-discipline/federation YAML "scoring profile" extending the
existing pydantic discriminated-union config pattern is the central design bet and the keystone on which
auto-calc, validation, and the entry UI all depend.

The dominant risk is not technical novelty -- every pattern here reuses something already shipped in this repo
-- but re-introducing bugs the project already retired: the byte-exact mirror drift (SCV-01), a double source
of truth for the on-air total, client-only validation bypassed by a direct LAN POST, and a crash-isolation
breach from importing numpy or `segugio.config` at console module top. Each is prevented by a hard,
already-enforced invariant; the build order is designed to assert those invariants phase by phase.

---

## Key Findings

### Recommended Stack

**From STACK.md -- confidence HIGH.**

No new runtime dependencies are required or justified. The entire milestone is buildable on the already-installed
stack: Python stdlib (`decimal`, `enum`, `re`, `dataclasses`) for the new `score_calc.py` pure module; pydantic
2.13.4 (already pinned, already console-tolerated) optionally for declarative per-discipline schemas; Flask
(already the console web layer) for two new routes; and vanilla ES2020 (no framework, no build step) for the ONE
shared JS component and its advisory calc mirror. Browser-native `<dialog>` replaces any modal library.
The `node v24.16.0` dev runtime (already present) enables the JS behavior-test harness exactly as
`test_ui_overlay_render.py` uses it -- dev-only, never a runtime dep.

**Core technologies (all already present):**

- **Python stdlib `decimal`** -- authoritative auto-calc server-side; avoids `0.1+0.2` float drift on broadcast totals
- **pydantic 2.13.4** -- per-discipline validation models; already installed in both venvs; NOT in HEAVY_MODULES
- **Flask** (lazy, inside `create_app`) -- serves `GET /score-entry`; enforces server-authoritative `POST /score` with 400 on invalid
- **Vanilla ES2020 + native `<dialog>`** -- the ONE shared `score-entry.js` component (advisory calc + UX); zero build step, zero CDN
- **`node v24.16.0`** (dev only) -- JS drift-guard tests via `subprocess`, gated by `shutil.which("node")`

### Expected Features

**From FEATURES.md -- confidence HIGH (disc-dog/agility formulas); MEDIUM (cross-federation completeness).**

Federation variance is the central domain finding: zone distances and point values, mid-air bonus amounts,
freestyle category names/counts/scales, agility scoring models (count-up vs deduct-from-100), fault values, and
time-fault rates all differ per federation (UFO, USDDN, Skyhoundz, FCI, AKC documented). The entry tool must be
config-driven (a YAML "scoring profile" per discipline/federation), not hardcoded.

**Must have (table stakes):**

- **Scoring profile schema** (YAML per federation: zone bands/units, bonus value, time limit, freestyle
  categories + scale, agility `scoring_model` + fault table + time-fault rate) -- keystone; build it first
- **Disc T&F multi-throw entry + running total** (add/edit/delete throw, zone pick per profile bands, mid-air
  toggle, auto-calc sum) -- headline feature; operator picks zone, tool does arithmetic
- **Agility auto-calc** (SCT + run time -> time faults; course faults; `count_up` AND `deduct_from_100` models;
  elimination flag overrides numeric output with "E")
- **Freestyle multi-criteria sum** (N categories from profile, increment-validated per federation scale)
- **Per-discipline server-side validation** with clear error messages (ranges, required fields, `mm:ss.cc` time
  format, increment snapping) -- `POST /score` returns 400, writes nothing on failure
- **Shared single renderer** (dedicated `/score-entry` page + console `<dialog>` modal = one `score-entry.js`
  component, one Jinja partial) -- SCV-02 lesson is binding
- **Publish current score** to `/overlay`, `overlay.txt`, `score.json` via the unchanged file channel

**Should have (differentiators):**

- **Config-driven profiles for multiple federations** (ship 1-2 vetted built-in profiles; operators add their own YAML)
- **Live running total + zone-pick buttons** matched to active profile bands (fast fat-finger entry on a tablet)
- **SCT -> time-fault auto-derivation** (enter run time, get faults; removes the most error-prone live mental math)
- **Explicit publish action** (distinct from "add throw" -- deliberate, danger-styled; prevents accidental broadcast)

**Defer (v2+):**

- Multi-judge combination beyond `sum` (average, drop-high/low for UFO Comprehensive) -- design the combiner now, ship `sum`+`average` in v1.3
- Per-category freestyle breakdown on the overlay (once simple total reads well on air)
- Roster / standings / class ranking -- explicitly out of scope (single on-air score only)
- CV auto-scoring -- anti-feature; conflicts with project scope ("shows, does not judge")

### Architecture Approach

**From ARCHITECTURE.md -- confidence HIGH (grounded in shipped codebase patterns).**

The architecture is fully determined by two already-proved constraints: crash-isolation (console process imports
ONLY Flask + `segugio.opcomm`) and publish-and-render over the opcomm file channel. Three new components handle
the v1.3 surface: (1) `score_calc.py` -- a pure stdlib Python module, the single authoritative source for
`validate(discipline, fields) -> errors` and `compute(discipline, fields) -> fields_with_totals`;
(2) `score-entry.js` -- the ONE vanilla-JS shared component mounted identically into the dedicated page and the
console modal; (3) `score-calc.js` -- a byte-exact JS port used ONLY for advisory live feedback, provably equal
to the Python via a shared-fixture drift-guard test. `POST /score` becomes authoritative; the client never sends
a computed total, only raw inputs. The data model enrichment is additive: `fields` gains structured subkeys
(throws[], criteria{}, faults_breakdown{}) while always retaining the flat summary keys (`totale`, `faults`,
`tempo`, etc.) the existing overlay renderer and `overlay.txt` fallback read verbatim.

**Major components:**

1. **`segugio/ui/score_calc.py`** -- pure stdlib validate+compute authority; imported by `POST /score`; NEVER
   imports numpy/cv2/torch/`segugio.config`; added to `PHASE1_SURFACE`; exercised under the heavy-absent console guard
2. **`static/score-entry.js` + `static/score-calc.js`** -- the ONE shared JS component (form + advisory calc);
   dual `module.exports`/`window` export (overlay-render.js precedent); both `<script src>`-d by dedicated page and modal
3. **`templates/score-entry.html` + `<dialog>` in `console.html`** -- thin host mounts only; ALL behavior in
   the shared JS module; markup skeleton shared via a Jinja `{% include "score-form.html" %}` partial
4. **`app.py POST /score`** (modified) -- server-authoritative: reject 400 on invalid, recompute totals in
   Python, write atomically, bump gen; preserve `running`/`started_at` from in-memory state (WR-03)
5. **`app.py GET /score-entry`** (new) -- thin host route exactly like `GET /overlay`; no score data baked in
6. **`segugio/ui/score_render.py`** (minimal) -- still reads flat summary keys; `render_overlay_text` stays display-only (SCR-04)

### Critical Pitfalls

**From PITFALLS.md -- confidence HIGH (all anchored to named project decisions and existing tests).**

1. **Re-introducing the SCV-01 byte-exact-mirror trap (page vs modal drift)** -- build score entry as ONE
   component (one JS module, one Jinja partial) mounted in both surfaces; any `gsd:*-mirror` comment or
   duplicated field label is the failure mode resurfacing; enforce with a test that both hosts contain no
   calc/submit logic of their own

2. **Double source of truth -- client live-calc disagrees with what actually airs** -- `score_calc.py` is the
   SOLE authority; client JS port is advisory UX only; `render_overlay_text` and `overlay-render.js` stay
   display-only (SCR-04); verified by round-trip acceptance test: form-displayed total === `overlay.txt` line
   === `/overlay-json`-rendered total for the same inputs

3. **Client-only validation bypassable by a direct LAN POST** -- `POST /score` rejects with 400 and writes
   NOTHING on invalid input; validate-before-write ordering is absolute; server rule set is the authority

4. **Breaking `overlay.txt` fallback or `/overlay-json` contract** -- data model enrichment is ADDITIVE (new
   keys alongside flat summary keys); `atomic_write_text(overlay.txt, render_overlay_text(doc))` stays on
   every publish; existing gate tests extended, not replaced

5. **Crash-isolation breach -- importing something heavy into `segugio.ui`** -- `score_calc.py` is stdlib-only;
   added to `PHASE1_SURFACE`; import-smoke gate extends to every new `segugio.ui` module; any future heavy
   import at module top fails CI immediately

---

## Implications for Roadmap

Based on combined research, four phases in strict dependency order, continuing from Phase 15.

### Phase 15: Pure Calc + Validation Core

**Rationale:** The authoritative `score_calc.py` must exist and pass the crash-isolation import gate before any
UI consumes it. Building it first makes it independently testable with no UI risk, and establishing the gate
here means every subsequent phase inherits that protection automatically.

**Delivers:** `segugio/ui/score_calc.py` (pure stdlib: `validate()` + `compute()` for all three disciplines);
per-discipline unit tests; scoring profile schema (config-driven YAML structure: zone bands, fault tables,
freestyle categories, agility `scoring_model`); `score_calc.py` added to `PHASE1_SURFACE`;
`test_console_resolves_with_heavy_stack_and_numpy_absent` extended to cover the new module and a `POST /score`
round-trip.

**Addresses:** scoring profile schema (P1), per-discipline validation (P1), auto-calc foundation for all three disciplines

**Avoids:** Pitfall 6 (crash-isolation breach -- gate established once, inherited by all later phases);
Pitfall 2 (double source of truth -- authority defined before any client calc is written)

**Research flag:** Standard pure-logic work (precedent: `score_render.py`, framing scorer). No deeper research
needed. Per-discipline rule tables must be pinned in the REQ before coding -- exact values from FEATURES.md
federation tables.

---

### Phase 16: Shared Component + Dedicated Page + Server-Authoritative POST

**Rationale:** Build the shared JS component against the dedicated `/score-entry` page first -- a simpler host
than the modal -- to prove the one-component pattern end-to-end before modal reuse. This phase also makes
`POST /score` server-authoritative, so all subsequent phases inherit correct server behavior and the round-trip
acceptance test is locked here.

**Delivers:** `static/score-entry.js` (the ONE shared component; `mount(root, cfg)` factory; dual export;
submit POSTs raw inputs only); `static/score-calc.js` (byte-exact advisory JS port); JS drift-guard test;
`templates/score-entry.html` (thin host); `app.py GET /score-entry`; `app.py POST /score` modified to
validate -> compute -> atomic write -> 400 on invalid; round-trip acceptance test (form total ===
`overlay.txt` === `/overlay-json` rendered total).

**Implements:** shared-component architecture (ARCHITECTURE Pattern B), server-authoritative POST /score
with advisory JS mirror and drift-guard

**Avoids:** Pitfall 1 (component proved singular before modal is added); Pitfall 2 (server recomputes on
every POST); Pitfall 3 (server rejects 400 from this phase forward)

**Research flag:** Standard shared-module pattern (precedent: `overlay-render.js`). JS drift-guard test
precedent from `test_ui_overlay_render.py`. No research needed.

---

### Phase 17: Console Modal Reusing the Same Component

**Rationale:** Add the native `<dialog>` modal to `console.html` mounting the SAME `score-entry.js`. This
proves the SCV-02 drift-free claim across two hosts and retires the legacy inline `#form-score`. Doing this
after Phase 16 means the component is already proved on its simpler host.

**Delivers:** `<dialog id="score-dialog">` in `console.html` with "Apri punteggio" trigger; Jinja
`{% include "score-form.html" %}` partial shared by both hosts (single markup source); modal focus trap +
Esc handling + `::backdrop`; explicit publish action (danger-styled, distinct from throw/criterion entry);
iOS inputs >=16px + UXT-01 touch contract; localStorage persistence of in-progress entry (reload survival);
ZERO external/CDN assets in new page and modal; legacy inline `#form-score` retired.

**Avoids:** Pitfall 1 (single Jinja partial proves markup also has one source); Pitfall 8 (explicit publish,
focus trap, offline assets, >=16px inputs enforced at code time; real-iPad UAT deferred to field verification)

**Research flag:** `<dialog>` + virtual keyboard on iPadOS 26 is a UAT note, not a code-time blocker.
Explicit publish UX (confirm dialog vs danger button) is a product decision to resolve in REQ before this phase.

---

### Phase 18: Rich Data Model + Overlay Continuity Verification

**Rationale:** Wire the structured field payloads (throws[], criteria{}, faults_breakdown{}) through the write
path and `/overlay-json`, verify the additive enrichment does not break `overlay.txt`, the `/overlay` renderer,
or the OBS fallback. Done last, once calc and UI exist, so the flat-key guarantee can be verified against the
live overlay in one focused phase.

**Delivers:** Structured `fields` subkeys (additive alongside flat summary keys) carried through `score.json`
and `/overlay-json`; `render_overlay_text` extended for a one-line discipline-appropriate summary; regression
tests confirming `overlay.txt` is single-line and non-empty after a rich POST; `/overlay-json` legacy keys
preserved; `/overlay` page contains no score data; XSS sink gate extended to new free-text fields (no
`innerHTML`, no `| safe`, crafted `<script>` name renders escaped).

**Avoids:** Pitfall 4 (`overlay.txt`/contract regression -- additive-only constraint + regression tests);
Pitfall 5 (XSS via free-text -- sink gate extended to new fields)

**Research flag:** Entirely mechanical/additive. Regression tests are the only gate. No research needed.

---

### Phase Ordering Rationale

- **Calc before UI:** `score_calc.py` is the single authority; the UI cannot be correctly wired until the
  server validates/computes. Building it first establishes the crash-isolation gate all later phases inherit.
- **Dedicated page before modal:** The simpler host proves the shared component works standalone; the modal
  then reuses it with confidence, not hope.
- **Server-authoritative POST in Phase 16, not 17:** The round-trip acceptance test must pass before the
  second mount point is added, or the modal inherits an unvalidated publish path.
- **Data-model enrichment last:** Additive structural changes are safely verified against a fully-wired
  system; done earlier they would be tested against stubs rather than the live overlay path.

### Research Flags

All four phases use standard in-repo patterns. No phase needs deeper external research.

- **Phase 15:** REQ must pin the exact per-discipline rule tables from FEATURES.md federation tables before
  coding. Standard pure-logic module work.
- **Phase 16:** Standard route + shared-module + drift-guard pattern. No research.
- **Phase 17:** `<dialog>` iPad UAT is hardware-gated (deferred); code-time work is standard. Explicit
  publish UX is a product decision for REQ.
- **Phase 18:** Regression and additive wiring only. No research.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All deps already installed and verified. Zero new installs. pydantic 2.13.4 confirmed in both venvs. |
| Features | HIGH / MEDIUM | Disc-dog formulas: HIGH (UFO/USDDN/Skyhoundz/FCI/AKC primary sources). Cross-federation completeness: MEDIUM (UpDog web-only; AKC time-fault rates by class cross-confirmed from secondary). |
| Architecture | HIGH | Grounded entirely in shipped v1.1/v1.2 codebase patterns. Every pattern has a production precedent in this repo. |
| Pitfalls | HIGH | All 8 pitfalls anchored to named decisions (SCV-01->02, RBT-06, D-03, T-11-03-01, WR-03) and existing tests. No inference from external sources. |

**Overall confidence: HIGH**

### Gaps to Address

- **Per-discipline rule tables in REQ (Phase 15 blocker):** The federation tables in FEATURES.md are
  research-level; Phase 15 REQ must commit to the exact values (which federation zone bands ship as the
  built-in profile). Product/operator decision, not a research gap.
- **Multi-judge combination scope:** ARCHITECTURE says design the combiner to support `drop_high_low` even
  if v1.3 ships only `sum` + `average`. The "design for" vs "implement" boundary must be pinned in Phase 16 REQ.
- **Explicit publish action UX:** PITFALLS flags this as a code-time decision (danger button vs confirm
  dialog). Resolve in Phase 17 REQ.
- **iPadOS 26 `<dialog>` + virtual keyboard:** Hardware-gated UAT item. Include as UAT note in Phase 17;
  not a code-time blocker.
- **`<dialog>` dismiss-on-dirty behavior:** Whether to block backdrop-dismiss when the form has unsaved
  throws is a product call. Resolve in Phase 17 REQ.

---

## Sources

### Primary (HIGH confidence -- in-repo, read 2026-06-21)

- `src/segugio/ui/app.py` -- crash-isolation contract, `POST /score` sink, `_gen_lock`/`_bump_score_gen`, WR-03 run-state preservation
- `src/segugio/ui/score_render.py` -- SCR-04 display-only invariant, `_clean` guard, single-line `overlay.txt` contract
- `src/segugio/ui/static/overlay-render.js` -- dual export pattern, `textContent`-only sink (T-11-03-01), SCV-02 shared-renderer mechanism
- `src/segugio/opcomm/atomic.py` / `channel.py` / `records.py` -- atomic write primitives, never-raise readers, `ScoreDoc`, D-03 separation
- `tests/test_imports.py` -- `PHASE1_SURFACE`, `CONSOLE_HEAVY_MODULES`, heavy-absent smoke gate
- `.planning/PROJECT.md` -- Key Decisions (SCV-01->02, RBT-06, D-03, crash-isolation, publish-and-render), v1.3 scope

### Primary (HIGH confidence -- external federation rules)

- UFO World Cup Throw & Catch + Freestyle rules -- zone tables (0/1/2/3 by meter band), mid-air bonus, 4-category 1-10 freestyle, 3-judge Comprehensive drop-high/low
- USDDN 2024 Judging Handbook -- yard zones + 0.5 mid-air, freestyle 10-scale multi-judge
- Skyhoundz Distance/Accuracy + Judging Criteria -- PAWS 1-10 x0.25, 10-yd zone bands +0.5 mid-air, End Zone = 5
- AKC Regulations for Agility Trials -- 100-base deduct, fault values, time-fault rates by class, >=85 qualifying
- PyPI pydantic release metadata -- 2.13.4 confirmed current (2026-05-06)

### Secondary (MEDIUM confidence)

- FCI Agility Regulations -- structure HIGH; exact pole-fault = 5 cross-sourced from secondary
- UpDog Challenge game rules -- zone bands and banking model (web/community)
- SpiritDog Training -- AKC time-fault rates by class cross-confirmation
- Wikipedia Dog agility -- SCT worked example and fault-ranking model cross-reference

---
*Research completed: 2026-06-21*
*Ready for roadmap: yes*
