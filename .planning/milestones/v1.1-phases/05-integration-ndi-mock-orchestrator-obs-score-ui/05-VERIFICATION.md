---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
verified: 2026-06-11T16:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "UAT gap (05-UAT.md ## Gaps, severity: major): no runnable entry point — CLOSED. `src/segugio/__main__.py` and `src/segugio/orchestrator/runtime.py` now exist; `python -m segugio <config.yaml>` composes NdiFrameSource + ObsWsController + PerCameraTracker from config and calls Orchestrator.run(). UAT Tests 1-4 are now launchable on the rig."
    - "CR-01 (05-09-REVIEW): build_orchestrator now calls os.makedirs(channel_dir, exist_ok=True) before _channel_paths, so the D-11 status reverse-channel is not silently dead on a clean standalone launch. Regression test test_build_creates_missing_channel_dir passes."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Real NDI receiver auto-reconnect and CPU (CR-02 code fixed, real behavior hardware-deferred)"
    expected: "CPU usage for disconnected receiver threads near-zero; source auto-reconnects when the named NDI source appears without stop()/start()"
    why_human: "Requires Windows hardware with cyndilib installed and a live/mock NDI source. The headless test proves the sleep+re-resolve LOGIC but the real cyndilib connection timing (WR-02 livelock risk when set_source is called repeatedly mid-handshake) requires hardware measurement."
  - test: "Real OBS startup with orchestrator — confirm _safe_startup works on the live obsws stack"
    expected: "python -m segugio starts without crashing when OBS is not yet running; director ticks; reconnects once OBS starts"
    why_human: "obsws-python is absent in dev. The headless test (test_run_measured_survives_connect_raising) drives the REAL _safe_startup code path with a ConnectionError-raising fake. On-Windows confirmation of the real websocket stack completing the same path is D-07."
  - test: "Anti-jitter grace empirical value (WR-02 code fixed to 0.067, empirical tuning hardware-deferred)"
    expected: "The shipped 0.067 grace (approx 2 frames @30fps) tolerates single-late-frame jitter on the real field hardware without cut-storms"
    why_human: "The correct grace depends on measured jitter characteristics of real WiFi phone feeds. The config default is non-zero and pinned by test; the hardware-measured value is a D-07 tuning concern."
  - test: "Full E2E real-stack run (D-07): mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update"
    expected: "All real-stack paths work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera and reason"
    why_human: "cyndilib, obsws-python, cv2, and CUDA/ultralytics are absent in dev. @pytest.mark.ndi and @pytest.mark.obs auto-skip. This is the v1 milestone on-Windows hardware validation (D-07). The entry point NOW EXISTS — `python -m segugio config.example.yaml` is launchable on the rig."
  - test: "GPU latency budget (RBT-05): python -m pytest tests/test_latency.py -m gpu on the RTX 4000 Ada with yolo26s.pt and real clip frames"
    expected: "Decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py."
    why_human: "No GPU in dev. The @pytest.mark.gpu test is collected and skipped headless. Wiring overhead is proven headless (mock-timed p95 < 50ms). Real GPU numbers require the Windows/RTX box."
---

# Phase 5: Integration (NDI Mock, Orchestrator, OBS, Score UI) Re-Verification Report

**Phase Goal:** Everything wires together end-to-end with no hardware, closing the v1 milestone: a mock NDI source feeds clips through cyndilib ingest, a timestamp-based watchdog drives automatic fallback, an OBS controller cuts scenes and PIP and updates overlays, a manual score-entry UI writes atomically to an OBS read-from-file text source, and a fault-isolated orchestrator ticks the full frame->YOLO->score->FSM->OBS loop within the latency budget and shuts down to SAFE without ever crashing.

**Verified:** 2026-06-11T16:00:00Z
**Status:** human_needed
**Re-verification:** Yes — gap-closure plan 05-09 (runnable entry point + CR-01 fix). Third verification pass.

---

## Gap-Closure Summary (05-09)

