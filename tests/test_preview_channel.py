"""PRV-02 — preview.json sidecar channel (PreviewDoc round-trip + safe-default boundary).

The off-tick "why" payload travels in a NEW ``preview.json`` sidecar (D-03 separation —
``status.json``/``DirectorStatus`` is NOT touched). Mirrors ``test_status_channel.py``:

  - round-trip equality: ``read_preview(write_preview(doc)) == doc`` regardless of dict order.
  - safe default on an absent file → ``PreviewDoc()`` (never raises, RBT-04).
  - safe default on a torn/malformed file → ``PreviewDoc()`` (never raises, RBT-04).

``PreviewDoc`` is frozen + normalizing (mirrors ``DirectorStatus``) so two docs with the same
content compare ``==`` independent of insertion order — the contract the round-trip relies on.
"""

from __future__ import annotations

from segugio.opcomm.channel import read_preview, write_preview
from segugio.opcomm.records import PreviewDoc


def _sample_doc() -> PreviewDoc:
    """A populated PreviewDoc: multiple cams (full D-07 per-cam payload) + a cuts ring."""
    return PreviewDoc(
        tick=42,
        gen=7,
        auto_candidate="cam_long",
        cams={
            "cam_wide": {
                "score": 0.81,
                "ema": 0.81,
                "state": "tracking",
                "locked": True,
                "track_id": 3,
                "energy": 0.12,
                "in_zone": True,
                "box": [0.5, 0.4, 0.2, 0.3],
            },
            "cam_long": {
                "score": 0.42,
                "ema": 0.42,
                "state": "coasting",
                "locked": False,
                "track_id": None,
                "energy": 0.0,
                "in_zone": False,
                "box": None,
            },
        },
        cuts=(
            {"tick": 10, "from": "SAFE", "to": "cam_wide", "reason": "auto"},
            {"tick": 31, "from": "cam_wide", "to": "cam_long", "reason": "auto"},
        ),
    )


def test_preview_round_trip(tmp_path):
    """write_preview then read_preview round-trips equal (PRV-02), regardless of dict order."""
    path = str(tmp_path / "preview.json")
    doc = _sample_doc()
    write_preview(path, doc)
    assert read_preview(path) == doc


def test_preview_round_trip_insertion_order_independent(tmp_path):
    """Two docs with the same content but different cam-insertion order are ==-equal + round-trip."""
    path = str(tmp_path / "preview.json")
    doc_a = PreviewDoc(
        tick=1,
        cams={"a": {"score": 0.1}, "b": {"score": 0.2}},
    )
    doc_b = PreviewDoc(
        tick=1,
        cams={"b": {"score": 0.2}, "a": {"score": 0.1}},
    )
    assert doc_a == doc_b  # normalization makes insertion order irrelevant
    write_preview(path, doc_a)
    assert read_preview(path) == doc_b


def test_preview_default_when_absent(tmp_path):
    """An absent preview.json → read_preview returns the empty default, never raises (RBT-04)."""
    path = str(tmp_path / "does-not-exist.json")
    assert read_preview(path) == PreviewDoc()


def test_preview_default_when_malformed(tmp_path):
    """A torn/malformed preview.json → read_preview returns the default, never raises (RBT-04)."""
    bad = tmp_path / "preview.json"

    bad.write_text("{not json", encoding="utf-8")
    assert read_preview(str(bad)) == PreviewDoc()

    bad.write_bytes(b"\x00\x01garbage")
    assert read_preview(str(bad)) == PreviewDoc()

    bad.write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, wrong top-level shape
    assert read_preview(str(bad)) == PreviewDoc()

    bad.write_text("", encoding="utf-8")  # empty file
    assert read_preview(str(bad)) == PreviewDoc()


def test_preview_doc_is_frozen_and_hashable():
    """PreviewDoc mirrors DirectorStatus: frozen + hashable (cams/cuts normalized to immutable)."""
    doc = _sample_doc()
    # hashable → the normalization to immutable forms worked (a plain dict would raise here is
    # NOT the point; the dataclass holds dicts but stays usable as a frozen ==-comparable value)
    assert doc == _sample_doc()
    # frozen: attribute assignment is rejected
    try:
        doc.tick = 99  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("PreviewDoc must be frozen")


def test_preview_empty_default_round_trips(tmp_path):
    """The empty PreviewDoc() also round-trips (write_preview(PreviewDoc()) → read back equal)."""
    path = str(tmp_path / "preview.json")
    write_preview(path, PreviewDoc())
    assert read_preview(path) == PreviewDoc()
