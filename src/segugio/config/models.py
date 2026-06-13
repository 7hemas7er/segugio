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

from ..framing.params import ScorerParams
from ..tracking.params import TrackingParams
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

    Phase 6 latency seams (additive, default to today's eager-FP32 ``.pt`` behavior so any
    existing ``extra="forbid"`` config still validates without an ``engine_path``/``use_fp16``
    key):
      * ``engine_path`` — the cached TensorRT ``.engine`` artifact path (GPU/driver-specific,
        rebuilt per rig — Pitfall 3). ``None`` = eager ``.pt`` (the current path). The engine
        load + graceful-fallback wiring lands in Wave 2 (06-03); this is only the config KEY.
      * ``use_fp16`` — the eager ``half=True`` toggle for the Wave 1 FP16 measurement. ``False``
        = FP32 (the current path).
    """

    model_config = ConfigDict(extra="forbid")
    path: Path = Path("yolo26s.pt")
    class_index: int = 16
    engine_path: Path | None = None
    use_fp16: bool = False


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
    # RBT-01 anti-jitter grace seed (T-05-04-02): extra tolerance (seconds) added to
    # watchdog_timeout so a single late frame does not flap the feed dead and trigger a cut
    # storm. 0.067 ≈ 2 frames at 30fps — a small few-ticks tolerance. The SHIPPED value is
    # tuned empirically on real measured jitter (human-deferred, VERIFICATION human-verify #3).
    watchdog_grace: Annotated[float, Field(ge=0.0)] = 0.067
    track_buffer: Annotated[int, Field(ge=1)] = 60


class ActionHoldParams(BaseModel):
    """Action-hold seeds (D-08): motion energy → ``HoldInput.action`` threshold + window.

    Phase 5 wires ACTION-hold from the locked subject's motion energy only (occlusion-hold
    stays deferred): when the locked dog's cumulative motion energy stays at/above
    ``motion_threshold`` for ``window_ticks`` consecutive ticks, the orchestrator raises
    ``HoldInput(action=True)`` so the FSM holds the cut through a catch/jump (the DEC-03
    mandatory max-cap still applies). These are tuning SEEDS (tuned on real footage); the
    SCHEMA + bounds are what Phase 5 locks. Additive sub-model — an existing ``extra="forbid"``
    config WITHOUT an ``action_hold`` block still validates (defaults in), exactly like
    ``scoring``/``tracking``. Bounds mirror the ``Thresholds`` style.
    """

    model_config = ConfigDict(extra="forbid")
    motion_threshold: Annotated[float, Field(gt=0.0)] = 0.02
    window_ticks: Annotated[int, Field(ge=1)] = 5


class PreviewParams(BaseModel):
    """Off-tick preview publish defaults (D-05) — the console's live-preview fidelity seeds.

    The off-tick frame-publishing channel publishes per-camera JPEG thumbnails + the "why"
    sidecar on its OWN slower clock (~``fps``), never on the 30 Hz decision tick. These four
    keys tune publish cadence + thumbnail fidelity. ``enabled`` is ON by default (D-06) — when
    set to ``false`` the orchestrator builds NO publisher (byte-identical to v1.0).

    Additive sub-model: an existing ``extra="forbid"`` config WITHOUT a ``preview:`` block still
    validates (defaults in), exactly like ``scoring``/``tracking``/``action_hold``. These are
    starting fidelity SEEDS; **Phase 8 owns the HARD preview-bandwidth cap** (preview must
    degrade before the NDI feeds). Bounds mirror the ``Thresholds``/``ActionHoldParams`` style.
    """

    model_config = ConfigDict(extra="forbid")
    enabled: bool = True  # D-06: ON by default
    fps: Annotated[float, Field(gt=0.0, le=30.0)] = 5.0  # ~5 fps publish cadence
    max_width: Annotated[int, Field(ge=64, le=1920)] = 384  # downscale target width (px)
    jpeg_quality: Annotated[int, Field(ge=1, le=100)] = 55  # cv2 IMWRITE_JPEG_QUALITY


class Config(BaseModel):
    """The single typed config root — the contract all later phases import."""

    model_config = ConfigDict(extra="forbid")
    field: FieldProfile
    cameras: list[Camera] = Field(min_length=1)
    framing_weights: dict[Role, dict[str, float]]
    thresholds: Thresholds = Field(default_factory=Thresholds)
    model: ModelConfig = Field(default_factory=ModelConfig)
    scoring: ScorerParams = Field(default_factory=ScorerParams)
    tracking: TrackingParams = Field(default_factory=TrackingParams)
    action_hold: ActionHoldParams = Field(default_factory=ActionHoldParams)
    preview: PreviewParams = Field(default_factory=PreviewParams)

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
