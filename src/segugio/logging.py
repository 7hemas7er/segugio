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

import sys

from loguru import logger

# Default sink format: timestamp, level, module:function:line, message.
_DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level: <8}</level> "
    "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
    "- <level>{message}</level>"
)

# Module-level guard so the bootstrap is idempotent across repeated calls.
_CONFIGURED = False


def configure_logging(level: str = "INFO", *, force: bool = False) -> None:
    """Configure loguru once for the whole package.

    Removes loguru's default handler and installs a single stderr sink at ``level``.
    Idempotent: a second call is a no-op (exactly one sink remains) unless ``force``
    is True, in which case the sink is re-applied with the given level.

    Args:
        level: Minimum log level for the stderr sink (default ``"INFO"``).
        force: Re-apply the configuration even if already configured (e.g. to
            change the level). Still results in exactly one sink.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    # remove() with no args clears ALL handlers (including loguru's default id=0),
    # guaranteeing we never accumulate duplicate sinks.
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=_DEFAULT_FORMAT,
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )
    _CONFIGURED = True


__all__ = ["configure_logging"]
