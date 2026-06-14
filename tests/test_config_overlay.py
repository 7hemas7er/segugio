"""OVD-03 / D-05 / D-06 — OverlayParams additive sub-model + Config.overlay field.

Mirrors ``test_config_engine_keys.py`` (the additive ``extra="forbid"`` sub-model idiom):
  - ``freestyle_duration_s`` defaults to 120 (D-06, 2-minute routines).
  - a full ``Config`` WITHOUT an ``overlay:`` block still validates (``default_factory``), so no
    existing config breaks (the loader is fail-fast ``SystemExit(2)`` on any ValidationError).
  - an explicit value parses.
  - a non-positive duration is rejected (``Field(gt=0)`` → ValidationError).
  - an unknown key is rejected (``extra="forbid"``).

RED-by-design: ``OverlayParams`` and ``Config.overlay`` do not exist until Plan 10-03. Every test
is ``@pytest.mark.xfail(strict=False)`` and imports the not-yet-existing symbols INSIDE its body so
collection stays green (an ImportError under xfail is an expected fail, not a collection error).
Plan 10-03 creates the symbols and REMOVES these markers.

Heavy imports (numpy/cv2/torch) are intentionally absent — pydantic + stdlib only.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl lands in Plan 10-03", strict=False)
def test_freestyle_duration_defaults_to_120():
    """OverlayParams() defaults freestyle_duration_s to 120 (D-06)."""
    from segugio.config.models import OverlayParams

    assert OverlayParams().freestyle_duration_s == 120


@pytest.mark.xfail(reason="impl lands in Plan 10-03", strict=False)
def test_config_without_overlay_block_still_validates(make_config):
    """A full Config WITHOUT an overlay: block still validates and exposes the 120 default.

    ``make_config`` builds the canonical 4-camera Config from a dict that has NO ``overlay:``
    key; the ``Field(default_factory=OverlayParams)`` wiring must fill it in so existing configs
    keep loading (loader is fail-fast SystemExit(2) on ValidationError).
    """
    cfg = make_config()
    assert cfg.overlay.freestyle_duration_s == 120


@pytest.mark.xfail(reason="impl lands in Plan 10-03", strict=False)
def test_freestyle_duration_explicit_value():
    """An explicit freestyle_duration_s parses through model_validate."""
    from segugio.config.models import OverlayParams

    assert OverlayParams.model_validate({"freestyle_duration_s": 90}).freestyle_duration_s == 90


@pytest.mark.xfail(reason="impl lands in Plan 10-03", strict=False)
@pytest.mark.parametrize("bad_value", [0, -1])
def test_freestyle_duration_nonpositive_rejected(bad_value):
    """freestyle_duration_s <= 0 is rejected (Field(gt=0) → ValidationError)."""
    from pydantic import ValidationError

    from segugio.config.models import OverlayParams

    with pytest.raises(ValidationError):
        OverlayParams.model_validate({"freestyle_duration_s": bad_value})


@pytest.mark.xfail(reason="impl lands in Plan 10-03", strict=False)
def test_overlay_params_extra_forbid():
    """An unknown key is rejected (extra='forbid')."""
    from pydantic import ValidationError

    from segugio.config.models import OverlayParams

    with pytest.raises(ValidationError):
        OverlayParams.model_validate({"freestyle_duration_s": 120, "bogus_key": 1})
