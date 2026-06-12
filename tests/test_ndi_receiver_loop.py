"""CR-02 (code fix) — the NDI receiver loop coasts + auto-reconnects, headlessly.

These are PURE-FAKE tests (NOT marked ``ndi``): they drive ``NdiFrameSource._run_receiver``
— the headless seam that takes every cyndilib/cv2 collaborator as a parameter — with light
fakes, so they run under ``pytest -m "not gpu and not ndi and not obs"`` with cyndilib/cv2
ABSENT. They assert the two CR-02 CODE defects are fixed:

  - the disconnected branch SLEEPS (``_RECEIVER_DISCONNECTED_SLEEP_S``) instead of busy-spinning;
  - a named source absent at thread start is RE-RESOLVED + reconnected (auto-reconnect) without
    a ``stop()``/``start()`` cycle.

The real near-zero-CPU figure and live cyndilib reconnect stay HARDWARE-verified
(@pytest.mark.ndi on the Windows box). Both tests are BOUNDED (they set ``_stop`` after a fixed
number of iterations) so a regression that reintroduces the bare-continue busy-spin would HANG
and fail under pytest's timeout rather than silently pass.
"""

from __future__ import annotations

import pytest

import numpy as np

from segugio.ndi import ndi_source
from segugio.ndi.ndi_source import (
    NdiFrameSource,
    _frame_fingerprint,
    _RECEIVER_DISCONNECTED_SLEEP_S,
    _RECEIVER_POLL_INTERVAL_S,
)


class _FakeReceiver:
    """A cyndilib-Receiver-shaped fake driven by a scripted is_connected() sequence."""

    def __init__(self, connected_seq):
        # connected_seq: list of bools consumed one per is_connected() call.
        self._seq = list(connected_seq)
        self.set_source_calls: list[object] = []

    def is_connected(self) -> bool:
        if self._seq:
            return self._seq.pop(0)
        return False

    def set_source(self, source) -> None:
        self.set_source_calls.append(source)


class _FakeFinder:
    """A cyndilib-Finder-shaped fake whose visible source names are scripted per call."""

    def __init__(self, names_per_call):
        # names_per_call: list of name-lists, one consumed per get_source_names() call.
        self._names_per_call = list(names_per_call)
        self.resolve_calls = 0

    def get_source_names(self):
        self.resolve_calls += 1
        if self._names_per_call:
            return self._names_per_call.pop(0)
        return []

    def get_source(self, name):
        return ("source", name)


def _make_source() -> NdiFrameSource:
    """An NdiFrameSource with no cameras (we drive _run_receiver directly, not start())."""
    return NdiFrameSource(cameras=[])


def test_receiver_loop_sleeps_when_disconnected(monkeypatch):
    """The disconnected branch SLEEPS (no busy-spin) and the loop terminates (CR-02)."""
    src = _make_source()

    sleep_calls: list[float] = []

    def _record_sleep(dt):
        sleep_calls.append(dt)
        # After the first disconnected sleep, signal stop so the loop exits — keeps the
        # test BOUNDED (a reintroduced bare-continue busy-spin would never sleep → hang here).
        src._stop.set()

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)

    # is_connected() returns False on the first iteration → disconnected branch → sleep → stop.
    receiver = _FakeReceiver(connected_seq=[False])
    finder = _FakeFinder(names_per_call=[[]])  # source still absent on the re-resolve attempt

    src._run_receiver("cam_wide", "PHONE-WIDE (NDI)", finder, receiver, video_frame=None, cv2=None)

    # (a) the disconnected branch slept with the documented interval → NO busy-spin.
    assert sleep_calls == [_RECEIVER_DISCONNECTED_SLEEP_S]
    # (b) the loop terminated (we got here without hanging).


def test_receiver_loop_re_resolves_absent_source(monkeypatch):
    """A late-appearing named source is re-resolved + reconnected on the disconnected branch."""
    src = _make_source()
    source_name = "PHONE-WIDE (NDI)"

    # Drive a bounded number of iterations; stop after the second disconnected pass so the
    # late source (visible on the 2nd get_source_names call) gets re-resolved + set.
    iterations = {"n": 0}

    def _record_sleep(dt):
        iterations["n"] += 1
        if iterations["n"] >= 2:
            src._stop.set()  # bounded: exit after the source has re-appeared

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)

    # Disconnected on both iterations (so we exercise only the disconnected/re-resolve branch).
    receiver = _FakeReceiver(connected_seq=[False, False])
    # Source ABSENT on the first re-resolve, PRESENT on the second (appears late).
    finder = _FakeFinder(names_per_call=[[], [source_name]])

    src._run_receiver(source_name, source_name, finder, receiver, video_frame=None, cv2=None)

    # _resolve_source was attempted more than once inside the disconnected branch
    # (auto-reconnect re-polls the finder each disconnected pass).
    assert finder.resolve_calls >= 2
    # set_source was called AFTER the late source appeared → reconnect without stop()/start().
    assert receiver.set_source_calls == [("source", source_name)]


