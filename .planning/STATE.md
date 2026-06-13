---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: — Console Regia
status: verifying
stopped_at: Phase 8 context gathered
last_updated: "2026-06-13T15:38:45.883Z"
last_activity: 2026-06-13
progress:
  total_phases: 9
  completed_phases: 8
  total_plans: 35
  completed_plans: 35
  percent: 89
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-13)

**Core value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.
**Current focus:** Phase 08 — console-serving-live-multiview-safety-hardening

## Current Position

Phase: 9
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-06-13
Next: `/gsd-plan-phase 7`

## Performance Metrics

**Velocity:**

- Total plans completed: 22
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 4 | - | - |
| 03 | 4 | - | - |
| 04 | 4 | - | - |
| 06 | 3 | - | - |
| 08 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 4 | 2 tasks | 12 files |
| Phase 01 P02 | 5min | 2 tasks | 7 files |
| Phase 01 P03 | 5min | 2 tasks | 6 files |
| Phase 01 P04 | 3min | 2 tasks | 4 files |
| Phase 02 P01 | 14min | 3 tasks | 19 files |
| Phase 02 P02 | 9min | 2 tasks tasks | 6 files files |
| Phase 02 P03 | 4min | 2 tasks | 3 files |
| Phase 02 P04 | 6min | 2 tasks tasks | 2 files files |
| Phase 03 P01 | 6min | 3 tasks tasks | 16 files files |
| Phase 03 P02 | 9min | 3 tasks | 4 files |
| Phase 03 P03 | 7min | 2 tasks tasks | 3 files files |
| Phase 03 P04 | 5min | 2 tasks tasks | 2 files files |
| Phase 04 P01 | 4min | 2 tasks | 11 files |
| Phase 04 P02 | 6min | 2 tasks tasks | 4 files files |
| Phase 04 P03 | 6min | 2 tasks tasks | 8 files files |
| Phase 04 P04 | 6min | 2 tasks tasks | 4 files files |
| Phase 05 P01 | 12min | 3 tasks | 27 files |
| Phase 05 P02 | 14min | 3 tasks | 9 files |
| Phase 05 P03 | 19min | 3 tasks | 10 files |
| Phase 05 P04 | 9min | 2 tasks tasks | 5 files files |
| Phase 05 P05 | 9min | 3 tasks | 7 files |
| Phase 05 P06 | 10min | 3 tasks tasks | 8 files files |
| Phase 05 P07 | 12min | 2 tasks | 5 files |
| Phase 05 P08 | 8min | 2 tasks | 4 files |
| Phase 05 P09 | 4min | 2 tasks | 6 files |
| Phase 06 P01 | 18min | 4 tasks | 8 files |
| Phase 06 P02 | 40min | 3 tasks | 5 files |
| Phase 06 P03 | 55min | 5 tasks tasks | 9 files files |
| Phase 07 P01 | 9min | 3 tasks tasks | 5 files files |
| Phase 07 P02 | 4min | 1 task tasks | 1 file files |
| Phase 07 P03 | 4min | 2 tasks | 2 files |
| Phase 07 P04 | 12min | 3 tasks tasks | 5 files files |
| Phase 08 P01 | 7min | 3 tasks | 7 files |
| Phase 08 P02 | 4min | 2 tasks | 2 files |
| Phase 08 P03 | 3min | 1 tasks | 1 files |

## Accumulated Context

### Roadmap Evolution

- Milestone v1.1 "Console Regia — visibilità live" roadmap created (2026-06-13): 3 phases appended after the v1.0 Phases 1–6 (numbering continues at Phase 7, no reset). 16/16 v1.1 requirements mapped. The shape is dependency-forced — the off-tick frame-publishing channel gates everything:
  - **Phase 7 — Off-tick Frame-Publishing Channel** (PRV-01/02/03): the gating foundation. `PreviewPublisher` daemon thread + `atomic_write_bytes` + `preview.json` sidecar publish per-camera JPEG thumbnails + the "why" data off the critical tick. Two HARD gates: (a) RBT-05 p95 unchanged with preview ON; (b) console crash-isolation proven by an import test with the heavy stack (ultralytics/torch/cv2/cyndilib) absent.
  - **Phase 8 — Console Serving, Live Multiview & Safety Hardening** (MVW-01/02/03, UXT-02): multiview grid + LIVE/tally + dead-feed marking, plus the `threaded=True`/Waitress server fix folded in as a SAFETY item (override POSTs never blocked, not cosmetic), a preview-bandwidth cap (preview degrades before NDI feeds), and a written threat re-eval (live video behind 0.0.0.0).
  - **Phase 9 — Explainability, Informed Override & Tablet UX** (MVW-04/05, WHY-01/02/03/04, SCV-01, UXT-01/03): score bars + plain-Italian reason + dog-lock bbox overlay + "auto wants vs aired" hint + switch-history strip + score preview + clickable-tile overrides + tablet restyle + leak/sleep/freshness hygiene.
