"""Typed read/write for the four operator↔system files — the validation BOUNDARY.

This is the only IPC between the Flask operator console (separate process, D-03) and the
orchestrator loop. Each message is its own file (``score.json`` / ``runstate.json`` /
``command.json`` / ``status.json``) so an operator score write never races the orchestrator's
status write — independent atomic swaps, each consumer reads only what it needs (RESEARCH
Pattern 3, the lower-risk default over one combined file).

The hard contract of every ``read_*`` (T-05-01-01, RBT-04 🔴): a malformed, half-present, or
wholly absent file returns a SAFE DEFAULT record (or ``None`` for the command — "no override")
and is LOGGED, but NEVER raises into the loop. Combined with the atomic write (the writer side
never leaves a partial file), the orchestrator's per-tick reads are exception-free by
construction. Each writer takes an explicit path so the orchestrator and UI inject their own
directory (no hardcoded location).

Light: ``json`` / ``loguru`` only (loguru is a core dep). No heavy imports.
"""

from __future__ import annotations

import json

from loguru import logger

from .atomic import atomic_write_json
from .records import DirectorStatus, OperatorCommand, RunState, ScoreDoc

__all__ = [
    "write_score",
    "read_score",
    "write_runstate",
    "read_runstate",
    "write_command",
    "read_command",
    "write_status",
    "read_status",
]


def _read_json(path: str):
    """Read+parse a JSON file; return ``None`` on absent/empty/malformed (never raises).

    This is the single boundary that absorbs torn/legacy/absent files. Any failure
    (FileNotFoundError, empty file, JSON decode error, OS error) is logged and collapses to
    ``None`` so the caller can substitute the record's safe default.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return None
    except OSError as exc:  # noqa: BLE001 - any OS read failure is a coast, not a crash
        logger.debug("opcomm read {} failed (OS): {}", path, exc)
        return None
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("opcomm malformed JSON at {} → default ({})", path, exc)
        return None


# --- score (SCR-02) -------------------------------------------------------- #


def write_score(path: str, score: ScoreDoc) -> None:
    """Write a ``ScoreDoc`` atomically to ``path``."""
    atomic_write_json(
        path, {"discipline": score.discipline.value, "fields": score.fields}
    )


def read_score(path: str) -> ScoreDoc:
    """Read a ``ScoreDoc`` from ``path``; malformed/absent → a default ``ScoreDoc``."""
    data = _read_json(path)
    if not isinstance(data, dict):
        return ScoreDoc()
    try:
        return ScoreDoc(
            discipline=data.get("discipline", ScoreDoc().discipline),
            fields=data.get("fields", {}) or {},
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid ScoreDoc at {} → default ({})", path, exc)
        return ScoreDoc()


# --- run-state (SCR-03 / D-09) --------------------------------------------- #


def write_runstate(path: str, run: RunState) -> None:
    """Write a ``RunState`` atomically to ``path``."""
    atomic_write_json(
        path,
        {
            "action": run.action,
            "just_started": run.just_started,
            "just_stopped": run.just_stopped,
        },
    )


def read_runstate(path: str) -> RunState:
    """Read a ``RunState`` from ``path``; malformed/absent → a default (stopped) ``RunState``."""
    data = _read_json(path)
    if not isinstance(data, dict):
        return RunState()
    try:
        return RunState(
            action=data.get("action", "stop"),
            just_started=bool(data.get("just_started", False)),
            just_stopped=bool(data.get("just_stopped", False)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid RunState at {} → default ({})", path, exc)
        return RunState()


# --- override command (D-10) ----------------------------------------------- #


def write_command(path: str, cmd: OperatorCommand) -> None:
    """Write an ``OperatorCommand`` atomically to ``path``."""
    atomic_write_json(path, {"force_cam": cmd.force_cam, "release": cmd.release})


def read_command(path: str) -> OperatorCommand | None:
    """Read an ``OperatorCommand`` from ``path``.

    Returns ``None`` (no override) on absent/malformed/contradictory/empty-no-op content so
    the orchestrator passes ``override=None`` into ``DecisionEngine.tick`` (auto continues).
    """
    data = _read_json(path)
    if not isinstance(data, dict):
        return None
    force_cam = data.get("force_cam")
    release = bool(data.get("release", False))
    if force_cam is None and not release:
        return None  # empty command is a no-op, not an error
    try:
        return OperatorCommand(force_cam=force_cam, release=release)
    except ValueError as exc:
        # contradictory force+release on disk → treat as no override (never raise into loop)
        logger.warning("opcomm contradictory OperatorCommand at {} → None ({})", path, exc)
        return None


# --- director status (D-11, reverse channel) ------------------------------- #


def write_status(path: str, status: DirectorStatus) -> None:
    """Write a ``DirectorStatus`` atomically to ``path`` (the panel polls it)."""
    atomic_write_json(
        path,
        {"live_cam": status.live_cam, "reason": status.reason, "alive": status.alive},
    )


def read_status(path: str) -> DirectorStatus:
    """Read a ``DirectorStatus`` from ``path``; malformed/absent → a default (SAFE) status."""
    data = _read_json(path)
    if not isinstance(data, dict):
        return DirectorStatus()
    try:
        alive = data.get("alive", {})
        return DirectorStatus(
            live_cam=data.get("live_cam", "SAFE"),
            reason=data.get("reason", "none"),
            alive=alive if isinstance(alive, dict) else {},
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid DirectorStatus at {} → default ({})", path, exc)
        return DirectorStatus()
