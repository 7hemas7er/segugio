"""TRK-03 mapper stub — filled by plan 04-01 Task 2 (TDD).

This placeholder exists so ``segugio.tracking.__init__`` can re-export
``signals_from_boxes`` (keeping the package importable under the lazy-import boundary)
while the real pure mapper is implemented test-first in Task 2. The stub is light
(stdlib only) so it never breaks the import-smoke boundary.
"""

from __future__ import annotations

__all__ = ["signals_from_boxes"]


def signals_from_boxes(xywhn, ids, confs, tick, cam_id):  # pragma: no cover - stub
    """Placeholder — implemented test-first in Task 2."""
    raise NotImplementedError("signals_from_boxes is implemented in plan 04-01 Task 2")
