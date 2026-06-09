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
    # Normal auto-switch: fires ONLY if the challenger cleared hysteresis + sustained
    # debounce_N AND dwell elapsed AND cooldown clear. `_promote_challenger` is the ONLY
    # place the target changes on a normal cut (DEC-01).
    {
        "trigger": "auto_switch",
        "source": ["auto", "safe"],
        "dest": "auto",
        "conditions": ["challenger_qualified", "dwell_elapsed_ok", "cooldown_clear"],
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
    """

    def __init__(self, cameras, thresholds, fps: float = 30.0) -> None:
        # Insertion-ordered camera id list (config declaration order) — the deterministic
        # no-incumbent tiebreak order (D-07). Mirrors the scorer's ordered-dict precedent.
        self.cam_ids: list[str] = [cam.id for cam in cameras]

        # Hysteresis / debounce parameters (read directly; debounce_N is already in ticks).
        self.hysteresis_margin: float = float(thresholds.hysteresis_margin)
        self.debounce_N: int = int(thresholds.debounce_N)

        # Seconds→ticks conversion happens ONCE here (fps injected, not from config).
        self.min_dwell_ticks: int = ticks_from_seconds(thresholds.min_dwell, fps)
        self.cooldown_ticks: int = ticks_from_seconds(thresholds.cooldown, fps)

        # Integer clocks / counters on the model (advanced at the top of tick()). Plain ints
        # — transitions manages states + guard dispatch, NOT these counters (RESEARCH P2).
        self.dwell_elapsed: int = 0
        self.cooldown_remaining: int = 0
        self.challenger_id: str | None = None
        self.challenger_streak: int = 0

        # The live aired target — a camera id or the SAFE sentinel. Assigned ONLY inside a
        # transition callback after construction.
        self.target: str = SAFE_TARGET

        # Per-tick scratch (set at the top of tick(), read by the guard predicates + the
        # `before` callbacks). Kept on the model so `transitions` callbacks can read them.
        self._best_eligible: str | None = None

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

    # ----- transition callbacks (the ONLY places `self.target` changes) ---------------- #

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

        # Deterministic best-eligible: iterate in config order, keep the strict-max (first
        # camera in declaration order wins an exact tie — D-07 no-incumbent fallback ordering).
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

        # (3) FIRE GUARDED TRIGGERS (fixed priority; this plan: just auto_switch). The
        # `before` callback is the ONLY path that changes self.target — a failed guard is a
        # silent no-op. We capture whether the target changed to derive the reason.
        prev_target = self.target
        # auto_switch fires from `auto` or `safe`; its conditions gate the actual change.
        self.auto_switch()

        changed = self.target != prev_target
        reason = "auto_switch" if changed else "none"

        # (4) EMIT the frozen Decision. Mode tracks the FSM state (safe/auto/override).
        return Decision(
            tick=tick_idx,
            target=self.target,
            mode=Mode(self.state),
            reason=reason,
        )
