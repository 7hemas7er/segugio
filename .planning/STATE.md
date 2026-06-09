---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: ready_to_plan
stopped_at: Phase 02 complete (4/4) — ready to discuss Phase 3
last_updated: 2026-06-09T16:17:59.767Z
last_activity: 2026-06-09
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 8
  completed_plans: 8
  percent: 40
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.
**Current focus:** Phase 3 — decision engine fsm

## Current Position

Phase: 3
Plan: Not started
Status: Ready to plan
Last activity: 2026-06-09

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 4 | - | - |

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

## Accumulated Context

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Framing-scorer math (Phase 2) is dense/novel — flagged for `--research-phase` during planning (lead-room, motion-adaptive alpha, conf-norm, size band, zone multiplier)
- [Phase 4]: Native-ReID engagement on yolo26s must be verified at startup (silently downloads a fallback if the head is end2end); COCO dog recall on real footage is unmeasured — measure in Phase 4

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-09T16:00:05.430Z
Stopped at: Completed 02-03-PLAN.md
Resume file: None
