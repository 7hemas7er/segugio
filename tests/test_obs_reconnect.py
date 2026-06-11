"""OBS-03 — reconnect path re-creates the client after a simulated drop.

Behavior (05-03):
  - a simulated websocket drop → the controller re-creates the ReqClient/EventClient
    (reconnect+reauth) and resumes (OBS-03, Pitfall 4).
  - a failed cut coasts the loop (never crashes — RBT-04).
"""

from __future__ import annotations

from loguru import logger

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


def test_obs_down_from_start_coasts_quietly_then_recovers():
    """OBS down at startup → cuts coast WITHOUT a per-tick traceback; once OBS comes up the
    controller reconnects and resumes (RBT-04 + log hygiene).

    UAT-1 regression: with OBS down at launch, ``_req`` stays None and the old ``_safe_call``
    dumped a full ``logger.exception`` traceback EVERY tick (~90 lines/sec at 30 Hz), which buried
    the output. The failure logging is now throttled (first failure + a periodic heartbeat) and
    the cause is reported accurately ("no OBS connection"), while the op is still retried every
    tick so the director rejoins the instant OBS returns.
    """
    state = {"up": False}

    def factory(host, port, password):
        if not state["up"]:
            raise ConnectionRefusedError("OBS down")  # OBS not running yet
        return _FakeReq(), _FakeEvt()

    ctrl = ObsWsController(client_factory=factory)

    records: list = []
    sink = logger.add(records.append, level="DEBUG")
    try:
        # the orchestrator's _safe_startup absorbs the failed connect at launch
        try:
            ctrl.connect()
        except ConnectionRefusedError:
            pass

        # many ticks while OBS stays down — must never raise (RBT-04)
        for _ in range(200):
            ctrl.cut("CAM Wide")

        errors = [r for r in records if r.record["level"].name in ("ERROR", "CRITICAL")]
        warnings = [r for r in records if r.record["level"].name == "WARNING"]
        assert errors == [], "a down OBS must not dump per-tick exception tracebacks"
        assert 1 <= len(warnings) <= 3, f"failure logging not throttled: {len(warnings)} warnings"
        assert "no OBS connection" in str(warnings[0]), "cause should name the missing connection"

        # OBS comes up → the next cut reconnects, lands on the live client, logs ONE recovery line
        state["up"] = True
        records.clear()
        ctrl.cut("CAM Long")
        assert ctrl.current_scene == "CAM Long"  # the cut actually reached the (now live) client
        infos = [r for r in records if r.record["level"].name == "INFO"]
        assert any("recovered" in str(r) for r in infos), "expected a single recovery log line"
    finally:
        logger.remove(sink)
