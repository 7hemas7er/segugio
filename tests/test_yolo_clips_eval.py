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

Each runs a real committed SLICE via ``resolve_clip_path`` (NOT ``gara_full.mp4``, A5).
"""

from __future__ import annotations

import pytest

import segugio.fixtures as fx

# The committed disc-dog slice the gpu eval decodes (real 1920x1080 file; gitignored binary).
_CLIP = "disc_dog/handler_close_01.mp4"

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
