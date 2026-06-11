---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
reviewed: 2026-06-11T13:31:39Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/segugio/config/models.py
  - src/segugio/ndi/ndi_source.py
  - src/segugio/obs/obsws_controller.py
  - src/segugio/opcomm/atomic.py
  - src/segugio/orchestrator/loop.py
  - tests/test_atomic_io.py
  - tests/test_fault_isolation.py
  - tests/test_ndi_receiver_loop.py
  - tests/test_orchestrator_startup.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 5: Code Review Report (gap-closure re-review)

**Reviewed:** 2026-06-11T13:31:39Z
**Depth:** standard
**Files Reviewed:** 9 (diff 5802108..HEAD)
**Status:** issues_found

## Summary

Gap-closure re-review scoped to the diff `5802108..HEAD` (plans 05-07 and 05-08). It supersedes
the prior full-phase 05-REVIEW for the closed findings and verifies no regression was introduced.

Change set:
- **05-07 (CR-01 startup fault-isolation):** `Orchestrator._safe_startup` wraps `source.start()` and
  `obs.connect()` in both `run()` and `run_measured()`; a non-zero `watchdog_grace` config seed
  (0.067) is added and `from_config(grace=None)` sources it; `ObsWsController.connect()` guards the
  `_cache_pip_ids` step so a partial connect coasts; the catch-all tick fault now reports a distinct
  `reason="fault"` (WR-09).
- **05-08 (WR-04 + CR-02):** `atomic_write_text` routes through the same `_atomic_replace`
  bounded-retry as the JSON path; the NDI receiver loop is extracted into `_run_receiver` with a
  sleep-and-re-resolve disconnected branch (de-busy-spin + auto-reconnect).

**Prior-finding verdict — all genuinely closed:**

- **CR-01 (startup fault-sink):** CLOSED. `_safe_startup` catches a raising `start()`/`connect()`;
  `test_orchestrator_startup.py` exercises both raising paths and asserts 5 ticks still run.
- **CR-02 (NDI busy-spin):** CLOSED. The bare `continue` is replaced by `time.sleep` + re-resolve;
  the bounded fake-driven tests would hang (and fail under timeout) on a regression.
- **WR-02 (zero grace default):** CLOSED. `from_config` defaults grace to
  `config.thresholds.watchdog_grace` (0.067 > 0); explicit arg still wins; both pinned by tests.
- **WR-04 (text write not retried):** CLOSED. `atomic_write_text` now calls `_atomic_replace`;
  `test_atomic_write_text_retries_on_permission_error` proves the retry.
- **WR-09 (non-feed fault mislabeled feed-dead):** CLOSED. Catch-all uses `reason="fault"`, pinned by
  `test_non_feed_fault_reason_is_not_feed_dead`.

No regressions that break the headless contract were found. The findings below are residual
robustness/quality gaps — several of which the gap-closure comments now make *load-bearing*.

## Warnings

### WR-01: `_cache_pip_ids` re-cache claim relies on an event callback that is never registered

**File:** `src/segugio/obs/obsws_controller.py:98-107`, `156-162`
**Issue:** The new CR-01 connect-guard swallows a failed `_cache_pip_ids()` and justifies it in the
comment: *"the EventClient SceneItemCreated/Removed callback and the per-tick `_safe_call` reconnect
re-cache ids."* But `_on_scene_items_changed` (the SceneItemCreated/Removed handler) is **defined and
never registered** anywhere — only `_on_scene_changed` is registered in `connect()` (lines 93-95). So
half of the stated recovery mechanism does not exist: after a partial connect the id cache is empty
(`self._item_ids = {}`) and stays empty until a *different* OBS op fails and triggers
`_safe_call` → `reconnect()`. The comment overstates the safety net created by CR-01.
**Fix:** Register the scene-item handler so the documented re-cache path actually exists:
```python
# in connect(), after registering _on_scene_changed:
register_items = getattr(getattr(self._evt, "callback", None), "register", None)
if callable(register_items):
    register_items(self._on_scene_items_changed)
```
(or, if obsws-python routes all events through one callback, dispatch on event type inside
`_on_scene_changed`). At minimum, correct the connect-guard comment to state recovery is solely via
the `_safe_call` reconnect, not an event callback.

### WR-02: receiver auto-reconnect re-issues `set_source` every disconnected pass — possible handshake livelock on real cyndilib

**File:** `src/segugio/ndi/ndi_source.py:143-152`
**Issue:** The disconnected branch unconditionally calls `receiver.set_source(source)` on **every** loop
pass (every 50 ms) for as long as `is_connected()` returns False. A real cyndilib `Receiver` connect is
asynchronous: `set_source` starts a connect that takes longer than 50 ms to report `is_connected()`.
Re-calling `set_source` with the same source mid-handshake can reset/restart the connect, so the
receiver may never settle into the connected state — an auto-reconnect livelock the headless fakes
(which flip `is_connected()` deterministically) cannot catch. The HARDWARE note acknowledges only
"near-zero CPU" is verified, not reconnect convergence.
**Fix:** Only call `set_source` when the bound source actually changes (or when none is set yet):
```python
if not receiver.is_connected():
    time.sleep(_RECEIVER_DISCONNECTED_SLEEP_S)
    source = self._resolve_source(finder, source_name)
    if source is not None and source != self._bound_source:
        receiver.set_source(source)
        self._bound_source = source
    continue
```
Track the last-set source so a still-connecting receiver is left to finish its handshake.

