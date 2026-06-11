---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - src/segugio/config/models.py
  - src/segugio/ndi/clip_source.py
  - src/segugio/ndi/mock_sender.py
  - src/segugio/ndi/ndi_source.py
  - src/segugio/ndi/source.py
  - src/segugio/obs/controller.py
  - src/segugio/obs/mapping.py
  - src/segugio/obs/obsws_controller.py
  - src/segugio/obs/recording_fake.py
  - src/segugio/opcomm/atomic.py
  - src/segugio/opcomm/channel.py
  - src/segugio/opcomm/records.py
  - src/segugio/orchestrator/action_hold.py
  - src/segugio/orchestrator/loop.py
  - src/segugio/tracking/competitor_lock.py
  - src/segugio/ui/app.py
  - src/segugio/ui/score_render.py
  - src/segugio/ui/templates/console.html
  - src/segugio/watchdog_feed/liveness.py
  - obs/segugio-scene-collection.json
  - tests/conftest.py
  - tests/test_action_hold.py
  - tests/test_atomic_io.py
  - tests/test_fallback_rejoin.py
  - tests/test_fault_isolation.py
  - tests/test_frame_source_empty_guard.py
  - tests/test_latency.py
  - tests/test_ndi_mock_sender.py
  - tests/test_ndi_source.py
  - tests/test_obs_mapping.py
  - tests/test_obs_reconnect.py
  - tests/test_overlay.py
  - tests/test_scene_template.py
  - tests/test_score_display_only.py
  - tests/test_status_channel.py
  - tests/test_ui_run.py
  - tests/test_ui_score.py
  - tests/test_watchdog.py
findings:
  critical: 2
  warning: 9
  info: 5
  total: 16
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 39
**Status:** issues_found

## Summary

This phase wires the NDI ingest, OBS controller, feed watchdog, operator Flask console, and the fault-isolated orchestrator tick. The core robustness pattern in `orchestrator/loop.py` (`_tick_once` wraps the whole pipeline in one try/except → coast to SAFE) is sound, and the watchdog liveness math, atomic file I/O, and opcomm boundary are all well-built and match their stated contracts. The display-only score path is genuinely display-only.

However the review surfaced two correctness BLOCKERs that defeat the never-crash contract at its most exposed points (the live startup path and the real NDI receiver loop), and a cluster of WARNINGs around startup robustness, a busy-spin in the receiver thread, a dead/misleading `live_cam` computation, and the watchdog grace defaulting to 0 (which contradicts the anti-jitter rationale documented in the file itself). None of the issues are in the display-only or atomic-write spine, which are solid.

## Critical Issues

### CR-01: Live `run()` startup is OUTSIDE the fault sink — `source.start()` / `obs.connect()` can crash the director

**File:** `src/segugio/orchestrator/loop.py:451-466`
**Issue:** The whole "nessun crash ammesso" contract (RBT-04) is implemented per-tick inside `_tick_once`, but the live loop calls `self.source.start()` and `self.obs.connect()` BEFORE the `try:` block:

```python
self.source.start()      # line 453 — NOT inside try
self.obs.connect()       # line 454 — NOT inside try
tick = 0
try:
    while not self._stopping:
        ...
finally:
    self.shutdown()
```

`NdiFrameSource.start()` spawns threads (cheap), but `ObsWsController.connect()` (line 89-97) calls `self._factory(...)` which, for the real factory `build_obsws_clients`, constructs `obs.ReqClient(...)` / `obs.EventClient(...)` — a live websocket connect with `timeout=3`. If OBS is not up yet at director launch (a normal field condition), `connect()` raises `ConnectionError`/socket error and the entire process exits before the loop ever starts. The whole point of SAFE-coast is that the director survives OBS being down. This crashes instead.

`_cache_pip_ids()` (line 123-132) inside `connect()` also calls `self._req.get_scene_item_id(...)` with no guard — a failure there also escapes `connect()`.

**Fix:** Wrap startup in the same coast logic, and let the loop retry connect on subsequent ticks (OBS calls already self-heal via `_safe_call`):

