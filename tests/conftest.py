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
