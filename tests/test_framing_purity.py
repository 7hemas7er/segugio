"""FRM-07 purity/determinism gate — the phase's defining property.

This is the contract the whole scorer-before-detector ordering rests on: the scorer
is PURE, DETERMINISTIC, and I/O-FREE. It is exercised entirely on synthetic detection
sequences, with zero randomness inside the scorer, zero wall-clock, and zero
heavy-dependency imports — so it runs CPU-only on a box with no GPU/NDI runtime.

Three assertions lock FRM-07:

  * ``test_purity_determinism``: feeding the SAME ``list[DetectionSignal | None]``
    sequence (with a dropout window, so the present → coast → lost → recovery paths are
    all exercised) through TWO freshly-constructed scorers produces byte-identical
    ``list[CameraScore]`` — works because ``CameraScore`` is frozen. Mirrors
    ``tests/test_generators.py`` ``test_determinism_score_stream_same_seed_identical``
    (``assert run(seq) == run(seq)``) and its explicit ``np.random.default_rng(SEED)``.
  * ``test_no_io_imports_in_framing``: a source-grep over every ``src/segugio/framing/*.py``
    asserting none of them imports ``time`` / ``np.random`` / ``os`` / ``socket`` /
    ``requests`` nor any heavy dep — no nondeterministic source (clock/RNG) and no I/O
    can ever slip in (threat T-2-01 DoS / T-2-03 tampering mitigation). This is NEW for
    this phase — no Phase-1 test greps source.
  * ``test_framing_imports_with_heavy_absent``: with torch / ultralytics / cyndilib /
    obsws_python forced absent (``sys.modules[name] = None``), ``import segugio.framing``
    still succeeds (the lazy-import boundary). The extended ``PHASE1_SURFACE`` in
    ``test_imports.py`` also auto-runs the existing parametrized import-smoke for
    ``segugio.framing``; this asserts it directly for explicitness.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from segugio.config import Role
from segugio.config.models import Camera, Zone
from segugio.framing.scorer import CameraScorer
from segugio.framing.signals import CameraScore, DetectionSignal
from segugio.synth import detection_stream
from tests.conftest import SEED

# Reuse the test_imports harness so HEAVY_MODULES / the force-absent helper stay
# single-sourced (this test extends the same lazy-import boundary).
from tests.test_imports import HEAVY_MODULES, _force_heavy_absent

CAM_ID = "cam_a"
N_TICKS = 60
ALPHA = 0.3
# A dropout window strictly inside the run: present → coast → (TTL expiry) lost → recovery,
# so the determinism check covers EVERY branch of CameraScorer.update, not just the present
# path. The window (10 ticks) is comfortably longer than TTL_TICKS below so `lost` is reached.
DROPOUT = (20, 30)
TTL_TICKS = 4
# Neutral full-frame zone (multiplier == 1.0) so the determinism check exercises the state
# machine, not a particular zone gate.
_FULL_FRAME_WEIGHTS = {Role.main_wide: {"all": 1.0}}


def _scorer() -> CameraScorer:
    """A fresh CameraScorer over a single full-frame neutral zone (multiplier == 1.0)."""
    camera = Camera(
        id=CAM_ID,
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])],
    )
    from segugio.config import ScorerParams

    return CameraScorer(
        camera,
        ScorerParams(),
        _FULL_FRAME_WEIGHTS,
        alpha=ALPHA,
        lead_gain=0.0,
        ttl_ticks=TTL_TICKS,
    )


def _run(seq: list) -> list[CameraScore]:
    """Drive a freshly-constructed scorer over the whole sequence → its CameraScore list."""
    sc = _scorer()
    return [sc.update(det, t) for t, det in enumerate(seq)]


def _framing_py_files() -> list[Path]:
    """Every ``*.py`` source file under ``src/segugio/framing/`` (resolved via the package)."""
    framing_dir = Path(importlib.import_module("segugio.framing").__file__).parent
    files = sorted(framing_dir.glob("*.py"))
    assert files, f"no framing source files found under {framing_dir}"
    return files


def test_purity_determinism() -> None:
    """Same DetectionSignal sequence → byte-identical CameraScore list across two runs.

    The sequence includes a dropout window so the present, coast, lost, and recovery
    branches are all inside the determinism check. Built with an explicit
    ``np.random.default_rng(SEED)`` (the rng lives only in the synth generator — the scorer
    itself is rng-free). Two FRESH scorers fed the SAME sequence must agree byte-for-byte.
    """
    # Identical input sequence both times (same SEED → byte-identical list — precondition).
    seq_a = detection_stream(np.random.default_rng(SEED), CAM_ID, N_TICKS, dropout=DROPOUT)
    seq_b = detection_stream(np.random.default_rng(SEED), CAM_ID, N_TICKS, dropout=DROPOUT)
    assert seq_a == seq_b  # the synth input is itself deterministic (FRM-07 precondition).

    out_a = _run(seq_a)
    out_b = _run(seq_b)

    # Byte-identical CameraScore lists — the FRM-07 determinism contract (frozen records).
    assert out_a == out_b
    assert len(out_a) == N_TICKS
    # The dropout window did exercise the coast/lost path (not a vacuous present-only run).
    statuses = {cs.status.value for cs in out_a}
    assert "tracking" in statuses
    assert "coasting" in statuses or "lost" in statuses


def test_no_io_imports_in_framing() -> None:
    """No framing source imports time / np.random / os / socket / requests / any heavy dep.

    A source-grep style assertion: the scorer is pure — time enters only as the injected
    ``tick``, randomness lives only in the synth generator, and no module does I/O or pulls
    a heavy runtime. This is what makes the determinism + lazy-import boundary structural
    (no nondeterministic source can slip in unnoticed).
    """
    # Patterns that must NOT appear anywhere in framing source. Word-boundary regexes so a
    # substring like "atime" or "ostream" never triggers a false positive.
    forbidden = {
        "import time": re.compile(r"(?m)^\s*import\s+time\b"),
        "from time import": re.compile(r"(?m)^\s*from\s+time\s+import\b"),
        "np.random": re.compile(r"\bnp\.random\b"),
        "numpy.random": re.compile(r"\bnumpy\.random\b"),
        "import os": re.compile(r"(?m)^\s*import\s+os\b"),
        "from os import": re.compile(r"(?m)^\s*from\s+os\s+import\b"),
        "import socket": re.compile(r"(?m)^\s*import\s+socket\b"),
        "import requests": re.compile(r"(?m)^\s*import\s+requests\b"),
    }
    # Heavy / GPU / NDI deps — none may be imported at module top level (lazy-import boundary).
    for name in (*HEAVY_MODULES, "cv2"):
        forbidden[f"import {name}"] = re.compile(rf"(?m)^\s*import\s+{re.escape(name)}\b")
        forbidden[f"from {name} import"] = re.compile(
            rf"(?m)^\s*from\s+{re.escape(name)}\s+import\b"
        )

    for path in _framing_py_files():
        source = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            assert not pattern.search(source), (
                f"{path.name} must not contain {label!r} "
                f"(framing/ is pure: no time / np.random / I/O / heavy import)"
            )


def test_framing_imports_with_heavy_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``import segugio.framing`` succeeds with torch/ultralytics/cyndilib/obsws absent.

    Replicates the ``test_imports`` force-absent pattern (``sys.modules[name] = None`` makes
    the heavy import raise) and drops any cached ``segugio.*`` so the import re-runs under
    the block. Explicit here for FRM-07; ``PHASE1_SURFACE`` also covers it parametrically.
    """
    _force_heavy_absent(monkeypatch)
    # Sanity: the block is real — heavy imports raise.
    for name in HEAVY_MODULES:
        with pytest.raises(ImportError):
            importlib.import_module(name)
    # Drop cached segugio modules so the import re-runs under the heavy-absent block.
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)

    module = importlib.import_module("segugio.framing")
    assert module is not None
    # The pure scorer surface is reachable with the heavy runtime absent.
    assert hasattr(module, "CameraScorer")
    assert hasattr(module, "MultiCamScorer")


