"""OBS-03 — reconnect path re-creates the client after a simulated drop.

Behavior (05-03):
  - a simulated websocket drop → the controller re-creates the ReqClient/EventClient
    (reconnect+reauth) and resumes (OBS-03, Pitfall 4).
  - a failed cut coasts the loop (never crashes — RBT-04).
"""

from __future__ import annotations

from segugio.obs.obsws_controller import ObsWsController


class _FakeReq:
    """A recording ReqClient double; ``fail_next_cut`` raises once to simulate a drop."""

    def __init__(self) -> None:
        self.cuts: list[str] = []
        self.fail_next_cut = False

    def get_scene_item_id(self, scene, source):  # no PIP sources in these tests
        raise AssertionError("not used")

    def set_current_program_scene(self, scene_name):
        if self.fail_next_cut:
            self.fail_next_cut = False
            raise ConnectionError("simulated websocket drop")
        self.cuts.append(scene_name)

    def disconnect(self):  # teardown hook
        pass


class _FakeEvt:
    class _CB:
        def __init__(self) -> None:
            self.registered = []

        def register(self, fn):
            self.registered.append(fn)

    def __init__(self) -> None:
        self.callback = _FakeEvt._CB()

    def disconnect(self):
        pass


def _factory_recorder():
    """A client_factory that records every build (so we can count re-creations)."""
    builds: list[tuple] = []

    def factory(host, port, password):
        req, evt = _FakeReq(), _FakeEvt()
        builds.append((req, evt))
        return req, evt

    return factory, builds


def test_reconnect_recreates_client_after_drop():
    factory, builds = _factory_recorder()
    ctrl = ObsWsController(client_factory=factory)
    ctrl.connect()
    assert len(builds) == 1  # first client pair built at connect

    # a normal cut works on the first client
    ctrl.cut("CAM Wide")
    assert builds[0][0].cuts == ["CAM Wide"]

    # simulate a websocket drop on the next cut → controller reconnects + retries
    builds[0][0].fail_next_cut = True
    ctrl.cut("CAM Long")

    # a SECOND client pair was created (reconnect+reauth) and the cut resumed on it
    assert len(builds) == 2, "controller did not re-create the client after the drop"
    assert builds[1][0].cuts == ["CAM Long"]
    # the EventClient callback was re-registered on the new client (manual-cut sync survives)
    assert builds[1][1].callback.registered, "EventClient callback not re-registered"


def test_failed_cut_coasts_without_raising():
    """A persistent failure (drop on every cut) must coast, never raise (RBT-04)."""

    class _AlwaysFailReq(_FakeReq):
        def set_current_program_scene(self, scene_name):
            raise ConnectionError("OBS down")

    def factory(host, port, password):
        return _AlwaysFailReq(), _FakeEvt()

    ctrl = ObsWsController(client_factory=factory)
    ctrl.connect()
    # must NOT raise even though every cut (and the reconnect's retry) fails
    ctrl.cut("CAM Long")
