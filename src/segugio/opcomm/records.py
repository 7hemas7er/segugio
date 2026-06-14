"""Frozen operator↔system records — the typed payloads on the atomic-file channel.

These are the four messages crossing the operator↔system trust boundary (D-03):

  * ``ScoreDoc``       — the manually-entered scores per discipline (SCR-02; display-only,
                          the system never adjudicates — SCR-04).
  * ``RunState``       — manual run start/stop (D-09): ``just_started`` resets the locks +
                          drives the overlay/timer; ``just_stopped`` parks the director on SAFE.
  * ``OperatorCommand``— the override command (D-10): ``force_cam`` XOR ``release``, mapping
                          directly onto the locked ``decision.signals.OverrideCmd``.
  * ``DirectorStatus`` — the reverse channel (D-11): the live camera + reason + per-feed
                          alive/dead map the panel polls.

Convention copied EXACTLY from ``decision/signals.py`` (the in-repo frozen-record analog):
``@dataclass(frozen=True)`` (hashable + ``==``-comparable so round-trip equality tests work),
``str``-Enum for any discipline/reason field (JSON-friendly + comparable), ``__post_init__``
boundary validation so a malformed operator message is rejected at CONSTRUCTION — never
reaching ``DecisionEngine.tick`` (mirrors ``OverrideCmd.__post_init__``, keeping the loop
exception-free, RBT-04 / T-05-01-03).

stdlib only (``dataclasses`` / ``enum``) — no numpy, no heavy deps. The
``OperatorCommand.to_override`` helper imports ``decision.signals`` LAZILY (inside the method)
so ``opcomm`` stays an independent leaf package (no opcomm→decision import at module top).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "Discipline",
    "ScoreDoc",
    "RunState",
    "OperatorCommand",
    "DirectorStatus",
    "PreviewDoc",
]


class Discipline(str, Enum):
    """The three scoring disciplines (SCR-02). A ``str`` Enum (mirrors ``decision.Mode``)
    so records stay ``==``-comparable and serialize as plain strings in the score file."""

    disc_tf = "disc_tf"  # disc dog Toss & Fetch (distance/accuracy)
    disc_freestyle = "disc_freestyle"  # disc dog freestyle (judged routine)
    agility = "agility"  # agility (time + faults)


# Run actions — the manual start/stop verbs (D-09). Kept as a small validated string set.
_RUN_ACTIONS = ("start", "stop")

# Director-status reasons (D-11) — why the live camera is what it is. Advisory strings the
# panel renders; not validated against an enum so a future reason never breaks an old reader.
_STATUS_REASONS = ("auto", "override", "subject-lost", "feed-dead", "fault", "shutdown", "none")


@dataclass(frozen=True)
class ScoreDoc:
    """Manually-entered scores for one discipline (SCR-02/04, display-only).

    ``fields`` is a free-form ``{label: value}`` map (the per-discipline field set the UI
    posts) — the system DISPLAYS these, it never computes/judges them (SCR-04). Frozen +
    ``==``-comparable; ``fields`` defaults to an empty dict so a fresh/absent score is valid.
    """

    discipline: Discipline = Discipline.disc_tf
    fields: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce a plain string discipline (e.g. read back from JSON) into the Enum at the
        # boundary so a hand-written/torn file value is validated loudly, not silently kept.
        if not isinstance(self.discipline, Discipline):
            object.__setattr__(self, "discipline", Discipline(self.discipline))


@dataclass(frozen=True)
class RunState:
    """Manual run start/stop state (D-09).

    ``action`` is ``"start"`` or ``"stop"``. ``just_started`` is the one-tick edge that resets
    ``CompetitorLock`` + (re)starts the overlay/timer; ``just_stopped`` is the edge that parks
    the director on SAFE + stops the timer. Defaults describe "no run yet / idle".
    """

    action: str = "stop"
    just_started: bool = False
    just_stopped: bool = False

    def __post_init__(self) -> None:
        if self.action not in _RUN_ACTIONS:
            raise ValueError(
                f"RunState.action must be one of {_RUN_ACTIONS}, got {self.action!r}"
            )

    @property
    def stopped(self) -> bool:
        """True while the run is stopped (the orchestrator parks on SAFE — D-09 STOP)."""
        return self.action == "stop"


@dataclass(frozen=True)
class OperatorCommand:
    """An override command from the panel (D-10) → the locked ``OverrideCmd``.

    ``force_cam`` set means "force this camera now" (immediate); ``release=True`` means
    "return to auto". The two are MUTUALLY EXCLUSIVE — both set is a contradictory operator
    command and is rejected at construction (mirrors ``OverrideCmd.__post_init__``, WR-04 /
    T-05-01-03) so a malformed command never reaches ``DecisionEngine.tick``. Both unset is a
    no-op (the channel treats "no command" as ``None``).
    """

    force_cam: str | None = None
    release: bool = False

    def __post_init__(self) -> None:
        if self.force_cam is not None and self.release:
            raise ValueError(
                "OperatorCommand is contradictory: set EITHER force_cam OR release=True, "
                "never both (mirrors OverrideCmd)"
            )

    def to_override(self):
        """Map to ``decision.signals.OverrideCmd`` (imported LAZILY to keep opcomm a leaf).

        The contract is 1:1 (force_cam / release), so this is a pure re-pack — the validation
        already happened at this record's construction.
        """
        from ..decision.signals import OverrideCmd

        return OverrideCmd(force_cam=self.force_cam, release=self.release)


@dataclass(frozen=True)
class DirectorStatus:
    """The reverse channel the panel polls (D-11): live cam + reason + per-feed liveness.

    ``live_cam`` is the aired camera id (or the ``"SAFE"`` sentinel); ``reason`` is an advisory
    tag (``auto`` / ``override`` / ``subject-lost`` / ``feed-dead`` / ``shutdown``); ``alive``
    is the per-feed ``{cam_id: bool}`` map. Defaults describe "idle, nothing live yet".

    ``alive`` is stored as an immutable tuple of sorted ``(cam_id, bool)`` pairs internally so
    the frozen dataclass stays hashable/``==``-comparable (a plain dict is unhashable); the
    ``alive`` property re-exposes it as a dict for callers. The constructor accepts a dict.
    """

    live_cam: str = "SAFE"
    reason: str = "none"
    alive: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize the alive dict into a deterministic immutable representation so two
        # DirectorStatus with the same content compare equal regardless of dict insertion
        # order (the round-trip equality contract the channel + status tests rely on).
        if isinstance(self.alive, dict):
            normalized = {str(k): bool(v) for k, v in self.alive.items()}
        else:
            normalized = {str(k): bool(v) for k, v in dict(self.alive).items()}
        object.__setattr__(self, "alive", normalized)


@dataclass(frozen=True)
class PreviewDoc:
    """Per-camera 'why' snapshot the console renders (camera live + perché). SIDECAR to status.json.

    The off-tick preview channel's typed record (PRV-02). Mirrors :class:`DirectorStatus` EXACTLY:
    frozen (hashable + ``==``-comparable so the round-trip equality test works), a normalizing
    ``__post_init__`` that coerces the nested ``cams``/``cuts`` containers to a deterministic form
    (so two ``PreviewDoc`` with the same content compare equal regardless of dict insertion order),
    and a safe-default reader (:func:`channel.read_preview`) that NEVER raises into the loop
    (RBT-04). Carries the FULL D-07 payload so Phases 8/9 are pure render — this contract is not
    reopened later.

    This is a SEPARATE channel from the safety-critical ``status.json`` (D-03): ``DirectorStatus``
    is byte-stable and untouched. The per-camera numeric values (``score``/``ema``/``energy`` and
    the ``box`` elements) are cast with ``float()`` where they are BUILT (the publisher in plan 03
    owns that cast — the ``CameraScore`` convention); ``PreviewDoc`` just normalizes the container
    shapes here.

    Fields:
      * ``tick`` — the orchestrator tick this snapshot was taken on.
      * ``gen`` — a monotonic cache-bust token the publisher bumps each publish (console ``?t=<gen>``).
      * ``auto_candidate`` — ``decision.target``: the camera auto WANTS this tick (id or ``"SAFE"``).
      * ``cams`` — ``{cam_id: {"score", "ema", "state", "locked", "track_id", "energy",
        "in_zone", "box"}}`` (``box`` is ``[cx,cy,w,h]`` normalized or ``None``).
      * ``cuts`` — recent-cuts ring, newest-last, depth ~16:
        ``({"tick", "from", "to", "reason"}, ...)``.
    """

    tick: int = 0
    gen: int = 0
    auto_candidate: str = "SAFE"
    cams: dict = field(default_factory=dict)
    cuts: tuple = ()

    def __post_init__(self) -> None:
        # Normalize cams to str-keyed dicts of dicts (mirror DirectorStatus.alive normalization)
        # so two PreviewDocs with the same content compare equal regardless of insertion order —
        # the round-trip equality contract the preview-channel tests rely on.
        cams = self.cams if isinstance(self.cams, dict) else dict(self.cams)
        object.__setattr__(self, "cams", {str(k): dict(v) for k, v in cams.items()})
        # Normalize cuts to a tuple of dicts (immutable → the frozen dataclass stays hashable).
        object.__setattr__(self, "cuts", tuple(dict(c) for c in self.cuts))
