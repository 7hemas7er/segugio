# Phase 12: SCV-01 Unification - Research

**Researched:** 2026-06-15
**Domain:** Flask + vanilla-JS overlay subsystem (same-origin iframe reuse, cosmetic preview fork, dead-code retirement, build/test parity)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Published-only preview.** The console preview iframe shows EXACTLY what `/overlay-json` serves — the last *submitted* score (`/score`) + the live run state — byte-faithful to OBS by construction. The instant as-you-type text preview is RETIRED together with the JS mirror. One renderer, one source; drift impossible.
- **D-02: On-air label.** Relabel the preview area so it's unambiguous the iframe shows the **live published / on-air** overlay (e.g. "Anteprima overlay — come va in onda" and/or a small ON-AIR tag), not a draft of what's being typed. Copy is Italian — match `console.html` conventions.
- **D-03: Scaled 16:9 framed box over a neutral backdrop.** `preview=1` renders `/overlay` inside a fit-to-panel 16:9 box with a neutral mid-gray (or subtle checkerboard) backdrop, so the lower-third's bottom-left position, the title-safe band, transparency, and relative scale all read as they will over real video. The operator judges *placement*, not just text. (Rejected: plain plate on the dark panel. Rejected: a real grass still.)
- **D-04: Force the plate visible in preview.** `preview=1` keeps the lower-third shown even between runs (suppresses ONLY the run-edge enter/exit hide/show animation) so pre-run score entry has feedback. Content, layout, per-discipline cells, and sanitize stay byte-identical to OBS — only the visibility-gating animation is the scoped cosmetic fork. With `running === false` the offset-cancellation timer shows its static initial value (T&F 60s / freestyle `freestyleDurationS` / agility 0). Verify the freshness watchdog does NOT dim the forced-visible plate locally (`.is-stale` should not trigger).
- **D-05: Delete `POST /score/preview` and the JS mirror entirely.** The route's ONLY caller is the drift-guard being removed → no caller after this phase → remove it. (Rejected: downgrading `/score/preview` to a runtime `overlay.txt`-parity endpoint.)
- **D-06: `render_overlay_text` (Python) survives unchanged** as the `overlay.txt` fallback renderer (RBT-06). Phase 12 does NOT touch `score_render.py` logic.
- **D-07: Parity = build/test assertion, structural + value cross-check.** The test asserts BOTH (1) STRUCTURAL unification and (2) VALUE cross-check (overlay-render.js executed in node vs `render_overlay_text`/`overlay.txt` render the same sanitized field values for the same `/overlay-json` input). Builds on the existing `cleanField`↔`_clean` byte-parity test in `tests/test_ui_overlay_render.py`.

