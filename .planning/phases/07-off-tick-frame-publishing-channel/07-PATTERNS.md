# Phase 7: Off-tick Frame-Publishing Channel - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 9 (4 new symbols + 3 modified source + tests + config)
**Analogs found:** 9 / 9 (every new symbol has a near-exact in-repo analog — this phase is "the opcomm pattern + bytes + one sidecar")

## File Classification

| New/Modified File | Symbol | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `src/segugio/opcomm/atomic.py` (MODIFY) | `atomic_write_bytes` | utility (leaf) | file-I/O | `atomic_write_text` (same file) | exact |
| `src/segugio/opcomm/records.py` (MODIFY) | `PreviewDoc` | model | transform | `DirectorStatus` (same file) | exact |
| `src/segugio/opcomm/channel.py` (MODIFY) | `read_preview`/`write_preview` | service (boundary) | file-I/O / safe-default | `read_status`/`write_status`+`_read_json` (same file) | exact |
| `src/segugio/orchestrator/preview.py` (NEW) | `PreviewPublisher` | service (daemon thread) | event-driven / pub-sub | `loop.py` daemon + RBT-04 coast | role-match |
| `src/segugio/config/models.py` (MODIFY) | `PreviewParams` | config | — | `ActionHoldParams` (same file) | exact |
| `src/segugio/orchestrator/loop.py` (MODIFY) | `_tick_once` `offer()`, `_cuts_ring`, `_fan_out` return | controller (hot path) | event-driven | RBT-04 try/except + `_apply` change-edge | self-extend |
| `src/segugio/orchestrator/runtime.py` (MODIFY) | `build_orchestrator`+`_channel_paths` | provider (DI) | — | `*_factory` seams + `_channel_paths` (same file) | exact |
| `tests/test_preview_channel.py` (NEW) | round-trip + safe-default | test | — | `tests/test_status_channel.py` | exact |
| `tests/test_ui_score.py` (MODIFY) | import-gate + start-check | test | — | `test_app_imports_nothing_heavy` | self-extend |
| `tests/test_atomic_io.py` (MODIFY) | `atomic_write_bytes` cases | test | — | existing atomic text cases | self-extend |
| `tests/test_latency.py` (MODIFY) | preview ON-vs-OFF p95 gate | test (gpu) | — | `@pytest.mark.gpu` p95 test | self-extend |

---

## Pattern Assignments

### `atomic_write_bytes` — `opcomm/atomic.py` (utility, file-I/O)

**Analog:** `atomic_write_text` (`opcomm/atomic.py:82-96`); reuse `_temp_path` (L55) + `_atomic_replace` (L39) VERBATIM.

**Template body** (`atomic_write_text`, L82-96):
```python
def atomic_write_text(path: str, text: str) -> None:
    tmp = _temp_path(path)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    _atomic_replace(tmp, path)  # atomic on the same volume (Windows: MoveFileEx + retry)
```

**Windows retry it inherits free** (`_atomic_replace`, L39-52):
```python
def _atomic_replace(tmp: str, path: str) -> None:
    for attempt in range(_REPLACE_RETRIES):   # 50 retries, 1ms backoff
        try:
            os.replace(tmp, path); return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1: raise
            time.sleep(_REPLACE_BACKOFF_S)
```

**What to change:** open `"wb"` (no encoding), write `data: bytes`, gate fsync behind `fsync: bool = True` param (publisher passes `False` for JPEGs — D-04). Add `"atomic_write_bytes"` to `__all__` at L26 (currently `["atomic_write_json", "atomic_write_text"]`). Document the fsync-drop-for-JPEG rationale INLINE so it is never silently reverted (D-04 / Pitfall 3). RESEARCH L206-223 has the exact target body.

---

### `PreviewDoc` — `opcomm/records.py` (model, transform)

**Analog:** `DirectorStatus` (`opcomm/records.py:133-158`) — frozen dataclass + normalizing `__post_init__`.

**Template** (L133-158):
```python
@dataclass(frozen=True)
class DirectorStatus:
    live_cam: str = "SAFE"
    reason: str = "none"
    alive: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.alive, dict):
            normalized = {str(k): bool(v) for k, v in self.alive.items()}
        else:
            normalized = {str(k): bool(v) for k, v in dict(self.alive).items()}
        object.__setattr__(self, "alive", normalized)
```

**What to change:** new fields `tick:int=0`, `gen:int=0`, `auto_candidate:str="SAFE"`, `cams:dict` (str-keyed, `{str(k): dict(v)}`), `cuts:tuple` (normalize to `tuple(dict(c) for c in ...)` for hashability). Copy the `object.__setattr__` dict-normalization trick so `read_preview(write_preview(doc)) == doc` round-trips regardless of insertion order. Cast numeric `cams` values with `float()` (the `signals.py` convention). Concrete shape in RESEARCH L256-285.

