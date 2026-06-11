"""NDI-02 — mock Sender publishes a named source consumable by the receiver (Wave-0 stub).

Real-NDI integration path (Windows-only): requires libndi + cyndilib Sender.
Marked @pytest.mark.ndi so it is excluded from the headless quick run; exercised only
on the on-Windows E2E run (05-02 / D-07).

Behavior (filled by 05-02):
  - a cyndilib Sender publishes recorded clip frames as a named NDI source.
  - the receiver consumes that named source end-to-end (no phones).
"""

from __future__ import annotations

import pytest


@pytest.mark.ndi
@pytest.mark.xfail(reason="impl pending 05-02 (NDI-02 mock named-source Sender)", strict=False)
def test_mock_sender_publishes_named_source():
    raise AssertionError("not implemented")
