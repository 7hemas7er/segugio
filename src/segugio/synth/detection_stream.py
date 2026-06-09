"""Deterministic, seedable synthetic detection-sequence generator (Phase-2 test substrate).

``detection_stream`` emits a reproducible ``list[DetectionSignal | None]`` for one camera
— the RAW per-detection signals (``cx, cy, w, h, conf, track_id``) the framing scorer
consumes. It is DISTINCT from ``score_stream``, which emits FINAL per-camera FSM scores
(``ScoreSample``); ``score_stream`` is the wrong layer for scorer input. The new behavior
here is emitting ``None`` inside a ``dropout`` window (the coast/TTL substrate) — something
``score_stream`` never does.

``multi_track_stream`` (Phase-4 substrate, plan 04-01) extends this additively: it emits
SEVERAL independent tracks per tick (each with its own id / path / size / conf / dropout)
so the competitor-lock + crossing brain tests (two dogs in/out of zone, sticky continuity,
teleport/crossing swap) have a deterministic source. It returns ``list[list[DetectionSignal]]``
(the present detections per tick — a track inside its dropout window contributes nothing).
The ``PATHS`` vocabulary grows additively (``"linear_left"``: cx ramps 0.8→0.2) so two
tracks can cross.

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

__all__ = ["detection_stream", "multi_track_stream", "PATHS"]

# The motion-path vocabulary (a typo fails fast, mirroring score_stream's scenario guard).
# "linear_left" (added 04-01) ramps cx 0.8→0.2 so two tracks can cross.
PATHS: tuple[str, ...] = ("linear_right", "linear_left", "static")


def _path_cx(path: str, frac: float) -> float:
    """The cx for a motion ``path`` at progress ``frac ∈ [0,1]`` (single source of truth).

    Shared by ``detection_stream`` and ``multi_track_stream`` so the path vocabulary stays
    consistent. Raises ``ValueError`` on an unknown path (fail-fast, mirroring score_stream).
    """
    if path == "linear_right":
        return 0.2 + 0.6 * frac
    if path == "linear_left":
        return 0.8 - 0.6 * frac
    if path == "static":
        return 0.5
    raise ValueError(f"unknown path {path!r}; expected one of {PATHS}")


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
        cx = _path_cx(path, frac)
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


def multi_track_stream(
    rng: np.random.Generator,
    cam_id: str,
    n_ticks: int,
    tracks: list[dict],
) -> list[list[DetectionSignal]]:
    """Emit several independent tracks per tick (the Phase-4 competitor-lock substrate).

    Each entry of ``tracks`` is a per-track spec dict carrying:
      * ``track_id`` (int, required) — the tracker id stamped on that track's signals;
      * ``path`` (str, required)     — one of ``PATHS`` (use ``"linear_right"`` +
        ``"linear_left"`` for a crossing);
      * ``size`` (float, required)   — constant normalized apparent size (w and h);
      * ``conf`` (float, required)   — base detector confidence;
      * ``dropout`` (``(start, end)`` half-open window, optional) — ticks where this track
        is absent (contributes nothing that tick — the per-track coast substrate);
      * ``conf_bias`` (float, optional, default 0.0) — additive confidence offset;
      * ``noise`` (float, optional, default 0.01) — stddev of the injected-rng jitter.

    Determinism contract (identical to ``detection_stream``): the injected ``rng`` is the
    ONLY randomness (one ``rng.normal`` draw per PRESENT detection, in tick-then-track
    order), ``t`` is the synthetic tick, every numeric field is ``float()``/``int()``-cast,
    and an unknown ``path`` fails fast. Same seed → byte-identical output.

    Args:
        rng: an INJECTED ``numpy.random.Generator`` (the only randomness source).
        cam_id: the camera identifier stamped on every signal.
        n_ticks: number of synthetic ticks (time runs 0..n_ticks-1).
        tracks: the per-track specs (see above).

    Returns:
        ``list[list[DetectionSignal]]`` of length ``n_ticks`` — the present detections at
        each tick across all tracks (a track inside its dropout window contributes nothing).

    Raises:
        ValueError: on an unknown ``path`` name in any track spec.
    """
    # Fail fast on an unknown path BEFORE drawing any randomness (deterministic guard).
    for spec in tracks:
        if spec["path"] not in PATHS:
            raise ValueError(
                f"unknown path {spec['path']!r}; expected one of {PATHS}"
            )

    per_tick: list[list[DetectionSignal]] = []
    for t in range(n_ticks):
        frac = t / max(n_ticks - 1, 1)  # divisor guard (one-tick run is degenerate)
        present: list[DetectionSignal] = []
        for spec in tracks:
            dropout = spec.get("dropout")
            if dropout is not None and dropout[0] <= t < dropout[1]:
                continue  # this track is absent this tick (per-track coast)
            noise = spec.get("noise", 0.01)
            conf_bias = spec.get("conf_bias", 0.0)
            cx = _path_cx(spec["path"], frac)
            cy = 0.5
            jx, jy = rng.normal(0.0, noise, 2)  # injected rng only — determinism
            present.append(
                DetectionSignal(
                    t,
                    cam_id,
                    float(np.clip(cx + jx, 0.0, 1.0)),
                    float(np.clip(cy + jy, 0.0, 1.0)),
                    float(spec["size"]),
                    float(spec["size"]),
                    float(np.clip(spec["conf"] + conf_bias, 0.0, 1.0)),
                    int(spec["track_id"]),
                )
            )
        per_tick.append(present)
    return per_tick
