"""``segugio.ui`` — the Flask operator console (separate process, D-02/03/04).

The project's ONLY human surface. Crash-isolated from the orchestrator: it talks to the
director EXCLUSIVELY through the ``segugio.opcomm`` atomic-file channel (D-03), and it
imports NOTHING heavy (Flask + ``segugio.opcomm`` only) — so a UI exception can never touch
the director (RBT-04). ``import segugio.ui`` therefore succeeds with cyndilib/obsws/cv2 and
even Flask absent (the Flask import lives inside ``app.create_app``, not at package top).

This package contains:
  * ``score_render`` — a PURE, stdlib-only per-discipline overlay renderer (display-only,
    no adjudication anywhere — SCR-04).
  * ``app`` — the Flask app factory (imported lazily by callers, not re-exported here, to
    keep ``import segugio.ui`` Flask-free).
"""

from __future__ import annotations

from .score_render import render_overlay_text

__all__ = ["render_overlay_text"]
