---
phase: 4
slug: yolo-per-camera-tracking-on-recorded-clips
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-10
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` § Validation Architecture. Split per D-09:
> CPU-only deterministic logic tests (the "brain", run everywhere every commit)
> vs a GPU-gated real-YOLO-on-clips eval (heavy, human-judged, SKIPs on CPU/CI).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-cov 7.1.0 (`[project.optional-dependencies] dev`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_competitor_lock.py tests/test_plausibility_gate.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest` (GPU-marked tests SKIP automatically when torch/CUDA/weights absent) |
| **Estimated runtime** | ~5–15 s CPU-pure suite; GPU eval is separate, run on the CUDA box after `pip install -e ".[heavy]"` |

> **Run tests via `.venv/bin/python -m pytest`** — system `python3` does not see numpy (conftest note, STATE.md).
> **NEW `gpu` marker** — register in `pyproject.toml` `[tool.pytest.ini_options] markers`; autouse `skipif` skips when `torch` import fails OR `torch.cuda.is_available()` is False OR weights absent (Wave 0).

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_competitor_lock.py tests/test_plausibility_gate.py -x`
- **After every plan wave:** Run `.venv/bin/python -m pytest` (full CPU-pure suite; GPU tests skip)
- **Before `/gsd:verify-work`:** Full CPU-pure suite green; GPU eval run + overlay reviewed on the CUDA box
- **Max feedback latency:** ~15 seconds (CPU-pure suite)

---

## Per-Task Verification Map

> Task IDs are assigned by the planner (plans not yet created). Rows below are requirement-level
> seeds; the planner/`gsd-nyquist-auditor` refines Task IDs and adds the Threat Ref column from the
> `<threat_model>` blocks. Test Type: **PURE** = CPU-only deterministic; **GPU** = `@pytest.mark.gpu`.

| Task ID | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| TBD (planner) | 0 | infra | N/A | smoke | `pytest tests/test_tracking_import_smoke.py -x` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | TRK-03 | malformed frame → `None`/coast, never raise | PURE | `pytest tests/test_signals_map.py -x` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | TRK-04 | locks in-field competitor, not handler/bystander | PURE | `pytest tests/test_competitor_lock.py -x` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | TRK-05 | suspect box rejected → `None` (coast), prev not poisoned | PURE | `pytest tests/test_plausibility_gate.py -x` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | D-08 | metric counters pure & correct | PURE | `pytest tests/test_tracking_metrics.py -x` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | TRK-01 | one tracker per cam_id, never frame list; dog by name | GPU | `pytest -m gpu tests/test_yolo_clips_eval.py::test_per_camera_isolation` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | TRK-02 | native ReID engaged (`end2end=False`); NO cls fallback | GPU (HARD) | `pytest -m gpu tests/test_yolo_clips_eval.py::test_native_reid_engaged` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | D-08 | overlay + per-clip metrics on hard clips | GPU | `pytest -m gpu tests/test_yolo_clips_eval.py::test_overlay_and_metrics` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Register `gpu` pytest marker + autouse skip in `pyproject.toml` / tracking-scope `conftest` (skip when torch/CUDA/weights absent)
- [ ] `tests/test_tracking_import_smoke.py` — lazy-import boundary: `import segugio.tracking` succeeds with `torch`/`ultralytics`/`cv2` forced ABSENT (01-01 pattern)
- [ ] `tests/test_signals_map.py` — TRK-03 pure `Results.boxes` row → frozen `DetectionSignal` mapping (incl. `None`-id → empty, determinism)
- [ ] `tests/test_competitor_lock.py` — TRK-04 pure logic on synthetic tracks (zone+motion acquire, sticky continuity, loss→re-acquire, per-camera independence)
- [ ] `tests/test_plausibility_gate.py` — TRK-05 pure logic (teleport, size-jump, continuous-fast false-positive guard, distinct-from-Phase-2)
- [ ] `tests/test_tracking_metrics.py` — D-08 pure metric counters (ID-switch, %lock-held, coast/uncertain)
- [ ] `tests/test_yolo_clips_eval.py` — `@pytest.mark.gpu` real-YOLO eval (TRK-01/02 + overlay/metrics)
- [ ] Multi-track extension to `synth.detection_stream` (≥2 simultaneous tracks, per-track zone/motion/path) for competitor-lock + crossing-swap tests
- [ ] `seeded_rng` reuse from `conftest`; add a `tracking_params` / crop-geometry fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Debug-overlay video correctness (boxes / track IDs / locked-subject highlight / zone overlays) | D-08, TRK-04/05 | An auto-director's correctness is ultimately visual; no automated assertion replaces eyeballing the locked subject through crossings/re-entry | On CUDA box: run the GPU eval, open each rendered overlay clip, confirm the highlighted track is the in-competition dog through blur/re-entry on `handler_close_01`, `crowd_distractor_01`, `sprint_blur_01` |
| COCO-`dog` recall on small/low-light clips | Q2 / D-02 | Measurement for the deferred custom-model decision, NOT a Phase-4 pass/fail gate | GPU eval logs per-clip recall on `distant_01` / `dusk_distant_01`; record the number, do not fail on it |
| UNVERIFIED case logging | D-02 | Corpus has no agility-tunnel-occlusion and no clean two-similar-dogs-crossing clip | GPU eval must emit explicit `UNVERIFIED: <case> — no corpus footage` log lines (synthetic crossing test exercises the *logic* only); confirm the lines appear, not a silent pass |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (CPU-pure suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
