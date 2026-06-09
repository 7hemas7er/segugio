"""D-01 pseudo-camera plumbing — ClipFrameSource crop geometry (CPU-only, no YOLO).

cv2 IS installed in ``.venv``, so the crop/frame-source path is exercised CPU-only here (no
GPU, no ultralytics). These tests verify the D-01 spatial-crop geometry: a real committed
1080p slice is decoded, cropped into the overlapping L/C/R pseudo-cameras (the
``crop_geometry`` fixture), and the emitted ``(tick, {cam_id: crop})`` is asserted —
tick is an int starting at 0, the crops match the normalized rects × source resolution, and
the overlapping crops share pixels. No YOLO inference is involved.

Skip-on-absent-resource (the ``test_fixtures_catalogue`` precedent): if the slice binary is
not present locally (binaries are gitignored), resolving it raises ``FixtureNotPresentError``
→ the test SKIPS with a clear reason rather than failing.
"""

from __future__ import annotations

import numpy as np
import pytest

import segugio.fixtures as fx
from segugio.tracking.frame_source import ClipFrameSource

# The committed disc-dog slice this test decodes (real 1920x1080 file; gitignored binary).
_CLIP = "disc_dog/handler_close_01.mp4"


def _resolve_or_skip(file: str):
    """Resolve a committed slice or SKIP when its binary is absent (gitignored locally)."""
    try:
        return fx.resolve_clip_path(file)
    except fx.FixtureNotPresentError:
        pytest.skip(f"fixture not present locally: {file} (binaries are gitignored)")


def test_first_emitted_frame_has_expected_cams_and_geometry(crop_geometry) -> None:
    """The first emitted ``(tick, crops)`` has tick=0, the L/C/R cam_ids, numpy crops sized
    to the normalized rect × source resolution (within rounding)."""
    clip = _resolve_or_skip(_CLIP)
    src = ClipFrameSource(clip, crop_geometry, stride=2)

    gen = src.frames()
    tick, crops = next(gen)
    gen.close()

    # tick is an int starting at 0 (the emitted-frame index, no wall-clock).
    assert isinstance(tick, int)
    assert tick == 0

    # The crops dict carries exactly the configured pseudo-camera ids.
    assert set(crops) == set(crop_geometry)

    # Each crop is a numpy array; recover the source resolution from a full-width crop.
    # cam_l spans x[0.0,0.55] over the full height, so its height == source height H and its
    # width == round(0.55*W). Verify every crop's pixel size matches rect × (W, H).
    for cam_id, crop in crops.items():
        assert isinstance(crop, np.ndarray)
        assert crop.ndim == 3  # H x W x C (BGR)

    # Derive (W, H) from cam_l (full-height, 0.55-width window) then assert each crop.
    h_full = crops["cam_l"].shape[0]
    # cam_l width = round(0.55 * W) → recover W (allow ±1px rounding).
    cam_l_w = crops["cam_l"].shape[1]
    w_full = round(cam_l_w / 0.55)

    for cam_id, rect in crop_geometry.items():
        x0, y0, x1, y1 = rect
        exp_w = round(x1 * w_full) - round(x0 * w_full)
        exp_h = round(y1 * h_full) - round(y0 * h_full)
        got_h, got_w = crops[cam_id].shape[0], crops[cam_id].shape[1]
        assert abs(got_w - exp_w) <= 1, f"{cam_id} width {got_w} != expected {exp_w}"
        assert abs(got_h - exp_h) <= 1, f"{cam_id} height {got_h} != expected {exp_h}"


def test_overlapping_crops_share_pixels(crop_geometry) -> None:
    """The L and C windows OVERLAP (cam_l x[0,0.55] ∩ cam_c x[0.225,0.775] = [0.225,0.55]),
    so the shared pixel column is non-empty and identical content in both crops."""
    clip = _resolve_or_skip(_CLIP)
    src = ClipFrameSource(clip, crop_geometry, stride=2)
    gen = src.frames()
    _, crops = next(gen)
    gen.close()

    cam_l, cam_c = crops["cam_l"], crops["cam_c"]
    # Overlap is a real, non-empty pixel band.
    overlap_norm = 0.55 - 0.225
    assert overlap_norm > 0
    # Recover W and assert the overlap width is a positive number of shared pixels.
    w_full = round(cam_l.shape[1] / 0.55)
    overlap_px = round(overlap_norm * w_full)
    assert overlap_px > 0
    assert cam_l.shape[1] >= overlap_px and cam_c.shape[1] >= overlap_px

    # The rightmost ``overlap_px`` columns of cam_l equal the leftmost ``overlap_px`` of cam_c
    # (same source pixels, same instant) — proving genuine spatial overlap.
    left_band = cam_l[:, -overlap_px:, :]
    right_band = cam_c[:, :overlap_px, :]
    # Heights match (both full-height windows); compare the shared band content.
    n = min(left_band.shape[1], right_band.shape[1])
    assert np.array_equal(left_band[:, -n:, :], right_band[:, :n, :])


def test_stride_advances_tick_deterministically(crop_geometry) -> None:
    """``tick`` advances 0,1,2,... by EMITTED frame regardless of stride; two passes over the
    same clip with the same stride yield the same tick sequence (determinism)."""
    clip = _resolve_or_skip(_CLIP)

    def first_ticks(stride: int, n: int) -> list[int]:
        src = ClipFrameSource(clip, crop_geometry, stride=stride)
        ticks: list[int] = []
        gen = src.frames()
        for tick, _ in gen:
            ticks.append(tick)
            if len(ticks) >= n:
                break
        gen.close()
        return ticks

    seq_a = first_ticks(stride=2, n=4)
    seq_b = first_ticks(stride=2, n=4)
    assert seq_a == [0, 1, 2, 3]
    assert seq_a == seq_b  # same clip + stride → byte-identical tick sequence
