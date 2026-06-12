---
status: partial
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
source: [05-VERIFICATION.md]
started: 2026-06-11T14:05:00Z
updated: 2026-06-12T00:30:00Z
---

## Current Test

number: 4
name: Full E2E real-stack run — POSITIVE PATH (single phone) (D-07)
result: positive-path PASS; one open blocker (FSM release-from-auto) + deferrals
awaiting: nothing — rig session paused

Phase 05 UAT live-at-rig progress (2026-06-13): Test 1 PASS (real OBS), Test 2 PASS (HX decode +
feed-death detection + reconnect, watchdog fix 95a592c live-verified), Test 4 POSITIVE PATH PASS
(dog → cam_wide → OBS cut SAFE→CAM Wide; overlay + status panel confirmed; "no return to SAFE on
subject loss" is BY DESIGN anti-flicker). OPEN: (1) FSM release-from-auto MachineError blocker —
headless-fixable, no rig (see Gaps + Test 4 fsm_release_bug); (2) Test 3 anti-jitter + Test 4
multi-cam switching/fallback + override Forza/Rilascia leg — need ≥2 phones; (3) Test 5 GPU latency
— desk-anytime (pytest -m gpu). NEXT: fix the FSM release bug via /gsd-debug (no rig), then resume
/gsd-verify-work 05 for the multi-cam/override legs when ≥2 phones are available.

## Smoke-test findings (heavy stack on dev box — 2026-06-12)

`pip install -e ".[heavy]"` succeeded on Python 3.14 (torch 2.12.0 cp314 wheel, ultralytics,
cyndilib, opencv, obsws all resolve — no need for 3.12). Running the real stack on the dev box
(no GPU, no live NDI source, OBS first absent then operator-started) gave PARTIAL D-07 signal
and exposed **4 real defects, all fixed**:

- **RBT-04 CONFIRMED (partial):** `python -m segugio config.example.yaml` downloaded `yolo26s.pt`,
  built source/obs/4 trackers, and ticked ~20s coasting in SAFE WITHOUT crashing while OBS+NDI
  were down — on the real obsws-python/ultralytics stack. (Full "reconnects once OBS starts" +
  the NDI/GPU paths still need the rig.)
- **OBS log spam (fixed `0935d48`):** with OBS down from start, `_req` was None so every tick
  threw an AttributeError that `_safe_call` dumped as a full traceback (~90 lines/sec). Throttled
  to first-failure + heartbeat, accurate cause, one recovery line; +regression test.
- **NDI mock-sender cyndilib 0.1.1 API (fixed `a9e96d0`):** the `[ASSUMED A2]` code was wrong in
  two places when first run for real — `FourCC` import path (`ndi_recv`→`ndi_structs`) and
  `write_video_async` needs a flat 1-D buffer (`bgra.reshape(-1)`). Both fixed; rest of the
  cyndilib surface probed and confirmed correct.
- **Tooling/test (fixed `5707286`, `682aa89`):** ultralytics ships its own top-level `tests/`
  package that shadowed the repo's in any heavy venv (→ `tests/__init__.py` + qualify one import);
  and `test_app_imports_nothing_heavy` was brittle in a heavy env (→ force-absent pattern).
- **NDI receiver busy-spin (fixed `06683a0`):** against a live NDI stream the connected receiver
  loop pinned ~2 CPU cores PER camera. `frame_sync.capture_video()` is non-blocking (~0.2us,
  5.6M calls/s) so the tight loop busy-spun. Paced to ~500Hz (mirrors CR-02) → ~2.09→~1.50
  core/cam (busy-spin ~0.6 core/cam gone), frames + liveness preserved; +bounded regression test.
  BUDGET NOTE: the remaining ~1.5 core/cam is INTRINSIC (NDI decode @bandwidth=highest + 1080p
  per-frame cvtColor) — 4 cams ≈ ~6 cores of ingest before YOLO; mitigate on a smaller rig CPU
  via a lower NDI bandwidth mode or downscaling before YOLO. (Measured on the 22-core dev box on
  AC; battery throttling earlier inflated the % — measure perf on AC.)

Headless suite: **319 passed** (global) / venv `-m "not ndi and not obs and not gpu"` all green.
The 2 `@pytest.mark.ndi` loopback tests still fail in the venv — real NDI frame delivery (rig).

## Tests

### 1. Real OBS startup with orchestrator (RBT-04, _safe_startup on the live obsws stack)
expected: `python -m segugio config.example.yaml` starts without crashing when OBS is not yet running; the director ticks; the controller reconnects once OBS starts on the live obsws-python v5 stack.
result: pass
verified: "VERIFIED on real OBS (2026-06-12, operator's box, obsws-python v5 up on localhost:4455 no-auth, scene collection imported — SAFE/CAM Wide/CAM Long/CAM Low/CAM Handler all present). (a) OBS-down launch downloads yolo26s.pt, builds source/obs/4 trackers, ticks ~20s coasting in SAFE WITHOUT crashing and writes status.json {live_cam: SAFE, reason: feed-dead} (RBT-04). (b) Live connect + cut('SAFE') succeeds — the OBS program scene read back == 'SAFE' (OBS-01 on the real stack). (c) Reconnect: a simulated client drop (_req=None) then cut() rebuilt the client and succeeded, logging exactly one throttled WARNING ('no OBS connection') + DEBUG rebuild + one INFO 'cut recovered after 1 failed tick(s)' — no spam (confirms fix 0935d48). The live-cam-from-NDI-feed selection is covered by Tests 2/4 (NDI), not this test."
reported: "`python -m segugio config.example.yaml` crashed at launch: ModuleNotFoundError: No module named 'ultralytics' (PerCameraTracker.__init__ -> from ultralytics import YOLO), via build_orchestrator -> _default_tracker_factory. User followed docs/run.md Prerequisites (`pip install -e .`)."
severity: major
diagnosis: "NOT a wiring bug — the entry point ran argparse -> load_config -> build_orchestrator -> created channel_dir -> built NdiFrameSource + ObsWsController, then crashed constructing the first PerCameraTracker, which lazily imports ultralytics. Root cause: the `heavy` optional-dependency group (ultralytics/cyndilib/obsws-python/watchdog/opencv-python) is NOT installed, and docs/run.md Prerequisites told the operator to run `pip install -e .` (base deps only). Secondary: the entry point died with a raw traceback instead of an actionable message (WR-01 from 05-09-REVIEW)."
resolution: "FIXED (commit bc4c5f5, headlessly verified on this box with the heavy stack genuinely absent): (1) docs/run.md Prerequisites now installs `pip install -e \".[heavy]\"` with a headless-vs-rig note + the libndi requirement; (2) main() catches a HEAVY-stack ModuleNotFoundError and exits 2 with `Heavy runtime stack not installed (missing 'ultralytics'). Install it on the rig with: pip install -e \".[heavy]\"` instead of a traceback (a non-heavy ModuleNotFoundError is re-raised so real bugs are not masked). Re-running `python -m segugio config.example.yaml` now prints that line and exits 2. The REMAINING live confirmation — director ticks + reconnects against real OBS with the heavy stack installed — is D-07 hardware-deferred (needs the Windows/RTX rig)."

### 2. Real NDI receiver auto-reconnect + near-zero CPU (CR-02, NDI-01)
expected: CPU for disconnected receiver threads is near-zero (no busy-spin); a named NDI source that appears after thread start auto-reconnects without stop()/start(). Watch for the WR-02 livelock risk — set_source re-issued every 50ms mid-handshake on real cyndilib. With the HX fix, a phone feed decodes into the loop AND a feed death is detected (alive→false→feed-dead) so the FSM can fall over.
result: pass
severity: blocker (RESOLVED — commit 95a592c, live-verified at rig 2026-06-13)
resolved_by: "Debug session watchdog-hx-feed-death (.planning/debug/resolved/). Two defects fixed in NdiFrameSource: liveness now gates on decoded-content change (not the FrameSync timestamp) and last_frame_ts is stamped with time.monotonic() (the watchdog's clock). LIVE-VERIFIED: closing the iPhone HX app flips cam_wide to feed-dead and reopening restores alive (probe fingerprint froze on close → NEW on reopen; python -m segugio status.json feed-dead↔alive). Decode-in-loop (step 1), feed-death detection (step 2), and auto-reconnect all confirmed; disconnected CPU near-zero unchanged. Headless 323 passed (+4 regression tests)."
reported: "Live phone (config.rigtest.yaml, cam_wide -> 'LOCALHOST (iPhone Camera for OBS Studio App)'): decode WORKS — status.json shows {live_cam: SAFE, reason: subject-lost, alive: {cam_wide: true}} (feed alive, no dog → correct). BUT with the sender app CLOSED, status.json STAYS {reason: subject-lost, alive: {cam_wide: true}} — never transitions to feed-dead. The watchdog does not detect HX feed death."
live_finding_2026-06-12: "DECODE-IN-LOOP CONFIRMED (step 1 PASS): with the live name in config, NdiFrameSource feeds decoded HX frames to the tick loop — alive.cam_wide=true, reason=subject-lost (not feed-dead). FEED-DEATH DETECTION FAILS (step 2): sender app closed → camera stays alive=true indefinitely. ROOT CAUSE (high confidence): the receiver reads receiver.frame_sync.capture_video() (cyndilib FrameSync), whose job is to deliver a frame at the RECEIVER clock — so on a dead sender it keeps emitting the repeated frame with an ADVANCING get_timestamp_posix(). The RBT-01 substrate (ndi_source.py:251-260, publish only when ts != last_ts) therefore never stalls → FeedWatchdog (now - last_frame_ts <= timeout+grace) keeps the camera alive forever. [ASSUMED A1] ('a frozen feed repeats its last frame with the SAME timestamp', ndi_source.py header L26-28, flagged load-bearing & needing a pull-the-cable test) is FALSE on the FrameSync path. Defeats the explicit live requirement (caduta feed → SAFE/fallback): in multi-cam a frozen feed with a dog in-frame would keep being aired. FIX CANDIDATES (for diagnosis): (a) liveness off the SENDER timecode (get_timecode) which a frozen sender repeats, not the receiver-clock timestamp; (b) raw Receiver.capture_video(timeout) which returns no-frame on starvation, instead of FrameSync, for the liveness substrate; (c) content-identity freeze detector (last decoded array unchanged > timeout). Needs a focused /gsd-debug — NOT a rushed fix."
hx_finding: "RESOLVED 8048319 — superseded by live_finding above (decode now works in-loop). Historical: cyndilib 0.1.1 decoded ZERO iPhone HX frames until the system 6.3.2 runtime was preloaded."
partial_verified: "NDI-01 RECEIVER CORE VERIFIED on real cyndilib 0.1.1 + a live NDI stream (2026-06-12, OBS DistroAV output 'MASTER (OBS PGM)' as the source). NdiFrameSource([cam@'MASTER (OBS PGM)']).start() resolved the named source via Finder, connected, and yielded a real frame shape=(1080,1920,3) uint8 BGR (NDI-03 zero-res guard + reshape RGBA->BGR correct); 20 distinct NEW timestamps in ~2s confirm RBT-01 liveness (get_timestamp_posix advances per NEW frame — [ASSUMED A1] CONFIRMED); stop() joined the threads. Also confirmed the Finder API (get_source_names/get_source) exists on 0.1.1 (the _resolve_source 'API may differ' pragma)."
cpu_finding: "CONNECTED-PATH CPU measured on the live stream and a busy-spin FIXED (06683a0): the loop pinned ~2 cores/cam; frame_sync.capture_video() is non-blocking (~0.2us) so the unpaced loop busy-spun → paced to ~500Hz → ~2.09→~1.50 core/cam. Remaining ~1.5 core/cam is intrinsic NDI decode + 1080p cvtColor (perf-budget item, not a bug)."
hx_finding: "CRITICAL (2026-06-12): cyndilib 0.1.1 does NOT decode the iPhone's NDI HX video. With a live iPhone 'NDI Camera' source, NdiFrameSource CONNECTS (receiver.is_connected()=True) but yields ZERO video frames (VideoFrameSync.xres/yres stay 0,0) across every color_format/bandwidth combo and even with OBS fully closed (so NOT a single-receiver limit). NDI Studio Monitor (system NDI runtime + the installed HX Driver) shows the SAME phone fine → the phone IS sending video and the system runtime decodes the HX. Root cause: cyndilib loads its OWN bundled NDI runtime (Processing.NDI.Lib.x64.dll v6.1.1 in site-packages) which does not load the NDI HX decoder; NDI_RUNTIME_DIR_V6 is ignored, so it can't be redirected to the system 6.3.2 runtime by env var. This BLOCKS the real use case — the phones are ALL NDI HX. Invisible until now because the headless tests use the mock clip source and the only live source tested before was OBS PGM (full/uncompressed NDI, which cyndilib decodes fine — that path IS verified). The receiver LOGIC is correct (validated on OBS PGM); the blocker is HX decode in cyndilib's bundled runtime — a dependency/packaging issue needing a focused investigation (HX-codec loading, a newer cyndilib, or an alternative NDI binding)."
reason: "STILL PENDING (Test 2 headline) AND now BLOCKED on the HX finding above for the real phone path: (a) auto-reconnect after a real drop/reappear — could not be exercised because no phone video decodes; (b) DISCONNECTED-branch CPU is near-zero (confirmed ~0% during the failed phone runs — the disconnected coast does NOT busy-spin); (c) frozen-feed liveness — needs decoded phone frames. Discovery itself was RESOLVED (NDI Access Manager on this multi-homed PC: 5 virtual NICs — VMware/Hyper-V/Tailscale — broke mDNS; Access Manager fixed it without disabling NICs). Operational notes for docs/run.md: NDI Access Manager for discovery on a multi-homed PC; the phone must have its camera VIEW active to send video; NDI HX phones serve essentially one receiver."

### 3. Anti-jitter grace empirical tuning (WR-02, RBT-02)
expected: The shipped watchdog_grace=0.067 (~2 frames @30fps) tolerates single-late-frame jitter on real WiFi phone feeds without cut-storms; tune against measured jitter if needed.
result: blocked
blocked_by: physical-device
reason: "Now launchable via the runner; empirical tuning needs the live system against real WiFi phone feeds (D-07). The non-zero default is already pinned by test."

### 4. Full E2E real-stack run (D-07 — v1 milestone validation)
expected: mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update all work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera + reason.
result: issue
severity: blocker
reported: "Live (config.rigtest.yaml, single phone). PASSED legs: overlay (console score → overlay.txt → OBS 'Score Text' shows it) and the console status panel (live cam + reason). NOT verified: detection→cut. Two operator-control findings: (1) reason stayed 'override' — a stale/active force_cam in command.json (operator UX, not a bug). (2) After 'Avvia' (start) + 'Rilascia' (release), the orchestrator throws every tick: transitions.core.MachineError 'Can't trigger event release from state auto!' (loop _tick_once:437 → SAFE coast), wedging the director permanently in SAFE so detection→cut can never be reached."
positive_path_verified: "PASS (live, single phone, via the command.json-delete workaround). Dog in frame → live_cam: cam_wide and OBS program scene cut SAFE → CAM Wide (the core value: la camera giusta al momento giusto). Score overlay (console → overlay.txt → OBS Score Text) and the console status panel (live cam + reason) both confirmed. NOTE — 'never returns to SAFE on subject loss' is BY DESIGN (anti-flicker / no cut tremolanti): the auto FSM HOLDS the last camera; SAFE is reached only on cold start, feed-death-with-no-alive-camera (verified Test 2), or run-stop (Ferma). On a live camera the status reason is 'auto', never 'subject-lost' (subject-lost is reported only when parked on SAFE — loop.py:350). DESIGN QUESTION (multi-cam, ≥2 phones, deferred): when the dog is gone from ALL cameras for a sustained stretch, hold the last (possibly tight) angle vs fall back to the wide/SAFE after a grace — a product decision, not a v1 bug; moot with one cam (the wide == safe)."
fsm_release_bug: "REAL BUG (headlessly reproducible, no rig needed). engine.py tick() fires self.release(override) whenever override.release is True (level-triggered: command.json persists release=True and is re-read every tick). The 'release' transition has source='override' ONLY (engine.py:140-145). First release: override→auto (valid). Every subsequent tick: release from 'auto' → MachineError → tick fault → SAFE coast. Fix: guard the release fire on self.mode_is_override (a release when already in auto is a no-op), or add ignore_invalid_triggers / a no-op release self-loop. FSM is pure → fix + regression test are headless. Workaround to unblock the live detection test: stop orchestrator, delete ./opcomm/command.json (read_command→None on absent, channel.py:50), restart, do NOT touch Forza/Rilascia."

### 5. GPU latency budget (RBT-05)
expected: `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with yolo26s.pt and real clip frames shows decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py. (Wiring overhead proven headless: mock-timed p95 < 50ms.)
result: blocked
blocked_by: toolchain
reason: "Attempted 2026-06-13 on this box: GPU IS present (NVIDIA RTX 4000 Ada Generation Laptop GPU, driver 596.36) but the installed torch is the CPU-only wheel (torch 2.12.0+cpu, torch.version.cuda=None) → torch.cuda.is_available()=False → the gpu test AUTO-SKIPS (conftest gpu gate). NOT a hardware gap and NOT a code issue. Root: the venv is Python 3.14, for which PyTorch does not yet publish CUDA wheels, so pip resolved torch+cpu. To run Test 5: provision a CUDA-enabled torch (PyTorch cu12x wheels — practically a Python 3.12 venv with `pip install -e \".[heavy]\"` + a cuXX torch), then `pytest tests/test_latency.py -m gpu` (4-cam canonical config, 100-tick window, p95<150ms target<80ms). Measure ON AC (laptop GPU throttles on battery). Headless WIRING-overhead p95<50ms already proven by the two mock-timed tests (test_latency.py)."

## Summary

total: 5
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 2

## Gaps

- truth: "An operator override RELEASE returns the FSM to auto WITHOUT faulting on subsequent ticks — the director resumes automatic selection, it does not wedge in SAFE. (D-06 auto-resume + the explicit 'nessun crash ammesso' / no-stuck-SAFE robustness constraint.)"
  status: failed
  reason: "User reported (UAT Test 4, live): after 'Avvia' + 'Rilascia' the orchestrator throws every tick — transitions.core.MachineError 'Can't trigger event release from state auto!' (loop _tick_once:437 → SAFE coast) — wedging the director in SAFE so detection→cut is unreachable."
  severity: blocker
  test: 4
  root_cause: "engine.py tick() (L556-557) fires self.release(override) whenever override.release is True, ungated on FSM state. command.json persists release=True and the loop re-reads it every tick (level-triggered). The 'release' transition is source='override' only (engine.py:140-145). First tick releases override→auto; every subsequent tick fires release from 'auto' → MachineError → per-tick fault → permanent SAFE coast. Headlessly reproducible (pure FSM, no hardware)."
  artifacts:
    - "src/segugio/decision/engine.py:553-557 — tick() fires force/release purely on the OverrideCmd flags, without gating release on self.mode_is_override."
    - "src/segugio/decision/engine.py:140-145 — the 'release' transition: source='override' only, so release from 'auto' is an invalid trigger."
    - "src/segugio/orchestrator/loop.py:_tick_once (~437) — the per-tick catch-all that turns the MachineError into a 'fault' SAFE coast; the fault recurs every tick."
  missing:
    - "Guard the release fire on self.mode_is_override (release when already auto = no-op), or set ignore_invalid_triggers / add a no-op release self-loop from auto/safe. + a headless regression test: a persistent release command must not fault once the FSM is in auto. Fix via /gsd-debug (no rig)."

- truth: "A dead/closed NDI HX phone feed is detected as dead (alive→false→feed-dead within ~watchdog_timeout) so the FSM degrades to SAFE / another live camera — the explicit live-robustness requirement (caduta feed → degrado a SAFE/fallback)."
  status: resolved
  resolved_by: "Debug session watchdog-hx-feed-death (commit 95a592c, live-verified at rig 2026-06-13). NdiFrameSource liveness now gates on decoded-content change + a time.monotonic() stamp (was: FrameSync get_timestamp_posix(), which re-clocks, + a POSIX stamp in a different clock domain than the watchdog's monotonic `now`). Closing the iPhone HX app now flips cam_wide to feed-dead and reopening restores alive. Headless 323 passed (+4 regression tests). FeedWatchdog unchanged; mock/OBS-PGM paths unaffected. Archived: .planning/debug/resolved/watchdog-hx-feed-death.md."
  reason: "User reported (UAT Test 2, live iPhone): decode into the loop works (alive.cam_wide=true, reason=subject-lost), but with the sender app CLOSED status.json stays {reason: subject-lost, alive: {cam_wide: true}} forever — never feed-dead. The watchdog does not detect HX feed death."
  severity: blocker
  test: 2
  root_cause: "The receiver reads cyndilib FrameSync (receiver.frame_sync.capture_video()), which delivers frames at the RECEIVER clock and keeps emitting the repeated frame with an ADVANCING get_timestamp_posix() after the sender dies. The RBT-01 substrate publishes whenever ts != last_ts (ndi_source.py:251-260), so last_frame_ts never stalls and FeedWatchdog (now - last_frame_ts <= timeout+grace, liveness.py) keeps the camera alive indefinitely. [ASSUMED A1] (ndi_source.py header L26-28: 'a frozen feed repeats its last frame with the SAME timestamp' — flagged load-bearing, pull-the-cable test) is FALSE on the FrameSync path."
  artifacts:
    - "src/segugio/ndi/ndi_source.py:248-260 — reads receiver.frame_sync.capture_video() and publishes on ts != last_ts; the FrameSync clock keeps ts advancing on a dead sender."
    - "src/segugio/ndi/ndi_source.py:12-28 — [ASSUMED A1] header note (frozen feed = same timestamp) that this disproves; explicitly flagged as needing a Windows pull-the-cable test."
    - "src/segugio/watchdog_feed/liveness.py — FeedWatchdog is correct given a stalling substrate; the substrate is the defect, not the math."
    - "config.rigtest.yaml — throwaway single-cam config used to reproduce (NOT committed)."
  missing:
    - "A liveness substrate that actually stalls on a dead HX feed. Candidates: (a) sender timecode (get_timecode) which a frozen sender repeats; (b) raw Receiver.capture_video(timeout) no-frame-on-starvation instead of FrameSync; (c) decoded-array content-identity freeze detector. Pick via /gsd-debug + a real pull-the-cable repro."

- truth: "Following docs/run.md exactly, `python -m segugio <config>` launches (or fails with an actionable message) — the operator can stand the rig up from the documented procedure without hitting a raw Python traceback."
  status: resolved
  reason: "UAT Test 1: docs/run.md Prerequisites said `pip install -e .`, which installs only the base deps and omits the `heavy` extras (ultralytics/cyndilib/obsws-python/opencv-python). The entry point then crashed with `ModuleNotFoundError: No module named 'ultralytics'` when build_orchestrator constructs the first PerCameraTracker. The documented launch procedure was wrong, and the failure mode was a raw traceback rather than a clear 'install the heavy stack' message (WR-01)."
  resolved_by: "Commit bc4c5f5 — (1) docs/run.md now installs `pip install -e \".[heavy]\"` (+ headless-vs-rig note + libndi); (2) main() catches a HEAVY-stack ModuleNotFoundError and exits 2 with an actionable `pip install -e \".[heavy]\"` message (non-heavy ModuleNotFoundError re-raised, so real bugs are not masked). Verified headlessly on this box (heavy stack genuinely absent): `python -m segugio config.example.yaml` prints the hint and exits 2; +2 regression tests (test_main_missing_heavy_dep_exits_2_with_actionable_message, test_main_non_heavy_module_error_is_not_masked); full suite 317 passed / 9 skipped / 0 failures."
  severity: major
  test: 1
  artifacts:
    - "docs/run.md — Prerequisites now `pip install -e \".[heavy]\"` (was `pip install -e .`, which omitted the heavy extras)."
    - "pyproject.toml — [project.optional-dependencies].heavy declares ultralytics/cyndilib/obsws-python/watchdog/opencv-python."
    - "src/segugio/__main__.py — main() heavy-dep ModuleNotFoundError guard → exit 2 with actionable message (WR-01)."
    - "src/segugio/tracking/detector.py — PerCameraTracker.__init__ `from ultralytics import YOLO` (the first uninstalled heavy dep surfaces here)."

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

- truth: "The orchestrator ingests the real phone camera feeds: NdiFrameSource receives and decodes the NDI HX video the phones publish, yielding BGR frames for YOLO. Without this the entire NDI->YOLO->score->FSM->OBS loop has no input from the actual cameras."
  status: resolved
  severity: blocker
  test: 2
  resolved_by: "Debug session cyndilib-ndi-hx-no-decode (commit 8048319, resolved 2026-06-12). Root cause: cyndilib's bundled NDI 6.1.1 base runtime can't drive the version-PAIRED 6.3.2 HX plugin (Processing.NDI.Plugins.IPCam.x64.dll, from the HX Driver) — connects but decodes 0 frames; OBS pairs base+plugin at 6.3.2. Fix: _prefer_system_ndi_runtime() in ndi_source.py preloads the system 6.3.2 base runtime by abspath (ctypes.WinDLL) BEFORE the first cyndilib import, so cyndilib binds to 6.3.2 — non-destructive, reversible, no site-packages edit, silent no-op on CI/Linux/headless. LIVE-VERIFIED on the real iPhone HX source: 1772 decoded frames at 1920x1080 (was 0); headless 319 passed, no regression. The version-pairing fix means a matching NDI runtime must be installed on the rig (the HX Driver / NDI Tools) — note for docs/run.md."
  reason: "Tested against a live iPhone 'NDI Camera' source (2026-06-12, real rig-style setup): cyndilib 0.1.1 CONNECTS to the phone (receiver.is_connected()=True) but decodes ZERO video frames (VideoFrameSync xres/yres stay 0) — across every color_format/bandwidth and even with OBS fully closed (so NOT a single-receiver limit). NDI Studio Monitor (system NDI 6.3.2 runtime + the installed HX Driver) shows the SAME phone fine, so the phone IS sending video and the HX is decodable — just not by cyndilib's bundled runtime."
  root_cause: "cyndilib loads its OWN bundled Processing.NDI.Lib.x64.dll (v6.1.1, in venv/Lib/site-packages/cyndilib/wrapper/bin/) which does not load the NDI HX decoder. NDI_RUNTIME_DIR_V6 is ignored (cyndilib links its bundled DLL directly), so it can't be redirected to the system runtime by env var. Phones are ALL NDI HX, so this blocks the real ingest. Invisible in CI because headless tests use the in-process mock clip source and the only prior live source was OBS PGM (full/uncompressed NDI — cyndilib decodes that fine; that path IS verified)."
  missing:
    - "A way for cyndilib's receiver to decode NDI HX: e.g. make its bundled runtime load the system HX codec/driver, replace/point the bundled Processing.NDI.Lib.x64.dll at the system NDI 6.3.2 runtime (user-authorized; DLL swap was safety-blocked this session), bump cyndilib to a version that decodes HX, or switch to an NDI binding that does. Needs a focused /gsd-debug or research session — NOT a rushed fix."
  artifacts:
    - "venv/Lib/site-packages/cyndilib/wrapper/bin/Processing.NDI.Lib.x64.dll — cyndilib's bundled NDI 6.1.1 runtime (the one that fails to decode HX)."
    - "C:/Program Files/NDI/NDI 6 Runtime/v6/Processing.NDI.Lib.x64.dll (6.3.2) + NDI 6 Tools/HX Driver — the system runtime+codec that DOES decode the phone (OBS/Studio Monitor use it)."
    - "src/segugio/ndi/ndi_source.py — NdiFrameSource._receiver_loop: receiver connects, capture_video() returns zero-res frames for HX (the NDI-03 guard then correctly skips them — the LOGIC is right; the decode upstream is the blocker)."
