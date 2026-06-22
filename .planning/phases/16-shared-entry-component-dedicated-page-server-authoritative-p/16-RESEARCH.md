# Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST - Research

**Researched:** 2026-06-22
**Domain:** Rich, SHARED vanilla-JS score-entry on the crash-isolated Flask console; server-authoritative `POST /score` (validate→400-write-nothing→recompute in Python→atomic write) + a byte-exact advisory JS calc port with a node-vs-Python drift-guard.
**Confidence:** HIGH (grounded in the shipped v1.1/v1.2/Phase-15 codebase — `ui/app.py`, `ui/score_calc.py`, `ui/score_render.py`, `config/discipline.py`, `opcomm/{records,channel}.py`, `static/overlay-render.js` + its drift-guard test — not on external sources; every pattern is the project's own proven one. Zero new dependencies.)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Disc Toss&Fetch entry shape (the Phase 16/17 boundary)**
- **D-01:** The dedicated page renders a **repeatable throw list** (a throw row = zone band + `midair` + `corridor` bonus checkboxes), and the component computes the **best-5-of-N** total LIVE via `score_calc`'s `throws[]` + `count_best_n` contract (already built in Phase 15). Submission posts the full throw list at once. This makes disc T&F genuinely usable after Phase 16.
- **D-01a:** ONLY the **reload-safe / progressive persistent state** is deferred to Phase 17 (SCC-05) — localStorage restore, atomic in-progress persistence, progressive total across reloads. Phase 16's throw list is **in-memory for the session** (lost on reload — that's acceptable; 17 fixes it). The planner must NOT build localStorage persistence here, and must NOT defer throw *entry* to 17.

**Live advisory feedback UX (SCE-03 / SCE-05)**
- **D-02:** The **advisory running total recalculates live** as the operator types (immediate feedback), explicitly labeled/treated as non-authoritative.
- **D-03:** Per-field validation errors appear **on blur** (per field), not on every keystroke — quiet while typing, immediate enough to catch before publish. Re-validate on submit-attempt.
- **D-04:** The publish/submit button is **always enabled** — the server is the real authority and 400s if truly invalid; never hard-block the operator client-side. (Phase 17 layers the explicit danger-styled publish on top; do not add a disabled/gated state here.)

**Publish result feedback (SCC-01)**
- **D-05:** A **persistent inline banner** on the page reports the publish result:
  - On 2xx → a clear success confirmation ("✓ In onda").
  - On 400 → render the server's **per-field errors** mapped onto the fields PLUS an explicit "punteggio precedente invariato" (previous on-air score unchanged) note.
  - The banner stays visible until the next action (not a transient toast — a live operator on a busy field must not miss it).
- **D-05a:** The server (authoritative) is the source of the displayed errors on a 400; the client advisory validation is a UX pre-filter, never the gate.

**Discipline selection on /score-entry (SCE-02)**
- **D-06:** The page derives its discipline options from the **configured sport** (the injected active profile): a **disc-dog** config offers **Toss&Fetch + Freestyle** (both served by the one `DiscDogProfile.scoring`); an **agility** config offers **Agility** only (from `AgilityProfile.scoring`). The active scoring profile always matches the selected discipline. NOT a free 3-way selector.

**Claude's Discretion (locked technical choices)**
- **D-07 — Profile + discipline options reach the client via server injection**, mirroring the proven `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` plain-arg injection. The active scoring profile (adapted to plain data) + the valid-discipline list are handed to the `/score-entry` template / `mount(root, cfg)` cfg. Exact transport (inlined JSON blob vs a small GET) is a planning detail — keep it crash-isolation-safe (no heavy imports; the console still imports only `Flask + segugio.opcomm + score_calc`).
- **D-08 — `POST /score` accepts RAW structured inputs** (e.g. `throws[]` for T&F, the 4 categories + manual `adjustment` for Freestyle, time/SCT/faults-or-deductions + elimination for agility) — NOT a client-computed total. The server runs `score_calc.validate` → 400 (write nothing) on errors → `score_calc.compute` → atomic write. This REPLACES the current display-only `post_score` (`app.py:193`, which trusts a manual `totale` field).
- **D-09 — `score-calc.js` is a byte-exact advisory port** of `score_calc.compute`, kept honest by the node-vs-Python shared-fixture drift-guard (the `tests/test_ui_overlay_render.py` / `overlay-render.js` precedent). It must NEVER become a second authority — Pitfall 2 (double source of truth) is the named risk. Decimal-equivalence in JS (avoid float drift) is part of the drift-guard's job.
- **D-10 — Reuse the existing console CSS/markup conventions** for the dedicated page baseline; full tablet-first hardening (≥16px inputs, focus-trap, offline assets) is Phase 17. The dedicated page in 16 should be clean and usable, not pixel-polished. A `/gsd-ui-phase 16` UI-SPEC may refine this.

### Claude's Discretion

See D-07..D-10 above (the CONTEXT.md filed the locked-but-Claude-chosen technical items under "Claude's Discretion (locked technical choices)" — they are LOCKED, not open). The remaining genuinely-open planning details inside those locks:
- D-07 transport: inlined JSON `<script type="application/json">` blob vs a small `GET /score-entry-cfg`. (Research recommends the inlined blob — see Architecture Pattern 1.)
- The exact `throws[]` / freestyle / agility field-name wire keys the form posts and the server parses (Research pins these against the Phase-15 `score_calc` contract — see "Authoritative POST contract").

### Deferred Ideas (OUT OF SCOPE)

- **Reload-safe / progressive multi-throw STATE** (localStorage restore, atomic in-progress persistence, progressive total across reloads) — Phase 17 (SCC-05). Phase 16 entry is in-session only (D-01a).
- **Console `<dialog>` modal mount + single Jinja form partial** — Phase 17 (SCE-04). The component must be *built to be re-mountable* (a `mount(root, cfg)` factory with dual export) but Phase 16 mounts it ONLY on the dedicated page.
- **Explicit danger-styled publish + full tablet contract** (≥16px anti-zoom, focus-trap, offline/no-CDN assets) — Phase 17 (SCE-04).
- **Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression** — Phase 18.
- **Multi-judge combiners beyond `sum`, per-category overlay breakdown, more federation profiles, roster/standings** — post-v1.3.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|-----------------------------------|------------------|
| **SCE-01** | Operator enters the score from a dedicated page (and later a modal) — both mount the SAME shared vanilla-JS component → no drift, no iframe-for-the-form, no byte-exact mirror copy. | Architecture Pattern 1 (one `mount(root,cfg)` JS module, dual export; mounted FIRST on `/score-entry`). Dedicated page is a thin Jinja host like `overlay.html`. |
| **SCE-02** | Component shows the rich per-discipline structured fields (disc T&F, disc freestyle, agility) driven by the active scoring profile. | "Per-discipline field sets" + "Authoritative POST contract" tables (fields derived from the injected `ScoringProfile`: `zones`/`bonuses`/`freestyle_cats`/`agility_model`). |
| **SCE-03** | Live advisory client calc — running total updates while typing, explicitly non-authoritative. | Pattern 2 + `score-calc.js` byte-exact port; D-02. Recompute IN PLACE (`textContent`), never node-rebuild (Performance Trap). |
| **SCE-05** | Per-field validation errors shown to the operator before publishing. | `score_calc.validate()` returns `[{field, message}]`; JS port mirrors it; D-03 (errors on blur + on submit). |
| **SCC-01** | `POST /score` is authoritative: validate raw inputs (400 + no write on invalid), recompute totals in Python (`decimal`), then atomic `score.json` + `overlay.txt`. | "Authoritative POST contract" section — validate-before-write ordering, preserve `running`/`started_at` via `_bump_score_gen` (WR-03). |
| **SCC-03** | Client `score-calc.js` port with a drift-guard test proving parity with the Python module (no double source of truth). | Pattern 2 + "Drift-guard mechanics" section, modeled byte-for-byte on `tests/test_ui_overlay_render.py::test_cleanfield_byte_parity_with_python_clean` / `test_value_crosscheck`. |
</phase_requirements>

