---
status: passed
phase: 04-yolo-per-camera-tracking-on-recorded-clips
source: [04-VERIFICATION.md]
started: 2026-06-10T06:16:29Z
updated: 2026-06-10T08:54:18Z
environment: "NVIDIA RTX 4000 Ada Laptop (12GB), CUDA 13.3, torch 2.12.0+cu130, ultralytics 8.4.62, yolo26s.pt"
---

## Current Test

[complete — all items executed on the CUDA box]

## Tests

### 1. GPU-gated test suite passes on real YOLO + native ReID
command: `.venv/bin/python -m pytest -m gpu tests/test_yolo_clips_eval.py -v`
expected: `test_native_reid_engaged` passes (TRK-02 HARD gate confirms native ReID engaged with `end2end=False`), `test_per_camera_isolation` passes (independent per-camera tracker state), `test_overlay_and_metrics` passes (overlay `.mp4` written, D-08 keys present, UNVERIFIED lines captured)
result: passed (after fixing a real bug — see Gaps). All 3 GPU tests green on real `yolo26s.pt`. `test_native_reid_engaged` does NOT raise → BoT-SORT native-feature ReID is genuinely engaged (no silent `yolo26n-cls.pt` fallback). Full suite: 215 passed, 0 skipped (GPU tests now execute, +4 resolver regression tests).

### 2. Overlay highlights the correct subject (visual)
command: rendered overlay `.mp4` on `handler_close_01.mp4`, frames inspected
expected: in-competition dog highlighted in green (distinct from yellow bystander/handler), lock consistent, zone rects visible
result: passed. Frame 216 shows a thick green box labeled `id=14 LOCK` bounding the dog (Australian Shepherd); the handler (magenta vest) sits OUTSIDE the box — the lock highlights the dog, not the handler. Faint gray zone-gate rect [0.2,0.2,0.8,0.8] visible. Pixel scan: 164 frames carry the green LOCK box (= cam_l lock_held 0.221 × 743), 3 carry a yellow bystander box, 674 carry the zone rect. Note: the overlay renders only the FIRST camera (cam_l, the SAFE cam, lock_held 0.221) — see Gaps note 2.

### 3. Real-clip subject continuity across the hard slices (SC5)
command: `run_clip_eval` on handler_close_01 + crowd_distractor_01, sprint_blur_01, distant_01, dusk_distant_01, warm_jump_01 (743 ticks each, real GPU inference)
expected: per-clip metrics show subject continuity; UNVERIFIED lines for agility-tunnel-occlusion + two-similar-dogs-crossing; non-zero lock_held even if low on distant/dusk
result: passed. Per-clip `cam_c` lock_held — handler_close 0.895, dusk_distant 0.764, sprint_blur 0.685, warm_jump 0.405, crowd_distractor 0.155, distant 0.035 (distant cam_r 0.404). UNVERIFIED lines emitted on every clip (D-02). Measures the previously-unmeasured COCO-dog recall (STATE blocker) — strong on close/clear subjects, degrades on distant/small + crowded scenes (the documented recall risk; candidate for dog-detector fine-tuning later).

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

1. **RESOLVED during UAT — tracker YAML not resolved (TRK-01/TRK-02 dead on the real path).**
   `PerCameraTracker` passed the bare name `"botsort_dog.yaml"` to `model.track(tracker=...)`; Ultralytics `check_yaml` does not search the repo `trackers/` dir, so every `.track()` raised `'botsort_dog.yaml' does not exist`, which the per-frame fail-safe silently degraded to coast → `predictor.trackers` never built, native ReID never engaged. CPU tests could not catch this (heavy edge is GPU-gated). Fixed by resolving `tracker_yaml` to an absolute path with fail-loud validation at construction (`src/segugio/tracking/detector.py`), plus a CPU regression suite (`tests/test_tracker_yaml_resolution.py`). Commit `fix(04): resolve tracker yaml to abs path`.

2. **Minor (open, tooling) — debug overlay renders only the first camera (cam_l).**
   `run_clip_eval` writes a single-camera overlay (cam_l, the SAFE cam at lock_held 0.221), so most overlay frames coast even though cam_c holds the lock 0.895. Visual review would be more useful rendering the best-lock camera or a 3-up composite. Not a correctness bug — metrics are computed per-camera correctly.
