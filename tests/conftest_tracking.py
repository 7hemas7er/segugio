"""GPU gate probe for ``@pytest.mark.gpu`` tests (D-09 split architecture).

The real-YOLO-on-clips eval is GPU/weights-dependent and must NOT run in normal CPU CI.
The ``gpu`` marker itself is registered in ``pyproject.toml`` (by 04-01); the SKIP behavior
is the ``pytest_collection_modifyitems`` hook in ``tests/conftest.py`` (pytest only
auto-loads files literally named ``conftest.py`` as plugins, so the hook must live there).

This module keeps the gpu-gate LOGIC isolated and import-guarded: ``gpu_available()``
probes ``torch`` + ``torch.cuda.is_available()`` + ``ultralytics`` (weights loader), each
guarded so collection NEVER imports torch at collection time unless it is actually present —
the lazy-import boundary is not violated by merely collecting the gpu tests on a CPU box. On
THIS box (``torch`` / ``ultralytics`` absent) the probe returns ``(False, reason)`` so every
gpu test SKIPs (intended, D-09).

The ONE exception that is a hard pass/fail (not skipped when the GPU IS present) is
``assert_native_reid_engaged()`` — but that is exercised INSIDE a gpu test body, so it only
runs when the gpu gate already passed (CUDA + weights present).
"""

from __future__ import annotations

__all__ = ["gpu_available"]


def gpu_available() -> tuple[bool, str]:
    """Return ``(ok, reason)`` — whether the real-YOLO gpu eval can run here.

    Probes torch + CUDA + weights, each guarded so a missing dep yields a SKIP reason rather
    than an import error at collection time.
    """
    try:
        import torch  # noqa: F401 — probe only; import-guarded so CPU collection is safe
    except ImportError:
        return False, "torch not installed (heavy group absent)"
    try:
        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() is False (no CUDA device)"
    except Exception as exc:  # noqa: BLE001 — a broken torch/CUDA probe is a skip, not an error
        return False, f"CUDA probe failed: {exc}"
    # Weights must be resolvable for YOLO to load. ultralytics resolves yolo26s.pt from its
    # assets cache or auto-downloads; treat an absent ultralytics as "weights unavailable".
    try:
        import ultralytics  # noqa: F401 — needed to load the weights at all
    except ImportError:
        return False, "ultralytics not installed (heavy group absent)"
    return True, ""
