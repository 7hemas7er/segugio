---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
verified: 2026-06-11T14:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Orchestrator run()/run_measured() startup is now fault-isolated via _safe_startup: a down OBS (ConnectionError) or down NDI (RuntimeError) at launch is caught, logged, and the tick loop still runs — CR-01 / SC-5 / RBT-04 VERIFIED"
    - "WR-02: watchdog_grace default is now 0.067 (non-zero) sourced from Thresholds; from_config sources it when grace=None so anti-jitter is active by default"
    - "WR-04: atomic_write_text now routes through _atomic_replace bounded-retry (same path as atomic_write_json), protecting against Windows PermissionError sharing-violation when OBS holds the overlay file open"
    - "WR-09: tick catch-all now reports reason='fault' (not 'feed-dead') for non-feed exceptions"
    - "WR-01: dead live_cam local variable removed from _status_for"
    - "CR-02: NDI receiver disconnected branch no longer busy-spins — it sleeps _RECEIVER_DISCONNECTED_SLEEP_S (0.05s) and re-resolves the named source for auto-reconnect without stop()/start()"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Real NDI receiver auto-reconnect and CPU (CR-02 code fixed, real behavior hardware-deferred)"
    expected: "CPU usage for disconnected receiver threads near-zero; source auto-reconnects when the named NDI source appears without stop()/start()"
    why_human: "Requires Windows hardware with cyndilib installed and a live/mock NDI source. The headless test proves the sleep+re-resolve LOGIC but the real cyndilib connection timing (WR-02 livelock risk when set_source is called repeatedly mid-handshake, per post-gap-review) requires hardware measurement."
  - test: "Real OBS startup with orchestrator — confirm _safe_startup works on the live obsws stack"
    expected: "python -m segugio starts without crashing when OBS is not yet running; director ticks; reconnects once OBS starts"
    why_human: "obsws-python is absent in dev. The headless test (test_run_measured_survives_connect_raising) drives the REAL _safe_startup code path with a ConnectionError-raising fake — the logic is verified. On-Windows confirmation of the real websocket stack completing the same path is D-07."
  - test: "Anti-jitter grace empirical value (WR-02 code fixed to 0.067, empirical tuning hardware-deferred)"
    expected: "The shipped 0.067 grace (≈2 frames @30fps) tolerates single-late-frame jitter on the real field hardware without cut-storms"
    why_human: "The correct grace depends on measured jitter characteristics of real WiFi phone feeds. The config default is non-zero and pinned by test; the hardware-measured value is a D-07 tuning concern."
  - test: "Full E2E real-stack run (D-07): mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update"
    expected: "All real-stack paths work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera and reason"
    why_human: "cyndilib, obsws-python, cv2, and CUDA/ultralytics are absent in dev. @pytest.mark.ndi and @pytest.mark.obs auto-skip. This is the v1 milestone on-Windows hardware validation (D-07)."
  - test: "GPU latency budget (RBT-05): python -m pytest tests/test_latency.py -m gpu on the RTX 4000 Ada with yolo26s.pt and real clip frames"
    expected: "Decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py."
    why_human: "No GPU in dev. The @pytest.mark.gpu test is collected and skipped headless. Wiring overhead is proven headless (mock-timed p95 < 50ms). Real GPU numbers require the Windows/RTX box."
---

# Phase 5: Integration (NDI Mock, Orchestrator, OBS, Score UI) Re-Verification Report

**Phase Goal:** Everything wires together end-to-end with no hardware, closing the v1 milestone: a mock NDI source feeds clips through cyndilib ingest, a timestamp-based watchdog drives automatic fallback, an OBS controller cuts scenes and PIP and updates overlays, a manual score-entry UI writes atomically to an OBS read-from-file text source, and a fault-isolated orchestrator ticks the full frame->YOLO->score->FSM->OBS loop within the latency budget and shuts down to SAFE without ever crashing.

