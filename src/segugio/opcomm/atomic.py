"""Atomic file write — the spine of the whole operator↔system channel (SCR-01).

Every operator↔system message (score, run-state, override command, director status) is a
small file written via **temp-in-the-same-directory → flush → os.fsync → os.replace**. This
is the ONE durable, crash-safe, never-partial write primitive the whole channel reuses
(D-03/09/10/11). A concurrent reader (OBS read-from-file, the orchestrator each tick, the UI
poll) therefore NEVER observes a half-written or empty file.

Why same-directory temp (Pitfall 6, 🔴): ``os.replace`` is atomic ONLY within a single
filesystem/volume. On Windows it lowers to ``MoveFileEx``, atomic on the same drive only. A
temp in ``/tmp`` or another volume silently degrades to a non-atomic copy — so the temp MUST
be created in ``os.path.dirname(target)``. The leading-dot temp name keeps it hidden and
distinct per target so concurrent writers to sibling files never collide.

stdlib only (``json`` / ``os``) — no heavy imports, keeps the lazy-import boundary intact
(``import segugio.opcomm`` succeeds with cyndilib/obsws/cv2/Flask absent).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

__all__ = ["atomic_write_json", "atomic_write_text"]

# Windows-only transient: if a reader (OBS / the orchestrator / the UI poll) holds the TARGET
# open at the instant of os.replace → MoveFileEx, Windows raises PermissionError [WinError 5]
# (a sharing violation), even though readers open-read-close quickly. POSIX has no such
# contention. We retry the swap a few times with a tiny backoff — the reader releases the
# handle within microseconds (RESEARCH Pitfall 6: "readers open-read-close quickly; the
# orchestrator reads its files with retry-on-PermissionError"). The write/fsync already
# completed; only the final rename is retried, so atomicity is preserved.
_REPLACE_RETRIES = 50
_REPLACE_BACKOFF_S = 0.001


def _atomic_replace(tmp: str, path: str) -> None:
    """``os.replace(tmp, path)`` with a bounded retry on the Windows sharing-violation.

    On the last attempt the exception is allowed to propagate (a persistent failure is a real
    error, not a transient reader collision). On POSIX the first attempt always succeeds.
    """
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_S)


def _temp_path(path: str) -> str:
    """Build the same-directory hidden temp name for ``path`` (Pitfall 6).

    The temp MUST live in the target's own directory so ``os.replace`` stays atomic
    (same volume). The ``.<name>.tmp`` form is hidden and unique per target.
    """
    abspath = os.path.abspath(path)
    d = os.path.dirname(abspath)
    return os.path.join(d, f".{os.path.basename(abspath)}.tmp")


def atomic_write_json(path: str, obj: Any) -> None:
    """Write ``obj`` as JSON to ``path`` atomically (temp + fsync + os.replace).

    A reader interleaved with rapid writes never sees a partial/empty file: the bytes land
    in a same-directory temp, are flushed + fsynced for durability, then swapped into place
    with a single atomic ``os.replace``. ``ensure_ascii=False`` keeps Italian text (è/ò/à)
    readable on disk (the file is UTF-8).
    """
    tmp = _temp_path(path)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())  # durability before the swap (survives a crash mid-write)
    _atomic_replace(tmp, path)  # atomic on the same volume (Windows: MoveFileEx + retry)


def atomic_write_text(path: str, text: str) -> None:
    """Write a plain string to ``path`` atomically — the OBS read-from-file overlay (OBS-05).

    Same atomicity guarantee as :func:`atomic_write_json`: OBS reading the overlay file
    mid-write never flickers to blank or a truncated line.
    """
    tmp = _temp_path(path)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
