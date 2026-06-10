"""CPU regression for `_resolve_tracker_yaml` (TRK-01/TRK-02 real-path fix).

The GPU UAT (04-HUMAN-UAT.md) revealed that passing the bare name ``"botsort_dog.yaml"`` to
``PerCameraTracker`` made Ultralytics ``.track()`` raise ``'botsort_dog.yaml' does not exist``
— ``check_yaml`` does NOT search Segugio's top-level ``trackers/`` dir — which the per-frame
fail-safe silently degraded to coast on every frame, so ``predictor.trackers`` was never built
and native ReID never engaged. These tests pin the resolver that fixes it. They are CPU-only
(pure ``pathlib``; the resolver does not import the heavy stack) so they run where the GPU
tests SKIP.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Module-level imports are loguru + pathlib only (heavy deps are imported inside methods),
# so importing the resolver is CPU-safe.
from segugio.tracking.detector import _resolve_tracker_yaml

_REPO_TRACKER = Path(__file__).resolve().parents[1] / "trackers" / "botsort_dog.yaml"


def test_bare_name_resolves_to_repo_trackers_dir() -> None:
    """The bare ``"botsort_dog.yaml"`` resolves to the repo ``trackers/`` copy (the real bug)."""
    resolved = _resolve_tracker_yaml("botsort_dog.yaml")
    assert Path(resolved).is_file()
    assert Path(resolved) == _REPO_TRACKER


def test_absolute_path_passes_through() -> None:
    """An absolute path to an existing yaml is returned as-is (resolved)."""
    resolved = _resolve_tracker_yaml(str(_REPO_TRACKER))
    assert Path(resolved) == _REPO_TRACKER


def test_cwd_relative_path_resolves(tmp_path, monkeypatch) -> None:
    """A CWD-relative path that exists is honored before the repo trackers/ fallback."""
    local = tmp_path / "custom_tracker.yaml"
    local.write_text("tracker_type: botsort\n")
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_tracker_yaml("custom_tracker.yaml")
    assert Path(resolved) == local.resolve()


def test_missing_yaml_fails_loudly() -> None:
    """A missing/misnamed config raises at construction time, never a silent coast."""
    with pytest.raises(FileNotFoundError, match="not found"):
        _resolve_tracker_yaml("does_not_exist_tracker.yaml")
