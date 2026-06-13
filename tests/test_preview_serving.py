"""MVW-01/02/03 — preview serving routes (GET /preview/<cam>.jpg + GET /preview).

The Phase-8 console SERVES the Phase-7 publishing channel: a whitelisted ``send_file`` route
for the per-camera JPEG and a thin ``read_preview`` JSON wrapper. All via the Flask test client
against a tmp_path opcomm dir (the ``preview_channel`` fixture). The whitelist (cam id against
``cam_ids``) + the FIXED ``cam_{id}.jpg`` filename are the T-05-05-01 path-traversal mitigation —
``<cam>`` is NEVER used as a raw filesystem path.

Test selectors: ``-k serve`` / ``-k whitelist`` / ``-k live_contract`` / ``-k freshness``.
"""

from __future__ import annotations

import pytest

from segugio.opcomm.channel import write_preview, write_status
from segugio.opcomm.records import DirectorStatus, PreviewDoc


@pytest.fixture
def client(preview_channel):
    from segugio.ui.app import create_app

    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    app.config.update(TESTING=True)
    return app.test_client(), preview_channel


# --- serve (MVW-01) ---------------------------------------------------------- #


def test_serve_preview_jpg_returns_bytes(client):
    """GET /preview/cam_wide.jpg → 200 image/jpeg with the EXACT bytes at cam_cam_wide.jpg."""
    c, ch = client
    resp = c.get("/preview/cam_wide.jpg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    # The cam_{id}.jpg mapping: id "cam_wide" → file cam_cam_wide.jpg (Pitfall-3).
    expected = (ch["preview_dir"] / "cam_cam_wide.jpg").read_bytes()
    assert resp.data == expected


def test_serve_preview_jpg_no_store_cache(client):
    """The JPEG response is marked no-store (belt-and-suspenders with the ?t=<gen> cache-bust)."""
    c, _ = client
    resp = c.get("/preview/cam_wide.jpg")
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_serve_preview_sidecar_json(client):
    """GET /preview → the sidecar JSON with keys gen/tick/auto_candidate/cams."""
    c, _ = client
    resp = c.get("/preview")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data) >= {"gen", "tick", "auto_candidate", "cams"}
    assert data["gen"] == 1
    assert data["tick"] == 1
    assert data["auto_candidate"] == "cam_wide"
    assert "cam_wide" in data["cams"]


# --- cuts ring (MVW-05) ------------------------------------------------------ #


def test_serve_preview_sidecar_exposes_cuts(client):
    """GET /preview exposes the recent-cuts ring under `cuts` (the 09-04 switch-history strip).

    Write a PreviewDoc with a non-empty cuts tuple via write_preview and assert GET /preview
    returns those exact cut dicts under the `cuts` key, newest-last as written (MVW-05 data
    source). The existing gen/tick/auto_candidate/cams keys stay present (no Phase-8 regression).
    """
    c, ch = client
    cuts = (
        {"tick": 10, "from": "SAFE", "to": "cam_wide", "reason": "auto"},
        {"tick": 25, "from": "cam_wide", "to": "cam_long", "reason": "auto"},
    )
    write_preview(
        str(ch["preview"]),
        PreviewDoc(
            tick=30,
            gen=4,
            auto_candidate="cam_long",
            cams={"cam_wide": {}, "cam_long": {}},
            cuts=cuts,
        ),
    )
    resp = c.get("/preview")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "cuts" in data
    assert isinstance(data["cuts"], list)
    # The returned cut dicts equal the written ring, in order (newest-last).
    assert data["cuts"] == [dict(c) for c in cuts]
    # No regression to the Phase-8 contract keys.
    assert set(data) >= {"gen", "tick", "auto_candidate", "cams", "cuts"}


def test_serve_preview_cuts_empty_when_absent(client):
    """With no preview file, `cuts` is `[]` and the route returns 200 (read_preview safe-default)."""
    c, ch = client
    # Remove the preview.json the fixture wrote → read_preview safe-defaults to PreviewDoc().
    ch["preview"].unlink()
    resp = c.get("/preview")
    assert resp.status_code == 200
    assert resp.get_json()["cuts"] == []


# --- whitelist (T-05-05-01) -------------------------------------------------- #


def test_whitelist_unknown_cam_404(client):
    """An id NOT in cam_ids → 404 (the whitelist is the path-traversal mitigation)."""
    c, _ = client
    resp = c.get("/preview/cam_bogus.jpg")
    assert resp.status_code == 404


def test_whitelist_path_traversal_404(client):
    """A path-traversal segment → 404 and status.json is never read off disk."""
    c, ch = client
    # Write a status file OUTSIDE the preview dir so a traversal would leak it if mishandled.
    write_status(str(ch["status"]), DirectorStatus(live_cam="cam_long"))
    # Raw '../status' and an encoded '..%2fstatus' variant — both must 404, never serve status.
    for path in ("/preview/../status.jpg", "/preview/..%2fstatus.jpg"):
        resp = c.get(path)
        assert resp.status_code == 404, path
        # The status.json bytes are never served through the JPEG route.
        assert b"cam_long" not in resp.data


def test_serve_not_yet_written_cam_404(client):
    """A whitelisted id with no file on disk yet → 404 (publisher not yet written)."""
    c, ch = client
    # cam_long is whitelisted; remove its file to simulate "publisher not yet written".
    (ch["preview_dir"] / "cam_cam_long.jpg").unlink()
    resp = c.get("/preview/cam_long.jpg")
    assert resp.status_code == 404


# --- live_contract (MVW-02) -------------------------------------------------- #


def test_live_contract(client):
    """GET /status exposes live_cam+alive AND GET /preview exposes cams keyed by the same ids."""
    c, ch = client
    write_status(
        str(ch["status"]),
        DirectorStatus(
            live_cam="cam_wide",
            reason="auto",
            alive={"cam_wide": True, "cam_long": False},
        ),
    )
    status = c.get("/status").get_json()
    preview = c.get("/preview").get_json()
    # The LIVE/MORTO data contract: /status carries live_cam + alive; /preview carries cams.
    assert status["live_cam"] == "cam_wide"
    assert set(status["alive"]) == {"cam_wide", "cam_long"}
    assert set(preview["cams"]) == {"cam_wide", "cam_long"}
    # The live_cam id appears in the preview cams set (the client can mark that tile LIVE).
    assert status["live_cam"] in preview["cams"]


# --- freshness (MVW-03) ------------------------------------------------------ #


def test_freshness_gen_advances(client):
    """GET /preview gen advances on a new write_preview, stable when unchanged (MVW-3 signal)."""
    c, ch = client
    assert c.get("/preview").get_json()["gen"] == 1
    # A stable read returns the same gen.
    assert c.get("/preview").get_json()["gen"] == 1
    # The publisher bumps gen on a new frame.
    write_preview(
        str(ch["preview"]),
        PreviewDoc(tick=2, gen=2, auto_candidate="cam_long", cams={"cam_wide": {}, "cam_long": {}}),
    )
    assert c.get("/preview").get_json()["gen"] == 2
    write_preview(
        str(ch["preview"]),
        PreviewDoc(tick=3, gen=3, auto_candidate="cam_long", cams={"cam_wide": {}, "cam_long": {}}),
    )
    assert c.get("/preview").get_json()["gen"] == 3
