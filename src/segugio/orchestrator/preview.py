"""The off-tick preview publisher — RESEARCH "Build Order" step 3 (PRV-01/PRV-02).

``PreviewPublisher`` is the only genuinely NEW construct in Phase 7, and even it composes
existing primitives (RBT-04 coast + a ``Lock``-guarded 1-slot mailbox + ``atomic_write_bytes``
+ ``write_preview`` + ``PreviewDoc``). Its single load-bearing invariant: **the decision tick
NEVER waits on the publisher.** The tick calls :meth:`offer` — a single locked attribute
assignment (last-writer-wins, frame-drop allowed, D-02 / PRV-01) — and returns. The publisher's
OWN daemon thread (:meth:`_run`) does ALL the resize/encode/IO off the tick at ~``1/fps``
cadence (:meth:`_publish`), and any encode/IO fault COASTS (logged, never raised — RBT-04
extended, the same coast-don't-crash shape as ``loop.py``'s tick catch + ``_safe_startup``).

Lazy-import boundary (gate 2): the module-level imports are stdlib + the ``opcomm`` contract
ONLY. ``cv2``/``numpy`` are imported LAZILY inside :meth:`_publish`, so ``import
segugio.orchestrator.preview`` succeeds with the heavy stack ABSENT (the console never gains a
heavy import across the boundary — threat T-07-03-04).

Frame-snapshot forward-assumption (RESEARCH "Frame-snapshot safety", L367-374): :meth:`offer`
stores the frame dict by REFERENCE — it does NOT ``.copy()`` the arrays. Both current
``FrameSource`` implementations (the mock clip source and the NDI receiver) allocate a FRESH
array per delivered frame, so the array the tick offered is not mutated under the publisher.
IF a future ``FrameSource`` ever reuses/overwrites a single buffer in place, add a ``.copy()``
in :meth:`offer` (the dropped-frame mailbox makes an occasional copy cheap) — do NOT add it
speculatively, it would tax every tick for a hazard that does not exist today.
"""

from __future__ import annotations

import os
import threading

from loguru import logger

from ..opcomm.atomic import atomic_write_bytes
from ..opcomm.channel import write_preview
from ..opcomm.records import PreviewDoc

__all__ = ["PreviewPublisher"]


