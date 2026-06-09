"""Deterministic, seedable synthetic score-stream generator (TST-02).

A ``score_stream`` emits a reproducible per-camera score timeline for one of four
named scenarios that exercise the Phase-3 FSM's hard cases:

  ping_pong : two cameras alternate as leader over time (the FSM must NOT chase this)
  tie       : two cameras hold near-equal scores (tiebreaker / no-oscillation case)
  dropout   : the leader's score collapses for a window then is absent (coast/TTL case)
  recovery  : a dropped camera's score returns after a gap (rejoin case)

Determinism contract (RESEARCH.md Pattern 4 + Pitfall 3):
  * the injected ``numpy.random.Generator`` is the ONLY source of randomness;
  * the module never seeds or calls the legacy global numpy RNG;
  * no wall-clock is read — ``t`` is the synthetic tick index.
  Same seed -> byte-identical ``list[ScoreSample]``; different seed -> different.

Imports only ``numpy`` + stdlib ``dataclasses`` (the 01-01 import-smoke test guards
this surface, so any later phase can import it with no GPU/NDI runtime).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["ScoreSample", "score_stream", "SCENARIOS"]

# The scenario vocabulary (matches DEC-07 / VALIDATION.md and the ROADMAP Phase-3 plans).
SCENARIOS: tuple[str, ...] = ("ping_pong", "tie", "dropout", "recovery")


@dataclass(frozen=True)
class ScoreSample:
    """One per-camera score reading at a synthetic tick.

    Frozen (hashable + comparable) so ``==`` over two ``list[ScoreSample]`` is the
    determinism assertion the downstream tests rely on. ``score`` is normalized [0..1].
    """

    tick: int
    cam_id: str
    score: float


def _scenario_base(scenario: str, t: int, n_cams: int, n_ticks: int) -> np.ndarray:
    """Pure deterministic per-camera base curve at tick ``t`` — uses NO rng.

    Returns an array of length ``n_cams`` of base scores in [0..1]. Jitter (from the
    injected rng) is added by the caller; this function is a function of the indices
    ``t`` / camera position / ``n_ticks`` only, so it never introduces nondeterminism.
    """
    # Guard against a divide-by-zero on the phase term; one tick is degenerate but valid.
    span = max(n_ticks - 1, 1)
    phase = t / span  # 0.0 .. 1.0 across the run

    base = np.full(n_cams, 0.5, dtype=np.float64)

    if scenario == "ping_pong":
        # Two (or more) cameras swap the lead on a slow square-ish wave. Camera 0 and
        # camera 1 are in antiphase so the argmax flips across the run; extra cameras
        # sit at a low constant so they never lead.
        period = max(n_ticks // 4, 2)  # ~4 alternations across the run
        leader_is_zero = (t // period) % 2 == 0
        hi, lo = 0.85, 0.35
        if n_cams >= 1:
            base[0] = hi if leader_is_zero else lo
        if n_cams >= 2:
            base[1] = lo if leader_is_zero else hi
        for i in range(2, n_cams):
            base[i] = 0.2  # spectators — never the leader

    elif scenario == "tie":
        # Both lead cameras hold a near-equal, gently drifting score; the per-camera
        # MEANS over the run are within a small epsilon (no stable leader).
        center = 0.55 + 0.05 * np.sin(2.0 * np.pi * phase)
        for i in range(n_cams):
            # A tiny per-camera offset that integrates to ~0 over the run (cos around 0).
            base[i] = center + 0.01 * np.cos(2.0 * np.pi * phase + i)

    elif scenario == "dropout":
        # The leader (cam 0) holds high, then its score collapses to ~0 for a window
        # in the middle of the run (coast / TTL case), then is absent through the end.
        drop_start = n_ticks // 3
        if n_cams >= 1:
            base[0] = 0.85 if t < drop_start else 0.0
        for i in range(1, n_cams):
            base[i] = 0.45  # the others hold a steady mid score

    elif scenario == "recovery":
        # A camera (cam 0) is present, goes absent for a gap, then RETURNS (rejoin).
        gap_start = n_ticks // 3
        gap_end = (2 * n_ticks) // 3
        if n_cams >= 1:
            base[0] = 0.0 if gap_start <= t < gap_end else 0.8
        for i in range(1, n_cams):
            base[i] = 0.45

    else:
        raise ValueError(
            f"unknown scenario {scenario!r}; expected one of {SCENARIOS}"
        )

    return np.clip(base, 0.0, 1.0)


def score_stream(
    rng: np.random.Generator,
    scenario: str,
    cam_ids: list[str],
    n_ticks: int,
    noise: float = 0.02,
) -> list[ScoreSample]:
    """Emit a reproducible per-camera score stream.

    Args:
        rng: an INJECTED ``numpy.random.Generator`` (the only randomness source).
        scenario: one of ``ping_pong`` | ``tie`` | ``dropout`` | ``recovery``.
        cam_ids: camera identifiers, in a fixed order.
        n_ticks: number of synthetic ticks (time runs 0..n_ticks-1).
        noise: stddev of the Gaussian jitter added per camera per tick.

    Returns:
        ``list[ScoreSample]`` of length ``n_ticks * len(cam_ids)``, ordered by
        (tick, camera). Same ``rng`` seed -> identical list.

    Raises:
        ValueError: on an unknown scenario name.
    """
    # Validate the scenario up front (so an empty cam list still fails fast on a typo).
    if scenario not in SCENARIOS:
        raise ValueError(
            f"unknown scenario {scenario!r}; expected one of {SCENARIOS}"
        )

    n_cams = len(cam_ids)
    out: list[ScoreSample] = []
    for t in range(n_ticks):
        base = _scenario_base(scenario, t, n_cams, n_ticks)  # pure, no rng
        jitter = rng.normal(0.0, noise, size=n_cams)         # injected rng only
        for cam, b, j in zip(cam_ids, base, jitter):
            out.append(ScoreSample(t, cam, float(np.clip(b + j, 0.0, 1.0))))
    return out
