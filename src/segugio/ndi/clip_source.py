"""``ClipReplayFrameSource`` — the in-process clip-replay mock ``FrameSource`` (D-05).

This is the headless, deterministic ingest path: it derives ``tracking.frame_source``'s
``ClipFrameSource`` semantics (per-camera numpy BGR crops, an injected EMITTED-frame tick,
the zero-size-frame skip — the NDI-03 precursor) and exposes the newest per-camera frame
behind the ``FrameSource`` Protocol's ``latest(cam_id)`` / ``last_frame_ts(cam_id)`` surface.
No network, no libndi, no cyndilib — every Phase-5 headless test drives the whole orchestrator
loop against this mock.

Two construction modes:
  - ``ClipReplayFrameSource(clip_path=..., crops=...)`` wraps a real ``ClipFrameSource`` and
    drives its ``frames()`` generator (``cv2`` lazy-imported INSIDE that generator — the mock
    itself stays on the LIGHT side of the import boundary, so ``import segugio.ndi.clip_source``
    succeeds with cv2 absent).
  - ``ClipReplayFrameSource(frames_iter=...)`` drives an INJECTED ``(tick, {cam_id: frame})``
    iterator directly — the deterministic, cv2-free test path.

Liveness substrate (RBT-01): ``last_frame_ts(cam_id)`` advances ONLY when a genuinely NEW
non-empty frame is published for that camera. A zero-size / zero-resolution frame is SKIPPED
(never reshaped, never raised) exactly as ``frame_source.py:76-89`` does (NDI-03), so a blank
frame coasts (``latest`` stays the last good frame / ``None``) and never advances the timestamp.

Determinism: the published per-camera timestamp is derived from the EMITTED-frame ``tick``
(a monotonic float = ``tick + 1``), NOT a wall-clock — so the same construction yields the
same per-camera sequence headless (clone of the ``ClipFrameSource`` injected-tick contract).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:  # type-only — keeps numpy off the runtime import path
    import numpy as np

__all__ = ["ClipReplayFrameSource"]


class ClipReplayFrameSource:
    """In-process clip-replay ``FrameSource`` (the headless mock). Skips empties (NDI-03).

    Implements the ``FrameSource`` Protocol (``start``/``latest``/``last_frame_ts``/``stop``).
    Drive it by repeatedly calling ``pump()`` (advance one emitted frame) — the orchestrator's
    tick calls ``pump()`` each tick to pull the next replayed frame, then reads ``latest``.
    """

    def __init__(
        self,
        clip_path=None,
        crops: "dict[str, list[float]] | None" = None,
        stride: int = 2,
        frames_iter: "Iterator[tuple[int, dict[str, np.ndarray]]] | None" = None,
    ) -> None:
        """Configure the mock over EITHER a clip (+crops) OR an injected frame iterator.

        Args:
            clip_path: absolute clip path (resolve via ``segugio.fixtures.resolve_clip_path``).
                Used to build a wrapped ``ClipFrameSource`` when ``frames_iter`` is not given.
            crops: ``{cam_id: [x0, y0, x1, y1]}`` normalized crop rects for the wrapped source.
            stride: frame-sampling stride passed to the wrapped ``ClipFrameSource``.
            frames_iter: an injected ``(tick, {cam_id: frame})`` iterator — the cv2-free test
                path. Mutually exclusive with ``clip_path`` (``frames_iter`` wins if both given).
        """
        self._clip_path = clip_path
        self._crops = dict(crops) if crops else None
        self._stride = stride
        self._injected = frames_iter

        self._gen: "Iterator[tuple[int, dict[str, np.ndarray]]] | None" = None
        self._lock = threading.Lock()
        self._latest: "dict[str, np.ndarray]" = {}
        self._ts: dict[str, float] = {}
        self._started = False
        self._exhausted = False

    def start(self) -> None:
        """Open the underlying generator (safe to call once; a no-op if already started)."""
        if self._started:
            return
        if self._injected is not None:
            self._gen = self._injected
        else:
            if self._clip_path is None or self._crops is None:
                raise ValueError(
                    "ClipReplayFrameSource needs either frames_iter or (clip_path + crops)"
                )
            # Lazy: ClipFrameSource.frames() imports cv2 INSIDE the generator, so building
            # the wrapper here stays on the light side of the import boundary.
            from ..tracking.frame_source import ClipFrameSource

            self._gen = ClipFrameSource(
                self._clip_path, self._crops, self._stride
            ).frames()
        self._started = True

    def pump(self) -> bool:
        """Advance the replay by one EMITTED frame; publish its non-empty per-camera crops.

        Returns ``True`` if a frame was consumed, ``False`` once the source is exhausted.
        A zero-size crop is SKIPPED (NDI-03): it is neither published nor does it advance
        that camera's ``last_frame_ts`` — the camera coasts on its last good frame.
        """
        if not self._started or self._gen is None or self._exhausted:
            return False
        try:
            tick, crops = next(self._gen)
        except StopIteration:
            self._exhausted = True
            return False
        # Derived monotonic timestamp from the EMITTED tick (no wall-clock — determinism).
        ts = float(tick) + 1.0
        with self._lock:
            for cam_id, frame in crops.items():
                # NDI-03 empty-frame guard — mirror frame_source.py:76-89 exactly.
                if getattr(frame, "size", 0) == 0:
                    continue  # skip a blank/zero-size frame: coast, never advance ts
                self._latest[cam_id] = frame
                self._ts[cam_id] = ts
        return True

    def latest(self, cam_id: str) -> "np.ndarray | None":
        """Return the newest non-empty BGR frame for ``cam_id``, or ``None`` to coast."""
        with self._lock:
            return self._latest.get(cam_id)

    def last_frame_ts(self, cam_id: str) -> float | None:
        """POSIX-like timestamp of the last NEW frame for ``cam_id`` (RBT-01), or ``None``.

        Advances only when a genuinely new non-empty frame was published; a skipped blank
        leaves it unchanged — the watchdog's liveness substrate.
        """
        with self._lock:
            return self._ts.get(cam_id)

    def stop(self) -> None:
        """Release the underlying generator (closes a wrapped ClipFrameSource cap)."""
        gen = self._gen
        self._gen = None
        self._started = False
        # Closing the generator runs its finally: (cap.release() in ClipFrameSource).
        if gen is not None and hasattr(gen, "close"):
            try:
                gen.close()
            except Exception:  # pragma: no cover - defensive: never raise on teardown
                pass
