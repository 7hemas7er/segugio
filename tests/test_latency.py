"""RBT-05 — decision-loop latency harness: per-stage + total p95 < 300ms (relaxed from 150ms, 2026-06-13).

Two modes (05-06 Task 3):
  (1) MOCK-TIMED (headless, no GPU): substitute a fixed-cost inference stub and assert the
      WIRING-overhead total p95 is within a deterministic bound. This validates the loop's
      per-tick overhead (fan-out plumbing + scorer + FSM + status write + OBS cut) OFF the GPU —
      it does NOT include real YOLO inference (that is the gpu mode). The bound is generous (the
      headless box is shared / unpredictable) — the point is the harness records per-stage +
      total timings and the wiring overhead is comfortably sub-budget.
  (2) GPU (``@pytest.mark.gpu``): run the real ``yolo26s.pt`` over the mock frames on the
      RTX 4000 Ada and assert total p95 < 300ms over a sustained window (RBT-05).
      Collected + skipped off-GPU via the existing gpu-skip hook (conftest).

The latency probe is ADDITIVE in ``Orchestrator.run_measured`` — it does not change the tick's
pipeline logic; it only wraps each stage with ``perf_counter`` deltas and returns
``{stage: [per-tick seconds], "total": [...]}``.
"""

from __future__ import annotations

import pytest

from segugio.orchestrator.loop import Orchestrator


