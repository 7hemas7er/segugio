---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
verified: 2026-06-11T12:00:00Z
status: gaps_found
score: 4/5
overrides_applied: 0
re_verification: false
gaps:
  - truth: "The orchestrator runs a fixed-rate tick ... shuts down to the SAFE scene, never crashes the process"
    status: failed
    reason: "CR-01: source.start() and obs.connect() are called OUTSIDE the try/except fault sink in both run() (lines 453-454) and run_measured() (lines 481-482). If OBS is down at launch (a normal field condition), obs.connect() raises ConnectionError and the process exits before the tick loop ever starts — the never-crash contract breaks at its most exposed point."
    artifacts:
      - path: "src/segugio/orchestrator/loop.py"
        issue: "run(): lines 453-454 call source.start()/obs.connect() before the try block. run_measured(): lines 481-482 are identical. _cache_pip_ids() inside connect() is also unguarded."
    missing:
      - "Wrap source.start() and obs.connect() in individual try/except in both run() and run_measured(), logging the exception and coasting (the OBS _safe_call already heals per-tick). Also guard _cache_pip_ids() inside ObsWsController.connect()."
human_verification:
  - test: "Real NDI receiver busy-spin (CR-02) — verify that when no NDI source is present the receiver thread does not consume a full CPU core (busy-spin on line 115 of ndi_source.py)"
    expected: "CPU usage for the receiver thread should be near-zero while waiting; the source should automatically reconnect once the named source appears without requiring a stop()/start() cycle"
    why_human: "Requires Windows hardware with cyndilib installed and a real/mock NDI source to connect and disconnect. Cannot be tested headless. The busy-spin is confirmed by code review (line 115: bare `continue` with no sleep); its impact on the <150ms AI loop budget requires measurement."
  - test: "Real OBS controller startup crash (CR-01) — verify on the Windows box that the director survives OBS being down at launch"
    expected: "python -m segugio (or Orchestrator.run()) should start without crashing even when OBS is not yet running, and should reconnect once OBS starts"
    why_human: "CR-01 is confirmed by code inspection as not fixed. The headless fault-isolation test (test_fault_isolation.py) uses an injected fake that does not exercise the real startup path — so the fix must be verified on the real wiring."
  - test: "Anti-jitter grace in production (WR-02) — verify the watchdog anti-jitter protection is actually active"
    expected: "A live field run should not exhibit cut storms on a mildly jittery feed (single frames arriving late); the grace should provide a few ticks of tolerance"
    why_human: "grace=0.0 is confirmed in from_config (line 190/220 of loop.py). The code is correct but the default is wrong for live operation. The fix (non-zero default or config sourcing) is straightforward but the correct value depends on measured frame-rate jitter on the real hardware."
  - test: "E2E real-stack run: mock NDI sender -> cyndilib receiver -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> pull a feed -> watchdog -> SAFE (D-07)"
    expected: "Full end-to-end loop works on the Windows/RTX box with the real NDI, obsws, and CUDA stack"
    why_human: "cyndilib, obsws-python, and cv2 are absent in the dev environment; the real NDI and OBS paths are gated behind @pytest.mark.ndi/@pytest.mark.obs and require the Windows E2E box (D-07). The headless tests prove the logic; the hardware integration is deferred to the on-Windows run."
  - test: "GPU latency budget (RBT-05) — run python -m pytest tests/test_latency.py -m gpu on the RTX 4000 Ada"
    expected: "Decision-loop p95 < 150ms (target <80ms). If over budget, apply the degradation ladder (yolo26n -> fewer cameras -> lower imgsz/fps) logged in loop.py."
    why_human: "GPU is absent in the dev environment. The @pytest.mark.gpu test exists (collected, skipped off-GPU) and the wiring-overhead mock-timed test passes headless. Real numbers require the Windows/RTX box."
---

# Phase 5: Integration (NDI Mock, Orchestrator, OBS, Score UI) Verification Report

**Phase Goal:** Everything wires together end-to-end with no hardware, closing the v1 milestone: a mock NDI source feeds clips through cyndilib ingest, a timestamp-based watchdog drives automatic fallback, an OBS controller cuts scenes and PIP and updates overlays, a manual score-entry UI writes atomically to an OBS read-from-file text source, and a fault-isolated orchestrator ticks the full frame->YOLO->score->FSM->OBS loop within the latency budget and shuts down to SAFE without ever crashing.

