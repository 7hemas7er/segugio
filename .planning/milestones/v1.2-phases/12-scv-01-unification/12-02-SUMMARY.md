---
phase: 12-scv-01-unification
plan: 02
subsystem: ui
tags: [overlay, flask, preview, scv, jinja, css]

# Dependency graph
requires:
  - phase: 12-scv-01-unification
    provides: "the 12-01 RED-by-design test contract (test_ui_overlay_page preview=1 assertions + test_ui_scv_unification /score/preview-removed) this plan flips to PASS"
  - phase: 11-shared-graphical-renderer-overlay-page-branding
    provides: "the FROZEN /static/overlay-render.js + transparent overlay.html host page + get_overlay() route this plan threads the cosmetic preview flag through"
provides:
  - "get_overlay() reads a closed boolean preview=request.args.get(\"preview\")==\"1\" and threads it as a SEPARATE render_template kwarg (no new import — RBT-07 crash-isolation green)"
  - "overlay.html <body> carries {{ 'preview' if preview else '' }} + three preview-only CSS rules (neutral backdrop, force-visible plate, run-edge animation suppressed) keyed on body.preview"
  - "POST /score/preview drift-guard route DELETED (D-05) — one fewer LAN POST surface; its only caller (driftCheck) is removed in 12-03"
affects: [12-03-console-iframe-rewrite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Server-flag -> body-class cosmetic fork: a closed boolean query arg drives a single Jinja body class that keys preview-only CSS; the SAME renderer at the SAME URL differs only by a class -> drift structurally impossible (SCV-02)"
    - "CSS-only force-visible (D-04): opacity:1 + animation:none scoped to the run-edge classes ONLY beats the renderer's animation state without touching any JS — .pulse-once/.is-stale logic untouched"

key-files:
  created: []
  modified:
    - src/segugio/ui/app.py
    - src/segugio/ui/templates/overlay.html

key-decisions:
  - "preview is a SEPARATE render kwarg, NOT folded into overlay_cfg — presentational state vs static branding (mirrors the 'STATIC config does not enter the poll payload' discipline)"
  - "body.preview backdrop is #6b6f76 (a neutral mid-gray between the plate #14161a and white) so the operator can judge plate transparency; class>type specificity beats the html,body transparent !important contract under preview only"
  - "animation:none scoped to .is-entering/.is-exiting ONLY (NOT the whole #lower-third) so .pulse-once still fires as on-air-faithful score-change feedback (Open Question 1 recommendation)"
  - "No preview placeholder content added — the resting 1:00/2:00/0.00 timer + verbatim fields are correct-by-construction; a content fork would defeat SCV-02 (D-04)"

patterns-established:
  - "Pattern: a purely-cosmetic request.args boolean is the crash-isolation-safe way to fork presentation (no heavy import, autoescaped Jinja boolean, never reflected as raw text — T-12-02-01 mitigated)"

requirements-completed: [SCV-02]

# Metrics
duration: 6min
completed: 2026-06-15
---

# Phase 12 Plan 02: Server Overlay Preview Flag & /score/preview Removal Summary

**`GET /overlay?preview=1` now threads a closed-boolean cosmetic flag into a `body.preview` class that keys a neutral backdrop + force-visible lower-third (run-edge animation suppressed, pulse/stale intact), and the callerless `POST /score/preview` drift-guard route is deleted — the console preview and OBS browser-source resolve to ONE renderer at ONE URL.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-15T22:28Z
- **Completed:** 2026-06-15T22:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `get_overlay()` reads `preview = request.args.get("preview") == "1"` (a closed boolean, no new module import) and threads it as a SEPARATE `render_template("overlay.html", preview=preview, **overlay_cfg)` kwarg — `Cache-Control: no-store` + the `make_response` wrapper unchanged; crash-isolation (RBT-07) stays green.
- Deleted the entire `POST /score/preview` route (decorator + body + docstring, D-05) — a net reduction of one LAN POST surface; the only caller (`driftCheck`) is removed in 12-03.
- `overlay.html` `<body>` became `<body class="{{ 'preview' if preview else '' }}">` (bare `/overlay` renders an empty class → byte-identical OBS page) plus three preview-only rules: neutral `#6b6f76` backdrop, `body.preview #lower-third { opacity: 1 }` force-visible, and `animation: none` scoped to `.is-entering`/`.is-exiting` ONLY.
- The renderer (`overlay-render.js`) and `score_render.py` are byte-unchanged (D-04 achieved in CSS / D-06).
- The 12-01 RED-by-design tests flipped to PASS: `tests/test_ui_overlay_page.py` preview=1 assertions and `test_score_preview_route_removed`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread preview flag in get_overlay() and delete post_score_preview()** - `6492357` (feat)
2. **Task 2: Preview body class + cosmetic CSS in overlay.html** - `186e220` (feat)

## Files Created/Modified
- `src/segugio/ui/app.py` (modified) - `get_overlay()` reads the closed boolean preview flag and threads it as a separate render kwarg; the `POST /score/preview` route is removed entirely.
- `src/segugio/ui/templates/overlay.html` (modified) - `<body>` carries the conditional `preview` class; three `body.preview` CSS rules add the neutral backdrop, force-visible plate, and run-edge animation suppression.

## Decisions Made
- `preview` threaded as a SEPARATE kwarg (not inside `overlay_cfg`) — presentational state is kept distinct from static branding, matching the established "static config never enters the live payload" discipline.
- Backdrop `#6b6f76` chosen as a neutral mid-gray between the plate and white so the operator can judge transparency; relied on class>type CSS specificity to override the `html, body { background: transparent !important }` contract under preview only.
- `animation: none` deliberately scoped to the run-edge classes only so `.pulse-once` (score-change pulse) still fires and `.is-stale` degrade logic stays untouched (D-04).
- No preview placeholder content added (the resting timer/fields are correct-by-construction) — a content fork would defeat the SCV-02 single-renderer guarantee.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The full suite (`python -m pytest -q`) shows 4 failures in `tests/test_fan_out_batched.py`, all raising `ModuleNotFoundError: No module named 'ultralytics'` inside `src/segugio/tracking/reid_check.py`. These are pre-existing, environment-driven (CPU-only `venv`; GPU work runs from `venv312/` per project memory), last changed in Phase 06/07, and wholly unrelated to the UI/overlay surface this plan touches. Logged to `.planning/phases/12-scv-01-unification/deferred-items.md` and left unfixed (out of scope per the executor scope boundary). The Phase-12 graded suites (`test_ui_overlay_page`, `test_ui_overlay_render`, `test_imports`, `test_ui_scv_unification`) all exit 0.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 12-03 (console iframe rewrite) is unblocked: it embeds `<iframe src="/overlay?preview=1">`, which now resolves to the live `body.preview` fork; and it deletes the `gsd:scv01-mirror` block + every mirror/drift symbol (`mirrorOverlayText`/`updateScorePreview`/`driftCheck`/...) whose now-callerless server endpoint (`/score/preview`) this plan already removed.
- The 12-01 structural tests that still stay xfail (iframe-embed + mirror-symbols-gone in `test_ui_scv_unification.py`) become the RED target for 12-03; they flip to PASS once the console embed lands.
- No blockers. No new runtime surface, no new dependency, crash-isolation (RBT-07) green.

## Self-Check: PASSED

- Files: FOUND `src/segugio/ui/app.py` (preview flag present, `/score/preview` absent), FOUND `src/segugio/ui/templates/overlay.html` (`body.preview` present).
- Commits: FOUND `6492357`, FOUND `186e220`.

---
*Phase: 12-scv-01-unification*
*Completed: 2026-06-15*
