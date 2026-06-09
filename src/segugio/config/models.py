"""Typed pydantic v2 config models — the contract every later module consumes.

One ``Config`` root aggregates the discipline ``field`` (discriminated union),
the ``cameras`` (each with normalized [0..1] zone rects), the
``framing_weights[role][zone]`` multiplier matrix, the switching ``thresholds``,
and the YOLO ``model`` path + class index. Validation is full and fail-fast:
a single ``ValidationError`` aggregates every problem with a JSON-path location.

pydantic v2 idioms ONLY (per RESEARCH.md "State of the Art"):
  - ``model_config = ConfigDict(extra="forbid")`` (no v1 inner ``class Config``)
  - ``field_validator`` / ``model_validator`` (no v1 ``@validator``)
  - ``Field(ge=, le=, gt=, min_length=, max_length=)`` constraints
  - ``Config.model_validate(...)`` (no v1 ``parse_obj``)

Light-import only — keeps the Phase-1 lazy-import boundary intact.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .discipline import FieldProfile


class Role(str, Enum):
    """Camera roles → the keys of the framing_weights matrix (ARCHITECTURE.md Part 2)."""

    main_wide = "main_wide"
    long = "long"
    low = "low"
    handler_side = "handler_side"


# Normalized [0..1] coordinate — used for zone rect components.
Norm = Annotated[float, Field(ge=0.0, le=1.0)]


class Zone(BaseModel):
    """A named region of a camera's frame in normalized [0..1] image coords.

    ``rect`` is ``[x0, y0, x1, y1]`` each in [0,1] with ``x0 < x1`` and ``y0 < y1``.
    Resolution-independent by design (ARCHITECTURE.md Part 3, Option A).
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    rect: list[Norm] = Field(min_length=4, max_length=4)

    @field_validator("rect", mode="after")
    @classmethod
    def _ordered(cls, v: list[float]) -> list[float]:
        x0, y0, x1, y1 = v
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"rect must have x0<x1 and y0<y1, got {v}")
        return v


class Camera(BaseModel):
    """A single camera: id, role, OBS scene, safe flag, optional NDI source, zones."""

    model_config = ConfigDict(extra="forbid")
    id: str
    role: Role
    obs_scene: str
    is_safe: bool = False
    ndi_source: str | None = None
    zones: list[Zone] = Field(min_length=1)


class ModelConfig(BaseModel):
    """YOLO model selection (CFG-04). Defaults to yolo26s.pt / COCO dog=16.

    ``path`` is a ``pathlib.Path`` (never shell-interpolated — path-injection guard).
    The class index must be re-verified against ``model.names`` at load time in
    Phase 4; Phase 1 only carries the configured value.
    """

    model_config = ConfigDict(extra="forbid")
    path: Path = Path("yolo26s.pt")
    class_index: int = 16


class Thresholds(BaseModel):
    """The seven switching parameters (CFG-01).

    Values are tuning *seeds* (A5: tuned on real footage in P2-P4); the SCHEMA and
    its bounds are what Phase 1 locks.
    """

    model_config = ConfigDict(extra="forbid")
    alpha: Annotated[float, Field(gt=0.0, le=1.0)] = 0.3
    hysteresis_margin: Annotated[float, Field(ge=0.0)] = 0.1
    min_dwell: Annotated[float, Field(ge=0.0)] = 2.0
    debounce_N: Annotated[int, Field(ge=1)] = 3
    cooldown: Annotated[float, Field(ge=0.0)] = 1.0
    watchdog_timeout: Annotated[float, Field(gt=0.0)] = 0.8
    track_buffer: Annotated[int, Field(ge=1)] = 60


class Config(BaseModel):
    """The single typed config root — the contract all later phases import."""

    model_config = ConfigDict(extra="forbid")
    field: FieldProfile
    cameras: list[Camera] = Field(min_length=1)
    framing_weights: dict[Role, dict[str, float]]
    thresholds: Thresholds = Field(default_factory=Thresholds)
    model: ModelConfig = Field(default_factory=ModelConfig)

    @model_validator(mode="after")
    def _zones_are_weighted(self) -> "Config":
        """CFG-02 typo guard + SAFE-fallback guard (fail fast at startup).

        Every zone name a camera references MUST have a framing_weights entry for
        that camera's role — a typo'd zone name is rejected here, not silently
        weighted 1.0 at scoring time. At least one camera must be ``is_safe``.
        """
        for cam in self.cameras:
            weights = self.framing_weights.get(cam.role, {})
            for z in cam.zones:
                if z.name not in weights:
                    raise ValueError(
                        f"camera '{cam.id}' (role={cam.role.value}) references zone "
                        f"'{z.name}' with no framing_weights[{cam.role.value}][{z.name}]"
                    )
        if not any(c.is_safe for c in self.cameras):
            raise ValueError(
                "at least one camera must have is_safe: true (SAFE fallback)"
            )
        return self
