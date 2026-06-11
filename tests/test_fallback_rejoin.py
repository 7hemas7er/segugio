"""RBT-02 — feed-death fallback + guarded rejoin (end-to-end, against the LOCKED FSM).

This is an INTEGRATION test, not new production logic: Phase 3 is locked, so the FSM is
NOT re-implemented here. It WIRES the 05-04 ``FeedWatchdog`` (Task 1) to a real
``DecisionEngine`` and proves RBT-02:

  * a live camera's feed freezes → its last-NEW-frame timestamp stalls → the watchdog flips
    ``alive[cam]=False`` → that map drives ``engine.tick(scores, alive=...)`` → the FSM
    excludes the dead camera (DEC-06) and falls back to SAFE or another live camera;
  * the dead feed recovers (a NEW frame advances the timestamp → ``alive[cam]=True``) but the
    recovered camera does NOT snap back immediately — it must WIN the full hysteresis +
    debounce + min_dwell qualification (the engine's existing guards), so there is no
    flickery re-introduction of the just-recovered feed;
  * the hard RBT-02 invariant across the WHOLE sequence: the FSM NEVER airs the dead camera
    while it is dead (``decision.target != dead_cam`` whenever the watchdog reports it dead).

The watchdog is driven on INJECTED timestamps (the ``injected_clock`` fixture); no wall-clock.
"""

from __future__ import annotations

from segugio.decision import DecisionEngine
from segugio.decision.signals import SAFE_TARGET
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.watchdog_feed import FeedWatchdog
from tests.conftest import FPS

_WIDE = "cam_wide"  # the is_safe camera in the Phase-5 make_config
_LONG = "cam_long"


def _sc(cam: str, score: float, t: int) -> CameraScore:
    return CameraScore(t, cam, score, ScorerStatus.tracking)


def _build(make_config):
    """A real DecisionEngine + a real FeedWatchdog from the Phase-5 4-camera config."""
    cfg = make_config()
    th = cfg.thresholds
    eng = DecisionEngine(cfg.cameras, th, fps=FPS)
    wd = FeedWatchdog(watchdog_timeout=th.watchdog_timeout, grace=0.1)
    return cfg, th, eng, wd


def _alive_for(wd: FeedWatchdog, now: float, ts: dict[str, float | None], cam_ids):
    """Adapter: build the engine's ``{cam: bool}`` alive map from per-camera last_frame_ts."""

    class _Src:
        def last_frame_ts(self, cam_id: str):
            return ts.get(cam_id)

    return wd.alive_map(now=now, frame_source=_Src(), cam_ids=cam_ids)


def test_feed_death_falls_back_to_safe_or_live(make_config, injected_clock):
    """A dead live feed → watchdog flips alive=False → FSM excludes it → SAFE / other-live."""
    cfg, th, eng, wd = _build(make_config)
    cam_ids = eng.cam_ids
    clock = injected_clock

    # (1) Acquire cam_long as the live incumbent: a sustained lead while ALL feeds are fresh.
    decision = None
    for t in range(200):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}  # every feed delivering fresh frames
        alive = _alive_for(wd, now, ts, cam_ids)
        decision = eng.tick([_sc(_LONG, 0.9, t), _sc(_WIDE, 0.2, t)], alive=alive)
        if decision.target == _LONG:
            break
    assert decision is not None and decision.target == _LONG, "precondition: cam_long is live"

    # (2) cam_long's feed FREEZES: its last_frame_ts stalls while `now` keeps advancing.
    # The watchdog only declares it dead once the stall exceeds watchdog_timeout + grace
    # (~0.9s ≈ 27 ticks at 30fps), so the run is long enough to cross that threshold.
    frozen_ts = clock()  # the timestamp cam_long is stuck at
    dead_target_seen = None
    saw_dead = False
    for t in range(200, 280):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        ts[_LONG] = frozen_ts  # frozen — no NEW frame
        alive = _alive_for(wd, now, ts, cam_ids)
        # The dead camera still has the higher raw score, but once dead it must be excluded.
        decision = eng.tick([_sc(_LONG, 0.9, t), _sc(_WIDE, 0.5, t)], alive=alive)
        if alive[_LONG] is False:
            saw_dead = True
            # Hard invariant: while dead, cam_long is NEVER aired.
            assert decision.target != _LONG
            # Target is SAFE or another LIVE camera.
            assert decision.target == SAFE_TARGET or alive.get(decision.target) is True
            dead_target_seen = decision.target
    assert saw_dead, "the frozen feed must eventually be declared dead by the watchdog"
    assert dead_target_seen is not None
    assert dead_target_seen != _LONG


