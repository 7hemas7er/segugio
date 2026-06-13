"""The Flask operator console — a SEPARATE process that writes the opcomm atomic files.

One Italian page (``console.html``) carrying D-04's four concerns: score entry (discipline
selector + 3 per-discipline field sets), run start/stop, override (Forza/Rilascia), and a live
director-status read-back. Every POST writes an opcomm atomic file the orchestrator reads each
tick; the page polls ``GET /status`` for the reverse channel (D-11).

Crash-isolation contract (D-03 / RBT-04): this app imports ONLY Flask + ``segugio.opcomm``
(stdlib + loguru leaf) — never ultralytics/torch/cyndilib/obsws/cv2. A UI exception can never
reach the director; the only coupling is the atomic file channel. ``import segugio.ui`` stays
Flask-free because Flask is imported INSIDE :func:`create_app`, not at module top.

Run as its own process::

    python -m segugio.ui.app                    # binds 0.0.0.0:8080 (tablet over the dedicated WiFi)

The ``0.0.0.0`` bind exposes the console to anyone on the dedicated WiFi LAN. That LAN is the
trust boundary; no auth in v1 is an ACCEPTED, documented decision for a single-operator field
tool (D-02, threat T-05-05-04), NOT an oversight. It is not internet-facing.

Security at the input boundary:
  * the channel write paths are FIXED server-side (``channel_dir`` + constant filenames) — the
    operator never supplies a path (T-05-05-01 path-traversal mitigation);
  * the discipline is whitelisted to the ``Discipline`` enum; unknown → 400 (T-05-05-01);
  * a contradictory force+release command is rejected by ``OperatorCommand.__post_init__`` and
    returned as 400, never written (T-05-05-03);
  * overlay text is constrained/sanitized by the renderer (T-05-05-02).
"""

from __future__ import annotations

import os

from ..opcomm.channel import (
    read_preview,
    read_status,
    write_command,
    write_runstate,
    write_score,
)
from ..opcomm.records import Discipline, OperatorCommand, RunState, ScoreDoc
from .score_render import render_overlay_text

# The opcomm submodule's atomic text writer for the OBS read-from-file overlay (OBS-05).
from ..opcomm.atomic import atomic_write_text

__all__ = ["create_app"]

# The four operator↔system files (RESEARCH Pattern 3 — separate files, independent atomic
# swaps). Filenames are CONSTANT server-side so a crafted POST can never steer the write path.
_SCORE_FILE = "score.json"
_OVERLAY_FILE = "overlay.txt"
_RUNSTATE_FILE = "runstate.json"
_COMMAND_FILE = "command.json"
_STATUS_FILE = "status.json"

# The Phase-7 publishing channel the console SERVES (runtime.py: preview_dir = <channel_dir>/preview).
# The per-camera JPEG filename is f"cam_{cam_id}.jpg" (preview.py) — for id "cam_wide" the on-disk
# file is literally cam_cam_wide.jpg. The route ALWAYS builds the path from this FIXED prefix and a
# WHITELISTED id; the raw URL segment is never used as a filesystem path (T-05-05-01).
_PREVIEW_SUBDIR = "preview"
_PREVIEW_FILE = "preview/preview.json"

# Fields posted by the operator that are NOT score values (don't leak into ScoreDoc.fields).
_NON_SCORE_KEYS = frozenset({"discipline"})