## Summary

This phase is **the spine of v1.3**: it takes the Phase-15 pure scoring authority (`segugio.ui.score_calc.validate`/`compute`, Decimal-exact, crash-isolated) and wires it to (a) a single shared vanilla-JS entry component proven on a dedicated `/score-entry` page, and (b) an authoritative `POST /score` that recomputes the on-air total in Python from RAW structured inputs. Every primitive this phase needs already exists in the repo — there is **nothing to invent and zero new dependency**. The work is *composition and discipline*, and the dominant risks are the named v1.3 pitfalls (double source of truth, client-only validation bypass, crash-isolation breach, mirror drift).

The three genuine planning unknowns, all resolved here:
1. **Profile injection transport (D-07):** inject the adapted plain `ScoringProfile` + valid-discipline list into the `/score-entry` template as an **inlined JSON `<script type="application/json">` blob** the JS reads at mount — mirroring the `cam_ids | tojson` precedent in `console.html`. This adds NO heavy import to the console (the adapter `adapt_scoring_profile` is called LAZILY in the entrypoint, like `load_config`).
2. **Byte-exact JS port with Decimal-equivalence (D-09 / SCC-03):** port `score_calc.compute` to `score-calc.js` using a small **fixed-scale integer/string decimal helper** (NOT JS `Number` float math) so `0.5 + 0.5` and best-5-of-N stringify identically to Python's `Decimal`. The drift-guard test is a near-verbatim clone of the shipped `overlay-render.js` node-parity test.
3. **Authoritative POST contract (D-08 / SCC-01):** retire the manual-`totale` path; parse RAW per-discipline structured inputs into the exact dict shape `score_calc.validate`/`compute` expect, validate-then-write, preserve `running`/`started_at`.

**Primary recommendation:** Build `score_calc.js` (advisory port + drift-guard) and the authoritative `POST /score` FIRST (they are pure and testable), then the `score-entry.js` component + `/score-entry` host page on top — and gate the whole thing behind the existing crash-isolation import-smoke test extended to the new modules.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Score validation (per-discipline, ranges, time format) | API / Backend (`score_calc.validate` in `POST /score`) | Client (advisory pre-filter only) | SCC-01 keystone: the server is the SOLE authority; a LAN POST must be rejected server-side (Pitfall 3). Client validation is UX, never the gate (D-05a). |
| Total recompute (best-5-of-N, freestyle sum, agility faults/deduct) | API / Backend (`score_calc.compute`, Decimal) | Client (advisory live total, `score-calc.js`) | Only Python writes the file → client and on-air score cannot diverge (Pitfall 2). |
| Live running-total feedback while typing | Browser / Client (`score-calc.js` advisory) | — | SCE-03; pure UX, never touches the server, never writes files. |
| Per-field error display | Browser / Client (renders server errors on 400; advisory errors on blur) | API (authoritative error list on 400) | D-03/D-05: advisory on blur, authoritative on the 400 response. |
| Atomic on-air write (`score.json` + `overlay.txt`) + gen-bump | API / Backend (`write_score`/`atomic_write_text`/`_bump_score_gen`) | — | Existing write path; preserve `running`/`started_at` (WR-03). |
| Profile + valid-discipline injection | Frontend Server (Jinja render of `/score-entry`, plain-arg) | API (entrypoint resolves config LAZILY) | D-07; crash-isolation: no config import at module top (Pitfall 6). |
| Form markup / discipline toggle / throw-list UI | Browser / Client (`score-entry.js`) | Frontend Server (thin Jinja host) | SCE-01: behavior lives in ONE JS module; host page is a dumb mount. |

## Standard Stack

**Zero new packages.** This phase is 100% in-repo composition. Confirmed against the locked `.planning/REQUIREMENTS.md` ("Nessuna nuova dipendenza runtime ... stdlib + pydantic lato server, vanilla JS + native `<dialog>` lato client") and `STACK.md` (zero-new-dependency).

### Core (all already present)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | (already a dep, imported INSIDE `create_app`) | Serves `/score-entry` (new GET) + authoritative `POST /score` | The console's only web framework; lazy-imported to keep `import segugio.ui` Flask-free. [VERIFIED: in-repo `app.py`] |
| `segugio.ui.score_calc` (stdlib: `decimal`/`re`/`dataclasses`/`enum` + `opcomm.records.Discipline`) | Phase-15 shipped | The authority `POST /score` calls; `score-calc.js` ports `compute`. | Pure, crash-isolated, Decimal-exact. [VERIFIED: in-repo `score_calc.py`, on `PHASE1_SURFACE`] |
| `segugio.opcomm.channel` / `.atomic` | shipped | `write_score`, `atomic_write_text`, never-raise `read_*`. | The atomic write boundary; never hand-roll `open().write()`. [VERIFIED: in-repo `channel.py`] |
| Vanilla JS (ES2020, no build step) | — | `score-entry.js` + `score-calc.js`, served by Flask static folder | The `overlay-render.js` precedent: served raw at `/static/*.js`, IIFE with `module.exports` for node tests. [VERIFIED: in-repo] |
| `node` (dev-only, test runtime) | already used | Runs the JS drift-guard parity test | Already a dev prerequisite (`shutil.which("node")`, `_requires_node` skip). [VERIFIED: in-repo `test_ui_overlay_render.py`] |

### Supporting (already present)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `segugio.config.discipline.adapt_scoring_profile` | Phase-15 shipped | Bridges pydantic `ScoringProfile` → plain `score_calc.ScoringProfile` at the entrypoint | Call LAZILY in `app.py:__main__` (like `load_config`), NEVER at module top. [VERIFIED: in-repo] |
| `score_calc.CSEN_DISC_PROFILE` / `FCI_AGILITY_PROFILE` | shipped | Built-in default profiles when no config path is given | The `create_app` default when `overlay_cfg`-style injection passes nothing. [VERIFIED: in-repo] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inlined JSON blob for profile injection (recommended) | A small `GET /score-entry-cfg` JSON route | The GET adds a round-trip + a second route to crash-isolation-test; the inlined blob is the proven `cam_ids \| tojson` pattern and is fetched-free. Use the blob. |
| Byte-exact JS calc port + drift-guard (LOCKED D-09) | Server-only calc via a pure `POST /score/preview` route the client calls per keystroke | The preview-route adds a network round-trip per keystroke on contended WiFi (the retired SCV-01 `/score/preview` was removed for exactly this); the mirror is the project's chosen discipline. LOCKED — do not propose. |
| Fixed-scale integer decimal in JS | `Number` float math | Float drift: `0.1+0.2 !== 0.3`; best-5-of-N and `0.5` bonuses would stringify differently from Python `Decimal` and FAIL the drift-guard. Use integer/string decimal. |

