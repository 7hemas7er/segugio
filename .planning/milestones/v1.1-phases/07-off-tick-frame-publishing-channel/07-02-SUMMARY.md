---
phase: 07-off-tick-frame-publishing-channel
plan: 02
subsystem: testing
tags: [crash-isolation, import-test, console, flask, ui, regression-gate]

# Dependency graph
requires:
  - phase: 05-orchestrator-obs-ndi-score-ui
    provides: "Flask console create_app(channel_dir) + /status reverse-channel route + segugio.opcomm atomic-file channel"
provides:
  - "HARD GATE 2: extended test_app_imports_nothing_heavy that forces ultralytics/torch/numpy/cv2/cyndilib/obsws_python absent and proves segugio.ui.app IMPORTS and STARTS (create_app + GET /status → 200)"
  - "A regression guard locking the console's clean Flask + segugio.opcomm-only import surface before Phase 8 widens it"
affects: [phase-08-console-serving-multiview, phase-09-explainability-tablet-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Heavy-absent START-check: under monkeypatch.setitem(sys.modules, heavy, None) for the full orchestrator stack, assert the Flask app both imports AND serves a request (not import-only)"

key-files:
  created: []
  modified:
    - "tests/test_ui_score.py"

key-decisions:
  - "Used GET /status as the start-check route — it read_status-safe-defaults to SAFE on the absent file (RBT-04), so it returns 200 with no feed/file present; no /status file fixture needed"
  - "numpy added to the heavy-block tuple so the gate cannot pass merely because numpy is installed (Pitfall 2 / false-green closed)"

patterns-established:
  - "Crash-isolation gate locks the surface as a regression guard BEFORE the next phase widens it (Phase 8 GET /preview)"

requirements-completed: [PRV-03]

# Metrics
duration: 4min
completed: 2026-06-13
---

# Phase 7 Plan 02: HARD GATE 2 — Console Crash-Isolation Start-Check Summary

**Extended `test_app_imports_nothing_heavy` to force the full orchestrator stack (ultralytics/torch/numpy/cv2/cyndilib/obsws_python) absent and prove the Flask console both IMPORTS and STARTS — `create_app(tmp)` + `GET /status` returns 200 — locking the clean Flask + segugio.opcomm import surface as a regression gate before Phase 8.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-13T11:24:53Z
- **Completed:** 2026-06-13
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `"numpy"` to the heavy-block tuple in `test_app_imports_nothing_heavy` — the gate previously blocked cv2/torch/ultralytics/cyndilib/obsws_python but NOT numpy, so it could have passed merely because numpy happens to be installed (RESEARCH / Pitfall 2, false-green closed).
- Promoted the gate from import-only to a START-check (D-09 gate 2 = "console STARTS"): under the heavy-absent block it now calls `create_app(str(tmp_path))` → builds a real Flask app → `client.get("/status")` and asserts `status_code == 200`. A request completing here proves the console started end-to-end with the entire heavy stack absent.
- Locked the console's clean `Flask + segugio.opcomm`-only import surface as a regression guard BEFORE Phase 8 adds the `GET /preview` routes (mitigates T-07-02-01 — console acquiring a heavy import as the channel lands, a high-severity RBT-04 never-crash regression).
- `src/segugio/ui/app.py` left INTENTIONALLY unmodified — the gate locks the existing surface, it does not change it.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend test_app_imports_nothing_heavy — add numpy + a create_app start-check (HARD GATE 2)** - `ed67990` (test)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP)

## Files Created/Modified
- `tests/test_ui_score.py` - Extended `test_app_imports_nothing_heavy`: added `numpy` to the forced-absent heavy tuple, added a `create_app(tmp)` + `GET /status` → 200 start-check under the heavy-absent block, and updated the docstring to record it now proves the console STARTS (not merely imports) and blocks numpy.

## Decisions Made
- **`/status` is the start-check route:** it is the D-11 reverse-channel poll route and `read_status` safe-defaults to SAFE on the absent file (RBT-04 boundary), so a `GET /status` returns 200 with no opcomm file present — proving the app started without needing any feed/file fixture. Asserted `== 200` (the real route), not a permissive `in (200, 404)`.
- **`tmp_path` added to the test signature:** a pytest builtin fixture, used as the `channel_dir` for `create_app` so the start-check has a clean writable opcomm dir.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The targeted test passed first run; the UI + import-boundary regression suite (`tests/test_ui_score.py tests/test_imports.py`) is fully green at 29 passed, zero regression.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HARD GATE 2 is in place and green: the console crash-isolation contract (Flask + segugio.opcomm only, no heavy stack, app STARTS) is now a regression guard. Phase 8 can add the `GET /preview` routes with confidence that any accidental heavy import (cv2/numpy/torch/…) into `ui/app.py` will fail this gate.
- Pairs with the Phase 7 RBT-05 latency HARD gate (the other D-09 gate, owned by the channel-internals plans 01/03/04) to complete Phase 7's two-gate crash-isolation + latency proof.

## Self-Check: PASSED

- FOUND: tests/test_ui_score.py
- FOUND: .planning/phases/07-off-tick-frame-publishing-channel/07-02-SUMMARY.md
- FOUND: commit ed67990

---
*Phase: 07-off-tick-frame-publishing-channel*
*Completed: 2026-06-13*
