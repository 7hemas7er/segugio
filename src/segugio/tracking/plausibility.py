"""``PlausibilityGate`` — the PURE stateful INTER-frame track-continuity gate (TRK-05).

This is the second half of the subject-selection brain (PITFALLS Pitfall 2). Even after the
``CompetitorLock`` picks a track, a silent BoT-SORT ID swap can hand the locked ``track_id``
a DIFFERENT box — a bystander that "teleports" or size-jumps relative to the last accepted
box. ``PlausibilityGate`` rejects that inter-frame discontinuity: ``check(det)`` returns
``None`` (the downstream scorer holds its last EMA — coast) WITHOUT updating ``self.prev``,
so the suspect box can never become the new reference. It honors the locked decisions:

  * D-06 reject suspect → uncertain → coast: a per-tick center jump beyond
    ``max_displacement_per_tick`` (teleport) OR an area ratio outside ``[1/r, r]`` with
    ``r = max_size_ratio`` (size-jump) → ``None``; ``self.prev`` is deliberately NOT updated
    on a rejection so a teleport does not poison the continuity reference.
  * D-07 distinct from the Phase-2 INTRA-frame guard: this is NOT ``terms.plausibility_ok``.
    That guard answers "is this box a plausible dog at all" (conf / area / aspect) on a
    SINGLE frame, signature ``plausibility_ok(det, p) -> bool``, stateless. THIS gate answers
    "is this box a plausible CONTINUATION of the locked track" across ticks, signature
    ``check(det) -> DetectionSignal | None``, STATEFUL on ``self.prev``. They live in
    different modules with different signatures so they are never conflated (PITFALLS
    Pitfall 5). This module neither calls nor imports ``terms.plausibility_ok``.

The coast mechanism is FREE — returning ``None`` IS the entire "uncertain → coast" logic.
No new coast/TTL machinery is built here: ``None`` flows straight into the existing
``CameraScorer.update`` FRM-05 branch, which holds the last EMA (status ``coasting``),
exactly as ``detection_stream`` already emits ``None`` in a dropout window.

Fail-safe, not fail-loud (threat T-04-02-03): a non-finite ``det`` field is treated as a
miss (→ coast), and every divisor is guarded (``prev_area > 0`` before the ratio). The gate
never raises on data the validated ``Config`` already passed.

PURE; STATEFUL across ticks on the LOCKED track. Imports only ``math`` + stdlib — no numpy
at module top, no heavy deps (the Phase-1 lazy-import boundary). Clock-free, RNG-free
(determinism contract): the same locked-track sequence yields the same ``check`` outputs.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only — no runtime cost, no config↔tracking cycle
    from ..framing.signals import DetectionSignal
    from .params import TrackingParams

__all__ = ["PlausibilityGate"]


def _is_finite(det: "DetectionSignal") -> bool:
    """True iff every spatial field of ``det`` is finite (no NaN/inf). Pure.

    A non-finite det must be treated as a miss (→ coast) rather than producing a NaN
    displacement/ratio comparison that would silently accept or crash (threat T-04-02-03).
    Mirrors ``framing.scorer._is_finite_detection`` / ``competitor_lock._is_finite``.
    """
    return all(math.isfinite(v) for v in (det.cx, det.cy, det.w, det.h))


class PlausibilityGate:
    """Stateful inter-frame plausibility gate for ONE locked track (TRK-05).

    Drive it with ``check(det)`` once per tick on the locked candidate (or ``None`` on a
    miss). It returns the det when it is a plausible continuation of the last accepted box,
    else ``None`` (coast). Deterministic given its input sequence: the same
    ``list[DetectionSignal | None]`` produces the same ``check`` outputs every run.

    Args:
        params: the validated ``TrackingParams`` — ``max_displacement_per_tick`` (the
            teleport threshold) and ``max_size_ratio`` (``r``; the allowed area band
            ``[1/r, r]``).
    """

    def __init__(self, params: "TrackingParams") -> None:
        self.p = params
        self.prev: "DetectionSignal | None" = None  # the previous ACCEPTED locked box

    def check(self, det: "DetectionSignal | None") -> "DetectionSignal | None":
        """Gate one tick's locked candidate → the det (accepted) or None (coast).

        ``det is None`` (genuine miss) or a non-finite det → ``None``, ``prev`` unchanged. If
        there is a ``prev``, reject (``None``, ``prev`` NOT updated) when the center jump
        exceeds ``max_displacement_per_tick`` or the area ratio leaves ``[1/r, r]`` (D-06).
        Otherwise accept: ``prev = det`` (the new reference) and return ``det``.
        """
        if det is None or not _is_finite(det):
            return None  # genuine miss / degenerate → coast (prev unchanged)

        if self.prev is not None:
            disp = math.hypot(det.cx - self.prev.cx, det.cy - self.prev.cy)
            area = det.w * det.h
            prev_area = self.prev.w * self.prev.h
            # Divisor guard (mirror scorer.py): a zero-area reference → treat as an infinite
            # ratio so a box growing out of nothing is rejected rather than dividing by zero.
            ratio = (area / prev_area) if prev_area > 0 else float("inf")
            r = self.p.max_size_ratio
            if disp > self.p.max_displacement_per_tick or not (1.0 / r <= ratio <= r):
                # D-06: suspect swap (teleport or size-jump) → uncertain → coast. Critically
                # do NOT update self.prev — the suspect box must not become the reference.
                return None

        self.prev = det  # accepted; becomes the next continuity reference
        return det

    def reset(self) -> None:
        """Clear the continuity reference (call on a genuine loss / re-acquire).

        The orchestrator/eval calls this when the locked track is genuinely lost and a new
        one is acquired, so the next accepted box starts a FRESH continuity chain — the first
        det after ``reset`` has no ``prev`` to compare against and is accepted unconditionally
        (a legitimate new lock elsewhere on the field must not be rejected as a teleport).
        """
        self.prev = None
