---
phase: 09-explainability-informed-override-tablet-ux
plan: 01
subsystem: ui-console-backend
tags: [flask, opcomm, score-render, crash-isolation, MVW-05, SCV-01]
requires:
  - "GET /preview route (Phase 8, 08-01)"
  - "PreviewDoc.cuts field + read_preview/write_preview (Phase 7, 07-01)"
  - "render_overlay_text + ScoreDoc + Discipline (Phase 5, score_render.py)"
provides:
  - "GET /preview JSON now carries the `cuts` ring (MVW-05 data source for the 09-04 switch-history strip)"
  - "POST /score/preview pure render endpoint (SCV-01 drift-guard) + Wave-0 byte-parity reference for the 09-03 JS mirror"
affects:
  - "09-03 (JS overlay mirror drift-checks server === client against /score/preview)"
  - "09-04 (switch-history strip consumes /preview cuts)"
tech-stack:
  added: []
  patterns:
    - "Pure (no-IO) Flask render endpoint reusing already-imported symbols to hold the crash-isolation allowlist"
key-files:
  created:
    - tests/test_score_preview.py
  modified:
    - src/segugio/ui/app.py
    - tests/test_preview_serving.py
decisions:
  - "Task 1 (one-key route addition) committed as a single feat with its test rather than split RED/GREEN commits — the change is a single jsonify key, the test and impl are inseparable."
  - "Reused ONLY already-imported symbols (render_overlay_text, Discipline, ScoreDoc, _NON_SCORE_KEYS) for /score/preview — zero new import, crash-isolation gate stays green."
metrics:
  duration: "~6min"
  completed: "2026-06-13"
  tasks: 2
  files: 3
---

# Phase 09 Plan 01: Backend Enablers (cuts ring + pure score-preview) Summary

Landed the two NON-render backend changes Phase 9 needs, isolated in `app.py` + tests: `GET /preview` now exposes the recent-cuts ring (MVW-05), and a new pure `POST /score/preview` returns the exact `render_overlay_text` line WITHOUT writing any channel file (the SCV-01 drift-guard the 09-03 JS mirror checks against). No heavy import added — the console import allowlist (Flask + segugio.opcomm + segugio.ui.score_render) is unchanged.

## What Was Built

### Task 1 — Expose the cuts ring in GET /preview (MVW-05)
- Added `"cuts": [dict(c) for c in doc.cuts]` to the `get_preview` route's `jsonify` dict, mirroring the existing `write_preview` precedent.
- `read_preview` safe-defaults `cuts` to `()` when the sidecar is absent/torn → the route returns `[]`, never raising (RBT-04 boundary preserved).
- The Phase-8 contract keys (`gen`/`tick`/`auto_candidate`/`cams`) are byte-unchanged.
- Tests added to `tests/test_preview_serving.py`: `test_serve_preview_sidecar_exposes_cuts` (non-empty ring round-trips in order, newest-last) + `test_serve_preview_cuts_empty_when_absent` (empty → `[]`, 200).

### Task 2 — Pure POST /score/preview render route (SCV-01 drift-guard)
- New `post_score_preview` route inside `create_app`: whitelists `discipline` against the closed `Discipline` enum (unknown → `("disciplina sconosciuta", 400)`), applies the same WR-05 empty-drop filter as `/score`, builds `ScoreDoc`, and returns `(render_overlay_text(doc), 200, {"Content-Type": "text/plain; charset=utf-8"})`.
- The route NEVER calls `write_score` / `atomic_write_text` — it is pure (no IO), so the JS mirror can call it once on blur/submit without touching the orchestrator's channel.
- Reuses ONLY already-imported symbols → no new import; the crash-isolation allowlist holds.
- New `tests/test_score_preview.py`: byte-exact assertions for all 3 disciplines (including the double spaces), `test_score_preview_byte_reference` (the canonical Wave-0 parity reference for the 09-03 JS mirror), unknown-discipline 400, and `test_score_preview_writes_no_file` (proves purity vs `/score`).

## Verification

- `pytest tests/test_preview_serving.py` → 10 passed (8 pre-existing + 2 new), no regression.
- `pytest tests/test_score_preview.py` → 6 passed.
- `pytest tests/test_imports.py -k "console_resolves or app_imports"` → passed (crash-isolation gate green; no heavy import added).
- `pytest tests/test_preview_serving.py tests/test_score_preview.py tests/test_imports.py tests/test_ui_score.py` → 47 passed, 0 failures.

## Must-Haves Confirmed

- GET /preview returns a `cuts` array (MVW-05) — verified via the Flask test client.
- POST /score/preview returns the exact `render_overlay_text` line for a posted ScoreDoc and writes NO channel file (SCV-01) — byte-exact + writes-no-file tests green.
- Console import surface stays Flask + segugio.opcomm + segugio.ui.score_render — crash-isolation gate green.

## Deviations from Plan

None — plan executed as written. (Task 1's TDD RED/GREEN was driven through but committed as one feat since the change is a single jsonify key inseparable from its test; documented as a decision, not a deviation.)

## Authentication Gates

None.

## Known Stubs

None — both routes are fully wired to live data sources (`PreviewDoc.cuts` and `render_overlay_text`).

## Self-Check: PASSED

- FOUND: src/segugio/ui/app.py
- FOUND: tests/test_score_preview.py
- FOUND: tests/test_preview_serving.py
- FOUND commit d03a9fc (Task 1)
- FOUND commit bddc4cf (Task 2)
