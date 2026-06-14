"""Shared pytest fixtures for the whole Phase-1 suite.

These are the load-bearing seams that plans 01-02 / 01-03 / 01-04 build their tests
on. Keep the names and shapes stable:

  seeded_rng        -> numpy.random.Generator   (deterministic, fixed module SEED)
  tmp_config        -> Callable[[str], Path]     (writes a YAML string, returns Path)
  valid_config_dict -> dict                      (canonical happy-path disc_dog config)

The generators are deterministic (TST-02): a fixed seed yields byte-identical draws,
so any test built on ``seeded_rng`` is reproducible across runs and parallel workers.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Callable

import numpy as np
import pytest

# Fixed module-level seed — the determinism baseline every TST-02 consumer inherits.
SEED = 1234

# Injected frames-per-second — the seconds→ticks bridge the Phase-3 DecisionEngine and
# ticks_from_seconds use (RESEARCH A2: fps is injected as an argument, NEVER a config field).
FPS = 30.0


def pytest_collection_modifyitems(config, items) -> None:
    """SKIP each hardware-gated item (``gpu``/``ndi``/``obs``) when its stack is unmet.

    The gate LOGIC lives in ``tests/conftest_tracking`` (isolated + import-guarded so
    collection never imports torch/cyndilib/obsws on a headless box). pytest only auto-loads
    files literally named ``conftest.py`` as plugins, so the session hook itself must live
    here. Imported in-body so this conftest stays heavy-import-free at module load. Touches
    ONLY the marked items — the pure CPU suite is untouched.

      - ``gpu`` → ``gpu_available`` (CUDA + ultralytics/torch + weights, D-09)
      - ``ndi`` → ``ndi_available`` (cyndilib + cv2; real-NDI E2E path, D-05/NDI-01/02)
      - ``obs`` → ``obs_available`` (obsws-python; real-OBS E2E path, D-06/OBS-01..05)
    """
    from tests.conftest_tracking import gpu_available, ndi_available, obs_available

    gates = {
        "gpu": (gpu_available, "gpu eval skipped: {reason} (D-09)"),
        "ndi": (ndi_available, "ndi E2E skipped: {reason} (D-05)"),
        "obs": (obs_available, "obs E2E skipped: {reason} (D-06)"),
    }
    for marker, (probe, template) in gates.items():
        ok, reason = probe()
        if ok:
            continue  # the stack is present — let the marked tests run
        skip = pytest.mark.skip(reason=template.format(reason=reason))
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def seeded_rng() -> np.random.Generator:
    """A fresh, deterministically-seeded ``numpy.random.Generator``.

    Two generators built from the same SEED produce identical first draws; this is
    the determinism contract downstream score-stream / feed-death tests rely on.
    """
    return np.random.default_rng(SEED)


@pytest.fixture
def tmp_config(tmp_path: Path) -> Callable[[str], Path]:
    """Factory: write a YAML string into pytest's tmp_path and return its Path.

    Usage::

        path = tmp_config("a: 1\\nb: 2\\n")
        cfg = yaml.safe_load(path.read_text())
    """
    counter = {"n": 0}

    def _write(yaml_str: str, name: str | None = None) -> Path:
        if name is None:
            counter["n"] += 1
            name = f"config_{counter['n']}.yaml"
        path = tmp_path / name
        path.write_text(yaml_str, encoding="utf-8")
        return path

    return _write


# Canonical happy-path config dict (disc_dog). Plan 01-02 reuses this as the
# minimal well-formed config its valid-config tests parse. Structure follows the
# schema in RESEARCH.md: field discriminated-union, cameras[] with normalized
# [0..1] zone rects, a framing_weights[role][zone] matrix covering every
# referenced zone, a thresholds block, and a model block.
_VALID_CONFIG: dict = {
    "field": {
        "sport": "disc_dog",
        "event": "distance_accuracy",
    },
    "cameras": [
        {
            "id": "cam_wide",
            "role": "main_wide",
            "obs_scene": "WIDE",
            "is_safe": True,  # SAFE fallback camera (required by the cross-validator)
            "zones": [
                {"name": "near", "rect": [0.0, 0.0, 1.0, 0.34]},
                {"name": "mid", "rect": [0.0, 0.34, 1.0, 0.67]},
                {"name": "far", "rect": [0.0, 0.67, 1.0, 1.0]},
            ],
        },
        {
            "id": "cam_long",
            "role": "long",
            "obs_scene": "LONG",
            "is_safe": False,
            "zones": [
                {"name": "mid", "rect": [0.2, 0.3, 0.8, 0.6]},
                {"name": "far", "rect": [0.2, 0.6, 0.8, 0.95]},
            ],
        },
    ],
    # role -> {zone_name: multiplier}. Covers every zone referenced above.
    "framing_weights": {
        "main_wide": {"near": 1.2, "mid": 1.0, "far": 0.8},
        "long": {"mid": 1.1, "far": 1.6},
    },
    "thresholds": {
        "alpha": 0.3,
        "hysteresis_margin": 0.1,
        "min_dwell": 2.0,
        "debounce_N": 3,
        "cooldown": 1.0,
        "watchdog_timeout": 0.8,
        "track_buffer": 60,
    },
    "model": {
        "path": "yolo26s.pt",
        "class_index": 16,
    },
}


@pytest.fixture
def valid_config_dict() -> dict:
    """A minimal well-formed disc_dog config dict (deep-copied so tests can mutate)."""
    return copy.deepcopy(_VALID_CONFIG)


@pytest.fixture
def scorer_params():
    """Seeded ``ScorerParams`` defaults the FRM tests score against (incl. ``eps``).

    Imported inside the fixture body to keep this conftest light; ``ScorerParams()``
    validates all seeds (and the w_c+w_s+w_conf==1 invariant) at construction.
    """
    from segugio.config import ScorerParams

    return ScorerParams()


@pytest.fixture
def tracking_params():
    """Seeded ``TrackingParams`` defaults the Phase-4 tracking tests use (TRK-04/05 seeds).

    Mirrors ``scorer_params``: imported in-body to keep this conftest heavy-import-free;
    ``TrackingParams()`` validates every bounded seed at construction.
    """
    from segugio.tracking.params import TrackingParams

    return TrackingParams()


@pytest.fixture
def crop_geometry():
    """Overlapping L/C/R normalized crop rects (D-01 multi-camera framing geometry).

    ``[x0, y0, x1, y1]`` in [0,1] per camera, with the L/C/R windows OVERLAPPING (cam_l and
    cam_c share [0.225, 0.55]; cam_c and cam_r share [0.45, 0.775]) — the geometry the 04-03
    ``frame_source`` (crop extraction) and the eval consume. Static data, no import needed.
    """
    return {
        "cam_l": [0.0, 0.0, 0.55, 1.0],
        "cam_c": [0.225, 0.0, 0.775, 1.0],
        "cam_r": [0.45, 0.0, 1.0, 1.0],
    }


@pytest.fixture
def thresholds():
    """Validated ``Thresholds`` the Phase-3 FSM reads (mirrors ``scorer_params``).

    Built from the canonical happy-path config (``hysteresis_margin: 0.1, min_dwell: 2.0,
    debounce_N: 3, cooldown: 1.0``). Imported in-body to keep this conftest heavy-import-free.
    """
    from segugio.config import Config

    return Config.model_validate(_VALID_CONFIG).thresholds


# --------------------------------------------------------------------------- #
# Phase-5 integration fixtures (ADDITIVE — the Phase-1 fixtures above are the
# stable seams 01-02/03/04 + Phase 2/3/4 build on; do NOT rename/reshape them).
#
# These are the shared seams the Phase-5 Wave-0 stubs + the four Wave-2 plans
# (NDI mock, orchestrator, OBS controller, score UI) assert against:
#
#   make_config        -> Callable[..., Config]  (minimal validated 4-camera Config)
#   fake_frame_source  -> object implementing start/latest/last_frame_ts/stop
#   recording_obs      -> a call-capturing ObsController stand-in (RecordingObsController-shaped)
#   injected_clock     -> Callable[[], float]    (a monotonic float advanced on demand)
#   file_channel       -> a tmp_path-backed bundle of score/runstate/command/status paths
#
# All are heavy-import-free at module load (imports happen in-body), preserving
# the lazy-import boundary (import segugio.* succeeds with cyndilib/obsws/cv2/Flask absent).
# --------------------------------------------------------------------------- #

# A minimal 4-camera config dict (one is_safe) — the Phase-5 wiring needs >1 camera
# and an explicit SAFE fallback. Built on the Phase-1 schema (FieldProfile + cameras
# + framing_weights + thresholds + model); reuses the same zone/weight shape.
_PHASE5_CONFIG: dict = {
    "field": {"sport": "disc_dog", "event": "distance_accuracy"},
    "cameras": [
        {
            "id": "cam_wide",
            "role": "main_wide",
            "obs_scene": "CAM Wide",
            "is_safe": True,
            "ndi_source": "PHONE-WIDE (NDI)",
            "zones": [{"name": "field", "rect": [0.0, 0.0, 1.0, 1.0]}],
        },
        {
            "id": "cam_long",
            "role": "long",
            "obs_scene": "CAM Long",
            "is_safe": False,
            "ndi_source": "PHONE-LONG (NDI)",
            "zones": [{"name": "field", "rect": [0.0, 0.0, 1.0, 1.0]}],
        },
        {
            "id": "cam_low",
            "role": "low",
            "obs_scene": "CAM Low",
            "is_safe": False,
            "ndi_source": "PHONE-LOW (NDI)",
            "zones": [{"name": "field", "rect": [0.0, 0.0, 1.0, 1.0]}],
        },
        {
            "id": "cam_handler",
            "role": "handler_side",
            "obs_scene": "CAM Handler",
            "is_safe": False,
            "ndi_source": "PHONE-HANDLER (NDI)",
            "zones": [{"name": "field", "rect": [0.0, 0.0, 1.0, 1.0]}],
        },
    ],
    "framing_weights": {
        "main_wide": {"field": 1.0},
        "long": {"field": 1.0},
        "low": {"field": 1.0},
        "handler_side": {"field": 1.0},
    },
    "thresholds": {
        "alpha": 0.3,
        "hysteresis_margin": 0.1,
        "min_dwell": 2.0,
        "debounce_N": 3,
        "cooldown": 1.0,
        "watchdog_timeout": 0.8,
        "track_buffer": 60,
    },
    "model": {"path": "yolo26s.pt", "class_index": 16},
}


@pytest.fixture
def make_config() -> Callable[..., object]:
    """Factory returning a minimal validated 4-camera ``Config`` (one ``is_safe``).

    Usage::

        cfg = make_config()                       # the canonical 4-cam Phase-5 config
        cfg = make_config(overrides={"action_hold": {"motion_threshold": 0.05}})

    ``Config`` is imported in-body to keep this conftest heavy-import-free. The dict is
    deep-copied per call so a test mutating ``overrides`` never leaks into another test.

    Overrides are DEEP-merged (WR-03): a nested override like
    ``{"model": {"use_fp16": True}}`` updates only that sub-key and PRESERVES the sibling
    ``model`` keys, rather than a shallow top-level ``update`` that would replace the whole
    ``model`` block and silently reset un-restated sub-keys to their defaults.
    """
    from segugio.config import Config

    def _deep_merge(base: dict, over: dict) -> dict:
        """Recursively merge ``over`` into ``base`` (mutating ``base``), dict-into-dict only.

        A value that is a dict on BOTH sides recurses; any other value (scalar, list, or a
        type mismatch) REPLACES wholesale. Lists are intentionally not merged element-wise.
        """
        for key, value in over.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                _deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _build(overrides: dict | None = None) -> object:
        raw = copy.deepcopy(_PHASE5_CONFIG)
        if overrides:
            _deep_merge(raw, copy.deepcopy(overrides))
        return Config.model_validate(raw)

    return _build


class _FakeFrameSource:
    """Light stand-in for the ``FrameSource`` interface (start/latest/last_frame_ts/stop).

    No numpy, no cv2 — ``latest`` returns whatever object the test seeds via ``set``.
    Tracks start/stop calls and per-camera last-NEW-frame timestamps (RBT-01 substrate).
    The real cyndilib impl + the in-process clip mock land in Wave 2 (05-02).
    """

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self._frames: dict[str, object] = {}
        self._ts: dict[str, float] = {}

    def set(self, cam_id: str, frame: object, ts: float | None = None) -> None:
        self._frames[cam_id] = frame
        if ts is not None:
            self._ts[cam_id] = ts

    def start(self) -> None:
        self.started = True

    def latest(self, cam_id: str):
        return self._frames.get(cam_id)

    def last_frame_ts(self, cam_id: str):
        return self._ts.get(cam_id)

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def fake_frame_source() -> _FakeFrameSource:
    """A light ``FrameSource``-shaped fake (start/latest/last_frame_ts/stop)."""
    return _FakeFrameSource()


class _InlineRecordingObs:
    """Inline RecordingObsController stand-in until 05-03 lands the real fake.

    Captures every controller call as a tuple in ``self.calls`` so the camera-id→scene
    mapping and failure paths can be asserted headless (RESEARCH Pattern 2). Once 05-03
    lands ``segugio.obs.recording_fake.RecordingObsController`` the fixture prefers it.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect",))

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut", scene_name))

    def set_pip(self, scene, source, enabled, transform=None) -> None:
        self.calls.append(("pip", scene, source, enabled, transform))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        self.calls.append(("overlay", input_name, text))

    def close(self) -> None:
        self.calls.append(("close",))


