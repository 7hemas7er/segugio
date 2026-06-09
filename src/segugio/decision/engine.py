"""``DecisionEngine`` — the camera-switching FSM (a ``transitions.Machine`` wrapper).

The single authority on which camera is live (a camera id, or the ``"SAFE"`` sentinel).
It is a thin wrapper around a ``transitions.Machine`` with three operational-mode states
(``safe`` / ``auto`` / ``override``) and the live camera id held as a model attribute. The
guarded transitions are the ONLY path by which the live target changes — the mechanical
guarantee behind DEC-01.

Per-decision traceability (this plan, 03-01 — the core auto-switching FSM):

  * DEC-01 (decision only from a guard): ``self.target`` is mutated ONLY inside a transition
    ``before`` callback (``_set_target_safe`` / ``_promote_challenger``) whose ``conditions``
    already passed. ``tick()`` computes the best ELIGIBLE candidate with a pure ``max(...)``
    but NEVER assigns ``self.target`` directly; it only FIRES triggers. A trigger whose guard
    fails is a silent no-op (``transitions``-verified) → the target is unchanged.
  * DEC-02 (hysteresis): a challenger camera must exceed the incumbent's score by
    ``hysteresis_margin`` to even become a challenger, then SUSTAIN that lead for
    ``debounce_N`` consecutive ticks (the ``challenger_streak`` counter) before a cut fires.
    A challenger that drops below the margin on any tick resets the streak.
  * DEC-02 (dwell): no auto-switch fires until ``dwell_elapsed >= min_dwell_ticks`` on the
    current target. ``dwell_elapsed`` resets to 0 on every target change.
  * DEC-02 (cooldown): no auto-switch fires while ``cooldown_remaining > 0``;
    ``cooldown_remaining`` is set to ``cooldown_ticks`` on every target change and decremented
    each tick to a floor of 0.
  * DEC-02 (no-chase): replaying ``score_stream(ping_pong)`` / ``(tie)`` yields <= 1
    transition after warm-up (the margin+debounce+dwell+cooldown gates hold the incumbent).
  * Cold start: begins in ``safe`` with ``target == "SAFE"``; switches to the first camera
    that clears the hysteresis upper threshold AND sustains ``debounce_N``.
  * Fail-safe (T-3-04, "nessun crash ammesso"): a NaN/inf/out-of-[0,1] ``CameraScore.score``
    makes that camera an ineligible candidate (never challenger, never target);
    ``tick()`` never raises.

Later plans extend (do NOT rewrite) this surface: 03-02 adds the ``feed_emergency`` edge +
hold guards (the seams ``_eligible`` / candidate selection leave open); 03-03 adds
``force`` / ``release`` (the ``override`` state is already declared).

Imports only ``transitions`` + stdlib ``math`` + the pure ``segugio.framing`` surface — no
torch / ultralytics / cyndilib / obsws at module top level (the Phase-1 lazy-import boundary).
Clock-free and RNG-free: time is the injected integer ``tick`` (the ``CameraScore.tick`` of
the per-tick batch); there is zero randomness and zero wall-clock here.
"""

from __future__ import annotations

import math

from transitions import Machine

from ..framing.signals import CameraScore
from .clocks import ticks_from_seconds
from .signals import SAFE_TARGET, Decision, HoldInput, Mode, OverrideCmd

__all__ = ["DecisionEngine"]

# The FSM's operational-mode states (mirror Mode). The selected camera id is a model
# attribute, NOT one state per camera (keeps the transition graph O(1) edges).
_STATES = ["safe", "auto", "override"]

