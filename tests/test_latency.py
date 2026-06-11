"""RBT-05 — latency harness: frame→YOLO→score→FSM→OBS p95 < 150ms (Wave-0 stub).

Behavior (filled by 05-06):
  - on the GPU box (@pytest.mark.gpu), the real-YOLO loop p95 < 150ms (target <80ms).
  - a mock-timed variant exercises the harness headless.
"""

from __future__ import annotations

import pytest


@pytest.mark.gpu
@pytest.mark.xfail(reason="impl pending 05-06 (RBT-05 latency p95)", strict=False)
def test_loop_latency_p95_under_budget():
    raise AssertionError("not implemented")
