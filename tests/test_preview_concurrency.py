"""UXT-02 / D-08 — the safety-critical /command override is never blocked by preview GETs.

The Flask in-process ``test_client`` does NOT exercise WSGI threading, so this is the one
genuinely new test shape (PATTERNS.md "No Analog Found"): bind a REAL server on an ephemeral
port (``port=0``) on a background thread with ``threaded=True``, fire N concurrent
``GET /preview/<cam>.jpg`` requests, then time a ``POST /command`` and assert it completes well
under threshold AND that command.json was written. This proves a preview GET can never starve
the lone WSGI worker so the override override stalls (threat T-08-01).
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


def test_command_not_blocked_during_preview_gets(live_server):
    """A POST /command (force_cam) returns < 1.0 s while 8 concurrent preview GETs are in flight."""
    base, ch = live_server
    n = 8
    with ThreadPoolExecutor(max_workers=n + 1) as pool:
        # Fire N concurrent preview GETs (the would-be worker starvers).
        get_futures = [pool.submit(_get, base, "/preview/cam_wide.jpg") for _ in range(n)]
        # While they are in flight, time the safety-critical override POST.
        code, elapsed = pool.submit(_post_command, base, "cam_long").result(timeout=10)
        for f in get_futures:
            f.result(timeout=10)

    assert code == 204, f"override POST returned {code}, expected 204"
    assert elapsed < 1.0, f"override POST took {elapsed:.3f}s — blocked by preview GETs (UXT-02)"
    # The override was actually written (not just acknowledged).
    cmd = read_command(str(ch["command"]))
    assert cmd is not None
    assert cmd.force_cam == "cam_long"
