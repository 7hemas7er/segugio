"""Fix #7 (SECURITY, T-9l5-01/02) — mutating routes require the shared secret + reject foreign Origin.

Flask-test-client checks (no server). With SEGUGIO_CONSOLE_SECRET set (here injected via the
``console_secret`` arg), the STATE-CHANGING routes (/score, /run, /command) require an
``Authorization: Bearer <secret>`` (401 without/wrong) AND a same-Origin check (403 on a foreign
Origin). With no secret configured the routes stay OPEN (back-compat with the ~80 existing UI
tests). The bind host is overridable via SEGUGIO_CONSOLE_HOST (default 0.0.0.0).
"""

from __future__ import annotations

import pytest

from segugio.ui.app import _bind_host, create_app

# The three mutating routes + a VALID body for each (so a passing gate yields the route's 204).
_VALID = {
    "/score": ("json", {"discipline": "disc_tf", "throws": [{"zone": 4, "midair": "on", "corridor": "false"}]}),
    "/run": ("data", {"action": "start"}),
    "/command": ("data", {"force_cam": "cam_wide"}),
}
_ROUTES = list(_VALID.keys())


@pytest.fixture
def secured_client(file_channel):
    """A test client whose console_secret is 'topsecret' (arg wins over the env)."""
    app = create_app(str(file_channel["dir"]), console_secret="topsecret")
    app.config.update(TESTING=True)
    return app.test_client()


def _post(client, route, headers=None):
    kind, body = _VALID[route]
    kwargs = {"headers": headers or {}}
    if kind == "json":
        kwargs["json"] = body
    else:
        kwargs["data"] = body
    return client.post(route, **kwargs)


@pytest.mark.parametrize("route", _ROUTES)
def test_missing_secret_is_401(secured_client, route):
    """A mutating POST with NO Authorization is rejected (401) when the secret is configured."""
    assert _post(secured_client, route).status_code == 401


@pytest.mark.parametrize("route", _ROUTES)
def test_wrong_secret_is_401(secured_client, route):
    """A wrong Bearer secret is rejected (401)."""
    assert _post(secured_client, route, {"Authorization": "Bearer wrong"}).status_code == 401


@pytest.mark.parametrize("route", _ROUTES)
def test_correct_bearer_no_origin_passes(secured_client, route):
    """The correct Bearer (no Origin header) reaches the route → 204 (valid body)."""
    resp = _post(secured_client, route, {"Authorization": "Bearer topsecret"})
    assert resp.status_code != 401
    assert resp.status_code == 204, resp.get_data(as_text=True)


@pytest.mark.parametrize("route", _ROUTES)
def test_correct_bearer_matching_origin_passes(secured_client, route):
    """The correct Bearer + a same-Origin (localhost) header reaches the route → 204."""
    resp = _post(
        secured_client, route,
        {"Authorization": "Bearer topsecret", "Origin": "http://localhost"},
    )
    assert resp.status_code == 204, resp.get_data(as_text=True)


@pytest.mark.parametrize("route", _ROUTES)
def test_foreign_origin_is_403(secured_client, route):
    """A foreign Origin is rejected (403) even WITH the correct Bearer (CSRF defense)."""
    resp = _post(
        secured_client, route,
        {"Authorization": "Bearer topsecret", "Origin": "http://evil.example"},
    )
    assert resp.status_code == 403


def test_unconfigured_routes_stay_open(file_channel, monkeypatch):
    """With NO secret configured (env unset), a mutating POST is open (204) — back-compat."""
    monkeypatch.delenv("SEGUGIO_CONSOLE_SECRET", raising=False)
    app = create_app(str(file_channel["dir"]))  # console_secret=None → reads the (unset) env
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post("/run", data={"action": "start"})
    assert resp.status_code == 204

    # A foreign Origin is also fine when no secret is configured (the gate is a no-op).
    resp2 = client.post("/run", data={"action": "stop"}, headers={"Origin": "http://evil.example"})
    assert resp2.status_code == 204


def test_read_routes_stay_open_when_secured(secured_client):
    """GET/read routes stay open even with the secret set (the accepted trusted-LAN read posture)."""
    assert secured_client.get("/status").status_code == 200
    assert secured_client.get("/overlay-json").status_code == 200


def test_console_page_inlines_secret_for_own_posts(file_channel):
    """The console page carries the secret as a JS constant so its own POSTs authenticate."""
    app = create_app(str(file_channel["dir"]), console_secret="topsecret", cam_ids=["cam_wide"])
    app.config.update(TESTING=True)
    html = app.test_client().get("/").get_data(as_text=True)
    assert "__CONSOLE_SECRET" in html
    assert "topsecret" in html


def test_bind_host_default_and_override(monkeypatch):
    """_bind_host() defaults to 0.0.0.0 and honours SEGUGIO_CONSOLE_HOST."""
    monkeypatch.delenv("SEGUGIO_CONSOLE_HOST", raising=False)
    assert _bind_host() == "0.0.0.0"
    monkeypatch.setenv("SEGUGIO_CONSOLE_HOST", "127.0.0.1")
    assert _bind_host() == "127.0.0.1"
