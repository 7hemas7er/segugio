"""``CompetitorLock`` — the PURE stateful in-competition-dog selector (TRK-04).

This is the subject-selection brain (PITFALLS Pitfall 1): the size+centeredness framing
scorer alone will happily lock onto a large, central handler or a spectator dog. TRK-04
fixes that by selecting the track that is BOTH in-field (zone gate) AND moving (cumulative
motion energy over a short window) — the signature of a dog actually running the course —
and then STAYING on it until it genuinely disappears. It honors the locked CONTEXT
decisions:

  * D-03 acquire on zone-gate AND motion-energy: a candidate must be inside some field zone
    AND have cumulative displacement above ``motion_deadzone`` to be eligible; among the
    eligible, the one with the MOST cumulative motion wins (the bystander/handler standing
    still, or the spectator dog out of the field, is excluded).
  * D-04 sticky continuity: once locked, keep the locked ``track_id`` while it is present in
    the candidates (do NOT recompute the best each tick) — re-pick fires ONLY on genuine
    loss (the locked id absent from this tick's candidates). A momentarily-higher-motion
    competitor must NOT steal the lock mid-run (the cut-stability invariant).
  * D-05 per-camera independence: one ``CompetitorLock`` per camera; its ``locked_id`` and
    per-track history are its own — two instances over two streams never share state.

Fail-safe, not fail-loud (CONTEXT ``<specifics>`` + threat T-04-02-03): never raise on data
the validated ``Config`` already passed. A NaN/inf candidate is excluded from history,
alive-ids, and the in-field set → it can neither be locked nor crash the loop; the lock
simply coasts (returns ``None``). Mirrors ``CameraScorer._is_finite_detection``.

Clock-free, RNG-free (the FRM-07 / TRK-07 determinism contract): time enters only as the
injected ``tick``; there is zero randomness and zero wall-clock here. Imports only stdlib
(``collections`` / ``math``) — no numpy at module top, no heavy deps (the Phase-1
lazy-import boundary). The zone test REUSES the point-in-rect semantics of
``framing.terms.zone_of`` (it is NOT hand-rolled differently).
"""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only — no runtime cost, no config↔tracking cycle
    from ..framing.signals import DetectionSignal
    from .params import TrackingParams

__all__ = ["CompetitorLock"]


def _is_finite(c: "DetectionSignal") -> bool:
    """True iff every spatial field of the candidate is finite (no NaN/inf). Pure.

    A NaN/inf candidate must be treated as absent (→ excluded from history / alive-ids /
    in-field) rather than poisoning the lock or crashing the loop (threat T-04-02-03).
    Mirrors ``framing.scorer._is_finite_detection``.
    """
    return all(math.isfinite(v) for v in (c.cx, c.cy, c.w, c.h))


