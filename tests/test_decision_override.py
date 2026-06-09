"""RBT-03 override suite — force → death → recover → release → auto-resume qualification.

The one operator-in-the-loop affordance in an otherwise operator-less system. The subtle
correctness lives in two interactions (03-CONTEXT D-03..D-06, 03-RESEARCH Pitfalls 5/6):

  * **override-through-feed-death (D-03):** a forced-but-dead camera shows SAFE / best-live
    (never the dead feed) while STAYING in OVERRIDE mode, and snaps back to the forced camera
    the instant its feed recovers; override ends only on explicit release (D-04, no auto-expire);
  * **non-flickery auto-resume (D-06):** after release, the next auto cut fires only once a
    candidate has won the FULL hysteresis + ``debounce_N`` + ``min_dwell`` qualification — no
    snap to the current argmax.

The two hard safety invariants asserted in EVERY override scenario (03-VALIDATION):
  1. ``target`` changes only on a tick whose ``reason != "none"`` (DEC-01);
  2. ``alive[target] is True OR target == "SAFE"`` for ALL ticks — including the forced-but-dead
     window (DEC-06: a dead feed is never aired, even under override).

Mirrors the tick-loop replay style of ``test_decision_feeddeath.py`` / ``test_decision_holds.py``
and drives the shipped ``feed_death`` substrate for the force→die→recover liveness timeline.
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET, Mode, OverrideCmd
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.synth import feed_death
from tests.conftest import FPS, SEED

_CAM_A = "cam_a"  # the SAFE camera (config-declared first → no-incumbent tiebreak)
_CAM_B = "cam_b"


def _two_cameras() -> list[Camera]:
    """Two cameras (cam_a is_safe), each a single full-frame neutral zone."""
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


def _engine(thresholds) -> DecisionEngine:
    return DecisionEngine(_two_cameras(), thresholds, fps=FPS)


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _assert_safety_invariants(decision, alive: dict[str, bool], prev_target: str) -> None:
    """The two hard safety invariants on a single tick (DEC-01 + DEC-06).

    (1) the aired target changed ONLY if the engine reported a firing reason; (2) the aired
    target is alive OR the SAFE sentinel (a dead feed is never on air — even under override).
    """
    changed = decision.target != prev_target
    assert changed == (decision.reason != "none"), (
        f"target change ({prev_target!r}→{decision.target!r}) disagrees with "
        f"reason={decision.reason!r} (DEC-01)"
    )
    assert decision.target == SAFE_TARGET or alive.get(decision.target, False) is True, (
        f"aired target {decision.target!r} is not alive (alive={alive}) — dead feed on air"
    )


def _acquire_auto(eng: DecisionEngine, cam: str, *, other: str, t0: int = 0) -> int:
    """Drive a steady AUTO lead until ``cam`` is the live incumbent; return the next free tick."""
    t = t0
    for _ in range(200):
        eng.tick([_sc(cam, 0.85, t), _sc(other, 0.10, t)], alive={cam: True, other: True})
        t += 1
        if eng.target == cam:
            break
    assert eng.target == cam, f"failed to acquire {cam} as incumbent"
    return t


# --------------------------------------------------------------------------- #
# Focused unit tests                                                           #
# --------------------------------------------------------------------------- #


def test_ambiguous_override_cmd_rejected_at_construction() -> None:
    """A contradictory ``OverrideCmd(force_cam=..., release=True)`` raises at construction (WR-04).

    Force and release are mutually-exclusive operator intents. A command setting BOTH is
    malformed and must be rejected at the input boundary (construction) — surfacing the
    contradiction loudly rather than letting ``tick()`` silently apply the force branch and
    discard the release. Validating here keeps ``tick()`` exception-free (T-3-04).
    """
    with pytest.raises(ValueError, match="contradictory"):
        OverrideCmd(force_cam=_CAM_B, release=True)

    # The two valid, unambiguous shapes still construct cleanly (no false positive).
    assert OverrideCmd(force_cam=_CAM_B).force_cam == _CAM_B
    assert OverrideCmd(release=True).release is True
    assert OverrideCmd() == OverrideCmd()  # the no-op (both unset) is still valid


def test_force_is_immediate(thresholds) -> None:
    """A force on an ALIVE camera sets ``target == cam`` THIS tick, bypassing dwell/debounce/cooldown.

    cam_a is the live incumbent with a FRESH dwell + cooldown (just acquired) and cam_b has NO
    challenger streak — a normal cut to cam_b would be impossible. Yet forcing cam_b makes it the
    live target immediately (D-05: an operator command is applied at once, not auto-switch noise).
    """
    eng = _engine(thresholds)
    t = _acquire_auto(eng, _CAM_A, other=_CAM_B)
    assert eng.target == _CAM_A
    # cam_a was just acquired: a normal auto cut is blocked by its fresh dwell/cooldown.
    assert eng.dwell_elapsed < eng.min_dwell_ticks or eng.cooldown_remaining > 0

    d = eng.tick(
        [_sc(_CAM_A, 0.95, t), _sc(_CAM_B, 0.10, t)],  # cam_b is LOWER-scored, no streak
        alive={_CAM_A: True, _CAM_B: True},
        override=OverrideCmd(force_cam=_CAM_B),
    )
    assert d.target == _CAM_B, "force did not immediately air the forced camera"
    assert d.mode == Mode.override
    assert eng.override_cam == _CAM_B
    assert d.reason != "none", "an immediate force must report a firing reason (DEC-01)"


def test_force_dead_camera_shows_safe_not_dead(thresholds) -> None:
    """Forcing an ALREADY-DEAD camera enters OVERRIDE, sets override_cam, but airs SAFE/best-live.

    The dead forced feed is NEVER aired (DEC-06 under override). With no other camera alive the
    aired target is the SAFE sentinel; override_cam stays sticky so it can snap back on recovery.
    """
    eng = _engine(thresholds)
    t = _acquire_auto(eng, _CAM_A, other=_CAM_B)

    # Force cam_b while cam_b is DEAD and cam_a (the only alive cam) is the SAFE camera.
    d = eng.tick(
        [_sc(_CAM_A, 0.40, t), _sc(_CAM_B, 0.99, t)],  # cam_b higher but DEAD
        alive={_CAM_A: True, _CAM_B: False},
        override=OverrideCmd(force_cam=_CAM_B),
    )
    assert eng.override_cam == _CAM_B, "override_cam must be set even when the forced cam is dead"
    assert d.mode == Mode.override, "must enter OVERRIDE even forcing a dead camera"
    assert d.target != _CAM_B, "a dead forced feed must never be aired (DEC-06)"
    # best-live alternative here is cam_a (the only alive camera).
    assert d.target == _CAM_A


def test_no_auto_expire(thresholds) -> None:
    """Override held for many ticks NEVER auto-resumes — release is manual-only (D-04).

    Force cam_b (alive), then drive a long run where cam_a steadily out-scores it. Without an
    explicit release the engine must remain in OVERRIDE on cam_b for the whole run (no timeout).
    """
    eng = _engine(thresholds)
    t = _acquire_auto(eng, _CAM_A, other=_CAM_B)

    # Force cam_b live.
    eng.tick(
        [_sc(_CAM_A, 0.10, t), _sc(_CAM_B, 0.90, t)],
        alive={_CAM_A: True, _CAM_B: True},
        override=OverrideCmd(force_cam=_CAM_B),
    )
    assert eng.target == _CAM_B and eng.mode_is_override
    t += 1

    # Many ticks, cam_a dominates — but no release command is sent.
    for _ in range(300):
        d = eng.tick(
            [_sc(_CAM_A, 0.99, t), _sc(_CAM_B, 0.05, t)],
            alive={_CAM_A: True, _CAM_B: True},
        )
        assert d.mode == Mode.override, "override auto-expired without an explicit release (D-04)"
        assert d.target == _CAM_B, "override drifted off the forced camera with no release"
        t += 1


def test_release_does_not_snap_to_argmax(thresholds) -> None:
    """``release`` re-enters AUTO but does NOT immediately jump to the current argmax (D-06).

    On the release tick, even though cam_a is the argmax, the aired target must NOT change to it:
    auto-resume requires the full hysteresis + debounce_N + min_dwell qualification first.
    """
    eng = _engine(thresholds)
    t = _acquire_auto(eng, _CAM_A, other=_CAM_B)
    eng.tick(
        [_sc(_CAM_A, 0.10, t), _sc(_CAM_B, 0.90, t)],
        alive={_CAM_A: True, _CAM_B: True},
        override=OverrideCmd(force_cam=_CAM_B),
    )
    assert eng.target == _CAM_B
    t += 1

    # Release on a tick where cam_a is clearly the argmax. The aired target must HOLD on cam_b
    # (the last aired target) — no snap to cam_a on the release tick itself.
    d = eng.tick(
        [_sc(_CAM_A, 0.99, t), _sc(_CAM_B, 0.05, t)],
        alive={_CAM_A: True, _CAM_B: True},
        override=OverrideCmd(release=True),
    )
    assert eng.override_cam is None, "release must clear the sticky override_cam"
    assert d.mode == Mode.auto, "release must re-enter AUTO mode"
    assert d.target == _CAM_B, "release snapped to argmax — flickery resume (D-06 violation)"


# --------------------------------------------------------------------------- #
# RBT-03 combined-scenario test                                               #
# --------------------------------------------------------------------------- #


def test_force_death_recover_release_resume(thresholds) -> None:
    """The full locked RBT-03 sequence: force → die → recover → release → qualified auto-resume.

    One continuous tick-loop with both hard safety invariants asserted on EVERY tick:
      (1) force cam_b (alive) → cam_b is aired immediately (dwell/cooldown bypassed);
      (2) cam_b's feed dies → aired target becomes SAFE/best-live, mode STAYS override, cam_b not aired;
      (3) cam_b recovers → aired target snaps back to cam_b while still in override;
      (4) release → no immediate jump to argmax;
      (5) cam_a wins the full hysteresis + min_dwell qualification → auto-resume fires (reason
          "auto_switch"), and ONLY then.
    """
    eng = _engine(thresholds)
    t = _acquire_auto(eng, _CAM_A, other=_CAM_B)

    n = 400
    cam_ids = [_CAM_A, _CAM_B]
    # cam_b dies at tick 40 (relative to this timeline) and recovers 30 ticks later.
    death_at_rel = 40
    recover_after = 30
    events = feed_death(
        np.random.default_rng(SEED), cam_ids, n, death_at={_CAM_B: death_at_rel},
        recover_after=recover_after,
    )
    alive_by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        alive_by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive

    # ----- (1) FORCE cam_b (alive at rel-tick 0) ------------------------------------------- #
    rel = 0
    alive = alive_by_tick[rel]
    prev = eng.target
    d = eng.tick(
        [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.80, t)],
        alive=alive,
        override=OverrideCmd(force_cam=_CAM_B),
    )
    _assert_safety_invariants(d, alive, prev)
    assert d.target == _CAM_B and d.mode == Mode.override, "force did not air cam_b in override"
    t += 1
    rel += 1

    # ----- (2)+(3) run THROUGH the death + recovery window while override is HELD ---------- #
    saw_dead_fallback = False
    saw_snap_back = False
    while rel < death_at_rel + recover_after + 10:
        alive = alive_by_tick[rel]
        prev = eng.target
        d = eng.tick(
            [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.80, t)],
            alive=alive,
        )
        _assert_safety_invariants(d, alive, prev)
        assert d.mode == Mode.override, f"left OVERRIDE at rel={rel} without a release (D-03/D-04)"
        if not alive[_CAM_B]:
            # forced-but-dead window: cam_b must NEVER be aired; best-live is cam_a or SAFE.
            assert d.target != _CAM_B, f"rel={rel}: aired the DEAD forced feed (DEC-06)"
            saw_dead_fallback = True
        elif rel >= death_at_rel + recover_after:
            # recovered: the aired target must have snapped back to the forced camera.
            assert d.target == _CAM_B, f"rel={rel}: did not snap back to cam_b after recovery"
            saw_snap_back = True
        t += 1
        rel += 1

    assert saw_dead_fallback, "never observed the forced-but-dead SAFE/best-live fallback"
    assert saw_snap_back, "never observed the snap-back to cam_b on recovery"

    # ----- (4) RELEASE — must NOT snap to argmax on the release tick ----------------------- #
    alive = alive_by_tick[rel]
    prev = eng.target  # cam_b (snapped back, alive)
    d = eng.tick(
        [_sc(_CAM_A, 0.99, t), _sc(_CAM_B, 0.05, t)],  # cam_a is argmax
        alive=alive,
        override=OverrideCmd(release=True),
    )
    _assert_safety_invariants(d, alive, prev)
    assert d.mode == Mode.auto, "release did not re-enter AUTO"
    assert d.target == _CAM_B, "release snapped straight to argmax (D-06 violation)"
    assert eng.override_cam is None
    t += 1
    rel += 1

    # ----- (5) AUTO-RESUME only after the FULL hysteresis + min_dwell qualification -------- #
    resumed_at = None
    for _ in range(200):
        alive = alive_by_tick[rel]
        prev = eng.target
        d = eng.tick(
            [_sc(_CAM_A, 0.95, t), _sc(_CAM_B, 0.05, t)],  # cam_a steady winner
            alive=alive,
        )
        _assert_safety_invariants(d, alive, prev)
        if d.target == _CAM_A and resumed_at is None:
            resumed_at = rel
            assert d.reason == "auto_switch", "auto-resume must fire via the normal-switch guard"
        t += 1
        rel += 1

    assert resumed_at is not None, "auto-resume never fired after release (resume stuck)"
    # The resume could not have happened on the release tick itself (qualification takes time).
    assert resumed_at > death_at_rel + recover_after + 11, (
        "auto-resume fired too early — it must clear hysteresis + debounce_N + min_dwell first"
    )
