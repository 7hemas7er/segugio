"""FRM-04 lead-room tests — scaffolded skip (filled by plan 02-02 lead-room composition).

Wave-0 contract: plan 02-02 removes the ``pytestmark`` skip and fills
``test_target_shifts_toward_motion`` (dog moving right → ``ideal_x > 0.5``; a dog behind
the shifted ideal outscores the same dog dead-center; zero speed → centered ideal; lead
clamped at ``lead_max``) when it composes lead-room into the ``CameraScorer``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="lead-room composition in 02-02")


def test_target_shifts_toward_motion() -> None:
    """Placeholder — 02-02 fills this with the lead-room sign/clamp assertions."""
    raise AssertionError("filled by 02-02")
