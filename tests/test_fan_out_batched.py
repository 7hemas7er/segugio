"""06-02 Task 2 — the batched ``_fan_out`` path: ONE forward per tick, N per-camera updates.

These headless tests drive ``Orchestrator._fan_out`` with fake per-camera trackers + a fake
shared model (no GPU, no ultralytics) and assert the Track-B dispatch shape AT THE LOOP LEVEL:

  * ONE batched detection forward per tick (``model.predict`` called exactly once), never a
    frame list to one ``model.track()`` (#13107) and never N serial ``tracker.track()`` calls.
  * Each of the 4 per-camera trackers updated EXACTLY once per tick with ONLY its own camera's
    detections (#13107 isolation at the loop level).
  * The returned per-camera ``DetectionSignal | None`` map is the SAME consumer shape
    ``MultiCamScorer.update`` expects (so the rest of the tick is byte-for-byte unchanged).
  * The HARD ``assert_native_reid_engaged`` runs ONCE after the first real-inference tick,
    threading ``is_engine`` (False for the eager FP16 path → HARD gate preserved), and does NOT
    falsely trip on a fake eager tracker.
  * A ``None`` frame for one camera coasts that camera to a ``None`` signal without crashing the
    tick (RBT-04); the dog-index-by-name resolve + locked-energy max still behave.
"""

from __future__ import annotations

from pathlib import Path


# --------------------------------------------------------------------------- #
# Fakes — a shared detection model + per-camera trackers exposing .update()/.model.
# --------------------------------------------------------------------------- #


class _Frame:
    """A non-empty BGR frame stand-in (``.size > 0`` so the live-frame guard treats it real)."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.size = 1


class _FakeBoxes:
    """A ``Results.boxes`` stand-in: no confirmed track → coast ([], None, [])."""

    id = None  # _arrays_from_results coasts to ([], None, []) on id is None


class _FakeResult:
    """One camera's slice of the batched forward; carries the cam tag so isolation is provable."""

    def __init__(self, cam_id: str) -> None:
        self.cam_id = cam_id
        self.boxes = _FakeBoxes()


class _NativeBot:
    """A BoT-SORT stand-in whose ``encoder`` is a bare lambda (the native-ReID path shape)."""

    encoder = staticmethod(lambda feats, s: list(feats))  # native lambda, NOT a ReID instance


class _FakePredictor:
    """A predictor stand-in satisfying ``assert_native_reid_engaged`` (native ReID engaged)."""

    def __init__(self) -> None:
        self.trackers = [_NativeBot()]
        self._hook = object()  # native path registers a forward-pre-hook (non-None)


class _SharedModel:
    """The ONE shared detection model: records the single batched predict + exposes .names.

    Carries a ``predictor`` shaped so the HARD native-ReID gate PASSES (encoder is the native
    lambda, hook registered) — so the loop's once-before-loop gate runs without falsely tripping.
    """

    def __init__(self, cam_ids: list[str]) -> None:
        self._cam_ids = cam_ids
        self.predict_calls: list[dict] = []
        self.track_calls: int = 0
        # {idx: name} so resolve_dog_index finds dog=16 by NAME (never hardcoded).
        self.names = {0: "person", 16: "dog"}
        self.predictor = _FakePredictor()

    def predict(self, frames, **kwargs):
        self.predict_calls.append({"n_frames": len(frames), "kwargs": kwargs})
        return [_FakeResult(cid) for cid in self._cam_ids]

    def track(self, *a, **k):  # the batched path must NOT call model.track([frames]) (#13107)
        self.track_calls += 1
        return []


class _FakeTracker:
    """A per-camera tracker: shares the ONE model, records its own .update() dispatches.

    Exposes ``.model`` (for the dog-index resolve + ReID gate guard), ``is_engine=False``
    (eager FP16 → HARD ReID gate), and ``.update(detections, frame)`` (the batched dispatch).
    """

    def __init__(self, cam_id: str, model: _SharedModel) -> None:
        self.cam_id = cam_id
        self.model = model
        self.is_engine = False
        self.dog_idx = 16
        self.update_calls: list = []

    def update(self, detections, frame):
        self.update_calls.append(detections)
        return detections  # a Results stand-in (boxes.id is None → the loop coasts cleanly)