```python
def run(self, rate_hz: float = 30.0) -> None:
    period = 1.0 / rate_hz if rate_hz > 0 else 0.0
    self._stopping = False
    try:
        self.source.start()
    except Exception as exc:  # noqa: BLE001
        logger.exception("source.start() failed — coasting: {}", exc)
    try:
        self.obs.connect()
    except Exception as exc:  # noqa: BLE001
        logger.exception("obs.connect() failed — coasting (will retry via _safe_call): {}", exc)
    tick = 0
    try:
        while not self._stopping:
            ...
    finally:
        self.shutdown()
```

Additionally, make `ObsWsController.connect()` not leave `_connected` half-set and not let `_cache_pip_ids` escape (wrap the id cache in try, log + coast).

### CR-02: Real NDI receiver loop busy-spins a full CPU core while disconnected/unresolved

**File:** `src/segugio/ndi/ndi_source.py:113-128`
**Issue:** The per-camera receiver loop:

```python
while not self._stop.is_set():
    if not receiver.is_connected():
        continue          # <-- no sleep: tight 100%-CPU spin
    receiver.frame_sync.capture_video()
    ...
```

When the named source has not appeared yet (`_resolve_source` returned `None`, so `set_source` was never called) or the phone drops, `receiver.is_connected()` stays false and the loop `continue`s with zero delay — a hot spin pinning one core per camera (3-4 cores on the production rig). On the live latency-budget box this directly threatens the <150ms AI-loop budget (the loop is competing for CPU/GPU scheduling with YOLO). The docstring claims the loop "simply coasts (stays disconnected) until the named source appears" — but coasting here means burning a core.

Worse: `_resolve_source` is called exactly once before the loop. If the source is not yet present at thread start, it returns `None`, `set_source` is never called, and the loop busy-spins forever even after the source appears — the camera never recovers without a `stop()`/`start()` cycle.

**Fix:** Add a short sleep on the disconnected branch AND re-attempt source resolution inside the loop:

```python
import time
...
last_ts = None
while not self._stop.is_set():
    if not receiver.is_connected():
        src = self._resolve_source(finder, source_name)
        if src is not None:
            receiver.set_source(src)
        if self._stop.wait(0.05):  # interruptible sleep; avoids the hot spin
            break
        continue
    receiver.frame_sync.capture_video()
    ...
```

Using `self._stop.wait(timeout)` instead of `time.sleep` keeps `stop()` responsive.

## Warnings

### WR-01: `_status_for` computes `live_cam` then ignores it — dead variable + docstring contradicts behavior

**File:** `src/segugio/orchestrator/loop.py:350-352`
**Issue:**

```python
live_cam = self._safe_cam_id if target == SAFE_TARGET else target
# live_cam is the camera id; the UI maps it to a label. SAFE target → the is_safe cam id.
return DirectorStatus(live_cam=target, reason=reason, alive=dict(alive))
```

`live_cam` is computed (resolving SAFE → the is_safe camera id) and then never used — `DirectorStatus(live_cam=target, ...)` passes the raw `target`. So on a SAFE decision the status reports the literal `"SAFE"` sentinel, not the is_safe camera id, directly contradicting the comment and the method docstring ("SAFE target → the is_safe cam id"). The tests (`test_status_written_on_change`) actually assert `status.live_cam == "SAFE"`, so the SHIPPED behavior is "emit SAFE", and the dead variable + docstring are simply wrong. This is a latent trap: a future reader fixing the "bug" to use `live_cam` would break the tests and the UI contract.

**Fix:** Delete the dead variable and correct the docstring to state that `live_cam` is the raw target (SAFE sentinel passed through), e.g.:

```python
# live_cam is the raw FSM target: a camera id, or the "SAFE" sentinel which the UI renders.
return DirectorStatus(live_cam=target, reason=reason, alive=dict(alive))
```

### WR-02: Watchdog `grace` defaults to 0.0 everywhere — the documented anti-jitter protection is OFF in production

