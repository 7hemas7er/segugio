"""``python -m segugio <config.yaml>`` — the runnable entry point (closes the UAT gap).

Phase 05 verified the orchestrator loop LOGIC headlessly (5/5) but shipped NO runnable entry
point, so the D-07 hardware E2E (UAT Tests 1-4) could not be launched on the rig. This module IS
that entry point: it loads + validates the config, builds the orchestrator via the runtime factory
(``segugio.orchestrator.runtime.build_orchestrator``), and calls ``Orchestrator.run(rate_hz)``.

  python -m segugio config.example.yaml                 # OBS up — the normal live run
  python -m segugio config.example.yaml --rate 25       # PAL 25p feeds
  python -m segugio config.example.yaml --opcomm-dir D:/seg/opcomm   # colocate the channel w/ UI

OBS/NDI DOWN at launch is a NORMAL field condition (RBT-04): the loop's ``_safe_startup`` (05-07)
absorbs a failed ``source.start()`` / ``obs.connect()`` and coasts into the tick loop, where the
per-tick ``ObsWsController._safe_call`` heals OBS and the watchdog handles a dead source. So this
entry point does NOT add crash handling around ``run()`` beyond the operator's Ctrl-C: a
``KeyboardInterrupt`` calls ``shutdown()`` so OBS coasts to the SAFE scene (the RBT-04 SAFE coast
the gap calls out). Calling ``shutdown()`` is best-effort/never-raises (loop.py), and ``run()``'s
own ``finally: shutdown()`` already covers a normal stop — the explicit branch is the Ctrl-C path.

LAZY-IMPORT BOUNDARY: only LIGHT deps are imported at module top (``argparse`` / ``os`` + the
config loader + the runtime factory whose heavy builders are lazy). ``import segugio.__main__``
succeeds with cyndilib / obsws-python / cv2 / ultralytics / torch ABSENT — the heavy clients are
constructed only when ``build_orchestrator`` actually wires the real source/obs/trackers.
"""

from __future__ import annotations

import argparse
import os
import sys

from .config.loader import load_config
from .orchestrator.runtime import build_orchestrator

__all__ = ["main"]

# The lazy "heavy" runtime stack (pyproject [project.optional-dependencies].heavy). These are
# imported INSIDE build_orchestrator's collaborators (PerCameraTracker → ultralytics, the NDI
# receiver → cyndilib, the OBS client → obsws-python, frame decode → cv2). On a box that ran only
# `pip install -e .` (base deps) they are absent, and the FIRST one (ultralytics, built eagerly at
# compose time) raises ModuleNotFoundError. We turn that into one actionable line instead of a raw
# traceback (RBT-04 "never crash" ethos / WR-01). A non-heavy ModuleNotFoundError is a real bug —
# re-raised, never masked.
_HEAVY_MODULES = frozenset({"ultralytics", "torch", "cyndilib", "obsws_python", "cv2"})

# Mirror ui/app.py's default opcomm dir so the console and the orchestrator share ONE channel dir
# out of the box (override via --opcomm-dir or the SEGUGIO_OPCOMM_DIR env var).
_DEFAULT_OPCOMM_DIR = os.environ.get(
    "SEGUGIO_OPCOMM_DIR", os.path.join(os.getcwd(), "opcomm")
)


def _parse_args(argv) -> argparse.Namespace:
    """Parse the CLI: positional config path + optional --rate / --opcomm-dir."""
    parser = argparse.ArgumentParser(
        prog="segugio",
        description="Run the Segugio automatic video director against a validated config.",
    )
    parser.add_argument(
        "config",
        help="path to the YAML config (e.g. config.example.yaml)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=30.0,
        help="tick rate in Hz passed to the loop (default 30.0; use 25 for PAL 25p feeds)",
    )
    parser.add_argument(
        "--opcomm-dir",
        default=_DEFAULT_OPCOMM_DIR,
        help=(
            "directory holding the operator↔system opcomm files; MUST match the operator "
            "console's SEGUGIO_OPCOMM_DIR so the two share one channel (default: ./opcomm)"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """Load the config, build the orchestrator, and run; Ctrl-C coasts OBS to SAFE (RBT-04).

    Args:
        argv: optional argument list (defaults to ``sys.argv[1:]`` via argparse).

    Returns:
        Process exit code: 0 on a clean run or Ctrl-C stop; 2 when the heavy runtime stack
        is not installed (an actionable hint is printed instead of a raw traceback — WR-01).
        ``load_config`` raises ``SystemExit(2)`` on a bad config — deliberately NOT re-wrapped.
    """
    args = _parse_args(argv)
    # Fix #4 (T-9l5-06): bootstrap logging FIRST so the orchestrator's rotating post-mortem log
    # lands in the shared opcomm dir — a live event then leaves a diagnosable, rotated log instead
    # of stderr-only output. Lazy in-body import keeps the module-top import surface light.
    from .logging import configure_logging

    configure_logging(log_dir=args.opcomm_dir)

    # Fix #7 (SECURITY, T-9l5-04): a LOUD degrade (never a crash — "nessun crash ammesso") when the
    # console is secured but obs-websocket is left unauthenticated. A missing OBS password is not
    # the same as OBS being down (the controller still connects), but on a secured rig it is a real
    # gap — warn prominently so the operator sets SEGUGIO_OBS_PASSWORD too.
    if os.environ.get("SEGUGIO_CONSOLE_SECRET") and not (
        os.environ.get("SEGUGIO_OBS_PASSWORD") or ""
    ).strip():
        from loguru import logger

        logger.warning(
            "SEGUGIO_CONSOLE_SECRET is set (console secured) but SEGUGIO_OBS_PASSWORD is "
            "empty/unset — obs-websocket is UNAUTHENTICATED. Set SEGUGIO_OBS_PASSWORD to secure "
            "OBS control too (this is a loud degrade, not a crash)."
        )

    config = load_config(args.config)  # fails fast with SystemExit(2) on a bad config
    try:
        orch = build_orchestrator(config, args.opcomm_dir)
    except ModuleNotFoundError as exc:
        top = (exc.name or "").split(".")[0]
        if top not in _HEAVY_MODULES:
            raise  # a genuine missing-module bug — do NOT mask it behind the install hint
        print(
            f"Heavy runtime stack not installed (missing '{exc.name}'). Install it on the "
            'rig with:  pip install -e ".[heavy]"  (also needs the libndi native lib for '
            "cyndilib; see docs/run.md).",
            file=sys.stderr,
        )
        return 2
    try:
        orch.run(args.rate)
    except KeyboardInterrupt:
        # The operator's Ctrl-C: coast OBS to SAFE and stop the source (RBT-04). shutdown() is
        # best-effort/never-raises; run()'s finally already covers a normal stop.
        orch.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
