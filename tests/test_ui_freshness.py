"""UXT-03 + MVW-05 — served-console hygiene assertions (Flask test client, no heavy deps).

These tests inspect the SERVED `console.html` (the single hand-rolled Jinja template) for the
Phase-9 Wave-3 contract:

  * MVW-05 switch-history strip rendered from the preview.json `cuts` ring (newest-first) with the
    Italian reason mapping, "Nessun cambio recente" when empty.
  * UXT-03 flicker-free + leak-free refresh: ONE persistent off-DOM `Image()` preloader per tile +
    `decode()`-before-swap — NEVER a `new Image()` per frame; hidden tiles → a 1×1 data-URI src.
  * UXT-03 freshness watchdog + freshness stamp + sleep/wake resume: the foreground gen-age STALE
    driver, the "agg. {n}s fa" / "frame non aggiornato" stamp, the visibilitychange + pageshow/
    pagehide lifecycle wiring (and the ABSENCE of focus/blur/freeze/resume), the deferred resume
    fetch, and the NAMED interval handles.

The console is crash-isolated (Flask + segugio.opcomm only); we assert against the served markup +
inline `<script>` text, mirroring tests/test_ui_score.py's `test_index_serves_italian_console`.
The switch-history *rendering* lives in client JS, so we assert the JS contract (the build function,
the newest-first reverse, the Italian map reuse) is present in the served script and that the
backing `cuts` data contract is exposed by GET /preview (proven end-to-end in test_preview_serving).
"""

from __future__ import annotations

import re

import pytest

from segugio.opcomm.channel import write_preview
from segugio.opcomm.records import PreviewDoc


@pytest.fixture
def client(preview_channel):
    """A Flask test client wired to the tmp_path preview channel (no server, no heavy deps)."""
    from segugio.ui.app import create_app

    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    app.config.update(TESTING=True)
    return app.test_client(), preview_channel


def _served_html(c):
    resp = c.get("/")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _script(html):
    """Extract the inline <script> body (the console's only script block)."""
    m = re.search(r"<script>(.*)</script>", html, re.DOTALL)
    assert m, "console.html must carry an inline <script>"
    return m.group(1)


# --- MVW-05 switch-history strip --------------------------------------------- #


def test_switch_history_renders_from_cuts(client):
    """The served script builds #switch-history from the `cuts` ring, NEWEST-FIRST, with the
    Italian reason map; the backing GET /preview exposes the exact cuts written (MVW-05).

    We assert (a) the data contract: GET /preview returns the written cuts ring, and (b) the
    render contract in the served JS: a buildSwitchHistory(cuts) that reverses the newest-last
    ring (newest-first), formats `"{from} → {to} · {reason-it}"`, and reuses reasonToItalian.
    """
    c, ch = client
    cuts = (
        {"tick": 10, "from": "SAFE", "to": "cam_wide", "reason": "auto"},
        {"tick": 25, "from": "cam_wide", "to": "cam_long", "reason": "override"},
    )
    write_preview(
        str(ch["preview"]),
        PreviewDoc(tick=30, gen=4, auto_candidate="cam_long",
                   cams={"cam_wide": {}, "cam_long": {}}, cuts=cuts),
    )
    # (a) data contract — the cuts ring is exposed for the strip.
    data = c.get("/preview").get_json()
    assert data["cuts"] == [dict(x) for x in cuts]

    # (b) render contract in the served JS.
    script = _script(_served_html(c))
    assert "buildSwitchHistory" in script
    assert "switch-history" in script
    # newest-first = reverse the newest-last ring.
    assert ".reverse()" in script
    # the row format string + the reuse of the WHY-01 Italian reason map.
    assert "→" in script and "·" in script
    assert "reasonToItalian" in script
    # the strip is rebuilt from p.cuts in the poll loop.
    assert "buildSwitchHistory(p.cuts)" in script