**File:** `src/segugio/orchestrator/loop.py:190,220` and `src/segugio/watchdog_feed/liveness.py:64`
**Issue:** `FeedWatchdog.__init__` defaults `grace=0.0`, `Orchestrator.from_config` defaults `grace=0.0`, and the live `run()` path never overrides it. The watchdog module docstring (liveness.py:18-22) and the threat model (T-05-04-02) describe `grace` as the explicit anti-jitter / flap / cut-storm mitigation ("a small extra tolerance ... so a single late frame does not flap the feed dead and trigger a cut storm"). With `grace=0.0` and `watchdog_timeout=0.8`, a single frame arriving at 0.81s late flips the feed dead and can trigger exactly the cut storm the design intended to prevent. Every test that exercises the protection passes `grace=0.1`, but no production construction path does.

**Fix:** Give `from_config` a sensible non-zero default (e.g. ~1-2 ticks: `grace=2.0/fps`) or source it from a config field so the live director actually gets the documented protection. At minimum, `Orchestrator.run` / the real wiring should pass a non-zero grace.

### WR-03: `run_measured` calls `source.pump()` OUTSIDE the per-tick fault sink — a decode error crashes the harness/loop

**File:** `src/segugio/orchestrator/loop.py:483-490`
**Issue:**

```python
for tick in range(n_ticks):
    pump = getattr(self.source, "pump", None)
    if callable(pump):
        pump()                       # <-- not inside _tick_once's try
    self._tick_once(tick, now=float(tick) + 1.0, probe=probe)
```

`ClipReplayFrameSource.pump()` only catches `StopIteration`; the wrapped `ClipFrameSource.frames()` generator does cv2 decode work and can raise (a corrupt/truncated clip → cv2 error, or a reshape error). That exception propagates out of `pump()` → out of `run_measured` → crash. The never-crash contract should hold for the measured/headless path too (it is the path the on-Windows latency run uses with real frames).

**Fix:** Move the pump inside the fault boundary, or wrap it:

```python
try:
    if callable(pump):
        pump()
except Exception as exc:  # noqa: BLE001
    logger.exception("source.pump() failed → SAFE coast: {}", exc)
    self._to_safe(reason="feed-dead")
    continue
self._tick_once(tick, now=float(tick) + 1.0, probe=probe)
```

### WR-04: `atomic_write_text` does NOT get the Windows replace-retry that `atomic_write_json` has

**File:** `src/segugio/opcomm/atomic.py:82-93`
**Issue:** `atomic_write_json` uses `_atomic_replace(tmp, path)` which retries on the Windows `PermissionError` sharing-violation (lines 39-52, 79). But `atomic_write_text` calls bare `os.replace(tmp, path)` (line 93). The overlay file (`overlay.txt`) is written via `atomic_write_text` and is read continuously by OBS's read-from-file text source on Windows — exactly the reader-holds-handle scenario the retry exists for. The module docstring and the JSON path both treat this Windows sharing-violation as a real, expected transient; the text path is left exposed, so an overlay write can raise a `PermissionError` while OBS has the file open.

If `atomic_write_text` is ever called from inside the orchestrator tick (or the UI process while OBS reads), this surfaces as an unhandled error / lost overlay update.

**Fix:** Use the same retry helper:

```python
def atomic_write_text(path: str, text: str) -> None:
    tmp = _temp_path(path)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    _atomic_replace(tmp, path)   # was: os.replace(tmp, path)
```

### WR-05: Atomic write leaves the temp file behind on a failed/aborted replace

**File:** `src/segugio/opcomm/atomic.py:74-79, 88-93`
**Issue:** If `_atomic_replace` exhausts its retries and re-raises (or `os.fsync` fails), the same-directory `.<name>.tmp` file is left on disk. Over a long live event with repeated transient failures this litters the opcomm directory with stale `.tmp` files. More subtly, because the temp name is fixed per target (`._temp_path`), two concurrent writers to the SAME target (e.g. two UI requests racing, or UI + orchestrator both writing the same file) will clobber each other's temp mid-write — the leading-dot-per-target scheme only prevents collisions between *sibling* files, not between concurrent writers of the *same* file.

