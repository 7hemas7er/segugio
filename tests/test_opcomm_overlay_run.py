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


def test_overlay_run_round_trip(tmp_path):
    """write_overlay_run then read_overlay_run round-trips equal (frozen ==)."""
    from segugio.opcomm.channel import read_overlay_run, write_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    path = str(tmp_path / "overlay_run.json")
    doc = OverlayRunDoc(running=True, started_at=123.5, gen=3)
    write_overlay_run(path, doc)
    assert read_overlay_run(path) == doc


def test_overlay_run_default_when_absent(tmp_path):
    """An absent overlay_run.json → read_overlay_run returns the empty default (RBT-04)."""
    from segugio.opcomm.channel import read_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    path = str(tmp_path / "does-not-exist.json")
    assert read_overlay_run(path) == OverlayRunDoc()


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


def test_overlay_run_doc_is_frozen():
    """OverlayRunDoc is frozen: attribute assignment is rejected (mirrors PreviewDoc)."""
    from segugio.opcomm.records import OverlayRunDoc

    doc = OverlayRunDoc(running=True, started_at=123.5, gen=3)
    with pytest.raises(Exception):
        doc.gen = 99  # type: ignore[misc]


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


# --- boundary hardening (CR-01 / WR-02 / WR-04) ------------------------------ #


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_overlay_run_rejects_non_finite_started_at(tmp_path, token):
    """CR-01: a non-finite started_at token on disk collapses the read to the safe default.

    json.loads accepts NaN/Infinity/-Infinity by default; without the parse_constant guard +
    math.isfinite check a non-finite would survive as OverlayRunDoc(started_at=nan) and escape
    /overlay-json as an RFC-8259-invalid token. The read boundary must default it (started_at None).
    """
    from segugio.opcomm.channel import read_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    bad = tmp_path / "overlay_run.json"
    bad.write_text(
        '{"running": true, "started_at": ' + token + ', "gen": 5}', encoding="utf-8"
    )
    # Whole file defaults (parse_constant rejects the token → _read_json returns None).
    assert read_overlay_run(str(bad)) == OverlayRunDoc()


def test_overlay_run_doc_rejects_non_finite_float():
    """CR-01 defense-in-depth: OverlayRunDoc rejects a non-finite started_at at construction."""
    import math

    from segugio.opcomm.records import OverlayRunDoc

    with pytest.raises(ValueError):
        OverlayRunDoc(started_at=math.nan)
    with pytest.raises(ValueError):
        OverlayRunDoc(started_at=math.inf)


def test_overlay_run_doc_rejects_bool_started_at():
    """WR-02: a bool started_at (float(True)=1.0 garbage anchor) is rejected at construction."""
    from segugio.opcomm.records import OverlayRunDoc

    with pytest.raises(ValueError):
        OverlayRunDoc(started_at=True)
    with pytest.raises(ValueError):
        OverlayRunDoc(started_at=False)


def test_overlay_run_bool_started_at_on_disk_defaults(tmp_path):
    """WR-02: a bool started_at on disk collapses the read to the safe default (None)."""
    from segugio.opcomm.channel import read_overlay_run
    from segugio.opcomm.records import OverlayRunDoc

    bad = tmp_path / "overlay_run.json"
    bad.write_text('{"running": true, "started_at": true, "gen": 5}', encoding="utf-8")
    assert read_overlay_run(str(bad)) == OverlayRunDoc()


def test_overlay_run_running_string_false_is_false(tmp_path):
    """WR-04: the string "false" must read as running=False (not blanket-truthy True)."""
    from segugio.opcomm.channel import read_overlay_run

    f = tmp_path / "overlay_run.json"
    f.write_text('{"running": "false", "started_at": null, "gen": 2}', encoding="utf-8")
    ovr = read_overlay_run(str(f))
    assert ovr.running is False
    assert ovr.gen == 2


def test_overlay_run_running_numeric_one_is_true(tmp_path):
    """WR-04: numeric running=1 still reads True (the pinned coercion is preserved)."""
    from segugio.opcomm.channel import read_overlay_run

    f = tmp_path / "overlay_run.json"
    f.write_text('{"running": 1, "started_at": null, "gen": 0}', encoding="utf-8")
    assert read_overlay_run(str(f)).running is True
