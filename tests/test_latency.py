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


def _percentile(values: list[float], q: float) -> float:
    """The ``q``-quantile of a list of per-tick durations (nearest-rank, deterministic).

    Generalises ``_p95``: nearest-rank ``ceil(q * n) - 1`` clamped to ``[0, n-1]``. ``q`` in
    ``[0, 1]`` (e.g. ``0.95`` for p95, ``0.99`` for p99).
    """
    assert values, "no timing samples recorded"
    ordered = sorted(values)
    import math

    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _p95(values: list[float]) -> float:
    """The 95th-percentile of a list of per-tick durations (nearest-rank, deterministic)."""
    return _percentile(values, 0.95)


# ── Absolute latency gates (Fix #1, replacing the flaky relative noise-band) ─────────────────
# A catastrophic-tail ceiling comfortably above the 300ms p95 budget (RBT-05): p99 AND the single
# worst tick must stay under this. It bounds a runaway tail spike without pinning the exact number
# (absolute latency needs AC power; the box may be battery-throttled — see dev-box-perf note).
_TAIL_BUDGET_MS = 400.0
# The preview-ON path may add at most this fixed ms over the preview-OFF baseline (an absolute
# regression margin — the guarded offer() is a single locked mailbox assignment, so any real
# regression is small and bounded, not a noise band derived from two jittery OFF runs).
_PREVIEW_REGRESSION_MARGIN_MS = 15.0
# The preview-ON p95 must also stay this far UNDER the 300ms RBT-05 budget (absolute headroom).
_ABSOLUTE_HEADROOM_MS = 20.0


def _looptest_clip_or_skip():
    """Resolve the real looptest dog clip, or ``pytest.skip`` when its binary is absent.

    The fixture (``tests/fixtures/looptest/cam_wide_9898282.mp4``) is present on the rig and
    gitignored elsewhere — so off-rig this SKIPs (never fails) exactly like the gpu gate.
    """
    from pathlib import Path

    clip = Path(__file__).parent / "fixtures" / "looptest" / "cam_wide_9898282.mp4"
    if not clip.is_file():
        pytest.skip(f"looptest fixture absent: {clip} (present on the rig; gitignored elsewhere)")
    return clip


# Cap on the number of DISTINCT decoded frames held in memory (a 1080p BGR frame is ~6MB, so
# 60 distinct frames ~360MB); the iterator cycles them to reach n_ticks. 60 frames is ample real
# dog imagery for the tracker to detect + run native ReID on every tick.
_LOOPTEST_MAX_FRAMES = 60

# The looptest fixture is 4K (3840x2160); production NDI HX3 phone feeds are ~1080p (CLAUDE.md
# NDI sender notes). Downscale each decoded frame to 1080p so the measured latency reflects the
# PRODUCTION feed resolution — not the fixture's heavier-than-real 4K preprocessing cost — while
# still feeding a REAL dog the tracker detects (the point of Fix #1). Frames already ≤ this height
# are left untouched.
_LOOPTEST_TARGET_HEIGHT = 1080


