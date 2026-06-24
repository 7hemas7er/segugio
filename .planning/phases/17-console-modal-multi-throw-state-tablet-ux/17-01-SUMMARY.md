---
phase: 17-console-modal-multi-throw-state-tablet-ux
plan: 01
subsystem: ui
tags: [jinja-partial, localStorage, vanilla-js, xss, tablet-ux, score-entry]

# Dependency graph
requires:
  - phase: 16-shared-entry-component-dedicated-page-server-authoritative-p
    provides: "score-entry.js mount(root,cfg) factory + score-entry.html thin host + authoritative POST /score"
provides:
  - "_score-entry-form.html — the ONE shared host markup partial (anti-drift spine for Plan 02's console modal)"
  - "score-entry.html rewired to {% include %} the partial (no inlined host markup)"
  - "Reload-safe localStorage draft for the flat disc-T&F throw list (save on mutation, never-raise restore, clear only on 2xx)"
  - "Two-step danger-styled publish confirm with auto-revert + Enter-never-publishes guard"
affects: [17-02, console-modal, tablet-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One shared Jinja partial = one host-markup source across page + modal (SCV-02 one-renderer applied to a form)"
    - "localStorage draft: one fixed key, atomic per setItem, try/caught never-raise reader, cleared only on success"
    - "Two-step arm→confirm publish gate (button never disabled; the confirm IS the gate)"
    - "node fake-DOM harness for behavior-testing the mount() closure without a browser"

key-files:
  created:
    - "src/segugio/ui/templates/_score-entry-form.html"
  modified:
    - "src/segugio/ui/templates/score-entry.html"
    - "src/segugio/ui/static/score-entry.js"
    - "tests/test_ui_score_entry.py"

key-decisions:
  - "DRAFT_KEY is a single fixed string 'segugio.score.draft' — no per-run/per-discipline keying (Deferred Idea)"
  - "Auto-revert window for the armed confirm set to 4000ms"
  - "Added a hand-rolled node fake-DOM harness (DOM tree + classList + localStorage + fetch/timer stubs) to exercise mount() end-to-end, matching the MEMORY 'node fake-DOM' precedent"

patterns-established:
  - "Shared host-markup partial included by both the dedicated page and (later) the console dialog"
  - "Reload-safe localStorage draft with never-raise restore and success-only clear"
  - "Two-step danger confirm + Enter suppression as the broadcast-integrity gate"

requirements-completed: [SCC-05, SCE-04]

# Metrics
duration: 9min
completed: 2026-06-24
---

# Phase 17 Plan 01: Shared Score-Entry Partial, Reload-Safe Draft & Two-Step Publish Confirm Summary

**Extracted the score-entry host markup into one shared Jinja partial the dedicated page now includes, and added reload-safe localStorage draft persistence + a two-step danger-styled publish confirm with Enter-never-publishes — all inside the single mount() closure, zero new assets, no innerHTML.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-24T15:27:54Z
- **Completed:** 2026-06-24T15:37Z (approx)
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `_score-entry-form.html` now holds the exact host markup (score-cfg blob + score-entry-root + publish-banner + 2 script tags) — the D-08 anti-drift spine Plan 02's console `<dialog>` will include verbatim; the dedicated page `{% include %}`s it instead of inlining.
- The flat best-5-of-N throw list (D-01) is now reload-safe: written to one localStorage key on every add/remove/input mutation, silently restored at the end of `mount()` via a try/caught never-raise reader, and cleared ONLY on a 2xx publish (400 and network errors keep it).
- Publishing is now a two-step deliberate action: the first tap morphs the button into a danger-styled "Conferma invio" (4s auto-revert), and only a second tap POSTs. Enter in any field is swallowed (preventDefault) and never arms, confirms, or POSTs. The button is never disabled.
- `score_calc` (Python and JS) untouched — the flat list and the drift-guard parity are preserved.

## Task Commits

1. **Task 1: Extract shared host partial + include from dedicated page** - `3759d46` (feat)
2. **Task 2: Reload-safe localStorage draft (TDD)** - `f78f12a` (test, RED) → `0f5965c` (feat, GREEN)
3. **Task 3: Two-step publish confirm + Enter-guard (TDD)** - `4ffdaba` (test, RED) → `d606725` (feat, GREEN)

_TDD tasks carry a RED test commit then a GREEN implementation commit. No refactor commits were needed._

## Files Created/Modified
- `src/segugio/ui/templates/_score-entry-form.html` (NEW) - The one shared score-entry host markup partial (cfg blob + root + banner + score-calc.js/score-entry.js script tags); zero new external asset.
- `src/segugio/ui/templates/score-entry.html` - Inlined host markup (former lines ~78-93) replaced by `{% include "_score-entry-form.html" %}`; `<style>` token set and `<h1>` stay on the page.
- `src/segugio/ui/static/score-entry.js` - Inside the one `mount()` closure: `DRAFT_KEY` + `saveDraft()`/`restoreDraft()` (never-raise reader), draft-clear only in the `resp.ok` branch, the arm→confirm publish gate with auto-revert, and the Enter-suppression keydown guard. No innerHTML introduced.
- `tests/test_ui_score_entry.py` - Added a hand-rolled node fake-DOM harness and six behavior tests (draft persist/restore, corrupt-draft empty, clear-only-on-2xx, two-step confirm, auto-revert, never-disabled, Enter-never-publishes).

## Decisions Made
- `DRAFT_KEY = "segugio.score.draft"` — a single fixed key (no per-run/per-discipline keying, which is a Deferred Idea).
- Auto-revert window for the armed confirm = 4000ms.
- Built a minimal node fake-DOM harness (element tree, classList, value/checked, querySelector with descendant-combinator support, in-memory localStorage, recorded setTimeout, controllable fetch stub) so the three Phase-17 behaviors could be exercised end-to-end against the served module without a browser. This follows the MEMORY "node fake-DOM" precedent and reuses the existing UTF-8 `_run_node` machinery shape.

## Deviations from Plan

None - plan executed exactly as written. (All three tasks implemented as specified; the only additive work was the node fake-DOM test harness, which is the explicit means by which the plan's behavior acceptance criteria are verified — not a scope change.)

## Issues Encountered
- A literal `{% include %}` written inside an HTML comment in the partial/page was parsed by Jinja and raised `TemplateSyntaxError`. Resolved by rephrasing the comments to avoid Jinja statement-block tokens (the actual include directive is the only `{% %}` in the templates). Caught and fixed before the Task 1 commit.
- `module` cannot be redeclared in node's CJS wrapper — the fake-DOM shim now uses the wrapper-provided `module.exports`. Fixed during the Task 2 RED harness setup.
- The plan's inline Task 2/Task 3 `innerHTML` verify snippet only strips `//` line comments, so it false-positives on the file's block-comment header that mentions "innerHTML". The authoritative gate is the pytest `test_no_innerhtml_sink` (checks for actual `innerHTML =` sink patterns), which passes; `grep` confirms every `innerHTML` occurrence in the file is inside a comment.

## Test Status
- `tests/test_ui_score_entry.py` — 11 passed (5 prior + 6 new behavior tests).
- `tests/test_imports.py`, `tests/test_ui_score_calc_js.py` (drift-guard), `tests/test_ui_score_authoritative.py`, `tests/test_ui_score.py`, `tests/test_score_display_only.py`, `tests/test_overlay_html_sink_gate.py` — all green.
- 5 pre-existing failures remain in the full suite (`test_ndi_mock_sender`, `test_ndi_source`, `test_ui_explainability::test_leaderboard_renders_sorted`, `test_ui_scv_unification::test_console_embeds_overlay_iframe`, `test_ui_tablet_layout::test_touch_action_and_targets`). Confirmed they reproduce identically on the pre-plan baseline (`3759d46~1`) and are unrelated to this plan's files (NDI hardware, node ESM mirror, and console iframe/tablet layout that Plan 02 delivers). Logged as out-of-scope; not fixed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The shared `_score-entry-form.html` partial is the spine Plan 02 needs: the console `<dialog>` includes the SAME partial and mounts the SAME `score-entry.js` on dialog-open, so the page and modal are byte-for-byte identical.
- The three component behaviors (draft persistence, two-step confirm, Enter-guard) land once in the one JS module and are automatically inherited by both hosts.
- Plan 02 still needs: console `<dialog>` + trigger, the on-air readout poll, `score_cfg=_score_cfg` on `index()`, retirement of the legacy `#form-score` + `_is_legacy_score_post` branch, and the `tests/test_imports.py` POST /score assertion update (D-11).

## Self-Check: PASSED

All created/modified files exist on disk and all task commits (`3759d46`, `f78f12a`, `0f5965c`, `4ffdaba`, `d606725`) are present in git history.

---
*Phase: 17-console-modal-multi-throw-state-tablet-ux*
*Completed: 2026-06-24*
