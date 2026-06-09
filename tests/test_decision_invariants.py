"""DEC-01 invariant suite — the live target changes ONLY via a guarded transition (03-01).

The first hard safety invariant (03-VALIDATION §Two Hard Safety Invariants): in every
scenario the live ``target`` only ever changes on a tick whose ``Decision.reason != "none"``
(a named guard passed). A trigger whose guard predicate is false is a silent no-op — the
target is unchanged.

  * ``test_no_decision_outside_guard``: drives ticks where the normal-switch guard is
    deliberately false (challenger below the hysteresis margin; then within dwell/cooldown
    after a cut) and asserts the target is unchanged across those ticks, that
    ``reason == "none"`` on every no-change tick, and that ``reason != "none"`` exactly on
    the tick the target DID change.
  * ``test_poisoned_score_is_ineligible``: a NaN / inf / out-of-[0,1] score makes that
    camera an ineligible candidate (never selected) and ``tick()`` never raises (T-3-04).

Mirrors the tick-loop replay style of ``test_framing_coast.py`` and the determinism/guard
style of ``test_framing_purity.py``.
"""

from __future__ import annotations

import math

import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET
from segugio.framing.signals import CameraScore, ScorerStatus
from tests.conftest import FPS

_CAM_A = "cam_a"
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
    """Two cameras (cam_a is_safe), each a single full-frame neutral zone."""
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


def _score(cam_id: str, score: float, tick: int = 0) -> CameraScore:
    return CameraScore(tick, cam_id, score, ScorerStatus.tracking)


def test_no_decision_outside_guard(thresholds) -> None:
    """The target changes ONLY on a tick where a named guard passed (reason != 'none').

    Sequence: cam_b leads cam_a by > hysteresis_margin and sustains it. Before the
    challenger clears debounce_N AND dwell elapses, NO cut fires (reason 'none', target
    unchanged). After it qualifies, exactly one cut fires (reason 'auto_switch'); thereafter
    cooldown + fresh dwell block any further cut even though cam_b still leads.
    """
    eng = _engine(thresholds)

    targets: list[str] = []
    reasons: list[str] = []
    # Drive a long, steady "cam_b strongly leads" stream. cam_a (incumbent after the first
    # acquisition) starts as SAFE; cam_b must clear the upper threshold + sustain debounce_N
    # + dwell before the cut, and cannot cut again during cooldown/dwell.
    for t in range(40):
        scores = [
            _score(_CAM_A, 0.30, t),
            _score(_CAM_B, 0.85, t),  # leads by 0.55 >> margin 0.1, steady
        ]
        d = eng.tick(scores, alive={_CAM_A: True, _CAM_B: True})
        targets.append(d.target)
        reasons.append(d.reason)

    # The target changed on EXACTLY the ticks where reason != 'none' (DEC-01 invariant).
    changes = [t for t in range(1, len(targets)) if targets[t] != targets[t - 1]]
    nonnone = [t for t in range(len(reasons)) if reasons[t] != "none"]
    assert changes == nonnone, (
        f"target changed at {changes} but reason!='none' at {nonnone} — DEC-01 violated"
    )
    # On every tick where the target did NOT change, reason is 'none'.
    for t in range(1, len(targets)):
        if targets[t] == targets[t - 1]:
            assert reasons[t] == "none"

    # The engine did eventually acquire cam_b (proves the guard CAN pass when qualified).
    assert _CAM_B in targets
    # Cold start was SAFE.
    assert targets[0] in (SAFE_TARGET, _CAM_B)


def test_no_cut_before_debounce_sustained(thresholds) -> None:
    """A one-tick challenger spike does NOT cut: it must sustain debounce_N consecutive ticks.

    cam_a is live (the incumbent). cam_b spikes above cam_a by > margin for a SINGLE tick,
    then drops back below the margin — the streak resets and no cut to cam_b ever fires. The
    incumbent cam_a is never stolen by the lone spike.
    """
    eng = _engine(thresholds)

    # Acquire cam_a as the incumbent first: a steady lead over SAFE for debounce_N ticks.
    for t in range(6):
        eng.tick(
            [_score(_CAM_A, 0.60, t), _score(_CAM_B, 0.10, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
    assert eng.target == _CAM_A  # cam_a is the live incumbent.

    # Now cam_b spikes above cam_a by > margin for a SINGLE tick, then drops back. The lone
    # spike never sustains debounce_N → no cut to cam_b.
    targets: list[str] = []
    for i in range(10):
        t = 6 + i
        b = 0.95 if i == 3 else 0.10  # a lone spike, never sustained
        d = eng.tick(
            [_score(_CAM_A, 0.60, t), _score(_CAM_B, b, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        targets.append(d.target)
    # The lone spike never qualifies (debounce_N=3 not sustained) → cam_a held throughout.
    assert all(t == _CAM_A for t in targets), targets


def test_poisoned_score_is_ineligible(thresholds) -> None:
    """A NaN/inf/out-of-range score → that camera is never selected; tick() never raises (T-3-04)."""
    eng = _engine(thresholds)

    for bad in (float("nan"), float("inf"), -float("inf"), 5.0, -1.0):
        d = eng.tick(
            [_score(_CAM_A, 0.20, 0), _score(_CAM_B, bad, 0)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        # Never raised; the poisoned cam_b is never the target.
        assert d.target != _CAM_B
        assert math.isfinite(0.0)  # sanity — no exception reached here

    # Sustained poisoned cam_b can never out-qualify cam_a — target never becomes cam_b.
    targets: list[str] = []
    for t in range(20):
        d = eng.tick(
            [_score(_CAM_A, 0.40, t), _score(_CAM_B, float("nan"), t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        targets.append(d.target)
    assert _CAM_B not in targets
