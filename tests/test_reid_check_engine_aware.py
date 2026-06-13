"""Engine-aware ReID gate tests (06-01, Open Q1 Option (a)).

``assert_native_reid_engaged`` gains an ``is_engine: bool = False`` keyword. On an
eager ``.pt`` model the HARD raise on the silent ``yolo26n-cls.pt`` cls fallback is
PRESERVED byte-for-byte (TRK-02). On an ``.engine``-backed model the SAME structural
shape (encoder is a ``ReID`` instance, or the forward hook is missing) is DOWNGRADED to a
``logger.warning`` and returns ``None`` — because a TensorRT engine loads via AutoBackend
and structurally cannot expose the in-graph Detect head, so native feats are impossible
BY DESIGN (RESEARCH Pitfall 1).

These tests inject fakes — no ultralytics / torch / GPU. To exercise the ``isinstance(enc,
ReID)`` branch without importing the real heavy ``ReID``, we inject a fake
``ultralytics.trackers.bot_sort`` module exposing a ``ReID`` class so the function's lazy
``from ultralytics.trackers.bot_sort import ReID`` resolves to our fake.
"""

from __future__ import annotations

import sys
import types

import pytest

from segugio.tracking.reid_check import assert_native_reid_engaged


class _FakeReID:
    """Stand-in for ``ultralytics.trackers.bot_sort.ReID`` (the cls-fallback encoder)."""


@pytest.fixture
def fake_reid_module(monkeypatch: pytest.MonkeyPatch):
    """Inject a fake ``ultralytics.trackers.bot_sort`` exposing ``ReID`` for the lazy import.

    The function does ``from ultralytics.trackers.bot_sort import ReID`` INSIDE its body. We
    populate ``sys.modules`` so that import resolves to ``_FakeReID`` without the heavy stack.
    Returns the ``_FakeReID`` class so tests can build encoders that ARE / ARE NOT instances.
    """
    ultra = types.ModuleType("ultralytics")
    trackers = types.ModuleType("ultralytics.trackers")
    bot_sort = types.ModuleType("ultralytics.trackers.bot_sort")
    bot_sort.ReID = _FakeReID
    ultra.trackers = trackers
    trackers.bot_sort = bot_sort
    monkeypatch.setitem(sys.modules, "ultralytics", ultra)
    monkeypatch.setitem(sys.modules, "ultralytics.trackers", trackers)
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.bot_sort", bot_sort)
    return _FakeReID


class _FakeTracker:
    def __init__(self, encoder) -> None:
        self.encoder = encoder


class _FakePredictor:
    def __init__(self, encoder, hook=object()) -> None:
        self.trackers = [_FakeTracker(encoder)]
        self._hook = hook


class _FakeModel:
    def __init__(self, predictor) -> None:
        self.predictor = predictor


def _model_with_reid_encoder(reid_cls) -> _FakeModel:
    """A model whose tracker encoder is a ReID instance (the cls fallback) + a hook present."""
    return _FakeModel(_FakePredictor(encoder=reid_cls()))


def _model_native() -> _FakeModel:
    """A model whose encoder is a bare lambda + the forward hook is present (native path)."""
    return _FakeModel(_FakePredictor(encoder=lambda feats, s: feats))


# --------------------------------------------------------------------------- #
# Test 1 — eager path unchanged: is_engine=False (default) still RAISES on cls fallback
# --------------------------------------------------------------------------- #


def test_eager_cls_fallback_still_raises(fake_reid_module) -> None:
    model = _model_with_reid_encoder(fake_reid_module)
    with pytest.raises(RuntimeError, match="cls"):
        assert_native_reid_engaged(model, is_engine=False)


# --------------------------------------------------------------------------- #
# Test 2 — engine path downgrade: is_engine=True warns-not-raises on the same fake
# --------------------------------------------------------------------------- #


def test_engine_cls_fallback_warns_not_raises(fake_reid_module) -> None:
    model = _model_with_reid_encoder(fake_reid_module)
    # Must NOT raise; returns None (accepting the cls-ReID fallback on an engine-backed model).
    assert assert_native_reid_engaged(model, is_engine=True) is None


def test_engine_missing_hook_warns_not_raises(fake_reid_module) -> None:
    # Native-shaped encoder but the forward hook is missing — on an engine this is expected.
    model = _FakeModel(_FakePredictor(encoder=lambda feats, s: feats, hook=None))
    assert assert_native_reid_engaged(model, is_engine=True) is None


# --------------------------------------------------------------------------- #
# Test 3 — native path still passes (no raise) for both is_engine values
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("is_engine", [False, True])
def test_native_path_passes_either_way(fake_reid_module, is_engine: bool) -> None:
    model = _model_native()
    assert assert_native_reid_engaged(model, is_engine=is_engine) is None


# --------------------------------------------------------------------------- #
# Test 4 — default arg: no is_engine kwarg behaves exactly as before (eager HARD gate)
# --------------------------------------------------------------------------- #


def test_default_arg_preserves_eager_hard_gate(fake_reid_module) -> None:
    model = _model_with_reid_encoder(fake_reid_module)
    with pytest.raises(RuntimeError, match="cls"):
        assert_native_reid_engaged(model)  # no is_engine kwarg → defaults to False
