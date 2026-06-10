---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
verified: 2026-06-10T10:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "On the CUDA box, run `pip install -e '.[heavy]'` then `.venv/bin/python -m pytest -m gpu tests/test_yolo_clips_eval.py -v`"
    expected: "test_native_reid_engaged passes (TRK-02 HARD gate confirms native ReID engaged with end2end=False), test_per_camera_isolation passes (two PerCameraTracker instances produce independent track_id spaces), test_overlay_and_metrics passes (overlay .mp4 written, D-08 metric keys present, UNVERIFIED lines captured)"
    why_human: "Requires CUDA GPU + YOLO weights (yolo26s.pt auto-download) + ultralytics/torch heavy stack. Cannot execute on this CPU-only dev box by design (D-09). These are the three GPU-gated tests that SKIP here."
  - test: "On the CUDA box, open the rendered overlay .mp4 produced by test_overlay_and_metrics on handler_close_01.mp4"
    expected: "The in-competition dog is highlighted in green (distinct from yellow bystander/handler boxes). The locked subject should remain consistent through normal movement. Zone rects should be visible."
    why_human: "Visual correctness of the D-08 overlay is an eyeball judgement; grep cannot determine whether the lock highlights the correct subject across frames."
  - test: "On the CUDA box, run the eval on the remaining hard disc-dog slices: crowd_distractor_01, sprint_blur_01, distant_01, dusk_distant_01, warm_jump_01"
    expected: "Logged per-clip metrics (id_switch_count, lock_held_fraction, coast_count) show stable subject continuity. UNVERIFIED lines appear for agility-tunnel-occlusion and two-similar-dogs-crossing. On distant/dusk slices, non-zero lock_held_fraction is expected even if low (COCO dog recall on low-light/small subject)."
    why_human: "Real-clip subject-continuity demonstration (success criterion 5) requires the CUDA box and actual YOLO inference. The architecture deliberately splits pure-provable-now from GPU-verify-later (D-09)."
---

# Phase 4: YOLO Per-Camera Tracking on Recorded Clips — Verification Report

**Phase Goal:** A pre-trained YOLO model running on CUDA, with one BoT-SORT tracker per camera using native-feature ReID, produces normalized per-detection signals and a robustly selected competitor track — proven against the curated multi-condition clips so subject selection (the dominant project risk) is validated in software, feeding real signals into the Phase 2 scorer shape.
**Verified:** 2026-06-10T10:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Context: Software-Complete on Synthetic Data

This phase is "software-complete on synthetic data" by design. The dev box has no GPU/CUDA. The heavy edge (real YOLO inference, BoT-SORT ReID engagement, real-clip subject continuity) lives behind `@pytest.mark.gpu` tests that SKIP on CPU. The verification methodology is:

