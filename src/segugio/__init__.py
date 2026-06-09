"""Segugio — automatic operator-free multi-camera video direction.

Package root. Imports NOTHING heavy: torch / ultralytics / cyndilib / obsws-python
are declared dependencies but are imported lazily inside their owning later-phase
modules, never here. This keeps `import segugio` working on a machine with no GPU
and no NDI runtime (the Phase-1 lazy-import boundary).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
