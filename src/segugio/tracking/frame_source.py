"""D-01 heavy edge — decode a clip and crop it into overlapping pseudo-cameras.

The committed corpus is single-camera disc-dog (1080p slices). ``ClipFrameSource`` builds
"N cameras" by cropping each decoded frame into OVERLAPPING normalized windows (e.g. L/C/R)
— genuinely simultaneous different framings of the SAME dog at the SAME instant (D-01).
This gives real per-camera pixel isolation, a realistic multi-camera interface for Phase 5,
and — for free — frame-exit/re-entry (the dog leaves a crop and reappears), the exact case
``track_buffer:60`` + native ReID exist to survive. Some crops naturally won't contain the
dog (a realistic "this camera doesn't see it" case — accepted, D-01). No real parallax.

Determinism (clone of the ``detection_stream`` contract): ``tick`` is the EMITTED frame
index — NO wall-clock. The footage is 1080p50 but the AI tick is ~30Hz, so ``stride``
samples ~every 2nd frame; ``tick`` counts the EMITTED frames (0, 1, 2, ...) so it stays a
stable, reproducible index regardless of the source fps.

Live-robustness guard (RBT analogue, NDI-03 precursor): a failed ``cap.read()`` or a
zero-size frame is SKIPPED, never raised — a malformed/blank frame must not crash the loop.

Trust boundary (T-04-03-02): clip paths are resolved ONLY via
``segugio.fixtures.resolve_clip_path`` (the validated, traversal-safe committed-slice API)
— never a raw string into ``cv2.VideoCapture``. Use the committed SLICES, not the
``gara_full.mp4`` symlink (A5: it points at a Windows path likely absent on the CUDA box).

Lazy-import boundary: ``cv2`` is imported INSIDE ``frames()``, never at module top — this is
the FIRST module in the repo to lazy-import cv2, so ``import segugio.tracking.frame_source``
must succeed with cv2 absent (proven by ``tests/test_tracking_import_smoke.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only — no runtime cost, keeps numpy/cv2 off the import path
    import numpy as np

__all__ = ["ClipFrameSource"]


class ClipFrameSource:
    """Decode a clip and yield ``(tick, {cam_id: crop})`` for overlapping spatial crops.

    Each crop is a numpy slice of the decoded frame defined by a normalized
    ``[x0, y0, x1, y1]`` rect per ``cam_id`` (the ``crop_geometry`` fixture / config). The
    crop is the camera frame: ``Results.boxes.xywhn`` is normalized to the CROP, which is
    exactly what the per-camera zone-gate consumes.
    """

    def __init__(self, clip_path, crops: dict[str, list[float]], stride: int = 2) -> None:
        """Configure the source over one clip + a crop-rect mapping.

        Args:
            clip_path: absolute path to a clip binary (resolve it via
                ``segugio.fixtures.resolve_clip_path`` — do NOT pass a raw user string).
            crops: ``{cam_id: [x0, y0, x1, y1]}`` normalized [0,1] crop rects (overlapping
                L/C/R windows). Each ``cam_id`` becomes a pseudo-camera.
            stride: frame-sampling stride (default 2: sample ~every 2nd frame, mapping a
                ~50fps source toward the ~30Hz AI tick). ``tick`` counts EMITTED frames.
        """
        self.clip_path = str(clip_path)
        self.crops = dict(crops)
        self.stride = max(int(stride), 1)  # stride < 1 would be a no-advance loop — clamp

    def frames(self):
        """Generator: yield ``(tick, {cam_id: crop})`` per EMITTED frame.

        Opens the clip (lazy ``import cv2`` inside the method), reads frames applying
        ``stride``, and for each emitted frame slices every crop rect (normalized × frame
        H/W → pixel slice). ``tick`` is the emitted frame index (0, 1, 2, ...). A blank /
        zero-size frame is skipped (never raised). The capture is always released.

        Yields:
            ``(tick: int, {cam_id: numpy.ndarray})`` — one BGR crop per camera. Crops that
            slice to zero pixels for a degenerate rect are still included (the empty array is
            the honest "this camera saw nothing usable" signal → coast downstream).
        """
        import cv2  # lazy — heavy import INSIDE the generator (the cv2 boundary)

        cap = cv2.VideoCapture(self.clip_path)
        try:
            tick = 0  # EMITTED-frame index (determinism — no wall-clock)
            raw_index = 0  # decoded-frame counter (for the stride decimation)
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break  # end of stream (or unreadable) — stop cleanly
                # Skip a blank / zero-size frame, never crash (NDI-03 precursor).
                if getattr(frame, "size", 0) == 0:
                    raw_index += 1
                    continue
                # Stride decimation: only emit every ``stride``-th decoded frame.
                if raw_index % self.stride != 0:
                    raw_index += 1
                    continue
                raw_index += 1
                h, w = frame.shape[0], frame.shape[1]
                crops = {
                    cam_id: self._crop(frame, rect, w, h)
                    for cam_id, rect in self.crops.items()
                }
                yield tick, crops
                tick += 1
        finally:
            cap.release()

    @staticmethod
    def _crop(frame: "np.ndarray", rect: list[float], w: int, h: int) -> "np.ndarray":
        """Slice a normalized ``[x0, y0, x1, y1]`` rect out of a frame as a pixel crop.

        Pixel bounds are rounded from the normalized rect × frame W/H and clamped into the
        frame so a rect at the [0,1] edges never slices out of bounds.
        """
        x0, y0, x1, y1 = rect
        px0 = max(0, min(int(round(x0 * w)), w))
        px1 = max(0, min(int(round(x1 * w)), w))
        py0 = max(0, min(int(round(y0 * h)), h))
        py1 = max(0, min(int(round(y1 * h)), h))
        return frame[py0:py1, px0:px1]
