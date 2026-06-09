"""TRK-03 pure mapper + multi-track synthetic-substrate determinism (plan 04-01 Task 2).

Pure unit tests (no GPU, no I/O) over fabricated plain-Python / numpy arrays — the
synthetic-input style of the Phase-2 ``test_framing_*`` suite:

  * Test 1 — mapping: an ``xywhn`` row maps to a frozen ``DetectionSignal`` with the exact
    field values, every numeric field a plain ``float``/``int`` (no numpy scalar leaks).
  * Test 2 — None-id coast: ``ids=None`` returns ``[]`` (no confirmed tracks → coast),
    never raises.
  * Test 3 — multi-row: a 2-row input maps to a 2-element list preserving order.
  * Test 4 — determinism: identical fabricated arrays → byte-identical list across calls.
  * Test 5 — multi-track synth: ``multi_track_stream`` emits two independent tracks
    (distinct ids, distinct cx) at the same ticks, byte-identical under the same seed.
"""

from __future__ import annotations

import numpy as np

from segugio.framing.signals import DetectionSignal
from segugio.tracking.signals_map import signals_from_boxes


def test_mapping_fills_frozen_detection_signal_with_plain_floats() -> None:
    """Test 1: a single xywhn row maps to the exact frozen DetectionSignal, float-cast."""
    out = signals_from_boxes(
        xywhn=[[0.5, 0.5, 0.2, 0.3]], ids=[7], confs=[0.9], tick=4, cam_id="cam_c"
    )
    assert out == [
        DetectionSignal(
            tick=4, cam_id="cam_c", cx=0.5, cy=0.5, w=0.2, h=0.3, conf=0.9, track_id=7
        )
    ]
    # No numpy scalar may leak into the frozen == (mandatory float()/int() casts).
    assert type(out[0].cx) is float
    assert type(out[0].cy) is float
    assert type(out[0].w) is float
    assert type(out[0].h) is float
    assert type(out[0].conf) is float
    assert type(out[0].track_id) is int
    assert type(out[0].tick) is int


def test_numpy_row_casts_to_plain_float() -> None:
    """A numpy-array row (as a real Results.boxes would give) still yields plain floats."""
    out = signals_from_boxes(
        xywhn=np.array([[0.25, 0.75, 0.1, 0.2]]),
        ids=np.array([3]),
        confs=np.array([0.42]),
        tick=np.int64(9),
        cam_id="cam_l",
    )
    assert type(out[0].cx) is float
    assert type(out[0].track_id) is int
    assert type(out[0].tick) is int
    assert out[0] == DetectionSignal(9, "cam_l", 0.25, 0.75, 0.1, 0.2, 0.42, 3)


def test_none_id_returns_empty_coast() -> None:
    """Test 2: ids=None → [] (coast), never raises — degrades, does not crash (T-04-01-02)."""
    out = signals_from_boxes(
        xywhn=[[0.5, 0.5, 0.2, 0.3]], ids=None, confs=[0.9], tick=2, cam_id="cam_c"
    )
    assert out == []


def test_multi_row_preserves_order() -> None:
    """Test 3: a 2-row input maps to a 2-element list in input order."""
    out = signals_from_boxes(
        xywhn=[[0.2, 0.5, 0.1, 0.1], [0.8, 0.5, 0.15, 0.15]],
        ids=[11, 22],
        confs=[0.6, 0.8],
        tick=5,
        cam_id="cam_r",
    )
    assert len(out) == 2
    assert out[0].track_id == 11 and out[0].cx == 0.2
    assert out[1].track_id == 22 and out[1].cx == 0.8


def test_mapping_is_deterministic() -> None:
    """Test 4: identical fabricated arrays → byte-identical list across two calls."""
    args = dict(
        xywhn=[[0.3, 0.4, 0.2, 0.25], [0.7, 0.6, 0.1, 0.1]],
        ids=[1, 2],
        confs=[0.5, 0.55],
        tick=8,
        cam_id="cam_c",
    )
    out_a = signals_from_boxes(**args)
    out_b = signals_from_boxes(**args)
    assert out_a == out_b


def test_multi_track_stream_emits_independent_tracks_deterministically(seeded_rng) -> None:
    """Test 5: two independent tracks (distinct ids + cx) at the same ticks, seed-reproducible."""
    import numpy as np

    from segugio.synth.detection_stream import multi_track_stream
    from tests.conftest import SEED

    tracks = [
        {"track_id": 1, "path": "linear_right", "size": 0.30, "conf": 0.7},
        {"track_id": 2, "path": "linear_left", "size": 0.25, "conf": 0.6},
    ]
    n_ticks = 12
    per_tick = multi_track_stream(seeded_rng, "cam_c", n_ticks, tracks)

    assert len(per_tick) == n_ticks
    # At a mid tick both tracks are present with distinct ids and distinct cx (they cross).
    mid = per_tick[6]
    ids_present = {d.track_id for d in mid}
    assert ids_present == {1, 2}
    cx_by_id = {d.track_id: d.cx for d in mid}
    assert cx_by_id[1] != cx_by_id[2]

    # Same seed → byte-identical multi-track output.
    rng_b = np.random.default_rng(SEED)
    per_tick_b = multi_track_stream(rng_b, "cam_c", n_ticks, tracks)
    assert per_tick == per_tick_b


def test_multi_track_dropout_window_contributes_nothing() -> None:
    """A track in its dropout window simply contributes no DetectionSignal that tick (coast)."""
    rng = np.random.default_rng(1234)
    from segugio.synth.detection_stream import multi_track_stream

    tracks = [
        {"track_id": 1, "path": "linear_right", "size": 0.30, "conf": 0.7},
        {"track_id": 2, "path": "linear_left", "size": 0.25, "conf": 0.6, "dropout": (3, 6)},
    ]
    per_tick = multi_track_stream(rng, "cam_c", 10, tracks)
    # During [3,6) only track 1 is present; track 2 dropped out.
    for t in (3, 4, 5):
        ids = {d.track_id for d in per_tick[t]}
        assert ids == {1}
    # After the dropout window track 2 returns.
    assert {d.track_id for d in per_tick[6]} == {1, 2}


def test_multi_track_unknown_path_fails_fast() -> None:
    """An unknown path name fails fast (fail-loud at config/setup, not silently in the loop)."""
    import pytest

    from segugio.synth.detection_stream import multi_track_stream

    rng = np.random.default_rng(1234)
    with pytest.raises(ValueError):
        multi_track_stream(
            rng, "cam_c", 5, [{"track_id": 1, "path": "diagonal", "size": 0.3, "conf": 0.7}]
        )
