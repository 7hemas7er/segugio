"""``ObsController`` — the OBS control interface the orchestrator drives (D-06).

Cut / PIP / overlay sit behind this Protocol (RESEARCH Pattern 2) so the camera-id→scene
mapping and the failure paths (feed-death→SAFE, reconnect) are asserted HEADLESS against a
recording fake, while the real ``obsws-python`` ``ReqClient``/``EventClient`` impl runs on
Windows. Both land in Wave 2 (05-03): the real client imports ``obsws_python`` lazily inside
its methods; the recording fake captures every call.

Method roles:
  * ``connect``         — open the persistent connection + cache numeric ``sceneItemId``s + wire
                          the EventClient (sync manual scene changes back into the FSM).
  * ``cut``             — ``SetCurrentProgramScene`` (OBS-01): switch the live scene.
  * ``set_pip``         — ``SetSceneItemEnabled`` (+ optional ``SetSceneItemTransform``) using the
                          CACHED numeric id (OBS-02); built but driven manually/idle-only in v1.
  * ``set_overlay_text``— one-shot ``SetInputSettings({"text": ...})`` fallback (OBS-05; the
                          primary overlay path is the read-from-file text source).
  * ``close``           — tear down the connection cleanly.

Light: no obsws import at module top — ``import segugio.obs`` succeeds with obsws absent (the
lazy-import boundary).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ObsController"]


@runtime_checkable
class ObsController(Protocol):
    """OBS scene/PIP/overlay control. The orchestrator depends ONLY on this interface.

    ``runtime_checkable`` so the recording fake (and any duck-typed double) is
    ``isinstance``-checkable structurally in tests without inheriting.
    """

    def connect(self) -> None:
        """Open the persistent connection, cache PIP ids, wire the event sync."""
        ...

    def cut(self, scene_name: str) -> None:
        """Switch the live program scene to ``scene_name`` (OBS-01)."""
        ...

    def set_pip(self, scene: str, source: str, enabled: bool, transform=None) -> None:
        """Toggle/transform a PIP scene item by its cached numeric id (OBS-02)."""
        ...

    def set_overlay_text(self, input_name: str, text: str) -> None:
        """One-shot overlay text via SetInputSettings (OBS-05 fallback)."""
        ...

    def close(self) -> None:
        """Tear down the connection cleanly."""
        ...
