---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 01
subsystem: infra
tags: [atomic-file-io, os.replace, frozen-dataclass, pydantic, protocol, pytest, flask, lazy-import]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: pydantic Config root + extra=forbid additive sub-model pattern (Thresholds/ScorerParams), shared conftest fixtures (seeded_rng/tmp_config/valid_config_dict), lazy-import boundary + import-smoke surface
  - phase: 03-decision-engine
    provides: decision.signals.OverrideCmd (force/release mutual-exclusion) + HoldInput contract the opcomm records mirror/map onto
  - phase: 04-yolo-tracking
    provides: CompetitorLock with the private _motion_energy windowed-displacement computation (D-08 source), frame_source TYPE_CHECKING lazy header
provides:
  - segugio.opcomm — atomic operator↔system file channel (atomic_write_json/text + frozen ScoreDoc/RunState/OperatorCommand/DirectorStatus + boundary-validated typed channel)
  - segugio.ndi.source.FrameSource — light per-camera latest-frame Protocol (D-05)
  - segugio.obs.controller.ObsController — light cut/PIP/overlay Protocol (D-06)
  - config.ActionHoldParams — additive D-08 action-hold seeds wired into Config
  - CompetitorLock.locked_motion_energy() — public additive accessor for D-08
  - complete Wave-0 test scaffold (17 stub files) + Phase-5 conftest fixtures + ndi/obs markers + Flask dep
affects: [05-02-ndi-frame-source, 05-03-obs-controller, 05-04-watchdog, 05-05-score-ui-flask, 05-06-orchestrator]

# Tech tracking
tech-stack:
  added: [Flask==3.1.3]
  patterns:
    - "Atomic file write: same-dir temp + flush + os.fsync + os.replace, with bounded retry on the Windows MoveFileEx sharing-violation"
    - "Boundary-validated channel read_*: malformed/absent file → safe default, never raises into the loop (RBT-04)"
    - "Light Protocol interfaces (FrameSource/ObsController) at the lazy-import boundary; heavy impls land in Wave 2"
    - "Wave-0 xfail test scaffold: every requirement has a collectable stub before its implementer lands"

key-files:
  created:
    - src/segugio/opcomm/atomic.py
    - src/segugio/opcomm/records.py
    - src/segugio/opcomm/channel.py
    - src/segugio/opcomm/__init__.py
    - src/segugio/ndi/source.py
    - src/segugio/ndi/__init__.py
    - src/segugio/obs/controller.py
    - src/segugio/obs/__init__.py
    - tests/test_atomic_io.py
    - tests/test_action_hold_config.py
    - "tests/test_{watchdog,obs_mapping,obs_reconnect,overlay,scene_template,frame_source_empty_guard,fallback_rejoin,fault_isolation,latency,ui_score,ui_run,score_display_only,action_hold,status_channel,ndi_source,ndi_mock_sender}.py (Wave-0 stubs)"
  modified:
    - pyproject.toml
    - tests/conftest.py
    - tests/test_imports.py
    - src/segugio/config/models.py
    - src/segugio/config/__init__.py
    - src/segugio/tracking/competitor_lock.py

key-decisions:
  - "Flask landed in [project.dependencies] (runtime UI tool, not [heavy]) per D-02/RESEARCH A4"
  - "Separate files per message (score/runstate/command/status) over one combined file — independent atomic swaps, no UI↔orchestrator write race"
  - "DirectorStatus alive normalized to {str: bool} for order-independent == round-trip equality"
  - "atomic_write retries os.replace on the Windows sharing-violation (PermissionError) — documented Pitfall-6 reader-contention caveat"

patterns-established:
  - "Atomic-file operator↔system channel: the single IPC primitive reused by all four operator messages (D-03/09/10/11, SCR-01)"
  - "read_* boundary returns last-good/default + logs, never raises (T-05-01-01, RBT-04)"
  - "Additive config sub-model via Field(default_factory=...) — zero schema break on extra=forbid"
  - "OperatorCommand mirrors OverrideCmd force/release rejection and maps via lazy to_override()"