_TRANSITIONS = [
    # Cold start / no eligible camera → SAFE. The `before` callback is the ONLY place the
    # target is set to the SAFE sentinel.
    {
        "trigger": "to_safe",
        "source": "*",
        "dest": "safe",
        "before": "_set_target_safe",
    },
    # Feed-death emergency (DEC-06, D-01): the LIVE feed died → cut THIS tick to the best
    # alive camera, bypassing dwell/cooldown. Fires ABOVE the normal auto_switch (RESEARCH
    # §Pattern 3 priority). `_emergency_cut` resets the new target's clocks so it then gets
    # NORMAL protection (Pitfall 4). NOTE: NO `holding` guard here — death wins over hold.
    {
        "trigger": "feed_emergency",
        "source": ["auto", "override"],
        "dest": "auto",
        "conditions": ["live_feed_dead", "has_alive_candidate"],
        "before": "_emergency_cut",
    },
    # Feed-death emergency with NO alive candidate → route to the SAFE sentinel. The whole
    # robustness constraint ("nessun crash ammesso", SAFE fallback) hinges on this edge.
    {
        "trigger": "feed_emergency",
        "source": ["auto", "override"],
        "dest": "safe",
        "conditions": ["live_feed_dead"],
        "unless": ["has_alive_candidate"],
        "before": "_set_target_safe",
    },
    # Normal auto-switch: fires ONLY if the challenger cleared hysteresis + sustained
    # debounce_N AND dwell elapsed AND cooldown clear. `_promote_challenger` is the ONLY
    # place the target changes on a normal cut (DEC-01).
    {
        "trigger": "auto_switch",
        "source": ["auto", "safe"],
        "dest": "auto",
        "conditions": ["challenger_qualified", "dwell_elapsed_ok", "cooldown_clear"],
        "unless": ["holding"],  # an active hold makes the normal cut a no-op (DEC-03/04)
        "before": "_promote_challenger",
    },
]


def _is_finite_score(score: float) -> bool:
    """True iff ``score`` is finite AND in [0, 1] (an eligible-candidate gate; T-3-04).

    A NaN/inf/out-of-range score must make its camera ineligible rather than poisoning the
    ``max(...)`` selection. Mirrors Phase-2 ``_is_finite_detection``.
    """
    return math.isfinite(score) and 0.0 <= score <= 1.0


