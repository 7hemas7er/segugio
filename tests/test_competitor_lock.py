"""TRK-04 ``CompetitorLock`` pure-logic suite on the synthetic multi-track substrate.

The competitor-lock is the project's defining brain (PITFALLS Pitfall 1): it must pick the
in-competition dog (in-zone AND moving) over a larger/more-central but out-of-zone,
stationary bystander/handler. These tests are PURE (no GPU, no clip) — they drive the lock
on the deterministic ``multi_track_stream`` substrate (04-01) and on hand-built
``DetectionSignal`` candidates, asserting the seven must-have truths:

  1. athlete-over-bystander: zone∧motion beats size/centeredness at acquisition.
  2. sticky continuity (D-04): once locked, a higher-motion in-zone competitor does NOT
     steal the lock — re-pick only on genuine loss.
  3. genuine loss → re-acquire: dropping the locked id re-acquires on zone∧motion.
  4. nothing in-field → coast: all candidates out-of-zone → ``select`` returns None.
  5. per-camera independence (D-05): two locks over different streams lock different ids
     and share no state.
  6. determinism: same stream → byte-identical selected-signal sequence across two runs.
  7. fail-safe: a NaN-cx candidate is treated as not-in-field (coast), never raises.

The ``camera`` is built from the canonical happy-path Config (``cam_wide`` with full-width
near/mid/far zones spanning x∈[0,1] but y-banded) so an out-of-FIELD box is one whose cy is
outside every zone band (cy < 0 or cy > 1 is impossible for normalized boxes, so we use a
custom centered-field Camera where an off-field box is genuinely outside ALL zones).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from segugio.config import Config, Role
from segugio.config.models import Camera, Zone
from segugio.framing.signals import DetectionSignal
from segugio.synth.detection_stream import multi_track_stream
from segugio.tracking.competitor_lock import CompetitorLock
from tests.conftest import SEED, _VALID_CONFIG

CAM_ID = "cam_a"


def _centered_field_camera(cam_id: str = CAM_ID) -> Camera:
    """A camera with ONE centered field zone so an off-field box is genuinely outside.

    The field zone is the central rect [0.3,0.3]-[0.7,0.7]; a box at cy=0.5,cx in [0.3,0.7]
    is IN-field, a box at cx=0.05 (far left) or cx=0.95 (far right) is OUT-of-field. This
    isolates the zone gate cleanly (the happy-path ``cam_wide`` zones span full width, so a
    left/right bystander would still be in-zone — a centered field is the right substrate).
    """
    return Camera(
        id=cam_id,
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        zones=[Zone(name="field", rect=[0.3, 0.3, 0.7, 0.7])],
    )


def test_athlete_over_bystander() -> None:
    """Lock the in-zone MOVING athlete, NOT the larger/central but out-of-zone stationary box.

    Track A (id=1): in-field, high cumulative motion (cx walks across the central zone).
    Track B (id=2): out-of-field (cx far left), stationary, LARGER + more central box.
    Zone∧motion must beat size/centeredness — the lock returns A's id at acquisition.
    """
    camera = _centered_field_camera()
    lock = CompetitorLock(camera, _tracking_params())

    selected_id = None
    # Walk A across the central field; B sits stationary far-left, bigger box.
    for tick in range(6):
        a_cx = 0.35 + 0.05 * tick  # 0.35→0.60, inside [0.3,0.7], moving
        athlete = DetectionSignal(tick, CAM_ID, a_cx, 0.5, 0.10, 0.10, 0.8, 1)
        bystander = DetectionSignal(tick, CAM_ID, 0.05, 0.5, 0.40, 0.40, 0.9, 2)
        sel = lock.select([athlete, bystander], tick)
        if sel is not None:
            selected_id = sel.track_id

    assert lock.locked_id == 1  # the in-zone moving athlete
    assert selected_id == 1


def test_sticky_continuity_does_not_switch() -> None:
    """After locking A, a higher-motion in-zone competitor B does NOT steal the lock (D-04).

    Lock A first (only in-field track for a few ticks). Then introduce B in-field with HIGHER
    motion. ``locked_id`` must stay A and ``select`` must return A's signal — re-pick happens
    only on genuine loss, never mid-run on a momentarily-better competitor.
    """
    camera = _centered_field_camera()
    lock = CompetitorLock(camera, _tracking_params())

    # Acquire A: in-field, moving, only candidate.
    for tick in range(4):
        a_cx = 0.35 + 0.03 * tick
        lock.select([DetectionSignal(tick, CAM_ID, a_cx, 0.5, 0.10, 0.10, 0.8, 1)], tick)
    assert lock.locked_id == 1

    # Now B appears in-field with much higher motion; A barely moves but stays present.
    for tick in range(4, 8):
        a = DetectionSignal(tick, CAM_ID, 0.47, 0.5, 0.10, 0.10, 0.8, 1)  # nearly static
        b_cx = 0.30 + 0.10 * (tick - 4)  # fast sweep across the field
        b = DetectionSignal(tick, CAM_ID, b_cx, 0.5, 0.10, 0.10, 0.8, 2)
        sel = lock.select([a, b], tick)
        assert lock.locked_id == 1  # sticky: A keeps the lock despite B's higher motion
        assert sel is not None and sel.track_id == 1


def test_genuine_loss_reacquires_on_zone_and_motion() -> None:
    """Dropping the locked id (genuine loss) re-acquires the best remaining in-field track.

    Lock A, then drop A from candidates entirely while B (in-field, moving) remains. The lock
    must re-acquire B on zone∧motion and ``locked_id`` updates to B's id.
    """
    camera = _centered_field_camera()
    lock = CompetitorLock(camera, _tracking_params())

    # Acquire A (only in-field track).
    for tick in range(4):
        a_cx = 0.35 + 0.03 * tick
        lock.select([DetectionSignal(tick, CAM_ID, a_cx, 0.5, 0.10, 0.10, 0.8, 1)], tick)
    assert lock.locked_id == 1

    # A disappears; B is in-field and moving — re-acquire B.
    for tick in range(4, 9):
        b_cx = 0.32 + 0.06 * (tick - 4)
        b = DetectionSignal(tick, CAM_ID, b_cx, 0.5, 0.10, 0.10, 0.8, 2)
        sel = lock.select([b], tick)

    assert lock.locked_id == 2  # re-acquired the remaining in-field track
    assert sel is not None and sel.track_id == 2


def test_nothing_in_field_coasts() -> None:
    """All candidates out-of-zone → ``select`` returns None and ``locked_id`` is None."""
    camera = _centered_field_camera()
    lock = CompetitorLock(camera, _tracking_params())

    for tick in range(5):
        # Both far-left / far-right of the central field → outside every zone.
        left = DetectionSignal(tick, CAM_ID, 0.05, 0.5, 0.10, 0.10, 0.8, 1)
        right = DetectionSignal(tick, CAM_ID, 0.95, 0.5, 0.10, 0.10, 0.8, 2)
        sel = lock.select([left, right], tick)
        assert sel is None

    assert lock.locked_id is None


def test_per_camera_independence() -> None:
    """Two CompetitorLock instances over different streams lock different ids, no shared state.

    Lock_a sees only track 1 in-field; lock_b sees only track 7 in-field. They must lock
    distinct ids, and advancing one does not perturb the other's ``locked_id`` (D-05).
    """
    cam_a = _centered_field_camera("cam_a")
    cam_b = _centered_field_camera("cam_b")
    lock_a = CompetitorLock(cam_a, _tracking_params())
    lock_b = CompetitorLock(cam_b, _tracking_params())

    for tick in range(5):
        cx = 0.35 + 0.03 * tick
        lock_a.select([DetectionSignal(tick, "cam_a", cx, 0.5, 0.10, 0.10, 0.8, 1)], tick)
        lock_b.select([DetectionSignal(tick, "cam_b", cx, 0.5, 0.10, 0.10, 0.8, 7)], tick)

    assert lock_a.locked_id == 1
    assert lock_b.locked_id == 7
    # Mutating lock_a's state must not touch lock_b's lock.
    for tick in range(5, 10):
        lock_a.select([DetectionSignal(tick, "cam_a", 0.5, 0.5, 0.10, 0.10, 0.8, 1)], tick)
    assert lock_b.locked_id == 7  # untouched by lock_a's continued operation


def test_determinism_byte_identical_selection() -> None:
    """Same synthetic stream → byte-identical sequence of selected signals across two runs.

    Uses the deterministic ``multi_track_stream`` (same SEED → identical per-tick detections)
    and a happy-path ``cam_wide`` camera so two fresh locks driven over the same stream emit
    the identical ``list[DetectionSignal | None]`` (frozen-record ``==``).
    """
    camera = Config.model_validate(_VALID_CONFIG).cameras[0]  # cam_wide, full-width zones
    tracks = [
        {"track_id": 1, "path": "linear_right", "size": 0.12, "conf": 0.8},
        {"track_id": 2, "path": "linear_left", "size": 0.18, "conf": 0.85},
    ]

    def _run() -> list:
        rng = np.random.default_rng(SEED)
        stream = multi_track_stream(rng, CAM_ID, 30, tracks)
        lock = CompetitorLock(camera, _tracking_params())
        return [lock.select(per_tick, t) for t, per_tick in enumerate(stream)]

    out_a = _run()
    out_b = _run()
    assert out_a == out_b  # byte-identical selected-signal sequence (frozen records)
    assert any(s is not None for s in out_a)  # not a vacuous all-None run


def test_nan_candidate_is_failsafe() -> None:
    """A NaN-cx candidate is treated as not-in-field (coast); ``select`` never raises.

    The lone candidate has a NaN center → it must be excluded from history / alive_ids /
    in_field, so the lock coasts (returns None, ``locked_id`` stays None) rather than raising
    or locking a poisoned box (threat T-04-02-03).
    """
    camera = _centered_field_camera()
    lock = CompetitorLock(camera, _tracking_params())

    nan_det = DetectionSignal(0, CAM_ID, float("nan"), 0.5, 0.10, 0.10, 0.8, 1)
    sel = lock.select([nan_det], 0)  # must not raise
    assert sel is None
    assert lock.locked_id is None


def _tracking_params():
    """Seeded ``TrackingParams`` (TRK-04 motion_window / motion_deadzone seeds)."""
    from segugio.tracking.params import TrackingParams

    return TrackingParams()
