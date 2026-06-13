"""#13107 per-camera state-isolation guard for the Track-B batched-detect adapter (06-01).

``batched_detect_dispatch`` runs ONE detection forward over all camera frames, then dispatches
EACH camera's OWN detections to its OWN persistent per-camera tracker — NEVER a frame list to
one tracker (Ultralytics #13107, which would build one tracker and mix track IDs across
cameras). These headless tests inject a fake model + fake per-camera trackers (no GPU, no
ultralytics) and assert the dispatch shape: one forward, N independent per-camera updates,
each receiving ONLY its own camera's detections.

Pitfall 4: a static ``batch=4`` engine needs exactly N frames — a dead-camera (None/blank)
slot is padded with a blank frame before the single forward, and that camera's result maps to
no-detection (coast), mirroring ``detector.track()``'s degrade-to-None contract.
"""

from __future__ import annotations

import numpy as np

from segugio.tracking.batched import batched_detect_dispatch


class _FakeDetectResult:
    """A stand-in for one camera's slice of the batched detect forward (``results[i]``)."""

    def __init__(self, cam_id: str) -> None:
        self.cam_id = cam_id  # tag so we can prove each tracker got ITS OWN detections


class _FakeModel:
    """Records the SINGLE batched predict call; returns one result per input frame.

    ``predict([f0..f3], ...)`` returns a list parallel to the input frames; each entry carries
    the index so a test can prove camera i's detection went to tracker i.
    """

    def __init__(self, cam_ids: list[str]) -> None:
        self._cam_ids = cam_ids
        self.predict_calls: list[dict] = []

    def predict(self, frames, **kwargs):
        self.predict_calls.append({"n_frames": len(frames), "kwargs": kwargs})
        # one result per frame, tagged by the camera that owns that slot
        return [_FakeDetectResult(cam_id) for cam_id in self._cam_ids]


class _FakeTracker:
    """A per-camera tracker that records every update + returns a tagged Results stand-in."""

    def __init__(self, cam_id: str) -> None:
        self.cam_id = cam_id
        self.update_calls: list = []

    def update(self, detections, frame):
        self.update_calls.append(detections)
        return f"results::{self.cam_id}"  # a Results stand-in for the consumer map


def _blank(h: int = 4, w: int = 4) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _setup(cam_ids):
    model = _FakeModel(cam_ids)
    trackers = {cid: _FakeTracker(cid) for cid in cam_ids}
    return model, trackers


# --------------------------------------------------------------------------- #
# Test 3 — #13107 isolation: each tracker updated exactly once with ONLY its own detections
# --------------------------------------------------------------------------- #


def test_each_tracker_gets_only_its_own_detections() -> None:
    cam_ids = ["cam_a", "cam_b", "cam_c", "cam_d"]
    model, trackers = _setup(cam_ids)
    frames_by_cam = {cid: _blank() for cid in cam_ids}

    out = batched_detect_dispatch(model, frames_by_cam, trackers, dog_idx=16, tick=0)

    # exactly ONE batched forward (never per-camera track(), never a frame list to one tracker)
    assert len(model.predict_calls) == 1
    assert model.predict_calls[0]["n_frames"] == 4

    for cid in cam_ids:
        tracker = trackers[cid]
        # each tracker updated EXACTLY once
        assert len(tracker.update_calls) == 1
        # with ONLY its own camera's detections (tagged result)
        dets = tracker.update_calls[0]
        assert dets.cam_id == cid
    # the consumer map is per-camera Results|None
    assert out == {cid: f"results::{cid}" for cid in cam_ids}


# --------------------------------------------------------------------------- #
# Test 4 — coast contract: a None/blank slot dispatches None to that tracker, never raises
# --------------------------------------------------------------------------- #


def test_none_slot_coasts_to_none() -> None:
    cam_ids = ["cam_a", "cam_b"]
    model, trackers = _setup(cam_ids)
    frames_by_cam = {"cam_a": _blank(), "cam_b": None}  # cam_b is a dead/blank slot

    out = batched_detect_dispatch(model, frames_by_cam, trackers, dog_idx=16, tick=1)

    # cam_b coasts: its tracker is NOT updated with detections (None dispatched → coast)
    assert out["cam_b"] is None
    assert trackers["cam_b"].update_calls == []
    # cam_a still tracked normally
    assert out["cam_a"] == "results::cam_a"
    assert len(trackers["cam_a"].update_calls) == 1


# --------------------------------------------------------------------------- #
# Test 5 — Pitfall 4: a dead slot is padded with a blank frame for the single forward
# --------------------------------------------------------------------------- #


def test_dead_slot_padded_for_static_batch() -> None:
    cam_ids = ["cam_a", "cam_b", "cam_c", "cam_d"]
    model, trackers = _setup(cam_ids)
    # one dead camera (None) — the single forward must still see exactly 4 frames (Pitfall 4)
    frames_by_cam = {"cam_a": _blank(), "cam_b": None, "cam_c": _blank(), "cam_d": _blank()}

    out = batched_detect_dispatch(model, frames_by_cam, trackers, dog_idx=16, tick=2)

    assert len(model.predict_calls) == 1
    assert model.predict_calls[0]["n_frames"] == 4  # padded to N=4 for the static batch
    # the dead camera maps to no-detection (coast), never raising
    assert out["cam_b"] is None
    assert trackers["cam_b"].update_calls == []
