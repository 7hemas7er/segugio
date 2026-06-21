# Architecture Research — v1.3 "Gestione Punteggi Avanzata"

**Domain:** Rich, SHARED score-entry on the crash-isolated Flask console (publish-and-render over the opcomm file channel)
**Researched:** 2026-06-21
**Confidence:** HIGH (grounded in the shipped v1.1/v1.2 codebase — `src/segugio/ui/app.py`, `score_render.py`, `overlay.html`/`overlay-render.js`, `opcomm/{records,channel}.py` — not on external sources; the patterns are the project's own proven ones)

---

## Executive Answer (for the roadmapper)

1. **Sharing approach → (B) a shared vanilla-JS component/module rendered into BOTH the dedicated page and the console modal.** NOT an iframe (C), NOT a Jinja partial (A). The SCV-02 lesson ("one renderer → drift impossible") is preserved by the *singleness of the module*, exactly as `overlay-render.js` is the one renderer behind `/overlay` and the console preview iframe. An iframe is right for a *passive render surface* (the overlay) but wrong for an *interactive form* (focus/keyboard/state/submission cross the iframe boundary awkwardly on iPadOS). A Jinja partial alone cannot give live auto-calc feedback without duplicating the calc in JS.

2. **Single source of truth for calc + validation → ONE pure module written in PYTHON, run AUTHORITATIVELY on the server, with a byte-exact JS port for live client feedback — BUT the server result always wins** (the client port is advisory UX only, never trusted). This is the same "mirror" discipline v1.2 used for `score_render._clean/_get` ↔ `overlay-render.js cleanField/scvGet`, **plus a drift-guard test** that runs the same vectors through both and asserts equality. The server-written `score.json` / `overlay.txt` are computed by the Python module; the client can never make them diverge because the client never writes them — it only POSTs raw inputs, and the server recomputes.

3. **Data model → keep `ScoreDoc{discipline, fields}` as the on-the-wire record, but make `fields` carry STRUCTURED-but-still-display-only values (multi-throw arrays, running total, freestyle criteria) that the existing renderer can ignore.** `overlay.txt` and `/overlay-json` keep emitting the SAME flat keys (`prese`/`zona`/`totale`/`tempo`/`sct`/`faults`/`nome`/`timer`) — the rich structure is *additive*; the legacy renderer reads the flat summary keys and is untouched. The server computes the flat summary keys (e.g. `totale`) from the structured inputs via the pure calc module before writing.

4. **Build order →** (P15) pure calc+validation module + drift-guard test → (P16) shared JS entry/render module + dedicated `/score-entry` page → (P17) console modal hosting the same module → (P18) richer data model wired through `/score` write + `/overlay-json` additive fields + overlay fallback verification.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CONSOLE PROCESS (crash-isolated: imports ONLY Flask + segugio.opcomm)     │
│                                                                            │
│  ┌────────────────────┐         ┌──────────────────────────────────────┐  │
│  │  Dedicated page     │         │  Console page (console.html)         │  │
│  │  GET /score-entry   │         │   └─ "Apri punteggio" → <dialog>     │  │
│  │   (full-screen      │         │       MODAL hosts the SAME module    │  │
│  │    tablet form)     │         │                                      │  │
│  └─────────┬──────────┘         └──────────────────┬───────────────────┘  │
│            │  both mount the ONE module             │                       │
│            ▼                                         ▼                       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  static/score-entry.js  — THE ONE shared score-entry component      │    │
│  │   • renderForm(root, discipline)  build per-discipline fields       │    │
│  │   • live auto-calc + validation feedback  (calls the JS port below) │    │
│  │   • on submit → POST /score  (raw inputs; NO computed authority)    │    │
│  └───────────────────────────┬──────────────────────────────────────┘    │
│                              (JS port, byte-exact, ADVISORY only)           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  static/score-calc.js   ←─ drift-guard ─→  segugio.ui.score_calc   │    │
│  │   (pure: validate(discipline,fields) + compute(discipline,fields)) │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  Flask routes (app.py)                                                      │
│   GET  /score-entry        host page for the dedicated form                 │
│   POST /score              ★ AUTHORITATIVE: validate→compute→write          │
│   GET  /overlay-json       additive rich fields (legacy keys preserved)     │
│   GET  /overlay /overlay-json /status /preview …  (unchanged)               │
│                                                                            │
│   score_calc.py  ── compute/validate (PURE, stdlib only)                    │
│   score_render.py ── render_overlay_text  (reads the FLAT summary keys)     │
│                                                                            │
└─────────────────────────── opcomm files (atomic) ─────────────────────────┘
        score.json        overlay.txt        overlay_run.json
        (structured)      (flat fallback)    (gen/running/started_at)
                                  │
                                  ▼
                    OBS browser-source GET /overlay   +   OBS text source overlay.txt (fallback)
                                  ▲ director NEVER imported / NEVER reads these
```

### Component Responsibilities

| Component | Responsibility | New / Modified |
|-----------|----------------|----------------|
| `static/score-entry.js` | The ONE shared form component: builds per-discipline fields, multi-throw rows, freestyle criteria; wires live feedback; POSTs raw inputs to `/score`. Mounted by BOTH the dedicated page and the console modal. | **NEW** |
| `static/score-calc.js` | Pure JS port of `score_calc.py` — `validate()` + `compute()`. ADVISORY (drives live feedback only); never the authority. | **NEW** |
| `segugio/ui/score_calc.py` | Pure Python module (stdlib only): `validate(discipline, fields) -> errors`, `compute(discipline, fields) -> fields_with_totals`. The AUTHORITY. Imported by `/score`. | **NEW** |
| `segugio/ui/score_render.py` | `render_overlay_text(ScoreDoc)` → flat `overlay.txt` line. Reads the FLAT summary keys (`totale` etc.) which `/score` now guarantees are present. **Largely unchanged**; may add per-discipline lines for richer summaries but must keep reading flat keys. | **MODIFIED (minimal)** |
| `templates/score-entry.html` | Thin host page for the dedicated full-screen form (mirrors how `overlay.html` is a thin host for `overlay-render.js`). Mounts `score-entry.js`. | **NEW** |
| `templates/console.html` | Add a `<dialog>`/modal container + an "Apri punteggio" button that mounts the SAME `score-entry.js` into the modal. The legacy inline `#form-score` is REPLACED by the shared component (or kept as a fallback during transition). | **MODIFIED** |
| `app.py` `POST /score` | Now AUTHORITATIVE: `validate()` (reject → 400 with messages) → `compute()` → write structured `score.json` + flat `overlay.txt`, then `_bump_score_gen()`. | **MODIFIED** |
| `app.py` `GET /score-entry` | New thin host route (like `/overlay`): render `score-entry.html`, no score data baked in. | **NEW** |
| `opcomm/records.py ScoreDoc` | `fields` stays a free-form dict but now legitimately holds structured values (lists/nested). No schema change required (it is already `dict`). | **UNCHANGED structurally** |
| `app.py` `GET /overlay-json` | Echoes `fields` verbatim (already does). The rich structure rides along; the flat keys the overlay renderer reads are still present. | **UNCHANGED** (additive payload) |

---

## Recommended Project Structure

```
src/segugio/ui/
├── app.py                      # MODIFIED: /score authoritative, + GET /score-entry
├── score_render.py             # MODIFIED minimal: still reads flat summary keys
├── score_calc.py               # NEW: pure validate() + compute() — the AUTHORITY
├── templates/
│   ├── console.html            # MODIFIED: <dialog> modal mounts score-entry.js
│   ├── score-entry.html        # NEW: thin host page for the dedicated form
│   └── overlay.html            # UNCHANGED
└── static/
    ├── score-entry.js          # NEW: the ONE shared form component (mounted twice)
    ├── score-calc.js           # NEW: byte-exact JS port of score_calc.py (advisory)
    └── overlay-render.js       # UNCHANGED (precedent for the shared-module pattern)

tests/
├── test_score_calc.py          # NEW: per-discipline validate/compute unit tests
├── test_score_calc_drift.py    # NEW: drift-guard — same vectors through py + node port
├── test_score_routes.py        # NEW/extended: /score 400-on-invalid, computed totals
└── test_crash_isolation.py     # EXTENDED: assert score_calc.py imports with heavy stack absent
```

### Structure Rationale

- **`score_calc.py` is its own pure module**, separate from `score_render.py`, mirroring how `score_render.py` was deliberately split from `app.py` so it imports with the whole heavy stack absent. `score_calc` must be stdlib-only (no Flask, no numpy) so the crash-isolation import test still passes.
- **`score-entry.js` + `score-calc.js` are two static files** so the dedicated page and the modal both `<script src>` the same bytes — singleness is what makes drift impossible (the SCV-02 mechanism, applied to a form instead of a render surface).
- **The dedicated page is a thin Jinja host** (`score-entry.html`) exactly like `overlay.html` — no score data baked in, the JS owns layout. This keeps the "one renderer" invariant: the modal and the page differ only by a cosmetic mount context, never by markup logic.

---

## Architectural Patterns

### Pattern 1: Shared interactive component via one JS module mounted into two hosts (the chosen approach — B)

**What:** A single `score-entry.js` exposes `mountScoreEntry(rootEl, {context})`. The dedicated page calls it on `document.body`; the console modal calls it on the `<dialog>`'s content element. Same code path, same DOM contract, same submit handler — only the mount root differs.

**Why this over the alternatives (the A/B/C comparison):**

| Option | Drift risk | Tablet UX | Where state lives | Verdict |
|--------|-----------|-----------|-------------------|---------|
| **(A) Jinja partial/macro** shared by page + modal | LOW for *markup*, but the live auto-calc + validation must be in JS → that JS would have to be written once and shared anyway, so you end up needing (B) for the behavior regardless. Partial alone can't give live feedback. | Good (server-rendered, no flash) | Server renders skeleton; client JS still owns live values | **Partial only.** Use a tiny Jinja include for the *static skeleton* if desired, but the behavior MUST be the one JS module. Not sufficient alone. |
| **(B) One shared JS component mounted into both** ← CHOSEN | NONE structurally — one module, one DOM contract, one submit path. Identical to the `overlay-render.js` precedent. | Best: native form focus/keyboard, no nested-document focus bugs, `<dialog>` is first-class on iPadOS 26. | Client (the live in-progress edit) + server (authoritative on submit). Clean. | **Recommended.** Matches the project's proven shared-renderer mechanism for an interactive surface. |
| **(C) iframe of the dedicated page inside the modal** (the v1.2 overlay trick) | NONE structurally (it IS the same page) | **Poor for a form:** keyboard/focus, `postMessage` plumbing to surface validation/submit results to the console, iOS iframe focus-zoom and viewport quirks, and the modal can't easily react to submit success. The v1.2 overlay is *passive* (no input) — that's why the iframe worked there. | Inside the iframe (isolated) → must `postMessage` out | **Rejected for the form.** Right tool for the overlay, wrong tool for an input surface. |

**Trade-offs of (B):** you must keep the dedicated page and the modal both *thin hosts* that do nothing but mount the module (no per-host form logic), or drift creeps back in. Enforce with a test that both hosts contain no `<input>`/calc logic of their own.

**Example:**
```js
// static/score-entry.js  (the ONE component; mounted by BOTH hosts)
function mountScoreEntry(root, opts) {
  const calc = window.SEGUGIO_SCORE_CALC;          // the advisory JS port
  function rerender() {
    const fields = collectFields(root);
    const errs = calc.validate(discipline, fields);  // live feedback ONLY
    const preview = calc.compute(discipline, fields); // show running total live
    paintErrors(root, errs); paintTotals(root, preview);
  }
  root.addEventListener("input", rerender);
  form.addEventListener("submit", e => {
    e.preventDefault();
    // POST RAW inputs — server recomputes authoritatively; 400 → show server errors
    post("/score", collectFields(root)).then(handleServerResult);
  });
}
// dedicated page: mountScoreEntry(document.querySelector("#score-entry-root"), {full:true})
// console modal: mountScoreEntry(dialog.querySelector(".dlg-body"), {modal:true})
```

### Pattern 2: Single pure calc/validation module, server-authoritative + advisory client mirror (the drift-free SOT)

**What:** `score_calc.py` is the ONE place auto-calc and per-discipline validation live. `/score` calls it on every write. `score-calc.js` is a byte-exact port used ONLY for live feedback. A drift-guard test feeds shared fixtures through both and asserts equal results — the exact mechanism v1.2 used for `_clean/_get` ↔ `cleanField/scvGet` (`gsd:scv01-mirror` block + drift test).

**Why a mirror and not "JS-only" or "server-only":**
- **Server-only (no client calc):** no live feedback (operator can't see the running total / validation until POST round-trip). Acceptable for safety but poor tablet UX during a live run.
- **Client-only (JS computes the authority, server trusts it):** BREAKS crash-isolation guarantees and the publish-and-render contract — a buggy/edited client could write a wrong `overlay.txt`. The server MUST recompute.
- **Mirror (chosen):** live feedback from the JS port + authoritative recompute on the server, with a test that makes them provably identical. Divergence is structurally caught in CI, not in production.

**Critical rule:** the client NEVER sends a computed total as authority. It POSTs raw inputs (catches, zone, faults, criteria). The server computes `totale`/result and writes it. So even if the JS port drifts, the on-air score is whatever the *Python* module produced — client and server-written files CANNOT diverge because only one of them (Python) writes.

**Trade-offs:** two implementations to keep in sync. Mitigated exactly as v1.2 did: keep both tiny and pure, mark them with `gsd:` sentinel comments, and gate with a drift test. If the team prefers ZERO duplication, a fallback is server-only calc with a `/score/preview` pure route (precedent: the retired SCV-01 `POST /score/preview`) the client calls on input for live totals — but that adds a round-trip per keystroke on contended WiFi, so the mirror is preferred.

**Example:**
```python
# src/segugio/ui/score_calc.py  (stdlib only — imports with heavy stack absent)
def validate(discipline, fields) -> list[dict]:
    """Return [{field, message}] — empty = valid. Per-discipline rules."""
    ...

def compute(discipline, fields) -> dict:
    """Return fields PLUS derived flat summary keys (e.g. totale) the renderer reads.
       PURE: no I/O, no judging beyond arithmetic the operator asked for."""
    ...
```
```python
# app.py POST /score becomes authoritative:
errs = score_calc.validate(discipline, fields)
if errs:
    return (jsonify({"errors": errs}), 400)        # client shows server messages
computed = score_calc.compute(discipline, fields)  # adds flat totale/result
doc = ScoreDoc(discipline=discipline, fields=computed)
write_score(_path(_SCORE_FILE), doc)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # reads flat keys
_bump_score_gen()
```

### Pattern 3: Additive structured data model that the legacy overlay renderer ignores

**What:** Keep `ScoreDoc{discipline, fields}` on the wire (no record schema change — `fields` is already `dict`). Enrich `fields` with structured values, but ALWAYS also include the FLAT summary keys the existing `render_overlay_text` and `overlay-render.js` already read. The rich structure is purely additive; old readers see the flat keys and never break.

**Concrete `fields` shape per discipline (proposal):**

| Discipline | Structured (NEW, additive) | Flat summary keys (PRESERVED — renderer reads these) |
|-----------|----------------------------|------------------------------------------------------|
| disc Toss & Fetch (multi-throw) | `throws: [{zone, caught}], round` | `prese` (count caught), `zona` (last/sum), `totale` (computed running total) |
| disc Freestyle (multi-criteria) | `criteria: {esecuzione, difficolta, presentazione}, judge` | `nome`, `timer`, `totale` (sum of criteria) |
| agility | `faults_breakdown: {refusals, knockdowns}` | `tempo`, `sct`, `faults` (total), `result` |

**Why additive:** `/overlay-json` already echoes `fields` verbatim and the overlay renderer reads only specific keys via `scvGet`. Adding keys to the dict is invisible to it. `overlay.txt` is produced by `render_overlay_text` from the flat keys, so the text fallback (SCR-01/RBT-06) keeps working with ZERO renderer change. The single on-air score stays "the current score" — multi-throw running total resolves to one `totale`.

**Trade-offs:** `fields` becomes a richer dict; the `read_score` guard (`fields` must be a dict) still holds, but nested lists/dicts now flow through. Confirm `_clean`/`cleanField` only ever touch leaf scalar values the renderer pulls (they do — `_get`/`scvGet` fetch named scalar keys). The structured sub-objects are carried but not rendered by the legacy path — fine.

---

## Data Flow

### Score-entry → on-air flow (the request flow)

```
Operator types in the form (dedicated page OR console modal)
    ↓  (same score-entry.js, live)
score-calc.js validate()/compute()  → live error chips + live running total  (ADVISORY)
    ↓  submit
POST /score  { discipline, throws[], criteria{}, faults_breakdown{}, ... raw inputs }
    ↓
score_calc.validate()  →  errors? → 400 {errors:[...]}  →  form shows server messages, NO write
    ↓ valid
score_calc.compute()   →  fields + flat summary keys (totale/result computed by PYTHON)
    ↓
write_score(score.json)              (structured + flat, atomic)
atomic_write_text(overlay.txt)       (render_overlay_text → flat line, fallback preserved)
_bump_score_gen()                    (gen++ → /overlay ?t= refresh; NOT a run edge)
    ↓
GET /overlay-json  → { discipline, fields:{...rich + flat...}, running, started_at, gen, server_now }
    ↓
overlay-render.js  reads the FLAT keys via scvGet → lower-third unchanged
OBS text source    reads overlay.txt → fallback unchanged
```

### State management

```
In-progress edit state  → lives in the CLIENT (the mounted score-entry.js instance)
Authoritative score     → lives in score.json (written ONLY by the server's compute())
Run/timer state         → unchanged: overlay_run.json (running/started_at/gen), console-owned
Validation rules        → live ONCE in score_calc.py (Python authority) mirrored to score-calc.js
```

### Key data flows

1. **Live feedback flow:** input → `score-calc.js` (advisory) → DOM chips/totals. Never touches the server, never writes files. Pure UX.
2. **Authoritative write flow:** submit → server `validate`+`compute` → atomic `score.json` + `overlay.txt` → `gen++`. The ONLY path that changes on-air state.
3. **Overlay read flow (unchanged):** OBS/console poll `/overlay-json` (rich-but-flat-compatible) and `overlay.txt` (flat). Both keep working because the flat keys are always present.

---

## Anti-Patterns

### Anti-Pattern 1: Letting the client compute the authoritative total

**What people do:** JS computes `totale` and POSTs it; the server trusts and writes it.
**Why it's wrong:** breaks the publish-and-render guarantee — a buggy/edited client (or a drifted JS port) puts a wrong score on air, and the server-written file now disagrees with the calc rule. This is precisely the divergence the question forbids.
**Do this instead:** POST raw inputs; the server recomputes with `score_calc.py`. The JS total is advisory only. Since only Python writes, client and file can't diverge.

### Anti-Pattern 2: Embedding the score-entry FORM as an iframe (copying the v1.2 overlay trick blindly)

**What people do:** reuse the SCV-02 iframe mechanism for the entry form because "it worked for the overlay."
**Why it's wrong:** the overlay is passive (no input); a form needs focus/keyboard/submit feedback to cross the iframe boundary via `postMessage`, and iOS iframe focus-zoom + viewport quirks degrade the tablet UX the project fought for in UXT-01.
**Do this instead:** share the one JS module (B). The iframe is the right pattern only for the passive `/overlay` render surface.

### Anti-Pattern 3: Changing `ScoreDoc`/`overlay.txt`/`/overlay-json` in a way the old renderer can't read

**What people do:** replace the flat keys (`prese`/`totale`/`tempo`...) with a nested structure and update the overlay renderer to match.
**Why it's wrong:** touches the v1.2-frozen overlay renderer and the `overlay.txt` fallback (SCR-01/RBT-06) — risk of regressing the shipped broadcast path, and the text fallback would break.
**Do this instead:** additive only. Keep the flat summary keys; add structured keys alongside. The legacy renderer and text fallback stay untouched.

### Anti-Pattern 4: Putting form/calc logic in the host pages instead of the shared module

**What people do:** the console modal keeps its own inline submit handler / field toggles; the dedicated page has its own.
**Why it's wrong:** two behavior copies → drift returns (the exact thing SCV-02 eliminated).
**Do this instead:** host pages are thin mounts only; ALL behavior in `score-entry.js`. Enforce with a test that the hosts contain no calc/submit logic.

### Anti-Pattern 5: Importing config models or anything heavy into the new calc module

**What people do:** `score_calc.py` imports `segugio.config` to read the discipline profile / valid ranges.
**Why it's wrong:** breaks crash-isolation (console must import ONLY Flask + `segugio.opcomm`); the import test with the heavy stack absent would fail.
**Do this instead:** `score_calc.py` is stdlib-only; per-discipline rules/ranges are constants in the module (or passed in as plain dicts, the `cam_ids`/`overlay_cfg` precedent). Extend `tests/test_crash_isolation.py` to assert it imports clean.

---

## Integration Points

### External boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Console ↔ OBS overlay | `GET /overlay` (browser-source) + `overlay.txt` (text source fallback) | Additive `fields` ride along; flat keys keep both working. NO change to OBS scene collection. |
| Console ↔ orchestrator/director | opcomm files only (`score.json` written; director NEVER reads it) | Director never imported/modified — HARD constraint preserved. `/score` only ever writes opcomm files. |

### Internal boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `score-entry.js` ↔ both hosts | `mountScoreEntry(root)` | One module, two mounts → drift-free (SCV-02 mechanism for a form). |
| `score-entry.js` ↔ `score-calc.js` | function calls (advisory) | Live feedback only; never authoritative. |
| `app.py /score` ↔ `score_calc.py` | function calls (authoritative) | validate→compute→write; the ONLY writer of computed totals. |
| `score_calc.py` ↔ `score-calc.js` | drift-guard test (shared fixtures) | Provable equality in CI — divergence caught before merge. |
| `app.py` ↔ `opcomm.channel` | `write_score` / `atomic_write_text` / `_bump_score_gen` | Unchanged atomic write + gen-bump discipline; `/score` is still NOT a run edge. |

---

## Suggested Build Order (dependency-respecting → roadmap phases)

| Phase | Deliverable | Depends on | Why this order |
|-------|-------------|-----------|----------------|
| **P15 — Pure calc + validation core** | `score_calc.py` (validate/compute, per-discipline incl. multi-throw total + freestyle criteria sum + agility faults) + unit tests + crash-isolation import test. | nothing | The authority must exist and be proven before any UI consumes it. Pure, testable, no UI risk. |
| **P16 — Shared component + dedicated page** | `score-entry.js` (the one component) + `score-calc.js` (byte-exact port) + drift-guard test + `score-entry.html` host + `GET /score-entry` route. Wire `/score` to be AUTHORITATIVE (validate→compute→write, 400 on invalid). | P15 (calc module + its rules) | Build the shared module against a real page first (simpler host than a modal); make the server authoritative here so totals/validation are real end-to-end. |
| **P17 — Console modal hosting the same module** | `console.html` `<dialog>` + "Apri punteggio" button mounting the SAME `score-entry.js`; retire/replace the inline `#form-score`. | P16 (the module exists and works standalone) | Reuse the proven module in the modal — proves the single-renderer drift-free claim across the two hosts. |
| **P18 — Rich data model + overlay continuity** | Structured `fields` (throws[], criteria{}, faults_breakdown{}) carried through `/score` write + `/overlay-json`; verify `overlay.txt` fallback + `/overlay` renderer + OBS path unchanged (regression tests). | P15–P17 (calc produces the flat keys; UI produces the structured inputs) | Do the data-model enrichment last, once calc + UI exist, so the additive flat-key guarantee can be verified against the live overlay/fallback in one focused phase. |

**Ordering rationale:** calc-first (pure, no UI dependency) → shared module proven on the simpler dedicated page → same module reused in the modal (the drift-free payoff) → data-model enrichment verified against the frozen overlay path last. Each phase is independently testable; the crash-isolation and overlay-fallback invariants are checked at the phases that touch them (P15 import test, P18 overlay regression).

**Research flags for the roadmapper:**
- **P15** is standard pure-logic work (precedent: `score_render.py`, `framing` scorer) — unlikely to need deeper research.
- **P16/P17** — the only real unknown is the iPadOS 26 `<dialog>` modal + focus/keyboard behavior with the on-screen keyboard; the project already validated tablet form inputs (UXT-01) so risk is low, but a quick on-device check of `<dialog>` + virtual keyboard is worth a UAT note.
- **P18** is mechanical/additive; the risk is purely "did we keep the flat keys" — covered by regression tests, not research.

---

## Confidence & Gaps

**Confidence: HIGH.** Every recommendation reuses a pattern already shipped and proven in this codebase: the shared-renderer-module mechanism (`overlay-render.js` → `/overlay` + preview iframe), the byte-exact mirror + drift-guard discipline (`_clean/_get` ↔ `cleanField/scvGet`), the authoritative-server / advisory-client split, the additive opcomm payload (`/overlay-json` echoes `fields` verbatim), the atomic-write + gen-bump in `/score`, and the stdlib-only crash-isolation rule.

**Gaps to resolve in phase planning (not blockers):**
- Exact per-discipline validation ranges (e.g. Toss & Fetch zone scoring table, freestyle criteria scales, agility fault penalties) — a rules question for the operator/domain, to be pinned in P15's REQ.
- `<dialog>` vs a CSS-overlay modal on iPadOS 26 with the soft keyboard — confirm in P17 (low risk; the project has on-device tablet validation history).
- Whether to keep the legacy inline `#form-score` as a transition fallback in P17 or remove it outright (recommend remove to avoid a second behavior copy = Anti-Pattern 4).

## Sources

- `src/segugio/ui/app.py`, `src/segugio/ui/score_render.py`, `src/segugio/ui/templates/{console,overlay}.html`, `src/segugio/ui/static/overlay-render.js` — the shipped console/overlay code and its sharing/mirror/atomic-write patterns — **HIGH** (in-repo, read 2026-06-21)
- `src/segugio/opcomm/{records,channel}.py` — `ScoreDoc{discipline, fields}` schema, atomic writers, never-raise readers, the additive `/overlay-json` echo contract — **HIGH** (in-repo)
- `src/segugio/config/discipline.py` — the per-discipline overlay-field sets + discriminated-union precedent informing the per-discipline `fields` shape — **HIGH** (in-repo)
- `.planning/PROJECT.md` — v1.3 goal/scope/constraints, crash-isolation rule, SCV-02 decision, publish-and-render history (Key Decisions table) — **HIGH** (in-repo)

---
*Architecture research for: v1.3 rich shared score-entry on the crash-isolated console*
*Researched: 2026-06-21*
