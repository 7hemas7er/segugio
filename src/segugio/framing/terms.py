"""Pure scoring term functions — the math substrate the ``CameraScorer`` composes.

Every function here is PURE: a function of its inputs only, with NO randomness, NO
wall-clock, and NO I/O (the FRM-07 determinism guarantee). Time enters the scorer as an
injected ``tick``; randomness lives only in the synthetic generator. These functions
must NOT raise on edge data the validated ``Config`` already passed (fail-safe, not
fail-loud, in the live loop): every divisor is guarded (``max(w*h, 0)`` before sqrt,
``h > 0`` before aspect, ``sqrt(var + eps)`` with the validated positive
``ScorerParams.eps``), and every output is ``np.clip``-ed to [0,1] and ``float()``-cast
so a numpy scalar never leaks into a frozen record's ``==``.

The eight terms (RESEARCH.md Patterns 1/3/4/6/8 + Code Examples lines 450-515):
  gaussian_centeredness  - FRM-01: Gaussian falloff against an ideal point
  gaussian_size_band     - FRM-01/D-02: non-monotonic single-ideal band over sqrt(area)
  base_score             - FRM-01/D-01: centeredness-dominant weighted sum
  lead_room_target       - FRM-04: ideal shifts TOWARD motion, magnitude clamped
  zone_of                - FRM-03: point-in-rect lookup over camera.zones
  gate                   - FRM-03: multiply by framing_weights[role][zone] (or gate-down)
  conf_norm_step         - FRM-06: streaming EMA z-score with sqrt(var+eps) divisor floor
  plausibility_ok        - guard: conf floor / min-area / aspect band

Imports only numpy (and the framing record/param types). No heavy deps at module top
level — keeps the Phase-1 lazy-import boundary intact.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # type-only — no runtime import (avoids any config↔framing cycle)
    from .params import ScorerParams
    from .signals import DetectionSignal

__all__ = [
    "gaussian_centeredness",
    "gaussian_size_band",
    "base_score",
    "lead_room_target",
    "zone_of",
    "gate",
    "conf_norm_step",
    "plausibility_ok",
]


def gaussian_centeredness(
    cx: float, cy: float, ideal: tuple[float, float], sigma_c: float
) -> float:
    """FRM-01: Gaussian falloff of (cx,cy) against ``ideal``. Pure; ∈(0,1].

    Maximal (==1.0) when (cx,cy) == ideal; strictly decreasing as Euclidean distance
    from the ideal grows. ``sigma_c`` (config-bounded > 0) sets how forgiving "centered"
    is. A function of inputs only — no rng, no clock.
    """
    dx = cx - ideal[0]
    dy = cy - ideal[1]
    return float(np.exp(-(dx * dx + dy * dy) / (2.0 * sigma_c * sigma_c)))


def gaussian_size_band(w: float, h: float, ideal_size: float, sigma_s: float) -> float:
    """FRM-01/D-02: non-monotonic size band over ``sqrt(max(w*h, 0))``. Pure; ∈(0,1].

    PEAKS at ``size == ideal_size`` and falls off for BOTH smaller and larger sizes —
    the "bigger is not always better" guarantee. Guards a degenerate negative area via
    ``max(w*h, 0)`` so it never raises. A function of inputs only.
    """
    size = float(np.sqrt(max(w * h, 0.0)))  # apparent scale ∈[0,1]; NOT monotonic area
    d = size - ideal_size
    return float(np.exp(-(d * d) / (2.0 * sigma_s * sigma_s)))


def base_score(
    c: float, s: float, conf_norm: float, w_c: float, w_s: float, w_conf: float
) -> float:
    """FRM-01/D-01: centeredness-dominant weighted sum, clipped to [0,1]. Pure float.

    ``w_c*c + w_s*s + w_conf*conf_norm`` with weights summing to 1 (validated by
    ``ScorerParams``). ``np.clip`` is belt-and-suspenders — never raises.
    """
    return float(np.clip(w_c * c + w_s * s + w_conf * conf_norm, 0.0, 1.0))


def lead_room_target(
    vx: float,
    vy: float,
    lead_gain: float,
    lead_max: float,
    v_deadzone: float,
) -> tuple[float, float]:
    """FRM-04: the ideal centeredness target, shifted TOWARD the motion direction. Pure.

    A resting dog (speed below ``v_deadzone``) gets the centered ideal ``(0.5, 0.5)`` so
    a still dog is not penalized. Otherwise the ideal shifts along the unit motion
    direction by ``min(lead_gain*speed, lead_max)`` — clamped so a fast dog can't push
    the ideal off-frame — and each coordinate is clipped to [0,1]. Sign: ``vx > 0`` →
    ``ideal_x > 0.5`` (the proven lead-room sign: dog behind center, room ahead).
    """
    speed = float(np.hypot(vx, vy))
    if speed < v_deadzone:
        return (0.5, 0.5)
    ux, uy = vx / speed, vy / speed  # unit motion direction (speed >= deadzone > 0)
    lead = min(lead_gain * speed, lead_max)  # magnitude ∝ speed, clamped
    return (
        float(np.clip(0.5 + lead * ux, 0.0, 1.0)),
        float(np.clip(0.5 + lead * uy, 0.0, 1.0)),
    )


def zone_of(cx: float, cy: float, camera, framing_weights=None) -> str | None:
    """FRM-03: map (cx,cy) to a zone name via point-in-rect over ``camera.zones``. Pure.

    Returns the matched zone name, or ``None`` if the point is outside ALL zones (the
    caller gate-downs rather than zeroing). On OVERLAP, pick the HIGHEST-weight match
    (``framing_weights[camera.role][name]``) when ``framing_weights`` is supplied
    (CONTEXT Claude's-Discretion); this falls back to first-match for the non-overlapping
    example configs where the two rules coincide. Never raises on a missing weight key
    (defaults that candidate's weight to neutral 1.0 for the comparison).
    """
    matches = [
        z.name
        for z in camera.zones
        if z.rect[0] <= cx <= z.rect[2] and z.rect[1] <= cy <= z.rect[3]
    ]
    if not matches:
        return None
    if framing_weights is None or len(matches) == 1:
        return matches[0]  # first-match (== highest-weight for non-overlapping configs)
    role_weights = framing_weights.get(camera.role, {})
    return max(matches, key=lambda name: role_weights.get(name, 1.0))


def gate(
    base: float,
    camera,
    zone_name: str | None,
    framing_weights,
    out_of_bounds_factor: float,
) -> float:
    """FRM-03: multiply ``base`` by ``framing_weights[role][zone]`` (or gate-down). Pure.

    ``zone_name is None`` (outside all zones) → ``base * out_of_bounds_factor`` (a small
    suppression, NOT 0, so a dog clipping a zone edge isn't disqualified). A missing
    weight key defaults to neutral ``1.0`` — the scorer never raises on data the config
    already validated. Output clipped to [0,1].
    """
    if zone_name is None:
        return float(np.clip(base * out_of_bounds_factor, 0.0, 1.0))
    weight = framing_weights.get(camera.role, {}).get(zone_name, 1.0)
    return float(np.clip(base * weight, 0.0, 1.0))


def conf_norm_step(
    state: dict,
    conf: float,
    beta: float,
    z_clip: float,
    eps: float,
    warmup: int,
) -> tuple[float, dict]:
    """FRM-06: one step of the streaming per-camera confidence z-score. Pure; O(1) state.

    Returns ``(conf_norm, new_state)`` where ``state`` carries ``{n, mu, var}``. The first
    sample and the warmup window pass ``conf`` through (the per-camera baseline isn't yet
    stable); afterwards returns a clipped z-score mapped to [0,1] (0.5 = "typical for this
    camera"). The ``sqrt(var + eps)`` denominator uses the PASSED ``eps`` (the validated
    ``ScorerParams.eps`` divisor floor, never a hardcoded literal) so it never raises even
    when ``var == 0``. No rng, no clock.
    """
    n = state["n"] + 1
    if n == 1:
        new_state = {"n": 1, "mu": conf, "var": 0.0}
        return float(conf), new_state  # passthrough on first sample
    mu, var = state["mu"], state["var"]
    delta = conf - mu
    mu = mu + beta * delta
    var = (1.0 - beta) * (var + beta * delta * delta)
    new_state = {"n": n, "mu": mu, "var": var}
    if n <= warmup:
        return float(conf), new_state  # passthrough until the baseline stabilizes
    z = delta / np.sqrt(var + eps)  # eps-guarded divisor → never raises (var may be 0)
    return float(np.clip(0.5 + z / (2.0 * z_clip), 0.0, 1.0)), new_state


def plausibility_ok(det: "DetectionSignal", p: "ScorerParams") -> bool:
    """Guard: reject implausible detections (shadow/noise) before scoring. Pure.

    Returns ``False`` if confidence is below ``conf_floor``, the box area ``w*h`` is below
    ``min_area``, or the aspect ratio ``w/h`` is outside ``[aspect_lo, aspect_hi]``. A
    rejected detection is treated by the scorer as "no detection this tick" (→ coast).
    Guards ``h > 0`` before the aspect division so a degenerate box never raises.
    """
    if det.conf < p.conf_floor:
        return False
    if det.w * det.h < p.min_area:
        return False
    if det.h <= 0:
        return False  # zero/negative height → implausible (and guards the division)
    ar = det.w / det.h
    if not (p.aspect_lo <= ar <= p.aspect_hi):
        return False
    return True