### Claude's Discretion
- Exact iframe dimensions, the 16:9 box CSS (aspect-ratio vs padding hack), the precise neutral backdrop (flat mid-gray vs checkerboard) and its value, and how `preview=1` scales the 1080p-designed lower-third into the small panel (CSS `transform: scale` on a fixed virtual viewport vs `vh/vw`-driven natural scaling).
- The exact ON-AIR label copy/styling (within D-02's intent).
- How `preview=1` is detected/threaded (query arg read in `get_overlay`, passed as a render flag to `overlay.html` / a body class the CSS keys on, or a JS bootstrap flag the renderer reads) — pick the path that keeps the renderer's content logic untouched and the fork purely presentational.
- Whether the value cross-check reuses/extends `tests/test_ui_overlay_render.py` or lands in a new parity test module.

### Deferred Ideas (OUT OF SCOPE)
- OBS scene-collection wiring, browser-source settings, `docs/obs-setup.md` → Phase 13 (SCN-01/02).
- End-to-end degrade / `/overlay-json` poll-storm vs `/command` starvation / HTML-injection acceptance under failure → Phase 14 (RBT-06, UXT-02 extension). Phase 12 adds one local iframe poller but does NOT harden the assembled live path.
- Agility under/over-SCT color bar → OVL-FUT-01 (deferred at Phase 11).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCV-02 | La preview punteggio della console riusa lo stesso renderer `/overlay` (iframe), ritirando il mirror JS byte-exact di Python + il drift-guard `POST /score/preview` — il drift console↔OBS diventa strutturalmente impossibile | The whole research: §`preview=1` threading (body-class approach), §iframe embed in console.html, §safe deletion inventory of the mirror + route, §parity test (structural + value cross-check) proving one renderer/one URL. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **GSD workflow enforcement.** All Edit/Write must flow through a GSD command (this phase is `/gsd-execute-phase`). No direct repo edits outside the workflow.
- **Stack is imposed** (Python orchestrator; this subsystem is Flask + vanilla JS). No new runtime dependency; the console is `Flask + segugio.opcomm` only.
- **No crash ever; degrade to SAFE.** RBT-04/RBT-07 invariants hold; this phase must not break crash-isolation.
- (The CLAUDE.md model/tracker/NDI tables are about the AI loop and do not bear on this UI phase.)

## Summary

Phase 12 is a **surgical reuse-and-delete** phase, not a build phase. The shared renderer already exists end-to-end (Phase 11: `GET /overlay` + `overlay.html` + `overlay-render.js`, verified live on the rig with a real iPhone NDI feed). Phase 12 (a) adds a **purely cosmetic** `preview=1` affordance to the existing `get_overlay()` route, (b) swaps the console's text-mirror `<div id="overlay-preview">` for an `<iframe src="/overlay?preview=1">`, and (c) **deletes** the hand-maintained Python↔JS byte-mirror (`gsd:scv01-mirror` block + its wiring) in `console.html` plus the `POST /score/preview` drift-guard route and its dedicated test. After this, the console preview and the OBS browser-source are literally the same page at the same URL reading the same `/overlay-json` — drift is structurally impossible, so the runtime drift-guard becomes dead weight.

The two highest-risk areas are NOT the renderer (which is frozen) but: (1) keeping the `preview=1` fork **provably cosmetic** — it must touch only the run-edge visibility animation and the framing chrome, never the sanitize/content/timer/per-discipline logic; and (2) the **two live fixes** the renderer carries (`quick-260615-sod` per-request poll nonce `++reqSeq`, and `quick-260615-tsi` response-recency freshness watchdog) must be preserved and verified to behave correctly under `preview=1` — specifically that the forced-visible plate does not get dimmed by `.is-stale` locally (it won't, because local polls are instant, but it must be proven).

**Primary recommendation:** Thread `preview=1` as a **server-side render flag → body CSS class** (`get_overlay()` reads `request.args.get("preview") == "1"`, passes `preview=True` into `render_template`, the template emits `<body class="preview">` or sets a `data-preview` attribute). Drive the 16:9 framing + neutral backdrop + force-visible-plate entirely in `overlay.html` CSS keyed on that class — **zero** change to `overlay-render.js` content logic. The one JS touch the force-visible plate requires (suppress the run-edge enter/exit gating between runs) is best done with a CSS rule that wins over the animation classes, so even D-04 needs no renderer logic change. The parity test is split: structural assertions in a new/extended page test, value cross-check extending the existing `tests/test_ui_overlay_render.py` node harness.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `preview=1` detection + flag injection | Frontend Server (Flask `get_overlay`) | — | Query-arg read + `render_template` arg; the only server touch. Stays Flask-free / crash-isolated. |
| 16:9 framed box + neutral backdrop chrome | Browser / Client (CSS in `overlay.html`) | — | Pure presentation; lives in the host page so the renderer is untouched. |
| Force-visible plate (suppress run-edge hide) | Browser / Client (CSS in `overlay.html`) | — | A CSS override keyed on the preview body class beats the animation classes — no renderer logic. |
| Score-to-DOM render, sanitize, timer, per-discipline cells | Browser / Client (`overlay-render.js`) | — | FROZEN. Reused as-is from Phase 11; preview must not alter it. |
| Data source (`/overlay-json`) | Frontend Server (existing route) | — | Pure consumer; no route change. |
| Console preview embed (iframe) + on-air label | Browser / Client (`console.html`) | — | Same-origin iframe + relabel; deletes the mirror it replaces. |
| `overlay.txt` text fallback render | API/Backend (`score_render.py`) | — | UNCHANGED (D-06/RBT-06); only referenced by the value cross-check. |
| Parity guarantee | Build/Test (pytest + node) | — | Drift moves from runtime drift-guard to a build-time assertion (D-07). |

## Standard Stack

No new packages. This phase is implemented entirely with the already-present stack.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | already installed (imported inside `create_app`) | Serve `/overlay`, read `request.args` | The existing console server; `request` is already imported in `create_app`. `[VERIFIED: src/segugio/ui/app.py line 118-126 imports request]` |
| Jinja2 | bundled with Flask | Render the `preview` flag into `overlay.html` body class | Already used for `overlay_cfg` injection. `[VERIFIED: app.py line 317 render_template]` |
| Vanilla JS (ES2020) | no build step | The frozen renderer; iframe is a plain `<iframe>` | No bundler, no package install (Phase-11 convention). `[VERIFIED: overlay-render.js header]` |
| node | dev-only (test harness) | Execute `overlay-render.js` in the value cross-check | Already the mechanism for `test_cleanfield_byte_parity_with_python_clean`. `[VERIFIED: tests/test_ui_overlay_render.py _run_node]` |
| pytest | dev | Structural + value parity assertions | The existing test runner. `[VERIFIED: tests/*.py]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Server-side flag → body class | JS bootstrap flag (`window.OVERLAY_CFG.preview`) read by the renderer | Couples preview into the renderer's JS; risks the "is it still cosmetic?" question and a content-logic change. The body-class path keeps the fork in CSS where it provably can't alter values. **Reject** the JS-bootstrap path for the *content* fork; a tiny bootstrap flag is acceptable ONLY if a CSS-only force-visible proves impossible (it doesn't — see Pattern 3). |
| Server-side flag → body class | URL-fragment / JS `location.search` parse in the renderer | Same coupling objection; also makes the test assert renderer behavior instead of served HTML. |
| `<iframe>` | `fetch` + inject HTML, or a second render path | Re-introduces a second renderer/data path — the exact drift this phase eliminates. HARD reject. |

**Installation:** None. (`npm view` / `pip index` not applicable — no new dependency.)

## Package Legitimacy Audit

Not applicable — this phase installs **no external packages**. All work uses the already-present Flask + vanilla-JS + node + pytest stack. (Per protocol, the audit table is required only when external packages are installed.)

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                  AFTER Phase 12 (one renderer, one URL, one data source)

  Operator types score ──POST /score──► score.json + overlay.txt + gen++ (overlay_run.json)
                                                  │
                          ┌───────────────────────┴───────────────────────┐
                          │                                                 │
              ┌───────────▼───────────┐                       ┌────────────▼────────────┐
              │ Console (browser)      │                       │ OBS CEF browser-source   │
              │ console.html           │                       │ GET /overlay             │
              │  <iframe               │                       │  overlay.html            │
              │   src="/overlay?       │                       │  overlay-render.js       │
              │        preview=1">     │                       │                          │
              └───────────┬───────────┘                       └────────────┬─────────────┘
                          │ (its own DOM,                                    │
                          │  its own renderer instance)                      │
                          ▼                                                  ▼
              GET /overlay?preview=1  ──renders same template──►  GET /overlay
                          │   (preview=1 → body.preview:                     │
                          │    16:9 frame + backdrop +                       │
                          │    force-visible plate; CSS only)                │
                          │                                                  │
                          └───────────────► poll GET /overlay-json ◄─────────┘
                                            (?t=<++reqSeq> nonce + no-store)
                                            same payload to BOTH consumers
                                                       │
                                                       ▼
                                            read_score + read_overlay_run
                                            (never-raise boundary)

  DELETED: console.html gsd:scv01-mirror + updateScorePreview/driftCheck/etc.
  DELETED: POST /score/preview route  +  tests/test_score_preview.py
  UNCHANGED: render_overlay_text (Python) → overlay.txt fallback (RBT-06)
```

The diagram's load-bearing point: the console preview and the OBS overlay are now **two instances of the identical page**, differing only by the `preview=1` body class (cosmetic). There is no console-side render code left.

### Recommended Project Structure (files touched)
```
src/segugio/ui/
├── app.py                       # MODIFY get_overlay() (~310); DELETE post_score_preview() (~216)
├── templates/
│   ├── overlay.html             # ADD preview-only CSS keyed on a body class; preview body class
│   └── console.html             # REPLACE preview div w/ iframe + on-air label; DELETE mirror+wiring+CSS
├── static/overlay-render.js     # UNCHANGED (frozen); preserve sod + tsi fixes
└── score_render.py              # UNCHANGED (D-06)

tests/
├── test_ui_overlay_page.py      # EXTEND: preview=1 structural assertions (body class, cosmetic-only)
├── test_ui_overlay_render.py    # EXTEND: value cross-check (node JS vs render_overlay_text)
├── test_score_preview.py        # DELETE (route is gone)
├── test_imports.py              # UNCHANGED but must STAY GREEN (RBT-07 gate)
└── (new) test_ui_scv_unification.py  # OPTIONAL: console.html-embeds-iframe + mirror-gone structural test
```

### Pattern 1: `preview=1` as a server-side render flag → body CSS class (RECOMMENDED)
**What:** `get_overlay()` reads the query arg and passes a boolean into the template; the template puts it on `<body>`; all preview chrome is CSS keyed on that class.
**When to use:** Always, here. Keeps the fork in the presentation layer, provably cosmetic, and assertable from served HTML.
**Minimal diff shape (NOT full implementation):**
```python
# app.py get_overlay() — the ONLY server change
@app.get("/overlay")
def get_overlay():
    preview = request.args.get("preview") == "1"   # cosmetic flag; no heavy import
    resp = make_response(render_template("overlay.html", preview=preview, **overlay_cfg))
    resp.headers["Cache-Control"] = "no-store"
    return resp
```
```html
<!-- overlay.html — body carries the flag; default (no arg) renders EXACTLY as today -->
<body class="{{ 'preview' if preview else '' }}">
  ... unchanged DOM ...
</body>
```
```css
/* overlay.html <style> — ALL preview chrome lives here, keyed on .preview.
   Without .preview the cascade is byte-identical to the current OBS page. */
body.preview { /* neutral backdrop fills the iframe viewport */
  background: #6b6f76 !important;   /* mid-gray, not transparent — preview only */
}
/* see Pattern 2 for the 16:9 framing and Pattern 3 for force-visible */
```
**Why this over a JS bootstrap flag:** the renderer never learns about preview, so there is *no path* by which preview could alter a value, an alias, the timer, or a per-discipline cell. The test can assert the difference purely from `GET /overlay` vs `GET /overlay?preview=1` served HTML.

### Pattern 2: Scaled 16:9 preview chrome (D-03)
**What:** Fit the 1080p-designed lower-third into a small sidebar panel inside a 16:9 framed box over a neutral backdrop so placement/title-safe-band/transparency/relative-scale read true.
**Key insight:** the lower-third is laid out in **`vw`/`vh` units relative to its OWN viewport** (`left: 4.5vw; bottom: 6vh; max-height: 18vh; font-size: 5.2vh`, etc. — `[VERIFIED: overlay.html lines 49-168]`). That is the decisive fact for the scaling choice:

| Approach | Placement reads true? | Scale reads true? | Verdict |
|----------|----------------------|-------------------|---------|
| **iframe with a 16:9 box + the page's own `vw/vh`** | **YES** — the iframe IS a viewport; `4.5vw`/`6vh` resolve against the iframe's box, so bottom-left placement + the 18vh title-safe band are proportionally correct at any panel size | **YES** — every dimension is `vh/vw`, so the whole lower-third scales with the iframe box | **RECOMMENDED.** Because the renderer already uses viewport-relative units, an `<iframe>` sized to a 16:9 box reproduces placement AND relative scale for free. No `transform: scale`, no virtual viewport needed. |
| `transform: scale()` on a fixed 1920×1080 virtual viewport | YES | YES | Works but redundant here and adds blurriness/sub-pixel artifacts; only needed if the layout used `px`. The renderer uses `vh/vw`, so this is unnecessary complexity. |
| `vh/vw`-natural scaling on the host (no iframe) | N/A | N/A | Not applicable — the console body is not a 16:9 viewport; this is exactly what the iframe provides. |
| padding-hack (`padding-top: 56.25%`) for the 16:9 box | YES (box only) | YES | A valid way to make the **container** 16:9 if `aspect-ratio` support is a concern; the iframe inside still scales naturally. |

**Recommended box (console.html CSS, around the iframe):**
```css
/* console.html — the preview panel wraps a 16:9 iframe over a neutral backdrop */
.overlay-preview-frame {
  width: 100%;
  aspect-ratio: 16 / 9;          /* the box; padding-hack fallback if older CEF/console browser */
  border: 1px solid #333;
  border-radius: 6px;
  overflow: hidden;
  background: #6b6f76;           /* neutral mid-gray = the .preview body background */
}
.overlay-preview-frame iframe {
  width: 100%; height: 100%; border: 0; display: block;
}
```
- **Tradeoff for judging PLACEMENT, not just legibility (the D-03 intent):** because the lower-third anchors to `bottom/left` in `vh/vw`, the iframe approach reproduces the *exact* fractional position the operator will see on a 1080p OBS canvas. A `px`-based plate would NOT — it would float to the wrong relative spot in a small panel. This is the strongest argument for the iframe + native-`vh/vw` choice and against any `px`/transform scheme.
- **Neutral backdrop value:** mid-gray `#6b6f76` (a value between the plate `#14161a` and white) lets the operator judge both the semi-transparent plate scrim (`color-mix(... 86%, transparent)`, `[VERIFIED: overlay.html line 78]`) and the white text legibility. A subtle CSS checkerboard (`linear-gradient`/`conic-gradient` tiles) is the discretionary alternative if flat gray makes transparency hard to read; flat gray is simpler and recommended first.

### Pattern 3: Force-visible plate (D-04) — CSS-only, no renderer change
**What:** Under `preview=1`, keep the lower-third shown even between runs (suppress ONLY the run-edge enter/exit hide/show animation) while content/layout/cells/sanitize stay byte-identical.
**The mechanism (CSS beats the animation classes):** the lower-third starts `opacity: 0` and is revealed by `.is-entering`/`.is-live` and hidden by `.is-exiting` (`[VERIFIED: overlay.html lines 57, 194-197]`). A preview-only rule that forces visibility and disables the enter/exit animations wins without touching JS:
```css
/* overlay.html — preview forces the plate visible, kills ONLY the run-edge anim.
   Does NOT touch .pulse-once (score/end-of-countdown pulse) or .is-stale. */
body.preview #lower-third {
  opacity: 1 !important;          /* always shown between runs (D-04) */
  animation: none !important;     /* suppress enter/exit slide — cosmetic only */
}
```
- `animation: none` here kills the `enter`/`exit`/`is-entering`/`is-exiting` keyframes but the renderer still *adds/removes* the classes (harmless — they no longer animate). The `pulse-once` primitive is a separate `animation:` on a different selector; if the planner wants pulses preserved in preview, scope the `animation: none` to the lower-third's enter/exit only (e.g. override `.is-entering`/`.is-exiting` specifically rather than the element). **Recommendation:** override `.is-entering`/`.is-exiting` to `animation: none` and force `opacity: 1`, leaving `.pulse-once` intact so a score-change pulse still gives feedback. This keeps the fork minimal and the pulse useful in preview.
- **Resting display with `running === false` (the planner-note question):** the timer text is driven by `paintTimer()` which, when not running, freezes at the static initial value (`currentElapsed()` returns `0` because `startedAt === null`, `[VERIFIED: overlay-render.js lines 301-326, 388-392]`). So at rest the preview shows:
  - **T&F (disc_tf):** `formatCountdown(60 - 0)` → **`1:00`** (DISC_TF_COUNTDOWN_S = 60).
  - **Freestyle (disc_freestyle):** `formatCountdown(freestyleDurationS - 0)` → e.g. **`2:00`** for the default 120s.
  - **Agility:** `formatAgility(0)` → **`0.00`**.
  - **Recommended resting display:** accept exactly these (the static start-of-run value) — they are the honest "what the overlay will show the instant a run starts," require zero new logic, and are already what the frozen renderer paints. Do NOT add a preview-only "--" or placeholder (that would be a content change and would diverge from OBS). NOTE: the CONTEXT planner-note says "T&F 60s" meaning the 60-second start value — `formatCountdown` renders that as the string `1:00`, which is correct; just be aware the *displayed string* is `1:00`, not `60`.
- **Freshness watchdog under preview (the must-verify):** `isStale()` returns `everResponded && (Date.now() - lastResponseAt) > STALE_MS` with `STALE_MS = 600ms` (`[VERIFIED: overlay-render.js lines 229-230, 295-297]`). In the local console the iframe polls same-origin `/overlay-json` and gets instant responses, so `lastResponseAt` advances every ~200ms → `isStale()` is `false` → `.is-stale` is never added → the forced-visible plate is **not** dimmed. This MUST be proven in the parity/behavior test (see Validation Architecture, scenario "preview never goes stale locally"). The `tsi` regression test `test_live_idle_run_not_stale_but_console_down_is_stale` already proves the watchdog behavior in isolation; the preview test should assert the watchdog code is byte-unchanged (the fork added no JS) and that a CSS-forced-visible plate is independent of `.is-stale`.

### Pattern 4: Same-origin iframe embed + on-air label (console.html)
**What:** Replace `#overlay-preview` text div with `<iframe src="/overlay?preview=1">` and relabel (D-02).
**Minimal shape:**
```html
<!-- console.html — replaces the deleted preview div + drift-warning -->
<label>Anteprima overlay — come va in onda <span class="on-air-tag">● ON AIR</span></label>
<div class="overlay-preview-frame">
  <iframe src="/overlay?preview=1" title="Anteprima overlay live" loading="lazy"></iframe>
</div>
```
- Same-origin → no CSP/X-Frame-Options issue (the console serves both; no `frame-ancestors`/`X-Frame-Options` header is set today, `[VERIFIED: app.py — no such header in any route]`). The iframe loads `/overlay?preview=1` from the same host.
- The iframe gets its OWN `overlay-render.js` instance polling `/overlay-json` — one extra local poller per open console. **Accepted in this phase** (the poll-storm/`/command` starvation concern is explicitly Phase 14 scope, `[CITED: 12-CONTEXT.md line 101]`).
- `loading="lazy"` is optional/discretionary; the panel is in-viewport on the console so eager load is fine too.

### Anti-Patterns to Avoid
- **Reading `preview` inside `overlay-render.js`.** Couples the cosmetic fork into the renderer and breaks the "provably cosmetic" guarantee. Keep it in CSS/body-class.
- **Adding a preview-only timer/placeholder string.** Any content the OBS page wouldn't show re-opens drift. The resting `1:00`/`2:00`/`0.00` is what OBS shows too.
- **A second fetch/render path for the preview.** Defeats the entire phase. The iframe IS the OBS page.
- **A module-top import in app.py to support preview.** Breaks RBT-07. `request` is already imported in-factory; no new import is needed.
- **Posting to the live `:8080` console to verify the fork** (auto-memory `overlay-bugs-sandbox-repro`). Use an alt-port sandbox + node fake-DOM.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Console↔OBS score parity | A runtime drift-guard endpoint (the thing being deleted) | One shared renderer at one URL (iframe) + a build-time value cross-check | Structural unification makes drift impossible; a runtime guard only *detects* drift after the fact and adds surface (D-05/D-07). |
| Scaling the 1080p lower-third into the panel | A `transform: scale()` on a fixed virtual viewport | An `<iframe>` sized to a 16:9 box (the layout is already `vh/vw`) | The renderer's viewport-relative units scale for free inside an iframe; no transform math, no blur. |
| Sanitize parity JS↔Python | A second hand-ported `cleanField`/`mirrorOverlayText` in console.html | The shared `overlay-render.js` `cleanField`/`scvGet` (already byte-parity tested) | The console copy IS the duplication being deleted; the renderer's copy stays the single source. |
| Value cross-check harness | A new node-execution mechanism | The existing `_run_node` + `module.exports` harness in `test_ui_overlay_render.py` | Already proven, UTF-8-safe on Windows, and the natural home (D-07). |

**Key insight:** the entire phase is the removal of a hand-rolled solution (the byte-mirror + drift-guard) in favor of the structural one (the shared renderer). The research's job is to make the *removal* safe and the *equivalence* provable.

## Runtime State Inventory

> This is a code-edit / delete phase (refactor of the preview path). No stored data, OS state, or migration. The "inventory" here is the **symbol/route deletion** safety audit, which is the rename-phase analogue.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None** — Phase 12 touches no datastore. `score.json`/`overlay.txt`/`overlay_run.json`/`runstate.json` write paths are UNCHANGED (`/score`, `/run` untouched). Verified: only `post_score_preview` (no file writes) and `get_overlay` are touched. | none |
| Live service config | **None** — no external service config. The iframe is same-origin; no OBS/scene config in this phase (that's Phase 13). | none |
| OS-registered state | **None** — no scheduled tasks/services reference the deleted symbols. | none |
| Secrets/env vars | **None** — the `SEGUGIO_OVERLAY_*` env vars feed `overlay_cfg` (branding), unrelated to `preview`/the mirror. No env var names change. | none |
| Build artifacts | **None** — no compiled assets; `overlay-render.js` is served raw. No `.egg-info`/bundle to rebuild. | none |
| **Code symbols to delete (the real inventory)** | See "Safe Deletion Inventory" below — JS functions, DOM ids, CSS rules, listeners, a route, a test file. | grep-prove zero references remain after removal (see Common Pitfall 1). |

### Safe Deletion Inventory (the exact set — research target #5 and #6)

**In `console.html` — DELETE:**
| Symbol / element | Location | Notes |
|------------------|----------|-------|
| HTML comment "SCV-01 live score-overlay preview… drift-guarded against POST /score/preview" | lines ~270-271 | descriptive comment for the mirror — goes with it |
| `<div id="overlay-preview" aria-live="polite">` | line ~273 | replaced by the iframe |
| `<div id="drift-warning">` | line ~274 | drift UI — gone |
| `<label for="overlay-preview">Anteprima overlay</label> | line ~272 | replaced by the D-02 on-air label |
| CSS `#overlay-preview { ... }` | lines ~154-157 | the text-mirror styling |
| CSS `#drift-warning { ... }` + `#drift-warning.show { ... }` | lines ~158-160 | drift styling |
| CSS comment "SCV-01 score-overlay preview… + drift warning." | line ~153 | goes with the rules |
| `gsd:scv01-mirror` block: `SCV_MAX_FIELD_LEN`, `SCV_NONPRINT`, `cleanField`, `scvGet`, `mirrorOverlayText` | lines ~341-391 (between `gsd:scv01-mirror:start`/`:end`) | the byte-mirror — delete the whole marked block |
| `scvCurrentFields()` | lines ~394-403 | collected fields for the mirror |
| `updateScorePreview()` | lines ~406-409 | wrote `#overlay-preview` |
| `scvPreviewTimer` + `scheduleScorePreview()` | lines ~412-416 | debounce |
| `setDrift()` | lines ~421-424 | drift UI toggle |
| `driftCheck()` | lines ~425-435 | the ONLY caller of `POST /score/preview` |
| Listener: `inp.addEventListener("input", scheduleScorePreview)` | line ~439 | per-field input preview |
| Listener: `inp.addEventListener("blur", driftCheck)` | line ~440 | per-field blur drift |
| `sel.addEventListener("change", updateScorePreview)` | line ~443 | discipline-change preview |
| `updateScorePreview();` seed call | line ~445 | load-time seed |
| `document.getElementById("form-score").addEventListener("submit", driftCheck);` | line ~446 | submit drift |
| The whole `.campi input` forEach block (lines ~438-441) | lines ~438-441 | its ONLY body is the two preview listeners; remove the whole forEach |

**KEEP (do not touch) in console.html:** the discipline selector + `showFields()`, the `post()` helper, the `form-score` `submit` → `post("/score", ...)` listener (lines ~325-335), the run buttons (~338-339), the `gsd:why-mirror` block (unrelated, line ~452+), `CAMS`/`CAM_LABEL`. NOTE: `sel.addEventListener("change", showFields)` (line 315) STAYS; only the *second* `sel.addEventListener("change", updateScorePreview)` (line 443) goes.

**In `app.py` — DELETE:**
| Symbol | Location | Notes |
|--------|----------|-------|
| `@app.post("/score/preview")` `def post_score_preview()` | lines ~216-238 | the entire route + decorator + docstring. Its ONLY caller is `driftCheck()` (deleted above). |

**In `tests/` — DELETE:**
| File | Notes |
|------|-------|
| `tests/test_score_preview.py` | the entire file exercises `POST /score/preview`; with the route gone it would fail. DELETE it. Its byte-exact reference strings are preserved by the value cross-check (D-07) against `render_overlay_text`. |

**`POST /score/preview` caller confirmation (research target #6):** grep across the repo shows the route string `/score/preview` appears in exactly three places: the route definition (`app.py`), the client caller `driftCheck` (`console.html`, being deleted), and the test (`test_score_preview.py`, being deleted). `[VERIFIED: Grep "/score/preview" — app.py:216, console.html:430, test_score_preview.py:34/50/59/89/100/116]`. After this phase there is **no caller**. SAFE to delete.

## Common Pitfalls

### Pitfall 1: A leftover reference to a deleted symbol (silent breakage)
**What goes wrong:** Deleting `mirrorOverlayText`/`updateScorePreview`/etc. but leaving one listener or seed call referencing it → a JS `ReferenceError` at console load that breaks ALL subsequent inline-script wiring (run buttons, score submit).
**Why it happens:** the mirror's wiring is spread across ~10 sites (listeners, seed call, submit hook).
**How to avoid:** after deletion, grep the served `console.html` for every deleted identifier and assert zero hits; load the console in the sandbox and check the JS console for errors. The structural test should assert the symbols are GONE *and* that the surviving wiring (score submit, run) is intact.
**Warning signs:** run buttons or score submit stop working after the edit (a thrown ReferenceError aborts the rest of the `<script>`).

### Pitfall 2: CEF cache / poll nonce under the iframe (research target #4)
**What goes wrong:** assuming the iframe needs a `?t=` nonce on its *src* (`/overlay?preview=1`).
**Why it doesn't:** the host page (`/overlay`) is served with `Cache-Control: no-store` (`[VERIFIED: app.py line 320]`) and is a thin shell; the load-bearing cache-bust is on the **`/overlay-json` poll**, where the renderer appends `?t=<++reqSeq>` per request (`quick-260615-sod`, `[VERIFIED: overlay-render.js line 411]`). The iframe's renderer instance runs the identical poll code, so it inherits the per-request nonce + `no-store` automatically. No same-origin iframe caching surprise: each iframe load runs `autoMount()` → `createRenderer()` → fresh `reqSeq` counter starting at 0, and every poll URL is distinct.
**How to avoid:** do NOT add a nonce to the iframe src; rely on the host-page `no-store` + the renderer's existing poll nonce. The structural test should assert `/overlay` (and `/overlay?preview=1`) responses both carry `Cache-Control: no-store`.
**Warning signs:** a stale preview that only updates on hard reload — would indicate the poll nonce regressed (it must be preserved verbatim).

### Pitfall 3: The `preview=1` fork accidentally becomes non-cosmetic
**What goes wrong:** threading preview into the renderer (JS bootstrap flag) and then "while I'm here" branching the render/timer logic on it.
**Why it happens:** the JS path is tempting because the renderer is where the timer/visibility live.
**How to avoid:** use the body-class/CSS path (Pattern 1); the renderer file stays byte-identical. The parity test asserts `overlay-render.js` content equivalence (the value cross-check runs the SAME file the OBS page loads) and the structural test asserts `/overlay` vs `/overlay?preview=1` differ ONLY by the body class / preview CSS, not the DOM contract or the script src.
**Warning signs:** a diff to `overlay-render.js` in this phase (there should be NONE, except possibly preserving — not changing — the sod/tsi fixes).

### Pitfall 4: Breaking RBT-07 crash-isolation (research target #7)
**What goes wrong:** adding a module-top import to support preview (e.g. importing config to read a preview default).
**Why it happens:** unlikely here, but any new top-level import in `app.py` or a new heavy import in the route would trip the gate.
**How to avoid:** `preview` is a pure `request.args` read + a `render_template` boolean — no import at all. `request` is already imported inside `create_app` (`[VERIFIED: app.py lines 118-126]`). The `test_console_resolves_with_heavy_stack_and_numpy_absent` test (`tests/test_imports.py`) forces `torch/cv2/ultralytics/numpy/cyndilib/obsws_python` absent and builds `create_app` + GETs `/overlay`; it must stay green. The route already registers and resolves heavy-free; adding a query-arg read changes nothing about imports.
**Warning signs:** `test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` red.

### Pitfall 5: The on-air label confusing the operator the OTHER way (D-02 intent)
**What goes wrong:** dropping the instant text preview without a clear label → operator types, nothing shows in the preview until they submit, thinks it's broken.
**Why it happens:** the mental model shifts from "preview what I'm typing" to "preview what's on air."
**How to avoid:** the D-02 label ("come va in onda" / ON-AIR tag) is required, not optional. It's the UX mitigation for the intentional behavior change.
**Warning signs:** (field/UAT) operator confusion — covered by the on-air label.

## Code Examples

All examples are the minimal diff shapes above (Patterns 1-4). No external-source code is needed — every pattern is grounded in the verified existing files. Key verified anchors:
- `get_overlay()` route + `request` already imported: `[VERIFIED: src/segugio/ui/app.py lines 118-126, 310-321]`
- Lower-third `vh/vw` layout + `opacity:0` start + animation classes: `[VERIFIED: src/segugio/ui/templates/overlay.html lines 49-201]`
- Resting timer values (`currentElapsed()` returns 0 when not running; `DISC_TF_COUNTDOWN_S=60`; `formatAgility(0)`→`0.00`): `[VERIFIED: src/segugio/ui/static/overlay-render.js lines 236, 250-255, 301-326]`
- Per-request poll nonce + response-recency watchdog: `[VERIFIED: overlay-render.js lines 229-230, 295-297, 411-413; git log f635f5c (tsi), 63713d8 (sod)]`
- node value-cross-check harness: `[VERIFIED: tests/test_ui_overlay_render.py lines 109-132, 383-399]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-maintained Python↔JS byte-mirror + runtime drift-guard (`POST /score/preview`) | One shared renderer at one URL (iframe reuse) + build-time parity test | This phase (Phase 12 / SCV-02) | Drift becomes structurally impossible; ~110 lines of mirror JS + a route + a test file removed; parity moves to a test guarantee. |
| As-you-type instant text preview | Published-only preview (last submitted score + live run state) | This phase (D-01) | Honest unification; the operator sees exactly OBS. Mitigated by the D-02 on-air label. |

**Deprecated/outdated by this phase:**
- `console.html` `gsd:scv01-mirror` block + `mirrorOverlayText`/`updateScorePreview`/`driftCheck`/`#drift-warning`/`#overlay-preview` — retired.
- `POST /score/preview` + `tests/test_score_preview.py` — retired.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No `X-Frame-Options`/CSP `frame-ancestors` header is set on any console route, so a same-origin iframe loads without framing restriction. | Pattern 4 | LOW — verified by Grep (no such header in app.py); if a reverse proxy adds one in deploy it's same-origin anyway. Worth a sandbox smoke check that the iframe actually renders. |
| A2 | `aspect-ratio: 16 / 9` is supported in the console's target browser (tablet WebKit/Chromium) and OBS isn't the console host. | Pattern 2 | LOW — `aspect-ratio` is broadly supported in current WebKit/Chromium; the padding-hack fallback is listed if a very old tablet browser is in play. The console is a tablet UI, not CEF, so CEF quirks don't apply to the *box*. |
| A3 | The "resting display" `1:00`/`2:00`/`0.00` is acceptable to the operator as the preview-at-rest value. | Pattern 3 | LOW/MEDIUM — it's what OBS shows at run start, so it's correct-by-construction, but the operator may expect a blanked timer. The CONTEXT D-04 planner note explicitly asks the planner to "decide the exact resting display"; this research recommends accepting the static value (no content fork). Confirm in planning/UAT. |
| A4 | One extra local `/overlay-json` poller (the iframe) is acceptable load in this phase. | Pattern 4 | LOW — explicitly stated in 12-CONTEXT line 101 (poll-storm is Phase 14 scope). |

**Note:** A3 is the only assumption that touches a user-visible behavioral choice and should be surfaced to the planner/discuss as the one D-04 detail still open.

## Open Questions

1. **Pulse-in-preview: keep or suppress?**
   - What we know: the force-visible CSS must kill the enter/exit run-edge animation; `.pulse-once` is a separate primitive.
   - What's unclear: whether a score-change pulse is desirable feedback in the preview panel.
   - Recommendation: KEEP `.pulse-once` (scope the `animation: none` override to `.is-entering`/`.is-exiting` only). It gives harmless, on-air-faithful feedback when a newly submitted score lands. Low risk; planner can decide.

2. **Flat mid-gray vs checkerboard backdrop (D-03 discretion).**
   - What we know: both read transparency; flat gray is simpler.
   - Recommendation: ship flat `#6b6f76` first; add a CSS checkerboard only if UAT says transparency is hard to judge.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| node | the value cross-check + sandbox node fake-DOM test | ✓ | (present — used by existing 11-03 tests; `_requires_node` skips gracefully if absent) | tests `skipif(node is None)` (existing pattern) |
| pytest | structural + value parity tests | ✓ | (the repo test runner) | — |
| Flask | the route (in-factory import) | ✓ | already installed | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** node — the node-executed value cross-check skips if node is unavailable (matching the existing `@_requires_node` decorator); structural assertions still run.

## Validation Architecture

> Nyquist validation is enabled (config has no `workflow.nyquist_validation: false`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + node (subprocess-executed JS behavior) |
| Config file | repo pytest defaults (no special config needed) |
| Quick run command | `python -m pytest tests/test_ui_overlay_page.py tests/test_ui_overlay_render.py tests/test_imports.py -x -q` |
| Full suite command | `python -m pytest -q` |

### D-07 Parity Test Strategy (the heart of this phase)

**(1) STRUCTURAL unification assertions** (extend `tests/test_ui_overlay_page.py`, or a new `tests/test_ui_scv_unification.py`):
- `GET /overlay?preview=1` returns 200 with `Cache-Control: no-store` (same as `/overlay`).
- The served HTML for `/overlay?preview=1` carries the preview body class (`class="preview"` / `body.preview`) AND `/overlay` (no arg) does NOT — proving the flag threads.
- The two served pages differ ONLY by the preview class/CSS: the DOM contract ids (`#lower-third`, `#identity`, `#timer`, `#cells`) and the `<script src="/static/overlay-render.js">` reference are present and identical in both. (Assert the script src and the four ids appear in both responses.)
- `console.html` (served at `GET /`) embeds `<iframe src="/overlay?preview=1">` and the on-air label copy is present.
- The mirror symbols are GONE from served `console.html`: assert `mirrorOverlayText`, `updateScorePreview`, `scheduleScorePreview`, `scvCurrentFields`, `driftCheck`, `setDrift`, `gsd:scv01-mirror`, `id="drift-warning"`, `id="overlay-preview"`, and the string `/score/preview` do NOT appear.
- `POST /score/preview` is gone: `client.post("/score/preview", ...)` returns 404/405 (route unregistered).
- RBT-07: `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` stays green (already covers `/overlay` under the heavy-absent block; optionally add a `GET /overlay?preview=1` under the same block to prove the cosmetic flag adds no heavy import).

**(2) VALUE cross-check** (extend `tests/test_ui_overlay_render.py`'s node harness — D-07 says build on the `cleanField`↔`_clean` precedent):
- For a representative set of `/overlay-json`-shaped payloads (one per discipline, incl. the `sct`/`SCT` alias and control-char/over-64 inputs), run the SERVED `overlay-render.js` in node (via the existing `_run_node` + `module.exports`) and compute the sanitized field VALUES the renderer would put in each cell (`scvGet`/`cleanField` per `DISCIPLINE_CELLS`). Compare against the Python `render_overlay_text` / `_get` / `_clean` output for the SAME payload.
- The assertion is on the **sanitized field values**, not the exact f-string layout (the JS renders to DOM cells, Python to a text line — they share the *values*, not the punctuation). Concretely: assert `js.scvGet(fields, "prese") == _clean(fields["prese"])` etc. for each discipline's fields, and the `sct`/`SCT` first-present alias resolves identically on both sides. This proves the broadcast overlay and the `overlay.txt` fallback can never silently diverge on the numbers.
- The deleted `test_score_preview.py` byte-exact reference strings are subsumed: the value cross-check pins the same sanitized values; if the planner wants to also preserve the exact Italian line layout as a guard, assert `render_overlay_text(ScoreDoc(...))` directly in a Python-only test (no route needed) — but that's optional, since `score_render.py` is unchanged (D-06).

**(3) LIVE-BEHAVIOR cosmetic fork validation (sandbox-first — auto-memory `overlay-bugs-sandbox-repro`):**
- Reproduce the `preview=1` force-visible/timer behavior in an **alt-port sandbox** (`create_app(tmp)` on a non-8080 port or via the Flask test client) + a **node fake-DOM** harness (the existing `test_live_idle_run_not_stale_but_console_down_is_stale` fake-DOM is the template).
- Prove: under `preview=1`, the lower-third is visible at rest (`opacity` forced by CSS — assert via served HTML that `body.preview #lower-third { opacity: 1` rule exists), AND the response-recency watchdog does NOT add `.is-stale` while the local poll answers (re-use the `(a) LIVE IDLE RUN → liveHasStaleClass === false` assertion; the preview fork added no JS, so this behavior is unchanged — assert the watchdog code in the served JS is byte-identical / the `tsi` markers are present).
- **NEVER POST to the live `:8080` console.** All verification uses the test client / sandbox.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCV-02 | console embeds `<iframe src="/overlay?preview=1">`; mirror symbols + `/score/preview` gone | structural | `pytest tests/test_ui_scv_unification.py -x` (new) or extend `test_ui_overlay_page.py` | ❌ Wave 0 |
| SCV-02 | `/overlay` vs `/overlay?preview=1` differ only by preview class (same DOM/script) | structural | `pytest tests/test_ui_overlay_page.py -x` | ✅ extend |
| SCV-02 | renderer (node) vs `render_overlay_text` sanitized values match per discipline | value cross-check | `pytest tests/test_ui_overlay_render.py::test_value_crosscheck -x` (new) | ✅ extend |
| SCV-02 | force-visible plate not dimmed by stale watchdog under instant local poll | behavior (node fake-DOM) | `pytest tests/test_ui_overlay_render.py -x` | ✅ extend |
| RBT-07 | console + `/overlay?preview=1` resolve with heavy stack absent | import gate | `pytest tests/test_imports.py -x` | ✅ keep green |
| D-05 | `POST /score/preview` returns 404/405 (route removed) | structural | (in the SCV-02 structural test) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_ui_overlay_page.py tests/test_ui_overlay_render.py tests/test_imports.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite — catches any console-wiring regression, e.g. score submit/run still work)
- **Phase gate:** full suite green before `/gsd-verify-work`; plus a sandbox smoke that the iframe actually renders the framed preview (manual/UAT).

### Wave 0 Gaps
- [ ] `tests/test_ui_scv_unification.py` (or additions to `test_ui_overlay_page.py`) — structural unification assertions (iframe embed, mirror-gone, `/score/preview` 404, preview body class).
- [ ] `tests/test_ui_overlay_render.py` — new `test_value_crosscheck` (node JS sanitized values vs `render_overlay_text`).
- [ ] DELETE `tests/test_score_preview.py` (route gone).
- [ ] No framework install needed (pytest + node already present).

## Security Domain

> `security_enforcement` is enabled (RBT-07 is a re-asserted gate). This phase is LAN-trust-boundary, single-operator; the threat surface is narrow.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in v1 (accepted, documented — LAN trust boundary, T-05-05-04). Unchanged. |
| V3 Session Management | no | Stateless console; unchanged. |
| V4 Access Control | no | LAN-only; the iframe is same-origin. Unchanged. |
| V5 Input Validation | yes | The discipline whitelist + field sanitize/length-bound live in the UNCHANGED `/score` path and `score_render._clean` / renderer `cleanField`. Deleting `/score/preview` removes one input surface (a net reduction). No new input is introduced (`preview=1` is a closed boolean comparison `== "1"`). |
| V6 Cryptography | no | None involved. |

### Known Threat Patterns for Flask + vanilla-JS overlay
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML injection via operator-typed score values | Tampering | `textContent` (never `innerHTML`) in the renderer — UNCHANGED and re-asserted by the existing `test_no_innerhtml_sink`. The iframe consumes the same sanitized renderer. `[VERIFIED: overlay-render.js; test_ui_overlay_render.py test_no_innerhtml_sink]` |
| Overlay-injection via control chars / overflow | Tampering | `_clean` / `cleanField` (strip control chars, cap 64) — UNCHANGED (D-06). The value cross-check re-proves parity. |
| `preview` query-arg as an attack vector | Tampering | Closed boolean comparison (`request.args.get("preview") == "1"`); any other value → no preview. Not used as a path, never reflected unescaped (it sets a fixed CSS class via Jinja boolean, autoescaped). |
| iframe clickjacking / framing | Spoofing/Tampering | Same-origin, LAN-only, single-operator; out of v1 threat model. (If a deploy adds `X-Frame-Options` it must allow same-origin — A1.) |
| Reduced attack surface | (defensive) | Deleting `POST /score/preview` removes one POST endpoint entirely — a net security improvement. |

## Sources

### Primary (HIGH confidence)
- `src/segugio/ui/app.py` (read in full) — `get_overlay()` (310-321), `post_score_preview()` (216-238), `create_app` in-factory imports (118-126), `overlay_cfg` injection, entrypoint — the route to modify and the route to delete, and the crash-isolation import discipline.
- `src/segugio/ui/templates/overlay.html` (read in full) — the `vh/vw` lower-third layout, `opacity:0` start + `.is-entering`/`.is-exiting`/`.is-live`/`.pulse-once`/`.is-stale` classes, the CSS-var theme, the bootstrap `window.OVERLAY_CFG`. Grounds Patterns 2 & 3.
- `src/segugio/ui/static/overlay-render.js` (read in full) — frozen renderer; resting-timer values, per-request poll nonce (`++reqSeq`), response-recency watchdog (`isStale`, `lastResponseAt`, `everResponded`), `cleanField`/`scvGet`/`DISCIPLINE_CELLS`. Grounds Pattern 3 + the value cross-check.
- `src/segugio/ui/templates/console.html` (lines 1-30, 150-160, 250-460) — the exact mirror block + wiring + CSS + DOM ids to delete; the surviving score/run wiring to keep. Grounds the Safe Deletion Inventory.
- `src/segugio/ui/score_render.py` (read in full) — `render_overlay_text`/`_get`/`_clean` (`_MAX_FIELD_LEN=64`), UNCHANGED; the value cross-check reference.
- `tests/test_ui_overlay_render.py`, `tests/test_ui_overlay_page.py`, `tests/test_imports.py`, `tests/test_score_preview.py` (read in full) — the node value-cross-check harness, the served-HTML assertion precedent, the RBT-07 heavy-absent gate, the route test to delete.
- `.planning/phases/12-scv-01-unification/12-CONTEXT.md` + `.planning/phases/11-.../11-CONTEXT.md` — locked decisions D-01..D-07, phase boundary, inherited renderer decisions.
- `.planning/REQUIREMENTS.md` (SCV-02, Out-of-Scope HARD table, RBT-06/RBT-07 status) — the single requirement + invariants.
- Grep `"/score/preview"` across repo — confirms the route has exactly three references (def + deleted caller + deleted test) → no caller after the phase.
- `git log` on `overlay-render.js` — confirms the `quick-260615-sod` (poll nonce) and `f635f5c tsi` (response-recency watchdog) fixes to preserve.

### Secondary (MEDIUM confidence)
- Auto-memory `overlay-bugs-sandbox-repro` (sandbox-first verification), `phase8-live-multiview-on-rig` (renderer verified live), `gsd-execute-phase-env-gotchas`.

### Tertiary (LOW confidence)
- None — every claim is grounded in a read file or grep in this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; everything verified against installed code.
- Architecture (preview threading, iframe, deletion inventory): HIGH — grounded line-by-line in the actual files.
- Pitfalls: HIGH — derived from the verified code paths (poll nonce, watchdog, crash-isolation test).
- Resting-display recommendation (A3): MEDIUM — correct-by-construction but a UX choice the planner should confirm.

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable — internal subsystem, no fast-moving external dependency).
