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
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from segugio.config import Config, Role, load_config
from segugio.config.discipline import AgilityProfile, DiscDogProfile
from segugio.config.models import ModelConfig

# Repo-root example configs (committed reference files).
_REPO_ROOT = Path(__file__).resolve().parents[1]
DISC_EXAMPLE = _REPO_ROOT / "config.example.yaml"
AGILITY_EXAMPLE = _REPO_ROOT / "config.agility.example.yaml"


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


def test_model_override_from_yaml_roundtrips(tmp_config, valid_config_dict):
    # CFG-04: overriding path + class in YAML round-trips through the loader.
    valid_config_dict["model"] = {"path": "yolo26n.pt", "class_index": 3}
    path = tmp_config(yaml.safe_dump(valid_config_dict))
    cfg = load_config(path)
    assert str(cfg.model.path) == "yolo26n.pt"
    assert cfg.model.class_index == 3


# --------------------------------------------------------------------------- #
# CFG-01 — the two example files load into typed Config objects (loader path)
# --------------------------------------------------------------------------- #


def test_valid_disc_example_loads():
    cfg = load_config(DISC_EXAMPLE)
    assert isinstance(cfg, Config)
    assert cfg.field.sport == "disc_dog"
    assert any(cam.is_safe for cam in cfg.cameras)


def test_valid_agility_example_loads():
    cfg = load_config(AGILITY_EXAMPLE)
    assert isinstance(cfg, Config)
    assert cfg.field.sport == "agility"
    assert any(cam.is_safe for cam in cfg.cameras)


# --------------------------------------------------------------------------- #
# CFG-02 (zones) — a known weight reads back from the real example file
# --------------------------------------------------------------------------- #


def test_zones_example_weight_reads_back():
    cfg = load_config(DISC_EXAMPLE)
    assert cfg.framing_weights[Role.long]["far"] == 1.6


# --------------------------------------------------------------------------- #
# CFG-03 (discipline) — load BOTH example files, prove the swap from real files
# --------------------------------------------------------------------------- #


def test_discipline_swap_from_example_files():
    disc = load_config(DISC_EXAMPLE)
    agility = load_config(AGILITY_EXAMPLE)
    assert isinstance(disc.field, DiscDogProfile)
    assert isinstance(agility.field, AgilityProfile)
    # overlay field sets differ between disciplines (zero code edits — just YAML)
    assert disc.field.overlay_fields != agility.field.overlay_fields
    # framing defaults differ too (disc holds longer / more lead room)
    assert disc.field.framing_defaults != agility.field.framing_defaults
    assert disc.field.framing_defaults.lead_room > agility.field.framing_defaults.lead_room


# --------------------------------------------------------------------------- #
# CFG-01 (invalid) — parametrized fail-fast rejection of malformed configs.
# Each mutator corrupts the canonical valid_config_dict one way; the loader path
# must raise SystemExit (fail-fast) and direct model_validate a ValidationError.
# --------------------------------------------------------------------------- #


def _drop_required_key(d: dict) -> None:
    del d["cameras"]  # missing required key


def _wrong_type(d: dict) -> None:
    d["thresholds"]["alpha"] = "not-a-float"  # string where float expected


def _extra_forbidden_key(d: dict) -> None:
    d["cameras"][0]["bogus_field"] = 123  # extra="forbid" rejects unknown keys


def _zero_cameras(d: dict) -> None:
    d["cameras"] = []  # min_length=1 violated


def _no_safe_camera(d: dict) -> None:
    for cam in d["cameras"]:
        cam["is_safe"] = False  # cross-validator: SAFE fallback required


def _unweighted_zone(d: dict) -> None:
    d["cameras"][0]["zones"][0]["name"] = "phantom"  # not in framing_weights


def _zone_out_of_range(d: dict) -> None:
    d["cameras"][0]["zones"][0]["rect"] = [0.0, 0.0, 1.5, 0.5]  # 1.5 out of [0,1]


def _zone_unordered(d: dict) -> None:
    d["cameras"][0]["zones"][0]["rect"] = [0.9, 0.0, 0.1, 0.5]  # x0 > x1


def _bad_discipline(d: dict) -> None:
    d["field"] = {"sport": "underwater_hockey"}  # union_tag_invalid


INVALID_MUTATORS = [
    pytest.param(_drop_required_key, id="missing-key"),
    pytest.param(_wrong_type, id="wrong-type"),
    pytest.param(_extra_forbidden_key, id="extra-key"),
    pytest.param(_zero_cameras, id="zero-cameras"),
    pytest.param(_no_safe_camera, id="no-safe-cam"),
    pytest.param(_unweighted_zone, id="unweighted-zone"),
    pytest.param(_zone_out_of_range, id="zone-out-of-range"),
    pytest.param(_zone_unordered, id="zone-unordered"),
    pytest.param(_bad_discipline, id="bad-discipline"),
]


@pytest.mark.parametrize("mutate", INVALID_MUTATORS)
def test_invalid_config_rejected_by_model_validate(mutate, valid_config_dict):
    mutate(valid_config_dict)
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


@pytest.mark.parametrize("mutate", INVALID_MUTATORS)
def test_invalid_config_fails_fast_via_loader(mutate, tmp_config, valid_config_dict):
    # The loader aggregates the error and fails fast with SystemExit(2) (CFG-01).
    mutate(valid_config_dict)
    path = tmp_config(yaml.safe_dump(valid_config_dict))
    with pytest.raises(SystemExit) as exc:
        load_config(path)
    assert exc.value.code == 2


def test_loader_unreadable_path_fails_fast(tmp_path):
    # A missing/unreadable file also fails fast with SystemExit(2).
    with pytest.raises(SystemExit) as exc:
        load_config(tmp_path / "does_not_exist.yaml")
    assert exc.value.code == 2
