"""``segugio.opcomm`` — the atomic-file operator↔system channel (D-03/09/10/11, SCR-01).

The ONE IPC between the Flask operator console (separate process) and the orchestrator loop:
small files written via temp + fsync + ``os.replace`` (never partial, never crash). This
package is a LIGHT leaf — stdlib + loguru only, NO heavy imports (cyndilib/obsws/cv2/Flask) —
so ``import segugio.opcomm`` succeeds with the whole heavy stack absent (the lazy boundary).

Re-exports the channel functions + record types for convenient ``from segugio.opcomm import``;
the ``atomic`` helper is imported from its submodule when needed directly.
"""

from __future__ import annotations

from .channel import (
    read_command,
    read_runstate,
    read_score,
    read_status,
    write_command,
    write_runstate,
    write_score,
    write_status,
)
from .records import Discipline, DirectorStatus, OperatorCommand, RunState, ScoreDoc

__all__ = [
    # records
    "Discipline",
    "ScoreDoc",
    "RunState",
    "OperatorCommand",
    "DirectorStatus",
    # channel
    "write_score",
    "read_score",
    "write_runstate",
    "read_runstate",
    "write_command",
    "read_command",
    "write_status",
    "read_status",
]
