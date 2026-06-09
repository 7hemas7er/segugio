"""Frozen input/output records for the per-camera framing scorer (FRM-07).

``DetectionSignal`` is the scorer's INPUT contract — the exact TRK-03 signal set
(``cx, cy, w, h, conf, track_id``) so a Phase-4 YOLO+BoT-SORT result row maps to one
unchanged. ``CameraScore`` is the scorer's OUTPUT — the smoothed [0,1] value plus a
``ScorerStatus`` the Phase-3 FSM consumes.

Both records are frozen (hashable + comparable) so ``==`` over two
``list[DetectionSignal | None]`` / ``list[CameraScore]`` is the determinism assertion
the synthetic-stream and purity tests rely on (mirrors the Phase-1 ``ScoreSample`` /
``FeedEvent`` convention). All numeric fields are plain ``float`` (``float()``-cast at
construction) so a numpy scalar never leaks into the ``==``.

stdlib only (``dataclasses`` / ``enum``) — no numpy, no synth import. The dependency
direction is one-way: ``synth.detection_stream`` depends UP onto this module; this
module must never import from ``synth`` (avoids an import cycle) and keeps the Phase-1
lazy-import boundary intact (no torch / ultralytics / cyndilib).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["DetectionSignal", "CameraScore", "ScorerStatus"]


class ScorerStatus(str, Enum):
    """Per-camera scorer state (FRM-05).

    A ``str`` Enum (mirrors ``config.models.Role``) so ``CameraScore`` stays
    ``==``-comparable and YAML/JSON-friendly. ``coasting`` = holding the last EMA
    through a short blur gap; ``lost`` = TTL expired (score driven to 0).
    """

    tracking = "tracking"
    coasting = "coasting"
    lost = "lost"


@dataclass(frozen=True)
class DetectionSignal:
    """One per-detection signal for one camera at one synthetic tick (scorer INPUT).

    Frozen (hashable + comparable) so ``==`` over two sequences is the determinism
    assertion. The field set is exactly TRK-03 (``cx, cy, w, h, conf, track_id``) so a
    Phase-4 YOLO+BoT-SORT result row maps here with no scorer change. ``None`` (not an
    instance of this class) means "no dog detected this camera this tick" → coast path.

    All spatial fields are normalized [0,1] (resolution-independent by construction);
    ``tick`` is the injected synthetic/frame index — never a wall-clock.
    """

    tick: int
    cam_id: str
    cx: float  # normalized bbox center x ∈ [0,1]
    cy: float  # normalized bbox center y ∈ [0,1]
    w: float  # normalized bbox width  ∈ [0,1]
    h: float  # normalized bbox height ∈ [0,1]
    conf: float  # raw detector confidence ∈ [0,1]
    track_id: int  # tracker-assigned id (advisory; velocity continuity)


@dataclass(frozen=True)
class CameraScore:
    """One smoothed per-camera score reading at one tick (scorer OUTPUT).

    Frozen (hashable + comparable) so ``==`` over two ``list[CameraScore]`` is the
    determinism assertion the FRM-07 purity test relies on. ``score`` is the smoothed
    [0,1] value the Phase-3 FSM consumes; ``status`` is the ``ScorerStatus`` enum.
    """

    tick: int
    cam_id: str
    score: float  # smoothed [0,1]
    status: ScorerStatus
