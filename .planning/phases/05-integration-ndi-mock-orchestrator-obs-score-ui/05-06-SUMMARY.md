---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 06
subsystem: orchestrator
tags: [orchestrator, fault-isolation, action-hold, latency, fsm-wiring, d-08, rbt-04, rbt-05]
requires:
  - "segugio.ndi.FrameSource + ClipReplayFrameSource (05-02)"
  - "segugio.obs.ObsController + RecordingObsController + scene_for (05-03)"
  - "segugio.watchdog_feed.FeedWatchdog (05-04)"
  - "segugio.opcomm.channel read_command/read_runstate/write_status (05-01/05-05)"
  - "segugio.framing.MultiCamScorer; segugio.decision.DecisionEngine (Phase 2/3)"
  - "segugio.tracking PerCameraTracker/CompetitorLock/PlausibilityGate/signals_from_boxes/reid_check (Phase 4)"
  - "CompetitorLock.locked_motion_energy() additive accessor (05-01 Task 3)"
  - "ActionHoldParams config sub-model (05-01)"
provides:
  - "segugio.orchestrator.action_hold.ActionHoldDeriver (D-08 motion energy -> HoldInput.action)"
  - "segugio.orchestrator.loop.Orchestrator (fixed-rate fault-isolated tick; RBT-04/05, D-08/09/10/11)"
  - "Orchestrator.from_config factory; run() live loop; run_measured(n_ticks) latency harness; shutdown()"
affects:
  - "tests/test_imports.py (segugio.orchestrator joins the lazy-import surface)"
tech-stack:
  added: []
  patterns:
    - "Grown-up run_clip_eval: per-camera fan-out (one tracker/lock/gate per cam, never a frame list, #13107)"
    - "Try/except EVERY stage -> coast to SAFE, never crash (RBT-04 / Pitfall 7)"
    - "Injected per-camera trackers (heavy YOLO stays out of headless tests); locks+gates built from config"
    - "Additive perf_counter latency probe in run_measured (no pipeline-logic change, RBT-05)"
    - "Tick-derived `now` in run_measured for deterministic off-GPU liveness; time.monotonic in run()"
key-files:
  created:
    - "src/segugio/orchestrator/__init__.py"
    - "src/segugio/orchestrator/action_hold.py"
    - "src/segugio/orchestrator/loop.py"
  modified:
    - "tests/test_action_hold.py"
    - "tests/test_status_channel.py"
    - "tests/test_fault_isolation.py"
    - "tests/test_latency.py"
    - "tests/test_imports.py"
decisions:
  - "D-09 STOP parks on the SAFE SENTINEL (engine.to_safe() + synthetic SAFE Decision), not by forcing the safe camera — so status.live_cam reads 'SAFE' not a cam id; Override still wins (top tier, RBT-03)"
  - "Per-camera trackers are INJECTED into the Orchestrator (not built internally) so headless tests inject fakes and YOLO loads only in real wiring; CompetitorLock + PlausibilityGate are pure/light so they are built from config inside the loop"
  - "_arrays_from_results is duplicated locally in loop.py (not imported from tracking/eval.py) so the loop never imports the cv2-edge module — preserves the lazy boundary"
  - "Latency probe attributes the per-camera fan-out time to the 'yolo' stage (dominant inference cost); 'ingest' is nominal/0 (source.latest is O(1); the network cost is off-tick on a receiver thread)"
metrics:
  duration: 10min
  tasks: 3
  files: 8
  completed: 2026-06-11
---

# Phase 5 Plan 6: Fixed-Rate Fault-Isolated Orchestrator Tick Summary

The live `Orchestrator` wires every locked Phase 1-4 brain into ONE fixed-rate, fault-isolated tick — the grown-up `run_clip_eval` — that derives the D-08 action-hold from locked-subject motion energy, degrades to SAFE on any fault without ever crashing (RBT-04), writes the D-11 live status, and measures decision-loop latency under budget (RBT-05). This closes the v1 milestone.

## What Was Built

### Task 1 — `ActionHoldDeriver` (D-08, the core-value defense)
`src/segugio/orchestrator/action_hold.py` — a PURE, clock-free, stdlib-only deriver. The orchestrator injects the locked subject's per-tick motion energy (`CompetitorLock.locked_motion_energy()`); the deriver maintains a small sustained-count of consecutive ticks where `energy >= ActionHoldParams.motion_threshold` and emits `HoldInput(action=True)` once the count reaches `window_ticks`. `occlusion` is ALWAYS `False` (deferred in v1, D-08). A dip below threshold resets the streak. The integration test feeds `HoldInput(action=True)` into a REAL `DecisionEngine.tick` and proves a qualified `auto_switch` cut is HELD (`reason == "hold"`) for exactly `action_hold_cap_ticks` ticks, then force-releases at the DEC-03 max-cap (the cut fires, `reason == "auto_switch"`).

### Task 2 — `Orchestrator` tick (RBT-04, D-09/10/11)
`src/segugio/orchestrator/loop.py` — `class Orchestrator` constructed with `(config, source, obs, scorer, engine, watchdog, action_hold, channel_paths, trackers)` plus a `from_config(...)` factory that builds the scorer/engine/watchdog/deriver from the validated `Config`. Per tick:

