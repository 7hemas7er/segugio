"""Deterministic, seedable synthetic feed-death generator (TST-02).

A ``feed_death`` emits a reproducible per-camera liveness timeline the Phase-3/5
feed watchdog is unit-tested against: a camera is alive until its death tick, then
dead, then (optionally) alive again at ``death + recover_after``.

This mirrors the domain's critical NDI gotcha (PROJECT.md): a fallen feed must be
detectable as dead even though NDI keeps repeating its last frame. The watchdog
tests need a deterministic death/recovery timeline to assert against — that is what
this generator provides.

Determinism contract (RESEARCH.md Pattern 4 + Pitfall 3):
  * the explicit ``death_at`` / ``recover_after`` path is FULLY deterministic — it
    reads no randomness at all;
  * the injected ``rng`` is present for signature consistency (and any future random
    deaths); NO module-level RNG, NO global ``np.random.*``, NO wall-clock.
  * time == the synthetic tick index. Same inputs -> byte-identical list.

Imports only ``numpy`` + stdlib ``dataclasses`` (heavy-import-free surface).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["FeedEvent", "feed_death"]


@dataclass(frozen=True)
class FeedEvent:
    """One per-camera liveness reading at a synthetic tick.

    Frozen (hashable + comparable) so ``==`` over two ``list[FeedEvent]`` is the
    determinism assertion the watchdog tests rely on.
    """

    tick: int
    cam_id: str
    alive: bool


def feed_death(
    rng: np.random.Generator,
    cam_ids: list[str],
    n_ticks: int,
    death_at: dict[str, int] | None = None,
    recover_after: int | None = None,
) -> list[FeedEvent]:
    """Build a reproducible per-tick liveness timeline (death + optional recovery).

    A camera is ``alive`` for ticks ``[0, death)``; ``dead`` from ``death`` onward;
    and (when ``recover_after`` is set) ``alive`` again from ``death + recover_after``.
    A camera with no entry in ``death_at`` stays alive for the whole run.

    Args:
        rng: injected ``numpy.random.Generator`` — present for signature consistency
            with ``score_stream`` and any future random-death path; the explicit
            ``death_at`` timeline below uses no randomness.
        cam_ids: camera identifiers, in a fixed order.
        n_ticks: number of synthetic ticks (time runs 0..n_ticks-1).
        death_at: explicit death tick per camera (``{cam_id: tick}``).
        recover_after: ticks after death at which every dying camera recovers; if
            ``None``, a dead camera stays dead through the end of the run.

    Returns:
        ``list[FeedEvent]`` of length ``n_ticks * len(cam_ids)``, ordered by
        (tick, camera). Same inputs -> identical list.
    """
    # ``rng`` is intentionally unused on the deterministic explicit-death path; touch
    # it (no draw) only to keep the parameter meaningful and silence lint noise.
    assert isinstance(rng, np.random.Generator)

    death_at = death_at or {}
    out: list[FeedEvent] = []
    for t in range(n_ticks):
        for cam in cam_ids:
            d = death_at.get(cam)
            if d is None or t < d:
                alive = True
            elif recover_after is not None and t >= d + recover_after:
                alive = True  # recovered (rejoined)
            else:
                alive = False  # dead (in the death window)
            out.append(FeedEvent(t, cam, alive))
    return out
