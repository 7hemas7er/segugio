---
phase: 07-off-tick-frame-publishing-channel
plan: 04
subsystem: orchestrator
tags: [orchestrator, wiring, hot-path, latency-gate, fault-isolation, preview]

# Dependency graph
requires:
  - phase: 07-off-tick-frame-publishing-channel
    plan: 01
    provides: "atomic_write_bytes, PreviewDoc, read_preview/write_preview, PreviewParams + Config.preview"
  - phase: 07-off-tick-frame-publishing-channel
    plan: 03
    provides: "PreviewPublisher daemon: offer(frames,scores,dets,decision,cuts) mailbox + start/stop + encode_fn seam + _build_doc"
  - phase: 05-wiring-integration
    provides: "Orchestrator loop.py RBT-04 coast-don't-crash tick + _safe_startup lifecycle; build_orchestrator runtime factory + *_factory DI seams"
provides:
  - "self._preview collaborator + the guarded offer() hot-path call (after _apply, INSIDE the RBT-04 try) in loop.py"
  - "_cuts_ring (deque maxlen=16) fed from the _apply target-change edge — orchestrator-owned cut history (Pitfall 5)"
  - "_fan_out returns frames_by_cam surfaced from whichever inference path ran (no second source.latest())"
  - "preview_factory seam + guarded publisher construction (config.preview.enabled) in runtime.py; opcomm/preview/ media dir"
  - "HARD GATE 1: gpu test_loop_latency_p95_preview_on_no_regression (preview ON vs OFF p95, on-rig noise band)"
  - "Orchestrator-level proofs: preview-files-written disk smoke + publisher-fault-coast (SC3/SC5)"
