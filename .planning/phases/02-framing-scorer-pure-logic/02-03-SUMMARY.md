---
phase: 02-framing-scorer-pure-logic
plan: 03
subsystem: scoring
tags: [framing-scorer, coast-ttl, dropout, multicam, fan-out, fail-safe, numpy, stateful]

# Dependency graph
requires:
  - phase: 02-framing-scorer-pure-logic
    provides: "02-02: CameraScorer present-detection path (composes the 8 pure terms into a fixed-alpha EMA-smoothed CameraScore) with self.ttl/self.ttl_ticks/self.ema/self.status/self.last_track state seeded on the tracking branch + a minimal coast/TTL else-branch placeholder"
provides:
  - "CameraScorer coast/TTL dropout path (FRM-05, D-03 hold-last-then-drop): on a missing/implausible/NaN-inf detection ttl-=1; ema held + status coasting while ema is not None and ttl>0; else ema=0.0 + status lost — never feeds raw=0 into the EMA"
  - "Recovery-without-re-seed (D-04): re-acquisition before TTL expiry resumes status tracking and continues the EMA from the held value (no cold-start); only a new track_id after lost cold-starts"
  - "MultiCamScorer per-camera fan-out (segugio.framing.scorer): one CameraScorer per camera; update(dets_by_cam, tick) -> list[CameraScore] in deterministic camera order; a missing camera coasts via dets_by_cam.get() (never KeyError)"
  - "ttl_ticks_from_seconds(ttl_seconds, fps) pure stdlib helper (math.ceil) — clock-free ttl_seconds->ticks for the orchestrator/tests"
  - "MultiCamScorer + ttl_ticks_from_seconds re-exported from segugio.framing"
  - "Green FRM-05 coast tests (test_framing_coast.py): coast-then-lost timeline + recovery-before-TTL + MultiCamScorer fan-out/missing-camera-coasts + ttl_ticks_from_seconds"
affects: [02-04-purity-gate, 03-fsm-switching, 04-yolo-tracker-wiring, 05-orchestrator-wiring]

# Tech tracking
tech-stack:
  added: []   # no new packages — numpy + stdlib (math) only
  patterns:
    - "Coast/TTL as a bounded integer countdown reset to ttl_ticks on every present detection; the absent branch holds the EMA (never feeds 0) until ttl==0 then drops to 0/lost (D-03 hold-last-then-drop, threat T-2-01 DoS mitigation)"
    - "Recovery continuity: the present-branch's `ema if self.ema is None else <recurrence>` means a re-acquisition before TTL blends from the held EMA (no re-seed) — only a track-id change after lost cold-starts (D-04)"
    - "MultiCamScorer fan-out over an insertion-ordered dict[cam_id, CameraScorer]; dets_by_cam.get(cam_id) degrades a missing camera to its coast path (never KeyError)"
    - "Coast test mirrors test_framing_ema's full-frame neutral-zone scorer (zone multiplier 1.0 isolates the TTL state machine) + test_feeddeath_timeline_boundaries' by-tick parametrize style"

key-files:
  created: []
  modified:
    - src/segugio/framing/scorer.py
    - src/segugio/framing/__init__.py
    - tests/test_framing_coast.py

key-decisions:
  - "D-03 hold-last-then-drop implemented in the absent branch: self.ttl -= 1; if self.ema is not None and self.ttl > 0 -> status coasting (HOLD self.ema, never feed raw=0); else self.ema = 0.0 + status lost — proven by test_coast_then_lost (held > 0 for ttl_ticks-1 misses, never 0 mid-window, 0/lost at expiry)"
  - "D-04 recovery-without-re-seed: NO long hold_length_s path added (grep-asserted absent); the present-branch's `ema is not None` check makes recovery blend from the held value — proven by test_recovery_before_ttl cross-checking against a fresh cold-start raw_0"
  - "ttl_ticks accepted directly at construction (clock-free); ttl_ticks_from_seconds(ttl_seconds, fps)=ceil(ttl_seconds*fps) added as the orchestrator/test convenience (math.ceil, >=1 coast tick for any positive ttl_seconds)"
  - "MultiCamScorer holds one independent CameraScorer per camera in insertion order; a camera absent from the per-tick map coasts via .get() rather than raising (T-2-01)"