class DecisionEngine:
    """Tick-driven camera-switching FSM (the auto-switching core; DEC-01/DEC-02).

    Construct once with the config ``cameras`` (declaration order is the no-incumbent
    tiebreak order, D-07), the validated ``thresholds``, and an injected ``fps`` (the
    seconds→ticks bridge; ``fps`` is an ARGUMENT, never read from config). Drive it with one
    ``tick(scores, alive, holds, override)`` call per tick.

    Args:
        cameras: the config ``list[Camera]`` (declaration order defines the tiebreak order).
        thresholds: the validated ``Thresholds`` (``hysteresis_margin`` / ``debounce_N`` /
            ``min_dwell`` seconds / ``cooldown`` seconds).
        fps: injected frames-per-second for the seconds→ticks conversion (default 30.0).
        hold_length_s: per-discipline occlusion-hold length in SECONDS
            (``Config.field.framing_defaults.hold_length_s``; disc_dog 2.5 / agility 1.5).
            Converted ONCE to ticks here via ``ticks_from_seconds`` (DEC-04 bound).
        action_hold_cap_ticks: MANDATORY safety max-cap (in ticks) for the action hold — once
            reached the hold force-releases even if the input is still set (no stuck-hold freeze).
        occlusion_hold_cap_ticks: MANDATORY safety max-cap (in ticks) for the occlusion hold;
            the effective occlusion bound is ``min(occlusion_hold_ticks, this cap)``.
    """

    def __init__(
        self,
        cameras,
        thresholds,
        fps: float = 30.0,
        hold_length_s: float = 2.5,
        action_hold_cap_ticks: int = 90,
        occlusion_hold_cap_ticks: int = 90,
    ) -> None:
        # Insertion-ordered camera id list (config declaration order) — the deterministic
        # no-incumbent tiebreak order (D-07). Mirrors the scorer's ordered-dict precedent.
        self.cam_ids: list[str] = [cam.id for cam in cameras]

        # Hysteresis / debounce parameters (read directly; debounce_N is already in ticks).
        self.hysteresis_margin: float = float(thresholds.hysteresis_margin)
        self.debounce_N: int = int(thresholds.debounce_N)

        # Seconds→ticks conversion happens ONCE here (fps injected, not from config).
        self.min_dwell_ticks: int = ticks_from_seconds(thresholds.min_dwell, fps)
        self.cooldown_ticks: int = ticks_from_seconds(thresholds.cooldown, fps)

        # Hold bounds (DEC-03/DEC-04). The occlusion hold auto-expires after the per-discipline
        # hold_length_s (converted to ticks once). EVERY hold carries a MANDATORY tick max-cap
        # so a stuck/forgotten hold can never freeze the show (the guardrail). The effective
        # occlusion bound is the MIN of the hold_length_s bound and its cap.
        self.occlusion_hold_ticks: int = ticks_from_seconds(hold_length_s, fps)
        self.action_hold_cap_ticks: int = int(action_hold_cap_ticks)
        self.occlusion_hold_cap_ticks: int = int(occlusion_hold_cap_ticks)
        self._occlusion_effective_ticks: int = min(
            self.occlusion_hold_ticks, self.occlusion_hold_cap_ticks
        )

        # Integer clocks / counters on the model (advanced at the top of tick()). Plain ints
        # — transitions manages states + guard dispatch, NOT these counters (RESEARCH P2).
        self.dwell_elapsed: int = 0
        self.cooldown_remaining: int = 0
        self.challenger_id: str | None = None
        self.challenger_streak: int = 0

        # Hold clocks (integer ticks, advanced at the top of tick()). `action_hold_age` counts
        # UP while the action input is set (force-released at the cap); `occlusion_hold_remaining`
        # counts DOWN from the effective bound on the rising edge of the occlusion input.
        self.action_hold_age: int = 0
        self.occlusion_hold_remaining: int = 0
        self._prev_occlusion: bool = False  # for rising-edge detection

        # The live aired target — a camera id or the SAFE sentinel. Assigned ONLY inside a
        # transition callback after construction.
        self.target: str = SAFE_TARGET

        # Per-tick scratch (set at the top of tick(), read by the guard predicates + the
        # `before` callbacks). Kept on the model so `transitions` callbacks can read them.
        self._best_eligible: str | None = None
        # The set of cameras alive THIS tick (alive AND finite-scored) and the eligible-only
        # score map — the feed-death guards (`live_feed_dead`/`has_alive_candidate`) and the
        # `_emergency_cut` callback read these (they cannot take args via `transitions`).
        self._alive_eligible: set[str] = set()
        self._score_by_cam: dict[str, float] = {}
        # Whether the action input was set THIS tick (read by the `holding` predicate).
        self._action_held_this_tick: bool = False

        # Build the machine LAST so `initial="safe"` does not collide with attribute setup.
        # auto_transitions=False → no generated `to_<state>()` methods to clash with our
        # explicit `to_safe` trigger.
        self.machine = Machine(
            model=self,
            states=_STATES,
            transitions=_TRANSITIONS,
            initial="safe",
            auto_transitions=False,
            send_event=False,
        )

    # ----- guard predicates (pure reads; referenced by transition `conditions`) -------- #

    def challenger_qualified(self) -> bool:
        """True iff a challenger has cleared the margin AND sustained it ``debounce_N`` ticks."""
        return (
            self.challenger_id is not None
            and self.challenger_streak >= self.debounce_N
        )

    def dwell_elapsed_ok(self) -> bool:
        """True iff the current target has been live at least ``min_dwell_ticks`` ticks.

        SAFE has no dwell obligation (there is no incumbent camera to protect), so a cold-start
        cut out of SAFE is allowed the instant the challenger qualifies.
        """
        if self.target == SAFE_TARGET:
            return True
        return self.dwell_elapsed >= self.min_dwell_ticks

    def cooldown_clear(self) -> bool:
        """True iff no post-cut cooldown is in effect."""
        return self.cooldown_remaining == 0

    def holding(self) -> bool:
        """True iff an action or occlusion hold is ACTIVE this tick (DEC-03/DEC-04).

        Action-active = the action input is set AND its age has not reached the max-cap
        (force-release at the cap). Occlusion-active = its countdown has not yet reached 0.
        Wired as ``unless=["holding"]`` on the normal ``auto_switch`` ONLY — NEVER on the
        ``feed_emergency`` edges (death wins over hold). Reads the per-tick scratch advanced
        at the top of ``tick()``; a pure read (no mutation).
        """
        action_active = self._action_held_this_tick and (
            self.action_hold_age <= self.action_hold_cap_ticks
        )
        occlusion_active = self.occlusion_hold_remaining > 0
        return action_active or occlusion_active

    def live_feed_dead(self) -> bool:
        """True iff the current live target is a real camera whose feed died THIS tick (DEC-06).

        SAFE is never "dead" (it is the fallback, not a feed). A camera id that is not in the
        alive-eligible set (dead, no-liveness-reading, or poisoned score) means the on-air feed
        has failed — the emergency cut must fire. Read of per-tick scratch only (pure).
        """
        if self.target == SAFE_TARGET:
            return False
        return self.target not in self._alive_eligible

    def has_alive_candidate(self) -> bool:
        """True iff at least one camera is alive with a finite score (an emergency target exists)."""
        return len(self._alive_eligible) > 0

    # ----- transition callbacks (the ONLY places `self.target` changes) ---------------- #

    def _emergency_cut(self) -> None:
        """Cut the live target to the best alive camera (DEC-06 / D-01), then re-protect it.

        Bypasses dwell/cooldown on the cut itself (this callback runs from the `feed_emergency`
        guard, which does NOT read those clocks), but resets BOTH clocks for the NEW target so a
        competing higher score one tick later cannot steal it (Pitfall 4 — the emergency target
        then receives normal min_dwell/cooldown protection). The best-alive camera is the
        already-computed config-order argmax over eligible (alive + finite) scores.
        """
        new = self._best_eligible
        if new is not None and new != self.target:
            self.target = new
            self._on_target_change()

    def _set_target_safe(self) -> None:
        """Set the live target to the SAFE sentinel (cold start / no eligible candidate)."""
        if self.target != SAFE_TARGET:
            self._on_target_change()
        self.target = SAFE_TARGET

    def _promote_challenger(self) -> None:
        """Promote the qualified challenger to live (the ONLY normal-cut target change)."""
        new = self.challenger_id
        if new is not None and new != self.target:
            self.target = new
            self._on_target_change()

    def _on_target_change(self) -> None:
        """Reset the dwell + cooldown clocks for the newly-selected target (DEC-02)."""
        self.dwell_elapsed = 0
        self.cooldown_remaining = self.cooldown_ticks

    # ----- the single per-tick entry point --------------------------------------------- #

    def tick(
        self,
        scores: list[CameraScore],
        alive: dict[str, bool] | None = None,
        holds: HoldInput | None = None,  # consumed in 03-02 (holds); accepted now for the seam
        override: OverrideCmd | None = None,  # consumed in 03-03 (override); accepted for the seam
    ) -> Decision:
        """Advance the FSM one tick and emit a frozen ``Decision``.

        Order (RESEARCH §Pattern 3, this plan's scope): (1) advance the integer clocks +
        the challenger/debounce counter; (2) compute the best ELIGIBLE candidate (pure
        ``max`` over finite, in-range, alive scores); (3) fire the guarded trigger(s) — only
        ``auto_switch`` this plan (override/feed-death/hold edges land in 03-02/03-03); a cut
        on a tick is reflected by ``reason != "none"``. Never raises (fail-safe, T-3-04).
        """
        tick_idx = scores[0].tick if scores else 0
        # No alive map supplied → treat every camera as alive (the FSM consumes liveness, it
        # never derives it). An EXPLICIT alive map means absent-from-map defaults to NOT alive
        # (a camera with no liveness reading is excluded — DEC-06 fail-safe, scorer .get()
        # never-KeyError precedent).
        has_alive_map = alive is not None
        alive = alive or {}

        # (1) ADVANCE CLOCKS/COUNTERS.
        self.dwell_elapsed += 1
        self.cooldown_remaining = max(0, self.cooldown_remaining - 1)

        # (1b) ADVANCE HOLD CLOCKS (DEC-03/DEC-04). Holds are first-class per-tick inputs
        # (D-02), never inferred from score dynamics. Action: count age UP while set, reset on
        # clear (force-release is via the cap in the `holding` predicate). Occlusion: arm the
        # countdown on a RISING edge to the effective (capped) bound, then decrement to floor 0.
        holds = holds or HoldInput()
        self._action_held_this_tick = bool(holds.action)
        if holds.action:
            self.action_hold_age += 1
        else:
            self.action_hold_age = 0
        if holds.occlusion and not self._prev_occlusion:
            self.occlusion_hold_remaining = self._occlusion_effective_ticks  # rising edge → arm
        else:
            self.occlusion_hold_remaining = max(0, self.occlusion_hold_remaining - 1)
        self._prev_occlusion = bool(holds.occlusion)

        # (2) ELIGIBLE CANDIDATE SELECTION (pure). A camera is eligible iff its score is
        # finite/in-range AND (when an alive map is given) alive.get(cam_id, False). Build a
        # score map so the max(...) below is over eligible cameras only.
        score_by_cam: dict[str, float] = {}
        for cs in scores:
            if not _is_finite_score(cs.score):
                continue  # poisoned → ineligible (T-3-04)
            if has_alive_map and not alive.get(cs.cam_id, False):
                continue  # dead / no-liveness-reading → ineligible (DEC-06 fail-safe)
            score_by_cam[cs.cam_id] = float(cs.score)

        # Publish the eligible (alive + finite-scored) set + score map as per-tick scratch so
        # the feed-death guard predicates (`live_feed_dead` / `has_alive_candidate`) and the
        # `_emergency_cut` callback can read them — `transitions` callbacks take no args.
        self._score_by_cam = score_by_cam
        self._alive_eligible = set(score_by_cam.keys())

        # Deterministic best-eligible (DEC-05 no-incumbent tiebreak): iterate in CONFIG
        # DECLARATION order and keep the STRICT-max (`>`, never `>=`), so two exactly-equal
        # scores always resolve to the EARLIER-declared camera. This is independent of the
        # per-tick scores list order (the loop is over `self.cam_ids`, not over `scores`).
        # Config declaration order is the ONLY no-incumbent fallback rule — no role-priority
        # concept is introduced (D-07).
        best_eligible: str | None = None
        best_score = -1.0
        for cam_id in self.cam_ids:
            if cam_id in score_by_cam and score_by_cam[cam_id] > best_score:
                best_eligible = cam_id
                best_score = score_by_cam[cam_id]
        self._best_eligible = best_eligible

        # Update the challenger / debounce streak from THIS tick's scores. The incumbent's
        # score is the live target's score (0.0 for SAFE — anything clears the margin from
        # cold start, but still must sustain debounce_N ticks before the cut).
        #
        # DEC-05 incumbent-wins tiebreak: the strict `> incumbent_score + hysteresis_margin`
        # test means a near-exact score tie INSIDE the dead-band (a challenger that does NOT
        # exceed the incumbent by the full margin) registers NO challenger → no cut → the
        # incumbent is retained. The hysteresis dead-band IS the incumbent-wins tiebreak.
        incumbent_score = score_by_cam.get(self.target, 0.0)
        challenger = best_eligible
        if (
            challenger is not None
            and challenger != self.target
            and score_by_cam[challenger] > incumbent_score + self.hysteresis_margin
        ):
            if challenger == self.challenger_id:
                self.challenger_streak += 1
            else:
                self.challenger_id = challenger
                self.challenger_streak = 1
        else:
            # No qualifying challenger this tick → reset the streak (a single dip breaks it).
            self.challenger_id = None
            self.challenger_streak = 0

        # (3) FIRE GUARDED TRIGGERS in fixed priority order (RESEARCH §Pattern 3): feed-death
        # emergency ABOVE the normal auto_switch (override/hold tiers land in 03-03/later in
        # 03-02). Each `before` callback is the ONLY path that changes self.target — a failed
        # guard is a silent no-op. We capture which tier moved the target to derive the reason.
        prev_target = self.target

        # 3a) Feed-death emergency: a dead LIVE feed must never stay on air (DEC-06). Fires
        # from `auto`/`override` only; its guards gate the cut. Bypasses dwell/cooldown.
        if self.state in ("auto", "override"):
            self.feed_emergency()
        emergency_fired = self.target != prev_target

        # 3b) Normal auto-switch: fires from `auto`/`safe`; its conditions gate the cut (incl.
        # `unless=holding`). Skipped if the emergency tier already moved the target this tick
        # (one decision per tick). Capture whether a hold SUPPRESSED an otherwise-qualified cut.
        suppressed_by_hold = False
        if not emergency_fired:
            if (
                self.holding()
                and self.challenger_qualified()
                and self.dwell_elapsed_ok()
                and self.cooldown_clear()
            ):
                # The challenger would have cut were it not for the active hold (DEC-03/04).
                suppressed_by_hold = True
            self.auto_switch()

        changed = self.target != prev_target
        if changed:
            reason = "feed_emergency" if emergency_fired else "auto_switch"
        elif suppressed_by_hold:
            reason = "hold"
        else:
            reason = "none"

        # (4) EMIT the frozen Decision. Mode tracks the FSM state (safe/auto/override).
        return Decision(
            tick=tick_idx,
            target=self.target,
            mode=Mode(self.state),
            reason=reason,
        )