def _p95(values: list[float]) -> float:
    """The 95th-percentile of a list of per-tick durations (nearest-rank, deterministic)."""
    assert values, "no timing samples recorded"
    ordered = sorted(values)
    # nearest-rank: ceil(0.95 * n) - 1, clamped to the last index.
    import math

    idx = min(len(ordered) - 1, max(0, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[idx]


class _OkObs:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def connect(self) -> None:
        self.calls.append(("connect",))

    def cut(self, scene_name: str) -> None:
        self.calls.append(("cut", scene_name))

    def set_overlay_text(self, input_name: str, text: str) -> None:
        pass

    def close(self) -> None:
        self.calls.append(("close",))


class _Frame:
    """A non-empty frame stand-in (``.size > 0`` so the NDI-03 guard publishes it)."""

    size = 1


class _FixedCostTracker:
    """A mock tracker with a deterministic fixed inference cost (no GPU, no YOLO).

    Returns no detections (the loop coasts) but consumes a fixed wall-time so the harness has a
    realistic, deterministic 'yolo' stage to time without loading the heavy stack.
    """

    def __init__(self, cost_s: float = 0.0) -> None:
        self.cost_s = cost_s

    def track(self, frame):
        if self.cost_s:
            import time

            time.sleep(self.cost_s)
        return None


def _orch(cfg, obs, trackers):
    from segugio.ndi.clip_source import ClipReplayFrameSource

    def _iter():
        for tick in range(200):
            yield (tick, {cam.id: _Frame() for cam in cfg.cameras})

    source = ClipReplayFrameSource(frames_iter=_iter())
    from pathlib import Path
    import tempfile

    d = Path(tempfile.mkdtemp())
    channel_paths = {
        "command": d / "command.json",
        "runstate": d / "runstate.json",
        "status": d / "status.json",
    }
    return Orchestrator.from_config(
        config=cfg, source=source, obs=obs, channel_paths=channel_paths,
        trackers=trackers, fps=30.0,
    )


def test_mock_timed_wiring_overhead_p95_under_bound(make_config):
    """MOCK-TIMED: the loop's WIRING-overhead total p95 is comfortably sub-budget off-GPU."""
    cfg = make_config()
    obs = _OkObs()
    # Zero-cost trackers → the measured total is pure wiring overhead (fan-out + scorer + FSM +
    # status write + OBS cut), no inference. This MUST be far under the 300ms budget.
    trackers = {cam.id: _FixedCostTracker(cost_s=0.0) for cam in cfg.cameras}
    orch = _orch(cfg, obs, trackers)

    timings = orch.run_measured(n_ticks=60)

    # The harness records per-stage + total timings.
    for stage in ("ingest", "yolo", "score", "fsm", "obs"):
        assert stage in timings and len(timings[stage]) == 60
    assert len(timings["total"]) == 60

    total_p95_ms = _p95(timings["total"]) * 1000.0
    # Deterministic bound: pure wiring overhead is a tiny fraction of the 300ms budget. A
    # generous 50ms ceiling absorbs shared-CI jitter while still proving the loop overhead is
    # not itself a latency risk (the inference cost is the gpu mode's concern).
    assert total_p95_ms < 50.0, f"wiring-overhead total p95 = {total_p95_ms:.2f}ms (bound 50ms)"


def test_mock_timed_fixed_inference_cost_is_attributed_to_yolo(make_config):
    """The fixed per-tick inference cost shows up in the 'yolo' stage (probe attribution)."""
    cfg = make_config()
    obs = _OkObs()
    cost = 0.002  # 2ms fixed cost per camera track call
    trackers = {cam.id: _FixedCostTracker(cost_s=cost) for cam in cfg.cameras}
    orch = _orch(cfg, obs, trackers)

    timings = orch.run_measured(n_ticks=20)

    # With N cameras each costing `cost`, the 'yolo' stage (the fan-out inference) is >= N*cost.
    n_cams = len(cfg.cameras)
    yolo_p95_ms = _p95(timings["yolo"]) * 1000.0
    assert yolo_p95_ms >= (n_cams * cost * 1000.0) * 0.8, (
        f"yolo stage p95 {yolo_p95_ms:.2f}ms should reflect the {n_cams}x{cost*1000:.0f}ms cost"
    )


@pytest.mark.gpu
def test_loop_latency_p95_under_budget(make_config, tmp_path):
    """GPU: the real yolo26s.pt loop total p95 < 300ms over a sustained window.

    Collected + skipped off-GPU by the conftest gpu hook. On the RTX 4000 Ada (D-07) this drives
    the REAL ``PerCameraTracker`` (yolo26s.pt) over the mock clip frames and asserts the
    decision-loop latency budget. Degradation ladder if over budget: yolo26n -> fewer cams ->
    lower AI-path imgsz/fps (logged by run_measured).
    """
    # MEASUREMENT SETUP: the CANONICAL path is eager FP16 + batched detection (use_fp16=True,
    # engine_path=None). It clears the 300ms RBT-05 budget (~213ms p95 on the RTX 4000 Ada) AND
    # preserves native-feature BoT-SORT ReID — the engine path loses native ReID to a cls fallback,
    # so eager is the chosen prod path (decision 2026-06-13). The TensorRT engine remains an
    # OPTIONAL higher-margin lever (~197ms p95): point config.model.engine_path at a built
    # yolo26s.engine and the engine-aware PerCameraTracker loads it, with graceful eager fallback
    # on ANY load failure (RBT-04). Build it via ``tools/build_engine.py`` on the deploy GPU.
    cfg = make_config(
        overrides={
            "model": {
                "path": "yolo26s.pt",
                "class_index": 16,
                "use_fp16": True,
                "engine_path": None,  # canonical eager FP16+batch (native ReID); set a path to measure the engine
            }
        }
    )
    obs = _OkObs()

    from segugio.tracking.detector import PerCameraTracker

    trackers = {
        cam.id: PerCameraTracker(
            cfg.model.path,
            cfg.model.class_index,
            "botsort_dog.yaml",
            use_fp16=cfg.model.use_fp16,
            engine_path=cfg.model.engine_path,
        )
        for cam in cfg.cameras
    }

    # Real frames (numpy) over the mock source so the real tracker runs inference. Use small
    # synthetic BGR frames; the latency budget is about the loop, not detection accuracy.
    import numpy as np

    def _iter():
        for tick in range(120):
            frame = (np.random.rand(360, 640, 3) * 255).astype("uint8")
            yield (tick, {cam.id: frame for cam in cfg.cameras})

    from segugio.ndi.clip_source import ClipReplayFrameSource

    source = ClipReplayFrameSource(frames_iter=_iter())
    channel_paths = {
        "command": tmp_path / "command.json",
        "runstate": tmp_path / "runstate.json",
        "status": tmp_path / "status.json",
    }
    orch = Orchestrator.from_config(
        config=cfg, source=source, obs=obs, channel_paths=channel_paths,
        trackers=trackers, fps=30.0,
    )

    # Warm up a few ticks (first inference includes model/engine spin-up), then measure.
    orch.run_measured(n_ticks=20)
    timings = orch.run_measured(n_ticks=100)

    total_p95_ms = _p95(timings["total"]) * 1000.0
    assert total_p95_ms < 300.0, f"loop total p95 = {total_p95_ms:.1f}ms exceeds the 300ms budget"


def _gpu_latency_orch(cfg, channel_dir, *, preview_enabled):
    """Build a REAL gpu orchestrator (yolo26s.pt) with preview ON or OFF, over numpy frames.

    Mirrors ``test_loop_latency_p95_under_budget``'s real ``PerCameraTracker`` +
    ``ClipReplayFrameSource`` setup but routes through ``build_orchestrator`` so the DEFAULT
    preview factory constructs a real ``PreviewPublisher`` when ``config.preview.enabled`` — the
    SAME wiring the live ``python -m segugio`` path uses (HARD GATE 1 measures the prod path).
    """
    import numpy as np

    from segugio.orchestrator.runtime import build_orchestrator

    enabled_cfg = cfg.model_copy(
        update={"preview": cfg.preview.model_copy(update={"enabled": bool(preview_enabled)})}
    )

    def source_factory(cameras):
        from segugio.ndi.clip_source import ClipReplayFrameSource

        def _iter():
            for tick in range(300):
                frame = (np.random.rand(360, 640, 3) * 255).astype("uint8")
                yield (tick, {cam.id: frame for cam in cameras})

        return ClipReplayFrameSource(frames_iter=_iter())

    return build_orchestrator(
        enabled_cfg,
        str(channel_dir),
        fps=30.0,
        source_factory=source_factory,
        obs_factory=lambda host, port, password: _OkObs(),
    )


@pytest.mark.gpu
def test_loop_latency_p95_preview_on_no_regression(make_config, tmp_path):
    """HARD GATE 1 (PRV-01/SC1/D-09): the real preview publisher ON does NOT regress the 4-cam p95.

    Collected + skipped off-GPU by the conftest gpu hook (this machine's CPU-only venv has no GPU;
    the GPU stack lives in venv312 — run on the rig: ``python -m pytest -m gpu tests/test_latency.py``).

    The load-bearing risk D-09 gates on is the guarded ``offer()`` taxing the tick. We measure it
    DIRECTLY: derive the run-to-run noise band from two back-to-back preview-OFF runs (NO magic
    number — RESEARCH Q1/A3), then run the REAL ``PreviewPublisher`` ON under the SAME harness and
    assert ``p95_on <= p95_off + noise_band``. The publisher is constructed by ``build_orchestrator``'s
    DEFAULT factory (the prod wiring), so this proves the live path, not a stub.
    """
    cfg = make_config(
        overrides={
            "model": {
                "path": "yolo26s.pt",
                "class_index": 16,
                "use_fp16": True,
                "engine_path": None,  # canonical eager FP16+batch (native ReID)
            }
        }
    )

    # ── Derive the noise band: two back-to-back preview-OFF runs (run-to-run jitter). ──
    off = _gpu_latency_orch(cfg, tmp_path / "off", preview_enabled=False)
    off.run_measured(n_ticks=20)  # warm up (first inference includes model spin-up)
    p95_off_a = _p95(off.run_measured(n_ticks=100)["total"]) * 1000.0
    p95_off_b = _p95(off.run_measured(n_ticks=100)["total"]) * 1000.0
    off.shutdown()
    noise_band = abs(p95_off_a - p95_off_b)
    p95_off = max(p95_off_a, p95_off_b)  # the conservative OFF baseline

    # ── Measure preview ON with the REAL publisher running under run_measured. ──
    on = _gpu_latency_orch(cfg, tmp_path / "on", preview_enabled=True)
    assert on._preview is not None, "preview ON must construct a real publisher"
    on.run_measured(n_ticks=20)  # warm up
    p95_on = _p95(on.run_measured(n_ticks=100)["total"]) * 1000.0
    on.shutdown()

    assert p95_on <= p95_off + noise_band, (
        f"preview ON regressed the tick p95: on={p95_on:.1f}ms off={p95_off:.1f}ms "
        f"band={noise_band:.1f}ms (on must be <= off + band)"
    )
