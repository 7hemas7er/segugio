"""``segugio.obs`` — OBS control package (lazy obsws edge, D-06).

LIGHT re-exports: the ``ObsController`` interface, the ``RecordingObsController`` test double,
and the pure ``scene_for`` camera-id→scene mapping. The real ``obsws-python`` client
(``obsws_controller.ObsWsController``) imports ``obsws_python`` LAZILY inside its methods, so
``import segugio.obs`` succeeds with obsws absent (the lazy-import boundary, proven by
``tests/test_imports.py``). The real controller is NOT re-exported here so importing the
package never touches the heavy client module path.
"""

from __future__ import annotations

from .controller import ObsController
from .mapping import scene_for
from .recording_fake import RecordingObsController

__all__ = ["ObsController", "RecordingObsController", "scene_for"]
