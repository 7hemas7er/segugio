---
phase: 10-overlay-data-contract-run-timestamp-publish
plan: 03
subsystem: config
tags: [overlay, config, pydantic, freestyle-timer]

requires:
  - phase: 10-overlay-data-contract-run-timestamp-publish (Plan 01)
    provides: "tests/test_config_overlay.py RED scaffold (xfail) + make_config fixture usage"
provides:
  - "OverlayParams pydantic sub-model (config/models.py) with freestyle_duration_s: Annotated[int, Field(gt=0)] = 120, extra='forbid'"
  - "Config.overlay: OverlayParams = Field(default_factory=OverlayParams) — optional block, legacy configs still validate"
  - "Documented commented overlay: block in config.example.yaml"
affects:
  - "Phase 11 (freestyle timer consumes overlay.freestyle_duration_s; OverlayParams is the future home of BRD-01 logo/theme/identity fields)"

tech-stack:
  added: []
  patterns:
    - "Additive extra='forbid' bounded-field sub-model wired via Field(default_factory=...) so an absent block still validates under the fail-fast SystemExit(2) loader"

key-files:
  created: []
  modified:
    - "src/segugio/config/models.py"
    - "config.example.yaml"
    - "tests/test_config_overlay.py"

key-decisions:
  - "freestyle_duration_s default = 120 (D-06, 2-minute routines); orgs running 90-second freestyle rounds override — resolves the flagged 90s-vs-120s blocker"
  - "freestyle_duration_s is STATIC config — NOT in the /overlay-json poll payload (D-07); Phase 11 injects it into the /overlay page via an entrypoint arg (like cam_ids)"

patterns-established:
  - "OverlayParams mirrors ActionHoldParams/PreviewParams line-for-line: ConfigDict(extra='forbid') + Annotated bounded field + default_factory wiring on Config"

requirements-completed: [OVD-03]

duration: 6min
completed: 2026-06-14
---

# Phase 10 Plan 03: Overlay Config Sub-Model Summary

**Additive `OverlayParams` pydantic sub-model (`extra='forbid'`, `freestyle_duration_s: int = 120`, `gt=0`) wired onto `Config.overlay` via `default_factory`, flipping `tests/test_config_overlay.py` from RED (xfail) to GREEN.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- `OverlayParams(BaseModel)` added next to `PreviewParams` in `config/models.py`: `model_config = ConfigDict(extra="forbid")` + `freestyle_duration_s: Annotated[int, Field(gt=0)] = 120`, with a docstring documenting the Phase-11 consumption, the additive optionality, and that it is the future home of the BRD-01 logo/theme/identity fields (D-05).
- `Config.overlay: OverlayParams = Field(default_factory=OverlayParams)` wired after the `preview:` field — a config WITHOUT an `overlay:` block still validates (mandatory: the loader is fail-fast `SystemExit(2)` on any `ValidationError`).
- `config.example.yaml` gained a documented commented `overlay:` block (default 120; note orgs override to 90; `> 0` constraint), mirroring the existing block-comment style.
- All 5 xfail markers removed from `tests/test_config_overlay.py` (now permanent regression guards); the now-stale RED-by-design docstring paragraph rewritten to GREEN.

## Task Commits

1. **Task 1: Add OverlayParams sub-model + wire Config.overlay + document config.example.yaml** - `a726602` (feat)

_Note: this is a TDD task whose RED phase was landed by Plan 10-01 (the xfail scaffold). This plan implements the production symbols and removes the xfail markers in a single GREEN commit._

## Files Created/Modified

- `src/segugio/config/models.py` - Added `OverlayParams` sub-model and the `Config.overlay` field (no new imports — `BaseModel`/`ConfigDict`/`Field`/`Annotated` already present).
- `config.example.yaml` - Added the commented `overlay:` block documenting `freestyle_duration_s`.
- `tests/test_config_overlay.py` - Removed all 5 xfail markers; updated module docstring.

## Decisions Made

- Default `freestyle_duration_s = 120` with orgs overriding to 90 — locked per D-06, resolving the 90s-vs-120s blocker.
- `freestyle_duration_s` stays out of the `/overlay-json` payload (D-07); Phase 11 injects it as an entrypoint arg.

## Deviations from Plan

None - plan executed exactly as written.

The pre-existing, unrelated working-tree edit to `cameras[].ndi_source` ("LOCALHOST (iPhone Camera for OBS Studio App)") in `config.example.yaml` was left untouched per the scope note; it rode along in the commit diff as expected and was not authored or reverted by this plan.

## Issues Encountered

None. `config.example.yaml` had no existing `preview:`/`action_hold:` block to mirror inline (those rely on defaults), so the new `overlay:` block was appended after the `model:` block following the file's established block-comment documentation style.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Config schema + default for the configurable freestyle round length is locked. Phase 11 can consume `cfg.overlay.freestyle_duration_s` and grow `OverlayParams` with the BRD-01 logo/theme/identity fields in one place.
- Zero file overlap with Plans 02/04 — ran in parallel cleanly.

## Self-Check: PASSED

- FOUND: src/segugio/config/models.py (contains `class OverlayParams`)
- FOUND: config.example.yaml (contains `freestyle_duration_s`)
- FOUND: tests/test_config_overlay.py (xfail markers removed; green)
- FOUND commit: a726602 (Task 1)

---
*Phase: 10-overlay-data-contract-run-timestamp-publish*
*Completed: 2026-06-14*
