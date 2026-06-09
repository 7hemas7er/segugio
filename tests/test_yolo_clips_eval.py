"""@pytest.mark.gpu real-YOLO-on-clips eval skeleton (D-09 GPU-gated half).

These tests run ONLY on a CUDA box with ``ultralytics`` / ``torch`` installed and the
``yolo26s.pt`` weights resolvable — the ``conftest_tracking`` gpu gate SKIPs them everywhere
else (including this CPU ``.venv`` and normal CI), so they are SKIPPED, not failed, here.

This plan (04-03) ships the two load-bearing GPU checks; 04-04 wires the overlay+metrics
eval (ID-switch count, %lock-held, coast/uncertain, per-clip recall) on top.

  * ``test_native_reid_engaged`` — the HARD TRK-02 gate. Instantiate a ``PerCameraTracker``,
    run ONE warmup ``.track()`` (end2end=False) on a real crop, then
    ``assert_native_reid_engaged`` — it RAISES on the silent ``yolo26n-cls.pt`` fallback.
    This is the ONE gpu test that is a true pass/fail (a correctness invariant), not a metric.
  * ``test_per_camera_isolation`` — TRK-01. TWO ``PerCameraTracker`` instances over two
    DIFFERENT crops (one per cam_id) keep INDEPENDENT tracker state — never a frame list to
    one tracker (#13107).
  * ``test_overlay_and_metrics`` — the D-08 end-to-end eval (04-04). ``run_clip_eval`` wires
    the full TRK-01..05 pipeline on a hard slice, writes a debug-overlay ``.mp4``, returns the
    per-camera D-08 metrics dict, and emits the explicit ``UNVERIFIED:`` lines (D-02). Asserts
    the overlay file exists+non-empty, the metrics carry the D-08 keys, and the UNVERIFIED
    lines were logged. The overlay's VISUAL correctness is a Manual-Only verification (open the
    rendered clip on the CUDA box — 04-VALIDATION.md).

Each runs a real committed SLICE via ``resolve_clip_path`` (NOT ``gara_full.mp4``, A5).
"""

from __future__ import annotations

import pytest

import segugio.fixtures as fx

# The committed disc-dog slice the gpu eval decodes (real 1920x1080 file; gitignored binary).
_CLIP = "disc_dog/handler_close_01.mp4"
# A second hard slice (crowd distractor — competitor-lock vs bystander) the D-08 eval also runs.
_CLIP_2 = "disc_dog/crowd_distractor_01.mp4"

# Default YOLO weights for the eval (matches ModelConfig.path / CFG-04).
_MODEL_PATH = "yolo26s.pt"
_TRACKER_YAML = "botsort_dog.yaml"


def _resolve_or_skip(file: str):
    """Resolve a committed slice or SKIP when its binary is absent (gitignored locally)."""
    try:
        return fx.resolve_clip_path(file)
    except fx.FixtureNotPresentError:
        pytest.skip(f"fixture not present locally: {file} (binaries are gitignored)")


def _first_crops(clip, crop_geometry):
    """Decode the first emitted ``{cam_id: crop}`` from the clip (helper for the gpu tests)."""
    from segugio.tracking.frame_source import ClipFrameSource

    src = ClipFrameSource(clip, crop_geometry, stride=2)
    gen = src.frames()
    _, crops = next(gen)
    gen.close()
    return crops


@pytest.mark.gpu
def test_native_reid_engaged(crop_geometry) -> None:
    """TRK-02 HARD gate: native-feature ReID engages with end2end=False (no cls fallback)."""
    from segugio.tracking.detector import PerCameraTracker, resolve_dog_index
    from segugio.tracking.reid_check import assert_native_reid_engaged

    clip = _resolve_or_skip(_CLIP)
    crops = _first_crops(clip, crop_geometry)
    cam_id = next(iter(crop_geometry))
    frame = crops[cam_id]

    tracker = PerCameraTracker(_MODEL_PATH, dog_idx=16, tracker_yaml=_TRACKER_YAML)
    # Reconcile the dog index BY NAME against the loaded model (CFG-04), then warmup.
    tracker.dog_idx = resolve_dog_index(tracker.model, configured_index=16)
    tracker.track(frame)  # ONE warmup so predictor.trackers exists

    # RAISES on the silent yolo26n-cls.pt fallback; logs on success.
    assert_native_reid_engaged(tracker.model)