The ONE UAT gap identified in `05-UAT.md` was: Phase 05 verified the orchestrator loop LOGIC headlessly (5/5) but shipped NO runnable entry point, so UAT Tests 1-4 could not be launched on the rig.

Plan 05-09 closed this gap by adding:

1. `src/segugio/orchestrator/runtime.py` — `build_orchestrator(config, channel_dir, *, fps, grace, source_factory, obs_factory, tracker_factory)` factory that maps `config.cameras` onto `NdiFrameSource` + `ObsWsController` + one `PerCameraTracker` per camera + `channel_paths`, then returns `Orchestrator.from_config(...)`. Heavy imports are lazy (inside the default factory bodies). Injectable construction seam for headless testing.
2. `src/segugio/__main__.py` — `main(argv) -> int` exposing `python -m segugio <config.yaml>`. Loads config, builds via factory, calls `orch.run(rate_hz)`, handles `KeyboardInterrupt` -> `orch.shutdown()` (RBT-04 SAFE coast). Light imports only at module top.
3. `docs/run.md` — the exact OBS-up and OBS-down launch commands mapping to UAT Tests 1-4.
4. `tests/test_orchestrator_runtime.py` — 11 headless regression tests (6 factory composition + 4 main() wiring + 1 CR-01 channel-dir regression).
5. CR-01 fix (code review 05-09-REVIEW): `os.makedirs(channel_dir, exist_ok=True)` in `build_orchestrator` before `_channel_paths`, so the D-11 status reverse-channel works on a clean standalone launch. Regression test `test_build_creates_missing_channel_dir` guards it.