def create_app(channel_dir: str, cam_ids=()):
    """Build the Flask operator console wired to ``channel_dir`` (the opcomm file directory).

    A factory (not a module-level ``app``) so tests inject a tmp_path dir via the Flask test
    client and the production entrypoint injects the real channel dir. The directory is created
    if absent. Flask is imported HERE (lazily) so ``import segugio.ui`` stays Flask-free.

    ``cam_ids`` is the WHITELIST of configured camera ids the preview-JPEG route serves — passed
    in as a plain arg (NEVER obtained by ``import segugio.config``, which would break the
    crash-isolation contract). The default ``()`` keeps existing single-arg callers green; with no
    ids passed, ``GET /preview/<cam>.jpg`` 404s every cam (the entrypoint passes the real ids).
    """
    from flask import Flask, abort, jsonify, render_template, request, send_file

    cam_ids = frozenset(cam_ids)

    os.makedirs(channel_dir, exist_ok=True)

    def _path(name: str) -> str:
        return os.path.join(channel_dir, name)

    app = Flask(__name__)

    @app.get("/")
    def index():
        # One Italian operator console page (selector + 3 field sets + run + override + status).
        return render_template("console.html")

    @app.post("/score")
    def post_score():
        form = request.form
        # Whitelist the discipline against the closed Enum (T-05-05-01) — unknown → 400.
        raw_discipline = form.get("discipline", Discipline.disc_tf.value)
        try:
            discipline = Discipline(raw_discipline)
        except ValueError:
            return ("disciplina sconosciuta", 400)
        # Everything else is the operator's free-form per-discipline field set (display-only).
        # WR-05: drop EMPTY values so the hidden (display:none) fieldsets of the other disciplines —
        # which FormData still serializes — do not sweep stray empty nome/timer/tempo/sct/faults
        # keys into ScoreDoc.fields, the OBS overlay render, and every score.json write.
        fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS and v.strip()}
        doc = ScoreDoc(discipline=discipline, fields=fields)
        # Write BOTH: score.json (structured, for the UI) AND overlay.txt (rendered, for OBS).
        write_score(_path(_SCORE_FILE), doc)
        atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))
        return ("", 204)

    @app.post("/run")
    def post_run():
        action = request.form.get("action", "")
        # Map the manual verb to the D-09 edge flags: START sets the lock-reset edge,
        # STOP sets the SAFE-park edge. RunState validates the action set at construction.
        try:
            run = RunState(
                action=action,
                just_started=(action == "start"),
                just_stopped=(action == "stop"),
            )
        except ValueError:
            return ("azione non valida", 400)
        write_runstate(_path(_RUNSTATE_FILE), run)
        return ("", 204)

    @app.post("/command")
    def post_command():
        # Each override button sends EITHER a force OR a release, never both (D-10). A
        # contradictory POST is rejected by OperatorCommand.__post_init__ → 400, never written
        # (T-05-05-03 — a malformed command never reaches the FSM).
        force_cam = request.form.get("force_cam") or None
        release = request.form.get("release") == "1"
        try:
            cmd = OperatorCommand(force_cam=force_cam, release=release)
        except ValueError:
            return ("comando contraddittorio: forza XOR rilascia", 400)
        write_command(_path(_COMMAND_FILE), cmd)
        return ("", 204)

    @app.get("/status")
    def get_status():
        # D-11 reverse channel — the panel polls this. read_status returns a safe default
        # (SAFE) on an absent/malformed file, never raising (RBT-04 boundary).
        status = read_status(_path(_STATUS_FILE))
        return jsonify(
            {"live_cam": status.live_cam, "reason": status.reason, "alive": status.alive}
        )

    @app.get("/preview/<cam>.jpg")
    def get_preview_jpg(cam: str):
        # T-05-05-01 path-traversal mitigation: <cam> is whitelisted against the configured ids
        # and NEVER used as a raw filesystem path. An unknown id (incl. a traversal segment that
        # is not a configured id) → 404. The on-disk filename is built from a FIXED cam_{id}.jpg
        # prefix (the Pitfall-3 mapping: id "cam_wide" → file cam_cam_wide.jpg).
        if cam not in cam_ids:
            abort(404)
        path = _path(os.path.join(_PREVIEW_SUBDIR, f"cam_{cam}.jpg"))
        if not os.path.exists(path):
            # Publisher hasn't written this frame yet → 404 (the browser shows its placeholder).
            abort(404)
        resp = send_file(path, mimetype="image/jpeg")
        # Belt-and-suspenders with the client-side ?t=<gen> cache-bust — never cache a live frame.
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/preview")
    def get_preview():
        # The off-tick "why" sidecar (PRV-02). read_preview is a safe-default never-raise reader
        # (RBT-04): an absent/torn/malformed file → a default PreviewDoc, never an exception.
        doc = read_preview(_path(_PREVIEW_FILE))
        return jsonify(
            {
                "gen": doc.gen,
                "tick": doc.tick,
                "auto_candidate": doc.auto_candidate,
                "cams": doc.cams,
            }
        )

    return app


if __name__ == "__main__":  # pragma: no cover - the production entrypoint
    # The channel dir defaults to ./opcomm next to the cwd; override via SEGUGIO_OPCOMM_DIR.
    _dir = os.environ.get("SEGUGIO_OPCOMM_DIR", os.path.join(os.getcwd(), "opcomm"))
    # Resolve the cam-id whitelist HERE (inside the entrypoint) so no config import leaks to the
    # module top and the crash-isolation guard stays green. Prefer an explicit comma-separated env
    # (SEGUGIO_CAM_IDS); fall back to loading the config only if a path is given. If neither is
    # set, the four default rig ids keep the preview routes serving out of the box.
    _cam_env = os.environ.get("SEGUGIO_CAM_IDS", "").strip()
    if _cam_env:
        _cam_ids = [c.strip() for c in _cam_env.split(",") if c.strip()]
    else:
        _cfg_path = os.environ.get("SEGUGIO_CONFIG", "").strip()
        if _cfg_path:
            from ..config.loader import load_config  # lazy: config import stays out of module top

            _cam_ids = [cam.id for cam in load_config(_cfg_path).cameras]
        else:
            _cam_ids = ["cam_wide", "cam_long", "cam_low", "cam_handler"]

    app = create_app(_dir, cam_ids=_cam_ids)
    try:
        # OPTIONAL deploy extra (`pip install segugio[console]`). The import stays INSIDE the
        # entrypoint so the crash-isolation guard passes whether or not waitress is installed.
        from waitress import serve

        serve(app, host="0.0.0.0", port=8080)
    except ImportError:
        # threaded=True is the HARD UXT-02/D-08 safety control on the dev-server fallback: a
        # preview GET can never starve the lone WSGI worker so the /command override stalls.
        app.run(host="0.0.0.0", port=8080, threaded=True)
