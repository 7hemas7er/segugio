"""``segugio.obs`` — OBS control package (lazy obsws edge, D-06).

LIGHT re-export of the ``ObsController`` interface only. The real ``obsws-python`` client
(``obsws_controller``) and the recording fake (``recording_fake``) land in Wave 2 (05-03); the
real client imports ``obsws_python`` LAZILY inside its methods, so ``import segugio.obs``
succeeds with obsws absent (the lazy-import boundary, proven by ``tests/test_imports.py``).
"""

from __future__ import annotations

from .controller import ObsController

__all__ = ["ObsController"]
