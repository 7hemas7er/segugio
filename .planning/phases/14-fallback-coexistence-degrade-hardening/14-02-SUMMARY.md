---
phase: 14-fallback-coexistence-degrade-hardening
plan: 02
subsystem: testing
tags: [pytest, werkzeug, flask, jinja, xss, concurrency, rbt-06]

# Dependency graph
requires:
  - phase: 11-shared-graphical-renderer
    provides: "overlay-render.js textContent sink + overlay.html Jinja branding sinks"
  - phase: 08-console-serving-multiview
    provides: "threaded=True WSGI server + the UXT-02 live_server poll-storm harness"
  - phase: 05-wiring
    provides: "POST /score atomic_write_text(overlay.txt) single-writer + opcomm channel"
provides:
  - "SC#1 named gate: overlay.txt on-disk persistence after a simulated console death (single-writer coexistence)"
  - "SC#3 named gate: /overlay-json poll storm never starves POST /command < 1.0s (real threaded server)"
  - "SC#4 named gate: textContent-not-innerHTML JS sink + Jinja autoescape of crafted event_name"
  - "14-HUMAN-UAT.md on-rig physical-scenario checklist (RBT-06, deferred, non-blocking)"
affects: [14-verify-work, rbt-06-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-criterion named gate: one test file per RBT-06 success criterion so a single-criterion regression cannot pass silently (D-03)"
    - "Real threaded make_server harness (NOT test_client) for any WSGI-concurrency proof — test_client yields a false green"

key-files:
  created:
    - tests/test_overlay_fallback_gate.py
    - tests/test_overlay_poll_storm.py
    - tests/test_overlay_html_sink_gate.py
    - .planning/phases/14-fallback-coexistence-degrade-hardening/14-HUMAN-UAT.md
  modified: []

key-decisions:
  - "SC#1 simulated death = drop the app/client with no second writer (no orchestrator import, no direct file write) — the single-writer property is what is under test"
  - "SC#3 reuses the test_preview_concurrency.py live_server fixture VERBATIM, retargeting the 8 concurrent GETs to /overlay-json (Pitfall 2: test_client does not exercise WSGI threading)"
  - "SC#4 Jinja half crafts event_name='<script>x</script>' through the create_app overlay_cfg arg and asserts the served HTML contains &lt;script&gt; and not the raw tag"

patterns-established:
  - "Per-criterion named regression gate (D-03): even where the underlying logic already passes, each SC gets its own named test so a regression names itself"

requirements-completed: [RBT-06]

# Metrics
duration: 8min
completed: 2026-06-20
---

# Phase 14 Plan 02: RBT-06 Per-Criterion Named Gates + HUMAN-UAT Summary

**Three new RBT-06 named gate tests (SC#1 overlay.txt single-writer persistence, SC#3 /overlay-json poll-storm vs /command, SC#4 textContent + Jinja-autoescape sink) plus the deferred on-rig 14-HUMAN-UAT checklist.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-06-20
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- SC#1 fallback gate: POST /score writes overlay.txt; a simulated console death (no second writer) leaves the last rendered score on disk byte-for-byte — single-writer coexistence proven via the Flask test_client.
- SC#3 poll-storm gate: copied the `live_server` (`make_server(..., threaded=True)`) fixture + `_get`/`_post_command` helpers from `test_preview_concurrency.py` verbatim, retargeted the 8 concurrent GETs to `/overlay-json`, and asserted `POST /command` returns 204 in < 1.0s AND that `command.json` actually carries `force_cam="cam_long"`.
- SC#4 HTML-sink gate: pure-source assertion that `overlay-render.js` uses `textContent` and never any `innerHTML` variant, plus a Jinja-autoescape regression — a crafted `event_name="<script>x</script>"` renders ESCAPED (`&lt;script&gt;`) and not raw on `GET /overlay`.
- 14-HUMAN-UAT.md authored: three physical scenarios (console-death auto-hide within DEAD_MS, LAN-drop timer-stop + gen re-anchor with no phantom jump, overlay.txt last-score airing) + the D-06 simplified `Score Text` reveal + the D-08 exact-`ndi_source`-name gotcha, explicitly marked non-blocking (D-02).

## Task Commits

1. **Task 1: SC#1 fallback gate + SC#3 poll-storm gate** - `15bf0cb` (test)
2. **Task 2: SC#4 HTML-sink gate + 14-HUMAN-UAT.md** - `2df6113` (test)

## Files Created/Modified
- `tests/test_overlay_fallback_gate.py` - SC#1 overlay.txt on-disk persistence after a simulated death (single-writer proof, Flask test_client, no orchestrator import).
- `tests/test_overlay_poll_storm.py` - SC#3 /overlay-json storm vs POST /command < 1.0s via the real threaded werkzeug server (copied live_server harness).
- `tests/test_overlay_html_sink_gate.py` - SC#4 textContent-not-innerHTML JS sink assert + Jinja autoescape regression on /overlay.
- `.planning/phases/14-fallback-coexistence-degrade-hardening/14-HUMAN-UAT.md` - on-rig physical-scenario checklist (RBT-06), three scenarios + D-06 reveal + D-08 note, non-blocking (D-02).

## Decisions Made
- The SC#1 "simulated console death" is modeled by dropping the app/client and re-reading overlay.txt — deliberately adding NO second writer (no orchestrator import, no direct file write), because the single-writer property is exactly what is under test.
- SC#3 uses the real `make_server(threaded=True)` harness, not `test_client`, per Pitfall 2 — `test_client` does not exercise WSGI threading and would yield a false green.
- The Jinja autoescape proof threads the crafted `event_name` through the existing `create_app(..., overlay_cfg={"event_name": ...})` arg (the route's static-branding render kwarg), matching how production resolves branding.

## Deviations from Plan
None - plan executed exactly as written. All three gates and the HUMAN-UAT checklist were authored per the task actions; each gate reuses an existing in-repo harness verbatim.

## Issues Encountered
None. The line-ending CRLF warnings on commit are benign (git autocrlf normalization).

## Threat Surface
No new security-relevant surface introduced — all four artifacts are tests/docs. The three gates ASSERT existing mitigations (T-14-xss textContent+autoescape, T-14-dos threaded server, T-14-fallback single-writer) and use Flask test_client / werkzeug only (T-14-iso: RBT-07 import surface stays clean; `test_imports.py` green per task).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RBT-06 automation half is now a complete, per-criterion named gate set (SC#1/SC#2 from plan 14-01's degrade gate, SC#1 fallback / SC#3 / SC#4 from this plan). Ready for `/gsd-verify-work`.
- 14-HUMAN-UAT.md is authored and ready to run on the rig — it is a deferred carry-forward and does NOT block Phase 14 completion (D-02).
- No regressions: the copied-from harnesses (`test_preview_concurrency.py`, `test_ui_overlay_render.py`) and `test_imports.py` stay green.

## Self-Check: PASSED
- FOUND: tests/test_overlay_fallback_gate.py
- FOUND: tests/test_overlay_poll_storm.py
- FOUND: tests/test_overlay_html_sink_gate.py
- FOUND: .planning/phases/14-fallback-coexistence-degrade-hardening/14-HUMAN-UAT.md
- FOUND commit: 15bf0cb
- FOUND commit: 2df6113

---
*Phase: 14-fallback-coexistence-degrade-hardening*
*Completed: 2026-06-20*
