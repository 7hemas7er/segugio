"""D-08 offline tracking eval — PURE metric counters (top) + heavy overlay/clip driver.

This module closes Phase 4: the offline eval that proves subject selection on the hard
disc-dog slices. It is SPLIT along the lazy-import boundary that defines the phase:

  * PURE METRIC COUNTERS (top of this file — :func:`compute_metrics`): integer/float
    counters over a ``list[DetectionSignal | None]`` stream — the locked-subject ID-switch
    count, the % frames the lock is held, the coast/uncertain count, and a per-tick signal
    dump for the regression net. They import NOTHING heavy (only stdlib + a type-only import
    of the frozen records). Deterministic, clock-free, RNG-free, cv2-free — unit-tested
    CPU-only in ``tests/test_tracking_metrics.py``. They are re-exported on the
    ``segugio.tracking`` surface (light + pure → safe at top level).

  * HEAVY OVERLAY RENDER + CLIP DRIVER (lower in this file — :func:`render_overlay` /
    :func:`run_clip_eval`, added by 04-04 Task 2): ``cv2`` is imported INSIDE each function
    (exactly like ``frame_source.py``), NEVER at module top. ``render_overlay`` draws boxes,
    track-id labels, the locked-subject highlight, and the per-camera zone rects, returning
    the annotated frame for a ``cv2.VideoWriter``. ``run_clip_eval`` wires the full TRK-01..05
    pipeline — ``ClipFrameSource`` → ``PerCameraTracker`` → ``signals_from_boxes`` →
    ``CompetitorLock`` → ``PlausibilityGate`` → per-camera ``DetectionSignal | None`` — mirroring
    the Phase-2 ``MultiCamScorer`` per-camera fan-out (``scorer.py:230-277``), then calls the
    PURE :func:`compute_metrics` per camera and logs the per-clip metrics + the explicit
    ``UNVERIFIED:`` lines (D-02) for the corpus-absent cases.

The lazy-import boundary (the phase's structural invariant): because the heavy ``cv2`` /
``ultralytics`` imports live INSIDE the render/driver functions, ``import
segugio.tracking.eval`` succeeds with ``cv2`` / ``ultralytics`` / ``torch`` ALL absent. The
purity source-grep (``tests/test_tracking_import_smoke.py``) deliberately EXCLUDES this
module from the cv2 ban for its render functions — but the module TOP must still carry no
cv2/heavy import (cv2 only inside functions). The pure counters above the boundary import
nothing that would break that.

D-08 establishes correctness (visual eyeballing of the rendered overlay on the CUDA box) +
a regression net (the deterministic metric counters). The metrics are an eyeball + regression
net, NOT a numeric pass/fail gate (D-02 / D-08); the ONE true pass/fail is the HARD
``assert_native_reid_engaged`` startup gate (TRK-02), called once before the processing loop.

Source: 04-RESEARCH.md §"GPU-gated real-YOLO eval" (lines 567-577), 04-PATTERNS.md §eval.py
(lines 263-267), 04-VALIDATION.md §"Manual-Only Verifications".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger  # LIGHT runtime dep (already used across the package) — top-level OK

if TYPE_CHECKING:  # type-only — keeps numpy/cv2/ultralytics off the runtime import path
    import numpy as np

    from ..framing.signals import DetectionSignal

__all__ = ["compute_metrics", "render_overlay", "run_clip_eval"]


# ======================================================================================== #
# PURE metric counters (D-08) — above the lazy-import boundary. No cv2 / heavy imports.     #
# ======================================================================================== #


def compute_metrics(stream: "list[DetectionSignal | None]") -> dict:
    """Compute the D-08 regression-net metrics over a locked-subject signal stream. PURE.

    Operates on a ``list[DetectionSignal | None]`` — the per-camera locked-subject stream the
    clip driver accumulates (one element per tick: the selected+gated ``DetectionSignal``, or
    ``None`` when the lock coasts this tick). Deterministic: the same stream yields an
    identical dict every call — no clock, no RNG, no cv2.

    Counters (04-RESEARCH.md lines 571-577):
      * ``id_switch_count`` — the number of times the locked ``track_id`` differs from the
        PREVIOUS non-None ``track_id``. A constant id → 0; an all-None stream → 0; a change
        across a coast (None) gap STILL counts (the None ticks do not reset the comparison —
        a silent BoT-SORT ID swap that surfaces after a blur is exactly what this catches).
      * ``lock_held_fraction`` — ``(count of non-None ticks) / max(n_ticks, 1)`` ∈ [0,1]
        (all-None → 0.0; all-present → 1.0; empty stream → 0.0 via the divisor guard).
      * ``coast_count`` — the count of ``None`` ticks (the lock-coast / gate-uncertain
        emissions). This module does NOT distinguish a gate-rejected "uncertain" None from a
        genuine-miss None: the ``DetectionSignal | None`` stream carries no such tag, so ALL
        Nones are counted as coast (the documented choice; a parallel uncertain counter would
        require the stream to carry the distinction).
      * ``n_ticks`` — ``len(stream)`` (the denominator + the dump length).
      * ``signal_dump`` — a per-tick ``list[tuple[int, int | None]]`` of
        ``(tick_index, locked_track_id_or_None)`` reconstructing the locked-subject identity
        per emitted frame (the regression net's eyeball-able record). ``tick_index`` is the
        POSITION in the stream (the emitted-frame index), independent of any ``DetectionSignal.tick``.

    Args:
        stream: the per-camera locked-subject stream (``DetectionSignal`` when the lock is
            held this tick, ``None`` when it coasts). Order is tick order.

    Returns:
        ``{"id_switch_count": int, "lock_held_fraction": float, "coast_count": int,
        "n_ticks": int, "signal_dump": list[tuple[int, int | None]]}``.
    """
    n_ticks = len(stream)
    coast_count = 0
    id_switch_count = 0
    prev_id: int | None = None  # the previous NON-None locked track_id (coast does not reset)
    signal_dump: list[tuple[int, int | None]] = []

    for tick_index, det in enumerate(stream):
        if det is None:
            coast_count += 1
            signal_dump.append((tick_index, None))
            continue  # a coast tick: do NOT reset prev_id (a switch across a gap still counts)
        cur_id = det.track_id
        if prev_id is not None and cur_id != prev_id:
            id_switch_count += 1
        prev_id = cur_id
        signal_dump.append((tick_index, cur_id))

    held = n_ticks - coast_count
    lock_held_fraction = held / n_ticks if n_ticks > 0 else 0.0

    return {
        "id_switch_count": id_switch_count,
        "lock_held_fraction": lock_held_fraction,
        "coast_count": coast_count,
        "n_ticks": n_ticks,
        "signal_dump": signal_dump,
    }


# ======================================================================================== #
# HEAVY edge (D-08) — below the lazy-import boundary. cv2 imported INSIDE each function.    #
# ======================================================================================== #

# The corpus-absent cases the eval cannot clip-prove — logged EXPLICITLY (D-02), never a
# silent pass. The select→gate LOGIC for these is exercised by the 04-02 synthetic
# crossing/teleport tests; the cases are simply not present in the committed disc-dog corpus.
_UNVERIFIED_CASES: tuple[str, ...] = (
    "agility-tunnel-occlusion — no corpus footage",
    "two-similar-dogs-crossing swap — no corpus footage",
)


def log_unverified_cases() -> None:
    """Emit the explicit ``UNVERIFIED: <case>`` loguru lines (D-02). Never a silent pass.

    The clip eval has no agility-tunnel-occlusion footage and no clean two-similar-dogs
    crossing in the committed disc-dog corpus, so those cases CANNOT be clip-proven here. The
    code paths exist and the 04-02 synthetic crossing/teleport tests exercise the logic, but
    the eval must RECORD the gap loudly rather than imply coverage. One warning line per case.
    """
    for case in _UNVERIFIED_CASES:
        logger.warning("UNVERIFIED: {}", case)


def render_overlay(frame, boxes, track_ids, locked_id, zones) -> "np.ndarray":
    """Annotate a BGR crop with boxes, track-id labels, the locked highlight, and zone rects.

    Lazy ``import cv2`` (the heavy-edge boundary — NEVER at module top). Draws, for human
    review on the CUDA box (D-08 is ultimately a visual judgement):
      * each detection box (normalized ``[cx, cy, w, h]`` → pixel rect) with a thin outline;
      * its ``track_id`` as a text label;
      * the LOCKED-subject box in a DISTINCT color + thicker outline (the eyeball-able
        "this is the in-competition dog" signal — TRK-04/05);
      * the per-camera ``zones`` as rectangles (the zone gate, normalized → pixels).

    Args:
        frame: the BGR crop (``numpy.ndarray``, H×W×3) to annotate IN A COPY (the original is
            left untouched so the caller may reuse it).
        boxes: per-detection ``(cx, cy, w, h)`` normalized-to-crop rows (``Results.boxes.xywhn``).
        track_ids: per-detection tracker ids aligned with ``boxes`` (``Results.boxes.id``), or
            ``None`` when BoT-SORT confirmed no track this frame.
        locked_id: the ``CompetitorLock``-selected ``track_id`` to highlight, or ``None`` (coast).
        zones: the camera's ``Zone`` objects (each ``.rect`` is normalized ``[x0,y0,x1,y1]``).

    Returns:
        The annotated frame (a copy). On a blank/zero-size frame returns it unchanged.
    """
    import cv2  # lazy — heavy import INSIDE the render function (the cv2 boundary)

    if frame is None or getattr(frame, "size", 0) == 0:
        return frame
    annotated = frame.copy()  # never mutate the caller's frame
    h, w = annotated.shape[0], annotated.shape[1]

    # Zone rects first (drawn under the boxes) — faint gray, normalized → pixels.
    for z in zones or []:
        zx0, zy0, zx1, zy1 = z.rect
        cv2.rectangle(
            annotated,
            (int(zx0 * w), int(zy0 * h)),
            (int(zx1 * w), int(zy1 * h)),
            (128, 128, 128),
            1,
        )

    ids = list(track_ids) if track_ids is not None else []
    for i, (cx, cy, bw, bh) in enumerate(boxes):
        # Normalized center+size → pixel corner rect (clamped to the crop).
        x0 = int(max(0.0, cx - bw / 2.0) * w)
        y0 = int(max(0.0, cy - bh / 2.0) * h)
        x1 = int(min(1.0, cx + bw / 2.0) * w)
        y1 = int(min(1.0, cy + bh / 2.0) * h)
        tid = int(ids[i]) if i < len(ids) else None
        is_locked = locked_id is not None and tid == int(locked_id)
        # Locked subject: green + thick; others: yellow + thin.
        color = (0, 255, 0) if is_locked else (0, 215, 255)
        thickness = 3 if is_locked else 1
        cv2.rectangle(annotated, (x0, y0), (x1, y1), color, thickness)
        label = f"id={tid}" + (" LOCK" if is_locked else "")
        cv2.putText(
            annotated, label, (x0, max(0, y0 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness,
        )
    return annotated


def _arrays_from_results(results):
    """Extract ``(xywhn, ids, confs)`` plain lists from one YOLO ``Results`` row (or None).

    ``Results.boxes`` may be ``None`` (no boxes) or have ``.id is None`` (BoT-SORT confirmed
    no track this frame) — both degrade to ``([], None, [])`` so ``signals_from_boxes``
    coasts (the no-crash / coast contract). ``.cpu().numpy().tolist()`` brings the tensors to
    plain Python so the downstream pure mapper never sees a live GPU tensor.
    """
    if results is None or getattr(results, "boxes", None) is None:
        return [], None, []
    boxes = results.boxes
    if boxes.id is None:  # no confirmed track this frame → coast
        return [], None, []
    xywhn = boxes.xywhn.cpu().numpy().tolist()
    ids = boxes.id.cpu().numpy().astype(int).tolist()
    confs = boxes.conf.cpu().numpy().tolist()
    return xywhn, ids, confs


def run_clip_eval(clip_path, cameras, crops, model_cfg, params, out_video_path):
    """Drive the full TRK-01..05 pipeline over one clip → overlay video + per-camera metrics.

    This is the phase's human-judged deliverable (D-08). It mirrors the Phase-2
    ``MultiCamScorer`` per-camera fan-out (``scorer.py:230-277``): one ``PerCameraTracker`` per
    ``cam_id`` (NEVER a frame list — #13107), one ``CompetitorLock`` + one ``PlausibilityGate``
    per camera (per-camera independence, D-05). Per ``(tick, crops)`` from
    ``ClipFrameSource.frames()`` it runs, for each camera:

        crop → tracker.track() → (xywhn, ids, confs) → signals_from_boxes
             → CompetitorLock.select(candidates, tick) → PlausibilityGate.check(selected)
             → the per-camera ``DetectionSignal | None``

    accumulating one ``DetectionSignal | None`` stream per camera and writing the annotated
    frame (``render_overlay``) to a ``cv2.VideoWriter`` at ``out_video_path``. At the end it
    calls the PURE :func:`compute_metrics` per camera and logs the per-clip metrics (ID-switch
    count, %lock-held, coast count) + the per-camera detection presence (a recall proxy on
    distant/dusk slices — RECORDED, never a pass/fail gate; Q2/D-02), and emits the explicit
    ``UNVERIFIED:`` lines.

    The HARD TRK-02 gate (:func:`assert_native_reid_engaged`) is called ONCE, after a warmup
    ``.track()`` on the first available crop and BEFORE the processing loop — it RAISES on the
    silent ``yolo26n-cls.pt`` fallback (the one true pass/fail). Fail-safe: a decode/inference
    error on any single frame degrades THAT frame to no-detection (coast) so the driver never
    crashes (the live no-crash requirement — T-04-04-01).

    Args:
        clip_path: an ABSOLUTE clip path (resolve via ``segugio.fixtures.resolve_clip_path`` —
            the committed SLICES, not ``gara_full``; A5 / T-04-04-04: a driver-controlled path).
        cameras: an iterable of Phase-1 ``Camera`` objects (each ``.id`` is a ``cam_id``;
            ``.zones`` feed both the lock gate and the overlay). Defines the deterministic
            per-camera output order. Each camera's ``id`` MUST have a ``crops`` entry.
        crops: ``{cam_id: [x0, y0, x1, y1]}`` normalized crop rects (the ``crop_geometry`` /
            config geometry) — the pseudo-camera windows ``ClipFrameSource`` slices.
        model_cfg: the ``ModelConfig`` (``.path`` → weights, ``.class_index`` → reconciled
            BY NAME via ``resolve_dog_index``).
        params: the validated ``TrackingParams`` (CompetitorLock + PlausibilityGate seeds).
        out_video_path: the overlay ``.mp4`` output path (driver-controlled location, T-04-04-04).

    Returns:
        ``dict[str, dict]`` — ``{cam_id: compute_metrics(stream)}`` per camera (the D-08
        regression net). The overlay video is a side-effect written to ``out_video_path``.
    """
    import cv2  # lazy — heavy import INSIDE the driver (the cv2 boundary)

    from ..framing.signals import DetectionSignal  # noqa: F401 — type clarity at call sites
    from .competitor_lock import CompetitorLock
    from .detector import PerCameraTracker, resolve_dog_index
    from .frame_source import ClipFrameSource
    from .plausibility import PlausibilityGate
    from .reid_check import assert_native_reid_engaged
    from .signals_map import signals_from_boxes

    cams = list(cameras)
    crop_map = {cam.id: crops[cam.id] for cam in cams}  # {cam_id: [x0,y0,x1,y1]}
    source = ClipFrameSource(clip_path, crop_map)

    # One tracker + one lock + one gate per camera (per-camera independence, D-05 / #13107).
    trackers: dict = {}
    locks: dict = {}
    gates: dict = {}
    streams: "dict[str, list[DetectionSignal | None]]" = {}
    for cam in cams:
        trackers[cam.id] = PerCameraTracker(model_cfg.path, model_cfg.class_index, "botsort_dog.yaml")
        locks[cam.id] = CompetitorLock(cam, params)
        gates[cam.id] = PlausibilityGate(params)
        streams[cam.id] = []

    frame_iter = source.frames()
    writer = None
    reid_checked = False
    try:
        for tick, frame_crops in frame_iter:
            for cam in cams:
                cam_id = cam.id
                crop = frame_crops.get(cam_id)
                tracker = trackers[cam_id]

                # Resolve the dog index BY NAME + run the HARD native-ReID gate ONCE, before
                # the real processing — after the first crop is decoded (predictor exists).
                if not reid_checked:
                    tracker.dog_idx = resolve_dog_index(tracker.model, model_cfg.class_index)

                results = tracker.track(crop)  # None on a blank/decode-failure frame → coast

                if not reid_checked:
                    assert_native_reid_engaged(tracker.model)  # RAISES on cls fallback (TRK-02)

                # Edge → signals → lock → gate → the per-camera DetectionSignal | None.
                xywhn, ids, confs = _arrays_from_results(results)
                candidates = signals_from_boxes(xywhn, ids, confs, tick, cam_id)
                selected = locks[cam_id].select(candidates, tick)
                if selected is None:
                    gates[cam_id].reset()  # genuine loss → fresh continuity chain on re-acquire
                signal = gates[cam_id].check(selected)
                streams[cam_id].append(signal)

                # Render the overlay for the FIRST camera's crop (the eyeball-able review feed).
                if cam is cams[0] and crop is not None and getattr(crop, "size", 0) > 0:
                    locked_id = signal.track_id if signal is not None else None
                    annotated = render_overlay(crop, xywhn, ids, locked_id, cam.zones)
                    if writer is None:
                        fh, fw = annotated.shape[0], annotated.shape[1]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        writer = cv2.VideoWriter(str(out_video_path), fourcc, 30.0, (fw, fh))
                    writer.write(annotated)
            # The native-ReID gate has now run for every camera's first frame.
            reid_checked = True
    finally:
        frame_iter.close()
        if writer is not None:
            writer.release()

    # PURE metrics per camera + per-clip logging (regression net + recall proxy, D-08/Q2).
    metrics_by_cam: dict = {}
    for cam in cams:
        m = compute_metrics(streams[cam.id])
        metrics_by_cam[cam.id] = m
        logger.info(
            "clip={} cam={} id_switches={} lock_held={:.3f} coast={} n_ticks={} "
            "(detection-presence/recall-proxy={:.3f}; recorded, not a gate — Q2/D-02)",
            out_video_path, cam.id, m["id_switch_count"], m["lock_held_fraction"],
            m["coast_count"], m["n_ticks"], m["lock_held_fraction"],
        )

    # Explicit UNVERIFIED lines for the corpus-absent cases (D-02) — never a silent pass.
    log_unverified_cases()

    return metrics_by_cam
