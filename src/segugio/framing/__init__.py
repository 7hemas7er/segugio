"""segugio.framing — the pure, I/O-free per-camera framing scorer substrate (Phase 2).

Turns a stream of normalized ``DetectionSignal``s into a smoothed [0,1] ``CameraScore``
per camera, encoding the domain's hardest framing decisions (centeredness, size band,
zone gating, lead-room, coast/TTL, per-camera confidence normalization).

This package is pure: it imports only numpy + stdlib + pydantic (via the params
sub-model), never torch / ultralytics / cyndilib, so ``import segugio.framing`` succeeds
on a machine with the heavy runtime absent (the FRM-07 lazy-import boundary).

Plan 02-01 establishes the substrate symbols; 02-02 adds the stateful ``CameraScorer``
(present-detection path) re-exported below; 02-03 adds the coast/TTL dropout path,
``MultiCamScorer`` (the per-camera fan-out), and the ``ttl_ticks_from_seconds`` helper.
"""

from __future__ import annotations

from .params import ScorerParams
from .scorer import CameraScorer, MultiCamScorer, ttl_ticks_from_seconds
from .signals import CameraScore, DetectionSignal, ScorerStatus

__all__ = [
    "DetectionSignal",
    "CameraScore",
    "ScorerStatus",
    "ScorerParams",
    "CameraScorer",
    "MultiCamScorer",
    "ttl_ticks_from_seconds",
]
