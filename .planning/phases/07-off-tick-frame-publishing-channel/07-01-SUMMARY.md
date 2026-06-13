---
phase: 07-off-tick-frame-publishing-channel
plan: 01
subsystem: opcomm
tags: [opcomm, atomic-write, sidecar, pydantic, config, preview]

# Dependency graph
requires:
  - phase: 05-wiring-integration
    provides: "opcomm atomic-file channel (atomic_write_text/json, _atomic_replace MoveFileEx-retry, DirectorStatus + read_status/write_status, _read_json safe-default boundary)"
  - phase: 01-foundation
    provides: "pydantic v2 Config root + additive sub-model pattern (ActionHoldParams)"
provides:
  - "atomic_write_bytes(path, data, *, fsync=True) — the binary atomic writer for the preview JPEGs"
  - "PreviewDoc frozen dataclass — the typed preview.json sidecar record (full D-07 why-payload)"
  - "read_preview / write_preview — the safe-default never-raise sidecar boundary"
  - "PreviewParams config sub-model + Config.preview (enabled/fps/max_width/jpeg_quality)"
affects: [phase-07-plan-03-PreviewPublisher, phase-07-plan-04-wiring, phase-08-console-multiview, phase-09-explainability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Preview channel = existing atomic-file opcomm channel extended with bytes + one typed sidecar (no new IPC, no new dep — D-01)"
    - "fsync gate on the binary writer: fsync=False for ephemeral JPEGs, default fsync=True for durable sidecars (D-04)"

key-files:
  created:
    - tests/test_preview_channel.py
  modified:
    - src/segugio/opcomm/atomic.py
    - src/segugio/opcomm/records.py
    - src/segugio/opcomm/channel.py
    - src/segugio/config/models.py
    - tests/test_atomic_io.py

key-decisions:
  - "preview.json rides on atomic_write_json (always fsyncs) — never atomic_write_bytes; the fsync=False writer is ONLY for the disposable JPEGs (D-04)"
  - "PreviewDoc mirrors DirectorStatus byte-for-byte (frozen + normalizing __post_init__) so round-trip equality is order-independent and the record stays hashable"
  - "status.json / DirectorStatus left untouched (D-03 separation): the safety-critical reverse channel is byte-stable; the new why-payload lives in a separate sidecar"
  - "PreviewParams is additive (default_factory) so an existing extra=forbid YAML without a preview: block still validates; Phase 8 owns the HARD bandwidth cap"

patterns-established:
  - "Binary atomic write: atomic_write_bytes reuses _temp_path + _atomic_replace VERBATIM, gating only os.fsync behind a kwarg"
  - "Sidecar record: a second frozen dataclass + read_*/write_* pair on the same _read_json safe-default boundary, fully separate from the safety-critical status channel"

requirements-completed: [PRV-02, PRV-03]

# Metrics
duration: 9min
completed: 2026-06-13
---

# Phase 7 Plan 01: Preview Channel Opcomm Primitives Summary

**The off-tick preview channel's four leaf primitives — `atomic_write_bytes` (fsync-gated binary writer), the `PreviewDoc` frozen sidecar record, the `read_preview`/`write_preview` safe-default boundary, and the additive `PreviewParams` config — all stdlib/pydantic-only with the opcomm lazy-import leaf intact.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-13 (T1 RED began immediately after context read)
- **Completed:** 2026-06-13
- **Tasks:** 3 completed
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments
- `atomic_write_bytes(path, data, *, fsync=True)` — binary sibling of `atomic_write_text`, reusing the proven `_temp_path`+`_atomic_replace` Windows MoveFileEx-retry primitive VERBATIM, with the fsync drop for ephemeral JPEGs documented inline (D-04 / Pitfall 3).
- `PreviewDoc` — a frozen, normalizing, hashable dataclass carrying the FULL D-07 per-camera why-payload (`tick`/`gen`/`auto_candidate`/`cams`/`cuts`), mirroring `DirectorStatus` so round-trip equality is insertion-order independent.
- `read_preview`/`write_preview` — `write_preview` rides on `atomic_write_json` (always fsyncs → D-04 "keep fsync for preview.json" for free), `read_preview` reuses `_read_json` and safe-defaults to `PreviewDoc()` on any absent/torn/malformed/empty input (never raises — RBT-04).
- `PreviewParams` + `Config.preview` — additive bounded sub-model (ON by default, D-06); an existing `extra="forbid"` YAML without a `preview:` block still validates.
- The safety-critical `status.json`/`DirectorStatus` channel was left byte-stable (D-03) — confirmed green by `test_status_channel.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: atomic_write_bytes binary writer (TDD)** - `6b0e282` (feat) — test extension + impl committed together (extends existing `test_atomic_io.py`)
2. **Task 2: PreviewDoc record + read_preview/write_preview boundary (TDD)** - `6a35750` (feat) — new `test_preview_channel.py` + impl
3. **Task 3: PreviewParams additive config sub-model** - `5da34fe` (feat)

_TDD note: Tasks 1 and 2 followed RED→GREEN. RED was confirmed via ImportError on the missing symbol before each implementation; because the plan's `<action>` extends an existing test file (T1) / pairs a new test file with same-task impl (T2), each task is a single atomic feat commit rather than separate test/feat commits._

## Files Created/Modified
- `src/segugio/opcomm/atomic.py` - added `atomic_write_bytes` + `__all__` entry; fsync-drop rationale in the docstring.
- `src/segugio/opcomm/records.py` - added frozen `PreviewDoc` + `__all__` entry; normalizing `__post_init__` mirroring `DirectorStatus`.
- `src/segugio/opcomm/channel.py` - added `read_preview`/`write_preview` + `__all__` entries; imported `PreviewDoc`.
- `src/segugio/config/models.py` - added `PreviewParams` sub-model + `Config.preview` field.
- `tests/test_preview_channel.py` (NEW) - round-trip equality, insertion-order independence, absent/torn/empty safe-default, frozen/hashable assertions.
- `tests/test_atomic_io.py` - added bytes round-trip, fsync-param spy, MoveFileEx-retry, and `__all__` cases.

## Decisions Made
None beyond the plan — all four design points (D-03/04/05/06/07) were already resolved in RESEARCH and followed exactly.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Staging hit a `.gitignore` glob warning on `src/segugio/opcomm` (the directory matches an ignore pattern), but the individual files are already TRACKED (`git ls-files` lists them; `git check-ignore` on each specific file returns not-ignored). The modified files staged and committed normally — no `-f` needed. This is cosmetic git noise, not a functional block.
- Full-suite regression surfaced 4 PRE-EXISTING failures in `tests/test_fan_out_batched.py` (`ModuleNotFoundError: No module named 'ultralytics'`) — environmental, caused by running the CPU-only py3.14 `venv/` instead of the GPU `venv312/` (per MEMORY.md). These predate this plan (present at `0b88c07`) and are unrelated to the touched surfaces. Logged to `deferred-items.md`, not fixed (scope boundary).

## Verification Evidence

- `python -m pytest tests/test_atomic_io.py tests/test_preview_channel.py tests/test_status_channel.py` → 23 passed.
- `python -m pytest tests/ -k "config or import"` → all green (additive config validates; lazy-import boundary holds).
- `python -c "import segugio.opcomm"` → succeeds with the heavy stack absent (opcomm stays stdlib/pydantic-only leaf).
- `PreviewParams()` defaults + bounds + `extra="forbid"` verified directly; out-of-range fps/max_width/jpeg_quality and unknown keys rejected.

## Next Phase Readiness
- The four symbols (`atomic_write_bytes`, `PreviewDoc`, `read_preview`/`write_preview`, `PreviewParams`) form the concrete, unit-tested contract that plan 03's `PreviewPublisher` and plan 04's wiring consume — they can be built against a frozen interface, not a scavenger hunt.
- Deferred to later Phase-7 plans: `PreviewPublisher` daemon thread, `orchestrator/preview.py`, the `offer()` hot-path call + cuts-ring, the `build_orchestrator` wiring, and both HARD gates (RBT-05 p95-unchanged-with-preview-ON; console crash-isolation import test).

## Self-Check: PASSED

All 5 touched/created source+test files exist on disk; all 3 task commits (`6b0e282`, `6a35750`, `5da34fe`) are present in git history.

---
*Phase: 07-off-tick-frame-publishing-channel*
*Completed: 2026-06-13*
