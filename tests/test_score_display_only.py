"""SCR-04 — the system DISPLAYS scores, never adjudicates (Wave-0 stub).

Behavior (filled by 05-05):
  - no scoring/adjudication code path exists (display-only): the score file is the
    operator's typed values, never a computed/judged result.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-05 (SCR-04 display-only, no adjudication)", strict=False)
def test_no_adjudication_code_path():
    raise AssertionError("not implemented")
