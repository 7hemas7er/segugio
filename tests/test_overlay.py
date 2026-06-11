"""OBS-05 — overlay write hits the read-from-file path + set_input_settings fallback.

Behavior (05-03):
  - PRIMARY: the rendered overlay string is written atomically to the read-from-file
    target (atomic_write_text) — OBS's read-from-file text source picks it up. No OBS
    request is needed for the steady-state overlay.
  - FALLBACK: the one-shot path calls set_input_settings(input_name, {"text": ...}) with
    overlay=True; the text input KIND is never hardcoded — only the generic "text" field
    is set (Pitfall 5).
"""

from __future__ import annotations

from segugio.obs.obsws_controller import ObsWsController
from segugio.opcomm.atomic import atomic_write_text


class _RecordingReq:
    """A ReqClient double recording set_input_settings calls."""

    def __init__(self) -> None:
        self.input_settings: list[tuple] = []

    def get_scene_item_id(self, scene, source):
        raise AssertionError("not used")

    def set_input_settings(self, input_name, settings, overlay):
        self.input_settings.append((input_name, settings, overlay))

    def disconnect(self):
        pass


class _Evt:
    class _CB:
        def register(self, fn):
            pass

    def __init__(self) -> None:
        self.callback = _Evt._CB()

    def disconnect(self):
        pass


def test_overlay_writes_read_from_file(file_channel):
    """PRIMARY path: the overlay string is written atomically; OBS reads it from file."""
    overlay_path = file_channel["overlay"]
    line = "Cane: Rex — Punti: 42"  # Italian overlay line (UTF-8)

    atomic_write_text(str(overlay_path), line)

    # OBS's read-from-file source would read exactly this — no OBS request involved.
    assert overlay_path.read_text(encoding="utf-8") == line
    # a partial/empty read never happens (atomic): the file is fully present.
    assert overlay_path.exists()


def test_overlay_set_input_settings_fallback():
    """FALLBACK path: a one-shot hits set_input_settings(input, {"text": ...}, overlay=True)."""
    req = _RecordingReq()

    def factory(host, port, password):
        return req, _Evt()

    ctrl = ObsWsController(client_factory=factory)
    ctrl.connect()

    ctrl.set_overlay_text("Score Text", "GO")

    assert req.input_settings, "set_overlay_text did not call set_input_settings"
    input_name, settings, overlay = req.input_settings[-1]
    assert input_name == "Score Text"
    # only the generic "text" field is set — the input KIND is never referenced (Pitfall 5)
    assert settings == {"text": "GO"}
    assert overlay is True
