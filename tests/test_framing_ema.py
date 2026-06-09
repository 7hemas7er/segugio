"""FRM-02 EMA-smoothing tests — driven against the real ``CameraScorer`` (02-02).

Proves the two EMA guarantees the CONTEXT D-05 decision locks:
  * COLD START seeds ``s_0 = raw_0`` (the first emitted score equals the first raw
    score, NOT 0 — seeding with 0 would lose the camera for the first ~1/alpha ticks);
  * a SMALLER alpha lags MORE than a larger alpha on a step input (the responsiveness
    /smoothness tradeoff): after a step up, the smaller-alpha scorer's score sits
    further below the new step value than the larger-alpha scorer's.

The scorer is driven directly: a tiny ``Camera`` stand-in with a single full-frame zone
removes the zone multiplier from the picture so the EMA recurrence is what's under test.
Mirrors ``tests/test_generators.py`` conventions (module-level constants, explicit
``np.random.default_rng(seed)``, shared ``scorer_params`` fixture).
"""

from __future__ import annotations

import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.framing.scorer import CameraScorer
from segugio.framing.signals import DetectionSignal

CAM_ID = "cam_a"
TTL_TICKS = 12  # ample so no coast fires during these present-detection sequences
# Neutral full-frame zone so the zone multiplier is exactly 1.0 → EMA is isolated.
_FULL_FRAME_WEIGHTS = {Role.main_wide: {"all": 1.0}}


def _scorer(alpha: float, params, lead_gain: float = 0.0) -> CameraScorer:
    """A CameraScorer over a single full-frame neutral zone (zone multiplier == 1.0)."""
    camera = Camera(
        id=CAM_ID,
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
    )
    return CameraScorer(
        camera,
        params,
        _FULL_FRAME_WEIGHTS,
        alpha=alpha,
        lead_gain=lead_gain,
        ttl_ticks=TTL_TICKS,
    )


def _det(tick: int, cx: float, cy: float, conf: float = 0.7) -> DetectionSignal:
    """A plausible, static, ideal-size detection at (cx, cy)."""
    return DetectionSignal(tick, CAM_ID, cx, cy, 0.30, 0.30, conf, 1)


def test_ema(scorer_params) -> None:
    """Cold start seeds s_0 = raw_0; smaller alpha lags more on a step input."""
    # --- Cold start: the first emitted score equals the first raw score (NOT 0) ----
    # With alpha arbitrary, the first present detection seeds ema = raw_0, so the first
    # emitted score is exactly raw_0. Recompute raw_0 from the composed pure terms.
    from segugio.framing.terms import (
        base_score,
        conf_norm_step,
        gate,
        gaussian_centeredness,
        gaussian_size_band,
        lead_room_target,
        zone_of,
    )

    p = scorer_params
    sc = _scorer(alpha=0.3, params=p)
    first_det = _det(0, 0.5, 0.5)
    first = sc.update(first_det, 0)

    # Hand-compute raw_0 the same way the scorer composes it (lead_gain=0 → ideal centered).
    cn0, _ = conf_norm_step({"n": 0, "mu": 0.0, "var": 0.0}, first_det.conf, p.beta, p.z_clip, p.eps, p.warmup)
    ideal0 = lead_room_target(0.0, 0.0, 0.0, p.lead_max, p.v_deadzone)
    c0 = gaussian_centeredness(first_det.cx, first_det.cy, ideal0, p.sigma_c)
    s0 = gaussian_size_band(first_det.w, first_det.h, p.ideal_size, p.sigma_s)
    base0 = base_score(c0, s0, cn0, p.w_c, p.w_s, p.w_conf)
    zone0 = zone_of(first_det.cx, first_det.cy, sc.camera, sc.fw)
    raw0 = gate(base0, sc.camera, zone0, sc.fw, p.out_of_bounds_factor)

    assert first.score == pytest.approx(raw0)  # cold start: s_0 == raw_0
    assert first.score > 0.0  # NOT seeded at 0

    # --- Lag: smaller alpha lags more than larger alpha on a step input ------------
    # Both scorers start well-centered (high raw) then STEP to a poorly-framed corner
    # (low raw). After K identical low-raw ticks the smaller-alpha scorer should still
    # sit HIGHER (lag more) than the larger-alpha one — both above the new low target.
    p_lo, p_hi = scorer_params, scorer_params.model_copy()
    slow = _scorer(alpha=0.1, params=p_lo)   # smaller alpha → more lag
    fast = _scorer(alpha=0.6, params=p_hi)   # larger alpha → snappier

    # Warm both to the same high-centered cold start (identical seed).
    slow.update(_det(0, 0.5, 0.5), 0)
    fast.update(_det(0, 0.5, 0.5), 0)

    # Step input: now poorly framed (far corner → low centeredness → low raw).
    last_slow = last_fast = None
    for t in range(1, 9):
        last_slow = slow.update(_det(t, 0.95, 0.95), t)
        last_fast = fast.update(_det(t, 0.95, 0.95), t)

    # The smaller-alpha scorer retains more of the old high value (lags more): its score
    # is strictly higher than the snappier scorer's after the same number of low ticks.
    assert last_slow.score > last_fast.score