**Installation:** None. No `pip install`, no `npm install`. New files only.

## Package Legitimacy Audit

> Not applicable — this phase installs **zero external packages**. All code is new in-repo modules (`score-entry.js`, `score-calc.js`) plus edits to existing files. No registry lookup needed.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
OPERATOR (tablet, dedicated WiFi LAN — no internet)
   │  opens
   ▼
GET /score-entry  ──►  templates/score-entry.html  (THIN Jinja host)
   │                     • inlines  <script type="application/json" id="score-cfg">
   │                       { sport, disciplines[], profile{zones,bonuses,freestyle_cats,
   │                         per_throw_cap,count_best_n,freestyle_max,agility_model,...} }
   │                     • <script src="/static/score-calc.js">   (advisory port)
   │                     • <script src="/static/score-entry.js">  (the ONE component)
   ▼
score-entry.js  mount(root, cfg)            ◄── reads the inlined cfg blob
   │  builds per-discipline fields from cfg.profile
   │  disc T&F → repeatable THROW LIST (zone band + midair + corridor)   [D-01]
   │  freestyle → 4 category inputs + manual adjustment
   │  agility → tempo/sct + course_faults|course_deductions + eliminated
   │
   ├─ on input  ─► score-calc.js .compute(discipline, fields, profile)  ──► LIVE total (advisory, D-02)
   ├─ on blur    ─► score-calc.js .validate(...) ──► per-field error chip (advisory, D-03)
   │
   └─ on submit (button always enabled, D-04)
         │  collect RAW structured inputs  (NO client-computed total — D-08)
         ▼
   POST /score   { discipline, throws:[{zone,midair,corridor},…]  OR
                   {team,dog,player,catch,adjustment}  OR
                   {tempo,sct,course_faults|course_deductions,eliminated} }
         │
         ▼  (app.py — AUTHORITATIVE, replaces the manual-totale path)
   discipline = Discipline(raw)              # 400 on unknown (existing)
   errors = score_calc.validate(discipline, fields, PROFILE)
   if errors:  return (jsonify({"errors": errors}), 400)   # ★ WRITE NOTHING (SCC-01)
   computed = score_calc.compute(discipline, fields, PROFILE)   # Decimal recompute
   write_score(score.json, ScoreDoc(discipline, computed))      # atomic
   atomic_write_text(overlay.txt, render_overlay_text(doc))     # flat fallback (display-only)
   _bump_score_gen()                          # gen++ only; PRESERVE running/started_at (WR-03)
   return ("", 204)
         │
         ├─ 2xx ─► banner "✓ In onda"                       [D-05]
         └─ 400 ─► banner: map errors onto fields +
                   "punteggio precedente invariato"          [D-05] (prev on-air untouched)

   ── round-trip read side (the acceptance test) ──
   GET /overlay-json → {discipline, fields(incl. computed totale), running, started_at, gen, server_now}
   overlay.txt line  → render_overlay_text reads the FLAT `totale` key (unchanged, display-only)

   DRIFT-GUARD (CI, node):  score-calc.js .compute  ==  score_calc.compute   (shared fixtures)  [SCC-03]
```

### Component Responsibilities
| Component | Responsibility | New / Modified |
|-----------|----------------|----------------|
| `static/score-entry.js` | The ONE shared component: `mount(root, cfg)` factory (dual export `window.SEGUGIO_SCORE_ENTRY` + `module.exports`). Builds per-discipline fields incl. the disc-T&F throw list; live advisory total + on-blur errors; POSTs RAW inputs; renders the persistent result banner. | **NEW** |
| `static/score-calc.js` | Byte-exact ADVISORY port of `score_calc.validate` + `compute` with a fixed-scale decimal helper. IIFE + `module.exports` (node parity test). Never the authority. | **NEW** |
| `templates/score-entry.html` | THIN full-screen Jinja host (like `overlay.html`): inlines the cfg JSON blob, `<script src>`s the two JS files, a `#score-entry-root` mount node. No form logic, no `<input>` of its own. | **NEW** |
| `app.py` `GET /score-entry` | New thin host route: render `score-entry.html` with the injected profile/disciplines. No score data baked in. | **NEW route** |
| `app.py` `POST /score` | Made AUTHORITATIVE (D-08): parse RAW structured inputs → `validate` → 400-write-nothing → `compute` → atomic write + `_bump_score_gen`. Retire the manual-`totale` verbatim path. | **MODIFIED** |
| `app.py` `create_app(...)` | Accept the active profile + valid-discipline list as a plain arg (the `cam_ids`/`overlay_cfg` precedent), default to `CSEN_DISC_PROFILE`. | **MODIFIED (signature additive)** |
| `app.py` `__main__` | Resolve `cfg.field` → `adapt_scoring_profile(cfg.field.scoring)` + the valid-discipline list LAZILY (like `load_config`), pass into `create_app`. | **MODIFIED** |
| `score_calc.py` | UNCHANGED (the authority already exists). `score-calc.js` mirrors it; mark with a `gsd:score-calc-mirror` sentinel block as the parity anchor. | **UNCHANGED** |
| `score_render.py` | UNCHANGED — stays display-only. `compute()` already emits the flat `totale`/`prese`/`zona`/`tempo`/`sct`/`faults` keys it reads. | **UNCHANGED** |
| `tests/test_imports.py` | EXTEND `PHASE1_SURFACE` is not needed (no new Python module); but the `test_console_resolves_with_heavy_stack_and_numpy_absent` POST round-trip must still pass with the now-authoritative route (already tolerant of 200/204). | **VERIFY (already tolerant)** |

### Recommended Project Structure
```
src/segugio/ui/
├── app.py                      # MODIFIED: /score authoritative, + GET /score-entry, profile arg
├── score_calc.py               # UNCHANGED (the authority)
├── score_render.py             # UNCHANGED (display-only)
├── templates/
│   ├── console.html            # UNCHANGED in P16 (modal mount is P17; legacy #form-score stays)
│   ├── score-entry.html        # NEW: thin full-screen host for the dedicated form
│   └── overlay.html            # UNCHANGED
└── static/
    ├── score-entry.js          # NEW: the ONE shared component (mount(root,cfg))
    ├── score-calc.js           # NEW: byte-exact advisory port + gsd:score-calc-mirror block
    └── overlay-render.js       # UNCHANGED (the shared-module + drift-guard precedent)

tests/
├── test_ui_score_calc_js.py    # NEW: node drift-guard — same fixtures through score_calc.py + score-calc.js
├── test_ui_score_entry.py      # NEW: served-JS asserts (no innerHTML sink, dual export, throw-list, no host-page form logic)
├── test_ui_score_authoritative.py # NEW: POST /score 400-write-nothing, Decimal recompute, prev-on-air-untouched, round-trip
└── test_ui_score.py            # EXISTING: the legacy display-only tests — REVIEW (the manual-totale path is retired)
```

