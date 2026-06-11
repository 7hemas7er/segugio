"""OBS-05 — overlay write hits the read-from-file path + set_input_settings fallback (Wave-0 stub).

Behavior (filled by 05-03):
  - the rendered overlay string is written atomically to the read-from-file target.
  - the one-shot fallback calls set_input_settings(input_name, {"text": ...}).
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-05 read-from-file overlay)", strict=False)
def test_overlay_writes_read_from_file():
    raise AssertionError("not implemented")


@pytest.mark.xfail(reason="impl pending 05-03 (OBS-05 set_input_settings fallback)", strict=False)
def test_overlay_set_input_settings_fallback():
    raise AssertionError("not implemented")
