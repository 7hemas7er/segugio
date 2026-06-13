---
phase: 08-console-serving-live-multiview-safety-hardening
plan: 01
subsystem: ui
tags: [flask, console, multiview, send_file, waitress, crash-isolation, path-traversal, concurrency]

# Dependency graph
requires:
  - phase: 05-operator-console-orchestrator
    provides: "create_app Flask factory, GET /status route, _path helper, atomic-file channel, read_status"
  - phase: 07-preview-publishing-channel
    provides: "read_preview/PreviewDoc sidecar, cam_<id>.jpg ephemeral JPEG publisher, <channel_dir>/preview/ layout"
provides:
  - "GET /preview/<cam>.jpg — whitelisted send_file route (fixed cam_{id}.jpg path, no-store, 404 on unknown/traversal/not-yet-written)"
  - "GET /preview — thin read_preview sidecar JSON wrapper (gen/tick/auto_candidate/cams)"
  - "create_app(channel_dir, cam_ids=()) — cam-id whitelist param (default keeps single-arg callers green)"
  - "threaded=True dev-server fallback + optional waitress entrypoint (UXT-02/D-08 control-plane safety)"
  - "CSS-Grid multiview console ON TOP with flicker-free Image() refresh + LIVE/MORTO tile marking"
  - "segugio.ui added to the crash-isolation import guard (resolves with torch/cv2/numpy absent)"
affects: [08-02, 08-03, phase-9-why-channel, console]

# Tech tracking
tech-stack:
  added: ["waitress==3.0.2 (optional [console] extra only)"]
  patterns:
    - "Whitelist-as-path-traversal-mitigation: <cam> validated against cam_ids, mapped to a FIXED cam_{id}.jpg prefix — URL segment never used as a raw path"
    - "Flicker-free tile refresh via off-DOM new Image() preload + onload swap, ?t=<gen> cache-bust (URL changes only on a genuine new frame)"
    - "Belt-and-suspenders MORTO: status.alive[cam]==false OR whole-channel gen-staleness"

key-files:
  created:
    - "tests/test_preview_serving.py"
    - "tests/test_preview_concurrency.py"
  modified:
    - "src/segugio/ui/app.py"
    - "src/segugio/ui/templates/console.html"
    - "pyproject.toml"
    - "tests/conftest.py"
    - "tests/test_imports.py"

key-decisions:
  - "numpy NOT added to the global HEAVY_MODULES (it is a hard runtime dep for synth/framing); the console must-resolve-with-numpy-absent assertion was implemented as a dedicated console guard test forcing numpy+cv2+heavy stack absent — the plan's literal instruction would have broken unrelated PHASE1_SURFACE modules (Rule 1)"
  - "Entrypoint resolves cam_ids from SEGUGIO_CAM_IDS env, else lazily from SEGUGIO_CONFIG, else the four default rig ids — config import kept inside __main__ to preserve the lazy boundary"

patterns-established:
  - "Pattern 1: whitelist + fixed filename prefix = path-traversal mitigation for any URL-segment-keyed file route"
  - "Pattern 2: real ephemeral-port threaded server (werkzeug make_server, port=0) on a background thread for WSGI-concurrency proofs the test_client cannot exercise"

requirements-completed: [MVW-01, MVW-02, MVW-03, UXT-02]

# Metrics
duration: 7min
completed: 2026-06-13
---

# Phase 8 Plan 01: Console Serving, Live Multiview & Safety Hardening Summary

**Crash-isolated Flask console now SERVES the Phase-7 channel — a whitelisted `send_file` JPEG route + a `read_preview` sidecar JSON route, a responsive CSS-Grid multiview with flicker-free `Image()` refresh and LIVE/MORTO marking, and a `threaded=True`/Waitress entrypoint so a preview GET can never block the `/command` override.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-06-13T15:06:27Z
- **Completed:** 2026-06-13T15:13:43Z
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments
- `GET /preview/<cam>.jpg`: whitelisted `send_file` route — unknown id, `../status` traversal (raw + `..%2f` encoded), and not-yet-written all 404; serves the exact bytes at `preview/cam_<id>.jpg` with `Cache-Control: no-store`.
- `GET /preview`: thin never-raise `read_preview` wrapper returning `{gen, tick, auto_candidate, cams}`.
- `create_app(channel_dir, cam_ids=())` whitelist param; default keeps the existing single-arg `test_ui_run.py` caller green.
- `__main__` entrypoint: optional `from waitress import serve` (inside the block) with an `app.run(host="0.0.0.0", port=8080, threaded=True)` fallback — the hard UXT-02/D-08 control-plane safety control. Concurrency proven by a real ephemeral-port threaded server: a `/command` override POST returns 204 in well under 1 s while 8 concurrent preview GETs are in flight.
- Responsive CSS-Grid multiview ON TOP (`repeat(auto-fit, minmax(240px,1fr))`), flicker-free `new Image()` preload-swap with `?t=<gen>` cache-bust, on-air tile marked LIVE (red border + badge + "ON AIR" banner) and dead/stale tiles MORTO (from `status.alive` OR gen-staleness). Text override buttons preserved; tiles strictly display-only.
- Crash-isolation contract preserved: `segugio.ui` added to `PHASE1_SURFACE`; a dedicated guard builds `create_app` with torch/cv2/numpy/cyndilib/obsws forced absent.

## Task Commits

