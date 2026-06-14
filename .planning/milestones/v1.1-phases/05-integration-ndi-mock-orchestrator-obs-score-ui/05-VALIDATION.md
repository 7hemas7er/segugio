---
phase: 5
slug: integration-ndi-mock-orchestrator-obs-score-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-11
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `05-RESEARCH.md` §Validation Architecture. Task IDs/waves are finalized by the planner; rows are keyed to requirement + plan stub until then.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==9.0.3` (+ `pytest-cov==7.1.0`) — already pinned; no install needed |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`, markers `gpu`/`ndi`/`obs`) |
| **Quick run command** | `python -m pytest tests/ -q -m "not gpu and not ndi and not obs"` |
| **Full suite command** | `python -m pytest tests/ -q` (Windows box; runs gpu/ndi/obs where the env is present) |
| **Estimated runtime** | ~15–30 s headless (mock NDI + fake OBS); real NDI/OBS/GPU paths added on Windows |

> **D-01 gotcha:** always invoke `python -m pytest` (never bare `pytest`) — ultralytics pollutes the bare entry point. Re-verify on Windows.

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/ -q -m "not gpu and not ndi and not obs"` (fast, deterministic, headless)
- **After every plan wave:** `python -m pytest tests/ -q -m "not ndi and not obs"` (+ `-m gpu` on the GPU box for latency)
- **Before `/gsd-verify-work`:** full suite green on Windows (incl. `-m "gpu or ndi or obs"`) PLUS the one human E2E run (D-07)
- **Max feedback latency:** ~30 seconds (headless quick run)

---

## Per-Task Verification Map

> Keyed by requirement → plan stub. Exact `NN-NN-NN` task IDs and execution waves are assigned by the planner (gsd-planner) and back-filled here. "Wave 0" = the test-scaffolding stubs that must exist before implementation tasks.

| Requirement | Plan | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------|----------|-----------|-------------------|-------------|--------|
| NDI-01 | 05-02 | Real cyndilib receiver yields BGR frames + last-NEW-frame ts | integration (real NDI) | `python -m pytest tests/test_ndi_source.py -m ndi -x` | ❌ W0 | ⬜ pending |
| NDI-02 | 05-02 | Mock Sender publishes a named source consumable by the receiver | integration (real NDI) | `python -m pytest tests/test_ndi_mock_sender.py -m ndi -x` | ❌ W0 | ⬜ pending |
| NDI-03 | 05-01 | Empty/zero-res first frames are skipped | unit | `python -m pytest tests/test_frame_source_empty_guard.py -x` | ❌ W0 | ⬜ pending |
| OBS-01 | 05-03 | `cut("CAM Long")` → fake records `set_current_program_scene("CAM Long")` | unit | `python -m pytest tests/test_obs_mapping.py::test_cut -x` | ❌ W0 | ⬜ pending |
| OBS-02 | 05-03 | PIP toggles use the CACHED numeric id; id resolved once at connect | unit | `python -m pytest tests/test_obs_mapping.py::test_pip_cached_id -x` | ❌ W0 | ⬜ pending |
| OBS-03 | 05-03 | Reconnect path re-creates the client after a simulated drop | unit (fake) / integration | `python -m pytest tests/test_obs_reconnect.py -x` | ❌ W0 | ⬜ pending |
| OBS-04 | 05-03 | Scene-template file exists + names match config `obs_scene`/`SAFE` | unit | `python -m pytest tests/test_scene_template.py -x` | ❌ W0 | ⬜ pending |
| OBS-05 | 05-03 | Overlay write hits read-from-file path; `set_input_settings({"text":...})` fallback | unit | `python -m pytest tests/test_overlay.py -x` | ❌ W0 | ⬜ pending |
| SCR-01 | 05-05 | Atomic write: a concurrent reader never sees a partial file; round-trips | unit | `python -m pytest tests/test_atomic_io.py -x` | ❌ W0 | ⬜ pending |
| SCR-02 | 05-05 | Flask POST /score for each discipline writes expected file content | unit (Flask test client) | `python -m pytest tests/test_ui_score.py -x` | ❌ W0 | ⬜ pending |
| SCR-03 | 05-05 | Run start/stop writes runstate; START flags lock-reset, STOP flags SAFE-park | unit | `python -m pytest tests/test_ui_run.py -x` | ❌ W0 | ⬜ pending |
| SCR-04 | 05-05 | No scoring/adjudication code path exists (display-only) | unit (assert no compute) | `python -m pytest tests/test_score_display_only.py -x` | ❌ W0 | ⬜ pending |
| RBT-01 | 05-04 | Watchdog liveness on INJECTED timestamps: stalled ts → dead after timeout+grace | unit (pure) | `python -m pytest tests/test_watchdog.py -x` | ❌ W0 | ⬜ pending |
| RBT-02 | 05-04 | Feed-death → `alive[cam]=False` → FSM excludes it → SAFE/other-live; guarded rejoin | unit | `python -m pytest tests/test_fallback_rejoin.py -x` | ❌ W0 | ⬜ pending |
| RBT-04 | 05-06 | Thrown error in any stage (UI/decode/OBS) → loop coasts to SAFE, never crashes; SAFE on shutdown | unit (throwing fakes) | `python -m pytest tests/test_fault_isolation.py -x` | ❌ W0 | ⬜ pending |
| RBT-05 | 05-06 | Latency harness: frame→YOLO→score→FSM→OBS p95 < 150ms (target <80ms) | integration (gpu) / unit (mock-timed) | `python -m pytest tests/test_latency.py -m gpu -x` | ❌ W0 | ⬜ pending |
| D-08 | 05-06 | Sustained motion energy → `HoldInput.action=True` → FSM holds the cut (DEC-03 cap) | unit | `python -m pytest tests/test_action_hold.py -x` | ❌ W0 | ⬜ pending |
| D-11 | 05-06 | Orchestrator writes status (live cam + reason + per-feed alive/dead) the UI reads | unit | `python -m pytest tests/test_status_channel.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Test scaffolding that must exist before implementation tasks (one stub per requirement, all initially red):

