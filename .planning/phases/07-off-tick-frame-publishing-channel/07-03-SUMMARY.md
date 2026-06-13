---
phase: 07-off-tick-frame-publishing-channel
plan: 03
subsystem: orchestrator
tags: [orchestrator, preview-publisher, daemon-thread, mailbox, off-tick, rbt-04]

# Dependency graph
requires:
  - phase: 07-off-tick-frame-publishing-channel
    plan: 01
    provides: "atomic_write_bytes(path, data, *, fsync=False), PreviewDoc frozen record, write_preview(path, doc), PreviewParams config sub-model"
  - phase: 05-wiring-integration
    provides: "loop.py RBT-04 coast-don't-crash + _safe_startup lifecycle shapes mirrored by the publisher daemon"
  - phase: 02-framing-scorer
    provides: "CameraScore (score/status), DetectionSignal (cx/cy/w/h/track_id), ScorerStatus enum — the _build_doc payload sources"
provides:
  - "PreviewPublisher daemon: offer/start/stop + _drain/_run/_publish + _build_doc/_cv2_encode + in-sidecar gen cache-bust"
  - "offer() — the single locked 1-slot mailbox assignment the tick calls (never blocks, last-writer-wins, D-02/PRV-01)"
  - "_build_doc — the PURE D-07 why-payload builder (unit-testable headless, no cv2)"
  - "encode_fn injectable seam — headless unit tests with no real cv2/GPU"
