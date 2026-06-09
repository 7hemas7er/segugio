"""segugio.synth — deterministic synthetic stream generators (TST-02).

Seedable score-stream and feed-death generators driven by an INJECTED
``numpy.random.Generator`` so the same seed yields byte-identical output. These are
the hardware-free substrate the Phase-2 scorer, Phase-3 FSM, and Phase-5 watchdog
are unit-tested against — no clip, no GPU, no NDI.

Pure-logic, numpy-only; heavy-import-free so any phase can import it (the 01-01
import-smoke test guards this surface).
"""

from .detection_stream import detection_stream, multi_track_stream
from .feed_death import FeedEvent, feed_death
from .score_stream import SCENARIOS, ScoreSample, score_stream

__all__ = [
    "ScoreSample",
    "score_stream",
    "SCENARIOS",
    "FeedEvent",
    "feed_death",
    "detection_stream",
    "multi_track_stream",
]
