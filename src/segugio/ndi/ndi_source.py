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

[RESOLVED A1 — debug/watchdog-hx-feed-death] The original RBT-01 substrate keyed liveness on
``VideoFrameSync.get_timestamp_posix()`` (the receiver-SDK timestamp), ASSUMING it stalls on a
frozen feed. That assumption is FALSE on the cyndilib **FrameSync** path: NDIlib_framesync
re-clocks delivery and ADVANCES ``timestamp`` even when it re-delivers the last (frozen) frame
after the sender dies (HX phone app closed). So a dead HX feed kept looking "new" forever and the
watchdog never declared it dead (Phase 05 UAT Test 2 blocker). Two coupled defects were fixed in
``_run_receiver`` below:
  1. **Liveness now gates on DECODED-CONTENT CHANGE**, not on the re-clocked timestamp. A lossy
     HX sender never emits two bit-identical frames; a dead sender re-delivers byte-identical
     pixels — so a cheap strided fingerprint of the decoded buffer is a sound live/dead signal,
     INDEPENDENT of which NDI time field the library re-clocks. (Real cameras are never bit-stable;
     a synthetic perfectly-static source is the documented edge — see ``_frame_fingerprint``.)
  2. **``last_frame_ts`` is stamped with ``time.monotonic()``** — the SAME clock the orchestrator's
     live ``run()`` passes as ``now`` to ``FeedWatchdog`` (loop.py). The old POSIX
     ``get_timestamp_posix()`` value lived in a different clock domain than ``time.monotonic()``,
     so even a true stall could not compute a correct ``now - last_frame_ts`` gap.
``FeedWatchdog`` itself was already correct and is unchanged. The headless mock-clip path
(``ClipReplayFrameSource``) and the full/uncompressed OBS-PGM path are separate code and unaffected.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # type-only — keeps numpy/cyndilib off the runtime import path
    import numpy as np

    from ..config.models import Camera

__all__ = ["NdiFrameSource"]

# Throttle for a persistently-faulting receiver body (RBT-04 / T-9l5-05): the loop keeps
# retrying every iteration so the camera rejoins the instant the fault clears, but only the first
# fault of a streak plus a periodic heartbeat are logged — never a per-iteration traceback that
# would bury every other log line (mirrors ObsWsController's _OBS_FAIL_LOG_EVERY hygiene).
_RECEIVER_FAULT_LOG_EVERY = 150  # ~a heartbeat every few seconds at the poll pace

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

# Decoded-content liveness fingerprint stride (RBT-01 / debug:watchdog-hx-feed-death). The
# liveness substrate is "did the SENDER produce new imagery?", which we read from whether the
# DECODED frame buffer changed — NOT from the cyndilib FrameSync timestamp (which the NDI library
# re-clocks even on a re-delivered frozen frame, so a dead HX feed kept looking 'new' forever).
# We sample the raw RGBA buffer every Nth byte and sum it: a lossy-compressed HX sender never
# emits two bit-identical frames (sensor noise + re-quantization), while a dead sender re-delivers
# byte-identical pixels — so a change in this cheap fingerprint is a sound NEW-frame signal. The
# stride keeps the per-poll cost tiny (a ~1080p RGBA buffer is ~8.3M bytes; stride 4096 samples
# ~2k bytes) — far inside the ~500Hz poll budget. A genuinely bit-stable source (a synthetic test
# pattern, NOT a real camera) is the documented edge: it would be treated as frozen; real HX
# cameras are never bit-stable, which is the live-verified case this fix targets.
_FINGERPRINT_STRIDE = 4096

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


def _frame_fingerprint(arr, stride: int = _FINGERPRINT_STRIDE) -> int:
    """Cheap content fingerprint of a decoded frame buffer — the NEW-frame liveness signal.

    Sums a strided sample of the 1-D ``uint8`` frame buffer (``VideoFrameSync.get_array()``).
    Two genuinely-new HX frames differ (lossy compression + sensor noise) so the fingerprint
    changes; a dead sender's re-delivered frozen frame is byte-identical so the fingerprint is
    stable — exactly the substrate the liveness gate needs (it never advances on a frozen feed,
    unlike the cyndilib FrameSync timestamp). Falls back to a length-only fingerprint if ``arr``
    is not subscriptable (defensive — never raises into the receiver loop).

    Args:
        arr: a 1-D ``numpy`` ``uint8`` buffer (the ``get_array()`` result), or any array-like.
        stride: sample every ``stride``-th byte (keeps the per-poll cost tiny on a 1080p buffer).

    Returns:
        An ``int`` fingerprint that changes iff the sampled content changed.
    """
    try:
        sample = arr[::stride]
        # numpy path: int(sample.sum()) is a single vectorized reduction over the small sample.
        total = sample.sum()
        return int(total)
    except Exception:  # pragma: no cover - defensive: never raise into the receiver loop
        try:
            return int(len(arr))
        except Exception:
            return 0