patterns-established:
  - "CameraScorer.update() absent branch: ttl countdown -> coasting (hold) | lost (ema=0.0); the np.clip(ema or 0.0) return is unchanged from 02-02"
  - "MultiCamScorer.update(dets_by_cam, tick): list comprehension over self.scorers.items() in fixed order, each fed dets_by_cam.get(cam_id) -> one CameraScore per camera"

requirements-completed: [FRM-05]

# Metrics
duration: 4min
completed: 2026-06-09
---

# Phase 2 Plan 03: CameraScorer coast/TTL dropout path + MultiCamScorer fan-out Summary

**The coast/TTL dropout path (FRM-05) that completes the `CameraScorer`: on a missing detection the EMA is HELD (status `coasting`) for the short blur-gap TTL window, then dropped to 0 + `lost` at expiry — never feeding `raw=0` into the EMA (D-03); a re-acquisition before expiry resumes `tracking` continuously from the held value with no cold-start re-seed (D-04); plus a `MultiCamScorer` fan-out that drives one `CameraScorer` per camera per tick (coasting on a missing camera, never raising) and a clock-free `ttl_ticks_from_seconds` helper — all proven by a green `test_framing_coast.py`.**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-06-09
- **Tasks:** 2
- **Files modified:** 3 (0 created, 3 modified)

## Accomplishments
- **Coast/TTL dropout path (FRM-05, D-03):** replaced the 02-02 `# 02-03: coast/TTL` placeholder else-branch in `CameraScorer.update()` with the real countdown — `self.ttl -= 1`; if `self.ema is not None and self.ttl > 0` → status `coasting` (the EMA is HELD, never touched; `raw=0` is never fed into the recurrence — the "never collapse at the catch/jump apex" invariant, PITFALL 3); else `self.ema = 0.0` + status `lost`.
- **Recovery-without-re-seed (D-04):** no `hold_length_s` long-occlusion path was added (grep-asserted absent — the long hold is a Phase-3 FSM concern). The 02-02 present-branch's `raw if self.ema is None else <recurrence>` already gives recovery continuity: a re-acquisition before TTL expiry blends from the held EMA (no cold-start re-seed); only a new `track_id` after `lost` cold-starts.
- **MultiCamScorer fan-out:** holds one independent `CameraScorer` per camera in an insertion-ordered `dict`; `update(dets_by_cam, tick)` returns one `CameraScore` per camera in deterministic camera order; a camera absent from `dets_by_cam` (or mapped to `None`) flows into that camera's coast path via `dets_by_cam.get(cam_id)` — never a `KeyError` (threat T-2-01).
- **`ttl_ticks_from_seconds(ttl_seconds, fps)`:** a pure stdlib `math.ceil` helper mapping the config's `ttl_seconds` to a positive integer tick count (≥1 for any positive `ttl_seconds`); the scorer itself stays clock-free by taking `ttl_ticks` directly.
- **Re-exports:** `MultiCamScorer` and `ttl_ticks_from_seconds` added to `segugio.framing` imports + `__all__`.
- **FRM-05 tests green:** `test_framing_coast.py` filled (skip marker removed) with `test_coast_then_lost` (coast-then-lost timeline + never-zero-mid-window invariant), `test_recovery_before_ttl` (parametrized gap=1 and ttl_ticks-1, with a cold-start cross-check proving no re-seed), `test_multicam_fanout_one_score_per_camera`, `test_multicam_missing_camera_coasts`, and `test_ttl_ticks_from_seconds_ceils_positive`.
- **Full suite:** **116 passed, 1 skipped** (up from the 110/2 baseline; the 6 new coast tests are green, only `test_framing_purity` remains skip-scaffolded for 02-04). No regression. Framing coverage **97%** (`scorer.py` 98%).

## Task Commits

Each task was committed atomically:

1. **Task 1: coast/TTL dropout path + MultiCamScorer fan-out** — `b5d9ce9` (feat)
2. **Task 2: fill FRM-05 coast/TTL tests green** — `e93d9db` (test)

