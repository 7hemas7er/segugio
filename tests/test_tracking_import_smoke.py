"""Lazy-import boundary + source-grep purity gate for ``segugio.tracking``.

Ports the two ``test_decision_imports.py`` boundary tests, retargeted at the tracking
package — but with one phase-specific tightening: ``cv2`` is forced absent too. The
tracking package is the FIRST to lazy-import ``cv2`` (in the 04-03 heavy edge), so the
smoke test must prove ``import segugio.tracking`` survives ``cv2`` absent.

  * ``test_tracking_imports_with_heavy_absent``: with torch / ultralytics / cyndilib /
    obsws_python AND cv2 forced absent (``sys.modules[name] = None``),
    ``import segugio.tracking`` still succeeds — the package surface is pure CPU logic.
  * ``test_no_io_imports_in_tracking_pure_modules``: a source-grep over ONLY the pure
    tracking modules (``params.py`` / ``signals_map.py`` — and ``competitor_lock.py`` /
    ``plausibility.py`` once they exist) asserting none imports
    ``time`` / ``np.random`` / ``os`` / ``socket`` / ``requests`` / ``cv2`` nor any heavy
    dep. The heavy-edge modules (``detector.py`` / ``reid_check.py`` / ``frame_source.py``
    / ``eval.py``) are deliberately OUT of scope — they legitimately lazy-import heavy
    deps inside functions (and do not exist yet).
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

# Reuse the test_imports harness so HEAVY_MODULES / the force-absent helper stay
# single-sourced (this test extends the same lazy-import boundary).
from tests.test_imports import HEAVY_MODULES, _force_heavy_absent

# The PURE tracking modules this plan ships (and the two 04-02 pure modules guarded by
# existence so this plan's run passes with only params/signals_map present). The heavy-edge
# modules are NOT listed here — they legitimately lazy-import heavy deps inside functions.
_PURE_MODULE_NAMES = ("params.py", "signals_map.py", "competitor_lock.py", "plausibility.py")


def _tracking_dir() -> Path:
    """The ``src/segugio/tracking/`` directory (resolved via the package)."""
    return Path(importlib.import_module("segugio.tracking").__file__).parent


def _pure_tracking_py_files() -> list[Path]:
    """Every EXISTING pure tracking source file (existence-guarded for 04-02 modules)."""
    tracking_dir = _tracking_dir()
    files = [tracking_dir / name for name in _PURE_MODULE_NAMES if (tracking_dir / name).exists()]
    assert files, f"no pure tracking source files found under {tracking_dir}"
    return files


def test_tracking_imports_with_heavy_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``import segugio.tracking`` succeeds with torch/ultralytics/cyndilib/obsws/cv2 absent.

    Replicates the ``test_imports`` force-absent pattern (``sys.modules[name] = None`` makes
    the heavy import raise) and ALSO forces ``cv2`` absent — the tracking package is the first
    to lazy-import cv2, so its pure surface must import with cv2 gone. Drops any cached
    ``segugio.*`` so the import re-runs under the block.
    """
    _force_heavy_absent(monkeypatch)
    # The tracking package is the first to lazy-import cv2 — prove the surface survives cv2 absent.
    monkeypatch.setitem(sys.modules, "cv2", None)
    # Sanity: the block is real — heavy imports (and cv2) raise.
    for name in (*HEAVY_MODULES, "cv2"):
        with pytest.raises(ImportError):
            importlib.import_module(name)
    # Drop cached segugio modules so the import re-runs under the heavy-absent block.
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)

    module = importlib.import_module("segugio.tracking")
    assert module is not None
    # The pure tracking surface is reachable with the heavy runtime (and cv2) absent.
    assert hasattr(module, "TrackingParams")
    assert hasattr(module, "signals_from_boxes")


def test_no_io_imports_in_tracking_pure_modules() -> None:
    """No PURE tracking module imports time / np.random / os / socket / requests / cv2 / heavy dep.

    A source-grep style assertion scoped to the PURE modules only: they carry no
    nondeterministic source (clock/RNG) and do no I/O or heavy import. The heavy-edge
    modules are deliberately NOT grepped (they legitimately lazy-import heavy deps).
    """
    # Patterns that must NOT appear in the pure modules. Word-boundary regexes so a substring
    # like "atime" or "ostream" never triggers a false positive (mirrors test_decision_imports).
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
    # Heavy / GPU / NDI deps + cv2 — none may be imported at a pure module's top level.
    for name in (*HEAVY_MODULES, "cv2"):
        forbidden[f"import {name}"] = re.compile(rf"(?m)^\s*import\s+{re.escape(name)}\b")
        forbidden[f"from {name} import"] = re.compile(
            rf"(?m)^\s*from\s+{re.escape(name)}\s+import\b"
        )

    for path in _pure_tracking_py_files():
        source = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            assert not pattern.search(source), (
                f"{path.name} must not contain {label!r} "
                f"(tracking pure modules: no time / np.random / I/O / cv2 / heavy import)"
            )