**Verified:** 2026-06-11
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Mock NDI source (ClipReplayFrameSource) publishes named clips; cyndilib FrameSource (NdiFrameSource) delivers numpy BGR per camera on supervised threads with empty-frame guard | VERIFIED | `src/segugio/ndi/clip_source.py` (ClipReplayFrameSource, zero-size skip), `src/segugio/ndi/ndi_source.py` (NdiFrameSource, _receiver_loop, min(xres,yres)!=0 guard, ts!=last_ts NEW-frame liveness). `test_frame_source_empty_guard.py` (2 passing). Real NDI path gated behind @pytest.mark.ndi (collected, skipped). |
| 2 | OBS controller cuts program scene, toggles PIP via cached numeric sceneItemId, reconnects on drop, EventClient observes manual scene changes | VERIFIED | `src/segugio/obs/obsws_controller.py` (set_current_program_scene, get_scene_item_id, set_scene_item_enabled, callback.register). `src/segugio/obs/recording_fake.py` (RecordingObsController). `obs/segugio-scene-collection.json` (CAM Wide/Long/Low/Handler + SAFE). Tests: `test_obs_mapping.py` (2 passing), `test_obs_reconnect.py` (2 passing), `test_overlay.py` (2 passing), `test_scene_template.py` (3 passing). |
| 3 | Feed watchdog deduces liveness from last-NEW-frame timestamp; dead feed triggers fallback to SAFE; recovered feed rejoins only after full hysteresis+dwell | VERIFIED | `src/segugio/watchdog_feed/liveness.py` (FeedWatchdog, `now - last_frame_ts <= _dead_after`, fail-safe on None). Tests: `test_watchdog.py` (8 passing), `test_fallback_rejoin.py` (3 passing against real DecisionEngine). |
| 4 | Score UI offers discipline selector + 3 field sets + run start/stop; writes atomically; system displays scores only | VERIFIED | `src/segugio/ui/app.py` (create_app, POST /score/run/command, GET /status). `src/segugio/ui/score_render.py` (render_overlay_text, no arithmetic). `src/segugio/ui/templates/console.html` (Disciplina, Avvia run, Ferma run, Forza, Rilascia, Stato live). Tests: `test_ui_score.py` (6 passing), `test_ui_run.py` (8 passing), `test_score_display_only.py` (7 passing, AST no-adjudication guard). |
| 5 | Orchestrator ticks full loop with fault isolation (try/except), shuts down to SAFE, never crashes, decision loop under ~150ms | FAILED | The fault-isolation-per-tick and SAFE shutdown are verified. The startup path is NOT fault-isolated: `run()` lines 453-454 and `run_measured()` lines 481-482 call `source.start()` and `obs.connect()` BEFORE the try block. If OBS is down at launch, `obs.connect()` raises and the process exits. This is CR-01 from the code review, confirmed in code. The headless fault isolation tests pass because they inject fakes that do not test the startup path. Latency wiring is proven headless (mock-timed p95 < 50ms overhead); GPU real numbers require Windows/RTX box (D-07). |

