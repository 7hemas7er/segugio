# Phase 7: Off-tick Frame-Publishing Channel - Research

**Researched:** 2026-06-13
**Domain:** Off-tick binary publish channel + typed sidecar over the existing opcomm atomic-file IPC, with two HARD invariant gates (RBT-05 latency; console crash-isolation)
**Confidence:** HIGH — every seam CONTEXT.md names was opened and confirmed in this session; no drift found. The only LOW/ASSUMED items are JPEG fidelity *defaults* (a Phase-8 tuning concern) and the exact EMA-vs-raw score split (resolved below: not separately available without a scorer change, which is out of scope).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Transport = per-camera JPEG files in `opcomm/preview/` over the existing atomic-file channel.** Chosen over MJPEG/WebSocket and OBS-multiview-embed. The console only `send_file`s bytes — its import set does not change.
- **D-02: Latest-only single-slot mailbox for the tick→publisher hand-off.** The tick's only added cost is a non-blocking `offer(frames_by_cam, scores, dets_by_cam)`. ALL resize/encode/fsync/IO happen on the `PreviewPublisher` daemon thread. The tick never waits on the publisher.
- **D-03: The "why" data travels in a NEW `preview.json` sidecar, never in `status.json`.** `status.json`/`DirectorStatus` stays byte-stable and write-on-change. `PreviewDoc` mirrors `DirectorStatus` exactly (frozen, normalizing `__post_init__`, safe-default `read_preview` that never raises). The cuts ring + FSM auto-candidate live HERE.
- **D-04: `atomic_write_bytes` reuses the temp→`os.replace` primitive, DROPS `fsync` for the ephemeral JPEGs, KEEPS it for `preview.json`.** This fsync-drop MUST be documented in `atomic_write_bytes` so it is not silently reverted. The Windows `_atomic_replace` MoveFileEx-retry covers the open-read-close race.
- **D-05: Default fidelity = ~5 fps / 384px-wide thumbnails / JPEG quality ≈ 55** → ~0.3–0.8 MB/s total for 4 cams. Config defaults in an additive `PreviewParams{fps, max_width, jpeg_quality, enabled}` sub-model (same pattern as `ScorerParams`/`TrackingParams`). Phase 8 owns the HARD bandwidth cap.
- **D-06: `preview.enabled` defaults to ON.** When `enabled: false`, the orchestrator is byte-identical to v1.0 — no daemon thread, no mailbox, no per-tick `offer()` (guard: `if self._preview is not None: ...`).
- **D-07: Publish the FULL "why" payload in Phase 7.** Per-camera: framing score (+ EMA), tracking state (tracking/coast/lost), `locked`/`track_id`, motion energy, in-zone flag, normalized dog bbox, plus top-level FSM auto-candidate and a recent-cuts ring (depth ~16).
- **D-08: Recent-cuts ring depth = ~16 entries.** Each entry small (tick, from→to camera, reason). Maintained on the publisher/orchestrator side and serialized into `preview.json`.
- **D-09: Phase 7 = channel (steps 1–4) wired into the REAL run path + both HARD gates.** "Done" = a real `python -m segugio <config>` launch writes per-camera JPEGs + `preview.json` into `opcomm/preview/`, AND gate 1 (RBT-05 p95 unchanged within noise with preview ON), AND gate 2 (crash-isolation import test with the heavy stack uninstalled). `threaded=True` fix, console routes, bandwidth cap, threat re-eval are OUT (Phase 8).

### Claude's Discretion
- **Mailbox implementation** — `threading.Lock` + 1-slot attribute vs `queue.Queue(maxsize=1)`. Invariant: the tick never blocks. → *Recommendation below: Lock + 1-slot attribute.*
- **Frame-snapshot safety** — `.copy()` when offering vs copy on the publisher; confirm `NdiFrameSource.latest()` buffer-reuse. → *Resolved below: NO copy needed; both sources return a fresh array per frame.*
- **Cache-bust token** — separate `gen.txt` vs reusing an in-sidecar `tick`/`gen` field. → *Recommendation below: in-sidecar `gen` field, no extra file.*
- **`atomic_write_bytes` fsync seam** — `fsync: bool = True` param vs two functions. → *Recommendation below: single function with `fsync: bool = True` param.*
- **Where the publisher pulls the N camera frames** — surface a single `frames_by_cam` dict to `offer()` cheaply. → *Resolved below: reuse the dict `_batched_inference` already builds; build it once in the serial path too.*
- **Exact `PreviewParams` field names / config placement** — additive sub-model mirroring `ScorerParams`/`TrackingParams`. → *Concrete shape below.*

### Deferred Ideas (OUT OF SCOPE)
- Console serving routes (`GET /preview`, `GET /preview/<cam>.jpg`), multiview grid, LIVE/tally, dead-feed marking — **Phase 8 (MVW-01/02/03)**.
- `threaded=True`/Waitress server fix — **Phase 8 (UXT-02)**.
- Preview-bandwidth HARD cap + real-WiFi-with-phones validation — **Phase 8**.
- Live operator kill-switch + freshness/staleness "never show a frozen frame as live" overlay — **Phase 9 (UXT-03)**.
- Explainability rendering (score bars, plain-Italian reason, bbox overlay, switch-history strip, score-overlay preview) — **Phase 9**. The *data* ships in `preview.json` now; only rendering is deferred.
- Re-verify BoT-SORT native ReID engages on `yolo26s` at startup before depending on `locked`/`track_id` — relevant in Phase 9 when the bbox renders; the field is published now.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (from REQUIREMENTS.md §PRV, Italian) | Research Support |
|----|-------------------------------------------------|------------------|
| **PRV-01** | The orchestrator publishes downscaled per-camera JPEG thumbnails **off the critical tick** (`PreviewPublisher` daemon thread, latest-only mailbox, frame-drop allowed) into a **separate, bounded** media dir — the RBT-05 gate p95 stays unchanged with preview ON. | Mailbox + daemon pattern (ARCHITECTURE Pattern 1, verified `loop.py` seams §"Architecture Patterns"); RBT-05 harness mechanics (§"Validation Architecture" gate 1); `opcomm/preview/` dir via `_channel_paths` extension (§"Integration Points"). |
| **PRV-02** | A `preview.json` sidecar (`PreviewDoc`, frozen + safe-default reader that never raises) carries per-camera framing score + tracking state (tracking/coast/lost) + normalized dog bbox + FSM auto-candidate + recent-cuts ring — **separate** from `status.json` (unchanged/safety-critical). | `PreviewDoc` shape modeled byte-for-byte on `DirectorStatus` (§"PreviewDoc Shape"); data-source map for every field (§"The 'why' payload — where each field already exists"). |
| **PRV-03** | Binary atomic write primitive (`atomic_write_bytes`, mirror of the text one, no fsync for ephemeral frames); the console keeps importing **only Flask + `segugio.opcomm`** (crash-isolation import test: import OK with the heavy stack absent). | `atomic_write_bytes` reuses `_temp_path`/`_atomic_replace` verbatim (§"Code Examples"); crash-isolation test extends the existing `test_app_imports_nothing_heavy` pattern, adding `numpy` to the block (§"Validation Architecture" gate 2). |
</phase_requirements>

## Summary

Phase 7 is **the opcomm pattern extended with one binary writer and one sidecar record — not a new IPC.** Every seam CONTEXT.md and ARCHITECTURE.md name was opened and confirmed in this session: `atomic.py`'s `_temp_path`/`_atomic_replace`/`atomic_write_text`, `records.py`'s `DirectorStatus` + normalizing `__post_init__`, `channel.py`'s `_read_json`/`read_status`/`write_status`, `loop.py`'s `_tick_once`/`_fan_out`/`_batched_inference`/`run`/`run_measured`/`shutdown`, `runtime.py`'s `build_orchestrator`/`_channel_paths`/`*_factory`, `app.py`'s lazy-Flask `create_app`, and the `FrameSource` Protocol. **There is no drift from what CONTEXT.md assumes.** The work is four new/modified surfaces (`atomic_write_bytes`, `PreviewDoc`+`read_preview`/`write_preview`, `PreviewPublisher`, the `loop.py`/`runtime.py` wiring) plus the two HARD gates.

