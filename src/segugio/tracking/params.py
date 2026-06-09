"""``TrackingParams`` — the additive pydantic sub-model carrying the tracking seeds.

The per-camera tracking layer (TRK-03/04/05) hardcodes NO numeric constant. Its tuning
seeds live here as bounded ``Field``-constrained values and are wired into the one
validated ``Config`` as ``config.tracking`` (additive — existing YAML that omits
``tracking:`` still validates via ``default_factory=TrackingParams``).

This mirrors the Phase-2 ``ScorerParams`` sub-model exactly: ``ConfigDict(extra="forbid")``
(typo'd keys fail fast), ``Annotated[float, Field(...)]`` bounds on every param, and the
"values are tuning seeds; the SCHEMA/bounds are what's locked" framing. A bad tracking
seed therefore fails at config-load (startup), never in the hot loop (T-04-01-01).

The seed values themselves are calibration seeds (D-06/D-02; calibration is opportunistic
per D-02, NOT a gate) — the bounds are what is locked.

Light-import only — depends on nothing from ``segugio.config`` (``config.models`` imports
``TrackingParams`` from here, so the arrow points config → tracking, never the reverse).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TrackingParams"]

# Normalized [0..1] tuning param (mirrors framing.params.Norm).
Norm = Annotated[float, Field(ge=0.0, le=1.0)]


class TrackingParams(BaseModel):
    """The per-camera tracking tuning seeds (TRK-04 competitor-lock + TRK-05 gate).

    Values are tuning *seeds* (D-06/D-02 calibration, opportunistic per D-02 — not a
    gate); the SCHEMA and its bounds are what's locked here. Every field is bounded so a
    bad value fails fast at config-load — the tracker never re-validates in the hot loop.
    """

    model_config = ConfigDict(extra="forbid")

    # --- TRK-05 inter-frame plausibility gate (a track must move plausibly) ---
    max_displacement_per_tick: Annotated[float, Field(gt=0.0)] = 0.15
    # ^ max normalized center jump/tick before a match is implausible (teleport guard)
    max_size_ratio: Annotated[float, Field(gt=1.0)] = 1.6
    # ^ allowed area band [1/r, r] tick-to-tick (r>1); a sudden size jump is implausible
    # --- TRK-04 competitor-lock (cumulative-motion "in-competition dog" selector) ---
    motion_window: Annotated[int, Field(ge=1)] = 5
    # ^ K-tick window over which cumulative displacement (motion energy) is measured
    motion_deadzone: Annotated[float, Field(ge=0.0)] = 0.001
    # ^ below this cumulative motion → treat the track as stationary (spectator/handler)