_TDD note: the RED state for this plan was the pre-existing skip-scaffolded `test_framing_coast.py` (a `raise AssertionError("filled by 02-03")` behind a `pytest.mark.skip`). Task 1 implemented the coast/TTL branch + MultiCamScorer (verified GREEN at its own commit via the four 02-02 present-path behavior tests staying green + the importability and negative-grep acceptance gates); Task 2 then removed the skip and filled the coast/recovery/fan-out assertions GREEN. As in 02-02, the `tdd="true"` tasks are a coupled implementation+test pair because the coast tests target the branch created in Task 1._

## Files Created/Modified
- `src/segugio/framing/scorer.py` — **modified.** Replaced the coast/TTL placeholder else-branch with the D-03 countdown (`ttl -= 1` → `coasting` hold | `lost` + `ema=0.0`); added the `ttl_ticks_from_seconds` module helper and the `MultiCamScorer` class; updated `__all__` and the module docstring (removed the literal `hold_length_s` token from prose to keep the D-04 scope-line grep gate clean — the long hold is described as "the long expected-occlusion hold (tunnels / contact equipment)").
- `src/segugio/framing/__init__.py` — **modified.** Re-export `MultiCamScorer` + `ttl_ticks_from_seconds` (added to the `.scorer` import + `__all__`); updated the plan-progression docstring line.
- `tests/test_framing_coast.py` — **modified.** Removed the 02-01 skip marker + stub; added the coast-then-lost timeline test, the parametrized recovery-before-TTL test (with a `_cold_start_raw` cross-check proving no re-seed), the two `MultiCamScorer` fan-out tests, and the `ttl_ticks_from_seconds` test.

## Decisions Made
- **D-03 implemented exactly per RESEARCH lines 547-553:** `self.ttl -= 1`; `self.ema is not None and self.ttl > 0` → `coasting` (hold); else `ema=0.0` + `lost`. The `np.clip(self.ema if self.ema is not None else 0.0, ...)` return is unchanged from 02-02, so a `lost` tick returns exactly `0.0`.
- **`ttl_ticks_from_seconds` added (Claude's-Discretion TTL plumbing):** a `math.ceil` helper for orchestrator/test convenience; the scorer stays clock-free by taking `ttl_ticks` directly at construction. `ceil` guarantees ≥1 coast tick for any positive `ttl_seconds`.
- **MultiCamScorer uses `dets_by_cam.get(cam_id)`** (not `[cam_id]`) so a missing camera coasts rather than raising — the explicit T-2-01 mitigation the threat register calls for.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing test coverage for a documented must-have] Added MultiCamScorer + ttl_ticks_from_seconds tests**
- **Found during:** Task 2 (running the per-wave coverage gate)
- **Issue:** The plan's Task 2 `<action>` focused the named test commands on `test_coast_then_lost` + the recovery case, but the plan's `must_haves.truths` and Task 1 `<behavior>` both list the `MultiCamScorer` fan-out (one `CameraScore` per camera; missing camera coasts) as an FRM-05 must-have, and the coverage gate showed `MultiCamScorer.__init__`/`update` and `ttl_ticks_from_seconds` unexercised (scorer.py 94%).
- **Fix:** Added `test_multicam_fanout_one_score_per_camera`, `test_multicam_missing_camera_coasts`, and `test_ttl_ticks_from_seconds_ceils_positive` to `test_framing_coast.py` — proving the documented fan-out must-have and closing the coverage to 98% (scorer.py) / 97% (framing).
- **Files modified:** tests/test_framing_coast.py
- **Verification:** all six coast tests green; full suite 116 passed, 1 skipped.
- **Committed in:** `e93d9db` (Task 2 commit)

