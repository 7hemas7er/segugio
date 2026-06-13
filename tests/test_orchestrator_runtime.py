"""05-09 — the runtime compose/factory + the `python -m segugio` entry point (the UAT gap).

Phase 05 verified the orchestrator loop LOGIC headlessly (5/5) but shipped NO runnable entry
point: ``Orchestrator.from_config(config, source, obs, channel_paths, trackers, ...)`` deliberately
requires the real ``source``/``obs``/``trackers``/``channel_paths`` to be built and injected by a
caller that did not exist. This module is the headless regression for the missing glue:

  * ``build_orchestrator(config, channel_dir, *, source_factory, obs_factory, tracker_factory)``
    composes one real ``NdiFrameSource`` + one ``ObsWsController`` + one ``PerCameraTracker`` per
    camera + the opcomm ``channel_paths`` and returns ``Orchestrator.from_config(...)``. The three
    ``*_factory`` params default to the real LAZY builders so this test injects fakes (no
    cyndilib/obsws/cv2/ultralytics) — proving the composition headless.
  * ``segugio.__main__.main`` loads the config, builds via the factory, and runs; Ctrl-C coasts
    OBS to SAFE (RBT-04); ``--rate``/``--opcomm-dir`` flow through.

Runs HEADLESS (``pytest -m "not gpu and not ndi and not obs"``): the heavy stack is genuinely
ABSENT in this repo, so the lazy-import boundary tests (Test 5 / Test 9) are real, not mocked.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from segugio.config.loader import load_config
from segugio.orchestrator.loop import Orchestrator

_REPO_ROOT = Path(__file__).resolve().parents[1]
DISC_EXAMPLE = _REPO_ROOT / "config.example.yaml"


# --------------------------------------------------------------------------- #
# Fakes — the injectable construction seam (no cyndilib/obsws/cv2/ultralytics).
# --------------------------------------------------------------------------- #


class _FakeSource:
    """A FrameSource stand-in recording the cameras it was built over."""

    def __init__(self, cameras) -> None:
        self.cameras = list(cameras)

    def start(self) -> None:  # pragma: no cover - lifecycle no-op
        pass

    def latest(self, cam_id):  # pragma: no cover - coast
        return None

    def last_frame_ts(self, cam_id):  # pragma: no cover - coast
        return None

    def stop(self) -> None:  # pragma: no cover - lifecycle no-op
        pass


class _FakeObs:
    """An ObsController stand-in recording the (host, port, password) it was built with."""

    def __init__(self, host, port, password) -> None:
        self.host = host
        self.port = port
        self.password = password

    def connect(self) -> None:  # pragma: no cover - lifecycle no-op
        pass

    def cut(self, scene_name) -> None:  # pragma: no cover - coast
        pass

    def set_overlay_text(self, input_name, text) -> None:  # pragma: no cover
        pass

    def close(self) -> None:  # pragma: no cover - lifecycle no-op
        pass


class _FakeTracker:
    """A per-camera tracker stand-in recording its construction args."""

    def __init__(
        self, model_path, class_index, tracker_yaml, engine_path=None, use_fp16=False
    ) -> None:
        self.model_path = model_path
        self.class_index = class_index
        self.tracker_yaml = tracker_yaml
        self.engine_path = engine_path
        self.use_fp16 = use_fp16

    def track(self, frame):  # pragma: no cover - coast
        return None


def _build(channel_dir, records=None, **overrides):
    """build_orchestrator from the disc example with the fakes injected; records call args."""
    from segugio.orchestrator.runtime import build_orchestrator

    config = load_config(DISC_EXAMPLE)
    records = records if records is not None else {}

    def source_factory(cameras):
        src = _FakeSource(cameras)
        records.setdefault("source", []).append(src)
        return src

    def obs_factory(host, port, password):
        obs = _FakeObs(host, port, password)
        records.setdefault("obs", []).append(obs)
        return obs

    def tracker_factory(
        model_path, class_index, tracker_yaml, engine_path=None, use_fp16=False
    ):
        trk = _FakeTracker(
            model_path, class_index, tracker_yaml, engine_path=engine_path, use_fp16=use_fp16
        )
        records.setdefault("tracker", []).append(trk)
        return trk

    kwargs = dict(
        source_factory=source_factory,
        obs_factory=obs_factory,
        tracker_factory=tracker_factory,
    )
    kwargs.update(overrides)
    orch = build_orchestrator(config, str(channel_dir), **kwargs)
    return config, orch, records


# --------------------------------------------------------------------------- #
# Task 1 — build_orchestrator composition.
# --------------------------------------------------------------------------- #


def test_compose_from_example_one_tracker_per_camera(tmp_path) -> None:
    """Test 1: returns an Orchestrator with exactly one tracker per config camera."""
    config, orch, _ = _build(tmp_path)
    assert isinstance(orch, Orchestrator)
    expected_ids = [c.id for c in config.cameras]
    assert list(orch.trackers.keys()) == expected_ids
    assert [c.id for c in orch.cameras] == expected_ids


def test_channel_paths_point_at_constant_filenames(tmp_path) -> None:
    """Test 2: the orchestrator reads command/runstate/status from channel_dir/<const file>."""
    _, orch, _ = _build(tmp_path)
    assert orch._cmd_path == str(tmp_path / "command.json")
    assert orch._runstate_path == str(tmp_path / "runstate.json")
    assert orch._status_path == str(tmp_path / "status.json")


def test_obs_factory_called_with_obs_defaults(tmp_path) -> None:
    """Test 3: obs_factory gets the hardcoded OBS defaults (localhost/4455/None)."""
    _, _, records = _build(tmp_path)
    obs = records["obs"][0]
    assert obs.host == "localhost"
    assert obs.port == 4455
    assert obs.password is None


def test_source_factory_called_with_all_cameras(tmp_path) -> None:
    """Test 4: source_factory gets the FULL config.cameras list (one source over every cam)."""
    config, _, records = _build(tmp_path)
    src = records["source"][0]
    assert [c.id for c in src.cameras] == [c.id for c in config.cameras]


def test_tracker_factory_seeded_with_config_model(tmp_path) -> None:
    """Test 4b: each tracker is seeded with config.model.path/class_index (never hardcoded 16)."""
    config, _, records = _build(tmp_path)
    assert len(records["tracker"]) == len(config.cameras)
    for trk in records["tracker"]:
        assert trk.model_path == config.model.path
        assert trk.class_index == config.model.class_index
        # bare tracker name — PerCameraTracker resolves it to the repo trackers/ dir.
        assert Path(str(trk.tracker_yaml)).name == "botsort_dog.yaml"


def test_build_creates_missing_channel_dir(tmp_path) -> None:
    """Test 4c (CR-01 regression): build_orchestrator creates a channel_dir that does not exist.

    On a clean rig launch the default ./opcomm does NOT exist and the orchestrator may start
    before/without the console (which is the only other code that creates it). The atomic writer
    writes its temp file INSIDE channel_dir before os.replace, so a missing dir makes every D-11
    write_status raise FileNotFoundError — swallowed by the tick's RBT-04 guard, so the loop
    survives but status.json is never written and the operator panel's reverse channel goes dead.
    The other tests pass an already-existing tmp_path, which hides this; this one does not.
    """
    missing = tmp_path / "does-not-exist" / "opcomm"
    assert not missing.exists()

    _, orch, _ = _build(missing)

    assert missing.is_dir()  # build created the full path
    # And the D-11 status write now actually lands (no swallowed FileNotFoundError):
    # _to_safe writes status.json, and with the dir present the atomic write succeeds.
    orch._to_safe("startup")
    assert (missing / "status.json").is_file()


def test_runtime_imports_with_heavy_stack_absent(monkeypatch) -> None:
    """Test 5: import segugio.orchestrator.runtime succeeds with the heavy stack ABSENT."""
    for name in ("torch", "ultralytics", "cyndilib", "obsws_python", "cv2"):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delitem(sys.modules, "segugio.orchestrator.runtime", raising=False)
    mod = importlib.import_module("segugio.orchestrator.runtime")
    assert mod is not None
    assert hasattr(mod, "build_orchestrator")


# --------------------------------------------------------------------------- #
# Task 2 — the `python -m segugio` entry point (main() wiring).
# --------------------------------------------------------------------------- #


class _FakeOrchestrator:
    """Records run/shutdown; ``run_raises`` lets a test simulate the operator's Ctrl-C."""

    def __init__(self, run_raises: BaseException | None = None) -> None:
        self.run_calls: list[float] = []
        self.shutdown_calls = 0
        self._run_raises = run_raises

    def run(self, rate_hz: float) -> None:
        self.run_calls.append(rate_hz)
        if self._run_raises is not None:
            raise self._run_raises

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _patch_main(monkeypatch, fake_orch, recorder):
    """Patch segugio.__main__.build_orchestrator to record (config, channel_dir) and return fake."""
    import segugio.__main__ as main_mod

    def fake_build(config, channel_dir, **kwargs):
        recorder["config"] = config
        recorder["channel_dir"] = channel_dir
        recorder["kwargs"] = kwargs
        return fake_orch

    monkeypatch.setattr(main_mod, "build_orchestrator", fake_build)
    return main_mod