**Full headless suite:** 315 passed, 3 skipped, 0 failures (baseline 302; +13 new tests from 05-09, zero regression).

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Mock NDI source (ClipReplayFrameSource) publishes named clips; cyndilib FrameSource (NdiFrameSource) delivers numpy BGR per camera on supervised threads with empty-frame guard | VERIFIED | `src/segugio/ndi/clip_source.py`, `src/segugio/ndi/ndi_source.py`. Unchanged from prior verification. Real NDI path gated behind @pytest.mark.ndi. |
| 2 | OBS controller cuts program scene, toggles PIP via cached numeric sceneItemId, reconnects on drop, EventClient observes manual scene changes | VERIFIED | `src/segugio/obs/obsws_controller.py`. Unchanged from prior verification. Tests pass headless. |
| 3 | Feed watchdog deduces liveness from last-NEW-frame timestamp; dead feed triggers fallback to SAFE; recovered feed rejoins only after full hysteresis+dwell | VERIFIED | `src/segugio/watchdog_feed/liveness.py`. Unchanged. `Thresholds.watchdog_grace = 0.067` (non-zero). test_watchdog.py (8 passing), test_fallback_rejoin.py (3 passing). |
| 4 | Score UI offers discipline selector + 3 field sets + run start/stop; writes atomically; system displays scores only | VERIFIED | `src/segugio/ui/app.py`, `src/segugio/ui/score_render.py`, `src/segugio/ui/templates/console.html`. Unchanged. |
| 5 | Orchestrator ticks full loop with fault isolation (try/except), shuts down to SAFE, never crashes, decision loop under ~150ms — AND the integrated orchestrator is launchable on the rig via `python -m segugio <config>` | VERIFIED (headless) / HUMAN-DEFERRED (hardware) | NEW (05-09): `src/segugio/orchestrator/runtime.py` builds the real NdiFrameSource + ObsWsController + PerCameraTracker from config; `src/segugio/__main__.py` provides the `python -m segugio` entry point. CR-01 fix: `os.makedirs(channel_dir, exist_ok=True)` at runtime.py:146. test_build_creates_missing_channel_dir passes. Full headless suite: 315 passed, 3 skipped, 0 failures. Real-stack hardware run (D-07) remains hardware-deferred. |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/orchestrator/runtime.py` | build_orchestrator factory (UAT gap closure) | VERIFIED | 173 lines, `def build_orchestrator` present, `os.makedirs` at line 146, `Orchestrator.from_config` call at line 164. Lazy imports: top-level imports are only os/pathlib/typing/.loop — no heavy deps. |
| `src/segugio/__main__.py` | python -m segugio entry point | VERIFIED | 94 lines, `def main` present, `build_orchestrator` called, `KeyboardInterrupt` -> `shutdown()`, `if __name__ == "__main__": raise SystemExit(main())` guard present. |
| `tests/test_orchestrator_runtime.py` | Headless regression for 05-09 | VERIFIED | 286 lines, 11 tests (`def test_` x11), all pass headless. Includes `test_build_creates_missing_channel_dir` (CR-01 guard). |
| `docs/run.md` | Rig launch commands for UAT Tests 1-4 | VERIFIED | 114 lines, 9 occurrences of `python -m segugio`, covers OBS-up, OBS-down, --rate, --opcomm-dir, UAT test table. |
| `src/segugio/ndi/clip_source.py` | In-process clip-replay FrameSource (headless mock) | VERIFIED | Unchanged from prior verification |
| `src/segugio/ndi/ndi_source.py` | Real cyndilib FrameSource (1 thread/cam, lazy import) | VERIFIED | Unchanged from prior verification (05-08 CR-02 fix intact) |
| `src/segugio/ndi/mock_sender.py` | NDI-02 named-source Sender (E2E only) | VERIFIED | Unchanged; E2E only under @pytest.mark.ndi |
| `src/segugio/obs/obsws_controller.py` | Real obsws-python v5 controller | VERIFIED | Unchanged from prior verification |
| `src/segugio/watchdog_feed/liveness.py` | FeedWatchdog pure liveness math | VERIFIED | Unchanged; grace non-zero by default |
| `src/segugio/opcomm/atomic.py` | Atomic write (temp+fsync+os.replace) with retry | VERIFIED | Unchanged from prior verification (WR-04 fix intact) |
| `src/segugio/ui/app.py` | Flask console | VERIFIED | Unchanged |
| `src/segugio/orchestrator/loop.py` | Orchestrator fixed-rate tick, fault isolation | VERIFIED | Unchanged from prior verification (CR-01 _safe_startup intact) |
| `src/segugio/orchestrator/__init__.py` | Re-exports build_orchestrator | VERIFIED | Modified by 05-09: build_orchestrator re-exported |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `__main__.main()` | `build_orchestrator` | `from .orchestrator.runtime import build_orchestrator`; called at main.py:82 | VERIFIED | Confirmed: `orch = build_orchestrator(config, args.opcomm_dir)` at line 82 |
| `__main__.main()` | `Orchestrator.run()` | `orch.run(args.rate)` at main.py:84 | VERIFIED | Confirmed in __main__.py:84 |
| `__main__.main()` | `Orchestrator.shutdown()` (SAFE coast) | `except KeyboardInterrupt: orch.shutdown()` at main.py:88 | VERIFIED | RBT-04 path confirmed; test_main_keyboardinterrupt_calls_shutdown passes |
| `runtime.build_orchestrator` | `Orchestrator.from_config` | `return Orchestrator.from_config(config=config, source=source, obs=obs, channel_paths=channel_paths, trackers=trackers, fps=fps, grace=grace)` at runtime.py:164 | VERIFIED | Confirmed in runtime.py:164-172 |
| `runtime.build_orchestrator` | `channel_dir` creation | `os.makedirs(channel_dir, exist_ok=True)` at runtime.py:146 | VERIFIED | CR-01 fix confirmed; test_build_creates_missing_channel_dir passes, D-11 write verified |
| `runtime._default_source_factory` | `NdiFrameSource` | lazy `from ..ndi.ndi_source import NdiFrameSource` inside builder body | VERIFIED | Import at runtime.py:82; heavy dep absent from module top-level (AST check confirmed) |
| `runtime._default_obs_factory` | `ObsWsController` | lazy `from ..obs.obsws_controller import ObsWsController` inside builder body | VERIFIED | Import at runtime.py:89 |
| `runtime._default_tracker_factory` | `PerCameraTracker` | lazy `from ..tracking.detector import PerCameraTracker` inside builder body | VERIFIED | Import at runtime.py:96 |
| Prior key links (loop, watchdog, OBS, score, atomic) | (as previous verification) | (unchanged) | VERIFIED | No regression — 315 passed headless |

---

### Data-Flow Trace (Level 4)

New artifacts in 05-09 are wiring/entry-point only — no new data-rendering paths. The factory `build_orchestrator` wires config -> collaborators -> Orchestrator; it does not render data itself. All prior Level 4 traces (ui/app.py, orchestrator/loop.py) are unchanged and remain FLOWING.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ui/app.py` | `ScoreDoc.fields` | operator POST form | Yes | FLOWING — unchanged |
| `ui/app.py` | `DirectorStatus` (GET /status) | `read_status(status_path)` | Yes | FLOWING — channel_dir now guaranteed to exist (CR-01 fix) |
| `orchestrator/loop.py` | `alive` map | `watchdog.alive_map(now, source, cam_ids)` | Yes | FLOWING — unchanged |
| `orchestrator/loop.py` | `decision` | `engine.tick(scores, alive, holds, override)` | Yes | FLOWING — unchanged |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gap-closure regression suite (factory + main + import-smoke) | `python -m pytest tests/test_orchestrator_runtime.py tests/test_imports.py -m "not gpu and not ndi and not obs" -v` | 34 passed in 0.46s | PASS |
| CR-01 regression: build creates missing nested channel_dir and D-11 write lands | `python -m pytest tests/test_orchestrator_runtime.py::test_build_creates_missing_channel_dir -v` | 1 passed in 0.23s | PASS |
| Lazy-import boundary: heavy-stack-absent import | `python -c "import segugio.__main__, segugio.orchestrator.runtime; print('import OK')"` | import OK | PASS |
| CR-01 direct verify: makedirs + Orchestrator.from_config call + trackers keyed correctly | runtime.py:146 `os.makedirs(channel_dir, exist_ok=True)` + runtime.py:164 `Orchestrator.from_config(...)` | Direct codebase check | PASS |
| Full headless suite (no regression from 05-09) | `python -m pytest -m "not gpu and not ndi and not obs"` | 315 passed, 3 skipped, 0 failures | PASS |
| Prior CR-01 regression: obs.connect() raising at launch still runs 5 ticks | `python -m pytest tests/test_orchestrator_startup.py -v` | 5 passed (baseline, no change) | PASS |
| GPU latency test (RBT-05) | `python -m pytest tests/test_latency.py -m gpu` | SKIPPED off-GPU (collected, skipped 1) | SKIP (D-07) |

