"""Dev/rig tool: build the one-time cached TensorRT FP16 ``.engine`` from the locked ``.pt``.

This is a **rig-time tool, NOT runtime code**. It runs ONCE on the deploy GPU to export a
TensorRT engine that ``PerCameraTracker`` then picks up at load time (06-03). It never runs in
the live director loop.

Why a separate one-time build (RESEARCH Pitfall 3 / Open Q3):
  * A TensorRT ``.engine`` is **specific to the exact GPU + driver + TensorRT version** it was
    built on — it is never committed and never copied between GPUs (a foreign engine either
    fails to load or silently mis-runs). It is therefore built on the **deploy rig** from the
    trusted locked ``.pt`` as a cached artifact written **beside the weights** (gitignored —
    ``.gitignore`` excludes ``*.engine`` / ``*.onnx`` since 06-01).
  * The export runs for **minutes** and needs the live CUDA env (cu12x torch + ``tensorrt``);
    run it on **AC power** (project memory ``dev-box-perf-on-ac.md``).

The CITED prod-path export shape (docs.ultralytics.com/integrations/tensorrt):
  ``YOLO(weights).export(format="engine", half=True, batch=4, imgsz=640, end2end=False, device=0)``
  * ``half=True`` → FP16 (the prod path; eager FP32 was the 231-247ms slow path);
  * ``batch=4`` STATIC → the 4-cam batched fan-out (the loop pads dead-camera slots with a
    blank frame per the 06-01 adapter, so a static batch=4 is valid; ``--dynamic`` is the
    escape hatch if reduced-camera operation must run on the engine — RESEARCH Pitfall 4 / Q3);
  * ``end2end=False`` → keeps the standard Detect head exposed so the eager warmup path's
    native-ReID hook story stays consistent with the locked stack (TRK-02); the engine itself
    loads via AutoBackend (no in-graph Detect head), which is the Q1 Option-(a) cls-ReID story.

Lazy-import boundary: ``from ultralytics import YOLO`` is imported INSIDE :func:`build_engine`,
NOT at module top — so ``import tools.build_engine`` / collecting it succeeds with the heavy
stack ABSENT (mirrors ``runtime.py``'s ``_default_tracker_factory``). Only ``argparse`` /
``pathlib`` / ``sys`` are top-level.

Usage (on the py3.12 GPU venv, on the RTX 4000 Ada, on AC power)::

    venv312\\Scripts\\python.exe tools/build_engine.py
    venv312\\Scripts\\python.exe tools/build_engine.py --weights yolo26s.pt --imgsz 640 --batch 4
    venv312\\Scripts\\python.exe tools/build_engine.py --dynamic   # dynamic-batch escape hatch

It writes ``<weights-stem>.engine`` beside the weights (e.g. ``yolo26s.engine``) and prints the
resolved artifact path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["build_engine", "main"]

_DEFAULT_WEIGHTS = "yolo26s.pt"
_DEFAULT_IMGSZ = 640
_DEFAULT_BATCH = 4
_DEFAULT_DEVICE = 0


def build_engine(
    weights: str | Path = _DEFAULT_WEIGHTS,
    *,
    imgsz: int = _DEFAULT_IMGSZ,
    batch: int = _DEFAULT_BATCH,
    device: int = _DEFAULT_DEVICE,
    dynamic: bool = False,
) -> Path:
    """Export the TensorRT FP16 engine from ``weights`` and return the written ``.engine`` path.

    Runs the CITED prod-path export — ``half=True`` (FP16), ``batch`` (static unless
    ``dynamic``), ``imgsz``, ``device``, ``end2end=False`` — on the deploy GPU. The
    ``from ultralytics import YOLO`` import is LAZY (inside this function), so the module
    imports with ultralytics absent.

    Args:
        weights: the source YOLO weights (default ``yolo26s.pt`` — the locked v1 detector).
        imgsz: the export inference size (default 640 — the AI-path crop size).
        batch: the STATIC batch dimension (default 4 — the 4-cam fan-out; dead slots are
            padded with a blank frame by the loop's batched adapter). Ignored shape-wise when
            ``dynamic`` is True (TensorRT then accepts a variable batch up to ``batch``).
        device: the CUDA device ordinal to build on (default 0). The engine is specific to
            THIS GPU (Pitfall 3) — build on the deploy rig.
        dynamic: when True, export a DYNAMIC-batch engine (the escape hatch for reduced-camera
            operation on the engine path); default False → a static ``batch``-shaped engine.

    Returns:
        The path to the written ``.engine`` (beside the weights, e.g. ``yolo26s.engine``).
    """
    from ultralytics import YOLO  # lazy — heavy import INSIDE the build function

    model = YOLO(str(weights))
    exported = model.export(
        format="engine",
        half=True,  # FP16 — the prod path (eager FP32 was the slow path)
        batch=int(batch),  # static batch=4 (the 4-cam fan-out) unless --dynamic
        imgsz=int(imgsz),
        device=int(device),  # build on THIS GPU — the engine is GPU-specific (Pitfall 3)
        end2end=False,  # standard Detect head (TRK-02 consistency); engine loads via AutoBackend
        dynamic=bool(dynamic),  # static batch by default; --dynamic for reduced-camera operation
    )
    return Path(exported)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse weights/imgsz/batch/device/--dynamic, build the engine, print its path."""
    parser = argparse.ArgumentParser(
        prog="build_engine",
        description=(
            "Build the one-time cached TensorRT FP16 .engine from the locked .pt, ON the deploy "
            "GPU (RTX 4000 Ada), on AC power. GPU-specific — rebuild per rig, never commit."
        ),
    )
    parser.add_argument(
        "--weights",
        default=_DEFAULT_WEIGHTS,
        help="source YOLO weights (default: yolo26s.pt — the locked v1 detector)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=_DEFAULT_IMGSZ,
        help="export inference size (default: 640)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=_DEFAULT_BATCH,
        help="static batch dimension (default: 4 — the 4-cam fan-out)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=_DEFAULT_DEVICE,
        help="CUDA device ordinal to build on (default: 0)",
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="export a DYNAMIC-batch engine (escape hatch for reduced-camera operation); "
        "default is a static batch=4 engine",
    )
    args = parser.parse_args(argv)

    engine_path = build_engine(
        args.weights,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        dynamic=args.dynamic,
    )
    print(f"engine written: {engine_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
