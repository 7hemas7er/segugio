"""OBS-03 — reconnect path re-creates the client after a simulated drop (Wave-0 stub).

Behavior (filled by 05-03):
  - a simulated websocket drop → the controller re-creates the ReqClient/EventClient.
  - a failed cut coasts the loop (never crashes — RBT-04).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-03 reconnect)", strict=False)
def test_reconnect_recreates_client_after_drop():
    raise AssertionError("not implemented")
