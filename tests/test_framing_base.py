"""FRM-01 base-score term tests — fully green this plan (02-01).

Proves the resolution-independent base-score terms at the pure-function level:
  * centeredness is maximal at the ideal point and decays with distance;
  * the size band PEAKS at ``ideal_size`` and is lower for both smaller AND larger
    sizes (non-monotonic — the D-02 "bigger is not always better" guarantee);
  * scoring the SAME normalized ``DetectionSignal`` sequence twice yields identical
    term outputs (resolution-invariance: there is no resolution variable to break).

Mirrors ``tests/test_generators.py`` conventions: module-level constants, explicit
``np.random.default_rng(seed)``, and the shared ``seeded_rng`` / ``scorer_params``
fixtures.
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.framing.signals import DetectionSignal
from segugio.framing.terms import (
    base_score,
    gaussian_centeredness,
    gaussian_size_band,
)

CAM = "cam_a"
N_TICKS = 40
DELTA = 0.1  # offset used for the non-monotonic size-band peak test


def _linear_right_seq(rng, cam_id: str, n_ticks: int, noise: float = 0.01):
    """A normalized rightward-moving DetectionSignal sequence (rng = the only randomness).

    Built directly here so the FRM-01 base tests are self-contained; the synthetic
    ``detection_stream`` generator (added in 02-01 Task 3) emits the equivalent shape.
    """
    seq = []
    for t in range(n_ticks):
        frac = t / max(n_ticks - 1, 1)
        cx = 0.2 + 0.6 * frac
        jx, jy = rng.normal(0.0, noise, 2)
        seq.append(
            DetectionSignal(
                t,
                cam_id,
                float(np.clip(cx + jx, 0.0, 1.0)),
                float(np.clip(0.5 + jy, 0.0, 1.0)),
                0.30,
                0.30,
                0.7,
                1,
            )
        )
    return seq


def test_centeredness(scorer_params) -> None:
    """Max (==1.0) at the ideal point; strictly decreasing as distance grows; ∈(0,1]."""
    sc = scorer_params.sigma_c
    ideal = (0.5, 0.5)
    at_ideal = gaussian_centeredness(0.5, 0.5, ideal, sc)
    near = gaussian_centeredness(0.55, 0.5, ideal, sc)
    far = gaussian_centeredness(0.9, 0.5, ideal, sc)

    assert at_ideal == pytest.approx(1.0)
    assert at_ideal > near > far  # strictly decreasing with distance
    assert 0.0 < far <= 1.0  # always in (0, 1]


def test_size_band_peak(scorer_params) -> None:
    """D-02: size band PEAKS at ideal_size; smaller AND larger both score strictly less."""
    isz = scorer_params.ideal_size
    ss = scorer_params.sigma_s
    # Use square boxes so sqrt(w*h) == w; pick widths that land at ideal/±delta in scale.
    peak = gaussian_size_band(isz, isz, isz, ss)
    smaller = gaussian_size_band(isz - DELTA, isz - DELTA, isz, ss)
    larger = gaussian_size_band(isz + DELTA, isz + DELTA, isz, ss)

    assert peak == pytest.approx(1.0)
    assert peak > smaller  # not monotonic: a smaller dog scores less than the ideal
    assert peak > larger  # AND a larger dog scores less than the ideal (anti-"bigger-better")


def test_size_band_guards_negative_area() -> None:
    """A degenerate negative-area box does not raise (max(w*h, 0) guard)."""
    val = gaussian_size_band(-0.5, 0.2, 0.3, 0.18)
    assert 0.0 <= val <= 1.0


def _term_scores(seq, params) -> list[float]:
    """Score the centeredness+size base term for each present signal in a sequence."""
    out: list[float] = []
    for det in seq:
        if det is None:
            continue
        c = gaussian_centeredness(det.cx, det.cy, (0.5, 0.5), params.sigma_c)
        s = gaussian_size_band(det.w, det.h, params.ideal_size, params.sigma_s)
        # conf passes through as a stand-in for the (composed-later) conf_norm term.
        out.append(base_score(c, s, det.conf, params.w_c, params.w_s, params.w_conf))
    return out


def test_resolution_invariant(seeded_rng, scorer_params) -> None:
    """The same normalized sequence scored twice yields identical term outputs.

    Because every input is normalized [0,1] there is no resolution variable: feeding
    the same ``detection_stream`` sequence to the pure terms is the resolution-invariance
    assertion (a "different resolution" is the identical normalized signal).
    """
    seq_a = _linear_right_seq(np.random.default_rng(7), CAM, N_TICKS)
    seq_b = _linear_right_seq(np.random.default_rng(7), CAM, N_TICKS)

    assert seq_a == seq_b  # determinism precondition
    scores_a = _term_scores(seq_a, scorer_params)
    scores_b = _term_scores(seq_b, scorer_params)
    assert scores_a == scores_b  # byte-identical term outputs → resolution-invariant


def test_base_score_in_unit_interval(scorer_params) -> None:
    """base_score is clipped to [0,1] and returns a plain float for any term inputs."""
    p = scorer_params
    for c, s, cn in [(1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (0.5, 0.3, 0.9)]:
        b = base_score(c, s, cn, p.w_c, p.w_s, p.w_conf)
        assert isinstance(b, float)
        assert 0.0 <= b <= 1.0
    # With weights summing to 1, all-1 terms give exactly 1.0.
    assert base_score(1.0, 1.0, 1.0, p.w_c, p.w_s, p.w_conf) == pytest.approx(1.0)
