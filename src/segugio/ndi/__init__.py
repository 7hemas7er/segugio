"""``segugio.ndi`` — NDI ingest package (lazy cyndilib edge, D-05).

LIGHT re-export of the ``FrameSource`` interface only — the orchestrator + the Wave-2
implementers depend on this. The real cyndilib receiver (``ndi_source``), the in-process clip
mock (``clip_source``), and the NDI-02 mock Sender land in Wave 2 (05-02) and import cyndilib
LAZILY inside their methods, so ``import segugio.ndi`` succeeds with cyndilib/cv2 absent (the
lazy-import boundary, proven by ``tests/test_imports.py``).
"""

from __future__ import annotations

from .source import FrameSource

__all__ = ["FrameSource"]
