"""``DecisionEngine`` — the camera-switching FSM (a ``transitions.Machine`` wrapper).

This module is the Phase-3 core (filled by plan 03-01 Task 2). It is a thin wrapper around
a ``transitions.Machine`` whose guarded transitions are the ONLY path by which the live
target changes — the mechanical guarantee behind DEC-01. The integer dwell/cooldown clocks
and the challenger/debounce counter live as plain model attributes the tick-loop advances.

This Task-1 stub establishes the constructor + ``tick()`` signatures (enough for
``import segugio.decision`` to succeed with the heavy runtime absent); Task 2 fills the
guarded-transition wiring and the hysteresis/dwell/debounce/cooldown logic.

Imports only ``transitions`` + stdlib + the pure ``segugio.framing`` surface — no torch /
ultralytics / cyndilib / obsws at module top level (the Phase-1 lazy-import boundary).
"""

from __future__ import annotations

from transitions import Machine

from ..framing.signals import CameraScore, ScorerStatus  # noqa: F401  — input contract
from .clocks import ticks_from_seconds
from .signals import Decision, HoldInput, Mode, OverrideCmd  # noqa: F401

__all__ = ["DecisionEngine"]


class DecisionEngine:
    """Tick-driven camera-switching FSM (filled in 03-01 Task 2)."""

    def __init__(self, cameras, thresholds, fps: float = 30.0) -> None:
        raise NotImplementedError("DecisionEngine is implemented in 03-01 Task 2")

    def tick(
        self,
        scores: list[CameraScore],
        alive: dict[str, bool] | None = None,
        holds: HoldInput | None = None,
        override: OverrideCmd | None = None,
    ) -> Decision:
        raise NotImplementedError("DecisionEngine.tick is implemented in 03-01 Task 2")
