"""FRM-05 coast/TTL tests — driven against the real ``CameraScorer`` (02-03).

Proves the single most important robustness invariant the CONTEXT D-03/D-04 decisions
lock: a SHORT detection dropout (blur on a catch/jump apex — the worst moment to cut,
PITFALL 3) must COAST, never collapse to 0.

  * ``test_coast_then_lost``: feed ``[det × 5, None × ttl_ticks]`` to a scorer with a small
    fixed ``ttl_ticks``. While the TTL has not expired the status is ``coasting`` and the
    score is HELD at the last tracking EMA (> 0, never 0 mid-window — the "never collapse"
    invariant, D-03). At the tick where the TTL reaches 0 the score drops to ``0.0`` and the
    status is ``lost``.
  * ``test_recovery_before_ttl``: feed ``[det × 5, None × (ttl_ticks - 1), det]``. The
    recovery tick resumes status ``tracking`` and the EMA is CONTINUOUS with the held value
    (the recovered score is the fixed-α blend of the held EMA and the new raw — NOT a
    cold-start jump to raw_0; D-04 re-acquire-without-re-seed).

The scorer is driven directly via a tiny ``Camera`` stand-in with a single full-frame
neutral zone (zone multiplier == 1.0), so the coast/TTL state machine is what is under
test, not the zone gate. Mirrors ``tests/test_framing_ema.py`` (module-level constants,
single full-frame zone) and the ``tests/test_generators.py``
``test_feeddeath_timeline_boundaries`` alive/dead-by-tick parametrize style.
"""

from __future__ import annotations

import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.framing.scorer import (
    CameraScorer,
    MultiCamScorer,
    ttl_ticks_from_seconds,
)
from segugio.framing.signals import DetectionSignal, ScorerStatus

CAM_ID = "cam_a"
TTL_TICKS = 4  # small + explicit → a short, deterministic coast timeline
ALPHA = 0.3
# Neutral full-frame zone so the zone multiplier is exactly 1.0 → the coast state machine
# (not the zone gate) is isolated.
_FULL_FRAME_WEIGHTS = {Role.main_wide: {"all": 1.0}}


def _scorer(params, ttl_ticks: int = TTL_TICKS) -> CameraScorer:
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
        alpha=ALPHA,
        lead_gain=0.0,  # no lead → ideal centered, keeps the present-path raw stable
        ttl_ticks=ttl_ticks,
    )


def _det(tick: int, track_id: int = 1, cx: float = 0.5, cy: float = 0.5) -> DetectionSignal:
    """A plausible, static, well-centered, ideal-size detection at (cx, cy)."""
    return DetectionSignal(tick, CAM_ID, cx, cy, 0.30, 0.30, 0.7, track_id)


def test_coast_then_lost(scorer_params) -> None:
    """A short dropout coasts (held EMA, status coasting) then drops to 0 + lost at TTL."""
    sc = _scorer(scorer_params)

    # --- Warm-up: 5 present, static, well-centered detections → a stable tracking EMA. ---
    held = None
    for t in range(5):
        out = sc.update(_det(t), t)
        assert out.status is ScorerStatus.tracking
        held = out.score
    assert held is not None and held > 0.0  # there IS a real EMA to hold.

    # --- Dropout: ttl_ticks consecutive Nones. Time runs 5 .. 5 + ttl_ticks - 1. ----------
    # The absent branch does `ttl -= 1` per tick; the last present tick set ttl = TTL_TICKS.
    #   miss #1 (t=5): ttl 4->3 (>0)  -> coasting, held
    #   miss #2 (t=6): ttl 3->2 (>0)  -> coasting, held
    #   miss #3 (t=7): ttl 2->1 (>0)  -> coasting, held
    #   miss #4 (t=8): ttl 1->0 (==0) -> lost, score 0.0
    statuses: list[ScorerStatus] = []
    scores: list[float] = []
    for i in range(TTL_TICKS):
        t = 5 + i
        out = sc.update(None, t)
        statuses.append(out.status)
        scores.append(out.score)

    # First ttl_ticks - 1 misses: coasting, score HELD at the last tracking EMA (D-03).
    for i in range(TTL_TICKS - 1):
        assert statuses[i] is ScorerStatus.coasting
        assert scores[i] == pytest.approx(held)  # EMA frozen — raw=0 never fed in.

    # never-collapse-mid-window invariant (D-03 "never collapse to 0"): no coasting score
    # is 0.0 (and none decays — they are all exactly the held value).
    assert all(s > 0.0 for s in scores[: TTL_TICKS - 1])
    assert all(s == pytest.approx(held) for s in scores[: TTL_TICKS - 1])

    # TTL expiry (the ttl-th miss): score drops to 0.0, status lost.
    assert statuses[TTL_TICKS - 1] is ScorerStatus.lost
    assert scores[TTL_TICKS - 1] == 0.0