# --------------------------------------------------------------------------- #
# Phase coverage gate — small focused assertions on the remaining real        #
# behavior branches the FRM-01..06 suites did not happen to hit.              #
# --------------------------------------------------------------------------- #


def test_zone_overlap_picks_highest_weight(scorer_params) -> None:
    """zone_of: on OVERLAPPING zones, pick the HIGHEST framing_weights match (terms.py:130-131).

    A point inside two zones must resolve to the higher-weight zone (the CONTEXT
    Claude's-Discretion overlap rule), not just first-match. Two zones both covering
    (0.5, 0.5); ``hi`` carries the larger weight → it wins.
    """
    from segugio.framing.terms import zone_of

    camera = Camera(
        id=CAM_ID,
        role=Role.main_wide,
        obs_scene="WIDE",
        is_safe=True,
        zones=[
            Zone(name="lo", rect=[0.0, 0.0, 1.0, 1.0]),
            Zone(name="hi", rect=[0.0, 0.0, 1.0, 1.0]),
        ],
    )
    weights = {Role.main_wide: {"lo": 0.8, "hi": 1.6}}
    assert zone_of(0.5, 0.5, camera, weights) == "hi"  # highest-weight match on overlap.
    # A missing weight key falls back to the neutral 1.0 for the comparison (never raises).
    assert zone_of(0.5, 0.5, camera, {Role.main_wide: {}}) in ("lo", "hi")


