"""``segugio.orchestrator`` — the live wiring layer (the grown-up ``run_clip_eval``).

This package closes the v1 milestone: it wires every locked Phase 1-4 brain
(``MultiCamScorer``, ``DecisionEngine``, ``CompetitorLock``, ``PlausibilityGate``, the
per-camera ``PerCameraTracker`` fan-out) into ONE fixed-rate, fault-isolated tick that
degrades to SAFE and never crashes (RBT-04), derives the D-08 action-hold from the locked
subject's motion energy, reads the operator command/run-state each tick, writes the D-11
status file on change, and measures the decision-loop latency (RBT-05).

Two modules:
  * :mod:`segugio.orchestrator.action_hold` — the PURE D-08 motion-energy → ``HoldInput.action``
    derivation (stdlib-only, clock-free). Re-exported here (it is light + pure).
  * :mod:`segugio.orchestrator.loop` — the ``Orchestrator`` tick (the I/O edge that owns the
    wall-clock + threads). NOT re-exported at package top: its body is light (the heavy
    cyndilib/obsws clients live only inside the INJECTED real impls) but importing it eagerly
    would still be needless; callers import ``from segugio.orchestrator.loop import Orchestrator``.

Lazy-import boundary (the Phase-1 invariant): ``import segugio.orchestrator`` succeeds with
cyndilib / obsws / ultralytics / torch / cv2 / Flask ABSENT — the orchestrator depends ONLY
on the light ``FrameSource`` / ``ObsController`` interfaces; the heavy clients are inside the
injected real implementations (Wave 2), never imported here.
"""

from __future__ import annotations

from .action_hold import ActionHoldDeriver

__all__ = ["ActionHoldDeriver"]