The single load-bearing risk is **step 4** — the guarded `offer()` in `_tick_once`, the only hot-path touch. It is a `with self._lock: self._latest = (...)` dict ref-assignment; the RBT-05 gate proves it does not regress the p95. The crash-isolation gate is a one-line extension of the *already-existing* `test_app_imports_nothing_heavy` (it must additionally block `numpy`, which today's test does not). Everything else (encode/resize/atomic-write/sidecar-serialize) is headless-unit-testable with an injected fake encoder — no real `cv2`/GPU needed off the rig.

**Two findings that de-risk Claude's-Discretion items immediately:** (1) **No frame `.copy()` is needed.** `NdiFrameSource._publish` stores the result of `cv2.cvtColor(...)` — a *freshly allocated* array each new frame; `ClipReplayFrameSource` publishes distinct injected arrays. Neither mutates a returned buffer in place. The mailbox holding a reference is safe (the next frame is a new object; the old reference stays valid). Anti-Pattern 5's "reused mutable buffer" does **not** apply to either current `FrameSource`. (2) **EMA-vs-raw score is NOT separately exposed.** `CameraScore.score` IS the smoothed (EMA) value; the raw per-tick score is internal to `CameraScorer` and not returned. Publish `score` as the EMA; if a separate raw value is wanted, that is a scorer change explicitly out of this phase's "no new scorer logic" boundary — treat the `ema` field as equal to `score` (or omit it) in Phase 7.

**Primary recommendation:** Build steps 1→2→3→4 in dependency order; gate step 4 on a `preview ON vs OFF, p95 delta within noise` comparison run through the *existing* `run_measured` harness; gate the sidecar+publisher on injected-fake headless unit tests; gate the console surface on the extended import test. Use a `threading.Lock` + 1-slot attribute mailbox, an in-sidecar `gen` cache-bust field (no `gen.txt`), and a single `atomic_write_bytes(path, data, *, fsync=True)`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Frame snapshot hand-off (tick→publisher) | Orchestrator (tick thread) | — | A non-blocking dict ref-assignment under a lock; must stay on the tick to capture the *current* frames, but pays only the assignment. |
| Resize / JPEG-encode | Orchestrator (PreviewPublisher daemon thread) | — | `cv2` already lives in the orchestrator process; encoding MUST be off the tick (Anti-Pattern 2). |
| Atomic binary write of `cam_<id>.jpg` | Orchestrator (publisher thread) | opcomm leaf (`atomic_write_bytes`) | Reuses the proven temp→`os.replace` primitive; stdlib-only, stays a leaf. |
| `preview.json` serialize + atomic write | Orchestrator (publisher thread) | opcomm leaf (`write_preview`) | Mirrors `write_status`; fsync KEPT (D-04). |
| Recent-cuts ring maintenance | Orchestrator (publisher/orchestrator side) | — | Fed from each tick's `Decision.target` change; serialized into the sidecar. |
| Reading `cam_<id>.jpg` / `preview.json` | Console (Flask + opcomm only) — **Phase 8, NOT now** | — | Phase 7 only WRITES the files; the console import surface is *locked* by the gate-2 test, not extended. |
| The "why" data (scores/bbox/state) | Already computed on the tick (Phase 2–4 brains) | — | Publish-and-render: nothing new is computed; v1.0 discards these and Phase 7 exposes them. |

## Standard Stack

**No new runtime dependencies.** [VERIFIED: codebase — `.planning/research/v1.1/STACK.md` + grep of `pyproject` deps] This phase adds *zero* packages.

### Core (all already present)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `opencv-python` (`cv2`) | 4.13.0.92 (already pinned, orchestrator side) | `cv2.resize` + `cv2.imencode(".jpg", frame, [IMWRITE_JPEG_QUALITY, q])` → numpy buffer → `.tobytes()` | Already imported in `NdiFrameSource._receiver_loop` (the orchestrator process). The console NEVER imports it. [CITED: STACK.md L45] |
| `numpy` | already present (orchestrator) | The BGR frame arrays the publisher resizes/encodes | Already a transitive orchestrator dep. The console must NOT import it — the gate-2 test blocks it. [CITED: STACK.md L33] |
| stdlib `os`/`json`/`threading`/`time`/`dataclasses` | — | `atomic_write_bytes`, `PreviewDoc`, the mailbox + daemon thread | Keeps `opcomm` a leaf (no heavy imports cross the lazy-import boundary). [VERIFIED: `atomic.py` header, read this session] |

### Supporting (Phase 8 only — NOT installed in Phase 7)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `waitress` | 3.0.2 | Windows production server for the console *once it serves a stream/long GET* | **Phase 8 deploy extra only** (optional `console`/`serve` extra, NOT a hard console dep). Out of Phase 7. [CITED: STACK.md L112] |

### Alternatives Considered (settled by D-01 — do not re-litigate)
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JPEG files in opcomm | MJPEG / WebSocket endpoint on the director | Puts a network server (threads, slowloris exposure) on the never-crash director — breaks D-03. Reject. [CITED: ARCHITECTURE §Option Comparison] |
| JPEG files in opcomm | OBS multiview embed | Requires the console to open obs-websocket (forbidden) or a Windows-only screen-share hack. Reject. |

**Installation:** None. (Documented per the output contract for completeness.)
```bash
# No new packages. cv2.imencode/numpy already present in the orchestrator; atomic_write_bytes is stdlib-only.
```

## Package Legitimacy Audit

> **Not applicable.** Phase 7 installs **zero** external packages. All capabilities use already-pinned, already-audited dependencies (`opencv-python`, `numpy`) and the Python standard library. No `npm view`/`pip index`/`cargo search` verification required because nothing is added.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Seam Verification (CONTEXT.md claims confirmed against the live code)

> This is the load-bearing section: CONTEXT.md asserts a set of named functions/classes/attributes exist as templates. Each was opened this session. **Result: zero drift.** Exact signatures below so the planner writes concrete actions.

| Claimed seam | File:line | Confirmed signature / shape | Notes for the planner |
|--------------|-----------|------------------------------|------------------------|
| `atomic_write_text` | `opcomm/atomic.py:82` | `def atomic_write_text(path: str, text: str) -> None` | Opens `"w"`, `f.write`, `f.flush()`, `os.fsync(f.fileno())`, `_atomic_replace(tmp, path)`. `atomic_write_bytes` is the `"wb"` sibling. |
| `_atomic_replace` | `opcomm/atomic.py:39` | `def _atomic_replace(tmp: str, path: str) -> None` | 50-retry loop on `PermissionError` w/ 1ms backoff (Windows MoveFileEx sharing-violation). Reuse VERBATIM. |
| `_temp_path` | `opcomm/atomic.py:55` | `def _temp_path(path: str) -> str` | Same-dir hidden `.<name>.tmp`. Reuse VERBATIM. |
| `__all__` | `opcomm/atomic.py:26` | `["atomic_write_json", "atomic_write_text"]` | **Action:** add `"atomic_write_bytes"`. |
| `DirectorStatus` | `opcomm/records.py:133` | `@dataclass(frozen=True)`; fields `live_cam: str="SAFE"`, `reason: str="none"`, `alive: dict=field(default_factory=dict)`; `__post_init__` normalizes `alive` to `{str(k): bool(v)}` via `object.__setattr__` | The EXACT template for `PreviewDoc`. Note `alive` is stored as a normalized dict (the docstring mentions a tuple, but the *code* stores a normalized dict — see L150-158; copy the dict-normalization trick). |
| `_read_json` | `opcomm/channel.py:40` | `def _read_json(path: str)` → dict/list or `None` on absent/empty/malformed; never raises | The single torn/absent boundary `read_preview` reuses. |
| `read_status`/`write_status` | `opcomm/channel.py:152,160` | `write_status(path, status)` serializes `{live_cam, reason, alive}`; `read_status(path)` returns `DirectorStatus()` default on any failure | EXACT template for `read_preview`/`write_preview`. |
| `Orchestrator._tick_once` | `orchestrator/loop.py:492` | `def _tick_once(self, tick: int, now: float, probe: dict | None = None) -> None`; `self._apply(decision, alive)` at L521 | **The guarded `offer()` goes immediately AFTER `self._apply(decision, alive)` (L521), still INSIDE the try (so a publisher fault coasts via the same RBT-04 catch at L534).** |
| `_fan_out` / `_batched_inference` | `loop.py:258,359` | `_batched_inference` builds `frames_by_cam = {cam.id: self.source.latest(cam.id) for cam in self.cameras}` at **L370**; `_fan_out` returns `(dets_by_cam, locked_energy)` | `frames_by_cam` exists in the batched path but is LOCAL to `_batched_inference`; `dets_by_cam` is returned by `_fan_out`. See §"Where the publisher pulls frames" for surfacing it cheaply. |
| `scores` | `loop.py:511` | `scores = self.scorer.update(dets_by_cam, tick)` → `list[CameraScore]` | Available in `_tick_once` after the scorer call. |
| `run` / `run_measured` / `shutdown` | `loop.py:565,590,628` | `run(rate_hz=30.0)`; `run_measured(n_ticks) -> dict` (the RBT-05 harness); `shutdown()` | `run`/`run_measured` start the source+OBS; `shutdown` joins teardown. Publisher start in `run`/`run_measured` startup, stop/join in `shutdown`. |
| RBT-04 coast pattern | `loop.py:534` | `except Exception as exc: ... self._to_safe(reason="fault", ...)` | Every stage already wrapped; the publisher `offer()` rides inside this same try. |
| `build_orchestrator` / `*_factory` | `orchestrator/runtime.py:114` | `build_orchestrator(config, channel_dir, *, fps=30.0, grace=None, source_factory=None, obs_factory=None, tracker_factory=None)` | **Action:** construct the `PreviewPublisher` here (guarded by `config.preview.enabled`); add a `preview_factory` injectable seam mirroring the existing `*_factory` pattern so headless tests inject a fake encoder. |
| `_channel_paths` | `runtime.py:68` | returns `{command, runstate, status, score, overlay}` (str paths under `channel_dir`) | **Action:** add a `preview` media dir key (e.g. `str(base / "preview")`) + the `preview.json` path. `os.makedirs(channel_dir, exist_ok=True)` at L161 — add a `makedirs(preview_dir, exist_ok=True)`. |
| `Orchestrator.__init__` | `loop.py:130` | takes `config, source, obs, scorer, engine, watchdog, action_hold, channel_paths, trackers` | **Action:** add an injected `preview=None` collaborator + store as `self._preview`. `from_config` (L181) + `build_orchestrator` pass it through. The `if self._preview is not None` guard (D-06) means a None publisher = byte-identical-to-v1.0. |
| `create_app` | `ui/app.py:60` | `def create_app(channel_dir: str)`; Flask imported INSIDE at L67 | Phase 7 does NOT touch this. The gate-2 test LOCKS the current import surface. |
| `FrameSource` Protocol | `ndi/source.py:32` | `start`/`latest(cam_id)->np.ndarray|None`/`last_frame_ts`/`stop` | The publisher consumes the `frames_by_cam` dict the tick already built, NOT a new `source.latest` call. |
| `NdiFrameSource.latest` | `ndi/ndi_source.py:367` | returns `self._latest.get(cam_id)`; `_publish` (L356) stores `bgr = cv2.cvtColor(arr, ...)` — a **NEW array per frame** | **Buffer-reuse RESOLVED: no in-place mutation; no `.copy()` needed.** See §"Frame-snapshot safety". |

## Architecture Patterns

### System Architecture Diagram

```
ORCHESTRATOR PROCESS (heavy: cv2/numpy/torch/cyndilib already imported)

  CRITICAL TICK (loop.py::_tick_once, RBT-05 budget)        PUBLISH (off the critical path)
  ┌──────────────────────────────────────────────┐         ┌──────────────────────────────────────────┐
  │ _fan_out → dets_by_cam, locked_energy         │         │ PreviewPublisher._run (own daemon thread)  │
  │ scorer.update → scores (list[CameraScore])    │         │  loop @ ~1/fps:                            │
  │ _decide → decision (Decision)                 │         │   grab+clear the 1-slot mailbox            │
  │ _apply → obs.cut + write_status (UNCHANGED)   │ offer() │   if None: sleep(period); continue         │
  │ ── ring.record(decision) on target change ──  │ ──────► │   try:                                     │
  │ if self._preview is not None:                 │ (1-slot │     for cam: cv2.resize → cv2.imencode(.jpg)│
  │    self._preview.offer(                       │  lock,  │       → atomic_write_bytes(cam_<id>.jpg,    │
  │       frames_by_cam, scores, dets_by_cam,     │  last-  │            fsync=False)   ◄ D-04 no fsync   │
  │       decision)                               │  wins,  │     build PreviewDoc(...)                   │
  │  (cost ≈ one locked tuple assignment)         │  drop-  │     write_preview(preview.json, doc)        │
  └──────────────────────────────────────────────┘  ok)    │            (fsync KEPT — D-04)              │
        │ writes status.json (D-11, byte-stable)            │   except Exception: logger.warning(coast)  │
        │                                                   │   sleep(period)                            │
        ▼                                                   └──────────────┬─────────────────────────────┘
   ── opcomm/ DIR (the ONLY coupling — atomic files) ──────────────────────┘ writes opcomm/preview/
   status.json  command.json  runstate.json  score.json  overlay.txt        ◄ existing, unchanged
   preview/cam_<id>.jpg × N   preview/preview.json                          ◄ NEW (Phase 7 writes them)
        ▲
   CONSOLE PROCESS (Flask + segugio.opcomm ONLY)  ── reads them in PHASE 8, not Phase 7. ──
```

### Recommended Project Structure (the delta)
```
src/segugio/
├── opcomm/
│   ├── atomic.py        # + atomic_write_bytes(path, data, *, fsync=True)   (NEW fn, +__all__)
│   ├── records.py       # + PreviewDoc frozen record                         (NEW)
│   └── channel.py       # + write_preview / read_preview                     (NEW)
├── orchestrator/
│   ├── preview.py       # PreviewPublisher: mailbox + daemon + resize/encode/atomic-write + ring (NEW)
│   ├── loop.py          # + self._preview, guarded offer() after _apply, ring.record on cut (MODIFIED)
│   └── runtime.py       # + preview_factory seam, construct publisher (guarded), preview/ dir (MODIFIED)
├── config/
│   └── models.py        # + PreviewParams sub-model + Config.preview field   (MODIFIED, additive)
└── (ui/app.py UNCHANGED — gate-2 test locks its import surface)
```

### Pattern 1: Latest-only single-slot mailbox (tick → publisher hand-off)
**What:** The tick writes `(frames_by_cam, scores, dets_by_cam, decision)` into a 1-slot attribute under a short lock; the publisher reads-and-clears on its own clock. Last-writer-wins; the tick never waits.
**When to use:** Producer (30 Hz, latency-critical) must not be throttled by consumer (~5 fps encode+disk).
**Recommendation (Claude's Discretion resolved):** **`threading.Lock` + 1-slot attribute**, NOT `queue.Queue(maxsize=1)`. Rationale: the Lock form is a 2-line `with self._lock: self._latest = item` on the producer and `with self._lock: item, self._latest = self._latest, None` on the consumer — zero allocation, no `except queue.Full` control-flow, and trivially headless-testable by calling `offer()` then `_drain()` directly. (Both are correct; the Lock form is marginally cheaper on the hot side and clearer to unit-test.) [VERIFIED: ARCHITECTURE Pattern 1 §code]
```python
# orchestrator/preview.py
def offer(self, frames, scores, dets, decision):
    with self._lock:
        self._latest = (frames, scores, dets, decision)   # overwrite previous, last-wins, never blocks

def _drain(self):
    with self._lock:
        item, self._latest = self._latest, None
    return item

def _run(self):                                            # own daemon thread
    while not self._stop.is_set():
        item = self._drain()
        if item is None:
            time.sleep(self._period); continue
        try:
            self._publish(*item)                           # resize → imencode → atomic_write_bytes + write_preview
        except Exception as exc:                           # RBT-04: an encode/IO fault coasts
            logger.warning("preview publish coasted: {}", exc)
        time.sleep(self._period)                           # ~1/fps cap
```

### Pattern 2: Atomic binary publish (reuse the proven primitive, fsync seam)
**What:** Each JPEG via the same temp-in-same-dir → (optional fsync) → `os.replace` dance, routed through the SAME `_atomic_replace` retry. **Recommendation (Claude's Discretion resolved):** ONE function with an `fsync: bool = True` param — the publisher passes `fsync=False` for the disposable JPEGs (D-04) and the default `True` for `preview.json`. Document the fsync-drop rationale inline (D-04 STATE.md carry-forward — so it is never silently reverted).
```python
# opcomm/atomic.py  (mirror of atomic_write_text; the ONLY new behavior is the fsync gate)
def atomic_write_bytes(path: str, data: bytes, *, fsync: bool = True) -> None:
    """Write raw bytes to ``path`` atomically (temp → optional fsync → os.replace).

    fsync gate (D-04): pass ``fsync=False`` for the ephemeral preview JPEGs — they are
    regenerated every frame, so durability does not matter and skipping fsync removes a few ms
    of disk time on the publisher thread. KEEP the default ``fsync=True`` for preview.json (a
    torn/old sidecar would mislead the console). The Windows MoveFileEx sharing-violation race
    against the console reader is covered by _atomic_replace's retry, INDEPENDENT of fsync.
    DO NOT silently re-enable fsync for the JPEGs — this drop is a deliberate decision.
    """
    tmp = _temp_path(path)
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        if fsync:
            os.fsync(f.fileno())
    _atomic_replace(tmp, path)   # Windows: MoveFileEx + retry, same volume
```

### Pattern 3: Sidecar typed record (`PreviewDoc`), modeled byte-for-byte on `DirectorStatus`
**What:** A NEW `preview.json` carrying the full "why" payload as its own atomic file, frozen + normalizing `__post_init__` + a safe-default `read_preview` that never raises. **`status.json` stays exactly as-is.** See §"PreviewDoc Shape" for the concrete fields.

### Anti-Patterns to Avoid (verified against this codebase)
- **Encoding on the tick thread (Anti-Pattern 2):** never `cv2.imencode` inside `_tick_once`. The tick pays only the `offer()` lock-assignment. [The RBT-05 gate is the enforcement.]
- **Console importing cv2/numpy (Anti-Pattern 1):** the console only `send_file`s bytes (Phase 8). Phase 7 keeps `ui/app.py` untouched; the gate-2 test locks it.
- **Bloating `status.json` (Anti-Pattern 3):** all per-tick "why" data goes in the SIDECAR. `DirectorStatus`/`write_status` are NOT modified.
- **Reusing a mutable frame buffer (Anti-Pattern 5):** **does not apply to either current FrameSource** (both allocate fresh arrays). See §"Frame-snapshot safety". If a *future* source reuses buffers, `.copy()` in `offer()`.
- **Per-tick sidecar rewrite competing with status.json:** the publisher writes `preview.json` on ITS clock (~5 fps), not every 30 Hz tick — independent atomic swaps, no contention with the write-on-change `status.json`.

## The "why" payload — where each field already exists (D-07)

> Confirms PRV-02 is pure publish-and-render: every field is computed on the tick today and discarded. The planner can write a concrete `offer()`→`PreviewDoc` mapping from this table.

| `preview.json` field (per camera) | Source on the tick | Confidence |
|-----------------------------------|--------------------|------------|
| `score` (smoothed/EMA) | `scores: list[CameraScore]` (`loop.py:511`), `CameraScore.score` — **this is already the EMA** (`framing/signals.py:65`) | [VERIFIED: signals.py read this session] |
| `ema` | **= `score`** — the raw per-tick score is internal to `CameraScorer` and NOT returned. Publishing a separate raw value would require a scorer change (OUT of Phase 7's "no new scorer logic" boundary). Set `ema == score` or omit. | [VERIFIED: scorer returns only the smoothed value] |
| `state` (tracking/coast/lost) | `CameraScore.status` → `ScorerStatus` enum (`tracking`/`coasting`/`lost`) | [VERIFIED: `framing/signals.py:28`] |
| `locked` (bool) + `track_id` | per-camera `CompetitorLock.locked_id` (`competitor_lock.py:75`); `dets_by_cam[cam_id]` is the selected `DetectionSignal | None` (carries `track_id`) | [VERIFIED: `loop.py:301` + `competitor_lock.py`] |
| `energy` (motion) | `locked_motion_energy()` is the MAX across cameras in `_fan_out`; **per-camera** energy is `self.locks[cam_id].locked_motion_energy()` (`competitor_lock.py:110`) — call per camera in the publisher (cheap, pure read) OR surface the per-cam value from `_fan_out`. | [VERIFIED] |
| `box` `[cx,cy,w,h]` normalized | `dets_by_cam[cam_id]` (the gated `DetectionSignal | None`) carries normalized `cx,cy,w,h` (`framing/signals.py:42`) — `None` when nothing detected → `box: null` | [VERIFIED] |
| `in_zone` (bool) | derivable from `dets_by_cam[cam_id] is not None` after the plausibility gate (a gated detection that survived `_in_any_zone`); OR expose `CompetitorLock`'s in-field state. For Phase 7, `in_zone = dets_by_cam[cam_id] is not None` is a sound approximation. | [ASSUMED — A1] |
| top-level `auto_candidate` (FSM) | `decision.target` from `_decide` (`loop.py:518`) — the camera the FSM WANTS this tick (a camera id or `"SAFE"`). The live-aired cam is in `status.json`; the auto-candidate is what auto would pick (same value unless overridden). | [VERIFIED: `Decision.target`, `signals.py:53`] |
| top-level `gen` (cache-bust) | a monotonic int the publisher bumps each publish | [design] |
| `cuts` ring (depth ~16) | each tick where `decision.target` changed (`_apply` already detects status change), record `{tick, from, to, reason}` | [VERIFIED: change-detection exists at `loop.py:468`/`485`] |

**Cuts-ring feed mechanism (recommendation):** the ring is best maintained on the **orchestrator side** and passed into `offer()` (or the publisher reads it from a shared ref), because the *cut event* (target change) is detected in `_apply`/`_status_for` on the tick, not on the publisher's slower clock (the publisher would miss intermediate cuts between two drains). Concretely: keep a `collections.deque(maxlen=16)` on the Orchestrator; append `{tick, from, to, reason}` in `_apply` exactly when `status != self._last_status` AND the `live_cam`/target changed; pass a snapshot (`list(ring)`) into `offer()`. This captures EVERY cut even when preview frames drop. [VERIFIED: the change-edge already exists at `loop.py:468`]

## PreviewDoc Shape (concrete, modeled on `DirectorStatus`)

```python
# opcomm/records.py  (mirror DirectorStatus EXACTLY: frozen, normalizing __post_init__, dict-normalized)
@dataclass(frozen=True)
class PreviewDoc:
    """Per-camera 'why' snapshot the console renders (camera live + perché). Sidecar to status.json.

    Mirrors DirectorStatus: frozen (hashable + ==-comparable so round-trip equality tests work),
    a normalizing __post_init__ that coerces the nested dicts to str-keyed normalized form (so two
    PreviewDocs with the same content compare equal regardless of dict insertion order), and a
    safe-default reader (read_preview) that NEVER raises into the loop (RBT-04). Carries the FULL
    D-07 payload so Phases 8/9 are pure render — this contract is not reopened later.
    """
    tick: int = 0
    gen: int = 0                                  # monotonic cache-bust token (console ?t=<gen>)
    auto_candidate: str = "SAFE"                  # decision.target — the cam auto WANTS this tick
    cams: dict = field(default_factory=dict)      # {cam_id: {"score": float, "ema": float,
                                                  #   "state": "tracking"|"coasting"|"lost",
                                                  #   "locked": bool, "track_id": int|None,
                                                  #   "energy": float, "in_zone": bool,
                                                  #   "box": [cx,cy,w,h] | None}}
    cuts: tuple = ()                              # recent-cuts ring, newest-last, depth ~16:
                                                  #   ({"tick": int, "from": str, "to": str, "reason": str}, ...)

    def __post_init__(self) -> None:
        # Normalize cams to str-keyed dicts (mirror DirectorStatus.alive normalization, L150-158).
        cams = self.cams if isinstance(self.cams, dict) else dict(self.cams)
        object.__setattr__(self, "cams", {str(k): dict(v) for k, v in cams.items()})
        # Normalize cuts to a tuple of dicts (immutable → the frozen dataclass stays hashable).
        object.__setattr__(self, "cuts", tuple(dict(c) for c in self.cuts))
```

**Hashability / round-trip-equality requirements:**
- `cams` and `cuts` MUST be normalized to immutable-by-convention forms in `__post_init__` (str keys; `cuts` a tuple) so two `PreviewDoc`s with identical content compare `==` regardless of insertion order — this is the determinism contract the `read_preview(write_preview(doc)) == doc` round-trip test relies on (exactly the `DirectorStatus`/status-channel test pattern). [VERIFIED: `records.py:150` + `test_status_channel.py`]
- **Note on float round-trip:** JSON serializes floats losslessly enough for `==` of Python floats that came from the same source, but if the round-trip test is strict, cast all numeric fields with `float()` at construction (the `CameraScore` convention — `signals.py` casts every numeric to `float`). The planner should mirror that cast in the `cams` dict builder.

**`read_preview`/`write_preview` (mirror `read_status`/`write_status`):**
```python
# opcomm/channel.py
def write_preview(path: str, doc: PreviewDoc) -> None:
    atomic_write_json(path, {                      # fsync KEPT (atomic_write_json always fsyncs)
        "tick": doc.tick, "gen": doc.gen, "auto_candidate": doc.auto_candidate,
        "cams": doc.cams, "cuts": [dict(c) for c in doc.cuts],
    })

def read_preview(path: str) -> PreviewDoc:
    data = _read_json(path)                         # absent/torn/malformed → None (never raises)
    if not isinstance(data, dict):
        return PreviewDoc()                         # empty safe default
    try:
        return PreviewDoc(
            tick=int(data.get("tick", 0)), gen=int(data.get("gen", 0)),
            auto_candidate=data.get("auto_candidate", "SAFE"),
            cams=data.get("cams", {}) if isinstance(data.get("cams"), dict) else {},
            cuts=tuple(data.get("cuts", ()) or ()),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid PreviewDoc at {} → default ({})", path, exc)
        return PreviewDoc()
```
> **Important:** `write_preview` uses the existing `atomic_write_json` (which always fsyncs) — that satisfies D-04 "keep fsync for preview.json" for free. The new `atomic_write_bytes(fsync=False)` is ONLY for the JPEGs. The planner should NOT route `preview.json` through `atomic_write_bytes`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic crash-safe file write on Windows | A custom write-then-rename with your own retry | `_temp_path` + `_atomic_replace` (reuse via `atomic_write_bytes`) | The MoveFileEx sharing-violation 50-retry/1ms-backoff is already tuned and proven against OBS/console readers. [VERIFIED: `atomic.py:39`] |
| Torn/absent/malformed JSON read boundary | A bespoke try/except in the publisher/console | `_read_json` (reuse in `read_preview`) | The single boundary that absorbs every read failure to a safe default; mirrors `read_status`. [VERIFIED: `channel.py:40`] |
| Frozen, ==-comparable, normalized record | A plain dict or a hand-rolled `__eq__` | The `DirectorStatus` `@dataclass(frozen=True)` + `__post_init__` pattern | Gives hashability + round-trip equality for free; the round-trip test depends on it. [VERIFIED: `records.py:133`] |
| JPEG encode | A manual encoder or `PIL` (new dep) | `cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, q])` | Already present; returns a numpy buffer → `.tobytes()`. No new dep. [CITED: STACK.md] |
| A latency-measurement harness | A new timing script | The existing `run_measured` / `test_latency.py` | Gate 1 RE-RUNS the existing harness with preview ON vs OFF — do not invent a parallel measurement. [VERIFIED: `test_latency.py`] |
| A crash-isolation test | A new env-stripping subprocess | Extend the existing `test_app_imports_nothing_heavy` (`test_ui_score.py:105`) | The `monkeypatch.setitem(sys.modules, heavy, None)` block already exists; just add `numpy`. [VERIFIED] |

**Key insight:** Phase 7 hand-rolls *nothing* — every primitive (atomic write, safe read, frozen record, JPEG encode, latency harness, import test) already exists. The work is composition and one new daemon thread.

## Runtime State Inventory

> **Not a rename/refactor/migration phase.** This is an additive feature phase (new files + additive config + one guarded hot-path call). No stored data, live-service config, OS-registered state, secrets/env vars, or build artifacts carry a renamed string. **None — verified by: this phase adds new symbols (`atomic_write_bytes`, `PreviewDoc`, `PreviewPublisher`, `PreviewParams`) and an additive `Config.preview` field; it renames nothing and migrates no datastore.** One operational note (not state-migration): a fresh `python -m segugio` run must `os.makedirs(opcomm/preview, exist_ok=True)` before the first publish — the same dir-creation defensiveness `build_orchestrator` already applies to `channel_dir` (`runtime.py:161`).

## Common Pitfalls

### Pitfall 1: Encoding on the tick (busts RBT-05)
**What goes wrong:** `cv2.imencode` + writes added inside `_tick_once` add tens of ms/tick.
**Why it happens:** It "feels simpler" to encode where the frames are.
**How to avoid:** The tick only `offer()`s; all encode/IO on the daemon. The RBT-05 gate (preview ON vs OFF) is the enforcement.
**Warning signs:** `run_measured` p95 climbs with preview ON; the `yolo`/`obs` stage timings inflate.
[VERIFIED: ARCHITECTURE Anti-Pattern 2 + PITFALLS Pitfall 1]

### Pitfall 2: The console importing cv2/numpy (busts gate 2 / RBT-04 isolation)
**What goes wrong:** A "just JPEG-encode in the console" shortcut imports a heavy dep into the Flask process.
**How to avoid:** Phase 7 does NOT modify `ui/app.py`. The gate-2 test blocks `numpy` AND `cv2` (today's test blocks cv2 but NOT numpy — **add numpy**) and asserts `import segugio.ui.app` still resolves.
**Warning signs:** The import test passes only because numpy happens to be installed; force it absent.
[VERIFIED: `test_ui_score.py:118` blocks `cv2` but not `numpy`]

### Pitfall 3: Wrong fsync posture / silently re-enabling fsync on JPEGs
**What goes wrong:** A later refactor "tidies" `atomic_write_bytes` to always fsync, adding disk time to every JPEG write 5×/s × 4 cams.
**How to avoid:** Document the `fsync=False`-for-JPEGs decision IN the function (D-04). A test asserts the publisher calls `atomic_write_bytes(..., fsync=False)` for JPEGs (inject a spy).
**Warning signs:** Publisher-thread CPU/disk climbs; opcomm dir IO-thrashes on slow/network storage.
[VERIFIED: D-04 + PITFALLS Pitfall 5]

### Pitfall 4: The mailbox blocking the tick
**What goes wrong:** Using a bounded `Queue.put()` (blocking) or a contended lock held during encode.
**How to avoid:** The lock is held ONLY for the tuple assignment/swap — never during encode/IO. Last-writer-wins; frame-drop allowed.
**Warning signs:** The `offer()` shows up in the RBT-05 probe; tick jitter under load.
[VERIFIED: ARCHITECTURE Pattern 1]

### Pitfall 5: Cuts ring maintained on the publisher (misses dropped cuts)
**What goes wrong:** The publisher only sees the *latest* mailbox state ~5×/s; two cuts between drains are lost from the history.
**How to avoid:** Maintain the ring on the ORCHESTRATOR (append on the tick's target-change edge in `_apply`); pass a snapshot into `offer()`.
**Warning signs:** Phase 9's switch-history strip shows fewer cuts than actually aired.
[VERIFIED: the change-edge is at `loop.py:468`]

## Frame-snapshot safety (Claude's Discretion — RESOLVED)

**Finding: no `.copy()` is required for either current `FrameSource`.**

- **`NdiFrameSource`** (`ndi_source.py:328,334,356,367`): `_publish(cam_id, bgr, ts)` stores `bgr`, which is the return of `cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)` — a **freshly allocated array each new frame**. `latest()` returns `self._latest.get(cam_id)`. When the next new frame arrives, `_publish` *rebinds* `self._latest[cam_id]` to a new array; it does NOT mutate the old one in place. A reference captured by the mailbox stays valid. [VERIFIED]
- **`ClipReplayFrameSource`** (`clip_source.py:117`): publishes distinct injected `(tick, {cam_id: frame})` arrays; each `latest()` returns a distinct object. No in-place reuse. [VERIFIED]

**Conclusion:** Anti-Pattern 5's "reused mutable buffer" risk does not apply today. The mailbox can hold the array reference directly. **Defensive recommendation for forward-safety:** document this assumption in `PreviewPublisher` (it depends on the `FrameSource` contract returning a fresh array per frame), and IF a future `FrameSource` is added that reuses a buffer, add `.copy()` in `offer()` (a cheap memcpy vs YOLO). Do NOT add `.copy()` now — it is wasted work against the current sources. [VERIFIED + ASSUMED forward-note A2]

## Where the publisher pulls frames (Claude's Discretion — RESOLVED)

`_batched_inference` builds `frames_by_cam = {cam.id: self.source.latest(cam.id) for cam in self.cameras}` at `loop.py:370` but it is LOCAL to that method. The serial path (`_serial_inference`) pulls `self.source.latest(cam_id)` per camera inside its loop without surfacing a dict.

**Recommendation:** have `_fan_out` (or the inference helpers) return `frames_by_cam` alongside `(dets_by_cam, locked_energy)`, so `_tick_once` has the exact dict the tick already pulled — **no duplicate `source.latest()` calls** (a second pull could return a *different* frame than the one inference ran on, and costs another lock acquisition). Concretely: `_batched_inference` already has the dict (return it); `_serial_inference` should accumulate `frames_by_cam[cam_id] = frame` in its loop and return it too. Then `_fan_out` returns `(dets_by_cam, locked_energy, frames_by_cam)` and `_tick_once` passes `frames_by_cam` to `offer()`. This keeps the published thumbnail consistent with the frame inference actually saw. [VERIFIED: `loop.py:352,370`]

## Cache-bust token (Claude's Discretion — RESOLVED)

**Recommendation: reuse an in-sidecar `gen` field; do NOT add a separate `gen.txt`.** The console (Phase 8) reads `preview.json` anyway for the "why" data, so the `gen` int is free there for the `?t=<gen>` image cache-bust — one fewer file to write, atomic-swap, and read. The ARCHITECTURE diagram shows a `gen.txt` option but explicitly allows the in-sidecar token ("Prefer the in-sidecar token if it avoids an extra file" — CONTEXT.md D-discretion). Bump `gen` once per publish. [VERIFIED: CONTEXT.md discretion + ARCHITECTURE]

## PreviewParams config placement (Claude's Discretion — RESOLVED)

Mirror `ScorerParams`/`TrackingParams`/`ActionHoldParams` exactly: a `BaseModel` with `ConfigDict(extra="forbid")`, bounded `Annotated[..., Field(...)]` seeds, added to `Config` via `Field(default_factory=...)` so existing `extra="forbid"` YAML without a `preview:` block still validates.

```python
# config/models.py  (additive — existing configs without `preview:` still validate)
class PreviewParams(BaseModel):
    """Off-tick preview publish defaults (D-05). Additive: omitting `preview:` keeps these defaults.
    Phase 8 owns the HARD bandwidth cap; these are the starting fidelity seeds."""
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True                                              # D-06: ON by default
    fps: Annotated[float, Field(gt=0.0, le=30.0)] = 5.0              # ~5 fps publish cadence
    max_width: Annotated[int, Field(ge=64, le=1920)] = 384          # downscale target width (px)
    jpeg_quality: Annotated[int, Field(ge=1, le=100)] = 55          # cv2 IMWRITE_JPEG_QUALITY

# in Config:
    preview: PreviewParams = Field(default_factory=PreviewParams)
```
[VERIFIED: `framing/params.py` + `config/models.py:128` ActionHoldParams pattern]

## Code Examples (composition, from verified seams)

### Wiring the publisher in `build_orchestrator` (guarded by `preview.enabled`)
```python
# orchestrator/runtime.py  (additive — mirrors the *_factory pattern)
def _default_preview_factory(preview_params, preview_dir, cameras):
    from .preview import PreviewPublisher          # cv2 imported lazily INSIDE its publish method
    return PreviewPublisher(preview_params, preview_dir, [c.id for c in cameras])

def build_orchestrator(config, channel_dir, *, ..., preview_factory=None):
    ...
    os.makedirs(channel_dir, exist_ok=True)
    preview_dir = str(Path(channel_dir) / "preview")
    os.makedirs(preview_dir, exist_ok=True)        # same defensiveness as channel_dir (L161)
    preview = None
    if config.preview.enabled:                      # D-06: byte-identical-to-v1.0 when disabled
        preview_factory = preview_factory or _default_preview_factory
        preview = preview_factory(config.preview, preview_dir, config.cameras)
    return Orchestrator.from_config(..., preview=preview)
```

### The guarded offer() in `_tick_once` (the ONLY hot-path touch)
```python
# orchestrator/loop.py  — inside _tick_once, immediately AFTER self._apply(decision, alive) at L521,
# still INSIDE the try (so a publisher fault coasts via the existing RBT-04 catch at L534).
self._apply(decision, alive)
t_obs = time.perf_counter()
if self._preview is not None:                                    # D-06 guard
    self._preview.offer(frames_by_cam, scores, dets_by_cam, decision, cuts=list(self._cuts_ring))
```
> `frames_by_cam` comes from `_fan_out` (see §"Where the publisher pulls frames"); `self._cuts_ring` is the orchestrator-side `deque(maxlen=16)` appended in `_apply` on a target change.

### Publisher lifecycle in run / run_measured / shutdown
```python
# in Orchestrator.run and run_measured, after _safe_startup(...):  (mirror the _safe_startup coast)
if self._preview is not None:
    self._safe_startup("preview.start", self._preview.start)     # starts the daemon thread
# in shutdown(), before/after source.stop():
if self._preview is not None:
    try: self._preview.stop()                                    # set stop event + join the daemon
    except Exception as exc: logger.warning("preview.stop coasted: {}", exc)
```
> **Gate-1 nuance:** `run_measured` drives the loop deterministically (tick-derived `now`). Starting the publisher daemon during `run_measured` is what makes the RBT-05 "preview ON" comparison real — the daemon competes for the GIL/CPU exactly as in production. The OFF run uses a config with `preview.enabled=False` (no publisher).

## State of the Art

| Old Approach (v1.0) | Phase 7 Approach | When Changed | Impact |
|--------------------|------------------|--------------|--------|
| Decoded frames + scores + bbox + decision discarded after the tick | Exposed over a binary atomic channel + typed sidecar, off-tick | Phase 7 (v1.1) | The console can SEE + understand (Phases 8/9 render); the director is provably untouched |
| `status.json` is the only reverse channel | `status.json` UNCHANGED + a new `preview.json` sidecar | Phase 7 | Safety-critical channel stays byte-stable; cosmetic always-changing data isolated |
| opcomm writes are text/JSON only | `atomic_write_bytes` adds binary writes (fsync-optional) | Phase 7 | Reuses the proven primitive; JPEGs skip fsync (disposable) |

**Deprecated/outdated:** none introduced. (The SUMMARY's note that the cuts ring lives in `DirectorStatus` is **superseded** by ROADMAP criterion 4 / D-03 / D-07: the ring lives in `preview.json`. Do not add cuts to `DirectorStatus`.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `in_zone` ≈ `dets_by_cam[cam_id] is not None` (a detection that survived the plausibility/zone gate) | "why" payload | LOW — if a distinct in-zone-but-not-locked flag is wanted later, surface it from `CompetitorLock._in_any_zone`; the field is renderer-only (Phase 9), so an approximation now is safe. Flag for the planner to confirm the exact semantics with the user if Phase 9 needs strict in-zone. |
| A2 | No future `FrameSource` reuses a mutable buffer within Phase 7's lifetime | "Frame-snapshot safety" | LOW — both current sources allocate fresh arrays (VERIFIED); the note is forward-defensive only. |
| A3 | The RBT-05 "within noise" band can be expressed as a fixed tolerance (e.g. p95 delta ≤ a few % or ≤ a few ms) on the GPU rig | "Validation Architecture" gate 1 | MEDIUM — the exact noise band is empirical; the planner should express the gate as "preview-ON p95 ≤ preview-OFF p95 + measured run-to-run jitter" and let the on-rig verifier set the numeric tolerance from back-to-back OFF/OFF runs first. |

**Note:** A3 is the most consequential — the gate is HARD but "within noise" is inherently empirical. The recommended concrete form is below in Validation Architecture.

## Open Questions

1. **What is the exact RBT-05 "within noise" tolerance for gate 1?**
   - What we know: `run_measured` returns per-tick `total` timings; `_p95` (`test_latency.py:26`) computes nearest-rank p95; the GPU test asserts `< 300ms`.
   - What's unclear: the run-to-run p95 variance on the RTX 4000 Ada (the "noise band").
   - Recommendation: the plan's gate-1 task FIRST measures two back-to-back preview-OFF runs to establish the jitter band, THEN asserts preview-ON p95 ≤ preview-OFF p95 + that band. Do not hardcode a magic number; derive it on the rig. This is the single human-verifiable acceptance on the GPU.

2. **Does the gate-2 import test need to also assert the console *starts* (not just imports)?**
   - What we know: ROADMAP criterion 2 says "`import segugio.ui` resolves AND the console starts."
   - Recommendation: extend the existing import test to ALSO call `create_app(tmp_dir)` under the heavy-absent block and assert it returns an app (a Flask test client GET `/status` works) — proving the console *starts* with the heavy stack absent, not merely imports.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `cv2` (opencv-python) | publisher resize/encode (orchestrator side) | ✓ (orchestrator venv) | 4.13.0.92 | — (headless tests inject a fake encoder; no cv2 needed off-rig) |
| `numpy` | frame arrays (orchestrator side) | ✓ | present | — |
| GPU / CUDA + ultralytics/torch | gate-1 RBT-05 GPU test only (`@pytest.mark.gpu`) | ✓ on the rig (`venv312/`) | per MEMORY.md cu126 | gate-1 is gpu-marked and SKIPPED off-rig; headless mock-timed wiring test always runs |
| (no new external services) | — | — | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** the GPU rig is only needed for the gate-1 latency assertion (gpu-marked, auto-skipped headless — `conftest.py:31`); all sidecar/encode/mailbox logic is headless-testable with an injected fake encoder.

## Validation Architecture

> nyquist_validation is enabled (`config.json: workflow.nyquist_validation: true`). This section enumerates observable signals → test seam → measurable pass for each PRV requirement and each of the 5 ROADMAP success criteria.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (existing; see `tests/`) |
| Config file | none custom — `tests/conftest.py` (fixtures) + `tests/conftest_tracking.py` (gpu/ndi/obs gate logic) |
| Quick run command | `pytest tests/test_atomic_io.py tests/test_status_channel.py -x` (the headless opcomm + new sidecar/mailbox/encode unit tests) |
| Full suite command | `pytest` (headless); `pytest -m gpu` on the rig for the latency gate |
| GPU-marker split | `@pytest.mark.gpu` auto-skips off-rig via `conftest.py:31` `pytest_collection_modifyitems` |

### Phase Requirements → Test Map
| Req / Criterion | Behavior | Test Type | Automated Command | File Exists? |
|-----------------|----------|-----------|-------------------|-------------|
| PRV-03 / SC2 | `import segugio.ui.app` resolves AND `create_app` starts with `ultralytics/torch/numpy/cv2/cyndilib` forced absent | unit (import) | `pytest tests/test_ui_score.py::test_app_imports_nothing_heavy` (EXTEND: add `numpy`; add a `create_app(tmp)` + GET `/status` start-check) | ✅ exists — EXTEND (add numpy + start check) |
| PRV-03 / SC3 | `atomic_write_bytes` writes bytes via temp→replace, no torn read; `fsync=False` skips fsync, `fsync=True` fsyncs | unit | `pytest tests/test_atomic_io.py -k bytes` (NEW cases in the existing file) | ❌ Wave 0 — add `atomic_write_bytes` cases to `test_atomic_io.py` |
| PRV-02 / SC4 | `PreviewDoc` round-trips (`read_preview(write_preview(doc)) == doc`); malformed/absent → default `PreviewDoc()` never raises; `cams`/`cuts` normalized for `==` | unit | `pytest tests/test_preview_channel.py` (NEW, mirror `test_status_channel.py`) | ❌ Wave 0 — new file mirroring the status-channel test |
| PRV-02 | The "why" mapping: given fake `scores`/`dets_by_cam`/`decision`, `PreviewPublisher` produces a `PreviewDoc` with the right per-cam fields + auto_candidate + cuts ring | unit (injected fake encoder) | `pytest tests/test_preview_publisher.py -k payload` | ❌ Wave 0 — new file |
| PRV-01 | Mailbox: `offer()` never blocks; last-writer-wins; `_drain()` returns the latest then `None` | unit | `pytest tests/test_preview_publisher.py -k mailbox` | ❌ Wave 0 |
| PRV-01 / SC5 | A publisher encode/IO fault COASTS (logged, no raise) and does not perturb the tick (RBT-04 extended) — inject an encoder that raises | unit | `pytest tests/test_preview_publisher.py -k coast` + an orchestrator-level `tests/test_fault_isolation.py` case where `offer`/publish raises and the tick still completes | ❌ Wave 0 — new publisher test + extend `test_fault_isolation.py` |
| PRV-01 / SC1 | **HARD GATE 1:** RBT-05 4-cam p95 unchanged within noise with preview ON | gpu (sustained) | `pytest -m gpu tests/test_latency.py` — add a `test_loop_latency_p95_preview_on_no_regression` that runs `run_measured` with `preview.enabled=True` (real `PreviewPublisher`) vs `False`, asserts `p95_on ≤ p95_off + noise_band` | ❌ Wave 0 — new gpu test alongside the existing one |
| SC3 | Real-run smoke: `python -m segugio <config>` writes `opcomm/preview/cam_<id>.jpg` + `preview.json` (files observable on disk) | integration (headless, fake encoder) OR manual on-rig | `pytest tests/test_orchestrator_runtime.py -k preview_files` (headless w/ injected `preview_factory` writing real bytes to tmp via a fake encoder) | ❌ Wave 0 — extend runtime test |
| SC4 | `status.json`/`DirectorStatus` byte-stable (NOT modified) — regression | unit | `pytest tests/test_status_channel.py` (existing — must stay green; `DirectorStatus` unchanged) | ✅ exists — regression guard |

### Sampling Rate
- **Per task commit:** `pytest tests/test_atomic_io.py tests/test_preview_channel.py tests/test_preview_publisher.py -x` (the headless preview surface — fast, no GPU)
- **Per wave merge:** `pytest` (full headless suite — proves no regression to opcomm/loop/runtime/ui)
- **Phase gate:** full headless suite green + `pytest -m gpu tests/test_latency.py` green on the rig (gate 1) + the extended import test green with `numpy` blocked (gate 2)

### Wave 0 Gaps
- [ ] `tests/test_preview_channel.py` — `PreviewDoc` round-trip + malformed→default (mirror `test_status_channel.py`), covers PRV-02/SC4
- [ ] `tests/test_preview_publisher.py` — mailbox non-block/last-wins, the "why" payload mapping, encode-fault coast (inject fake encoder), covers PRV-01/SC5
- [ ] `test_atomic_io.py` — add `atomic_write_bytes` cases (bytes round-trip; `fsync` param spy), covers PRV-03/SC3
- [ ] `test_latency.py` — add the preview-ON-vs-OFF gpu regression test, covers SC1 (gate 1)
- [ ] `test_ui_score.py::test_app_imports_nothing_heavy` — add `numpy` to the blocked set + a `create_app` start-check, covers SC2 (gate 2)
- [ ] `test_orchestrator_runtime.py` and/or `test_fault_isolation.py` — preview-files-written smoke + publisher-fault-coast at the orchestrator level
- [ ] Framework install: none — `pytest` + fixtures already present.

## Security Domain

> `security_enforcement` is not explicitly `false` in config — treat as enabled. Phase 7 is WRITE-only (the orchestrator writes files); the read/serve side (the path-traversal-sensitive `GET /preview/<cam>.jpg`) is **Phase 8**, NOT this phase. So most input-validation controls are Phase 8's.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | partial | `PreviewParams` is pydantic-validated (`extra="forbid"`, bounded fields) — a bad fidelity value fails at config-load, never at publish time. The `cam_id` keys written into filenames come from the validated `Config.cameras` (server-controlled, never operator input) — no traversal surface in Phase 7. |
| V6 Cryptography | no | No crypto. (JPEGs are disposable, non-sensitive within the LAN trust boundary.) |
| V2/V3/V4 Auth/Session/Access | no (Phase 7) | The `0.0.0.0` no-auth LAN exposure + the "live competitor video behind the endpoint" threat re-evaluation are **Phase 8** (the console SERVES the frames there). Phase 7 only writes files into the opcomm dir. |

### Known Threat Patterns for this phase
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via a crafted cam id in a filename | Tampering | Filenames use validated `Config.cameras[].id` (server-side), never operator input. The console-side whitelist on `<cam>` is **Phase 8** (the route does not exist yet). [VERIFIED: cam ids come from validated Config] |
| Torn/partial read of `cam_<id>.jpg` / `preview.json` by a concurrent reader | Tampering / DoS-of-correctness | The same temp→`os.replace`→MoveFileEx-retry atomicity the whole channel relies on; `read_preview` safe-defaults on any malformed read. [VERIFIED: `atomic.py` + `_read_json`] |
| Publisher fault crashing the director | Denial of Service (the never-crash invariant) | RBT-04 coast: every publish wrapped in `except Exception: logger.warning`; the `offer()` rides inside the tick's existing RBT-04 try. [VERIFIED: `loop.py:534`] |

## Sources

### Primary (HIGH confidence — read in full this session)
- `src/segugio/opcomm/atomic.py` — `_temp_path`/`_atomic_replace` (50-retry MoveFileEx)/`atomic_write_text`/`atomic_write_json`; `__all__` to extend
- `src/segugio/opcomm/records.py` — `DirectorStatus` frozen + normalizing `__post_init__` (L133-158); the EXACT `PreviewDoc` template
- `src/segugio/opcomm/channel.py` — `_read_json`/`read_status`/`write_status` (the `read_preview`/`write_preview` template)
- `src/segugio/orchestrator/loop.py` — `_tick_once` (offer site = after `_apply` L521, inside the RBT-04 try L534), `_fan_out`/`_batched_inference` (`frames_by_cam` at L370), `scores` (L511), `run`/`run_measured`/`shutdown`, the cut change-edge (L468)
- `src/segugio/orchestrator/runtime.py` — `build_orchestrator`/`_channel_paths`/`*_factory`/`os.makedirs` (L161); where the publisher is constructed + the `preview/` dir extension
- `src/segugio/ui/app.py` — the lazy-Flask `create_app`; the crash-isolation surface gate-2 locks (untouched in Phase 7)
- `src/segugio/ndi/ndi_source.py` + `ndi/clip_source.py` — `latest()` returns a freshly-allocated array per frame (buffer-reuse RESOLVED: no copy needed)
- `src/segugio/ndi/source.py` — the `FrameSource` Protocol
- `src/segugio/framing/signals.py` — `CameraScore`(score=EMA, status), `DetectionSignal`(cx,cy,w,h,conf,track_id), `ScorerStatus`
- `src/segugio/decision/signals.py` — `Decision.target` (the FSM auto-candidate)
- `src/segugio/tracking/competitor_lock.py` — `locked_id`/`locked_motion_energy()`
- `src/segugio/config/models.py` + `framing/params.py` — `ActionHoldParams`/`ScorerParams` additive-sub-model pattern (the `PreviewParams` template)
- `tests/test_latency.py` — `run_measured`/`_p95`/`@pytest.mark.gpu` (gate-1 harness)
- `tests/test_ui_score.py::test_app_imports_nothing_heavy` + `tests/test_imports.py` — the heavy-absent `monkeypatch.setitem(sys.modules, heavy, None)` pattern (gate-2 template; today blocks cv2 NOT numpy)
- `tests/conftest.py` — `make_config`/`file_channel`/fakes; `pytest_collection_modifyitems` gpu-skip
- `.planning/phases/07-off-tick-frame-publishing-channel/07-CONTEXT.md` — the 9 locked decisions + Claude's-Discretion items
- `.planning/research/v1.1/ARCHITECTURE.md` — Patterns 1–3, Anti-Patterns, Build Order (steps 1–4 = Phase 7)
- `.planning/ROADMAP.md` §Phase 7 — the 5 success criteria + the two HARD gates
- `.planning/REQUIREMENTS.md` §PRV — PRV-01/02/03

### Secondary (MEDIUM confidence)
- `.planning/research/v1.1/STACK.md` — no-new-runtime-deps verdict; `cv2.imencode`/`numpy` already present; `waitress` Phase-8-only
- `.planning/research/v1.1/PITFALLS.md` — encoding-on-tick / console-imports-cv2 / fsync-thrash / cuts-ring failure modes
- `CLAUDE.md` — locked stack, <300ms p95 budget, no-crash live robustness

### Tertiary (LOW confidence)
- none — every load-bearing claim is grounded in a file read this session.

## Project Constraints (from CLAUDE.md)
- **Locked stack:** Python orchestrator; `cv2`/`numpy` already present — **no new runtime deps** in Phase 7 (consistent with this research).
- **Performance:** AI loop p95 **< 300ms** (revised 2026-06-13). Gate 1 enforces "preview ON must not regress" this budget.
- **No crash ever / degrade to SAFE:** the publisher fault must COAST (RBT-04 extended) — never crash the director. Enforced by SC5 + the `offer()` riding inside the tick's existing RBT-04 try.
- **GSD workflow enforcement:** all edits go through a GSD command (this is the research step; planning/execution follow).
- **OS-agnostic, prod on Windows:** the `_atomic_replace` MoveFileEx retry is already Windows-correct; the new binary writer reuses it.

## Metadata

**Confidence breakdown:**
- Seam verification: HIGH — every named function/class/attribute opened and confirmed; zero drift.
- Standard stack: HIGH — no new deps; `cv2.imencode`/`numpy` confirmed present.
- Architecture/patterns: HIGH — modeled directly on the in-repo `DirectorStatus`/`atomic_write_text`/`run_measured` templates.
- "why" payload mapping: HIGH for score/state/bbox/track_id/auto_candidate/cuts (all VERIFIED); MEDIUM for `in_zone`/`ema` (A1: in_zone approximated; ema = score since raw isn't exposed).
- Gate-1 noise band: MEDIUM (A3) — empirical, derived on the rig; the gate FORM is specified, the numeric tolerance is for the verifier.
- Pitfalls: HIGH — each grounded in a verified seam or the milestone PITFALLS doc.

**Research date:** 2026-06-13
**Valid until:** ~2026-07-13 (stable — pure-stdlib + already-pinned deps; the only time-sensitive item is the GPU rig's measured noise band, which the gate derives fresh each run).
