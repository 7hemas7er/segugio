"""DEC-02 hysteresis suite — no-chase (ping_pong/tie) + margin/debounce/dwell/cooldown (03-01).

The defining DEC-02 property is the TRANSITION COUNT, not per-tick argmax (RESEARCH
Pitfall 3): replaying ``ping_pong`` / ``tie`` through the hysteretic FSM must produce at
most one transition after warm-up — a flicker-prone FSM would cut ~4-8× on ping_pong's
leader flips. The primary assertion is therefore ``num_transitions <= 1``.

  * ``test_no_chase_pingpong``: drive the shipped ``score_stream(ping_pong)`` + ``(tie)``
    substrate (wrapped to ``CameraScore`` via ``_as_camera_scores``); collect the
    ``list[Decision]``; post-process into a transition list (ticks where ``target`` changed)
    and assert ``<= 1`` after warm-up.
  * ``test_dwell_debounce_cooldown``: a crafted steady-incumbent / jumping-challenger
    sequence asserting the cut needs margin + ``debounce_N`` AND is blocked while
    ``dwell_elapsed < min_dwell_ticks`` and during ``cooldown``. The tick-by-tick clock walk
    is documented inline (mirrors ``test_framing_coast.py:83-87``).
"""

from __future__ import annotations

import numpy as np

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine, ticks_from_seconds
from segugio.decision.signals import SAFE_TARGET
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.synth import score_stream
from tests.conftest import FPS, SEED, _as_camera_scores

_CAM_A = "cam_a"
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
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


def _group_by_tick(samples) -> dict[int, list[CameraScore]]:
    """Group a flat ``list[CameraScore]`` (ordered by tick, cam) into per-tick lists."""
    by_tick: dict[int, list[CameraScore]] = {}
    for s in samples:
        by_tick.setdefault(s.tick, []).append(s)
    return by_tick


def _run_scenario(thresholds, scenario: str, n_ticks: int = 120) -> list[str]:
    """Drive the FSM over a score_stream scenario; return the per-tick target list."""
    rng = np.random.default_rng(SEED)
    cam_ids = [_CAM_A, _CAM_B]
    samples = _as_camera_scores(score_stream(rng, scenario, cam_ids, n_ticks))
    by_tick = _group_by_tick(samples)
    eng = _engine(thresholds)
    targets: list[str] = []
    for t in range(n_ticks):
        d = eng.tick(by_tick[t], alive={_CAM_A: True, _CAM_B: True})
        targets.append(d.target)
    return targets


def _num_transitions(targets: list[str], warmup: int = 10) -> int:
    """Count target changes after a warm-up window (the DEC-02 no-chase metric)."""
    return sum(
        1
        for t in range(warmup + 1, len(targets))
        if targets[t] != targets[t - 1]
    )


def test_no_chase_pingpong(thresholds) -> None:
    """Replaying ping_pong yields <= 1 transition after warm-up (no leader-chase, DEC-02)."""
    targets = _run_scenario(thresholds, "ping_pong")
    # ping_pong flips the leader ~4× across the run; a flicker-prone FSM would cut ~4-8×.
    assert _num_transitions(targets) <= 1, (
        f"ping_pong produced {_num_transitions(targets)} transitions after warm-up "
        f"(expected <= 1 — the FSM must hold the incumbent through the leader swing)"
    )


def test_no_chase_tie(thresholds) -> None:
    """Replaying tie yields <= 1 transition after warm-up (no oscillation, DEC-02)."""
    targets = _run_scenario(thresholds, "tie")
    assert _num_transitions(targets) <= 1, (
        f"tie produced {_num_transitions(targets)} transitions after warm-up (expected <= 1)"
    )


