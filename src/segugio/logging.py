"""segugio.logging — the single loguru bootstrap for the whole package.

Call ``configure_logging()`` once at application startup. Every module then does
``from loguru import logger`` and gets the configured sink. The bootstrap is
idempotent: calling it more than once leaves exactly one configured stderr sink
(repeat calls are no-ops unless ``force=True`` re-applies the configuration).

Imports loguru at module top level — loguru is a light runtime dependency and is
explicitly allowed. Nothing heavy (torch / ultralytics / cyndilib / obsws-python)
is imported here, preserving the Phase-1 lazy-import boundary.
"""

from __future__ import annotations

import os
import sys

from loguru import logger

# Default sink format: timestamp, level, module:function:line, message.
_DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level: <8}</level> "
    "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
    "- <level>{message}</level>"
)

# The post-mortem log filename written under the opcomm dir (a live event then leaves a
# diagnosable, rotated log — Fix #4 / T-9l5-06).
_LOG_FILENAME = "segugio.log"

# Module-level guards so the bootstrap is idempotent across repeated calls: _CONFIGURED tracks the
# stderr sink; _FILE_SINK_ID holds the rotating-file sink id so repeated calls never stack a second
# file handler (a duplicate would double-write every line to the same file).
_CONFIGURED = False
_FILE_SINK_ID: int | None = None


def configure_logging(
    level: str = "INFO", *, force: bool = False, log_dir: str | None = None
) -> None:
    """Configure loguru once for the whole package (stderr + an optional rotating file sink).

    Installs a single stderr sink at ``level`` (idempotent — a second call leaves exactly one
    stderr sink unless ``force`` re-applies it). When ``log_dir`` is a non-empty path, ALSO adds a
    native loguru rotating file sink at ``<log_dir>/segugio.log`` (``rotation="10 MB"``,
    ``retention=5``, ``enqueue=True`` so a disk write never blocks the live tick) — the post-mortem
    log a live event needs (Fix #4 / T-9l5-06). The file sink is guarded by ``_FILE_SINK_ID`` so
    repeated calls do not stack duplicate file handlers.

    Args:
        level: Minimum log level for both sinks (default ``"INFO"``).
        force: Re-apply the configuration even if already configured (e.g. to change the level or
            the log dir). Still results in exactly one stderr sink and at most one file sink.
        log_dir: Directory for the rotating ``segugio.log`` post-mortem file. ``None``/empty →
            stderr only (the file sink is not added). The directory is created if absent.
    """
    global _CONFIGURED, _FILE_SINK_ID

    # --- stderr sink (idempotent) ------------------------------------------------------------ #
    if not _CONFIGURED or force:
        # remove() with no args clears ALL handlers (including loguru's default id=0 AND any prior
        # file sink), so re-arm _FILE_SINK_ID below rather than leak a dangling id.
        logger.remove()
        _FILE_SINK_ID = None
        logger.add(
            sys.stderr,
            level=level,
            format=_DEFAULT_FORMAT,
            backtrace=False,
            diagnose=False,
            enqueue=False,
        )
        _CONFIGURED = True

    # --- optional rotating file sink (guarded — never stacks duplicates) --------------------- #
    if log_dir:
        if _FILE_SINK_ID is None or force:
            if _FILE_SINK_ID is not None:
                try:
                    logger.remove(_FILE_SINK_ID)
                except ValueError:  # already gone (e.g. cleared above) — nothing to remove
                    pass
                _FILE_SINK_ID = None
            os.makedirs(log_dir, exist_ok=True)
            _FILE_SINK_ID = logger.add(
                os.path.join(log_dir, _LOG_FILENAME),
                level=level,
                rotation="10 MB",
                retention=5,
                enqueue=True,  # non-blocking: a disk write never taxes the live decision tick
                backtrace=False,
                diagnose=False,
            )


__all__ = ["configure_logging"]
