---
phase: 06
slug: decision-loop-latency-optimization-tensorrt-fp16-export-batc
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-13
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (requirements.txt) |
| **Config file** | pyproject.toml (markers `gpu`/`ndi`/`obs` registered; skip hook in `tests/conftest.py` via `conftest_tracking.gpu_available`) |
| **Quick run command** | `pytest -q` (headless — no GPU needed for the 314+ logic tests) |
| **Full suite command** | `pytest -q` |
| **GPU gate command** | `pytest tests/test_latency.py -m gpu -x` (py3.12 cu12x venv, RTX 4000 Ada, on AC power) |
| **Estimated runtime** | headless suite seconds; gpu gate ~20+100 ticks × 4-cam inference on the rig |

---

## Sampling Rate

- **After every task commit:** Run the task's headless `<automated>` command (fast — proves no wiring/contract regression off-GPU).
- **After every plan wave:** Run `pytest -q` (full headless suite).
- **Before `/gsd-verify-work`:** Full headless suite green AND `pytest tests/test_latency.py -m gpu -x` p95 < 150ms on the 4-cam canonical config (the human-run rig gate).
- **Max feedback latency:** headless seconds; the gpu gate is human-run on the rig (no CI GPU).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | RBT-05 | T-06-SC | Confirm tensorrt provenance on rig (env checkpoint) | human-verify | `pytest tests/test_latency.py -m gpu --co -q` (collectability proxy) | ❌ W0 (rig env) | ⬜ pending |
| 06-01-02 | 01 | 0 | RBT-05 | T-06-01 | engine-aware reid gate (warn-on-engine, raise-on-eager) | unit | `pytest tests/test_reid_check_engine_aware.py tests/test_tracking_import_smoke.py -q` | ✅ created | ⬜ pending |
| 06-01-03 | 01 | 0 | RBT-05 | — | #13107 per-camera isolation; additive config keys | unit | `pytest tests/test_config_engine_keys.py tests/test_batched_detect.py tests/test_tracking_import_smoke.py -q` | ✅ created | ⬜ pending |
| 06-01-04 | 01 | 0 | RBT-05 | T-06-02 | gitignore `.engine`/`.onnx`; doc env+rebuild | config | `grep -v '^#' .gitignore \| grep -c -E '\*\.engine\|\*\.onnx'` | ✅ created | ⬜ pending |
| 06-02-01 | 02 | 1 | RBT-05 | — | FP16 thread-through; #13107 + end2end=False preserved | unit | `pytest tests/test_batched_detect.py tests/test_tracking_import_smoke.py -q` | ✅ extended | ⬜ pending |
| 06-02-02 | 02 | 1 | RBT-05 | T-06-02-01 | one batched forward/tick; coast preserved (RBT-04) | unit | `pytest tests/test_fan_out_batched.py tests/test_latency.py -k mock_timed tests/test_orchestrator_tick.py -q` | ✅ created | ⬜ pending |
| 06-02-03 | 02 | 1 | RBT-05 | — | 4-cam FP16 p95 measured (gates 06-03) | gpu integration | `pytest tests/test_latency.py -m gpu -x` (human, rig, AC) | ✅ (gpu) | ⬜ pending |
| 06-03-01 | 03 | 2 | RBT-05 | T-06-01 | engine↔ReID decision (Open Q1) | decision | n/a (recorded in SUMMARY) | n/a | ⬜ pending |
| 06-03-02 | 03 | 2 | RBT-05 | T-06-03-01 | engine build CLI lazy-import-safe | config | `python -c "import ast; ast.parse(open('tools/build_engine.py').read())"` | ✅ created | ⬜ pending |
| 06-03-03 | 03 | 2 | RBT-05 | T-06-03-02 | graceful engine→eager fallback (RBT-04, no crash) | unit | `pytest tests/test_engine_loader_fallback.py tests/test_tracking_import_smoke.py tests/test_runtime_build.py -q` | ✅ created | ⬜ pending |
| 06-03-04 | 03 | 2 | RBT-05 | T-06-01 | is_engine threaded; engine warns / eager raises | unit | `pytest tests/test_orchestrator_tick.py tests/test_latency.py -k "mock_timed or reid" -q` | ✅ extended | ⬜ pending |
| 06-03-05 | 03 | 2 | RBT-05 | T-06-03-01 | engine built + 4-cam p95 < 150ms (RBT-05 phase goal) | gpu integration | `python tools/build_engine.py` then `pytest tests/test_latency.py -m gpu -x` (human, rig, AC) | ✅ (gpu) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **py3.12 venv with cu12x torch (+ tensorrt)** — GPU torch must import and `torch.cuda.is_available()` true; `import tensorrt` resolves a 10.x version (06-01 Task 1, human checkpoint). Without it every gpu test SKIPs and nothing is measurable — the gating prerequisite.
- [ ] **`tests/test_latency.py` `-m gpu` collectable** on the CUDA env (`pytest tests/test_latency.py -m gpu --co -q`).
- [ ] **engine-aware `assert_native_reid_engaged`** (warn-not-raise when engine-backed) + `tests/test_reid_check_engine_aware.py` (06-01 Task 2).
- [ ] **Track-B batched-detect adapter** (`src/segugio/tracking/batched.py`) + `tests/test_batched_detect.py` (#13107 per-camera state-isolation guard, no GPU) (06-01 Task 3).
- [ ] **additive config keys** `ModelConfig.engine_path` + `use_fp16` + `tests/test_config_engine_keys.py` (06-01 Task 3).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| py3.12 cu12x torch + tensorrt env stood up | RBT-05 | OS-level venv + GPU wheel install on the rig; agent has no rig access and cannot run CUDA on this box | `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` True + RTX 4000 Ada; `import tensorrt; tensorrt.__version__` 10.x (06-01 Task 1) |
| 4-cam FP16-batched decision loop p95 measured | RBT-05 | GPU-only measurement; CPU box SKIPs the gpu marker; battery throttles (measure on AC) | `pytest tests/test_latency.py -m gpu -x` on the rig on AC; record `loop total p95` + PASS/FAIL vs 150ms (06-02 Task 3) |
| One-time TensorRT FP16 engine build on the deploy GPU | RBT-05 | The `.engine` is GPU/driver-specific, takes minutes, requires the live CUDA env; not portable, not committable | `python tools/build_engine.py` on the RTX 4000 Ada → `yolo26s.engine` beside the weights (06-03 Task 2/5) |
| 4-cam engine-path decision loop p95 < 150ms (RBT-05 phase goal) | RBT-05 | GPU-only, engine-specific, on AC | point `model.engine_path` at the built engine, `pytest tests/test_latency.py -m gpu -x`; record `loop total p95` < 150ms + engine-path reid behavior matching the Q1 decision + competitor-lock continuity (06-03 Task 5) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 / human-checkpoint dependencies (the three GPU/decision-only tasks are explicitly human-verify/decision with headless proxies + a `<human-check>`; no 3 consecutive code tasks lack automated verify)
- [x] Sampling continuity: every code-producing task carries a headless `<automated>` command
- [x] Wave 0 covers all MISSING references (py3.12 GPU env, engine-aware gate, batched adapter, config keys)
- [x] No watch-mode flags
- [x] Feedback latency: headless seconds; gpu gate human-run on the rig (no CI GPU)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned (pending execution)
