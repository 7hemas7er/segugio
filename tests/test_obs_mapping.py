"""OBS-01/02 — recording fake: cut + cached PIP id.

Behavior (05-03):
  - test_cut: a Decision(target="cam_long") maps through Camera.obs_scene to
    cut("CAM Long"); target=="SAFE" maps to the is_safe camera's obs_scene
    ("CAM Wide"). The fake records ("cut", scene_name) — the headless
    set_current_program_scene equivalent (OBS-01).
  - test_pip_cached_id: set_pip records the CACHED numeric sceneItemId resolved
    once at connect; the source NAME is never the recorded id argument (OBS-02).
"""

from __future__ import annotations

from segugio.obs import scene_for
from segugio.obs.recording_fake import RecordingObsController


def _decision(target: str):
    """A real Decision (only .target is read by scene_for)."""
    from segugio.decision.signals import Decision, Mode

    return Decision(tick=0, target=target, mode=Mode.auto, reason="auto_switch")


def test_cut(make_config):
    cfg = make_config()
    fake = RecordingObsController()
    fake.connect()

    # target = a real camera id → its obs_scene
    fake.cut(scene_for(_decision("cam_long"), cfg.cameras))
    assert ("cut", "CAM Long") in fake.calls

    # target = "SAFE" sentinel → the is_safe camera's obs_scene (cam_wide → "CAM Wide")
    fake.cut(scene_for(_decision("SAFE"), cfg.cameras))
    assert ("cut", "CAM Wide") in fake.calls


def test_pip_cached_id():
    fake = RecordingObsController()
    fake.connect()  # pre-seeds the numeric sceneItemId cache

    fake.set_pip("PIP", "overlay-source", enabled=True)

    pip_calls = [c for c in fake.calls if c[0] == "pip"]
    assert pip_calls, "set_pip recorded nothing"
    scene, item_id, enabled, transform = pip_calls[-1][1:]
    # the recorded id must be the NUMERIC cached id, never the source NAME (OBS-02)
    assert isinstance(item_id, int)
    assert item_id != "overlay-source"
    assert item_id == fake.item_id("PIP", "overlay-source")