@pytest.fixture
def recording_obs():
    """A call-capturing ObsController stand-in (RecordingObsController-shaped).

    Prefers the real ``segugio.obs.recording_fake.RecordingObsController`` once 05-03
    lands it; until then returns the inline stand-in so the Wave-0 stubs collect/run.
    """
    try:  # pragma: no cover - exercised once 05-03 lands the real fake
        from segugio.obs.recording_fake import RecordingObsController  # type: ignore

        return RecordingObsController()
    except Exception:
        return _InlineRecordingObs()


@pytest.fixture
def injected_clock() -> Callable[..., float]:
    """A controllable monotonic-float clock for watchdog tests (no wall-clock).

    Returns a callable: ``clock()`` reads the current value; ``clock(advance=dt)`` advances
    it by ``dt`` and returns the new value. Liveness math (RBT-01) is PURE on injected
    timestamps — the wall-clock lives only in the orchestrator, never in the watchdog.
    """
    state = {"t": 0.0}

    def _clock(advance: float | None = None) -> float:
        if advance is not None:
            state["t"] += advance
        return state["t"]

    return _clock


@pytest.fixture
def file_channel(tmp_path: Path) -> dict:
    """A tmp_path-backed bundle of the operator↔system file paths.

    Returns ``{"dir", "score", "runstate", "command", "status", "overlay", "overlay_run"}``
    Paths under pytest's ``tmp_path`` (same volume → ``os.replace`` is atomic). The
    atomic-file channel (05-01 Task 2) and the Flask UI (05-05) write/read these files.

    The ``overlay_run`` key (Phase 10) points at the NEW console-owned ``overlay_run.json``
    that stamps ``running``/``started_at``/``gen`` on the run start/stop edge — kept separate
    from ``runstate.json`` (the director reads runstate every tick; overlay_run is never read
    by the director).
    """
    d = tmp_path / "opcomm"
    d.mkdir()
    return {
        "dir": d,
        "score": d / "score.json",
        "runstate": d / "runstate.json",
        "command": d / "command.json",
        "status": d / "status.json",
        "overlay": d / "overlay.txt",
        "overlay_run": d / "overlay_run.json",
    }


