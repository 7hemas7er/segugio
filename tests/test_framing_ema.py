"""FRM-02 EMA-smoothing tests — scaffolded skip (filled by plan 02-02 EMA).

Wave-0 contract: plan 02-02 removes the ``pytestmark`` skip and fills ``test_ema``
(cold-start ``s_0 = raw_0``; smaller alpha lags more than larger alpha on a step input)
when it composes EMA smoothing into the ``CameraScorer``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="EMA smoothing composed in 02-02")


def test_ema() -> None:
    """Placeholder — 02-02 fills this with the EMA lag/cold-start assertions."""
    raise AssertionError("filled by 02-02")
