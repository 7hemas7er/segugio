"""RBT-01 — feed watchdog liveness on INJECTED timestamps (Wave-0 stub).

Behavior (filled by 05-04):
  - a stalled last-NEW-frame timestamp → feed declared dead after watchdog_timeout + grace.
  - liveness is PURE math on injected timestamps (never the NDI source "connected" state).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-04 (FeedWatchdog liveness)", strict=False)
def test_stalled_timestamp_marks_dead_after_timeout():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-04 (anti-jitter grace)", strict=False)
def test_advancing_timestamp_stays_alive():
    raise AssertionError("not implemented")