def test_switch_history_empty(client):
    """An empty cuts ring → "Nessun cambio recente" (served markup + the JS empty branch)."""
    c, _ = client
    html = _served_html(c)
    # the empty-state copy is present (scaffold default + the JS empty branch both use it).
    assert "Nessun cambio recente" in html
    script = _script(html)
    assert '"Nessun cambio recente"' in script


# --- UXT-03 leak-free / flicker-free refresh --------------------------------- #


def test_no_new_image_per_frame(client):
    """The per-frame refresh creates NO `new Image()` per frame — exactly ONE persistent
    preloader per tile, reused, + decode() before swap (UXT-03 leak-free contract)."""
    c, _ = client
    script = _script(_served_html(c))
    # The persistent-preloader registry + accessor must exist.
    assert "preloaders" in script
    assert "preloaderFor" in script
    # `new Image()` is created exactly ONCE (inside preloaderFor), never per frame.
    assert script.count("new Image()") == 1
    # the persistent Image() lives behind the registry-miss guard (created once, then cached).
    assert "preloaders[cam] = img" in script
    # decode() is the flicker control.
    assert "decode()" in script
    # refreshTile must NOT itself construct an Image (it reuses the preloader).
    m = re.search(r"async function refreshTile\(cam, gen\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m, "refreshTile must be the async decode-swap function"
    assert "new Image()" not in m.group(1)


def test_decode_before_swap(client):
    """The refresh awaits preloader.decode() BEFORE assigning the visible <img>.src, and a decode
    reject is caught (no throw) — the silent-coast invariant (UXT-03)."""
    c, _ = client
    script = _script(_served_html(c))
    m = re.search(r"async function refreshTile\(cam, gen\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m
    body = m.group(1)
    # await decode() must appear BEFORE the visible.src swap.
    decode_idx = body.find("await pre.decode()")
    swap_idx = body.find("visible.src = pre.src")
    assert decode_idx != -1 and swap_idx != -1
    assert decode_idx < swap_idx, "decode() must be awaited before the visible swap"
    # a try/catch wraps the decode-swap so a reject never throws.
    assert "try {" in body and "catch" in body
    # ?t=<gen> nonce preserved (load-bearing, NOT no-store alone).
    assert "?t=" in body
    # gen-strictly-advances gate preserved in the poll loop.
    assert "p.gen > lastGen" in script
    # decoding="sync" belt-and-suspenders on the visible <img>.
    assert 'decoding="sync"' in _served_html(c)


def test_hidden_tile_data_uri(client):
    """Hidden/off tiles get a 1×1 `data:image` src (NOT display:none) so the decoded bitmap frees
    deterministically (UXT-03)."""
    c, _ = client
    script = _script(_served_html(c))
    assert "blankTile" in script
    assert "data:image/gif;base64," in script   # the 1×1 transparent data-URI
    # the poll loop blanks cams absent from `cams` rather than hiding them.
    assert "else blankTile(c)" in script
    # we must NOT switch off tiles via display:none in the refresh path.
    m = re.search(r"function blankTile\(cam\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m and "display" not in m.group(1)


# --- UXT-03 lifecycle / freshness watchdog / sleep-wake resume --------------- #


def test_lifecycle_wiring_present(client):
    """The served script registers visibilitychange + pageshow + pagehide ONLY, and registers
    NONE of focus/blur/unload/freeze/resume; the poll intervals are NAMED handles torn down on
    hide (UXT-03 lifecycle)."""
    c, _ = client
    script = _script(_served_html(c))
    # mandatory lifecycle events.
    assert 'addEventListener("visibilitychange"' in script
    assert '"pageshow"' in script
    assert '"pagehide"' in script
    # FORBIDDEN lifecycle events must NOT be registered on document/window (the SCV-01 input-field
    # `blur` drift-check is unrelated — it is an <input> blur, not a lifecycle trigger). Scope the
    # ban to the document./window. lifecycle surface.
    for forbidden in ("focus", "blur", "unload", "freeze", "resume"):
        assert 'document.addEventListener("' + forbidden + '"' not in script, forbidden
        assert 'window.addEventListener("' + forbidden + '"' not in script, forbidden
    # NAMED interval handles (torn down on hide), not anonymous setInterval-and-forget.
    assert "previewTimer" in script and "statusTimer" in script
    assert "clearInterval(previewTimer)" in script and "clearInterval(statusTimer)" in script
    # hide tears the polls down; resume restarts them.
    assert "function onHide" in script and "function onResume" in script
    assert "stopPolling()" in script and "startPolling()" in script


def test_resume_defers_fetch(client):
    """The resume handler defers the first fetch via setTimeout(...) and records resumeAt; a tile
    renders LIVE only once a frame post-dating resumeAt arrives (UXT-03 iOS Load-failed dodge)."""
    c, _ = client
    script = _script(_served_html(c))
    m = re.search(r"function onResume\(\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m, "onResume must exist"
    body = m.group(1)
    # resumeAt recorded + the first resume fetch wrapped in setTimeout (never sync inside handler).
    assert "resumeAt = Date.now()" in body
    assert "setTimeout(" in body
    assert "RESUME_DEFER_MS" in script
    # a verified-fresh frame post-dating resumeAt clears the just-resumed gate (LIVE only then).
    assert "lastGenAt > resumeAt" in script
    assert "justResumed" in script


def test_gen_age_staleness_watchdog(client):
    """markTiles sets a per-tile STALE state on a stalled gen (the foreground gen-age watchdog) and
    NEVER labels a stale tile LIVE; the bbox overlay hides on STALE (UXT-03 PRIMARY watchdog)."""
    c, _ = client
    html = _served_html(c)
    script = _script(html)
    # the foreground gen-age check (gen vs local clock) is the primary watchdog.
    assert "function isStale" in script
    assert "STALE_MS" in script and "lastGenAt" in script
    m = re.search(r"function markTiles\(status\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m
    body = m.group(1)
    # a frozen tile is forced to the "stale" state, NOT "live".
    assert 'state = "stale"' in body
    # the live-cam computation excludes a frozen tile (so a stale tile can never be LIVE).
    assert "!frozen" in body or "!stale" in body
    # the bbox overlay is hidden on .stale (CSS contract preserved from 09-02).
    assert ".tile.dead .bbox-overlay, .tile.stale .bbox-overlay" in html
    # WR-02 load-time seed preserved (no false MORTO on first paint).
    assert "lastGenAt = Date.now()" in script
    assert "lastGen < 0" in script or "lastGen >= 0" in script


def test_freshness_stamp_copy(client):
    """The freshness stamp shows "agg. {n}s fa" and "frame non aggiornato" when stale (UXT-03)."""
    c, _ = client
    html = _served_html(c)
    script = _script(html)
    assert "function freshnessStamp" in script
    assert '"agg. "' in script and 'agg.' in html
    assert '"frame non aggiornato"' in script
    # the stale stamp is visually distinct (turns red).
    assert ".freshness.stale" in html
    # never "LIVE" on a stale tile: the stale overlay copy is STALE / RICONNESSIONE…, not LIVE.
    assert '"RICONNESSIONE…"' in script and '"STALE"' in script


def test_resume_marks_all_stale_and_named_intervals(client):
    """On resume ALL tiles are marked stale immediately + fresh NAMED intervals start; the WR-02
    load-time lastGenAt seed is preserved (UXT-03)."""
    c, _ = client
    script = _script(_served_html(c))
    m = re.search(r"function onResume\(\)\s*\{(.*?)\n    \}", script, re.DOTALL)
    assert m
    body = m.group(1)
    # all tiles painted stale on resume (either via markTiles(lastStatus) or the explicit fallback).
    assert "markTiles(lastStatus)" in body or 'setTileState(c, "stale")' in body
    assert "startPolling()" in body
    # startPolling builds the named handles via setInterval.
    assert "previewTimer = setInterval(pollPreview" in script
    assert "statusTimer = setInterval(pollStatus" in script
