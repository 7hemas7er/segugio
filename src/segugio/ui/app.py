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
import threading
import time

from ..opcomm.channel import (
    read_overlay_run,
    read_preview,
    read_score,
    read_status,
    write_command,
    write_overlay_run,
    write_runstate,
    write_score,
)
from ..opcomm.records import (
    Discipline,
    OperatorCommand,
    OverlayRunDoc,
    RunState,
    ScoreDoc,
)
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

# The Phase-10 console-owned overlay run-state sidecar (running/started_at/gen). A SEPARATE
# file from runstate.json — the director reads runstate.json every tick and NEVER this sidecar
# (the HARD D-03 byte-for-byte invariant). /run + /score side-write it; /overlay-json reads it.
_OVERLAY_RUN_FILE = "overlay_run.json"

# The Phase-7 publishing channel the console SERVES (runtime.py: preview_dir = <channel_dir>/preview).
# The per-camera JPEG filename is f"cam_{cam_id}.jpg" (preview.py) — for id "cam_wide" the on-disk
# file is literally cam_cam_wide.jpg. The route ALWAYS builds the path from this FIXED prefix and a
# WHITELISTED id; the raw URL segment is never used as a filesystem path (T-05-05-01).
_PREVIEW_SUBDIR = "preview"
_PREVIEW_FILE = "preview/preview.json"

def _profile_to_json(profile) -> dict:
    """Serialise a plain ``score_calc.ScoringProfile`` into a JSON-safe dict (D-07 / T-16-10).

    EVERY numeric is emitted as a decimal STRING (``str(Decimal)`` → ``"5"``, ``"0.5"``, ``"40"`` —
    never the float ``5.0``/``0.5``) so the inlined ``score-cfg`` blob round-trips byte-exact into
    ``score-calc.js``'s BigInt-Decimal helper; a ``Number``-coerced ``0.1+0.2`` would drift the
    advisory total away from the Python ``Decimal`` authority (Pitfall 1 / D-09). Mirrors the shape
    of ``tests/_score_fixtures.PROFILE_JSON``. Pure stdlib — ``str()`` on a ``Decimal`` is
    crash-isolation safe (no config/numpy import, RBT-08).

      * ``zones``          → ``[[band, str(points)], ...]`` (band stays the int selector value)
      * ``bonuses``        → ``[[key, str(value)], ...]``
      * ``freestyle_cats`` → ``[[name, str(min), str(max), str(inc)], ...]``
      * ``per_throw_cap``  → ``str(...)`` | ``None``
      * ``freestyle_max``  → ``str(...)``
      * ``count_best_n``   → ``int`` | ``None``  (a count, not a Decimal)
      * ``agility_model`` / ``elimination_sentinel`` / ``units`` → ``str``
    """
    return {
        "units": str(profile.units),
        "zones": [[band, str(points)] for band, points in profile.zones],
        "bonuses": [[key, str(value)] for key, value in profile.bonuses],
        "per_throw_cap": None if profile.per_throw_cap is None else str(profile.per_throw_cap),
        "count_best_n": profile.count_best_n,
        "freestyle_cats": [
            [name, str(cmin), str(cmax), str(inc)]
            for name, cmin, cmax, inc in profile.freestyle_cats
        ],
        "freestyle_max": str(profile.freestyle_max),
        "agility_model": str(profile.agility_model),
        "time_fault_rate": str(profile.time_fault_rate),
        "fault_value": str(profile.fault_value),
        "elimination_sentinel": str(profile.elimination_sentinel),
    }


def _disciplines_for_sport(sport: str) -> list:
    """The valid-discipline list the ``/score-entry`` page offers (D-06).

    Derived from the configured sport (the active scoring profile), NOT a free 3-way selector:
    a disc-dog config offers Toss & Fetch + Freestyle (both served by ``DiscDogProfile.scoring`` —
    zones drive T&F, ``freestyle_cats`` drive Freestyle); an agility config offers Agility only
    (``AgilityProfile.scoring``). The active profile therefore always matches the selected
    discipline — no fallback profile, no "which profile for which discipline" ambiguity.
    """
    return ["disc_tf", "disc_freestyle"] if sport == "disc_dog" else ["agility"]


