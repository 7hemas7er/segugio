"""``CameraScorer`` — the stateful per-camera object composing the pure ``terms``.

This is the heart of the framing scorer (Phase 2): a small per-camera state machine
whose ``update(det, tick)`` composes the eight pure ``terms`` functions into a single
EMA-smoothed [0,1] ``CameraScore`` the Phase-3 FSM consumes. It honors every locked
CONTEXT decision:

  * D-01 centeredness-dominant base score (via ``base_score`` weights from ``ScorerParams``).
  * D-02 non-monotonic Gaussian size band (via ``gaussian_size_band``).
  * D-05 fixed-α EMA read once at construction; cold start seeds ``s_0 = raw_0`` (NOT 0).
  * D-06 lead-room shifts the ideal TOWARD motion, magnitude ∝ clamped speed, with a
    velocity deadzone → no lead; velocity is a finite difference over the last
    ``vel_window`` samples of the LOCKED track; a track-id swap clears history (speed 0).
  * D-07 motion-adaptive α is DEFERRED — the single fixed ``alpha`` read at construction is
    the clean hook a future upgrade plugs into. No velocity-coupled α is computed here.

This plan (02-02) implements the **present-detection branch** of ``update`` (the four
behaviors that fire when a plausible detection IS present each tick: EMA, zone-multiplier,
lead-room, conf-norm). The dropout/coast branch (FRM-05, TTL countdown) is owned by 02-03;
here it is a minimal placeholder that holds the last EMA without the TTL countdown, marked
with a ``# 02-03: coast/TTL`` seam comment.

Fail-safe, not fail-loud (CONTEXT ``<specifics>`` + the threat register): the scorer never
raises on data the validated ``Config`` already passed. A NaN/inf detection is treated as
"no detection" (delegates to the coast branch); the emitted EMA is ``np.clip``-ed to [0,1];
``gate`` defaults a missing weight to neutral ``1.0``; every divisor is guarded.

Clock-free and RNG-free (FRM-07): time is the injected ``tick``; there is zero randomness
and zero wall-clock here. Imports only ``numpy`` + stdlib ``collections`` + the framing
records/terms — no heavy deps at module top level (the Phase-1 lazy-import boundary).
"""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from .signals import CameraScore, ScorerStatus
from .terms import (
    base_score,
    conf_norm_step,
    gate,
    gaussian_centeredness,
    gaussian_size_band,
    lead_room_target,
    plausibility_ok,
    zone_of,
)

if TYPE_CHECKING:  # type-only imports — no runtime cost, no config↔framing cycle
    from .params import ScorerParams
    from .signals import DetectionSignal

__all__ = ["CameraScorer"]


def _is_finite_detection(det: "DetectionSignal") -> bool:
    """True iff every spatial/confidence field of ``det`` is finite (no NaN/inf).

    A NaN/inf detection must be treated as "no detection" (→ coast) rather than poisoning
    the EMA (threat T-2-01). Pure — a function of ``det`` only.
    """
    return all(
        math.isfinite(v) for v in (det.cx, det.cy, det.w, det.h, det.conf)
    )


