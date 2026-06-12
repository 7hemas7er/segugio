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
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only — keeps numpy/cyndilib off the runtime import path
    import numpy as np

    from ..config.models import Camera

__all__ = ["NdiFrameSource"]

# Disconnected-branch sleep (CR-02): while the named source is absent / the receiver is not
# connected, the loop sleeps this short interval instead of a bare ``continue``. A bare
# continue pins a CPU core (busy-spin) per camera while a feed is down; ~50ms coasting costs
# ~no CPU and is well inside the ~30Hz tick (the real near-zero-CPU figure is HARDWARE-verified
# under @pytest.mark.ndi — this constant is the busy-spin FIX, not a tuned hardware value).
_RECEIVER_DISCONNECTED_SLEEP_S = 0.05

# Connected-branch poll pace. ``frame_sync.capture_video()`` is NON-BLOCKING — it copies the
# latest synced frame and returns in ~0.2us (measured on real cyndilib 0.1.1: ~5.6M calls/s),
# so a tight capture loop busy-spins a full CPU core PER camera (found in the 05 UAT against a
# live NDI stream — ~1 core of the ~2-core/camera receiver cost was this spin; the rest is the
# intrinsic NDI decode + per-frame 1080p cvtColor). Sleeping ~2ms paces the poll at ~500Hz —
# far above the 30-60fps feed and the ~30Hz tick, so no added pickup latency in practice (the
# frame_sync always hands back the NEWEST frame; a slower poll never builds a queue) — while
# dropping the connected-path CPU from a pinned core to ~nothing.
_RECEIVER_POLL_INTERVAL_S = 0.002

# Candidate install locations of the SYSTEM NDI base runtime (newest-first). The runtime DLL
# (``Processing.NDI.Lib.x64.dll``) sits directly inside one of these. ``NDI_RUNTIME_DIR_V6`` is
# the env var the NDI installer sets (on this box -> ``...\NDI 6 Tools\Runtime``); the literals
# are the standard NDI 6 install paths as a fallback when the env var is unset.
_SYSTEM_NDI_RUNTIME_DIRS = (
    r"C:\Program Files\NDI\NDI 6 Tools\Runtime",
    r"C:\Program Files\NDI\NDI 6 Runtime\v6",
)
_NDI_BASE_DLL_NAME = "Processing.NDI.Lib.x64.dll"
# True once we have attempted the preload (idempotent across threads/cameras).
_SYSTEM_NDI_RUNTIME_PRELOADED = False