def _parse_structured_inputs(discipline, raw, is_json: bool) -> dict:
    """Build the RAW per-discipline dict ``score_calc.validate``/``compute`` consume (D-08).

    JSON bodies deliver native types (``throws`` is a list of ``{zone, midair, corridor}`` dicts,
    ``eliminated`` a bool); urlencoded forms deliver strings. The dict is RAW input — the strict
    flag/time/number parsing happens inside ``score_calc`` (CR-01 truthiness, mm:ss(.cc), Decimal),
    never here, so the server stays the single validation authority.
    """
    fields: dict = {}
    if discipline == Discipline.disc_tf:
        throws = raw.get("throws")
        if throws is None and not is_json:
            throws = []
        fields["throws"] = throws if throws is not None else []
    elif discipline == Discipline.disc_freestyle:
        # Each freestyle category value + the optional manual adjustment + the routine name.
        for key in ("team", "dog", "player", "catch", "adjustment", "nome", "timer"):
            if key in raw:
                fields[key] = raw.get(key)
    elif discipline == Discipline.agility:
        for key in (
            "tempo",
            "sct",
            "course_faults",
            "course_deductions",
            "eliminated",
        ):
            if key in raw:
                fields[key] = raw.get(key)
    return fields


# Console-palette branding defaults (D-06) — mirrored from OverlayParams so the /overlay route
# always renders a valid page even when a caller passes no overlay_cfg. Kept here as a plain dict
# (NOT imported from segugio.config) so the crash-isolation allowlist holds: the console never
# imports the config models at module top.
_OVERLAY_CFG_DEFAULTS = {
    "freestyle_duration_s": 120,
    "event_name": "",
    "logo_path": "",
    "theme_accent": "#34D399",
    "theme_plate": "#14161a",
    "theme_text": "#E6E9EF",
}


