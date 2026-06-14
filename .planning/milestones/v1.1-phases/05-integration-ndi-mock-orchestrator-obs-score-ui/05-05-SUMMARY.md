---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 05
subsystem: ui
tags: [flask, operator-console, atomic-file-channel, display-only, lazy-import, italian, tdd]

# Dependency graph
requires:
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    plan: 01
    provides: opcomm atomic channel (write_score/write_runstate/write_command/read_status + atomic_write_text) + frozen ScoreDoc/RunState/OperatorCommand/DirectorStatus/Discipline; file_channel test fixture; Flask==3.1.3 dep
  - phase: 03-decision-engine
    provides: OverrideCmd force/release mutual-exclusion contract OperatorCommand mirrors (D-10)
provides:
  - segugio.ui.score_render.render_overlay_text — pure stdlib per-discipline Italian overlay renderer (display-only, SCR-04)
  - segugio.ui.app.create_app(channel_dir) — Flask operator console factory; POST /score|/run|/command (atomic writes) + GET / page + GET /status poll
  - src/segugio/ui/templates/console.html — one Italian operator console page (selector + 3 field sets + Avvia/Ferma + Forza/Rilascia + Stato live poll)
affects: [05-06-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Flask app FACTORY (create_app(channel_dir)) with Flask imported INSIDE the factory → import segugio.ui stays Flask-free (lazy boundary)"
    - "POST writes route through the opcomm atomic channel only (D-03 files-only IPC); fixed server-side paths (no operator-supplied path → T-05-05-01)"
    - "Display-only renderer: operator values formatted VERBATIM, never computed (SCR-04), sanitized + length-bounded against overlay injection (T-05-05-02)"
    - "Force-XOR-release enforced at the record boundary (OperatorCommand.__post_init__) → contradictory POST returns 400, never written (T-05-05-03)"
    - "AST source-guard test asserts no adjudication/judge/compute function exists under segugio.ui — SCR-04 as an automated gate"

key-files:
  created:
    - src/segugio/ui/__init__.py
    - src/segugio/ui/score_render.py
    - src/segugio/ui/app.py
    - src/segugio/ui/templates/console.html
  modified:
    - tests/test_score_display_only.py
    - tests/test_ui_score.py
    - tests/test_ui_run.py

key-decisions:
  - "create_app(channel_dir) factory (not a module-level app) so tests inject a tmp_path dir via the Flask test client and prod injects the real dir"
  - "Score written as BOTH score.json (structured, for the UI/round-trip) AND overlay.txt (rendered Italian line, for the OBS read-from-file source) — RESEARCH Q2"
  - "POST /run maps action=start→just_started edge, action=stop→just_stopped(+stopped) SAFE-park edge (D-09); RunState validates the action set"
  - "Discipline whitelisted to the closed Enum at the POST boundary → unknown → 400 (T-05-05-01); overlay values stripped of control chars + capped at 64 (T-05-05-02)"
  - "SCR-04 enforced by an AST guard test (no scoring/judge/compute_* function under segugio.ui) + a verbatim-totale test (wrong operator total shown as-is, never recomputed)"

requirements-completed: [SCR-02, SCR-03, SCR-04]

# Metrics
duration: 9min
completed: 2026-06-11
---

# Phase 5 Plan 05: Operator Console (Flask) Summary

**The project's only human surface: a crash-isolated separate-process Flask console serving one Italian page (discipline selector + 3 per-discipline field sets, run start/stop, Forza/Rilascia override, live status poll) whose every POST writes an opcomm atomic file and which displays operator-entered scores with zero adjudication (SCR-04 enforced by an AST gate).**

## Performance

- **Duration:** ~9 min
- **Tasks:** 3 (Tasks 1 & 2 TDD: RED→GREEN)
- **Files:** 4 src created, 3 test files flipped from xfail stubs to real assertions

## Accomplishments

- `segugio.ui.score_render.render_overlay_text` — a PURE, stdlib-only renderer mapping a `ScoreDoc` to the Italian OBS overlay line per discipline (T&F `Prese/Zona/Totale`; freestyle `nome + Timer`; agility `Tempo / SCT  Faults`). It formats operator-entered values **verbatim** — no arithmetic, no derivation, no judging (SCR-04).
- `segugio.ui.app.create_app(channel_dir)` — the Flask operator console factory. `POST /score` writes `score.json` (structured) AND `overlay.txt` (rendered) atomically; `POST /run` writes the D-09 start/stop edge flags; `POST /command` writes a force-XOR-release `OperatorCommand` (contradictory → 400); `GET /status` serves the `DirectorStatus` JSON the panel polls (D-11). Imports ONLY Flask + `segugio.opcomm`, with Flask imported inside the factory so `import segugio.ui` stays Flask-free (RBT-04 crash-isolation).
- `console.html` — one Italian page carrying D-04's four concerns: a discipline selector that toggles the 3 field sets, Avvia/Ferma run buttons, "Forza CAM Wide/Long/Low/Handler" + "Rilascia (auto)" override buttons (each posts EITHER a force OR a release, never both — D-10), and a "Stato live" panel that polls `/status` every second and renders the live camera + reason + per-feed alive/dead (D-11). Vanilla fetch, no framework.
- SCR-04 made an **automated gate**, not a claim: an AST guard test walks every `segugio.ui` module and asserts no `adjudicate`/`judge`/`compute_*`/`tally`/`score_dog` function exists; a second test posts `prese=5, zona=3, totale=999` and asserts the line shows `999` (operator value) and never `8` (the would-be computed sum).

## Task Commits

1. **Task 1: Pure display-only overlay renderer** (TDD) — `b60e0f3` (test RED) → `9b85ad7` (feat GREEN)
2. **Task 2: Flask console app factory** (TDD) — `7fa0a76` (test RED) → `ee624cc` (feat GREEN)
3. **Task 3: Italian console page** — `e48103d` (feat)

## Files Created/Modified

- `src/segugio/ui/__init__.py` — light package doc + `render_overlay_text` re-export (NO Flask at top, lazy boundary)
- `src/segugio/ui/score_render.py` — pure per-discipline Italian overlay renderer; `_clean` sanitizes/bounds values (T-05-05-02); stdlib-only
- `src/segugio/ui/app.py` — `create_app(channel_dir)` factory; Flask imported in-body; fixed server-side file paths; discipline/command boundary validation
- `src/segugio/ui/templates/console.html` — Italian operator console (selector + 3 field sets + run + override + live-status poll)
- `tests/test_score_display_only.py` — flipped: verbatim per-discipline rendering, the never-recompute-totale SCR-04 gate, the AST no-adjudication guard, import-light smoke
- `tests/test_ui_score.py` — flipped: POST /score per discipline → score.json + overlay.txt content; unknown discipline → 400; GET / page-content assertion; import-nothing-heavy
- `tests/test_ui_run.py` — flipped: POST /run start→just_started, stop→SAFE-park; POST /command force/release/contradictory→400; GET /status poll + default

## Decisions Made

- **App factory over module-level `app`** — `create_app(channel_dir)` lets the Flask test client inject a tmp_path opcomm dir and the production entrypoint inject the real dir; the factory also localizes the Flask import (keeps `import segugio.ui` Flask-free).
- **Write BOTH `score.json` and `overlay.txt`** — structured JSON for the UI/round-trip and a rendered plain Italian line for the OBS read-from-file source (RESEARCH Open Question Q2 recommendation; score-file content was Claude's discretion).
- **D-09 edge mapping in the POST handler** — `action=start` sets `just_started`, `action=stop` sets `just_stopped` (and `stopped` is derived). The orchestrator (05-06) consumes these edges to reset locks / park on SAFE.

## Deviations from Plan

None — plan executed exactly as written. The threat-model mitigations (T-05-05-01 path-fixing + discipline whitelist, T-05-05-02 overlay sanitization, T-05-05-03 force-XOR-release 400, T-05-05-05 lazy-import crash-isolation) were implemented as specified; T-05-05-04 (0.0.0.0 bind, no-auth) is the documented accepted decision recorded in `app.py`'s module docstring.

## Authentication Gates

None.

## Known Stubs

None. The three previously-xfail Wave-0 stubs (`test_score_display_only.py`, `test_ui_score.py`, `test_ui_run.py`) were flipped to real passing assertions. No hardcoded UI data, no placeholder rendering — the status panel is wired to the real `/status` opcomm read, and the score fields flow to real atomic file writes.

## Threat Flags

None — no security surface beyond the plan's `<threat_model>` was introduced. The `0.0.0.0` bind is the pre-declared, accepted T-05-05-04 decision (dedicated-WiFi trust boundary), documented in `app.py`.

## Verification

- `python -m pytest tests/test_ui_score.py tests/test_ui_run.py tests/test_score_display_only.py -x` → **21 passed**.
- `python -c "import segugio.ui, segugio.ui.app, segugio.ui.score_render"` → succeeds with cyndilib/obsws/cv2 absent (Flask 3.1.3 present); the import-nothing-heavy test asserts no heavy module leaks into `segugio.ui.app`.
- Full `tests/test_imports.py` + the three UI suites → **41 passed**.
- On-Windows E2E (`python -m segugio.ui.app`, open page, confirm writes + status poll) remains the D-07 manual run — not blocking the headless gate.

## Next Phase Readiness

- 05-06 (orchestrator) can read `runstate.json` (the D-09 just_started/SAFE-park edges), `command.json` (`OperatorCommand.to_override()` → the FSM `OverrideCmd`), and write `status.json` (the panel's `/status` poll source). The console writes exactly the files the orchestrator reads each tick — the operator↔system loop is closed on the UI side.

## Self-Check: PASSED

All four src files (`__init__.py`, `score_render.py`, `app.py`, `templates/console.html`) verified on disk; all five task commits (b60e0f3, 9b85ad7, 7fa0a76, ee624cc, e48103d) confirmed in git log.

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*
