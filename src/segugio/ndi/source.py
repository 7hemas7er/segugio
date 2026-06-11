"""``FrameSource`` — the per-camera latest-frame interface the orchestrator depends on (D-05).

This is the structural seam (RESEARCH Pattern 1) that keeps the orchestrator and its unit
tests on the LIGHT side of the lazy-import boundary. Two implementations land in Wave 2
(05-02): (a) the real cyndilib receiver (Finder/Receiver/FrameSync → numpy BGR, one supervised
thread per camera) and (b) the in-process clip-replay mock (no network/libndi, derives the
existing ``tracking/frame_source.ClipFrameSource`` semantics). The orchestrator depends ONLY
on this Protocol, so the same loop runs against the mock headless and the real receiver on
Windows.

``last_frame_ts`` is the load-bearing RBT-01 detail: the POSIX timestamp of the last *NEW*
frame (never the NDI "connected" state — a dropped phone repeats its last frame for ~75 min).
The watchdog (05-04) deduces liveness purely from whether this timestamp advances.

Light: the ``from __future__ import annotations`` + ``TYPE_CHECKING`` header keeps numpy OFF
the runtime import path (mirrors ``tracking/frame_source.py``), so ``import segugio.ndi``
succeeds with cyndilib/cv2/numpy-as-a-hard-dep absent. The heavy cyndilib imports live INSIDE
the real implementation's methods only (Wave 2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # type-only — keeps numpy off the runtime import path
    import numpy as np

__all__ = ["FrameSource"]


@runtime_checkable
class FrameSource(Protocol):
    """Per-camera newest-frame provider. The orchestrator depends ONLY on this interface.

    ``runtime_checkable`` so a fake/mock can be ``isinstance``-checked structurally in tests
    without inheriting (matches the duck-typed fakes the conftest provides).
    """

    def start(self) -> None:
        """Spin up the receiver thread(s) (a no-op for the in-process clip mock)."""
        ...

    def latest(self, cam_id: str) -> "np.ndarray | None":
        """Return the newest BGR frame for ``cam_id``, or ``None`` to coast (no frame yet)."""
        ...

    def last_frame_ts(self, cam_id: str) -> float | None:
        """POSIX timestamp of the last *NEW* frame for ``cam_id`` (RBT-01), or ``None``.

        Advances ONLY on a genuinely new frame; a frozen/repeated feed stops advancing it,
        which is how the watchdog declares the feed dead (never the NDI source state).
        """
        ...

    def stop(self) -> None:
        """Tear down receiver thread(s) / release resources."""
        ...
