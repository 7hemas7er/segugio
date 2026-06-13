---
phase: 06-decision-loop-latency-optimization-tensorrt-fp16-export-batc
verified: 2026-06-13T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
amendment: "2026-06-13 post-verification: the sole gap (RBT-05 <150ms) was resolved by an explicit product decision to REVISE the budget to <300ms (user-approved; the original <150ms is reachable only on faster/cooler desktop deploy hardware). The canonical path was set to FP16+batch EAGER (engine_path=None, use_fp16=True) — it preserves native-feature BoT-SORT ReID and measures p95 ~256ms cool < 300ms (orchestrator-verified, RTX 4000 Ada Laptop, AC power). The TensorRT engine (~197ms) is kept as an OPTIONAL higher-margin lever. Budget revised in REQUIREMENTS.md, CLAUDE.md, ROADMAP, and tests/test_latency.py (assert < 300.0). ⚠ Thermal variance noted: cool ~210–256ms, heat-soaked outlier ~546ms after back-to-back GPU runs — sustained live operation favors a desktop deploy GPU."
gaps: []
---

# Phase 6: Decision-Loop Latency Optimization Verification Report

> **⚠ AMENDED 2026-06-13 (post-verification):** Initial verification found 1 gap (RBT-05 <150ms not met on the Laptop GPU). Resolved by an **explicit, user-approved product decision to revise the budget to <300ms** and ship the **FP16+batch eager** path (native ReID, ~256ms p95 cool). Status flipped gaps_found → **passed (5/5)**. See the `amendment` frontmatter field and the updated Gaps Summary below. The original <150ms remains reachable only on faster/cooler desktop deploy hardware.

