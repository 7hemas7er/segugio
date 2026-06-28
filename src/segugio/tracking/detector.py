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

__all__ = ["PerCameraTracker", "ensure_native_feats", "resolve_dog_index"]


def ensure_native_feats(model) -> None:
    """Register the native-ReID FEATS-EXTRACTION hook on a shared detection model (Track-B).

    This is the load-bearing batched-path fix. In the serial ``model.track()`` path Ultralytics'
    ``on_predict_start`` callback registers a forward-pre-hook on the Detect head that captures the
    feature pyramid into ``predictor._feats``; ``DetectionPredictor.postprocess`` then attaches one
    per-detection feature vector to each ``result.feats`` (only when ``_feats`` is set). The native
    BoT-SORT encoder (``lambda feats, s: [f.cpu().numpy() for f in feats]``) consumes exactly those
    per-detection ``result.feats``.

    The batched path runs ``model.predict([N frames])`` — which does NOT register that hook — so
    ``result.feats`` is never attached, ``BOTSORT.update`` receives ``feats=None``, and the native
    encoder is handed the raw BGR frame (numpy rows) → ``'numpy.ndarray' object has no attribute
    'cpu'``. Re-using ``model.track()`` to register the hook is WORSE: it also registers
    ``on_predict_postprocess_end`` (auto-tracking on the shared predictor, mixing IDs across the N
    batched frames — #13107) which re-indexes ``predictor.results[i]`` and STRIPS the ``feats`` attr.

    So this helper registers ONLY the feats hook — mirroring the native-ReID branch of Ultralytics'
    ``on_predict_start`` WITHOUT the tracker construction and WITHOUT the postprocess auto-tracking.
    A single ``model.predict(..., end2end=False)`` then populates ``result.feats``, and association
    is dispatched manually to one BOTSORT per ``cam_id`` (built via :meth:`PerCameraTracker._build_botsort`).

    Idempotent (guarded by ``model._segugio_feats_cb``) and called every tick before the batched
    forward; a no-op on a model without ``add_callback`` (a headless fake) so the dispatch-shape
    tests keep injecting plain fakes. The hook only engages when the in-graph Detect head is a real
    ``nn.Module`` with ``end2end=False`` (the eager ``.pt`` native-ReID precondition); on an
    engine-backed model the condition is False and no hook registers (cls-ReID fallback wants the
    frame, so ``feats=None`` is correct there).

    Args:
        model: the shared ``ultralytics.YOLO`` that runs the single batched detection forward (in
            production ``any_tracker.model``). A headless fake (no ``add_callback``) is a no-op.
    """
    if not hasattr(model, "add_callback"):
        return  # headless fake model — nothing to hook (dispatch-shape tests inject plain fakes)
    if getattr(model, "_segugio_feats_cb", False):
        return  # already registered — idempotent across ticks
    import torch  # lazy — heavy import inside the function (lazy-import boundary)
    from ultralytics.nn.modules.head import Detect

    def _on_predict_start(predictor, persist: bool = False) -> None:
        # Reset + re-arm each predict so feats stay fresh and never leak across ticks. Mirrors
        # Ultralytics' on_predict_start native-ReID branch (the hook half only).
        predictor._feats = None
        if getattr(predictor, "_hook", None) is not None:
            try:
                predictor._hook.remove()
            except Exception:  # noqa: BLE001 — a stale handle must not crash the live loop
                pass
            predictor._hook = None
        try:
            inner = predictor.model.model  # AutoBackend.model → the torch DetectionModel
            det = inner.model[-1]  # the Detect head (last module of the Sequential)
        except (AttributeError, TypeError, IndexError):
            return  # engine / non-standard backend → no in-graph Detect head, no native feats
        if (
            isinstance(inner, torch.nn.Module)
            and isinstance(det, Detect)
            and not getattr(det, "end2end", False)
        ):

            def _pre_hook(module, inp):
                predictor._feats = list(inp[0])  # unroll to a new list (avoid forward mutation)

            predictor._hook = det.register_forward_pre_hook(_pre_hook)

    model.add_callback("on_predict_start", _on_predict_start)
    model._segugio_feats_cb = True


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

    def __init__(
        self,
        model_path,
        dog_idx: int,
        tracker_yaml,
        use_fp16: bool = False,
        engine_path=None,
    ) -> None:
        """Load the YOLO model for this camera (lazy heavy import inside the constructor).

        Engine-aware load with a GRACEFUL eager fallback (06-03, RESEARCH Pattern 3 / RBT-04 —
        the dominant robustness concern this phase). When ``engine_path`` is set AND the file
        exists, TRY ``YOLO(<engine>)`` and set ``self.is_engine = True`` (Q1 Option (a): the
        engine accelerates the FULL ``.track()`` and the reid gate downgrades to a warning). On
        ANY failure — a missing/incompatible/wrong-GPU/corrupt engine (RESEARCH Pitfall 3), or
        a missing engine FILE (the staleness signal — there is no metadata schema) — log a
        WARNING and fall back to the eager ``YOLO(<model_path>)`` with ``self.is_engine = False``.
        The live director NEVER crashes on a bad engine; it degrades to the eager ``.pt`` path.

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
            engine_path: optional cached TensorRT ``.engine`` (``ModelConfig.engine_path``). When
                set AND on disk, the engine is loaded and ``is_engine`` becomes True; on ANY load
                failure or a missing file, the loader degrades gracefully to the eager ``.pt``
                (``is_engine`` False). ``None`` (the default) = today's eager path unchanged.
        """
        from ultralytics import YOLO  # lazy — heavy import INSIDE the constructor

        # Resolve + validate BEFORE loading the model so a bad tracker path fails fast.
        self.tracker_yaml = _resolve_tracker_yaml(tracker_yaml)
        self.dog_idx = int(dog_idx)
        self.use_fp16 = bool(use_fp16)
        # Lazily-built persistent BoT-SORT tracker for the Track-B batched ``update()`` path.
        self._bot = None

        # Engine-aware load with graceful eager fallback (RBT-04). Default (engine_path None)
        # keeps the eager ``.pt`` path byte-for-byte — ``is_engine`` False → the HARD TRK-02
        # ReID gate stays a raise; an engine-backed model sets it True → the gate warns (Q1 (a)).
        self.is_engine = False
        if engine_path is not None and Path(engine_path).is_file():
            try:
                self.model = YOLO(str(engine_path))  # engine accelerates the FULL .track() (Q1 a)
                self.is_engine = True
                logger.info("loaded TensorRT engine {} (is_engine=True)", engine_path)
            except Exception as exc:  # noqa: BLE001 — RBT-04: a bad engine never crashes the loop
                logger.warning(
                    "engine load failed for {} — degrading to eager .pt {} (is_engine=False): {}",
                    engine_path,
                    model_path,
                    exc,
                )
                self.model = YOLO(str(model_path))
                self.is_engine = False
        else:
            if engine_path is not None:
                # A configured-but-absent engine IS the staleness signal (no metadata schema) —
                # coast to eager rather than failing the live loop.
                logger.warning(
                    "engine_path {} configured but file is absent — using eager .pt {} "
                    "(is_engine=False); rebuild the engine on this rig to enable it.",
                    engine_path,
                    model_path,
                )
            self.model = YOLO(str(model_path))  # own predictor.trackers state per camera

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

    def _ensure_persistent_tracker(self, frame: "np.ndarray | None" = None) -> None:
        """Build THIS camera's persistent BoT-SORT for the Track-B batched ``update()`` path.

        The Track-B batched path bypasses ``model.track()`` (it runs ONE shared ``model.predict()``
        over all cameras), so the per-camera ``predictor.trackers`` are never built — and must NOT
        be: building them via a ``model.track()`` warmup also registers Ultralytics'
        ``on_predict_postprocess_end`` callback, which then re-runs association on the shared
        batched ``predict()`` (mixing IDs across the N frames, #13107) AND strips ``result.feats``
        by re-indexing the result (the root-cause of the native-ReID encoder crash). So we build
        the ``BOTSORT`` DIRECTLY (no warmup forward, no tracking callbacks) for BOTH backends:

          * EAGER ``.pt`` (``is_engine`` False): register the feats-extraction hook on this
            model via :func:`ensure_native_feats` (so the batched ``predict(..., end2end=False)``
            populates ``result.feats``) and build the BOTSORT with the NATIVE config
            (``model: auto`` → the zero-extra-weight native lambda encoder, fed the real
            per-detection ``result.feats``).

          * ENGINE (``is_engine`` True): the in-graph Detect head is structurally absent on an
            AutoBackend engine (Q1 Option (a)), so native feats are impossible — build the BOTSORT
            with the cls-ReID fallback (``yolo26n-cls.pt``), which takes the frame (``feats=None``)
            and crops its own embeddings. No feats hook is registered (its precondition is False).

        ``frame`` is accepted for call-site parity (the dispatcher passes this camera's frame) but
        is unused — the direct build needs no single-frame warmup. One tracker per ``cam_id`` (#13107).
        """
        if self._bot is not None:
            return
        if self.is_engine:
            self._bot = self._build_botsort(native_reid=False)
            return
        # Eager native-ReID path: arm the feats hook on this model, then build the native BOTSORT.
        ensure_native_feats(self.model)
        self._bot = self._build_botsort(native_reid=True)

    def _build_botsort(self, native_reid: bool):
        """Construct a per-camera ``BOTSORT`` DIRECTLY (no single-frame warmup, no callbacks).

        Mirrors Ultralytics' ``on_predict_start`` tracker construction: load the resolved
        ``botsort_dog.yaml`` into the tracker cfg and build one ``BOTSORT``.

        When ``native_reid`` is True (eager ``.pt``) the cfg's ``model: auto`` is PRESERVED, so
        ``BOTSORT.__init__`` wires the native lambda encoder (``lambda feats, s: [...]``) — the
        zero-extra-weight path, fed the per-detection ``result.feats`` populated by the feats hook.

        When ``native_reid`` is False (engine, Q1 Option (a)) the in-graph Detect head is
        unavailable, so we force ``cfg.model = "yolo26n-cls.pt"`` and the BOTSORT builds the
        cls-ReID encoder (which crops embeddings from the frame). One tracker per ``cam_id`` (#13107).
        """
        from ultralytics.trackers.track import TRACKER_MAP  # lazy heavy import inside the method
        from ultralytics.utils import IterableSimpleNamespace, YAML
        from ultralytics.utils.checks import check_yaml

        cfg = IterableSimpleNamespace(**YAML.load(check_yaml(self.tracker_yaml)))
        if (
            not native_reid
            and getattr(cfg, "tracker_type", None) == "botsort"
            and getattr(cfg, "with_reid", False)
        ):
            # Engine reality (Q1 a): no in-graph Detect head → cls-ReID fallback encoder.
            cfg.model = "yolo26n-cls.pt"
        return TRACKER_MAP[cfg.tracker_type](args=cfg)

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
