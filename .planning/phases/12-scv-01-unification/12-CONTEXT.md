# Phase 12: SCV-01 Unification - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Repoint the console's live score preview to the **one shared `/overlay` renderer** (Phase 11) via an `<iframe src="/overlay?preview=1">`, and **retire the hand-maintained byte-exact Python↔JS mirror** in `console.html` plus its `POST /score/preview` drift-guard. After this phase, the console preview and the OBS browser-source resolve to **one renderer at one URL reading one data source** (`/overlay-json`) — console↔OBS drift becomes structurally impossible instead of guarded.

**In scope (Phase 12):**
- Add `preview=1` handling to the existing `GET /overlay` route (it currently ignores query args) — a **cosmetic** preview affordance only (scaled framing + backdrop + force-visible plate), NOT a second renderer or a second data path.
- Replace the console's `#overlay-preview` text div with an `<iframe src="/overlay?preview=1">` (same-origin).
- **Delete** from `console.html`: the `gsd:scv01-mirror` block (`cleanField`/`scvGet`/`mirrorOverlayText`), `updateScorePreview`, `scheduleScorePreview`, `scvCurrentFields`, `driftCheck`/`setDrift`, `#drift-warning`, and all their wiring (the `input`/`blur`/`change`/`submit` preview listeners).
- **Delete** the `POST /score/preview` route from `app.py`.
- Keep `render_overlay_text` (Python, `score_render.py`) **unchanged** — it is the `overlay.txt` fallback renderer (RBT-06).
- A parity test (structural + value cross-check) and the RBT-07 crash-isolation import test stay green.

**Out of scope (deferred / HARD invariant — never):**
- OBS scene-collection wiring + browser-source settings + setup docs → **Phase 13** (SCN-01/02).
- End-to-end live degrade / poll-storm / HTML-injection acceptance under failure → **Phase 14** (RBT-06).
- Any change to the director, `runstate.json`, the opcomm records, the score data-model, or the graphical renderer's content/layout/sanitize logic (the renderer ships as-is from Phase 11 — Phase 12 only *reuses* it).
- Re-introducing an as-you-type / unsubmitted-edit preview path (explicitly rejected below — it would reopen the drift the phase closes).
</domain>

<decisions>
## Implementation Decisions

### Preview semantics (the behavioral heart)
- **D-01: Published-only preview.** The console preview iframe shows **exactly** what `/overlay-json` serves — the last *submitted* score (`/score`) + the live run state — byte-faithful to OBS by construction. The instant **as-you-type text preview is RETIRED** together with the JS mirror. One renderer, one source; drift impossible. (Rationale accepted by the user: for a live operator, "what's on air right now" is more useful than "what I'm typing", and it's the only honest unification.)
- **D-02: On-air label.** Relabel the preview area so it's unambiguous the iframe shows the **live published / on-air** overlay (e.g. "Anteprima overlay — come va in onda" and/or a small ON-AIR tag), not a draft of what's being typed. Prevents the "why isn't my typing showing?" confusion the change could otherwise cause. (Copy is Italian — match `console.html` conventions.)

### Panel presentation (how the transparent lower-third reads in the sidebar)
- **D-03: Scaled 16:9 framed box over a neutral backdrop.** `preview=1` renders `/overlay` inside a **fit-to-panel 16:9 box** with a **neutral mid-gray (or subtle checkerboard) backdrop**, so the lower-third's bottom-left position, the title-safe band, transparency, and relative scale all read as they will over real video. The operator judges *placement*, not just text. (Rejected: plain plate on the dark panel — placement/scale/transparency don't read. Rejected: a real grass still — avoids committing/choosing an image asset; revisit only if the neutral backdrop proves hard to judge.)
- **D-04: Force the plate visible in preview.** `preview=1` keeps the lower-third **shown even between runs** (suppresses ONLY the run-edge enter/exit hide/show animation) so pre-run score entry has feedback. **Content, layout, per-discipline cells, and sanitize stay byte-identical to OBS** — only the visibility-gating animation is the scoped cosmetic fork. This does NOT reopen content drift (the drift that matters is values/layout, still one renderer).
  - *Planner note:* with `running === false` the offset-cancellation timer shows its static initial value (T&F 60s / freestyle `freestyleDurationS` / agility 0). Decide the exact resting display; don't let the freshness watchdog dim the forced-visible plate in the local console (responses are instant locally, so `.is-stale` should not trigger — but verify the response-recency watchdog from quick-260615-tsi behaves under `preview=1`).