**Fix:** Use a unique temp name per write (e.g. include `os.getpid()` + a counter or `tempfile.mkstemp` in the target dir) and clean up the temp in a `finally` / `except` on replace failure:

```python
tmp = _temp_path(path)
try:
    with open(tmp, "w", encoding="utf-8") as f:
        ...
    _atomic_replace(tmp, path)
except Exception:
    try:
        os.remove(tmp)
    except OSError:
        pass
    raise
```

### WR-06: `NdiFrameSource.start()` is not safe to call concurrently / re-clears the stop event

**File:** `src/segugio/ndi/ndi_source.py:64-83`
**Issue:** `start()` does `self._stop.clear()` then iterates `self._sources` creating threads, reading/writing `self._threads` with no lock. The class is explicitly designed to be the supervisor restart hook ("a dead receiver thread is restartable by start()"). If the orchestrator calls `start()` to restart a dead thread while `stop()` is concurrently running (or two restarts race), `self._stop.clear()` can race a `self._stop.set()` in `stop()`, and the unsynchronized `self._threads` dict mutation can drop/overwrite a thread handle (a leaked, unjoinable thread). The `_lock` exists but guards only `_publish`/`latest`/`last_frame_ts`, never the thread lifecycle.

**Fix:** Guard `start()` and `stop()`'s `_threads` access with a dedicated lifecycle lock, and do not blanket-`clear()` the stop event when only restarting individual dead threads (clearing it un-stops every still-running thread's exit signal).

### WR-07: `Config.model_validate` overrides are shallow-merged in the `make_config` test factory — silently drops sub-keys

**File:** `tests/conftest.py:293-297`
**Issue:**

```python
raw = copy.deepcopy(_PHASE5_CONFIG)
if overrides:
    raw.update(copy.deepcopy(overrides))   # shallow update
return Config.model_validate(raw)
```

`dict.update` is shallow: `make_config(overrides={"thresholds": {"alpha": 0.5}})` REPLACES the entire `thresholds` block with `{"alpha": 0.5}`, dropping `watchdog_timeout`, `debounce_N`, etc. Pydantic then fills defaults, so it won't error — it will silently produce a config different from what the test author intended, masking real failures. This is a test-reliability defect (a future test that relies on overriding one nested key will be quietly wrong).

**Fix:** Deep-merge overrides, or document that `overrides` replaces whole top-level blocks. A small recursive merge is safest given this is the shared factory all Phase-5 tests build on.

### WR-08: `to_safe()` advance during STOP runs unguarded inside `_decide`, and `_decide` imports inside the hot path

**File:** `src/segugio/orchestrator/loop.py:314-324`
**Issue:** `_decide` calls `self.engine.to_safe()` while the run is stopped. `_decide` is invoked inside `_tick_once`'s try, so an exception there coasts — acceptable. But while STOPPED with no override, `self.engine.to_safe()` is invoked EVERY tick (30 Hz) purely to "keep clocks coherent," and the `from ..decision.signals import Decision, Mode` import runs every stopped tick. The import is cached by Python so the cost is small, but `to_safe()` being driven at 30 Hz indefinitely while idle is a questionable steady-state (it assumes `to_safe()` is idempotent and side-effect-free across thousands of calls; if it accumulates any internal counter this drifts). Confirm `DecisionEngine.to_safe()` is truly idempotent under repeated calls; if not, this silently corrupts FSM clocks during long STOP periods.

**Fix:** Hoist the `Decision`/`Mode` import to module top (it is a light pure module already imported transitively) and verify `to_safe()` idempotency; consider only advancing the FSM on the STOP edge rather than every stopped tick.

### WR-09: `_to_safe` fault path always reports `reason="feed-dead"` even when the fault was NOT a feed