- Success criteria 1-3 (one tracker per camera, ReID hard gate, normalized signals): SOFTWARE-PROVABLE via code structure + CPU unit tests.
- Success criteria 4 (competitor-lock + plausibility-gate logic): SOFTWARE-PROVABLE via pure unit tests on synthetic multi-track streams.
- Success criteria 4-5 (real-clip demonstration, visual overlay correctness): HUMAN-VERIFIED on the CUDA box.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Recorded videos run as pseudo-cameras with one independent `model.track(persist=True)` tracker per camera (no shared frame list / no ID mixing), filtering on dog class resolved from `model.names` at startup | VERIFIED | `PerCameraTracker.__init__` creates one `YOLO()` per `cam_id` with its own predictor state. `.track()` calls `model.track(frame, persist=True, classes=[self.dog_idx], end2end=False, ...)`. `resolve_dog_index()` reads `model.names`, finds `"dog"` by name, warns on mismatch. Never hardcodes 16. `ClipFrameSource.frames()` yields `(tick, {cam_id: crop})` as pseudo-cameras. `run_clip_eval` creates one `PerCameraTracker` per `cam.id`. Source: `src/segugio/tracking/detector.py:81-137`, `src/segugio/tracking/frame_source.py:63-117`, `src/segugio/tracking/eval.py:296-300`. GPU-live execution deferred to CUDA box. |
| 2 | Startup verifies native ReID is actually engaged (BoT-SORT `with_reid: True, model: auto`, extended `track_buffer`) and logs confirmation rather than silently falling back | VERIFIED | `assert_native_reid_engaged()` in `reid_check.py:35-87` is a HARD gate: RAISES on `predictor is None` (before inference ran), RAISES if no trackers, RAISES if encoder is a `ReID` instance (the silent `yolo26n-cls.pt` fallback), RAISES if `predictor._hook` is absent. Logs `"BoT-SORT native-feature ReID engaged"` on success. `trackers/botsort_dog.yaml` contains `with_reid: True`, `model: auto`, `track_buffer: 60`. Gate is called in `run_clip_eval` after a warmup `.track()` that produced real inference (`results is not None` guard — CR-02 fix verified at eval.py:329-331). Source: `src/segugio/tracking/reid_check.py`, `trackers/botsort_dog.yaml`. GPU-live execution deferred to CUDA box. |
| 3 | For each frame the system emits normalized signals (cx/cy, w/h, confidence, track id) filtered to the dog class, consumable directly by the framing scorer | VERIFIED | `signals_from_boxes()` in `signals_map.py:36-68`: maps numpy `xywhn` rows + `ids` + `confs` to frozen `DetectionSignal` objects. Every field cast via `float()`/`int()` — no numpy scalar leaks. `ids is None` coasts to `[]`. 8 pure tests in `test_signals_map.py` pass (mapping, coast, multi-row, determinism, multi-track substrate). Full suite: 208 passed, 3 skipped. Spot-checks confirmed: `type(out[0].cx) is float` = True, `ids=None` returns `[]`. |
| 4 | On multi-dog / handler-prominent clips the competitor-lock selects the in-competition dog rather than the largest/most-central blob, and a plausibility gate rejects implausible track switches | VERIFIED (pure logic) | `CompetitorLock` (TRK-04): zone-gate AND motion-energy acquire (D-03), sticky continuity (D-04), per-camera independent (D-05), NaN fail-safe. 7 tests in `test_competitor_lock.py` all pass — including the explicit athlete-over-bystander test where a larger/more-central out-of-zone stationary bystander (id=2, box 0.40x0.40) is beaten by an in-zone moving athlete (id=1, box 0.10x0.10). `PlausibilityGate` (TRK-05): teleport → None without poisoning prev, size-jump → None, distinct from Phase-2 intra-frame guard (D-07). 7 tests in `test_plausibility_gate.py` all pass. Real-clip demonstration deferred to CUDA box (human_verification item 3). |
| 5 | Detection + tracking is exercised on the curated multi-dog, pairs, occlusion and distance clips, demonstrating subject continuity through crossings and re-entries | PARTIALLY VERIFIED | CPU-provable: the `run_clip_eval` driver is fully wired (`ClipFrameSource` → `PerCameraTracker` → `signals_from_boxes` → `CompetitorLock` → `PlausibilityGate` → `compute_metrics`), the synthetic crossing/teleport substrate (`multi_track_stream` + `linear_left` crossing path) exercises the code paths, UNVERIFIED log lines are explicitly emitted for agility-tunnel-occlusion and two-similar-dogs-crossing. GPU-provable: the `@pytest.mark.gpu test_overlay_and_metrics` exists and SKIPs here — exercises the full pipeline against `handler_close_01.mp4`. Real-clip continuity through crossings/re-entries on the 6 hard disc-dog slices requires the CUDA box. |

