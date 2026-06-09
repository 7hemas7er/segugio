"""DEC-03 / DEC-04 hold suite — action_hold + occlusion_hold suppression and max-caps.

These are the anti-cut guards that keep the camera through a climax (a catch / jump) and a
known occlusion (a tunnel / contact). Two hard properties (03-CONTEXT D-02 + the MANDATORY
max-cap guardrail):

  * while ``HoldInput.action`` is set the normal ``auto_switch`` is suppressed even if a
    challenger fully qualifies; the hold force-releases at its tick max-cap regardless of the
    input still being set (no stuck-hold freeze);
  * while ``HoldInput.occlusion`` is set ``auto_switch`` is suppressed; the occlusion hold
    auto-expires after ``ticks_from_seconds(hold_length_s, fps)`` ticks (disc_dog 2.5s /
    agility 1.5s) AND is independently max-capped;
  * a hold NEVER suppresses the feed-death emergency cut — death wins over hold.

Holds are timed in INTEGER ticks on the model (``action_hold_age`` /
``occlusion_hold_remaining``), advanced at the top of ``tick()``, never wall-clock.
"""

from __future__ import annotations

from segugio.config import Config, Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine, ticks_from_seconds
from segugio.decision.signals import SAFE_TARGET, HoldInput
from segugio.framing.signals import CameraScore, ScorerStatus
from tests.conftest import FPS, _VALID_CONFIG
import copy

_CAM_A = "cam_a"
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
    return [
        Camera(
            id=cid,
            role=Role.main_wide,
            obs_scene="WIDE",
            is_safe=(cid == _CAM_A),
            zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
        )
        for cid in (_CAM_A, _CAM_B)
    ]


def _disc_dog_hold_length() -> float:
    """disc_dog framing_defaults.hold_length_s (2.5s)."""
    return Config.model_validate(_VALID_CONFIG).field.framing_defaults.hold_length_s


def _agility_hold_length() -> float:
    """agility framing_defaults.hold_length_s (1.5s) via a sport=agility config overlay."""
    cfg = copy.deepcopy(_VALID_CONFIG)
    cfg["field"] = {"sport": "agility", "event": "agility_standard"}
    return Config.model_validate(cfg).field.framing_defaults.hold_length_s


def _engine(thresholds, hold_length_s: float, **kw) -> DecisionEngine:
    return DecisionEngine(
        _two_cameras(), thresholds, fps=FPS, hold_length_s=hold_length_s, **kw
    )


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _acquire(eng: DecisionEngine, cam: str, *, other: str, t0: int = 0) -> int:
    """Drive a steady lead until ``cam`` is the live incumbent past its dwell; next free tick."""
    t = t0
    for _ in range(400):
        eng.tick([_sc(cam, 0.85, t), _sc(other, 0.10, t)], alive={cam: True, other: True})
        t += 1
        # Stop once cam is live AND its dwell/cooldown have cleared (so a later challenger
        # would otherwise be free to cut — isolating the hold as the only suppressor).
        if eng.target == cam and eng.dwell_elapsed >= eng.min_dwell_ticks and eng.cooldown_remaining == 0:
            break
    assert eng.target == cam
    return t


def test_action_hold_suppresses_and_caps(thresholds) -> None:
    """An action hold suppresses a qualified cut; force-releases at the max-cap.

    cam_a is the live incumbent (dwell+cooldown cleared). cam_b then fully qualifies (steady
    lead, debounce sustained). While ``action`` is held, NO cut fires — even past the point
    cam_b qualifies. Once the hold is held PAST its cap, it force-releases and the (still
    qualified) cut to cam_b fires.
    """
    cap = 20  # short cap so the force-release is reached within the test
    eng = _engine(thresholds, _disc_dog_hold_length(), action_hold_cap_ticks=cap)
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    held = HoldInput(action=True)
    cut_while_held = False
    cut_after_cap = None
    for i in range(cap + 10):
        d = eng.tick(
            [_sc(_CAM_A, 0.20, t), _sc(_CAM_B, 0.95, t)],  # cam_b fully qualifies
            alive={_CAM_A: True, _CAM_B: True},
            holds=held,
        )
        if i < cap and d.target == _CAM_B:
            cut_while_held = True
        if d.target == _CAM_B and cut_after_cap is None:
            cut_after_cap = i
        t += 1

    assert not cut_while_held, "a cut fired while the action hold was active (before the cap)"
    assert cut_after_cap is not None, "the hold never force-released at the cap (stuck-hold freeze)"
    assert cut_after_cap >= cap - 1, (
        f"cut at i={cut_after_cap} fired before the action cap {cap} (cap not enforced)"
    )


