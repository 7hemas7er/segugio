---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 07
subsystem: orchestrator
tags: [robustness, fault-isolation, obs-websocket, watchdog, pytest, rbt-04]

# Dependency graph
requires:
  - phase: 05 (05-06)
    provides: Orchestrator run()/run_measured() fixed-rate fault-isolated tick
  - phase: 05 (05-03)
    provides: ObsWsController connect()/reconnect with cached PIP ids
  - phase: 05 (05-04)
    provides: FeedWatchdog grace-aware liveness math + Thresholds seeds
provides:
  - "_safe_startup: source.start()/obs.connect() fault-isolation so a down OBS/NDI at launch coasts into the tick loop (CR-01, the FAILED truth SC-5/RBT-04)"
  - "ObsWsController.connect() partial-connect guard: _cache_pip_ids() failure cannot crash"
  - "Thresholds.watchdog_grace additive config seed (non-zero anti-jitter grace, WR-02)"
  - "Distinct 'fault' status reason for non-feed faults (WR-09)"
  - "tests/test_orchestrator_startup.py — the startup-fault regression that flips Truth #5 to VERIFIED"
affects: [05-verification, hardware-milestone, phase-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_safe_startup: per-startup-call try/except coast — the startup analogue of the per-tick _to_safe fault sink"
    - "config-sourced defaults via grace=None sentinel (explicit arg wins, else config seed)"

key-files:
  created:
    - tests/test_orchestrator_startup.py
  modified:
    - src/segugio/orchestrator/loop.py
    - src/segugio/obs/obsws_controller.py
    - src/segugio/config/models.py
    - tests/test_fault_isolation.py

key-decisions:
  - "Startup fault-isolation reaches the tick loop rather than retrying connect: the per-tick ObsWsController._safe_call already heals OBS reconnection each tick and the watchdog handles a dead source, so coasting into the loop is sufficient for 'never crash'"
  - "watchdog_grace default 0.067 (≈2 frames @30fps) is a headless-fixed seed; the SHIPPED empirical value stays human-deferred (VERIFICATION human-verify #3)"
  - "Non-feed faults labelled 'fault', genuine feed deaths keep 'feed-dead' in _status_for — operator-trust correctness, not a security change"

patterns-established:
  - "_safe_startup(label, fn): a one-call startup fault sink mirroring the per-tick coast; used by both run() and run_measured()"
  - "Config-seeded optional defaults: param default None → resolve from config.thresholds.* when None, explicit value overrides"

requirements-completed: [RBT-04, RBT-01]

# Metrics
duration: 12min
completed: 2026-06-11
---

# Phase 5 Plan 07: Startup Fault-Isolation (CR-01 close) Summary

**source.start()/obs.connect() fault-isolated via _safe_startup so a down OBS/NDI at launch coasts into the tick loop, plus a guarded partial connect, a non-zero config-sourced watchdog grace, a distinct 'fault' reason, and the headless regression that flips Truth #5 (SC-5/RBT-04) to VERIFIED**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-06-11
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- **CR-01 closed** — `Orchestrator.run()` and `run_measured()` now wrap `source.start()` and `obs.connect()` in `_safe_startup`, so a `ConnectionError` from a down OBS at launch (a normal field condition) is caught, logged, and the tick loop still runs. The process no longer exits before the loop starts.
- **Partial-connect guard** — `ObsWsController.connect()` wraps `_cache_pip_ids()` in try/except (still setting `_connected = True`), so OBS coming up mid-connect cannot crash; ids re-cache via the EventClient callback / per-tick reconnect. The client-build failure itself is NOT swallowed (it surfaces to `_safe_startup`).
- **WR-02 closed** — additive `Thresholds.watchdog_grace = 0.067` seed; `from_config` sources it when `grace is None`, an explicit grace still wins. `from_config(...)` now yields a non-zero anti-jitter grace by default.
- **WR-09 closed** — the tick catch-all reports `reason="fault"` (not the mislabelled "feed-dead"); genuine feed deaths keep "feed-dead" in `_status_for`.
- **WR-01 closed** — the dead `live_cam` local in `_status_for` was removed with zero behavior change (`DirectorStatus(live_cam=target, ...)` preserved; "SAFE" sentinel intact).
- **Regression coverage** — new `tests/test_orchestrator_startup.py` exercises the REAL `run_measured` startup path with a source/obs that RAISE on `start()`/`connect()` and proves the loop ticks 5×. Plus a partial-connect test in `test_fault_isolation.py`.

## Task Commits

1. **Task 1: Fault-isolate startup + non-zero grace + distinct fault reason (CR-01, WR-02, WR-09, WR-01)** - `4c33415` (fix)
2. **Task 2: Startup-fault regression test (closes the CR-01 test gap)** - `cdc0fb8` (test)

## Files Created/Modified

- `src/segugio/orchestrator/loop.py` - Added `_safe_startup`; wrapped startup in `run()`/`run_measured()`; `from_config` grace `None`-sentinel sourcing from config; tick catch-all reason `"fault"`; removed dead `live_cam`.
- `src/segugio/obs/obsws_controller.py` - Guarded `_cache_pip_ids()` inside `connect()`; `_connected = True` still reached on id-cache failure.
- `src/segugio/config/models.py` - Additive `Thresholds.watchdog_grace` (`ge=0.0`, default 0.067).
- `tests/test_orchestrator_startup.py` - 5 new headless tests: survive connect()/start() raising; grace nonzero-by-default; grace config/explicit override; non-feed fault reason != "feed-dead".
- `tests/test_fault_isolation.py` - `test_partial_connect_does_not_crash`.

## Decisions Made

- Startup fault-isolation **reaches the tick loop** rather than retrying connect at startup — the per-tick `_safe_call` heals OBS and the watchdog handles a dead source, so coasting in is sufficient for "never crash".
- `watchdog_grace` default 0.067 is a **headless-fixed seed**; the SHIPPED empirical value stays human-deferred per VERIFICATION human-verify #3.
- Non-feed faults get the **distinct `"fault"`** advisory; `"feed-dead"` is reserved for genuine feed deaths in `_status_for` — operator-trust correctness.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The local pytest output suppressed the summary footer over piped stdout; resolved by capturing the exit code (`EXIT=0`) and filtering the summary line through a Python one-liner. Final headless run: **297 passed, 3 skipped, 6 deselected, 0 failures** (grown from the ≥291 baseline + the new tests).
- `make_config(overrides={"thresholds": {...}})` does a shallow dict update that REPLACES the whole thresholds block — the config-grace test passes the full thresholds dict (every required key present) so validation succeeds. Documented inline in the test.

## Verification

Targeted (all green, exit 0):
- `python -m pytest tests/test_orchestrator_startup.py tests/test_fault_isolation.py` → 10 passed
- `python -m pytest tests/test_fault_isolation.py tests/test_latency.py tests/test_watchdog.py tests/test_fallback_rejoin.py tests/test_status_channel.py` → exit 0
- `python -c "import segugio.orchestrator.loop, segugio.obs.obsws_controller, segugio.config.models"` → exit 0 (lazy-import boundary intact)
- `python -c "from segugio.config.models import Thresholds; assert Thresholds().watchdog_grace > 0.0"` → 0.067

Full headless: `python -m pytest -m "not gpu and not ndi and not obs"` → **297 passed, 3 skipped, 0 failures**.

### Hardware-deferred (NOT closed in code — remain human-verification on the Windows/RTX box, D-07)

- Real OBS startup-crash confirmation on the live obsws stack (start `run()` with OBS down, confirm it ticks and reconnects when OBS starts).
- Anti-jitter grace empirical tuning on real measured jitter (code default 0.067s is fixed headless; SHIPPED value stays human).
- Full E2E real-stack run (D-07) and GPU latency budget RBT-05 — unaffected by this plan, remain deferred.

## Next Phase Readiness

- CR-01 (the single FAILED truth, SC-5/RBT-04) is closed with real headless regression coverage — re-verification should flip Truth #5 to VERIFIED.
- WR-01/02/09 loop.py code-quality warnings folded in; no remaining loop.py warnings from this gap source.
- The hardware-deferred items above remain the only open verification surface for this plan.

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*

## Self-Check: PASSED

- FOUND: tests/test_orchestrator_startup.py
- FOUND commit: 4c33415 (Task 1)
- FOUND commit: cdc0fb8 (Task 2)
- Full headless suite: 297 passed, 0 failures
