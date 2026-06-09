"""``ticks_from_seconds(seconds, fps)`` — the seconds→ticks bridge for the FSM clocks.

A byte-for-byte clone of ``framing.scorer.ttl_ticks_from_seconds`` (the established
Phase-2 precedent). Config holds ``min_dwell`` / ``cooldown`` / ``hold_length_s`` in
SECONDS; the FSM measures everything in integer TICKS (determinism — no wall-clock). This
helper converts once, at engine construction, with ``fps`` injected as an ARGUMENT (never a
config field: ``Thresholds`` has no ``fps``, RESEARCH Pattern 2 / A2).

``math.ceil`` is the single source of rounding truth → at least one tick for any positive
seconds. stdlib ``math`` only — keeps the lazy-import boundary intact.
"""

from __future__ import annotations

import math

__all__ = ["ticks_from_seconds"]


def ticks_from_seconds(seconds: float, fps: float) -> int:
    """Convert a ``seconds`` duration to whole ticks at ``fps`` (clock-free).

    Pure stdlib (``math.ceil``) — the FSM stays clock-free by taking tick counts directly;
    this helper is the construction-time convenience that maps the config's seconds-valued
    durations (``min_dwell`` 2.0s, ``cooldown`` 1.0s, ``hold_length_s`` 2.5/1.5s) to a
    positive integer tick count. ``ceil`` guarantees at least one tick for any positive
    ``seconds``.
    """
    return int(math.ceil(seconds * fps))
