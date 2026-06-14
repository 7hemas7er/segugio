---
phase: 7
slug: off-tick-frame-publishing-channel
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-13
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` §"Validation Architecture". Per-Task rows are
> finalized by the planner/Wave-0 once PLAN task IDs exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — see `tests/`) |
| **Config file** | `tests/conftest.py` (fixtures) + `tests/conftest_tracking.py` (gpu/ndi/obs gate logic) |
| **Quick run command** | `pytest tests/test_atomic_io.py tests/test_preview_channel.py tests/test_preview_publisher.py -x` |
| **Full suite command** | `pytest` (headless) · `pytest -m gpu tests/test_latency.py` (rig, gate 1) |
| **Estimated runtime** | ~10–30 s headless · gpu latency gate runs only on the rig |

> `@pytest.mark.gpu` auto-skips off-rig via `conftest.py` `pytest_collection_modifyitems`.

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_atomic_io.py tests/test_preview_channel.py tests/test_preview_publisher.py -x`
- **After every plan wave:** `pytest` (full headless suite — proves no regression to opcomm/loop/runtime/ui)
- **Before `/gsd-verify-work`:** Full headless suite green + `pytest -m gpu tests/test_latency.py` green on the rig (gate 1) + extended import test green with `numpy` blocked (gate 2)
- **Max feedback latency:** ~30 s headless

---

## Per-Task Verification Map

> Requirement/criterion → test seam mapping from research. `Task ID`/`Wave` columns
> are filled by the planner once PLAN.md task IDs are assigned.

| Req / Criterion | Behavior | Test Type | Automated Command | File Exists | Status |
|-----------------|----------|-----------|-------------------|-------------|--------|
| PRV-03 / SC3 | `atomic_write_bytes` temp→replace, no torn read; `fsync` param honored | unit | `pytest tests/test_atomic_io.py -k bytes` | ❌ W0 (extend) | ⬜ pending |
| PRV-02 / SC4 | `PreviewDoc` round-trips; malformed/absent → default, never raises | unit | `pytest tests/test_preview_channel.py` | ❌ W0 (new) | ⬜ pending |
| PRV-02 | "why" mapping: fake scores/dets/decision → correct `PreviewDoc` per-cam fields + auto-candidate + cuts ring | unit (fake encoder) | `pytest tests/test_preview_publisher.py -k payload` | ❌ W0 (new) | ⬜ pending |
| PRV-01 | Mailbox: `offer()` never blocks; last-writer-wins; drain returns latest then `None` | unit | `pytest tests/test_preview_publisher.py -k mailbox` | ❌ W0 (new) | ⬜ pending |
| PRV-01 / SC5 | Publisher encode/IO fault COASTS (logged, no raise), tick still completes (RBT-04 extended) | unit + orch | `pytest tests/test_preview_publisher.py -k coast` + `tests/test_fault_isolation.py` | ❌ W0 (new + extend) | ⬜ pending |
| PRV-01 / SC1 | **HARD GATE 1:** RBT-05 4-cam p95 unchanged within noise, preview ON vs OFF | gpu (sustained) | `pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression` | ❌ W0 (new gpu) | ⬜ pending |
| PRV-03 / SC2 | **HARD GATE 2:** `import segugio.ui` + `create_app` start with `ultralytics/torch/numpy/cv2/cyndilib` absent | unit (import) | `pytest tests/test_ui_score.py::test_app_imports_nothing_heavy` (extend: add `numpy` + start-check) | ✅ exists (extend) | ⬜ pending |
| SC3 | Real-run smoke: writes `opcomm/preview/cam_<id>.jpg` + `preview.json` to disk | integration (headless, fake encoder) | `pytest tests/test_orchestrator_runtime.py -k preview_files` | ❌ W0 (extend) | ⬜ pending |
| SC4 | `status.json`/`DirectorStatus` byte-stable (unchanged) — regression guard | unit | `pytest tests/test_status_channel.py` | ✅ exists (guard) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_preview_channel.py` — `PreviewDoc` round-trip + malformed→default (mirror `test_status_channel.py`) — PRV-02 / SC4
- [ ] `tests/test_preview_publisher.py` — mailbox non-block/last-wins, "why" payload mapping, encode-fault coast (inject fake encoder) — PRV-01 / SC5
- [ ] `tests/test_atomic_io.py` — add `atomic_write_bytes` cases (bytes round-trip; `fsync` param spy) — PRV-03 / SC3
- [ ] `tests/test_latency.py` — add preview-ON-vs-OFF gpu regression test — SC1 (gate 1)
- [ ] `tests/test_ui_score.py::test_app_imports_nothing_heavy` — add `numpy` to blocked set + `create_app` start-check — SC2 (gate 2)
- [ ] `tests/test_orchestrator_runtime.py` and/or `tests/test_fault_isolation.py` — preview-files-written smoke + publisher-fault-coast at orchestrator level
- [ ] Framework install: none — `pytest` + fixtures already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gate-1 noise band calibration | PRV-01 / SC1 | The "within noise" tolerance is rig-empirical, not a magic number | Run two back-to-back preview-OFF `run_measured` passes on the rig; derive the jitter band; assert `p95_on ≤ p95_off + band` |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
