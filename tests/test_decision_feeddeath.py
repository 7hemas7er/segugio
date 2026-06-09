"""DEC-06 feed-death suite — a dead feed is never live nor challenger; emergency cut.

The catastrophic-failure guard the whole robustness constraint ("nessun crash ammesso",
SAFE fallback) hinges on. Two hard properties (03-VALIDATION §Two Hard Safety Invariants):

  * a camera with ``alive == False`` is NEVER the emitted ``target`` and NEVER the
    ``challenger_id`` — it is filtered out before the argmax;
  * when the LIVE camera's feed dies, the FSM emergency-cuts THIS tick to the
    highest-scoring alive camera (or ``"SAFE"`` if none), bypassing ``min_dwell`` and
    ``cooldown``; the new target then receives NORMAL dwell/cooldown protection (a
    competing higher score one tick later does not steal it — D-01).

The hard invariant asserted in EVERY feed-death scenario:
``alive[decision.target] is True OR decision.target == "SAFE"`` for all ticks.

Mirrors the tick-loop replay style of ``test_decision_hysteresis.py`` /
``test_framing_coast.py`` and drives the shipped ``score_stream`` + ``feed_death`` substrate.
"""

from __future__ import annotations

import numpy as np

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.synth import feed_death, score_stream
from tests.conftest import FPS, SEED, _as_camera_scores

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


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _group_alive(events) -> dict[int, dict[str, bool]]:
    """Group a flat ``list[FeedEvent]`` into a per-tick ``{cam_id: alive}`` map."""
    by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive
    return by_tick


def _acquire(eng: DecisionEngine, cam: str, *, other: str, t0: int = 0) -> int:
    """Drive a steady lead until ``cam`` is the live incumbent; return the next free tick."""
    t = t0
    for _ in range(200):
        eng.tick(
            [_sc(cam, 0.85, t), _sc(other, 0.10, t)],
            alive={cam: True, other: True},
        )
        t += 1
        if eng.target == cam:
            break
    assert eng.target == cam, f"failed to acquire {cam} as incumbent"
    return t


def test_dead_never_live_nor_challenger(thresholds) -> None:
    """In every feed-death scenario the target is never a dead cam, nor a dead challenger.

    Drives the ping_pong score stream (both cameras swing the lead) together with a
    feed-death timeline that kills the eventual live camera mid-run. The hard DEC-06
    invariant must hold on EVERY tick: ``alive[target] is True OR target == "SAFE"``.
    A dead camera must also never appear as ``challenger_id``.
    """
    n_ticks = 120
    cam_ids = [_CAM_A, _CAM_B]
    rng = np.random.default_rng(SEED)
    samples = _as_camera_scores(score_stream(rng, "ping_pong", cam_ids, n_ticks))
    by_tick_scores: dict[int, list[CameraScore]] = {}
    for s in samples:
        by_tick_scores.setdefault(s.tick, []).append(s)

    # Kill cam_b at tick 50, never recovers; cam_a stays alive the whole run.
    events = feed_death(
        np.random.default_rng(SEED), cam_ids, n_ticks, death_at={_CAM_B: 50}
    )
    alive_by_tick = _group_alive(events)

    eng = _engine(thresholds)
    for t in range(n_ticks):
        alive = alive_by_tick[t]
        d = eng.tick(by_tick_scores[t], alive=alive)
        # HARD invariant: never air a dead feed.
        assert d.target == SAFE_TARGET or alive.get(d.target, False) is True, (
            f"t={t}: aired target {d.target!r} which is not alive (alive={alive})"
        )
        # A dead camera is never the registered challenger.
        if eng.challenger_id is not None:
            assert alive.get(eng.challenger_id, False) is True, (
                f"t={t}: dead camera {eng.challenger_id!r} registered as challenger"
            )


def test_live_feed_death_emergency_cuts_immediately(thresholds) -> None:
    """When the live feed dies, the FSM cuts THIS tick to the best-alive cam (dwell bypassed).

    Acquire cam_b as the live incumbent (fresh dwell + cooldown). On the tick cam_b's feed
    goes dead, the emergency cut fires immediately — even though cam_b's dwell has NOT
    elapsed and cooldown is NOT clear — to cam_a (the only alive camera). reason ==
    "feed_emergency".
    """
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)
    assert eng.target == _CAM_B
    # cam_b's dwell/cooldown are FRESH (just acquired) — a normal cut would be blocked.
    assert eng.dwell_elapsed < eng.min_dwell_ticks
    assert eng.cooldown_remaining > 0

    # cam_b's feed dies THIS tick. Even with cam_a only modestly scored, the emergency cut
    # must fire immediately (a dead feed is never held on air).
    d = eng.tick(
        [_sc(_CAM_A, 0.40, t), _sc(_CAM_B, 0.95, t)],  # cam_b higher but DEAD
        alive={_CAM_A: True, _CAM_B: False},
    )
    assert d.target == _CAM_A, "emergency cut did not move off the dead live feed"
    assert d.reason == "feed_emergency"