---

### Probe Execution

No explicit `probe-*.sh` probes declared for this phase. The pytest suite above is the equivalent.

---

### Requirements Coverage

All 15 Phase-5 requirements verified — no change from prior verification except RBT-04 status upgraded to fully VERIFIED headless (the entry-point half was previously the UAT gap).

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NDI-01 | 05-02 | Cyndilib Finder/Receiver/FrameSync -> numpy BGR, supervised threads | VERIFIED | Unchanged; NdiFrameSource._run_receiver; headless: ClipReplayFrameSource |
| NDI-02 | 05-02 | Mock NDI Sender publishes clips as named NDI sources | VERIFIED | mock_sender.publish_clip; @pytest.mark.ndi E2E |
| NDI-03 | 05-02 | Guard on empty first frames (skip zero-size) | VERIFIED | min(xres,yres)!=0 guard in _run_receiver |
| OBS-01 | 05-03 | Cut program scene via SetCurrentProgramScene | VERIFIED | obsws_controller.py; tests pass |
| OBS-02 | 05-03 | PIP via cached numeric sceneItemId | VERIFIED | _cache_pip_ids guarded; test_obs_mapping.py passes |
| OBS-03 | 05-03 | Persistent connection with reconnect+reauth; EventClient syncs manual changes | VERIFIED | _safe_call reconnects; test_obs_reconnect.py passes |
| OBS-04 | 05-03 | OBS scene-collection template (CAM*/SAFE/MULTIVIEW/PIP) | VERIFIED | obs/segugio-scene-collection.json; test_scene_template.py passes |
| OBS-05 | 05-03 | Overlay via read-from-file + SetInputSettings fallback | VERIFIED | atomic_write_text with retry; test_overlay.py passes |
| SCR-01 | 05-01 | Score file written atomically (temp + os.replace) | VERIFIED | atomic_write_text routes through _atomic_replace retry |
| SCR-02 | 05-05 | Manual score UI: discipline selector + 3 field sets | VERIFIED | console.html; test_ui_score.py (6 passing) |
| SCR-03 | 05-05 | Run start/stop resets overlay, starts/stops timer | VERIFIED | POST /run -> RunState; test_ui_run.py (8 passing) |
| SCR-04 | 05-05 | System displays scores only, no adjudication | VERIFIED | score_render formats verbatim; test_score_display_only.py (7 passing) |
| RBT-01 | 05-04 | Watchdog from last-NEW-frame timestamp only | VERIFIED | ts!=last_ts in _run_receiver; test_watchdog.py (8 passing) |
| RBT-02 | 05-04 | Feed fallback to SAFE; guarded rejoin | VERIFIED | test_fallback_rejoin.py (3 passing) |
| RBT-04 | 05-06/07/09 | Fixed-rate tick, fault isolation, SAFE shutdown, never crashes + runnable entry point | VERIFIED (headless) / HARDWARE-DEFERRED | Headless: _safe_startup (05-07), per-tick try/except, SAFE shutdown, test_orchestrator_startup.py (5 passing). Entry point: `python -m segugio` now exists (05-09), Ctrl-C -> shutdown() proven by test_main_keyboardinterrupt_calls_shutdown. Real-OBS hardware confirmation is D-07 (UAT Test 1). |
| RBT-05 | 05-06 | Decision loop < ~150ms (target <80ms) | PARTIAL (HARDWARE) | Wiring overhead headless mock-timed p95 < 50ms; @pytest.mark.gpu collected, skipped off-GPU. No regression from 05-09 (wiring-only). Real GPU numbers require Windows/RTX box (D-07). |

