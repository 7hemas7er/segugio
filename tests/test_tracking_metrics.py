"""D-08 PURE metric-counter suite for the offline tracking eval (``compute_metrics``).

These tests are PURE — no GPU, no cv2, no clip. They drive ``compute_metrics`` over
fabricated ``list[DetectionSignal | None]`` streams (the exact per-camera signal stream the
GPU clip driver accumulates, and the shape ``MultiCamScorer.update`` consumes one element of
per tick) and assert the EXACT integer/float counter values. They mirror the determinism
discipline of the Phase-2 framing tests and the 04-02 brain suites: same stream → identical
metrics dict, no clock, no RNG.

The five must-have behaviors (04-PLAN.md Task 1):

  1. ID-switch count — the locked ``track_id`` changing value mid-stream counts switches
     (constant id → 0; all-None → 0; a change across a coast gap still counts).
  2. % frames lock-held — K non-None of N ticks → ``lock_held_fraction == K / N``
     (all-None → 0.0; all-present → 1.0).
  3. Coast/uncertain count — the number of ``None`` ticks equals ``coast_count``.
  4. Determinism — the same stream computed twice → identical metrics dict.
  5. Signal dump — the counters expose a per-tick ``(tick, track_id-or-None)`` list to
     reconstruct the locked-subject signal for the regression net.
"""

from __future__ import annotations

import numpy as np

from segugio.framing.signals import DetectionSignal
from segugio.synth.detection_stream import multi_track_stream
from segugio.tracking import compute_metrics
from tests.conftest import SEED

CAM_ID = "cam_a"


def _sig(tick: int, track_id: int, cx: float = 0.5) -> DetectionSignal:
    """A minimal present locked signal at ``tick`` carrying ``track_id`` (the lock identity)."""
    return DetectionSignal(tick, CAM_ID, cx, 0.5, 0.1, 0.1, 0.8, track_id)


# --- Behavior 1: locked-subject ID-switch count ----------------------------------------- #


def test_id_switch_count_one_mid_stream_change() -> None:
    """A stream whose locked track_id changes once (id 1 for 5 ticks, id 2 for 5) → 1 switch."""
    stream = [_sig(t, 1) for t in range(5)] + [_sig(t, 2) for t in range(5, 10)]
    m = compute_metrics(stream)
    assert m["id_switch_count"] == 1


def test_id_switch_count_zero_for_constant_id() -> None:
    """A constant locked track_id across the whole stream → zero ID switches."""
    stream = [_sig(t, 7) for t in range(8)]
    assert compute_metrics(stream)["id_switch_count"] == 0


def test_id_switch_count_zero_for_all_none() -> None:
    """An all-None (all-coast) stream has no locked id at all → zero ID switches."""
    stream: list[DetectionSignal | None] = [None] * 6
    assert compute_metrics(stream)["id_switch_count"] == 0


def test_id_switch_counts_change_across_a_coast_gap() -> None:
    """A coast (None) gap between two DIFFERENT ids still counts as one switch (D-08).

    The switch is measured between consecutive NON-None track_ids — the None ticks in the
    middle do not reset the comparison, so id 1 → coast → id 2 is one switch (not zero).
    """
    stream = [_sig(0, 1), _sig(1, 1), None, None, _sig(4, 2), _sig(5, 2)]
    assert compute_metrics(stream)["id_switch_count"] == 1


# --- Behavior 2: % frames lock-held ----------------------------------------------------- #


def test_lock_held_fraction_partial() -> None:
    """K non-None of N total ticks → ``lock_held_fraction == K / N`` exactly."""
    # 6 present + 4 None = 6/10.
    stream = [_sig(t, 1) for t in range(6)] + [None, None, None, None]
    m = compute_metrics(stream)
    assert m["n_ticks"] == 10
    assert m["lock_held_fraction"] == 6 / 10


def test_lock_held_fraction_all_none_is_zero() -> None:
    """An all-None stream holds the lock 0% of the time → 0.0."""
    stream: list[DetectionSignal | None] = [None] * 5
    assert compute_metrics(stream)["lock_held_fraction"] == 0.0


def test_lock_held_fraction_all_present_is_one() -> None:
    """An all-present stream holds the lock 100% of the time → 1.0."""
    stream = [_sig(t, 1) for t in range(5)]
    assert compute_metrics(stream)["lock_held_fraction"] == 1.0


def test_lock_held_fraction_empty_stream_is_zero() -> None:
    """An empty stream is the degenerate divisor-guard case → 0.0, never a ZeroDivisionError."""
    assert compute_metrics([])["lock_held_fraction"] == 0.0


# --- Behavior 3: coast/uncertain count -------------------------------------------------- #


def test_coast_count_equals_number_of_nones() -> None:
    """``coast_count`` equals the count of None ticks in the stream."""
    stream = [_sig(0, 1), None, _sig(2, 1), None, None, _sig(5, 1)]
    m = compute_metrics(stream)
    assert m["coast_count"] == 3


def test_coast_count_zero_when_no_nones() -> None:
    """A stream with no None ticks → coast_count 0."""
    stream = [_sig(t, 1) for t in range(4)]
    assert compute_metrics(stream)["coast_count"] == 0


# --- Behavior 4: determinism ------------------------------------------------------------ #


def test_metrics_are_deterministic_on_the_same_stream() -> None:
    """The same stream computed twice yields an IDENTICAL metrics dict (pure, no clock/RNG)."""
    rng = np.random.default_rng(SEED)
    per_tick = multi_track_stream(
        rng,
        CAM_ID,
        12,
        [
            {"track_id": 1, "path": "linear_right", "size": 0.1, "conf": 0.8},
            {"track_id": 2, "path": "linear_left", "size": 0.1, "conf": 0.7},
        ],
    )
    # Reduce the multi-track substrate to a single locked-id-or-None stream: pick track 1
    # when present this tick (else coast) — a realistic "locked subject" projection.
    stream: list[DetectionSignal | None] = [
        next((d for d in dets if d.track_id == 1), None) for dets in per_tick
    ]
    first = compute_metrics(stream)
    second = compute_metrics(stream)
    assert first == second


# --- Behavior 5: signal dump ------------------------------------------------------------ #


def test_signal_dump_reconstructs_per_tick_locked_id() -> None:
    """The ``signal_dump`` is a per-tick ``(tick, track_id-or-None)`` list for the regression net."""
    stream = [_sig(0, 1), _sig(1, 1), None, _sig(3, 2)]
    dump = compute_metrics(stream)["signal_dump"]
    assert dump == [(0, 1), (1, 1), (2, None), (3, 2)]
    # ^ tick is the POSITION in the stream (the emitted-frame index); the locked track_id
    #   where present (id 2 at tick 3 — a switch from id 1), None where coasted (tick 2).


def test_signal_dump_length_matches_stream() -> None:
    """The signal dump has exactly one entry per stream tick (a faithful per-tick record)."""
    stream = [_sig(t, 1) for t in range(7)] + [None, None]
    dump = compute_metrics(stream)["signal_dump"]
    assert len(dump) == len(stream) == 9
