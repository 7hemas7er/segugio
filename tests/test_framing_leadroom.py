"""FRM-04 lead-room tests — the proven sign + clamp + zero-speed (02-02).

The load-bearing correctness point (RESEARCH Pitfall 2): the ideal centeredness target
shifts TOWARD the motion direction (dog moving right → ``ideal_x > 0.5``), so a dog
slightly BEHIND that forward-shifted ideal — sitting on the trailing side with empty
"lead room" ahead — outscores the same dog pinned dead-center. This test asserts:

  * the sign directly (``lead_room_target`` with ``vx > 0`` → ``ideal_x > 0.5``);
  * the behavioral consequence (a dog at cx=0.42 scores higher against the lead-shifted
    ideal than against the centered ideal);
  * zero speed (a resting/static dog) → ideal == (0.5, 0.5) (no twitch, PITFALL 9);
  * the magnitude is CLAMPED at ``lead_max`` for an arbitrarily fast step;
  * end-to-end: a linear_right stream driven through the CameraScorer builds a positive
    velocity, so the scorer's internal ideal has ``ideal_x > 0.5`` after history fills.
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.framing.scorer import CameraScorer
from segugio.framing.signals import DetectionSignal
from segugio.framing.terms import gaussian_centeredness, lead_room_target
from segugio.synth import detection_stream

CAM_ID = "cam_a"
N_TICKS = 30
SEED = 1234


def _full_frame_scorer(params, lead_gain: float) -> CameraScorer:
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
        {Role.main_wide: {"all": 1.0}},
        alpha=0.3,
        lead_gain=lead_gain,
        ttl_ticks=N_TICKS + 1,
    )


def test_target_shifts_toward_motion(scorer_params) -> None:
    """ideal_x>0.5 for rightward motion; dog behind ideal beats dead-center; zero→center; clamp."""
    p = scorer_params

    # --- Sign: rightward motion (vx>0) shifts the ideal toward motion (ideal_x>0.5) ---
    ideal_x, ideal_y = lead_room_target(0.2, 0.0, p.lead_max, p.lead_max, p.v_deadzone)
    assert ideal_x > 0.5
    assert ideal_y == pytest.approx(0.5)  # no vertical motion → ideal stays centered in y

    # --- Behavioral consequence: a dog leading into the empty space scores best with lead ---
    # The dog is moving right and is positioned where it is HEADING (at the lead-shifted
    # ideal). With lead-room active, that forward position is the optimum (score 1.0); the
    # SAME forward position scored against the (wrong) centered ideal scores strictly less —
    # i.e. lead-room rewards the dog that has empty "lead room" ahead in its direction.
    lead = ideal_x - 0.5
    assert lead > 0.0
    dog_cx = 0.5 + lead  # the dog sits where it is heading (at the lead-shifted ideal)
    scored_with_lead = gaussian_centeredness(dog_cx, 0.5, (0.5 + lead, 0.5), p.sigma_c)
    scored_centered = gaussian_centeredness(dog_cx, 0.5, (0.5, 0.5), p.sigma_c)
    assert scored_with_lead > scored_centered  # leading dog + lead room scores best

    # --- Zero speed (resting/static dog) → centered ideal, no lead -------------------
    assert lead_room_target(0.0, 0.0, p.lead_max, p.lead_max, p.v_deadzone) == (0.5, 0.5)
    # Below the deadzone is also treated as resting.
    tiny = p.v_deadzone / 2.0
    assert lead_room_target(tiny, 0.0, p.lead_max, p.lead_max, p.v_deadzone) == (0.5, 0.5)

    # --- Clamp: an arbitrarily fast dog cannot push the lead past lead_max -----------
    fast_x, _ = lead_room_target(100.0, 0.0, p.lead_max, p.lead_max, p.v_deadzone)
    assert (fast_x - 0.5) == pytest.approx(p.lead_max)  # magnitude clamped exactly at lead_max


def test_scorer_builds_positive_velocity_on_linear_right(scorer_params) -> None:
    """End-to-end: a linear_right stream → the scorer's internal ideal has ideal_x > 0.5."""
    p = scorer_params
    sc = _full_frame_scorer(p, lead_gain=0.25)
    stream = detection_stream(
        np.random.default_rng(SEED), CAM_ID, N_TICKS, path="linear_right", noise=0.0
    )
    # Drive past vel_window so the finite-difference history is full.
    for det in stream:
        sc.update(det, det.tick)

    vx, vy = sc._velocity()
    assert vx > 0.0  # rightward stream → positive x-velocity

    ideal_x, _ = lead_room_target(vx, vy, sc.lead_gain, p.lead_max, p.v_deadzone)
    assert ideal_x > 0.5  # the scorer's internal ideal leads the motion
