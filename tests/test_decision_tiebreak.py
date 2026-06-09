"""DEC-05 tiebreaker suite — incumbent-wins; no incumbent → first camera in config order.

The tiebreaker stops the equidistant-score ping-pong the hysteresis dead-band alone does not
fully settle (03-CONTEXT D-07). Two hard properties:

  * with an incumbent, a near-exact score tie INSIDE the dead-band resolves to the incumbent
    (no cut — reinforcing the hysteresis stickiness);
  * with NO incumbent (cold start / just back from SAFE), an exact tie resolves to the FIRST
    camera in config DECLARATION order — the only fallback rule (no role-priority concept).

And the determinism property: replaying the ``tie`` score stream yields <= 1 transition after
warm-up (no oscillation on equidistant noise — consistent with the DEC-02 no-chase metric).
"""

from __future__ import annotations

import numpy as np

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.synth import score_stream
from tests.conftest import FPS, SEED, _as_camera_scores

_CAM_A = "cam_a"
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
    """Two cameras in declaration order [cam_a, cam_b]; cam_a is the SAFE fallback."""
    return [
        Camera(
            id=cid,
            role=Role.main_wide,
            obs_scene="WIDE",
            is_safe=(cid == _CAM_A),
            zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
        )
        for cid in (_CAM_A, _CAM_B)
    ]


def _engine(thresholds) -> DecisionEngine:
    return DecisionEngine(_two_cameras(), thresholds, fps=FPS)


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _acquire(eng: DecisionEngine, cam: str, *, other: str, t0: int = 0) -> int:
    """Drive a steady lead until ``cam`` is the live incumbent past dwell; next free tick."""
    t = t0
    for _ in range(400):
        eng.tick([_sc(cam, 0.85, t), _sc(other, 0.10, t)], alive={cam: True, other: True})
        t += 1
        if eng.target == cam and eng.dwell_elapsed >= eng.min_dwell_ticks and eng.cooldown_remaining == 0:
            break
    assert eng.target == cam
    return t


def test_incumbent_wins_near_tie(thresholds) -> None:
    """With an incumbent, a near-exact tie inside the dead-band retains the incumbent (no cut).

    Acquire cam_b as the live incumbent (dwell+cooldown cleared, so only the dead-band protects
    it now). Then feed cam_a a score within ``hysteresis_margin`` of cam_b's (a near-exact tie,
    a touch UNDER cam_b so cam_a does not clear the margin). The incumbent cam_b must be held
    across the whole tie window — the dead-band tiebreak resolves to the incumbent.
    """
    margin = thresholds.hysteresis_margin
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)

    # cam_a sits a hair below cam_b — well inside the dead-band (does NOT exceed by margin).
    for _ in range(40):
        d = eng.tick(
            [_sc(_CAM_A, 0.60, t), _sc(_CAM_B, 0.60 + margin * 0.5, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        assert d.target == _CAM_B, "a near-exact dead-band tie stole the incumbent (DEC-05)"
        t += 1


def test_no_incumbent_resolves_config_order(thresholds) -> None:
    """From cold start (no incumbent), an exact tie resolves to the FIRST camera in config order.

    With no incumbent the SAFE score is 0.0, so both cameras clear the margin and tie EXACTLY.
    The deterministic config-declaration-order tiebreak must pick cam_a (declared first), never
    cam_b — and never flip on the equal scores. Sustained long enough to clear debounce_N.
    """
    eng = _engine(thresholds)
    assert eng.target == SAFE_TARGET  # cold start, no incumbent.

    acquired = None
    t = 0
    for _ in range(eng.debounce_N + 5):
        d = eng.tick(
            [_sc(_CAM_A, 0.80, t), _sc(_CAM_B, 0.80, t)],  # EXACT tie
            alive={_CAM_A: True, _CAM_B: True},
        )
        if d.target != SAFE_TARGET and acquired is None:
            acquired = d.target
        t += 1
    assert acquired == _CAM_A, (
        f"an exact cold-start tie resolved to {acquired!r}; expected the first config camera cam_a"
    )


def test_no_incumbent_config_order_is_independent_of_score_argument_order(thresholds) -> None:
    """The config-order tiebreak does NOT depend on the per-tick scores list order (determinism).

    Feeding the exact-tie scores with cam_b listed FIRST in the per-tick batch must STILL resolve
    to cam_a — the tiebreak key is the config declaration order, not the argument order.
    """
    eng = _engine(thresholds)
    acquired = None
    t = 0
    for _ in range(eng.debounce_N + 5):
        d = eng.tick(
            [_sc(_CAM_B, 0.80, t), _sc(_CAM_A, 0.80, t)],  # cam_b listed FIRST, exact tie
            alive={_CAM_A: True, _CAM_B: True},
        )
        if d.target != SAFE_TARGET and acquired is None:
            acquired = d.target
        t += 1
    assert acquired == _CAM_A, (
        f"tie resolved to {acquired!r} based on score-list order; must use config order (cam_a)"
    )


def test_tie_stream_no_oscillation(thresholds) -> None:
    """Replaying the `tie` score stream yields <= 1 transition after warm-up (no ping-pong)."""
    n_ticks = 120
    cam_ids = [_CAM_A, _CAM_B]
    rng = np.random.default_rng(SEED)
    samples = _as_camera_scores(score_stream(rng, "tie", cam_ids, n_ticks))
    by_tick: dict[int, list[CameraScore]] = {}
    for s in samples:
        by_tick.setdefault(s.tick, []).append(s)

    eng = _engine(thresholds)
    targets: list[str] = []
    for t in range(n_ticks):
        d = eng.tick(by_tick[t], alive={_CAM_A: True, _CAM_B: True})
        targets.append(d.target)

    warmup = 10
    transitions = sum(
        1 for t in range(warmup + 1, len(targets)) if targets[t] != targets[t - 1]
    )
    assert transitions <= 1, (
        f"the tie stream produced {transitions} transitions after warm-up "
        f"(expected <= 1 — equidistant noise must not oscillate the FSM)"
    )
