"""FRM-06 confidence-normalization tests — scaffolded skip (filled by plan 02-02 conf-norm).

Wave-0 contract: plan 02-02 removes the ``pytestmark`` skip and fills
``test_brightness_anti_bias`` (two cameras, identical framing, one with a +conf bias →
after normalization they score within epsilon; an intra-camera spike still registers)
when it composes the per-camera conf-norm into the ``CameraScorer``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="conf-norm composition in 02-02")


def test_brightness_anti_bias() -> None:
    """Placeholder — 02-02 fills this with the brighter-camera anti-bias assertions."""
    raise AssertionError("filled by 02-02")
