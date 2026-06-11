"""NDI-03 — empty/zero-resolution first frames are skipped (Wave-0 stub).

Behavior (filled by 05-02):
  - a zero-resolution (xres==0 or yres==0) frame is skipped, never reshaped/raised.
  - the FrameSource coasts (latest stays None) until a valid frame arrives.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-02 (NDI-03 empty-frame guard)", strict=False)
def test_zero_resolution_frame_skipped():
    raise AssertionError("not implemented")