### `/score/preview` route + parity guard
- **D-05: Delete `POST /score/preview` and the JS mirror entirely.** The route's ONLY caller is the drift-guard being removed, so it has no caller after this phase — remove it rather than keep a dead/repurposed endpoint. The unification is total. (Rejected: downgrading `/score/preview` to a runtime `overlay.txt`-parity endpoint — more surface for a check a test does offline.)
- **D-06: `render_overlay_text` (Python) survives unchanged** as the `overlay.txt` fallback renderer (RBT-06). Phase 12 does NOT touch `score_render.py` logic.
- **D-07: Parity = build/test assertion, structural + value cross-check.** The test asserts BOTH:
  1. **Structural unification** — `console.html` embeds `<iframe src="/overlay?preview=1">`; the `gsd:scv01-mirror` block + `mirrorOverlayText`/`updateScorePreview`/`driftCheck`/`#drift-warning` are GONE; `/overlay` and `/overlay?preview=1` resolve to the same renderer/template (only cosmetic preview differences); the RBT-07 crash-isolation import test stays green.
  2. **Value cross-check** — the graphical overlay (`overlay-render.js` executed in node) and `render_overlay_text`/`overlay.txt` render the **same sanitized field values** for the same `/overlay-json` input, so the broadcast overlay and the text fallback can never silently diverge on the numbers. (Builds on the existing `cleanField`↔`_clean` byte-parity test shipped in 11-03's `tests/test_ui_overlay_render.py`.)

### Claude's Discretion
- Exact iframe dimensions, the 16:9 box CSS (aspect-ratio vs padding hack), the precise neutral backdrop (flat mid-gray vs checkerboard) and its value, and how `preview=1` scales the 1080p-designed lower-third into the small panel (CSS `transform: scale` on a fixed virtual viewport vs `vh/vw`-driven natural scaling).
- The exact ON-AIR label copy/styling (within D-02's intent).
- How `preview=1` is detected/threaded (query arg read in `get_overlay`, passed as a render flag to `overlay.html` / a body class the CSS keys on, or a JS bootstrap flag the renderer reads) — pick the path that keeps the renderer's content logic untouched and the fork purely presentational.
- Whether the value cross-check reuses/extends `tests/test_ui_overlay_render.py` or lands in a new parity test module.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements, roadmap & milestone shape
- `.planning/ROADMAP.md` §"Phase 12: SCV-01 Unification" — the goal + 3 success criteria this phase is graded against, and the v1.2 build-order rationale (renderer must exist first — it does, Phase 11).
- `.planning/REQUIREMENTS.md` — **SCV-02** (the single Phase-12 requirement) + the **Out of Scope** table (WS/MJPEG/SSE transport rejected, free-form HTML rejected, director compute rejected, `overlay.txt` removal rejected — all HARD).

### Prior phase context (the renderer this phase reuses)
- `.planning/phases/11-shared-graphical-renderer-overlay-page-branding/11-CONTEXT.md` — the `/overlay` renderer's decisions (left-accent lower-third, offset-cancellation timer, freshness watchdog, branding) the iframe inherits; §"Deferred Ideas" explicitly hands SCV-02 (this phase) the iframe reuse + mirror retirement. The Phase-11 "Font decision must match what Phase 12's iframe renders" note is satisfied automatically (one page, one font).

### Research (milestone v1.2)
- `.planning/research/v1.2/SUMMARY.md` — publish-and-render decision; the SCV unification = iframe reuse of the one `/overlay` route.
- `.planning/research/v1.2/PITFALLS.md` — P2 (CEF cache: `?t=<gen>` nonce + `no-store`), P3 (crash-isolation: no module-top heavy import), the HTML-injection note (`textContent` not `innerHTML`).
- `.planning/research/v1.2/ARCHITECTURE.md` — contract/route architecture; the fetch discipline the iframe's `overlay-render.js` already follows.

### Code this phase modifies / deletes from / preserves
- `src/segugio/ui/app.py` — **MODIFY** `get_overlay()` (line ~310) to handle `preview=1` (currently ignores query args); **DELETE** `post_score_preview()` (the `POST /score/preview` route, line ~216). Study the crash-isolation import allowlist (Flask + `segugio.opcomm`, Flask imported inside `create_app`) and the `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` entrypoint-arg pattern.
- `src/segugio/ui/templates/console.html` — **DELETE** the `gsd:scv01-mirror` block (lines ~341–391) + `scvCurrentFields`/`updateScorePreview`/`scheduleScorePreview`/`driftCheck`/`setDrift` (lines ~394–446) + `#overlay-preview` (line ~273) + `#drift-warning` (line ~274) and their listeners; **REPLACE** the preview area (lines ~270–274) with the `<iframe src="/overlay?preview=1">` + on-air label (D-02). The HTML comment at lines ~270–271 describing the mirror must go too.
- `src/segugio/ui/templates/overlay.html` — the shared host page (Phase 11). The `preview=1` cosmetic fork (D-03/D-04) is applied here and/or in the renderer; **do not** alter the per-discipline content/DOM contract.
- `src/segugio/ui/static/overlay-render.js` — the shared renderer (Phase 11). Reused as-is for content; if `preview=1` needs the force-visible behavior (D-04), gate ONLY the run-edge animation, never the render/sanitize/timer logic. NOTE recent live fixes this file carries: quick-260615-sod (per-request poll nonce `++reqSeq` for OBS CEF cache) and quick-260615-tsi (freshness watchdog keys on console **response recency**, not gen-age) — preserve both; verify they behave under `preview=1`.
- `src/segugio/ui/score_render.py` — `render_overlay_text` + `_get` + `_clean` (`_MAX_FIELD_LEN = 64`). **UNCHANGED** (overlay.txt fallback, RBT-06) — the value cross-check (D-07) compares against it.

### Crash-isolation gate (RBT-07 — re-asserted as a Phase-12 success criterion)
- `docs/security.md` — the LAN-trust-boundary threat model.
- The `test_app_imports_nothing_heavy`-style import test (forces `torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws` absent AND proves the console starts) — must stay green; the `/overlay?preview=1` change adds no heavy import.

### Existing parity / overlay tests to extend or mirror
- `tests/test_ui_overlay_render.py` — 11-03's served-JS + node-executed behavior tests, incl. the `cleanField` byte-parity vs `_clean` — the natural home/precedent for the D-07 value cross-check.
- `tests/test_ui_overlay_page.py` — 11-02's served-HTML assertions (transparency, DOM ids, no-store) — the precedent for asserting the `preview=1` host-page behavior.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GET /overlay` + `overlay.html` + `overlay-render.js` — the entire shared renderer already ships (Phase 11). Phase 12 *consumes* it via iframe; it builds no new renderer.
- `create_app(..., cam_ids=(), overlay_cfg=None)` entrypoint-arg / `render_template("overlay.html", **overlay_cfg)` pattern — the precedent for any new render flag (e.g. a `preview` flag) without a config import.
- `get_preview_jpg` / `get_overlay_json` `Cache-Control: no-store` precedent — the iframe host page is already `no-store` (line ~320).
- The 11-03 `cleanField`↔`_clean` byte-parity node-execution harness — extend it for the D-07 value cross-check rather than inventing a new mechanism.

### Established Patterns
- **Crash-isolation allowlist** — `import segugio.ui` stays Flask-free; `preview=1` is pure query-arg + template/CSS, no heavy import (Pitfall 3).
- **Display-only verbatim (SCR-04)** — the renderer already shows operator values unmodified via `textContent`; Phase 12 changes nothing here.
- **`?t=<gen>` nonce + `no-store`** + **response-recency freshness watchdog** — the iframe inherits these from `overlay-render.js`; the `preview=1` fork must not break them.
- **Sandbox-first for overlay live-behavior** (auto-memory `overlay-bugs-sandbox-repro`): reproduce any `/overlay` live-behavior change in an alt-port sandbox + node fake-DOM before shipping; never POST to the live `:8080` console. Applies to verifying the `preview=1` force-visible/timer behavior.

### Integration Points
- `console.html` preview area → `<iframe src="/overlay?preview=1">` (same-origin; one new local `/overlay-json` poller per open console — acceptable here; the poll-storm/UXT-02 concurrency concern is Phase 14 scope, not this phase).
- `get_overlay()` reads `request.args` for `preview` and threads a presentational flag into `overlay.html` / a body class.
- Data source is the unchanged `GET /overlay-json` (Phase 10) — the iframe is a pure consumer; no route change there.

</code_context>

<specifics>
## Specific Ideas

- The console preview must read as **"the live overlay OBS is showing,"** not a draft — D-01 + D-02 together. The mental model shift (type → submit → both console + OBS update from `/overlay-json`) is intentional and the founder signed off on losing the instant text preview.
- Preview look: a **scaled 16:9 frame with a neutral 'this sits over your video' backdrop** so the operator can judge placement/transparency/title-safe band — not just legibility of the text.
- The plate is **forced visible between runs in preview only** (D-04) so the operator can format/verify a score before starting a run; on-air it still animates in/out on the run edge.
- Parity is now a **test guarantee**, not a runtime drift-guard: structurally one renderer + a value cross-check against the `overlay.txt` Python renderer (D-07).

</specifics>

<deferred>
## Deferred Ideas

- **OBS scene-collection wiring, browser-source settings, `docs/obs-setup.md`** → Phase 13 (SCN-01/02).
- **End-to-end degrade / `/overlay-json` poll-storm vs `/command` starvation / HTML-injection acceptance under failure** → Phase 14 (RBT-06, UXT-02 extension). Phase 12 adds one local iframe poller but does NOT harden the assembled live path.
- **Agility under/over-SCT color bar** → OVL-FUT-01 (already deferred at Phase 11).

None of the discussion raised new out-of-scope capabilities — it stayed within the iframe-reuse + mirror-retirement boundary.

</deferred>

---

*Phase: 12-scv-01-unification*
*Context gathered: 2026-06-15*
