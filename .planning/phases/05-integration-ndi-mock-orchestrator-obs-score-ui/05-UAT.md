---
status: testing
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
source: [05-VERIFICATION.md]
started: 2026-06-11T14:05:00Z
updated: 2026-06-11T16:10:00Z
---

## Current Test

[ready for hardware — D-07]

All 5 phase truths are VERIFIED headlessly (315 passed, 9 skipped, 0 failures).
The blocking prerequisite UAT first surfaced — no runnable entry point — is now
RESOLVED by gap-closure plan 05-09: `python -m segugio <config.yaml>` exists and
composes the real NdiFrameSource + ObsWsController + PerCameraTracker from config,
then calls Orchestrator.run() (Ctrl-C → shutdown() SAFE coast, RBT-04). The CR-01
blocker found in code review (channel_dir never created → D-11 status channel
silently dead on a clean launch) is also fixed and regression-tested. The items
below are now LAUNCHABLE on the Windows/RTX hardware box via `docs/run.md` — they
remain deferred to that box (D-07), no longer blocked on missing code.

## Tests

### 1. Real OBS startup with orchestrator (RBT-04, _safe_startup on the live obsws stack)
expected: `python -m segugio config.example.yaml` starts without crashing when OBS is not yet running; the director ticks; the controller reconnects once OBS starts on the live obsws-python v5 stack.
result: pending
reason: "Code gap RESOLVED — the entry point now exists (05-09: __main__.py + runtime.py). obsws-python is absent in dev; the headless test (test_run_measured_survives_connect_raising) drives the REAL _safe_startup path with a ConnectionError-raising fake. On-Windows confirmation of the live websocket stack is D-07. Launch per docs/run.md (OBS-down section)."

### 2. Real NDI receiver auto-reconnect + near-zero CPU (CR-02, NDI-01)
expected: CPU for disconnected receiver threads is near-zero (no busy-spin); a named NDI source that appears after thread start auto-reconnects without stop()/start(). Watch for the WR-02 livelock risk — set_source re-issued every 50ms mid-handshake on real cyndilib.
result: pending
blocked_by: physical-device
reason: "Now launchable via `python -m segugio` (Test-1 runner exists). Requires Windows + cyndilib + a live/mock NDI source to observe real reconnect timing and CPU. Headless logic (sleep + re-resolve) proven by test_ndi_receiver_loop.py."

### 3. Anti-jitter grace empirical tuning (WR-02, RBT-02)
expected: The shipped watchdog_grace=0.067 (~2 frames @30fps) tolerates single-late-frame jitter on real WiFi phone feeds without cut-storms; tune against measured jitter if needed.
result: pending
blocked_by: physical-device
reason: "Now launchable via the runner; empirical tuning needs the live system against real WiFi phone feeds (D-07). The non-zero default is already pinned by test."

### 4. Full E2E real-stack run (D-07 — v1 milestone validation)
expected: mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update all work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera + reason.
result: pending
blocked_by: physical-device
reason: "Now launchable — `python -m segugio config.example.yaml` + the operator console (docs/run.md). cyndilib/obsws/cv2/CUDA/ultralytics are absent in dev (@pytest.mark.ndi/obs auto-skip). This is the v1 milestone on-Windows hardware validation (D-07)."

### 5. GPU latency budget (RBT-05)
expected: `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with yolo26s.pt and real clip frames shows decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py. (Wiring overhead proven headless: mock-timed p95 < 50ms.)
result: pending
blocked_by: physical-device
reason: "Needs the RTX 4000 Ada GPU box with yolo26s.pt. Independent of the runner — runnable any time via `pytest tests/test_latency.py -m gpu` on the GPU machine."

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

- truth: "The integrated orchestrator can be launched on the rig: a runnable entry point composes the real NdiFrameSource + ObsWsController + PerCameraTracker (yolo26s.pt) from config and calls Orchestrator.run(), so the full NDI->YOLO->score->FSM->OBS loop runs against real hardware. The phase goal ('everything wires together end-to-end ... a fault-isolated orchestrator ticks the full loop') is only half-met without it: the logic is verified headless but nothing launches it on hardware, so the D-07 human E2E (Tests 1-4) cannot be executed."
  status: resolved
  reason: "User reported (UAT Test 1): no way to launch the integrated system on the rig. Code inspection confirmed: no src/segugio/__main__.py, no `python -m segugio`, no console_script entry, and Orchestrator.from_config() required source/obs/trackers/channel_paths to be injected by a caller that did not exist."
  resolved_by: "Gap-closure plan 05-09 (commits a6a8a66 build_orchestrator factory, 9ec23ca `python -m segugio` entry + docs/run.md) and code-review fix 9c8ac26 (CR-01: build_orchestrator now creates channel_dir so the D-11 status reverse-channel works on a clean standalone launch). Re-verified 5/5 (05-VERIFICATION.md, 2026-06-11T16:00). The runnable entry point now exists and is correct headless; UAT Tests 1-4 are LAUNCHABLE on the rig per docs/run.md. Only the hardware E2E execution remains (D-07), a physical-device deferral, not a code gap."
  severity: major
  test: 1
  artifacts:
    - "src/segugio/orchestrator/runtime.py — build_orchestrator(config, channel_dir, *, fps, grace, *_factory) maps config.cameras -> real NdiFrameSource + ObsWsController + per-camera PerCameraTracker + channel_paths, creates channel_dir, returns Orchestrator.from_config(...). Heavy imports lazy; *_factory injectable for headless tests."
    - "src/segugio/__main__.py — `python -m segugio <config> [--rate R] [--opcomm-dir DIR]`: load_config -> build_orchestrator -> run; KeyboardInterrupt -> shutdown() (RBT-04 SAFE coast)."
    - "docs/run.md — exact rig launch commands (OBS up/down) + operator console + opcomm-dir contract, making UAT Tests 1-4 executable."
    - "tests/test_orchestrator_runtime.py — 11 headless regressions incl. test_build_creates_missing_channel_dir (CR-01 guard) and the lazy-import boundary tests."
