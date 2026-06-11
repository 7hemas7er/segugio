"""D-08 — sustained motion energy → HoldInput.action=True → FSM holds the cut.

Two layers (05-06 Task 1):
  (a) UNIT — ``ActionHoldDeriver`` returns ``HoldInput(action=True)`` ONLY after
      ``window_ticks`` of sustained over-threshold locked-subject motion energy, and
      ``action=False`` below threshold or before the window is reached. ``occlusion`` is
      ALWAYS ``False`` (occlusion-hold deferred in v1, D-08). The deriver is pure/clock-free
      (the per-tick energy is injected) — the same energy sequence yields the same
      ``HoldInput`` sequence every run.
  (b) INTEGRATION — feeding ``HoldInput(action=True)`` into a REAL ``DecisionEngine.tick(...)``
      HOLDS the current target through a would-be ``auto_switch`` (the cut is suppressed,
      ``reason == "hold"``) and the hold FORCE-RELEASES at the engine's
      ``action_hold_cap_ticks`` (DEC-03 max-cap) — using the real engine, no FSM logic
      re-implemented.
"""

from __future__ import annotations

from segugio.config.models import ActionHoldParams
from segugio.decision.engine import DecisionEngine
from segugio.decision.signals import HoldInput
from segugio.framing.signals import CameraScore, ScorerStatus
from segugio.orchestrator.action_hold import ActionHoldDeriver


# --------------------------------------------------------------------------- #
# (a) UNIT — the pure deriver                                                  #
# --------------------------------------------------------------------------- #


def test_sustained_motion_sets_action_hold():
    """>= motion_threshold sustained for window_ticks → action=True (occlusion always False)."""
    params = ActionHoldParams(motion_threshold=0.02, window_ticks=3)
    d = ActionHoldDeriver(params)

    # Ticks 0,1: over threshold but window (3) not yet reached → no hold.
    h0 = d.derive(0.05)
    h1 = d.derive(0.05)
    assert h0 == HoldInput(action=False, occlusion=False)
    assert h1 == HoldInput(action=False, occlusion=False)

    # Tick 2: the 3rd consecutive over-threshold tick reaches window_ticks → hold arms.
    h2 = d.derive(0.05)
    assert h2 == HoldInput(action=True, occlusion=False)

    # Stays held while sustained.
    assert d.derive(0.05) == HoldInput(action=True, occlusion=False)


def test_below_threshold_never_holds_and_resets_streak():
    """Below-threshold energy → action=False, and a dip resets the sustained count."""
    params = ActionHoldParams(motion_threshold=0.02, window_ticks=3)
    d = ActionHoldDeriver(params)

    d.derive(0.05)  # 1 over
    d.derive(0.05)  # 2 over
    assert d.derive(0.01) == HoldInput(action=False)  # dip below → reset, no hold

    # After the dip the streak restarts: two more over-threshold ticks are NOT enough.
    assert d.derive(0.05) == HoldInput(action=False)  # 1 over (post-reset)
    assert d.derive(0.05) == HoldInput(action=False)  # 2 over
    assert d.derive(0.05) == HoldInput(action=True)   # 3 over → arms again


def test_threshold_is_inclusive():
    """Energy EXACTLY at the threshold counts as over (>= comparison)."""
    params = ActionHoldParams(motion_threshold=0.02, window_ticks=1)
    d = ActionHoldDeriver(params)
    assert d.derive(0.02) == HoldInput(action=True)


def test_occlusion_never_set_true():
    """v1 wires ONLY the action hold — occlusion stays deferred False (D-08)."""
    params = ActionHoldParams(motion_threshold=0.02, window_ticks=1)
    d = ActionHoldDeriver(params)
    for energy in (0.0, 0.01, 0.02, 0.5, 100.0):
        assert d.derive(energy).occlusion is False


def test_deriver_is_clock_free_and_deterministic():
    """Same injected energy sequence → byte-identical HoldInput sequence every run."""
    params = ActionHoldParams(motion_threshold=0.02, window_ticks=4)
    seq = [0.05, 0.05, 0.0, 0.05, 0.05, 0.05, 0.05, 0.05, 0.01, 0.05]

    def run() -> list[HoldInput]:
        d = ActionHoldDeriver(params)
        return [d.derive(e) for e in seq]

    assert run() == run()


# --------------------------------------------------------------------------- #
# (b) INTEGRATION — the REAL DecisionEngine holds then releases at the cap     #
# --------------------------------------------------------------------------- #


class _Cam:
    """Minimal camera stand-in (the engine reads only ``.id``)."""

    def __init__(self, cam_id: str) -> None:
        self.id = cam_id


class _Thresholds:
    """Minimal thresholds stand-in (the engine reads these attributes only)."""

    hysteresis_margin = 0.1
    debounce_N = 1
    min_dwell = 0.0
    cooldown = 0.0


def _scores(tick: int, mapping: dict[str, float]) -> list[CameraScore]:
    return [
        CameraScore(tick, cam_id, score, ScorerStatus.tracking)
        for cam_id, score in mapping.items()
    ]


def test_action_hold_suppresses_a_qualified_cut_then_releases_at_cap():
    """A real DecisionEngine HOLDS through a would-be auto_switch, releases at the cap (DEC-03)."""
    cams = [_Cam("cam_a"), _Cam("cam_b")]
    cap = 5
    engine = DecisionEngine(
        cams,
        _Thresholds(),
        fps=30.0,
        action_hold_cap_ticks=cap,
        occlusion_hold_cap_ticks=cap,
    )

    # Warm up onto cam_a (no hold): cam_a clearly best → it gets aired.
    tick = 0
    for _ in range(3):
        engine.tick(_scores(tick, {"cam_a": 0.9, "cam_b": 0.0}), {"cam_a": True, "cam_b": True})
        tick += 1
    assert engine.target == "cam_a"

    # Now cam_b becomes clearly better — but an ACTION hold is active. The qualified cut MUST
    # be suppressed for exactly `cap` ticks, then force-release.
    held = HoldInput(action=True)
    suppressed_ticks = 0
    for _ in range(cap):
        dec = engine.tick(
            _scores(tick, {"cam_a": 0.0, "cam_b": 0.95}),
            {"cam_a": True, "cam_b": True},
            holds=held,
        )
        tick += 1
        if dec.reason == "hold":
            suppressed_ticks += 1
        assert engine.target == "cam_a", "the cut must be HELD while the action hold is active"

    assert suppressed_ticks >= 1, "at least one tick reported reason='hold'"

    # The tick AFTER the cap is reached: the hold force-releases and the qualified cut fires.
    dec = engine.tick(
        _scores(tick, {"cam_a": 0.0, "cam_b": 0.95}),
        {"cam_a": True, "cam_b": True},
        holds=held,
    )
    assert engine.target == "cam_b", "the hold must force-release at the cap → the cut fires"
    assert dec.reason == "auto_switch"
