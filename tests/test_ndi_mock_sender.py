"""NDI-02 — mock Sender publishes a named source the real receiver consumes end-to-end.

Real-NDI integration path (Windows-only): requires libndi + cyndilib Sender + Receiver.
Marked ``@pytest.mark.ndi`` so it is excluded from the headless quick run; exercised only on
the on-Windows E2E run (05-02 / D-07). This closes the no-phones loop: ``publish_clip`` puts a
curated clip on the network as a named NDI source, and ``NdiFrameSource`` receives it.

Behavior (05-02 Task 3):
  - ``publish_clip(source_name, bgr_frames)`` publishes recorded frames as a named NDI source.
  - an ``NdiFrameSource`` bound to that name receives a BGR frame (the receive path is real).
"""

from __future__ import annotations

import threading
import time

import pytest


@pytest.mark.ndi
def test_mock_sender_publishes_named_source():
    """The mock Sender's named source is consumable by the real receiver (NDI-02 E2E)."""
    import numpy as np

    from segugio.ndi import publish_clip  # re-exported at the package top (stays light)
    from segugio.ndi.ndi_source import NdiFrameSource

    source_name = "SEGUGIO-SENDER-TEST (NDI)"
    frames = [np.full((96, 128, 3), v, dtype=np.uint8) for v in (40, 120, 200)]

    stop = threading.Event()

    def _send() -> None:
        while not stop.is_set():
            publish_clip(source_name, frames, fps=30)

    sender = threading.Thread(target=_send, name="ndi-sender-test", daemon=True)
    sender.start()

    class _Cam:
        id = "cam_e2e"
        ndi_source = source_name

    src = NdiFrameSource([_Cam()])
    src.start()
    try:
        deadline = time.monotonic() + 15.0
        frame = None
        while time.monotonic() < deadline:
            frame = src.latest("cam_e2e")
            if frame is not None:
                break
            time.sleep(0.05)
        assert frame is not None, "receiver did not consume the mock Sender's named source"
        assert frame.ndim == 3 and frame.shape[2] == 3, "received frame must be BGR (H, W, 3)"
    finally:
        stop.set()
        src.stop()
        sender.join(timeout=2.0)
