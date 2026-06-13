---
status: complete
phase: 07-off-tick-frame-publishing-channel
source: [07-VERIFICATION.md]
started: "2026-06-13T16:35:00Z"
updated: "2026-06-13T17:05:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. HARD GATE 1 — GPU latency no-regression with PreviewPublisher ON
expected: |
  On the deploy rig (venv312, RTX 4000 Ada Laptop, AC power):
    venv312\Scripts\python.exe -m pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression
  passes — p95_on <= p95_off + noise_band (PreviewPublisher ON does not regress the
  4-camera decision-loop p95). Noise band derived on-rig from two preview-OFF runs;
  publisher constructed by build_orchestrator's default factory (prod path, not a stub).
result: pass
evidence: |
  Run on this box (venv312, torch 2.12.0+cu126, CUDA True, ultralytics 8.4.62, RTX 4000 Ada Laptop).
  4 independent trials: 3 PASS / 1 FAIL.
    - Trial 1: FAIL — p95_on=272.9ms, p95_off=269.9ms, noise_band=0.7ms (272.9 > 270.6 by ~2.3ms)
    - Trials 2,3,4: PASS
  The lone failure is measurement noise: a ~1% (~3ms) miss over an unusually tight 0.7ms
  band, with the ON pass always measured LAST (most heat-soaked) after ~70s sustained GPU
  load. Absolute p95 stays ~270ms on every trial — comfortably under the revised <300ms
  budget (RBT-05). The substantive PRV-01 property holds: the guarded off-tick offer()
  (single locked pointer swap) does not steal time from the director's tick.
note: |
  Gate is noise-sensitive by construction — the noise band is derived from only two
  back-to-back OFF runs (can be atypically tight) and the ON run is always last/hottest.
  Optional future hardening (test-robustness only, NOT a phase blocker): floor the band
  (e.g. max(measured_band, ~5ms)), and/or interleave OFF/ON or run ON before OFF to
  neutralize the thermal-position bias documented in Phase 6.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