---

### Anti-Patterns Found

Scanned: `src/segugio/orchestrator/runtime.py`, `src/segugio/__main__.py`, `docs/run.md`, `tests/test_orchestrator_runtime.py`.

No `TBD`, `FIXME`, or `XXX` markers found in any 05-09 file. No stub/placeholder patterns. One intentional TODO marker found:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/orchestrator/runtime.py` | 59 | `# Future: source from a config.obs model (out of scope for this thin-wiring plan)` (inline comment, no TODO marker) | INFO | OBS creds hardcoded to localhost/4455/None — intentional scope decision, acknowledged in 05-09-REVIEW IN-02. Not a blocker. |

Carried-forward warnings from prior verification (05-07/05-08, not introduced by 05-09):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/obs/obsws_controller.py` | 156-162 | `_on_scene_items_changed` defined but never registered in `connect()` | WARNING | Dual-recovery path overstated; _safe_call reconnect works. Does not crash. |
| `src/segugio/ndi/ndi_source.py` | 143-152 | `set_source` called unconditionally every 50ms when disconnected — livelock risk on real cyndilib | WARNING | Hardware-verified by D-07 (Test 2). Headless fakes deterministic. |
| `src/segugio/obs/obsws_controller.py` | 193-201 | `set_pip` reads `self._item_ids[key]` directly -> KeyError when cache is empty post-partial-connect | WARNING | _safe_call wraps it; triggers reconnect rather than cheap re-cache. v1: set_pip is idle. |
| `src/segugio/orchestrator/loop.py` | 426-435 | Probe append inside try: fault ticks excluded from p95, over-reporting health | INFO | Only affects the latency harness telemetry, not correctness. |

No new anti-patterns introduced by 05-09.

---

### Human Verification Required

All items below are hardware/real-stack deferrals. The headless code has been verified. None block the headless phase goal. The entry point NOW EXISTS — `python -m segugio config.example.yaml` is launchable.

#### 1. Real NDI receiver auto-reconnect convergence and CPU usage (CR-02 hardware validation)

**Test:** On the Windows box with cyndilib installed, start `NdiFrameSource` for all cameras when no NDI sources are present. Monitor CPU for receiver threads. Then bring up a mock NDI source and confirm automatic reconnection without `stop()`/`start()`.
**Expected:** CPU for disconnected threads near-zero (not 100%). Source reconnects automatically. Watch for the WR-02 set_source livelock: if reconnect never converges, add last-bound-source tracking before each `set_source` call.
**Why human:** cyndilib `is_connected()` and the `set_source` async handshake timing require real hardware. The headless test proves the sleep+re-resolve LOGIC but the WR-02 livelock risk on real cyndilib cannot be caught headlessly.

#### 2. Real OBS startup survival on the live obsws stack (UAT Test 1)

**Test:** Run `python -m segugio config.example.yaml` on the Windows box with OBS NOT running. Start OBS after a few seconds and confirm the director reconnects and starts cutting.
**Expected:** No crash during the down period; once OBS starts, the director connects and ticks normally.
**Why human:** The headless `test_run_measured_survives_connect_raising` exercises the REAL `_safe_startup` code with a raising fake. Confirmation on the live `obsws-python` + OBS websocket stack is D-07. The entry point (`python -m segugio`) is now code-verified — it exists and wires correctly; this test confirms it runs on the real stack.

#### 3. Anti-jitter grace empirical value

**Test:** On the Windows box, induce a jittery NDI feed and observe whether the director cut-storms with `grace=0.067`.
**Expected:** A non-zero grace of 0.067s should absorb single-late-frame jitter. Tune upward if cut-storms persist.
**Why human:** The correct grace value is empirical. Code default 0.067 (approx 2 frames @30fps) is the headless fixed seed; shipped value should be measured.

#### 4. Full E2E real-stack run (D-07, UAT Tests 2-4)

**Test:** On Windows/RTX: start `python -m segugio config.example.yaml`, confirm cyndilib receives NDI, load OBS with the scene-collection template, verify scene cuts, trigger a feed death, verify SAFE fallback, open Flask console and enter scores, confirm OBS overlay updates. See `docs/run.md` for exact commands.
**Expected:** All real-stack paths work end-to-end.
**Why human:** cyndilib, obsws-python, cv2, ultralytics, and CUDA absent in dev. @pytest.mark.ndi and @pytest.mark.obs tests auto-skip. The entry point is now CODE-VERIFIED — this test runs it on hardware.

#### 5. GPU latency budget (RBT-05)

**Test:** `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with `yolo26s.pt` and real clip frames.
**Expected:** Decision-loop p95 < 150ms (target <80ms). Apply `_DEGRADATION_LADDER` in loop.py if over budget.
**Why human:** No GPU in dev. @pytest.mark.gpu test collected, skipped headless.

---

### Gap Closure vs Prior Verification

**Prior status (05-VERIFICATION.md, second pass):** human_needed, 5/5 headless, UAT gap blocking D-07.

**This pass (third, after 05-09):**
- The ONE code gap is CLOSED: `src/segugio/__main__.py` and `src/segugio/orchestrator/runtime.py` exist and are substantive and wired.
- `python -m segugio <config>` is a real, launchable entry point.
- The CR-01 code-review finding (channel_dir never created) is FIXED by `os.makedirs` in `build_orchestrator` and guarded by `test_build_creates_missing_channel_dir`.
- The WR-01/WR-03/WR-04 code-review warnings (05-09-REVIEW) are carried forward as warnings — none introduced by this plan, none are blockers.
- Full headless suite: **315 passed, 3 skipped, 0 failures** (baseline 302; +13 from 05-09).
- Status remains `human_needed`: the D-07 hardware UAT (Tests 1-4) is the only remaining gate, and it is correctly hardware-deferred (not a code gap).

**Headless milestone: PASSED (5/5, code-complete).** Hardware milestone (D-07, Windows/RTX box) is the only open gate. The rig can now be set up using `docs/run.md`.

---

_Verified: 2026-06-11T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after gap-closure plan 05-09 (third verification pass)_