**Score: 4/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ndi/clip_source.py` | In-process clip-replay FrameSource (headless mock) | VERIFIED | Contains `ClipReplayFrameSource`, `def latest`, `getattr(frame, "size", 0) == 0` empty-frame guard |
| `src/segugio/ndi/ndi_source.py` | Real cyndilib FrameSource (1 thread/cam, lazy import) | VERIFIED | Contains `NdiFrameSource`, `def _receiver_loop`, `get_timestamp_posix`, `min(xres,yres)!=0` guard, `ts != last_ts` liveness |
| `src/segugio/ndi/mock_sender.py` | NDI-02 named-source Sender (E2E only, lazy import) | VERIFIED | Contains `def publish_clip`; A2 [ASSUMED] caveat documented |
| `src/segugio/obs/obsws_controller.py` | Real obsws-python v5 controller (lazy import) | VERIFIED | Contains `set_current_program_scene`, `get_scene_item_id`, `set_scene_item_enabled`, `set_input_settings`, `callback.register` |
| `src/segugio/obs/recording_fake.py` | RecordingObsController headless test double | VERIFIED | Contains `class RecordingObsController` with `self.calls` capture |
| `obs/segugio-scene-collection.json` | OBS scene-collection template (CAM*/SAFE) | VERIFIED | Scenes: CAM Wide, CAM Long, CAM Low, CAM Handler, SAFE, MULTIVIEW, PIP. Verified by `test_scene_template.py` cross-referencing both example configs. |
| `src/segugio/watchdog_feed/liveness.py` | FeedWatchdog pure liveness math | VERIFIED | Contains `class FeedWatchdog`, reads `watchdog_timeout`, clock-free |
| `src/segugio/opcomm/atomic.py` | Atomic write (temp+fsync+os.replace) | VERIFIED | Contains `os.replace` (via `_atomic_replace` retry), `os.fsync`. NOTE: `atomic_write_text` uses bare `os.replace` (WR-04) — not `_atomic_replace`. |
| `src/segugio/opcomm/records.py` | Frozen ScoreDoc/RunState/OperatorCommand/DirectorStatus | VERIFIED | Contains `frozen=True`, Discipline Enum, OperatorCommand force-XOR-release guard |
| `src/segugio/opcomm/channel.py` | Boundary-validated typed channel (never raises) | VERIFIED | `read_*` wraps in try/except, returns defaults, never raises |
| `src/segugio/ui/app.py` | Flask console (Flask + opcomm only) | VERIFIED | Contains `Flask`, `write_score/write_runstate/write_command`. Flask imported INSIDE `create_app` (lazy boundary). |
| `src/segugio/ui/score_render.py` | Pure display-only overlay renderer | VERIFIED | Contains `def render_overlay_text`, stdlib-only, no arithmetic |
| `src/segugio/ui/templates/console.html` | Italian operator console page | VERIFIED | Contains "Disciplina", "Avvia run", "Ferma run", "Forza", "Rilascia", "Stato live" |
| `src/segugio/orchestrator/loop.py` | Orchestrator fixed-rate tick, fault isolation | PARTIAL | Contains `class Orchestrator`, per-camera fan-out, `_tick_once` try/except, SAFE shutdown. CR-01: `source.start()`/`obs.connect()` unguarded at startup in both `run()` and `run_measured()`. |
| `src/segugio/orchestrator/action_hold.py` | ActionHoldDeriver D-08 motion->HoldInput | VERIFIED | Contains `ActionHoldDeriver`, `HoldInput`, `motion_threshold`/`window_ticks` usage |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ndi/clip_source.py` | `FrameSource.latest` | ClipReplayFrameSource.latest() | VERIFIED | Implements the Protocol; test drives it headless |
| `ndi/ndi_source.py` | `get_timestamp_posix` | NEW-frame liveness stamp (ts != last_ts) | VERIFIED | Line 119 in _receiver_loop |
| `obs/obsws_controller.py` | `get_scene_item_id` (cached) | _cache_pip_ids resolves once at connect | VERIFIED | Lines 123-132 in connect() |
| `watchdog_feed/liveness.py` | `Thresholds.watchdog_timeout` | `dead if ts not advanced for > watchdog_timeout` | VERIFIED | Line 220: `FeedWatchdog(config.thresholds.watchdog_timeout, grace=grace)` |
| `watchdog alive map` | `DecisionEngine.tick(scores, alive, ...)` | `alive[cam]=False -> excluded (DEC-06) -> SAFE/other-live fallback` | VERIFIED | Proven by `test_fallback_rejoin.py` (3 tests) against real DecisionEngine |
| `ui/app.py` | `segugio.opcomm.channel write_score/write_runstate/write_command` | POST endpoints -> atomic file writes | VERIFIED | All three POST handlers call the respective channel writes |
| `orchestrator/loop.py` | `DecisionEngine.tick(scores, alive, holds, override)` | scorer + watchdog + action-hold + operator-command | VERIFIED | `_tick_once` lines 403-418 |
| `orchestrator/action_hold.py` | `CompetitorLock.locked_motion_energy()` | threshold over ActionHoldParams.motion_threshold sustained window_ticks | VERIFIED | `action_hold.py` line 83 (`locked_motion_energy >= self._threshold`) |
| `orchestrator/loop.py` | `opcomm status.json` | atomic status write on change (D-11) | VERIFIED | `_apply` calls `write_status` on change; `_to_safe` also writes status |
| `run()` / `run_measured()` startup | fault-isolated try block | source.start()/obs.connect() inside try | NOT_WIRED | Both methods call start()/connect() BEFORE the `try:` block (CR-01 confirmed) |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ui/app.py` | `ScoreDoc.fields` | operator POST form → `request.form` | Yes — operator-entered values written atomically | FLOWING |
| `ui/app.py` | `DirectorStatus` (GET /status) | `read_status(status_path)` → opcomm channel | Yes — reads atomic file written by orchestrator each tick | FLOWING |
| `orchestrator/loop.py` | `alive` map | `watchdog.alive_map(now, source, cam_ids)` | Yes — per-camera `last_frame_ts` from mock FrameSource | FLOWING |
| `orchestrator/loop.py` | `decision` | `engine.tick(scores, alive, holds, override)` | Yes — real DecisionEngine with real scores/alive map | FLOWING |
| `watchdog_feed/liveness.py` | `last_frame_ts` | injected `frame_source.last_frame_ts(cam_id)` | Yes — real per-camera timestamps from ClipReplayFrameSource | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All headless Phase-5 tests pass | `python -m pytest -q -m "not gpu and not ndi and not obs"` | 291 passed, 3 skipped, 6 deselected in 6.90s | PASS |
| All light imports succeed without heavy deps | `python -c "import segugio.opcomm, segugio.ndi, segugio.obs, segugio.watchdog_feed, segugio.orchestrator.loop, segugio.ui, segugio.ui.app, segugio.ui.score_render"` | OK | PASS |
| Key Phase-5 tests (fault isolation, latency, action-hold, watchdog, fallback, atomic IO, OBS, scene template, UI, status) | `python -m pytest tests/test_fault_isolation.py tests/test_latency.py tests/test_action_hold.py tests/test_watchdog.py tests/test_fallback_rejoin.py tests/test_atomic_io.py tests/test_obs_mapping.py tests/test_scene_template.py tests/test_ui_score.py tests/test_ui_run.py tests/test_score_display_only.py tests/test_status_channel.py` | 60 passed, 1 skipped (gpu) | PASS |
| No `xfail impl pending` stubs remain in test suite | grep for "xfail.*impl pending" in tests/ | 0 matches — all Wave-0 stubs flipped to real assertions | PASS |
| GPU latency test (RBT-05) | `python -m pytest tests/test_latency.py -m gpu` | SKIPPED off-GPU (collected, skipped 1) | SKIP (requires Windows/RTX box, D-07) |

---

### Probe Execution

No explicit `probe-*.sh` probes declared or found for this phase. The equivalent is the pytest suite above.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NDI-01 | 05-02 | Cyndilib Finder/Receiver/FrameSync -> numpy BGR, supervised threads | VERIFIED | NdiFrameSource _receiver_loop; headless: ClipReplayFrameSource; test_frame_source_empty_guard.py |
| NDI-02 | 05-02 | Mock NDI Sender publishes clips as named NDI sources | VERIFIED | mock_sender.publish_clip; @pytest.mark.ndi E2E test (skipped, real-NDI only) |
| NDI-03 | 05-02 | Guard on empty first frames (skip zero-size) | VERIFIED | min(xres,yres)!=0 (real); getattr(frame,"size",0)==0 (mock); test_frame_source_empty_guard.py (2 passing) |
| OBS-01 | 05-03 | Cut program scene via SetCurrentProgramScene | VERIFIED | obsws_controller.py `set_current_program_scene`; test_obs_mapping.py |
| OBS-02 | 05-03 | PIP via cached numeric sceneItemId | VERIFIED | _cache_pip_ids resolves once at connect; test_obs_mapping.py::test_pip_cached_id |
| OBS-03 | 05-03 | Persistent connection with reconnect+reauth; EventClient syncs manual changes | VERIFIED | _safe_call reconnects once on failure; EventClient _on_scene_changed registered; test_obs_reconnect.py |
| OBS-04 | 05-03 | OBS scene-collection template (CAM*/SAFE/MULTIVIEW/PIP) | VERIFIED | obs/segugio-scene-collection.json; test_scene_template.py (3 passing, both example configs) |
| OBS-05 | 05-03 | Overlay via read-from-file (primary) + SetInputSettings one-shot fallback | VERIFIED | read-from-file: score_render/atomic_write_text; set_input_settings fallback in obsws_controller.py; test_overlay.py |
| SCR-01 | 05-01 | Score file written atomically (temp + os.replace) | VERIFIED | atomic.py _atomic_replace; test_atomic_io.py (8 passing). NOTE: atomic_write_text uses bare os.replace (WR-04, not a hard requirement gap) |
| SCR-02 | 05-05 | Manual score UI: discipline selector + 3 field sets | VERIFIED | console.html (3 field sets); test_ui_score.py (6 passing) |
| SCR-03 | 05-05 | Run start/stop resets overlay, starts/stops timer | VERIFIED | POST /run -> RunState(just_started/just_stopped); test_ui_run.py (8 passing) |
| SCR-04 | 05-05 | System displays scores only, no adjudication | VERIFIED | score_render formats verbatim; AST guard test in test_score_display_only.py (7 passing) |
| RBT-01 | 05-04 | Watchdog from last-NEW-frame timestamp only (never NDI state) | VERIFIED | FeedWatchdog alive(); ts!=last_ts in ndi_source.py; test_watchdog.py (8 passing) |
| RBT-02 | 05-04 | Feed fallback to SAFE; guarded rejoin | VERIFIED | test_fallback_rejoin.py (3 passing against real DecisionEngine) |
| RBT-04 | 05-06 | Fixed-rate tick, fault isolation, SAFE shutdown, never crashes | PARTIAL | Per-tick try/except and SAFE shutdown are implemented and tested. CR-01 BLOCKER: source.start()/obs.connect() unguarded at startup — a down OBS crashes the director before the tick loop starts. test_fault_isolation.py passes because fakes do not test startup. |
| RBT-05 | 05-06 | Decision loop < ~150ms (target <80ms) | PARTIAL | Wiring overhead proven headless (mock-timed p95 < 50ms). Real GPU numbers require Windows/RTX box (D-07); @pytest.mark.gpu test exists, collected, skipped. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/orchestrator/loop.py` | 453-454, 481-482 | `source.start()` / `obs.connect()` before `try:` block in `run()` and `run_measured()` | BLOCKER | Startup crash if OBS is down at launch — breaks the "never crashes" contract (RBT-04, CR-01 from code review) |
| `src/segugio/orchestrator/loop.py` | 350, 352 | Dead variable `live_cam` computed but `DirectorStatus(live_cam=target, ...)` passed | WARNING | `live_cam` variable vs. docstring mismatch. Shipped behavior is intentional (`"SAFE"` sentinel passed through). Tests assert `"SAFE"`, so behavior is correct but code is misleading (WR-01). |
| `src/segugio/orchestrator/loop.py` | 190, 220 | `grace=0.0` default in `from_config` — anti-jitter protection off in production | WARNING | A single late frame (at `watchdog_timeout + 1ms`) immediately declares feed dead, risking cut storms on a jittery field feed (WR-02). |
| `src/segugio/opcomm/atomic.py` | 93 | `atomic_write_text` uses bare `os.replace(tmp, path)` instead of `_atomic_replace` | WARNING | OBS reads the overlay file continuously; Windows PermissionError on sharing-violation is possible when OBS holds the file open. `atomic_write_json` has the retry; text path does not (WR-04). |
| `src/segugio/ndi/ndi_source.py` | 114-115 | Busy-spin `while not self._stop.is_set(): if not receiver.is_connected(): continue` — no sleep | WARNING | Pins a full CPU core per camera while disconnected/unresolved. Also: if the source is absent at thread start, it never reconnects without a stop/start cycle (CR-02). |
| `src/segugio/orchestrator/loop.py` | 430-432 | `_to_safe(reason="feed-dead")` in the catch-all — wrong reason for non-feed faults | INFO | Mislabels scorer/FSM/OBS crashes as "feed-dead" in the operator status panel (WR-09). |

