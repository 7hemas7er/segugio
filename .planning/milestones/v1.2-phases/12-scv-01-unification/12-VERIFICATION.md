---
phase: 12-scv-01-unification
verified: 2026-06-16T00:00:00Z
status: passed
score: 3/3 must-haves verified
human_verification_result: passed (12-UAT.md — 2/2 passed 2026-06-16: visual 16:9 fidelity ✓, live score-update flow ✓)
overrides_applied: 0
human_verification:
  - test: "Open a browser to the console (or use create_app sandbox on an alt port). Confirm the 16:9 preview box renders the lower-third lower-third with the correct neutral backdrop (#6b6f76), the plate is visible, and the title-safe band placement looks correct."
    expected: "The overlay lower-third is visible inside the 16:9 iframe, positioned at the bottom-left with the plate transparency and font readable. The neutral gray backdrop lets the operator judge plate opacity. The on-air badge reads '● ON AIR'."
    why_human: "CSS layout, compositing, and visual fidelity cannot be verified programmatically. The test requires a browser to render the iframe in a 16:9 box and a human eye to judge placement, transparency, and the title-safe band — the stated purpose of the SCV-02 unification (D-03)."
  - test: "With the console open, enter a score in all three disciplines in turn. Confirm the iframe updates (the overlay-render.js poll loop runs) and shows the correct field values for each discipline without any JS console error."
    expected: "After each discipline switch and field entry, the iframe overlay updates within the poll interval (~200ms) showing the correct sanitized values. No JS ReferenceError, no broken score form, no broken run buttons."
    why_human: "Live polling behavior and the absence of JS runtime errors require a live browser session. The test also validates that the surviving score form still POSTs correctly after the mirror deletion."
---

# Phase 12: SCV-01 Unification Verification Report

**Phase Goal:** The console's live score preview renders through the exact same `/overlay` route that OBS loads, making console↔OBS drift structurally impossible and retiring the hand-maintained byte-exact Python↔JS mirror and its `/score/preview` drift-guard.
**Verified:** 2026-06-16T00:00:00Z
**Status:** passed (automated 3/3 + human UAT 2/2 on 2026-06-16)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Console live preview loads `/overlay?preview=1` (iframe reuse) — both console preview and OBS overlay resolve to one renderer at one URL | VERIFIED | `console.html` line 277: `<iframe src="/overlay?preview=1" title="Anteprima overlay live">`. Behavioral check: `create_app(tmp).test_client().get("/")` response contains `<iframe src="/overlay?preview=1"`. All 4 `test_ui_scv_unification.py` structural tests XPASS. |
| 2 | The byte-exact `render_overlay_text` JS mirror block and `POST /score/preview` drift-guard are retired; `render_overlay_text` (Python) survives unchanged as the `overlay.txt` fallback renderer | VERIFIED | `console.html`: all 10 mirror symbols absent (confirmed by live check and `test_mirror_symbols_gone` XPASS). `app.py`: no `post_score_preview` function, no `/score/preview` route string. `POST /score/preview` returns 404. `score_render.py` is 86 lines, unchanged, and `render_overlay_text` is imported and called at `app.py` line 210. |
| 3 | Parity check confirms console preview and OBS-served overlay share the same template + `/overlay-json` shape, and the crash-isolation import test stays green | VERIFIED | `/overlay` and `/overlay?preview=1` share identical DOM ids (`#lower-third`, `#identity`, `#timer`, `#cells`) and `<script src="/static/overlay-render.js">`. `overlay.html` `<body>` tag emits `class="preview"` only for `?preview=1` and `class=""` for bare `/overlay`. `test_value_crosscheck` (Node vs Python `_get` per discipline) passes. All 25 `test_imports.py` crash-isolation tests pass. |

**Score:** 3/3 truths verified

### Requirement Coverage

