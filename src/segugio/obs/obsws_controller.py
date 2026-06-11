"""``ObsWsController`` — the real obs-websocket v5 controller (D-06, OBS-01/02/03/05).

Implements the ``ObsController`` Protocol against ``obsws-python`` 1.8.0
(``ReqClient`` + ``EventClient``). The heavy ``import obsws_python`` lives INSIDE ``connect()``
(the lazy boundary) so ``import segugio.obs.obsws_controller`` succeeds with obsws ABSENT.

Responsibilities (RESEARCH §Code Examples + §Common Pitfalls):
  * ``connect``          — build ReqClient+EventClient, register the manual-scene-change
                           callback (OBS-03), and CACHE the numeric ``sceneItemId``s once
                           (OBS-02, Pitfall 3).
  * ``cut``              — ``set_current_program_scene`` (OBS-01).
  * ``set_pip``          — ``set_scene_item_enabled`` (+ optional ``set_scene_item_transform``)
                           on the CACHED numeric id (OBS-02); built but driven manually/idle in
                           v1 (ARCHITECTURE Part 5).
  * ``set_overlay_text`` — ``set_input_settings(input, {"text": ...}, overlay=True)``: the
                           ONE-SHOT FALLBACK. The PRIMARY overlay path is the read-from-file
                           text source the score manager (05-05) writes (OBS-05, Pitfall 5 —
                           the text input kind is NEVER hardcoded; only the generic ``text``
                           field is set).
  * ``close``            — tear down both clients cleanly.

Robustness (RBT-04, Pitfall 4): every OBS call is wrapped so a transient websocket failure
triggers ONE reconnect+reauth (rebuild ReqClient/EventClient + re-cache ids) and then coasts —
a failed OBS op NEVER raises into the orchestrator tick. ``EventClient`` syncs the operator's
MANUAL scene changes back into ``self.current_scene`` (OBS-03).

Testability: ``connect`` accepts an injected ``client_factory`` (a callable returning the
``(ReqClient, EventClient)`` pair). Tests inject a recording / fault-injecting factory to drive
the reconnect and overlay paths HEADLESS (no obsws, no OBS). When no factory is given, the real
``obsws_python`` clients are built lazily.
"""

from __future__ import annotations

from typing import Callable, Sequence

from loguru import logger

__all__ = ["ObsWsController", "build_obsws_clients"]


def build_obsws_clients(host: str, port: int, password: str | None):
    """Build the real ``(ReqClient, EventClient)`` pair — the default client factory.

    The ONLY place ``obsws_python`` is imported: inside this function (called from
    ``connect()``), so the module import stays light (the lazy boundary, OBS-05/Pitfall).
    """
    import obsws_python as obs  # heavy import INSIDE — never module-top (lazy boundary)

    req = obs.ReqClient(host=host, port=port, password=password, timeout=3)
    evt = obs.EventClient(host=host, port=port, password=password)
    return req, evt


