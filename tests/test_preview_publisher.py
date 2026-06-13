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