- **Per-camera independence** — one `CompetitorLock` + one `PlausibilityGate` per `cam.id` (built from config); the `PerCameraTracker`s are injected. Each tracker is driven with ONE frame (never a frame list, #13107 — asserted by a test).
- **The exact `run_clip_eval` fan-out** — `source.latest(cam) -> tracker.track -> _arrays_from_results -> signals_from_boxes -> CompetitorLock.select -> (CR-01 gate-reset only on a genuine re-acquire) -> PlausibilityGate.check -> DetectionSignal | None`, accumulated into the `MultiCamScorer.update` consumer map.
- **The once-before-loop HARD ReID gate** — `assert_native_reid_engaged` is called ONCE after a warmup that actually ran inference (`results is not None`), only on the real tracker (`hasattr(tracker, "model")`); RAISES on the silent cls fallback (TRK-02).
- **Downstream** — action-hold derived from the max locked-motion-energy over cameras; `scorer.update`; `watchdog.alive_map(now, source, cam_ids)`; `read_runstate`/`read_command` (D-09 START resets locks, STOP parks on the SAFE sentinel, Override wins); `engine.tick`; `_apply` cuts OBS via `scene_for` and writes the D-11 status on change.
- **Fault isolation (RBT-04)** — every tick stage is inside one try/except → log → `_to_safe(...)` coast; the process never exits. `shutdown()` cuts to SAFE, stops the source, closes OBS (each best-effort, never raises).

### Task 3 — Latency harness (RBT-05)
`run_measured(n_ticks)` instruments each stage (ingest/yolo/score/fsm/obs + total) with `perf_counter` deltas ADDITIVELY (no pipeline-logic change) and returns the timings. `tests/test_latency.py`: a MOCK-TIMED test asserts wiring-overhead total p95 < 50ms off-GPU (and that a fixed inference cost lands in the 'yolo' stage), and a `@pytest.mark.gpu` test runs the real `yolo26s.pt` and asserts total p95 < 150ms. The degradation ladder (yolo26n → fewer cams → lower imgsz/fps) is logged for the on-Windows run to act on.

## Verification

- `python -m pytest tests/test_action_hold.py tests/test_status_channel.py tests/test_fault_isolation.py tests/test_latency.py -m "not gpu"` → **15 passed, 1 deselected (gpu)**.
- `python -m pytest tests/ -m "not gpu and not ndi and not obs"` → **291 passed, 3 skipped, 0 failed** (zero regression on Phases 1-4).
- `python -c "import segugio.orchestrator.loop, segugio.orchestrator.action_hold"` succeeds with cyndilib/obsws/Flask/torch/ultralytics absent (heavy-absent smoke test green; `segugio.orchestrator` added to the surface).
- The gpu latency test is collected and skipped off-GPU via the conftest gpu hook (1 skipped).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] D-09 STOP park mechanism changed from force-safe-camera to SAFE-sentinel**
- **Found during:** Task 2 (status-channel test failed: `live_cam` was the safe camera id, not `"SAFE"`).
- **Issue:** The RESEARCH sketch suggested forcing the SAFE target while STOP is latched. Forcing the is_safe *camera* through the OVERRIDE surface set `decision.target` to the camera id, so the D-11 status reported `live_cam = cam_wide` instead of the SAFE sentinel — the panel could not distinguish "parked between runs" from "auto picked the wide cam".
- **Fix:** While STOPPED with no live override, the loop calls `engine.to_safe()` (advancing the FSM coherently for the next START) and returns a synthetic SAFE `Decision`, so the status/cut report the SAFE sentinel. A live override during STOP still runs the normal `engine.tick` (Override is the top tier, RBT-03). No new FSM state (honors D-09 / RESEARCH OQ3 discretion).
- **Files modified:** `src/segugio/orchestrator/loop.py` (`_decide`).
- **Commit:** c60df51

**2. [Rule 2 - Critical wiring] Injected per-camera trackers + local `_arrays_from_results`**
- **Found during:** Task 2 design.
- **Issue:** Building `PerCameraTracker`s inside the loop would load YOLO at construction (heavy import) and importing `_arrays_from_results` from `tracking/eval.py` would pull the cv2-edge module — both breaking the lazy-import boundary for headless tests.
- **Fix:** Trackers are injected (`{cam_id: tracker}`); the headless tests inject fakes. `_arrays_from_results` is duplicated locally in `loop.py` (byte-for-byte the eval contract) so the loop never imports the cv2 edge. The ReID gate + dog-index resolution run only when `hasattr(tracker, "model")` (the real tracker), so fakes skip them cleanly.
- **Files modified:** `src/segugio/orchestrator/loop.py`.
- **Commit:** c60df51

## Self-Check: PASSED

- `src/segugio/orchestrator/__init__.py` — FOUND
- `src/segugio/orchestrator/action_hold.py` — FOUND
- `src/segugio/orchestrator/loop.py` — FOUND
- commit 1312e5d (test action-hold RED) — FOUND
- commit fa217cf (feat action-hold GREEN) — FOUND
- commit 4e041f6 (test orchestrator RED) — FOUND
- commit c60df51 (feat Orchestrator GREEN) — FOUND
- commit a0cb6a7 (test latency harness) — FOUND

## TDD Gate Compliance

- Task 1: `test(05-06)` RED (1312e5d) → `feat(05-06)` GREEN (fa217cf). Gate sequence satisfied.
- Task 2: `test(05-06)` RED (4e041f6) → `feat(05-06)` GREEN (c60df51). Gate sequence satisfied.
- Task 3 (`type="auto"`, not TDD): the latency probe was added additively to `loop.py` in Task 2; the test landed in a0cb6a7. No behavior-adding source change in Task 3.

## Notes for the Windows/RTX E2E run (D-01/D-07)

- Run `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada to record the real total p95 (< 150ms; target < 80ms). If over budget, apply the logged degradation ladder.
- The full human E2E (mock-sender NDI → cyndilib → YOLO → score → FSM → real OBS cut/PIP/overlay → pull a feed → watchdog → SAFE) exercises the same `Orchestrator.run()` with the real `FrameSource`/`ObsController`/`PerCameraTracker` injected — the heavy clients live only inside those injected impls.
