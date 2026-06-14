---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 04
subsystem: robustness
tags: [watchdog, liveness, feed-death, fallback, fsm, rbt-01, rbt-02, ndi]

# Dependency graph
requires:
  - phase: 05-01
    provides: "FrameSource Protocol (last_frame_ts), Phase-5 conftest fixtures (make_config 4-cam, injected_clock), PHASE1_SURFACE harness, Wave-0 watchdog/fallback stubs"
  - phase: 03 (decision-engine-fsm)
    provides: "locked DecisionEngine.tick(scores, alive, ...) with DEC-06 alive-map exclusion + hysteresis/debounce/min_dwell guards"
  - phase: 02 (framing-scorer)
    provides: "CameraScore frozen input contract the FSM consumes"
provides:
  - "segugio.watchdog_feed.FeedWatchdog — pure last-NEW-frame liveness math (RBT-01)"
  - "FeedWatchdog.alive_map(now, frame_source, cam_ids) — the {cam: bool} map that drives engine.tick(alive=...)"
  - "End-to-end RBT-02 proof: dead feed → fallback to SAFE/other-live; recovered feed rejoins only after full hysteresis+dwell"
affects: [05-06 (orchestrator loop wires the watchdog alive map into the FSM each tick)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Clock-free injected-value liveness: now is an argument, no wall-clock stored (mirrors CompetitorLock._motion_energy / decision/ determinism)"
    - "Liveness from last-NEW-frame timestamp ONLY — never the NDI source/connection state (Pitfall 1 / 75-min freeze trap)"

key-files:
  created:
    - src/segugio/watchdog_feed/__init__.py
    - src/segugio/watchdog_feed/liveness.py
    - tests/test_watchdog.py (filled from Wave-0 stub)
    - tests/test_fallback_rejoin.py (filled from Wave-0 stub)
  modified:
    - tests/test_imports.py (added segugio.watchdog_feed to PHASE1_SURFACE)

key-decisions:
  - "Anti-jitter grace is an additive tolerance on watchdog_timeout (dead iff now-ts > timeout+grace), defaulting to 0.0; the test seeds grace=0.1 to damp single-late-frame flap (T-05-04-02)"
  - "None / non-finite last_frame_ts (and non-finite now) → DEAD fail-safe, never raises (T-05-04-03 / 'nessun crash ammesso')"
  - "alive_map reads each camera's last_frame_ts off the injected FrameSource Protocol — the watchdog holds NO per-camera state"
  - "Task 2 re-implements NO FSM logic; it is a pure integration test wiring FeedWatchdog → real DecisionEngine"

patterns-established:
  - "FeedWatchdog: pure liveness deducer with a precomputed dead-after window (timeout+grace) and a FrameTimestampSource Protocol"
  - "RBT-02 integration test idiom: drive the real engine with the real watchdog's alive map; assert the never-air-dead invariant only on ticks where alive[cam] is False (the stall must first cross timeout+grace)"

requirements-completed: [RBT-01, RBT-02]

# Metrics
duration: 9min
completed: 2026-06-11
---

# Phase 5 Plan 04: Feed Watchdog (RBT-01/02) Summary

**`FeedWatchdog` — clock-free last-NEW-frame liveness math (dead iff `now - last_frame_ts > watchdog_timeout + grace`) whose `alive` map drives the locked `DecisionEngine` to fall back off a dead feed to SAFE/another live camera and rejoin only after full hysteresis+dwell, never airing the dead feed.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-11
- **Completed:** 2026-06-11
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 test stubs filled, 1 modified)

## Accomplishments
- `FeedWatchdog` deduces liveness PURELY from the injected last-NEW-frame timestamp — never the NDI source "connected" state (the 75-min freeze trap, Pitfall 1 / RBT-01). Clock-free, stdlib-only (`math` + `typing`), deterministic on injected `(now, last_frame_ts)` pairs.
- Anti-jitter grace damps single-late-frame flap; `None`/non-finite timestamps fail safe to DEAD; the watchdog never raises (the three STRIDE mitigations T-05-04-01/02/03 all landed).
- `alive_map(now, frame_source, cam_ids)` produces the exact `{cam: bool}` map `DecisionEngine.tick(scores, alive=...)` consumes — the single liveness authority feeding DEC-06.
- End-to-end RBT-02 proof against the LOCKED FSM (no FSM logic re-implemented): a dead feed is excluded → director falls back to SAFE/another live camera; a recovered feed does NOT snap back, it must win full hysteresis+debounce+min_dwell; the never-air-a-dead-feed invariant holds across a full kill→recover sequence.
- `segugio.watchdog_feed` joins the proven lazy-import surface (`PHASE1_SURFACE`) — imports cleanly with torch/ultralytics/cyndilib/obsws absent.

## Task Commits

