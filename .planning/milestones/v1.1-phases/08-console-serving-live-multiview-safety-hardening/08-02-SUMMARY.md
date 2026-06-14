---
phase: 08-console-serving-live-multiview-safety-hardening
plan: 02
subsystem: config
tags: [pydantic, config, bandwidth-cap, fail-fast, preview, model_validator]

# Dependency graph
requires:
  - phase: 07-off-tick-frame-publishing-channel
    provides: PreviewParams sub-model (fps/max_width/jpeg_quality seeds) + PreviewPublisher (the JPEG traffic the cap budgets)
provides:
  - "PreviewParams.max_total_mbps — tunable HARD preview-bandwidth ceiling (default 8.0 Mbps)"
  - "Config._preview_bitrate_within_cap @model_validator — config-time fail-fast rejection of over-cap previews (SystemExit(2) via loader)"
  - "_estimate_jpeg_bytes(max_width, jpeg_quality) helper + documented q55 bpp calibration constant"
affects: [phase-08-console-serving, phase-09-explainability, hardware-milestone-wifi-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Config-time bandwidth guarantee via pydantic @model_validator (CFG-01 fail-fast posture) — NO runtime throttle"
    - "Documented, tunable calibration constant gated in both directions (default-passes / cranked-fails)"

key-files:
  created:
    - tests/test_preview_bitrate_cap.py
  modified:
    - src/segugio/config/models.py

key-decisions:
  - "The preview-bandwidth cap is a CONFIG-TIME guarantee enforced by a pydantic @model_validator at load — an over-budget preview config is a startup SystemExit(2), not a live surprise. NO runtime throttle (D-01 anti-pattern declined; a feedback loop overlaps Phase-9 UXT-03)."
  - "bpp constant = 0.30 (q55, 16:9 thumbnail), calibrated so the Phase-7 defaults (5/384/q55/4 cams) land at ~3.98 Mbps inside the measured 0.3-0.8 MB/s (~2.4-6.4 Mbps) band; quality scales linearly via jpeg_quality/55. LOW-confidence calibration surfaced as a comment + made tunable via max_total_mbps (T-08-05 accept-documented)."
  - "preview.enabled=false short-circuits the cap (no JPEGs published -> nothing to budget, D-09 source-side off-switch)."

patterns-established:
  - "Bandwidth cap as a first-class capped resource enforced at the config trust boundary, mirroring the existing _zones_are_weighted validator shape (iterate/raise ValueError/return self)."

requirements-completed: [MVW-03]

# Metrics
duration: 4min
completed: 2026-06-13
---

# Phase 8 Plan 02: Preview Bandwidth Cap (config-time guarantee) Summary

**Added a HARD preview-bandwidth ceiling (`PreviewParams.max_total_mbps`, default 8.0 Mbps) enforced fail-fast at config load by a `Config` pydantic `@model_validator` that computes the worst-case bitrate (`bytes/frame × 8 × fps × N_cams`) and rejects over-cap configs with `SystemExit(2)` — no runtime throttle.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-13T15:15Z
- **Completed:** 2026-06-13T15:19Z
- **Tasks:** 2 (TDD: RED test + GREEN implementation)
- **Files modified:** 2

## Accomplishments
- `PreviewParams.max_total_mbps` additive tunable ceiling field (default 8.0 Mbps, `Field(gt=0.0)`) — existing `extra="forbid"` configs without it still validate.
- Module-level `_estimate_jpeg_bytes(max_width, jpeg_quality)` helper with a documented, calibration-cited bpp constant (`_JPEG_BYTES_PER_PIXEL = 0.30`).
- `Config._preview_bitrate_within_cap` `@model_validator(mode="after")` mirroring `_zones_are_weighted`: computes `est_bytes × 8 × fps × N_cams / 1e6`, raises a descriptive `ValueError` (naming the computed bitrate, the cap, the inputs, and the remediation) on exceed; early-returns when `preview.enabled` is false. The raised error aggregates into the loader's `SystemExit(2)` (CFG-01).
- Five tests pinning: default passes, over-cap rejected (`ValidationError`), disabled skips, cap is tunable, and the loader path aborts with `SystemExit(2)`.

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: Wave-0 scaffold — bitrate-cap config test** — `959924d` (test)
2. **Task 2: PreviewParams ceiling field + Config bitrate validator + bpp helper (D-01)** — `fd6c59d` (feat)

_No REFACTOR commit needed — the GREEN implementation mirrored the existing validator shape directly._

## Files Created/Modified
- `tests/test_preview_bitrate_cap.py` — D-01/D-02 config-validation tests (default passes / over-cap rejected / disabled skips / cap tunable / loader SystemExit(2)).
- `src/segugio/config/models.py` — `PreviewParams.max_total_mbps` field, `_JPEG_BYTES_PER_PIXEL` + `_estimate_jpeg_bytes` helper, `Config._preview_bitrate_within_cap` validator.

## Decisions Made
- See `key-decisions` frontmatter: config-time-only enforcement (no runtime throttle), bpp=0.30 q55 calibration made tunable, `enabled=false` short-circuit.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. (The full-suite `tests/test_fan_out_batched.py` failures are PRE-EXISTING and environmental — they require the heavy `ultralytics` GPU stack, which lives in `venv312/`, absent from this headless `venv`. Confirmed `import ultralytics` raises `ModuleNotFoundError` on the active interpreter; unrelated to this config-only change. The config/loader/preview/import subset is fully green: 132 passed, 1 skipped.)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The preview byte budget is now a first-class capped resource enforced at config load. Phase 8's console-serving + multiview work can rely on an over-budget preview being a startup error.
- **Hardware-milestone carry-forward (D-02):** the real-WiFi-with-phones false-death-rate validation (MVW success criterion 4 "with phones live") requires 3-4 real NDI phones on the dedicated AP + the console open and CANNOT be validated headless. No synthetic network-contention harness was built (rejected, D-02). This remains a deferred must-have, not a Phase-8 test. The bpp=0.30 calibration should be re-checked against real on-rig preview byte measurements; `max_total_mbps` is the tuning knob if it shifts.

## Self-Check: PASSED
- `src/segugio/config/models.py` — FOUND (modified)
- `tests/test_preview_bitrate_cap.py` — FOUND (created)
- Commit `959924d` (test) — FOUND
- Commit `fd6c59d` (feat) — FOUND
- `pytest tests/test_preview_bitrate_cap.py` — 5 passed

---
*Phase: 08-console-serving-live-multiview-safety-hardening*
*Completed: 2026-06-13*
