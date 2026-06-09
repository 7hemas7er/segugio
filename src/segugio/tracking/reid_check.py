"""TRK-02 HARD startup gate — assert BoT-SORT native-feature ReID actually engaged.

This is the phase's central correction made a TRUE pass/fail check (not a tuning metric).
``yolo26s.pt`` runs ``end2end=True`` by default; under that head the native-ReID hook
condition in Ultralytics' ``on_predict_start`` is FALSE, so it SILENTLY downloads a
``yolo26n-cls.pt`` classifier and uses it as the ReID encoder — discarding the
"zero-extra-weight native ReID" premise and adding latency. ``PerCameraTracker`` passes
``end2end=False`` to avoid that; ``assert_native_reid_engaged`` PROVES it engaged.

It is a HARD gate: it RAISES on any sign of the silent fallback (Open Question Q1 / A1
mitigation — a wrong head/attribute assumption fails LOUDLY at startup, never silently).
Run it ONCE at startup, after the FIRST ``track(..., end2end=False)`` warmup call, since the
``predictor`` + its ``trackers`` only exist after the first ``.track()``.

The native path: ``BOTSORT.encoder`` is a bare ``lambda(feats, s) -> [...]`` (a passthrough
over the detector's own features) and Ultralytics registers a forward-pre-hook on the Detect
head (``predictor._hook``). The fallback path: ``encoder`` is a ``ReID`` instance and no hook
is registered.

Lazy-import boundary: ``ultralytics.trackers.bot_sort.ReID`` is imported INSIDE the function
(it is heavy), so ``import segugio.tracking.reid_check`` succeeds with the heavy stack absent.
``loguru`` is a LIGHT dep imported at module top.

Source: 04-RESEARCH.md "Code Examples — native-ReID engagement assertion" (lines 380-401),
Context7-verified against the shipped ``on_predict_start`` + ``BOTSORT.__init__`` (8.4.x).
"""

from __future__ import annotations

from loguru import logger

__all__ = ["assert_native_reid_engaged"]


def assert_native_reid_engaged(model) -> None:
    """Raise if BoT-SORT native-feature ReID did NOT engage (silent fallback detected).

    Inspects the live tracker on ``model.predictor`` after the first ``.track()`` call:
    the encoder must be the native lambda (NOT a ``ReID`` instance) and the Detect forward
    hook must be registered. Any deviation RAISES — this is a correctness invariant, not a
    metric.

    Args:
        model: the ``ultralytics.YOLO`` instance that has already run ONE
            ``track(..., end2end=False)`` warmup call (so ``predictor.trackers`` exists).

    Raises:
        RuntimeError: if no trackers exist, if ``with_reid`` is off, if native ReID fell back
            to ``yolo26n-cls.pt`` (encoder is a ``ReID``), or if the forward hook is missing.
    """
    predictor = model.predictor  # exists only after the first .track() call
    trackers = getattr(predictor, "trackers", None)
    if not trackers:
        raise RuntimeError(
            "no trackers on predictor — did .track() run with a botsort yaml?"
        )
    bot = trackers[0]  # one BOTSORT per stream (per camera)
    enc = getattr(bot, "encoder", None)
    # Native path: encoder is a bare lambda(feats, s); fallback path: a ReID instance.
    from ultralytics.trackers.bot_sort import ReID  # lazy heavy import inside the function

    if enc is None:
        raise RuntimeError(
            "with_reid is False — native ReID not enabled in botsort_dog.yaml"
        )
    if isinstance(enc, ReID):
        raise RuntimeError(
            "native ReID FELL BACK to a downloaded cls model (yolo26n-cls.pt). "
            "Pass end2end=False to model.track() so the standard Detect head engages."
        )
    # Belt-and-suspenders: the native path also registers a forward-pre-hook on Detect.
    if getattr(predictor, "_hook", None) is None:
        raise RuntimeError(
            "native-ReID forward hook not registered — fallback likely."
        )
    logger.info(
        "BoT-SORT native-feature ReID engaged (zero extra weights, end2end=False)."
    )
