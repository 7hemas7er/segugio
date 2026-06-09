"""DEC-07 determinism suite — same seed + scenario → byte-identical list[Decision].

This is the FSM's defining property, the exact analogue of the Phase-2 scorer's FRM-07
purity gate (``tests/test_framing_purity.py``): the engine is PURE, DETERMINISTIC, and
I/O-FREE, exercised entirely on the shipped synthetic substrates with zero randomness
inside the FSM, zero wall-clock, and zero heavy-dependency imports — so it runs CPU-only
with no GPU/NDI runtime.

Three assertions lock DEC-07:

  * ``test_purity_determinism``: for each of the four named ``SCENARIOS`` the synthetic
    INPUT stream is itself deterministic (``score_stream(SEED) == score_stream(SEED)`` — the
    precondition), AND driving TWO freshly-constructed engines over that stream produces
    byte-identical ``list[Decision]`` (works because ``Decision`` is frozen). Mirrors the
    ``test_framing_purity.py`` ``_run(seq)`` / ``assert _run(a) == _run(b)`` pattern and its
    explicit ``np.random.default_rng(SEED)``.
  * ``test_purity_determinism_full_input_contract``: the determinism check ALSO drives a
    feed-death liveness timeline + an occlusion-hold window + an override command through the
    FULL ``tick(scores, alive, holds, override)`` contract — proving determinism over the
    WHOLE input surface, not just the bare score path. Two fresh engines, the same timeline,
    byte-identical ``list[Decision]``.
  * ``test_all_scenarios_drive_without_error``: parametrized over ``SCENARIOS`` — each scenario
    drives a fresh engine to a complete ``list[Decision]`` of the expected length with no
    exception, and every ``Decision.mode`` is a valid ``Mode``.

The synthetic input is generated once with an explicit ``np.random.default_rng(SEED)`` (the
rng lives only in the synth generators — the FSM itself is rng-free and clock-free), reusing
the shipped ``score_stream`` / ``feed_death`` substrates and the ``SEED`` / ``FPS`` /
``_as_camera_scores`` seams from conftest exactly as ``test_framing_purity.py`` reuses ``SEED``
(no ad-hoc generators).
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.decision import DecisionEngine
from segugio.decision.signals import Decision, HoldInput, Mode, OverrideCmd
from segugio.framing.signals import CameraScore
from segugio.synth import SCENARIOS, feed_death, score_stream
from tests.conftest import FPS, SEED, _as_camera_scores

_CAM_A = "cam_a"  # cam_a is_safe + config-declared first → the no-incumbent tiebreak winner
_CAM_B = "cam_b"
_CAM_IDS = [_CAM_A, _CAM_B]
N_TICKS = 120


def _two_cameras() -> list[Camera]:
    """Two cameras (cam_a is_safe), each a single full-frame neutral zone (multiplier 1.0)."""
    return [
        Camera(
            id=cid,
            role=Role.main_wide,
            obs_scene="WIDE",
            is_safe=(cid == _CAM_A),
            zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
        )
        for cid in _CAM_IDS
    ]


def _engine(thresholds) -> DecisionEngine:
    """A FRESH DecisionEngine over the two-camera config (the system under test)."""
    return DecisionEngine(_two_cameras(), thresholds, fps=FPS)


def _scores_by_tick(scenario: str, seed: int) -> dict[int, list[CameraScore]]:
    """The shipped ``score_stream`` for ``scenario``, adapted to ``CameraScore`` and grouped by tick.

    Reuses the deterministic ``score_stream`` + the conftest ``_as_camera_scores`` adapter
    (no ad-hoc generator); same seed → byte-identical grouped scores.
    """
    samples = _as_camera_scores(
        score_stream(np.random.default_rng(seed), scenario, _CAM_IDS, N_TICKS)
    )
    by_tick: dict[int, list[CameraScore]] = {}
    for s in samples:
        by_tick.setdefault(s.tick, []).append(s)
    return by_tick


def _alive_by_tick(seed: int) -> dict[int, dict[str, bool]]:
    """A deterministic feed-death liveness timeline (cam_b dies at 50, recovers 30 ticks later)."""
    events = feed_death(
        np.random.default_rng(seed),
        _CAM_IDS,
        N_TICKS,
        death_at={_CAM_B: 50},
        recover_after=30,
    )
    by_tick: dict[int, dict[str, bool]] = {}
    for e in events:
        by_tick.setdefault(e.tick, {})[e.cam_id] = e.alive
    return by_tick


def _run_scores_only(scenario: str, seed: int, thresholds) -> list[Decision]:
    """Drive a freshly-constructed engine over the bare score stream → its ``list[Decision]``.

    The bare-score path: every camera is treated alive (no alive map), no holds, no override —
    so this isolates the core auto-switching determinism over the synthetic scenario substrate.
    """
    eng = _engine(thresholds)
    by_tick = _scores_by_tick(scenario, seed)
    return [eng.tick(by_tick[t]) for t in range(N_TICKS)]


def _run_full_contract(scenario: str, seed: int, thresholds) -> list[Decision]:
    """Drive a fresh engine over the FULL ``tick(scores, alive, holds, override)`` contract.

    Layers a deterministic feed-death alive timeline, an occlusion-hold window, and a single
    force→release override pair onto the score stream — so the determinism assertion covers the
    ENTIRE typed input surface, not just bare scores. All three extra streams are functions of
    the tick index (and ``seed`` for the liveness timeline) only → fully reproducible.
    """
    eng = _engine(thresholds)
    scores_by_tick = _scores_by_tick(scenario, seed)
    alive_by_tick = _alive_by_tick(seed)

    out: list[Decision] = []
    for t in range(N_TICKS):
        # An occlusion-hold window in the middle of the run (a deterministic tick range).
        holds = HoldInput(occlusion=70 <= t < 80)
        # A force on cam_b at tick 20, an explicit release at tick 90 — both deterministic.
        if t == 20:
            override = OverrideCmd(force_cam=_CAM_B)
        elif t == 90:
            override = OverrideCmd(release=True)
        else:
            override = None
        out.append(
            eng.tick(scores_by_tick[t], alive=alive_by_tick[t], holds=holds, override=override)
        )
    return out


def test_purity_determinism(thresholds) -> None:
    """Same seed + scenario → byte-identical ``list[Decision]`` across two fresh engines.

    For each of the four named ``SCENARIOS``: the synthetic INPUT stream is itself
    deterministic (the precondition), and two freshly-constructed engines driven over it agree
    byte-for-byte (frozen ``Decision`` records). This is the DEC-07 contract on the bare score
    path; the full-input-contract variant below extends it to alive + holds + override.
    """
    for scenario in SCENARIOS:
        # Precondition: the synth input is itself deterministic (mirrors the FRM-07 gate).
        stream_a = score_stream(np.random.default_rng(SEED), scenario, _CAM_IDS, N_TICKS)
        stream_b = score_stream(np.random.default_rng(SEED), scenario, _CAM_IDS, N_TICKS)
        assert stream_a == stream_b, f"{scenario}: synth score stream is not deterministic"

        out_a = _run_scores_only(scenario, SEED, thresholds)
        out_b = _run_scores_only(scenario, SEED, thresholds)

        assert out_a == out_b, f"{scenario}: engine is not byte-identical on replay (DEC-07)"
        assert len(out_a) == N_TICKS, f"{scenario}: decision list is not the expected length"


def test_purity_determinism_full_input_contract(thresholds) -> None:
    """Determinism holds over the FULL ``tick(scores, alive, holds, override)`` input contract.

    Two fresh engines driven over the same score stream + the same feed-death liveness timeline
    + the same occlusion-hold window + the same force/release override pair produce byte-identical
    ``list[Decision]`` — proving the determinism is a property of the whole typed input surface,
    not just the bare scores. Runs across all four ``SCENARIOS`` so the death/hold/override
    interactions are exercised on every substrate.
    """
    for scenario in SCENARIOS:
        out_a = _run_full_contract(scenario, SEED, thresholds)
        out_b = _run_full_contract(scenario, SEED, thresholds)

        assert out_a == out_b, (
            f"{scenario}: full-contract (scores+alive+holds+override) replay is not "
            f"byte-identical (DEC-07)"
        )
        assert len(out_a) == N_TICKS

        # The override stream really engaged: at least one OVERRIDE-mode decision is present
        # (a vacuous run that never entered override would not exercise the full contract).
        assert any(d.mode == Mode.override for d in out_a), (
            f"{scenario}: the override command never put the engine into OVERRIDE mode — "
            f"the full input contract was not exercised"
        )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_scenarios_drive_without_error(scenario: str, thresholds) -> None:
    """Every named scenario drives a fresh engine to a complete, valid ``list[Decision]``.

    A coverage-of-substrate guard: each of the four ``SCENARIOS`` runs the full input contract
    end-to-end with no exception (fail-safe — the FSM never raises, T-3-04), yields exactly
    ``N_TICKS`` decisions, and every ``Decision.mode`` is a valid ``Mode`` member.
    """
    decisions = _run_full_contract(scenario, SEED, thresholds)

    assert len(decisions) == N_TICKS
    for d in decisions:
        # Mode is a valid enum member (round-trips through Mode without raising).
        assert isinstance(d.mode, Mode)
        assert d.mode in Mode
        # The aired target is always one of the declared cameras or the SAFE sentinel.
        assert d.target in (_CAM_A, _CAM_B, "SAFE")