def _diagnose_sources(configured: "dict[str, str]", discovered_names) -> dict:
    """PURE, cyndilib-free NDI discovery diagnosis (Fix #6 / T-9l5-07) — the headless-testable core.

    Splits the configured ``{cam_id: source_name}`` into ``found``/``missing`` by EXACT-match
    membership against the Finder's advertised ``discovered_names`` — the SAME match
    :meth:`NdiFrameSource._resolve_source` uses, so a drifted/near-miss name (the recurring
    "OBS sees it but the console is blank" gotcha) is reported as missing.

    Args:
        configured: ``{cam_id: source_name}`` — the cameras' configured ``ndi_source`` names.
        discovered_names: the list/iterable of source names the Finder currently advertises.

    Returns:
        ``{"found": {cam_id: name, ...}, "missing": {cam_id: name, ...}}``.
    """
    names = set(discovered_names or ())
    found: dict[str, str] = {}
    missing: dict[str, str] = {}
    for cam_id, name in configured.items():
        (found if name in names else missing)[cam_id] = name
    return {"found": found, "missing": missing}


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
        # Per-camera SETUP-fault streak (WR-01): throttles the setup-fault log across the
        # supervisor's ~1Hz respawns so a persistent setup failure (e.g. the NDI base<->HX plugin
        # pairing gotcha) logs a heartbeat, not one raw traceback per respawn.
        self._setup_faults: dict[str, int] = {}

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
        NDI-03 zero-resolution guard → reshape ``(yres, xres, 4)`` → NEW-frame CONTENT-CHANGE
        check (a frozen feed stops here) → ``cvtColor(RGBA2BGR)`` → ``_publish`` with a
        ``time.monotonic()`` stamp. Runs until ``stop()`` sets the event.
        """
        # Pair the system NDI 6.3.2 base runtime with the 6.3.2 HX plugin BEFORE importing
        # cyndilib, so NDI|HX (compressed phone) sources actually decode. cyndilib bundles a
        # 6.1.1 base that connects to HX but yields zero-resolution frames; the system 6.3.2
        # base loaded here is reused for cyndilib's by-name DLL import. Silent no-op when the
        # system runtime is absent (then cyndilib uses its bundled runtime — full/mock NDI is
        # unaffected). See _prefer_system_ndi_runtime + debug/cyndilib-ndi-hx-no-decode.
        finder = None
        receiver = None
        try:
            # ── SETUP (WR-01 fault isolation) ──────────────────────────────────────────────────
            # Pairing the system NDI 6.3.2 runtime, the lazy cyndilib/cv2 imports, and the
            # Finder/Receiver construction below can all raise PERSISTENTLY — most notably the
            # NDI base<->HX plugin pairing gotcha (debug/cyndilib-ndi-hx-no-decode) this team has
            # already been bitten by. If any of that escaped _receiver_loop, the thread would die
            # with a RAW, unthrottled stderr traceback that the loguru file sink (Fix #4) never
            # captures, and the tick-loop supervisor (Fix #2) would respawn it ~1Hz forever. Isolate
            # setup so a setup fault is logged THROUGH loguru (lands in segugio.log), throttled, and
            # the thread exits cleanly — the supervisor still retries, now diagnosably.
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
        except Exception as exc:  # noqa: BLE001 — WR-01: a setup fault must NOT dump a raw stderr traceback
            n = self._setup_faults.get(cam_id, 0) + 1
            self._setup_faults[cam_id] = n
            if n == 1 or n % _RECEIVER_FAULT_LOG_EVERY == 0:
                logger.error(
                    "ndi receiver {} SETUP fault (thread exits; supervisor retries) [{} consecutive]: {}",
                    cam_id,
                    n,
                    exc,
                )
            self._close_quietly(receiver, finder)
            return

        # Setup succeeded — clear this camera's setup-fault streak.
        self._setup_faults[cam_id] = 0
        try:
            # Best-effort initial connect. _run_receiver re-resolves + reconnects in its disconnected
            # branch, so a transient set_source hiccup here must not kill the thread (WR-01) — defer it.
            try:
                source = self._resolve_source(finder, source_name)
                if source is not None:
                    receiver.set_source(source)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ndi receiver {} initial connect deferred to the loop: {}", cam_id, exc
                )
            # The per-iteration loop body lives in _run_receiver, which takes every
            # collaborator (finder/receiver/video_frame/cv2) as a PARAMETER. This is the
            # headless seam: tests drive _run_receiver with pure fakes (no real cyndilib/cv2).
            self._run_receiver(cam_id, source_name, finder, receiver, video_frame, cv2)
        finally:
            self._close_quietly(receiver, finder)

    @staticmethod
    def _close_quietly(receiver, finder) -> None:
        """Best-effort teardown of a receiver/finder — never raises (WR-01 cleanup)."""
        if receiver is not None:
            try:
                receiver.disconnect()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
        if finder is not None:
            try:
                finder.close()
            except Exception:  # pragma: no cover - defensive cleanup
                pass

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

        Connected branch (RBT-01 liveness, debug:watchdog-hx-feed-death): a frame is published
        (advancing ``last_frame_ts``) ONLY when its decoded-content fingerprint CHANGES — a frozen
        HX feed re-delivers byte-identical pixels, so its fingerprint stalls and ``last_frame_ts``
        stops advancing → the watchdog declares it dead. The stamp is ``time.monotonic()`` (the
        watchdog's own clock domain), not the FrameSync POSIX timestamp (which re-clocks on a
        repeated frame and lives in a different clock domain).
        """
        last_fingerprint: int | None = None
        # RBT-04 / T-9l5-05 fault isolation: the per-iteration BODY is wrapped in a try/except so a
        # single transient cyndilib/cv2 fault (a decode hiccup, a mid-reconnect finder call) is
        # caught → logged (throttled) → coasted, and the daemon thread SURVIVES to re-attempt next
        # iteration. Without this, one stray exception escapes _receiver_loop and KILLS the thread —
        # the camera is lost for the whole event (no crash, but a silently dead feed). The
        # ``while not self._stop.is_set()`` guard stays OUTSIDE the try so a genuine stop() still
        # exits cleanly (the stop is never swallowed). ``fault_streak`` drives the log throttle.
        fault_streak = 0
        while not self._stop.is_set():
            try:
                if not receiver.is_connected():
                    # CR-02: no busy-spin — coast a short interval (no CPU pin) ...
                    time.sleep(_RECEIVER_DISCONNECTED_SLEEP_S)
                    # ... then re-resolve a (possibly late-appearing) named source and reconnect
                    # without a stop()/start() cycle (auto-reconnect).
                    source = self._resolve_source(finder, source_name)
                    if source is not None:
                        receiver.set_source(source)
                    fault_streak = 0  # a healthy disconnected coast clears the fault streak
                    continue
                receiver.frame_sync.capture_video()
                # NDI-03: the first frames after set_source are often zero-resolution.
                if min(video_frame.xres, video_frame.yres) != 0:
                    # RBT-01 NEW-frame substrate (debug:watchdog-hx-feed-death): liveness is gated on
                    # whether the DECODED CONTENT changed, NOT on the FrameSync timestamp. cyndilib
                    # FrameSync re-clocks (advances) get_timestamp_posix() even when it re-delivers
                    # the last frozen frame after the sender dies, so a dead HX feed used to look
                    # 'new' forever. A lossy HX sender never emits two bit-identical frames; a dead
                    # sender re-delivers byte-identical pixels — so a change in the content
                    # fingerprint is the genuine NEW-frame signal that STALLS on a dead feed.
                    arr = video_frame.get_array().reshape(
                        video_frame.yres, video_frame.xres, 4
                    )
                    fingerprint = _frame_fingerprint(arr)
                    if fingerprint != last_fingerprint:
                        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                        # Stamp with time.monotonic() — the SAME clock the orchestrator's live run()
                        # passes to FeedWatchdog as `now`, so (now - last_frame_ts) is a correct,
                        # single-domain gap (the old get_timestamp_posix() was real POSIX, a different
                        # clock than time.monotonic() → a meaningless gap). On a frozen feed the
                        # fingerprint stops changing → last_frame_ts stops advancing → watchdog dead.
                        self._publish(cam_id, bgr, time.monotonic())
                        last_fingerprint = fingerprint
                # Pace the NON-BLOCKING frame_sync poll (~500Hz) so the connected loop does not
                # busy-spin a full CPU core per camera (see _RECEIVER_POLL_INTERVAL_S). The newest
                # frame is always available on the next capture, so this adds no real pickup latency.
                time.sleep(_RECEIVER_POLL_INTERVAL_S)
                fault_streak = 0  # a healthy connected pass clears the fault streak
            except Exception as exc:  # noqa: BLE001 — RBT-04: a transient fault must NOT kill the thread
                fault_streak += 1
                if fault_streak == 1 or fault_streak % _RECEIVER_FAULT_LOG_EVERY == 0:
                    logger.warning(
                        "ndi receiver {} body fault (coasting; thread survives) [{} consecutive]: {}",
                        cam_id,
                        fault_streak,
                        exc,
                    )
                # Never re-raise, never tight-spin. On the FIRST fault, coast one poll interval so a
                # one-off transient re-attempts promptly; on a PERSISTENT streak, back off to the
                # longer disconnected interval so a stuck connected-path fault does not churn ~500
                # exceptions/sec/camera on the box running the <300ms AI loop (review WR-02).
                time.sleep(
                    _RECEIVER_DISCONNECTED_SLEEP_S if fault_streak > 1 else _RECEIVER_POLL_INTERVAL_S
                )

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
        """Store the newest frame + its NEW-frame ``time.monotonic()`` stamp under the lock (RBT-01).

        ``ts`` is a ``time.monotonic()`` reading taken at the moment a genuinely-new frame
        (content fingerprint changed) was observed — the same clock domain the watchdog's ``now``
        uses, so ``now - last_frame_ts`` is a correct gap.
        """
        with self._lock:
            self._latest[cam_id] = bgr
            self._ts[cam_id] = ts

    def latest(self, cam_id: str) -> "np.ndarray | None":
        """Return the newest BGR frame for ``cam_id``, or ``None`` to coast (no frame yet)."""
        with self._lock:
            return self._latest.get(cam_id)

    def last_frame_ts(self, cam_id: str) -> float | None:
        """``time.monotonic()`` stamp of the last CONTENT-CHANGED frame for ``cam_id``, or ``None``.

        Advances only when the decoded content actually changed (a frozen HX feed stalls it); read
        by ``FeedWatchdog`` against a ``time.monotonic()`` ``now`` (same clock domain) — RBT-01.
        """
        with self._lock:
            return self._ts.get(cam_id)

    def stop(self) -> None:
        """Signal every receiver thread to stop, join them, and release resources (RBT-04)."""
        self._stop.set()
        for t in self._threads.values():
            t.join(timeout=2.0)
        self._threads.clear()

    def preflight(self, wait_s: float = 2.0, finder=None) -> dict:
        """Startup NDI discovery doctor: enumerate live sources + emit a per-camera NOT-FOUND error.

        ``_resolve_source`` does a literal ``source_name in names`` and silently coasts on any miss,
        so a drifted/near-miss configured ``ndi_source`` never resolves and the operator gets no
        signal (the "OBS sees it but the console is blank" gotcha). This doctor is called ONCE at
        startup (from the orchestrator ``run()``): it enumerates the live NDI sources and emits a
        clear, operator-facing ``ERROR`` for every configured source ABSENT from discovery, plus an
        ``INFO`` summary of the found ones.

        Best-effort (RBT-04 "nessun crash ammesso"): any discovery failure is logged and returns an
        empty/partial report — it NEVER raises into startup.

        Args:
            wait_s: seconds to let the Finder populate before reading names (discovery is async).
            finder: an injectable cyndilib-``Finder``-shaped collaborator (``get_source_names()``);
                ``None`` builds + opens + closes the real ``Finder`` (lazy import, mirroring
                ``_receiver_loop``'s boundary + the system-NDI-runtime preload). The seam lets a
                headless test drive the doctor with a pure fake (no real cyndilib).

        Returns:
            ``{"found": {cam_id: name, ...}, "missing": {cam_id: name, ...}}`` (empty on failure).
        """
        own_finder = False
        try:
            if finder is None:
                # Pair the system 6.3.2 NDI runtime BEFORE importing cyndilib (see _receiver_loop).
                _prefer_system_ndi_runtime()
                from cyndilib.finder import Finder  # lazy heavy import inside the method

                finder = Finder()
                finder.open()
                own_finder = True
            # Let discovery populate (async) before reading the advertised names.
            time.sleep(wait_s)
            try:
                names = list(finder.get_source_names())
            except Exception:  # pragma: no cover - finder API may differ across cyndilib builds
                names = []
            report = _diagnose_sources(self._sources, names)
            for cam_id, name in report["missing"].items():
                logger.error(
                    "ndi_source '{}' (cam {}) NOT FOUND among discovered NDI sources: {}",
                    name,
                    cam_id,
                    names,
                )
            if report["found"]:
                logger.info(
                    "ndi preflight: {} configured source(s) discovered: {}",
                    len(report["found"]),
                    report["found"],
                )
            return report
        except Exception as exc:  # noqa: BLE001 — a discovery failure must NEVER crash startup
            logger.warning("ndi preflight coasted (discovery failure): {}", exc)
            return {"found": {}, "missing": {}}
        finally:
            if own_finder and finder is not None:
                try:
                    finder.close()
                except Exception:  # pragma: no cover — teardown must never raise
                    pass
