"""Frozen input/output records for the camera-switching decision FSM (DEC-01/02).

These are the FSM's I/O contracts. ``Decision`` is the engine's OUTPUT — the live
target (a camera id, or the ``"SAFE"`` sentinel string per RESEARCH Assumption A4) plus
the operational ``Mode`` and a ``reason`` tag (event-on-change semantics). ``HoldInput``
and ``OverrideCmd`` are the FSM's first-class control inputs (D-02 holds; D-03/D-05
override) — defined here now so 03-02 (holds/guards) and 03-03 (override) only fill the
engine bodies, never re-declare the contracts.

The FSM's per-camera INPUT type is ``CameraScore`` from ``segugio.framing.signals`` — it
is imported by the engine, NEVER redefined here (one-way dependency: decision depends UP
onto framing, framing never depends on decision).

Every record is ``@dataclass(frozen=True)`` (hashable + comparable) so ``==`` over two
``list[Decision]`` is the determinism assertion DEC-07 relies on, exactly mirroring the
Phase-2 ``CameraScore`` / Phase-1 ``ScoreSample`` convention. ``Mode`` is a ``str`` Enum
(mirrors ``ScorerStatus`` / ``config.models.Role``) so it stays ``==``-comparable and
JSON/YAML-friendly. Any numeric field that could receive a numpy scalar is ``float()``-cast
at construction so a numpy scalar never leaks into the ``==``.

stdlib only (``dataclasses`` / ``enum``) — no numpy, no ``transitions``, no synth import.
Keeps the Phase-1 lazy-import boundary intact (no torch / ultralytics / cyndilib / obsws).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["Mode", "Decision", "HoldInput", "OverrideCmd"]

# The SAFE pseudo-target sentinel (RESEARCH A4): a distinct ``"SAFE"`` string emitted as
# ``Decision.target`` to cleanly separate "deliberately safe" from "happened to pick the
# wide cam". The orchestrator (Phase 5) maps it to the SAFE OBS scene.
SAFE_TARGET = "SAFE"


class Mode(str, Enum):
    """The FSM's operational mode (mirrors the ``transitions`` state set).

    A ``str`` Enum (mirrors ``framing.signals.ScorerStatus`` / ``config.models.Role``) so
    ``Decision`` stays ``==``-comparable and JSON/YAML-friendly. ``safe`` = on the SAFE
    fallback; ``auto`` = normal hysteretic auto-switching; ``override`` = an operator force
    is in effect (D-03/D-05; the edges land in 03-03).
    """

    safe = "safe"
    auto = "auto"
    override = "override"


@dataclass(frozen=True)
class Decision:
    """One emitted decision at one tick (FSM OUTPUT).

    Frozen (hashable + comparable) so ``==`` over two ``list[Decision]`` is the DEC-07
    determinism assertion. ``target`` is a camera id or the ``"SAFE"`` sentinel; ``mode``
    is the operational ``Mode``; ``reason`` is the firing transition's name on the tick a
    target change happened, else ``"none"`` (event-on-change semantics) — the DEC-01 test
    asserts ``reason != "none"`` exactly on the ticks where ``target`` changed.
    """

    tick: int
    target: str  # a camera id, or the "SAFE" sentinel
    mode: Mode
    reason: str  # one of: "auto_switch" | "feed_emergency" | "hold" | "override" |
    #              "override_dead_fallback" | "none". ("override_dead_fallback" is the
    #              forced-but-dead / snap-back reconciliation while held in OVERRIDE — a
    #              distinct event from a plain "override" so a Phase-5 orchestrator that
    #              maps reasons → OBS actions can handle it explicitly. See engine.tick().)


@dataclass(frozen=True)
class HoldInput:
    """A per-tick hold signal the FSM exposes as a first-class input (D-02).

    Two typed flags (RESEARCH A3): ``action`` = a catch/jump is in progress (don't cut
    away mid-action); ``occlusion`` = an expected occlusion (tunnel/contact) is in progress.
    Both default ``False`` (no hold). The engine's hold suppression + mandatory max-cap land
    in 03-02; this record is the stable input contract those guards read.
    """

    action: bool = False
    occlusion: bool = False


@dataclass(frozen=True)
class OverrideCmd:
    """A per-tick operator override command the FSM exposes as a first-class input (RBT-03).

    Discriminates force-vs-release: ``force_cam`` set (non-``None``) means "force this
    camera now" (immediate, bypasses dwell/debounce/cooldown — D-05); ``release=True`` means
    "return to auto" (auto-resume only after full qualification — D-06). Both unset is a
    no-op. Frozen + ``==``-comparable.

    The 03-03 override edges consume this record exactly as defined here — the 03-01 shape was
    confirmed sufficient (force-vs-release is cleanly discriminated; no extension was needed).
    """

    force_cam: str | None = None
    release: bool = False
