---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 05-07-PLAN.md
last_updated: "2026-06-13T00:40:02.587Z"
last_activity: 2026-06-11 -- Phase 05 execution started
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 25
  completed_plans: 25
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.
**Current focus:** Phase 05 — integration-ndi-mock-orchestrator-obs-score-ui

## Current Position

Phase: 05 (integration-ndi-mock-orchestrator-obs-score-ui) — EXECUTING
Plan: 2 of 9
Status: Ready to execute
Last activity: 2026-06-11 -- Phase 05 execution started

Progress: [████████░░] 80% (4/5 phases verified-complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 16
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 4 | - | - |
| 03 | 4 | - | - |
| 04 | 4 | - | - |

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

## Accumulated Context

### Roadmap Evolution

- Phase 6 added (2026-06-13): Decision-loop latency optimization (TensorRT FP16 export + batched/parallel per-camera inference) to meet RBT-05 <150ms — created from the Phase 05 UAT Test 5 finding (4× yolo26s eager-FP32 measured 231–247ms p95; yolo26n ineffective on GPU). The milestone's latency success criterion is not met until this lands.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Framing-scorer math (Phase 2) is dense/novel — flagged for `--research-phase` during planning (lead-room, motion-adaptive alpha, conf-norm, size band, zone multiplier)
- [Phase 4 — RESOLVED 2026-06-10 GPU UAT]: Native-ReID engagement on yolo26s VERIFIED on RTX 4000 Ada (assert_native_reid_engaged does not raise with end2end=False → no silent yolo26n-cls.pt fallback). COCO dog recall MEASURED on the 6 hard slices: strong on close/clear (handler_close cam_c 0.89, dusk_distant 0.76, sprint_blur 0.69), weak on distant/small + crowd (distant 0.04, crowd_distractor 0.16) — candidate for dog-detector fine-tuning later. NOTE: GPU UAT also found+fixed a real bug — the tracker yaml was passed as a bare name and never resolved, so TRK-01/TRK-02 were dead on the real path (silent coast every frame); fixed in detector.py with fail-loud abs-path resolution + CPU regression test.

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

Last session: 2026-06-11T16:22:10.256Z
Stopped at: Completed 05-07-PLAN.md
Resume file: None
