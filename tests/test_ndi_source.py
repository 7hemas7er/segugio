"""NDI-01 — real cyndilib receiver yields BGR frames + advancing last-NEW-frame ts.

Real-NDI integration path (Windows-only): requires libndi + cyndilib + a LIVE named NDI
source on the network. Marked ``@pytest.mark.ndi`` so it is excluded from the headless quick
run; exercised only on the on-Windows E2E run (05-02 / D-07). The companion mock Sender
(``test_ndi_mock_sender.py``) publishes the named source this test consumes.

Behavior (05-02 Task 2):
  - the cyndilib Receiver/VideoFrameSync path yields numpy BGR frames (H, W, 3).
  - ``last_frame_ts`` advances only on a NEW frame (RBT-01 liveness substrate).
"""

from __future__ import annotations

import time

import pytest


@pytest.mark.ndi
def test_receiver_yields_bgr_and_new_frame_ts():
    """A live named source → BGR frame + an advancing last-NEW-frame timestamp (NDI-01)."""
    import threading

    import numpy as np

    from segugio.ndi.clip_source import ClipReplayFrameSource  # noqa: F401  (parity import)
    from segugio.ndi.mock_sender import publish_clip
    from segugio.ndi.ndi_source import NdiFrameSource

    source_name = "SEGUGIO-TEST (NDI)"

    # A tiny synthetic clip: distinct frames so consecutive timestamps differ.
    frames = [np.full((120, 160, 3), v, dtype=np.uint8) for v in (30, 90, 150, 210)]

    # Publish the clip as a named NDI source on a background thread (loops a few times).
    stop = threading.Event()

    def _send() -> None:
        while not stop.is_set():
            publish_clip(source_name, frames, fps=30)

    sender = threading.Thread(target=_send, name="ndi-test-sender", daemon=True)
    sender.start()

    # Build a one-camera receiver bound to the published source.
    class _Cam:
        id = "cam_test"
        ndi_source = source_name

    src = NdiFrameSource([_Cam()])
    src.start()
    try:
        # Poll for the first real frame (give the Finder/Receiver time to resolve + connect).
        deadline = time.monotonic() + 15.0
        first = None
        while time.monotonic() < deadline:
            first = src.latest("cam_test")
            if first is not None:
                break
            time.sleep(0.05)
        assert first is not None, "no frame received from the named NDI source within 15s"
        assert first.ndim == 3 and first.shape[2] == 3, "frame must be BGR (H, W, 3)"

        ts0 = src.last_frame_ts("cam_test")
        assert ts0 is not None

        # Wait for the timestamp to ADVANCE on a NEW frame (RBT-01).
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            ts1 = src.last_frame_ts("cam_test")
            if ts1 is not None and ts1 != ts0:
                break
            time.sleep(0.05)
        else:
            pytest.fail("last_frame_ts did not advance on a NEW frame")
    finally:
        stop.set()
        src.stop()
        sender.join(timeout=2.0)
