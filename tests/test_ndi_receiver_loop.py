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

from segugio.ndi import ndi_source
from segugio.ndi.ndi_source import (
    NdiFrameSource,
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