affects: [phase-08-console-multiview, phase-09-explainability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The ONLY hot-path preview touch is a single guarded offer() inside the existing RBT-04 tick try — a publisher fault coasts via the same catch, never crashes the director (D-02/T-07-04-01)"
    - "frames surfaced from the fan-out (no second source.latest()): the inference path returns frames_by_cam, reused by offer() — one source pull per tick (RESEARCH L376-380)"
    - "Orchestrator-owned cuts ring: the cut history lives on the loop (deque maxlen=16, fed at the _apply change edge) not the publisher, so a dropped preview frame never loses a cut (Pitfall 5)"
    - "Guarded-by-config-flag wiring: every new tick-path call is `if self._preview is not None`; config.preview.enabled=False => _preview None => byte-identical-to-v1.0 (D-06)"
    - "HARD GATE 1 derives its tolerance on-rig: two back-to-back preview-OFF runs give the run-to-run noise band, then assert p95_on <= p95_off + band (no magic number)"

key-files:
  created: []
  modified:
    - src/segugio/orchestrator/loop.py
    - src/segugio/orchestrator/runtime.py
    - tests/test_orchestrator_runtime.py
    - tests/test_fault_isolation.py
    - tests/test_latency.py

key-decisions:
  - "_apply gained a `tick: int = 0` param (default-valued so existing callers/tests are unaffected) so the cuts-ring entry can record the tick at the change edge"
  - "The cuts ring appends ONLY when the live target actually changed (status.live_cam != prev live_cam), reading the previous live cam from self._last_status BEFORE reassigning it"
  - "HARD GATE 1 builds the publisher via build_orchestrator's DEFAULT factory (the prod wiring), not a stub — the gate measures the real live path the operator runs"
  - "The opcomm/preview/ dir is created unconditionally (cheap) even when preview is disabled — mirrors the channel_dir os.makedirs defensiveness; the publisher's atomic temp-write needs the dir to exist"
  - "The publisher-fault test makes offer() RAISE (not the encoder) so it proves the HOT-PATH catch specifically — the offer is the only new tick-path call"

patterns-established:
  - "Surface-don't-re-pull: when a downstream off-tick consumer needs the per-tick frames, return them up from the inference path rather than calling source.latest() again (avoids a different frame + an extra lock)"
  - "Guarded-collaborator wiring: a new optional collaborator threaded through __init__/from_config/build_orchestrator with every call site guarded by `is not None`, so disabled = byte-identical-to-baseline and provable by a single None-construction test"

requirements-completed: [PRV-01, PRV-02, PRV-03]

# Metrics
duration: 12min
completed: 2026-06-13
---

# Phase 7 Plan 04: Hot-Path Preview Wiring + Both HARD-Gate Proofs Summary

**The single hot-path touch of Phase 7 — `self._preview` on the `Orchestrator`, a guarded `offer()` immediately after `_apply` INSIDE the existing RBT-04 tick try, the `_cuts_ring` fed from the `_apply` target-change edge, and `_fan_out` surfacing `frames_by_cam` with no second `source.latest()` — wired in `runtime.py` via a `preview_factory` seam + `config.preview.enabled`-guarded construction + the `opcomm/preview/` dir, then proven by a headless disk-smoke (real `cam_<id>.jpg` + `preview.json`), a publisher-fault-coast (a raising `offer()` rides the RBT-04 catch and `status.json` is still written), and HARD GATE 1 (the gpu preview-ON-vs-OFF p95 no-regression deriving its noise band on-rig).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-13T11:40:00Z
- **Completed:** 2026-06-13T11:52:00Z
- **Tasks:** 3 completed
- **Files modified:** 5 (2 source, 3 tests)

## Accomplishments

- **Task 1 — `loop.py` hot-path wiring:** `preview=None` threaded through `__init__`/`from_config` (`self._preview`); `self._cuts_ring = deque(maxlen=16)`; `_fan_out` now returns `(dets_by_cam, locked_energy, frames_by_cam)` with both the batched and serial inference paths surfacing the single-pull `frames_by_cam` (NO second `source.latest()`); the guarded `offer(frames_by_cam, scores, dets_by_cam, decision, list(self._cuts_ring))` after `_apply` INSIDE the RBT-04 try; the cuts ring appended at the `_apply` target-change edge (`{tick, from, to, reason}`, threading `tick` into `_apply`); `run`/`run_measured` `_safe_startup` the daemon, `shutdown` coast-stops it — all guarded by `is not None`.
- **Task 2 — `runtime.py` construction + disk smoke:** lazy `_default_preview_factory`, `_channel_paths` extended with `preview_dir`/`preview` keys, `preview_factory` param, `os.makedirs(preview_dir, exist_ok=True)`, publisher construction GUARDED by `config.preview.enabled` and injected via `preview=`. The disk-smoke test drives a real run with an injected fake encoder and asserts real `cam_<id>.jpg` bytes + a readable `preview.json` land on disk; the disabled test proves `_preview is None` and the factory is never called.
- **Task 3 — both HARD-gate proofs:** the gpu `test_loop_latency_p95_preview_on_no_regression` derives the run-to-run noise band from two preview-OFF runs then asserts `p95_on <= p95_off + band` with the REAL publisher via `build_orchestrator`'s default factory (auto-skips off-rig); the headless `test_preview_offer_fault_coasts` proves a raising `offer()` does not crash the tick and `status.json` is still written (SC5).

## Task Commits

Each task was committed atomically:

1. **Task 1: wire preview into loop.py — collaborator, guarded offer(), cuts ring, frames_by_cam** - `c637245` (feat)
2. **Task 2: runtime preview_factory seam + guarded construction + preview/ dir + disk-smoke proof** - `4f4c593` (feat)
3. **Task 3: HARD GATE 1 gpu latency no-regression + publisher-fault-coast** - `e405c8b` (test)

## Files Created/Modified

- `src/segugio/orchestrator/loop.py` — `self._preview` + `self._cuts_ring`; `preview=` on `__init__`/`from_config`; `_fan_out`/`_serial_inference`/`_batched_inference` return `frames_by_cam`; guarded `offer()` after `_apply` in the RBT-04 try; cuts-ring feed at the `_apply` change edge (`tick` threaded in); `run`/`run_measured` start + `shutdown` stop the daemon (all `is not None`-guarded).
- `src/segugio/orchestrator/runtime.py` — lazy `_default_preview_factory`; `_channel_paths` + `preview_dir`/`preview`; `preview_factory` param; `os.makedirs(preview_dir)`; guarded construction by `config.preview.enabled`; `preview=` injection.
- `tests/test_orchestrator_runtime.py` — `test_preview_files_written_on_real_run` (SC3/D-09 disk smoke) + `test_preview_disabled_constructs_no_publisher` (D-06).
- `tests/test_fault_isolation.py` — `_RaisingPreview` + `test_preview_offer_fault_coasts` (PRV-01 criterion 5 / SC5); `preview=` threaded through the `_build` helper.
- `tests/test_latency.py` — `_gpu_latency_orch` helper + `test_loop_latency_p95_preview_on_no_regression` (HARD GATE 1, gpu).

## Decisions Made

- `_apply(self, decision, alive, tick: int = 0)` — the `tick` param is default-valued so no existing caller/test breaks; only `_tick_once` passes the live `tick` for the cuts-ring entry.
- The cuts ring appends only on a genuine live-target change (reads `self._last_status.live_cam` before reassigning), so steady-state ticks add no entries.
- HARD GATE 1 builds via `build_orchestrator`'s default factory (the prod path) rather than a stub publisher — the gate measures what the operator actually runs.
- `opcomm/preview/` is created unconditionally (even when disabled) — the same defensiveness as `channel_dir`; harmless when no publisher writes into it.

## Deviations from Plan

None - plan executed exactly as written. Every change followed the plan's `<action>` and the RESEARCH/PATTERNS insertion sites; no Rule 1-4 deviations were needed.

## Issues Encountered

- **Pre-existing `ultralytics`-absent failures (out of scope):** `tests/test_fan_out_batched.py` (4 tests) fails with `ModuleNotFoundError: No module named 'ultralytics'` on the CPU-only py3.14 `venv/` (per MEMORY.md the heavy stack lives in `venv312/`). These predate this plan (documented in 07-01's SUMMARY + `deferred-items.md`), are unrelated to the touched surfaces, and were NOT fixed (scope boundary). Confirmed they fail identically on the prior commit.
- LF→CRLF git line-ending normalization warnings on the touched files (cosmetic Windows noise; files staged/committed normally).

## HARD Gate Status

- **HARD GATE 1 (RBT-05 preview-ON p95 no-regression):** LANDED as the gpu-marked `test_loop_latency_p95_preview_on_no_regression`; it collects cleanly and auto-skips off-rig (this CPU-only `venv/` cannot run gpu tests — the GPU stack is `venv312/`). It is a **rig-deferred human-verification gate**: run on the deploy GPU via `python -m pytest -m gpu tests/test_latency.py`. The gate was deliberately left correctly GATED behind the gpu marker — NOT weakened to force a pass here.
- **HARD GATE 2 (console crash-isolation import):** landed in plan 07-02 (not this plan).

## Verification Evidence

- Task 1: `python -m pytest tests/test_fault_isolation.py tests/test_orchestrator_runtime.py tests/test_latency.py -k "not gpu" -x` → 20 passed (byte-identical with `preview=None`).
- Task 2: `python -m pytest tests/test_orchestrator_runtime.py -k "preview" -x` → 2 passed; full file → 15 passed.
- Task 3: `python -m pytest tests/test_fault_isolation.py -k "preview or coast" -x` → 2 passed; `tests/test_latency.py` → 2 passed, 2 gpu-skipped.
- Full plan verification: `python -m pytest tests/test_orchestrator_runtime.py tests/test_orchestrator_startup.py tests/test_fault_isolation.py tests/test_latency.py -k "not gpu"` → 28 passed.
- Full headless repo suite (minus the pre-existing `ultralytics`-absent `test_fan_out_batched.py`): all green.
- Lazy-import boundary held: `import segugio.orchestrator.runtime` succeeds with `torch/ultralytics/cyndilib/obsws_python/cv2` forced absent (the `_default_preview_factory` import stays lazy).

## Threat Model Coverage

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-07-04-01 (DoS / never-crash, RBT-04) | mitigated | `offer()` sits inside the `_tick_once` RBT-04 try; `test_preview_offer_fault_coasts` proves a raising `offer()` coasts and `status.json` is still written. |
| T-07-04-02 (DoS / latency, RBT-05) | mitigated (rig-deferred) | HARD GATE 1 `test_loop_latency_p95_preview_on_no_regression` runs the real publisher under `run_measured`, derives the on-rig noise band, asserts `p95_on <= p95_off + band`. Auto-skips off-rig — run on the deploy GPU. |
| T-07-04-03 (Tampering / disk exhaustion) | mitigated | per-camera JPEGs are fixed-filename atomic overwrites (`cam_<id>.jpg`); the camera set comes from validated `Config.cameras` — bounded (N files + 1 sidecar). Phase 8 owns the HARD bandwidth cap + stale-file cleanup. |
| T-07-04-04 (Tampering / path traversal) | accept | `cam_<id>.jpg` filenames are built from pydantic-validated `Config.cameras[].id`, never operator input. |
| T-07-04-05 (Tampering / safety regression when disabled) | mitigated | every change is `is not None`-guarded; `test_preview_disabled_constructs_no_publisher` proves `_preview is None` when `config.preview.enabled=False`; the full headless suite is the regression guard. |

No new threat surface introduced beyond the plan's `<threat_model>` (no new endpoints, no untrusted input parsed; the read/serve route is Phase 8).

## Next Phase Readiness

- D-09's "done" line is reached: `python -m segugio <config>` now constructs/starts/stops the `PreviewPublisher` and writes `opcomm/preview/cam_<id>.jpg` + `preview.json` (PRV-01/PRV-02/PRV-03). Phase 8 can build the console serving route (`GET /preview`, multiview grid) against a live, populated `opcomm/preview/` dir.
- Rig-deferred: run HARD GATE 1 on the deploy GPU (`python -m pytest -m gpu tests/test_latency.py`) to confirm the preview-ON p95 stays within the on-rig noise band of OFF before Phase 8 acceptance. Phase 8 also owns the preview-bandwidth cap (preview must degrade before the NDI feeds) and the `threaded=True`/Waitress server fix (override POST must never be blocked by a preview stream).

## Self-Check: PASSED

All 5 modified files exist on disk; all 3 task commits (`c637245`, `4f4c593`, `e405c8b`) are present in git history.

---
*Phase: 07-off-tick-frame-publishing-channel*
*Completed: 2026-06-13*