Each task committed atomically (Task 1 followed the TDD RED→GREEN cycle):

1. **Task 1 (RED): failing FeedWatchdog liveness tests** - `2196522` (test)
2. **Task 1 (GREEN): FeedWatchdog pure last-NEW-frame liveness** - `136185a` (feat)
3. **Task 2: wire FeedWatchdog into locked DecisionEngine (fallback+rejoin)** - `308bab7` (test)

_No REFACTOR commit — the GREEN implementation was already clean (single comparison, no duplication)._

## Files Created/Modified
- `src/segugio/watchdog_feed/liveness.py` - `FeedWatchdog` (`alive` / `alive_map`) + `FrameTimestampSource` Protocol; pure liveness math, clock-free, fail-safe.
- `src/segugio/watchdog_feed/__init__.py` - light re-export of `FeedWatchdog` / `FrameTimestampSource`.
- `tests/test_watchdog.py` - 8 RBT-01 tests over injected timestamps (advancing→alive, stalled past timeout+grace→dead, grace anti-jitter, None→dead, alive_map over a frame source, determinism).
- `tests/test_fallback_rejoin.py` - 3 RBT-02 integration tests (feed-death fallback, guarded rejoin, never-air-dead across a full sequence) against the real `DecisionEngine`.
- `tests/test_imports.py` - appended `"segugio.watchdog_feed"` to `PHASE1_SURFACE`.

## Decisions Made
- **Grace as an additive tolerance, default 0.0:** `dead iff now - last_frame_ts > watchdog_timeout + grace`. Keeps the bare-timeout semantics when no grace is configured; the orchestrator (05-06) can seed a small grace (≈1-2 ticks) to stop a single late frame flapping the feed dead (T-05-04-02).
- **Fail-safe on bad inputs:** `None`/non-finite `last_frame_ts` and non-finite `now` → DEAD, never raises — mirrors the FSM absent-from-map=NOT-alive rule (T-05-04-03).
- **Stateless watchdog:** no per-camera memory or wall-clock; `alive_map` reads each camera's timestamp off the injected `FrameSource` per call, so the same inputs always give the same answer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `segugio.watchdog_feed` to `PHASE1_SURFACE`**
- **Found during:** Task 1 (FeedWatchdog import smoke)
- **Issue:** The acceptance criterion `python -c "import segugio.watchdog_feed"` (heavy stack absent) requires the package to be on the proven lazy-import surface, but `tests/test_imports.py` was not listed in the plan's `files_modified`.
- **Fix:** Appended `"segugio.watchdog_feed"` to `PHASE1_SURFACE` (one-line edit, mirroring how `segugio.framing`/`decision`/`tracking`/`opcomm`/`ndi`/`obs` were added). The watchdog imports only `math` + `typing`, so it belongs on the surface.
- **Files modified:** tests/test_imports.py
- **Verification:** `test_phase1_surface_imports_with_heavy_deps_absent` passes (11 params); `import segugio.watchdog_feed` succeeds.
- **Committed in:** `136185a` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The addition is required to satisfy the plan's own acceptance criterion; the watchdog is pure (math+typing only) so it correctly belongs on the lazy-import surface. No scope creep.

## Issues Encountered
- **Freeze does not declare dead instantly.** The first draft of the Task-2 death loop asserted `alive[cam] is False` on the first frozen tick, but a fresh freeze is only ~1/30s stale — the watchdog correctly keeps it alive until the stall exceeds `watchdog_timeout + grace` (~0.9s ≈ 27 ticks at 30fps). Fixed the test to run the freeze long enough to cross the threshold and to assert the never-air-dead invariant only on ticks where `alive[cam]` is actually `False`. This is the correct, realistic semantics (the grace is exactly what prevents an over-eager dead declaration).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `FeedWatchdog.alive_map(now, frame_source, cam_ids)` is ready for the 05-06 orchestrator loop to call each tick (wall-clock injected by the loop) and pass straight into `DecisionEngine.tick(scores, alive=...)`.
- RBT-01 and RBT-02 are closed and proven headless; zero regression on the locked Phase-3 FSM (`test_decision_feeddeath.py` / `test_decision_hysteresis.py` green).

## Self-Check: PASSED
- `src/segugio/watchdog_feed/liveness.py` — FOUND (contains `class FeedWatchdog`, reads `watchdog_timeout`)
- `src/segugio/watchdog_feed/__init__.py` — FOUND
- `tests/test_watchdog.py` — FOUND (8 tests pass)
- `tests/test_fallback_rejoin.py` — FOUND (3 tests pass)
- Commits `2196522`, `136185a`, `308bab7` — all FOUND in git log
- Full suite: 254 passed, 9 skipped, 10 xfailed; `tests/test_decision_feeddeath.py tests/test_decision_hysteresis.py` green (zero FSM regression)

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*