---

### Human Verification Required

#### 1. Real OBS startup crash (CR-01 — BLOCKER confirmation on real stack)

**Test:** Start the orchestrator (`Orchestrator.run()`) on the Windows box WITHOUT OBS running. Then start OBS and verify the director reconnects automatically.
**Expected:** The process should NOT crash when OBS is down at launch; it should log a warning and begin ticking (connecting on retry via `_safe_call`).
**Why human:** CR-01 is confirmed by code inspection. The headless `test_fault_isolation.py` uses injected fakes that never call the real `obs.connect()`. This requires the real `obsws-python` / OBS stack to reproduce.

#### 2. Real NDI receiver busy-spin (CR-02)

**Test:** On the Windows box with cyndilib installed, start `NdiFrameSource` for 4 cameras when no NDI sources are present. Monitor CPU usage for the receiver threads. Then bring up a mock NDI source and verify automatic reconnection.
**Expected:** CPU for disconnected receiver threads should be near-zero (not 100%). Source should reconnect automatically when it appears, without requiring `stop()`/`start()`.
**Why human:** CR-02 is confirmed by code inspection (line 115: bare `continue`). Requires Windows + cyndilib + an NDI source to test. CPU impact on the <150ms AI-loop budget also needs measurement.

#### 3. Anti-jitter grace in production (WR-02)

