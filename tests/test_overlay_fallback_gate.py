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

from segugio.opcomm.channel import read_score
from segugio.opcomm.records import Discipline
from segugio.ui import score_calc
from segugio.ui.app import create_app
from segugio.ui.score_render import render_overlay_text

_MAX_FIELD_LEN = 64  # mirrors score_render._MAX_FIELD_LEN (the per-field cap)


def test_overlay_txt_persists_last_score_after_simulated_death(file_channel):
    """POST /score writes overlay.txt; a simulated console death leaves it intact (SC#1).

    Single-writer proof: the route is the SOLE writer, so a death (no further write) cannot
    clear the last rendered score — the OBS read-from-file source keeps airing it.
    """
    channel_dir = str(file_channel["dir"])
    overlay_path = file_channel["overlay"]
    app = create_app(channel_dir, cam_ids=["cam_wide"])
    client = app.test_client()

    # POST a real disc Toss & Fetch score through the SOLE writer (the route). P17 (D-11) retired
    # the legacy flat-key path — post the AUTHORITATIVE structured body (two zone-4 throws); the
    # server recomputes the total (zona=8, totale=8) and writes the rendered line.
    resp = client.post(
        "/score",
        json={
            "discipline": Discipline.disc_tf.value,
            "throws": [{"zone": 4}, {"zone": 4}],
        },
    )
    assert resp.status_code == 204, f"/score returned {resp.status_code}, expected 204"

    # The rendered line is on disk — compare byte-for-byte to the pure renderer for the SERVER-
    # computed doc (the route is authoritative; the overlay shows the recomputed fields verbatim).
    written = read_score(str(file_channel["score"]))
    expected = render_overlay_text(written)
    assert overlay_path.exists(), "overlay.txt must exist on disk after POST /score"
    on_disk_after_write = overlay_path.read_text(encoding="utf-8")
    assert on_disk_after_write == expected, "overlay.txt must hold the rendered last score"
    # The recomputed total is present in the aired line (sanity on the display path).
    assert "Prese" in on_disk_after_write and written.fields.get("totale") in on_disk_after_write

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


def test_overlay_txt_single_line_after_rich_post(file_channel):
    """A RICH POST /score per discipline leaves overlay.txt a single non-empty bounded line (D-06).

    The Plan 18-01 enrichment added DICT/LIST subkeys (``throws[].score`` / ``criteria{}`` /
    ``faults_breakdown{}``) and free-text identity (``cane``/``conduttore``/``giudici``) to the
    score doc. ``render_overlay_text`` reads FLAT SCALAR keys ONLY, so none of those subkeys can
    spill a newline into the OBS read-from-file source or overflow it: after a rich POST the aired
    ``overlay.txt`` stays a SINGLE non-empty line, each field length-bounded by ``_clean`` (≤ 64).

    Proven per discipline: a multi-throw disc T&F (subkey-producing) + identity, a four-category
    freestyle (criteria-producing) + identity + an OVERLONG ``nome`` (cap proof), and a count_up
    agility run (faults_breakdown-producing) + identity. Each aired line is byte-for-byte equal to
    the pure ``render_overlay_text`` for the written doc — proving the renderer is unbroken by 18-01.
    """
    channel_dir = str(file_channel["dir"])
    overlay_path = file_channel["overlay"]
    identity = {"cane": "Rex", "conduttore": "Anna", "giudici": "G1"}

    rich_posts = [
        # disc_tf — two subkey-producing throws (each gets throws[].score) + identity.
        (
            create_app(channel_dir, cam_ids=["cam_wide"]),
            {
                "discipline": "disc_tf",
                "throws": [
                    {"zone": 4, "midair": "on", "corridor": "false"},
                    {"zone": 3, "midair": "false", "corridor": "false"},
                ],
                **identity,
            },
        ),
        # disc_freestyle — four maxed categories (criteria{}-producing) + identity + an OVERLONG
        # nome (80 chars > 64) to prove the _clean per-field cap holds on the aired line.
        (
            create_app(channel_dir, cam_ids=["cam_wide"]),
            {
                "discipline": "disc_freestyle",
                "team": "10",
                "dog": "10",
                "player": "10",
                "catch": "10",
                "adjustment": "0",
                "nome": "N" * 80,
                **identity,
            },
        ),
        # agility — a count_up run over SCT (faults_breakdown{}-producing) + identity. Needs the
        # agility profile app (sport="agility").
        (
            create_app(
                channel_dir,
                cam_ids=["cam_wide"],
                profile=score_calc.FCI_AGILITY_PROFILE,
                sport="agility",
            ),
            {
                "discipline": "agility",
                "tempo": "00:34.50",
                "sct": "00:30.00",
                "course_faults": "5",
                **identity,
            },
        ),
    ]

    for app, body in rich_posts:
        disc = body["discipline"]
        resp = app.test_client().post("/score", json=body)
        assert resp.status_code == 204, f"{disc}: /score returned {resp.status_code}, expected 204"

        written = read_score(str(file_channel["score"]))
        line = overlay_path.read_text(encoding="utf-8")

        # SINGLE non-empty line — the rich subkeys never reached render_overlay_text.
        assert line, f"{disc}: overlay.txt is empty after a rich POST"
        assert "\n" not in line and "\r" not in line, (
            f"{disc}: overlay.txt spilled a CR/LF — a dict/list subkey reached render_overlay_text"
        )
        # Byte-for-byte equal to the pure renderer for the SAME doc (renderer unbroken by 18-01).
        assert line == render_overlay_text(written), f"{disc}: aired line drifted from the renderer"

        # The overlong freestyle nome is bounded by _clean — the 80-char value never airs in full,
        # proving the per-field 64-char cap (no line-injection / OBS read-from-file overflow).
        if disc == "disc_freestyle":
            assert "N" * 80 not in line, "freestyle nome was not length-capped (OBS-source overflow)"
            assert "N" * _MAX_FIELD_LEN in line, "the 64-char nome cap prefix must be present"