def create_app(channel_dir: str, cam_ids=(), overlay_cfg=None, profile=None, sport="disc_dog"):
    """Build the Flask operator console wired to ``channel_dir`` (the opcomm file directory).

    A factory (not a module-level ``app``) so tests inject a tmp_path dir via the Flask test
    client and the production entrypoint injects the real channel dir. The directory is created
    if absent. Flask is imported HERE (lazily) so ``import segugio.ui`` stays Flask-free.

    ``cam_ids`` is the WHITELIST of configured camera ids the preview-JPEG route serves — passed
    in as a plain arg (NEVER obtained by ``import segugio.config``, which would break the
    crash-isolation contract). The default ``()`` keeps existing single-arg callers green; with no
    ids passed, ``GET /preview/<cam>.jpg`` 404s every cam (the entrypoint passes the real ids).

    ``overlay_cfg`` is the static branding the ``GET /overlay`` host page renders — a plain dict
    (``freestyle_duration_s`` + ``event_name`` + ``logo_path`` + the three theme color strings),
    resolved by the entrypoint EXACTLY like ``cam_ids`` (NEVER ``import segugio.config`` at module
    top — Pitfall 3 / crash-isolation). ``None`` → the console-palette defaults so a caller that
    passes nothing still renders a valid page; any keys present override the defaults. This is
    STATIC config (D-07): it is injected at render time and does NOT enter the ``/overlay-json``
    poll payload.

    ``profile`` is the active scoring :class:`~segugio.ui.score_calc.ScoringProfile` the
    authoritative ``POST /score`` validates + recomputes against (Phase 16 / SCC-01). It arrives as
    a plain stdlib dataclass — NEVER ``import segugio.config`` here (the heavy config layer adapts
    its pydantic profile INTO this plain shape and injects it, mirroring ``cam_ids``/``overlay_cfg``
    — crash-isolation / Pitfall 3). ``None`` defaults to the pinned ``CSEN_DISC_PROFILE`` so every
    existing single-/triple-arg caller (and the legacy console form) stays green. ``sport`` selects
    the valid-discipline list for the (Plan-02) ``/score-entry`` page (``disc_dog`` →
    Toss&Fetch + Freestyle; ``agility`` → Agility only, D-06); it is inert for the route itself.
    """
    from flask import (
        Flask,
        abort,
        jsonify,
        make_response,
        render_template,
        request,
        send_file,
    )

    # Lazy/in-factory — score_calc is stdlib-only (no Flask, no config, no numpy), so this stays
    # inside the crash-isolation allowlist (RBT-08 / Pitfall 1). The authoritative POST /score
    # validates + recomputes against this profile; default is the pinned CSEN 2026 disc profile.
    from . import score_calc

    profile = profile or score_calc.CSEN_DISC_PROFILE

    # The /score-entry injection blob (D-07): the active sport, its valid-discipline list (D-06),
    # and the profile as decimal STRINGS (T-16-10). Built ONCE at factory time (static config —
    # like cam_ids/overlay_cfg) and inlined into the thin host via `score_cfg | tojson`. The
    # component reads it with JSON.parse(#score-cfg.textContent) and renders the fields from it.
    _score_cfg = {
        "sport": sport,
        "disciplines": _disciplines_for_sport(sport),
        "profile": _profile_to_json(profile),
    }

    cam_ids = frozenset(cam_ids)
    # Fold the caller's overlay_cfg over the console-palette defaults so the template never sees an
    # undefined branding var (a partial dict is fine — missing keys fall back to the defaults).
    overlay_cfg = {**_OVERLAY_CFG_DEFAULTS, **(overlay_cfg or {})}

    os.makedirs(channel_dir, exist_ok=True)

    def _path(name: str) -> str:
        return os.path.join(channel_dir, name)

    # D-02: seed the monotonic gen from the persisted overlay_run.json at build time — NEVER
    # reset to 0. A fresh create_app over a dir with gen=7 on disk continues from 7, so a console
    # restart re-anchors the Phase-11 freestyle timer (the started_at on disk also survives). The
    # read goes through the never-raise read_overlay_run boundary, so an absent/torn file → gen 0.
    # WR-03: seed running/started_at alongside gen from the persisted doc so /score gen-bumps
    # re-persist the run state from authoritative IN-MEMORY state, never from a disk re-read that
    # a momentary torn/absent file could collapse to the default (silently flipping a live run to
    # running=False/started_at=None). The seed read still goes through the never-raise boundary.
    _seed = read_overlay_run(_path(_OVERLAY_RUN_FILE))
    _state = {"gen": _seed.gen, "running": _seed.running, "started_at": _seed.started_at}
    # The console serves multi-threaded (entrypoint: threaded=True / waitress) — guard the
    # read-modify-write gen bump with a Lock (the PreviewPublisher gen-bump precedent).
    _gen_lock = threading.Lock()

    def _bump_overlay_run(running: bool, started_at) -> None:
        # Run edge (start/stop): bump gen and persist the new running/started_at. started_at is
        # a wall-clock time.time() epoch on START (never time.monotonic() — it must be comparable
        # to the client's Date.now(), Pitfall 3) and None on STOP.
        with _gen_lock:
            _state["gen"] += 1
            # WR-03: this run edge is the source of truth for running/started_at — cache it in
            # memory so a subsequent /score gen-bump preserves it without a disk re-read.
            _state["running"] = running
            _state["started_at"] = started_at
            write_overlay_run(
                _path(_OVERLAY_RUN_FILE),
                OverlayRunDoc(running=running, started_at=started_at, gen=_state["gen"]),
            )

    def _bump_score_gen() -> None:
        # /score is NOT a run edge (Open Q1): advance gen only, PRESERVING the current
        # running/started_at from authoritative in-memory state (WR-03). A disk re-read here could
        # momentarily default a live run to running=False/started_at=None on a torn/absent file —
        # a wrong, data-losing flip — so only the gen field changes; the run state comes from memory.
        with _gen_lock:
            _state["gen"] += 1
            write_overlay_run(
                _path(_OVERLAY_RUN_FILE),
                OverlayRunDoc(
                    running=_state["running"],
                    started_at=_state["started_at"],
                    gen=_state["gen"],
                ),
            )

    app = Flask(__name__)

    @app.get("/")
    def index():
        # One Italian operator console page (selector + 3 field sets + run + override + status).
        # Render the multiview tiles, force buttons, and the JS CAMS list from the SAME configured
        # whitelist the preview-JPEG route honours (WR-01) so a non-default rig is fully wired — the
        # cam_ids arg is no longer half-honoured (route only); the page derives its ids from it too.
        return render_template("console.html", cam_ids=sorted(cam_ids))

    @app.get("/score-entry")
    def score_entry():
        # SCE-01/02 (Plan 16-02): the dedicated full-screen score-entry page — a THIN Jinja host
        # that inlines the static `score_cfg` blob (decimal strings, D-06 discipline list) and
        # mounts the ONE shared `score-entry.js` component into #score-entry-root. The page carries
        # NO <input>/calc logic of its own (the component builds every field from the injected
        # profile); the same mount(root, cfg) module is re-mounted in the P17 console modal so drift
        # is structurally impossible (the SCV-02 one-renderer-two-mounts lesson applied to a form).
        return render_template("score-entry.html", score_cfg=_score_cfg)

    def _write_score_doc(doc) -> None:
        # The ONE write path: score.json (structured, for the UI) AND overlay.txt (rendered, for
        # OBS), then a gen-bump (NOT a run edge — running/started_at preserved, WR-03/Open Q1).
        write_score(_path(_SCORE_FILE), doc)
        atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))
        _bump_score_gen()

    @app.post("/score")
    def post_score():
        # Phase 16 (SCC-01 / D-08): POST /score is the SOLE authority. A JSON body carries the
        # structured RAW inputs (throws[] for T&F, the 4 categories + adjustment for Freestyle,
        # time/SCT/faults-or-deductions + elimination for agility); the server validates RAW input
        # FIRST and recomputes the total in Python (Decimal) before writing. The client can never
        # air a client-computed total.
        json_body = request.get_json(silent=True)
        # CR-01: get_json(silent=True) returns whatever the body parsed to — a list/int/bool/str
        # for a non-object JSON body (e.g. [1,2,3], 42, true, "x"), all of which are non-None. Use
        # isinstance(..., dict) so a non-object JSON body is NOT treated as a structured body (which
        # would then crash on raw.get(...)); it falls through to the form path (an empty
        # ImmutableMultiDict), which the authoritative parser handles as empty inputs → validate
        # returns errors → 400, honouring the validate→400/no-crash contract ("nessun crash
        # ammesso") instead of raising an unhandled 500.
        is_json = isinstance(json_body, dict)
        raw = json_body if is_json else request.form

        # Whitelist the discipline against the closed Enum (T-05-05-01 / T-16-02) — unknown → 400.
        raw_discipline = raw.get("discipline", Discipline.disc_tf.value)
        try:
            discipline = Discipline(raw_discipline)
        except ValueError:
            return ("disciplina sconosciuta", 400)

        # AUTHORITATIVE path (SCC-01): the SOLE write path (the legacy urlencoded display-only
        # back-compat branch was retired in P17 once the console #form-score was removed — Open Q1
        # (a) / D-11; no producer posts the flat shape anymore). validate-BEFORE-write → 400 + write
        # NOTHING on any error
        # (prev on-air score.json/overlay.txt stays byte-identical, D-05 / T-16-05) → Decimal
        # recompute → atomic write.
        fields = _parse_structured_inputs(discipline, raw, is_json)
        errors = score_calc.validate(discipline, fields, profile)
        if errors:
            return (jsonify({"errors": errors}), 400)
        computed = score_calc.compute(discipline, fields, profile)
        _write_score_doc(ScoreDoc(discipline=discipline, fields=computed))
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
        # NEW (D-03): the overlay_run side-write lands STRICTLY AFTER the byte-for-byte-unchanged
        # write_runstate above (the director reads runstate.json every tick — never reordered or
        # consolidated). started_at uses the wall clock so Phase 11 can offset-cancel skew.
        if action == "start":
            _bump_overlay_run(running=True, started_at=time.time())
        else:  # action == "stop"
            _bump_overlay_run(running=False, started_at=None)
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

    @app.get("/overlay-json")
    def get_overlay_json():
        # OVD-01 — the overlay's whole data contract over the existing publish-and-render channel.
        # Assemble EXCLUSIVELY from the two never-raise readers + time.time(): NEVER json.load/open
        # in the route (Pitfall 5 — read_score/read_overlay_run are the safe-default boundary, so a
        # torn/absent source → safe-default payload, never a 500, D-04). server_now + gen are ALWAYS
        # set regardless of source state. fields are echoed VERBATIM (operator-typed keys+values, no
        # server-side alias resolution — D-08; the Phase-11 JS renderer owns layout/aliases).
        s = read_score(_path(_SCORE_FILE))
        ovr = read_overlay_run(_path(_OVERLAY_RUN_FILE))
        resp = jsonify(
            {
                "discipline": s.discipline.value,  # default ScoreDoc() → disc_tf when absent
                "fields": s.fields,  # raw verbatim dict (D-08 / SCR-04)
                "running": ovr.running,
                "started_at": ovr.started_at,
                "server_now": time.time(),  # console wall clock — the skew anchor, ALWAYS set
                "gen": ovr.gen,  # monotonic — ALWAYS set
            }
        )
        # Never cache a live fetch (the get_preview_jpg no-store precedent).
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/overlay")
    def get_overlay():
        # OVL-01 — the transparent OBS browser-source host page. THIN: no score/run data is baked
        # in (the page polls /overlay-json each tick), so the page never reloads on a score change.
        # Only the STATIC branding (freestyle duration + event name + logo path + theme colors) is
        # injected as plain render args from overlay_cfg — resolved by the entrypoint like cam_ids,
        # NEVER `import segugio.config` (Pitfall 3 / crash-isolation). overlay.html ships in 11-02.
        #
        # SCV-02 (D-03): `preview` is a purely COSMETIC flag the console iframe sets via
        # `/overlay?preview=1`. It is a CLOSED boolean read off request.args (no new import, no heavy
        # work — RBT-07 crash-isolation stays green) threaded as a SEPARATE render kwarg, NOT folded
        # into overlay_cfg (presentational state, not static branding). The template turns it into a
        # `body.preview` class that keys neutral-backdrop + force-visible CSS — the same renderer at
        # the same URL, differing only by a cosmetic class, so drift is structurally impossible.
        preview = request.args.get("preview") == "1"
        resp = make_response(
            render_template("overlay.html", preview=preview, **overlay_cfg)
        )
        # Never cache the host page (the get_overlay_json / get_preview_jpg no-store precedent) —
        # a CEF browser-source must always re-fetch on refresh, never serve a stale shell.
        resp.headers["Cache-Control"] = "no-store"
        return resp

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
                # MVW-05: expose the already-parsed recent-cuts ring (newest-last) so the console
                # switch-history strip (09-04) has its data source. Mirror write_preview's precedent
                # ([dict(c) for c in doc.cuts]); read_preview safe-defaults cuts to () → [] here.
                "cuts": [dict(c) for c in doc.cuts],
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
    # The static overlay branding (D-07) is resolved HERE too — same lazy discipline as cam_ids so
    # no config import leaks to the module top. Defaults to the console palette; env vars override
    # individual fields, and a SEGUGIO_CONFIG path seeds the rest from cfg.overlay.*.
    _overlay_cfg = dict(_OVERLAY_CFG_DEFAULTS)
    # The active scoring profile + sport for the authoritative /score route and the /score-entry
    # page (D-07/D-06). Resolved HERE only when a SEGUGIO_CONFIG path is given — adapt_scoring_profile
    # lives in the HEAVY config tier, so it is imported LAZILY in __main__ ONLY (mirroring load_config)
    # and the plain dataclass is injected; create_app NEVER imports the config layer (RBT-08/Pitfall 3).
    # None/"disc_dog" defaults fall through to the pinned CSEN_DISC_PROFILE inside create_app.
    _profile = None
    _sport = "disc_dog"
    if _cam_env:
        _cam_ids = [c.strip() for c in _cam_env.split(",") if c.strip()]
    else:
        _cfg_path = os.environ.get("SEGUGIO_CONFIG", "").strip()
        if _cfg_path:
            from ..config.loader import load_config  # lazy: config import stays out of module top
            from ..config.discipline import adapt_scoring_profile  # lazy: heavy-tier adapter

            _cfg = load_config(_cfg_path)
            _cam_ids = [cam.id for cam in _cfg.cameras]
            # Adapt the pydantic scoring profile into the plain stdlib dataclass and read the sport
            # off the discriminated-union field profile — both injected into create_app like cam_ids.
            _profile = adapt_scoring_profile(_cfg.field.scoring)
            _sport = _cfg.field.sport
            # Seed the overlay branding from cfg.overlay.* (the config is the source of truth when a
            # path is given). Env vars below still win over these so an operator can override per run.
            _ovl = _cfg.overlay
            _overlay_cfg.update(
                {
                    "freestyle_duration_s": _ovl.freestyle_duration_s,
                    "event_name": _ovl.event_name,
                    "logo_path": _ovl.logo_path,
                    "theme_accent": _ovl.theme_accent,
                    "theme_plate": _ovl.theme_plate,
                    "theme_text": _ovl.theme_text,
                }
            )
        else:
            _cam_ids = ["cam_wide", "cam_long", "cam_low", "cam_handler"]

    # Per-field env overrides (win over config) — let an operator brand a run without editing the
    # config file. Only set keys an env var is actually present for.
    for _env_key, _cfg_key in (
        ("SEGUGIO_OVERLAY_EVENT", "event_name"),
        ("SEGUGIO_OVERLAY_LOGO", "logo_path"),
        ("SEGUGIO_OVERLAY_ACCENT", "theme_accent"),
        ("SEGUGIO_OVERLAY_PLATE", "theme_plate"),
        ("SEGUGIO_OVERLAY_TEXT", "theme_text"),
    ):
        _val = os.environ.get(_env_key)
        if _val is not None and _val.strip():
            _overlay_cfg[_cfg_key] = _val.strip()

    app = create_app(
        _dir, cam_ids=_cam_ids, overlay_cfg=_overlay_cfg, profile=_profile, sport=_sport
    )
    try:
        # OPTIONAL deploy extra (`pip install segugio[console]`). The import stays INSIDE the
        # entrypoint so the crash-isolation guard passes whether or not waitress is installed.
        from waitress import serve

        serve(app, host="0.0.0.0", port=8080)
    except ImportError:
        # threaded=True is the HARD UXT-02/D-08 safety control on the dev-server fallback: a
        # preview GET can never starve the lone WSGI worker so the /command override stalls.
        app.run(host="0.0.0.0", port=8080, threaded=True)
