# Stack Research — v1.3 "Gestione Punteggi Avanzata"

**Domain:** Richer, *shared* score-entry (dedicated page + console modal) for the crash-isolated Flask operator console — validation, auto-calc totals, multi-throw/round, freestyle multi-criteria. Publish-and-render unchanged.
**Researched:** 2026-06-21
**Confidence:** HIGH

## Headline Recommendation

**Add ZERO new runtime dependencies.** This milestone is fully buildable on the stack already present and already proven crash-isolation-safe: stdlib + **pydantic 2.13.4** (already pinned/installed) on the Python side, and **plain vanilla ES2020** (no framework, no build step) on the client side — the exact pattern v1.1 (preview) and v1.2 (`overlay-render.js`) shipped.

The three sub-questions resolve as:

1. **A pure `segugio.scoring` module on the console import surface is ALLOWED** — but it must be a stdlib-only leaf (and may import `segugio.opcomm` for the `Discipline` enum), imported lazily/at-top exactly like `score_render`. It must be added to `PHASE1_SURFACE` in `tests/test_imports.py` and must survive the `CONSOLE_HEAVY_MODULES` block (torch/cv2/numpy/cyndilib/obsws absent). Do NOT put pydantic models on the *required* import path if you want the strongest isolation — but pydantic is acceptable (see §"pydantic on the console surface" for the exact rule and how to keep the smoke test green).
2. **One vanilla-JS renderer module** (`ui/static/score-entry.js`, `module.exports` + `window.SEGUGIO_SCORE` dual export) **mounted into BOTH** a standalone `/score-entry` page **and** a `<dialog>`/modal injected into `console.html`. One `mount(rootEl, cfg)` factory, one renderer, two mount points → drift is structurally impossible (the SCV-02 lesson, identical to how `/overlay?preview=1` is iframed into the console).
3. **No tiny libraries are worth it.** The native `<dialog>` element (modal), `URLSearchParams`/`FormData` (POST), and `Intl`/manual `mm:ss` parsing cover everything. Adding any micro-lib (validators, decimal libs, modal libs) costs more isolation/audit surface than it saves.

## Recommended Stack

