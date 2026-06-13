"""Track-B batched-detect adapter — ONE detection forward → N per-camera tracker updates.

This is the optional Wave-B latency path: instead of N separate ``model.track(frame)`` calls
(one per camera, the ``PerCameraTracker`` path in ``detector.py``), run ONE batched detection
forward over all camera frames, THEN dispatch each camera's OWN detections into its OWN
persistent per-camera tracker. The track-association stage stays per-camera so each camera
keeps its own BoT-SORT state and native-ReID embeddings.

The load-bearing rule (``detector.py:1-20`` contract, CLAUDE.md "What NOT to Use"): NEVER pass
a frame list to one ``model.track([frames])`` — that builds ONE tracker and mixes track IDs
across cameras (Ultralytics #13107). Batching here is DETECTION-ONLY; association is dispatched
to N independent tracker objects keyed by ``cam_id``.

Pitfall 4 (static-batch padding): a TensorRT engine exported with a static ``batch=N`` needs
exactly N frames per forward. A dead-camera slot (``None``/blank frame) is padded with a blank
frame before the single forward so the static batch stays valid; that camera's result maps to
no-detection (coast) — the same degrade-to-None contract as ``PerCameraTracker.track()``
(RBT-04, never crash on one bad frame).

Lazy-import boundary: ``ultralytics``/``torch`` are imported INSIDE the function, never at
module top, so ``import segugio.tracking.batched`` succeeds with the heavy stack absent
(``tests/test_tracking_import_smoke.py``). ``loguru`` is a LIGHT runtime dep imported at top.

Headless contract: the per-camera tracker objects and the model are INJECTED. The adapter's
contract under test is the DISPATCH SHAPE (one forward, N per-camera updates, each receiving
only its own detections) — not real inference. Tests pass fakes (no GPU).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # type-only — keeps heavy deps off the runtime import path
    import numpy as np

__all__ = ["batched_detect_dispatch"]


def _blank_like(frames_by_cam: dict) -> "np.ndarray":
    """Return a blank frame shaped like the first real frame (Pitfall 4 static-batch pad).

    A dead-camera slot is ``None``; the single batched forward still needs N frames, so we pad
    with a zero frame matching a live camera's shape. ``numpy`` is imported lazily here (heavy
    boundary) — a blank-pad is only needed when there IS at least one live frame to batch.
    """
    import numpy as np  # lazy — keeps the import boundary intact

    for frame in frames_by_cam.values():
        if frame is not None and getattr(frame, "size", 0) != 0:
            return np.zeros_like(frame)
    # no live frame at all — a 1x1x3 blank is enough to keep the batch shape non-empty
    return np.zeros((1, 1, 3), dtype="uint8")


def batched_detect_dispatch(model, frames_by_cam, trackers_by_cam, dog_idx, tick):
    """Run ONE batched detection forward then dispatch per-camera detections to N trackers.

    Steps:
      1. Build the per-camera frame list in a STABLE camera order (the keys of
         ``frames_by_cam``), padding any ``None``/blank slot with a blank frame so a static
         ``batch=N`` engine forward stays valid (Pitfall 4).
      2. Run ONE ``model.predict([f0..fN], classes=[dog_idx], verbose=False)`` — detection
         only, NEVER ``model.track([frames])`` (#13107). ``ultralytics`` is used only through
         the injected ``model``; nothing heavy is imported here.
      3. Dispatch each camera's detection result to its OWN persistent
         ``trackers_by_cam[cam_id]`` via that tracker's ``update(detections, frame)``. A dead
         (``None``/blank) slot dispatches NOTHING and coasts to ``None`` — mirroring
         ``PerCameraTracker.track()``'s degrade-to-None (RBT-04).

    Args:
        model: an object exposing ``predict(frames, **kwargs) -> list`` parallel to ``frames``
            (the injected ``ultralytics.YOLO`` in production, a fake in tests).
        frames_by_cam: ``{cam_id: frame|None}`` — one BGR frame per camera this tick.
        trackers_by_cam: ``{cam_id: tracker}`` — one PERSISTENT per-camera tracker object, each
            exposing ``update(detections, frame) -> Results`` (#13107: one tracker per cam_id).
        dog_idx: the dog class index (resolved BY NAME upstream — never hardcoded 16).
        tick: the current loop tick (advisory; threaded through for parity with the loop).

    Returns:
        ``{cam_id: Results | None}`` — the per-camera consumer map (``_arrays_from_results``
        shape). A dead/coasting camera maps to ``None``.
    """
    cam_ids = list(frames_by_cam.keys())  # STABLE camera order for the batch
    # 1. Build the batch, padding dead slots (Pitfall 4). Track which slots are live so a dead
    #    camera coasts to None instead of being fed a fabricated detection.
    blank = None
    batch_frames = []
    live = {}
    for cam_id in cam_ids:
        frame = frames_by_cam[cam_id]
        is_live = frame is not None and getattr(frame, "size", 0) != 0
        live[cam_id] = is_live
        if is_live:
            batch_frames.append(frame)
        else:
            if blank is None:
                blank = _blank_like(frames_by_cam)
            batch_frames.append(blank)  # pad so the static-batch forward stays valid

    # 2. ONE batched DETECTION forward (never model.track([frames]) — #13107).
    try:
        results = model.predict(
            batch_frames, classes=[int(dog_idx)], verbose=False
        )
    except Exception as exc:  # noqa: BLE001 — live-robustness: never crash the loop on a bad batch
        logger.warning(
            "batched_detect_dispatch degraded the whole batch to coast (tick={}): {}",
            tick,
            exc,
        )
        return {cam_id: None for cam_id in cam_ids}

    # 3. Dispatch each camera's OWN detections to its OWN persistent tracker.
    out: dict = {}
    for idx, cam_id in enumerate(cam_ids):
        if not live[cam_id]:
            out[cam_id] = None  # dead/blank slot coasts — no detection fed to the tracker
            continue
        tracker = trackers_by_cam.get(cam_id)
        if tracker is None:
            out[cam_id] = None
            continue
        try:
            detections = results[idx]
            out[cam_id] = tracker.update(detections, frames_by_cam[cam_id])
        except Exception as exc:  # noqa: BLE001 — one bad camera coasts, never crashes the loop
            logger.warning(
                "per-camera dispatch degraded cam {} to coast (tick={}): {}",
                cam_id,
                tick,
                exc,
            )
            out[cam_id] = None
    return out
