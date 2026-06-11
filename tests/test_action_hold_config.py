"""05-01 Task 3 — ActionHoldParams config + light interfaces + motion-energy accessor.

Behaviors (D-08 seeds + D-05/D-06 interfaces + RESEARCH Q1/A6 accessor gap):
  - a Config built from an existing extra=forbid config WITHOUT an action_hold block still
    validates (ActionHoldParams defaults in — pure additive, zero schema break).
  - ActionHoldParams rejects motion_threshold<=0 and window_ticks<1 (Field bounds).
  - FrameSource and ObsController interfaces are declared LIGHT (no heavy import).
  - CompetitorLock.locked_motion_energy() returns _motion_energy(locked_id) when locked,
    0.0 when locked_id is None — byte-identical to the existing private path, no logic change.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError


# --- ActionHoldParams additive config (D-08) ------------------------------- #


def test_config_without_action_hold_still_validates(valid_config_dict):
    """An existing extra=forbid config with NO action_hold block defaults in (no break)."""
    from segugio.config import Config

    assert "action_hold" not in valid_config_dict  # the legacy shape
    cfg = Config.model_validate(valid_config_dict)
    assert cfg.action_hold.motion_threshold > 0.0
    assert cfg.action_hold.window_ticks >= 1


def test_action_hold_accepts_explicit_block(valid_config_dict):
    """An explicit action_hold block is honored."""
    from segugio.config import Config

    valid_config_dict["action_hold"] = {"motion_threshold": 0.05, "window_ticks": 7}
    cfg = Config.model_validate(valid_config_dict)
    assert cfg.action_hold.motion_threshold == 0.05
    assert cfg.action_hold.window_ticks == 7


@pytest.mark.parametrize(
    "bad",
    [
        {"motion_threshold": 0.0, "window_ticks": 5},
        {"motion_threshold": -0.1, "window_ticks": 5},
        {"motion_threshold": 0.02, "window_ticks": 0},
        {"motion_threshold": 0.02, "window_ticks": -1},
    ],
)
def test_action_hold_rejects_out_of_bounds(valid_config_dict, bad):
    """motion_threshold<=0 and window_ticks<1 are rejected (Thresholds-style bounds)."""
    from segugio.config import Config

    valid_config_dict["action_hold"] = bad
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


def test_action_hold_forbids_extra(valid_config_dict):
    """ActionHoldParams uses extra='forbid' (mirrors the other sub-models)."""
    from segugio.config import Config

    valid_config_dict["action_hold"] = {"motion_threshold": 0.02, "window_ticks": 5, "x": 1}
    with pytest.raises(ValidationError):
        Config.model_validate(valid_config_dict)


# --- light interfaces (D-05 / D-06) ---------------------------------------- #


def test_frame_source_interface_declared():
    """segugio.ndi.source declares the FrameSource interface (light, no heavy import)."""
    from segugio.ndi.source import FrameSource

    for m in ("start", "latest", "last_frame_ts", "stop"):
        assert hasattr(FrameSource, m), f"FrameSource missing {m}"


def test_obs_controller_interface_declared():
    """segugio.obs.controller declares the ObsController interface (light)."""
    from segugio.obs.controller import ObsController

    for m in ("connect", "cut", "set_pip", "set_overlay_text", "close"):
        assert hasattr(ObsController, m), f"ObsController missing {m}"


# --- CompetitorLock public motion-energy accessor (RESEARCH Q1/A6) --------- #


def _signal(track_id, cx, cy, tick):
    from segugio.framing.signals import DetectionSignal

    return DetectionSignal(
        tick=tick, cam_id="cam_wide", track_id=track_id, cx=cx, cy=cy, w=0.1, h=0.1, conf=0.9
    )


def test_locked_motion_energy_zero_when_unlocked(make_config, tracking_params):
    """locked_motion_energy() returns 0.0 when nothing is locked (locked_id is None)."""
    from segugio.tracking.competitor_lock import CompetitorLock

    cam = make_config().cameras[0]
    lock = CompetitorLock(cam, tracking_params)
    assert lock.locked_id is None
    assert lock.locked_motion_energy() == 0.0


def test_locked_motion_energy_matches_private(make_config, tracking_params):
    """When locked, the accessor == the existing private _motion_energy(locked_id) (no logic change)."""
    from segugio.tracking.competitor_lock import CompetitorLock

    cam = make_config().cameras[0]  # zone covers the full field [0,0,1,1]
    lock = CompetitorLock(cam, tracking_params)
    # feed a moving track over several ticks so it acquires the lock
    for tick in range(6):
        lock.select([_signal(1, 0.1 + 0.1 * tick, 0.5, tick)], tick)
    assert lock.locked_id == 1
    public = lock.locked_motion_energy()
    private = lock._motion_energy(lock.locked_id)
    assert public == private
    assert math.isfinite(public)
