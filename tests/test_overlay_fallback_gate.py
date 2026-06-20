"""RBT-06 SC#1 — overlay.txt on-disk persistence + single-writer coexistence.

The OBS "read from file" text source airs ``overlay.txt`` as the always-on fallback when the
console stops answering (console-down → the browser overlay auto-hides via DEAD_MS, but the
text source keeps showing the LAST score). The load-bearing property (14-RESEARCH.md Q1
RESOLVED) is the SINGLE WRITER: ``POST /score`` is the SOLE writer of ``overlay.txt``. If the
console dies, no second writer can clear the last score — the rendered line stays on disk
byte-for-byte until the next operator score.

This gate proves it with the Flask in-process ``test_client`` (no node, no orchestrator
import — crash-isolation/RBT-07 friendly): POST a score, read ``overlay.txt`` from disk and
assert it holds the rendered line, then SIMULATE a console death (do NOT call the app again,
do NOT add any second writer) and re-read — the last score is STILL there byte-for-byte.
"""

from __future__ import annotations

from segugio.opcomm.records import Discipline, ScoreDoc
from segugio.ui.app import create_app
from segugio.ui.score_render import render_overlay_text


def test_overlay_txt_persists_last_score_after_simulated_death(file_channel):
    """POST /score writes overlay.txt; a simulated console death leaves it intact (SC#1).

    Single-writer proof: the route is the SOLE writer, so a death (no further write) cannot
    clear the last rendered score — the OBS read-from-file source keeps airing it.
    """
    channel_dir = str(file_channel["dir"])
    overlay_path = file_channel["overlay"]
    app = create_app(channel_dir, cam_ids=["cam_wide"])
    client = app.test_client()

    # POST a real disc Toss & Fetch score through the SOLE writer (the route).
    fields = {"discipline": Discipline.disc_tf.value, "prese": "12", "zona": "3", "totale": "7"}
    resp = client.post("/score", data=fields)
    assert resp.status_code == 204, f"/score returned {resp.status_code}, expected 204"

    # The rendered line is on disk — compare byte-for-byte to the pure renderer for the same doc.
    expected = render_overlay_text(
        ScoreDoc(discipline=Discipline.disc_tf, fields={"prese": "12", "zona": "3", "totale": "7"})
    )
    assert overlay_path.exists(), "overlay.txt must exist on disk after POST /score"
    on_disk_after_write = overlay_path.read_text(encoding="utf-8")
    assert on_disk_after_write == expected, "overlay.txt must hold the rendered last score"
    # The operator-typed value is present in the aired line (sanity on the display path).
    assert "12" in on_disk_after_write and "Prese" in on_disk_after_write

    # --- SIMULATE A CONSOLE DEATH ---------------------------------------------------------
    # Drop the app/client: no further write, no orchestrator import, NO second writer. This
    # mirrors the live scenario where the console process stops answering. The single-writer
    # property says the last score must survive on disk untouched.
    del client
    del app

    # Re-read overlay.txt from disk AFTER the simulated death — it is byte-for-byte unchanged.
    on_disk_after_death = overlay_path.read_text(encoding="utf-8")
    assert on_disk_after_death == on_disk_after_write, (
        "overlay.txt changed after a simulated console death — a second writer cleared the "
        "last score (single-writer coexistence broken, SC#1)"
    )
    assert on_disk_after_death == expected
