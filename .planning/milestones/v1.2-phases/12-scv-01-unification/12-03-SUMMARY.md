---
phase: 12-scv-01-unification
plan: 03
subsystem: ui
tags: [overlay, console, iframe, scv, deletion, jinja]

# Dependency graph
requires:
  - phase: 12-scv-01-unification
    provides: "12-01 RED-by-design structural contract (iframe-embed + mirror-symbols-gone tests) this plan flips to PASS, and 12-02's GET /overlay?preview=1 body.preview cosmetic fork the embedded iframe consumes"
  - phase: 11-shared-graphical-renderer-overlay-page-branding
    provides: "the ONE /overlay route + frozen /static/overlay-render.js the iframe reuses (the single renderer the console preview now points at)"
provides:
  - "console.html preview region is a same-origin <iframe src=\"/overlay?preview=1\"> in a 16:9 framed box over a neutral #6b6f76 backdrop + a D-02 on-air label (come va in onda / ● ON AIR) — drift console-vs-OBS structurally impossible (SCV-02)"
  - "the gsd:scv01-mirror block + scvCurrentFields/updateScorePreview/scheduleScorePreview/scvPreviewTimer/setDrift/driftCheck + #overlay-preview/#drift-warning + every preview listener REMOVED (D-05), surviving post(/score)/run-buttons/showFields/gsd:why-mirror intact (Pitfall 1)"
