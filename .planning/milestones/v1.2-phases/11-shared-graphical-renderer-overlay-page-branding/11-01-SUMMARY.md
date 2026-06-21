---
phase: 11-shared-graphical-renderer-overlay-page-branding
plan: 01
subsystem: ui-console / config
tags: [overlay, branding, flask-route, crash-isolation, config-model]
requires:
  - "OverlayParams sub-model + Config.overlay (Phase 10 / 10-03)"
  - "GET /overlay-json + create_app(channel_dir, cam_ids=()) (Phase 10 / 10-04)"
  - "render_overlay_text + opcomm never-raise readers (Phase 9)"
provides:
  - "GET /overlay route (transparent OBS host page; render_template overlay.html, no-store)"
  - "create_app(channel_dir, cam_ids=(), overlay_cfg=None) — new overlay_cfg plain-dict arg"
  - "OverlayParams.event_name / logo_path / theme_accent / theme_plate / theme_text (BRD-01/BRD-02)"
  - "Entrypoint overlay branding resolution (cfg.overlay.* + SEGUGIO_OVERLAY_* env overrides)"
  - "RBT-07 crash-isolation gate extended to GET /overlay"
affects:
  - "11-02 (ships templates/overlay.html consuming the overlay_cfg render args)"
  - "11-03 (overlay-render.js consumes /overlay-json; branding is render-time only)"
tech-stack:
  added: []
  patterns:
    - "Branding injected as plain dict render args (like cam_ids) — never import segugio.config at module top"
    - "Console-palette defaults mirrored in app.py (_OVERLAY_CFG_DEFAULTS) so the template never sees an undefined var"
    - "Flat str theme fields (not hex-validated) accept any CSS color token"
key-files:
  created: []
  modified:
    - "src/segugio/config/models.py"
    - "src/segugio/ui/app.py"
    - "tests/test_config_overlay.py"
    - "tests/test_imports.py"
    - "config.example.yaml"
decisions:
  - "Flat str theme fields (theme_accent/plate/text) over a nested theme block (CONTEXT discretion)"
  - "overlay_cfg defaults live as a plain dict in app.py (NOT imported from config) to hold the crash-isolation allowlist"
  - "New optional entrypoint env vars: SEGUGIO_OVERLAY_EVENT/LOGO/ACCENT/PLATE/TEXT (win over cfg.overlay.*)"
  - "The full GET /overlay 200+no-store assertion is gated to once overlay.html exists (11-02) — this plan proves route-registered + heavy-free"
metrics:
  duration: 9min
  completed: "2026-06-14"
  tasks: 2
  files: 5
---

# Phase 11 Plan 01: Shared Graphical Renderer /overlay Backend & Branding Summary

The backend half of the overlay page: `OverlayParams` grows with logo/theme/event branding (zero data-model change), `GET /overlay` serves `overlay.html` with that branding injected as plain render args resolved lazily in the entrypoint, and the RBT-07 crash-isolation gate now covers the new route — green with the heavy stack absent.

## What Was Built

**Task 1 — OverlayParams branding (BRD-01/BRD-02), commit `7c9d75e`**
- Grew `OverlayParams` additively with `event_name: str = ""` (D-08), `logo_path: str = ""` (D-07), and three flat CSS-var theme color strings defaulting to the console palette: `theme_accent="#34D399"`, `theme_plate="#14161a"`, `theme_text="#E6E9EF"` (D-06).
- All fields carry defaults so a config without an `overlay:` block (or with only `freestyle_duration_s`) still validates under the fail-fast `SystemExit(2)` loader; `model_config = ConfigDict(extra="forbid")` and `freestyle_duration_s` default 120 unchanged.
- Theme fields are plain `str` (NOT hex-validated) so an org may pass any CSS color token (`rgb(...)`, named, hex).
- Documented every new `overlay.*` key with its default in `config.example.yaml`.
- Extended `tests/test_config_overlay.py`: branding defaults, freestyle-only config still validates, full round-trip, and `extra=forbid` rejection.

