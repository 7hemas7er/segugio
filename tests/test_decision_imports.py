"""Lazy-import boundary + source-grep purity gate for ``segugio.decision``.

Ports the two Phase-2 ``test_framing_purity.py`` boundary tests, retargeted at the decision
package:

  * ``test_decision_imports_with_heavy_absent``: with torch / ultralytics / cyndilib /
    obsws_python forced absent (``sys.modules[name] = None``), ``import segugio.decision``
    still succeeds — the FSM is pure CPU logic. ``transitions`` is now a LIGHT runtime dep,
    importable in that environment (it is NOT in ``HEAVY_MODULES``).
  * ``test_no_io_imports_in_decision``: a source-grep over every ``src/segugio/decision/*.py``
    asserting none imports ``time`` / ``np.random`` / ``os`` / ``socket`` / ``requests`` / ``cv2``
    nor any heavy dep — no nondeterministic source (clock/RNG) and no I/O can slip in. NOTE:
    ``transitions`` is deliberately KEPT OUT of the forbidden set (it is the legitimate light
    FSM dep).
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


def _decision_py_files() -> list[Path]:
    """Every ``*.py`` source file under ``src/segugio/decision/`` (resolved via the package)."""
    decision_dir = Path(importlib.import_module("segugio.decision").__file__).parent
    files = sorted(decision_dir.glob("*.py"))
    assert files, f"no decision source files found under {decision_dir}"
    return files


def test_decision_imports_with_heavy_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``import segugio.decision`` succeeds with torch/ultralytics/cyndilib/obsws absent.

    Replicates the ``test_imports`` force-absent pattern (``sys.modules[name] = None`` makes
    the heavy import raise) and drops any cached ``segugio.*`` so the import re-runs under the
    block. ``transitions`` (the now-light FSM dep) stays importable in that environment.
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

    module = importlib.import_module("segugio.decision")
    assert module is not None
    # The pure FSM surface is reachable with the heavy runtime absent.
    assert hasattr(module, "DecisionEngine")
    assert hasattr(module, "Decision")
    assert hasattr(module, "Mode")
    assert hasattr(module, "ticks_from_seconds")
    # transitions is a legitimate light dep — importable even with the heavy modules blocked.
    assert importlib.import_module("transitions") is not None


def test_no_io_imports_in_decision() -> None:
    """No decision source imports time / np.random / os / socket / requests / cv2 / heavy dep.

    A source-grep style assertion: the FSM is pure — time enters only as the injected
    ``tick``, there is zero randomness, and no module does I/O or pulls a heavy runtime.
    ``transitions`` is the legitimate light FSM dep and is intentionally NOT forbidden.
    """
    # Patterns that must NOT appear anywhere in decision source. Word-boundary regexes so a
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
    # transitions is NOT here — it is a light runtime dep.
    for name in (*HEAVY_MODULES, "cv2"):
        forbidden[f"import {name}"] = re.compile(rf"(?m)^\s*import\s+{re.escape(name)}\b")
        forbidden[f"from {name} import"] = re.compile(
            rf"(?m)^\s*from\s+{re.escape(name)}\s+import\b"
        )

    for path in _decision_py_files():
        source = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            assert not pattern.search(source), (
                f"{path.name} must not contain {label!r} "
                f"(decision/ is pure: no time / np.random / I/O / heavy import)"
            )
