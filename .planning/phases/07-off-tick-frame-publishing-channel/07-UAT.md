---
status: testing
phase: 07-off-tick-frame-publishing-channel
source: [07-VERIFICATION.md]
started: "2026-06-13T16:35:00Z"
updated: "2026-06-13T16:35:00Z"
---

## Current Test

number: 1
name: HARD GATE 1 — GPU latency no-regression with PreviewPublisher ON
expected: |
  On the deploy rig (venv312, RTX 4000 Ada Laptop, AC power), run:
    venv312\Scripts\python.exe -m pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression
  PASSES — p95_on <= p95_off + noise_band. The test derives the noise band from two
  back-to-back preview-OFF run_measured passes (no magic number), then runs the REAL
  PreviewPublisher ON under the same harness via build_orchestrator's default factory
  (the prod wiring), asserting the guarded off-tick offer() does not regress the
  4-camera decision-loop p95.
awaiting: user response

## Tests

### 1. HARD GATE 1 — GPU latency no-regression with PreviewPublisher ON
expected: |
  On the deploy rig (venv312, RTX 4000 Ada Laptop, AC power):
    venv312\Scripts\python.exe -m pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression
  passes — p95_on <= p95_off + noise_band (PreviewPublisher ON does not regress the
  4-camera decision-loop p95). Noise band derived on-rig from two preview-OFF runs;
  publisher constructed by build_orchestrator's default factory (prod path, not a stub).
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