class _FrameSyncStub:
    """A non-blocking frame_sync, like real cyndilib: capture_video() just bumps a counter."""

    def __init__(self):
        self.captures = 0

    def capture_video(self) -> None:
        self.captures += 1


class _ConnectedReceiver:
    """Always-connected receiver exposing the non-blocking frame_sync.capture_video() seam."""

    def __init__(self):
        self.frame_sync = _FrameSyncStub()
        self.set_source_calls: list[object] = []

    def is_connected(self) -> bool:
        return True

    def set_source(self, source) -> None:  # pragma: no cover - not hit on the connected path
        self.set_source_calls.append(source)


class _ZeroResFrame:
    """A video_frame whose xres/yres are 0 → the NDI-03 guard skips frame work (no cv2 needed)."""

    xres = 0
    yres = 0


def test_receiver_loop_paces_connected_branch(monkeypatch):
    """The CONNECTED branch SLEEPS the poll interval — no busy-spin (perf fix).

    ``frame_sync.capture_video()`` is non-blocking (~0.2us on real cyndilib 0.1.1, ~5.6M
    calls/s), so without pacing the connected loop pins a full CPU core PER camera — found in
    the 05 UAT against a live NDI stream. The loop now sleeps ``_RECEIVER_POLL_INTERVAL_S`` each
    connected pass; a regression that drops the sleep would busy-spin and HANG this bounded test.
    """
    src = _make_source()
    sleeps: list[float] = []

    def _record_sleep(dt):
        sleeps.append(dt)
        src._stop.set()  # bounded: stop after the first connected-branch pace sleep

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)

    receiver = _ConnectedReceiver()
    finder = _FakeFinder(names_per_call=[[]])
    src._run_receiver("cam_wide", "X", finder, receiver, video_frame=_ZeroResFrame(), cv2=None)

    # It polled the frame_sync once, then PACED (slept the poll interval) instead of busy-spinning.
    assert receiver.frame_sync.captures == 1
    assert sleeps == [_RECEIVER_POLL_INTERVAL_S]


def test_run_receiver_is_bounded_and_terminates_on_stop(monkeypatch):
    """Sanity: with _stop already set the loop does no work and returns immediately."""
    src = _make_source()
    src._stop.set()

    # If the loop somehow entered the body it would call sleep; assert it never does.
    monkeypatch.setattr(
        ndi_source.time, "sleep",
        lambda dt: pytest.fail("loop body ran despite _stop set"),
    )
    receiver = _FakeReceiver(connected_seq=[False])
    finder = _FakeFinder(names_per_call=[[]])

    src._run_receiver("cam_wide", "X", finder, receiver, video_frame=None, cv2=None)
    assert receiver.set_source_calls == []


# --------------------------------------------------------------------------- #
# RBT-01 NEW-frame liveness substrate (debug:watchdog-hx-feed-death)
#
# The bug: cyndilib FrameSync re-clocks get_timestamp_posix() even when it re-delivers the LAST
# (frozen) frame after the sender dies, so a dead HX feed kept advancing last_frame_ts forever and
# the watchdog never declared it dead. The fix gates liveness on whether the DECODED CONTENT
# changed (a frozen feed re-delivers byte-identical pixels → fingerprint stalls) and stamps
# last_frame_ts with time.monotonic() (the watchdog's clock domain). These pure-fake tests model a
# STALLING (frozen) vs NON-STALLING (live) decoded-content substrate and assert last_frame_ts
# behaves correctly — the headless-provable core of the live close-app repro.
# --------------------------------------------------------------------------- #


class _FakeCv2:
    """A cv2 stub: cvtColor is identity (the loop only needs SOMETHING array-shaped to publish)."""

    COLOR_RGBA2BGR = 0

    @staticmethod
    def cvtColor(arr, code):
        # Return a cheap BGR-shaped view; the test only inspects last_frame_ts, not pixels.
        return arr[..., :3]


class _ScriptedVideoFrame:
    """A VideoFrameSync-shaped fake whose get_array() returns a scripted RGBA buffer per poll.

    Each entry in ``arrays`` is a 1-D uint8 RGBA buffer returned on successive capture polls.
    Repeating the SAME buffer models a frozen feed (FrameSync re-delivering the last frame); a
    DIFFERENT buffer models a genuinely-new frame. reshape() is honored so the loop's
    ``(yres, xres, 4)`` reshape works on the flat buffer.
    """

    def __init__(self, arrays, xres=2, yres=2):
        self._arrays = list(arrays)
        self._i = 0
        self.xres = xres
        self.yres = yres

    def get_array(self):
        arr = self._arrays[min(self._i, len(self._arrays) - 1)]
        self._i += 1
        return arr


