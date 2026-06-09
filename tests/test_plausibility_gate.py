"""TRK-05 ``PlausibilityGate`` pure-logic suite (inter-frame teleport/size-jump → coast).

The plausibility gate is the second half of the subject-selection brain (PITFALLS Pitfall
2): even after the competitor-lock picks a track, a silent BoT-SORT ID swap can hand the
locked id a DIFFERENT box (a bystander that "teleports" or size-jumps relative to the last
accepted box). TRK-05 rejects that inter-frame discontinuity → ``check`` returns ``None``
(the scorer holds its last EMA — coast) WITHOUT updating ``prev`` (so the suspect box never
becomes the new reference). It is provably DISTINCT from the Phase-2 intra-frame
``terms.plausibility_ok`` guard (D-07): different module, different signature
(``check(det)`` vs ``plausibility_ok(det, p)``), different state.

The seven must-have truths:

  1. teleport: Δcenter > max_displacement_per_tick → None AND ``prev`` unchanged (not poisoned).
  2. size-jump: area ratio outside [1/r, r] → None.
  3. continuous fast dog (false-positive guard): within-threshold per-tick motion is accepted.
  4. genuine miss: ``check(None)`` → None, ``prev`` unchanged (coast, not a rejection).
  5. distinct-from-Phase-2 (D-07): a box that PASSES ``terms.plausibility_ok`` but teleports
     relative to ``prev`` is STILL rejected by the gate — the two gates are independent.
  6. determinism: same sequence → byte-identical list of ``check`` outputs across two runs.
  7. recovery: after ``reset`` (genuine loss / re-acquire), the first new det is accepted.

Pure — no GPU, no clip; ``DetectionSignal`` sequences are fabricated directly.
"""

from __future__ import annotations

from segugio.framing.signals import DetectionSignal
from segugio.tracking.plausibility import PlausibilityGate

CAM_ID = "cam_a"


def _det(tick: int, cx: float, cy: float, w: float, h: float, conf: float = 0.8) -> DetectionSignal:
    """A fabricated locked-track ``DetectionSignal`` (track_id fixed — the gate is id-agnostic)."""
    return DetectionSignal(tick, CAM_ID, cx, cy, w, h, conf, 1)


def test_teleport_rejected_prev_not_poisoned(tracking_params) -> None:
    """A teleport (Δcenter > max_displacement_per_tick) → None AND ``prev`` is unchanged.

    Accept a first box, then feed one that jumps far beyond ``max_displacement_per_tick``.
    ``check`` returns None for that frame, and ``gate.prev`` is still the last ACCEPTED box
    (the teleport must NOT become the new reference — that is what lets the gate recover when
    the real track returns near the last good position).
    """
    gate = PlausibilityGate(tracking_params)
    first = _det(0, 0.40, 0.50, 0.10, 0.10)
    assert gate.check(first) is first  # accepted; becomes the reference
    assert gate.prev is first

    # Jump far beyond the per-tick displacement budget (default 0.15) → teleport.
    teleport = _det(1, 0.90, 0.50, 0.10, 0.10)
    disp = abs(teleport.cx - first.cx)
    assert disp > tracking_params.max_displacement_per_tick  # precondition: genuine teleport
    assert gate.check(teleport) is None  # rejected → coast
    assert gate.prev is first  # NOT poisoned — still the last accepted box


def test_size_jump_rejected(tracking_params) -> None:
    """A size jump beyond ``max_size_ratio`` (area ratio outside [1/r, r]) → None."""
    gate = PlausibilityGate(tracking_params)
    first = _det(0, 0.50, 0.50, 0.10, 0.10)  # area 0.01
    assert gate.check(first) is first

    # Area ratio = (0.20*0.20)/(0.10*0.10) = 4.0 > max_size_ratio (default 1.6) → reject.
    grown = _det(1, 0.50, 0.50, 0.20, 0.20)
    ratio = (grown.w * grown.h) / (first.w * first.h)
    assert ratio > tracking_params.max_size_ratio  # precondition: genuine size jump
    assert gate.check(grown) is None
    assert gate.prev is first  # not poisoned by the size-jump box either