### Pattern 1: Profile + disciplines injected as an inlined JSON blob (D-07)
**What:** The entrypoint resolves the active profile and valid-discipline list and passes them to `create_app`; `GET /score-entry` renders them into the page as `{{ score_cfg | tojson }}` inside `<script type="application/json" id="score-cfg">`. `score-entry.js` reads `JSON.parse(document.getElementById("score-cfg").textContent)` at mount.
**When to use:** Every config value the client needs and that must not break crash-isolation.
**Why this over a GET route:** zero extra round-trip, zero extra route to crash-isolation-test, and it is the EXACT shipped `cam_ids | tojson` mechanism already in `console.html` (`const CAMS = {{ cam_ids | tojson }}`).
**Example (host page + entrypoint):**
```html
<!-- templates/score-entry.html (THIN host — mirrors overlay.html) — Source: in-repo console.html cam_ids precedent -->
<script type="application/json" id="score-cfg">{{ score_cfg | tojson }}</script>
<div id="score-entry-root"></div>
<script src="/static/score-calc.js"></script>
<script src="/static/score-entry.js"></script>
```
```python
# app.py __main__ — resolve the profile LAZILY (the load_config precedent; NEVER module-top).
# Source: in-repo app.py cam_ids/overlay_cfg resolution + config/discipline.adapt_scoring_profile
if _cfg_path:
    from ..config.loader import load_config            # lazy — config import stays out of module top
    from ..config.discipline import adapt_scoring_profile
    _cfg = load_config(_cfg_path)
    _profile = adapt_scoring_profile(_cfg.field.scoring)   # pydantic → plain score_calc.ScoringProfile
    _sport = _cfg.field.sport                              # "disc_dog" | "agility"
else:
    from ..ui.score_calc import CSEN_DISC_PROFILE          # built-in default
    _profile, _sport = CSEN_DISC_PROFILE, "disc_dog"
app = create_app(_dir, cam_ids=_cam_ids, overlay_cfg=_overlay_cfg, profile=_profile, sport=_sport)
```
**Valid-discipline derivation (D-06):** `sport == "disc_dog"` → `["disc_tf", "disc_freestyle"]`; `sport == "agility"` → `["agility"]`. Both disc disciplines share the one `DiscDogProfile.scoring` (zones drive T&F, `freestyle_cats` drive Freestyle).

**Crash-isolation note:** the plain `score_calc.ScoringProfile` is a frozen dataclass of tuples/`Decimal`/str/int — to JSON-ize it for the blob, convert `Decimal` to **string** (not float — Pitfall: float drift) inside `create_app` using stdlib only. A tiny `_profile_to_json(profile)` helper that emits `{"zones": [[band, str(points)], …], "bonuses": [[key, str(value)], …], "freestyle_cats": [[name, str(min), str(max), str(inc)], …], "per_throw_cap": str|None, "count_best_n": int|None, "freestyle_max": str, "agility_model": str, …}` keeps every numeric as a decimal string the JS decimal helper parses exactly.

### Pattern 2: One pure calc authority (Python) + byte-exact advisory JS port + drift-guard (LOCKED D-09 / SCC-03)
**What:** `score_calc.py` stays the ONE authority. `score-calc.js` is a byte-exact port used ONLY for the live total + advisory per-field errors. A node-vs-Python drift-guard feeds shared fixtures through both and asserts equality — the EXACT mechanism the shipped `overlay-render.js` ↔ `score_render.py` uses (`test_ui_overlay_render.py::test_cleanfield_byte_parity_with_python_clean`, `test_value_crosscheck`).
**When to use:** The advisory live feedback. The server ALWAYS recomputes; the client never sends a computed total.
**Critical rule:** the client POSTs RAW inputs (throws, categories, times, faults). Only Python's `compute()` writes the file → even if the JS port drifts, the on-air score is whatever Python produced (they CANNOT diverge because only one writes).
**Decimal-equivalence (the hard part of D-09):** Python uses `Decimal` end-to-end and stringifies verbatim (`"19.0"`, never `"19.000…04"`). JS `Number` would drift. Port `compute` with a **fixed-scale integer decimal helper** that mirrors each Python op:
- best-5-of-N: parse each operand as a scaled integer, add as integers, `sorted(reverse)[:n]`, sum — then format back to a Decimal string. Mirrors `_compute_disc_tf`.
- freestyle: `quantize(inc, ROUND_HALF_UP)` per category → scaled-integer round-half-up; sum; cap at `freestyle_max`; minus `adjustment`. Mirrors `_compute_freestyle`.
- agility time-faults: `ceil(rate * max(0, run - sct))` with `mm:ss(.cc)` parsing → centisecond integer math; `ROUND_CEILING`. Mirrors `_compute_agility` + `_parse_time_seconds` + `_time_faults`.
- truthy bonus flag: mirror `_is_truthy_flag` EXACTLY (`{"true","1","yes","on"}` lowercased/trimmed) — CR-01 from Phase 15 is now live because REAL form-string flags flow in (a checkbox posts `"on"`/absent; map to the strict set).
**Example (parity test, near-verbatim clone of the shipped one):**
```python
# tests/test_ui_score_calc_js.py — Source: clone of test_ui_overlay_render.py::test_cleanfield_byte_parity_with_python_clean
@_requires_node
def test_compute_byte_parity_with_python():
    js = _read_file_js()  # static/score-calc.js
    fixtures = [  # one per discipline + edge cases (best-5-of-N, 0.5 bonus, freestyle cap, agility ceil, elimination)
        {"discipline": "disc_tf", "fields": {"throws": [{"zone": 4, "midair": "on", "corridor": "on"}, ...]}},
        {"discipline": "disc_freestyle", "fields": {"team": "8.33", "dog": "7.50", "player": "9.01", "catch": "8.00", "adjustment": "1.5"}},
        {"discipline": "agility", "fields": {"tempo": "0:42.50", "sct": "0:40.00", "course_faults": "5"}},
    ]
    driver = js + "\nconst _m=module.exports;\nconst _p=PROFILE_JSON;\n" + \
        "process.stdout.write(JSON.stringify(_in.map(f => _m.compute(f.discipline, f.fields, _p))));\n"
    js_out = json.loads(_run_node(driver))
    py_out = [score_calc.compute(f["discipline"], f["fields"], PROFILE) for f in fixtures]
    # compare the FLAT summary keys the renderer reads (totale/prese/zona/faults/result) — the on-air contract
    for j, p in zip(js_out, py_out):
        assert j["totale"] == p["totale"]
```
**Sentinel discipline (Pitfall 1 guard):** wrap the ported functions in a `// ===== gsd:score-calc-mirror:start/end =====` block exactly like `gsd:scv01-mirror`, and add a served-JS assert that the block + each ported function name is present. This is the project's accepted "mirror + drift-guard" pattern for a NECESSARY second tier (advisory client); it is NOT the retired SCV-01 byte-exact-text mirror (that mirrored a display string with no authority; here the server is the authority and the JS is provably advisory).