def _rgba(values):
    """Build a 1-D uint8 RGBA buffer for a 2x2 frame (16 bytes) from a 16-int list."""
    return np.array(values, dtype=np.uint8)


def test_fingerprint_changes_with_content_and_stalls_when_frozen():
    """_frame_fingerprint: changes iff sampled content changes (the live/dead discriminator)."""
    a = _rgba([10] * 16)
    b = _rgba([10] * 16)  # byte-identical → frozen-feed re-delivery
    c = _rgba([10] * 15 + [200])  # one byte different → genuinely-new frame

    # Stride 1 so the tiny test buffers are fully sampled.
    fa = _frame_fingerprint(a, stride=1)
    fb = _frame_fingerprint(b, stride=1)
    fc = _frame_fingerprint(c, stride=1)

    assert fa == fb, "byte-identical (frozen) frames must share a fingerprint → no false 'new'"
    assert fc != fa, "a changed frame must produce a different fingerprint → genuine 'new'"


def test_fingerprint_never_raises_on_non_array():
    """Defensive: a non-subscriptable / odd input falls back, never raises into the loop."""
    assert isinstance(_frame_fingerprint(object()), int)


def _run_connected_n_polls(src, video_frame, n, monkeypatch):
    """Drive _run_receiver for exactly ``n`` connected polls, then stop. Returns sleep count."""
    receiver = _ConnectedReceiver()
    finder = _FakeFinder(names_per_call=[[]] * (n + 1))
    polls = {"n": 0}

    def _record_sleep(dt):
        # Only the connected-branch pace sleep matters here; stop after n polls.
        if dt == _RECEIVER_POLL_INTERVAL_S:
            polls["n"] += 1
            if polls["n"] >= n:
                src._stop.set()

    monkeypatch.setattr(ndi_source.time, "sleep", _record_sleep)
    src._run_receiver("cam_wide", "X", finder, receiver, video_frame, _FakeCv2())
    return polls["n"]


def test_live_feed_advances_last_frame_ts(monkeypatch):
    """A NON-STALLING (changing-content) substrate keeps advancing last_frame_ts (feed alive)."""
    src = _make_source()
    # Three DISTINCT frames over three polls → three genuine 'new' frames.
    frames = [
        _rgba([i] * 16) for i in (10, 20, 30)
    ]
    video_frame = _ScriptedVideoFrame(frames)

    # A monotonic clock we control so the assertion is deterministic (and proves the
    # time.monotonic() stamp domain — the fix's second leg).
    clock = {"t": 100.0}
    monkeypatch.setattr(ndi_source.time, "monotonic", lambda: clock["t"])

    stamps = []
    orig_publish = src._publish

    def _record(cam_id, bgr, ts):
        stamps.append(ts)
        clock["t"] += 1.0  # advance the monotonic clock between published frames
        orig_publish(cam_id, bgr, ts)

    monkeypatch.setattr(src, "_publish", _record)

    _run_connected_n_polls(src, video_frame, n=3, monkeypatch=monkeypatch)

    # Each distinct frame advanced last_frame_ts with a monotonic stamp (the live, alive case).
    assert stamps == [100.0, 101.0, 102.0]
    assert src.last_frame_ts("cam_wide") == 102.0


def test_frozen_feed_stalls_last_frame_ts(monkeypatch):
    """A STALLING (byte-identical re-delivery) substrate FREEZES last_frame_ts → watchdog dead.

    This is the headless analogue of the live close-app repro: after one real frame the feed
    'dies' and FrameSync re-delivers byte-identical pixels. last_frame_ts must be published ONCE
    (the last real frame) and then STOP advancing, no matter how many more frozen polls occur — so
    the orchestrator's FeedWatchdog (now - last_frame_ts > timeout) declares the camera dead.
    """
    src = _make_source()
    # One real frame, then the SAME bytes re-delivered forever (frozen sender).
    real = _rgba([42] * 16)
    frozen = _rgba([42] * 16)  # byte-identical re-delivery
    video_frame = _ScriptedVideoFrame([real, frozen, frozen, frozen, frozen])

    clock = {"t": 500.0}
    monkeypatch.setattr(ndi_source.time, "monotonic", lambda: clock["t"])

    stamps = []
    orig_publish = src._publish

    def _record(cam_id, bgr, ts):
        stamps.append(ts)
        clock["t"] += 1.0  # if a frozen frame were (wrongly) published, the stamp would advance
        orig_publish(cam_id, bgr, ts)

    monkeypatch.setattr(src, "_publish", _record)

    _run_connected_n_polls(src, video_frame, n=5, monkeypatch=monkeypatch)

    # Exactly ONE publish (the single real frame); the 4 frozen re-deliveries advanced nothing.
    assert stamps == [500.0], "a frozen feed must NOT keep advancing last_frame_ts (the bug)"
    assert src.last_frame_ts("cam_wide") == 500.0