def test_main_wires_config_factory_run(monkeypatch, tmp_path) -> None:
    """Test 6: main([config]) -> load_config -> build_orchestrator -> run(rate) once."""
    fake = _FakeOrchestrator()
    rec: dict = {}
    main_mod = _patch_main(monkeypatch, fake, rec)
    rc = main_mod.main([str(DISC_EXAMPLE), "--opcomm-dir", str(tmp_path)])
    assert rc == 0
    # load_config produced a Config and the factory got the resolved channel_dir.
    assert rec["config"].cameras  # a real validated Config flowed through
    assert rec["channel_dir"] == str(tmp_path)
    assert fake.run_calls == [30.0]  # default rate
    assert fake.shutdown_calls == 0  # clean run does not double-shutdown in main


def test_main_keyboardinterrupt_calls_shutdown(monkeypatch, tmp_path) -> None:
    """Test 7: run() raising KeyboardInterrupt -> main calls shutdown() once, returns 0."""
    fake = _FakeOrchestrator(run_raises=KeyboardInterrupt())
    rec: dict = {}
    main_mod = _patch_main(monkeypatch, fake, rec)
    rc = main_mod.main([str(DISC_EXAMPLE), "--opcomm-dir", str(tmp_path)])
    assert rc == 0  # Ctrl-C is a clean operator stop, NOT a crash
    assert fake.shutdown_calls == 1  # SAFE coast on Ctrl-C (RBT-04)


