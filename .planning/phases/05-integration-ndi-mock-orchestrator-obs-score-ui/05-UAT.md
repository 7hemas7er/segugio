---
status: partial
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
source: [05-VERIFICATION.md]
started: 2026-06-11T14:05:00Z
updated: 2026-06-11T14:30:00Z
---

## Current Test

[testing complete]

## Tests

All 5 phase truths are VERIFIED headlessly (302 passed, 3 skipped, 0 failures).
The items below are deferred by the phase's headless-first design to the
Windows/RTX hardware box (D-07). UAT surfaced a blocking prerequisite: there is
no runnable entry point to launch the integrated orchestrator on the rig.

### 1. Real OBS startup with orchestrator (CR-01 hardware confirmation, RBT-04)
expected: `python -m segugio` starts without crashing when OBS is not yet running; director ticks; controller reconnects once OBS starts on the live obsws-python v5 stack.
result: issue
reported: "No runnable entry point exists — `python -m segugio` is not defined, no __main__.py / console_script, and Orchestrator.from_config() requires source/obs/trackers/channel_paths to be constructed and injected by a caller that does not exist. The integrated system cannot be launched on the rig."
severity: major

### 2. Real NDI receiver auto-reconnect + near-zero CPU (CR-02, NDI-01)
expected: CPU for disconnected receiver threads is near-zero (no busy-spin); a named NDI source that appears after thread start auto-reconnects without stop()/start(). Watch for the WR-02 livelock risk — set_source re-issued every 50ms mid-handshake on real cyndilib.
result: blocked
blocked_by: other
reason: "The live auto-reconnect/CPU behavior can only be observed with the orchestrator running against a real NdiFrameSource — depends on the missing runner (Test 1). The headless logic (sleep + re-resolve) is already proven by test_ndi_receiver_loop.py."

### 3. Anti-jitter grace empirical tuning (WR-02, RBT-02)
expected: The shipped watchdog_grace=0.067 (~2 frames @30fps) tolerates single-late-frame jitter on real WiFi phone feeds without cut-storms; tune against measured jitter if needed.
result: blocked
blocked_by: other
reason: "Empirical tuning needs the live system running against real WiFi phone feeds — depends on the missing runner (Test 1). The non-zero default is already pinned by test."

### 4. Full E2E real-stack run (D-07 — v1 milestone validation)
expected: mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update all work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera + reason.
result: blocked
blocked_by: other
reason: "The full milestone E2E cannot run without a launchable integrated orchestrator — depends on the missing runner (Test 1)."

### 5. GPU latency budget (RBT-05)
expected: `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with yolo26s.pt and real clip frames shows decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py. (Wiring overhead proven headless: mock-timed p95 < 50ms.)
result: blocked
blocked_by: physical-device
reason: "Needs the RTX 4000 Ada GPU box with yolo26s.pt. Independent of the runner — runnable any time via `pytest tests/test_latency.py -m gpu` on the GPU machine."

## Summary

total: 5
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 4

## Gaps

- truth: "The integrated orchestrator can be launched on the rig: a runnable entry point composes the real NdiFrameSource + ObsWsController + PerCameraTracker (yolo26s.pt) from config and calls Orchestrator.run(), so the full NDI->YOLO->score->FSM->OBS loop runs against real hardware. The phase goal ('everything wires together end-to-end ... a fault-isolated orchestrator ticks the full loop') is only half-met without it: the logic is verified headless but nothing launches it on hardware, so the D-07 human E2E (Tests 1-4) cannot be executed."
  status: failed
  reason: "User reported (UAT Test 1): no way to launch the integrated system on the rig. Code inspection confirms: no src/segugio/__main__.py, no `python -m segugio`, no console_script entry, and Orchestrator.from_config() requires source/obs/trackers/channel_paths to be constructed and injected by a caller that does not exist. Only the Flask UI (ui/app.py) is runnable today."
  severity: major
  test: 1
  artifacts:
    - "src/segugio/orchestrator/loop.py — Orchestrator.from_config(config, source, obs, channel_paths, trackers, ...) builds only scorer/engine/watchdog/deriver; it does NOT construct the real source/obs/trackers."
    - "config.example.yaml — config schema exists (cameras, obs, scoring, thresholds) but there is no loader->compose->run path that turns it into a running orchestrator."
    - "src/segugio/ui/app.py — the only runnable process today (Flask console); proves the pattern for a __main__ but covers only the UI side."
  missing:
    - "src/segugio/__main__.py (and/or a [project.scripts] console_script) — load Config from a yaml path, build opcomm channel paths, construct one real NdiFrameSource per config.camera (NDI name) + an ObsWsController (host/port/password) + one PerCameraTracker(yolo26s.pt) per camera, call Orchestrator.from_config(...).run(rate_hz), and on KeyboardInterrupt call shutdown() to coast OBS to SAFE (RBT-04)."
    - "A compose/factory (e.g. src/segugio/orchestrator/runtime.py: build_orchestrator(config, config_path)) that maps config.cameras -> real FrameSource/ObsController/trackers + channel_paths — the runtime glue from_config deliberately does not own. Keep heavy imports (cyndilib/obsws/cv2/ultralytics) lazy inside it so the headless import boundary stays intact."
    - "docs note (extend docs/obs-setup.md or a short docs/run.md): the exact command to launch on the rig with OBS up/down, so the D-07 Tests 1-4 are executable."
