"""``NdiFrameSource`` — the real cyndilib ``FrameSource`` (D-05 / NDI-01 / NDI-03 / RBT-01).

One supervised ``threading.Thread`` per camera owns a cyndilib ``Receiver`` + ``VideoFrameSync``,
resolves the camera's configured ``ndi_source`` name via a ``Finder``, and loops capturing the
newest frame. The orchestrator's main thread never touches libndi — it only pulls
``latest(cam_id)`` / ``last_frame_ts(cam_id)`` each tick (the structural seam that keeps the
loop headless-testable against the in-process mock).

Three load-bearing details from RESEARCH §Code Examples / §Common Pitfalls:
  - **NDI-03 empty-frame guard:** ``if min(video_frame.xres, video_frame.yres) != 0`` before any
    reshape — the first frames after ``set_source`` are often zero-resolution.
  - **RBT-01 NEW-frame liveness (Pitfall 1):** a dropped phone repeats its LAST frame for ~75 min,
    so ``receiver.is_connected()`` stays true. Liveness comes ONLY from the frame timestamp:
    ``ts = video_frame.get_timestamp_posix()`` and we publish (and stamp ``last_frame_ts``) ONLY
    when ``ts != last_ts``. A frozen feed stops advancing the timestamp → the watchdog (05-04)
    declares it dead from that, never from the NDI source state.
  - **RBT-04 supervised threads:** ``stop()`` sets the stop event, joins the threads, disconnects
    the receiver and closes the Finder. A dead receiver thread is restartable by ``start()`` (the
    orchestrator restarts a dead thread — RBT-04).

Lazy-import boundary: ``cv2`` and every ``cyndilib`` symbol are imported INSIDE ``_receiver_loop``
(mirrors ``frame_source.py``'s ``import cv2`` inside ``frames()``), so
``import segugio.ndi.ndi_source`` succeeds with cyndilib/cv2 ABSENT. Exercised end-to-end only by
the ``@pytest.mark.ndi`` Windows run against a live (mock or real) named NDI source.

[ASSUMED A1] ``VideoFrameSync.get_timestamp_posix()`` advances per NEW frame and stalls on a
repeated/frozen frame; if it advances on repeats, switch to ``get_timecode_posix()``. Confirm on
the Windows box with a pull-the-cable test (load-bearing for RBT-01 liveness).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only — keeps numpy/cyndilib off the runtime import path
    import numpy as np

    from ..config.models import Camera

__all__ = ["NdiFrameSource"]


class NdiFrameSource:
    """Real cyndilib ``FrameSource``: one supervised receiver thread per camera (NDI-01)."""

    def __init__(self, cameras: "list[Camera]") -> None:
        """Configure over the cameras whose ``ndi_source`` names the receivers resolve.

        Args:
            cameras: the validated ``Camera`` list; each camera with a non-``None``
                ``ndi_source`` gets one supervised receiver thread keyed by ``Camera.id``.
        """
        # Map cam_id -> source name (only cameras that actually carry an ndi_source).
        self._sources: dict[str, str] = {
            cam.id: cam.ndi_source for cam in cameras if cam.ndi_source is not None
        }
        self._stop = threading.Event()
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._latest: "dict[str, np.ndarray]" = {}
        self._ts: dict[str, float] = {}

    def start(self) -> None:
        """Launch (or restart) one supervised receiver thread per camera (RBT-04).

        Idempotent per camera: a thread that is still alive is left running; a missing or
        dead thread is (re)created — this is the supervisor hook the orchestrator calls to
        restart a dead receiver.
        """
        self._stop.clear()
        for cam_id, source_name in self._sources.items():
            existing = self._threads.get(cam_id)
            if existing is not None and existing.is_alive():
                continue
            t = threading.Thread(
                target=self._receiver_loop,
                args=(cam_id, source_name),
                name=f"ndi-recv-{cam_id}",
                daemon=True,
            )
            self._threads[cam_id] = t
            t.start()

    def _receiver_loop(self, cam_id: str, source_name: str) -> None:
        """Per-camera receiver loop: capture NEW frames → numpy BGR → publish (lazy imports).

        Heavy imports live HERE (the lazy boundary). Opens a Finder, resolves ``source_name``,
        sets a ``VideoFrameSync`` on the receiver, then loops: ``capture_video()`` →
        NDI-03 zero-resolution guard → NEW-frame timestamp check → reshape ``(yres, xres, 4)``
        → ``cvtColor(RGBA2BGR)`` → ``_publish``. Runs until ``stop()`` sets the event.
        """
        import cv2
        from cyndilib.finder import Finder
        from cyndilib.receiver import Receiver
        from cyndilib.video_frame import VideoFrameSync
        from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat

        finder = Finder()
        receiver = Receiver(
            color_format=RecvColorFormat.RGBX_RGBA,
            bandwidth=RecvBandwidth.highest,
        )
        video_frame = VideoFrameSync()
        receiver.frame_sync.set_video_frame(video_frame)
        finder.open()
        try:
            # Resolve the configured source name → a cyndilib Source, then connect.
            source = self._resolve_source(finder, source_name)
            if source is not None:
                receiver.set_source(source)
            last_ts: float | None = None
            while not self._stop.is_set():
                if not receiver.is_connected():
                    continue
                receiver.frame_sync.capture_video()
                # NDI-03: the first frames after set_source are often zero-resolution.
                if min(video_frame.xres, video_frame.yres) != 0:
                    ts = video_frame.get_timestamp_posix()  # RBT-01 NEW-frame substrate
                    # Only a genuinely NEW frame advances liveness (Pitfall 1: a frozen
                    # feed repeats its last frame for ~75 min with the same timestamp).
                    if ts != last_ts:
                        arr = video_frame.get_array().reshape(
                            video_frame.yres, video_frame.xres, 4
                        )
                        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                        self._publish(cam_id, bgr, ts)
                        last_ts = ts
        finally:
            receiver.disconnect()
            finder.close()

    @staticmethod
    def _resolve_source(finder, source_name: str):
        """Resolve a named NDI source from the Finder, or ``None`` if not yet present.

        Tries ``get_source_names``/``get_source`` (the cyndilib Finder surface). The receiver
        loop simply coasts (stays disconnected) until the named source appears.
        """
        try:
            names = finder.get_source_names()
        except Exception:  # pragma: no cover - finder API may differ across cyndilib builds
            names = []
        if source_name in names:
            return finder.get_source(source_name)
        return None

    def _publish(self, cam_id: str, bgr: "np.ndarray", ts: float) -> None:
        """Store the newest frame + its NEW-frame timestamp under the lock (RBT-01)."""
        with self._lock:
            self._latest[cam_id] = bgr
            self._ts[cam_id] = ts

    def latest(self, cam_id: str) -> "np.ndarray | None":
        """Return the newest BGR frame for ``cam_id``, or ``None`` to coast (no frame yet)."""
        with self._lock:
            return self._latest.get(cam_id)

    def last_frame_ts(self, cam_id: str) -> float | None:
        """POSIX timestamp of the last NEW frame for ``cam_id`` (RBT-01), or ``None``."""
        with self._lock:
            return self._ts.get(cam_id)

    def stop(self) -> None:
        """Signal every receiver thread to stop, join them, and release resources (RBT-04)."""
        self._stop.set()
        for t in self._threads.values():
            t.join(timeout=2.0)
        self._threads.clear()