### Core Technologies (all ALREADY present — nothing to install)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python stdlib** (`dataclasses`, `enum`, `decimal`, `re`, `os`) | py3.12 (`venv312`) / py3.14 (`venv`) | The new `segugio.scoring` validation + auto-calc leaf module | Keeps the console import surface heavy-free by construction. `decimal.Decimal` (not `float`) for points/penalty sums avoids `0.1+0.2` drift in displayed totals — load-bearing because the overlay shows the number verbatim. Mirrors the existing stdlib-only `score_render.py` and `opcomm/records.py` convention. |
| **pydantic** | **2.13.4** (current latest 2.x, released 2026-05-06 — Context7/PyPI verified) | Per-discipline validation models (ranges, required fields, `mm:ss`/decimal formats) with structured error messages | ALREADY pinned in `requirements.txt` and installed in both venvs; ALREADY a console-tolerated dep (it is `segugio.config`'s engine, and v2.13.4 is the exact installed build). `ValidationError.errors()` gives field-level messages the form can surface. Pure-Python import, no heavy transitive deps. |
| **Flask** (lazy, inside `create_app`) | as-installed (served via Waitress/dev server) | Serve the new `GET /score-entry` page + keep the existing `POST /score` sink | Already the console's only web dep, imported INSIDE `create_app` so `import segugio.ui` stays Flask-free. The new page route follows the `GET /overlay` precedent exactly. |
| **Vanilla ES2020** (no framework) | n/a (browser-native) | The ONE shared score-entry renderer/validator (`ui/static/score-entry.js`) | Zero build step, zero install, zero director compute — the proven `overlay-render.js` pattern. A framework (React/Vue/Svelte) would add a build toolchain and bundle for a 3-fieldset form: net negative. |
| **HTML `<dialog>`** | browser-native (Chromium/CEF, Safari 15.4+, all evergreen) | The console **modal** mount point | Native modal: focus-trap, `Esc`-to-close, backdrop, and `::backdrop` styling for free — no JS modal library. `showModal()`/`close()`. iPad Safari (the validated console client, iPadOS 26.x) supports it. |

### Supporting Libraries (browser-native — nothing to add)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `URLSearchParams` / `FormData` | browser-native | POST the current on-air score to `/score` (`application/x-www-form-urlencoded`) | Reuse the existing `post(url, data)` helper in `console.html`; the shared module returns a flat `{discipline, ...fields}` object the helper serializes. |
| `<output>` / `aria-live` regions | browser-native | Show auto-calc totals + per-field validation errors accessibly | The running total and error text update in place via `textContent` (the `overlay-render.js` flicker-free convention), announced to assistive tech. |
| `Intl.NumberFormat` (optional) | browser-native | Locale-correct total display (Italian decimal comma) if desired | Only if you want `12,5` instead of `12.5` in the UI; the POSTed/overlay value stays canonical. Optional polish. |

### Development Tools (all ALREADY present)

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest==9.0.3` | Python unit tests for `segugio.scoring` (validation + auto-calc) + the extended import-smoke test | Already the suite runner. Add focused tests beside `test_score_display_only.py`. |
| `node` (`v24.16.0`, dev-only, `shutil.which("node")`-gated) | Behavior tests for the shared JS validator/calculator — the EXACT harness `test_ui_overlay_render.py` uses (`subprocess` + `module.exports`) | NOT a runtime dep; tests skip gracefully if node is absent (`@_requires_node`). Lets you assert JS↔Python parity for any duplicated calc/format logic. |

## Installation

```bash
# Nothing to install. The entire milestone runs on the locked stack:
#   pydantic==2.13.4   (already in requirements.txt, installed in venv & venv312)
#   Python stdlib      (decimal / enum / dataclasses / re)
#   vanilla JS + native <dialog>   (browser-native, no npm, no build)
#
# Confirm the (already-true) baseline:
./venv/Scripts/python -c "import pydantic; print(pydantic.VERSION)"   # -> 2.13.4
node --version                                                         # -> v24.16.0 (dev test harness only)
```

## The three answers in detail

### (1) A pure `segugio.scoring` leaf IS allowed on the console import surface

**Verdict: YES — add `segugio.scoring` as a stdlib(+pydantic+opcomm)-only leaf.** The crash-isolation contract is *"the console imports ONLY Flask + `segugio.opcomm` — never ultralytics/torch/cyndilib/obsws/cv2/numpy"* (`app.py` docstring, `tests/test_imports.py::CONSOLE_HEAVY_MODULES`). The contract is about **excluding the heavy stack**, not about a literal two-module allowlist — `segugio.ui.score_render` already imports `segugio.opcomm.records` and is on the surface. A new pure module that imports only stdlib + `segugio.opcomm` (+ optionally pydantic) is the same shape and is fully compliant.

**Where it lives:** put validation + auto-calc in `src/segugio/scoring/` (or `src/segugio/ui/scoring.py` next to `score_render.py`). Keep `app.py`'s `POST /score` as the single channel sink — the route imports `scoring`, validates/calculates, and on success writes `score.json` + `overlay.txt` + bumps gen *exactly as today*. **Do NOT import the orchestrator/director, decision, tracking, ndi, obs, or runtime** — none are needed for scoring math.

**Hard rules for the new module (each is what keeps the smoke test green):**
- **stdlib only at module top**, plus `from ..opcomm.records import Discipline` (a proven console-safe leaf). `decimal`, `enum`, `re`, `dataclasses` are fine; `math` is fine.
- **NEVER** import `numpy`/`cv2`/`torch` — the dedicated console guard (`test_console_resolves_with_heavy_stack_and_numpy_absent`) forces `numpy`+`cv2` absent and builds `create_app`. A numpy import anywhere on the `POST /score` path would raise there.
- **Add it to `PHASE1_SURFACE`** in `tests/test_imports.py` (e.g. `"segugio.scoring"`) so `test_phase1_surface_imports_with_heavy_deps_absent` proves it imports with the heavy stack blocked.
- **Exercise it under the console guard:** extend `test_console_resolves_with_heavy_stack_and_numpy_absent` to `POST /score` under the heavy+numpy-absent block and assert `204` — this proves the validation/calc path imports nothing heavy (the same way that test already proves `GET /overlay-json` is heavy-free). This is the single most important new test for this milestone.

**pydantic on the console surface — the precise rule.** pydantic is already installed and is NOT in `HEAVY_MODULES`/`CONSOLE_HEAVY_MODULES`, so importing it does NOT break the existing smoke test. You may use pydantic v2 models for validation. Two safe options, in order of isolation strength:
  - **Preferred (strongest):** pure-stdlib validators (plain functions / `dataclass` + `decimal` + `re`) for the *hot* `POST /score` path, and reserve pydantic for nothing new — zero added import risk, mirrors `opcomm/records.py`'s hand-rolled `__post_init__` validation that the project already favors for boundary records.
  - **Acceptable (ergonomic):** pydantic v2 `BaseModel` per discipline with `field_validator`/`model_validator`, surfacing `ValidationError.errors()` to the form. This is fine because pydantic is already a tolerated dep — but **add `"pydantic"` to neither HEAVY list** and keep an explicit test that the scoring module imports with `numpy`/`cv2`/torch absent (pydantic-core is a compiled wheel but is self-contained and does NOT pull numpy/cv2). Verify once at test time, then it is locked.

> Recommendation: use **stdlib + `decimal`** for the auto-calc and the canonical validators, and use **pydantic v2 only if** you want declarative per-discipline schemas with auto-generated error messages. Either way the *server* re-validates (never trust the client) and the *display-only / no-adjudication* invariant (SCR-04) holds — auto-calc of a **total the operator's own inputs imply** is arithmetic on operator data, NOT judging/CV; it does not violate SCR-04, but keep that boundary explicit in the module docstring (the way `score_render.py` does).

### (2) Vanilla-JS modal + shared form component WITHOUT drift (the SCV-02 lesson)

**Pattern: ONE renderer module, TWO mount points, ZERO duplication** — the same structural guarantee that retired the byte-exact Python↔JS overlay mirror in v1.2.

- **`src/segugio/ui/static/score-entry.js`** — a single IIFE exporting a `mount(rootEl, cfg)` factory plus pure helpers, with the dual export footer already used by `overlay-render.js`:
  ```js
  if (typeof window !== "undefined") window.SEGUGIO_SCORE = api;          // page + modal
  if (typeof module !== "undefined" && module.exports) module.exports = api; // node tests
  ```
  `mount(rootEl, cfg)` builds (or wires) the discipline selector + per-discipline fieldsets, attaches the validation + auto-calc + running-total logic, and returns `{ getPayload, validate, reset, destroy }`. It writes values/errors/totals with `textContent` in place (never `innerHTML` for operator data — the T-11-03-01 sink rule), reusing the `cleanField` sanitize mirror style.
- **Standalone page** — new `GET /score-entry` route renders `templates/score-entry.html`, which contains the form skeleton and one `<script src="/static/score-entry.js">` + `SEGUGIO_SCORE.mount(document.getElementById("score-root"), CFG)`.
- **Console modal** — add a native `<dialog id="score-dialog">` to `console.html` whose body is the **same** form skeleton (extract it into a Jinja `{% include "score-form.html" %}` partial shared by both `score-entry.html` and `console.html` so even the *markup* has one source). On "Apri punteggio" → `dialog.showModal()` then `SEGUGIO_SCORE.mount(dialog.querySelector("#score-root"), CFG)`. Submit calls `getPayload()` → existing `post("/score", data)` → `dialog.close()`.

**Why this cannot drift:** the validation rules, the auto-calc, the field layout, and the POST shape all live in *one* JS module and *one* Jinja partial. The page and the modal differ only in their container (full page vs `<dialog>`) — exactly like `/overlay` vs `/overlay?preview=1` differ only by a cosmetic `body.preview` class. There is no second copy to fall out of sync.

**Native `<dialog>` specifics (no library):** `showModal()` gives a top-layer modal with built-in focus trap, `Esc` dismissal, and inert background; style the dimmer with `dialog::backdrop`. Honor the existing UXT-01 touch contract (≥44/48px targets, `touch-action: manipulation`, `font-size ≥1rem` to block iOS focus-zoom) — copy those rules from `console.html`. Guard the `mount` auto-call behind `typeof document !== "undefined"` so the node behavior test can import the module headless (the `overlay-render.js` `autoMount` precedent).

**Client/server validation split:** the JS validates for instant UX feedback; the server (`segugio.scoring` via `POST /score`) **re-validates authoritatively** and returns `400` with a message on failure (the existing `POST /score` already returns `400` for an unknown discipline — extend that to validation failures). If you duplicate any format/calc logic in JS, pin parity with a node-executed test against the Python module — the `test_ui_overlay_render.py` `cleanField`↔`_clean` parity check is the template.

### (3) Tiny libraries: stay dependency-free

| Candidate micro-lib | Verdict | Native replacement |
|---------------------|---------|--------------------|
| A JS form-validation lib (just-validate, validator.js, Zod) | **Skip** | `<input pattern=…>` + a few pure functions in `score-entry.js`; server re-validates in `segugio.scoring`. |
| A JS modal/dialog lib (micromodal, a11y-dialog) | **Skip** | Native `<dialog>.showModal()` — accessible by default, zero bytes. |
| A decimal/money JS lib (decimal.js, big.js) | **Skip** | Scores are small fixed-precision sums; integer-cents arithmetic or `toFixed` suffices client-side. The *authoritative* total is computed server-side with Python `decimal.Decimal`. |
| A Python validation/parse lib beyond pydantic | **Skip** | pydantic v2 (already present) or stdlib `decimal`/`re` cover ranges, required fields, and `mm:ss`. |
| A frontend framework / build step | **Skip** | Vanilla ES2020 — the whole console is already framework-free and a build step would break the "served-as-is static file" test harness. |

Every avoided dependency is import surface you do NOT have to prove heavy-free in the crash-isolation guard, and bytes you do NOT have to ship to a CEF/iPad client. Dependency-free is the lower-risk *and* lower-effort choice here.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Native `<dialog>` modal | a11y-dialog / micromodal | Only if a target browser lacked `<dialog>` — not the case (CEF + iPadOS 26.x both support it). |
| Stdlib `decimal` (+ optional pydantic) validators | pydantic v2 models everywhere | Use full pydantic models if you want declarative per-discipline schemas with auto error messages and don't mind the (already-tolerated) dep on the hot path. |
| One JS module + Jinja partial (page + modal) | Separate page-JS and modal-JS | Never — that is exactly the drift the SCV-02 lesson forbids. |
| New `GET /score-entry` standalone page | Reuse `/` console only | If you decide the modal alone is enough (no dedicated page); but the milestone goal explicitly wants both. |
| Server-authoritative `POST /score` validation | Client-only validation | Never — the LAN trust boundary means the server must re-validate (T-05-05-* boundary discipline). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Importing the orchestrator/director/decision/tracking/ndi/obs into the console for "scoring" | Breaks the HARD crash-isolation contract (D-03/RBT-04); a UI exception could reach the director | Keep scoring as a pure `segugio.scoring` leaf; publish via the existing opcomm files |
| `numpy`/`cv2`/`torch` anywhere on the `POST /score` path (e.g. for "math") | `test_console_resolves_with_heavy_stack_and_numpy_absent` forces them absent and would fail | stdlib `decimal`/`math` |
| `float` for points/penalty/criteria sums | `0.1+0.2 == 0.30000000000000004` shows a wrong total verbatim on the broadcast overlay | `decimal.Decimal` server-side; integer-cents or `toFixed` client-side |
| `innerHTML =` for operator-entered values/totals/errors | HTML-injection sink (T-11-03-01 — the v1.2 closed threat) | `textContent` in place (the `overlay-render.js` rule) |
| A WebSocket/SSE channel for "live" total updates | Breaks crash-isolation / starves `POST /command` (UXT-02) — rejected in v1.1 and v1.2 | The form computes totals locally; only the final on-air score is POSTed to the file channel |
| Adding `pydantic` to `HEAVY_MODULES` | It is a *required* light dep (config engine) — blocking it would break unrelated tests | Leave the HEAVY lists as-is; just keep the new module heavy-free |
| Duplicating the form markup in both page and modal | Drift between the two surfaces (the SCV-02 failure mode) | One Jinja partial `{% include "score-form.html" %}` + one `score-entry.js` |

## Stack Patterns by Variant

**If you want the strongest isolation guarantee:**
- Implement `segugio.scoring` with stdlib only (`decimal` + `re` + plain functions / frozen dataclasses with `__post_init__` validation, mirroring `opcomm/records.py`).
- Because it adds *zero* new import risk to the console surface and matches the existing boundary-record idiom.

**If you want declarative per-discipline schemas + free error messages:**
- Use pydantic v2 `BaseModel` per discipline with `field_validator`/`model_validator`, surfacing `ValidationError.errors()`.
- Because pydantic 2.13.4 is already installed/tolerated; just keep the module otherwise heavy-free and assert it under the console guard.

**For the shared UI (always):**
- One `score-entry.js` (`mount(root, cfg)` + dual export) + one Jinja `score-form.html` partial, mounted into both `GET /score-entry` and a `<dialog>` in `console.html`.
- Because one renderer + one markup source makes console↔page drift structurally impossible (SCV-02).

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `pydantic==2.13.4` | py3.12 (`venv312`) + py3.14 (`venv`) | Verified installed in BOTH venvs at 2.13.4; current latest 2.x (released 2026-05-06). pydantic-core is a self-contained compiled wheel — does NOT pull numpy/cv2/torch, so it stays console-safe. |
| `segugio.scoring` (new) | `segugio.opcomm` + stdlib (+ optional pydantic) | Must import nothing in `CONSOLE_HEAVY_MODULES`; add to `PHASE1_SURFACE` and exercise under the heavy+numpy-absent console guard. |
| `score-entry.js` (vanilla ES2020) | CEF (OBS browser source) + iPadOS 26.x Safari + Chromium | Same runtime envelope as `overlay-render.js`; native `<dialog>` supported across all three. No build step. |
| `node v24.16.0` | the JS behavior tests only | Dev-only, `shutil.which("node")`-gated skip — never a runtime dep (the `test_ui_overlay_render.py` precedent). |

## Sources

- `src/segugio/ui/app.py` (read) — crash-isolation contract, `POST /score` sink (write `score.json`+`overlay.txt`+gen bump), lazy Flask-in-factory, `GET /overlay` page precedent — **HIGH**
- `src/segugio/ui/score_render.py` + `src/segugio/ui/__init__.py` (read) — stdlib-only leaf convention, display-only/no-adjudication (SCR-04) invariant, opcomm-only import — **HIGH**
- `tests/test_imports.py` (read) — `PHASE1_SURFACE`, `HEAVY_MODULES`, `CONSOLE_HEAVY_MODULES` (numpy+cv2 forced absent), `test_console_resolves_with_heavy_stack_and_numpy_absent` (the gate the new module must pass) — **HIGH**
- `src/segugio/ui/static/overlay-render.js` (read) — dual `module.exports`/`window` export, `mount`/`autoMount` headless guard, `textContent`-only sink (T-11-03-01), one-renderer-no-drift (SCV-02) pattern — **HIGH**
- `src/segugio/ui/templates/console.html` (read) — existing 3-fieldset score form, discipline-toggle JS, `post(url,data)` URLSearchParams helper, UXT-01 touch contract — **HIGH**
- `src/segugio/opcomm/records.py` (read) — frozen `__post_init__` boundary-validation idiom, `Discipline` enum (console-safe leaf), stdlib-only records — **HIGH**
- `tests/test_ui_overlay_render.py` (read) — the node-subprocess JS behavior-test harness + JS↔Python parity pattern (`shutil.which("node")` gate) — **HIGH**
- `requirements.txt` + `venv`/`venv312` probe (`pydantic.VERSION` → 2.13.4) — installed/pinned dependency baseline — **HIGH**
- PyPI `pydantic` release metadata (Context7/PyPI, verified 2026-06-21): latest = **2.13.4**, released 2026-05-06 — confirms the pinned version is current; no bump needed — **HIGH**

---
*Stack research for: richer shared score-entry on the crash-isolated Segugio console (v1.3)*
*Researched: 2026-06-21*
