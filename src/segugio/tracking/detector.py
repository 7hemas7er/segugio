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

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # type-only — keeps heavy deps off the runtime import path
    import numpy as np

__all__ = ["PerCameraTracker", "resolve_dog_index"]


def _resolve_tracker_yaml(tracker_yaml) -> str:
    """Resolve a BoT-SORT tracker yaml to an absolute path, failing loudly if absent.

    Ultralytics' ``check_yaml`` only resolves its built-in tracker names (``botsort.yaml`` /
    ``bytetrack.yaml``) or a path it can find from the CWD — it does NOT search Segugio's
    top-level ``trackers/`` dir. Passing the bare name ``"botsort_dog.yaml"`` therefore made
    ``.track()`` raise ``'botsort_dog.yaml' does not exist``, which the per-frame fail-safe
    silently degraded to coast on EVERY frame (so ``predictor.trackers`` was never built and
    native ReID never engaged — TRK-01/TRK-02 dead on the real path). Resolving to an absolute
    path here and validating at construction makes a missing/misnamed tracker config fail
    LOUDLY at startup instead of as a silent perpetual coast.

    Resolution order:
      1. the path as given (absolute, or relative to the CWD) if it is a file;
      2. Segugio's repo-level ``trackers/<name>`` dir, located relative to this package;
      3. otherwise raise ``FileNotFoundError`` listing every location searched.

    Args:
        tracker_yaml: a bare name (``"botsort_dog.yaml"``), a CWD-relative path, or an
            absolute path to the BoT-SORT override yaml.

    Returns:
        An absolute filesystem path (str) that Ultralytics ``.track(tracker=...)`` can load.

    Raises:
        FileNotFoundError: if the yaml is not found at any candidate location.
    """
    given = Path(tracker_yaml)
    if given.is_file():
        return str(given.resolve())
    # src-layout: detector.py → tracking → segugio → src → <repo root> (parents[3]).
    repo_trackers = Path(__file__).resolve().parents[3] / "trackers" / given.name
    if repo_trackers.is_file():
        return str(repo_trackers)
    raise FileNotFoundError(
        f"tracker yaml {tracker_yaml!r} not found — looked at {given.resolve()} and "
        f"{repo_trackers}. Pass an absolute path or place it in the repo trackers/ dir."
    )


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

    def __init__(self, model_path, dog_idx: int, tracker_yaml, use_fp16: bool = False) -> None:
        """Load the YOLO model for this camera (lazy heavy import inside the constructor).

        Args:
            model_path: path to the YOLO weights (e.g. ``ModelConfig.path`` → ``yolo26s.pt``).
            dog_idx: the dog class index, resolved BY NAME via :func:`resolve_dog_index`
                (never hardcoded 16).
            tracker_yaml: ``botsort_dog.yaml`` as a bare name, CWD-relative, or absolute path.
                Resolved to an absolute path via :func:`_resolve_tracker_yaml` and validated to
                exist HERE — a missing/misnamed config fails loudly at construction rather than
                degrading to a silent per-frame coast (Ultralytics ``check_yaml`` does NOT search
                the repo ``trackers/`` dir, so the bare name alone does not resolve).
            use_fp16: when True, the per-camera fallback ``track()`` runs ``half=True`` (eager
                FP16) so the serial path also runs FP16 if the batched fan-out is bypassed.
                Defaults to False (FP32, today's path). The batched fan-out threads FP16 via
                ``batched_detect_dispatch(..., use_fp16=...)`` directly, independent of this.
        """
        from ultralytics import YOLO  # lazy — heavy import INSIDE the constructor

        # Resolve + validate BEFORE loading the model so a bad tracker path fails fast.
        self.tracker_yaml = _resolve_tracker_yaml(tracker_yaml)
        self.model = YOLO(str(model_path))  # own predictor.trackers state per camera
        self.dog_idx = int(dog_idx)
        self.use_fp16 = bool(use_fp16)
        # Eager ``.pt`` is NOT engine-backed — the HARD TRK-02 ReID gate stays a raise (06-02).
        # The 06-03 engine-backed tracker sets this True so the gate downgrades to a warning.
        self.is_engine = False
        # Lazily-built persistent BoT-SORT tracker for the Track-B batched ``update()`` path.
        self._bot = None

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
                half=self.use_fp16,  # eager FP16 toggle (Wave-1 measurement); FP32 by default
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001 — live-robustness: never crash on one bad frame
            logger.warning("track() degraded a frame to no-detection (coast): {}", exc)
            return None
        return results[0]  # one Results for the single frame

    def _ensure_persistent_tracker(self, frame: "np.ndarray") -> None:
        """Build THIS camera's persistent BoT-SORT tracker + register the native-ReID hook.

        The Track-B batched path bypasses ``model.track()`` (it runs ONE shared
        ``model.predict()`` over all cameras), so the per-camera ``predictor.trackers`` +
        the native-ReID forward hook are never built. We run ONE warmup ``self.track(frame)``
        here — that registers Ultralytics' Detect forward-pre-hook on the shared model graph
        (so the subsequent batched ``predict()`` populates ``result.feats`` for native ReID)
        AND constructs this camera's persistent ``BOTSORT`` in ``predictor.trackers[0]``. We
        then cache that tracker as ``self._bot`` and drive it directly on later ticks.
        """
        if self._bot is not None:
            return
        self.track(frame)  # warmup: registers the native-ReID hook + builds predictor.trackers
        predictor = getattr(self.model, "predictor", None)
        trackers = getattr(predictor, "trackers", None) if predictor is not None else None
        if trackers:
            self._bot = trackers[0]  # this camera's persistent BoT-SORT (one per cam_id)

    def update(self, detections, frame: "np.ndarray"):
        """Dispatch ONE camera's pre-computed batched detections into its OWN persistent tracker.

        The Track-B association entry point (``loop._batched_inference`` → ``batched.py``): the
        single shared ``model.predict()`` already ran detection over all cameras; ``detections``
        is THIS camera's ``Results`` slice. We drive this camera's persistent ``BOTSORT.update``
        with the detection boxes + the native-ReID ``feats`` carried on the result, then fold the
        track ids back onto the ``Results`` so the consumer (``_arrays_from_results``) sees
        confirmed track ids — the SAME shape ``track()`` returns. One tracker per ``cam_id``
        (#13107); never a frame list to one tracker.

        Fail-safe (RBT-04): any failure (a blank slice, a tracker raise) degrades to ``None``
        (coast), never a crash.

        Args:
            detections: this camera's ``Results`` slice from the batched ``model.predict()``.
            frame: this camera's BGR frame (the tracker's ``img`` for GMC / ReID).

        Returns:
            The per-camera ``Results`` with track ids folded in, or ``None`` (coast).
        """
        if detections is None or frame is None or getattr(frame, "size", 0) == 0:
            return None
        try:
            import torch  # lazy — heavy import inside the method

            self._ensure_persistent_tracker(frame)
            if self._bot is None:
                return None
            boxes = getattr(detections, "boxes", None)
            if boxes is None:
                return None
            det = boxes.cpu().numpy()
            tracks = self._bot.update(
                det, frame, getattr(detections, "feats", None)
            )
            if len(tracks) == 0:
                return detections  # no confirmed track this frame → boxes.id stays None → coast
            idx = tracks[:, -1].astype(int)
            out = detections[idx]
            out.update(boxes=torch.as_tensor(tracks[:, :-1]))
            return out
        except Exception as exc:  # noqa: BLE001 — live-robustness: one bad camera coasts
            logger.warning("update() degraded a camera to no-detection (coast): {}", exc)
            return None
