---
phase: 19
slug: detection-eval-on-real-footage-fine-tune-decision
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-14
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (custom `gpu` marker registered in `pyproject.toml:51`, gated by `tests/conftest_tracking.py`) |
| **Config file** | `pyproject.toml` (`testpaths=["tests"]`, `addopts="-q"`, `markers=["gpu: ..."]`) |
| **Quick run command** | `python -m pytest -m "not gpu" -q` (CPU: pure IoU/matcher + GT-parse + headless label-tool units) |
| **Full suite command** | `venv312\Scripts\python.exe -m pytest tests/test_yolo_clips_eval.py -m gpu` (GPU harness, from venv312, on AC power) |
| **Estimated runtime** | CPU quick ~5s; gpu harness ~30-90s per labeled slice on the RTX 4000 Ada |

The pure IoU/matcher (`detection_metrics.py`) is CPU-unit-testable with NO GPU/torch. The
recall/precision harness (`run_detection_eval`) is `@pytest.mark.gpu` and runs from `venv312`
(py3.12 + cu126 torch); the py3.14 CPU `.venv` SKIPs every gpu-marked test.

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest -m "not gpu" -q` (pure metric + GT-parse + label-tool units — fast, CPU).
- **After every plan wave:** Run the gpu harness from `venv312` on one real labeled slice (proves the FP16 forward + metric end-to-end): `venv312\Scripts\python.exe -m pytest tests/test_yolo_clips_eval.py -m gpu -k detection_recall_precision`.
- **Before `/gsd-verify-work`:** Full CPU suite green AND the gpu harness run + numbers captured into `19-DECISION.md`.
- **Max feedback latency:** ~10 seconds (CPU quick suite).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | DET-02/03 | T-19-01-02 | aggregate never divides by zero (recall/precision None) | unit (CPU) | `python -m pytest -m "not gpu" -q tests/test_detection_metrics.py` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | DET-02 | T-19-01-01 | GT parsed via yaml.safe_load; box bounds validated | unit (CPU) | `python -m pytest -m "not gpu" -q tests/test_detection_gt.py tests/test_tracking_import_smoke.py` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 1 | DET-01 | — | disc-only scope recorded; coverage asserted | unit (CPU) | `python -m pytest -m "not gpu" -q tests/test_fixtures_catalogue.py` | ⚠️ extend | ⬜ pending |
| 19-02-02 | 02 | 1 | DET-01 | T-19-02-01 | new slices/`.tags` stay gitignored (no footage/PII committed) | manifest re-parse | `python -m pytest -m "not gpu" -q tests/test_fixtures_catalogue.py` | ✅ | ⬜ pending |
| 19-03-01 | 03 | 2 | DET-02 | T-19-03-01/03 | tool imports no ultralytics/torch (D-05); `--out` under tests/fixtures | unit (CPU, headless) | `python -m pytest -m "not gpu" -q tests/test_label_clips.py` | ❌ W0 | ⬜ pending |
| 19-03-02 | 03 | 2 | DET-02 | T-19-03-02 | GT sidecar tracked; footage binary stays local | schema validate | `python -c "import glob,segugio.tracking as t;[t.parse_gt(f) for f in glob.glob('tests/fixtures/disc_dog/*.gt.yaml')]"` | ❌ operator | ⬜ pending |
| 19-04-01 | 04 | 2 | DET-03 | T-19-04-02 | FP16 forward (half=True), never eager FP32 track() | import + source | `python -m pytest -m "not gpu" -q tests/test_tracking_import_smoke.py tests/test_imports.py` | ✅ | ⬜ pending |
| 19-04-02 | 04 | 2 | DET-03 | T-19-04-02 | gpu test asserts half=True / end2end=False | gpu (skips off-GPU) | `python -m pytest -q tests/test_yolo_clips_eval.py -k detection_recall_precision` | ❌ W0 (extend) | ⬜ pending |
| 19-05-01 | 05 | 3 | DET-03 | T-19-05-02 | numbers from a real venv312 run, never fabricated | gpu | `venv312\Scripts\python.exe -m pytest tests/test_yolo_clips_eval.py -m gpu -k detection_recall_precision` | ✅ (from 19-04) | ⬜ pending |
| 19-05-02 | 05 | 3 | DET-04 | T-19-05-01 | decision doc = aggregates only, no PII/frames | doc grep | `grep -niE "method\|p04\|distant\|0.70\|GO\|NO-GO" .planning/phases/19-*/19-DECISION.md` | ❌ W0 | ⬜ pending |
| 19-05-03 | 05 | 3 | DET-04 | — | operator confirms verdict vs measured numbers | manual (human-verify) | `test -f .planning/phases/19-*/19-DECISION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_detection_metrics.py` — pure `iou`/`score_frame`/`aggregate` (TP/FP/FN, null-GT precision, empty-detection FN) — DET-02/03 (created in 19-01)
- [ ] `tests/test_detection_gt.py` — GT sidecar round-trip (safe_dump/safe_load, normalized-corner bounds, `bbox: null`) — DET-02 (created in 19-01)
- [ ] `tests/test_label_clips.py` — headless pixel→normalized conversion + parse_gt round-trip — DET-02 (created in 19-03)
- [ ] Extend `tests/test_yolo_clips_eval.py` — add `@pytest.mark.gpu test_detection_recall_precision` (asserts recall/precision keys + FP16 forward) — DET-03 (created in 19-04)
- [ ] Extend `tests/test_fixtures_catalogue.py` — disc coverage + agility carry-forward assertion — DET-01 (created in 19-02)
- [ ] Framework install: none (pytest already configured, `gpu` marker registered)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cutting new disc slices for `multi_dog`/`midfield_equidistant` | DET-01 | Requires an operator to scrub ~10h of LOCAL private footage to find the moments (A5); moments may not exist → carry-forward | Scrub `gara_full.mp4`, cut ~30s slices via opencv `VideoWriter` (no ffmpeg), tag, re-catalogue (19-02 Task 2) |
| Drawing the in-competition dog bbox per frame | DET-02 | Ground truth must be a HUMAN judgment, detector-independent (D-05); `cv2.selectROI` needs an interactive HighGUI window | Run `tools/label_clips.py` on the decisive + precision-guard disc slices; label a ~30-50-frame window per condition (19-03 Task 2) |
| Confirming the go/no-go verdict against real numbers | DET-04 | The fine-tune decision (and any threshold adjustment, D-10 tunable) is an operator judgment on the captured metrics | Review `19-DECISION.md`; spot-check one condition's tp/fp/fn against a rerun (19-05 Task 3) |

The automated portions (pure metric, GT parse, harness FP16-forward assertion, coverage
assertion) fully cover the CODE; the manual items are the inherently human data-production and
sign-off steps.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s (CPU quick suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-14
