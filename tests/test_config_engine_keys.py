"""Additive ModelConfig.engine_path + use_fp16 keys (06-01, Wave-0 config seam).

Two ADDITIVE keys on ``ModelConfig`` defaulting to today's eager-FP32 ``.pt`` behavior:
  * ``engine_path: Path | None = None`` — the cached ``.engine`` artifact path (None = eager);
  * ``use_fp16: bool = False`` — the eager ``half=True`` toggle for Wave 1.

``extra="forbid"`` is preserved (unknown keys still rejected). An existing config WITHOUT
either key still validates with the defaults in — no existing config is affected.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from segugio.config.models import ModelConfig


# --------------------------------------------------------------------------- #
# Test 1 — additive: defaults preserve existing eager-FP32 .pt behavior
# --------------------------------------------------------------------------- #


def test_engine_keys_default_to_eager() -> None:
    m = ModelConfig()
    assert m.engine_path is None  # None = eager .pt (existing behavior)
    assert m.use_fp16 is False  # FP32 eager (existing behavior)
    # existing keys unchanged
    assert str(m.path) == "yolo26s.pt"
    assert m.class_index == 16


def test_extra_forbid_still_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        ModelConfig.model_validate({"path": "yolo26s.pt", "bogus_key": 1})


# --------------------------------------------------------------------------- #
# Test 2 — explicit values parse correctly
# --------------------------------------------------------------------------- #


def test_engine_path_parses_to_path() -> None:
    m = ModelConfig.model_validate({"engine_path": "yolo26s.engine"})
    assert isinstance(m.engine_path, Path)
    assert str(m.engine_path) == "yolo26s.engine"


def test_use_fp16_parses_true() -> None:
    m = ModelConfig.model_validate({"use_fp16": True})
    assert m.use_fp16 is True