**Test:** On the Windows box with a real or mock NDI source, induce a jittery feed (frames arriving 900ms apart — just over `watchdog_timeout=0.8s`) and observe whether the director cut-storms.
**Expected:** With `grace=0.0` the feed will be declared dead and cause fallback; with a non-zero grace (e.g. `2/fps = 0.067s`) single-late-frame jitter should be tolerated.
**Why human:** The correct grace value depends on measured jitter characteristics of the real hardware; the code fix (non-zero default) is straightforward but the value to ship needs empirical guidance.

#### 4. Full E2E real-stack run (D-07)

**Test:** On the Windows/RTX box: start the mock NDI sender (`publish_clip`), confirm cyndilib receives it, start OBS with the scene-collection template, run the orchestrator, verify scene cuts, trigger a feed death, verify SAFE fallback, open the Flask console and enter scores, confirm OBS overlay updates.
**Expected:** All real-stack paths work end-to-end; the OBS overlay shows operator-entered scores; feed death causes automatic SAFE fallback; UI status panel shows live camera and reason.
**Why human:** cyndilib, obsws-python, and cv2 are absent in the dev environment. The @pytest.mark.ndi and @pytest.mark.obs paths are real assertions that auto-skip headless.

#### 5. GPU latency budget (RBT-05)

