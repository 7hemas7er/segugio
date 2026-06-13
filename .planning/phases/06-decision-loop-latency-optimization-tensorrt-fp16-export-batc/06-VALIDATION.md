---
phase: 06
slug: decision-loop-latency-optimization-tensorrt-fp16-export-batc
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-13
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini (verify; Wave 0 confirms `-m gpu` marker registered) |
| **Quick run command** | `pytest tests/test_latency.py -m gpu -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~{N} seconds (latency harness dominates — measure on rig) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_latency.py -m gpu -q` (the canonical p95 gate)
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green AND p95 < 150ms on 4-cam canonical config
- **Max feedback latency:** {N} seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | RBT-05 | — | N/A | integration | `python -c "import torch; assert torch.cuda.is_available()"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] py3.12 venv with cu12x torch (+ tensorrt) — GPU torch must import and `torch.cuda.is_available()` true
- [ ] `tests/test_latency.py` `-m gpu` marker registered and collectable on the CUDA env
- [ ] (planner to confirm) conftest / fixtures for engine-vs-eager weight swap

*Filled by planner — see RESEARCH.md "Validation Architecture" section.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| {behavior} | RBT-05 | {reason — e.g. one-time TensorRT engine build on the deploy GPU} | {steps} |

*Filled by planner.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < {N}s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
