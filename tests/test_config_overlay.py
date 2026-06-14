"""OVD-03 / D-05 / D-06 — OverlayParams additive sub-model + Config.overlay field.

Mirrors ``test_config_engine_keys.py`` (the additive ``extra="forbid"`` sub-model idiom):
  - ``freestyle_duration_s`` defaults to 120 (D-06, 2-minute routines).
  - a full ``Config`` WITHOUT an ``overlay:`` block still validates (``default_factory``), so no
    existing config breaks (the loader is fail-fast ``SystemExit(2)`` on any ValidationError).
  - an explicit value parses.
  - a non-positive duration is rejected (``Field(gt=0)`` → ValidationError).
  - an unknown key is rejected (``extra="forbid"``).

GREEN (Plan 10-03): ``OverlayParams`` and ``Config.overlay`` now exist; the xfail markers Plan
10-01 placed here have been removed, so these are permanent regression guards. Symbol imports stay
inside each test body (the idiom the scaffold established) — harmless now that the symbols exist.

Heavy imports (numpy/cv2/torch) are intentionally absent — pydantic + stdlib only.
"""

from __future__ import annotations

import pytest


def test_freestyle_duration_defaults_to_120():
    """OverlayParams() defaults freestyle_duration_s to 120 (D-06)."""
    from segugio.config.models import OverlayParams

    assert OverlayParams().freestyle_duration_s == 120


def test_config_without_overlay_block_still_validates(make_config):
    """A full Config WITHOUT an overlay: block still validates and exposes the 120 default.

    ``make_config`` builds the canonical 4-camera Config from a dict that has NO ``overlay:``
    key; the ``Field(default_factory=OverlayParams)`` wiring must fill it in so existing configs
    keep loading (loader is fail-fast SystemExit(2) on ValidationError).
    """
    cfg = make_config()
    assert cfg.overlay.freestyle_duration_s == 120


def test_freestyle_duration_explicit_value():
    """An explicit freestyle_duration_s parses through model_validate."""
    from segugio.config.models import OverlayParams

    assert OverlayParams.model_validate({"freestyle_duration_s": 90}).freestyle_duration_s == 90


@pytest.mark.parametrize("bad_value", [0, -1])
def test_freestyle_duration_nonpositive_rejected(bad_value):
    """freestyle_duration_s <= 0 is rejected (Field(gt=0) → ValidationError)."""
    from pydantic import ValidationError

    from segugio.config.models import OverlayParams

    with pytest.raises(ValidationError):
        OverlayParams.model_validate({"freestyle_duration_s": bad_value})


def test_overlay_params_extra_forbid():
    """An unknown key is rejected (extra='forbid')."""
    from pydantic import ValidationError

    from segugio.config.models import OverlayParams

    with pytest.raises(ValidationError):
        OverlayParams.model_validate({"freestyle_duration_s": 120, "bogus_key": 1})


# --------------------------------------------------------------------------- #
# Phase 11 (BRD-01 / BRD-02) — branding fields grown additively onto
# OverlayParams: event_name (D-08), logo_path (D-07), and the three CSS-var
# theme colors (D-06, defaulting to the console palette). All carry defaults so
# a config without an `overlay:` block (or with only freestyle_duration_s) still
# validates under the fail-fast SystemExit(2) loader.
# --------------------------------------------------------------------------- #


def test_overlay_branding_defaults():
    """The branding fields default to the empty identity + console palette (D-06/D-07/D-08)."""
    from segugio.config.models import OverlayParams

    p = OverlayParams()
    assert p.event_name == ""          # D-08 — empty → identity line hides gracefully
    assert p.logo_path == ""           # D-07 — empty → no logo bug rendered
    assert p.theme_accent == "#34D399"  # D-06 — console green
    assert p.theme_plate == "#14161a"   # D-06 — console plate
    assert p.theme_text == "#E6E9EF"    # D-06 — console text
    # freestyle_duration_s default is unchanged by the additive grow.
    assert p.freestyle_duration_s == 120


def test_config_without_overlay_keys_applies_branding_defaults(make_config):
    """A Config WITHOUT an overlay: block still validates and exposes the branding defaults."""
    cfg = make_config()
    assert cfg.overlay.event_name == ""
    assert cfg.overlay.logo_path == ""
    assert cfg.overlay.theme_accent == "#34D399"
    assert cfg.overlay.theme_plate == "#14161a"
    assert cfg.overlay.theme_text == "#E6E9EF"


def test_overlay_freestyle_only_still_validates():
    """An overlay block with ONLY freestyle_duration_s still validates (branding defaults in)."""
    from segugio.config.models import OverlayParams

    p = OverlayParams.model_validate({"freestyle_duration_s": 90})
    assert p.freestyle_duration_s == 90
    assert p.event_name == ""
    assert p.theme_accent == "#34D399"


def test_overlay_branding_round_trip():
    """event_name / logo_path / theme colors round-trip through model_validate (BRD-01/BRD-02)."""
    from segugio.config.models import OverlayParams

    p = OverlayParams.model_validate(
        {
            "event_name": "Disc Dog Open 2026",
            "logo_path": "static/branding/club-logo.png",
            "theme_accent": "rgb(12, 200, 120)",  # any CSS color token, not just hex
            "theme_plate": "#000000",
            "theme_text": "white",
        }
    )
    assert p.event_name == "Disc Dog Open 2026"
    assert p.logo_path == "static/branding/club-logo.png"
    assert p.theme_accent == "rgb(12, 200, 120)"
    assert p.theme_plate == "#000000"
    assert p.theme_text == "white"


def test_overlay_branding_extra_forbid():
    """An unknown branding key is still rejected (extra='forbid')."""
    from pydantic import ValidationError

    from segugio.config.models import OverlayParams

    with pytest.raises(ValidationError):
        OverlayParams.model_validate({"event_name": "X", "bogus": 1})
