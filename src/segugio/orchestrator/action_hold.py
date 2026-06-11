"""``ActionHoldDeriver`` — D-08 motion-energy → ``HoldInput.action`` (the core-value defense).

The single derivation behind the "never cut mid-catch / mid-jump" guarantee (the project's
core value; threat T-05-06-03, RESEARCH Pitfall 8). Disc-dog and agility have a recurring
failure mode: motion blur at a catch apex or a jump drops detection for a few frames, and a
naively-wired loop reads "subject gone" and cuts away from the climax. D-08 prevents that by
deriving the FSM's ``HoldInput.action`` from the LOCKED subject's motion energy — while the
locked dog is moving hard (a catch/jump in progress), the cut is held.

The signal source is ``CompetitorLock.locked_motion_energy()`` (the additive public accessor
from 05-01 Task 3, which reads the existing private ``_motion_energy`` for the current
``locked_id``). The orchestrator pulls that per-tick energy and injects it here; this deriver
thresholds it over ``ActionHoldParams`` and emits a ``HoldInput``:

  * ``action = True`` once the locked-subject motion energy has stayed ``>= motion_threshold``
    for ``window_ticks`` CONSECUTIVE ticks (the sustained window — a single noisy frame above
    threshold must not arm the hold);
  * ``action = False`` below threshold or before the window is reached; a dip below the
    threshold RESETS the sustained count (the streak must rebuild from scratch).
  * ``occlusion`` is ALWAYS ``False`` — occlusion-hold is DEFERRED in v1 (D-08). Phase 5 wires
    the action hold only; the FSM already carries the DEC-03 mandatory max-cap that
    force-releases a stuck action hold, so this deriver never needs an upper bound of its own.

PURE / clock-free / stdlib-only (the determinism convention shared with ``CompetitorLock`` and
``decision/``): the per-tick energy is INJECTED (the orchestrator owns the wall-clock + the
``CompetitorLock`` read); there is no clock, no RNG, no heavy import here. The same energy
sequence yields the same ``HoldInput`` sequence every run — so the integration with the real
``DecisionEngine`` is byte-deterministically testable headless. ``import
segugio.orchestrator.action_hold`` succeeds with the heavy stack absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..decision.signals import HoldInput

if TYPE_CHECKING:  # type-only — no config↔orchestrator runtime cost
    from ..config.models import ActionHoldParams

__all__ = ["ActionHoldDeriver"]


class ActionHoldDeriver:
    """Stateful-but-pure D-08 deriver: sustained locked-subject motion energy → ``HoldInput``.

    Construct once per orchestrator with the validated ``ActionHoldParams`` (the
    ``motion_threshold`` / ``window_ticks`` seeds). Call :meth:`derive` once per tick with the
    locked subject's motion energy (``CompetitorLock.locked_motion_energy()``, or ``0.0`` when
    nothing is locked). The only state is a small integer sustained-count of consecutive
    over-threshold ticks — no clock, no RNG.

    Args:
        params: the validated ``ActionHoldParams`` — ``motion_threshold`` (the energy floor,
            inclusive) and ``window_ticks`` (the number of CONSECUTIVE over-threshold ticks
            required before the action hold arms).
    """

    def __init__(self, params: "ActionHoldParams") -> None:
        self._threshold: float = float(params.motion_threshold)
        self._window: int = int(params.window_ticks)
        # The count of CONSECUTIVE ticks the injected energy has been >= threshold. Reset to 0
        # on any below-threshold tick. The hold arms once this reaches `window_ticks`.
        self._sustained: int = 0

    def derive(self, locked_motion_energy: float) -> HoldInput:
        """Thresholds the injected per-tick energy → ``HoldInput`` (the D-08 action hold).

        Increments the sustained-count while ``locked_motion_energy >= motion_threshold``
        (inclusive — energy exactly at the threshold counts as over); a tick below the
        threshold resets the count to 0. Emits ``HoldInput(action=True)`` once the count has
        reached ``window_ticks`` (the sustained window), else ``HoldInput(action=False)``.
        ``occlusion`` is ALWAYS ``False`` (deferred, D-08). Pure: the same energy sequence
        yields the same ``HoldInput`` sequence.

        Args:
            locked_motion_energy: the locked subject's motion energy THIS tick
                (``CompetitorLock.locked_motion_energy()``; ``0.0`` when nothing is locked).

        Returns:
            ``HoldInput(action=<armed>, occlusion=False)``.
        """
        if locked_motion_energy >= self._threshold:
            self._sustained += 1
        else:
            self._sustained = 0  # a single dip below threshold breaks the sustained window
        action = self._sustained >= self._window
        # occlusion is DEFERRED in v1 (D-08) — never set True here.
        return HoldInput(action=action, occlusion=False)
