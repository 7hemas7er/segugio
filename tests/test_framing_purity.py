"""FRM-07 purity/determinism tests — scaffolded skip (filled by plan 02-04 purity gate).

Wave-0 contract: plan 02-04 removes the ``pytestmark`` skip and fills
``test_purity_determinism`` (same ``DetectionSignal`` sequence → byte-identical
``CameraScore`` list across two runs; no ``time``/``np.random``/I/O imports in
``framing/``; ``import segugio.framing`` works with the heavy runtime absent — adding
``segugio.framing`` to the proven-importable surface) when it locks the purity gate.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="purity gate composed in 02-04")


def test_purity_determinism() -> None:
    """Placeholder — 02-04 fills this with the determinism + purity-grep assertions."""
    raise AssertionError("filled by 02-04")