@pytest.mark.parametrize("gap", [1, TTL_TICKS - 1])
def test_recovery_before_ttl(scorer_params, gap: int) -> None:
    """A dropout shorter than the TTL resumes tracking continuously (no cold-start)."""
    sc = _scorer(scorer_params)

    # Warm-up: 5 present detections → a stable held EMA.
    held = None
    for t in range(5):
        held = sc.update(_det(t), t).score
    assert held is not None and held > 0.0

    # A gap of `gap` Nones, all strictly inside the TTL window (gap < TTL_TICKS → ttl > 0).
    for i in range(gap):
        out = sc.update(None, 5 + i)
        assert out.status is ScorerStatus.coasting
        assert out.score == pytest.approx(held)  # held throughout the (sub-TTL) gap.

    # Recovery: the next present detection (SAME track id) resumes tracking.
    recover_tick = 5 + gap
    recovered = sc.update(_det(recover_tick), recover_tick)
    assert recovered.status is ScorerStatus.tracking

    # D-04 re-acquire-without-re-seed: the recovered EMA is the fixed-α blend of the HELD
    # value and the new raw — NOT a cold-start jump to raw_0. Because the held detection and
    # the recovery detection are identical (raw == held), the blended EMA equals the held
    # value (continuous), and it is NOT a fresh cold-start (which would have re-seeded the
    # EMA from scratch only after a `lost` + new track id, which never happened here).
    assert recovered.score == pytest.approx(held)

    # Cross-check the no-re-seed path explicitly with a DIFFERENT recovery raw: a recovery
    # detection in a worse position blends DOWN from the held value (continuity), it does
    # not snap to the cold-start raw_0 of that worse detection.
    sc2 = _scorer(scorer_params)
    held2 = None
    for t in range(5):
        held2 = sc2.update(_det(t), t).score
    for i in range(gap):
        sc2.update(None, 5 + i)
    worse_raw_cold = _cold_start_raw(scorer_params, cx=0.95, cy=0.95)
    out2 = sc2.update(_det(5 + gap, cx=0.95, cy=0.95), 5 + gap)
    # Continuous: the blended EMA sits between the worse raw and the (higher) held value,
    # strictly above the cold-start raw_0 it would have snapped to if it had re-seeded.
    assert out2.status is ScorerStatus.tracking
    assert worse_raw_cold < out2.score < held2
    assert out2.score == pytest.approx(ALPHA * worse_raw_cold + (1.0 - ALPHA) * held2)


def _cold_start_raw(params, *, cx: float, cy: float) -> float:
    """The raw_0 a FRESH (cold-start) CameraScorer would emit for a single detection.

    Used to prove the recovery EMA does NOT snap to this value (no re-seed) but blends from
    the held EMA instead.
    """
    fresh = _scorer(params)
    return fresh.update(_det(0, cx=cx, cy=cy), 0).score


# --- MultiCamScorer fan-out (FRM-05 must-have) -------------------------------------- #

_CAM_A = "cam_a"
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
    """Two cameras, each with a single full-frame neutral zone (multiplier == 1.0)."""
    return [
        Camera(
            id=cid,
            role=Role.main_wide,
            obs_scene="WIDE",
            is_safe=True,
            zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
        )
        for cid in (_CAM_A, _CAM_B)
    ]


def _multi(params) -> MultiCamScorer:
    return MultiCamScorer(
        _two_cameras(),
        params,
        {Role.main_wide: {"all": 1.0}},
        alpha=ALPHA,
        lead_gain=0.0,
        ttl_ticks=TTL_TICKS,
    )


def test_multicam_fanout_one_score_per_camera(scorer_params) -> None:
    """update(dets_by_cam, tick) returns one CameraScore per camera, in camera order."""
    multi = _multi(scorer_params)
    dets = {
        _CAM_A: DetectionSignal(0, _CAM_A, 0.5, 0.5, 0.30, 0.30, 0.7, 1),
        _CAM_B: DetectionSignal(0, _CAM_B, 0.5, 0.5, 0.30, 0.30, 0.7, 1),
    }
    out = multi.update(dets, 0)
    assert [cs.cam_id for cs in out] == [_CAM_A, _CAM_B]  # deterministic camera order.
    assert all(cs.status is ScorerStatus.tracking for cs in out)
    assert all(cs.score > 0.0 for cs in out)


def test_multicam_missing_camera_coasts(scorer_params) -> None:
    """A camera absent from dets_by_cam coasts (never KeyError) while the present one tracks."""
    multi = _multi(scorer_params)

    # Both present for a few ticks → both have a held EMA.
    for t in range(5):
        multi.update(
            {
                _CAM_A: DetectionSignal(t, _CAM_A, 0.5, 0.5, 0.30, 0.30, 0.7, 1),
                _CAM_B: DetectionSignal(t, _CAM_B, 0.5, 0.5, 0.30, 0.30, 0.7, 1),
            },
            t,
        )

    # Now cam_b is missing entirely from the map: it must coast (held, not raise), while
    # cam_a keeps tracking. ttl_ticks=4 > 0 after one decrement → coasting.
    out = multi.update(
        {_CAM_A: DetectionSignal(5, _CAM_A, 0.5, 0.5, 0.30, 0.30, 0.7, 1)}, 5
    )
    by_cam = {cs.cam_id: cs for cs in out}
    assert by_cam[_CAM_A].status is ScorerStatus.tracking
    assert by_cam[_CAM_B].status is ScorerStatus.coasting
    assert by_cam[_CAM_B].score > 0.0  # held — missing camera never collapsed to 0.


def test_ttl_ticks_from_seconds_ceils_positive() -> None:
    """ttl_ticks_from_seconds ceils to a positive int (>= 1 for any positive ttl_seconds)."""
    assert ttl_ticks_from_seconds(0.4, 30.0) == 12  # ceil(12.0)
    assert ttl_ticks_from_seconds(0.41, 30.0) == 13  # ceil(12.3) → 13
    assert ttl_ticks_from_seconds(0.001, 30.0) == 1  # ceil(0.03) → at least 1 coast tick
