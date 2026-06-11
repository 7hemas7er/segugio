"""NDI-01 — real cyndilib receiver yields BGR frames + last-NEW-frame ts (Wave-0 stub).

Real-NDI integration path (Windows-only): requires libndi + a live named NDI source.
Marked @pytest.mark.ndi so it is excluded from the headless quick run; exercised only
on the on-Windows E2E run (05-02 / D-07).

Behavior (filled by 05-02):
  - the cyndilib Receiver/FrameSync path yields numpy BGR frames.
  - last_frame_ts advances only on a NEW frame (RBT-01 liveness substrate).
"""

from __future__ import annotations

import pytest


@pytest.mark.ndi
@pytest.mark.xfail(reason="impl pending 05-02 (NDI-01 real cyndilib receiver)", strict=False)
def test_receiver_yields_bgr_and_new_frame_ts():
    raise AssertionError("not implemented")
