"""RBT-02 — feed-death fallback + guarded rejoin (Wave-0 stub).

Behavior (filled by 05-04):
  - feed-death → alive[cam]=False → FSM excludes it → SAFE / other-live cam.
  - rejoin only after the feed is alive AND full hysteresis + min_dwell qualification.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-04 (RBT-02 feed-death fallback)", strict=False)
def test_feed_death_falls_back_to_safe_or_live():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-04 (RBT-02 guarded rejoin)", strict=False)
def test_rejoin_only_after_qualification():
    raise AssertionError("not implemented")