**File:** `src/segugio/orchestrator/loop.py:430-432`
**Issue:** The catch-all in `_tick_once` coasts with `self._to_safe(reason="feed-dead", alive=alive)`. But the exception could be from the scorer, the FSM, the OBS cut, or a status-write — none of which are "feed dead." The operator panel (D-11) renders `reason` as the advisory tag explaining why the director is on SAFE. Mislabeling a scorer/FSM crash as "feed-dead" sends the operator to debug the wrong subsystem (e.g. checking phones/WiFi when the actual fault is in decision logic). For a live, operator-facing tool this is a real diagnostic-quality defect.

**Fix:** Use a distinct reason for an internal fault, e.g. add `"fault"` to `_STATUS_REASONS` and coast with `reason="fault"` (or log the stage and pass a more specific tag). Reserve `"feed-dead"` for actual watchdog-declared feed loss.

## Info

### IN-01: `_read_run_and_override` docstring claims a 3-tuple but returns a 2-tuple

**File:** `src/segugio/orchestrator/loop.py:291-301`
**Issue:** The docstring says `Returns (run, override, just_started)` but the function `return run, override` (2-tuple), and the caller unpacks `run, override = ...`. Just a stale docstring, but misleading.
**Fix:** Update the docstring to `Returns (run, override)`.

### IN-02: `_on_scene_items_changed` is never registered

**File:** `src/segugio/obs/obsws_controller.py:146-151`
**Issue:** The handler that refreshes the numeric sceneItemId cache on SceneItemCreated/Removed (Pitfall 3) is defined but never wired into the EventClient (only `_on_scene_changed` is registered in `connect()`). So the "refreshed via the EventClient on SceneItemCreated/Removed" claim in `_cache_pip_ids`'s docstring is not actually true — the cache only refreshes on a full `reconnect()`. PIP is idle in v1 so the blast radius is low, but the code is dead as wired.
**Fix:** Register `_on_scene_items_changed` for the relevant events in `connect()`, or remove the method and correct the docstring.

### IN-03: `mock_sender.publish_clip` imports `FourCC` from `wrapper.ndi_recv` (likely wrong module for a send frame)

**File:** `src/segugio/ndi/mock_sender.py:59`
**Issue:** `from cyndilib.wrapper.ndi_recv import FourCC` — `FourCC` for a *send* frame is more plausibly under `ndi_send`/a send wrapper, not `ndi_recv`. The file already flags this as `[ASSUMED A2]` and gates the path behind `@pytest.mark.ndi`, so it is documented and low-blast-radius, but it is a likely import error on the real `cyndilib==0.1.1`.
**Fix:** Verify the `FourCC` / `VideoSendFrame` / `write_video_async` import paths against the installed cyndilib on the Windows box (as the assumption note already states).

### IN-04: Conftest Phase-5 config `ndi_source` names (`"PHONE-WIDE (NDI)"`) differ from the OBS template / example configs (`"PHONE-WIDE (NDI HX3)"`)

**File:** `tests/conftest.py:232,240,248,256` vs `obs/segugio-scene-collection.json` / `config.example.yaml`
**Issue:** The test fixture uses `"... (NDI)"` while the shipped scene collection and example configs use `"... (NDI HX3)"`. Harmless because the headless tests never resolve real NDI names, but it is an inconsistency that could confuse anyone copying the fixture as a config template.
**Fix:** Align the fixture names with the shipped convention for clarity.

### IN-05: Flask app binds `0.0.0.0:8080` with no auth — accepted, but the file relies on LAN trust only

**File:** `src/segugio/ui/app.py:140-143`
**Issue:** Not a defect — the no-auth `0.0.0.0` bind is an explicitly documented, accepted decision (D-02, T-05-05-04) for a single-operator field tool on a dedicated WiFi LAN. Noting it only so the reviewer log records that the path-traversal and overlay-injection inputs ARE mitigated (fixed server-side filenames, Discipline whitelist, `_clean` sanitizer) and the residual exposure is the accepted LAN trust boundary. No fix required; flagged for completeness.

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