def test_emergency_target_is_normally_protected(thresholds) -> None:
    """After the emergency cut, the new target gets normal dwell/cooldown (no instant steal).

    cam_b dies → emergency cut to cam_a. On the VERY NEXT tick a competing higher cam_b
    score (cam_b now recovered) must NOT steal the target: cam_a was just acquired with a
    fresh dwell + cooldown, so the normal-switch guard blocks the cut.
    """
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)

    # Emergency cut off the dying cam_b to cam_a.
    eng.tick(
        [_sc(_CAM_A, 0.40, t), _sc(_CAM_B, 0.95, t)],
        alive={_CAM_A: True, _CAM_B: False},
    )
    assert eng.target == _CAM_A
    # The new target's clocks were reset (normal protection going forward).
    assert eng.dwell_elapsed == 0
    assert eng.cooldown_remaining == eng.cooldown_ticks
    t += 1

    # cam_b recovers and out-scores cam_a by a lot for several ticks. It must NOT steal cam_a
    # during the fresh dwell window (the emergency target is normally protected — D-01).
    for _ in range(min(eng.min_dwell_ticks, eng.cooldown_ticks)):
        d = eng.tick(
            [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.99, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        assert d.target == _CAM_A, (
            f"t={t}: cam_b stole the emergency target during its protected dwell window"
        )
        t += 1


def test_all_cameras_dead_cuts_to_safe(thresholds) -> None:
    """When no camera is alive, the emergency cut routes to the SAFE sentinel."""
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)
    assert eng.target == _CAM_B

    # BOTH feeds die — there is no alive candidate, so the target must become SAFE.
    d = eng.tick(
        [_sc(_CAM_A, 0.50, t), _sc(_CAM_B, 0.60, t)],
        alive={_CAM_A: False, _CAM_B: False},
    )
    assert d.target == SAFE_TARGET
    assert d.reason == "feed_emergency"


def test_recovery_out_of_safe_reacquires_promptly(thresholds) -> None:
    """A total blackout → SAFE, then a single camera recovers → re-acquisition fires PROMPTLY.

    Regression for the SAFE-carries-a-spurious-cooldown bug (CR-01): SAFE is a fallback, not
    an incumbent to protect, so — exactly as it carries no dwell — it must carry NO cooldown.
    After a total blackout drops the FSM to SAFE, the moment a healthy camera recovers and
    sustains the debounce window it must be aired within ~1 tick of qualifying, NOT held off
    the air for the full cooldown window (~1s @ 30fps) while the show lingers on the SAFE/wide
    scene. The bug aired SAFE for ~cooldown_ticks-1 extra ticks after recovery.
    """
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)
    assert eng.target == _CAM_B

    # Total blackout → SAFE (no alive candidate). Before the fix this also armed a fresh
    # cooldown_ticks countdown on the SAFE target.
    d = eng.tick(
        [_sc(_CAM_A, 0.50, t), _sc(_CAM_B, 0.60, t)],
        alive={_CAM_A: False, _CAM_B: False},
    )
    assert d.target == SAFE_TARGET
    t += 1

    # cam_a recovers at a strong, steady score. It must qualify (clear the margin from the
    # SAFE 0.0 incumbent, sustain debounce_N) and be aired PROMPTLY — within one tick of
    # clearing debounce, not delayed until the spurious SAFE cooldown drains.
    reacquired_at = None
    for i in range(eng.cooldown_ticks + eng.debounce_N + 5):
        d = eng.tick(
            [_sc(_CAM_A, 0.95, t), _sc(_CAM_B, 0.05, t)],
            alive={_CAM_A: True, _CAM_B: False},
        )
        if d.target == _CAM_A and reacquired_at is None:
            reacquired_at = i
            assert d.reason == "auto_switch"
        t += 1

    assert reacquired_at is not None, "never re-acquired a recovered camera out of SAFE"
    # Re-acquisition must fire as soon as the challenger clears debounce_N — NOT be blocked
    # for the (buggy) spurious SAFE cooldown. A correct engine fires the cut the tick the
    # streak reaches debounce_N (i == debounce_N - 1, since the streak counts from 1 on the
    # first qualifying tick). The bug delayed it to ~cooldown_ticks - 1 (~1s of wasted SAFE
    # airtime). Require it to land within one tick of clearing debounce — never near the
    # cooldown horizon.
    prompt_window = eng.debounce_N + 1
    assert reacquired_at < prompt_window, (
        f"re-acquisition out of SAFE was delayed to i={reacquired_at} "
        f"(expected < {prompt_window}, debounce_N={eng.debounce_N}, "
        f"cooldown_ticks={eng.cooldown_ticks}) — SAFE carried a spurious cooldown that "
        f"held the show on SAFE for ~1s after recovery (CR-01)"
    )
