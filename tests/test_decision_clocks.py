"""Seconds→ticks bridge tests for ``segugio.decision.clocks.ticks_from_seconds``.

A table-style test mirroring ``test_framing_coast.py::test_ttl_ticks_from_seconds_ceils_positive``.
``ceil`` guarantees at least one tick for any positive seconds (the single source of rounding
truth the FSM's dwell/cooldown clocks rely on).
"""

from __future__ import annotations

from segugio.decision import ticks_from_seconds


def test_ticks_from_seconds_ceils_positive() -> None:
    """ticks_from_seconds ceils to a positive int (>= 1 for any positive seconds)."""
    assert ticks_from_seconds(2.0, 30.0) == 60  # ceil(60.0) — min_dwell 2.0s @ 30fps
    assert ticks_from_seconds(1.0, 30.0) == 30  # ceil(30.0) — cooldown 1.0s @ 30fps
    assert ticks_from_seconds(0.001, 30.0) == 1  # ceil(0.03) → at least 1 tick