class CompetitorLock:
    """Stateful per-camera competitor selector (TRK-04). One instance per ``cam_id`` (D-05).

    Drive it with ``select(candidates, tick)`` once per tick, where ``candidates`` are the
    dog-class detections for THIS camera at THIS tick (``list[DetectionSignal]``). It returns
    the selected (locked) signal, or ``None`` when nothing is in-field (coast). Deterministic
    given its input *stream*: the same per-tick candidate lists produce the same selected
    sequence every run (no rng, no clock).

    Args:
        camera: the Phase-1 ``Camera`` (its ``zones`` are the validated normalized field
            rects the zone gate tests against).
        params: the validated ``TrackingParams`` — ``motion_window`` (the K-tick cumulative
            displacement window) and ``motion_deadzone`` (below → treat as stationary).
    """

    def __init__(self, camera, params: "TrackingParams") -> None:
        self.camera = camera
        self.p = params
        self.locked_id: int | None = None
        # Per-track bounded history of recent (tick, cx, cy) for the motion-energy window.
        # maxlen == motion_window so cumulative displacement is measured over exactly K ticks.
        self.hist: dict[int, deque[tuple[int, float, float]]] = {}

    def select(
        self, candidates: "list[DetectionSignal]", tick: int
    ) -> "DetectionSignal | None":
        """Select the locked in-competition dog for this tick (or None → coast).

        Per the RESEARCH.md skeleton: update per-track motion history, then (D-04) keep the
        locked id while it is present; otherwise (genuine loss or no lock) re-acquire on
        zone∧motion over the finite, in-field candidates. Nothing in-field → ``None``.
        """
        self._update_history(candidates, tick)

        # Only finite candidates are real this tick (NaN/inf → absent, fail-safe).
        finite = [c for c in candidates if _is_finite(c)]
        alive_ids = {c.track_id for c in finite}

        # D-04 sticky: keep the locked track while it is present — do NOT recompute the best.
        if self.locked_id is not None and self.locked_id in alive_ids:
            return self._by_id(finite, self.locked_id)

        # Genuine loss (locked id absent) OR no lock yet → re-acquire on zone AND motion (D-03).
        in_field = [c for c in finite if self._in_any_zone(c)]
        if not in_field:
            self.locked_id = None
            return None  # nothing in-field → coast

        # Among in-field tracks pick the one with the MOST cumulative motion (deadzone-floored).
        best = max(in_field, key=lambda c: self._motion_energy(c.track_id))
        self.locked_id = best.track_id
        return best

    def locked_motion_energy(self) -> float:
        """Public read of the LOCKED subject's motion energy (D-08 action-hold seed).

        Additive accessor (RESEARCH Open Q1 / Assumption A6): the orchestrator's action-hold
        derivation thresholds this value to set ``HoldInput.action`` (a catch/jump in progress
        → don't cut away). It ONLY READS the existing private ``_motion_energy`` for the current
        ``locked_id`` — no logic change, byte-identical to the internal path on the same input
        stream — and returns ``0.0`` when nothing is locked (``locked_id is None`` → no action
        to hold through). Pure / clock-free / stdlib-only, preserving the TRK-04 boundary.
        """
        if self.locked_id is None:
            return 0.0
        return self._motion_energy(self.locked_id)

    # --- internals ---------------------------------------------------------- #

    def _update_history(self, candidates: "list[DetectionSignal]", tick: int) -> None:
        """Append each FINITE candidate's (tick, cx, cy) to its track_id's bounded deque.

        A NaN/inf candidate is skipped (never enters history → cannot influence motion or be
        locked). The deque is created lazily per track_id with ``maxlen == motion_window`` so
        cumulative displacement is always measured over at most K ticks.
        """
        for c in candidates:
            if not _is_finite(c):
                continue
            hist = self.hist.get(c.track_id)
            if hist is None:
                hist = deque(maxlen=self.p.motion_window)
                self.hist[c.track_id] = hist
            hist.append((tick, c.cx, c.cy))

    def _in_any_zone(self, c: "DetectionSignal") -> bool:
        """True iff the candidate center is inside ANY of the camera's zone rects (D-03).

        Reuses the EXACT point-in-rect semantics of ``framing.terms.zone_of`` (do NOT
        hand-roll a different rule): ``x0 <= cx <= x1 and y0 <= cy <= y1`` over
        ``camera.zones``. The simpler boolean "is it in the field at all" is what the
        competitor-lock needs (not the named zone).
        """
        return any(
            z.rect[0] <= c.cx <= z.rect[2] and z.rect[1] <= c.cy <= z.rect[3]
            for z in self.camera.zones
        )

    def _motion_energy(self, track_id: int) -> float:
        """Cumulative displacement over the track's history window (the motion energy). Pure.

        Sum of consecutive ``hypot(dx, dy)`` over the bounded deque; returns ``0.0`` with
        fewer than 2 samples. A result below ``motion_deadzone`` is floored to ``0.0`` so a
        stationary handler/bystander scores zero motion (D-03 standing-dog exclusion) and a
        genuinely moving athlete dominates the ``max``.
        """
        hist = self.hist.get(track_id)
        if hist is None or len(hist) < 2:
            return 0.0
        total = 0.0
        pts = list(hist)
        for (_, cx0, cy0), (_, cx1, cy1) in zip(pts, pts[1:]):
            total += math.hypot(cx1 - cx0, cy1 - cy0)
        if total < self.p.motion_deadzone:
            return 0.0  # below the deadzone → stationary (excluded from the motion ranking)
        return total

    @staticmethod
    def _by_id(
        candidates: "list[DetectionSignal]", track_id: int
    ) -> "DetectionSignal | None":
        """Return the candidate whose ``track_id`` matches (the sticky return), else None."""
        for c in candidates:
            if c.track_id == track_id:
                return c
        return None
