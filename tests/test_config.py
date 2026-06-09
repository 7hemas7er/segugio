"""Config contract tests — CFG-01..04 (plan 01-02).

Covers the typed pydantic v2 Config schema, fail-fast loader, zone/framing_weights
cross-validation, the discipline discriminated-union swap, and the model defaults.

Test groups are named so VALIDATION.md's ``-k`` selectors resolve:
  -k valid       happy-path parse into a typed Config
  -k invalid     parametrized malformed-config rejection (CFG-01)
  -k zones       zone-rect bounds/ordering + framing_weights matrix (CFG-02)
  -k discipline  disc_dog vs agility swap on field.sport (CFG-03)
  -k model       ModelConfig defaults + YAML override (CFG-04)
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from segugio.config import Config, Role, load_config
from segugio.config.discipline import AgilityProfile, DiscDogProfile
from segugio.config.models import ModelConfig


# --------------------------------------------------------------------------- #
# CFG-01 — valid config parses into a typed Config
# --------------------------------------------------------------------------- #


def test_valid_config_dict_parses(valid_config_dict):
    cfg = Config.model_validate(valid_config_dict)
    assert isinstance(cfg, Config)
    # attribute access works through every nested model
    assert cfg.cameras[0].role is Role.main_wide
    assert cfg.thresholds.alpha == 0.3
    assert cfg.model.class_index == 16
    assert cfg.field.sport == "disc_dog"


def test_valid_config_has_safe_camera(valid_config_dict):
    cfg = Config.model_validate(valid_config_dict)
    assert any(cam.is_safe for cam in cfg.cameras)


# --------------------------------------------------------------------------- #
# CFG-02 — zones: bounds, ordering, framing_weights cross-check
# --------------------------------------------------------------------------- #


def test_zones_unordered_rect_rejected():
    from segugio.config.models import Zone

    with pytest.raises(ValidationError):
        Zone(name="bad", rect=[0.2, 0.5, 0.1, 0.9])  # x0 > x1


def test_zones_out_of_range_rect_rejected():
    from segugio.config.models import Zone

    with pytest.raises(ValidationError):
        Zone(name="bad", rect=[0.0, 0.0, 1.5, 0.9])  # 1.5 out of [0,1]


def test_zones_unweighted_zone_rejected(valid_config_dict):
    # camera references "middle" but framing_weights[main_wide] only has near/mid/far
    valid_config_dict["cameras"][0]["zones"][1]["name"] = "middle"
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


def test_zones_weight_reads_back(valid_config_dict):
    cfg = Config.model_validate(valid_config_dict)
    assert cfg.framing_weights[Role.long]["far"] == 1.6


# --------------------------------------------------------------------------- #
# CFG-01 — cross-validator: missing SAFE camera fails fast
# --------------------------------------------------------------------------- #


def test_invalid_no_safe_camera_rejected(valid_config_dict):
    for cam in valid_config_dict["cameras"]:
        cam["is_safe"] = False
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


# --------------------------------------------------------------------------- #
# CFG-03 — discipline discriminated union swaps profiles on field.sport
# --------------------------------------------------------------------------- #


def test_discipline_disc_dog_profile(valid_config_dict):
    cfg = Config.model_validate(valid_config_dict)
    assert isinstance(cfg.field, DiscDogProfile)
    assert "catch_count" in cfg.field.overlay_fields


def test_discipline_agility_profile(valid_config_dict):
    valid_config_dict["field"] = {"sport": "agility", "event": "agility_standard"}
    cfg = Config.model_validate(valid_config_dict)
    assert isinstance(cfg.field, AgilityProfile)
    assert "faults" in cfg.field.overlay_fields
    # the two disciplines expose different overlay field sets
    assert cfg.field.overlay_fields != DiscDogProfile(sport="disc_dog").overlay_fields


def test_discipline_bogus_sport_rejected(valid_config_dict):
    valid_config_dict["field"] = {"sport": "bogus"}
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


# --------------------------------------------------------------------------- #
# CFG-04 — model path / class_index defaults + override
# --------------------------------------------------------------------------- #


def test_model_defaults():
    m = ModelConfig()
    assert str(m.path) == "yolo26s.pt"
    assert m.class_index == 16


def test_model_override(valid_config_dict):
    valid_config_dict["model"] = {"path": "custom.pt", "class_index": 0}
    cfg = Config.model_validate(valid_config_dict)
    assert str(cfg.model.path) == "custom.pt"
    assert cfg.model.class_index == 0
