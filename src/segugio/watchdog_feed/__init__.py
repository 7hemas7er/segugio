"""``segugio.watchdog_feed`` — pure feed-liveness math (RBT-01).

Light re-export of ``FeedWatchdog``: the clock-free, stdlib-only component that deduces
whether each camera's feed is alive from the last-NEW-frame timestamp (never the NDI source
"connected" state — Pitfall 1). On the proven lazy-import surface (imports only ``math`` +
``typing``), so ``import segugio.watchdog_feed`` succeeds with torch / ultralytics / cyndilib
/ obsws absent. Its output drives ``DecisionEngine.tick(..., alive=...)`` (DEC-06 → RBT-02).
"""

from __future__ import annotations

from .liveness import FeedWatchdog, FrameTimestampSource

__all__ = ["FeedWatchdog", "FrameTimestampSource"]
