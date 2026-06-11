"""``scene_for`` — the pure camera-id→OBS-scene mapping (OBS-01).

The orchestrator's output edge: a ``Decision.target`` (a camera id, or the ``"SAFE"``
sentinel) → the OBS scene name to cut to. ``target == "SAFE"`` maps to the ``is_safe``
camera's ``obs_scene`` (the SAFE fallback scene); any other target maps to that camera's
``obs_scene``. Pure + light (no obsws, no heavy imports) so it is headless-testable against
the recording fake and reused unchanged by the orchestrator in 05-06.

Kept as a free function (not a controller method) so both the real ``ObsWsController`` and
the ``RecordingObsController`` consume the SAME mapping — the camera→scene contract lives in
exactly one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # type-only — keeps config import off the runtime light path
    from segugio.config.models import Camera
    from segugio.decision.signals import Decision

# The SAFE pseudo-target sentinel (decision.signals.SAFE_TARGET). Inlined as a literal here
# so this module imports nothing heavy at load; cross-checked against the signals constant.
_SAFE_TARGET = "SAFE"

__all__ = ["scene_for"]


def scene_for(decision: "Decision", cameras: "Sequence[Camera]") -> str:
    """Map ``decision.target`` to the OBS scene name to cut to (OBS-01).

    * ``target == "SAFE"`` → the ``is_safe`` camera's ``obs_scene`` (the SAFE fallback).
    * any camera id → that camera's ``obs_scene``.

    Raises ``KeyError`` if the target id is unknown or no ``is_safe`` camera exists — a
    configuration error the orchestrator surfaces (the FSM only ever emits a known camera id
    or the SAFE sentinel, so this is a hard invariant, not a runtime branch).
    """
    target = decision.target
    if target == _SAFE_TARGET:
        for cam in cameras:
            if cam.is_safe:
                return cam.obs_scene
        raise KeyError("no is_safe camera in config — cannot map SAFE target to a scene")
    for cam in cameras:
        if cam.id == target:
            return cam.obs_scene
    raise KeyError(f"unknown decision target {target!r} — not a configured camera id")
