"""TST-02 — synthetic generator suite: determinism, scenario shapes, feed-death.

Proves the Phase-1 determinism contract the whole synthetic substrate rests on:

  * byte-reproducibility per seed (same seed -> identical list) for BOTH generators,
    and different seed -> different output;
  * structural shape of all four score scenarios (ping_pong / tie / dropout / recovery);
  * correct feed-death + recovery liveness timelines (the watchdog's test target);
  * an unknown scenario fails fast with ``ValueError``.

The test names embed the ``-k`` selectors the plan's verify commands use:
``determinism`` / ``shape`` / ``feeddeath`` / ``bounds``. Determinism cases build the
RNG explicitly via ``np.random.default_rng(seed)`` (so the seed is visible) and at
least one case uses the shared ``seeded_rng`` conftest fixture.
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.synth import (
    SCENARIOS,
    FeedEvent,
    ScoreSample,
    feed_death,
    score_stream,
)

CAMS = ["a", "b"]
N_TICKS = 120


# --------------------------------------------------------------------------- #
# Determinism — same seed identical, different seed differs (both generators)  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_determinism_score_stream_same_seed_identical(scenario: str) -> None:
    a = score_stream(np.random.default_rng(7), scenario, CAMS, N_TICKS)
    b = score_stream(np.random.default_rng(7), scenario, CAMS, N_TICKS)
    assert a == b  # byte-identical list of frozen ScoreSamples


def test_determinism_score_stream_different_seed_differs() -> None:
    a = score_stream(np.random.default_rng(7), "ping_pong", CAMS, N_TICKS)
    c = score_stream(np.random.default_rng(8), "ping_pong", CAMS, N_TICKS)
    assert a != c


def test_determinism_score_stream_with_seeded_rng_fixture(
    seeded_rng: np.random.Generator,
) -> None:
    # One case driven by the shared conftest fixture: re-seeding to the same SEED
    # reproduces it exactly (the fixture's contract).
    from tests.conftest import SEED

    a = score_stream(seeded_rng, "tie", CAMS, 40)
    b = score_stream(np.random.default_rng(SEED), "tie", CAMS, 40)
    assert a == b


def test_determinism_feed_death_same_seed_identical() -> None:
    fa = feed_death(np.random.default_rng(3), CAMS, 30, death_at={"a": 5}, recover_after=4)
    fb = feed_death(np.random.default_rng(3), CAMS, 30, death_at={"a": 5}, recover_after=4)
    assert fa == fb


def test_determinism_feed_death_inputs_drive_output() -> None:
    # The explicit-death path is fully deterministic regardless of the rng seed.
    f_seed3 = feed_death(np.random.default_rng(3), CAMS, 20, death_at={"a": 5})
    f_seed9 = feed_death(np.random.default_rng(9), CAMS, 20, death_at={"a": 5})
    assert f_seed3 == f_seed9  # rng must not perturb the explicit timeline
    # ...but different inputs must produce different output.
    f_other = feed_death(np.random.default_rng(3), CAMS, 20, death_at={"a": 8})
    assert f_seed3 != f_other


# --------------------------------------------------------------------------- #
# Bounds / structure — length, tick coverage, score range, dataclass identity  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_bounds_scores_in_unit_interval(scenario: str) -> None:
    out = score_stream(np.random.default_rng(1), scenario, CAMS, N_TICKS)
    assert all(0.0 <= s.score <= 1.0 for s in out)


def test_bounds_length_and_tick_coverage() -> None:
    out = score_stream(np.random.default_rng(1), "tie", CAMS, N_TICKS)
    assert len(out) == N_TICKS * len(CAMS)
    assert all(isinstance(s, ScoreSample) for s in out)
    # Every tick 0..N-1 present for every camera.
    for cam in CAMS:
        ticks = sorted(s.tick for s in out if s.cam_id == cam)
        assert ticks == list(range(N_TICKS))


def test_bounds_frozen_sample_is_hashable_and_comparable() -> None:
    s1 = ScoreSample(0, "a", 0.5)
    s2 = ScoreSample(0, "a", 0.5)
    assert s1 == s2 and hash(s1) == hash(s2)
    assert {s1, s2} == {s1}  # frozen dataclasses dedupe in a set


# --------------------------------------------------------------------------- #
# Scenario shapes — each scenario structurally matches its FSM purpose          #
# --------------------------------------------------------------------------- #


def _per_cam_series(out: list[ScoreSample], cam: str) -> np.ndarray:
    return np.array([s.score for s in out if s.cam_id == cam], dtype=np.float64)


def test_shape_ping_pong_leader_alternates() -> None:
    # The argmax (leader) camera must change across the run — the FSM must not chase.
    out = score_stream(np.random.default_rng(5), "ping_pong", CAMS, N_TICKS)
    a = _per_cam_series(out, "a")
    b = _per_cam_series(out, "b")
    leader = np.where(a >= b, 0, 1)  # 0 == cam a leads, 1 == cam b leads
    assert leader.min() == 0 and leader.max() == 1  # both lead at some point
    # And the leadership actually flips (more than one transition).
    flips = int(np.sum(leader[1:] != leader[:-1]))
    assert flips >= 2


def test_shape_tie_means_near_equal() -> None:
    out = score_stream(np.random.default_rng(5), "tie", CAMS, N_TICKS)
    mean_a = float(_per_cam_series(out, "a").mean())
    mean_b = float(_per_cam_series(out, "b").mean())
    assert abs(mean_a - mean_b) < 0.05  # near-equal — no stable leader


def test_shape_dropout_leader_collapses_window() -> None:
    out = score_stream(np.random.default_rng(5), "dropout", CAMS, N_TICKS)
    a = _per_cam_series(out, "a")  # cam a is the leader that collapses
    drop_start = N_TICKS // 3
    assert a[: drop_start].mean() > 0.5          # high before the dropout
    assert a[drop_start:].max() < 0.2            # collapsed/absent after (jitter only)


def test_shape_recovery_gap_then_return() -> None:
    out = score_stream(np.random.default_rng(5), "recovery", CAMS, N_TICKS)
    a = _per_cam_series(out, "a")
    gap_start, gap_end = N_TICKS // 3, (2 * N_TICKS) // 3
    assert a[:gap_start].mean() > 0.5            # present before the gap
    assert a[gap_start:gap_end].max() < 0.2      # absent during the gap
    assert a[gap_end:].mean() > 0.5              # returned after the gap (rejoin)


def test_shape_unknown_scenario_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        score_stream(np.random.default_rng(0), "spinning", CAMS, 10)


# --------------------------------------------------------------------------- #
# Feed-death — exact alive/dead tick boundaries (death only + death+recovery)   #
# --------------------------------------------------------------------------- #


def _alive_by_tick(events: list[FeedEvent], cam: str) -> dict[int, bool]:
    return {ev.tick: ev.alive for ev in events if ev.cam_id == cam}


@pytest.mark.parametrize(
    "death_at, recover_after, alive_ticks, dead_ticks",
    [
        # Death only: alive 0..3, dead 4..9 (never recovers).
        ({"a": 4}, None, [0, 3], [4, 5, 9]),
        # Death + recovery: alive 0..3, dead 4..6, alive again 7..9.
        ({"a": 4}, 3, [0, 3, 7, 9], [4, 5, 6]),
        # Death at tick 0: dead immediately, recovers at 2.
        ({"a": 0}, 2, [2, 9], [0, 1]),
    ],
)
def test_feeddeath_timeline_boundaries(
    death_at: dict[str, int],
    recover_after: int | None,
    alive_ticks: list[int],
    dead_ticks: list[int],
) -> None:
    events = feed_death(
        np.random.default_rng(0), ["a"], 10, death_at=death_at, recover_after=recover_after
    )
    alive = _alive_by_tick(events, "a")
    assert all(alive[t] for t in alive_ticks)
    assert all(not alive[t] for t in dead_ticks)


def test_feeddeath_length_and_full_coverage() -> None:
    events = feed_death(np.random.default_rng(0), CAMS, 15, death_at={"a": 7})
    assert len(events) == 15 * len(CAMS)
    assert all(isinstance(ev, FeedEvent) for ev in events)


def test_feeddeath_multicam_only_one_dies() -> None:
    # Only camera 'a' dies; 'b' stays alive the whole run (no entry in death_at).
    events = feed_death(np.random.default_rng(0), ["a", "b"], 12, death_at={"a": 6})
    alive_a = _alive_by_tick(events, "a")
    alive_b = _alive_by_tick(events, "b")
    assert alive_a[5] and not alive_a[6] and not alive_a[11]
    assert all(alive_b.values())  # b never dies


def test_feeddeath_no_death_stays_alive() -> None:
    events = feed_death(np.random.default_rng(0), ["a"], 8)  # no death_at
    assert all(ev.alive for ev in events)