def test_zero_height_detection_is_implausible(scorer_params) -> None:
    """plausibility_ok: a zero/negative-height box is implausible (terms.py:199 guard).

    Guards the aspect-ratio division (``w / h``) AND treats a degenerate box as
    "no detection" — the scorer must coast on it rather than raise.
    """
    from segugio.framing.terms import plausibility_ok

    zero_h = DetectionSignal(0, CAM_ID, 0.5, 0.5, 0.30, 0.0, 0.7, 1)
    assert plausibility_ok(zero_h, scorer_params) is False  # caught by the min-area gate.

    # Degenerate box reaching the explicit `h <= 0` guard (terms.py:199): a malformed
    # tracker row with NEGATIVE w AND negative h has a POSITIVE area (> min_area), so it
    # slips past the conf-floor and min-area gates and must be caught by the height guard
    # — which also guards the aspect-ratio division `w / h` from a zero/negative divisor.
    neg_box = DetectionSignal(0, CAM_ID, 0.5, 0.5, -0.20, -0.01, 0.7, 1)
    assert neg_box.w * neg_box.h >= scorer_params.min_area  # positive area slips the gates.
    assert plausibility_ok(neg_box, scorer_params) is False  # caught by `h <= 0` (line 199).

    # End-to-end: a zero-height detection flows into the coast path (status not tracking),
    # and the scorer never raises on it.
    sc = _scorer()
    out = sc.update(zero_h, 0)
    assert out.status.value in ("coasting", "lost")  # treated as no-detection → coast.


def test_velocity_guards_nonpositive_tick_span(scorer_params) -> None:
    """CameraScorer._velocity returns (0,0) on a non-positive tick span (scorer.py:146 guard).

    Two present detections stamped at the SAME tick give ``dt == 0``; the divisor guard
    must return zero velocity (no lead) rather than dividing by zero (threat T-2-01). The
    scorer never raises and the score stays in [0,1].
    """
    sc = _scorer()
    sc.update(DetectionSignal(0, CAM_ID, 0.5, 0.5, 0.30, 0.30, 0.7, 1), 0)
    # Same tick again (same track id → history is appended, not cleared) → dt == 0.
    out = sc.update(DetectionSignal(0, CAM_ID, 0.6, 0.5, 0.30, 0.30, 0.7, 1), 0)
    assert sc._velocity() == (0.0, 0.0)  # non-positive span → no velocity (guarded divisor).
    assert 0.0 <= out.score <= 1.0


def test_new_track_after_lost_cold_starts(scorer_params) -> None:
    """A re-acquisition AFTER `lost` cold-starts the EMA to raw_0 (no stale-EMA carry-over).

    The D-04 boundary: recovery WITHIN the TTL continues the held EMA, but once the scorer
    has gone `lost` (TTL expired, ema sentinel reset to None) a present detection re-seeds
    the EMA from raw_0 (the cold-start path, D-05) — NOT alpha*raw blended from a stale 0.0.
    Regression guard for CR-01: a re-acquired, well-framed camera must emit its true framing
    score immediately so the selector can switch to it, not a suppressed alpha*raw that
    ramps up over ~1/alpha ticks.
    """
    # The cold-start raw_0 a FRESH scorer emits for the identical recovery detection. With
    # warmup=10, the recovery (the 6th conf sample: 5 present + this one) is still inside the
    # conf-norm passthrough window, exactly like a fresh scorer's first sample — so the raw
    # is identical and this is the precise value a correct cold-start must reproduce.
    cold = _scorer().update(
        DetectionSignal(0, CAM_ID, 0.5, 0.5, 0.30, 0.30, 0.7, 2), 0
    ).score
    assert cold > 0.0

    sc = _scorer()
    # Track 1: warm up, then drop out long enough to go `lost` (TTL_TICKS misses).
    for t in range(5):
        sc.update(DetectionSignal(t, CAM_ID, 0.5, 0.5, 0.30, 0.30, 0.7, 1), t)
    for i in range(TTL_TICKS):
        last = sc.update(None, 5 + i)
    assert last.status.value == "lost"
    assert last.score == 0.0

    # Track 2 (NEW track id) after lost: the present branch clears history (track swap) and
    # re-seeds the EMA from raw_0 — tracking resumes from the cold-start raw, not from 0.0.
    recover_tick = 5 + TTL_TICKS
    out = sc.update(
        DetectionSignal(recover_tick, CAM_ID, 0.5, 0.5, 0.30, 0.30, 0.7, 2), recover_tick
    )
    assert out.status.value == "tracking"
    # Cold-started from raw_0 — the FULL raw, NOT alpha*raw (the CR-01 stale-EMA-carry bug,
    # which would emit ALPHA * cold ≈ 0.3*raw and suppress the re-acquired camera).
    assert out.score == pytest.approx(cold)
    assert out.score != pytest.approx(ALPHA * cold)