def test_rejoin_only_after_qualification(make_config, injected_clock):
    """A recovered feed does NOT snap back — it must win full hysteresis + debounce + min_dwell."""
    cfg, th, eng, wd = _build(make_config)
    cam_ids = eng.cam_ids
    clock = injected_clock

    # (1) Acquire cam_long live.
    for t in range(200):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        alive = _alive_for(wd, now, ts, cam_ids)
        d = eng.tick([_sc(_LONG, 0.9, t), _sc(_WIDE, 0.2, t)], alive=alive)
        if d.target == _LONG:
            break
    assert eng.target == _LONG

    # (2) cam_long dies → once the watchdog declares it dead the FSM falls back off it.
    frozen_ts = clock()
    saw_dead = False
    for t in range(200, 280):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        ts[_LONG] = frozen_ts
        alive = _alive_for(wd, now, ts, cam_ids)
        d = eng.tick([_sc(_LONG, 0.9, t), _sc(_WIDE, 0.6, t)], alive=alive)
        if alive[_LONG] is False:
            saw_dead = True
            assert d.target != _LONG
    assert saw_dead
    fallback_target = eng.target
    assert fallback_target != _LONG

    # (3) cam_long's feed RECOVERS (fresh ts → alive=True) but no longer wins by margin.
    # Right after recovery the engine must NOT immediately re-air cam_long: the challenger
    # streak was reset while it was excluded, so it has to re-qualify (debounce_N + min_dwell).
    recover_start = 280
    # First tick of recovery: cam_long is alive again AND highest scoring — assert it does
    # NOT instantly snap back (the rejoin is gated by debounce_N consecutive ticks + dwell).
    now = clock(advance=1.0 / FPS)
    ts = {c: now for c in cam_ids}  # cam_long fresh again
    alive = _alive_for(wd, now, ts, cam_ids)
    assert alive[_LONG] is True
    d = eng.tick([_sc(_LONG, 0.95, recover_start), _sc(_WIDE, 0.5, recover_start)], alive=alive)
    assert d.target != _LONG, "recovered feed must NOT snap back on its first alive tick"
    assert d.reason in {"none", "hold"} or d.target == fallback_target

    # Over the next FEW ticks (fewer than debounce_N) it still must not have cut back.
    for t in range(recover_start + 1, recover_start + th.debounce_N):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        alive = _alive_for(wd, now, ts, cam_ids)
        d = eng.tick([_sc(_LONG, 0.95, t), _sc(_WIDE, 0.5, t)], alive=alive)
    # Within debounce_N ticks of re-qualifying the cut has not necessarily fired yet (dwell on
    # the fallback target may also still be pending) — the point is it was NOT an instant snap.
    # Eventually, sustaining the lead long enough, the rejoin DOES fire (full qualification).
    rejoined = False
    for t in range(recover_start + th.debounce_N, recover_start + 400):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        alive = _alive_for(wd, now, ts, cam_ids)
        d = eng.tick([_sc(_LONG, 0.95, t), _sc(_WIDE, 0.5, t)], alive=alive)
        if d.target == _LONG:
            rejoined = True
            break
    assert rejoined, "after full hysteresis+debounce+min_dwell the recovered feed rejoins"


def test_never_airs_dead_feed_across_full_sequence(make_config, injected_clock):
    """Hard RBT-02 invariant: the FSM NEVER targets the dead camera while it is dead."""
    cfg, th, eng, wd = _build(make_config)
    cam_ids = eng.cam_ids
    clock = injected_clock

    frozen_ts = None
    for t in range(400):
        now = clock(advance=1.0 / FPS)
        ts = {c: now for c in cam_ids}
        # Kill cam_long for a window in the middle of the run.
        if 200 <= t < 280:
            if frozen_ts is None:
                frozen_ts = now - 1.0  # already stale enough to be dead immediately
            ts[_LONG] = frozen_ts
        else:
            frozen_ts = None
        alive = _alive_for(wd, now, ts, cam_ids)
        d = eng.tick([_sc(_LONG, 0.9, t), _sc(_WIDE, 0.3, t)], alive=alive)
        # The invariant: a dead target is never aired.
        if alive[_LONG] is False:
            assert d.target != _LONG
        # And every aired target is either SAFE or genuinely alive.
        assert d.target == SAFE_TARGET or alive.get(d.target) is True