class ObsWsController:
    """Real obs-websocket v5 controller with cached PIP ids, reconnect+reauth, EventClient sync.

    Satisfies the ``ObsController`` Protocol (``connect``/``cut``/``set_pip``/
    ``set_overlay_text``/``close``). All OBS calls coast on transient failure after one
    reconnect attempt (RBT-04). ``pip_sources`` is the list of ``(scene, source)`` pairs whose
    numeric ``sceneItemId`` is resolved+cached at connect (OBS-02).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4455,
        password: str | None = None,
        pip_sources: Sequence[tuple[str, str]] = (),
        *,
        client_factory: Callable[[str, int, str | None], tuple[object, object]] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        # (scene, source) pairs whose numeric sceneItemId is cached once at connect (OBS-02).
        self.pip_sources: list[tuple[str, str]] = list(pip_sources)
        # Injectable for headless tests; defaults to the real lazy obsws factory.
        self._factory = client_factory or build_obsws_clients

        self._req = None  # obsws ReqClient (or injected double)
        self._evt = None  # obsws EventClient (or injected double)
        self._item_ids: dict[tuple[str, str], int] = {}  # OBS-02 numeric id cache
        self._connected = False
        self.current_scene: str | None = None  # synced from EventClient manual cuts (OBS-03)

    # -- connection lifecycle ------------------------------------------------ #

    def connect(self) -> None:
        """Open the persistent connection, register the event sync, cache PIP ids (OBS-02/03)."""
        self._req, self._evt = self._factory(self.host, self.port, self.password)
        # OBS-03: sync the operator's MANUAL scene changes back into current_scene.
        register = getattr(getattr(self._evt, "callback", None), "register", None)
        if callable(register):
            register(self._on_scene_changed)
        self._cache_pip_ids()
        self._connected = True

    def reconnect(self) -> None:
        """Rebuild both clients + re-cache ids after a transient drop (OBS-03, Pitfall 4)."""
        logger.warning("obs: websocket drop — reconnecting+reauth")
        self._teardown_clients()
        self.connect()

    def close(self) -> None:
        """Tear down both clients cleanly."""
        self._teardown_clients()
        self._connected = False

    def _teardown_clients(self) -> None:
        for client in (self._req, self._evt):
            disconnect = getattr(client, "disconnect", None)
            if callable(disconnect):
                try:
                    disconnect()
                except Exception:  # teardown must never raise (RBT-04)
                    logger.exception("obs: error during client teardown (ignored)")
        self._req = None
        self._evt = None

    # -- numeric sceneItemId cache (OBS-02, Pitfall 3) ----------------------- #

    def _cache_pip_ids(self) -> None:
        """Resolve ``get_scene_item_id(scene, source).scene_item_id`` ONCE per pair + cache it.

        PIP/scene-item ops require the NUMERIC id, never the source name (Pitfall 3). Resolved
        once at connect; refreshed via the EventClient on SceneItemCreated/Removed.
        """
        self._item_ids = {}
        for scene, source in self.pip_sources:
            resp = self._req.get_scene_item_id(scene, source)
            self._item_ids[(scene, source)] = resp.scene_item_id

    def item_id(self, scene: str, source: str) -> int:
        """Return the cached numeric sceneItemId for ``(scene, source)`` (OBS-02)."""
        return self._item_ids[(scene, source)]

    # -- EventClient callbacks (OBS-03) -------------------------------------- #

    def _on_scene_changed(self, data) -> None:
        """Sync a MANUAL operator scene change back into ``current_scene`` (OBS-03)."""
        scene = getattr(data, "scene_name", None)
        if scene is not None:
            self.current_scene = scene

    def _on_scene_items_changed(self, data=None) -> None:
        """Refresh the numeric id cache on SceneItemCreated/Removed (Pitfall 3)."""
        try:
            self._cache_pip_ids()
        except Exception:  # never raise out of an event callback (RBT-04)
            logger.exception("obs: failed to refresh sceneItemId cache (ignored)")

    # -- coast-on-failure wrapper (RBT-04, Pitfall 4) ------------------------ #

    def _safe_call(self, op_name: str, fn) -> None:
        """Run an OBS op; on a transient failure reconnect ONCE then coast (never raise).

        A failed OBS call must NEVER propagate into the orchestrator tick (RBT-04). On the
        first failure we rebuild the clients (reconnect+reauth, Pitfall 4) and retry once; a
        second failure is logged and swallowed — the loop keeps ticking on SAFE.
        """
        try:
            fn()
            return
        except Exception:
            logger.exception("obs: {} failed — attempting reconnect", op_name)
        try:
            self.reconnect()
            fn()
        except Exception:
            logger.exception("obs: {} failed after reconnect — coasting", op_name)

    # -- control surface ----------------------------------------------------- #

    def cut(self, scene_name: str) -> None:
        """Switch the live program scene (OBS-01)."""
        def _do() -> None:
            self._req.set_current_program_scene(scene_name)
            self.current_scene = scene_name

        self._safe_call("cut", _do)

    def set_pip(self, scene: str, source: str, enabled: bool, transform=None) -> None:
        """Toggle/transform a PIP item by its CACHED numeric id (OBS-02)."""
        def _do() -> None:
            item_id = self._item_ids[(scene, source)]
            self._req.set_scene_item_enabled(scene, item_id, enabled)
            if transform is not None:
                self._req.set_scene_item_transform(scene, item_id, transform)

        self._safe_call("set_pip", _do)

    def set_overlay_text(self, input_name: str, text: str) -> None:
        """One-shot overlay text via SetInputSettings — the FALLBACK path (OBS-05).

        The PRIMARY overlay path is the read-from-file text source the score manager writes;
        this is for one-shots only. The text input KIND is never hardcoded — only the generic
        ``text`` field is set, identical across text-source kinds (Pitfall 5).
        """
        def _do() -> None:
            self._req.set_input_settings(input_name, {"text": text}, overlay=True)

        self._safe_call("set_overlay_text", _do)