affects: [13-obs-scene-collection-setup-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Iframe reuse of the one renderer: the console preview embeds the SAME /overlay page OBS loads (preview=1 cosmetic fork) instead of a duplicated Python↔JS byte-mirror → no second sanitize/render to drift (SCV-02 = drift structurally impossible, not drift-detected)"
    - "Deleting code deletes its tests: the Phase-9 byte-mirror tests (test_scv01_mirror/byte_reference/cleanfield/preview_no_orchestrator) are retired with the mirror; their byte-parity guarantee migrates to the frozen-renderer test_value_crosscheck (12-01) + the structural test_ui_scv_unification contract"

key-files:
  created: []
  modified:
    - src/segugio/ui/templates/console.html
    - tests/test_ui_explainability.py

key-decisions:
  - "Iframe src is EXACTLY /overlay?preview=1 with NO ?t= nonce (Pitfall 2): the host console page is no-store and the renderer's own /overlay-json poll carries the ++reqSeq cache-bust — a host-page nonce would be redundant and force a full reload on every score change"
  - "on-air-tag styled with the status-palette LIVE green (#34D399 on #14161a) for a small color-distinct ON-AIR badge consistent with the console tile-state palette"
  - "Retire (not silence) the 4 obsolete Phase-9 SCV-01 mirror tests in test_ui_explainability.py: they asserted the now-deleted mirror exists, so they fail by construction once the mirror is gone — the same disposition 12-01 applied to test_score_preview.py. test_scv01_score_inputs_touch_contract is unrelated to the mirror and kept; the three now-unused imports (render_overlay_text/Discipline/ScoreDoc) removed to keep the module lint-clean"

patterns-established:
  - "Pattern: a same-origin iframe sized to a 16:9 aspect-ratio box reproduces the overlay's vh/vw lower-third placement + scale for free — no JS letterbox math, the operator judges placement/title-safe band/transparency over a neutral backdrop"

requirements-completed: [SCV-02]

# Metrics
duration: 4min
completed: 2026-06-15
---

# Phase 12 Plan 03: Console Iframe Rewrite Summary

**The console live preview is now a same-origin `<iframe src="/overlay?preview=1">` in a 16:9 framed box over a neutral backdrop with a D-02 on-air label — reusing the ONE `/overlay` renderer OBS loads — and the entire hand-maintained `gsd:scv01-mirror` byte-mirror plus all its wiring, CSS, and DOM is deleted (D-05), closing SCV-02 (drift structurally impossible).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-15T22:37:48Z
- **Completed:** 2026-06-15T22:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced the `#overlay-preview`/`#drift-warning` CSS (lines ~153-160) with the `.overlay-preview-frame` 16:9 box (`aspect-ratio: 16 / 9`, neutral `#6b6f76` backdrop, `border-radius: 6px`, `overflow: hidden`) + `.overlay-preview-frame iframe` (full-bleed, `border: 0`) + a discretionary `.on-air-tag` badge (status-palette LIVE green).
- Replaced the mirror preview div with the D-02 on-air label `Anteprima overlay — come va in onda` + `<span class="on-air-tag">● ON AIR</span>` and `<div class="overlay-preview-frame"><iframe src="/overlay?preview=1" title="Anteprima overlay live"></iframe></div>` — the `<button type="submit">Aggiorna punteggio</button>` below it kept intact. No `?t=` nonce on the src (Pitfall 2).
- Deleted the entire `gsd:scv01-mirror` block (`SCV_MAX_FIELD_LEN`, `SCV_NONPRINT`, `cleanField`, `scvGet`, `mirrorOverlayText`, both `:start`/`:end` markers) plus all wiring (`scvCurrentFields`, `updateScorePreview`, `scvPreviewTimer`, `scheduleScorePreview`, `setDrift`, `driftCheck`, the `.campi input` `forEach`, the second `change`→`updateScorePreview` listener, the seed call, and the `form-score` submit→`driftCheck` listener) — net -219 lines.
- Verified ZERO leftover reference to any deleted identifier (Pitfall 1: a ReferenceError would abort the whole inline `<script>` and break run/score wiring) and that the surviving `post("/score")`, run buttons, `function showFields`, `sel.addEventListener("change", showFields)`, `CAMS`/`CAM_LABEL`, and `gsd:why-mirror` block all remain.
- The four 12-01 structural tests (`test_console_embeds_overlay_iframe`, `test_mirror_symbols_gone`, `test_surviving_console_wiring_intact`, `test_score_preview_route_removed`) now pass (xfail → XPASS under strict=False).

## Task Commits

Each task was committed atomically:

1. **Task 1: Embed /overlay?preview=1 iframe + on-air label + 16:9 box CSS** - `c0b65c2` (feat)
2. **Task 2: Delete the gsd:scv01-mirror block + all its wiring** - `53b4920` (feat)

## Files Created/Modified
- `src/segugio/ui/templates/console.html` (modified) - Preview region became a same-origin iframe of `/overlay?preview=1` in a 16:9 box + D-02 on-air label; the byte-mirror block, its wiring, CSS, and DOM elements removed.
- `tests/test_ui_explainability.py` (modified) - Retired the 4 obsolete Phase-9 SCV-01 mirror tests (the mirror they exercised is deleted); kept `test_scv01_score_inputs_touch_contract` (unrelated to the mirror); removed the now-unused `render_overlay_text`/`Discipline`/`ScoreDoc` imports and the `_PARITY_CASES`/`_py_render` helpers; added a SCV-02 unification note pointing to where byte-parity now lives.

## Decisions Made
- The iframe src is exactly `/overlay?preview=1` with NO `?t=` nonce (Pitfall 2): the host page is `no-store` and the renderer's `/overlay-json` poll already carries the `++reqSeq` cache-bust; a host-page nonce would force a full reload on every score change.
- Styled the `.on-air-tag` with the console status-palette LIVE green for a small, color-distinct ON-AIR badge consistent with the tile-state palette.
- Retired (not silenced) the 4 obsolete Phase-9 SCV-01 mirror tests — they assert the deleted mirror exists, so they fail by construction once it is gone; the same disposition 12-01 applied to `test_score_preview.py`. The byte-parity guarantee now lives in `test_ui_overlay_render.py::test_value_crosscheck` (frozen renderer vs Python) and the structural contract in `test_ui_scv_unification.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Retired the obsolete Phase-9 SCV-01 mirror tests broken by the mandated deletion**
- **Found during:** Task 2 (full-suite verification)
- **Issue:** `tests/test_ui_explainability.py` carried 4 tests (`test_scv01_mirror_matches_render_overlay_text`, `test_scv01_byte_reference_strings`, `test_scv01_cleanfield_mirrors_clean`, `test_scv01_preview_no_orchestrator_roundtrip`) that assert the `gsd:scv01-mirror` block / `mirrorOverlayText` / `cleanField` / `/score/preview` / `#overlay-preview` exist in the served console. This plan deletes exactly that mirror (D-05), so those tests fail by construction — they test the deleted code, not a regression.
- **Fix:** Removed the 4 obsolete tests + their `_PARITY_CASES`/`_py_render` helpers + the section header, kept the unrelated `test_scv01_score_inputs_touch_contract`, removed the three now-unused imports, and added a SCV-02 note pointing to where the byte-parity contract now lives (`test_value_crosscheck` + `test_ui_scv_unification`). This is the same disposition 12-01 applied when it deleted `test_score_preview.py`.
- **Files modified:** tests/test_ui_explainability.py
- **Commit:** 53b4920

## Issues Encountered
- The full suite (`python -m pytest -q`) still shows the **4 pre-existing `tests/test_fan_out_batched.py` failures** (`ModuleNotFoundError: No module named 'ultralytics'` in `src/segugio/tracking/reid_check.py`). These are the CPU-only-`venv` environment artifact already logged to `.planning/phases/12-scv-01-unification/deferred-items.md` by 12-02 (GPU work runs from `venv312/` per project memory); wholly unrelated to the UI/overlay surface this plan touches. Left unfixed (out of scope). Every Phase-12 graded UI suite (`test_ui_scv_unification`, `test_ui_overlay_page`, `test_ui_overlay_render`, `test_imports`, `test_ui_explainability`) exits 0.

## User Setup Required
None - no external service configuration required.

## Manual Verification (deferred to verify-work)
- Visually confirm the scaled 16:9 framed preview reads placement / title-safe band / plate transparency / relative scale over the neutral `#6b6f76` backdrop (D-03) in a sandbox console (alt-port `create_app(tmp)` test client — NEVER the live `:8080` console, per auto-memory `overlay-bugs-sandbox-repro`).

## Next Phase Readiness
- SCV-02 is now fully closed across the phase: 12-02 landed the `preview=1` server fork + removed `POST /score/preview`; 12-03 embeds the iframe and deletes the mirror. The console preview and the OBS browser-source resolve to ONE renderer at ONE URL — `render_overlay_text` survives only as the `overlay.txt` fallback.
- Phase 13 (OBS scene collection) is unblocked: the `/overlay` route is the single transparent browser-source target; the iframe reuse proves the page renders correctly in an embedded frame.
- No blockers. No new runtime surface, no new dependency, crash-isolation (RBT-07) untouched (app.py not modified; only the template + a test).

## Self-Check: PASSED

- Files: FOUND `src/segugio/ui/templates/console.html` (iframe `/overlay?preview=1` present, `gsd:scv01-mirror` absent), FOUND `tests/test_ui_explainability.py`.
- Commits: FOUND `c0b65c2`, FOUND `53b4920`.

---
*Phase: 12-scv-01-unification*
*Completed: 2026-06-15*
