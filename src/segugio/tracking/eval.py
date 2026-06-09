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

if TYPE_CHECKING:  # type-only — keeps numpy/cv2/ultralytics off the runtime import path
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
