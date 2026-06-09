"""FRM-05 coast/TTL tests — scaffolded skip (filled by plan 02-03 coast/TTL).

Wave-0 contract: plan 02-03 removes the ``pytestmark`` skip and fills
``test_coast_then_lost`` (a dropout window holds the score with status ``coasting`` for
``ttl_ticks``, then drops to 0 with status ``lost``; recovery before TTL resumes
``tracking`` with no cold-start re-seed) when it composes the TTL countdown.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="coast/TTL composed in 02-03")


def test_coast_then_lost() -> None:
    """Placeholder — 02-03 fills this with the coast-then-lost timeline assertions."""
    raise AssertionError("filled by 02-03")
