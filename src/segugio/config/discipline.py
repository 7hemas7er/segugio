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

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class FramingDefaults(BaseModel):
    """Per-discipline framing-bias defaults (FEATURES.md: lead room + hold length).

    disc dog leaves more lead room and holds longer (sprint-and-return); agility
    follows tighter with shorter holds (obstacle-to-obstacle cutting).
    """

    model_config = ConfigDict(extra="forbid")
    lead_room: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    hold_length_s: Annotated[float, Field(ge=0.0)] = 2.0


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


# pydantic selects the sub-model from the YAML `sport` value — zero code branches
# downstream. A bad sport value raises a discriminated-union error (union_tag_invalid).
FieldProfile = Annotated[
    DiscDogProfile | AgilityProfile, Field(discriminator="sport")
]
