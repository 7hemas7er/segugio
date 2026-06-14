---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
plan: 04
subsystem: tracking
tags: [trk-01, trk-02, trk-03, trk-04, trk-05, d-08, eval, overlay, metrics, gpu-gated, lazy-import, unverified]

# Dependency graph
requires:
  - phase: 04-yolo-per-camera-tracking-on-recorded-clips
    plan: 01
    provides: "signals_from_boxes (TRK-03 mapper) + TrackingParams + crop_geometry/tracking_params fixtures + gpu marker + multi_track_stream substrate"
  - phase: 04-yolo-per-camera-tracking-on-recorded-clips
    plan: 02
    provides: "CompetitorLock.select (TRK-04 sticky lock) + PlausibilityGate.check/.reset (TRK-05 inter-frame gate) — the pure brain the eval drives"
  - phase: 04-yolo-per-camera-tracking-on-recorded-clips
    plan: 03
    provides: "PerCameraTracker.track + resolve_dog_index + assert_native_reid_engaged (HARD TRK-02 gate) + ClipFrameSource.frames + botsort_dog.yaml + gpu autouse-skip + gpu eval skeleton"
  - phase: 02-framing-scorer-pure-substrate
    provides: "frozen DetectionSignal record + MultiCamScorer.update consumer shape (scorer.py:230-277) the eval output fits"
provides:
  - "compute_metrics (D-08) — PURE deterministic metric counters over a list[DetectionSignal | None] stream: id_switch_count, lock_held_fraction, coast_count, n_ticks, signal_dump; clock-free, RNG-free, cv2-free; re-exported on segugio.tracking"
  - "render_overlay (D-08) — heavy-edge cv2-in-function overlay: boxes + track-id labels + locked-subject highlight + per-camera zone rects -> annotated frame for a VideoWriter"
  - "run_clip_eval — the clip eval driver wiring the full TRK-01..05 pipeline (ClipFrameSource -> PerCameraTracker -> signals_from_boxes -> CompetitorLock -> PlausibilityGate -> per-camera DetectionSignal|None + compute_metrics), the MultiCamScorer.update consumer shape; HARD native-ReID gate before the loop; per-frame coast fail-safe; per-clip metric + UNVERIFIED logging"
  - "log_unverified_cases (D-02) — explicit UNVERIFIED loguru lines for agility-tunnel-occlusion + two-similar-dogs-crossing (never a silent pass)"
  - "test_overlay_and_metrics (@pytest.mark.gpu) — the D-08 end-to-end eval extending the 04-03 skeleton; SKIPs here, runs on the CUDA box"
