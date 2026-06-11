"""SCR-01 — atomic operator↔system file channel.

Behaviors asserted (05-01 Task 2):
  - atomic round-trip: atomic_write_json/atomic_write_text round-trip exactly.
  - same-dir temp: the temp file lands in os.path.dirname(target), never another volume.
  - interleaved reader never sees a partial/empty file across many rapid writes.
  - channel read_* on a malformed/half-present file returns a safe default, never raises.

The atomic write is the spine of the whole operator↔system channel (D-03/09/10/11):
score/runstate/command/status all ride on temp + fsync + os.replace (Pitfall 6).
"""

from __future__ import annotations

import json
import os
import threading

import pytest

from segugio.opcomm.atomic import atomic_write_json, atomic_write_text
from segugio.opcomm import channel
from segugio.opcomm.records import (
    Discipline,
    DirectorStatus,
    OperatorCommand,
    RunState,
    ScoreDoc,
)


def test_atomic_round_trip(tmp_path):
    """atomic_write_json round-trips a dict exactly (UTF-8, non-ASCII preserved)."""
    target = tmp_path / "score.json"
    obj = {"discipline": "disc_freestyle", "punti": 42.5, "label": "Però"}
    atomic_write_json(str(target), obj)
    assert json.loads(target.read_text(encoding="utf-8")) == obj

    txt_target = tmp_path / "overlay.txt"
    atomic_write_text(str(txt_target), "Punti: 42 — Però")
    assert txt_target.read_text(encoding="utf-8") == "Punti: 42 — Però"


def test_temp_is_same_dir(tmp_path, monkeypatch):
    """The temp file is created in os.path.dirname(target), NEVER another volume (Pitfall 6)."""
    target = tmp_path / "score.json"
    seen_dirs: list[str] = []

    real_replace = os.replace

    def _spy_replace(src, dst):
        # at replace time the temp must still be in the target's directory
        seen_dirs.append(os.path.dirname(os.path.abspath(src)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _spy_replace)
    atomic_write_json(str(target), {"a": 1})
    assert seen_dirs == [os.path.dirname(os.path.abspath(str(target)))]


def test_interleaved_reader_never_partial(tmp_path):
    """A reader interleaved with many rapid writes never observes a partial/empty file."""
    target = tmp_path / "score.json"
    atomic_write_json(str(target), {"n": 0})

    stop = threading.Event()
    bad: list[str] = []

    def _reader():
        while not stop.is_set():
            try:
                raw = target.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            if raw == "":
                bad.append("empty")
                continue
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                bad.append(raw[:20])

    t = threading.Thread(target=_reader)
    t.start()
    try:
        for i in range(500):
            atomic_write_json(str(target), {"n": i, "pad": "x" * (i % 64)})
    finally:
        stop.set()
        t.join()

    assert bad == [], f"reader saw partial/empty content: {bad[:5]}"


def test_channel_read_malformed_returns_default(file_channel):
    """A malformed/half-present file → channel read_* returns the record default, never raises."""
    # write garbage directly (simulating a torn/legacy file)
    file_channel["score"].write_text("{not json", encoding="utf-8")
    file_channel["runstate"].write_text("", encoding="utf-8")
    file_channel["command"].write_text("[1,2,3]", encoding="utf-8")  # wrong shape
    file_channel["status"].write_text("\x00\x01garbage", encoding="utf-8")

    # none of these raise; each returns a safe default record (or None for command)
    score = channel.read_score(str(file_channel["score"]))
    run = channel.read_runstate(str(file_channel["runstate"]))
    cmd = channel.read_command(str(file_channel["command"]))
    status = channel.read_status(str(file_channel["status"]))

    assert isinstance(score, ScoreDoc)
    assert isinstance(run, RunState)
    assert cmd is None  # no valid command present → None (no-op override)
    assert isinstance(status, DirectorStatus)


def test_channel_missing_file_returns_default(file_channel):
    """A wholly absent file → read_* returns a default, never raises (boundary, RBT-04)."""
    assert isinstance(channel.read_score(str(file_channel["score"])), ScoreDoc)
    assert isinstance(channel.read_runstate(str(file_channel["runstate"])), RunState)
    assert channel.read_command(str(file_channel["command"])) is None
    assert isinstance(channel.read_status(str(file_channel["status"])), DirectorStatus)


def test_channel_round_trip(file_channel):
    """write_* then read_* round-trips each record type through the atomic spine."""
    score = ScoreDoc(discipline=Discipline.agility, fields={"tempo": "32.10", "penalita": "5"})
    channel.write_score(str(file_channel["score"]), score)
    assert channel.read_score(str(file_channel["score"])) == score

    run = RunState(action="start", just_started=True, just_stopped=False)
    channel.write_runstate(str(file_channel["runstate"]), run)
    assert channel.read_runstate(str(file_channel["runstate"])) == run

    cmd = OperatorCommand(force_cam="cam_long")
    channel.write_command(str(file_channel["command"]), cmd)
    assert channel.read_command(str(file_channel["command"])) == cmd

    status = DirectorStatus(
        live_cam="cam_long", reason="auto", alive={"cam_wide": True, "cam_long": True}
    )
    channel.write_status(str(file_channel["status"]), status)
    assert channel.read_status(str(file_channel["status"])) == status


def test_operator_command_rejects_force_and_release():
    """OperatorCommand mirrors OverrideCmd: force_cam + release both set is rejected."""
    with pytest.raises(ValueError):
        OperatorCommand(force_cam="cam_long", release=True)


def test_operator_command_to_override():
    """OperatorCommand.to_override() yields the locked decision.signals.OverrideCmd."""
    from segugio.decision.signals import OverrideCmd

    assert OperatorCommand(force_cam="cam_low").to_override() == OverrideCmd(force_cam="cam_low")
    assert OperatorCommand(release=True).to_override() == OverrideCmd(release=True)
