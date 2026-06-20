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


def _source_def(name: str) -> dict | None:
    """Return the top-level ``sources`` entry whose ``name`` matches, or ``None``."""
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    for src in data.get("sources", []):
        if src.get("name") == name:
            return src
    return None


def _scene_items(scene_name: str) -> list[dict]:
    """Return the ``settings.items`` list for the scene source named ``scene_name``."""
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    for src in data.get("sources", []):
        if src.get("id") == "scene" and src.get("name") == scene_name:
            return src.get("settings", {}).get("items", [])
    return []


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


def test_score_overlay_source_def():
    """SCN-01 — the shared browser_source exists with the verified obs-browser CEF keys.

    Assert the REAL JSON keys ``shutdown`` / ``restart_when_active`` (NOT the UI-label
    strings ``shutdown_source_when_not_visible`` / ``refresh_when_scene_is_active``, which
    silently no-op — Pitfall 2). Transparency holds via the page's own CSS; the JSON ships
    ``css: ""`` so no opaque background is injected (D-06).
    """
    so = _source_def("Score Overlay")
    assert so is not None, "template is missing the Score Overlay browser source"
    assert so["id"] == "browser_source", so["id"]

    settings = so["settings"]
    assert settings["url"] == "http://localhost:8080/overlay", settings["url"]
    assert settings["shutdown"] is False, "shutdown must be False (no re-flash on a cut)"
    assert (
        settings["restart_when_active"] is False
    ), "restart_when_active must be False (no timer-state loss on a cut)"
    # Transparency: page owns it; the JSON injects no opaque background (D-06).
    assert settings.get("css", "") == "", "Score Overlay must not inject opaque CSS"


def test_every_scene_has_overlay_and_text():
    """SCN-01 + RBT-06 — every scene references BOTH Score Overlay and Score Text."""
    for scene in _template_scene_names():
        names = {item["name"] for item in _scene_items(scene)}
        assert names >= {
            "Score Overlay",
            "Score Text",
        }, f"{scene}: items must contain both Score Overlay and Score Text, got {names}"


def test_overlay_is_top_layer():
    """SCN-01 — Score Overlay is the LAST item (top of z-order) and above every NDI item."""
    for scene in _template_scene_names():
        items = _scene_items(scene)
        assert items, f"{scene}: has no items"
        assert (
            items[-1]["name"] == "Score Overlay"
        ), f"{scene}: Score Overlay must be the last item (top of z-order)"

        overlay_idx = len(items) - 1
        ndi_indices = [
            i for i, item in enumerate(items) if item["name"].startswith("NDI - ")
        ]
        assert ndi_indices, f"{scene}: expected at least one NDI item"
        assert overlay_idx > max(
            ndi_indices
        ), f"{scene}: Score Overlay must render above every NDI item"


def test_score_text_is_fallback_hidden():
    """RBT-06 / D-03 — Score Text ships visible:false (the manual-toggle fallback)."""
    for scene in _template_scene_names():
        text_items = [
            item for item in _scene_items(scene) if item["name"] == "Score Text"
        ]
        assert text_items, f"{scene}: missing the Score Text fallback item"
        assert (
            text_items[0]["visible"] is False
        ), f"{scene}: Score Text must ship visible:false (manual-toggle fallback)"


def _scene_ndi_source_names() -> set[str]:
    """All NDI ``ndi_source_name`` values declared in the scene-collection template.

    Every NDI input source ships ``id == "ndi_source"`` and carries the published phone
    NDI name in ``settings.ndi_source_name``. These are the strings OBS resolves a live
    feed by — a config ``ndi_source`` that does not byte-match one of these is the
    "OBS sees it but the console is blank" drift (D-08).
    """
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    return {
        src["settings"]["ndi_source_name"]
        for src in data.get("sources", [])
        if src.get("id") == "ndi_source"
    }


def _config_ndi_sources(config_path: Path) -> dict[str, str]:
    """Map each camera id -> its configured ``ndi_source`` in the example config."""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {cam["id"]: cam["ndi_source"] for cam in raw["cameras"]}


@pytest.mark.parametrize(
    "config_name",
    ["config.example.yaml", "config.agility.example.yaml"],
)
def test_config_ndi_source_matches_scene_collection(config_name):
    """D-08 — every example-config ``ndi_source`` byte-matches a scene ``ndi_source_name``.

    The scene-collection JSON + the agility config are canonical (RESEARCH A2); this
    lockstep assertion catches the "OBS sees it but console blank" drift (T-14-ndidrift)
    if the example config's NDI name ever diverges from the published name OBS resolves.
    """
    scene_names = _scene_ndi_source_names()
    config_sources = _config_ndi_sources(_REPO_ROOT / config_name)

    for cam_id, ndi_source in config_sources.items():
        assert ndi_source in scene_names, (
            f"{config_name}: camera {cam_id} ndi_source {ndi_source!r} does not byte-match "
            f"any scene-collection ndi_source_name {sorted(scene_names)} "
            "(the 'OBS sees it but console blank' drift, D-08)"
        )