---

### `read_preview`/`write_preview` — `opcomm/channel.py` (service, safe-default file-I/O)

**Analog:** `write_status`/`read_status` (`channel.py:152-174`) + `_read_json` (L40-61).

**Template** (L152-174):
```python
def write_status(path: str, status: DirectorStatus) -> None:
    atomic_write_json(path, {"live_cam": status.live_cam, "reason": status.reason, "alive": status.alive})

def read_status(path: str) -> DirectorStatus:
    data = _read_json(path)                       # absent/torn/malformed → None, never raises
    if not isinstance(data, dict):
        return DirectorStatus()                   # safe default
    try:
        alive = data.get("alive", {})
        return DirectorStatus(live_cam=data.get("live_cam", "SAFE"),
                              reason=data.get("reason", "none"),
                              alive=alive if isinstance(alive, dict) else {})
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid DirectorStatus at {} → default ({})", path, exc)
        return DirectorStatus()
```

**What to change:** `write_preview` serializes `{tick, gen, auto_candidate, cams, cuts}` through the EXISTING `atomic_write_json` (which always fsyncs → satisfies D-04 "keep fsync for preview.json" for free — do NOT route preview.json through `atomic_write_bytes`). `read_preview` reuses `_read_json` and returns `PreviewDoc()` on any failure. Concrete bodies in RESEARCH L292-315.

---

### `PreviewPublisher` — `orchestrator/preview.py` (NEW; service, event-driven daemon)

**Analogs:** (1) RBT-04 coast-don't-crash try/except in `loop.py`; (2) `_safe_startup` (`loop.py:551-563`); (3) the additive sub-model `ActionHoldParams` for `PreviewParams`.

**RBT-04 coast shape to mirror** (`loop.py:534-540`):
```python
except Exception as exc:  # noqa: BLE001 — RBT-04: ANY stage fault → coast to SAFE
    logger.exception("tick {} failed → SAFE coast: {}", tick, exc)
    self._to_safe(reason="fault", alive=alive)
```
The publisher's `_run` loop wraps `self._publish(*item)` in exactly this `except Exception: logger.warning(...)` shape — an encode/IO fault coasts, never perturbs the director.

**Startup-coast shape** (`_safe_startup`, L551-563) — the lifecycle calls `self._safe_startup("preview.start", self._preview.start)`:
```python
def _safe_startup(self, label: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup {} failed (coasting into tick loop): {}", label, exc)
```

**Mailbox + daemon shape** (RESEARCH L180-200 — Lock + 1-slot attribute, NOT `queue.Queue`):
```python
def offer(self, frames, scores, dets, decision, cuts):
    with self._lock:
        self._latest = (frames, scores, dets, decision, cuts)   # last-wins, never blocks
def _drain(self):
    with self._lock:
        item, self._latest = self._latest, None
    return item
def _run(self):                                  # own daemon thread @ ~1/fps
    while not self._stop.is_set():
        item = self._drain()
        if item is None: time.sleep(self._period); continue
        try: self._publish(*item)                # cv2.resize → imencode → atomic_write_bytes + write_preview
        except Exception as exc: logger.warning("preview publish coasted: {}", exc)
        time.sleep(self._period)
```

**What to change:** `cv2`/`numpy` import LAZILY inside `_publish` only (lazy-import boundary — gate 2). `_publish` does per-cam `cv2.resize`→`cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, q])`→`.tobytes()`→`atomic_write_bytes(cam_<id>.jpg, fsync=False)`, then builds `PreviewDoc` and calls `write_preview(preview.json, doc)`. NO `.copy()` of frames needed (both current FrameSources allocate fresh arrays — RESEARCH L369-374; document the forward-assumption). Bump `gen` each publish (in-sidecar cache-bust, no `gen.txt`).

---

### `PreviewParams` — `config/models.py` (config, additive sub-model)

**Analog:** `ActionHoldParams` (`config/models.py:128-143`) + the `Config` field wiring (L155-157).

**Template** (L141-143 + L155-157):
```python
class ActionHoldParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motion_threshold: Annotated[float, Field(gt=0.0)] = 0.02
    window_ticks: Annotated[int, Field(ge=1)] = 5
# in Config:
    scoring: ScorerParams = Field(default_factory=ScorerParams)
    tracking: TrackingParams = Field(default_factory=TrackingParams)
    action_hold: ActionHoldParams = Field(default_factory=ActionHoldParams)
```

