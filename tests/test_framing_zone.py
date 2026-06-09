"""FRM-03 zone-gating tests — scaffolded skip (filled by plan 02-02).

This Wave-0 contract file exists so the test surface is fixed once; plan 02-02 removes
the ``pytestmark`` skip and fills ``test_zone_multiplier`` (a center in a known band ×
``framing_weights[role][zone]``; outside all zones → ``base × out_of_bounds_factor``)
when it composes the ``gate``/``zone_of`` terms into the scorer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="zone-gating composed in 02-02")


def test_zone_multiplier() -> None:
    """Placeholder — 02-02 fills this with the gate/zone-of multiplier assertions."""
    raise AssertionError("filled by 02-02")
