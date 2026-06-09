"""``ScorerParams`` — the additive pydantic sub-model carrying every scorer tuning seed.

The framing scorer hardcodes NO numeric constant (CONTEXT `<specifics>`: "all params in
validated config, none hardcoded"). All 19 tuning seeds live here as bounded
``Field``-constrained values and are wired into the one validated ``Config`` as
``config.scoring`` (additive — existing YAML that omits ``scoring:`` still validates via
``default_factory=ScorerParams``).

This mirrors the Phase-1 ``Thresholds`` sub-model exactly: ``ConfigDict(extra="forbid")``
(typo'd keys fail fast), ``Annotated[float, Field(...)]`` bounds on every param, and the
"values are tuning seeds; the schema/bounds are what's locked" framing. A bad scorer
param therefore fails at config-load (startup), never at scoring time (T-2-03 mitigation).

Light-import only — depends on nothing from ``segugio.config`` (``config.models`` imports
``ScorerParams`` from here, so the arrow points config → framing, never the reverse).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["ScorerParams"]

# Normalized [0..1] tuning param (mirrors config.models.Norm).
Norm = Annotated[float, Field(ge=0.0, le=1.0)]


class ScorerParams(BaseModel):
    """The framing-scorer tuning seeds (FRM-01..06 + the plausibility guard).

    Values are tuning *seeds* (calibrated on the curated clip set in Phase 3/4); the
    SCHEMA and its bounds are what's locked here. Every field is bounded so a bad value
    fails fast at config-load — the scorer never re-validates in the hot loop.

    The ``w_c + w_s + w_conf == 1`` invariant (D-01: centeredness-dominant weights) is
    enforced by a ``@model_validator`` so the base score is guaranteed ``∈ [0,1]``.
    """

    model_config = ConfigDict(extra="forbid")

    # --- centeredness (FRM-01) ---
    sigma_c: Annotated[float, Field(gt=0.0)] = 0.25  # Gaussian centeredness falloff
    # --- size target-band (FRM-01, D-02 non-monotonic) ---
    ideal_size: Norm = 0.30  # ideal apparent scale sqrt(w*h)
    sigma_s: Annotated[float, Field(gt=0.0)] = 0.18  # size-band tolerance
    # --- base-score weights (FRM-01, D-01 — sum to 1, w_conf low) ---
    w_c: Norm = 0.5  # centeredness weight (dominant)
    w_s: Norm = 0.3  # size weight (secondary)
    w_conf: Norm = 0.2  # normalized-confidence weight (low tiebreaker)
    # --- lead-room (FRM-04) ---
    lead_max: Norm = 0.25  # clamp so a fast dog can't push the ideal off-frame
    v_deadzone: Annotated[float, Field(ge=0.0)] = 0.005  # below this → no lead
    vel_window: Annotated[int, Field(ge=1)] = 3  # K-sample finite-difference window
    # --- coast / TTL (FRM-05) ---
    ttl_seconds: Annotated[float, Field(gt=0.0)] = 0.4  # short blur-gap coast window
    # --- per-camera confidence normalization (FRM-06) ---
    beta: Annotated[float, Field(gt=0.0, le=1.0)] = 0.05  # conf-norm EMA adaptation rate
    z_clip: Annotated[float, Field(gt=0.0)] = 2.0  # clip z-score to ±z_clip
    warmup: Annotated[int, Field(ge=1)] = 10  # passthrough samples before normalizing
    eps: Annotated[float, Field(gt=0.0)] = 1e-6  # sqrt(var + eps) divisor floor
    # --- plausibility / shadow guard ---
    conf_floor: Norm = 0.25  # confidence floor (recall gate)
    min_area: Norm = 0.0004  # below this → noise (keep LOW; distant dogs are small)
    aspect_lo: Annotated[float, Field(gt=0.0)] = 0.3  # implausible-aspect lower bound
    aspect_hi: Annotated[float, Field(gt=0.0)] = 3.5  # implausible-aspect upper bound
    # --- zone gating (FRM-03) ---
    out_of_bounds_factor: Norm = 0.15  # multiply (NOT zero) when outside all zones

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "ScorerParams":
        """D-01: the base-score weights must sum to 1 so ``base ∈ [0,1]``.

        Enforced here (not at scoring time) so a mis-tuned weight triple fails fast at
        config-load, mirroring the Phase-1 ``_zones_are_weighted`` cross-field validator.
        """
        total = self.w_c + self.w_s + self.w_conf
        if abs(total - 1.0) >= 1e-6:
            raise ValueError(
                f"base-score weights must sum to 1.0 (D-01 centeredness-dominant), got "
                f"w_c={self.w_c} + w_s={self.w_s} + w_conf={self.w_conf} = {total}"
            )
        return self