def test_main_rate_and_opcomm_dir_flow_through(monkeypatch, tmp_path) -> None:
    """Test 8: --rate 25 -> run(25.0); --opcomm-dir -> build_orchestrator channel_dir."""
    fake = _FakeOrchestrator()
    rec: dict = {}
    main_mod = _patch_main(monkeypatch, fake, rec)
    rc = main_mod.main(
        [str(DISC_EXAMPLE), "--rate", "25", "--opcomm-dir", str(tmp_path)]
    )
    assert rc == 0
    assert fake.run_calls == [25.0]
    assert rec["channel_dir"] == str(tmp_path)


def test_main_module_imports_with_heavy_stack_absent(monkeypatch) -> None:
    """Test 9: import segugio.__main__ succeeds with the heavy stack ABSENT (lazy boundary)."""
    for name in ("torch", "ultralytics", "cyndilib", "obsws_python", "cv2"):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delitem(sys.modules, "segugio.__main__", raising=False)
    mod = importlib.import_module("segugio.__main__")
    assert mod is not None
    assert hasattr(mod, "main")


def test_main_missing_heavy_dep_exits_2_with_actionable_message(
    monkeypatch, tmp_path, capsys
) -> None:
    """Test 10 (UAT-1 / WR-01 regression): a missing HEAVY dep at launch exits 2 with an
    actionable `pip install -e ".[heavy]"` message — NOT a raw ModuleNotFoundError traceback.

    UAT Test 1 hit this for real: docs/run.md said `pip install -e .` (base deps only), so
    build_orchestrator's eager PerCameraTracker construction raised
    `ModuleNotFoundError: No module named 'ultralytics'` and `python -m segugio` died with a
    traceback. The entry point now catches a heavy-stack import failure and degrades to one line.
    """
    import segugio.__main__ as main_mod

    def boom(config, channel_dir, **kwargs):
        # Exactly what PerCameraTracker.__init__ -> `from ultralytics import YOLO` raises.
        raise ModuleNotFoundError("No module named 'ultralytics'", name="ultralytics")

    monkeypatch.setattr(main_mod, "build_orchestrator", boom)
    rc = main_mod.main([str(DISC_EXAMPLE), "--opcomm-dir", str(tmp_path)])
    assert rc == 2  # actionable exit, not an uncaught crash
    err = capsys.readouterr().err
    assert "ultralytics" in err  # names the offending module
    assert '.[heavy]' in err  # tells the operator the exact fix