**What to change:** add `PreviewParams{enabled:bool=True, fps≈5.0, max_width≈384, jpeg_quality≈55}` with bounded `Annotated[..., Field(...)]` seeds + `ConfigDict(extra="forbid")`, then `preview: PreviewParams = Field(default_factory=PreviewParams)` on `Config` (so YAML without a `preview:` block still validates — D-05/D-06). Concrete fields in RESEARCH L392-402.

---

### `loop.py` MODIFY — guarded `offer()` + `_cuts_ring` + `_fan_out` return (controller, hot path)

**Insertion site** — `_tick_once` (`loop.py:492-540`), immediately AFTER `self._apply(decision, alive)` at **L521**, still INSIDE the RBT-04 try (so a publisher fault coasts via the catch at L534):
```python
            self._apply(decision, alive)          # L521
            t_obs = time.perf_counter()           # L522
            # ── insert here, before/around the probe block ──
            # if self._preview is not None:
            #     self._preview.offer(frames_by_cam, scores, dets_by_cam, decision, cuts=list(self._cuts_ring))
```
- `scores` is already in scope (`scores = self.scorer.update(dets_by_cam, tick)`, **L511**).
- `dets_by_cam` is already in scope (`dets_by_cam, locked_energy = self._fan_out(tick)`, **L507**).
- `frames_by_cam` exists but is LOCAL to `_batched_inference` (L370: `frames_by_cam = {cam.id: self.source.latest(cam.id) for cam in self.cameras}`). **Surface it:** have `_fan_out` return `(dets_by_cam, locked_energy, frames_by_cam)` — do NOT call `source.latest()` a second time (could return a different frame + extra lock; RESEARCH L376-380).

**Cuts-ring feed** — the change-edge already exists in `_apply` (`loop.py:467-470`):
```python
        status = self._status_for(decision, alive)
        if status != self._last_status:           # L468 — this is the cut edge
            write_status(self._status_path, status)
            self._last_status = status
```
**What to change:** add a `self._cuts_ring = collections.deque(maxlen=16)` in `__init__`; append `{tick, from, to, reason}` at this L468 edge when the live target changed. Maintain the ring on the orchestrator (not the publisher) so dropped preview frames never lose a cut (Pitfall 5). Add `preview=None` to `__init__` (L130) + `from_config` (L181), store `self._preview`. Add `if self._preview is not None: self._safe_startup("preview.start", self._preview.start)` in `run`/`run_measured`; `self._preview.stop()` (coast-wrapped) in `shutdown()`. RESEARCH L427-448 has exact snippets.

---

### `runtime.py` MODIFY — `build_orchestrator` factory seam + `_channel_paths` (provider, DI)

**Analog:** the `*_factory` injection pattern (`runtime.py:114-152`) + `_channel_paths` (L68-77) + `os.makedirs` defensiveness (L161).

**Factory-seam template** (L120-122 + L150-152 + L80-84):
```python
    source_factory: Callable | None = None,
    obs_factory: Callable | None = None,
    tracker_factory: Callable | None = None,
    ...
    source_factory = source_factory or _default_source_factory   # L150
    obs_factory = obs_factory or _default_obs_factory

def _default_source_factory(cameras):
    from ..ndi.ndi_source import NdiFrameSource     # LAZY heavy import inside the default
    return NdiFrameSource(list(cameras))
```

**`_channel_paths` to extend** (L68-77):
```python
def _channel_paths(channel_dir: str) -> dict[str, str]:
    base = Path(channel_dir)
    return {"command": ..., "runstate": ..., "status": ..., "score": ..., "overlay": ...}
```

**`makedirs` defensiveness** (L161): `os.makedirs(channel_dir, exist_ok=True)`.

**What to change:** add a `preview_factory: Callable | None = None` param + `_default_preview_factory` (lazy `from .preview import PreviewPublisher`). Construct the publisher guarded by `config.preview.enabled` (D-06 — None when disabled = byte-identical-to-v1.0) and pass `preview=` into `Orchestrator.from_config`. Add a `preview` media dir + `preview.json` path to `_channel_paths`, and `os.makedirs(preview_dir, exist_ok=True)` mirroring L161. RESEARCH L409-424.

---

### `tests/test_preview_channel.py` NEW (test) — template: `tests/test_status_channel.py`

**Round-trip / safe-default templates** (`test_status_channel.py:71-76, 108-113`):
```python
    status = read_status(str(file_channel["status"]))
    assert status.live_cam == "SAFE"
    assert set(status.alive.keys()) == {cam.id for cam in cfg.cameras}

def test_status_default_when_no_loop_run(make_config, file_channel):
    """Before any tick, read_status of an absent file returns the SAFE default (RBT-04)."""
    status = read_status(str(file_channel["status"]))
    assert status.live_cam == "SAFE"
    assert status.reason == "none"
```
**What to change:** write a `PreviewDoc` with cams+cuts, `write_preview`→`read_preview`, assert `==` (round-trip equality on the normalized dataclass). Assert `read_preview(<absent path>) == PreviewDoc()` (safe default). Add a torn/malformed-JSON case → default.

