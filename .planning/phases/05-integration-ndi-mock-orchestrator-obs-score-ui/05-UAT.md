---
status: testing
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
source: [05-VERIFICATION.md]
started: 2026-06-11T14:05:00Z
updated: 2026-06-11T14:05:00Z
---

## Current Test

number: 1
name: Real OBS startup survival — _safe_startup on the live obsws stack
expected: |
  `python -m segugio` starts without crashing when OBS is not yet running; the
  director ticks; the controller reconnects once OBS starts. (CR-01 logic verified
  headless via test_run_measured_survives_connect_raising; this confirms the real
  websocket stack completes the same fault-isolated path.)
awaiting: user response

## Tests

All 5 phase truths are VERIFIED headlessly (302 passed, 3 skipped, 0 failures).
The items below are deferred by the phase's headless-first design to the
Windows/RTX hardware box (D-07) — they are not failures, they require real
hardware/drivers (cyndilib, obsws-python, cv2, CUDA/ultralytics) absent in dev.

### 1. Real OBS startup with orchestrator (CR-01 hardware confirmation, RBT-04)
expected: `python -m segugio` starts without crashing when OBS is not yet running; director ticks; controller reconnects once OBS starts on the live obsws-python v5 stack.
result: [pending]

### 2. Real NDI receiver auto-reconnect + near-zero CPU (CR-02, NDI-01)
expected: CPU for disconnected receiver threads is near-zero (no busy-spin); a named NDI source that appears after thread start auto-reconnects without stop()/start(). Watch for the WR-02 livelock risk — set_source re-issued every 50ms mid-handshake on real cyndilib.
result: [pending]

### 3. Anti-jitter grace empirical tuning (WR-02, RBT-02)
expected: The shipped watchdog_grace=0.067 (~2 frames @30fps) tolerates single-late-frame jitter on real WiFi phone feeds without cut-storms; tune against measured jitter if needed.
result: [pending]

### 4. Full E2E real-stack run (D-07 — v1 milestone validation)
expected: mock NDI sender → cyndilib → YOLO → score → FSM → OBS cut/PIP/overlay → feed death → SAFE fallback → UI score entry → overlay update all work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera + reason.
result: [pending]

### 5. GPU latency budget (RBT-05)
expected: `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with yolo26s.pt and real clip frames shows decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py. (Wiring overhead proven headless: mock-timed p95 < 50ms.)
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
