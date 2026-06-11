"""OBS-04 — scene-template names match config obs_scene / SAFE.

Behavior (05-03):
  - the provided OBS scene-collection template exists and parses as JSON.
  - every Camera.obs_scene in the example config(s) AND the literal "SAFE" scene appear
    as scenes in the template — the cross-reference that keeps the template and config in
    lockstep (the orchestrator cuts by these names).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _REPO_ROOT / "obs" / "segugio-scene-collection.json"


def _template_scene_names() -> set[str]:
    """Parse the scene names from the OBS scene-collection template.

    OBS exports a scene as a source whose ``id`` == ``"scene"``; its ``name`` is the scene
    name. ``scene_order`` lists the same names — assert both agree.
    """
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    from_sources = {
        src["name"] for src in data.get("sources", []) if src.get("id") == "scene"
    }
    from_order = {entry["name"] for entry in data.get("scene_order", [])}
    assert from_order <= from_sources, "scene_order references a scene with no source entry"
    return from_sources


def _config_obs_scenes(config_path: Path) -> set[str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {cam["obs_scene"] for cam in raw["cameras"]}


def test_template_exists():
    assert _TEMPLATE.is_file(), f"missing OBS scene-collection template at {_TEMPLATE}"


@pytest.mark.parametrize(
    "config_name",
    ["config.example.yaml", "config.agility.example.yaml"],
)
def test_template_scene_names_match_config(config_name):
    scenes = _template_scene_names()
    config_scenes = _config_obs_scenes(_REPO_ROOT / config_name)

    missing = config_scenes - scenes
    assert not missing, f"{config_name}: obs_scene(s) {missing} absent from the template"

    # SAFE must be a first-class scene in the template (RBT-02 fallback target).
    assert "SAFE" in scenes, "template is missing the first-class SAFE scene"