@pytest.mark.gpu
def test_per_camera_isolation(crop_geometry) -> None:
    """TRK-01: two PerCameraTracker instances over two crops keep independent tracker state.

    NEVER a frame list to one tracker (#13107). After tracking each cam's own crop, each
    tracker owns its OWN ``predictor.trackers`` object (distinct instances, not shared).
    """
    from segugio.tracking.detector import PerCameraTracker, resolve_dog_index

    clip = _resolve_or_skip(_CLIP)
    crops = _first_crops(clip, crop_geometry)
    cam_ids = list(crop_geometry)[:2]
    assert len(cam_ids) == 2, "need at least two pseudo-cameras for the isolation test"

    trackers = {}
    for cam_id in cam_ids:
        t = PerCameraTracker(_MODEL_PATH, dog_idx=16, tracker_yaml=_TRACKER_YAML)
        t.dog_idx = resolve_dog_index(t.model, configured_index=16)
        t.track(crops[cam_id])  # each cam tracks ONLY its own crop (one tracker per cam)
        trackers[cam_id] = t

    a, b = (trackers[cam_ids[0]], trackers[cam_ids[1]])
    # Distinct YOLO objects → distinct predictor state → independent track-id spaces.
    assert a.model is not b.model
    assert a.model.predictor is not b.model.predictor
    assert a.model.predictor.trackers is not b.model.predictor.trackers


def _cameras_for(crop_geometry):
    """Build one ``Camera`` per ``crop_geometry`` cam_id (a centered field zone for the gate).

    The crop geometry supplies the per-camera crop RECTS; the ``Camera`` supplies the per-camera
    field ZONES the competitor-lock gate + the overlay consume. A single centered zone is a
    reasonable field gate for the eval (the real config zones land in Phase 5 wiring).
    """
    from segugio.config import Role
    from segugio.config.models import Camera, Zone

    return [
        Camera(
            id=cam_id,
            role=Role.main_wide,
            obs_scene=cam_id.upper(),
            is_safe=(i == 0),
            zones=[Zone(name="field", rect=[0.2, 0.2, 0.8, 0.8])],
        )
        for i, cam_id in enumerate(crop_geometry)
    ]


@pytest.mark.gpu
def test_overlay_and_metrics(crop_geometry, tracking_params, tmp_path) -> None:
    """D-08 end-to-end: run_clip_eval writes an overlay .mp4, returns metrics, logs UNVERIFIED.

    Runs the full TRK-01..05 pipeline (decode→crop→track→map→lock→gate→signal+metrics) on a
    hard disc-dog slice. Asserts:
      * the overlay ``.mp4`` exists and is non-empty (the debug video was rendered);
      * the per-camera metrics dict carries every D-08 key;
      * the explicit ``UNVERIFIED:`` lines were emitted (D-02 — captured via a loguru sink,
        since loguru does NOT propagate to pytest's ``caplog`` by default).
    The overlay's visual correctness is a Manual-Only verification (open it on the CUDA box).
    """
    from loguru import logger

    from segugio.config.models import ModelConfig
    from segugio.tracking.eval import run_clip_eval

    clip = _resolve_or_skip(_CLIP)
    cameras = _cameras_for(crop_geometry)
    out_video = tmp_path / "overlay_handler_close_01.mp4"
    model_cfg = ModelConfig(path=_MODEL_PATH, class_index=16)

    # Capture loguru output (loguru ≠ stdlib logging → caplog won't see it without a sink).
    captured: list[str] = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="WARNING")
    try:
        metrics = run_clip_eval(
            clip, cameras, crop_geometry, model_cfg, tracking_params, out_video
        )
    finally:
        logger.remove(sink_id)

    # 1. The overlay video was written and is non-empty.
    assert out_video.exists(), "run_clip_eval did not write the overlay .mp4"
    assert out_video.stat().st_size > 0, "overlay .mp4 is empty"

    # 2. The per-camera metrics dict carries the D-08 keys.
    assert set(metrics) == set(crop_geometry), "one metrics entry per camera expected"
    d08_keys = {"id_switch_count", "lock_held_fraction", "coast_count", "n_ticks", "signal_dump"}
    for cam_id, m in metrics.items():
        assert d08_keys.issubset(m), f"{cam_id} metrics missing D-08 keys: {d08_keys - set(m)}"

    # 3. The explicit UNVERIFIED lines were emitted (D-02 — never a silent pass).
    joined = "\n".join(captured)
    assert "UNVERIFIED: agility-tunnel-occlusion" in joined
    assert "UNVERIFIED: two-similar-dogs-crossing" in joined