def test_continuous_fast_dog_not_rejected(tracking_params) -> None:
    """A fast-but-continuous run (per-tick disp within threshold, stable area) is NOT rejected.

    The false-positive guard: a genuinely fast dog whose per-tick center jump stays within
    ``max_displacement_per_tick`` and whose area is stable must pass every tick, and ``prev``
    must advance to each accepted box.
    """
    gate = PlausibilityGate(tracking_params)
    step = tracking_params.max_displacement_per_tick * 0.8  # fast, but within budget
    cx = 0.10
    for tick in range(6):
        det = _det(tick, min(cx, 1.0), 0.50, 0.10, 0.10)
        out = gate.check(det)
        assert out is det  # accepted every tick
        assert gate.prev is det  # prev advances to each accepted box
        cx += step


def test_genuine_miss_coasts_prev_unchanged(tracking_params) -> None:
    """``check(None)`` → None and leaves ``prev`` unchanged (coast, NOT a rejection).

    A genuine miss (no locked candidate this tick) is a coast — distinct from a rejected
    teleport in cause but identical in effect (None). ``prev`` is preserved so the next real
    det is compared against the last GOOD box, not reset.
    """
    gate = PlausibilityGate(tracking_params)
    first = _det(0, 0.50, 0.50, 0.10, 0.10)
    gate.check(first)
    assert gate.prev is first

    assert gate.check(None) is None  # genuine miss → coast
    assert gate.prev is first  # unchanged — next det compares against the last good box


def test_distinct_from_phase2_intraframe_guard(tracking_params) -> None:
    """A box that PASSES ``terms.plausibility_ok`` but teleports relative to prev is REJECTED.

    D-07 independence: the Phase-2 intra-frame guard answers "is this a plausible dog box at
    all" (conf/area/aspect) — and a perfectly plausible box can STILL be an inter-frame
    teleport. The gate rejects it on continuity while ``plausibility_ok`` accepts it on
    appearance — proving the two gates are independent (different inputs, different purpose).
    """
    from segugio.config import ScorerParams
    from segugio.framing.terms import plausibility_ok

    sp = ScorerParams()
    # A perfectly plausible dog box: conf 0.8 > conf_floor, area 0.01 > min_area, aspect 1.0.
    plausible = _det(1, 0.90, 0.50, 0.10, 0.10, conf=0.8)
    assert plausibility_ok(plausible, sp) is True  # the Phase-2 guard accepts it on appearance

    gate = PlausibilityGate(tracking_params)
    gate.check(_det(0, 0.40, 0.50, 0.10, 0.10))  # establish prev far from the plausible box
    # Same box: appearance-plausible, but a teleport relative to prev → the gate rejects it.
    assert gate.check(plausible) is None  # inter-frame gate rejects what the intra-frame guard passed


def test_determinism_byte_identical_outputs(tracking_params) -> None:
    """Same locked-track sequence → byte-identical list of ``check`` outputs across two runs.

    A fixed sequence mixing accepted moves, a teleport, a miss, and a recovery, fed to two
    fresh gates, must produce identical output lists (frozen-record ``==``; ``None`` for the
    coast/reject ticks).
    """
    seq = [
        _det(0, 0.40, 0.50, 0.10, 0.10),
        _det(1, 0.48, 0.50, 0.10, 0.10),  # accepted (within budget)
        _det(2, 0.95, 0.50, 0.10, 0.10),  # teleport → None
        None,  # genuine miss → None
        _det(4, 0.50, 0.50, 0.10, 0.10),  # near last-good prev (0.48) → accepted
    ]

    def _run() -> list:
        gate = PlausibilityGate(tracking_params)
        return [gate.check(d) for d in seq]

    out_a = _run()
    out_b = _run()
    assert out_a == out_b  # byte-identical check() outputs (frozen records / None)
    assert out_a[2] is None and out_a[3] is None  # teleport + miss both coasted
    assert out_a[1] is not None and out_a[4] is not None  # the accepted ticks


def test_reset_recovers_accepts_first_new_det(tracking_params) -> None:
    """After ``reset`` (genuine loss / re-acquire), the first new det is accepted (no prev).

    ``reset`` clears ``prev`` so a freshly re-acquired track starts a NEW continuity chain;
    the first det has nothing to compare against and is accepted unconditionally — even if it
    is far from where the old track was (a legitimate new lock elsewhere on the field).
    """
    gate = PlausibilityGate(tracking_params)
    gate.check(_det(0, 0.40, 0.50, 0.10, 0.10))
    assert gate.prev is not None

    gate.reset()
    assert gate.prev is None  # continuity chain cleared

    # A det far from the old prev would have been a teleport — but after reset there is no
    # prev to compare against, so it is accepted and becomes the new reference.
    far = _det(5, 0.95, 0.50, 0.10, 0.10)
    assert gate.check(far) is far
    assert gate.prev is far
