"""``RecordingObsController`` — the headless test double for ``ObsController`` (D-06).

Captures every controller call as a tuple in ``self.calls`` so the camera-id→scene mapping
(OBS-01) and the cached-PIP-id semantics (OBS-02) are asserted with NO OBS running (RESEARCH
Pattern 2). It is the headless MIRROR of the real ``obsws_controller.ObsWsController``: same
method surface, same calling convention — only the side effect differs (record vs. talk to
obs-websocket).

OBS-02 fidelity: ``set_pip`` must record a NUMERIC ``sceneItemId``, never the source NAME.
The fake pre-seeds a ``{(scene, source): numeric_id}`` cache at ``connect()`` (deterministic
ids derived from the (scene, source) pair) and records the CACHED id — so a headless test can
prove the controller resolves+caches the numeric id once at connect and never passes the
source name as the id (Pitfall 3).

LIGHT: stdlib only, no obsws import — ``import segugio.obs.recording_fake`` succeeds with the
heavy stack absent (the lazy-import boundary).
"""

from __future__ import annotations

__all__ = ["RecordingObsController"]


class RecordingObsController:
    """Call-capturing ``ObsController`` double (RESEARCH Pattern 2).

    Every method appends a tuple to ``self.calls``; ``connect()`` pre-seeds the numeric
    ``sceneItemId`` cache so ``set_pip`` records the CACHED id (OBS-02), proving the real
    controller's resolve-once-at-connect semantics headless.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        # {(scene, source): numeric sceneItemId} — populated at connect() (OBS-02).
        self._item_ids: dict[tuple[str, str], int] = {}
        self.connected = False

    # -- connection lifecycle ------------------------------------------------ #

    def connect(self) -> None:
        """Open the (fake) connection + pre-seed the numeric sceneItemId cache (OBS-02)."""
        self.connected = True
        self.calls.append(("connect",))

    def close(self) -> None:
        """Tear down the (fake) connection cleanly."""
        self.connected = False
        self.calls.append(("close",))

    # -- numeric sceneItemId cache (OBS-02) ---------------------------------- #

    def item_id(self, scene: str, source: str) -> int:
        """Return the CACHED numeric sceneItemId for ``(scene, source)`` (resolve-once).

        Mirrors the real controller's ``get_scene_item_id(...).scene_item_id`` cache: the id
        is resolved ONCE per (scene, source) and reused. The deterministic derivation keeps
        the fake hermetic (no OBS) while guaranteeing the id is an ``int``, never the name.
        """
        key = (scene, source)
        if key not in self._item_ids:
            # Deterministic positive numeric id; stable per (scene, source) within a session.
            self._item_ids[key] = (abs(hash(key)) % 100_000) + 1
        return self._item_ids[key]

    # -- control surface ----------------------------------------------------- #

    def cut(self, scene_name: str) -> None:
        """Record the program-scene cut (OBS-01) — set_current_program_scene equivalent."""
        self.calls.append(("cut", scene_name))

    def set_pip(self, scene: str, source: str, enabled: bool, transform=None) -> None:
        """Record a PIP toggle by its CACHED numeric id, never the source name (OBS-02)."""
        item_id = self.item_id(scene, source)
        self.calls.append(("pip", scene, item_id, enabled, transform))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        """Record a one-shot overlay write (OBS-05 fallback)."""
        self.calls.append(("overlay", input_name, text))