def _orch(cfg, trackers, source):
    """Build an Orchestrator with the given per-camera trackers + frame source (headless)."""
    from segugio.orchestrator.loop import Orchestrator

    class _OkObs:
        def connect(self):
            pass

        def cut(self, scene):
            pass

        def set_overlay_text(self, n, t):
            pass

        def close(self):
            pass

    import tempfile

    d = Path(tempfile.mkdtemp())
    channel_paths = {
        "command": d / "command.json",
        "runstate": d / "runstate.json",
        "status": d / "status.json",
    }
    return Orchestrator.from_config(
        config=cfg, source=source, obs=_OkObs(),
        channel_paths=channel_paths, trackers=trackers, fps=30.0,
    )


class _DictSource:
    """A FrameSource stand-in returning a seeded per-camera frame map (or None)."""

    def __init__(self, frames_by_cam: dict) -> None:
        self._frames = frames_by_cam

    def start(self):
        pass

    def latest(self, cam_id):
        return self._frames.get(cam_id)

    def last_frame_ts(self, cam_id):
        return None

    def stop(self):
        pass


# --------------------------------------------------------------------------- #
# Test 1 + 2 — ONE forward, N per-camera updates, each with ONLY its own detections.
# --------------------------------------------------------------------------- #


def test_fan_out_one_batched_forward_per_tick(make_config):
    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    model = _SharedModel(cam_ids)
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    dets_by_cam, locked_energy, _frames_by_cam = orch._fan_out(tick=0)

    # ONE batched forward this tick; NEVER model.track([frames]) (#13107).
    assert len(model.predict_calls) == 1
    assert model.predict_calls[0]["n_frames"] == len(cam_ids)
    assert model.track_calls == 0

    # Each per-camera tracker updated EXACTLY once with ONLY its own camera's detections.
    for cid in cam_ids:
        assert len(trackers[cid].update_calls) == 1
        assert trackers[cid].update_calls[0].cam_id == cid

    # The returned map is the per-camera consumer shape (one entry per camera).
    assert set(dets_by_cam.keys()) == set(cam_ids)
    assert isinstance(locked_energy, float)


def test_fan_out_fp16_half_threaded(make_config):
    """The batched forward runs FP16 when config.model.use_fp16 is set (half=True)."""
    cfg = make_config(overrides={"model": {"path": "yolo26s.pt", "class_index": 16, "use_fp16": True}})
    cam_ids = [c.id for c in cfg.cameras]
    model = _SharedModel(cam_ids)
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    orch._fan_out(tick=0)

    assert model.predict_calls[0]["kwargs"].get("half") is True
    assert model.predict_calls[0]["kwargs"].get("end2end") is False


# --------------------------------------------------------------------------- #
# Test 3 — the HARD ReID gate runs ONCE, threading is_engine; no false trip on a fake.
# --------------------------------------------------------------------------- #


def test_fan_out_reid_gate_runs_once_threading_is_engine(make_config, monkeypatch):
    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    model = _SharedModel(cam_ids)
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    calls: list = []

    def _fake_gate(m, is_engine=False):
        calls.append({"model": m, "is_engine": is_engine})

    monkeypatch.setattr(
        "segugio.tracking.reid_check.assert_native_reid_engaged", _fake_gate
    )

    orch._fan_out(tick=0)
    orch._fan_out(tick=1)

    # The HARD gate ran EXACTLY once (after the first real-inference tick), threading is_engine.
    assert len(calls) == 1
    assert calls[0]["is_engine"] is False  # eager FP16 path → HARD gate preserved


# --------------------------------------------------------------------------- #
# Task 4 — is_engine flows through the loop into the REAL reid gate: engine WARNS,
# eager HARD-raises (Q1 Option (a)). Drives the genuine assert_native_reid_engaged.
# --------------------------------------------------------------------------- #


class _ClsReID:
    """A ``ultralytics.trackers.bot_sort.ReID`` stand-in (the cls-fallback encoder shape)."""


class _ClsFallbackBot:
    """A BoT-SORT whose ``encoder`` is a ReID instance — the silent cls-fallback path."""

    def __init__(self, reid) -> None:
        self.encoder = reid


class _ClsFallbackPredictor:
    """A predictor on the cls-fallback path: encoder is a ReID instance, no native hook."""

    def __init__(self, reid) -> None:
        self.trackers = [_ClsFallbackBot(reid)]
        self._hook = None  # cls fallback registers NO forward-pre-hook


