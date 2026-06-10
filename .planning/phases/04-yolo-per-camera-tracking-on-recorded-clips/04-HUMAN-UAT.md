---
status: partial
phase: 04-yolo-per-camera-tracking-on-recorded-clips
source: [04-VERIFICATION.md]
started: 2026-06-10T06:16:29Z
updated: 2026-06-10T06:16:29Z
---

## Current Test

[awaiting human testing on the CUDA box]

## Tests

### 1. GPU-gated test suite passes on real YOLO + native ReID
command: On the CUDA box, run `pip install -e '.[heavy]'` then `.venv/bin/python -m pytest -m gpu tests/test_yolo_clips_eval.py -v`
expected: `test_native_reid_engaged` passes (TRK-02 HARD gate confirms native ReID engaged with `end2end=False`), `test_per_camera_isolation` passes (two `PerCameraTracker` instances produce independent `track_id` spaces), `test_overlay_and_metrics` passes (overlay `.mp4` written, D-08 metric keys present, UNVERIFIED lines captured)
result: [pending]

### 2. Overlay highlights the correct subject (visual)
command: On the CUDA box, open the rendered overlay `.mp4` produced by `test_overlay_and_metrics` on `handler_close_01.mp4`
expected: The in-competition dog is highlighted in green (distinct from yellow bystander/handler boxes); the locked subject stays consistent through normal movement; zone rects are visible
result: [pending]

### 3. Real-clip subject continuity across the hard slices (SC5)
command: On the CUDA box, run the eval on the remaining hard disc-dog slices: `crowd_distractor_01`, `sprint_blur_01`, `distant_01`, `dusk_distant_01`, `warm_jump_01`
expected: Logged per-clip metrics (`id_switch_count`, `lock_held_fraction`, `coast_count`) show stable subject continuity; UNVERIFIED lines appear for agility-tunnel-occlusion and two-similar-dogs-crossing; on distant/dusk slices, non-zero `lock_held_fraction` is expected even if low (COCO dog recall on low-light/small subject)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
