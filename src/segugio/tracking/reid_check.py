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

Engine-aware downgrade (Open Q1 Option (a), Phase 6 / 06-01): a TensorRT ``.engine`` loads
via ``AutoBackend`` and structurally CANNOT expose the in-graph ``nn.Module`` Detect head the
native-ReID forward hook attaches to — so native feats are impossible BY DESIGN on an
engine-backed model (RESEARCH Pitfall 1). The ``is_engine`` keyword DOWNGRADES the would-be
HARD raise to a ``logger.warning`` for an engine-backed model (accepting the cls-ReID
fallback), while keeping the eager ``.pt`` HARD gate (TRK-02) byte-for-byte unchanged at the
``is_engine=False`` default.

Lazy-import boundary: ``ultralytics.trackers.bot_sort.ReID`` is imported INSIDE the function
(it is heavy), so ``import segugio.tracking.reid_check`` succeeds with the heavy stack absent.
``loguru`` is a LIGHT dep imported at module top.

Source: 04-RESEARCH.md "Code Examples — native-ReID engagement assertion" (lines 380-401),
Context7-verified against the shipped ``on_predict_start`` + ``BOTSORT.__init__`` (8.4.x).
"""

from __future__ import annotations

from loguru import logger

__all__ = ["assert_native_reid_engaged"]


def assert_native_reid_engaged(model, is_engine: bool = False) -> None:
    """Raise if BoT-SORT native-feature ReID did NOT engage (silent fallback detected).

    Inspects the live tracker on ``model.predictor`` after the first ``.track()`` call:
    the encoder must be the native lambda (NOT a ``ReID`` instance) and the Detect forward
    hook must be registered. On an eager ``.pt`` model any deviation RAISES — this is a
    correctness invariant, not a metric.

    Engine-aware downgrade (Open Q1 Option (a)): when ``is_engine`` is True, the would-be
    HARD raise on the cls-ReID fallback (encoder is a ``ReID`` instance) OR a missing forward
    hook is DOWNGRADED to a ``logger.warning`` and the function returns ``None`` — because a
    TensorRT engine loads via ``AutoBackend`` and structurally cannot expose the in-graph
    Detect head, so native feats are impossible BY DESIGN (RESEARCH Pitfall 1). The
    ``is_engine=False`` default keeps EVERY existing raise verbatim (the eager TRK-02 gate).

    Args:
        model: the ``ultralytics.YOLO`` instance that has already run ONE
            ``track(..., end2end=False)`` warmup call (so ``predictor.trackers`` exists).
        is_engine: True when ``model`` is backed by a TensorRT ``.engine`` (AutoBackend) —
            downgrades the cls-fallback / missing-hook raise to a warning. Defaults to False
            (eager ``.pt`` HARD gate unchanged).

    Raises:
        RuntimeError: if no trackers exist or ``with_reid`` is off (always, both paths); and —
            ONLY when ``is_engine=False`` — if native ReID fell back to ``yolo26n-cls.pt``
            (encoder is a ``ReID``) or the forward hook is missing.
    """
    predictor = getattr(model, "predictor", None)  # exists only after a real .track() call
    if predictor is None:
        # The caller must run the gate only after a warmup that ACTUALLY performed inference
        # (eval.py guards on `results is not None`). A None predictor means model.track() never
        # ran (e.g. an empty/None warmup crop returned None WITHOUT inference) — fail with the
        # real cause, not a misleading "no trackers" / AttributeError downstream (CR-02).
        raise RuntimeError(
            "model.predictor is None — assert_native_reid_engaged was called before any real "
            ".track() inference ran (an empty/None warmup crop performs no inference)."
        )
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
        if is_engine:
            # Engine-backed: native feats are structurally impossible (AutoBackend, no in-graph
            # Detect head) — accept the cls-ReID fallback instead of failing the live loop.
            logger.warning(
                "native ReID structurally unavailable on engine-backed model — "
                "accepting cls-ReID fallback (yolo26n-cls.pt)."
            )
            return
        raise RuntimeError(
            "native ReID FELL BACK to a downloaded cls model (yolo26n-cls.pt). "
            "Pass end2end=False to model.track() so the standard Detect head engages."
        )
    # Belt-and-suspenders: the native path also registers a forward-pre-hook on Detect.
    if getattr(predictor, "_hook", None) is None:
        if is_engine:
            logger.warning(
                "native-ReID forward hook absent on engine-backed model "
                "(expected — AutoBackend exposes no in-graph Detect head)."
            )
            return
        raise RuntimeError(
            "native-ReID forward hook not registered — fallback likely."
        )
    logger.info(
        "BoT-SORT native-feature ReID engaged (zero extra weights, end2end=False)."
    )
