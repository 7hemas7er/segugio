"""Phase-3 combined cross-scenario suite — the high-value mode INTERACTIONS no single plan owns.

The 03-01/02/03 suites each test one concern in isolation (hysteresis, holds, feed-death,
override). This file proves the three high-value COMBINED scenarios from 03-CONTEXT §Specific
Ideas — where two or more of those concerns collide in one tick-loop — and asserts the two hard
safety invariants (03-VALIDATION §Two Hard Safety Invariants) as REUSABLE helpers applied in
EVERY combined scenario:

  1. ``assert_no_decision_outside_guard`` — the aired ``target`` changes ONLY on a tick whose
     ``Decision.reason != "none"`` (DEC-01: no unguarded switch);
  2. ``assert_never_airs_dead_feed`` — ``alive[target] is True OR target == "SAFE"`` on EVERY
     tick (DEC-06: a dead feed is never on air, even under override or a hold).

The three combined scenarios:
  * ``test_force_release_resume`` — operator force → hold → release → qualified auto-resume
    (override × auto-resume; RBT-03 as a combined invariant-asserted run);
  * ``test_hold_through_occlusion_then_release`` — an occlusion hold suppresses a switch-worthy
    challenger window, then auto-expiry lets the qualified cut through (holds × auto-switch);
  * ``test_live_feed_death_mid_hold_death_wins`` — a hold is active, then the LIVE feed dies
    mid-hold; the engine STILL emergency-cuts (death > hold) and never airs the dead feed
    (feed-death × holds — the T-3-02 availability mitigation).

Drives the shipped ``score_stream`` / ``feed_death`` substrates with ``np.random.default_rng(SEED)``
and reuses the ``_two_cameras`` / ``_sc`` / ``_acquire`` builders established by the single-concern
03-02/03-03 suites. A final focused test closes the pure module's last coverage branch.
"""

from __future__ import annotations

import numpy as np

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET, Decision, HoldInput, Mode, OverrideCmd
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.synth import feed_death
from tests.conftest import FPS, SEED

_CAM_A = "cam_a"  # the SAFE camera (config-declared first → no-incumbent tiebreak)
_CAM_B = "cam_b"
_CAM_IDS = [_CAM_A, _CAM_B]


def _two_cameras() -> list[Camera]:
    """Two cameras (cam_a is_safe), each a single full-frame neutral zone (multiplier 1.0)."""
    return [
        Camera(
            id=cid,
            role=Role.main_wide,
            obs_scene="WIDE",
            is_safe=(cid == _CAM_A),
            zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
        )
        for cid in _CAM_IDS
    ]


def _engine(thresholds, **kw) -> DecisionEngine:
    return DecisionEngine(_two_cameras(), thresholds, fps=FPS, **kw)


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _acquire(eng: DecisionEngine, cam: str, *, other: str, t0: int = 0) -> int:
    """Drive a steady lead until ``cam`` is the live incumbent past its dwell; next free tick.

    Stops once ``cam`` is live AND its dwell/cooldown have cleared, so a later challenger would
    otherwise be free to cut — isolating the hold / override as the only suppressor under test.
    """
    t = t0
    for _ in range(400):
        eng.tick([_sc(cam, 0.85, t), _sc(other, 0.10, t)], alive={cam: True, other: True})
        t += 1
        if (
            eng.target == cam
            and eng.dwell_elapsed >= eng.min_dwell_ticks
            and eng.cooldown_remaining == 0
        ):
            break
    assert eng.target == cam, f"failed to acquire {cam} as incumbent"
    return t


# --------------------------------------------------------------------------- #
# The two hard safety invariants, as reusable assertions over a whole run.     #
# --------------------------------------------------------------------------- #


