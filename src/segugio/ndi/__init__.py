"""``segugio.ndi`` — NDI ingest package (lazy cyndilib edge, D-05).

LIGHT re-exports of the ``FrameSource`` interface, the in-process clip-replay mock
(``ClipReplayFrameSource``), and the NDI-02 mock Sender (``publish_clip``). All three modules
keep their heavy ``cyndilib``/``cv2`` imports INSIDE their methods/functions, so re-exporting
the symbols here does NOT trigger a heavy import — ``import segugio.ndi`` still succeeds with
cyndilib/cv2 ABSENT (the lazy-import boundary, proven by ``tests/test_imports.py``).

``NdiFrameSource`` (the real cyndilib receiver) is intentionally NOT re-exported at the package
top: while its module also imports light, callers that want the real receiver import it
explicitly (``from segugio.ndi.ndi_source import NdiFrameSource``) — the package surface stays
the interface + the two mock/E2E entry points the orchestrator and the E2E run depend on.
"""

from __future__ import annotations

from .clip_source import ClipReplayFrameSource
from .mock_sender import publish_clip
from .source import FrameSource

__all__ = ["FrameSource", "ClipReplayFrameSource", "publish_clip"]
