"""RBT-05 — decision-loop latency harness: per-stage + total p95 < 150ms (target <80ms).

Two modes (05-06 Task 3):
  (1) MOCK-TIMED (headless, no GPU): substitute a fixed-cost inference stub and assert the
      WIRING-overhead total p95 is within a deterministic bound. This validates the loop's
      per-tick overhead (fan-out plumbing + scorer + FSM + status write + OBS cut) OFF the GPU —
      it does NOT include real YOLO inference (that is the gpu mode). The bound is generous (the
      headless box is shared / unpredictable) — the point is the harness records per-stage +
      total timings and the wiring overhead is comfortably sub-budget.
  (2) GPU (``@pytest.mark.gpu``): run the real ``yolo26s.pt`` over the mock frames on the
      RTX 4000 Ada and assert total p95 < 150ms (target <80ms) over a sustained window (RBT-05).
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
    # status write + OBS cut), no inference. This MUST be far under the 150ms budget.
    trackers = {cam.id: _FixedCostTracker(cost_s=0.0) for cam in cfg.cameras}
    orch = _orch(cfg, obs, trackers)

    timings = orch.run_measured(n_ticks=60)

    # The harness records per-stage + total timings.
    for stage in ("ingest", "yolo", "score", "fsm", "obs"):
        assert stage in timings and len(timings[stage]) == 60
    assert len(timings["total"]) == 60

    total_p95_ms = _p95(timings["total"]) * 1000.0
    # Deterministic bound: pure wiring overhead is a tiny fraction of the 150ms budget. A
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
    """GPU: the real yolo26s.pt loop total p95 < 150ms (target <80ms) over a sustained window.

    Collected + skipped off-GPU by the conftest gpu hook. On the RTX 4000 Ada (D-07) this drives
    the REAL ``PerCameraTracker`` (yolo26s.pt) over the mock clip frames and asserts the
    decision-loop latency budget. Degradation ladder if over budget: yolo26n -> fewer cams ->
    lower AI-path imgsz/fps (logged by run_measured).
    """
    cfg = make_config()
    obs = _OkObs()

    from segugio.tracking.detector import PerCameraTracker

    trackers = {
        cam.id: PerCameraTracker(cfg.model.path, cfg.model.class_index, "botsort_dog.yaml")
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
    assert total_p95_ms < 150.0, f"loop total p95 = {total_p95_ms:.1f}ms exceeds the 150ms budget"