**2. [Rule 3 - Blocking acceptance gate] Removed the literal `hold_length_s` token from scorer prose**
- **Found during:** Task 1 (running the acceptance gates)
- **Issue:** Task 1's acceptance gate requires `grep -nE "hold_length_s" src/segugio/framing/scorer.py` to return NO matches (the D-04 scope-line check). My initial docstring/comment prose documented the scope line using the literal `hold_length_s` token, which the grep matched (2 hits), tripping the gate even though no `hold_length_s` *code path* exists.
- **Fix:** Rephrased the docstring + comment to describe the boundary without the literal token ("the long expected-occlusion hold (tunnels / contact equipment) is a Phase-3 FSM concern and is deliberately NOT implemented here (D-04 hard scope line)"). The D-04 intent (no long-hold logic) is unchanged and still documented; the grep gate now returns no matches.
- **Files modified:** src/segugio/framing/scorer.py
- **Verification:** `grep -nE "hold_length_s" src/segugio/framing/scorer.py` exits 1 (no matches).
- **Committed in:** `b5d9ce9` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (Rule 2 added must-have coverage; Rule 3 unblocked an acceptance gate). No scope change, no behavior change to the coast/TTL logic — the coast path matches RESEARCH lines 547-553 verbatim.

## Issues Encountered
None beyond the two auto-fixed items above. The 02-02 `CameraScorer` left the coast state (`self.ttl`/`self.ema`/`self.status`/`self.last_track`) seeded exactly as the plan's interface described, so the else-branch replacement was a clean drop-in; the present-path and EMA machinery were not touched.

## User Setup Required
None — no external service configuration. Phase 2 installs no new packages (all deps vetted in Phase 1).

## Threat Flags
None — no new network endpoints, auth paths, file access, or trust-boundary schema beyond the plan's `<threat_model>`. T-2-01 (coast-collapse DoS / missing-camera KeyError) is mitigated by the bounded integer TTL countdown that never feeds 0 into the EMA + `MultiCamScorer.update`'s `dets_by_cam.get()`; the never-zero-mid-window invariant is asserted by `test_coast_then_lost`. T-2-03 (bad `ttl_seconds`/`ttl_ticks`) is mitigated by the Phase-1-validated `ScorerParams.ttl_seconds` (`gt 0`) + `ttl_ticks_from_seconds`' `ceil` to a positive int. T-2-SC (installs) — no new packages.

## Known Stubs
None. The coast/TTL path is fully implemented (no placeholder remains in `CameraScorer.update`). The only remaining skip in the suite is `test_framing_purity.py`, which is 02-04's scope (determinism + no `time`/`np.random`/I-O in `framing/`) — a documented wave boundary, not a stub in this plan's deliverables.

## Next Phase Readiness
- **02-04 (purity gate)** can now fill `test_framing_purity.py`: the whole `segugio.framing` surface (now incl. the coast/TTL branch + `MultiCamScorer` + `ttl_ticks_from_seconds`) is clock-free and RNG-free (`grep -nE "import time|np\.random" src/segugio/framing/scorer.py` returns no matches) and imports only numpy + stdlib `math`/`collections` + the framing records/terms. The determinism assertion (same `list[DetectionSignal | None]` → byte-identical `list[CameraScore]`) holds for both the single-camera and the multi-camera paths.
- **Phase 3 (FSM)** consumes the `CameraScore.status ∈ {tracking, coasting, lost}` the scorer now emits, and drives the long expected-occlusion hold (`hold_length_s`) the scorer deliberately does NOT implement (D-04 boundary held). The Phase-3 cross-dependency flagged in 02-02 (the fixed EMA `alpha` tuned jointly with `debounce_N`/`min_dwell`/`hysteresis_margin`) still stands.
- **Phase 4/5** map a YOLO+BoT-SORT result row → `DetectionSignal` (or `None`) and drive `MultiCamScorer.update(dets_by_cam, tick)` per loop tick; `ttl_ticks_from_seconds(params.ttl_seconds, fps)` converts the config seconds to ticks at the real loop rate.
- No blockers.

## Self-Check: PASSED

- `src/segugio/framing/scorer.py` contains `class MultiCamScorer`, `def ttl_ticks_from_seconds`, and the `ScorerStatus.coasting`/`ScorerStatus.lost` assignments in the absent branch (verified on disk).
- `tests/test_framing_coast.py` has 0 `pytest.mark.skip` markers and 6 green tests (verified).
- Both task commits (`b5d9ce9`, `e93d9db`) are in the git log.
- Full suite: 116 passed, 1 skipped (no regression of the 110-test baseline; FRM-05 coast/recovery/fan-out green; only the 02-04 purity scaffold still skips). Framing coverage 97%.

---
*Phase: 02-framing-scorer-pure-logic*
*Completed: 2026-06-09*
