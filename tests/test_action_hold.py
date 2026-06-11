"""D-08 — sustained motion energy → HoldInput.action=True → FSM holds the cut (Wave-0 stub).

Behavior (filled by 05-06):
  - locked-subject motion energy >= ActionHoldParams.motion_threshold sustained over
    window_ticks → HoldInput(action=True); the FSM's hold suppression (DEC-03 cap) holds.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-06 (D-08 motion → HoldInput.action)", strict=False)
def test_sustained_motion_sets_action_hold():
    raise AssertionError("not implemented")
