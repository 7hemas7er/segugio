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
import time

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
        T-07-03-01). When the mailbox is empty the loop sleeps the publish period (no busy-spin).
        Terminates when :meth:`stop` sets the stop event.
        """
        while not self._stop.is_set():
            item = self._drain()
            if item is None:
                # nothing new offered — sleep the publish period (do not busy-spin)
                time.sleep(self._period)
                continue
            try:
                self._publish(*item)
            except Exception as exc:  # noqa: BLE001 — RBT-04 extended: a publish fault COASTS
                logger.warning("preview publish coasted: {}", exc)
            time.sleep(self._period)

    def start(self) -> None:
        """Launch the daemon publisher thread (idempotent-ish: a fresh thread each call)."""
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
    # Implemented in Task 2 — see the same-file _publish/_build_doc/_cv2_encode below.
