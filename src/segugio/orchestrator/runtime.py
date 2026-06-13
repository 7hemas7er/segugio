"""``build_orchestrator`` — the runtime compose/factory the UAT gap says ``from_config`` lacks.

``Orchestrator.from_config(config, source, obs, channel_paths, trackers, ...)`` deliberately
requires the real ``source`` / ``obs`` / ``trackers`` / ``channel_paths`` to be built and injected
by a caller. Phase 05 verified the loop LOGIC headlessly (5/5) but shipped NO such caller, so the
D-07 hardware E2E (UAT Tests 1-4) could not be launched on the rig. This module IS that caller —
the thin runtime glue that maps a validated ``Config`` onto the real collaborators:

  * ONE :class:`~segugio.ndi.ndi_source.NdiFrameSource` over ``config.cameras`` (each camera with a
    non-``None`` ``ndi_source`` gets one supervised receiver thread keyed by ``Camera.id``);
  * ONE :class:`~segugio.obs.obsws_controller.ObsWsController` (``host``/``port``/``password``);
  * ONE :class:`~segugio.tracking.detector.PerCameraTracker` PER camera (never a frame list to one
    tracker — #13107); seeded with ``config.model.path`` + ``config.model.class_index`` (the loop
    resolves the dog index BY NAME at first inference — never hardcodes 16, CFG-04);
  * the opcomm ``channel_paths`` built from ``channel_dir`` with the SAME constant filenames the UI
    writes (``command.json`` / ``runstate.json`` / ``status.json`` — plus ``score.json`` /
    ``overlay.txt``), so the operator console and the orchestrator agree on ONE channel.

It then returns ``Orchestrator.from_config(...)`` — it does NOT re-architect the loop and does NOT
change ``from_config``'s signature; it CALLS it.

OBS credentials: ``Config`` has NO ``obs`` block and uses ``extra="forbid"`` (one cannot be added
without a model change), so the factory passes the hardcoded defaults ``localhost`` / ``4455`` /
``None`` — already identical to ``ObsWsController.__init__``'s own defaults. Sourcing OBS creds
from YAML is a future Config-model change, deliberately out of scope for this thin-wiring plan.

INJECTABLE CONSTRUCTION SEAM (the headless-testability contract): the three ``*_factory`` params
DEFAULT to the real builders below but can be overridden so a unit test passes fakes — exactly the
``ObsWsController.client_factory`` (05-03) / ``NdiFrameSource._run_receiver`` (05-08) pattern. The
default builders import the heavy deps (cyndilib / obsws / cv2 / ultralytics) LAZILY, INSIDE the
builder bodies, so ``import segugio.orchestrator.runtime`` succeeds with the heavy stack ABSENT
(the Phase-1 lazy-import boundary, mirrored from ``loop.py``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .loop import Orchestrator

if TYPE_CHECKING:  # type-only — keeps heavy/config deps off the runtime import path
    from ..config.models import Config

__all__ = ["build_orchestrator"]

# The operator↔system channel filenames — IDENTICAL to ui/app.py's constants so the console and
# the orchestrator share ONE channel dir. The loop reads command/runstate/status; score/overlay
# are written by the UI/score manager and carried here so the bundle is complete (harmless to the
# loop, which only reads the three it needs).
_COMMAND_FILE = "command.json"
_RUNSTATE_FILE = "runstate.json"
_STATUS_FILE = "status.json"
_SCORE_FILE = "score.json"
_OVERLAY_FILE = "overlay.txt"

# OBS defaults — Config carries no obs block (extra="forbid"); these match ObsWsController's own
# defaults. Future: source from a config.obs model (out of scope for this thin-wiring plan).
_DEFAULT_OBS_HOST = "localhost"
_DEFAULT_OBS_PORT = 4455
_DEFAULT_OBS_PASSWORD: str | None = None

# The BoT-SORT override the tracker resolves to the repo trackers/ dir (detector.py).
_TRACKER_YAML = "botsort_dog.yaml"


def _channel_paths(channel_dir: str) -> dict[str, str]:
    """Build the opcomm channel-path bundle under ``channel_dir`` with the UI's constant names."""
    base = Path(channel_dir)
    return {
        "command": str(base / _COMMAND_FILE),
        "runstate": str(base / _RUNSTATE_FILE),
        "status": str(base / _STATUS_FILE),
        "score": str(base / _SCORE_FILE),
        "overlay": str(base / _OVERLAY_FILE),
    }


def _default_source_factory(cameras):
    """Real ``FrameSource`` builder — LAZY ``NdiFrameSource`` (cyndilib/cv2 stay inside the impl)."""
    from ..ndi.ndi_source import NdiFrameSource

    return NdiFrameSource(list(cameras))