def test_occlusion_hold_bounded(thresholds) -> None:
    """Occlusion hold suppresses switching for hold_length_s-derived ticks, then auto-expires.

    disc_dog hold_length_s = 2.5s → at FPS=30 that is ticks_from_seconds(2.5, 30) = 75 ticks.
    The cap (120) is larger, so the effective bound is the 75-tick hold_length_s. On the rising
    edge of ``occlusion`` the hold arms for 75 ticks; switching is suppressed for exactly those
    ticks; then it auto-expires and a qualified cut resumes.

    Tick-by-tick countdown:
      edge tick     : occlusion_hold_remaining set to min(75, 120) = 75, decremented to 74
      next 73 ticks : remaining 73..1 → still ACTIVE → suppressed
      expiry tick   : remaining hits 0 → hold inactive → qualified cut may fire
    """
    hl = _disc_dog_hold_length()
    bound = ticks_from_seconds(hl, FPS)
    assert bound == 75
    eng = _engine(thresholds, hl, occlusion_hold_cap_ticks=120)
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    occ = HoldInput(occlusion=True)
    suppressed_ticks = 0
    expired_at = None
    # Hold occlusion for the full bound; cam_b fully qualifies throughout.
    for i in range(bound + 30):
        d = eng.tick(
            [_sc(_CAM_A, 0.20, t), _sc(_CAM_B, 0.95, t)],
            alive={_CAM_A: True, _CAM_B: True},
            holds=occ,
        )
        if d.target == _CAM_A:
            suppressed_ticks += 1
        if d.target == _CAM_B and expired_at is None:
            expired_at = i
        t += 1

    assert expired_at is not None, "occlusion hold never expired (no cut ever resumed)"
    # Switching was suppressed for ~bound ticks (the hold_length_s window), then resumed.
    assert expired_at >= bound - 1, (
        f"occlusion expired at i={expired_at}, earlier than the {bound}-tick hold_length_s bound"
    )


def test_occlusion_cap_bounds_a_long_hold_length(thresholds) -> None:
    """The cap bounds even a hold_length_s longer than the cap (the effective bound is the min).

    Here the cap (10 ticks) is SHORTER than the disc_dog hold_length_s (75 ticks), so the
    effective occlusion bound is the 10-tick cap — the show is never frozen past the cap.
    """
    hl = _disc_dog_hold_length()  # 2.5s → 75 ticks
    cap = 10
    eng = _engine(thresholds, hl, occlusion_hold_cap_ticks=cap)
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    occ = HoldInput(occlusion=True)
    cut_at = None
    for i in range(cap + 20):
        d = eng.tick(
            [_sc(_CAM_A, 0.20, t), _sc(_CAM_B, 0.95, t)],
            alive={_CAM_A: True, _CAM_B: True},
            holds=occ,
        )
        if d.target == _CAM_B and cut_at is None:
            cut_at = i
        t += 1
    assert cut_at is not None, "the cap did not bound a hold_length_s longer than the cap"
    assert cut_at < ticks_from_seconds(hl, FPS), (
        "the cut waited the full hold_length_s — the cap did not bound it"
    )


def test_agility_occlusion_bound_is_shorter(thresholds) -> None:
    """The agility hold_length_s (1.5s → 45 ticks) bound differs from disc_dog (2.5s → 75)."""
    disc = ticks_from_seconds(_disc_dog_hold_length(), FPS)
    agi = ticks_from_seconds(_agility_hold_length(), FPS)
    assert (disc, agi) == (75, 45)

    eng = _engine(thresholds, _agility_hold_length(), occlusion_hold_cap_ticks=120)
    t = _acquire(eng, _CAM_A, other=_CAM_B)
    # The engine derived the agility 45-tick bound (not the disc 75-tick one).
    assert eng.occlusion_hold_ticks == agi


def test_feed_death_wins_over_hold(thresholds) -> None:
    """A feed-death during an active hold still emergency-cuts — death wins over hold (DEC-06)."""
    eng = _engine(thresholds, _disc_dog_hold_length())
    t = _acquire(eng, _CAM_B, other=_CAM_A)
    assert eng.target == _CAM_B

    # Both an action AND occlusion hold are active — yet cam_b's feed dies. The emergency cut
    # must still fire off the dead live feed to cam_a (the only alive camera).
    held = HoldInput(action=True, occlusion=True)
    d = eng.tick(
        [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.95, t)],
        alive={_CAM_A: True, _CAM_B: False},
        holds=held,
    )
    assert d.target == _CAM_A, "a hold suppressed the feed-death emergency cut (death must win)"
    assert d.reason == "feed_emergency"


def test_hold_reason_when_suppressing(thresholds) -> None:
    """A tick where a qualified switch is suppressed by a hold reports reason == 'hold'."""
    eng = _engine(thresholds, _disc_dog_hold_length())
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    # Build cam_b's challenger streak under no hold first (so the next tick would cut), then
    # apply the hold on the tick the cut would fire and assert it is reported as 'hold'.
    occ = HoldInput(occlusion=True)
    saw_hold_reason = False
    for _ in range(eng.debounce_N + 3):
        d = eng.tick(
            [_sc(_CAM_A, 0.20, t), _sc(_CAM_B, 0.95, t)],
            alive={_CAM_A: True, _CAM_B: True},
            holds=occ,
        )
        if d.reason == "hold":
            saw_hold_reason = True
        # The hold must keep cam_a live throughout.
        assert d.target == _CAM_A
        t += 1
    assert saw_hold_reason, "a hold-suppressed qualified switch never reported reason == 'hold'"