def assert_no_decision_outside_guard(decisions: list[Decision], initial_target: str) -> None:
    """DEC-01: the aired ``target`` changes on a tick IFF that tick reported ``reason != "none"``.

    A target change with ``reason == "none"`` is an UNGUARDED switch (forbidden); a reported
    reason with no target change is only allowed for the ``"hold"`` and ``"override"`` reasons,
    which are mode-level events (a hold SUPPRESSING a cut, or a force on the already-live camera)
    that do not move the target. Any other reason MUST coincide with an actual target change.
    """
    prev = initial_target
    for d in decisions:
        changed = d.target != prev
        if changed:
            assert d.reason != "none", (
                f"tick {d.tick}: target changed {prev!r}→{d.target!r} with reason 'none' "
                f"(unguarded switch — DEC-01 violation)"
            )
        else:
            # No target change → only the mode-level event reasons may fire (hold / override).
            assert d.reason in ("none", "hold", "override", "override_dead_fallback"), (
                f"tick {d.tick}: reason {d.reason!r} reported a cut but the target did not "
                f"change (DEC-01)"
            )
        prev = d.target


def assert_never_airs_dead_feed(
    steps: list[tuple[Decision, dict[str, bool]]]
) -> None:
    """DEC-06: ``alive[target] is True OR target == "SAFE"`` on EVERY tick (no dead feed on air).

    Takes ``(decision, alive_map)`` pairs — the alive map is the EXACT liveness input the engine
    saw on the tick that produced ``decision`` — so the invariant is checked against the same
    liveness the engine acted on (no absolute/relative tick-index aliasing).
    """
    for d, alive in steps:
        assert d.target == SAFE_TARGET or alive.get(d.target, False) is True, (
            f"tick {d.tick}: aired target {d.target!r} is not alive (alive={alive}) — "
            f"dead feed on air (DEC-06 violation)"
        )


# --------------------------------------------------------------------------- #
# Combined high-value scenario 1: force → hold → release → qualified resume.   #
# --------------------------------------------------------------------------- #


def test_force_release_resume(thresholds) -> None:
    """Operator force → hold the override → release → auto-resume ONLY after full qualification.

    One continuous tick-loop, both shared invariants asserted over the whole run:
      (1) force cam_b (alive) → cam_b aired immediately, in OVERRIDE (dwell/cooldown bypassed);
      (2) hold the override across many ticks where cam_a out-scores it — no auto-expire (D-04);
      (3) release → no snap to argmax on the release tick (D-06);
      (4) cam_a then wins the full hysteresis + debounce_N + min_dwell qualification → auto-resume
          fires via the normal-switch guard (reason "auto_switch"), and ONLY then.
    """
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    n = 400
    # cam_a stays alive the whole run; cam_b stays alive too (this scenario is override-driven,
    # not feed-death-driven — the death interaction is scenario 3 below).
    events = feed_death(np.random.default_rng(SEED), _CAM_IDS, n)
    alive_by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        alive_by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive

    steps: list[tuple[Decision, dict[str, bool]]] = []
    initial = eng.target
    rel = 0

    # ----- (1) FORCE cam_b ----------------------------------------------------------------- #
    alive = alive_by_tick[rel]
    d = eng.tick(
        [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.80, t)],
        alive=alive,
        override=OverrideCmd(force_cam=_CAM_B),
    )
    steps.append((d, alive))
    assert d.target == _CAM_B and d.mode == Mode.override, "force did not air cam_b in override"
    t += 1
    rel += 1

    # ----- (2) HOLD the override: cam_a dominates but no release is sent (D-04) ------------- #
    for _ in range(60):
        alive = alive_by_tick[rel]
        d = eng.tick(
            [_sc(_CAM_A, 0.99, t), _sc(_CAM_B, 0.05, t)],
            alive=alive,
        )
        steps.append((d, alive))
        assert d.mode == Mode.override, "override auto-expired without an explicit release (D-04)"
        assert d.target == _CAM_B, "override drifted off the forced camera with no release"
        t += 1
        rel += 1

    # ----- (3) RELEASE: must NOT snap to the cam_a argmax on the release tick (D-06) -------- #
    alive = alive_by_tick[rel]
    d = eng.tick(
        [_sc(_CAM_A, 0.99, t), _sc(_CAM_B, 0.05, t)],
        alive=alive,
        override=OverrideCmd(release=True),
    )
    steps.append((d, alive))
    assert d.mode == Mode.auto, "release did not re-enter AUTO"
    assert d.target == _CAM_B, "release snapped straight to argmax (D-06 violation)"
    assert eng.override_cam is None, "release must clear the sticky override_cam"
    release_rel = rel
    t += 1
    rel += 1

    # ----- (4) AUTO-RESUME only after the full hysteresis + min_dwell qualification --------- #
    resumed_at = None
    for _ in range(120):
        alive = alive_by_tick[rel]
        d = eng.tick(
            [_sc(_CAM_A, 0.95, t), _sc(_CAM_B, 0.05, t)],  # cam_a the steady winner
            alive=alive,
        )
        steps.append((d, alive))
        if d.target == _CAM_A and resumed_at is None:
            resumed_at = rel
            assert d.reason == "auto_switch", "auto-resume must fire via the normal-switch guard"
        t += 1
        rel += 1

    assert resumed_at is not None, "auto-resume never fired after release (resume stuck)"
    assert resumed_at > release_rel, "auto-resume fired on/before the release tick (no qualify)"

    # Both hard safety invariants over the WHOLE combined run.
    assert_no_decision_outside_guard([s[0] for s in steps], initial)
    assert_never_airs_dead_feed(steps)


