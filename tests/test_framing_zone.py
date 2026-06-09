"""FRM-03 zone-gating tests — driven against the real composition (02-02).

Proves the entire sport→scorer coupling (ARCHITECTURE.md Part 3): the raw score is the
base score MULTIPLIED by ``framing_weights[role][zone]`` for the zone the bbox center
lands in, and a center outside ALL zones is gated DOWN by ``out_of_bounds_factor`` (NOT
to zero — PITFALL 1). Built from the canonical ``valid_config_dict`` so the weights matrix
under test is the real Phase-1 contract:

  long role: {mid: 1.1, far: 1.6};  main_wide role: {near: 1.2, mid: 1.0, far: 0.8}

The assertion compares the scorer's gated raw against an independently composed
``base × weight`` (the base from the same pure terms), within float epsilon.
"""

from __future__ import annotations

import pytest

from segugio.config import Config, Role
from segugio.framing.scorer import CameraScorer
from segugio.framing.signals import DetectionSignal
from segugio.framing.terms import (
    base_score,
    conf_norm_step,
    gate,
    gaussian_centeredness,
    gaussian_size_band,
    lead_room_target,
    zone_of,
)

# cam_long zones (from conftest _VALID_CONFIG): mid=[0.2,0.3,0.8,0.6], far=[0.2,0.6,0.8,0.95]
_FAR_CENTER = (0.5, 0.75)   # inside far  (y∈[0.6,0.95]) → long weight 1.6
_MID_CENTER = (0.5, 0.45)   # inside mid  (y∈[0.3,0.6])  → long weight 1.1
_OUT_CENTER = (0.05, 0.05)  # outside both long zones    → out_of_bounds_factor


def _base_at(cx: float, cy: float, params) -> float:
    """Independently compose the base score (pre-gate) the way the scorer does.

    Single-detection cold start: conf-norm passes ``conf`` through; velocity is 0
    (one sample) so the ideal is centered (lead_gain irrelevant). Mirrors the scorer's
    present-detection branch exactly so the only difference left to test is the gate.
    """
    p = params
    conf = 0.7
    cn, _ = conf_norm_step({"n": 0, "mu": 0.0, "var": 0.0}, conf, p.beta, p.z_clip, p.eps, p.warmup)
    ideal = lead_room_target(0.0, 0.0, 0.0, p.lead_max, p.v_deadzone)
    c = gaussian_centeredness(cx, cy, ideal, p.sigma_c)
    s = gaussian_size_band(0.30, 0.30, p.ideal_size, p.sigma_s)
    return base_score(c, s, cn, p.w_c, p.w_s, p.w_conf)


def _scorer_for(config: Config) -> CameraScorer:
    """A CameraScorer over the cam_long camera from the parsed config (role=long)."""
    cam_long = next(c for c in config.cameras if c.role == Role.long)
    return CameraScorer(
        cam_long,
        config.scoring,
        config.framing_weights,
        alpha=config.thresholds.alpha,
        lead_gain=0.0,  # isolate the gate: no lead shift
        ttl_ticks=10,
    )


def _raw(scorer: CameraScorer, cx: float, cy: float) -> float:
    """Drive a single cold-start detection at (cx,cy) → the emitted (== raw) score."""
    det = DetectionSignal(0, scorer.camera.id, cx, cy, 0.30, 0.30, 0.7, 1)
    return scorer.update(det, 0).score  # cold start → ema == raw


def test_zone_multiplier(valid_config_dict, scorer_params) -> None:
    """In-zone raw == base × framing_weights[role][zone]; out-of-zone == base × oob_factor."""
    config = Config.model_validate(valid_config_dict)
    p = config.scoring

    # Sanity: the detection center maps to the zone we expect (precondition).
    cam_long = next(c for c in config.cameras if c.role == Role.long)
    assert zone_of(*_FAR_CENTER, cam_long, config.framing_weights) == "far"
    assert zone_of(*_MID_CENTER, cam_long, config.framing_weights) == "mid"
    assert zone_of(*_OUT_CENTER, cam_long, config.framing_weights) is None

    far_weight = config.framing_weights[Role.long]["far"]   # 1.6
    mid_weight = config.framing_weights[Role.long]["mid"]   # 1.1
    oob = p.out_of_bounds_factor

    # --- far band: raw == clip(base × 1.6) ---------------------------------------
    base_far = _base_at(*_FAR_CENTER, p)
    raw_far = _raw(_scorer_for(config), *_FAR_CENTER)
    assert raw_far == pytest.approx(min(base_far * far_weight, 1.0))

    # --- mid band: raw == base × 1.1 ---------------------------------------------
    base_mid = _base_at(*_MID_CENTER, p)
    raw_mid = _raw(_scorer_for(config), *_MID_CENTER)
    assert raw_mid == pytest.approx(min(base_mid * mid_weight, 1.0))

    # A high-weight zone outscores a low-weight zone for IDENTICAL framing (the must-have
    # truth). Assert it on the gate directly with one fixed base and the two weights, so a
    # different per-zone framing quality (and [0,1] saturation) can't confound it. Use a
    # modest base so neither product clips.
    cam_long = next(c for c in config.cameras if c.role == Role.long)
    fixed_base = 0.5
    gated_far = gate(fixed_base, cam_long, "far", config.framing_weights, oob)
    gated_mid = gate(fixed_base, cam_long, "mid", config.framing_weights, oob)
    assert gated_far == pytest.approx(min(fixed_base * far_weight, 1.0))
    assert gated_mid == pytest.approx(fixed_base * mid_weight)
    assert gated_far > gated_mid  # higher-weight zone wins for the same framing

    # --- outside all zones: gated DOWN by out_of_bounds_factor, NOT to zero ------
    base_out = _base_at(*_OUT_CENTER, p)
    raw_out = _raw(_scorer_for(config), *_OUT_CENTER)
    assert raw_out == pytest.approx(base_out * oob)
    assert raw_out > 0.0  # PITFALL 1: gate-down, never hard-zero