**Verified:** 2026-06-11T14:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plans 05-07 and 05-08)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Mock NDI source (ClipReplayFrameSource) publishes named clips; cyndilib FrameSource (NdiFrameSource) delivers numpy BGR per camera on supervised threads with empty-frame guard | VERIFIED | `src/segugio/ndi/clip_source.py` (ClipReplayFrameSource, zero-size skip), `src/segugio/ndi/ndi_source.py` (NdiFrameSource, _run_receiver, min(xres,yres)!=0 guard, ts!=last_ts NEW-frame liveness). `test_frame_source_empty_guard.py` (2 passing). Real NDI path gated behind @pytest.mark.ndi. NO REGRESSION: ndi_source.py was modified by 05-08 (CR-02) — the guard and liveness logic at lines 155-165 are intact and unchanged. |
| 2 | OBS controller cuts program scene, toggles PIP via cached numeric sceneItemId, reconnects on drop, EventClient observes manual scene changes | VERIFIED | `src/segugio/obs/obsws_controller.py` (set_current_program_scene, _cache_pip_ids guarded by try/except, _on_scene_changed callback registered). `obs/segugio-scene-collection.json`. Tests: test_obs_mapping.py, test_obs_reconnect.py, test_overlay.py, test_scene_template.py (all pass in the 302 headless run). 05-07 modified obsws_controller.py — connect() guard is wired (lines 101-107). |
| 3 | Feed watchdog deduces liveness from last-NEW-frame timestamp; dead feed triggers fallback to SAFE; recovered feed rejoins only after full hysteresis+dwell | VERIFIED | `src/segugio/watchdog_feed/liveness.py`. WR-02 closed: `Thresholds.watchdog_grace = 0.067` (non-zero default confirmed: `python -c "from segugio.config.models import Thresholds; assert Thresholds().watchdog_grace > 0.0"` → 0.067). `from_config` sources it when grace=None (pinned by `test_from_config_grace_is_nonzero_by_default`). Tests: test_watchdog.py (8 passing), test_fallback_rejoin.py (3 passing). |
| 4 | Score UI offers discipline selector + 3 field sets + run start/stop; writes atomically; system displays scores only | VERIFIED | `src/segugio/ui/app.py`, `src/segugio/ui/score_render.py`, `src/segugio/ui/templates/console.html`. WR-04 closed: `atomic_write_text` routes through `_atomic_replace` bounded-retry (2 call sites confirmed by grep). Tests: test_ui_score.py (6), test_ui_run.py (8), test_score_display_only.py (7), test_atomic_io.py (10 including `test_atomic_write_text_retries_on_permission_error`). |
| 5 | Orchestrator ticks full loop with fault isolation (try/except), shuts down to SAFE, never crashes, decision loop under ~150ms | VERIFIED | CR-01 CLOSED: `_safe_startup` method at loop.py:453-465 wraps both `source.start()` (line 477/505) and `obs.connect()` (line 478/506) in both `run()` and `run_measured()`. A ConnectionError/RuntimeError at launch is caught, logged, and the loop ticks regardless. `test_run_measured_survives_connect_raising` (5 ticks after ConnectionError) and `test_run_measured_survives_source_start_raising` (5 ticks after RuntimeError) both pass — these drive the REAL _safe_startup code path with raising fakes (not a bypassed fake). WR-09: tick catch-all at line 442 uses `reason="fault"`, pinned by `test_non_feed_fault_reason_is_not_feed_dead`. WR-01: dead `live_cam` variable removed. Full headless suite: **302 passed, 3 skipped, 0 failures**. |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ndi/clip_source.py` | In-process clip-replay FrameSource (headless mock) | VERIFIED | Unchanged from initial verification |
| `src/segugio/ndi/ndi_source.py` | Real cyndilib FrameSource (1 thread/cam, lazy import) | VERIFIED | Modified by 05-08: _receiver_loop now extracts _run_receiver with sleep+re-resolve disconnected branch (no busy-spin). Guards, liveness logic unchanged. |
| `src/segugio/ndi/mock_sender.py` | NDI-02 named-source Sender (E2E only) | VERIFIED | Unchanged; E2E only under @pytest.mark.ndi |
| `src/segugio/obs/obsws_controller.py` | Real obsws-python v5 controller | VERIFIED | Modified by 05-07: _cache_pip_ids wrapped in try/except inside connect() (lines 101-107); _connected=True still reached. WARNING: _on_scene_items_changed is defined but never registered (WR-01 from post-gap review — does not block the "never crashes" contract, ids re-cache via _safe_call reconnect). |
| `src/segugio/obs/recording_fake.py` | RecordingObsController headless test double | VERIFIED | Unchanged |
| `obs/segugio-scene-collection.json` | OBS scene-collection template (CAM*/SAFE) | VERIFIED | Unchanged; test_scene_template.py passes |
| `src/segugio/watchdog_feed/liveness.py` | FeedWatchdog pure liveness math | VERIFIED | Unchanged; grace path now non-zero by default via Thresholds |
| `src/segugio/opcomm/atomic.py` | Atomic write (temp+fsync+os.replace) | VERIFIED | Modified by 05-08: atomic_write_text now uses _atomic_replace (line 96). Both json and text paths confirmed by grep (2 _atomic_replace call sites). |
| `src/segugio/opcomm/records.py` | Frozen ScoreDoc/RunState/OperatorCommand/DirectorStatus | VERIFIED | Unchanged |
| `src/segugio/opcomm/channel.py` | Boundary-validated typed channel (never raises) | VERIFIED | Unchanged |
| `src/segugio/ui/app.py` | Flask console | VERIFIED | Unchanged |
| `src/segugio/ui/score_render.py` | Pure display-only overlay renderer | VERIFIED | Unchanged |
| `src/segugio/ui/templates/console.html` | Italian operator console page | VERIFIED | Unchanged |
| `src/segugio/orchestrator/loop.py` | Orchestrator fixed-rate tick, fault isolation | VERIFIED | Modified by 05-07: `_safe_startup` added (lines 453-465); both `run()` and `run_measured()` call `_safe_startup` for source.start and obs.connect before the tick loop. CR-01 closed. |
| `src/segugio/config/models.py` | Thresholds with watchdog_grace | VERIFIED | Modified by 05-07: `watchdog_grace: float = 0.067` (ge=0.0) at line 113. |
| `tests/test_orchestrator_startup.py` | CR-01 regression test (5 tests) | VERIFIED | New file (05-07). 5 tests drive the REAL run_measured startup path with raising source/obs; all 5 pass. |
| `tests/test_ndi_receiver_loop.py` | CR-02 regression test (3 tests) | VERIFIED | New file (05-08). 3 tests drive _run_receiver with fake collaborators (sleep, re-resolve, bounded-stop); all 3 pass. |
| `src/segugio/orchestrator/action_hold.py` | ActionHoldDeriver D-08 | VERIFIED | Unchanged |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ndi/clip_source.py` | `FrameSource.latest` | ClipReplayFrameSource.latest() | VERIFIED | Unchanged |
| `ndi/ndi_source.py` | `get_timestamp_posix` | NEW-frame liveness stamp (ts != last_ts) | VERIFIED | Lines 156-165 in _run_receiver — unchanged by 05-08 refactor |
| `obs/obsws_controller.py` | `get_scene_item_id` (cached) | _cache_pip_ids guarded inside connect() | VERIFIED | Lines 101-107 in connect() — _cache_pip_ids failure coasts; ids re-cache on reconnect |
| `watchdog_feed/liveness.py` | `Thresholds.watchdog_grace` | `from_config(grace=None)` sources `config.thresholds.watchdog_grace` (0.067) | VERIFIED | `test_from_config_grace_is_nonzero_by_default` pins this path |
| `watchdog alive map` | `DecisionEngine.tick(scores, alive, ...)` | alive[cam]=False → excluded → SAFE/other-live fallback | VERIFIED | Unchanged; test_fallback_rejoin.py (3 passing) |
| `ui/app.py` | `segugio.opcomm.channel write_score/write_runstate/write_command` | POST endpoints → atomic file writes | VERIFIED | Unchanged |
| `orchestrator/loop.py` | `DecisionEngine.tick(scores, alive, holds, override)` | scorer + watchdog + action-hold + operator-command | VERIFIED | `_tick_once` lines 403-418 unchanged |
| `run()` / `run_measured()` startup | fault-isolated `_safe_startup` | source.start()/obs.connect() inside _safe_startup try/except BEFORE the tick loop | VERIFIED | Lines 477-478 (run) and 505-506 (run_measured) confirmed. THIS IS THE CR-01 FIX. |
| `opcomm/atomic.py` | `_atomic_replace` retry | `atomic_write_text` routes through `_atomic_replace(tmp, path)` at line 96 | VERIFIED | Confirmed by grep: 2 _atomic_replace call sites in atomic.py (json + text) |
| `ndi/ndi_source.py` `_run_receiver` | `time.sleep(_RECEIVER_DISCONNECTED_SLEEP_S)` | disconnected branch sleeps 0.05s then re-resolves source | VERIFIED | Lines 146-151 in _run_receiver; test_ndi_receiver_loop.py drives and asserts the sleep |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ui/app.py` | `ScoreDoc.fields` | operator POST form → `request.form` | Yes | FLOWING — unchanged |
| `ui/app.py` | `DirectorStatus` (GET /status) | `read_status(status_path)` → opcomm channel | Yes | FLOWING — unchanged |
| `orchestrator/loop.py` | `alive` map | `watchdog.alive_map(now, source, cam_ids)` | Yes | FLOWING — watchdog now gets non-zero grace |
| `orchestrator/loop.py` | `decision` | `engine.tick(scores, alive, holds, override)` | Yes | FLOWING — unchanged |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 regression: obs.connect() raising at launch still runs 5 ticks | `python -m pytest tests/test_orchestrator_startup.py -v` | 5 passed in 0.24s | PASS |
| CR-01 regression: source.start() raising at launch still runs 5 ticks | included in above | 5 passed | PASS |
| CR-02 regression: NDI receiver disconnected branch sleeps + re-resolves | `python -m pytest tests/test_ndi_receiver_loop.py -v` | 3 passed in 0.05s | PASS |
| WR-04 regression: atomic_write_text retries on PermissionError | `python -m pytest tests/test_atomic_io.py -v` | 10 passed in 3.78s | PASS |
| WR-02: watchdog_grace default non-zero | `python -c "from segugio.config.models import Thresholds; assert Thresholds().watchdog_grace > 0.0"` | 0.067 | PASS |
| All headless Phase-5 tests (incl. gap-closure) | `python -m pytest tests/test_fault_isolation.py tests/test_latency.py tests/test_watchdog.py tests/test_fallback_rejoin.py tests/test_atomic_io.py tests/test_obs_mapping.py tests/test_scene_template.py tests/test_ui_score.py tests/test_ui_run.py tests/test_score_display_only.py tests/test_status_channel.py tests/test_orchestrator_startup.py tests/test_ndi_receiver_loop.py` | 65 passed, 1 skipped in 5.34s | PASS |
| Full headless suite (not gpu and not ndi and not obs) | `python -m pytest -m "not gpu and not ndi and not obs"` | **302 passed, 3 skipped, 0 failures** in 7.28s | PASS |
| All light imports succeed without heavy deps | `python -c "import segugio.opcomm, segugio.ndi, segugio.obs, segugio.watchdog_feed, segugio.orchestrator.loop, segugio.ui, segugio.ui.app, segugio.ui.score_render"` | OK | PASS |
| GPU latency test (RBT-05) | `python -m pytest tests/test_latency.py -m gpu` | SKIPPED off-GPU (collected, skipped 1) | SKIP (D-07) |

---

### Probe Execution

No explicit `probe-*.sh` probes declared for this phase. The pytest suite above is the equivalent.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NDI-01 | 05-02 | Cyndilib Finder/Receiver/FrameSync → numpy BGR, supervised threads | VERIFIED | NdiFrameSource._run_receiver with _RECEIVER_DISCONNECTED_SLEEP_S; headless: ClipReplayFrameSource; tests pass |
| NDI-02 | 05-02 | Mock NDI Sender publishes clips as named NDI sources | VERIFIED | mock_sender.publish_clip; @pytest.mark.ndi E2E (skipped, real-NDI only) |
| NDI-03 | 05-02 | Guard on empty first frames (skip zero-size) | VERIFIED | min(xres,yres)!=0 guard in _run_receiver line 155; unchanged by 05-08 |
| OBS-01 | 05-03 | Cut program scene via SetCurrentProgramScene | VERIFIED | obsws_controller.py; test_obs_mapping.py passes |
| OBS-02 | 05-03 | PIP via cached numeric sceneItemId | VERIFIED | _cache_pip_ids guarded (lines 101-107); test_obs_mapping.py::test_pip_cached_id passes |
| OBS-03 | 05-03 | Persistent connection with reconnect+reauth; EventClient syncs manual changes | VERIFIED | _safe_call reconnects; _on_scene_changed registered; test_obs_reconnect.py passes |
| OBS-04 | 05-03 | OBS scene-collection template (CAM*/SAFE/MULTIVIEW/PIP) | VERIFIED | obs/segugio-scene-collection.json; test_scene_template.py (3 passing) |
| OBS-05 | 05-03 | Overlay via read-from-file + SetInputSettings fallback | VERIFIED | atomic_write_text (now with retry); set_input_settings fallback; test_overlay.py passes |
| SCR-01 | 05-01 | Score file written atomically (temp + os.replace) | VERIFIED | WR-04 CLOSED: atomic_write_text routes through _atomic_replace retry (line 96). test_atomic_write_text_retries_on_permission_error passes. |
| SCR-02 | 05-05 | Manual score UI: discipline selector + 3 field sets | VERIFIED | console.html; test_ui_score.py (6 passing) |
| SCR-03 | 05-05 | Run start/stop resets overlay, starts/stops timer | VERIFIED | POST /run → RunState; test_ui_run.py (8 passing) |
| SCR-04 | 05-05 | System displays scores only, no adjudication | VERIFIED | score_render formats verbatim; AST guard test passes (7 passing) |
| RBT-01 | 05-04 | Watchdog from last-NEW-frame timestamp only | VERIFIED | ts!=last_ts in _run_receiver line 159; FeedWatchdog; test_watchdog.py (8 passing) |
| RBT-02 | 05-04 | Feed fallback to SAFE; guarded rejoin | VERIFIED | test_fallback_rejoin.py (3 passing); unchanged |
| RBT-04 | 05-06/07 | Fixed-rate tick, fault isolation, SAFE shutdown, never crashes | VERIFIED | CR-01 CLOSED: _safe_startup wraps source.start()/obs.connect() in both run() and run_measured(). Per-tick try/except at line 436. SAFE shutdown in shutdown(). test_orchestrator_startup.py (5 passing): exercises the REAL raising startup path. |
| RBT-05 | 05-06 | Decision loop < ~150ms (target <80ms) | PARTIAL (HARDWARE) | Wiring overhead headless mock-timed p95 < 50ms. @pytest.mark.gpu test collected, skipped off-GPU. Real GPU numbers require Windows/RTX box (D-07). No regression from gap-closure changes. |

---

### Anti-Patterns Found

Gap-closure diff (plans 05-07 and 05-08) scanned:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/obs/obsws_controller.py` | 156-162 | `_on_scene_items_changed` defined but never registered in `connect()` | WARNING | The comment in the CR-01 guard (lines 98-100) states "the EventClient SceneItemCreated/Removed callback re-caches ids" — but this handler is never registered. After a partial connect the id cache is empty and recovery is ONLY via _safe_call reconnect (which works), but the documented dual recovery path is overstated. Identified in 05-REVIEW WR-01 (new numbering). Does not break the "never crashes" contract. |
| `src/segugio/ndi/ndi_source.py` | 143-152 | `set_source` called every disconnected pass without tracking the last-set source | WARNING | WR-02 from post-gap review: calling `set_source` unconditionally every 50ms while disconnected may cause a reconnect livelock on real cyndilib (async handshake). Headless fakes flip `is_connected()` deterministically and cannot catch this. Hardware-verified by D-07. |
| `src/segugio/obs/obsws_controller.py` | 193-201 | `set_pip` reads `self._item_ids[key]` directly → KeyError when cache is empty (post-partial-connect) | WARNING | WR-03 from post-gap review: _safe_call wraps it so no crash, but triggers a full reconnect+reauth on every set_pip until ids resolve, rather than a cheap lazy re-cache. v1: set_pip is idle/manual so blast radius is low. |
| `src/segugio/orchestrator/loop.py` | 426-435, 492-524 | Probe append block inside try: fault ticks append nothing → `len(probe["total"]) < n_ticks` | INFO | WR-04 from post-gap review: the latency harness silently excludes fault ticks from p95, over-reporting health. `test_run_measured_survives_connect_raising` does not expose this because source.start() raises at startup (caught by _safe_startup before the tick loop) rather than inside the tick body. Low impact for the headless milestone. |