def _default_obs_factory(host, port, password):
    """Real ``ObsController`` builder — LAZY ``ObsWsController`` (obsws imported inside connect())."""
    from ..obs.obsws_controller import ObsWsController

    return ObsWsController(host=host, port=port, password=password)


def _default_tracker_factory(
    model_path, class_index, tracker_yaml, engine_path=None, use_fp16=False
):
    """Real per-camera tracker builder — LAZY ``PerCameraTracker`` (ultralytics inside the ctor).

    Threads the 06-03 latency keys: ``engine_path`` (the cached TensorRT ``.engine`` — loaded
    with a graceful eager fallback inside the ctor, RBT-04) and ``use_fp16`` (the eager FP16
    toggle). Both default to today's eager-FP32 ``.pt`` behavior.
    """
    from ..tracking.detector import PerCameraTracker

    return PerCameraTracker(
        model_path,
        class_index,
        tracker_yaml,
        use_fp16=use_fp16,
        engine_path=engine_path,
    )


def build_orchestrator(
    config: "Config",
    channel_dir: str,
    *,
    fps: float = 30.0,
    grace: float | None = None,
    source_factory: Callable | None = None,
    obs_factory: Callable | None = None,
    tracker_factory: Callable | None = None,
) -> Orchestrator:
    """Compose a runnable :class:`Orchestrator` from a validated ``Config`` (the missing glue).

    Maps ``config.cameras`` onto ONE real ``NdiFrameSource`` + ONE ``ObsWsController`` + ONE
    ``PerCameraTracker`` per camera + the opcomm ``channel_paths`` (built from ``channel_dir``),
    then returns ``Orchestrator.from_config(...)``. The three ``*_factory`` params default to the
    real LAZY builders and are INJECTABLE so a headless test passes fakes (no
    cyndilib/obsws/cv2/ultralytics).

    Args:
        config: the validated ``Config`` (cameras / model / thresholds / framing / action_hold).
        channel_dir: the directory holding the operator↔system opcomm files (same dir the UI
            console writes to). The constant filenames are appended here.
        fps: the nominal tick Hz passed to ``Orchestrator.from_config`` (the scorer/engine derive
            their tick budgets from it).
        grace: the anti-jitter watchdog grace; ``None`` lets ``from_config`` source the non-zero
            ``config.thresholds.watchdog_grace`` seed (WR-02). An explicit value still wins.
        source_factory: ``(cameras) -> FrameSource``; defaults to the real lazy ``NdiFrameSource``.
        obs_factory: ``(host, port, password) -> ObsController``; defaults to ``ObsWsController``.
        tracker_factory: ``(model_path, class_index, tracker_yaml, *, engine_path, use_fp16)
            -> tracker``; defaults to the real lazy ``PerCameraTracker`` (which loads the
            ``engine_path`` engine with a graceful eager fallback — RBT-04). Built ONCE per
            camera.

    Returns:
        A runnable ``Orchestrator`` ready for ``.run(rate_hz)`` (or ``.run_measured(n)`` headless).
    """
    source_factory = source_factory or _default_source_factory
    obs_factory = obs_factory or _default_obs_factory
    tracker_factory = tracker_factory or _default_tracker_factory

    # Create the opcomm channel dir up front — IDENTICAL to ui/app.py:create_app's
    # os.makedirs (the UI's own dir-creation). The orchestrator must NOT depend on the
    # console having started first: on a clean rig launch the default ./opcomm does not
    # exist, and the atomic writer writes its temp file INSIDE this dir before os.replace,
    # so a missing dir makes every D-11 write_status raise FileNotFoundError. That error is
    # swallowed by the tick's RBT-04 try/except — the loop never crashes but status.json is
    # never written, silently killing the operator panel's reverse channel this plan wires.
    os.makedirs(channel_dir, exist_ok=True)

    channel_paths = _channel_paths(channel_dir)

    # ONE source over EVERY camera (NdiFrameSource keys threads by Camera.id for cameras carrying
    # an ndi_source — never a frame list to one tracker, #13107 is handled per-camera below).
    source = source_factory(list(config.cameras))

    # ONE ObsController with the hardcoded OBS defaults (Config has no obs block).
    obs = obs_factory(_DEFAULT_OBS_HOST, _DEFAULT_OBS_PORT, _DEFAULT_OBS_PASSWORD)

    # ONE PerCameraTracker per camera, seeded with config.model.path + class_index (resolved BY
    # NAME at first inference inside the loop — never hardcode 16, CFG-04).
    trackers = {
        cam.id: tracker_factory(
            config.model.path,
            config.model.class_index,
            _TRACKER_YAML,
            engine_path=config.model.engine_path,
            use_fp16=config.model.use_fp16,
        )
        for cam in config.cameras
    }

    return Orchestrator.from_config(
        config=config,
        source=source,
        obs=obs,
        channel_paths=channel_paths,
        trackers=trackers,
        fps=fps,
        grace=grace,
    )
