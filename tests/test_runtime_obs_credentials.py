"""Fix #3 (T-9l5-04) — SEGUGIO_OBS_* env credentials reach ObsWsController via build_orchestrator.

Before this fix ``build_orchestrator`` passed the hardcoded ``password=None`` to the obs factory,
so an operator who set an obs-websocket password (per docs/obs-setup.md) silently broke every cut
(the controller connected unauthenticated and all ops failed). These headless tests capture the
``(host, port, password)`` tuple the injectable ``obs_factory`` receives and assert:

  * with ``SEGUGIO_OBS_HOST``/``PORT``/``PASSWORD`` set, the exact tuple is threaded through;
  * with the env unset, the defaults ``("localhost", 4455, None)`` are used (byte-identical to the
    old behavior — no regression);
  * an EMPTY ``SEGUGIO_OBS_PASSWORD`` is normalized to ``None`` ("no password");
  * a non-integer ``SEGUGIO_OBS_PORT`` coasts to the default (never crashes startup, RBT-04).

Pure fakes for source/tracker so no heavy stack (cyndilib/obsws/cv2/ultralytics) loads; preview
is disabled via an override so no publisher is constructed either.
"""

from __future__ import annotations

from segugio.orchestrator.runtime import build_orchestrator

_OBS_ENV = ("SEGUGIO_OBS_HOST", "SEGUGIO_OBS_PORT", "SEGUGIO_OBS_PASSWORD")


class _FakeObs:
    def connect(self):  # pragma: no cover - never called (no run())
        pass

    def close(self):  # pragma: no cover
        pass


class _FakeSource:
    def start(self):  # pragma: no cover
        pass

    def stop(self):  # pragma: no cover
        pass


class _FakeTracker:
    """A .track-only fake (no .model/.update) so the loop stays on the light serial path."""


def _fake_source_factory(cameras):
    return _FakeSource()


def _fake_tracker_factory(model_path, class_index, tracker_yaml, engine_path=None, use_fp16=False):
    return _FakeTracker()


def _capturing_obs_factory(bucket):
    def _factory(host, port, password):
        bucket["args"] = (host, port, password)
        return _FakeObs()

    return _factory


def _build(cfg, tmp_path, bucket):
    """Build with fakes + a capturing obs factory; preview disabled so no publisher is built."""
    build_orchestrator(
        cfg,
        str(tmp_path),
        source_factory=_fake_source_factory,
        tracker_factory=_fake_tracker_factory,
        obs_factory=_capturing_obs_factory(bucket),
    )


def test_obs_password_env_reaches_factory(make_config, tmp_path, monkeypatch):
    """A configured SEGUGIO_OBS_HOST/PORT/PASSWORD is threaded into obs_factory verbatim."""
    monkeypatch.setenv("SEGUGIO_OBS_HOST", "obsbox")
    monkeypatch.setenv("SEGUGIO_OBS_PORT", "4499")
    monkeypatch.setenv("SEGUGIO_OBS_PASSWORD", "s3cr3t")

    cfg = make_config(overrides={"preview": {"enabled": False}})
    bucket: dict = {}
    _build(cfg, tmp_path, bucket)

    assert bucket["args"] == ("obsbox", 4499, "s3cr3t")


def test_defaults_when_env_unset(make_config, tmp_path, monkeypatch):
    """Env unset → the localhost:4455/None defaults (byte-identical to the pre-fix behavior)."""
    for var in _OBS_ENV:
        monkeypatch.delenv(var, raising=False)

    cfg = make_config(overrides={"preview": {"enabled": False}})
    bucket: dict = {}
    _build(cfg, tmp_path, bucket)

    assert bucket["args"] == ("localhost", 4455, None)


def test_empty_password_is_normalized_to_none(make_config, tmp_path, monkeypatch):
    """An empty SEGUGIO_OBS_PASSWORD means 'no password' → None (not the empty string)."""
    monkeypatch.setenv("SEGUGIO_OBS_PASSWORD", "")
    monkeypatch.delenv("SEGUGIO_OBS_HOST", raising=False)
    monkeypatch.delenv("SEGUGIO_OBS_PORT", raising=False)

    cfg = make_config(overrides={"preview": {"enabled": False}})
    bucket: dict = {}
    _build(cfg, tmp_path, bucket)

    assert bucket["args"] == ("localhost", 4455, None)


def test_non_integer_port_coasts_to_default(make_config, tmp_path, monkeypatch):
    """A garbage SEGUGIO_OBS_PORT coasts to the default 4455 — never crashes startup (RBT-04)."""
    monkeypatch.setenv("SEGUGIO_OBS_PORT", "not-a-port")
    monkeypatch.delenv("SEGUGIO_OBS_HOST", raising=False)
    monkeypatch.delenv("SEGUGIO_OBS_PASSWORD", raising=False)

    cfg = make_config(overrides={"preview": {"enabled": False}})
    bucket: dict = {}
    _build(cfg, tmp_path, bucket)

    assert bucket["args"] == ("localhost", 4455, None)