No `TBD`, `FIXME`, or `XXX` markers found in any gap-closure file (confirmed by grep over `src/segugio/`).

---

### Human Verification Required

All five items below are hardware/real-stack deferrals — the headless code has been verified. None block the headless phase goal.

#### 1. Real NDI receiver auto-reconnect convergence and CPU usage (CR-02 hardware validation)

**Test:** On the Windows box with cyndilib installed, start `NdiFrameSource` for 4 cameras when no NDI sources are present. Monitor CPU for receiver threads. Then bring up a mock NDI source and confirm automatic reconnection without `stop()`/`start()`.
**Expected:** CPU for disconnected threads near-zero (not 100%). Source reconnects automatically. Watch for the set_source livelock: if reconnect never converges, add last-bound-source tracking before each `set_source` call.
**Why human:** cyndilib `is_connected()` and the `set_source` async handshake timing require real hardware. The headless test proves the sleep+re-resolve LOGIC but the WR-02 (post-gap review) livelock risk on real cyndilib cannot be caught headlessly.

#### 2. Real OBS startup survival on the live obsws stack

**Test:** Start `Orchestrator.run()` on the Windows box with OBS NOT running. Start OBS after a few seconds and confirm the director reconnects and starts cutting.
**Expected:** No crash during the down period; once OBS starts, the director connects and ticks normally.
**Why human:** The headless `test_run_measured_survives_connect_raising` exercises the REAL `_safe_startup` code with a raising fake — the logic is proven. Confirmation on the live `obsws-python` + OBS websocket stack is D-07.