**Task 2 — GET /overlay route + entrypoint injection + RBT-07 gate, commit `76e8c72`**
- Registered `@app.get("/overlay")` inside `create_app`: a thin host page that `render_template("overlay.html", **overlay_cfg)` with NO score/run data baked in (the page polls `/overlay-json`), setting `Cache-Control: no-store`.
- Extended the factory signature to `create_app(channel_dir, cam_ids=(), overlay_cfg=None)`; a partial `overlay_cfg` is folded over the `_OVERLAY_CFG_DEFAULTS` console-palette dict so the template never sees an undefined branding var.
- Resolved `overlay_cfg` lazily in `__main__` from `cfg.overlay.*` (when `SEGUGIO_CONFIG` is set), with per-field env overrides (`SEGUGIO_OVERLAY_EVENT/LOGO/ACCENT/PLATE/TEXT`) winning over config. No `import segugio.config` at module top — the crash-isolation allowlist holds.
- Added `make_response` to the in-factory `from flask import ...`.
- Extended `test_console_resolves_with_heavy_stack_and_numpy_absent`: under the heavy-absent block, asserts `/overlay` is registered and `create_app` builds without raising; the full `200 + no-store` assertion is gated to once `templates/overlay.html` exists (the cross-plan acceptance owned by 11-02).
- `/overlay-json` payload shape is unchanged — verified branding never leaks into the poll (6 keys: discipline, fields, gen, running, server_now, started_at).

## Verification

- `python -m pytest tests/test_config_overlay.py -x -q` — 11 passed
- `python -m pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x -q` — passed (heavy stack + numpy forced absent)
- `python -m pytest tests/ -k "ui or import or overlay or config" -q` — all passed (1 skipped, pre-existing)
- `load_config('config.example.yaml')` resolves the new `overlay.*` keys to the documented defaults
- Functional check: `/overlay` registered; `/overlay-json` keys unchanged; no branding in the poll payload

## Deviations from Plan

None — plan executed exactly as written. The two tasks followed the RED → GREEN TDD cycle (config test RED on missing `event_name`, then GREEN; imports test RED on unregistered `/overlay`, then GREEN).

## Authentication Gates

None.

## Known Stubs

- **Gated `GET /overlay` 200 + no-store assertion** (`tests/test_imports.py`) — `templates/overlay.html` does not exist yet (it is produced by plan 11-02). Until it ships, `GET /overlay` would 500 on the missing template, so the full `200`/`no-store` assertion is conditionally gated behind `os.path.exists(overlay.html)`. This plan's contribution (route registered + no module-top heavy import) is fully asserted unconditionally. This is an intentional cross-plan dependency, not an unresolved gap — the gate auto-activates the moment 11-02 lands the template.

## New Symbols Introduced (created-here, not drift)

- Route: `GET /overlay` (`src/segugio/ui/app.py`)
- `create_app` param: `overlay_cfg` (plain dict)
- Module constant: `_OVERLAY_CFG_DEFAULTS` (`src/segugio/ui/app.py`)
- `OverlayParams` fields: `event_name`, `logo_path`, `theme_accent`, `theme_plate`, `theme_text`
- Entrypoint env vars (optional): `SEGUGIO_OVERLAY_EVENT`, `SEGUGIO_OVERLAY_LOGO`, `SEGUGIO_OVERLAY_ACCENT`, `SEGUGIO_OVERLAY_PLATE`, `SEGUGIO_OVERLAY_TEXT`
- `config.example.yaml` keys: `overlay.event_name`, `overlay.logo_path`, `overlay.theme_accent`, `overlay.theme_plate`, `overlay.theme_text`

## TDD Gate Compliance

Both tasks ran RED → GREEN. Per-task commits use `feat(...)` (the implementation also contains the test extension in the same commit, matching the existing repo convention for additive route/config work). RED was observed and recorded before each GREEN implementation.

## Self-Check: PASSED

All 5 modified files and the SUMMARY exist on disk; both task commits (`7c9d75e`, `76e8c72`) are in the git log.