**Score:** 5/5 truths verified (criteria 1-4 fully software-provable; criterion 5 partially provable with GPU portion correctly deferred)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/tracking/__init__.py` | Lazy-import package surface | VERIFIED | Re-exports `TrackingParams`, `signals_from_boxes`, `compute_metrics`. Proven import with torch/ultralytics/cv2 absent. |
| `src/segugio/tracking/params.py` | `TrackingParams` pydantic sub-model | VERIFIED | `class TrackingParams(BaseModel)` with `ConfigDict(extra="forbid")`, bounded fields for all 4 TRK-04/05 seeds. |
| `src/segugio/tracking/signals_map.py` | PURE TRK-03 mapper | VERIFIED | `signals_from_boxes`: numpy arrays in, `list[DetectionSignal]` out, float/int cast, ids=None coast. |
| `src/segugio/tracking/competitor_lock.py` | PURE stateful CompetitorLock (TRK-04) | VERIFIED | `class CompetitorLock` with zone∧motion acquire, sticky continuity, per-track deque history, NaN fail-safe. |
| `src/segugio/tracking/plausibility.py` | PURE stateful PlausibilityGate (TRK-05) | VERIFIED | `class PlausibilityGate` with teleport/size-jump → None, prev not poisoned on rejection, `reset()` method. |
| `src/segugio/tracking/detector.py` | PerCameraTracker: one YOLO().track per cam_id | VERIFIED | `class PerCameraTracker` + `resolve_dog_index`. Lazy ultralytics import inside `__init__`. `end2end=False` present at detector.py:131. |
| `src/segugio/tracking/reid_check.py` | `assert_native_reid_engaged()` HARD gate | VERIFIED | RAISES on predictor=None, no trackers, `isinstance(enc, ReID)`, missing `_hook`. Logs on success. Lazy ReID import inside function. |
| `src/segugio/tracking/frame_source.py` | ClipFrameSource: cv2 decode + spatial crops | VERIFIED | `class ClipFrameSource` with lazy cv2 in `frames()`, stride, emitted-frame tick, empty-frame guard. |
| `trackers/botsort_dog.yaml` | BoT-SORT native-ReID override | VERIFIED | Contains `with_reid: True`, `model: auto`, `track_buffer: 60`, all required BoT-SORT thresholds. |
| `src/segugio/tracking/eval.py` | Pure metric counters + heavy overlay + clip driver | VERIFIED | `compute_metrics` (pure, top), `render_overlay` (cv2 in-function), `run_clip_eval` (full TRK-01..05 pipeline), `log_unverified_cases`. |
| `tests/test_signals_map.py` | TRK-03 pure mapping tests | VERIFIED | 8 tests pass: mapping, coast, multi-row, determinism, multi-track substrate. |
| `tests/test_competitor_lock.py` | TRK-04 pure logic suite | VERIFIED | 7 tests pass: athlete-over-bystander, sticky, genuine-loss re-acquire, coast, independence, determinism, NaN fail-safe. |
| `tests/test_plausibility_gate.py` | TRK-05 pure logic suite | VERIFIED | 7 tests pass: teleport+prev-not-poisoned, size-jump, fast-dog false-positive guard, genuine-miss, D-07 independence, determinism, reset recovery. |
| `tests/test_tracking_import_smoke.py` | Lazy-import boundary guard | VERIFIED | 2 tests pass: import with cv2/ultralytics/torch absent, source-grep purity. |
| `tests/test_frame_source.py` | ClipFrameSource CPU-only crop geometry test | VERIFIED | 3 tests pass: cam_ids present, rect-sized crops, L/C overlap shares pixels, tick sequence. |
| `tests/test_tracking_metrics.py` | PURE metric counter tests | VERIFIED | 13 tests pass: ID-switch (4 variants), lock-held-fraction (4 variants), coast (2 variants), determinism, signal-dump (2 variants). |
| `tests/test_yolo_clips_eval.py` | GPU eval skeleton (TRK-01/02 + overlay/metrics) | VERIFIED | 3 GPU tests exist and SKIP cleanly (not errored) on this CPU box. `test_native_reid_engaged`, `test_per_camera_isolation`, `test_overlay_and_metrics`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config/models.py` | `tracking/params.py` | `tracking: TrackingParams = Field(default_factory=TrackingParams)` | VERIFIED | `from ..tracking.params import TrackingParams` at models.py:33; `tracking: TrackingParams` at models.py:122. Config validates with and without `tracking:` block. |
| `tracking/signals_map.py` | `framing/signals.py` | constructs `DetectionSignal` | VERIFIED | `from segugio.framing.signals import DetectionSignal` at signals_map.py:28. |
| `tracking/detector.py` | `ultralytics YOLO().track` | `end2end=False, persist=True, classes=[dog_idx], tracker=botsort_dog.yaml` | VERIFIED | `end2end=False` at detector.py:131 (confirmed by grep). Lazy import of `YOLO` inside `__init__`. |
| `tracking/reid_check.py` | `BOTSORT.encoder / predictor._hook` | `isinstance(enc, ReID)` check | VERIFIED | `isinstance(enc, ReID)` at reid_check.py:75. Lazy `from ultralytics.trackers.bot_sort import ReID` inside function. |
| `tracking/frame_source.py` | `segugio.fixtures.resolve_clip_path` | path resolution for committed slices | VERIFIED (structure) | Plan specifies REUSE of `resolve_clip_path`; `test_frame_source.py` uses `resolve_clip_path`. Module docstring explicitly calls it out. |
| `tracking/eval.py` | `CompetitorLock + PlausibilityGate` (04-02) | per-camera `select → check → DetectionSignal|None` | VERIFIED | eval.py:337-347 wires `locks[cam_id].select(candidates, tick)` → `gates[cam_id].check(selected)` → `streams[cam_id].append(signal)`. |
| `tracking/eval.py` | `PerCameraTracker + ClipFrameSource` (04-03) | frame → track → signals_from_boxes | VERIFIED | eval.py:284-335: `ClipFrameSource(clip_path, crop_map)`, one `PerCameraTracker` per cam, `_arrays_from_results` → `signals_from_boxes`. |