### Pattern 3: Authoritative `POST /score` — validate-before-write, preserve run-state
**What:** Parse RAW per-discipline inputs into the dict `score_calc` expects, validate, 400-write-nothing on errors, compute, atomic write, gen-bump preserving `running`/`started_at`.
**Why validate-before-write:** SCC-01 broadcast-integrity guarantee (D-05 "punteggio precedente invariato") — a rejected submit must leave the previous on-air `score.json`/`overlay.txt` byte-untouched. The route must do NO write before `validate()` returns clean.
**Example:**
```python
# app.py POST /score (authoritative) — Source: in-repo app.py + score_calc contract + ARCHITECTURE.md Pattern 2
@app.post("/score")
def post_score():
    raw = request.form  # or request.get_json() — see "wire format" below
    try:
        discipline = Discipline(raw.get("discipline", Discipline.disc_tf.value))
    except ValueError:
        return ("disciplina sconosciuta", 400)
    fields = _parse_structured_inputs(discipline, raw)        # build throws[]/categories/agility dict
    errors = score_calc.validate(discipline, fields, profile) # profile injected at create_app
    if errors:
        return (jsonify({"errors": errors}), 400)             # ★ NO write — prev on-air untouched
    computed = score_calc.compute(discipline, fields, profile)
    doc = ScoreDoc(discipline=discipline, fields=computed)
    write_score(_path(_SCORE_FILE), doc)                      # atomic
    atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # flat fallback, display-only
    _bump_score_gen()                                         # gen++ only; preserves running/started_at (WR-03)
    return ("", 204)
```

### Wire format for `throws[]` (a real planning decision)
The disc-T&F `throws` is a **list of dicts** — `request.form` (urlencoded) does not natively carry nested lists. Two viable shapes (planner picks one; recommend **A** for simplicity and to match the JSON the JS already builds):
- **(A) JSON body:** the form POSTs `Content-Type: application/json` with `{"discipline","throws":[{"zone":4,"midair":true,"corridor":false},…]}`. Server uses `request.get_json(silent=True)`. Clean nested structure; `validate`/`compute` consume `throws` directly. *Tradeoff:* changes the content-type from the existing `application/x-www-form-urlencoded` (the legacy `console.html` form path stays urlencoded — fine, they are different routes/forms in P16).
- **(B) Indexed form keys:** `throws[0][zone]=4&throws[0][midair]=on&…`, server reassembles into a list. *Tradeoff:* fiddly parsing, easy to get the strict-flag truthiness wrong; no upside over (A).
**Recommendation: (A) JSON body** for `POST /score` from the new component. `_is_truthy_flag` in `score_calc` already handles bool AND string flags, so either a JSON `true` or a string `"on"` validates correctly (CR-01 holds). [VERIFIED: in-repo `_is_truthy_flag`]

### Anti-Patterns to Avoid
- **Client computes the authoritative total and POSTs it** → breaks publish-and-render; a drifted JS port airs a wrong score. POST raw inputs; server recomputes. (D-08, Pitfall 2)
- **Client-only validation** → a `curl`/stale-tab POST airs garbage. Server `validate()` is the gate; 400-write-nothing. (Pitfall 3)
- **Arithmetic in `render_overlay_text`/`overlay-render.js`** → 3rd source of truth. They stay display-only; `compute()` produces `totale`. (Pitfall 2)
- **`import segugio.config`/`numpy` at a `segugio.ui` module top** → crash-isolation breach. Inject the profile as a plain arg; adapt LAZILY in the entrypoint. (Pitfall 6)
- **iframe the form / hand-copy the component for the future modal** → re-introduces SCV-01 drift. ONE `mount(root,cfg)` module; the dedicated page is its only host in P16. (Pitfall 1, SCE-01)
- **`innerHTML` for any operator value** (esp. freestyle `nome`, future judge names) → XSS on air. `textContent`/`createTextNode` only. (Pitfall 5)
- **localStorage / progressive-across-reload state in P16** → that's Phase 17 (SCC-05). In-session memory only (D-01a).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Score calc / validation | A new JS or Python calc with its own rules | `score_calc.validate`/`compute` (server) + the byte-exact `score-calc.js` port (advisory) | The authority already exists, Decimal-exact, CSEN-verified 11/11. A second ruleset drifts (Pitfall 2). |
| Atomic file write | `open(path,"w").write(...)` | `write_score` / `atomic_write_text` | Torn-file reads are exactly what the channel was built to prevent (Pitfall 7). |
| gen bump | A new counter / bump outside the lock | `_bump_score_gen()` under `_gen_lock` | Preserves `running`/`started_at` (WR-03); monotonic `gen` the overlay cache-bust depends on. |
| Profile → client transport | A new config endpoint + parser | `{{ score_cfg \| tojson }}` inlined blob | The shipped `cam_ids \| tojson` precedent; zero new route to crash-isolation-test. |
| Decimal in JS | `Number` float math | A fixed-scale integer/string decimal helper mirroring `Decimal` ops | Float drift fails the drift-guard; `0.5+0.5`, best-N, `quantize` must match Python. |
| Discipline whitelist | A manual string list | `Discipline(...)` enum coercion (existing) + the injected valid-discipline list (D-06) | Already the boundary guard; unknown → 400. |
| JS↔Python parity harness | A bespoke comparison | Clone `test_ui_overlay_render.py`'s node driver + `_run_node` UTF-8 helper | The exact shipped, Windows-UTF-8-correct mechanism. |

**Key insight:** every "hard" piece of this phase was already solved and shipped (Phase 15 calc, the v1.2 mirror+drift-guard, the atomic write + gen-bump + run-state preservation). The phase's real work is *wiring them correctly and not re-introducing the retired bugs*.

## Common Pitfalls