**Test:** `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with `yolo26s.pt` and real clip frames.
**Expected:** Total decision-loop p95 < 150ms (target <80ms). If over budget, apply the degradation ladder logged in `loop.py` `_DEGRADATION_LADDER`.
**Why human:** No GPU in the dev environment. The @pytest.mark.gpu test exists and is collected; the wiring-overhead mock-timed test passes headless at p95 < 50ms.

---

### Gaps Summary

One BLOCKER gap blocks the "never crashes" success criterion (SC-5 / RBT-04):

**CR-01 — Startup outside the fault sink:** In `Orchestrator.run()` (lines 453-454) and `Orchestrator.run_measured()` (lines 481-482), `source.start()` and `obs.connect()` are called before the `try:` / `finally:` block. A `ConnectionError` from `obs.connect()` (OBS not yet started — a normal field condition) propagates unhandled and exits the process. The "never crashes" contract is the most fundamental of the phase requirements (stated literally in SC-5 and RBT-04). The headless `test_fault_isolation.py` passes because injected fakes do not raise in their connect methods, so the gap was not caught by the test suite.

The fix is small and surgical: wrap `source.start()` and `obs.connect()` in individual `try/except` in both methods, logging the exception and coasting (the per-tick `_safe_call` in `ObsWsController` already handles per-tick OBS reconnection). Also guard `_cache_pip_ids()` inside `ObsWsController.connect()`.

No other must-haves are FAILED. The four passing truths (NDI ingest, OBS controller, watchdog+fallback, score UI) are all substantively implemented, wired, and tested. The latency claim is proven headless (mock-timed wiring overhead) and verified to the GPU by a collected but deferred test (D-07).

The code review's WR-02 (grace=0.0), WR-04 (atomic_write_text missing retry), CR-02 (busy-spin), WR-01 (dead variable), and WR-09 (wrong fault reason) are real code quality issues that should be fixed before the hardware milestone, but they do not individually block the headless phase goal claims — they affect the real-stack path. Human verification items 2, 3, and 4 cover them.

---

_Verified: 2026-06-11_
_Verifier: Claude (gsd-verifier)_