Each task was committed atomically:

1. **Task 1: Test scaffold (preview_channel fixture + serving/concurrency tests + crash-isolation guard)** - `5208f86` (test — TDD RED)
2. **Task 2: Preview serving routes + threaded entrypoint + waitress optional extra** - `ac597f7` (feat — TDD GREEN)
3. **Task 3: Multiview grid + flicker-free refresh + LIVE/MORTO marking** - `72ca65c` (feat)

**Plan metadata:** see final docs commit.

## Files Created/Modified
- `tests/test_preview_serving.py` (created) - MVW-01/02/03 serve / whitelist / live_contract / freshness tests.
- `tests/test_preview_concurrency.py` (created) - UXT-02 override-not-blocked proof on a real ephemeral-port threaded server.
- `src/segugio/ui/app.py` (modified) - two new routes, `cam_ids` whitelist param, `read_preview` import, preview constants, threaded/waitress entrypoint.
- `src/segugio/ui/templates/console.html` (modified) - multiview grid + CSS + preview poll / flicker-free refresh / LIVE-MORTO marking JS.
- `pyproject.toml` (modified) - `[project.optional-dependencies].console = ["waitress==3.0.2"]`.
- `tests/conftest.py` (modified) - `preview_channel` fixture (preview/ sub-dir + `cam_<id>.jpg` + `preview.json`).
- `tests/test_imports.py` (modified) - `segugio.ui` in `PHASE1_SURFACE` + dedicated console guard with numpy/cv2 forced absent.

## Decisions Made
- **numpy handling in the import guard:** The plan said to add `numpy` to `HEAVY_MODULES`, but that list is applied to ALL `PHASE1_SURFACE` modules — and `segugio.synth`/`segugio.framing` legitimately import numpy at module top (numpy is a hard runtime dep in `pyproject.dependencies`, not a lazy/heavy one). Forcing numpy globally absent broke 8 unrelated surface tests. Implemented the actual Pitfall-5 intent (the *console* must resolve with numpy absent) as a dedicated `test_console_resolves_with_heavy_stack_and_numpy_absent` guard that forces numpy+cv2+the heavy stack absent and imports only `segugio.ui` + builds `create_app`. Tracked below as a Rule 1 fix.
- **Entrypoint cam_ids resolution:** `SEGUGIO_CAM_IDS` (comma list) → else lazy `load_config(SEGUGIO_CONFIG)` → else the four default rig ids. The config import stays inside `if __name__ == "__main__"` (`pragma: no cover`) to keep the module top opcomm-only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the numpy crash-isolation assertion to not break unrelated modules**
- **Found during:** Task 1 (test scaffold)
- **Issue:** The plan instructed adding `numpy` to `HEAVY_MODULES`. That list is parametrized across the entire `PHASE1_SURFACE`, so forcing numpy absent failed `segugio.config/synth/framing/decision/tracking/orchestrator/__main__` imports — numpy is a hard runtime dependency, not a lazy/heavy one. The plan's intent (Pitfall 5) is specifically that the *console* must resolve with numpy absent.
- **Fix:** Left `HEAVY_MODULES` unchanged; added a `CONSOLE_HEAVY_MODULES = HEAVY_MODULES + ["numpy", "cv2"]` set and a dedicated `test_console_resolves_with_heavy_stack_and_numpy_absent` that forces those absent and asserts `import segugio.ui` + `create_app(...)` resolve.
- **Files modified:** `tests/test_imports.py`
- **Verification:** `pytest tests/test_imports.py -q` green (the new console guard passes; the existing surface tests stay green).
- **Committed in:** `5208f86` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** The fix preserves the plan's actual goal (console resolves with numpy absent) while not regressing the legitimately-numpy-dependent Phase-1 surface. No scope creep.

## Issues Encountered
- Full-suite run shows 4 pre-existing failures in `tests/test_fan_out_batched.py` (`ModuleNotFoundError: No module named 'ultralytics'`) — the heavy GPU/tracking stack is not installed in the active CPU-only py3.14 venv (it lives in `venv312/` per project memory). These touch none of the 08-01 files and fail identically on the baseline commit `4997e51`. Logged to `deferred-items.md`; out of scope per the executor scope boundary.

## User Setup Required
None - no external service configuration required. The `console` extra (`pip install segugio[console]`) is optional; the `threaded=True` dev-server fallback works without it.

## Next Phase Readiness
- 08-02 (preview bitrate cap config validator) and 08-03 (`docs/security.md` threat re-eval) can proceed; the `T-08-03` "live video behind 0.0.0.0" exposure noted here is the input to 08-03's D-09 write-up.
- The `/preview` `cams` payload carries the full D-07 fields (score/box/track_id/energy) but Phase 8 renders only the tile set + LIVE/MORTO — Phase 9 (WHY-01 / MVW-04 clickable tiles) consumes the rest.

## TDD Gate Compliance
RED gate `test(08-01)` `5208f86` precedes GREEN gate `feat(08-01)` `ac597f7`. Tasks 1+2 followed the TDD cycle; Task 3 (template, `type="auto"` non-TDD) verified via a marker check + a render+placement assertion.

## Self-Check: PASSED
- All created/modified files exist on disk.
- All three task commits (`5208f86`, `ac597f7`, `72ca65c`) present in git history.

---
*Phase: 08-console-serving-live-multiview-safety-hardening*
*Completed: 2026-06-13*