affects: [05-integration-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PURE/HEAVY split inside one module along the lazy-import boundary: compute_metrics (counters) at the top with no cv2/heavy import; render_overlay/run_clip_eval lower with cv2 imported INSIDE each function (clone of frame_source.py) — module top stays cv2-free so import survives cv2/ultralytics/torch absent; the purity source-grep excludes eval.py from the cv2 ban for its render functions"
    - "the eval driver mirrors the Phase-2 MultiCamScorer per-camera fan-out (scorer.py:230-277): one PerCameraTracker + one CompetitorLock + one PlausibilityGate per cam_id (#13107, D-05); per (tick, crops): track -> _arrays_from_results -> signals_from_boxes -> select -> check -> per-camera DetectionSignal|None stream"
    - "HARD native-ReID gate (assert_native_reid_engaged) called ONCE, after the first crop warmup .track(), BEFORE the real processing loop (reid_checked flag) — the one true pass/fail; everything else (metrics, recall proxy) is recorded, not gated (D-02/D-08)"
    - "metrics: coast (None) ticks do NOT reset the prev-id comparison so an ID switch ACROSS a blur gap still counts (catches a silent BoT-SORT ID swap that surfaces after the dog re-appears); empty-stream divisor guard -> lock_held_fraction 0.0"
    - "loguru capture in tests via logger.add(sink) (loguru does NOT propagate to pytest caplog) — the gpu test installs a temporary WARNING sink to assert the UNVERIFIED lines"

key-files:
  created:
    - src/segugio/tracking/eval.py
    - tests/test_tracking_metrics.py
  modified:
    - src/segugio/tracking/__init__.py
    - tests/test_yolo_clips_eval.py

key-decisions:
  - "compute_metrics counts ALL Nones as coast_count (no uncertain/genuine-miss split): the DetectionSignal|None stream carries no tag distinguishing a gate-rejected uncertain None from a genuine-miss None, so the documented choice is total Nones = coast (a parallel uncertain counter would require the stream to carry the distinction). Documented in the docstring + the test module."
  - "id_switch_count compares consecutive NON-None track_ids and does NOT reset on a coast gap — id 1 -> coast -> id 2 is ONE switch. This is the load-bearing semantic: a silent BoT-SORT ID swap that surfaces only after a blur/re-entry IS the failure D-08 must catch, so the gap must not hide it."
  - "run_clip_eval takes an explicit `crops` mapping ({cam_id: [x0,y0,x1,y1]}) rather than reading cam.crop_rect — the Camera model has no crop_rect field (crop geometry is the separate crop_geometry fixture/config; the Camera supplies the field zones). The signature separates zone gate (Camera.zones) from crop geometry (crops)."
  - "render_overlay annotates a COPY of the frame (never mutates the caller's crop) and is called only for the first camera's crop (the single eyeball-able review feed) — one overlay .mp4 per clip, the human-review artifact D-08 calls for."
  - "the native-ReID gate runs per camera's first frame inside the loop (guarded by reid_checked, flipped true after the first full tick) so each PerCameraTracker's predictor exists before its gate call — the gate cannot run before .track() created predictor.trackers."

patterns-established:
  - "Pattern: a heavy-edge module can host PURE unit-testable counters at its top (above the lazy-import boundary) and lazy heavy render/driver below — one file, two import tiers, proven by a cv2-absent import smoke + a pure metric suite. The purity source-grep's fixed _PURE_MODULE_NAMES tuple keeps eval.py out of the cv2 ban automatically."
  - "Pattern: the offline eval driver is the FIRST place the 04-01/02/03 pieces compose end-to-end into the exact MultiCamScorer.update consumer shape (one DetectionSignal|None per camera per tick) — the seam Phase 5 wiring inherits."

requirements-completed: [TRK-01, TRK-02, TRK-03, TRK-04, TRK-05]

# Metrics
duration: 6min
completed: 2026-06-09
---

# Phase 4 Plan 04: Offline Clip Eval (D-08) Summary

**The phase's human-judged deliverable: a PURE/HEAVY-split `eval.py` whose deterministic metric counters (`compute_metrics` — locked-subject ID-switch count, %lock-held, coast count, signal dump) are unit-tested CPU-only, and whose heavy clip driver (`run_clip_eval`) wires the full TRK-01..05 pipeline — `ClipFrameSource` → `PerCameraTracker` → `signals_from_boxes` → `CompetitorLock` → `PlausibilityGate` → per-camera `DetectionSignal | None` (the exact `MultiCamScorer.update` consumer shape) — renders the debug-overlay video, asserts native ReID at startup (the HARD TRK-02 gate), logs per-clip metrics, and emits explicit `UNVERIFIED:` lines for the corpus-absent cases. The gpu eval SKIPs here and runs on the CUDA box.**

## Performance

- **Duration:** ~6 min (task-execution span)
- **Tasks:** 2 (Task 1 TDD: RED → GREEN; Task 2 auto)
- **Files modified:** 4 (2 created, 2 modified)
- **Tests:** +12 pure metric tests + 1 gpu overlay/metrics test; suite 195→208 passed, 2→3 skipped, zero regressions

## Accomplishments

- **`compute_metrics` (D-08, PURE)** — deterministic integer/float counters over a `list[DetectionSignal | None]` stream: `id_switch_count` (changes between consecutive non-None locked track_ids — a switch ACROSS a coast gap still counts, the silent-ID-swap catcher), `lock_held_fraction` ((non-None)/max(n,1), empty-stream divisor-guarded to 0.0), `coast_count` (None ticks), `n_ticks`, and `signal_dump` (per-tick `(tick_index, track_id-or-None)` for the regression net). Clock-free, RNG-free, cv2-free; re-exported on `segugio.tracking`. 12 pure tests cover all five must-have behaviors + edge cases (constant id, all-None, all-present, empty, multi-track-substrate determinism).
- **`render_overlay` (D-08, heavy edge)** — lazy `cv2` annotates a COPY of the crop: each detection box (normalized → pixels), its `track_id` label, the LOCKED subject in green+thick vs others yellow+thin, and the per-camera zone rects in gray. The eyeball-able "this is the in-competition dog" feed for the human review D-08 ultimately rests on.
- **`run_clip_eval` (the driver)** — mirrors the Phase-2 `MultiCamScorer` per-camera fan-out (`scorer.py:230-277`): one `PerCameraTracker` + one `CompetitorLock` + one `PlausibilityGate` per `cam_id` (never a frame list — #13107; per-camera independence — D-05). Per `(tick, crops)` from `ClipFrameSource.frames()` it runs, per camera, `track()` → `_arrays_from_results` → `signals_from_boxes` → `CompetitorLock.select` → (`reset()` on genuine loss) → `PlausibilityGate.check` → the per-camera `DetectionSignal | None`, accumulating the stream and writing the first camera's annotated frame to a `cv2.VideoWriter`. At the end it calls the PURE `compute_metrics` per camera, logs the per-clip metrics + a detection-presence recall proxy (recorded, not a gate — Q2/D-02), and emits the `UNVERIFIED:` lines. The HARD `assert_native_reid_engaged` (TRK-02) runs ONCE after a warmup `.track()` and BEFORE the real processing — the one true pass/fail; it RAISES on the silent `yolo26n-cls.pt` fallback. Per-frame fail-safe: a decode/inference error degrades that frame to no-detection (coast), the driver never crashes (T-04-04-01).
- **`log_unverified_cases` (D-02)** — explicit `logger.warning("UNVERIFIED: agility-tunnel-occlusion — no corpus footage")` + `... two-similar-dogs-crossing swap ...`. The select→gate logic for these is exercised by the 04-02 synthetic crossing/teleport tests, but the committed disc-dog corpus has neither clip, so the gap is RECORDED loudly, never a silent pass (T-04-04-03).
- **`test_overlay_and_metrics` (@pytest.mark.gpu)** — extends the 04-03 skeleton (keeps `test_native_reid_engaged` + `test_per_camera_isolation`): runs `run_clip_eval` on `handler_close_01`, asserts the overlay `.mp4` exists and is non-empty, the per-camera metrics dict carries all five D-08 keys, and the UNVERIFIED lines were emitted (captured via a temporary loguru sink, since loguru does not propagate to `caplog`). SKIPs here (torch/ultralytics absent, the 04-03 gpu autouse-skip), runs on the CUDA box.
- **Lazy-import boundary holds** — `eval.py` module top is cv2/heavy-free (the split: counters above, lazy render/driver below). `import segugio.tracking.eval` AND `from segugio.tracking import compute_metrics` both succeed with `cv2`/`ultralytics`/`torch` forced absent. The purity source-grep (`test_tracking_import_smoke._PURE_MODULE_NAMES`) deliberately excludes `eval.py`, so its in-function cv2 import is allowed while the module top stays clean.

## Task Commits

1. **Task 1 (RED): failing D-08 pure metric-counter suite** — `3ce1f0a` (test)
2. **Task 1 (GREEN): PURE compute_metrics + tracking surface re-export** — `28a4ebd` (feat)
3. **Task 2: heavy-edge overlay render + clip eval driver + D-08 gpu eval** — `f8a78f2` (feat)

_Task 1 is TDD (test RED → feat GREEN). No refactor commit — the GREEN implementation was clean as written. Task 2 is a single `auto` feat (render + driver + gpu test together — the heavy edge is one cohesive unit)._

## Files Created/Modified

- `src/segugio/tracking/eval.py` — **created.** PURE `compute_metrics` (D-08 counters) at the top above the lazy-import boundary; heavy `render_overlay` (cv2 in-function) + `run_clip_eval` (the TRK-01..05 driver) + `log_unverified_cases` + `_arrays_from_results` helper below. Module docstring names D-08, the pure/heavy split, and the cv2 boundary.
- `tests/test_tracking_metrics.py` — **created.** 12 pure metric tests (ID-switch ×4, %lock-held ×4, coast ×2, determinism on the multi_track_stream substrate, signal dump ×2).
- `src/segugio/tracking/__init__.py` — **modified.** Re-export `compute_metrics` (light + pure); docstring clarified that `eval`'s pure counter IS re-exported while its heavy overlay/driver are not.
- `tests/test_yolo_clips_eval.py` — **modified (extended, not rewritten).** Added `test_overlay_and_metrics` (@pytest.mark.gpu) + `_cameras_for` helper + the second hard slice constant; kept the two 04-03 skeleton tests intact.

## Decisions Made

- **All Nones counted as `coast_count` (no uncertain split):** the `DetectionSignal | None` stream carries no tag separating a gate-rejected "uncertain" None from a genuine-miss None, so the documented choice is total Nones = coast (the action's "otherwise count total Nones as coast"). A parallel uncertain counter would require the stream to carry the distinction — out of scope for this stream shape.
- **ID switch counts across a coast gap (does not reset on None):** id 1 → coast → id 2 is ONE switch. This is deliberate — a silent BoT-SORT ID swap that only surfaces after a blur/re-entry is exactly the failure the metric must catch, so the gap must not hide it.
- **`run_clip_eval(clip_path, cameras, crops, model_cfg, params, out_video_path)`:** added an explicit `crops` mapping parameter because the `Camera` model has no `crop_rect` field — crop geometry is the separate `crop_geometry` fixture/config, while `Camera.zones` is the field gate. The signature cleanly separates the two (zones → lock gate + overlay; crops → `ClipFrameSource` windows).
- **One overlay per clip (first camera's crop):** `render_overlay` is called only for `cams[0]`'s crop and annotates a copy — one human-review `.mp4` per clip, the artifact D-08 calls for, without mutating the decoded frame.
- **Native-ReID gate inside the loop, guarded by `reid_checked`:** the gate must run after `.track()` created `predictor.trackers`, so it fires on each camera's first frame (the flag flips true after the first full tick) — before any real per-camera selection is acted on.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] driver referenced a nonexistent `Camera.crop_rect` attribute**
- **Found during:** Task 2 (writing `run_clip_eval`'s `ClipFrameSource` construction).
- **Issue:** The first draft built the crop map as `{cam.id: cam.crop_rect for cam in cams}`, but the Phase-1 `Camera` model (`config/models.py:70-79`) has NO `crop_rect` field — crop geometry lives in the separate `crop_geometry` fixture / config mapping, while `Camera` carries only the field `zones`. As written, `run_clip_eval` would have raised `AttributeError` on the first camera.
- **Fix:** Added an explicit `crops: {cam_id: [x0,y0,x1,y1]}` parameter to `run_clip_eval` (placed after `cameras`), built the crop map from it, and documented the zones-vs-crops separation. The gpu test passes `crop_geometry` as that argument.
- **Files modified:** `src/segugio/tracking/eval.py` (signature + body + docstring), `tests/test_yolo_clips_eval.py` (call site).
- **Verification:** `import segugio.tracking.eval` clean with heavy deps absent; the gpu test composes the driver with `crop_geometry` and SKIPs cleanly here (no `AttributeError` at collection or in the body's static shape).
- **Committed in:** `f8a78f2` (Task 2 commit).

**Total deviations:** 1 auto-fixed (1 Rule-1 bug — a wrong-attribute assumption corrected into a cleaner explicit signature; no scope change, all D-08 artifacts ship as specified).

## Issues Encountered

None beyond the deviation above. One TEST expectation bug was caught and fixed during Task 1 GREEN (the `signal_dump` test asserted `(3, None)` where the implementation correctly records `(3, 2)` — the locked id IS present at that tick; the test, not the implementation, was wrong). Baseline suite was green (195 passed, 2 skipped) before and is green (208 passed, 3 skipped) after — every new CPU test is additive, the gpu test skips by design, zero Phase 1-4 / 04-01/02/03 regression.

## Known Stubs

None. `compute_metrics`, `render_overlay`, `run_clip_eval`, and `log_unverified_cases` are complete implementations (no TODO/FIXME). The recall measurement is a detection-presence PROXY (lock_held_fraction), logged-not-gated per Q2/D-02 — a true per-clip detection-vs-ground-truth recall would require labeled clip annotations the corpus does not carry, which is explicitly out of Phase-4 scope (D-02: calibration/recall is recorded for the deferred custom-model decision, not a gate). `test_overlay_and_metrics` is the GPU eval the plan output spec calls for — a complete runnable test that exercises the real driver against a committed slice; it SKIPs on this CPU box by design (D-09) and runs for real once `.[heavy]` + CUDA are present.

## Threat Surface Scan

No new security-relevant surface beyond the plan's `<threat_model>`. All four registered mitigations are honored in `run_clip_eval`: per-frame coast fail-safe (T-04-04-01, the try/except in `PerCameraTracker.track` + `_arrays_from_results` None-degradation), the HARD native-ReID gate before the loop (T-04-04-02), the explicit UNVERIFIED lines (T-04-04-03), and the driver-controlled `out_video_path` (T-04-04-04 — the test writes under pytest `tmp_path`, never a raw user string). No new install (T-04-04-SC: all deps pre-pinned).

## Authentication Gates

None — all CPU deliverables are heavy-deps-absent. To RUN the gpu eval (CUDA box): `pip install -e ".[heavy]"` + a CUDA torch build; `assert_native_reid_engaged` is the hard gate on the first GPU run.

## Next Phase Readiness

- **Phase 4 is CLOSED.** TRK-01..05 are all mechanized: TRK-03 mapper (04-01), TRK-04/05 brain (04-02), TRK-01/02 heavy edge (04-03), and now (04-04) the D-08 offline eval that COMPOSES them end-to-end into the per-camera `DetectionSignal | None` stream — the exact `MultiCamScorer.update` consumer shape Phase 5 wiring inherits.
- **Phase 5 (integration orchestrator)** inherits the `run_clip_eval` fan-out as the template for the live per-camera loop (one tracker/lock/gate per cam_id → `DetectionSignal | None` → scorer → FSM → OBS). The gpu eval + overlay are the regression/eyeball net to re-run on the deploy box as wiring lands.
- **Open Phase-4 concern (STATE.md):** native-ReID engagement on `yolo26s` + COCO-dog recall on real footage are now FULLY mechanized — `assert_native_reid_engaged` (04-03) is the runnable hard gate, and `run_clip_eval` logs the recall proxy + overlay for the human/CUDA-box judgement. They execute on the first GPU run; if the gate RAISES, escalate per Open Question Q1 (ByteTrack/YOLO11 fallback).
- No blockers.

## Self-Check: PASSED

All created files exist and all three task commits are present (verified in the self-check step below).

---
*Phase: 04-yolo-per-camera-tracking-on-recorded-clips*
*Completed: 2026-06-09*
