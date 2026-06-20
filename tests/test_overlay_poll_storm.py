"""RBT-06 SC#3 / UXT-02 — the safety-critical /command override is never starved by an
/overlay-json poll storm.

The Phase-11 overlay page fetch-polls ``GET /overlay-json`` every tick; with several tablets
open this is a concurrent GET storm against the lone WSGI worker. The override ``POST /command``
is safety-critical (the operator forcing a camera) and must NEVER be blocked by that storm.

The Flask in-process ``test_client`` does NOT exercise WSGI threading, so it yields a FALSE
GREEN here (PATTERNS.md Pitfall 2): this gate binds a REAL ``make_server(..., threaded=True)``
werkzeug server on an ephemeral port (``port=0``) on a background thread — the exact UXT-02
harness from ``test_preview_concurrency.py`` — and retargets the N concurrent GETs from
``/preview/<cam>.jpg`` to ``/overlay-json`` (the route under test for SC#3). It then times a
``POST /command`` and asserts it completes well under threshold AND that command.json was
actually written (the override took effect, not just acknowledged).
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from werkzeug.serving import make_server

from segugio.opcomm.channel import read_command


@pytest.fixture
def live_server(preview_channel):
    """A real Waitress-free threaded werkzeug server on an ephemeral port (UXT-02 proof)."""
    from segugio.ui.app import create_app

    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    server = make_server("127.0.0.1", 0, app, threaded=True)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", preview_channel
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _get(base: str, path: str) -> int:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as exc:  # 404 etc. still proves the worker served it
        return exc.code


def _post_command(base: str, force_cam: str) -> tuple[int, float]:
    data = urllib.parse.urlencode({"force_cam": force_cam}).encode()
    req = urllib.request.Request(base + "/command", data=data, method="POST")
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()
        code = resp.status
    return code, time.perf_counter() - start


def test_command_not_blocked_during_overlay_json_storm(live_server):
    """A POST /command (force_cam) returns < 1.0 s while 8 concurrent /overlay-json GETs fly."""
    base, ch = live_server
    n = 8
    with ThreadPoolExecutor(max_workers=n + 1) as pool:
        # Fire N concurrent /overlay-json polls (the would-be worker starvers — SC#3 storm).
        get_futures = [pool.submit(_get, base, "/overlay-json") for _ in range(n)]
        # While they are in flight, time the safety-critical override POST.
        code, elapsed = pool.submit(_post_command, base, "cam_long").result(timeout=10)
        for f in get_futures:
            f.result(timeout=10)

    assert code == 204, f"override POST returned {code}, expected 204"
    assert elapsed < 1.0, (
        f"override POST took {elapsed:.3f}s — starved by an /overlay-json poll storm "
        f"(SC#3 / UXT-02)"
    )
    # The override was actually written (not just acknowledged).
    cmd = read_command(str(ch["command"]))
    assert cmd is not None
    assert cmd.force_cam == "cam_long"