class PreviewPublisher:
    """Latest-only off-tick publisher: a 1-slot mailbox + an own daemon loop + ``_publish``.

    Construction is cheap and heavy-stack-free. ``offer(frames, scores, dets, decision, cuts)``
    is the ONLY method the tick calls — a single locked assignment that never blocks. ``start``
    launches the daemon; ``stop`` joins it best-effort. The daemon ``_run`` drains the latest
    offered tuple, calls ``_publish``, and coasts on any fault.

    Args:
        params: the ``PreviewParams`` sub-model (``fps``/``max_width``/``jpeg_quality``/
            ``enabled``). Only ``fps`` is read at construction (the publish period).
        preview_dir: the directory the JPEGs + ``preview.json`` are written into
            (``opcomm/preview/``; created by the plan-04 wiring, not here).
        cam_ids: the ordered camera ids to publish a thumbnail + a ``cams`` entry for.
        encode_fn: an OPTIONAL injectable encoder seam ``frame -> bytes`` for HEADLESS tests
            (so no real cv2/GPU is needed). ``None`` (the live default) routes through the lazy
            ``cv2`` encode in :meth:`_cv2_encode`.
    """

    def __init__(self, params, preview_dir, cam_ids, *, encode_fn=None) -> None:
        self._params = params
        self._preview_dir = preview_dir
        self._cam_ids = list(cam_ids)
        # The publish period is the inverse of the configured preview fps — the daemon sleeps
        # ~1/fps when the mailbox is empty (it does NOT busy-spin) and after each publish.
        self._period = 1.0 / params.fps
        self._encode_fn = encode_fn
        # The 1-slot mailbox: a single attribute under a short lock. NOT a queue.Queue — a queue
        # would buffer stale frames; we want LATEST-only with last-writer-wins (D-02).
        self._lock = threading.Lock()
        self._latest = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # The in-sidecar monotonic cache-bust token (RESEARCH "Cache-bust token"): bumped once
        # per publish so the console can append ``?t=<gen>`` to defeat its image cache. No
        # separate ``gen.txt`` file — the token rides inside ``preview.json``.
        self._gen = 0

    # ----- the mailbox (the tick side — never blocks) ----------------------- #

    def offer(self, frames, scores, dets, decision, cuts) -> None:
        """Drop the latest snapshot into the 1-slot mailbox (last-writer-wins, never blocks).

        Called from the decision tick. This is a SINGLE locked attribute assignment — the lock
        is held only for the pointer swap, so the tick is never delayed by the publisher's
        encode/IO (D-02 / PRV-01). If the publisher has not yet drained the previous offer, this
        OVERWRITES it (frame-drop is allowed — the console wants the freshest frame, not a
        backlog). The ``frames`` dict is stored by reference (see the module docstring's
        frame-snapshot forward-assumption — no ``.copy()`` needed today).
        """
        with self._lock:
            self._latest = (frames, scores, dets, decision, cuts)

    def _drain(self) -> tuple | None:
        """Take the latest offered tuple ONCE (clearing the slot), or ``None`` if empty.

        The publisher-side counterpart to :meth:`offer`: read-and-clear under the same lock so
        a concurrent ``offer`` either lands before (drained now) or after (drained next loop) —
        never torn. Returns ``None`` when no new frame has been offered since the last drain.
        """
        with self._lock:
            item, self._latest = self._latest, None
        return item

    # ----- the daemon loop (the off-tick side — does ALL the work) ---------- #

    def _run(self) -> None:
        """The daemon loop: drain → publish → sleep ~1/fps; coast on any publish fault.

        Mirrors ``loop.py``'s RBT-04 tick catch (``except Exception: logger.warning(...)``): an
        encode/IO fault in ``_publish`` is logged and the loop CONTINUES — the publisher thread
        is isolated from the director, so a bad frame never perturbs the tick (threat
        T-07-03-01). When the mailbox is empty the loop WAITS the publish period (no busy-spin).
        Terminates when :meth:`stop` sets the stop event.

        The period wait is ``self._stop.wait(self._period)`` rather than ``time.sleep`` (WR-01):
        a bare ``time.sleep`` is NOT interrupted by ``stop()``, so with a low-fps config the
        period can be hundreds of seconds and ``stop()`` (the RBT-04 SAFE shutdown path) would
        block until the daemon finally woke. ``Event.wait`` returns True immediately when
        ``stop()`` fires, so shutdown is prompt. The wait also subsumes the top-of-loop
        ``_stop.is_set()`` check — we break as soon as it returns True.
        """
        while True:
            item = self._drain()
            if item is not None:
                try:
                    self._publish(*item)
                except Exception as exc:  # noqa: BLE001 — RBT-04 extended: publish fault COASTS
                    logger.warning("preview publish coasted: {}", exc)
            # Wait the publish period on the STOP EVENT (WR-01): wakes immediately on stop() so
            # the RBT-04 shutdown path is never blocked by a long (low-fps) publish period.
            if self._stop.wait(self._period):
                break

    def start(self) -> None:
        """Launch the daemon publisher thread — IDEMPOTENT (CR-01).

        ``Orchestrator.run`` and ``Orchestrator.run_measured`` both call ``start()``, and
        ``run_measured`` is driven multiple times back-to-back on a SINGLE publisher instance
        (see ``tests/test_latency.py``). Without a guard, a second ``start()`` would overwrite
        ``self._thread`` and ORPHAN the first daemon — ``stop()`` could then never join it, and
        the two daemons would race on the same fixed atomic temp path, defeating the
        never-partial atomic-write guarantee. Early-return while a thread is already alive so at
        most one daemon ever runs per publisher.
        """
        if self._thread is not None and self._thread.is_alive():
            return  # already running — do not leak a second daemon (CR-01)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="preview-publisher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the loop to stop and join the thread best-effort (never raises).

        Sets the stop event so ``_run`` returns on its next iteration, then joins with a bounded
        timeout. A failure to join (a wedged daemon) is logged and swallowed — ``stop`` is called
        from the orchestrator shutdown path, which must itself never crash (RBT-04).
        """
        self._stop.set()
        thread = self._thread
        if thread is None:
            return
        try:
            thread.join(timeout=max(2.0, self._period * 4))
        except Exception as exc:  # noqa: BLE001 — shutdown must not crash on a wedged join
            logger.warning("preview publisher stop coasted: {}", exc)

    # ----- the publish (resize/encode/IO + the D-07 'why' payload) ---------- #

    def _cv2_encode(self, frame) -> bytes:
        """Resize ``frame`` to ``max_width`` (aspect-preserving) → encode JPEG → bytes.

        The LIVE encoder. ``cv2``/``numpy`` import LAZILY HERE (gate-2 boundary — the module
        imports with the heavy stack absent; only an actual publish pulls cv2 in). Aspect ratio
        is preserved: the target height is derived from ``max_width / frame.width``. The JPEG
        quality is the configured ``jpeg_quality`` (cv2 ``IMWRITE_JPEG_QUALITY``).
        """
        import cv2  # lazy heavy import — keeps the module importable without cv2 (gate 2)
        import numpy as np  # noqa: F401 — imported lazily alongside cv2 per the boundary

        h, w = frame.shape[0], frame.shape[1]
        max_width = self._params.max_width
        if w > max_width:
            scale = max_width / float(w)
            target = (max_width, max(1, int(round(h * scale))))
            resized = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        else:
            resized = frame
        ok, buf = cv2.imencode(
            ".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), int(self._params.jpeg_quality)]
        )
        if not ok:
            raise RuntimeError("cv2.imencode failed to encode the preview JPEG")
        return buf.tobytes()

    def _build_doc(self, scores, dets, decision, cuts) -> PreviewDoc:
        """Build the full D-07 'why' ``PreviewDoc`` from injected scores/dets/decision/cuts.

        PURE — no frames, no cv2 (so it is unit-testable headless). Bumps :attr:`_gen` once per
        call (the in-sidecar cache-bust token). Field-by-field source map (RESEARCH L235-252):

          * ``score`` / ``ema`` — ``CameraScore.score`` (the EMA; the raw is not exposed, so
            ``ema == score`` — no scorer change, RESEARCH L242).
          * ``state``          — ``CameraScore.status.value`` (the ``ScorerStatus`` str enum).
          * ``locked`` / ``in_zone`` — ``dets[cam_id] is not None`` (A1 approximation: a present
            locked detection IS the in-zone signal in Phase 7).
          * ``track_id``       — ``det.track_id`` or ``None``.
          * ``box``            — ``[cx, cy, w, h]`` (normalized) or ``None`` when no detection.
          * ``energy``         — per-camera locked-motion energy if surfaced; ``0.0`` default
            (the FIELD MUST exist for the D-07 contract — plan 04 wires the real value).
          * top-level ``auto_candidate`` — ``decision.target`` (or the ``"SAFE"`` sentinel).
          * top-level ``cuts`` — the orchestrator's recent-cuts ring (newest-last).
        """
        score_by_cam = {s.cam_id: s for s in scores}
        cams: dict = {}
        for cam_id in self._cam_ids:
            cs = score_by_cam.get(cam_id)
            score = float(cs.score) if cs is not None else 0.0
            state = cs.status.value if cs is not None else "lost"
            det = dets.get(cam_id)
            locked = det is not None
            track_id = det.track_id if det is not None else None
            in_zone = det is not None  # RESEARCH A1 approximation
            box = (
                [float(det.cx), float(det.cy), float(det.w), float(det.h)]
                if det is not None
                else None
            )
            cams[cam_id] = {
                "score": score,
                "ema": score,  # RESEARCH L242: ema == score (raw EMA not exposed)
                "state": state,
                "locked": locked,
                "track_id": track_id,
                "energy": 0.0,  # D-07 field MUST exist; real value wired in plan 04 if surfaced
                "in_zone": in_zone,
                "box": box,
            }
        self._gen += 1
        tick = scores[0].tick if scores else 0
        auto_candidate = str(getattr(decision, "target", "SAFE"))
        return PreviewDoc(
            tick=tick,
            gen=self._gen,
            auto_candidate=auto_candidate,
            cams=cams,
            cuts=tuple(cuts),
        )

    def _publish(self, frames, scores, dets, decision, cuts) -> None:
        """Off-tick publish: per-cam JPEG (atomic, fsync=False) + the D-07 ``preview.json``.

        Runs on the daemon thread only. For each camera with a frame: encode (via the injected
        ``encode_fn`` seam or the lazy :meth:`_cv2_encode`) and write the JPEG through
        ``atomic_write_bytes(..., fsync=False)`` — the JPEGs are EPHEMERAL (regenerated every
        publish), so durability does not matter and the fsync is dropped to save disk time on the
        publisher (D-04). Then build the full D-07 ``PreviewDoc`` and write it via
        ``write_preview`` (which rides ``atomic_write_json`` — always fsynced, D-04 "keep fsync
        for preview.json"). Any fault here is COASTED by :meth:`_run` (RBT-04 extended).
        """
        enc = self._encode_fn or self._cv2_encode
        for cam_id in self._cam_ids:
            frame = frames.get(cam_id)
            if frame is None:
                continue  # no frame this camera this publish — skip its JPEG (no stale write)
            data = enc(frame)
            atomic_write_bytes(
                os.path.join(self._preview_dir, f"cam_{cam_id}.jpg"), data, fsync=False
            )
        doc = self._build_doc(scores, dets, decision, cuts)
        write_preview(os.path.join(self._preview_dir, "preview.json"), doc)