### Pitfall 1: Double source of truth — client total ≠ on-air total (SCC-03 / D-09)
**What goes wrong:** the form shows 19.0 but 19.000…04 (or 18.5) airs because the JS port uses float math or a subtly different rule.
**Why:** JS `Number` ≠ Python `Decimal`; or the two rulesets edited independently.
**How to avoid:** POST RAW inputs (server recomputes — they can't diverge by construction); port with a fixed-scale decimal helper; the drift-guard test pins parity on the FLAT summary keys; mark the port with a `gsd:score-calc-mirror` sentinel.
**Warning signs:** `parseFloat`/`Number(...)+Number(...)` in `score-calc.js`; the round-trip acceptance test fails on a `0.5` or best-N fixture.

### Pitfall 2: Client-only validation bypassable by a direct LAN POST (SCC-01 / Pitfall 3)
**What goes wrong:** `curl -d discipline=agility,tempo=notatime` round-trips a malformed score on air.
**Why:** the legacy `POST /score` accepts any non-empty field verbatim; client JS validation doesn't protect the route.
**How to avoid:** server `validate()` is the gate; 400 + write NOTHING; validate-BEFORE-write so the previous on-air score is byte-untouched.
**Warning signs:** the route writes before `validate()`; an invalid POST returns 204; `score.json` mtime changes on a rejected submit.

### Pitfall 3: Crash-isolation breach via the profile injection (Pitfall 6)
**What goes wrong:** a `from ..config.discipline import adapt_scoring_profile` (or `import numpy`) lands at a `segugio.ui` module top → `test_console_resolves_with_heavy_stack_and_numpy_absent` fails.
**Why:** the adapter lives in the heavy config tier; importing it at module top pulls pydantic+config in.
**How to avoid:** adapt LAZILY in the entrypoint (`__main__`), pass the resulting PLAIN dataclass into `create_app`; the default is the stdlib-only `CSEN_DISC_PROFILE`. `create_app` builds with the heavy stack absent.
**Warning signs:** any `from ..config` at a `ui` module top; the import-smoke test fails or is weakened.

### Pitfall 4: Agility field-name mismatch (the legacy form vs the score_calc contract)
**What goes wrong:** the legacy `console.html` agility form posts a manual `faults` total; `score_calc` agility expects `tempo`/`sct` + `course_faults` (count_up) OR `course_deductions` (deduct) + `eliminated`, and COMPUTES `faults`/`result`/`totale`. Reusing the legacy field names silently fails validation or computes wrong.
**Why:** the legacy path was display-only; the authoritative path needs the RAW inputs `score_calc` was written for.
**How to avoid:** the new component posts the `score_calc` field names. Pick `course_faults` vs `course_deductions` from `profile.agility_model`. Surface `eliminated` as a checkbox (elimination short-circuits validation AND compute). [VERIFIED: in-repo `score_calc.validate`/`_compute_agility`]
**Warning signs:** an agility POST 400s on a "missing course_faults" the form never offered; the overlay `Faults` cell shows the operator's typed total instead of the computed one.

### Pitfall 5: Freestyle bonus/flag truthiness on real form strings (CR-01, now LIVE)
**What goes wrong:** a checkbox bonus posts `"on"` (or `"false"`/`"0"` from a hidden field) and a naive `if throw[key]` scores it truthy → inflates the total.
**Why:** Phase 16 is the FIRST place real form-string flags flow into `compute()`; CR-01 was fixed in `score_calc._is_truthy_flag` but the JS port must mirror it.
**How to avoid:** the JS port's bonus check uses the SAME strict set `{"true","1","yes","on"}` (trim+lowercase) as `_is_truthy_flag`; the drift-guard includes a `"false"`/`"0"` flag fixture.
**Warning signs:** a throw with an unchecked bonus posting `"false"` adds 0.5 in the JS preview; the drift-guard's flag fixture fails.

### Pitfall 6: Breaking `overlay.txt` / `/overlay-json` continuity (Pitfall 4 in PITFALLS.md)
**What goes wrong:** the rich inputs stop producing the flat `totale`/`prese`/`zona`/`tempo`/`sct`/`faults` keys → `render_overlay_text` blanks, the OBS text fallback breaks.
**Why:** `compute()` MUST emit the flat summary keys (it does today — SCR-04); a refactor that bypasses `compute()` loses them.
**How to avoid:** always route through `compute()` (it adds the flat keys); keep `render_overlay_text` reading them verbatim; the round-trip acceptance test pins `overlay.txt` line === `/overlay-json` total === form total.
**Warning signs:** `overlay.txt` blank/missing after a rich POST; `/overlay-json` `fields` missing `totale`.

## Runtime State Inventory

> This is a feature-addition phase, not a rename/migration. Included for the one item that matters: the retired legacy write path.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `score.json` / `overlay.txt` schema UNCHANGED — `ScoreDoc{discipline, fields}` already a free-form dict; `compute()` writes the same flat keys the legacy path wrote. No data migration. | None — additive, byte-compatible at the file level. |
| Live service config | None — no external service holds score-entry state. | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | `SEGUGIO_CONFIG` / `SEGUGIO_OPCOMM_DIR` / `SEGUGIO_CAM_IDS` unchanged; the profile is resolved from the same `SEGUGIO_CONFIG` path. | None — reuse the existing env resolution. |
| Build artifacts | None — new `.js`/`.html`/`.py` files, no package rebuild. | None. |
| **Retired code path** | The legacy display-only `post_score` (app.py:193, manual `totale` verbatim) AND the legacy `console.html` `#form-score` (3 inline fieldsets posting manual flat keys). | P16: `POST /score` becomes authoritative (D-08). The console `#form-score` is NOT removed in P16 (its retirement is P17 with the modal) — but it now posts to an AUTHORITATIVE route that expects RAW inputs. **Planning risk:** the legacy `console.html` form still posts manual `prese`/`zona`/`totale`/manual-`faults`; after `POST /score` becomes authoritative those legacy posts will 400 (missing `throws[]`/`course_faults`). The planner MUST decide: (a) keep a back-compat branch in `POST /score` for the legacy flat keys until P17 retires the form, OR (b) update `console.html`'s `#form-score` submit to the new component in P16. **Recommend (a)** a thin legacy-compat acceptance during transition, since `console.html` modal+partial retirement is explicitly P17 — see Open Question 1. |

## Code Examples

### Reading the injected cfg blob in `score-entry.js` (mount)
```js
// static/score-entry.js — Source: in-repo console.html "{{ cam_ids | tojson }}" + overlay-render.js mount pattern
(function () {
  "use strict";
  function mount(root, cfg) {
    // cfg = { sport, disciplines:[...], profile:{ zones, bonuses, freestyle_cats, per_throw_cap,
    //         count_best_n, freestyle_max, agility_model, ... all numerics as DECIMAL STRINGS } }
    const calc = (typeof window !== "undefined" && window.SEGUGIO_SCORE_CALC) || (typeof require !== "undefined" && require("./score-calc.js"));
    // build per-discipline fields from cfg.disciplines / cfg.profile; wire input→live total, blur→errors, submit→POST
  }
  function autoMount() {
    if (typeof document === "undefined") return null;
    const el = document.getElementById("score-cfg");
    const cfg = el ? JSON.parse(el.textContent) : {};
    return mount(document.getElementById("score-entry-root"), cfg);
  }
  const api = { mount };
  if (typeof window !== "undefined") window.SEGUGIO_SCORE_ENTRY = api;   // dual export (SCE-01: re-mountable in P17 modal)
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", autoMount);
    else autoMount();
  }
})();
```

### Persistent result banner (D-05)
```js
// Source: D-05 (persistent inline banner, not a toast)
async function publish(root, discipline, fields) {
  const r = await fetch("/score", { method: "POST", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ discipline, ...fields }) });
  const banner = root.querySelector("#publish-banner");
  if (r.status === 204 || r.ok) {
    banner.textContent = "✓ In onda";                          // success, stays until next action
    banner.className = "banner ok";
  } else if (r.status === 400) {
    const { errors } = await r.json();                         // [{field, message}] from score_calc.validate
    paintFieldErrors(root, errors);                            // map onto fields (textContent only)
    banner.textContent = "Errore — punteggio precedente invariato"; // prev on-air untouched (D-05)
    banner.className = "banner error";
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `POST /score` display-only, trusts manual `totale` | Authoritative: validate→recompute (Decimal)→write | This phase (D-08/SCC-01) | The server is the sole authority; the client can never air a wrong/bypassing score. |
| Manual flat-key entry (`prese`/`zona`/`totale`) | RAW structured inputs (`throws[]`, freestyle cats, agility raw) recomputed server-side | This phase | Disc T&F best-5-of-N becomes a real auto-calc (D-01). |
| Per-surface form copies / byte-exact text mirror (SCV-01, retired) | ONE `mount(root,cfg)` module + advisory calc port with drift-guard | v1.2 SCV-02 lesson, applied here | Drift structurally impossible for the form's behavior; the JS calc is provably advisory. |

**Deprecated/outdated:** the manual-`totale` trust path in `post_score` (retired this phase, D-08). The legacy `console.html` `#form-score` is superseded but not removed until P17.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The new `POST /score` should accept a JSON body for `throws[]` (Pattern: wire format A), while the legacy urlencoded `console.html` form needs a transition story. | Wire format / Runtime State Inventory | If the planner prefers urlencoded indexed keys, the parser differs; LOW risk (both consume the same `score_calc` dict). |
| A2 | The legacy `console.html` `#form-score` is kept in P16 (its modal retirement is P17), so `POST /score` needs a back-compat branch for legacy flat keys OR the console form is repointed. | Open Question 1, Runtime State Inventory | If the planner removes the form in P16, that pulls P17 scope forward; MEDIUM — must be an explicit plan decision. |
| A3 | `cfg.field` exposes `.sport` and `.scoring` for any loaded config (disc_dog or agility). | Pattern 1 | Verified against `config/discipline.py` (`FieldProfile = DiscDogProfile | AgilityProfile`, both have `sport` + `scoring`). LOW. |
| A4 | A fixed-scale integer/string decimal helper in JS can reproduce every `score_calc` Decimal op (quantize ROUND_HALF_UP, ceil, best-N) byte-exactly. | Pattern 2 | If an op resists exact porting, the drift-guard catches it pre-merge; LOW (the ops are simple add/sort/round/ceil over 2-dp scales). |

**Note:** No `[ASSUMED]` claim here is a locked decision — A1/A2 are planning choices the planner finalizes; A3/A4 are verified-low-risk.

## Open Questions

1. **Legacy `console.html` `#form-score` compatibility during the P16→P17 transition.**
   - What we know: P16 makes `POST /score` authoritative (expects RAW structured inputs); the legacy console form still posts manual flat keys (`prese`/`zona`/`totale`, manual `faults`); the modal+partial retirement of that form is explicitly Phase 17.
   - What's unclear: does P16 (a) add a thin back-compat branch in `POST /score` accepting the legacy flat keys (so the legacy console form keeps working until P17), or (b) repoint `console.html`'s submit to the new component now?
   - Recommendation: **(a)** a clearly-marked transition branch (or: route the legacy form through `score_calc` by treating its manual flat keys as a pre-computed display-only fallback) so the existing `test_ui_score.py` round-trips stay green and P17 cleanly retires the form. The planner should make this an explicit task with its own acceptance test. *(This is the single most important planning decision in the phase.)*

2. **Decimal-string JSON for the profile blob.**
   - What we know: the profile must reach the client without float drift; `Decimal` must serialize as a string.
   - What's unclear: nothing blocking — just confirm the `_profile_to_json` helper emits every numeric as a string and the JS decimal helper parses strings (not `Number`).
   - Recommendation: pin a unit test asserting `json.loads(blob)["per_throw_cap"] == "5"` (string), not `5.0`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib (`decimal`/`re`/`json`/`threading`) | server calc + route | ✓ | — | — |
| Flask | `/score-entry`, `POST /score` | ✓ (project dep) | — | — |
| `node` | JS drift-guard parity test (dev/CI only) | ✓ (already used by `test_ui_overlay_render.py`) | — | test SKIPS via `_requires_node` if absent (non-blocking) |
| Internet / CDN | — | ✗ (rig is offline LAN) | — | N/A — all assets self-hosted under `/static` (P16 reuses the offline pattern; full no-CDN hardening is P17) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `node` (the parity test self-skips when absent — but CI/dev should have it; the drift-guard is the SCC-03 acceptance, so a node-present run is required to verify the phase).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ Flask test client; node subprocess for JS parity) |
| Config file | `tests/conftest.py` (provides `file_channel` fixture: `dir`/`score`/`overlay` paths) |
| Quick run command | `pytest tests/test_ui_score_authoritative.py -x` |
| Full suite command | `pytest tests/ -q` |
| JS parity command | `pytest tests/test_ui_score_calc_js.py -x` (requires `node`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCC-01 | Invalid input → 400 AND nothing written (prev on-air `score.json`/`overlay.txt` byte-untouched) | integration | `pytest tests/test_ui_score_authoritative.py::test_invalid_post_400_writes_nothing -x` | ❌ Wave 0 |
| SCC-01 | Valid input → server recomputes the Decimal total → atomic `score.json` + `overlay.txt` | integration | `pytest tests/test_ui_score_authoritative.py::test_valid_post_recomputes_and_writes -x` | ❌ Wave 0 |
| SCC-01 / WR-03 | A `/score` write bumps `gen` but preserves `running`/`started_at` | integration | `pytest tests/test_ui_score_authoritative.py::test_score_preserves_run_state -x` | ❌ Wave 0 |
| SCC-01 (acceptance) | form total === `overlay.txt` line === `/overlay-json` total for the same inputs | integration | `pytest tests/test_ui_score_authoritative.py::test_round_trip_total_equality -x` | ❌ Wave 0 |
| SCC-03 / D-09 | `score-calc.js .compute` === `score_calc.compute` for shared fixtures (best-N, 0.5 bonus, freestyle cap, agility ceil, elimination, "false"/"on" flags) | unit (node) | `pytest tests/test_ui_score_calc_js.py::test_compute_byte_parity_with_python -x` | ❌ Wave 0 |
| SCC-03 | `score-calc.js .validate` === `score_calc.validate` (error fields match) | unit (node) | `pytest tests/test_ui_score_calc_js.py::test_validate_parity -x` | ❌ Wave 0 |
| SCE-01 | `score-entry.js` exports `mount` on `window` AND `module.exports` (re-mountable for P17); the `/score-entry` host page contains NO `<input>`/calc logic of its own | unit (served-JS) | `pytest tests/test_ui_score_entry.py::test_dual_export_and_thin_host -x` | ❌ Wave 0 |
| SCE-02 | `/score-entry` renders disc-dog → T&F+Freestyle (agility config → Agility only); fields driven by the injected profile | integration | `pytest tests/test_ui_score_entry.py::test_disciplines_from_profile -x` | ❌ Wave 0 |
| SCE-02/05 | No `innerHTML` sink for operator values (`nome`); values via `textContent` | unit (served-JS) | `pytest tests/test_ui_score_entry.py::test_no_innerhtml_sink -x` | ❌ Wave 0 |
| SCE-03 | Live total updates IN PLACE on input (advisory, labeled non-authoritative) | unit (node DOM harness, optional) | `pytest tests/test_ui_score_entry.py::test_live_total_advisory -x` | ❌ Wave 0 |
| crash-isolation (inherited RBT-08) | console + authoritative `POST /score` import/resolve with torch/cv2/numpy/cyndilib/obsws absent | integration | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ✅ (exists; already tolerant of 200/204 — verify still green) |
| regression | legacy display-only round-trips (transition decision, Open Q1) | integration | `pytest tests/test_ui_score.py -x` | ✅ (REVIEW — may need a transition-compat task) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_ui_score_authoritative.py tests/test_ui_score_calc_js.py -x` (the two SCC gates).
- **Per wave merge:** `pytest tests/ -q` (full suite, incl. crash-isolation + legacy round-trips).
- **Phase gate:** full suite green (incl. the node parity test with `node` present) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_ui_score_authoritative.py` — covers SCC-01 (400-write-nothing, recompute, run-state preserve, round-trip equality).
- [ ] `tests/test_ui_score_calc_js.py` — covers SCC-03 (node byte-parity of `compute`/`validate`); clone the `_run_node` UTF-8 helper + `_requires_node` skip from `test_ui_overlay_render.py`.
- [ ] `tests/test_ui_score_entry.py` — covers SCE-01/02/05 (dual export, thin host, disciplines-from-profile, no-innerHTML sink).
- [ ] Shared fixtures: a `PROFILE_JSON` constant (the CSEN profile as decimal-string JSON) reused by the parity test and the authoritative route test.
- [ ] Decision task for Open Q1 (legacy console form transition) with its own acceptance test.
- Framework install: none — pytest + Flask test client + node already in use.

*(Existing `conftest.py` `file_channel` fixture covers the channel paths; no new framework needed.)*

## Security Domain

> `security_enforcement` is not set to `false` in `.planning/config.json` → included. The trust boundary is the dedicated WiFi LAN (no auth in v1 — D-02, an accepted documented decision); the relevant controls are input validation and output encoding at the overlay sink.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | None — single-operator field tool on an isolated LAN (D-02, accepted). |
| V3 Session Management | no | Stateless; no sessions. |
| V4 Access Control | no | LAN trust boundary; no per-user roles. |
| V5 Input Validation | **yes** | `score_calc.validate()` server-side gate (400-write-nothing); `Discipline(...)` enum whitelist; fixed server-side write paths (no operator-supplied filename — existing). |
| V6 Cryptography | no | No secrets/crypto in this path. |
| V14 / Output Encoding (XSS) | **yes** | `textContent`/`createTextNode` for ALL operator values (freestyle `nome` etc.); Jinja autoescape for any static label; NO `innerHTML`, NO `\| safe`. (Pitfall 5) |

### Known Threat Patterns for {Flask console + OBS browser-source}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Bypassing LAN POST airs an invalid/out-of-range score | Tampering | Server `validate()` rejects with 400, writes nothing (validate-before-write); previous on-air untouched (D-05). |
| XSS in a free-text field (`nome`, future judge names) executing in CEF on air | Tampering / Elevation | `textContent` sink only; never `innerHTML`/string-built markup; carry the `overlay-render.js` no-innerHTML gate forward to the new component. |
| Malformed/torn `score.json` from a partial write | DoS (overlay) | `atomic_write_*` (temp+fsync+replace) + never-raise `read_score`; route writes only after validation. |
| Unknown / path-like discipline value | Tampering | `Discipline(raw)` enum coercion → 400 (existing); fixed server-side filenames. |
| `gen` clobber / run-state flip on a score write | DoS (timer) | `_bump_score_gen()` under `_gen_lock`, preserves `running`/`started_at` from in-memory `_state` (WR-03). |

## Sources

### Primary (HIGH confidence — in-repo, read 2026-06-22)
- `src/segugio/ui/app.py` — `create_app(channel_dir, cam_ids, overlay_cfg)` plain-arg injection; the display-only `post_score` (line 193, manual `totale`) this phase replaces; `_bump_score_gen`/`_gen_lock`/WR-03 run-state preservation; `/overlay-json` round-trip read side; the lazy `load_config` entrypoint pattern.
- `src/segugio/ui/score_calc.py` — `validate()` (`[{field,message}]`) + `compute()` (Decimal-exact, flat summary keys), `ScoringProfile` dataclass shape, `_is_truthy_flag` (CR-01 strict set), `_parse_time_seconds`/`_time_faults`, `CSEN_DISC_PROFILE`/`FCI_AGILITY_PROFILE`.
- `src/segugio/config/discipline.py` — `adapt_scoring_profile` (pydantic→plain dataclass, lazy `score_calc` import), `DiscDogProfile | AgilityProfile` union with `.sport`/`.scoring` (D-06 valid-discipline derivation).
- `src/segugio/ui/score_render.py` — `render_overlay_text` display-only invariant (reads flat keys; stays dumb).
- `src/segugio/ui/static/overlay-render.js` + `tests/test_ui_overlay_render.py` — the node-vs-Python drift-guard PRECEDENT (`gsd:scv01-mirror` block, `_run_node` UTF-8 helper, `_requires_node` skip, byte-parity + value-crosscheck tests) to clone for `score-calc.js`.
- `src/segugio/ui/templates/console.html` — `{{ cam_ids | tojson }}` inlined-injection precedent (D-07), the existing `#form-score` (3 fieldsets, manual flat keys) superseded, the discipline-toggle JS + CSS to reuse (D-10).
- `src/segugio/opcomm/channel.py` + `records.py` — `write_score`/`atomic_write_text`/never-raise `read_*`; `ScoreDoc{discipline, fields}` free-form dict (no schema change); boundary enum coercion.
- `tests/test_imports.py` — `test_console_resolves_with_heavy_stack_and_numpy_absent` (already tolerant of the authoritative route's 200/204) + `PHASE1_SURFACE` crash-isolation gate.
- `tests/test_ui_score.py` — the legacy display-only round-trip tests to REVIEW under the transition decision.

### Secondary (HIGH — upstream phase research, treated as input)
- `.planning/research/v1.3/ARCHITECTURE.md` — `score-entry.js`/`score-calc.js` contracts, authoritative POST flow, additive data model.
- `.planning/research/v1.3/PITFALLS.md` — #1 mirror drift, #2 double source of truth, #3 client-only validation, #6 crash-isolation, #5 XSS sink (all mapped above).
- `.planning/research/v1.3/STACK.md` (zero-new-dependency) and `SUMMARY.md` (server-authoritative keystone).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new deps; every primitive is shipped and read in-repo.
- Architecture: HIGH — composes the proven shared-module + drift-guard + authoritative-write patterns; the only choices (blob vs route, JSON vs urlencoded body) are low-risk and recommended explicitly.
- Pitfalls: HIGH — each is anchored to a named, already-paid-for project decision (SCV-02, WR-03, CR-01, the crash-isolation gate).

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable — in-repo patterns, no fast-moving external dependency).
