---
status: partial
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
source: [05-VERIFICATION.md]
started: 2026-06-11T14:05:00Z
updated: 2026-06-12T00:30:00Z
---

## Current Test

[Test 1 PASS — verified end-to-end against real OBS (connect + cut to SAFE confirmed by reading
the program scene back + reconnect-after-drop, all on obsws-python v5). Heavy stack installed on
the dev box; smoke test confirmed RBT-04 no-crash and fixed 4 defects (see findings). Tests 2-5
(NDI receiver, anti-jitter, full E2E, GPU latency) still need a live NDI source + the RTX GPU.
Resume the rest with `/gsd-verify-work 05` at the full rig.]

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

Headless suite: **318 passed** (global) / venv `-m "not ndi and not obs and not gpu"` all green.
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
expected: CPU for disconnected receiver threads is near-zero (no busy-spin); a named NDI source that appears after thread start auto-reconnects without stop()/start(). Watch for the WR-02 livelock risk — set_source re-issued every 50ms mid-handshake on real cyndilib.
result: blocked
blocked_by: physical-device
partial_verified: "NDI-01 RECEIVER CORE VERIFIED on real cyndilib 0.1.1 + a live NDI stream (2026-06-12, OBS DistroAV output 'MASTER (OBS PGM)' as the source). NdiFrameSource([cam@'MASTER (OBS PGM)']).start() resolved the named source via Finder, connected, and yielded a real frame shape=(1080,1920,3) uint8 BGR (NDI-03 zero-res guard + reshape RGBA->BGR correct); 20 distinct NEW timestamps in ~2s confirm RBT-01 liveness (get_timestamp_posix advances per NEW frame — [ASSUMED A1] CONFIRMED); stop() joined the threads. Also confirmed the Finder API (get_source_names/get_source) exists on 0.1.1 (the _resolve_source 'API may differ' pragma)."
reason: "STILL PENDING (the test's CR-02 headline): (a) auto-reconnect after a real drop/reappear without stop()/start() — needs the source toggled off then on mid-receive; (b) near-zero CPU on the disconnected branch (measurement); (c) the frozen-feed 'pull the cable' liveness (timestamp STOPS advancing → watchdog declares dead) — needs a real phone feed that freezes. NOTE: the phone NDI Camera was started but is NOT discoverable from the PC (only OBS PGM is) — almost certainly WiFi client-isolation / subnet split; a real-rig network item since the phones are the actual cameras."

### 3. Anti-jitter grace empirical tuning (WR-02, RBT-02)
expected: The shipped watchdog_grace=0.067 (~2 frames @30fps) tolerates single-late-frame jitter on real WiFi phone feeds without cut-storms; tune against measured jitter if needed.
result: blocked
blocked_by: physical-device
reason: "Now launchable via the runner; empirical tuning needs the live system against real WiFi phone feeds (D-07). The non-zero default is already pinned by test."

### 4. Full E2E real-stack run (D-07 — v1 milestone validation)
expected: mock NDI sender -> cyndilib -> YOLO -> score -> FSM -> OBS cut/PIP/overlay -> feed death -> SAFE fallback -> UI score entry -> overlay update all work end-to-end; OBS overlay shows operator scores; feed death triggers SAFE; UI status panel shows live camera + reason.
result: blocked
blocked_by: physical-device
reason: "Now launchable — `python -m segugio config.example.yaml` + the operator console (docs/run.md). cyndilib/obsws/cv2/CUDA/ultralytics are absent in dev (@pytest.mark.ndi/obs auto-skip). This is the v1 milestone on-Windows hardware validation (D-07)."

### 5. GPU latency budget (RBT-05)
expected: `python -m pytest tests/test_latency.py -m gpu` on the RTX 4000 Ada with yolo26s.pt and real clip frames shows decision-loop p95 < 150ms (target <80ms). If over budget, apply the _DEGRADATION_LADDER logged in loop.py. (Wiring overhead proven headless: mock-timed p95 < 50ms.)
result: blocked
blocked_by: physical-device
reason: "Needs the RTX 4000 Ada GPU box with yolo26s.pt. Independent of the runner — runnable any time via `pytest tests/test_latency.py -m gpu` on the GPU machine."

## Summary

total: 5
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 4

## Gaps

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
