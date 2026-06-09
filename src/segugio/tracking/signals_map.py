"""TRK-03 — the PURE mapper from a YOLO ``Results`` row to a frozen ``DetectionSignal``.

``signals_from_boxes`` is a function of its inputs only: numpy arrays (or plain Python
sequences) in, ``list[DetectionSignal]`` out. No randomness, no wall-clock, no I/O — the
same arrays map byte-identically every call (the determinism contract the scorer and the
brain tests depend on).

``Results.boxes.xywhn`` is already crop-normalized ``(cx, cy, w, h) ∈ [0,1]`` (the box is
expressed relative to the inference crop), so the mapper needs NO math — it only fills the
frozen ``DetectionSignal`` and ``float()``/``int()``-casts every field so a ``numpy.float64``
never leaks into the frozen ``==``.

Two degradation guards (T-04-01-02 — malformed input coasts, never crashes):
  * ``ids is None`` (BoT-SORT had no confirmed tracks this frame) → ``[]`` (coast), no iter;
  * an empty ``xywhn`` simply yields ``[]`` via the ``zip``.

This mapper does NOT filter by class — ``classes=[dog_idx]`` already filters at inference
(04-03); it trusts its inputs are dog-only rows.

Light, stdlib-only construction import — ``segugio.framing.signals`` is a frozen-dataclass
module (no torch/cv2), safe under the lazy-import boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from segugio.framing.signals import DetectionSignal

if TYPE_CHECKING:  # type-only — keeps numpy out of the runtime path of this pure module
    import numpy as np

__all__ = ["signals_from_boxes"]


def signals_from_boxes(xywhn, ids, confs, tick, cam_id) -> list[DetectionSignal]:
    """Map one camera's ``Results`` row arrays to a list of frozen ``DetectionSignal``s.

    Args:
        xywhn: per-detection ``(cx, cy, w, h)`` rows, already crop-normalized to [0,1]
            (``Results.boxes.xywhn``). May be a numpy array or a sequence of sequences.
        ids: per-detection tracker ids (``Results.boxes.id``), or ``None`` when BoT-SORT
            confirmed no track this frame → coast.
        confs: per-detection detector confidences (``Results.boxes.conf``).
        tick: the injected synthetic/frame index stamped on every signal.
        cam_id: the camera identifier stamped on every signal.

    Returns:
        ``list[DetectionSignal]`` — one per row, in input order. Empty list when
        ``ids is None`` (no confirmed tracks → coast) or when ``xywhn`` is empty.
    """
    if ids is None:  # no confirmed tracks this frame → coast (degrade, never crash)
        return []
    out: list[DetectionSignal] = []
    for (cx, cy, w, h), tid, conf in zip(xywhn, ids, confs):
        out.append(
            DetectionSignal(
                tick=int(tick),
                cam_id=cam_id,
                cx=float(cx),
                cy=float(cy),
                w=float(w),
                h=float(h),
                conf=float(conf),
                track_id=int(tid),
            )
        )
    return out
