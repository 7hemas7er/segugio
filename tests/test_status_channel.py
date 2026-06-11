"""D-11 — orchestrator writes director status (live cam + reason + per-feed alive) (Wave-0 stub).

Behavior (filled by 05-06):
  - on each change the orchestrator writes a small atomic status file: live camera +
    reason (auto/override/subject-lost/feed-dead) + per-feed alive/dead — the UI polls it.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-06 (D-11 director status channel)", strict=False)
def test_status_written_on_change():
    raise AssertionError("not implemented")