affects: [phase-07-plan-04-wiring, phase-08-console-multiview, phase-09-explainability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Latest-only 1-slot Lock mailbox (NOT queue.Queue): offer/_drain read-and-clear so the tick never waits on the publisher (D-02)"
    - "Off-tick daemon coast: _run wraps _publish in except Exception -> logger.warning (RBT-04 extended), isolated from the director thread"
    - "Lazy heavy-import boundary: cv2/numpy import INSIDE _publish/_cv2_encode only; PreviewPublisher imports with the heavy stack absent (gate 2)"
    - "fsync=False for ephemeral per-cam JPEGs (D-04); preview.json keeps fsync via write_preview/atomic_write_json"

key-files:
  created:
    - src/segugio/orchestrator/preview.py
    - tests/test_preview_publisher.py
  modified: []

key-decisions:
  - "ema == score: the raw EMA is not exposed by CameraScore (RESEARCH L242), so _build_doc sets ema = score with NO scorer change"
  - "in_zone == (det is not None): the A1 Phase-7 approximation — a present locked detection IS the in-zone signal; the field exists for the D-07 contract"
  - "energy defaults to 0.0: the per-camera locked-motion energy field MUST exist for the D-07 contract; plan 04 wires the real value if surfaced"
  - "encode routed through an injectable encode_fn seam (default None -> lazy _cv2_encode) so the whole publisher is unit-tested headless with no real cv2/GPU"
  - "frames stored by reference in offer() (no .copy()) — both current FrameSources allocate a fresh array per frame (RESEARCH L369-374); forward-assumption documented in the module docstring"

requirements-completed: [PRV-01, PRV-02]

# Metrics
duration: 4min
completed: 2026-06-13
---

# Phase 7 Plan 03: PreviewPublisher Off-tick Daemon Summary

**The off-tick engine — a `PreviewPublisher` whose `offer()` is a single locked 1-slot mailbox assignment (never blocks, last-writer-wins, D-02) and whose own daemon thread does ALL resize/encode/IO (`_publish`) at ~`1/fps`, building the full D-07 'why' `PreviewDoc` and writing per-camera JPEGs via `atomic_write_bytes(..., fsync=False)` — every publish coasting on fault (RBT-04 extended), with cv2/numpy imported lazily inside `_publish` so the module imports with the heavy stack absent.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-13T11:30:48Z
- **Completed:** 2026-06-13T11:34:48Z
- **Tasks:** 2 completed (both TDD: RED → GREEN)
- **Files modified:** 2 (both created)

## Accomplishments

- **`PreviewPublisher` mailbox + daemon + lifecycle (Task 1):** the 1-slot `Lock`-guarded mailbox (`offer`/`_drain`, last-writer-wins, never blocks — D-02/PRV-01), the own daemon `_run` loop at ~`1/fps` (sleeps the period when empty, no busy-spin), and `start`/`stop` (daemon thread, bounded join, never raises). The in-sidecar monotonic `gen` cache-bust token (no `gen.txt`). The frame-snapshot forward-assumption (no `.copy()` needed today) documented in the module docstring.
- **`_publish` + `_build_doc` + `_cv2_encode` (Task 2):** `_build_doc` is PURE (no cv2) — it maps every D-07 field from injected `scores`/`dets`/`decision`/`cuts` (per-cam `score`/`ema`/`state`/`locked`/`track_id`/`energy`/`in_zone`/`box` + top-level `auto_candidate`/`cuts` + monotonic `gen`). `_publish` does the per-camera `cv2.resize` → `imencode(".jpg")` → `atomic_write_bytes(cam_<id>.jpg, fsync=False)` (D-04) then `write_preview(preview.json, doc)`. `cv2`/`numpy` import LAZILY inside `_cv2_encode` (gate-2 boundary); an injectable `encode_fn` seam keeps the whole class unit-tested headless with no real cv2/GPU.
- **Coast invariant proven:** an injected encoder that raises makes `_run` log + continue (never raise — RBT-04 extended, PRV-01 criterion 5); a bounded `_run` test confirms it returns cleanly past the fault.

## Task Commits

Each task was committed atomically (both TDD RED→GREEN; new file paired with same-task impl, so each task is a single `feat` commit):

1. **Task 1: PreviewPublisher mailbox + daemon + lifecycle** - `5ea5514` (feat) — new `preview.py` (mailbox/daemon/lifecycle) + `test_preview_publisher.py -k mailbox` (6 tests)
2. **Task 2: _publish resize/encode/atomic-write + D-07 why-payload + coast** - `1cb5e56` (feat) — `_publish`/`_build_doc`/`_cv2_encode` + `-k "payload or coast"` (6 tests)

_TDD note: each task's RED was confirmed (ModuleNotFoundError on the missing module for T1; AttributeError on the missing `_build_doc` for T2) before the GREEN implementation. Because the plan pairs a new test file with same-task impl, each task is a single atomic `feat` commit rather than separate `test`/`feat` commits — matching the plan-01 precedent._

## Files Created/Modified

- `src/segugio/orchestrator/preview.py` (NEW) — `PreviewPublisher` daemon: `offer`/`_drain`/`_run`/`start`/`stop` (Task 1) + `_publish`/`_build_doc`/`_cv2_encode` (Task 2); stdlib + opcomm-contract module-level imports only, cv2/numpy lazy inside `_cv2_encode`.
- `tests/test_preview_publisher.py` (NEW) — `-k mailbox` (offer-never-blocks, last-writer-wins, drain-then-None, bounded `_run` coast, start/stop no-hang, import-without-heavy-stack), `-k payload` (full D-07 field mapping, gen increments, SAFE default), `-k coast` (fsync=False JPEG spy, encode-fault coast).

## Decisions Made

All within the plan's `<action>` — no decisions beyond what RESEARCH/the plan already resolved:
- `ema == score` (raw EMA not exposed by `CameraScore`, RESEARCH L242) — no scorer change.
- `in_zone == (det is not None)` — the A1 Phase-7 approximation; the field exists for the D-07 contract.
- `energy` defaults to `0.0` — the field MUST exist for the D-07 contract; plan 04 wires the real per-cam locked-energy if surfaced.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Package `__init__` numpy requirement (NOT a boundary regression):** `import segugio.orchestrator` (the package `__init__`) pulls in `framing.scorer`, which legitimately imports numpy at module level — so forcing `numpy` absent breaks the *package* import. This is pre-existing and unrelated to this plan's boundary: the gate-2 contract is that the **`preview` submodule** imports with **cv2** absent (cv2/numpy are lazy inside `_publish`/`_cv2_encode`), which is verified directly (`import sys; sys.modules['cv2']=None; from segugio.orchestrator.preview import PreviewPublisher` → OK). The console-path gate-2 test (plan 07-02) already locks the clean Flask + opcomm surface; `orchestrator.preview` is never imported by the console.
- Tests run on the CPU-only py3.14 `venv/` (no cv2/GPU needed — the whole plan is headless with an injected fake encoder, per MEMORY.md the GPU `venv312/` is only for `-m gpu`).
- LF→CRLF git warnings on the two new files (cosmetic Windows line-ending normalization; files staged/committed normally).

## Verification Evidence

- `python -m pytest tests/test_preview_publisher.py -k mailbox -x` → 6 passed (Task 1 verify).
- `python -m pytest tests/test_preview_publisher.py -k "payload or coast" -x` → 6 passed (Task 2 verify).
- `python -m pytest tests/test_preview_publisher.py tests/test_preview_channel.py tests/test_atomic_io.py` → 31 passed (plan + plan-01 contract green).
- `python -m pytest tests/test_preview_publisher.py tests/test_preview_channel.py tests/test_atomic_io.py tests/test_status_channel.py` → 34 passed (status channel byte-stable, no regression).
- `python -c "import sys; sys.modules['cv2']=None; from segugio.orchestrator.preview import PreviewPublisher"` → OK (lazy-import boundary holds, gate 2).

## Threat Model Coverage

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-07-03-01 (DoS / never-crash) | mitigated | `_run` wraps `_publish` in `except Exception: logger.warning`; coast test injects a raising encoder, `_run` returns cleanly. |
| T-07-03-02 (DoS / latency) | mitigated (here) | ALL encode/IO is in `_publish` on the daemon; `offer()` is a single locked assignment (mailbox tests). End-to-end RBT-05 proof is gate 1 (plan 04). |
| T-07-03-03 (Tampering / disk thrash) | mitigated | `_publish` calls `atomic_write_bytes(..., fsync=False)` for the JPEGs; the spy test confirms `fsync=False`. |
| T-07-03-04 (info disclosure / isolation) | mitigated | cv2/numpy import lazily inside `_cv2_encode`; module imports with cv2 absent (verified). |

No new threat surface introduced beyond the plan's `<threat_model>` (no new endpoints, no untrusted input parsed on the write side).

## Next Phase Readiness

- The `PreviewPublisher` is built and headless-unit-tested against the plan-01 frozen contract (`atomic_write_bytes`/`PreviewDoc`/`write_preview`/`PreviewParams`). Plan 04 only has to WIRE it: surface `frames_by_cam` from `_fan_out`, maintain the `_cuts_ring` on the orchestrator, call `offer(...)` inside the existing RBT-04 tick try, `_safe_startup`/`stop` the publisher in the lifecycle, and create the `opcomm/preview/` dir + `preview_factory` in `build_orchestrator`.
- Deferred to plan 04: the `loop.py`/`runtime.py` wiring, the `opcomm/preview/` dir creation, and BOTH HARD gates (RBT-05 p95-unchanged-with-preview-ON; the console crash-isolation import test extension).

## Self-Check: PASSED

Both created files exist on disk; both task commits (`5ea5514`, `1cb5e56`) are present in git history.

---
*Phase: 07-off-tick-frame-publishing-channel*
*Completed: 2026-06-13*