- Phase 6 added (2026-06-13): Decision-loop latency optimization (TensorRT FP16 export + batched/parallel per-camera inference) to meet RBT-05 — created from the Phase 05 UAT Test 5 finding (4× yolo26s eager-FP32 measured 231–247ms p95; yolo26n ineffective on GPU). Closed under the revised <300ms budget (FP16+batch eager ~256ms cool with native ReID; TensorRT engine ~197ms optional).

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Milestone v1.1]: Console Regia is a publish-and-render problem, not compute — the orchestrator already computes per-camera scores, dog bbox, FSM reason every tick and holds the decoded frames; v1.0 discards them. v1.1 exposes them over a new off-tick file channel.
- [Milestone v1.1]: Transport = polling per-camera JPEG thumbnails over the existing atomic-file opcomm channel (separate `opcomm/preview/` dir). MJPEG / WebSocket / OBS-multiview-embed REJECTED by research (break/strain crash-isolation or add a network server on the director).
- [Milestone v1.1]: Per-camera "why" data travels in a NEW `preview.json` sidecar, NOT bloated into the safety-critical write-on-change `status.json`.
- [Milestone v1.1]: The console stays crash-isolated (imports only Flask + `segugio.opcomm`); JPEG encode happens in the orchestrator, the console only `send_file`s bytes. Proven by an import test with the heavy stack absent (the Phase 7 hard gate).
- [Milestone v1.1]: The `threaded=True`/Waitress fix is a SAFETY control (override POST must never be blocked by a preview stream), not polish — it lands in Phase 8 with the first streaming endpoint.
- [Milestone v1]: Software-complete on synthetic data (recorded clips + mock NDI); all 5 phases hardware-free on the dev box
- [Phase 1]: Curated multi-condition clip set + config contract front-loaded as the decisive de-risk
- [Phase 2/3]: Pure-logic brains (scorer, FSM) built and unit-tested in isolation on synthetic streams before YOLO is wired
- [Phase 4]: Model pin yolo26s.pt, dog=16 (verified via model.names); native-ReID BoT-SORT included in v1
- [Phase 5]: Full wiring (NDI mock + orchestrator + OBS + manual score UI) is the integration phase that closes the milestone
- [Phase ?]: [Phase 1 / 01-01]: src-layout package editable-installed; lazy-import boundary enforced by an import-smoke test (heavy deps forced absent); shared conftest fixtures seeded_rng/tmp_config/valid_config_dict seed all downstream Phase-1 tests
- [Phase ?]: [Phase 1 / 01-02]: typed pydantic v2 Config root; discipline = DiscDogProfile|AgilityProfile discriminated union on field.sport (zero-code-edit overlay/framing swap, CFG-03); loader uses yaml.safe_load only + fails fast with SystemExit(2) on any read/parse/validation error (CFG-01); model defaults yolo26s.pt/16 (CFG-04)
- [Phase ?]: [Phase 1 / 01-03]: clip-set substrate — opencv-free segugio.fixtures query API (load_manifest/select_clips/coverage_report/resolve_clip_path + 7x2 CONDITIONS/DISCIPLINES checklist) + tools/catalog_clips.py dev cataloguer (argparse footage dir at execution time, lazy cv2 probe, no ffprobe) emitting clip_manifest.yaml + condition-coverage gap report; external-dir + committed-manifest (binaries gitignored, README documents license/consent + no-hardcoded-path ingest); TST-01 complete
- [Phase ?]: [Phase 1 / 01-04]: deterministic synth substrate — score_stream (ping_pong/tie/dropout/recovery) + feed_death (death/recovery liveness) driven by an INJECTED numpy.random.Generator (pure base curve + single rng.normal jitter draw); frozen ScoreSample/FeedEvent dataclasses; same seed -> byte-identical output; no global RNG, no wall-clock; numpy+dataclasses only; TST-02 complete
- [Phase ?]: test
- [Phase 02]: framing-scorer pure substrate: frozen DetectionSignal/CameraScore/ScorerStatus + 8 numpy-only terms (centeredness, non-monotonic size band over sqrt(area) [D-02], centeredness-dominant base_score [D-01], lead_room, zone gate, EMA z-score conf_norm with sqrt(var+eps), plausibility_ok); ScorerParams 19 bounded seeds incl. positive eps wired additively into Config.scoring + both YAMLs (w_c+w_s+w_conf==1 validator); detection_stream raw-detection generator (None=dropout); FRM-01+guard green, 6 tests skip-scaffolded for 02-02/03/04 — 02-01 plan complete
- [Phase 02]: 02-02 CameraScorer present-detection path: stateful per-camera object composes the 8 pure terms into a fixed-alpha EMA-smoothed CameraScore — cold start s_0=raw_0 (D-05), lead-room ideal shifts TOWARD motion via finite-diff velocity over vel_window history with track-id-swap reset (D-06), zone gate x framing_weights[role][zone], per-camera conf z-score; fail-safe (NaN/inf->coast, np.clip on exit), clock-free, rng-free. Coast/TTL else-branch is a minimal 02-03 seam. FRM-02/03/04/06 green. — D-07 motion-adaptive alpha deferred; fixed-alpha construction seam is the hook. Phase-3 cross-dependency: alpha tuned jointly with debounce_N/min_dwell/hysteresis_margin.
- [Phase 02]: 02-03 coast/TTL dropout path (FRM-05) + MultiCamScorer fan-out: absent-detection branch counts ttl down (D-03 hold-last-then-drop) — ema HELD + status coasting while ema is not None and ttl>0, else ema=0.0 + status lost; never feeds raw=0 into the EMA. Re-acquisition before TTL resumes tracking continuously from the held value (D-04, no cold-start re-seed); NO long hold_length_s path (Phase-3 FSM scope). MultiCamScorer drives one CameraScorer per camera in deterministic order, coasting on a missing camera via .get() (T-2-01). ttl_ticks_from_seconds(ttl_seconds,fps)=ceil helper; scorer stays clock-free/rng-free. FRM-05 green; suite 116 passed, 1 skipped (only 02-04 purity left). — Coast/TTL is the single most important robustness invariant — never collapse to 0 on a miss (PITFALL 3, the worst time to cut is the blur at a catch/jump apex); the long expected-occlusion hold is deliberately deferred to the Phase-3 FSM per the D-04 hard scope line.
- [Phase 02]: 02-04 FRM-07 purity gate locked: same DetectionSignal seq (present->coast->lost->recovery) -> byte-identical CameraScore list (test_purity_determinism); word-boundary source-grep rejects any time/np.random/I-O/heavy import in framing/*.py (test_no_io_imports_in_framing, distinguishes real imports from docstring prose); segugio.framing added to PHASE1_SURFACE + explicit import-with-heavy-absent test. Coverage gate closed at 99% (scorer/signals/terms/__init__ 100%; only params.py:80 weight-sum config-load validator intentionally uncovered). Suite 124 passed, 0 skipped — Phase 2 complete, ready for verify-work. — FRM-07 is the phase's defining property: determinism is what makes the scorer unit-testable in isolation (same input stream -> same output every run/worker, the contract Phase-3 FSM and Phase-4 wiring depend on); the lazy-import boundary lets import segugio.framing work CPU-only with no GPU/NDI runtime present.
- [Phase ?]: [Phase 03 / 03-01]: transitions reclassified heavy→light and installed; segugio.decision on the lazy-import surface; DecisionEngine = transitions.Machine wrapper, target changes only in guarded before-callbacks (DEC-01); hysteresis margin+debounce_N + min_dwell + cooldown integer clocks (fps injected) → ≤1 transition on ping_pong/tie (DEC-02); SAFE sentinel (A4), status advisory (A1); NaN/inf fail-safe never raises. Seams for 03-02 holds/feed-death + 03-03 override
- [Phase ?]: [Phase 03 / 03-02]: feed-death emergency cut (DEC-06) — two feed_emergency guarded transitions (best-alive/SAFE) fired ABOVE auto_switch, bypass dwell/cooldown then re-protect the new target (D-01); hard invariant alive[target] or SAFE every tick
- [Phase ?]: [Phase 03 / 03-02]: action+occlusion holds (DEC-03/04) — holding() unless on auto_switch ONLY (death wins over hold); occlusion bound=ticks_from_seconds(hold_length_s,fps); EVERY hold mandatory tick max-capped (force-release/auto-expiry)
- [Phase ?]: [Phase 03 / 03-02]: deterministic tiebreaker (DEC-05) — incumbent-wins inside the hysteresis dead-band; no-incumbent → first config-declared camera (strict-max over cam_ids, scores-order independent); no role-priority
- [Phase ?]: [Phase 03 / 03-03]: OVERRIDE mode (RBT-03) — force/release guarded transitions as the TOP-priority tier above feed-death emergency; sticky override_cam (operator intent) distinct from the aired target (D-03)
- [Phase ?]: [Phase 03 / 03-03]: force is immediate (bypasses dwell/debounce/cooldown, D-05); forced-but-dead airs SAFE/best-live never the dead feed and snaps back on recovery while staying in OVERRIDE (D-03, reuses DEC-06 selection)
- [Phase ?]: [Phase 03 / 03-03]: release is manual-only (D-04, no auto-expire) and auto-resume reuses the normal auto_switch guard — zeroes the streak, no argmax snap, full hysteresis+min_dwell qualification (D-06, Pitfall 6)
- [Phase ?]: [Phase 03 / 03-04]: DEC-07 determinism gate — same seed + scenario → byte-identical list[Decision] across all four SCENARIOS over the FULL tick(scores, alive, holds, override) contract; fresh-engine _run driver + == over frozen output (FRM-07 analogue)
- [Phase ?]: [Phase 03 / 03-04]: two reusable hard-safety-invariant helpers (assert_no_decision_outside_guard DEC-01, assert_never_airs_dead_feed DEC-06) over (decision, alive_map) pairs, applied in all three combined scenarios (force→release→resume, hold-through-occlusion→release, live-feed-death-mid-hold death-wins); segugio.decision 100% coverage
- [Phase ?]: [Phase 04 / 04-01]: tracking substrate — lazy-import segugio.tracking surface (pure TrackingParams + signals_from_boxes, cv2 forced absent in smoke test); TrackingParams additive sub-model (TRK-04/05 seeds) wired into Config.tracking; signals_from_boxes PURE TRK-03 mapper (Results-row -> frozen DetectionSignal, float/int cast, ids=None coast); multi_track_stream deterministic N-track substrate + linear_left crossing path for 04-02; gpu marker + tracking_params/crop_geometry fixtures; 178 tests green (+11, zero regression)
- [Phase ?]: [Phase 04 / 04-02]: subject-selection brain — PURE CompetitorLock (TRK-04, zone-gate AND motion-energy acquire D-03, sticky continuity D-04, per-camera independence D-05, NaN fail-safe) + PURE PlausibilityGate (TRK-05, inter-frame teleport/size-jump reject -> None coast D-06 without poisoning prev, distinct from Phase-2 intra-frame guard D-07, reset() for re-acquire); both stdlib-only/clock-free/rng-free, unit-tested on multi_track_stream; 192 tests green (+14, zero regression)
- [Phase ?]: [Phase 04 / 04-03]: heavy-edge per-camera tracker — PerCameraTracker (TRK-01) one YOLO().track(persist=True, end2end=False, classes=[dog_idx], tracker=botsort_dog.yaml) per cam_id (never a frame list, #13107); resolve_dog_index by name (CFG-04, never hardcodes 16); assert_native_reid_engaged (TRK-02) HARD gate RAISES on the silent yolo26n-cls.pt cls fallback; ClipFrameSource (D-01) cv2 decode + overlapping L/C/R pseudo-camera crops with injected emitted-frame tick + empty-frame guard; botsort_dog.yaml (with_reid:True/model:auto/track_buffer:60); gpu autouse-skip wired in conftest.py + gpu eval skeleton SKIPs here; heavy deps lazy — import boundary holds with ultralytics/torch/cv2 absent; 195 passed +2 gpu-skip, zero regression
- [Phase ?]: [Phase 04 / 04-04]: offline clip eval (D-08) — PURE compute_metrics (id_switch_count counts across coast gaps to catch silent BoT-SORT ID swaps; lock_held_fraction; coast_count; signal_dump; cv2-free, deterministic) + heavy run_clip_eval wiring ClipFrameSource -> PerCameraTracker -> signals_from_boxes -> CompetitorLock -> PlausibilityGate -> per-camera DetectionSignal|None (the MultiCamScorer.update consumer shape); render_overlay (cv2 in-function) draws boxes/track-ids/locked-highlight/zones; HARD assert_native_reid_engaged before the loop; explicit UNVERIFIED lines (D-02); gpu overlay/metrics test SKIPs here; 208 passed +3 skip, zero regression; Phase 4 complete

- [Phase 05 / 05-01]: opcomm atomic-file channel is the single operator↔system IPC (temp+fsync+os.replace, separate files per message); read_* is boundary-safe (malformed/absent → default, never raises into the loop, RBT-04). atomic_write retries os.replace on the Windows MoveFileEx sharing-violation (Pitfall 6 reader contention) — a real Windows-portability fix surfaced by the interleaved-reader test. FrameSource/ObsController declared as light runtime_checkable Protocols (D-05/D-06); ActionHoldParams additive (D-08 seeds, motion_threshold>0/window_ticks>=1); CompetitorLock.locked_motion_energy() additive public accessor (no logic change to _motion_energy). Wave-0: 17 xfail stub files + Phase-5 conftest fixtures (make_config 4-cam/fake_frame_source/recording_obs/injected_clock/file_channel) + ndi/obs markers + Flask==3.1.3. segugio.opcomm/ndi/obs added to the import-smoke surface (lazy boundary holds with cyndilib/obsws/cv2 absent). 231 headless tests pass, 21 xfailed (remaining Wave-0 stubs), zero regression.
- [Phase ?]: 05-02: NEW-frame liveness (ts != last_ts) is the RBT-01 substrate — last_frame_ts never advances on a frozen NDI feed (Pitfall 1)
- [Phase ?]: 05-02: ndi/obs marker tests auto-skip when cyndilib/obsws absent (conftest hook mirrors the gpu gate)
- [Phase ?]: 05-03: scene_for is a pure free function (segugio.obs.mapping) sharing one camera->scene contract across the real client and the recording fake; SAFE->is_safe camera obs_scene
- [Phase ?]: 05-03: ObsWsController takes an injectable client_factory so reconnect+reauth and the overlay fallback are asserted headless with fake ReqClient/EventClient
- [Phase ?]: 05-04: FeedWatchdog pure last-NEW-frame liveness (RBT-01) — dead iff now-ts > watchdog_timeout+grace, clock-free/stdlib-only, None/non-finite ts -> dead fail-safe; never reads NDI source state (Pitfall 1)
- [Phase ?]: 05-04: RBT-02 proven as integration only (no FSM logic) — watchdog alive_map drives locked DecisionEngine.tick; dead feed -> SAFE/other-live, recovered feed rejoins only after full hysteresis+dwell, never airs dead feed
- [Phase ?]: [Phase 05 / 05-06]: Orchestrator = grown-up run_clip_eval — fixed-rate fault-isolated tick: source.latest -> per-camera fan-out (one tracker/lock/gate per cam, never a frame list #13107) -> action-hold deriver -> scorer -> watchdog alive map -> engine.tick -> obs.cut -> atomic D-11 status on change. Every stage try/except -> coast to SAFE, never crash (RBT-04); shutdown cuts to SAFE. D-08 action-hold from locked motion energy holds the cut through a catch/jump then force-releases at the DEC-03 cap. D-09 STOP parks on the SAFE SENTINEL (engine.to_safe + synthetic SAFE Decision) so status.live_cam reads SAFE; Override still wins. Trackers INJECTED (YOLO out of headless tests); locks+gates built from config. Latency probe additive in run_measured; mock-timed wiring p95 + gpu real-yolo p95<150ms (RBT-05). segugio.orchestrator on the lazy-import surface. v1 milestone closed.
- [Phase 05 / 05-08]: gap-closure code fixes — WR-04: atomic_write_text now routes its final swap through the same _atomic_replace retry as atomic_write_json, so an OBS reader holding the overlay file at the MoveFileEx instant retries instead of crashing the writer (headless test monkeypatches os.replace fail-then-succeed). CR-02: extracted the per-camera capture loop into _run_receiver (collaborators injected — the headless seam, lazy cv2/cyndilib stay in _receiver_loop); the disconnected branch now sleeps _RECEIVER_DISCONNECTED_SLEEP_S (0.05) instead of busy-spinning AND re-resolves/reconnects a late-appearing named source without a stop()/start() cycle (auto-reconnect). New tests/test_ndi_receiver_loop.py drives the loop with pure fakes (bounded → a reintroduced busy-spin would hang). Suite 302 passed / 3 skipped / 0 failures (+5 vs 05-07). Real near-zero-CPU + live cyndilib reconnect + real Windows overlay sharing-violation stay HARDWARE-deferred (D-07, human-verification #2/#4).

- [Phase 05 / 05-07]: CR-01 closed (the FAILED truth, SC-5/RBT-04) — _safe_startup fault-isolates source.start()/obs.connect() in run()/run_measured() so a down OBS/NDI at launch coasts into the tick loop (the per-tick _safe_call heals OBS, the watchdog handles a dead source — reaching the loop is sufficient for "never crash"). ObsWsController.connect() guards _cache_pip_ids() (partial connect cannot crash; ids re-cache via EventClient/per-tick reconnect). Additive Thresholds.watchdog_grace=0.067 seed; from_config sources it on grace=None, explicit wins (WR-02). Tick catch-all reason "fault" not "feed-dead" (WR-09); dead live_cam removed (WR-01, no behavior change). NEW tests/test_orchestrator_startup.py exercises the REAL run_measured startup with start()/connect() RAISING and proves the loop ticks 5× — the regression that flips Truth #5. Full headless suite 297 passed / 3 skipped / 0 failures. watchdog_grace SHIPPED tuning + real-OBS startup confirmation stay HARDWARE-deferred (D-07).
- [Phase ?]: [Phase 05 / 05-09]: UAT gap closed — build_orchestrator runtime factory maps Config -> real NdiFrameSource + ObsWsController + per-camera PerCameraTracker + opcomm channel_paths, then Orchestrator.from_config (signature unchanged); python -m segugio entry point (load_config -> build -> run; Ctrl-C -> shutdown SAFE coast, RBT-04); docs/run.md OBS-up/OBS-down rig launch. Injectable *_factory seam keeps it headless-unit-tested with the heavy stack absent; lazy-import boundary held. 314 passed / 3 skipped (+12, zero regression). UAT Tests 1-4 now launchable on the Windows/RTX rig (D-07).
- [Phase 06 / 06-02]: Batched FP16 decision-loop (the cheap rung) — Orchestrator._fan_out now runs ONE batched detection forward per tick (half=config.model.use_fp16, end2end=False) then per-camera tracker.update() dispatch (#13107-safe), selected via _supports_batched() with a serial .track() fallback so the mock-timed wiring/attribution tests stay green. PerCameraTracker gained update()/_ensure_persistent_tracker (lazy track() warmup registers the native-ReID hook + builds the persistent BoT-SORT, then drives trackers[0].update() on the batched result.feats), plus use_fp16/is_engine attributes (is_engine threaded into the once-before-loop HARD ReID gate). batched_detect_dispatch gained use_fp16. MEASURED on the RTX 4000 Ada (venv312, AC power): 4-cam loop total p95 ~210ms (211.4/209.5 two runs) on the batched FP16 path with native ReID confirmed engaged — improved from the 231-247ms FP32-serial baseline but DID NOT clear 150ms. VERDICT: FAIL → 06-03 (TensorRT engine build) AUTHORIZED. RBT-05 still NOT complete.
- [Phase 06 / 06-01]: Wave-0 latency seams landed headless (Tasks 2-4; Task 1 = blocking-human GPU-env checkpoint, see Blockers). assert_native_reid_engaged is engine-aware — an is_engine: bool = False kwarg downgrades the cls-fallback / missing-hook would-be RuntimeError to a logger.warning ONLY on engine-backed models (Open Q1 Option a; a TensorRT .engine loads via AutoBackend and structurally cannot expose the in-graph Detect head — Pitfall 1), while is_engine=False keeps the eager .pt HARD gate byte-for-byte (TRK-02). ModelConfig gained additive engine_path (Path|None=None) + use_fp16 (bool=False) defaulting to today's eager-FP32 .pt (extra=forbid preserved). New batched.py: batched_detect_dispatch runs ONE model.predict([frames]) detection forward then per-camera tracker.update() — never model.track([frames]) (#13107) — with Pitfall-4 static-batch padding of dead None slots and per-slot degrade-to-None (RBT-04), proven headless with fakes. docs/run.md "GPU latency env" section + .gitignore *.engine/*.onnx. Full headless suite green, lazy-import boundary held. RBT-05 NOT complete — every GPU measurement is blocked on Task 1.
- [Phase ?]: [Phase 06 / 06-03]: Q1 RESOLVED -> Option (a) cls-ReID fallback on the engine (gate WARNS-not-raises when is_engine=True; single-dog A2). tools/build_engine.py ships the one-time cached TensorRT FP16 build (format=engine half=True batch=4 end2end=False, static batch=4, --dynamic escape hatch). Engine-aware PerCameraTracker: loads .engine when on-disk (is_engine True), graceful eager .pt fallback on ANY failure/missing-file (RBT-04 never crash). Rule-1 fix found on the rig: a static batch=N engine REJECTS the single-frame track() warmup, so the per-camera BOTSORT is built DIRECTLY; reid gate downgrades predictor-None AND empty-predictor.trackers to warnings on the engine. MEASURED engine-path 4-cam p95 ~193-195ms on the RTX 4000 Ada Laptop GPU (AC) — STILL >= 150ms. VERDICT FAIL, RBT-05 NOT met; next lever surfaced (Option b re-plan / yolo26n engine / flagged camera-reduction ladder), re-measure on desktop deploy GPU.
- [Phase ?]: [Phase 07 / 07-01]: preview channel = existing atomic-file opcomm channel + bytes (atomic_write_bytes, fsync=False for ephemeral JPEGs, default fsync=True for durable sidecars, D-04) + one typed sidecar PreviewDoc — no new IPC/dep (D-01). preview.json rides atomic_write_json (always fsyncs); PreviewDoc mirrors DirectorStatus (frozen+normalizing, order-independent ==, hashable); read_preview reuses _read_json, safe-defaults to PreviewDoc() never raising (RBT-04). status.json/DirectorStatus byte-stable (D-03). PreviewParams additive (Config.preview ON by default D-06); Phase 8 owns the HARD bandwidth cap. 23 opcomm tests green, leaf import holds.
- [Phase ?]: [Phase 07 / 07-02]: HARD GATE 2 locked — test_app_imports_nothing_heavy now forces numpy absent too (Pitfall 2 false-green closed) AND proves the console STARTS not just imports (create_app(tmp) + GET /status → 200 with ultralytics/torch/numpy/cv2/cyndilib/obsws_python all absent, D-09 gate 2). Locks the clean Flask + segugio.opcomm import surface as a regression guard before Phase 8 adds GET /preview; ui/app.py intentionally unmodified (PRV-03).
- [Phase ?]: [Phase 07 / 07-03]: PreviewPublisher off-tick daemon — offer() is a single locked 1-slot mailbox (last-writer-wins, never blocks, D-02/PRV-01); the daemon _run does ALL resize/encode/IO off the tick at ~1/fps and coasts on fault (RBT-04 extended). _build_doc PURE (no cv2) maps the full D-07 why-payload (ema==score L242, in_zone==det-present A1, energy default 0.0); _publish writes per-cam JPEGs via atomic_write_bytes(fsync=False, D-04) then write_preview(preview.json). cv2/numpy lazy inside _cv2_encode (gate-2: imports with cv2 absent); injectable encode_fn = headless-tested. PRV-01/PRV-02 done; plan 04 wires it.
- [Phase ?]: [Phase 07 / 07-04]: hot-path preview wiring — self._preview + guarded offer() AFTER _apply INSIDE the RBT-04 tick try (publisher fault coasts via the same catch, D-02/PRV-01 criterion 5); _fan_out surfaces frames_by_cam (no second source.latest()); orchestrator-owned _cuts_ring (deque maxlen=16) fed at the _apply target-change edge (Pitfall 5); runtime preview_factory seam + construction GUARDED by config.preview.enabled (None when disabled = byte-identical-to-v1.0, D-06) + opcomm/preview/ dir. Disk-smoke writes real cam_<id>.jpg + preview.json; publisher-fault-coast proves a raising offer() rides the catch and status.json still lands (SC5). HARD GATE 1 (gpu preview-ON-vs-OFF p95 no-regression, on-rig noise band) LANDED gated behind the gpu marker — rig-deferred. PRV-01/02/03 done; D-09 done line reached.
- [Phase ?]: 08-01: numpy stays out of HEAVY_MODULES (hard runtime dep); console numpy-absent assertion via a dedicated guard test
- [Phase ?]: 08-01: preview JPEG route mitigates path traversal by whitelisting <cam> against cam_ids + a fixed cam_{id}.jpg prefix (T-05-05-01)
- [Phase ?]: [Phase 08 / 08-02]: preview-bandwidth cap (MVW-03) is a CONFIG-TIME guarantee — PreviewParams.max_total_mbps (default 8.0 Mbps) + Config._preview_bitrate_within_cap @model_validator computes worst-case fps×bytes×N_cams bitrate and rejects over-cap configs fail-fast (SystemExit(2) via loader, CFG-01); NO runtime throttle (D-01 declined). bpp=0.30 q55 calibration tunable + gated by default-passes/cranked-fails test; enabled=false short-circuits (D-09). Real-WiFi false-death validation is a hardware-milestone carry-forward (D-02).
- [Phase 08]: [Phase 08 / 08-03]: docs/security.md = the v1.1 written threat re-eval (D-09) — reaffirms LAN-as-trust-boundary single-operator no-auth posture (T-05-05-01..04, cross-referenced from ui/app.py docstrings), ADDS the live-competitor-video-behind-0.0.0.0 exposure (T-08-03, STRIDE Information Disclosure: GET /preview + GET /preview/<cam>.jpg, mitigated by the cam-id whitelist→fixed cam_{id}.jpg path + threaded=True/Waitress override-availability), and mandates AP client-isolation + no internet/guest bridge as a HARD OPERATIONAL requirement. preview.enabled is the source-side off-switch; NO new in-code auth/configurable-bind/shared-token in v1.1 (rejected). Mitigation is operational+documented, not code.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Framing-scorer math (Phase 2) is dense/novel — flagged for `--research-phase` during planning (lead-room, motion-adaptive alpha, conf-norm, size band, zone multiplier)
- [Phase 4 — RESOLVED 2026-06-10 GPU UAT]: Native-ReID engagement on yolo26s VERIFIED on RTX 4000 Ada (assert_native_reid_engaged does not raise with end2end=False → no silent yolo26n-cls.pt fallback). COCO dog recall MEASURED on the 6 hard slices: strong on close/clear (handler_close cam_c 0.89, dusk_distant 0.76, sprint_blur 0.69), weak on distant/small + crowd (distant 0.04, crowd_distractor 0.16) — candidate for dog-detector fine-tuning later. NOTE: GPU UAT also found+fixed a real bug — the tracker yaml was passed as a bare name and never resolved, so TRK-01/TRK-02 were dead on the real path (silent coast every frame); fixed in detector.py with fail-loud abs-path resolution + CPU regression test.
- [Phase 6 / 06-01 — RESOLVED 2026-06-13]: The py3.12 cu12x-torch + tensorrt GPU env (venv312: Python 3.12.10, torch 2.12.0+cu126, ultralytics 8.4.62, tensorrt-cu12 10.16.1.11, RTX 4000 Ada driver 596.36) is LIVE — torch.cuda.is_available()=True and the gpu latency test collects+runs. 06-02 RAN the gpu gate on it (p95 ~210ms). All Wave-1/Wave-2 latency work unblocked.
- [Phase 6 / 06-02 — RBT-05 gate, INFORMS 06-03]: The cheap rung (eager FP16 + ONE batched forward per tick) measured p95 ~210ms ≥ 150ms on the RTX 4000 Ada — it did NOT meet RBT-05. 06-03 (TensorRT FP16 engine build) is AUTHORIZED and required to cross the budget. 06-03 should weigh keeping FP32 detection if FP16 visibly regresses recall on real distant/dusk footage (RESEARCH A5 — not spot-checked this run; the gpu gate uses synthetic frames).
- [Phase 6 / 06-03 — RESOLVED 2026-06-13 under revised budget]: The TensorRT FP16 engine (static batch=4) measured 4-cam loop p95 ~193-195ms; the canonical FP16+batch eager path ~256ms cool — both < the revised <300ms budget → RBT-05 MET on the RTX 4000 Ada Laptop GPU. ⚠ Thermal variance (heat-soaked outlier ~546ms) → prefer a desktop deploy GPU for sustained live; original <150ms reachable only on faster/cooler hardware.
- [Milestone v1.1 — carry into Phase 9 planning]: Tablet transport (iOS Safari MJPEG support + background-tab timer/suspension) flagged for `--research-phase` if the operator tablet is an iPad/Safari; Android Chrome / desktop are standard. (Research SUMMARY gap.)
- [Milestone v1.1 — carry into Phase 7/8 planning]: Re-verify BoT-SORT native ReID actually engages on yolo26s at startup before depending on `locked`/`track_id` stability in the Phase 9 dog-lock bbox overlay; validate the <=5–8 Mbps preview bandwidth budget with phones live before Phase 8 acceptance; document the fsync-drop for ephemeral preview JPEGs explicitly in `atomic_write_bytes` so it is not silently reverted.

## Quick Tasks Completed

| Date | Slug | Summary |
|------|------|---------|
| 2026-06-12 | run-md-ndi-hx-ops-notes | docs/run.md Prerequisites: NDI Tools/HX Driver required on rig (HX decode depends on system 6.3.2 runtime), multi-homed discovery via NDI Access Manager, active camera view, don't-hardcode source names |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-13T15:24:34.887Z
Stopped at: Phase 8 context gathered
Resume file: .planning/phases/08-console-serving-live-multiview-safety-hardening/08-CONTEXT.md