# --------------------------------------------------------------------------- #
# Combined high-value scenario 2: hold through occlusion, then release lets    #
# the qualified cut through.                                                   #
# --------------------------------------------------------------------------- #


def test_hold_through_occlusion_then_release(thresholds) -> None:
    """An occlusion hold suppresses a switch-worthy challenger window, then auto-expiry cuts.

    cam_a is the live incumbent (dwell/cooldown cleared). cam_b then fully qualifies (steady
    lead). While ``occlusion`` is held the cut is SUPPRESSED for the whole bounded window
    (reason "hold", target unchanged); once the occlusion auto-expires the still-qualified cut
    to cam_b fires. Both shared invariants assert across the whole run.
    """
    # A short occlusion cap so the window is reached well within the test, but long enough to
    # span a switch-worthy challenger window (cam_b qualifies inside it).
    cap = 20
    eng = _engine(thresholds, occlusion_hold_cap_ticks=cap)
    t = _acquire(eng, _CAM_A, other=_CAM_B)

    n = 400
    events = feed_death(np.random.default_rng(SEED), _CAM_IDS, n)
    alive_by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        alive_by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive

    steps: list[tuple[Decision, dict[str, bool]]] = []
    initial = eng.target
    rel = 0
    occ = HoldInput(occlusion=True)

    suppressed_during_hold = 0
    cut_after_expiry_at = None
    saw_hold_reason = False

    # The effective occlusion bound is min(hold_length_s ticks, cap) = cap (cap is the shorter).
    for i in range(cap + 40):
        holding = i < cap  # hold occlusion for the bounded window, then drop it
        alive = alive_by_tick[rel]
        d = eng.tick(
            [_sc(_CAM_A, 0.20, t), _sc(_CAM_B, 0.95, t)],  # cam_b fully qualifies throughout
            alive=alive,
            holds=occ if holding else HoldInput(),
        )
        steps.append((d, alive))
        if holding and d.target == _CAM_A:
            suppressed_during_hold += 1
            if d.reason == "hold":
                saw_hold_reason = True
        if d.target == _CAM_B and cut_after_expiry_at is None:
            cut_after_expiry_at = i
        t += 1
        rel += 1

    assert suppressed_during_hold > 0, "the occlusion hold never suppressed the qualified cut"
    assert saw_hold_reason, "a hold-suppressed qualified switch never reported reason == 'hold'"
    assert cut_after_expiry_at is not None, "the qualified cut never fired after the hold expired"
    assert cut_after_expiry_at >= cap - 1, (
        f"the cut at i={cut_after_expiry_at} fired before the {cap}-tick occlusion bound "
        f"(the hold did not suppress for its full window)"
    )

    assert_no_decision_outside_guard([s[0] for s in steps], initial)
    assert_never_airs_dead_feed(steps)


