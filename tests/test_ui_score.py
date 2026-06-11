"""SCR-02 — Flask POST /score writes expected file content per discipline (Wave-0 stub).

Behavior (filled by 05-05):
  - POST /score for disc T&F / freestyle / agility writes the expected score.json + overlay.txt.
  - exercised via the Flask test client (no server, no heavy deps).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-02 Flask POST /score)", strict=False)
def test_post_score_disc_tf():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-02 freestyle)", strict=False)
def test_post_score_freestyle():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-02 agility)", strict=False)
def test_post_score_agility():
    raise AssertionError("not implemented")
