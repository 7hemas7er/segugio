"""``publish_clip`` — the NDI-02 mock Sender: publish curated clips as a named NDI source.

This is the real-NDI SIDE of D-05: a cyndilib ``Sender`` publishes recorded clip frames under
the config ``Camera.ndi_source`` name, so the real cyndilib RECEIVE path (``NdiFrameSource``)
is exercised end-to-end WITHOUT phones. Used ONLY by the on-Windows ``@pytest.mark.ndi`` E2E
run (NDI-02) — never the headless unit tests, which use the in-process clip-replay mock
(``clip_source.ClipReplayFrameSource``).

Lazy-import boundary: ``cv2`` and every ``cyndilib`` symbol are imported INSIDE
``publish_clip`` (mirrors ``ndi_source._receiver_loop`` and ``frame_source.frames()``), so
``import segugio.ndi.mock_sender`` succeeds with cyndilib/cv2 ABSENT.

[ASSUMED A2] The exact ``VideoSendFrame`` / ``FourCC`` import paths and the ``write_video_async``
signature follow the cyndilib docs example. They MUST be confirmed against the installed
``cyndilib==0.1.1`` on Windows — the 0.1.1 API may differ slightly. Because this path is
E2E-only (gated behind ``@pytest.mark.ndi``), the blast radius of an API mismatch is low.
"""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # type-only — keeps numpy off the runtime import path
    import numpy as np

__all__ = ["publish_clip"]


def publish_clip(
    source_name: str,
    bgr_frames: "Sequence[np.ndarray]",
    fps: int = 30,
) -> None:
    """Publish ``bgr_frames`` as a named NDI source ``source_name`` via a cyndilib Sender.

    Sets the send-frame resolution from the first frame, the frame rate to ``Fraction(fps, 1)``,
    fourcc BGRA, then writes each BGR frame (converted to BGRA) asynchronously inside the
    sender's context manager. Heavy imports live INSIDE this function (the lazy boundary).

    Args:
        source_name: the NDI source NAME the receiver resolves — the config ``Camera.ndi_source``
            value, so ``NdiFrameSource`` finds it by name.
        bgr_frames: a non-empty sequence of BGR ``numpy.ndarray`` frames (H, W, 3).
        fps: publish frame rate (default 30 — matches the ~30 Hz AI tick).

    Raises:
        ValueError: if ``bgr_frames`` is empty (no resolution to derive).

    [ASSUMED A2] ``VideoSendFrame`` / ``FourCC`` / ``write_video_async`` — confirm on
    ``cyndilib==0.1.1`` on Windows.
    """
    if len(bgr_frames) == 0:
        raise ValueError("publish_clip needs at least one frame to derive the resolution")

    import cv2
    from cyndilib.sender import Sender
    from cyndilib.video_frame import VideoSendFrame
    from cyndilib.wrapper.ndi_recv import FourCC

    sender = Sender(source_name)  # the config `ndi_source` name
    vf = VideoSendFrame()
    h, w = bgr_frames[0].shape[:2]
    vf.set_resolution(w, h)
    vf.set_frame_rate(Fraction(fps, 1))
    vf.set_fourcc(FourCC.BGRA)
    sender.set_video_frame(vf)
    with sender:
        for bgr in bgr_frames:
            bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
            sender.write_video_async(bgra)
