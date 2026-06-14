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
import math

from loguru import logger

from .atomic import atomic_write_json
from .records import (
    DirectorStatus,
    OperatorCommand,
    OverlayRunDoc,
    PreviewDoc,
    RunState,
    ScoreDoc,
)

__all__ = [
    "write_score",
    "read_score",
    "write_runstate",
    "read_runstate",
    "write_command",
    "read_command",
    "write_status",
    "read_status",
    "write_preview",
    "read_preview",
    "write_overlay_run",
    "read_overlay_run",
]


def _reject_non_finite_token(token: str):
    """``parse_constant`` hook: reject ``NaN``/``Infinity``/``-Infinity`` on read (CR-01).

    ``json.loads`` calls this for each non-standard constant token it encounters. Raising a
    ``ValueError`` here makes the parse fail, which ``_read_json`` catches and collapses to the
    safe default — so a non-finite float can never enter a record (and thus never escape
    ``/overlay-json`` as a non-finite, RFC-8259-invalid JSON token).
    """
    raise ValueError(f"non-finite JSON token {token!r}")


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
        # parse_constant rejects the non-standard tokens NaN / Infinity / -Infinity that
        # json.loads accepts by default — a torn/legacy/attacker-touched sidecar carrying one
        # of these would otherwise pass float() coercion silently and re-emit as a non-finite
        # token from /overlay-json (invalid JSON per RFC 8259, breaks the consumer's .json()
        # parse). Raising here collapses the whole file to the safe default for ALL readers
        # (CR-01 belt-and-suspenders — defends every float field on the channel at once).
        return json.loads(raw, parse_constant=_reject_non_finite_token)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("opcomm malformed JSON at {} → default ({})", path, exc)
        return None


def _as_bool(value, default: bool = False) -> bool:
    """Coerce a read-back JSON value to a STRICT bool (WR-04).

    Blanket ``bool(value)`` is a footgun on a hand-edited/legacy file: the non-empty string
    ``"false"`` is truthy → ``True``, so an operator who typed ``"running": "false"`` (intending
    "stopped") would have the overlay read "running". Only real bools, numerics, and the known
    string forms are accepted; anything else falls back to ``default``. Note ``"running": 1`` →
    ``True`` is preserved (numeric path), matching the pinned ``test_overlay_run_doc_normalizes``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


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
        # WR-01: guard fields to a dict (mirror read_status/read_preview). A non-dict on disk
        # (e.g. "fields": [1,2,3]) would otherwise be kept verbatim — ScoreDoc validates only
        # discipline — and leak a list out of /overlay-json, violating the {label: value} contract.
        raw_fields = data.get("fields", {})
        fields = raw_fields if isinstance(raw_fields, dict) else {}
        return ScoreDoc(
            discipline=data.get("discipline", ScoreDoc().discipline),
            fields=fields,
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


# --- preview sidecar (PRV-02, off-tick "why" channel) ---------------------- #


def write_preview(path: str, doc: PreviewDoc) -> None:
    """Write a ``PreviewDoc`` atomically to ``preview.json`` (the console polls it).

    Rides on :func:`atomic_write_json`, which ALWAYS fsyncs — that satisfies D-04's "keep fsync
    for preview.json" for free. The ephemeral JPEGs (NOT this file) are the ones written with
    ``atomic_write_bytes(fsync=False)``; ``preview.json`` is NEVER routed through
    ``atomic_write_bytes``. This is a SEPARATE file from ``status.json`` (D-03 separation).
    """
    atomic_write_json(
        path,
        {
            "tick": doc.tick,
            "gen": doc.gen,
            "auto_candidate": doc.auto_candidate,
            "cams": doc.cams,
            "cuts": [dict(c) for c in doc.cuts],
        },
    )


def read_preview(path: str) -> PreviewDoc:
    """Read a ``PreviewDoc`` from ``path``; malformed/absent → a default ``PreviewDoc`` (RBT-04).

    Reuses the :func:`_read_json` never-raise boundary (absent/torn/malformed → ``None``) and
    safe-defaults to an empty ``PreviewDoc()`` on any failure, exactly like :func:`read_status`,
    so a corrupt/torn/attacker-touched sidecar can never raise into the director loop.
    """
    data = _read_json(path)
    if not isinstance(data, dict):
        return PreviewDoc()
    try:
        cams = data.get("cams")
        cuts = data.get("cuts", ())
        return PreviewDoc(
            tick=int(data.get("tick", 0)),
            gen=int(data.get("gen", 0)),
            auto_candidate=data.get("auto_candidate", "SAFE"),
            cams=cams if isinstance(cams, dict) else {},
            cuts=tuple(cuts or ()),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid PreviewDoc at {} → default ({})", path, exc)
        return PreviewDoc()


# --- overlay-run sidecar (OVD-02, console-owned run-edge channel) ----------- #


def write_overlay_run(path: str, doc: OverlayRunDoc) -> None:
    """Write an ``OverlayRunDoc`` atomically to ``overlay_run.json`` (the overlay polls it).

    Rides on :func:`atomic_write_json` (always-fsync + the Windows MoveFileEx sharing-violation
    retry) so a reader never sees a partially-written run-edge file (D-03 / T-10-02-02). This is
    a SEPARATE file from the safety-critical ``runstate.json`` — the director NEVER reads it.
    Never hand-roll ``open(...).write()``.
    """
    atomic_write_json(
        path,
        {"running": doc.running, "started_at": doc.started_at, "gen": doc.gen},
    )


def read_overlay_run(path: str) -> OverlayRunDoc:
    """Read an ``OverlayRunDoc`` from ``path``; malformed/absent → a default (RBT-04 / D-04).

    Reuses the :func:`_read_json` never-raise boundary (absent/torn/malformed → ``None``) and
    safe-defaults to an empty ``OverlayRunDoc()`` on any failure, exactly like
    :func:`read_preview`, so a corrupt/torn/attacker-touched sidecar can never raise into the
    ``/overlay-json`` route or the loop (T-10-02-01). ``started_at`` is nullable — a stored
    ``None`` (the STOP/not-started state, D-03) is preserved, never coerced to ``0.0``.
    """
    data = _read_json(path)
    if not isinstance(data, dict):
        return OverlayRunDoc()
    try:
        started = data.get("started_at")
        if started is None:
            started_val = None
        elif isinstance(started, bool):
            # WR-02: JSON true/false are Python bools and float(True)=1.0 — a garbage "run started
            # at epoch 1.0" anchor. Reject here BEFORE float() coercion (which would mask the bool)
            # so the except below collapses it to the safe default (None).
            raise ValueError("started_at must be a number, not bool")
        else:
            # CR-01 defense-in-depth: 1e999 parses to inf via OVERFLOW (no NaN/Infinity TOKEN, so
            # parse_constant never fires) — reject non-finite here so started_at never carries a
            # non-finite anchor into /overlay-json (which would emit an RFC-8259-invalid token).
            started_val = float(started)
            if not math.isfinite(started_val):
                raise ValueError(f"non-finite started_at {started_val!r}")
        return OverlayRunDoc(
            # WR-04: strict bool coercion ("false"/garbage → default, not blanket-truthy).
            running=_as_bool(data.get("running", False)),
            started_at=started_val,
            gen=int(data.get("gen", 0)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid OverlayRunDoc at {} → default ({})", path, exc)
        return OverlayRunDoc()
