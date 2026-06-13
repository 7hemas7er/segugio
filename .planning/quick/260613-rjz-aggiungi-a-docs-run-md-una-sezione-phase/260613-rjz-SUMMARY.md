---
phase: quick-260613-rjz
plan: 01
subsystem: docs
tags: [docs, run, phase-8, console, multiview, ndi, preview]
requires: []
provides: ["docs/run.md Phase 8 console-multiview launch + troubleshooting section"]
affects: [docs/run.md]
tech-stack:
  added: []
  patterns: ["doc mirrors shipped code identifiers verbatim (env vars, routes, config fields)"]
key-files:
  created: []
  modified: ["docs/run.md"]
decisions:
  - "Diagnostic commands run from venv312 (has cyndilib + system NDI runtime); plain invocation works because segugio is editable-installed there, with a $env:PYTHONPATH='src' fallback documented for venvs where it is not"
metrics:
  duration: ~6min
  completed: 2026-06-13
---

# Phase quick-260613-rjz: Add "Phase 8 — Console multiview live" section to docs/run.md Summary

Added a single new `## Phase 8 — Console multiview live` section to `docs/run.md` giving the rig operator a code-verified, copy-paste-correct launch + troubleshooting procedure for the two-process (light CPU-venv console / heavy venv312 orchestrator) live multiview — every command, env var, route, and config field mirrors the shipped code.

## What Was Done

Task 1 (single doc-only task): inserted the new section **between** the existing `## What the UAT tests exercise from here` and `## GPU latency env (Phase 6)` sections, with a leading `---` separator to match the file's section style. No existing content was modified, reordered, or deleted (Edit-append, byte-preserving). All five required points are covered:

1. **Two-process architecture** — light Flask console (CPU `venv`, imports only Flask + `segugio.opcomm`, crash-isolation contract) vs heavy orchestrator (`venv312`, `[heavy]` stack); coupled only via the shared opcomm dir; console renders only what the orchestrator publishes; the `venv312` import-path gotcha (editable-install OR `$env:PYTHONPATH = "src"`).
2. **Console launch** — `python -m segugio.ui.app` binds `0.0.0.0:8080`; the real whitelist env vars `SEGUGIO_OPCOMM_DIR` / `SEGUGIO_CAM_IDS` (precedence) / `SEGUGIO_CONFIG`, the four default ids `cam_wide,cam_long,cam_low,cam_handler`; the waitress → `threaded=True` fallback documented as the UXT-02 SAFETY control; optional `pip install -e ".[console]"`; PowerShell launch example.
3. **Routes served** — `GET /preview` (the `preview.json` why-sidecar via safe-default `read_preview`) and `GET /preview/<cam>.jpg` (whitelisted `send_file`, anti path-traversal, fixed `preview/cam_{id}.jpg` prefix → `cam_cam_wide.jpg`, unknown id → 404, `Cache-Control: no-store`); tiles populate only with preview ENABLED + same opcomm dir.
4. **Preview bandwidth cap** — config-time guarantee: `PreviewParams.max_total_mbps` (default `8.0`) + `Config._preview_bitrate_within_cap` `@model_validator` rejecting over-cap configs with `SystemExit(2)`; `preview.enabled: false` short-circuits; cross-reference to `docs/security.md` for the T-08-03 / AP-client-isolation posture.
5. **Troubleshooting "il telefono si vede in OBS ma non nella console"** — (a) exact `ndi_source` name match (`source_name in names`), (b) the `verify_ndi_hx_decode.py` diagnostic from `venv312`, (c) a cyndilib `Finder` discovery one-liner, (d) the load-bearing reminder that the console only renders what the orchestrator publishes.

Style: English prose with Italian project terms (matching the existing file), Windows PowerShell command syntax (`$env:VAR = "..."`), fenced code blocks.

## Verification

- Plan's automated PowerShell check PASSED: section heading present, all required code tokens present (`SEGUGIO_OPCOMM_DIR`, `SEGUGIO_CAM_IDS`, `SEGUGIO_CONFIG`, `/preview/<cam>.jpg`, `GET /preview`, `max_total_mbps`, `threaded=True`, `verify_ndi_hx_decode.py`, `console`), and the existing `GPU latency env (Phase 6)` + `What the UAT tests exercise from here` sections preserved.
- All identifiers were copied verbatim after re-reading `app.py`, `models.py`, `pyproject.toml`, `ndi_source.py`, and `verify_ndi_hx_decode.py`. No env var, route, or config field was invented.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Doc accuracy] `venv312` editable-install state reconciled against the actual box**
- **Found during:** Task 1 (the plan/verification note's flagged reconciliation)
- **Issue:** The plan and the orchestrator's verification note both assumed segugio is **NOT** editable-installed in `venv312` on this box, and instructed documenting the diagnostic exclusively as `$env:PYTHONPATH="src"; venv312\Scripts\python.exe tools\verify_ndi_hx_decode.py`. On inspection (`pip show segugio` in `venv312`) segugio **IS** editable-installed there ("Editable project location" → repo root; `segugio.__file__` resolves to `src/segugio`). cyndilib is present in both `venv` and `venv312`.
- **Fix:** Documented the **plain** invocation `venv312\Scripts\python.exe tools\verify_ndi_hx_decode.py "<name>"` as the primary command (correct against the actual box), and kept the `$env:PYTHONPATH = "src"` form as a documented **fallback** for any venv where segugio is not importable. This preserves the plan's safety intent while keeping the doc accurate.
- **Files modified:** docs/run.md
- **Commit:** 109aaa5

## Commits

- `109aaa5`: docs(quick-260613-rjz): add Phase 8 console multiview live section to run.md

## Self-Check: PASSED

- FOUND: docs/run.md (modified, `## Phase 8 — Console multiview live` section present between UAT and GPU sections)
- FOUND: commit 109aaa5