class _ClsFallbackModel:
    """A shared model whose predictor is on the cls-ReID fallback path (engine reality)."""

    def __init__(self, cam_ids: list[str], reid) -> None:
        self._cam_ids = cam_ids
        self.names = {0: "person", 16: "dog"}
        self.predictor = _ClsFallbackPredictor(reid)
        self.predict_calls: list[dict] = []

    def predict(self, frames, **kwargs):
        self.predict_calls.append({"n_frames": len(frames), "kwargs": kwargs})
        return [_FakeResult(cid) for cid in self._cam_ids]

    def track(self, *a, **k):  # pragma: no cover - batched path never calls this
        return []


class _EngineTracker(_FakeTracker):
    """An engine-backed tracker stand-in: ``is_engine=True`` (the Q1 Option-(a) path)."""

    def __init__(self, cam_id: str, model) -> None:
        super().__init__(cam_id, model)
        self.is_engine = True


def _patch_reid_module(monkeypatch, reid_cls):
    """Make the gate's lazy ``from ultralytics.trackers.bot_sort import ReID`` resolve to a fake."""
    import sys
    import types

    pkg = types.ModuleType("ultralytics.trackers.bot_sort")
    pkg.ReID = reid_cls
    monkeypatch.setitem(sys.modules, "ultralytics", types.ModuleType("ultralytics"))
    monkeypatch.setitem(
        sys.modules, "ultralytics.trackers", types.ModuleType("ultralytics.trackers")
    )
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.bot_sort", pkg)


def test_fan_out_engine_path_gate_warns_not_raises(make_config, monkeypatch):
    """Task 4 Test 1: is_engine=True + cls-fallback predictor → the REAL gate WARNS, loop proceeds."""
    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    reid = _ClsReID()
    model = _ClsFallbackModel(cam_ids, reid)
    trackers = {cid: _EngineTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    _patch_reid_module(monkeypatch, _ClsReID)

    # The cls-fallback would HARD-raise on the eager path; is_engine=True downgrades it to a
    # warning (Q1 Option (a)) — the loop must tick without raising and mark the gate checked.
    orch._fan_out(tick=0)
    assert orch._reid_checked is True


def test_fan_out_eager_path_gate_hard_raises_on_cls_fallback(make_config, monkeypatch):
    """Task 4 Test 2: is_engine=False + a genuine cls fallback → the REAL gate HARD-raises (TRK-02)."""
    import pytest

    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    reid = _ClsReID()
    model = _ClsFallbackModel(cam_ids, reid)
    # default _FakeTracker → is_engine False (eager path) on a cls-fallback model.
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    _patch_reid_module(monkeypatch, _ClsReID)

    with pytest.raises(RuntimeError, match="cls model"):
        orch._fan_out(tick=0)


# --------------------------------------------------------------------------- #
# Test 4 — coast: a None frame for one camera coasts that camera, never crashes.
# --------------------------------------------------------------------------- #


def test_fan_out_none_frame_coasts(make_config):
    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    model = _SharedModel(cam_ids)
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    # one dead camera (None frame)
    dead = cam_ids[1]
    frames = {cid: _Frame(cid) for cid in cam_ids}
    frames[dead] = None
    source = _DictSource(frames)
    orch = _orch(cfg, trackers, source)

    dets_by_cam, _, _ = orch._fan_out(tick=0)

    # The dead camera coasts to a None signal; its tracker is NOT updated with detections.
    assert dets_by_cam[dead] is None
    assert trackers[dead].update_calls == []
    # The live cameras still produced an entry in the consumer map.
    for cid in cam_ids:
        if cid != dead:
            assert len(trackers[cid].update_calls) == 1


def test_fan_out_dog_index_resolved_by_name(make_config):
    """The batched forward uses the NAME-resolved dog index (16 here), never a hardcoded value."""
    cfg = make_config()
    cam_ids = [c.id for c in cfg.cameras]
    model = _SharedModel(cam_ids)
    trackers = {cid: _FakeTracker(cid, model) for cid in cam_ids}
    source = _DictSource({cid: _Frame(cid) for cid in cam_ids})
    orch = _orch(cfg, trackers, source)

    orch._fan_out(tick=0)

    assert model.predict_calls[0]["kwargs"].get("classes") == [16]
