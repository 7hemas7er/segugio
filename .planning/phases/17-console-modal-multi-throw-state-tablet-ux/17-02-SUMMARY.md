---
phase: 17-console-modal-multi-throw-state-tablet-ux
plan: 02
subsystem: ui
tags: [console, native-dialog, jinja-partial, overlay-json-poll, legacy-retirement, xss, tablet-ux]

# Dependency graph
requires:
  - phase: 17-console-modal-multi-throw-state-tablet-ux
    provides: "_score-entry-form.html shared partial + score-entry.js mount(root,cfg) component (Plan 01)"
  - phase: 16-shared-entry-component-dedicated-page-server-authoritative-p
    provides: "authoritative POST /score (_parse_structured_inputs -> validate -> compute -> _write_score_doc)"
provides:
  - "Console <dialog id=score-dialog> including the SAME shared partial as /score-entry (SCV-02 drift-free across two hosts)"
  - "Read-only on-air readout (discipline + total) polled from /overlay-json, safe-coast + textContent-only"
  - "index() injects score_cfg=_score_cfg so the console-modal partial resolves with the same blob as the dedicated page"
  - "Legacy #form-score + its JS and the _is_legacy_score_post back-compat branch fully retired; authoritative JSON is the SOLE write path"
affects: [console-modal, tablet-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Native <dialog>.showModal() as the focus-trap (no hand-rolled trap) hosting a Jinja-included shared partial"
    - "Mount-on-open: the shared component is mounted via SEGUGIO_SCORE_ENTRY.mount(root, cfg) on dialog-open, re-mountable"
    - "Safe-coast read-only readout poll (textContent-only, named-interval handle, leave-last-value on error)"
    - "Single authoritative write path after legacy back-compat retirement (no flat urlencoded display-only round-trip)"

key-files:
  created: []
  modified:
    - "src/segugio/ui/app.py"
    - "src/segugio/ui/templates/console.html"
    - "tests/test_imports.py"
    - "tests/test_ui_score.py"
    - "tests/test_ui_score_authoritative.py"
    - "tests/test_ui_overlay_json.py"
    - "tests/test_overlay_fallback_gate.py"
    - "tests/test_ui_scv_unification.py"
    - "tests/test_ui_tablet_layout.py"
    - "tests/test_ui_explainability.py"

key-decisions:
  - "On-air total reads fields.totale (disc/freestyle/deduct-agility); falls back to fields.faults for count_up agility (which carries no totale)"
  - "The console modal mounts the component on dialog-open AND score-entry.js still auto-mounts on DOMContentLoaded into the single #score-entry-root — mount() is re-mountable, so the on-open mount cleanly re-runs (restores the localStorage draft each open)"
  - "Stale tests that asserted the retired legacy flat-key path / inline form were updated to the authoritative + modal reality (in-scope: they directly depend on the D-11 change surface)"
  - "Pre-existing class=\"layout\" staleness in test_touch_action_and_targets (Phase-9-era rename) left untouched and logged to deferred-items.md (out of scope; failed identically on baseline)"

patterns-established:
  - "Two hosts (dedicated page + console modal) include ONE Jinja partial and mount ONE component — structural anti-drift"
  - "Read-only authoritative readout over the existing /overlay-json poll channel (no new route, no baked-in score data)"

requirements-completed: []

# Metrics
duration: 16min
completed: 2026-06-24
---

# Phase 17 Plan 02: Console On-Air Readout + Native Score-Entry Modal & Legacy Retirement Summary

**Wired the console as the in-the-flow score-entry surface: a read-only on-air readout polled from /overlay-json plus a native <dialog> that includes the SAME shared partial and mounts the SAME component as the dedicated page — and fully retired the legacy #form-score + the _is_legacy_score_post back-compat branch so the authoritative JSON path is the sole writer.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-06-24T20:05:16Z
- **Completed:** 2026-06-24T20:21:32Z
- **Tasks:** 3
- **Files modified:** 10 (0 created, 10 modified) — 2 source + 8 test files

## Accomplishments
- **Single authoritative write path (D-11):** deleted `_is_legacy_score_post` and its `post_score` branch; the now-unreferenced `_NON_SCORE_KEYS` / `_STRUCTURED_KEYS` frozensets were removed too (verified by grep that their only references were inside the deleted code). A direct LAN POST of the old flat urlencoded shape now correctly 400s (no valid `throws`) instead of silently airing a display-only total.
- **Drift-free two-host form (D-08):** `index()` now injects `score_cfg=_score_cfg` — the SAME blob `/score-entry` gets — and `console.html` adds a native `<dialog id="score-dialog">` whose body is `{% include "_score-entry-form.html" %}` (the exact partial the dedicated page includes). Exactly ONE `#score-entry-root` / `#score-cfg` / `#publish-banner` resolves in the rendered console.
- **Mount-on-open + native focus-trap (D-09/D-10):** the "Inserisci / modifica punteggio" button calls `dialog.showModal()` (native focus-trap + Escape, no hand-rolled trap) and mounts the shared component via `SEGUGIO_SCORE_ENTRY.mount(dialogRoot, cfg)` on open. The modal inherits Plan-01's localStorage draft + two-step confirm + Enter-guard for free.
- **Read-only on-air readout (D-07/D-07a):** replaced the inline form with a `.sidebar-block` card showing discipline + total, fed by a new `pollOverlayJson` (safe-coast try/catch, `textContent` only — no `innerHTML`, T-17-06 XSS-inert), wired into `startPolling`/`stopPolling` as a named interval handle on the existing 1s cadence (T-17-08 accepted), and seeded on cold start. After a 2xx publish from the modal the readout updates on the next poll tick (it polls the authoritative `/overlay-json`).
- **Kept the load-bearing wiring:** the `post(url, data)` helper and the `.run-btn` start/stop binding stay (reused by the run controls).

## Task Commits

1. **Task 1: Retire the legacy post_score branch + update the import-smoke gate** - `10ba4f0` (refactor)
2. **Task 2: Inject score_cfg + native dialog hosting the shared partial** - `1c2daa8` (feat)
3. **Task 3: Retire console #form-score + on-air readout polling /overlay-json** - `1686fed` (feat)

## Files Modified
- `src/segugio/ui/app.py` - Deleted `_is_legacy_score_post` + its `post_score` branch + the unreferenced `_NON_SCORE_KEYS`/`_STRUCTURED_KEYS`; updated the get_json fall-through comment to the single-path reality; `index()` now renders `console.html` with `score_cfg=_score_cfg`.
- `src/segugio/ui/templates/console.html` - Added the native `<dialog>` including the shared partial + its dark-token CSS; added `openScoreDialog()` (showModal + mount-on-open) and the open-button binding; replaced the legacy `#form-score` card with the read-only on-air readout + modal-open button; removed the `showFields()` toggle + the `#form-score` submit listener; added `pollOverlayJson` + the `overlayTimer` named handle wired into start/stop + cold start.
- `tests/test_imports.py` - POST /score smoke now posts the authoritative structured JSON disc_tf body (one zone-2 throw) asserting 204/200 — the crash-isolation gate stays green.
- `tests/test_ui_score.py` - The three per-discipline POSTs rewritten to authoritative structured JSON (server-recomputed totals); `test_index_serves_italian_console` updated to the modal-host reality (one root/cfg, no `{% include %}` literal, legacy form gone).
- `tests/test_ui_score_authoritative.py` - `test_legacy_flat_keys_still_round_trip` → `test_legacy_flat_keys_now_rejected` (the retired path now 400s + writes nothing).
- `tests/test_ui_overlay_json.py` - `test_overlay_json_fields_verbatim` rewritten to assert the SERVER-computed fields round-trip verbatim; the two gen-bump tests post the authoritative structured body.
- `tests/test_overlay_fallback_gate.py` - The single-writer persistence gate posts the authoritative structured body and compares overlay.txt to the renderer for the SERVER-computed doc.
- `tests/test_ui_scv_unification.py` - `test_surviving_console_wiring_intact` updated: `post()` + run buttons survive; `showFields`/`#form-score` are gone; the modal-open button is present.
- `tests/test_ui_tablet_layout.py` - `test_index_still_serves_italian_console` + `test_touch_action_and_targets` updated to the on-air-readout + modal reality (legacy flat field labels no longer in static HTML).
- `tests/test_ui_explainability.py` - `test_scv01_score_inputs_touch_contract` re-pointed to the served `/static/score-entry.js` (the inputs are now built by the component, not in console HTML).

## Decisions Made
- The on-air readout total reads `fields.totale` and falls back to `fields.faults` (count_up agility has no `totale` — it carries `faults`); on absent/torn it leaves the last value ("a poll error never breaks the page").
- The console modal mounts on open while score-entry.js still auto-mounts on DOMContentLoaded; `mount()` clears+rebuilds the single `#score-entry-root`, so the on-open mount cleanly re-runs and restores the localStorage draft each open.
- Stale tests asserting the retired legacy path / inline form were updated (in-scope — they directly depend on the D-11 change surface, not pre-existing unrelated failures).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated 8 test files broken by the intentional legacy retirement**
- **Found during:** Tasks 1 and 3
- **Issue:** The plan listed only `tests/test_imports.py` in `files_modified`, but retiring the legacy flat-key path (D-11, the plan's core change) broke tests across 7 other files that POSTed the legacy `prese`/`zona`/`totale`/`points` urlencoded shape or asserted the legacy inline `#form-score` markup. All were confirmed PASSING on the pre-plan baseline and breaking solely because of the legacy retirement.
- **Fix:** Updated each broken test to the authoritative-JSON + modal reality (structured bodies with server-recomputed totals; readout/modal assertions instead of inline-form assertions). The retired-path test was rewritten to assert the new 400-on-flat-shape behavior.
- **Files modified:** test_ui_score.py, test_ui_score_authoritative.py, test_ui_overlay_json.py, test_overlay_fallback_gate.py, test_ui_scv_unification.py, test_ui_tablet_layout.py, test_ui_explainability.py
- **Commits:** 10ba4f0 (Task 1 set), 1686fed (Task 3 set)

**2. [Rule 3 - Blocking] Jinja-token-in-HTML-comment TemplateSyntaxError**
- **Found during:** Task 2
- **Issue:** An HTML comment in console.html literally contained a Jinja `{% include %}` token, which Jinja parsed and raised `TemplateSyntaxError` (the same gotcha logged in Plan 01).
- **Fix:** Rephrased the comment to avoid Jinja statement-block tokens. Caught and fixed before the Task 2 commit.

## Out-of-Scope (logged, NOT fixed)
- `tests/test_ui_tablet_layout.py::test_touch_action_and_targets` still fails on `assert 'class="layout"' in html` — a Phase-9-era layout rename staleness that failed IDENTICALLY on the pre-17-02 baseline. Only the `id="form-score"` assertion (this plan's change surface) was updated; the `class="layout"` staleness is logged to `deferred-items.md`.
- Two other pre-existing failures confirmed identical on baseline and unrelated to this plan's files: `test_ui_explainability::test_leaderboard_renders_sorted` (node ESM mirror harness) and `test_ui_scv_unification::test_console_embeds_overlay_iframe` (iframe embed).

## Test Status
- `tests/test_imports.py` — 26 passed (crash-isolation gate green; create_app builds + /overlay-json + the authoritative /score resolve with the heavy stack + numpy absent).
- `tests/test_ui_score.py`, `tests/test_ui_score_authoritative.py`, `tests/test_ui_overlay_json.py`, `tests/test_overlay_fallback_gate.py`, `tests/test_ui_score_entry.py`, `tests/test_ui_score_calc_js.py`, `tests/test_score_display_only.py`, `tests/test_overlay_html_sink_gate.py` — all green.
- `tests/test_ui_scv_unification.py::test_surviving_console_wiring_intact`, `tests/test_ui_tablet_layout.py::test_index_still_serves_italian_console`, `tests/test_ui_explainability.py::test_scv01_score_inputs_touch_contract` — updated and green.
- 3 pre-existing failures remain (`test_touch_action_and_targets` class="layout" staleness, `test_leaderboard_renders_sorted` node ESM, `test_console_embeds_overlay_iframe`) — all reproduce identically on the pre-plan baseline; logged to deferred-items.md.

## Threat Surface
- T-17-05 (validation not weakened): the authoritative path is byte-identical and is now the SOLE path; the import-smoke + a structured-JSON POST re-prove it resolves. No regression.
- T-17-06 (readout XSS): the on-air readout writes via `textContent` only — a crafted `fields` value renders as inert text. No `innerHTML` in the new readout/poll code (verified by grep).
- T-17-07 (info disclosure): `score_cfg` is the SAME public scoring-profile blob already served on `/score-entry`; the readout reads only public `/overlay-json`. No new privileged surface.
- T-17-08 (DoS): the readout reuses the existing console poll cadence (named-interval, idempotent start/stop); no new worker thread.
- No new dependencies, no install task — no package-legitimacy gate needed.

## User Setup Required
None - no external service configuration required.

## Self-Check: PASSED

All modified files exist on disk and all task commits (`10ba4f0`, `1c2daa8`, `1686fed`) are present in git history (verified below).
