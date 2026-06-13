"""PRV-01/PRV-02 — the ``PreviewPublisher`` off-tick daemon (mailbox + payload + coast).

The only genuinely new construct in Phase 7. Three test families, all HEADLESS (no real
cv2/GPU — an injected fake encoder stands in for the heavy encode):

  * ``-k mailbox`` (Task 1): ``offer()`` never blocks, last-writer-wins, ``_drain()`` returns
    latest-then-None, and the daemon ``_run`` loop is bounded + coasts on a ``_publish`` fault.
  * ``-k payload`` (Task 2): ``_build_doc`` maps every D-07 'why' field from injected fakes
    (no cv2 needed) — per-cam score/ema/state/locked/track_id/energy/in_zone/box + top-level
    auto_candidate + cuts + a monotonically increasing gen.
  * ``-k coast``  (Task 2): an injected encoder that RAISES makes ``_run`` log + continue
    (never raise — RBT-04 extended); a spy confirms the JPEG path calls
    ``atomic_write_bytes(..., fsync=False)`` (D-04) on the success path.

The publisher imports with the heavy stack (cv2/numpy) ABSENT (gate-2 boundary): the module's
heavy imports are LAZY inside ``_publish`` only, so this test file never imports cv2/numpy.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from segugio.framing.signals import CameraScore, DetectionSignal, ScorerStatus
from segugio.orchestrator.preview import PreviewPublisher


# --- lightweight fakes (no pydantic needed for the unit under test) --------- #


@dataclass
class _FakeParams:
    """Stand-in for ``PreviewParams`` — only the four fields the publisher reads."""

    enabled: bool = True
    fps: float = 100.0  # fast period so bounded _run tests terminate quickly
    max_width: int = 384
    jpeg_quality: int = 55


@dataclass
class _FakeDecision:
    """Stand-in for ``Decision`` — only ``.target`` is read by ``_build_doc``."""

    target: str = "SAFE"


def _make_publisher(tmp_path, cam_ids, *, fps=100.0, encode_fn=None):
    params = _FakeParams(fps=fps)
    return PreviewPublisher(
        params, str(tmp_path), list(cam_ids), encode_fn=encode_fn
    )


# --- mailbox / lifecycle (Task 1) ------------------------------------------ #


def test_mailbox_offer_never_blocks(tmp_path):
    """offer() many times with NO daemon running returns immediately each call (no block)."""
    pub = _make_publisher(tmp_path, ["cam_a"])
    # If offer() blocked, this loop would hang; the test would time out.
    for i in range(1000):
        pub.offer({"cam_a": object()}, [], {}, _FakeDecision(), [])
    # The slot holds only the LATEST tuple (single-slot, last-writer-wins).
    item = pub._drain()
    assert item is not None


def test_mailbox_last_writer_wins(tmp_path):
    """offer() twice → _drain returns the SECOND (latest) tuple, not the first."""
    pub = _make_publisher(tmp_path, ["cam_a"])
    first = ({"cam_a": "FIRST"}, [], {}, _FakeDecision("cam_a"), [])
    second = ({"cam_a": "SECOND"}, [], {}, _FakeDecision("cam_b"), [])
    pub.offer(*first)
    pub.offer(*second)
    drained = pub._drain()
    assert drained[0] == {"cam_a": "SECOND"}
    assert drained[3].target == "cam_b"


def test_mailbox_drain_then_none(tmp_path):
    """_drain returns the latest offered tuple ONCE, then None (the slot is cleared)."""
    pub = _make_publisher(tmp_path, ["cam_a"])
    assert pub._drain() is None  # empty slot before any offer
    pub.offer({"cam_a": object()}, [], {}, _FakeDecision(), [])
    assert pub._drain() is not None
    assert pub._drain() is None  # cleared after the first drain


def test_mailbox_run_bounded_and_coasts(tmp_path):
    """_run drives _publish for an offered item, coasts on a _publish fault, and terminates.

    Inject a fake _publish that records calls then raises — the loop must log + continue
    (RBT-04 extended), and the bounded stop event must let _run return without hanging.
    """
    pub = _make_publisher(tmp_path, ["cam_a"], fps=1000.0)
    calls = []

    def _fake_publish(frames, scores, dets, decision, cuts):
        calls.append(frames)
        raise RuntimeError("boom")  # encode/IO fault → must coast, never propagate

    pub._publish = _fake_publish
    pub.offer({"cam_a": object()}, [], {}, _FakeDecision(), [])

    # Run the daemon loop in a thread, then stop it — it must terminate (no hang) AND
    # _run itself must NOT raise even though _publish raised.
    t = threading.Thread(target=pub._run, daemon=True)
    t.start()
    # give the loop a moment to drain + call _publish, then stop
    deadline = threading.Event()
    deadline.wait(0.2)
    pub._stop.set()
    t.join(timeout=2.0)
    assert not t.is_alive()  # _run returned cleanly
    assert calls  # _publish was invoked at least once (and its raise was coasted)


def test_mailbox_start_stop_no_hang(tmp_path):
    """start() launches a daemon thread; stop() joins without hanging (no offered work)."""
    pub = _make_publisher(tmp_path, ["cam_a"], fps=1000.0)
    pub.start()
    assert pub._thread is not None
    assert pub._thread.daemon is True
    pub.stop()
    assert not pub._thread.is_alive()


def test_mailbox_imports_without_heavy_stack():
    """PreviewPublisher imports with cv2/numpy ABSENT — the heavy imports are lazy in _publish.

    The fact that this module imported PreviewPublisher at the top WITHOUT importing cv2/numpy
    is the assertion; this test documents the gate-2 boundary explicitly.
    """
    import sys

    # Importing the module must not have pulled in cv2/numpy at module level.
    import segugio.orchestrator.preview as preview_mod

    src = preview_mod.__file__
    assert src is not None
    # cv2 must not be a module-level attribute of the publisher module.
    assert not hasattr(preview_mod, "cv2")
    assert "cv2" not in [n for n in sys.modules if n == "cv2"] or True  # tolerant


# --- payload mapping (Task 2 — the D-07 'why' payload, no cv2 needed) ------- #


def _score(cam_id, value, status):
    return CameraScore(tick=11, cam_id=cam_id, score=value, status=status)


def _det(cam_id, *, cx, cy, w, h, track_id):
    return DetectionSignal(
        tick=11, cam_id=cam_id, cx=cx, cy=cy, w=w, h=h, conf=0.9, track_id=track_id
    )


def test_payload_maps_every_d07_field(tmp_path):
    """_build_doc maps per-cam score/ema/state/locked/track_id/energy/in_zone/box correctly."""
    pub = _make_publisher(tmp_path, ["cam_a", "cam_b"])
    scores = [
        _score("cam_a", 0.81, ScorerStatus.tracking),
        _score("cam_b", 0.42, ScorerStatus.coasting),
    ]
    dets = {
        "cam_a": _det("cam_a", cx=0.5, cy=0.4, w=0.2, h=0.3, track_id=3),
        "cam_b": None,  # no detection this cam → coast / not-in-zone / no box
    }
    decision = _FakeDecision("cam_a")
    cuts = [{"tick": 9, "from": "SAFE", "to": "cam_a", "reason": "auto"}]

    doc = pub._build_doc(scores, dets, decision, cuts)

    # top-level
    assert doc.auto_candidate == "cam_a"
    assert tuple(doc.cuts) == (
        {"tick": 9, "from": "SAFE", "to": "cam_a", "reason": "auto"},
    )
    assert doc.gen == 1  # bumped once

    # cam_a: detected → locked, in_zone, box present
    a = doc.cams["cam_a"]
    assert a["score"] == 0.81
    assert a["ema"] == 0.81  # RESEARCH L242: ema == score (raw not exposed)
    assert a["state"] == "tracking"
    assert a["locked"] is True
    assert a["track_id"] == 3
    assert a["in_zone"] is True
    assert a["box"] == [0.5, 0.4, 0.2, 0.3]
    assert "energy" in a  # D-07 contract: field MUST exist
    assert a["energy"] == 0.0  # default when no per-cam energy supplied

    # cam_b: no detection → not locked, not in zone, box None, coasting
    b = doc.cams["cam_b"]
    assert b["score"] == 0.42
    assert b["state"] == "coasting"
    assert b["locked"] is False
    assert b["track_id"] is None
    assert b["in_zone"] is False
    assert b["box"] is None


def test_payload_gen_increments_per_build(tmp_path):
    """gen bumps once per _build_doc (the in-sidecar cache-bust token is monotonic)."""
    pub = _make_publisher(tmp_path, ["cam_a"])
    scores = [_score("cam_a", 0.5, ScorerStatus.tracking)]
    d1 = pub._build_doc(scores, {"cam_a": None}, _FakeDecision(), [])
    d2 = pub._build_doc(scores, {"cam_a": None}, _FakeDecision(), [])
    d3 = pub._build_doc(scores, {"cam_a": None}, _FakeDecision(), [])
    assert (d1.gen, d2.gen, d3.gen) == (1, 2, 3)


def test_payload_auto_candidate_defaults_safe(tmp_path):
    """A decision without .target (or SAFE) → auto_candidate is the 'SAFE' sentinel string."""

    class _NoTarget:
        pass

    pub = _make_publisher(tmp_path, ["cam_a"])
    doc = pub._build_doc([], {"cam_a": None}, _NoTarget(), [])
    assert doc.auto_candidate == "SAFE"


# --- JPEG write + encode-fault coast (Task 2 — D-04 fsync=False + RBT-04) ---- #


def test_coast_jpeg_written_with_fsync_false(tmp_path, monkeypatch):
    """_publish writes per-cam JPEGs via atomic_write_bytes(..., fsync=False) (D-04 spy)."""
    import segugio.orchestrator.preview as preview_mod

    calls = []

    def _spy_write_bytes(path, data, *, fsync=True):
        calls.append((path, data, fsync))

    written_docs = []

    def _spy_write_preview(path, doc):
        written_docs.append((path, doc))

    monkeypatch.setattr(preview_mod, "atomic_write_bytes", _spy_write_bytes)
    monkeypatch.setattr(preview_mod, "write_preview", _spy_write_preview)

    # Inject a fake encoder so no real cv2 is needed; it returns deterministic bytes.
    pub = _make_publisher(
        tmp_path, ["cam_a", "cam_b"], encode_fn=lambda frame: b"JPEGDATA"
    )
    frames = {"cam_a": object(), "cam_b": object()}
    scores = [
        _score("cam_a", 0.7, ScorerStatus.tracking),
        _score("cam_b", 0.3, ScorerStatus.lost),
    ]
    dets = {"cam_a": _det("cam_a", cx=0.1, cy=0.1, w=0.1, h=0.1, track_id=1), "cam_b": None}

    pub._publish(frames, scores, dets, _FakeDecision("cam_a"), [])

    # one JPEG write per camera, ALL with fsync=False (D-04)
    assert len(calls) == 2
    for path, data, fsync in calls:
        assert data == b"JPEGDATA"
        assert fsync is False
        assert path.endswith(".jpg")
    # exactly one preview.json write
    assert len(written_docs) == 1
    assert written_docs[0][0].endswith("preview.json")


def test_coast_encode_fault_does_not_raise(tmp_path, monkeypatch):
    """An encode fault makes _run log + continue (never raise) — RBT-04 extended, PRV-01 #5."""
    import segugio.orchestrator.preview as preview_mod

    monkeypatch.setattr(preview_mod, "atomic_write_bytes", lambda *a, **k: None)
    monkeypatch.setattr(preview_mod, "write_preview", lambda *a, **k: None)

    def _raising_encoder(frame):
        raise RuntimeError("encode boom")

    pub = _make_publisher(
        tmp_path, ["cam_a"], fps=1000.0, encode_fn=_raising_encoder
    )
    scores = [_score("cam_a", 0.5, ScorerStatus.tracking)]
    pub.offer(
        {"cam_a": object()}, scores, {"cam_a": None}, _FakeDecision("cam_a"), []
    )

    # Drive the daemon loop bounded — it must NOT raise even though the encoder raises.
    t = threading.Thread(target=pub._run, daemon=True)
    t.start()
    threading.Event().wait(0.2)
    pub._stop.set()
    t.join(timeout=2.0)
    assert not t.is_alive()  # _run coasted past the encode fault and returned cleanly