# --------------------------------------------------------------------------- #
# Combined high-value scenario 3: live feed dies mid-hold — death wins.        #
# --------------------------------------------------------------------------- #


def test_live_feed_death_mid_hold_death_wins(thresholds) -> None:
    """A hold is active, then the LIVE feed dies mid-hold — the emergency cut STILL fires.

    cam_b is the live incumbent under BOTH an action and an occlusion hold. While the hold is
    active and cam_b is fully alive the engine holds cam_b (a hold legitimately suppresses a
    challenger). Then cam_b's feed DIES mid-hold: death must win over the hold (DEC-06) — the
    engine emergency-cuts to cam_a (the only alive camera) on the death tick and NEVER airs the
    dead cam_b feed. Both shared invariants assert across the whole run.
    """
    eng = _engine(thresholds)
    t = _acquire(eng, _CAM_B, other=_CAM_A)
    assert eng.target == _CAM_B

    n = 200
    death_at_rel = 15  # cam_b's feed dies partway through the held window, never recovers
    events = feed_death(
        np.random.default_rng(SEED), _CAM_IDS, n, death_at={_CAM_B: death_at_rel}
    )
    alive_by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        alive_by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive

    steps: list[tuple[Decision, dict[str, bool]]] = []
    initial = eng.target
    held = HoldInput(action=True, occlusion=True)  # BOTH holds active the whole window

    emergency_fired_at = None
    for rel in range(40):
        alive = alive_by_tick[rel]
        d = eng.tick(
            [_sc(_CAM_A, 0.30, t), _sc(_CAM_B, 0.95, t)],  # cam_b scores higher but dies mid-run
            alive=alive,
            holds=held,
        )
        steps.append((d, alive))
        if rel < death_at_rel:
            # cam_b alive + held → the hold legitimately keeps cam_b live (no challenger cut).
            assert d.target == _CAM_B, f"rel={rel}: left the held live camera while it was alive"
        else:
            # cam_b dead → death wins over the hold: must be off the dead feed (cam_a/SAFE).
            assert d.target != _CAM_B, f"rel={rel}: aired the DEAD held feed (death must win)"
            assert d.target == _CAM_A, f"rel={rel}: emergency cut did not go to the alive cam_a"
            if emergency_fired_at is None:
                emergency_fired_at = rel
                assert d.reason == "feed_emergency", (
                    "the death-wins cut must report reason 'feed_emergency'"
                )
        t += 1

    assert emergency_fired_at == death_at_rel, (
        f"emergency cut fired at rel={emergency_fired_at}, expected the death tick {death_at_rel} "
        f"(death did not win over the active hold immediately)"
    )

    assert_no_decision_outside_guard([s[0] for s in steps], initial)
    assert_never_airs_dead_feed(steps)


# --------------------------------------------------------------------------- #
# Coverage-closing focused test — the remaining real behavior branch.         #
# --------------------------------------------------------------------------- #


def test_live_feed_dead_is_false_at_safe(thresholds) -> None:
    """``live_feed_dead()`` is False whenever the aired target is the SAFE sentinel (DEC-06 guard).

    The defensive SAFE-is-never-dead branch (``engine.py`` ``live_feed_dead`` early return): SAFE
    is the fallback, not a feed, so it can never be "dead". This branch is unreachable through the
    ``feed_emergency`` transition (its ``source`` is only ``auto``/``override``, never ``safe``),
    but the predicate is a pure read and the SAFE-state guard is real behavior — assert it
    directly so the invariant is regression-locked, closing the pure module to ~100% coverage.
    """
    eng = _engine(thresholds)
    # A freshly-constructed engine starts in SAFE with target == "SAFE".
    assert eng.state == "safe"
    assert eng.target == SAFE_TARGET
    # SAFE is never "dead" — the early-return guard holds even with no eligible cameras computed.
    assert eng.live_feed_dead() is False
