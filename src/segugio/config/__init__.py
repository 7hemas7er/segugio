"""segugio.config — typed, fail-fast config contract (plan 01-02).

The pydantic v2 config models + loader every later module consumes. Re-exports the
load-bearing public surface (``Config``, ``load_config``, ``Role``); the full schema
(``Camera``, ``Zone``, ``ModelConfig``, ``Thresholds``) lives in ``.models`` and the
discipline discriminated union in ``.discipline``. Heavy-import-free by design.
"""

from ..framing.params import ScorerParams
from .discipline import AgilityProfile, DiscDogProfile, FieldProfile, FramingDefaults
from .loader import load_config
from .models import Camera, Config, ModelConfig, Role, Thresholds, Zone

__all__ = [
    "load_config",
    "Config",
    "Role",
    "Camera",
    "Zone",
    "ModelConfig",
    "Thresholds",
    "ScorerParams",
    "FieldProfile",
    "DiscDogProfile",
    "AgilityProfile",
    "FramingDefaults",
]
