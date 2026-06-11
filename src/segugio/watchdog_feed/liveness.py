"""``FeedWatchdog`` — pure last-NEW-frame liveness math (RBT-01).

The single robustness control that converts an unreliable feed-liveness signal into
the FSM's authoritative ``alive`` map. Liveness is deduced PURELY from the last-NEW-frame
timestamp the caller injects — NEVER from the NDI source / receiver ``is_connected()``
state (Pitfall 1 / T-05-04-01: a frozen NDI feed keeps reporting "connected" for ~75 min
while its frames stop arriving; only the last-NEW-frame timestamp catches the freeze).

Determinism / purity convention (mirrors ``CompetitorLock._motion_energy`` and the
``decision/`` clock-free style): the watchdog stores NO wall-clock and NO numpy at module
top. ``now`` is an INJECTED argument on every call, so the same ``(now, last_frame_ts)``
pair always yields the same answer. The wall-clock lives ONLY in the orchestrator caller
(05-06), never here — exactly the ``tick``-injected determinism the FSM and scorer follow.

Per-decision traceability (05-04 Task 1):

  * RBT-01 (liveness from last-NEW-frame ts ONLY): ``alive(cam, now, last_frame_ts)`` reads
    ``now - last_frame_ts`` and compares it against ``watchdog_timeout + grace``. It never
    consults a connection/source state.
  * Anti-jitter grace (T-05-04-02, DoS / flap mitigation): a small extra ``grace`` tolerance
    is added to ``watchdog_timeout`` so a single late frame does not flap the feed dead and
    trigger a cut storm. The FSM's hysteresis + dwell further damp the rejoin (RBT-02).
  * Fail-safe (T-05-04-03, Tampering): a ``None`` (no frame yet) / non-finite ``last_frame_ts``
    is treated as DEAD — the watchdog never raises (mirrors the FSM absent-from-map = NOT-alive
    rule and the "nessun crash ammesso" robustness constraint).
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

__all__ = ["FeedWatchdog", "FrameTimestampSource"]


@runtime_checkable
class FrameTimestampSource(Protocol):
    """The minimal frame-source shape ``alive_map`` reads: a per-camera last-NEW-frame ts.

    Structurally satisfied by the Phase-5 ``FrameSource`` (the NDI / clip mock) which exposes
    ``last_frame_ts(cam_id) -> float | None`` (the timestamp of the last frame whose payload
    actually CHANGED, never advanced on a frozen feed — the RBT-01 substrate, 05-02).
    """

    def last_frame_ts(self, cam_id: str) -> float | None: ...


class FeedWatchdog:
    """Pure liveness deducer: is each camera's feed alive from its last-NEW-frame timestamp?

    Construct once with the ``watchdog_timeout`` (read from ``Thresholds.watchdog_timeout``,
    =0.8s) and an optional anti-jitter ``grace`` (a small extra tolerance, e.g. 1-2 ticks
    worth). Then call ``alive(cam_id, now, last_frame_ts)`` per camera per tick, or
    ``alive_map(now, frame_source, cam_ids)`` to read every camera's timestamp off an injected
    frame source. The result feeds straight into ``DecisionEngine.tick(scores, alive=...)``.

    Args:
        watchdog_timeout: seconds a feed may go without a NEW frame before it is suspected dead
            (``Thresholds.watchdog_timeout``).
        grace: extra anti-jitter tolerance in seconds added to ``watchdog_timeout`` so a single
            late frame does not flap the feed dead (T-05-04-02). Defaults to 0.0 (no grace).
    """

    def __init__(self, watchdog_timeout: float, grace: float = 0.0) -> None:
        self.watchdog_timeout: float = float(watchdog_timeout)
        self.grace: float = float(grace)
        # The effective dead-after window: timeout + anti-jitter grace. Precomputed once;
        # the watchdog holds NO other state (no wall-clock, no per-camera memory).
        self._dead_after: float = self.watchdog_timeout + self.grace

    def alive(
        self, cam_id: str, now: float, last_frame_ts: float | None
    ) -> bool:
        """True iff ``cam_id``'s feed delivered a NEW frame within ``timeout + grace`` of ``now``.

        ``cam_id`` is accepted for interface symmetry with ``alive_map`` (and future per-camera
        tuning) but the liveness decision is purely ``now - last_frame_ts`` vs the dead-after
        window — the watchdog keeps no per-camera state. A ``None`` or non-finite
        ``last_frame_ts`` (no frame yet / poisoned reading) is DEAD (fail-safe). A negative gap
        (a fresh frame timestamped slightly ahead of ``now`` from clock skew) is alive.
        """
        if last_frame_ts is None or not math.isfinite(last_frame_ts):
            return False  # no frame observed / poisoned ts → fail-safe DEAD (T-05-04-03)
        if not math.isfinite(now):
            return False  # poisoned clock → fail-safe DEAD (never raise)
        # Alive iff the last NEW frame is within the dead-after window of `now`. Liveness is
        # this comparison ONLY — never a source/connection state (Pitfall 1 / RBT-01).
        return (now - last_frame_ts) <= self._dead_after

    def alive_map(
        self,
        now: float,
        frame_source: FrameTimestampSource,
        cam_ids: list[str],
    ) -> dict[str, bool]:
        """Build the ``{cam_id: bool}`` alive map the FSM consumes (``engine.tick(alive=...)``).

        Reads each camera's last-NEW-frame timestamp off the injected ``frame_source`` and
        applies ``alive(...)``. The result is the authoritative liveness map: a ``False`` entry
        means the on-air feed for that camera has failed, so the FSM excludes it as both live
        and challenger (DEC-06) → SAFE / other-live fallback (RBT-02).
        """
        return {
            cam_id: self.alive(cam_id, now, frame_source.last_frame_ts(cam_id))
            for cam_id in cam_ids
        }
