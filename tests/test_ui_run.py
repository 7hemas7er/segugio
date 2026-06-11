"""SCR-03 — run start/stop writes runstate; START flags lock-reset, STOP flags SAFE-park (Wave-0 stub).

Behavior (filled by 05-05):
  - POST /run start → runstate with the just_started/lock-reset flag (D-09 START).
  - POST /run stop → runstate with the SAFE-park flag (D-09 STOP).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-03 run start → lock-reset)", strict=False)
def test_run_start_flags_lock_reset():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-03 run stop → SAFE-park)", strict=False)
def test_run_stop_flags_safe_park():
    raise AssertionError("not implemented")