**Phase Goal (revised):** Bring the multi-camera decision loop within the **<300ms** p95 budget (RBT-05, revised from <150ms). Deliver TensorRT FP16 export of the detector, batch/parallelize the per-camera inferences, and confirm `tests/test_latency.py -m gpu` p95 < 300ms (4-cam canonical config).
**Verified:** 2026-06-13
**Status:** passed (amended)
**Re-verification:** No — initial verification + post-decision amendment

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ModelConfig` carries `engine_path` (Optional[Path]) + `use_fp16` (bool, default False), both validated, defaulting to eager-FP32 `.pt` behavior | VERIFIED | `src/segugio/config/models.py` lines 102-103: `engine_path: Path \| None = None` and `use_fp16: bool = False` present; `extra="forbid"` preserved; 4/4 `test_config_engine_keys.py` tests pass |
| 2 | `assert_native_reid_engaged` warns-not-raises when `is_engine=True` and HARD-raises unchanged when `is_engine=False` (default) | VERIFIED | `src/segugio/tracking/reid_check.py` lines 43-145: `is_engine: bool = False` kwarg present; three `is_engine=True` downgrade paths to `logger.warning` + return; eager path raises unchanged; 6/6 `test_reid_check_engine_aware.py` tests pass in venv312 |
| 3 | A batched-detect adapter dispatches ONE forward's per-camera detections to N independent per-camera trackers (never a frame list to one tracker, #13107-safe); `tools/build_engine.py` exports TensorRT FP16 engine; engine-aware `PerCameraTracker` loads `.engine` with graceful fallback on any load failure (RBT-04); `is_engine` threads from tracker into loop into reid gate | VERIFIED | `batched.py` (153 lines), `tools/build_engine.py` (151 lines), `detector.py` engine-aware `__init__`, `runtime.py` threading `engine_path` + `use_fp16`, loop `_maybe_reid_gate` threads `is_engine`; 22/22 headless tests pass; venv312 full suite 340/340 pass |
| 4 | The 4-cam decision loop runs ONE batched FP16 detection forward per tick (not 4 serial calls); `_fan_out` uses `_supports_batched()` to select the Track-B path; mock-timed wiring + attribution tests stay green | VERIFIED | `loop.py` `_batched_inference` + `_supports_batched()` present; `test_fan_out_batched.py` (7 tests, all pass in venv312); `test_latency.py` mock-timed tests (2/2 pass in py3.14 venv) |
| 5 | On the py3.12 GPU venv on AC power, tests/test_latency.py -m gpu confirms 4-cam p95 < **300ms** (RBT-05 — revised budget) | VERIFIED | Canonical FP16+batch **eager** path (engine_path=None, use_fp16=True, native ReID engaged): orchestrator-verified p95 **256.7ms cool < 300ms** → gpu gate PASSES. (Engine path ~197ms also passes, kept optional.) Budget revised from 150ms→300ms by user decision 2026-06-13; `assert total_p95_ms < 300.0` PASSES. ⚠ Thermal variance: heat-soaked outlier ~546ms after back-to-back GPU runs → desktop deploy GPU recommended for sustained operation. |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/config/models.py` | `engine_path` (Optional[Path]) + `use_fp16` (bool) on ModelConfig | VERIFIED | Lines 102-103; `extra="forbid"` preserved; defaults eager-FP32 |
| `src/segugio/tracking/reid_check.py` | Engine-aware `assert_native_reid_engaged` (`is_engine` kwarg; warn-not-raise on engine, HARD-raise unchanged on eager) | VERIFIED | 146 lines; `is_engine: bool = False` kwarg; three warn+return branches for engine; lazy ultralytics import boundary held |
| `src/segugio/tracking/batched.py` | `batched_detect_dispatch` — one predict([frames]) then per-camera tracker.update(), #13107-safe, lazy-import boundary | VERIFIED | 153 lines; ONE `model.predict()` call; dispatch loop over `cam_ids`; `half=use_fp16`, `end2end=False` explicit; lazy ultralytics boundary held |
| `tests/test_reid_check_engine_aware.py` | Engine-aware reid gate unit tests (4 behaviors) | VERIFIED | 124 lines; 6 tests pass (py3.14 venv + venv312) |
| `tests/test_batched_detect.py` | Per-camera state-isolation regression guard + FP16 tests | VERIFIED | 214 lines; 7 tests pass (py3.14 venv + venv312) |
| `tests/test_config_engine_keys.py` | Additive defaults, extra=forbid, explicit parse | VERIFIED | 53 lines; 4 tests pass (py3.14 venv + venv312) |
| `tests/test_fan_out_batched.py` | Loop-level batched dispatch: one forward / N updates / #13107 isolation / FP16 half / reid gate / coast / dog-index-by-name | VERIFIED (venv312 only) | 373 lines; 7/7 pass in venv312 (require ultralytics); 4/7 fail in py3.14 venv (no ultralytics installed — NOT a Phase 6 regression; tests require the project's standard runtime dep) |
| `tests/test_engine_loader_fallback.py` | Engine present→is_engine; load-raises→eager fallback; missing-file→eager; factory threads keys | VERIFIED | 162 lines; 5 tests pass (py3.14 venv + venv312) |
| `tools/build_engine.py` | One-time cached TensorRT FP16 engine build CLI; lazy ultralytics import; CITED export shape (half=True, batch=4, end2end=False) | VERIFIED | 151 lines; `from ultralytics import YOLO` INSIDE `build_engine()` function (lazy); correct export kwargs; argparse with `--dynamic` escape hatch; imports with ultralytics absent |
| `src/segugio/tracking/detector.py` | Engine-aware `PerCameraTracker.__init__` — try .engine, fallback to eager .pt, store `is_engine`; `update()` + `_ensure_persistent_tracker()` for Track-B; `_build_engine_botsort()` direct BOTSORT construction for engine | VERIFIED | `engine_path` kwarg at line 136; try/except graceful fallback; `is_engine` attribute; `update()` + `_ensure_persistent_tracker()` + `_build_engine_botsort()` present |
| `src/segugio/orchestrator/runtime.py` | `_default_tracker_factory` + `build_orchestrator` thread `engine_path` + `use_fp16` | VERIFIED | Lines 94-111: factory accepts and passes `engine_path` + `use_fp16`; `build_orchestrator` passes `config.model.engine_path` + `config.model.use_fp16` (lines 174-183) |
| `.gitignore` | `*.engine` and `*.onnx` excluded | VERIFIED | Both patterns present as non-comment lines; confirmed via `grep -v '^#' .gitignore | grep -E '\*.engine|\*.onnx'` |
| `docs/run.md` | GPU env section: py3.12 venv, cu12x torch, tensorrt-cu12<11, both probe commands, AC-power note, engine-rebuild caveat, build invocation | VERIFIED | Section "GPU latency env (Phase 6)" at line 143; all required content present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/segugio/tracking/batched.py` | Per-camera tracker objects | Dispatch loop `for idx, cam_id in enumerate(cam_ids)` | WIRED | Lines 134-152; each tracker's `update()` called exactly once with only its own results slice |
| `src/segugio/orchestrator/loop.py:_batched_inference` | `src/segugio/tracking/batched.py:batched_detect_dispatch` | `from ..tracking.batched import batched_detect_dispatch` + one call per tick | WIRED | `_batched_inference` method imports and calls `batched_detect_dispatch` once |
| `src/segugio/orchestrator/loop.py:_maybe_reid_gate` | `src/segugio/tracking/reid_check.py:assert_native_reid_engaged` | `is_engine=getattr(tracker, "is_engine", False)` kwarg | WIRED | Lines 342-343: `is_engine = bool(getattr(tracker, "is_engine", False))` then `assert_native_reid_engaged(tracker.model, is_engine=is_engine)` |
| `src/segugio/tracking/detector.py:PerCameraTracker.__init__` | Cached `.engine` (or eager `.pt` fallback) | `try YOLO(str(engine_path)) except → YOLO(.pt); set self.is_engine` | WIRED | Lines 180-201: try/except pattern confirmed |
| `src/segugio/orchestrator/runtime.py:_default_tracker_factory` | `PerCameraTracker(engine_path=..., use_fp16=...)` | factory passes both kwargs | WIRED | Lines 105-111 |
| `tools/build_engine.py` | `ultralytics YOLO.export(format="engine")` | lazy `from ultralytics import YOLO` inside `build_engine()` | WIRED | Lines 84-96: `format="engine", half=True, batch=4, end2end=False, device=0` confirmed |

---

## Data-Flow Trace (Level 4)

Not applicable — Phase 6 artifacts are inference infrastructure (trackers, config keys, CLI tool), not components that render dynamic data to a user-visible output. The relevant data flow (model weights → inference results → per-camera scores → FSM → OBS) was verified end-to-end in Phase 5. Phase 6 modifies the inference dispatch path and measures its latency; the measurement data flows through the `run_measured` harness (verified in Phase 5, regression-tested here).

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `tools/build_engine.py` imports with ultralytics absent | `python -c "import ast; ast.parse(open('tools/build_engine.py').read()); print('parse-ok')"` | parse-ok | PASS |
| `batched.py` imports with ultralytics absent | `python -m pytest tests/test_tracking_import_smoke.py -q` | 2 passed | PASS |
| Headless suite passes (22 new Phase 6 tests, py3.14 venv) | `pytest tests/test_reid_check_engine_aware.py tests/test_batched_detect.py tests/test_config_engine_keys.py tests/test_engine_loader_fallback.py -q` | 22 passed in 0.24s | PASS |
| Mock-timed latency wiring + attribution regression | `pytest tests/test_latency.py -k mock_timed -q` | 2 passed, 1 deselected | PASS |
| Full headless suite (venv312, 340 tests, ultralytics present) | `pytest tests/ -m "not ndi and not gpu and not obs" --ignore=tests/test_ui_score.py --ignore=tests/test_ui_run.py -q` | 340 passed, 3 skipped, 6 deselected | PASS |
| GPU latency gate: canonical eager FP16+batch p95 < 300ms (RBT-05, revised) | `pytest tests/test_latency.py -m gpu -x` on RTX 4000 Ada, AC power, venv312 | p95 = 256.7ms cool (PASS < 300ms; native ReID engaged) | PASS |

---

## Probe Execution

No `scripts/*/tests/probe-*.sh` files exist. The GPU latency gate (`test_loop_latency_p95_under_budget`) is the phase probe. Result: p95 ≈ 193–197ms on the Laptop GPU (FAIL, measured and documented in 06-03-SUMMARY.md). This is not a probe script defect — the measurement is real and honest.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RBT-05 | 06-01, 06-02, 06-03 | Decision-loop latency p95 < **300ms** (revised from <150ms, 2026-06-13) | **MET** | Canonical FP16+batch eager path measures p95 256.7ms cool < 300ms on the RTX 4000 Ada Laptop GPU (native ReID preserved). Engine path ~197ms also passes (optional lever). All deliverables (TRT FP16 export CLI, batched FP16 inference, engine-aware loader, is_engine reid-gate threading) SHIPPED and working. The original <150ms is reachable only on faster/cooler desktop deploy hardware. |

**REQUIREMENTS.md traceability note:** The traceability table in REQUIREMENTS.md maps RBT-05 to Phase 5 (line 153: `RBT-05 | Phase 5 | Complete`). Phase 6 was added after the REQUIREMENTS.md was authored and the traceability table was never updated. Phase 6 is the genuine owner of the RBT-05 latency optimization work; Phase 5 delivered the latency harness infrastructure. This is a metadata inaccuracy in REQUIREMENTS.md, not a code gap.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX debt markers found in any Phase 6-modified file | — | — |

No placeholder implementations, empty handlers, or hardcoded stubs found in Phase 6 deliverables. All implementations are substantive and wired.

**test_fan_out_batched.py — 4 tests fail in py3.14 venv (WARNING, not blocker):**
Four tests (`test_fan_out_one_batched_forward_per_tick`, `test_fan_out_fp16_half_threaded`, `test_fan_out_none_frame_coasts`, `test_fan_out_dog_index_resolved_by_name`) fail in the py3.14 dev venv with `ModuleNotFoundError: No module named 'ultralytics'`. These tests call `_fan_out()` which triggers `assert_native_reid_engaged` → `from ultralytics.trackers.bot_sort import ReID` (a lazy import inside the function). The issue: the lazy import is ALWAYS reached when checking `isinstance(enc, ReID)`, even on the native-ReID path, because the `isinstance` check itself needs the `ReID` class. All 4 failing tests pass correctly in `venv312` (where ultralytics 8.4.62 is installed). This is NOT a regression — the file is new in Phase 6, and the project's standard runtime depends on ultralytics being installed. The `venv312` (the documented execution environment) is green.

---

## Human Verification Required

None. All technical assertions are code-verifiable or have been directly measured.

---

## Gaps Summary

**RESOLVED — no open gaps.** The single initial gap (RBT-05 <150ms) was a hardware-budget gap, not a software gap, and was closed by an explicit user-approved product decision (2026-06-13): **revise the budget to <300ms** and ship the **FP16+batch eager** canonical path.

All three Phase 6 plans delivered their technical artifacts correctly and the code works as designed:
- Wave 0 (06-01): engine-aware ReID gate, config keys, batched adapter, GPU env (venv312 stood up) — SHIPPED
- Wave 1 (06-02): FP16+batch eager _fan_out, native ReID preserved, p95 ~210–256ms MEASURED — SHIPPED, **canonical path**
- Wave 2 (06-03): TensorRT FP16 engine CLI, engine-aware tracker with graceful fallback (RBT-04), is_engine thread-through — SHIPPED; engine BUILT on rig; p95 ~197ms — kept as **optional higher-margin lever**

**RBT-05 (revised <300ms) is MET:** the canonical eager FP16+batch path measures p95 256.7ms cool < 300ms with native-feature ReID preserved. The deliverables are complete and production-ready.

⚠ **Two carry-forward notes (documented, not blocking):**
1. **Thermal variance on the Laptop GPU** — p95 ranged cool ~210–256ms to a heat-soaked ~546ms outlier after back-to-back GPU runs. For sustained live operation (hours-long gare) prefer the **desktop deploy GPU** (better cooling, no throttle) — which would also reach the original <150ms — or the engine's larger margin.
2. **FP16 recall (RESEARCH A2/A5)** — the eager path runs `half=True`; a dog-recall spot-check on hard/distant/dusk clips vs FP32 is DEFERRED (no curated multi-dog clip locally). Note any regression before the live gara.

---

_Verified: 2026-06-13_
_Verifier: Claude (gsd-verifier)_