class CameraScorer:
    """Stateful per-camera framing scorer (present-detection path; FRM-02/03/04/06).

    Construct one per camera, then drive it with ``update(det, tick)`` once per tick.
    The object is deterministic given its input *stream*: the same
    ``list[DetectionSignal | None]`` produces the same ``list[CameraScore]`` every run
    (no rng, no clock — the FRM-07 contract).

    Args:
        camera: the Phase-1 ``Camera`` (``role`` + normalized ``zones``) for zone gating.
        params: the validated ``ScorerParams`` (all tuning seeds, incl. ``eps``).
        framing_weights: ``Config.framing_weights`` — ``{role: {zone: multiplier}}``.
        alpha: the fixed EMA factor (``Thresholds.alpha``). Read ONCE here — this single
            construction seam is the clean hook D-07 leaves for a future motion-adaptive
            α; no α is computed from velocity in this class.
        lead_gain: the per-discipline lead-room gain (``FramingDefaults.lead_room``).
        ttl_ticks: the coast TTL in ticks (precomputed ``ttl_seconds * fps``), kept here so
            the scorer stays clock-free. 02-03 exercises the countdown; this plan only
            seeds the counter on a present detection.
    """

    def __init__(
        self,
        camera,
        params: "ScorerParams",
        framing_weights,
        alpha: float,
        lead_gain: float,
        ttl_ticks: int,
    ) -> None:
        self.camera = camera
        self.p = params
        self.fw = framing_weights
        self.alpha = alpha
        self.lead_gain = lead_gain
        self.ttl_ticks = ttl_ticks

        self.ema: float | None = None
        self.status: ScorerStatus = ScorerStatus.lost
        self.hist: deque[tuple[int, float, float]] = deque(maxlen=params.vel_window + 1)
        self.ttl: int = 0
        self.last_track: int | None = None
        self.conf_state: dict = {"n": 0, "mu": 0.0, "var": 0.0}

    def _velocity(self) -> tuple[float, float]:
        """Finite-difference velocity over the oldest-vs-newest history sample. Pure.

        Returns ``(0.0, 0.0)`` when fewer than 2 samples are held or the tick span is
        non-positive (guards the divisor — threat T-2-01). Velocity is in normalized
        units per tick (resolution-independent because positions are normalized).
        """
        if len(self.hist) < 2:
            return (0.0, 0.0)
        tick_old, cx_old, cy_old = self.hist[0]
        tick_new, cx_new, cy_new = self.hist[-1]
        dt = tick_new - tick_old
        if dt <= 0:  # guard: non-positive span → no velocity
            return (0.0, 0.0)
        return ((cx_new - cx_old) / dt, (cy_new - cy_old) / dt)

    def update(self, det: "DetectionSignal | None", tick: int) -> CameraScore:
        """Score one tick. Composes the pure terms → EMA-smoothed ``CameraScore``.

        Present-detection branch (this plan): a plausible, finite detection drives the
        full composition (conf-norm → velocity → lead-room ideal → centeredness → size →
        base → zone gate → EMA), seeds the TTL, and marks ``tracking``. A missing,
        implausible, or NaN/inf detection falls through to the coast placeholder.
        """
        if (
            det is not None
            and _is_finite_detection(det)
            and plausibility_ok(det, self.p)
        ):
            p = self.p
            # New/swapped track → reset the velocity history (speed 0 until rebuilt; D-06).
            if det.track_id != self.last_track:
                self.hist.clear()
                self.last_track = det.track_id

            # FRM-06: per-camera streaming conf z-score (the `eps` divisor floor is passed,
            # never a literal). Confidence enters via conf_norm, NOT raw det.conf.
            conf_norm, self.conf_state = conf_norm_step(
                self.conf_state, det.conf, p.beta, p.z_clip, p.eps, p.warmup
            )

            # FRM-04: finite-difference velocity over the locked track's recent history.
            self.hist.append((tick, det.cx, det.cy))
            vx, vy = self._velocity()
            ideal = lead_room_target(vx, vy, self.lead_gain, p.lead_max, p.v_deadzone)

            # FRM-01: centeredness-dominant base score (against the lead-shifted ideal).
            c = gaussian_centeredness(det.cx, det.cy, ideal, p.sigma_c)
            s = gaussian_size_band(det.w, det.h, p.ideal_size, p.sigma_s)
            base = base_score(c, s, conf_norm, p.w_c, p.w_s, p.w_conf)

            # FRM-03: zone lookup × framing_weights[role][zone] (or out-of-bounds gate-down).
            zone = zone_of(det.cx, det.cy, self.camera, self.fw)
            raw = gate(base, self.camera, zone, self.fw, p.out_of_bounds_factor)

            # FRM-02/D-05: cold start seeds s_0 = raw_0 (NOT 0); else the fixed-α recurrence.
            self.ema = (
                raw
                if self.ema is None
                else self.alpha * raw + (1.0 - self.alpha) * self.ema
            )
            self.ttl = self.ttl_ticks
            self.status = ScorerStatus.tracking
        else:
            # 02-03: coast/TTL — replace this placeholder with the coast/TTL countdown
            # (hold the EMA for ttl_ticks → status coasting; then ema=0.0 → status lost).
            # This plan only needs update() callable on an absent detection: hold the last
            # EMA and status (no countdown, no behavior asserted here). Never feed raw=0.
            self.status = self.status

        return CameraScore(
            tick,
            self.camera.id,
            float(np.clip(self.ema if self.ema is not None else 0.0, 0.0, 1.0)),
            self.status,
        )