| Requirement | Phase | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| SCV-02 | Phase 12 | Console score preview reuses the same `/overlay` renderer (iframe), retiring the byte-exact Python↔JS mirror + drift-guard `POST /score/preview` | SATISFIED | All three truths above verified. REQUIREMENTS.md traceability table marks SCV-02 as Complete at Phase 12. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/app.py` | `get_overlay()` reads `request.args.get("preview")` flag; `post_score_preview()` removed | VERIFIED | Line 300: `preview = request.args.get("preview") == "1"`. Line 302: `render_template("overlay.html", preview=preview, **overlay_cfg)`. No `post_score_preview` anywhere in the file. No `/score/preview` route string. `render_overlay_text` still imported (line 53) and used (line 210). |
| `src/segugio/ui/templates/overlay.html` | `<body>` carries `{{ 'preview' if preview else '' }}`; three `body.preview` CSS rules | VERIFIED | Line 224: `<body class="{{ 'preview' if preview else '' }}">`. Lines 213, 216, 220-221: three preview CSS rules — neutral backdrop, force-visible `opacity: 1 !important`, run-edge animation suppressed. |
| `src/segugio/ui/templates/console.html` | iframe embed + on-air label + 16:9 box CSS; mirror block and wiring removed | VERIFIED | Lines 276-278: `<div class="overlay-preview-frame"><iframe src="/overlay?preview=1" ...>`. Line 275: label with `come va in onda` + `ON AIR` span. Lines 153-163: `.overlay-preview-frame` CSS with `aspect-ratio: 16 / 9`. No mirror symbols present. |
| `tests/test_ui_scv_unification.py` | Four structural tests (iframe embed, mirror-symbols-gone, surviving wiring, /score/preview 404) | VERIFIED | File exists. All 4 tests XPASS (`test_console_embeds_overlay_iframe`, `test_mirror_symbols_gone`, `test_surviving_console_wiring_intact`, `test_score_preview_route_removed`). |
| `tests/test_ui_overlay_render.py::test_value_crosscheck` | Node vs Python sanitized-value parity per discipline | VERIFIED | Function at line 164. Passes (not xfail). Asserts identical values for disc_tf (control-char dropped, >64 capped), disc_freestyle (UTF-8 café preserved), agility (sct/SCT alias resolved). |
| `tests/test_ui_overlay_page.py` — preview assertions | `_serve_preview()` + 4 preview=1 structural assertions | VERIFIED | `_serve_preview()` at line 171. `test_preview_shares_dom_and_script` XPASS. `test_preview_force_visible_rule_present` XPASS. `test_preview_no_store` XPASS. `test_preview_flag_threads_body_class` XFAIL (see Anti-Patterns, WR-01). |
| `tests/test_score_preview.py` | Deleted (route removed in 12-02) | VERIFIED | File does not exist on disk. `python -m pytest -q` collects without error. |
| `tests/test_ui_explainability.py` | 4 obsolete Phase-9 SCV-01 mirror tests retired; `test_scv01_score_inputs_touch_contract` kept | VERIFIED | File contains 8 test functions. `test_scv01_mirror_matches_render_overlay_text` et al. are gone. SCV-02 note at line 310 redirects to `test_value_crosscheck`. `test_scv01_score_inputs_touch_contract` at line 322 passes. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `console.html .overlay-preview-frame iframe` | `GET /overlay?preview=1` | same-origin iframe src | WIRED | `src="/overlay?preview=1"` present in `console.html`. Route exists in `app.py` and returns 200. |
| `app.py::get_overlay` | `overlay.html` | `render_template("overlay.html", preview=preview, **overlay_cfg)` | WIRED | Line 302 of `app.py`. Pattern `render_template("overlay.html", preview=preview` confirmed present. |
| `overlay.html body.preview` | CSS force-visible / backdrop | `body.preview { background ... }`, `body.preview #lower-third { opacity: 1 !important }` | WIRED | Lines 213 and 216 of `overlay.html`. Preview body tag emits `class="preview"` when flag is set, `class=""` otherwise (confirmed via runtime check). |
| `console.html score form submit` | `POST /score` | surviving `post("/score", ...)` listener | WIRED | `console.html` line 338: `post("/score", data)`. `test_surviving_console_wiring_intact` XPASS. |
| `app.py::post_score` | `score_render.render_overlay_text` | import + call on line 53/210 | WIRED | `render_overlay_text` imported at `app.py` line 53; called at line 210 for `overlay.txt` fallback write. Not orphaned. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `overlay.html` iframe | overlay-json payload | `GET /overlay-json` (polled by `overlay-render.js`) | Yes — reads `score.json` + `overlay_run.json` via `read_score` / `read_overlay_run` | FLOWING |
| `console.html` iframe embed | Same as above (shared renderer) | Same `/overlay-json` poll — one renderer, one data source | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Console GET `/` contains iframe | `create_app(tmp).test_client().get("/")` → check `<iframe src="/overlay?preview=1"` | PRESENT | PASS |
| `POST /score/preview` returns 404 | `client.post("/score/preview", ...)` | Status 404 | PASS |
| `/overlay?preview=1` body tag | Runtime: `<body class="preview">` | Confirmed | PASS |
| Bare `/overlay` body tag | Runtime: `<body class="">` | Confirmed (not `class="preview"`) | PASS |
| All mirror symbols absent | Runtime check of 10 symbols | All ABSENT | PASS |
| Surviving wiring intact | `post("/score"`, `data-action="start"/"stop"`, `function showFields` | All PRESENT | PASS |
| `render_overlay_text` still active | Import + call in `app.py` lines 53, 210 | PRESENT and called | PASS |
| Crash-isolation gate | `python -m pytest tests/test_imports.py` | 25/25 passed | PASS |
| Phase-12 graded suites | `python -m pytest tests/test_ui_scv_unification.py tests/test_ui_overlay_page.py tests/test_ui_overlay_render.py tests/test_imports.py tests/test_ui_explainability.py -q` | 58 passed, 1 xfailed, 7 xpassed (exit 0) | PASS |

### Probe Execution

No probes declared in PLAN files. No conventional `scripts/*/tests/probe-*.sh` applicable to this UI phase. Step 7c: SKIPPED (no probes declared).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_ui_overlay_page.py` | 179-187 | `test_preview_flag_threads_body_class` is permanently masked: the assertion `"body.preview" not in bare_html` can never pass because `body.preview { ... }` CSS rules are inlined into every `/overlay` response. The test correctly fails but stays reported as `xfail` (masked) under `strict=False`. | WARNING (WR-01 from code review) | The invariant "broadcast page body must NOT be in preview mode" is not enforced by this test. Runtime behavior is correct (`<body class="">` on broadcast, `<body class="preview">` on preview=1), but the regression guard has a hole exactly where SCV-02's "drift structurally impossible" claim relies on it. |
| `src/segugio/ui/templates/overlay.html` | 216 | `body.preview #lower-third { opacity: 1 !important }` overrides `.is-stale { opacity: 0.55 }` because `!important` beats non-`!important` regardless of specificity. The comment on line 219 claims `.is-stale` logic is "untouched" but the opacity half of that degrade is suppressed under preview. | WARNING (WR-02 from code review) | A stale overlay in the console preview shows at full opacity rather than dimmed, partially undermining the "looks exactly like what airs" goal. Grayscale filter still applies. Not a security or data issue. |
| `tests/test_ui_scv_unification.py`, `tests/test_ui_overlay_page.py` | Various | Six shipped-feature tests (`test_console_embeds_overlay_iframe`, `test_mirror_symbols_gone`, `test_surviving_console_wiring_intact`, `test_score_preview_route_removed`, `test_preview_shares_dom_and_script`, `test_preview_force_visible_rule_present`, `test_preview_no_store`) are `xfail(strict=False)` but now XPASS. With `strict=False` a future regression would flip these back to `xfail` and still report "passing" — no failure raised. | WARNING (WR-03 from code review) | The structural-contract tests lose their hard-assert protection now that the implementation has shipped. This is the 12-REVIEW WR-03 finding. |

No `TBD`, `FIXME`, or `XXX` debt markers found in phase-modified files.

### Human Verification Required

#### 1. Visual 16:9 Preview Fidelity

**Test:** Open the console in a browser (or run `create_app` on an alt port per the `overlay-bugs-sandbox-repro` project memory — never POST to the live `:8080` console). Navigate to the operator console and observe the "Anteprima overlay" section.
**Expected:** The 16:9 framed box renders the overlay lower-third over a neutral gray (#6b6f76) backdrop. The plate is visible (not transparent-on-white, not invisible), positioned at the bottom-left. The `● ON AIR` badge appears. The `come va in onda` label is present above the frame. The operator can judge the plate transparency and the title-safe band placement.
**Why human:** CSS compositing, aspect ratio behavior, and visual scale cannot be verified programmatically. This is the stated purpose of D-03 — the operator uses the preview to judge what will air.

#### 2. Live Score Update Flow in Preview Iframe

**Test:** With the console open in a browser (sandbox alt-port), enter score values in the disc Toss & Fetch fields and click "Aggiorna punteggio". Switch disciplines to Freestyle and enter values. Then switch to Agility.
**Expected:** The iframe updates within the poll interval (~200ms) showing the correct sanitized values for each discipline. The score form POSTs successfully (no network error). The run start/stop buttons remain functional. No JS console errors (no `ReferenceError` for deleted mirror symbols).
**Why human:** Live browser polling behavior, JS runtime error detection, and cross-form wiring require a live browser session. The test exercises the critical path that the mirror deletion (D-05) must not break.

### Gaps Summary

No gaps blocking goal achievement. All three success criteria are VERIFIED in the codebase. The three WARNING-level findings (WR-01, WR-02, WR-03) are quality defects inherited from the code review phase (12-REVIEW.md) and do not prevent the phase goal from being achieved — the runtime behavior is correct, the structural guarantees hold, and the test suite exits 0. They are tracked for cleanup in a future quick-fix pass.

The `status: human_needed` results from two visual/behavioral checks that are deferred to UAT per the 12-03 plan's explicit "MANUAL/UAT (deferred to verify-work)" note — not from any automated-check failure.

---

_Verified: 2026-06-16_
_Verifier: Claude (gsd-verifier)_