### WR-03: `set_pip` reads `self._item_ids[...]` directly — uncached id raises `KeyError`, defeating the partial-connect guard's intent

**File:** `src/segugio/obs/obsws_controller.py:193-201` (interaction with `89-107`)
**Issue:** With CR-01 now allowing `connect()` to complete with an EMPTY id cache (partial connect
coasted), `set_pip(scene, source, ...)` does `item_id = self._item_ids[(scene, source)]`, which raises
`KeyError` for any pair never cached. `_safe_call` wraps it, so the orchestrator does not crash — but
the first failure path is a `KeyError` that triggers a full reconnect+reauth (an expensive websocket
rebuild) on every `set_pip` until ids resolve, instead of a cheap re-cache. In v1 `set_pip` is "driven
manually/idle" (module docstring), so live blast radius is low, but the code is now structurally
fragile against the partial-connect state the CR-01 guard deliberately creates.
**Fix:** Make `set_pip` lazily resolve+cache a missing id before use:
```python
def _do() -> None:
    key = (scene, source)
    if key not in self._item_ids:
        self._item_ids[key] = self._req.get_scene_item_id(scene, source).scene_item_id
    item_id = self._item_ids[key]
    ...
```
so an empty post-partial-connect cache self-heals on first use without forcing a full reconnect.

### WR-04: `run_measured` probe length silently diverges from `n_ticks` when a tick stage raises

**File:** `src/segugio/orchestrator/loop.py:426-442`, `492-524`
**Issue:** The per-stage probe-append block (lines 426-435) lives INSIDE the `try`, after every stage.
When any stage raises (`_ThrowingFrameSource`, or any real fault tick) the `except` runs `_to_safe` but
appends NOTHING to `probe`. So `len(probe["total"])` < `n_ticks` whenever faults occur, and the
instance accumulator (`self._latency_total.extend(...)`) under-counts fault ticks. The latency harness
and any p95 over `probe["total"]` then silently exclude every degraded tick — exactly the ticks most
likely to be slow (SAFE coast + status write) — over-reporting health.
`test_run_measured_survives_connect_raising` only passes because its source never raises in the tick
body (start() raises at startup, caught by `_safe_startup`; `latest()` returns None thereafter).
**Fix:** Record a probe entry for fault ticks too (attribute to a `fault`/`coast` bucket) so the per-tick
count always equals `n_ticks`; or document `probe["total"]` as "successful ticks only" and have the
latency harness assert `len(...) == n_ticks` to surface dropped ticks instead of averaging fewer.

## Info

### IN-01: stale docstring — `_read_run_and_override` documents a 3-tuple return but returns a 2-tuple

**File:** `src/segugio/orchestrator/loop.py:297-307`
**Issue:** The docstring says *"Returns `(run, override, just_started)`"* but the function returns
`return run, override` (2 elements). The caller correctly unpacks two, so no bug — only a misleading
docstring.
**Fix:** Change to `Returns ``(run, override)``.` (the `just_started` edge is read off
`run.just_started` at the call site).

### IN-02: `reason="fault"` is not in the documented advisory-tag set the panel renders

**File:** `src/segugio/orchestrator/loop.py:442`, `src/segugio/opcomm/records.py:137-138`
**Issue:** WR-09's new `reason="fault"` value is correct and distinct, but `DirectorStatus`'s docstring
enumerates the advisory tags as `auto / override / subject-lost / feed-dead / shutdown` — "fault" is
absent. `ui/app.py` (line 134) passes `reason` through verbatim to the panel as JSON, so an
unrecognized tag may render with no styling/label in the operator console.
**Fix:** Add `fault` to the `DirectorStatus.reason` advisory-tag docstring list and confirm the panel
template has a label/style for it.

### IN-03: capture/publish path of `_run_receiver` has no headless coverage

**File:** `src/segugio/ndi/ndi_source.py:153-165`, `tests/test_ndi_receiver_loop.py`
**Issue:** All three new receiver tests drive ONLY the disconnected branch; the connected path
(`capture_video` → NDI-03 zero-res guard → NEW-frame ts check → reshape → `cvtColor` → `_publish`) is
exercised only under `@pytest.mark.ndi` on hardware. A regression in the publish branch (wrong reshape
order, flipped `ts != last_ts` guard) would not be caught headlessly even though the branch is
pure-logic-testable with a fake `video_frame`.
**Fix:** Add a headless test: a fake `receiver` whose `is_connected()` returns True plus a fake
`video_frame` exposing scripted `xres/yres/get_timestamp_posix/get_array` and a fake `cv2.cvtColor`,
asserting `_publish` fires once per NEW ts and is skipped on a repeated ts (the RBT-01 liveness rule).

### IN-04: magic offset `now=float(tick) + 1.0` couples `run_measured` to the mock source by an unenforced convention

**File:** `src/segugio/orchestrator/loop.py:512-514`
**Issue:** `run_measured` derives `now = float(tick) + 1.0` to match "the mock source's ts (= tick + 1.0)".
This `+ 1.0` cross-module convention is enforced nowhere — if the mock's tick-derived timestamp formula
changes, liveness in the headless harness silently breaks (feeds appear dead/alive incorrectly) with no
failing assertion at the seam.
**Fix:** Extract the tick→ts mapping into a single shared helper/constant imported by both the mock
source and `run_measured`, or add a test asserting `source.last_frame_ts(cam) == now` for a freshly
pumped tick.

---

_Reviewed: 2026-06-11T13:31:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
