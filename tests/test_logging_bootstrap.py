"""Fix #4 (T-9l5-06) — configure_logging() is called at BOTH entry points + writes a rotating file.

configure_logging() had ZERO call sites, so both processes logged stderr-only with no post-mortem
file — a live event left nothing diagnosable. These tests assert:

  (a) configure_logging(log_dir=...) writes a rotating segugio.log that captures a logged line;
  (b) `python -m segugio` (segugio.__main__.main) calls configure_logging with log_dir == the
      opcomm dir, and the console run_console() entrypoint calls configure_logging too.

Pure-fake / monkeypatched so no orchestrator or server actually starts, and the crash-isolation
import gate (test_imports.py) is unaffected (segugio.logging stays a loguru+stdlib leaf).
"""

from __future__ import annotations

import segugio.logging as seglog


def test_rotating_file_sink_writes(tmp_path):
    """configure_logging(log_dir=...) installs a rotating segugio.log that captures a log line."""
    from loguru import logger

    try:
        seglog.configure_logging(log_dir=str(tmp_path), force=True)
        logger.info("bootstrap-probe")
        # enqueue=True → the file sink writes asynchronously; complete() flushes the queue so the
        # assertion is deterministic (not a race on the background writer thread).
        logger.complete()

        log_file = tmp_path / "segugio.log"
        assert log_file.exists(), "configure_logging(log_dir=...) must write segugio.log"
        assert "bootstrap-probe" in log_file.read_text(encoding="utf-8")
    finally:
        # Reset sinks so this test's file handler does not leak into other tests.
        seglog.configure_logging(force=True)


def test_file_sink_not_stacked_on_repeat(tmp_path):
    """Repeated configure_logging(log_dir=...) calls do NOT stack duplicate file handlers."""
    from loguru import logger

    try:
        seglog.configure_logging(log_dir=str(tmp_path), force=True)
        first_id = seglog._FILE_SINK_ID
        # A second NON-force call with the same log_dir must be a no-op for the file sink.
        seglog.configure_logging(log_dir=str(tmp_path))
        assert seglog._FILE_SINK_ID == first_id, "the file sink must not be re-added (no duplicate)"

        logger.info("once-only-line")
        logger.complete()
        text = (tmp_path / "segugio.log").read_text(encoding="utf-8")
        # Exactly one file handler → the line appears exactly once (a stacked duplicate would double it).
        assert text.count("once-only-line") == 1
    finally:
        seglog.configure_logging(force=True)


def test_main_entrypoint_calls_configure_logging(tmp_path, monkeypatch):
    """`python -m segugio` calls configure_logging(log_dir=<opcomm dir>) before running."""
    import segugio.__main__ as entry

    recorded: dict = {}

    def _recording_configure(level="INFO", *, force=False, log_dir=None):
        recorded["log_dir"] = log_dir

    # The in-body `from .logging import configure_logging` fetches the attribute at call time, so
    # patching segugio.logging.configure_logging is what main() picks up.
    monkeypatch.setattr(seglog, "configure_logging", _recording_configure)

    # Neutralize the heavy build + run so main() does not actually start the director.
    class _FakeOrch:
        def run(self, rate):  # pragma: no cover - trivial no-op
            pass

        def shutdown(self):  # pragma: no cover
            pass

    monkeypatch.setattr(entry, "build_orchestrator", lambda cfg, opcomm_dir: _FakeOrch())

    opcomm = tmp_path / "opcomm"
    rc = entry.main(["config.example.yaml", "--opcomm-dir", str(opcomm)])
    assert rc == 0
    assert recorded.get("log_dir") == str(opcomm), (
        f"main() must configure logging with the opcomm dir, got {recorded}"
    )


def test_run_console_calls_configure_logging(tmp_path, monkeypatch):
    """The console run_console() entrypoint calls configure_logging before serving."""
    import segugio.ui.app as app_mod

    recorded: dict = {}

    def _recording_configure(level="INFO", *, force=False, log_dir=None):
        recorded["log_dir"] = log_dir

    monkeypatch.setattr(seglog, "configure_logging", _recording_configure)
    monkeypatch.setenv("SEGUGIO_OPCOMM_DIR", str(tmp_path / "opcomm"))
    # No cam/config env → the default rig ids branch (no config import).
    monkeypatch.delenv("SEGUGIO_CAM_IDS", raising=False)
    monkeypatch.delenv("SEGUGIO_CONFIG", raising=False)

    # create_app + the server are no-ops so run_console() neither builds the real app nor binds 8080.
    class _FakeApp:
        def run(self, *a, **k):  # pragma: no cover - dev-server fallback, not reached when waitress present
            pass

    monkeypatch.setattr(app_mod, "create_app", lambda *a, **k: _FakeApp())
    # waitress is installed in this env → run_console() calls `serve`; stub it so nothing binds.
    import waitress

    monkeypatch.setattr(waitress, "serve", lambda app, host=None, port=None: None)

    app_mod.run_console()

    assert recorded.get("log_dir") == str(tmp_path / "opcomm"), (
        f"run_console() must configure logging with the opcomm dir, got {recorded}"
    )