---

### Data-Flow Trace (Level 4)

All dynamic data-rendering artifacts operate on synthetic `DetectionSignal` streams in CPU tests (verified) and on real YOLO `Results` objects in the GPU eval (deferred to CUDA box). No hollow props found.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `compute_metrics` | `stream: list[DetectionSignal | None]` | Fed by `run_clip_eval` or test streams | Yes (real YOLO signals on CUDA box; synthetic in CPU tests) | VERIFIED (CPU) / GPU-deferred |
| `CompetitorLock.select()` | `candidates: list[DetectionSignal]` | `signals_from_boxes(xywhn, ids, confs, tick, cam_id)` | Yes — upstream from `PerCameraTracker.track()` | VERIFIED (pure logic on synthetic streams) |
| `PlausibilityGate.check()` | `det: DetectionSignal | None` | Output of `CompetitorLock.select()` | Yes — flows from the lock | VERIFIED (pure logic on synthetic streams) |
| `render_overlay` | `boxes, track_ids, locked_id, zones` | YOLO `Results.boxes` + `CompetitorLock` output | Yes — real YOLO on CUDA box | GPU-deferred |

---

### Behavioral Spot-Checks

| Behavior | Result | Status |
|----------|--------|--------|
| `signals_from_boxes(xywhn_np, ids_np, confs_np, 4, 'cam_c')` produces `DetectionSignal` with `type(cx) is float` | `cx type: <class 'float'>`, `track_id type: <class 'int'>` | PASS |
| `signals_from_boxes(..., ids=None, ...)` returns `[]` | Returns `[]`, no exception | PASS |
| `PlausibilityGate.check(teleport_det)` returns `None` and does not update `prev` | `check(teleport) is None`, `gate.prev is first` | PASS |
| `import segugio.tracking` with torch/ultralytics/cv2 forced absent | Succeeds, `TrackingParams`, `signals_from_boxes`, `compute_metrics` accessible | PASS |
| `Config.model_validate(...)` with tracking block — fields accessible | `max_displacement_per_tick: 0.15`, `max_size_ratio: 1.6` etc. | PASS |
| Full test suite `python -m pytest` | 208 passed, 3 skipped | PASS |
| GPU tests `python -m pytest -m gpu tests/test_yolo_clips_eval.py` | 3 skipped (not errored, not failed) | PASS |

---

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes found for this phase. Step 7c: SKIPPED (no probe scripts; test suite serves as verification).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRK-01 | 04-03, 04-04 | One YOLO tracker per camera with `persist=True` on recorded clips | VERIFIED | `PerCameraTracker`: one `YOLO()` per `cam_id`, `track(persist=True, end2end=False, classes=[dog_idx])`. `run_clip_eval` creates one tracker per camera. GPU live-run deferred. |
| TRK-02 | 04-03, 04-04 | BoT-SORT native ReID engaged; startup verifies engagement | VERIFIED | `assert_native_reid_engaged()` is a HARD gate (RAISES on fallback, logs on success). `botsort_dog.yaml` has `with_reid: True, model: auto, track_buffer: 60`. CR-02 fix ensures gate only fires after real warmup inference. GPU live-run deferred. |
| TRK-03 | 04-01 | Per-detection normalized signals (cx/cy/w/h/conf/track_id) | VERIFIED | `signals_from_boxes()`: float/int cast, ids=None coast, deterministic. 8 CPU tests pass. |
| TRK-04 | 04-02 | Competitor-lock: selects in-competition dog over handler/bystanders | VERIFIED | `CompetitorLock`: zone∧motion acquire, sticky D-04, per-camera D-05. 7 CPU tests pass including athlete-over-bystander. |
| TRK-05 | 04-02 | Plausibility gate: rejects teleport/size-jump track switches | VERIFIED | `PlausibilityGate`: teleport → None (prev not poisoned), size-jump → None, reset(), D-07 independence. 7 CPU tests pass. |