- [ ] `tests/conftest.py` — shared fixtures: tiny `Config` builder, fake `FrameSource`, `RecordingObsController`, injected-timestamp clock, `tmp_path` file channel
- [ ] `tests/test_atomic_io.py` — SCR-01 (atomic round-trip + same-dir temp)
- [ ] `tests/test_watchdog.py` — RBT-01 (injected-timestamp liveness math)
- [ ] `tests/test_obs_mapping.py` — OBS-01/02 (recording fake: cut + cached PIP id)
- [ ] `tests/test_obs_reconnect.py` — OBS-03 (reconnect)
- [ ] `tests/test_overlay.py` — OBS-05
- [ ] `tests/test_scene_template.py` — OBS-04 (template names match config)
- [ ] `tests/test_frame_source_empty_guard.py` — NDI-03
- [ ] `tests/test_fallback_rejoin.py` — RBT-02
- [ ] `tests/test_fault_isolation.py` — RBT-04 (throwing fakes → SAFE coast)
- [ ] `tests/test_latency.py` — RBT-05 (mock-timed + gpu-marked)
- [ ] `tests/test_ui_score.py`, `tests/test_ui_run.py` — SCR-02/03 (Flask test client)
- [ ] `tests/test_score_display_only.py` — SCR-04
- [ ] `tests/test_action_hold.py` — D-08
- [ ] `tests/test_status_channel.py` — D-11
- [ ] `tests/test_ndi_source.py`, `tests/test_ndi_mock_sender.py` — NDI-01/02 (`@pytest.mark.ndi`, Windows-only)
- [ ] Register `ndi` + `obs` markers in `pyproject.toml [tool.pytest.ini_options].markers`
- [ ] Add `Flask==3.1.3` dependency for the UI tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real cyndilib receive of a named NDI source | NDI-01/02 | Requires libndi + a live named source on the network (Windows box) | On Windows: start the mock Sender publishing a clip as a named source; run `python -m pytest -m ndi`; confirm BGR frames + advancing timestamp |
| End-to-end on real OBS | OBS-01..05 | Requires OBS Studio + DistroAV + obs-websocket v5 running | Load the scene-collection template; run the orchestrator; confirm scene cuts, PIP toggle, and overlay text update live (D-07) |
| True latency under load (3–4 cams, real GPU) | RBT-05 | Real `yolo26s.pt` on the RTX 4000 Ada gives the actual figure | On the GPU box: `python -m pytest tests/test_latency.py -m gpu`; record p95 < 150ms (target <80ms) |
| Full human E2E run | D-07 | Acceptance bar combines NDI→YOLO→score→FSM→OBS + a cut/frozen feed → watchdog → SAFE | Follow D-07 script on Windows; observe SAFE on feed-death and recovery |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
