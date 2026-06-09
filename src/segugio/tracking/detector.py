"""TRK-01 heavy edge — one persistent ``YOLO().track`` wrapper per camera + dog-by-name.

``PerCameraTracker`` is the ONLY YOLO inference site in Segugio. It owns a single
``YOLO`` object per ``cam_id`` so each camera keeps its OWN ``predictor.trackers`` state
across ticks (``persist=True``) — never a list of frames passed to one tracker, which
would build ONE tracker and mix track IDs across cameras (Ultralytics #13107) and pollute
the native-ReID embeddings (Pitfall 2). One instance per ``cam_id`` is the contract.

The ``.track()`` call passes ``end2end=False`` — this is the load-bearing TRK-02
correction. ``yolo26s.pt`` defaults to ``end2end=True``, which fails the native-ReID hook
condition in Ultralytics' ``on_predict_start`` and SILENTLY downloads a ``yolo26n-cls.pt``
classifier as the ReID encoder. ``end2end=False`` activates the standard one-to-many Detect
head, satisfies the hook, and engages the zero-extra-weight native lambda encoder. The
companion ``reid_check.assert_native_reid_engaged`` is the HARD startup gate that proves it.

Anti-patterns enforced here (04-RESEARCH.md "Anti-Patterns to Avoid"):
  * NEVER a frame list to one ``.track()`` (one tracker per ``cam_id``);
  * NEVER the default ``end2end=True`` (disables native ReID);
  * the tracker ``track_id`` is ADVISORY only — the locked-subject identity is the
    competitor-lock's, enforced by the plausibility gate (04-02).

Live-robustness fail-safe (RBT analogue, the no-crash requirement): ``track()`` must NOT
raise on a blank / zero-size / decode-failure frame. Such a frame degrades to "no
detection" (an empty ``Results`` → coast), never a crash.

Lazy-import boundary: ``ultralytics`` / ``torch`` are imported INSIDE methods, never at
module top, so ``import segugio.tracking.detector`` succeeds with the heavy stack absent
(proven by ``tests/test_tracking_import_smoke.py``). ``loguru`` is a LIGHT runtime dep
(already used by ``segugio.fixtures``) and is imported at module top.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # type-only — keeps heavy deps off the runtime import path
    import numpy as np

__all__ = ["PerCameraTracker", "resolve_dog_index"]


def resolve_dog_index(model, configured_index: int) -> int:
    """Resolve the ``dog`` class index BY NAME from ``model.names``, reconciled with config.

    Reads ``model.names`` (an ``{index: name}`` mapping) and returns the index whose name is
    ``"dog"``. NEVER hardcodes 16: a custom mono-class model has ``dog`` at index 0, and
    hardcoding 16 there would silently filter out every detection (CLAUDE.md "What NOT to
    Use", CFG-04). The configured ``class_index`` is carried by ``ModelConfig`` (default 16);
    Phase 4 VERIFIES it against the loaded model — the name-resolved index wins, with a
    warning when the two disagree.

    Args:
        model: a loaded ``ultralytics.YOLO`` (or anything exposing ``.names`` as
            ``{int: str}``).
        configured_index: the ``ModelConfig.class_index`` value to reconcile against.

    Returns:
        The name-resolved ``dog`` class index.

    Raises:
        ValueError: if the model exposes no ``"dog"`` class (a wrong/custom model).
    """
    names = model.names  # {idx: name}, e.g. {0: 'person', ..., 16: 'dog', ...}
    dog_indices = [i for i, n in names.items() if n == "dog"]
    if not dog_indices:
        raise ValueError(
            f"model has no 'dog' class; cannot track — names={names}"
        )
    resolved = dog_indices[0]
    if resolved != configured_index:
        logger.warning(
            "configured class_index={} but model.names resolves dog={} — using resolved",
            configured_index,
            resolved,
        )
    return resolved


class PerCameraTracker:
    """One persistent ``YOLO().track(persist=True)`` per ``cam_id`` (TRK-01).

    Construct ONE instance per camera so each owns its own ``predictor.trackers`` state.
    ``track(frame)`` runs inference + BoT-SORT on a SINGLE numpy BGR crop for THIS camera and
    returns the per-frame ``Results`` (or ``None`` on a blank/decode-failure frame → coast).
    """

    def __init__(self, model_path, dog_idx: int, tracker_yaml) -> None:
        """Load the YOLO model for this camera (lazy heavy import inside the constructor).

        Args:
            model_path: path to the YOLO weights (e.g. ``ModelConfig.path`` → ``yolo26s.pt``).
            dog_idx: the dog class index, resolved BY NAME via :func:`resolve_dog_index`
                (never hardcoded 16).
            tracker_yaml: path to ``botsort_dog.yaml`` (a bare name resolvable by Ultralytics
                ``check_yaml`` if it lives on the search path, or an absolute path).
        """
        from ultralytics import YOLO  # lazy — heavy import INSIDE the constructor

        self.model = YOLO(str(model_path))  # own predictor.trackers state per camera
        self.dog_idx = int(dog_idx)
        self.tracker_yaml = str(tracker_yaml)

    def track(self, frame: "np.ndarray"):
        """Run one persistent track step on a single BGR crop for THIS camera.

        Passes ``end2end=False`` (CRITICAL — engages native ReID, TRK-02), ``persist=True``
        (keep this camera's tracker state across ticks), ``classes=[dog_idx]`` (dog only),
        ``tracker=botsort_dog.yaml``, and ``verbose=False``. Returns the single ``Results``.

        Fail-safe: a blank / zero-size / ``None`` frame degrades to ``None`` (no detection →
        coast), never a crash — the live no-crash requirement (RBT analogue).

        Args:
            frame: ONE numpy BGR crop for this camera (the ``ClipFrameSource`` crop, or an
                NDI frame in Phase 5).

        Returns:
            The per-frame ``Results``, or ``None`` when the frame is blank / unusable.
        """
        # Degrade a blank/decode-failure frame to "no detection" BEFORE touching inference.
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        try:
            results = self.model.track(
                frame,
                persist=True,  # keep THIS camera's tracker state across ticks
                classes=[self.dog_idx],  # dog only (index resolved BY NAME at startup)
                tracker=self.tracker_yaml,  # botsort_dog.yaml (check_yaml-resolvable)
                end2end=False,  # ◀ CRITICAL: enables native-feature ReID (TRK-02)
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001 — live-robustness: never crash on one bad frame
            logger.warning("track() degraded a frame to no-detection (coast): {}", exc)
            return None
        return results[0]  # one Results for the single frame