### `tests/test_ui_score.py` MODIFY (test) — gate 2 import-isolation, EXTEND

**Template** (`test_app_imports_nothing_heavy`, L105-125):
```python
def test_app_imports_nothing_heavy(monkeypatch):
    import importlib, sys
    for heavy in ("ultralytics", "torch", "cyndilib", "obsws_python", "cv2"):
        monkeypatch.setitem(sys.modules, heavy, None)   # importing it now raises ImportError
    for cached in list(sys.modules):
        if cached == "segugio.ui" or cached.startswith("segugio.ui."):
            monkeypatch.delitem(sys.modules, cached, raising=False)
    importlib.import_module("segugio.ui.app")            # must NOT raise
```
**What to change:** add `"numpy"` to the heavy tuple (today's gate blocks cv2 but NOT numpy — Pitfall 2). Add a `create_app(...)` start-check (ROADMAP gate 2: "console starts", not just imports).

### `tests/test_atomic_io.py` MODIFY + `tests/test_latency.py` MODIFY

- `test_atomic_io.py`: add `atomic_write_bytes` round-trip + a spy asserting the publisher calls it with `fsync=False` for JPEGs (Pitfall 3).
- `test_latency.py`: the gpu p95 gate already asserts `total_p95_ms < 300.0` (L210) via `run_measured` (L206-207) under `@pytest.mark.gpu` (L142). EXTEND with a preview-ON-vs-OFF comparison: measure two back-to-back OFF runs for the jitter band, then assert ON p95 ≤ OFF p95 + band (RESEARCH Open-Q 1 / A3 — derive the tolerance on-rig, do NOT hardcode a magic number).

---

## Shared Patterns

### RBT-04 coast-don't-crash
**Source:** `loop.py:534-540` (`except Exception: logger.exception(...); self._to_safe(...)`) and `_safe_startup` (L551-563).
**Apply to:** `PreviewPublisher._run`, `PreviewPublisher.start`/`stop` calls, and the `offer()` site (which rides inside the EXISTING tick try at L534). Every publish coasts on fault and is logged — never perturbs the director (PRV-01 criterion 5).

### Atomic temp→replace primitive
**Source:** `atomic.py` `_temp_path` (L55) + `_atomic_replace` (L39, 50-retry Windows MoveFileEx).
**Apply to:** `atomic_write_bytes` (reuse VERBATIM); `write_preview` rides on `atomic_write_json` which reuses the same primitive.

### Safe-default never-raise read boundary
**Source:** `channel.py:_read_json` (L40-61).
**Apply to:** `read_preview` (absent/torn/malformed → `PreviewDoc()`), exactly as `read_status` does.

### Lazy heavy-import boundary (gate 2)
**Source:** the `_default_*_factory` lazy imports in `runtime.py` (L80-90) + `create_app`'s inside-Flask import (`ui/app.py:60-67`).
**Apply to:** `cv2`/`numpy` import ONLY inside `PreviewPublisher._publish`; `from .preview import PreviewPublisher` lazy in `_default_preview_factory`. `ui/app.py` is NOT touched — the gate-2 test locks its clean surface.

### Additive config sub-model
**Source:** `ActionHoldParams` (`config/models.py:128-143`) + `Config` `Field(default_factory=...)` wiring (L155-157).
**Apply to:** `PreviewParams` + `Config.preview` — existing `extra="forbid"` YAML without a `preview:` block still validates.

### Injectable `*_factory` DI seam (headless tests)
**Source:** `build_orchestrator(source_factory/obs_factory/tracker_factory)` (`runtime.py:114-152`).
**Apply to:** add `preview_factory` so headless unit tests inject a fake encoder (no real cv2/GPU).

---

## No Analog Found

None. Every Phase-7 symbol has an exact or role-match in-repo analog (this phase is deliberately "the opcomm pattern + bytes + one sidecar"). The only genuinely NEW construct is the `PreviewPublisher` daemon thread, and even it composes existing primitives (RBT-04 coast + `_safe_startup` + atomic write + Lock-mailbox) — no new IPC, no new dependency.

## Metadata

**Analog search scope:** `src/segugio/opcomm/`, `src/segugio/orchestrator/`, `src/segugio/config/`, `src/segugio/ui/`, `tests/`
**Files scanned:** atomic.py, records.py, channel.py, loop.py, runtime.py, config/models.py, test_status_channel.py, test_ui_score.py, test_latency.py
**Pattern extraction date:** 2026-06-13
