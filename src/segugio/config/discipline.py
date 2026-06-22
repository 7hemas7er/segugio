"""Discipline profiles as a pydantic v2 discriminated union (CFG-03).

Switching ``field.sport`` between ``disc_dog`` and ``agility`` selects a different
overlay-field set + framing defaults with ZERO code edits: pydantic picks the
sub-model from the ``sport`` tag, and consumers read ``config.field.overlay_fields``
/ ``config.field.framing_defaults`` — they never branch on ``if sport == ...``.

Overlay field sets come from FEATURES.md (per-discipline live-overlay tables):
  disc_dog (Toss&Fetch): team, round, timer, catch_count, zone, total
  agility:               dog, sct, running_time, faults, result

Light-import only — no heavy deps, keeping the Phase-1 import boundary intact.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:  # pragma: no cover - typing only; never imported at runtime here
    from ..ui import score_calc


class FramingDefaults(BaseModel):
    """Per-discipline framing-bias defaults (FEATURES.md: lead room + hold length).

    disc dog leaves more lead room and holds longer (sprint-and-return); agility
    follows tighter with shorter holds (obstacle-to-obstacle cutting).
    """

    model_config = ConfigDict(extra="forbid")
    lead_room: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    hold_length_s: Annotated[float, Field(ge=0.0)] = 2.0


# --------------------------------------------------------------------------- #
# Scoring profile (SCP-01/SCP-02) — config-driven per-discipline/federation rules.
#
# These pydantic sub-models live in the HEAVY config tier (pydantic-validated,
# fail-fast at config-load via the existing SystemExit(2) loader). They are
# adapted into the PLAIN stdlib `score_calc.ScoringProfile` dataclass by
# `adapt_scoring_profile` and INJECTED into the crash-isolated console (D-10) —
# `segugio.ui.score_calc` never imports this module.
#
# Decimal-typed bounded fields so a 0.5 bonus / 0.01 increment round-trip is exact
# (D-09 — no float drift on a broadcast total). Zones are an ORDERED band list
# (D-13), not a fixed 4-row table, so CSEN's 4 bands and FIDASC's 5 both express.
# --------------------------------------------------------------------------- #


class ZoneBand(BaseModel):
    """One ordered scoring zone: a band ordinal/label and its Decimal points (D-13)."""

    model_config = ConfigDict(extra="forbid")
    band: int
    points: Annotated[Decimal, Field(ge=0)]


class Bonus(BaseModel):
    """A config-declared per-catch bonus (e.g. ``midair`` +0.5, ``corridor`` +0.5) (D-13)."""

    model_config = ConfigDict(extra="forbid")
    key: str
    value: Annotated[Decimal, Field(ge=0)]


class FreestyleCategory(BaseModel):
    """One judged freestyle category: name + bounded range + grid increment (D-03/D-08)."""

    model_config = ConfigDict(extra="forbid")
    name: str
    min: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    max: Annotated[Decimal, Field(ge=0)] = Decimal("10")
    increment: Annotated[Decimal, Field(gt=0)] = Decimal("0.01")

    @model_validator(mode="after")
    def _min_le_max(self) -> "FreestyleCategory":
        if self.min > self.max:
            raise ValueError(
                f"freestyle category '{self.name}': min ({self.min}) must be <= max ({self.max})"
            )
        return self


class ScoringProfile(BaseModel):
    """Per-discipline/federation scoring rules — the pydantic (config-tier) form.

    Attached ADDITIVELY to the CFG-03 union members so an existing ``extra="forbid"``
    config WITHOUT a ``scoring:`` block still validates (mirrors the ``OverlayParams``
    / ``PreviewParams`` precedent in ``models.py``). A malformed profile (negative
    points, an unknown ``agility_model``, an extra key) raises a ``ValidationError``
    aggregated into the loader's fail-fast ``SystemExit(2)`` — no new fail-fast
    surface (SCP-02). ``adapt_scoring_profile`` converts a validated instance into the
    plain ``score_calc.ScoringProfile`` dataclass the console consumes (D-10).
    """

    model_config = ConfigDict(extra="forbid")
    units: str = "m"
    zones: list[ZoneBand] = Field(default_factory=list)
    bonuses: list[Bonus] = Field(default_factory=list)
    per_throw_cap: Decimal | None = None
    count_best_n: int | None = None
    freestyle_cats: list[FreestyleCategory] = Field(default_factory=list)
    freestyle_max: Decimal = Decimal("40")
    agility_model: Literal["count_up", "deduct_from_100"] = "count_up"
    time_fault_rate: Decimal = Decimal("1")
    fault_value: Decimal = Decimal("5")
    elimination_sentinel: str = "E"


class DiscDogProfile(BaseModel):
    """Disc-dog discipline profile (Toss&Fetch overlay fields by default)."""

    model_config = ConfigDict(extra="forbid")
    sport: Literal["disc_dog"]
    event: Literal["distance_accuracy", "freestyle", "xtreme"] = "distance_accuracy"
    overlay_fields: list[str] = Field(
        default_factory=lambda: ["team", "round", "timer", "catch_count", "zone", "total"]
    )
    framing_defaults: FramingDefaults = Field(
        default_factory=lambda: FramingDefaults(lead_room=0.25, hold_length_s=2.5)
    )
    # Additive (D-10/SCP-02): an existing disc_dog config without a `scoring:` block still
    # validates — the default is an empty-zone profile (the disc compute path needs real
    # zones, so a shipped fixture always declares them).
    scoring: ScoringProfile = Field(default_factory=ScoringProfile)

    @model_validator(mode="after")
    def _disc_zones_present_when_scoring(self) -> "DiscDogProfile":
        """A disc-dog profile that declares any scoring rule MUST declare zones (D-13).

        An empty default `scoring` (no block in the YAML) is allowed so existing configs
        stay valid; but the moment a `scoring:` block carries bonuses/cap/best-N/freestyle
        without zones, that is a malformed disc profile — reject it fail-fast (SCP-02).
        """
        s = self.scoring
        declared = (
            bool(s.bonuses)
            or s.per_throw_cap is not None
            or s.count_best_n is not None
            or bool(s.freestyle_cats)
        )
        if declared and not s.zones:
            raise ValueError(
                "disc_dog scoring profile declares scoring rules but no zones — "
                "an ordered zone band list is required (D-13)"
            )
        return self


class AgilityProfile(BaseModel):
    """Agility discipline profile (clock + fault overlay fields by default)."""

    model_config = ConfigDict(extra="forbid")
    sport: Literal["agility"]
    event: Literal["agility_standard"] = "agility_standard"
    overlay_fields: list[str] = Field(
        default_factory=lambda: ["dog", "sct", "running_time", "faults", "result"]
    )
    framing_defaults: FramingDefaults = Field(
        default_factory=lambda: FramingDefaults(lead_room=0.10, hold_length_s=1.5)
    )
    # Additive (D-10/SCP-02): agility configs without a `scoring:` block keep the generic
    # count_up defaults. `agility_model` is constrained to the two literals at the field
    # level (a third value raises union/literal error → fail-fast SystemExit(2)).
    scoring: ScoringProfile = Field(default_factory=ScoringProfile)


# pydantic selects the sub-model from the YAML `sport` value — zero code branches
# downstream. A bad sport value raises a discriminated-union error (union_tag_invalid).
FieldProfile = Annotated[
    DiscDogProfile | AgilityProfile, Field(discriminator="sport")
]


def adapt_scoring_profile(profile: ScoringProfile) -> "score_calc.ScoringProfile":
    """Convert a pydantic-validated :class:`ScoringProfile` into the plain stdlib dataclass.

    This is the D-10 adapter — it lives in the HEAVY config tier (it may reference both the
    pydantic model and ``score_calc``) and is called at the entrypoint, EXACTLY like
    ``load_config`` is called lazily in ``app.py:__main__``. ``segugio.ui.score_calc`` is
    imported LAZILY inside the function body so this module's top-level import surface stays
    light and ``score_calc`` itself never imports the config layer (RBT-08 / Pitfall 1).

    The pydantic list fields are mapped into the dataclass's immutable TUPLE fields so the
    plain profile stays hashable + ``==``-comparable for round-trip tests (D-13).
    """
    from ..ui import score_calc  # lazy: keeps the import surface clean (D-10 / RBT-08)

    return score_calc.ScoringProfile(
        units=profile.units,
        zones=tuple((z.band, z.points) for z in profile.zones),
        bonuses=tuple((b.key, b.value) for b in profile.bonuses),
        per_throw_cap=profile.per_throw_cap,
        count_best_n=profile.count_best_n,
        freestyle_cats=tuple(
            (c.name, c.min, c.max, c.increment) for c in profile.freestyle_cats
        ),
        freestyle_max=profile.freestyle_max,
        agility_model=profile.agility_model,
        time_fault_rate=profile.time_fault_rate,
        fault_value=profile.fault_value,
        elimination_sentinel=profile.elimination_sentinel,
    )
