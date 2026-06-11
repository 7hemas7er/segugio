"""RBT-04 — a thrown error in any stage → loop coasts to SAFE, never crashes (Wave-0 stub).

Behavior (filled by 05-06):
  - a throwing fake at any stage (UI/decode/OBS) → the tick coasts to SAFE, keeps ticking.
  - on shutdown the orchestrator cuts to SAFE explicitly.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-06 (RBT-04 fault isolation → SAFE)", strict=False)
def test_thrown_error_coasts_to_safe():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-06 (RBT-04 SAFE on shutdown)", strict=False)
def test_safe_on_shutdown():
    raise AssertionError("not implemented")