def _decode_looptest_frames(n: int):
    """Decode up to ``min(n, _LOOPTEST_MAX_FRAMES)`` real BGR frames from the looptest clip.

    Imports cv2 lazily (inside the body) so ``import tests.test_latency`` succeeds with cv2
    absent. Each frame is downscaled to a production-representative ~1080p (the fixture is 4K;
    phone HX3 feeds are ~1080p) so the timing reflects the real feed resolution. Loops the clip
    when it holds fewer frames than requested. ``pytest.skip`` if the clip decodes zero frames.
    """
    import cv2

    clip = str(_looptest_clip_or_skip())
    want = min(n, _LOOPTEST_MAX_FRAMES)
    frames: list = []
    cap = cv2.VideoCapture(clip)
    try:
        while len(frames) < want:
            ok, frame = cap.read()
            if not ok:
                # Loop the clip from the top when it is shorter than `want` frames.
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                if not ok:
                    break
            h = frame.shape[0]
            if h > _LOOPTEST_TARGET_HEIGHT:
                scale = _LOOPTEST_TARGET_HEIGHT / float(h)
                frame = cv2.resize(
                    frame,
                    (int(round(frame.shape[1] * scale)), _LOOPTEST_TARGET_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                )
            frames.append(frame)
    finally:
        cap.release()
    if not frames:
        pytest.skip(f"looptest clip decoded 0 frames: {clip}")
    return frames


def _looptest_frames(cam_ids, n_ticks: int):
    """Yield ``(tick, {cam_id: frame})`` over ``n_ticks`` using REAL decoded dog frames.

    The SAME decoded frame is fanned to every camera each tick, so every per-camera tracker runs
    real inference on a real dog (non-zero detections → the batched BoT-SORT ``update()`` +
    native-ReID ``result.feats`` cost restored by 296ed3e is actually timed). Frames are cycled
    when the clip is shorter than ``n_ticks``.
    """
    frames = _decode_looptest_frames(n_ticks)
    cam_ids = list(cam_ids)
    for tick in range(n_ticks):
        frame = frames[tick % len(frames)]
        yield (tick, {cam_id: frame for cam_id in cam_ids})


def _assert_nonzero_detection(tracker, frames) -> None:
    """Warm up the tracker on real frames and assert at least one yields a detection.

    Proves detections are non-zero (the dog IS detected) so the ReID/feats path is genuinely
    exercised in the timed loop — mirrors the warmup+assert style in
    ``tests/test_yolo_clips_eval.py::test_native_reid_engaged``. Tries a handful of frames so a
    single frame where the dog is momentarily out of view does not flake the gate.
    """
    total = 0
    for frame in frames[:10]:
        results = tracker.track(frame)
        boxes = getattr(results, "boxes", None) if results is not None else None
        if boxes is not None:
            try:
                total += len(boxes)
            except TypeError:  # pragma: no cover - defensive on an odd boxes stand-in
                pass
        if total >= 1:
            break
    assert total >= 1, (
        "expected non-zero detections on real looptest dog frames — the ReID/feats path must be "
        "live (a np.random frame detects 0 dogs and never times the real BoT-SORT update cost)"
    )


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

    from segugio.tracking.detector import PerCameraTracker, resolve_dog_index

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

    # FUNCTIONAL non-zero-detection warmup (Fix #1): before the timed loop, resolve the dog index
    # BY NAME and warm up a DEDICATED throwaway tracker on real decoded looptest frames, asserting
    # at least one detection — proving the dog is detected so the batched BoT-SORT update() +
    # native-ReID result.feats path is actually exercised (a np.random frame detects 0 dogs and
    # never times it). The warmup tracker is SEPARATE from the loop's `trackers` on purpose: the
    # serial `.track()` warmup registers Ultralytics' own on_predict_start on that tracker's model,
    # and the batched loop reuses `trackers`' first model for its single detection forward — warming
    # one of the loop trackers would pollute that shared model's callbacks and break the batched
    # feats hook (feats→None → the native encoder gets the raw frame → coast). Keep them disjoint.
    warmup_frames = _decode_looptest_frames(10)
    _warm = PerCameraTracker(
        cfg.model.path,
        cfg.model.class_index,
        "botsort_dog.yaml",
        use_fp16=cfg.model.use_fp16,
        engine_path=cfg.model.engine_path,
    )
    try:
        _warm.dog_idx = resolve_dog_index(_warm.model, cfg.model.class_index)
    except (AttributeError, TypeError):  # pragma: no cover - real model always resolves
        pass
    _assert_nonzero_detection(_warm, warmup_frames)

    # REAL frames over the mock source so every per-camera tracker runs real inference on a real
    # dog (Fix #1) — the latency now reflects the live ReID cost, not a np.random understatement.
    from segugio.ndi.clip_source import ClipReplayFrameSource

    source = ClipReplayFrameSource(
        frames_iter=_looptest_frames([cam.id for cam in cfg.cameras], 120)
    )
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

    # TAIL gate (Fix #1): a catastrophic tail spike must not hide behind a healthy p95. Bound BOTH
    # the p99 and the single worst tick under a fixed absolute ceiling comfortably above the budget.
    total_p99_ms = _percentile(timings["total"], 0.99) * 1000.0
    total_max_ms = max(timings["total"]) * 1000.0
    assert total_p99_ms < _TAIL_BUDGET_MS, (
        f"loop total p99 = {total_p99_ms:.1f}ms exceeds the {_TAIL_BUDGET_MS:.0f}ms tail ceiling"
    )
    assert total_max_ms < _TAIL_BUDGET_MS, (
        f"loop total max = {total_max_ms:.1f}ms exceeds the {_TAIL_BUDGET_MS:.0f}ms tail ceiling"
    )


def _gpu_latency_orch(cfg, channel_dir, *, preview_enabled):
    """Build a REAL gpu orchestrator (yolo26s.pt) with preview ON or OFF, over numpy frames.

    Mirrors ``test_loop_latency_p95_under_budget``'s real ``PerCameraTracker`` +
    ``ClipReplayFrameSource`` setup but routes through ``build_orchestrator`` so the DEFAULT
    preview factory constructs a real ``PreviewPublisher`` when ``config.preview.enabled`` — the
    SAME wiring the live ``python -m segugio`` path uses (HARD GATE 1 measures the prod path).
    """
    from segugio.orchestrator.runtime import build_orchestrator

    enabled_cfg = cfg.model_copy(
        update={"preview": cfg.preview.model_copy(update={"enabled": bool(preview_enabled)})}
    )

    def source_factory(cameras):
        from segugio.ndi.clip_source import ClipReplayFrameSource

        # REAL decoded looptest dog frames (Fix #1) so the tracker times the live ReID cost.
        return ClipReplayFrameSource(
            frames_iter=_looptest_frames([cam.id for cam in cameras], 300)
        )

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
    DIRECTLY against ABSOLUTE gates (Fix #1 — replacing the flaky two-OFF-run noise band): keep ONE
    preview-OFF baseline run and ONE preview-ON run (both over REAL looptest dog frames), then
    assert ``p95_on <= p95_off + _PREVIEW_REGRESSION_MARGIN_MS`` (a fixed absolute regression
    margin) AND ``p95_on < 300.0 - _ABSOLUTE_HEADROOM_MS`` (fixed absolute headroom under the RBT-05
    budget). The publisher is constructed by ``build_orchestrator``'s DEFAULT factory (the prod
    wiring), so this proves the live path, not a stub.
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

    # ── ONE preview-OFF baseline run (over REAL looptest frames). ──
    off = _gpu_latency_orch(cfg, tmp_path / "off", preview_enabled=False)
    off.run_measured(n_ticks=20)  # warm up (first inference includes model spin-up)
    p95_off = _p95(off.run_measured(n_ticks=100)["total"]) * 1000.0
    off.shutdown()

    # ── ONE preview-ON run with the REAL publisher running under run_measured. ──
    on = _gpu_latency_orch(cfg, tmp_path / "on", preview_enabled=True)
    assert on._preview is not None, "preview ON must construct a real publisher"
    on.run_measured(n_ticks=20)  # warm up
    p95_on = _p95(on.run_measured(n_ticks=100)["total"]) * 1000.0
    on.shutdown()

    # ABSOLUTE regression margin: preview ON adds at most a fixed ms over the OFF baseline.
    assert p95_on <= p95_off + _PREVIEW_REGRESSION_MARGIN_MS, (
        f"preview ON regressed the tick p95: on={p95_on:.1f}ms off={p95_off:.1f}ms "
        f"(on must be <= off + {_PREVIEW_REGRESSION_MARGIN_MS:.0f}ms absolute margin)"
    )
    # ABSOLUTE headroom: preview ON must stay a fixed margin under the 300ms RBT-05 budget.
    assert p95_on < 300.0 - _ABSOLUTE_HEADROOM_MS, (
        f"preview ON p95 = {p95_on:.1f}ms leaves < {_ABSOLUTE_HEADROOM_MS:.0f}ms headroom under "
        f"the 300ms budget"
    )