def test_main_non_heavy_module_error_is_not_masked(monkeypatch, tmp_path) -> None:
    """Test 11: a genuine missing INTERNAL module is a real bug — it must propagate, never be
    masked behind the heavy-stack install hint (which would hide the actual defect)."""
    import segugio.__main__ as main_mod

    def boom(config, channel_dir, **kwargs):
        raise ModuleNotFoundError(
            "No module named 'segugio.does_not_exist'", name="segugio.does_not_exist"
        )

    monkeypatch.setattr(main_mod, "build_orchestrator", boom)
    with pytest.raises(ModuleNotFoundError):
        main_mod.main([str(DISC_EXAMPLE), "--opcomm-dir", str(tmp_path)])


# --------------------------------------------------------------------------- #
# 07-04 Task 2 — the preview channel wired into the REAL run path (D-09 / SC3).
# --------------------------------------------------------------------------- #


class _Frame:
    """A non-empty frame stand-in (``.size > 0`` so the clip source's NDI-03 guard publishes it).

    The injected ``encode_fn`` accepts this object directly — no real cv2/numpy is touched, so the
    preview-files-written smoke runs fully headless.
    """

    size = 1

    def __init__(self, cam_id: str) -> None:
        self.cam_id = cam_id


_FAKE_JPEG = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"  # deterministic fake JPEG bytes (header+trailer)


def _drive_until_preview_written(orch, preview_json, n_ticks=4, timeout_s=5.0):
    """Run a few ticks, then wait for the async publisher daemon to land preview.json.

    The publisher does its resize/encode/IO on its OWN daemon thread (off the tick), so the files
    appear slightly AFTER ``run_measured`` returns. Drive the ticks (offering frames into the
    mailbox), then poll for the sidecar up to ``timeout_s`` before asserting. ``shutdown`` joins
    the daemon so any final drain completes.
    """
    import time as _time

    orch.run_measured(n_ticks=n_ticks)
    deadline = _time.monotonic() + timeout_s
    while _time.monotonic() < deadline:
        if Path(preview_json).is_file():
            break
        _time.sleep(0.02)
    orch.shutdown()  # joins the daemon — any in-flight publish completes