@pytest.fixture
def preview_channel(file_channel: dict) -> dict:
    """Extend ``file_channel`` with the Phase-7 ``preview/`` sub-dir the console serves (Phase 8).

    Builds ``<dir>/preview/`` then writes:
      * ``cam_cam_wide.jpg`` + ``cam_cam_long.jpg`` — raw fake-JPEG bytes (NO cv2). The
        ``cam_<id>.jpg`` name encodes the LOAD-BEARING Pitfall-3 mapping: id ``cam_wide`` →
        on-disk file ``cam_cam_wide.jpg`` (the route builds the path from a FIXED ``cam_{id}.jpg``
        prefix, never from the raw URL segment — T-05-05-01).
      * ``preview/preview.json`` via :func:`write_preview` (gen/tick/auto_candidate/cams).

    Adds ``preview_dir`` (the ``preview/`` Path) and ``preview`` (the ``preview.json`` Path) keys
    to the returned dict. Imports are in-body so this conftest stays heavy-import-free (like
    :func:`_as_camera_scores`).
    """
    from segugio.opcomm.channel import write_preview
    from segugio.opcomm.records import PreviewDoc

    pdir = file_channel["dir"] / "preview"
    pdir.mkdir()
    (pdir / "cam_cam_wide.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    (pdir / "cam_cam_long.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpeglong")
    write_preview(
        str(pdir / "preview.json"),
        PreviewDoc(
            tick=1,
            gen=1,
            auto_candidate="cam_wide",
            cams={"cam_wide": {}, "cam_long": {}},
        ),
    )
    file_channel["preview_dir"] = pdir
    file_channel["preview"] = pdir / "preview.json"
    return file_channel


def _as_camera_scores(samples, status_default=None):
    """Wrap each ``ScoreSample`` (no status field) as a ``CameraScore`` (RESEARCH Pitfall 2).

    ``score_stream`` emits ``ScoreSample(tick, cam_id, score)`` with NO status; the FSM's
    public input contract is ``CameraScore`` (which carries a ``status``). This 3-line adapter
    lets the DEC-07 substrate reuse the shipped scenarios while the engine consumes the real
    production type. ``status_default`` defaults to ``ScorerStatus.tracking`` (advisory only
    in v1 — the FSM keys hysteresis/debounce on ``score``, RESEARCH A1). In-body lazy import
    keeps this conftest heavy-import-free.
    """
    from segugio.framing.signals import CameraScore, ScorerStatus

    if status_default is None:
        status_default = ScorerStatus.tracking
    return [
        CameraScore(s.tick, s.cam_id, s.score, status_default) for s in samples
    ]
