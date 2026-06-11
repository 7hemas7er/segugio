"""OBS-04 — scene-template names match config obs_scene / SAFE (Wave-0 stub).

Behavior (filled by 05-03):
  - the provided OBS scene-collection template exists.
  - every Camera.obs_scene (and the SAFE scene) in the example config has a matching scene.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-04 scene template names)", strict=False)
def test_template_scene_names_match_config():
    raise AssertionError("not implemented")
