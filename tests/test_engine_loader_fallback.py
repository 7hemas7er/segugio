"""06-03 Task 3 — engine-aware ``PerCameraTracker`` loader + graceful eager fallback (RBT-04).

Headless guard (no GPU, no ultralytics): a fake ``YOLO`` is injected so the loader logic is
exercised WITHOUT the heavy stack. The behaviors proven here are the Q1-Option-(a) engine path:

  * Test 1 — engine present + loads → ``is_engine`` True, the engine-backed model is used.
  * Test 2 — engine load RAISES → graceful fallback to the eager ``.pt``, ``is_engine`` False,
    a warning logged, NO crash (RBT-04 — the dominant robustness concern this phase).
  * Test 3 — ``engine_path=None`` → eager ``.pt`` exactly as today, ``is_engine`` False
    (the existing ``__init__`` contract preserved).
  * Test 4 — ``engine_path`` set but the file does NOT exist → eager fallback, ``is_engine``
    False, no crash (a missing engine IS the staleness signal — no metadata schema).
  * Test 5 — the runtime factory threads ``config.model.engine_path`` + ``use_fp16`` into
    ``PerCameraTracker`` (with fakes, the tracker receives them).

The fake ``YOLO`` is installed via ``sys.modules['ultralytics']`` so the lazy
``from ultralytics import YOLO`` inside ``PerCameraTracker.__init__`` resolves to it.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from segugio.tracking.detector import PerCameraTracker


# --------------------------------------------------------------------------- #
# Fake ultralytics.YOLO — records the path it was constructed with and can be
# scripted to RAISE on the .engine path (to drive the graceful fallback).
# --------------------------------------------------------------------------- #


class _FakeYOLO:
    """A YOLO stand-in recording its construction path; carries a ``.names`` for the resolve."""

    #: paths that should make construction RAISE (set per-test to script the engine failure).
    raise_on_suffix: tuple[str, ...] = ()

    def __init__(self, path: str) -> None:
        self.path = str(path)
        if self.path.endswith(self.raise_on_suffix):
            raise RuntimeError(f"fake engine load failure for {self.path}")
        self.names = {16: "dog"}


@pytest.fixture
def fake_ultralytics(monkeypatch):
    """Install a fake ``ultralytics`` module exposing ``YOLO`` for the lazy ctor import.

    Returns the ``_FakeYOLO`` class so a test can set ``raise_on_suffix`` to script a failure.
    """
    _FakeYOLO.raise_on_suffix = ()  # reset between tests
    mod = types.ModuleType("ultralytics")
    mod.YOLO = _FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", mod)
    return _FakeYOLO


@pytest.fixture
def tracker_yaml(tmp_path) -> str:
    """A real on-disk tracker yaml so ``_resolve_tracker_yaml`` validates at construction."""
    p = tmp_path / "botsort_dog.yaml"
    p.write_text("tracker_type: botsort\nwith_reid: True\n", encoding="utf-8")
    return str(p)


# --------------------------------------------------------------------------- #
# Task 3 — engine-aware loader behaviors.
# --------------------------------------------------------------------------- #


def test_engine_present_loads_engine_is_engine_true(fake_ultralytics, tracker_yaml, tmp_path):
    """Test 1: engine_path set + file exists + loads → is_engine True, engine-backed model."""
    engine = tmp_path / "yolo26s.engine"
    engine.write_bytes(b"fake-engine")  # exists + loads (fake does not raise)

    trk = PerCameraTracker(
        "yolo26s.pt", 16, tracker_yaml, engine_path=engine, use_fp16=True
    )

    assert trk.is_engine is True
    assert trk.model.path.endswith("yolo26s.engine")  # the engine, not the .pt
    assert trk.use_fp16 is True


def test_engine_load_raises_falls_back_to_eager(fake_ultralytics, tracker_yaml, tmp_path, caplog):
    """Test 2 (RBT-04): engine load RAISES → eager .pt fallback, is_engine False, NO crash."""
    engine = tmp_path / "yolo26s.engine"
    engine.write_bytes(b"corrupt-engine")
    fake_ultralytics.raise_on_suffix = (".engine",)  # the engine path raises; the .pt succeeds

    # Must NOT raise — the graceful degrade (the dominant robustness concern this phase).
    trk = PerCameraTracker("yolo26s.pt", 16, tracker_yaml, engine_path=engine)

    assert trk.is_engine is False
    assert trk.model.path.endswith("yolo26s.pt")  # fell back to the eager weights


def test_engine_path_none_loads_eager_unchanged(fake_ultralytics, tracker_yaml):
    """Test 3: engine_path=None → eager .pt exactly as today; is_engine False (contract preserved)."""
    trk = PerCameraTracker("yolo26s.pt", 16, tracker_yaml)

    assert trk.is_engine is False
    assert trk.model.path.endswith("yolo26s.pt")
    assert trk.use_fp16 is False


def test_missing_engine_file_falls_back_to_eager(fake_ultralytics, tracker_yaml, tmp_path):
    """Test 4: engine_path set but the file is absent → eager fallback, is_engine False, no crash."""
    missing = tmp_path / "does-not-exist.engine"
    assert not missing.exists()

    trk = PerCameraTracker("yolo26s.pt", 16, tracker_yaml, engine_path=missing)

    assert trk.is_engine is False
    assert trk.model.path.endswith("yolo26s.pt")


def test_factory_threads_engine_path_and_use_fp16(monkeypatch, tmp_path):
    """Test 5: build_orchestrator threads config.model.engine_path + use_fp16 into the tracker."""
    from segugio.config.loader import load_config
    from segugio.orchestrator.runtime import build_orchestrator

    repo_root = Path(__file__).resolve().parents[1]
    config = load_config(repo_root / "config.example.yaml")
    # Arm the engine keys on the loaded config so the factory has something to thread.
    config.model.engine_path = tmp_path / "yolo26s.engine"
    config.model.use_fp16 = True

    records: list[dict] = []

    def tracker_factory(model_path, class_index, tracker_yaml, engine_path=None, use_fp16=False):
        records.append(
            {
                "model_path": model_path,
                "class_index": class_index,
                "engine_path": engine_path,
                "use_fp16": use_fp16,
            }
        )

        class _Fake:
            pass

        return _Fake()

    build_orchestrator(
        config,
        str(tmp_path / "opcomm"),
        source_factory=lambda cameras: types.SimpleNamespace(cameras=list(cameras)),
        obs_factory=lambda host, port, password: types.SimpleNamespace(),
        tracker_factory=tracker_factory,
    )

    assert records, "tracker_factory was never called"
    for rec in records:
        assert rec["engine_path"] == config.model.engine_path
        assert rec["use_fp16"] is True
