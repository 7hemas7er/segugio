"""OBS-01/02 — recording fake: cut + cached PIP id (Wave-0 stub).

Behavior (filled by 05-03):
  - test_cut: cut("CAM Long") → fake records set_current_program_scene("CAM Long").
  - test_pip_cached_id: PIP toggles use the CACHED numeric sceneItemId resolved once at connect.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-01 cut mapping)", strict=False)
def test_cut():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-02 cached PIP id)", strict=False)
def test_pip_cached_id():
    raise AssertionError("not implemented")