def test_preview_files_written_on_real_run(tmp_path) -> None:
    """SC3 / D-09: a headless run with an injected encoder writes cam_<id>.jpg + preview.json.

    Builds a frame-emitting clip source + a REAL ``PreviewPublisher`` (constructed by an injected
    ``preview_factory`` with a fake ``encode_fn`` returning deterministic JPEG bytes), drives a
    couple of ticks via ``run_measured``, then asserts the per-camera JPEGs carry the fake bytes
    AND ``read_preview`` round-trips a ``PreviewDoc`` with the expected cams. This is the D-09
    'done' line: a REAL run path constructs/starts/stops the publisher and writes the channel.
    """
    from segugio.ndi.clip_source import ClipReplayFrameSource
    from segugio.opcomm.channel import read_preview
    from segugio.orchestrator.preview import PreviewPublisher
    from segugio.orchestrator.runtime import build_orchestrator

    config = load_config(DISC_EXAMPLE)
    cam_ids = [c.id for c in config.cameras]

    def source_factory(cameras):
        def _iter():
            for tick in range(50):
                yield (tick, {c.id: _Frame(c.id) for c in cameras})

        return ClipReplayFrameSource(frames_iter=_iter())

    built: dict = {}

    def preview_factory(preview_params, preview_dir, cameras):
        pub = PreviewPublisher(
            preview_params,
            preview_dir,
            [c.id for c in cameras],
            encode_fn=lambda frame: _FAKE_JPEG,  # no cv2 — deterministic bytes
        )
        built["publisher"] = pub
        built["preview_dir"] = preview_dir
        return pub

    orch = build_orchestrator(
        config,
        str(tmp_path),
        source_factory=source_factory,
        obs_factory=lambda host, port, password: _FakeObs(host, port, password),
        tracker_factory=lambda *a, **k: _FakeTracker(*a, **k),
        preview_factory=preview_factory,
    )

    # The publisher was constructed (preview enabled by default) and injected into the loop.
    assert orch._preview is built["publisher"]

    preview_dir = Path(built["preview_dir"])
    preview_json = preview_dir / "preview.json"
    _drive_until_preview_written(orch, preview_json)

    # Per-camera JPEGs landed with the injected fake bytes (real atomic_write_bytes path).
    for cam_id in cam_ids:
        jpg = preview_dir / f"cam_{cam_id}.jpg"
        assert jpg.is_file(), f"missing preview JPEG for {cam_id}"
        assert jpg.read_bytes() == _FAKE_JPEG

    # The sidecar round-trips through the safe-default boundary with the expected cams.
    assert preview_json.is_file()
    doc = read_preview(str(preview_json))
    assert set(doc.cams.keys()) == set(cam_ids)
    assert doc.gen >= 1  # the in-sidecar cache-bust token advanced at least once


def test_preview_disabled_constructs_no_publisher(tmp_path) -> None:
    """D-06: with config.preview.enabled=False the orchestrator's _preview is None (v1.0-identical).

    No ``PreviewPublisher`` is constructed and the injected ``preview_factory`` is NEVER called —
    the wiring is guarded by ``config.preview.enabled`` so a disabled preview is byte-identical to
    v1.0 (no publisher, no offer(), no daemon).
    """
    from segugio.orchestrator.runtime import build_orchestrator

    config = load_config(DISC_EXAMPLE)
    # Disable preview on the validated config (model_copy keeps it pydantic-valid + frozen-safe).
    disabled = config.model_copy(
        update={"preview": config.preview.model_copy(update={"enabled": False})}
    )

    factory_called = {"n": 0}

    def preview_factory(*args, **kwargs):  # pragma: no cover - must NOT be called
        factory_called["n"] += 1
        raise AssertionError("preview_factory must not be called when preview is disabled")

    orch = build_orchestrator(
        disabled,
        str(tmp_path),
        source_factory=lambda cameras: _FakeSource(cameras),
        obs_factory=lambda host, port, password: _FakeObs(host, port, password),
        tracker_factory=lambda *a, **k: _FakeTracker(*a, **k),
        preview_factory=preview_factory,
    )

    assert orch._preview is None
    assert factory_called["n"] == 0
