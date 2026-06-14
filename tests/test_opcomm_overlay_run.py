"""OVD-02 — overlay_run.json channel (OverlayRunDoc round-trip + safe-default boundary).

The run start/stop edge stamps a NEW console-owned ``overlay_run.json`` sidecar (D-03 separation
— ``runstate.json``/``RunState`` is NOT touched; the director reads runstate every tick, never
overlay_run). Mirrors ``test_preview_channel.py``:

  - round-trip equality: ``read_overlay_run(write_overlay_run(doc)) == doc`` (frozen ==).
  - safe default on an absent file → ``OverlayRunDoc()`` (never raises, RBT-04 / D-04).
  - safe default on a torn/malformed file → ``OverlayRunDoc()`` (never raises, RBT-04 / D-04).
  - frozen + boundary-normalizing record (mirrors ``PreviewDoc``/``ScoreDoc``).

RED-by-design: ``OverlayRunDoc`` / ``read_overlay_run`` / ``write_overlay_run`` do not exist until
Plan 10-02. Every test is ``@pytest.mark.xfail(strict=False)`` and imports the not-yet-existing
symbols INSIDE its body so collection stays green (an ImportError under xfail is an expected fail,
never a collection error). Plan 10-02 creates the symbols and REMOVES these markers, flipping the
tests to real passing assertions.

Heavy imports (numpy/cv2/torch) are intentionally absent — opcomm + stdlib only.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="impl lands in Plan 10-02", strict=False)
def test_overlay_run_round_trip(tmp_path):
    """write_overlay_run then read_overlay_run round-trips equal (frozen ==)."""
    from segugio.opcomm.channel import read_overlay_run, write_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    path = str(tmp_path / "overlay_run.json")
    doc = OverlayRunDoc(running=True, started_at=123.5, gen=3)
    write_overlay_run(path, doc)
    assert read_overlay_run(path) == doc


@pytest.mark.xfail(reason="impl lands in Plan 10-02", strict=False)
def test_overlay_run_default_when_absent(tmp_path):
    """An absent overlay_run.json → read_overlay_run returns the empty default (RBT-04)."""
    from segugio.opcomm.channel import read_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    path = str(tmp_path / "does-not-exist.json")
    assert read_overlay_run(path) == OverlayRunDoc()


@pytest.mark.xfail(reason="impl lands in Plan 10-02", strict=False)
@pytest.mark.parametrize(
    "payload",
    [
        "{not json",  # torn JSON
        b"\x00\x01garbage",  # binary garbage
        "[1, 2, 3]",  # valid JSON, wrong top-level shape
        "",  # empty file
    ],
)
def test_overlay_run_default_when_malformed(tmp_path, payload):
    """A torn/malformed overlay_run.json → the safe default, never raises (RBT-04 / D-04)."""
    from segugio.opcomm.channel import read_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    bad = tmp_path / "overlay_run.json"
    if isinstance(payload, bytes):
        bad.write_bytes(payload)
    else:
        bad.write_text(payload, encoding="utf-8")
    assert read_overlay_run(str(bad)) == OverlayRunDoc()


@pytest.mark.xfail(reason="impl lands in Plan 10-02", strict=False)
def test_overlay_run_doc_is_frozen():
    """OverlayRunDoc is frozen: attribute assignment is rejected (mirrors PreviewDoc)."""
    from segugio.opcomm.records import OverlayRunDoc

    doc = OverlayRunDoc(running=True, started_at=123.5, gen=3)
    with pytest.raises(Exception):
        doc.gen = 99  # type: ignore[misc]


@pytest.mark.xfail(reason="impl lands in Plan 10-02", strict=False)
def test_overlay_run_doc_normalizes():
    """__post_init__ coerces scalars (bool/float|None/int) at the frozen boundary."""
    from segugio.opcomm.records import OverlayRunDoc

    doc = OverlayRunDoc(running=1, started_at="123.5", gen="7")
    assert doc.running is True
    assert doc.started_at == 123.5
    assert isinstance(doc.started_at, float)
    assert doc.gen == 7
    assert isinstance(doc.gen, int)

    # started_at=None survives as None (the run-not-started / stopped state).
    assert OverlayRunDoc(started_at=None).started_at is None
