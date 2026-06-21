# Phase 10: Overlay Data Contract & Run-Timestamp Publish - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 8 (4 modified, 4 new/extended)
**Analogs found:** 8 / 8 (all exact, all VERIFIED against live source)

All analogs the research named were verified line-by-line against the current source. Line numbers below are confirmed accurate as of this read. This phase is pure composition — every primitive already exists; there is no "no analog found" file.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/opcomm/records.py` (ADD `OverlayRunDoc`) | model (frozen record) | transform / boundary-normalize | `PreviewDoc` (records.py L162-203) | exact |
| `src/segugio/opcomm/channel.py` (ADD `write_overlay_run`/`read_overlay_run`) | service (IO boundary) | file-I/O, request-response | `write_preview`/`read_preview` (channel.py L182-224) | exact |
| `src/segugio/ui/app.py` (MODIFY `create_app`/`post_run`/`post_score`; ADD `get_overlay_json`) | controller (route) | request-response, file-I/O | `get_status`/`get_preview`/`post_run`/`post_score` (app.py L99-215) | exact |
| `src/segugio/config/models.py` (ADD `OverlayParams` + `overlay` field) | config (pydantic) | transform / validate | `PreviewParams`/`ActionHoldParams` (models.py L128-171, L227) | exact |
| `tests/test_imports.py` (EXTEND crash-isolation test) | test (import-isolation) | — | `test_console_resolves_with_heavy_stack_and_numpy_absent` (L87-108) | exact (extend in place) |
| `tests/test_opcomm_overlay_run.py` (NEW) | test (unit round-trip) | file-I/O | `tests/test_preview_channel.py` (full file) | exact |
| `tests/test_ui_overlay_json.py` (NEW) | test (route) | request-response | `tests/test_ui_run.py` (full file) + `file_channel` fixture | exact |
| `tests/test_config_overlay.py` (NEW) | test (pydantic) | validate | `tests/test_config_engine_keys.py` (full file) | exact |

## Pattern Assignments

### `src/segugio/opcomm/records.py` — ADD `OverlayRunDoc` (model, transform)

**Analog:** `PreviewDoc` (records.py L162-203). Also see `ScoreDoc` L58-74 for the simplest `__post_init__` coercion shape.

**`__all__` entry** (records.py L31-38) — append `"OverlayRunDoc"`:
```python
__all__ = [
    "Discipline",
    "ScoreDoc",
    "RunState",
    "OperatorCommand",
    "DirectorStatus",
    "PreviewDoc",
]
```

**Frozen-record + `object.__setattr__` normalization convention** (the exact idiom to mirror — from `PreviewDoc.__post_init__`, records.py L196-203):
```python
@dataclass(frozen=True)
class PreviewDoc:
    tick: int = 0
    gen: int = 0
    auto_candidate: str = "SAFE"
    cams: dict = field(default_factory=dict)
    cuts: tuple = ()

    def __post_init__(self) -> None:
        cams = self.cams if isinstance(self.cams, dict) else dict(self.cams)
        object.__setattr__(self, "cams", {str(k): dict(v) for k, v in cams.items()})
        object.__setattr__(self, "cuts", tuple(dict(c) for c in self.cuts))
```

**Adaptation for Phase 10** — a 3-field record `{running: bool, started_at: float|None, gen: int}` with scalar coercion (no container normalization needed; `started_at` is nullable):
```python
@dataclass(frozen=True)
class OverlayRunDoc:
    running: bool = False
    started_at: float | None = None
    gen: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "running", bool(self.running))
        if self.started_at is not None:
            object.__setattr__(self, "started_at", float(self.started_at))
        object.__setattr__(self, "gen", int(self.gen))
