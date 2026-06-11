"""NDI-03 — empty/zero-resolution frames are skipped by the clip-replay mock FrameSource.

Behavior (05-02 Task 1):
  - a zero-size / zero-resolution frame is skipped, never reshaped/raised.
  - the FrameSource coasts (``latest`` stays ``None``) until a valid frame arrives.
  - ``last_frame_ts`` advances ONLY on a genuinely NEW non-empty frame (RBT-01 substrate),
    never on a skipped blank.

Headless + deterministic: the mock is driven over an INJECTED frame generator (no cv2,
no real clip decode), so the empty-frame guard (mirrors ``frame_source.py:76-89``) is
proven on the light side of the lazy-import boundary.
"""

from __future__ import annotations

import numpy as np

from segugio.ndi.clip_source import ClipReplayFrameSource


def _blank() -> np.ndarray:
    """A zero-size frame — the NDI-03 / ``ClipFrameSource`` empty-frame case."""
    return np.empty((0, 0, 3), dtype=np.uint8)


def _real(value: int) -> np.ndarray:
    """A small non-empty BGR frame."""
    return np.full((4, 4, 3), value, dtype=np.uint8)


def test_zero_resolution_frame_skipped():
    """Blanks are skipped; the first real frame is what ``latest`` returns (NDI-03)."""
    real0 = _real(10)
    real1 = _real(20)
    # An injected source: tick -> {cam: frame}. Two blanks, then two real frames.
    sequence = [
        (0, {"cam_a": _blank()}),
        (1, {"cam_a": _blank()}),
        (2, {"cam_a": real0}),
        (3, {"cam_a": real1}),
    ]
    src = ClipReplayFrameSource(frames_iter=iter(sequence))
    src.start()

    # Pull 1: the first emitted frame is blank -> coast (no new frame), latest stays None.
    src.pump()
    assert src.latest("cam_a") is None
    assert src.last_frame_ts("cam_a") is None

    # Pull 2: still blank -> still coasting.
    src.pump()
    assert src.latest("cam_a") is None
    assert src.last_frame_ts("cam_a") is None

    # Pull 3: the first REAL frame -> latest returns it, last_frame_ts advances.
    src.pump()
    out = src.latest("cam_a")
    assert out is not None
    assert np.array_equal(out, real0)
    ts_after_first_real = src.last_frame_ts("cam_a")
    assert ts_after_first_real is not None

    # Pull 4: the second REAL frame -> latest updates, last_frame_ts advances again.
    src.pump()
    out2 = src.latest("cam_a")
    assert np.array_equal(out2, real1)
    assert src.last_frame_ts("cam_a") > ts_after_first_real

    src.stop()


def test_last_frame_ts_only_advances_on_new_frames():
    """``last_frame_ts`` advanced exactly twice (the two real frames), not on the blanks."""
    sequence = [
        (0, {"cam_a": _blank()}),
        (1, {"cam_a": _real(1)}),
        (2, {"cam_a": _blank()}),
        (3, {"cam_a": _real(2)}),
    ]
    src = ClipReplayFrameSource(frames_iter=iter(sequence))
    src.start()

    seen_ts: list[float] = []
    for _ in range(4):
        src.pump()
        ts = src.last_frame_ts("cam_a")
        if ts is not None and (not seen_ts or ts != seen_ts[-1]):
            seen_ts.append(ts)

    # Exactly two distinct advances — one per real frame, none for the blanks.
    assert len(seen_ts) == 2
    assert seen_ts[0] < seen_ts[1]
