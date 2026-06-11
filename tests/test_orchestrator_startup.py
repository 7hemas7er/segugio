"""CR-01 — the orchestrator survives OBS/NDI being DOWN at launch (the FAILED truth, SC-5/RBT-04).

The existing ``tests/test_fault_isolation.py`` doubles never RAISE on ``connect()``/``start()`` —
so they never exercise the startup path. THIS file injects a source/obs that RAISE on
``start()``/``connect()`` and proves ``run_measured`` still reaches and runs the tick loop. That is
the regression that flips Truth #5 (SC-5 / RBT-04 "nessun crash ammesso") to VERIFIED.

It also pins the three loop.py code-quality fixes folded into the same pass:
  - WR-02: ``from_config`` yields a non-zero config-sourced anti-jitter grace by default, and an
    explicit ``grace`` / a config value flow through.
  - WR-09: a non-feed fault (scorer/FSM exception) yields a status reason that is NOT "feed-dead".

Runs HEADLESS (``pytest -m "not gpu and not ndi and not obs"``): no cyndilib / obsws / cv2 /
ultralytics — the trackers are injected fakes so YOLO never loads.
"""

from __future__ import annotations

import copy

from segugio.opcomm.channel import read_status
from segugio.orchestrator.loop import Orchestrator


class _FakeTracker:
    """A per-camera tracker stand-in returning no detections (so the loop coasts cleanly)."""

    def track(self, frame):
        return None


class _ConnectRaisingObs:
    """An ObsController whose ``connect()`` RAISES (OBS down at launch) but otherwise records.

    ``cut`` never raises so the loop can air SAFE; ``connect`` raising is the CR-01 condition.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect-attempt",))
        raise ConnectionError("OBS is down at launch")

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut", scene_name))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        self.calls.append(("close",))


class _OkObs:
    """A recording ObsController that succeeds (used when the SOURCE is the fault under test)."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect",))

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut", scene_name))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        self.calls.append(("close",))


class _StartRaisingSource:
    """A FrameSource whose ``start()`` RAISES (NDI bring-up failed) but otherwise coasts.

    ``latest``/``last_frame_ts`` return None so every tick coasts cleanly; ``stop`` is a no-op.
    """

    def __init__(self) -> None:
        self.started_attempted = False
        self.stopped = False

    def start(self) -> None:
        self.started_attempted = True
        raise RuntimeError("source bring-up failed")

    def latest(self, cam_id: str):
        return None

    def last_frame_ts(self, cam_id: str):
        return None

    def stop(self) -> None:
        self.stopped = True


class _OkSource:
    """A FrameSource that never raises and produces nothing (isolates the OBS fault)."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def latest(self, cam_id: str):
        return None

    def last_frame_ts(self, cam_id: str):
        return None

    def stop(self) -> None:
        self.stopped = True


def _build(cfg, source, obs, file_channel, *, grace=None):
    """Construct an Orchestrator via from_config with fake trackers (YOLO never loads)."""
    trackers = {cam.id: _FakeTracker() for cam in cfg.cameras}
    kwargs = {}
    if grace is not None:
        kwargs["grace"] = grace
    return Orchestrator.from_config(
        config=cfg,
        source=source,
        obs=obs,
        channel_paths=file_channel,
        trackers=trackers,
        fps=30.0,
        **kwargs,
    )


def test_run_measured_survives_connect_raising(make_config, file_channel):
    """obs.connect() raising at launch (OBS down) → the tick loop STILL runs (CR-01/SC-5).

    THE regression that flips Truth #5: a ConnectionError crossing the OBS startup boundary is
    caught by _safe_startup and the loop coasts into 5 full ticks.
    """
    cfg = make_config()
    source = _OkSource()
    obs = _ConnectRaisingObs()
    orch = _build(cfg, source, obs, file_channel)

    # Must NOT raise even though connect() raised at startup.
    probe = orch.run_measured(n_ticks=5)

    # connect() was attempted (and raised) — proof the fault path was exercised, not bypassed.
    assert ("connect-attempt",) in obs.calls
    # The tick loop reached AND ran the tick body all 5 times despite the failed startup.
    assert len(probe["total"]) == 5


def test_run_measured_survives_source_start_raising(make_config, file_channel):
    """source.start() raising at launch (NDI down) → the tick loop STILL runs (CR-01/RBT-04)."""
    cfg = make_config()
    source = _StartRaisingSource()
    obs = _OkObs()
    orch = _build(cfg, source, obs, file_channel)

    probe = orch.run_measured(n_ticks=5)

    assert source.started_attempted is True  # start() was attempted (and raised)
    assert len(probe["total"]) == 5  # the loop ran all 5 ticks regardless


def test_from_config_grace_is_nonzero_by_default(make_config, fake_frame_source, file_channel):
    """from_config with NO grace arg yields a non-zero config-sourced anti-jitter grace (WR-02)."""
    cfg = make_config()
    obs = _OkObs()
    orch = _build(cfg, fake_frame_source, obs, file_channel)

    assert orch.watchdog.grace > 0.0
    assert orch.watchdog.grace == cfg.thresholds.watchdog_grace


def test_from_config_grace_respects_config_value(make_config, fake_frame_source, file_channel):
    """An explicit config watchdog_grace flows through; an explicit grace arg overrides it."""
    # The thresholds block is REPLACED wholesale by make_config's shallow update, so pass the
    # full block (every required key present) with watchdog_grace overridden to 0.25.
    thresholds = {
        "alpha": 0.3,
        "hysteresis_margin": 0.1,
        "min_dwell": 2.0,
        "debounce_N": 3,
        "cooldown": 1.0,
        "watchdog_timeout": 0.8,
        "watchdog_grace": 0.25,
        "track_buffer": 60,
    }
    cfg = make_config(overrides={"thresholds": copy.deepcopy(thresholds)})
    assert cfg.thresholds.watchdog_grace == 0.25

    obs = _OkObs()
    orch = _build(cfg, fake_frame_source, obs, file_channel)
    # No grace arg → config value (0.25) flows through to the watchdog.
    assert orch.watchdog.grace == 0.25

    # An explicit grace arg WINS over the config value.
    orch2 = _build(cfg, fake_frame_source, _OkObs(), file_channel, grace=0.5)
    assert orch2.watchdog.grace == 0.5


def test_non_feed_fault_reason_is_not_feed_dead(make_config, file_channel):
    """A scorer/FSM exception → the written status reason is NOT "feed-dead" (WR-09).

    Inject a scorer whose update() raises a non-feed exception; drive ONE tick and read the
    status the loop wrote. It must coast to SAFE with the distinct "fault" reason, never the
    "feed-dead" tag reserved for genuine feed deaths.
    """
    cfg = make_config()
    source = _OkSource()
    obs = _OkObs()
    orch = _build(cfg, source, obs, file_channel)

    def _boom(dets_by_cam, tick):
        raise RuntimeError("scorer blew up (non-feed fault)")

    orch.scorer.update = _boom  # type: ignore[assignment]

    orch._tick_once(0, now=1.0)

    status = read_status(str(file_channel["status"]))
    assert status.reason != "feed-dead"
    assert status.reason == "fault"
