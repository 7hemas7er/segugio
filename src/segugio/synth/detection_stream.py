"""Deterministic, seedable synthetic detection-sequence generator (Phase-2 test substrate).

``detection_stream`` emits a reproducible ``list[DetectionSignal | None]`` for one camera
— the RAW per-detection signals (``cx, cy, w, h, conf, track_id``) the framing scorer
consumes. It is DISTINCT from ``score_stream``, which emits FINAL per-camera FSM scores
(``ScoreSample``); ``score_stream`` is the wrong layer for scorer input. The new behavior
here is emitting ``None`` inside a ``dropout`` window (the coast/TTL substrate) — something
``score_stream`` never does.

Knobs: ``path`` (motion path for lead-room sign tests), ``size`` (apparent scale),
``conf`` + ``conf_bias`` (the "brighter camera" knob for the FRM-06 anti-bias test),
``dropout`` (a ``(start, end)`` window of missed detections → coast), ``noise``,
``track_id``.

Determinism contract (RESEARCH.md Pattern 4 + Pitfall 3):
  * the injected ``numpy.random.Generator`` is the ONLY source of randomness;
  * the module never seeds or calls the legacy global numpy RNG;
  * no wall-clock is read — ``t`` is the synthetic tick index.
  Same seed -> byte-identical ``list[DetectionSignal | None]``; different seed -> different.

Imports only ``numpy`` + ``segugio.framing.signals`` (the dependency points UP onto the
lower ``framing`` layer; ``framing.signals`` must never import ``synth``). Heavy-import-free
so the 01-01 import-smoke surface stays green.
"""

from __future__ import annotations

import numpy as np

from segugio.framing.signals import DetectionSignal

__all__ = ["detection_stream", "PATHS"]

# The motion-path vocabulary (a typo fails fast, mirroring score_stream's scenario guard).
PATHS: tuple[str, ...] = ("linear_right", "static")


def detection_stream(
    rng: np.random.Generator,
    cam_id: str,
    n_ticks: int,
    *,
    path: str = "linear_right",
    size: float = 0.30,
    conf: float = 0.7,
    conf_bias: float = 0.0,
    dropout: tuple[int, int] | None = None,
    noise: float = 0.01,
    track_id: int = 1,
) -> list[DetectionSignal | None]:
    """Emit a reproducible raw-detection stream for one camera.

    Args:
        rng: an INJECTED ``numpy.random.Generator`` (the only randomness source).
        cam_id: the camera identifier stamped on every signal.
        n_ticks: number of synthetic ticks (time runs 0..n_ticks-1).
        path: ``"linear_right"`` (cx ramps 0.2→0.8) | ``"static"`` (cx held at 0.5).
        size: constant normalized apparent size (both w and h).
        conf: base detector confidence.
        conf_bias: additive confidence offset (the "brighter camera" knob, FRM-06).
        dropout: a ``(start, end)`` half-open tick window emitting ``None`` (coast/TTL).
        noise: stddev of the Gaussian center jitter (injected rng only).
        track_id: the tracker id stamped on every signal.

    Returns:
        ``list[DetectionSignal | None]`` of length ``n_ticks``. ``None`` marks a dropout
        tick (no detection). Same ``rng`` seed -> identical list.

    Raises:
        ValueError: on an unknown ``path`` name.
    """
    if path not in PATHS:
        raise ValueError(f"unknown path {path!r}; expected one of {PATHS}")

    out: list[DetectionSignal | None] = []
    for t in range(n_ticks):
        if dropout is not None and dropout[0] <= t < dropout[1]:
            out.append(None)  # coast/TTL case — no detection this tick
            continue
        frac = t / max(n_ticks - 1, 1)  # divisor guard (one-tick run is degenerate)
        cx = 0.2 + 0.6 * frac if path == "linear_right" else 0.5
        cy = 0.5
        jx, jy = rng.normal(0.0, noise, 2)  # injected rng only — determinism
        out.append(
            DetectionSignal(
                t,
                cam_id,
                float(np.clip(cx + jx, 0.0, 1.0)),
                float(np.clip(cy + jy, 0.0, 1.0)),
                size,
                size,
                float(np.clip(conf + conf_bias, 0.0, 1.0)),
                track_id,
            )
        )
    return out