#### 3. Anti-jitter grace empirical value

**Test:** On the Windows box, induce a jittery NDI feed (frames arriving ~1s apart, just over `watchdog_timeout=0.8s`) and observe whether the director cut-storms with `grace=0.067`.
**Expected:** A non-zero grace of 0.067s should absorb single-late-frame jitter. Tune upward if cut-storms persist on real hardware.
**Why human:** The correct grace value is empirical. Code default 0.067 (≈2 frames @30fps) is the headless fixed seed; shipped value should be measured.

#### 4. Full E2E real-stack run (D-07)

**Test:** On Windows/RTX: start mock NDI sender, confirm cyndilib receives it, load OBS with the scene-collection template, run the orchestrator, verify scene cuts, trigger a feed death, verify SAFE fallback, open Flask console and enter scores, confirm OBS overlay updates.
**Expected:** All real-stack paths work end-to-end.
**Why human:** cyndilib, obsws-python, cv2, ultralytics, and CUDA absent in dev. @pytest.mark.ndi and @pytest.mark.obs tests auto-skip.

#### 5. GPU latency budget (RBT-05)

**Test:** `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with `yolo26s.pt` and real clip frames.
**Expected:** Decision-loop p95 < 150ms (target <80ms). Apply `_DEGRADATION_LADDER` in loop.py if over budget.
**Why human:** No GPU in dev. @pytest.mark.gpu test collected, skipped headless.

---

### Re-Verification Gap Closure Summary

**Prior gap (CR-01 / Truth #5):** CLOSED.

The single BLOCKER from the initial verification has been closed cleanly:

- `_safe_startup(label, fn)` at `loop.py:453-465` wraps each startup callable in a `try/except Exception` that logs and coasts — it does NOT swallow the exception silently (it logs a warning). Both `run()` (lines 477-478) and `run_measured()` (lines 505-506) now call `_safe_startup` for `source.start` and `obs.connect` BEFORE the tick loop.
- The `ObsWsController.connect()` guards `_cache_pip_ids()` (lines 101-107) so a partial connect coasts; `_connected = True` is still reached.
- `tests/test_orchestrator_startup.py` drives the REAL `run_measured` code path with a `ConnectionError`-raising obs and a `RuntimeError`-raising source. Both tests assert the loop runs 5 ticks — proving the fault was exercised, not bypassed.

**Post-gap-closure review findings:** The 05-REVIEW (a8d7f0c) identified 4 new warnings (WR-01 through WR-04 in new numbering) and 4 info items. None of these are blockers for the headless phase goal:
- WR-01 (unregistered scene-item handler) and WR-03 (KeyError in set_pip on empty cache): correctness gaps in partial-connect recovery, but the _safe_call reconnect path works and v1 set_pip is idle.
- WR-02 (set_source livelock risk): requires hardware verification.
- WR-04 (probe count < n_ticks on fault ticks): latency over-reporting issue, not a crash.

All 41 v1 requirements are mapped and accounted for. The 15 Phase-5 requirements (NDI-01..03, OBS-01..05, SCR-01..04, RBT-01, RBT-02, RBT-04, RBT-05) are all either VERIFIED (headless) or PARTIAL with hardware-deferred human verification items.

**Headless milestone: PASSED (5/5).** Hardware milestone (D-07, Windows/RTX box) remains the only open gate.

---

_Verified: 2026-06-11T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after gap closure (plans 05-07 and 05-08)_