```
Note: `dataclass`/`field`/`enum` are already imported at records.py L28-29 — no new imports. No Enum field here (unlike `ScoreDoc`), so no `Discipline`-style coercion.

---

### `src/segugio/opcomm/channel.py` — ADD `write_overlay_run`/`read_overlay_run` (service, file-I/O)

**Analog:** `write_preview`/`read_preview` (channel.py L182-224). The never-raise boundary `_read_json` is L42-63; `atomic_write_json` is imported at L25.

**Import line to extend** (channel.py L26):
```python
from .records import DirectorStatus, OperatorCommand, PreviewDoc, RunState, ScoreDoc
```
→ add `OverlayRunDoc`.

**`__all__` entries** (channel.py L28-39) — append `"write_overlay_run"`, `"read_overlay_run"`.

**Writer pattern** (mirror `write_preview`, channel.py L182-199 — atomic_write_json with an explicit dict):
```python
def write_preview(path: str, doc: PreviewDoc) -> None:
    atomic_write_json(
        path,
        {"tick": doc.tick, "gen": doc.gen, "auto_candidate": doc.auto_candidate,
         "cams": doc.cams, "cuts": [dict(c) for c in doc.cuts]},
    )
```

**Safe-default reader + `logger.warning` on invalid** (the exact never-raise shape — `read_preview`, channel.py L202-224):
```python
def read_preview(path: str) -> PreviewDoc:
    data = _read_json(path)
    if not isinstance(data, dict):
        return PreviewDoc()
    try:
        return PreviewDoc(
            tick=int(data.get("tick", 0)),
            gen=int(data.get("gen", 0)),
            ...
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid PreviewDoc at {} → default ({})", path, exc)
        return PreviewDoc()
```

**Adaptation for Phase 10** — note the nullable `started_at` (mirror the `read_score` nullable-field handling at L82-85 + `read_command` `None` handling at L139):
```python
def write_overlay_run(path: str, doc: OverlayRunDoc) -> None:
    atomic_write_json(path, {"running": doc.running,
                             "started_at": doc.started_at, "gen": doc.gen})

def read_overlay_run(path: str) -> OverlayRunDoc:
    data = _read_json(path)
    if not isinstance(data, dict):
        return OverlayRunDoc()
    try:
        started = data.get("started_at")
        return OverlayRunDoc(
            running=bool(data.get("running", False)),
            started_at=None if started is None else float(started),
            gen=int(data.get("gen", 0)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid OverlayRunDoc at {} → default ({})", path, exc)
        return OverlayRunDoc()
```

---

### `src/segugio/ui/app.py` — MODIFY `create_app`/`post_run`/`post_score`; ADD `get_overlay_json` (controller)

**Analogs:** `get_status` (L173-180), `get_preview` (L199-215), `post_run` (L143-157), `post_score` (L99-117). The `Cache-Control: no-store` precedent is `get_preview_jpg` L194-197. The `_path()` helper is L86-87; the file-name constants are L51-62. The import allowlist is L34-45 (Flask imported *inside* `create_app` at L80).

**Import-allowlist extension** (app.py L34-40) — add only in-repo opcomm names + stdlib `time`. Do NOT add any heavy import; do NOT import `segugio.config` at module top:
```python
from ..opcomm.channel import (
    read_preview,
    read_status,
    write_command,
    write_runstate,
    write_score,
)
from ..opcomm.records import Discipline, OperatorCommand, RunState, ScoreDoc
```
→ add `read_score`, `read_overlay_run`, `write_overlay_run` to the channel import; add `OverlayRunDoc` to the records import; add `import time` (stdlib, at module top is fine — `os` is already there at L32). Add a new constant beside L51-62:
```python
_OVERLAY_RUN_FILE = "overlay_run.json"
```

**Closure-state + seed-from-disk precedent** — `create_app` already holds closure state via `cam_ids = frozenset(cam_ids)` (L82) and the `_path` closure (L86-87). Seed `gen` from disk right after `os.makedirs` (L84):
```python
# D-02: seed gen from the persisted overlay_run.json (never reset to 0 → restart re-anchors).
_state = {"gen": read_overlay_run(_path(_OVERLAY_RUN_FILE)).gen}
```
> Discretion note (research Pattern 2): the planner finalizes whether `gen` is a closure dict (shown) or a small object, and SHOULD guard the read-modify-write bump with a `threading.Lock` (the console serves multi-threaded — app.py L243-249; the PreviewPublisher precedent locks its bump).

**`post_run` side-write — byte-for-byte invariant** (app.py L143-157). The `write_runstate(_path(_RUNSTATE_FILE), run)` line at L156 stays EXACTLY as-is; append the overlay-run write strictly after it:
```python
write_runstate(_path(_RUNSTATE_FILE), run)   # UNCHANGED — director reads this every tick
# NEW (D-03): additional side-write AFTER write_runstate.
if action == "start":
    # bump gen + persist OverlayRunDoc(running=True, started_at=time.time(), gen=...)
else:  # "stop"
    # bump gen + persist OverlayRunDoc(running=False, started_at=None, gen=...)
```

**`post_score` gen bump** (app.py L99-117). The existing `write_score` (L115) + `atomic_write_text(...render_overlay_text...)` (L116) stay UNCHANGED; add a gen-only bump that PRESERVES `running`/`started_at` (read current `OverlayRunDoc`, re-persist with only `gen+1` — `/score` is not a run edge, per Open Question 1):
```python
write_score(_path(_SCORE_FILE), doc)                               # UNCHANGED
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # UNCHANGED
# NEW (D-02): bump gen only; keep running/started_at as-is.
```

**`get_overlay_json` route** — mirror `get_status` (L173-180) shape + the `Cache-Control: no-store` header from `get_preview_jpg` (L196). Assemble from two never-raise reads + `time.time()` (D-04/D-08):
```python
@app.get("/overlay-json")
def get_overlay_json():
    s = read_score(_path(_SCORE_FILE))               # discipline + verbatim fields (D-08)
    ovr = read_overlay_run(_path(_OVERLAY_RUN_FILE))
    resp = jsonify({
        "discipline": s.discipline.value,            # ScoreDoc() default disc_tf when absent
        "fields": s.fields,                          # raw verbatim dict (D-08)
        "running": ovr.running,
        "started_at": ovr.started_at,
        "server_now": time.time(),                   # console wall clock — ALWAYS set
        "gen": ovr.gen,                              # monotonic — ALWAYS set
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp
```
> `jsonify` is already in the in-factory Flask import at L80. `read_score` is the safe-default reader (channel.py L76-88) — its default `ScoreDoc().discipline` is `disc_tf` (A2). Do NOT use `json.load`/`open` in the route (Pitfall 5); do NOT resolve aliases server-side (D-08, Pitfall).

---

### `src/segugio/config/models.py` — ADD `OverlayParams` + `overlay` field (config, validate)

**Analog:** `PreviewParams` (L146-171) and `ActionHoldParams` (L128-144) — both additive `ConfigDict(extra="forbid")` sub-models; the `Config` field-wiring with `default_factory` is L222-227.

**Sub-model convention** (mirror `ActionHoldParams`, L141-143 — the bounded-field shape):
```python
class ActionHoldParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motion_threshold: Annotated[float, Field(gt=0.0)] = 0.02
    window_ticks: Annotated[int, Field(ge=1)] = 5
```

**`Config` field-wiring** (the `default_factory` line that lets a config WITHOUT an `overlay:` block still validate — models.py L222-227):
```python
    thresholds: Thresholds = Field(default_factory=Thresholds)
    model: ModelConfig = Field(default_factory=ModelConfig)
    scoring: ScorerParams = Field(default_factory=ScorerParams)
    tracking: TrackingParams = Field(default_factory=TrackingParams)
    action_hold: ActionHoldParams = Field(default_factory=ActionHoldParams)
    preview: PreviewParams = Field(default_factory=PreviewParams)
```

**Adaptation for Phase 10** (D-05/D-06):
```python
class OverlayParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    freestyle_duration_s: Annotated[int, Field(gt=0)] = 120   # D-06: 2-min routines

# On Config (append after `preview`):
    overlay: OverlayParams = Field(default_factory=OverlayParams)
```
`BaseModel`, `ConfigDict`, `Field`, `Annotated` are all already imported (L22-30). `default_factory` is mandatory — the loader is fail-fast `SystemExit(2)` on `ValidationError` so existing configs must keep validating. `config.example.yaml` (already modified in git) SHOULD gain a commented `overlay:` block — planner reconciles (A3).

---

### `tests/test_imports.py` — EXTEND `test_console_resolves_with_heavy_stack_and_numpy_absent` (test, RBT-07)

**Analog:** the existing test at L87-108, and the `CONSOLE_HEAVY_MODULES` mechanism at L25 (`HEAVY_MODULES + ["numpy", "cv2"]`).

**Exact structure to extend** (L87-108):
```python
def test_console_resolves_with_heavy_stack_and_numpy_absent(monkeypatch):
    for name in CONSOLE_HEAVY_MODULES:
        monkeypatch.setitem(sys.modules, name, None)
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)
    import segugio.ui  # noqa: F401
    from segugio.ui.app import create_app
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(tmp, cam_ids=["cam_wide"])
        assert app is not None
```

**Adaptation for Phase 10** — after `create_app`, exercise the new route via the test client under the heavy-absent block (proves `/overlay-json` imports only Flask + opcomm):
```python
        client = app.test_client()
        resp = client.get("/overlay-json")
        assert resp.status_code == 200
        assert "gen" in resp.get_json() and "server_now" in resp.get_json()
```
Keep `numpy`/`cv2`/`torch`/`cyndilib`/`obsws_python` in the forced-absent set — do NOT add any heavy import to satisfy the route (Pitfall 4).

---

### `tests/test_opcomm_overlay_run.py` (NEW) — unit round-trip + safe-default (test)

**Analog:** `tests/test_preview_channel.py` (full file). Mirror its four-test shape exactly.

**Patterns to mirror** (from test_preview_channel.py):
- `test_preview_round_trip` (L55-60): `write_overlay_run(path, doc); assert read_overlay_run(path) == doc` (frozen `==` round-trip).
- `test_preview_default_when_absent` (L79-82): absent path → `OverlayRunDoc()`.
- `test_preview_default_when_malformed` (L85-99): `"{not json"`, `b"\x00\x01garbage"`, `"[1,2,3]"` (wrong top-level shape), `""` (empty) → all `OverlayRunDoc()`.
- `test_preview_doc_is_frozen_and_hashable` (L102-114): frozen attribute-assignment is rejected.

**Adaptation for Phase 10** — add a `test_overlay_run_doc_normalizes` asserting `__post_init__` coercion: e.g. `OverlayRunDoc(running=1, started_at="123.5", gen="7")` yields `running is True`, `started_at == 123.5` (float), `gen == 7` (int); and `started_at=None` survives. Imports: `from segugio.opcomm.channel import read_overlay_run, write_overlay_run` + `from segugio.opcomm.records import OverlayRunDoc`. Use the `tmp_path` fixture directly (the preview test does — no special fixture needed for the unit layer).

---

### `tests/test_ui_overlay_json.py` (NEW) — Flask route tests (test)

**Analog:** `tests/test_ui_run.py` (full file) — the `client` fixture over `file_channel` (L15-21) and the POST/GET assertion shape.

**`client` fixture to copy verbatim** (test_ui_run.py L15-21):
```python
@pytest.fixture
def client(file_channel):
    from segugio.ui.app import create_app
    app = create_app(str(file_channel["dir"]))
    app.config.update(TESTING=True)
    return app.test_client(), file_channel
```

**Route-test shape to mirror** (test_ui_run.py L27-42, L87-99):
```python
def test_run_start_flags_lock_reset(client):
    c, ch = client
    resp = c.post("/run", data={"action": "start"})
    assert resp.status_code in (200, 204)
    run = read_runstate(str(ch["runstate"]))
    ...
```

**Adaptations for Phase 10** (covers the Phase-Requirements→Test map, RESEARCH L429-439):
- The `file_channel` fixture (conftest.py L422-439) returns keys `dir/score/runstate/command/status/overlay` — it has **NO `overlay_run` key**. Either reference `ch["dir"] / "overlay_run.json"` directly, or (cleaner) add an `"overlay_run": d / "overlay_run.json"` key to the fixture. **Planner's call — flag this as the one fixture adaptation.**
- Tests to write: `test_run_start_stamps_overlay_run` (running=true + started_at is a float epoch, not seconds-since-boot — Pitfall 3), `test_run_stop_nulls_overlay_run`, `test_runstate_byte_for_byte_unchanged` (capture bytes from a `write_runstate(RunState(action="start", just_started=True, just_stopped=False))` baseline, assert `post_run` produces identical bytes — the HARD director invariant, RESEARCH L457), `test_overlay_json_payload_shape` (6 keys + `Cache-Control: no-store`), `test_overlay_json_safe_default_when_absent`, `test_overlay_json_safe_default_on_corrupt` (write `"{torn"` to both sources; assert 200 + `server_now`/`gen` still set), `test_overlay_json_fields_verbatim`, `test_gen_bumps_on_run_and_score`, `test_gen_seeds_from_disk_on_restart` (write `overlay_run.json` with `gen=7`, build a FRESH `create_app`, POST `/run`, assert next gen ≥ 8), `test_started_at_persists_across_restart`.

---

### `tests/test_config_overlay.py` (NEW) — pydantic tests (test)

**Analog:** `tests/test_config_engine_keys.py` (full file) — the additive-sub-model test idiom.

**Patterns to mirror** (test_config_engine_keys.py):
- `test_engine_keys_default_to_eager` (L26-32): default value present (`OverlayParams().freestyle_duration_s == 120`).
- `test_extra_forbid_still_rejects_unknown_key` (L35-37): `pytest.raises(ValidationError)` on a bogus key.
- explicit-value parse (L45-52): `OverlayParams.model_validate({"freestyle_duration_s": 90})`.

**Adaptations for Phase 10** (D-05/D-06):
- `freestyle_duration_s` defaults to 120.
- A `Config` WITHOUT an `overlay:` block still validates (use the `valid_config_dict`/`make_config` fixture from conftest — see test_config.py for how the full `Config` is built — and assert `cfg.overlay.freestyle_duration_s == 120`).
- `freestyle_duration_s <= 0` is rejected (`Field(gt=0)` → `ValidationError`).
- Imports: `from segugio.config.models import OverlayParams` (+ `Config` for the optional-block test) and `from pydantic import ValidationError`.

## Shared Patterns

### Never-raise file-read boundary
**Source:** `_read_json` (channel.py L42-63) — absorbs absent/empty/torn/malformed → `None`.
**Apply to:** `read_overlay_run` and the `/overlay-json` route (via `read_score` + `read_overlay_run` only — no direct `json.load`). D-04 blank-safe semantics fall out for free.

### Atomic, always-fsync write
**Source:** `atomic_write_json` (imported channel.py L25; impl in `opcomm/atomic.py`) — same-dir temp + fsync + Windows MoveFileEx retry.
**Apply to:** `write_overlay_run`. Never hand-roll `open(...).write()`.

### `Cache-Control: no-store` on a live fetch
**Source:** `get_preview_jpg` (app.py L196): `resp.headers["Cache-Control"] = "no-store"`.
**Apply to:** the new `/overlay-json` route.

### Frozen-record `object.__setattr__` boundary normalization
**Source:** `PreviewDoc.__post_init__` (records.py L196-203) / `ScoreDoc.__post_init__` (L70-74).
**Apply to:** `OverlayRunDoc.__post_init__` (scalar coercion: `bool`/`float|None`/`int`).

### Additive `extra="forbid"` sub-model + `default_factory`
**Source:** `PreviewParams`/`ActionHoldParams` (models.py L128-171) wired via `Field(default_factory=...)` on `Config` (L222-227).
**Apply to:** `OverlayParams` + the `overlay` field. Mandatory so existing configs without an `overlay:` block keep loading (loader is fail-fast `SystemExit(2)`).

### Crash-isolation import allowlist (RBT-07)
**Source:** `ui/app.py` imports only `segugio.opcomm` + stdlib at module top; Flask imported INSIDE `create_app` (L80). Gate: `test_console_resolves_with_heavy_stack_and_numpy_absent` (test_imports.py L87-108).
**Apply to:** all `ui/app.py` edits — only `time` (stdlib) + the new opcomm names. NEVER `import segugio.config` at module top (the freestyle duration is Phase-11, injected as an entrypoint arg like `cam_ids`, app.py L222-239).

## No Analog Found

None. Every Phase-10 file has an exact in-repo analog (the `PreviewDoc` triad, the `PreviewParams` additive sub-model, the existing route/test/fixture patterns). This phase is composition, not invention.

## Metadata

**Analog search scope:** `src/segugio/opcomm/`, `src/segugio/ui/`, `src/segugio/config/`, `tests/`
**Files scanned (full read):** records.py, channel.py, ui/app.py, config/models.py, test_imports.py, test_ui_run.py, test_preview_channel.py, test_config_engine_keys.py, conftest.py (file_channel fixture)
**Pattern extraction date:** 2026-06-14
