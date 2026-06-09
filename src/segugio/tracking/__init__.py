"""segugio.tracking — the per-camera YOLO+BoT-SORT tracking layer (Phase 4).

Maps a YOLO ``Results`` row (``Results.boxes.xywhn`` / ``.id`` / ``.conf``) to the frozen
``DetectionSignal`` the Phase-2 framing scorer consumes (TRK-03), selects the
in-competition dog over spectators/handler via cumulative motion (TRK-04), and gates
implausible inter-frame jumps (TRK-05) — feeding the existing scorer→FSM→OBS pipeline.

This package surface is PURE: it re-exports only the light, CPU-only symbols that import
no heavy runtime (``torch`` / ``ultralytics`` / ``cv2`` / ``cyndilib`` / ``obsws_python``),
so ``import segugio.tracking`` succeeds on a machine with the heavy stack absent (the
lazy-import boundary, proven by ``tests/test_tracking_import_smoke.py``).

The heavy-edge modules (``detector`` / ``reid_check`` / ``frame_source``, added by 04-03)
lazy-import their heavy deps INSIDE functions and are deliberately NOT re-exported here —
keeping this top-level surface minimal and pure. ``eval`` (04-04) is SPLIT: its PURE metric
counter ``compute_metrics`` (above the lazy-import boundary, importing nothing heavy) IS
re-exported here; its heavy overlay/clip-driver functions (``render_overlay`` /
``run_clip_eval``, cv2 imported in-function) are NOT.

Plan 04-01 establishes the substrate symbols: ``TrackingParams`` (the additive config
sub-model) and ``signals_from_boxes`` (the pure TRK-03 mapper). Plan 04-04 adds the pure
``compute_metrics`` (D-08 metric counters).
"""

from __future__ import annotations

from .eval import compute_metrics
from .params import TrackingParams
from .signals_map import signals_from_boxes

__all__ = [
    "TrackingParams",
    "compute_metrics",
    "signals_from_boxes",
]