def _prefer_system_ndi_runtime() -> str | None:
    """Preload the SYSTEM NDI base runtime so cyndilib decodes NDI|HX (debug: cyndilib-ndi-hx-no-decode).

    cyndilib 0.1.1 bundles the NDI **6.1.1** base runtime, but NDI|HX (compressed phone) decode is
    done by a separate, *version-paired* plugin — ``Processing.NDI.Plugins.IPCam.x64.dll`` (FileVersion
    **6.3.2.0**), installed by the **HX Driver** and registered in ``C:\\ProgramData\\NDI\\ndi-plugins.v1.json``.
    A 6.1.1 base cannot drive the 6.3.2 HX plugin: the receiver connects to the phone but every frame
    is ``xres/yres == 0`` (zero decoded frames). OBS / NDI Studio Monitor decode the same phone because
    they pair the **system 6.3.2** base with the **6.3.2** HX plugin.

    The fix: load the *system* 6.3.2 base ``Processing.NDI.Lib.x64.dll`` **by absolute path** into this
    process BEFORE the first ``import cyndilib``. cyndilib imports the runtime *by name*
    (``os.add_dll_directory(wrapper/bin)`` in ``cyndilib/__init__.py``), so Windows reuses the
    already-loaded 6.3.2 module for that by-name import — pairing base+plugin at 6.3.2 with **no
    site-packages edit, no dependency bump, fully reversible** (it only changes which DLL is resolved
    in *this* process). Uncompressed/full NDI (e.g. OBS PGM) is unaffected — 6.3.2 is a strict
    superset of 6.1.1's decode surface.

    Idempotent and best-effort: runs once per process; if the system runtime is absent (CI / headless /
    Linux) it is a **silent no-op** and cyndilib falls back to its bundled 6.1.1 runtime — preserving
    the headless mock-clip path and the full-NDI path on machines without the HX Driver.

    Returns:
        The absolute path of the system runtime DLL that was preloaded, or ``None`` if none was found
        / the platform is not Windows / the preload was already attempted.
    """
    global _SYSTEM_NDI_RUNTIME_PRELOADED
    if _SYSTEM_NDI_RUNTIME_PRELOADED:
        return None
    _SYSTEM_NDI_RUNTIME_PRELOADED = True  # attempt-once, even if it fails below

    import os
    import sys

    if sys.platform != "win32":
        return None

    import ctypes

    # Prefer the installer-set env var (newest installed runtime), then the standard paths.
    candidate_dirs: list[str] = []
    env_dir = os.environ.get("NDI_RUNTIME_DIR_V6")
    if env_dir:
        candidate_dirs.append(env_dir)
    candidate_dirs.extend(_SYSTEM_NDI_RUNTIME_DIRS)

    for d in candidate_dirs:
        dll = os.path.join(d, _NDI_BASE_DLL_NAME)
        if not os.path.isfile(dll):
            continue
        try:
            # Make this dir (and the HX Driver dir, for the plugin's sibling FFmpeg DLLs)
            # resolvable for any dependent loads, then preload the base runtime by abspath.
            os.add_dll_directory(d)
            hx_dir = r"C:\Program Files\NDI\NDI 6 Tools\HX Driver\x64"
            if os.path.isdir(hx_dir):
                os.add_dll_directory(hx_dir)
            ctypes.WinDLL(dll)
        except OSError:
            # Could not load this candidate — try the next, else fall back to bundled.
            continue
        return dll
    return None


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
        # Pair the system NDI 6.3.2 base runtime with the 6.3.2 HX plugin BEFORE importing
        # cyndilib, so NDI|HX (compressed phone) sources actually decode. cyndilib bundles a
        # 6.1.1 base that connects to HX but yields zero-resolution frames; the system 6.3.2
        # base loaded here is reused for cyndilib's by-name DLL import. Silent no-op when the
        # system runtime is absent (then cyndilib uses its bundled runtime — full/mock NDI is
        # unaffected). See _prefer_system_ndi_runtime + debug/cyndilib-ndi-hx-no-decode.
        _prefer_system_ndi_runtime()

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
            # The per-iteration loop body lives in _run_receiver, which takes every
            # collaborator (finder/receiver/video_frame/cv2) as a PARAMETER. This is the
            # headless seam: tests drive _run_receiver with pure fakes (no real cyndilib/cv2).
            self._run_receiver(cam_id, source_name, finder, receiver, video_frame, cv2)
        finally:
            receiver.disconnect()
            finder.close()

    def _run_receiver(self, cam_id, source_name, finder, receiver, video_frame, cv2) -> None:
        """The supervised per-camera capture loop, driven by injected collaborators.

        No heavy import lives here — ``cv2`` and the cyndilib objects are passed in by
        :meth:`_receiver_loop` (which owns the lazy boundary). That makes this loop the seam a
        headless test drives with pure fakes.

        Disconnected branch (CR-02 fix): instead of a bare ``continue`` that busy-spins a CPU
        core, the loop sleeps ``_RECEIVER_DISCONNECTED_SLEEP_S`` and then re-resolves the named
        source — so a source absent at thread start (or one that dropped) is picked up and
        reconnected WITHOUT a ``stop()``/``start()`` cycle (auto-reconnect). The real near-zero
        CPU + live cyndilib reconnect are HARDWARE-verified (@pytest.mark.ndi); this code path
        is the headless-provable logic.
        """
        last_ts: float | None = None
        while not self._stop.is_set():
            if not receiver.is_connected():
                # CR-02: no busy-spin — coast a short interval (no CPU pin) ...
                time.sleep(_RECEIVER_DISCONNECTED_SLEEP_S)
                # ... then re-resolve a (possibly late-appearing) named source and reconnect
                # without a stop()/start() cycle (auto-reconnect).
                source = self._resolve_source(finder, source_name)
                if source is not None:
                    receiver.set_source(source)
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
            # Pace the NON-BLOCKING frame_sync poll (~500Hz) so the connected loop does not
            # busy-spin a full CPU core per camera (see _RECEIVER_POLL_INTERVAL_S). The newest
            # frame is always available on the next capture, so this adds no real pickup latency.
            time.sleep(_RECEIVER_POLL_INTERVAL_S)

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