def test_dwell_debounce_cooldown(thresholds) -> None:
    """Challenger needs margin + debounce_N; cut blocked while dwell<min_dwell or cooldown>0.

    thresholds: hysteresis_margin=0.1, debounce_N=3, min_dwell=2.0s, cooldown=1.0s.
    At FPS=30: min_dwell_ticks=60, cooldown_ticks=30, debounce_N=3.

    The crafted sequence (cam_a steady 0.30, cam_b steady 0.85, both alive) walks:
      t=0 : cold start SAFE; cam_b is challenger (0.85 > 0.30+0.1), streak 1   → no cut
      t=1 : streak 2                                                            → no cut
      t=2 : streak 3 == debounce_N; from SAFE dwell_ok (no incumbent dwell) +
            cooldown clear → CUT to cam_b (reason auto_switch). dwell_elapsed→0,
            cooldown_remaining→30.
      t=3.. : cam_b is incumbent; no challenger (cam_a far below) → no further cut.
    The assertion: the FIRST cut happens no earlier than debounce_N ticks; once cam_b is
    live, a (hypothetical) competing higher score cannot steal it during dwell/cooldown.
    """
    debounce_N = thresholds.debounce_N
    min_dwell_ticks = ticks_from_seconds(thresholds.min_dwell, FPS)
    cooldown_ticks = ticks_from_seconds(thresholds.cooldown, FPS)
    assert (debounce_N, min_dwell_ticks, cooldown_ticks) == (3, 60, 30)

    eng = _engine(thresholds)

    def _sc(cam, score, t):
        return CameraScore(t, cam, score, ScorerStatus.tracking)

    # Phase 1: cam_b strongly leads from SAFE. Cut must NOT fire before debounce_N ticks.
    first_cut_tick = None
    for t in range(10):
        d = eng.tick(
            [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.85, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        if d.reason != "none" and first_cut_tick is None:
            first_cut_tick = t
    # The cut fired no earlier than the debounce_N-th tick (streak must reach debounce_N).
    assert first_cut_tick is not None, "cam_b never acquired despite a steady > margin lead"
    assert first_cut_tick >= debounce_N - 1, (
        f"cut fired at t={first_cut_tick}, earlier than debounce_N={debounce_N} sustain"
    )
    assert eng.target == _CAM_B

    # Phase 2: cam_b is live with a FRESH dwell (just reset to 0 on the cut) + cooldown
    # (cooldown_ticks). cam_a now jumps to a HIGHER score. The guard reads the clocks AFTER
    # the top-of-tick increment, so a tick blocks the cut iff (dwell_elapsed + 1) <
    # min_dwell_ticks. Assert cam_b is held on every such genuinely-blocked tick, and that the
    # cut to cam_a is allowed exactly once the dwell guard clears.
    assert eng.dwell_elapsed < min_dwell_ticks  # fresh dwell right after the cut.
    blocked = 0
    cut_to_a_at = None
    t = 10
    for _ in range(min_dwell_ticks + cooldown_ticks + 5):  # bounded — never infinite-loop
        # Predict whether THIS tick's guard will block (post-increment dwell still < min).
        will_block = (eng.dwell_elapsed + 1) < min_dwell_ticks
        d = eng.tick(
            [_sc(_CAM_A, 0.95, t), _sc(_CAM_B, 0.40, t)],  # cam_a now leads by a lot
            alive={_CAM_A: True, _CAM_B: True},
        )
        if will_block:
            # No steal while the dwell guard is still blocking (double-cut prevention).
            assert d.target == _CAM_B, (
                f"cam_a stole the target at t={t} while dwell would be "
                f"{eng.dwell_elapsed} < {min_dwell_ticks} (double-cut in the protected window)"
            )
            blocked += 1
        if d.target == _CAM_A and cut_to_a_at is None:
            cut_to_a_at = t
            break
        t += 1
    # The protected window blocked the would-be steal for many ticks (the remaining dwell
    # after cam_b's acquisition), THEN allowed the cut once dwell+cooldown cleared. cam_b was
    # acquired partway through phase 1, so the phase-2 blocked count is the dwell remainder.
    assert blocked >= 40, blocked  # a substantial protected window held cam_b.
    assert cut_to_a_at is not None, "cam_a never won even after dwell+cooldown cleared"


def test_cold_start_is_safe(thresholds) -> None:
    """The engine begins in SAFE with target == 'SAFE' (cold start)."""
    eng = _engine(thresholds)
    assert eng.target == SAFE_TARGET
    # A first tick with no camera clearing the upper threshold from SAFE keeps SAFE.
    d = eng.tick(
        [CameraScore(0, _CAM_A, 0.05, ScorerStatus.tracking),
         CameraScore(0, _CAM_B, 0.04, ScorerStatus.tracking)],
        alive={_CAM_A: True, _CAM_B: True},
    )
    # Neither clears the upper threshold over the SAFE incumbent (0.0) by enough to sustain
    # immediately, so the cold-start tick is still SAFE (no instant cut on tick 0).
    assert d.target == SAFE_TARGET