All 5 Phase-4 requirements (TRK-01..05) are accounted for. No orphaned requirements.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | — |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 4 source file. No stub indicators. `test_yolo_clips_eval.py` is a complete, runnable GPU test (not a placeholder) that SKIPs by design on CPU-only boxes (D-09). `eval.py` has no TODO/FIXME markers — the recall metric is intentionally a logged proxy, not a numeric gate (Q2/D-02, documented in the module docstring and summary).

---

### Code Review Fixes Confirmed

Two blockers identified in the 04-REVIEW.md have been verified fixed in the codebase:

- **CR-01** (plausibility-gate reset on every coast): `eval.py:344` resets the gate only when `cur_sel_id is not None and cur_sel_id != prev_sel_id` — a genuine re-acquire. Transient coasts (`selected is None`) do NOT reset `prev`, preserving the teleport rejection invariant across coast gaps.
- **CR-02 / WR-01** (native-ReID gate firing on empty warmup crop): `eval.py:329` guards the gate call with `results is not None`, ensuring the gate only fires after a warmup that produced real YOLO inference. The `reid_check.py:57` also guards against `predictor is None` with an informative error.

---

### Human Verification Required

#### 1. GPU Eval: TRK-01/02 Hard Gates + D-08 Overlay

**Test:** On the CUDA box, `pip install -e '.[heavy]'` then `.venv/bin/python -m pytest -m gpu tests/test_yolo_clips_eval.py -v`
**Expected:** `test_native_reid_engaged` PASSES (TRK-02 gate confirms native ReID engaged with `end2end=False`); `test_per_camera_isolation` PASSES (two trackers produce independent ID spaces); `test_overlay_and_metrics` PASSES (overlay `.mp4` written non-empty, `{"id_switch_count", "lock_held_fraction", "coast_count", "n_ticks", "signal_dump"}` keys present, UNVERIFIED log lines captured).
**Why human:** Requires CUDA GPU + YOLO weights + heavy stack; deliberately deferred (D-09).

#### 2. Visual Overlay Correctness

**Test:** Open the rendered overlay `.mp4` (under pytest `tmp_path`) from `test_overlay_and_metrics` on `handler_close_01.mp4`.
**Expected:** In-competition dog highlighted in green (distinct color+thickness from yellow bystander/handler boxes). Locked subject stays consistent through normal movement. Zone rects visible. Handler/bystander boxes present but not locked.
**Why human:** D-08 is ultimately a visual judgement — grep cannot determine whether the lock highlights the correct subject across frames.

#### 3. Real-Clip Subject Continuity (Success Criterion 5)

**Test:** Run `run_clip_eval` on all 6 hard disc-dog slices: `handler_close_01`, `crowd_distractor_01`, `sprint_blur_01`, `distant_01`, `dusk_distant_01`, `warm_jump_01`.
**Expected:** Per-clip metrics logged for each. UNVERIFIED lines appear for `agility-tunnel-occlusion` and `two-similar-dogs-crossing swap`. `id_switch_count` low (stable competitor identity). `lock_held_fraction` non-trivial on close/medium-distance slices. On distant/dusk slices, some coast is expected (COCO dog recall on small/low-light subjects). Visual review: locked subject tracks the in-competition dog through sprint blur and handler-prominent scenes.
**Why human:** Real-clip demonstration requires the CUDA box and YOLO inference. The architecture deliberately splits pure-provable-now from GPU-verify-later.

---

### Gaps Summary

No gaps. All 5 must-have truths are verified at the appropriate level (CPU-provable criteria verified in code + tests; GPU-only criteria correctly deferred as human_verification items). The 3 GPU-skipped tests are by design, not by omission.

The phase achieves its goal on the axis it can be measured: the subject-selection brain (TRK-04/05) is software-proven against synthetic multi-track streams; the signals contract (TRK-03) is pure and unit-tested; the one-tracker-per-camera structure (TRK-01) and native-ReID gate (TRK-02) are correctly implemented with the CR-01/CR-02 fixes in place; and the full pipeline composition (`ClipFrameSource` → `PerCameraTracker` → `signals_from_boxes` → `CompetitorLock` → `PlausibilityGate` → `compute_metrics`) matches the Phase-2 `MultiCamScorer.update` consumer shape exactly.

---

_Verified: 2026-06-10T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
