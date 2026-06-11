"""RBT-01 — feed watchdog liveness on INJECTED timestamps.

``FeedWatchdog`` deduces whether each camera's feed is alive PURELY from the
last-NEW-frame timestamp the caller passes in — never from the NDI source /
connection state (Pitfall 1: a frozen feed reports "connected" for ~75 min while
its frames stop; only the last-NEW-frame timestamp catches that). The watchdog
stores NO wall-clock: ``now`` is an injected argument, so these tests drive it on
injected ``(now, last_frame_ts)`` pairs and are fully deterministic.

Contract (05-04 Task 1):
  - advancing ``last_frame_ts`` within ``watchdog_timeout`` of ``now`` → alive.
  - ``last_frame_ts`` stalled (frozen feed repeats the same ts) for
    > ``watchdog_timeout + grace`` → DEAD (the anti-jitter grace stops a single
    late frame from flapping the feed dead).
  - a resumed/fresh ``last_frame_ts`` → alive again only because a NEW frame
    advanced the timestamp (not because ``now`` ticked forward).
  - ``last_frame_ts is None`` (no frame yet) → NOT alive (fail-safe, mirrors the
    FSM absent-from-map = NOT-alive rule).
"""

from __future__ import annotations

from segugio.watchdog_feed import FeedWatchdog


def test_advancing_timestamp_stays_alive():
    """A timestamp that keeps advancing with ``now`` is always alive (RBT-01)."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    # Each tick the feed delivers a fresh frame ~at `now` → always within timeout.
    for now in (0.0, 0.5, 1.0, 1.5, 2.0):
        assert wd.alive("cam_long", now=now, last_frame_ts=now) is True


def test_fresh_frame_within_timeout_is_alive():
    """A small gap (now - ts) under timeout+grace stays alive (RBT-01)."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    # 0.5s since the last NEW frame — well inside the 0.8s timeout.
    assert wd.alive("cam_long", now=10.5, last_frame_ts=10.0) is True


def test_stalled_timestamp_marks_dead_after_timeout():
    """A frozen feed (ts stuck) past timeout+grace is declared DEAD (RBT-01)."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    frozen_ts = 5.0  # the feed froze here; the source keeps reporting "connected"
    # Just inside the timeout+grace window → still alive (anti-jitter grace).
    assert wd.alive("cam_long", now=frozen_ts + 0.85, last_frame_ts=frozen_ts) is True
    # Past timeout+grace with the SAME (stalled) ts → DEAD.
    assert wd.alive("cam_long", now=frozen_ts + 1.0, last_frame_ts=frozen_ts) is False
    assert wd.alive("cam_long", now=frozen_ts + 5.0, last_frame_ts=frozen_ts) is False


def test_anti_jitter_grace_holds_a_single_late_frame():
    """A single frame arriving just past the bare timeout (within grace) does NOT flap dead."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.2)
    ts = 3.0
    # now - ts = 0.9 > timeout (0.8) but <= timeout + grace (1.0) → still alive (grace).
    assert wd.alive("cam_long", now=ts + 0.9, last_frame_ts=ts) is True
    # now - ts = 1.05 > timeout + grace → dead.
    assert wd.alive("cam_long", now=ts + 1.05, last_frame_ts=ts) is False


def test_fresh_timestamp_recovers_alive():
    """A NEW frame (advanced ts) brings a dead feed back alive — only because the ts moved."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    frozen_ts = 7.0
    # Feed is dead while frozen and `now` keeps advancing.
    assert wd.alive("cam_long", now=9.0, last_frame_ts=frozen_ts) is False
    # Same `now`, but a NEW frame arrived (ts advanced to ~now) → alive again.
    assert wd.alive("cam_long", now=9.0, last_frame_ts=8.95) is True


def test_none_timestamp_is_not_alive():
    """No frame ever observed (last_frame_ts is None) → NOT alive (fail-safe)."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    assert wd.alive("cam_long", now=0.0, last_frame_ts=None) is False
    assert wd.alive("cam_long", now=100.0, last_frame_ts=None) is False


def test_alive_map_reads_each_cameras_last_frame_ts():
    """``alive_map`` reads each camera's last_frame_ts off an injected frame source (RBT-01)."""

    class _Source:
        def __init__(self, ts: dict[str, float | None]) -> None:
            self._ts = ts

        def last_frame_ts(self, cam_id: str):
            return self._ts.get(cam_id)

    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    src = _Source(
        {
            "cam_wide": 9.9,  # fresh → alive
            "cam_long": 5.0,  # stalled (now=10.0, gap 5.0) → dead
            "cam_low": None,  # never delivered → dead
        }
    )
    amap = wd.alive_map(now=10.0, frame_source=src, cam_ids=["cam_wide", "cam_long", "cam_low"])
    assert amap == {"cam_wide": True, "cam_long": False, "cam_low": False}


def test_watchdog_is_clock_free_and_deterministic():
    """Same injected (now, ts) → same answer every call (no internal wall-clock/state drift)."""
    wd = FeedWatchdog(watchdog_timeout=0.8, grace=0.1)
    first = [wd.alive("c", now=n, last_frame_ts=t) for n, t in [(1.0, 1.0), (2.0, 1.0), (3.0, 2.9)]]
    second = [wd.alive("c", now=n, last_frame_ts=t) for n, t in [(1.0, 1.0), (2.0, 1.0), (3.0, 2.9)]]
    assert first == second == [True, False, True]
