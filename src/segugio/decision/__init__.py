"""segugio.decision — the pure, tick-driven camera-switching decision FSM (Phase 3).

The single source of truth on which camera is live (a camera id or the ``"SAFE"``
sentinel). Each tick the orchestrator (synthetic tests in Phase 3) feeds the engine a
``list[CameraScore]`` + a per-camera feed-alive map + the explicit hold input(s) + an
optional override command; the FSM evaluates its guards (hysteresis dead-band,
``debounce_N`` sustain, ``min_dwell``, ``cooldown``, feed-alive, holds, override) and emits
a switch decision ONLY from inside a guarded ``transitions`` callback — the invariant behind
DEC-01. All "time" is the injected integer tick; seconds-valued config is converted to ticks
once via an injected ``fps`` (``ticks_from_seconds``). Same input stream → byte-identical
``list[Decision]`` (DEC-07), mirroring the Phase-1 synth and Phase-2 scorer determinism.

This package is pure: it imports only ``transitions`` + stdlib (+ the pure
``segugio.framing`` / ``segugio.config`` surfaces), never torch / ultralytics / cyndilib /
obsws — so ``import segugio.decision`` succeeds with the heavy runtime absent (the
lazy-import boundary; ``transitions`` is a LIGHT runtime dep as of 03-01).

Plan 03-01 establishes the package + the core auto-switching FSM (DEC-01/02); 03-02 adds
holds/tiebreaker/feed-death guards; 03-03 adds override + auto-resume; 03-04 the DEC-07 suite.
"""

from __future__ import annotations

from .clocks import ticks_from_seconds
from .engine import DecisionEngine
from .signals import Decision, HoldInput, Mode, OverrideCmd

__all__ = [
    "DecisionEngine",
    "Decision",
    "Mode",
    "HoldInput",
    "OverrideCmd",
    "ticks_from_seconds",
]
