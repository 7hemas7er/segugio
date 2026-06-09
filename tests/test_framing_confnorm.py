"""FRM-06 confidence-normalization tests — the brighter-camera anti-bias (02-02).

The failure this prevents (PITFALL 10): a uniformly brighter/clearer camera yields
systematically higher YOLO confidence, so a raw-confidence term would bias selection
toward it regardless of framing. The per-camera streaming z-score normalizes confidence
*relative to that camera's own baseline*, so a constant +bias washes out after warmup.

Asserts:
  * two ``detection_stream``s with IDENTICAL framing but ``conf_bias=+0.2`` score within
    epsilon after warmup (the brighter camera does NOT win on confidence alone);
  * an INTRA-camera confidence spike still raises that camera's ``conf_norm`` (the
    normalizer reports *relative* confidence — it isn't simply flat).
"""

from __future__ import annotations

import numpy as np
import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.framing.scorer import CameraScorer
from segugio.framing.signals import DetectionSignal
from segugio.framing.terms import conf_norm_step
from segugio.synth import detection_stream

N_TICKS = 60  # well past the default warmup (10 samples)
SEED = 1234
EPS = 1e-9


def _scorer(params) -> CameraScorer:
    """A full-frame neutral scorer (zone multiplier 1.0) so only conf differs."""
    camera = Camera(
        id="cam",
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
    )
    return CameraScorer(
        camera,
        params,
        {Role.main_wide: {"all": 1.0}},
        alpha=0.3,
        lead_gain=0.0,  # static path anyway; keep the ideal centered
        ttl_ticks=N_TICKS + 1,
    )


def _final_score(params, conf_bias: float) -> float:
    """Run a static, identical-framing stream (only conf differs) → the final score."""
    sc = _scorer(params)
    stream = detection_stream(
        np.random.default_rng(SEED),
        "cam",
        N_TICKS,
        path="static",
        conf=0.7,
        conf_bias=conf_bias,
        noise=0.0,  # identical framing across both runs — isolate confidence
    )
    last = None
    for det in stream:
        last = sc.update(det, det.tick)
    return last.score


def test_brightness_anti_bias(scorer_params) -> None:
    """Two cams identical but +conf bias score within epsilon; intra-cam spike still registers."""
    # Both runs use the SAME framing (static, noise=0); the only difference is a uniform
    # +0.2 confidence offset on the "bright" camera. After warmup the per-camera z-score
    # has the same baseline → conf_norm is identical → the scores match within epsilon.
    dim = _final_score(scorer_params, conf_bias=0.0)
    bright = _final_score(scorer_params, conf_bias=0.2)
    assert abs(bright - dim) < 1e-6  # normalization removed the brightness advantage

    # --- Intra-camera spike still registers (the normalizer reports RELATIVE conf) ---
    # Walk a steady baseline past warmup, then a single spike: conf_norm must rise above
    # the steady-state (which sits near 0.5 = "typical for this camera").
    p = scorer_params
    state = {"n": 0, "mu": 0.0, "var": 0.0}
    steady = None
    for _ in range(N_TICKS):
        steady, state = conf_norm_step(state, 0.6, p.beta, p.z_clip, p.eps, p.warmup)
    spiked, _ = conf_norm_step(state, 0.95, p.beta, p.z_clip, p.eps, p.warmup)
    assert spiked > steady  # a relative spike raises this camera's conf_norm
    assert steady == pytest.approx(0.5, abs=1e-6)  # a flat baseline normalizes to ~0.5