requirements-completed: [SCR-01]

# Metrics
duration: 12min
completed: 2026-06-11
---

# Phase 5 Plan 01: Phase-5 Foundation + Wave-0 Scaffold Summary

**Atomic-file operator↔system channel (temp+fsync+os.replace, boundary-safe reads), light FrameSource/ObsController interfaces, additive ActionHoldParams config + CompetitorLock motion-energy accessor, and the complete 17-file Wave-0 test scaffold.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-11T08:27:41Z
- **Completed:** 2026-06-11T08:39:28Z
- **Tasks:** 3
- **Files modified:** 27 (8 src created, 3 src modified, 19 test files, pyproject + 2 config)

## Accomplishments

- `segugio.opcomm`: the atomic-file channel spine — `atomic_write_json`/`atomic_write_text` (same-dir temp + fsync + os.replace, Windows-retry), four frozen records, and a boundary-validated typed channel whose `read_*` never raises into the loop (RBT-04).
- The two structural seams Wave-2 builds against: `FrameSource` (D-05) and `ObsController` (D-06) Protocols, declared light so `import segugio.ndi`/`segugio.obs` succeed with cyndilib/obsws/cv2 absent.
- `ActionHoldParams` additive config (D-08 seeds) + `CompetitorLock.locked_motion_energy()` public accessor (no logic change to the locked Phase-4 `_motion_energy`).
- The full Wave-0 test scaffold (17 stub files), Phase-5 conftest fixtures (`make_config`/`fake_frame_source`/`recording_obs`/`injected_clock`/`file_channel`), the `ndi`/`obs` markers, and the `Flask==3.1.3` dependency — so every later Phase-5 task has its `<automated>` target already on disk (Nyquist contract satisfied).

## Task Commits

1. **Task 1: Wave-0 scaffold + conftest fixtures + markers + Flask dep** — `31697bd` (test)
2. **Task 2: Atomic-file opcomm channel** (TDD) — `320b3a5` (test RED) → `535b681` (feat GREEN)
3. **Task 3: ActionHoldParams + interfaces + motion-energy accessor** (TDD) — `caacaab` (test RED) → `968131f` (feat GREEN)

_TDD tasks 2 and 3 each produced a RED test commit then a GREEN implementation commit._

## Files Created/Modified

- `src/segugio/opcomm/atomic.py` — atomic_write_json/atomic_write_text (same-dir temp + fsync + os.replace + Windows retry)
- `src/segugio/opcomm/records.py` — frozen ScoreDoc/RunState/OperatorCommand/DirectorStatus + Discipline str-Enum
- `src/segugio/opcomm/channel.py` — typed write_*/read_* per message; read_* boundary-safe (never raises)
- `src/segugio/opcomm/__init__.py` — light re-exports
- `src/segugio/ndi/source.py` + `__init__.py` — FrameSource Protocol (start/latest/last_frame_ts/stop)
- `src/segugio/obs/controller.py` + `__init__.py` — ObsController Protocol (connect/cut/set_pip/set_overlay_text/close)
- `src/segugio/config/models.py` — ActionHoldParams sub-model + `action_hold` Config field; `config/__init__.py` re-export
- `src/segugio/tracking/competitor_lock.py` — additive `locked_motion_energy()` (reads `_motion_energy`, no logic change)
- `pyproject.toml` — Flask==3.1.3 dep; ndi/obs pytest markers
- `tests/conftest.py` — Phase-5 fixtures (Phase-1 fixtures untouched)
- `tests/test_atomic_io.py`, `tests/test_action_hold_config.py` — real assertions (flipped from xfail)
- `tests/test_imports.py` — extended import-smoke surface (opcomm/ndi/obs)
- 15 additional Wave-0 stub files — collectable xfail skeletons for 05-02..05-06

