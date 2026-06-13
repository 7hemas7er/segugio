"""D-01/D-02 — the HARD preview-bandwidth cap as a CONFIG-TIME guarantee.

Phase 8 promotes the Phase-7 preview seeds to a first-class capped resource: WiFi
contention is the #1 domain risk (3-4 phones already push 60-200 Mbps of NDI HX3), so
the preview byte budget must be ≤ 5-8 Mbps and enforced fail-fast at config load (CFG-01
posture), NOT by a runtime throttle (D-01, anti-pattern declined).

These tests pin the four truths:
  * D-01 — the default PreviewParams (5 fps / 384 px / q55) over N cameras computes a
    preview bitrate at or under the configured ceiling and the config VALIDATES.
  * D-02 — a cranked over-cap config (high fps/width/quality) is REJECTED at load with a
    ``pydantic.ValidationError`` (aggregating to ``SystemExit(2)`` through ``load_config``).
  * ``preview.enabled=false`` SKIPS the cap check (no JPEGs written → nothing to budget).
  * ``max_total_mbps`` is a settable, tunable ``PreviewParams`` field (raising the ceiling
    makes a previously-over-cap config pass — calibration is tunable, not baked, D-02/T-08-05).

They import the new ``PreviewParams.max_total_mbps`` field + ``Config._preview_bitrate_within_cap``
validator (not present until Task 2) so they go RED before the implementation lands.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from segugio.config import Config

# A cranked preview block that blows past any sane 5-8 Mbps ceiling: high cadence,
# full-HD thumbnails, max JPEG quality. Used by the over-cap + tunable-cap tests.
_CRANKED_PREVIEW = {
    "enabled": True,
    "fps": 30.0,
    "max_width": 1920,
    "jpeg_quality": 100,
}


def test_default_preview_config_passes_cap(valid_config_dict: dict) -> None:
    """The default PreviewParams (5 fps / 384 px / q55) validates under the default ceiling.

    No ``preview`` block is set → the additive defaults fill in (D-06 ON, 5/384/q55, the
    8.0 Mbps default cap). The computed worst-case bitrate over the config's cameras must
    land at or under the ceiling, so ``model_validate`` SUCCEEDS.
    """
    cfg = Config.model_validate(copy.deepcopy(valid_config_dict))
    assert cfg.preview.enabled is True
    assert cfg.preview.max_total_mbps == 8.0


def test_over_cap_config_rejected(valid_config_dict: dict) -> None:
    """A cranked over-cap preview config is REJECTED with a descriptive ValidationError (D-02)."""
    raw = copy.deepcopy(valid_config_dict)
    raw["preview"] = copy.deepcopy(_CRANKED_PREVIEW)
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(raw)
    msg = str(exc.value)
    # The error names the computed bitrate, the cap, and the remediation.
    assert "mbps" in msg.lower()
    assert "cap" in msg.lower() or "exceed" in msg.lower()


def test_disabled_preview_skips_cap(valid_config_dict: dict) -> None:
    """``preview.enabled=false`` skips the cap check entirely (no JPEGs → nothing to budget)."""
    raw = copy.deepcopy(valid_config_dict)
    raw["preview"] = copy.deepcopy(_CRANKED_PREVIEW)
    raw["preview"]["enabled"] = False  # source-side off-switch (D-09)
    cfg = Config.model_validate(raw)  # cranked but disabled → validates
    assert cfg.preview.enabled is False


def test_cap_is_config_field_tunable(valid_config_dict: dict) -> None:
    """Raising ``max_total_mbps`` makes a previously-over-cap config pass (the cap is tunable).

    The calibration is a tunable config field (T-08-05 accept-documented), not a baked
    constant — bumping the ceiling high enough admits the cranked config.
    """
    raw = copy.deepcopy(valid_config_dict)
    raw["preview"] = copy.deepcopy(_CRANKED_PREVIEW)
    # Without a raised cap → rejected.
    with pytest.raises(ValidationError):
        Config.model_validate(copy.deepcopy(raw))
    # Raise the ceiling well above the cranked bitrate → now it validates.
    raw["preview"]["max_total_mbps"] = 100000.0
    cfg = Config.model_validate(raw)
    assert cfg.preview.max_total_mbps == 100000.0


def test_over_cap_config_aborts_loader(valid_config_dict: dict, tmp_config) -> None:
    """Loading a cranked YAML through ``load_config`` aggregates to ``SystemExit(2)`` (CFG-01)."""
    import yaml

    from segugio.config.loader import load_config

    raw = copy.deepcopy(valid_config_dict)
    raw["preview"] = copy.deepcopy(_CRANKED_PREVIEW)
    path = tmp_config(yaml.safe_dump(raw))
    with pytest.raises(SystemExit) as exc:
        load_config(path)
    assert exc.value.code == 2