## Decisions Made

- Flask added to `[project.dependencies]` (runtime UI tool) rather than `[heavy]` — D-02 + RESEARCH A4.
- Separate per-message files (score/runstate/command/status) over one combined file — independent atomic swaps avoid a UI-write racing the orchestrator status-write (RESEARCH Pattern 3).
- `DirectorStatus.alive` normalized to `{str: bool}` at construction so `==` round-trip equality is dict-order independent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Windows os.replace sharing-violation on concurrent reader**
- **Found during:** Task 2 (atomic channel GREEN)
- **Issue:** On Windows, `os.replace(tmp, target) → MoveFileEx` raises `PermissionError [WinError 5]` when a reader holds the target open at the instant of the swap. The `test_interleaved_reader_never_partial` test (a reader thread + 500 rapid writes) surfaced it — exactly the documented Pitfall 6 caveat ("readers open-read-close quickly; the orchestrator reads its files with retry-on-PermissionError").
- **Fix:** Added a bounded retry loop (`_atomic_replace`, 50× / 1ms backoff) around `os.replace` in `atomic.py`. The write+fsync already completed; only the final rename is retried, so atomicity is preserved. Also hardened the test's reader to tolerate the transient `PermissionError` mid-rename (the correct real-reader behavior).
- **Files modified:** src/segugio/opcomm/atomic.py, tests/test_atomic_io.py
- **Verification:** `python -m pytest tests/test_atomic_io.py` → 8 passed, no warnings.
- **Committed in:** `535b681` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Test helper missing DetectionSignal.tick**
- **Found during:** Task 3 (accessor GREEN)
- **Issue:** The new `_signal` test helper in `test_action_hold_config.py` omitted the required `tick` field of `DetectionSignal`, raising a TypeError.
- **Fix:** Added the `tick` argument (this was a defect in test code I authored this plan, not production code).
- **Files modified:** tests/test_action_hold_config.py
- **Verification:** Task-3 verify set → 73 passed.
- **Committed in:** `968131f` (Task 3 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 bugs — 1 production Windows-portability fix, 1 test-helper fix)
**Impact on plan:** The Windows-retry fix is a correctness requirement for the locked Windows-native target (D-01) and the no-crash live invariant. No scope creep.

## Issues Encountered

- The default Windows Python on PATH (3.14) had no pytest/venv; resolved by `pip install -e ".[dev]"` (installs into the active 3.14 interpreter, which satisfies `requires-python>=3.12`). The heavy stack (cyndilib/obsws/cv2) is genuinely absent here, which conveniently makes the lazy-import-boundary assertions real rather than mocked.

## Known Stubs

The 15 not-yet-implemented Wave-0 test files are **intentional** xfail scaffolds (the plan's explicit deliverable — collectable skeletons each Wave-2 implementer flips to real assertions). They are NOT product stubs: no hardcoded UI data, no placeholder rendering. Each is keyed to a requirement + the plan that lands it (05-02..05-06) per 05-VALIDATION.md §Wave 0. `test_atomic_io.py` and `test_action_hold_config.py` were flipped to real passing assertions in this plan.

## Next Phase Readiness

- Wave-2 plans (05-02 NDI, 05-03 OBS, 05-04 watchdog, 05-05 UI, 05-06 orchestrator) can now run against stable contracts: the opcomm channel, the FrameSource/ObsController Protocols, ActionHoldParams, and the motion-energy accessor are all on disk.
- The heavy NDI/OBS/GPU paths and the real cyndilib/obsws clients remain Wave-2 + on-Windows-E2E work (markers `ndi`/`obs`/`gpu` reserved, stubs in place).

## Self-Check: PASSED

All created files verified on disk (opcomm package, ndi/obs interfaces, SUMMARY) and all 6 commits (31697bd, 320b3a5, 535b681, caacaab, 968131f, a42f826) confirmed in git log.

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*
