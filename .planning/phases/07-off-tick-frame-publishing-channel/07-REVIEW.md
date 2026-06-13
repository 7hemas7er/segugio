---
phase: 07-off-tick-frame-publishing-channel
reviewed: 2026-06-13T11:54:52Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - src/segugio/config/models.py
  - src/segugio/opcomm/atomic.py
  - src/segugio/opcomm/channel.py
  - src/segugio/opcomm/records.py
  - src/segugio/orchestrator/loop.py
  - src/segugio/orchestrator/preview.py
  - src/segugio/orchestrator/runtime.py
  - tests/test_atomic_io.py
  - tests/test_fault_isolation.py
  - tests/test_latency.py
  - tests/test_orchestrator_runtime.py
  - tests/test_preview_channel.py
  - tests/test_preview_publisher.py
  - tests/test_ui_score.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-06-13T11:54:52Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the off-tick frame-publishing channel: the new `PreviewParams`/`PreviewDoc`
config+record types, `atomic_write_bytes(fsync=...)`, the `read_preview`/`write_preview`
channel boundary, the `PreviewPublisher` daemon, the `Orchestrator` tick wiring, and the
`build_orchestrator` runtime glue.

The four hard invariants hold in the common path: `offer()` is a single locked pointer swap
(non-blocking, last-writer-wins); the hot-path `offer()` rides inside the existing RBT-04 tick
`try/except` so a publisher fault coasts to SAFE; the `opcomm` package and `preview.py` keep
cv2/numpy lazy inside `_publish`/`_cv2_encode` (import surface stays heavy-free); and
`config.preview.enabled=False` yields a `None` publisher with no tick-path calls. The
`fsync=False` JPEG drop is correctly scoped to ephemeral thumbnails only.

However, the publisher's lifecycle is NOT safe under the repeated-`start()` pattern the code
itself exercises. `Orchestrator.run` and `Orchestrator.run_measured` BOTH call
`self._preview.start()`, and `run_measured` is called multiple times on one orchestrator
instance (the GPU no-regression test does exactly this back-to-back). The second `start()`
overwrites `self._thread` and leaks the first daemon — and the two daemons then write the SAME
fixed temp path concurrently, breaking the atomic-write guarantee. That is the load-bearing
defect below. A handful of robustness/quality findings follow.

## Critical Issues

### CR-01: Repeated `start()` leaks a daemon and two publishers race on the same atomic temp path

**File:** `src/segugio/orchestrator/preview.py:128-134` (and `src/segugio/orchestrator/loop.py:632-633, 662-663`)
**Issue:**
`PreviewPublisher.start()` unconditionally clears the stop event and assigns a brand-new
thread to `self._thread`, with no guard against an already-running thread:

```python
def start(self) -> None:
    self._stop.clear()
    self._thread = threading.Thread(target=self._run, name="preview-publisher", daemon=True)
    self._thread.start()
```

`Orchestrator.run_measured` calls `self._preview.start()` every invocation (loop.py:662-663),
and the orchestrator is explicitly driven with multiple `run_measured(...)` calls on a SINGLE
publisher instance — see `tests/test_latency.py:284-285`:

```python
on.run_measured(n_ticks=20)   # start() #1 — daemon A
on.run_measured(n_ticks=100)  # start() #2 — daemon B; self._thread now points only at B
```

After the second `start()`:
1. Daemon A is orphaned — `self._thread` no longer references it, so `stop()` never joins it.
2. Both daemons run concurrently, each calling `_publish` → `atomic_write_bytes`. The temp
   filename is FIXED per target (`atomic.py:_temp_path` → `.cam_<id>.jpg.tmp`), so two
   publishers writing `cam_<id>.jpg` use the SAME temp file. One daemon's `open(tmp,"wb")` +
   `write` + `os.replace` interleaves with the other's: a half-written temp can be `os.replace`d
   into the live JPEG, or one `os.replace` races the other's open handle. This DEFEATS the
   never-partial atomic-write guarantee the whole channel is built on — exactly on the prod GPU
   path the `_gpu_latency_orch`/`build_orchestrator` test claims to validate.

Even `Orchestrator.run()` is exposed: calling `run()` after a `run_measured()` warmup (without
an intervening `shutdown()`) double-starts the same way.

**Fix:** Make `start()` idempotent — refuse to launch a second thread while one is alive, or
stop+join the prior one first:

```python
def start(self) -> None:
    if self._thread is not None and self._thread.is_alive():
        return  # already running — do not leak a second daemon
    self._stop.clear()
    self._thread = threading.Thread(
        target=self._run, name="preview-publisher", daemon=True
    )
    self._thread.start()
```

Additionally consider making the temp name unique per writer (e.g. include `os.getpid()`/a
counter) so concurrent writers to the same target can never collide on the temp path
(defense-in-depth for the atomic primitive).

## Warnings

### WR-01: `stop()` can block up to one full publish period (config-tunable to ~1000s)

**File:** `src/segugio/orchestrator/preview.py:107-126, 136-150`
**Issue:** When the mailbox is empty `_run` does `time.sleep(self._period)`, and the stop event
is only checked at the top of the loop — a `time.sleep` is NOT interrupted by `self._stop.set()`.
`self._period = 1.0 / params.fps`, and `PreviewParams.fps` is bounded only `gt=0.0, le=30.0`, so
a config of `fps: 0.001` yields a 1000-second period. `stop()` then joins with
`timeout=max(2.0, self._period * 4)` and blocks the orchestrator shutdown path for up to a full
period before the daemon notices the stop. Shutdown latency, not a crash, but `shutdown()` is the
RBT-04 SAFE path that must be prompt.
**Fix:** Sleep on the stop event instead of `time.sleep`, so `stop()` wakes the loop immediately:

```python
# in _run, replace time.sleep(self._period) with:
if self._stop.wait(self._period):
    break
```
This also lets you drop the bespoke `_stop.is_set()` top-of-loop check.

### WR-02: `_gen` increment is a non-atomic read-modify-write outside the lock

**File:** `src/segugio/orchestrator/preview.py:223` (`self._gen += 1` in `_build_doc`)
**Issue:** `_build_doc` mutates `self._gen` with `+=` while holding NO lock. Today `_build_doc`
only runs on the single daemon thread, so it is safe — but CR-01's double-start path puts TWO
daemons in `_build_doc` concurrently, making `self._gen += 1` a lost-update race (the cache-bust
token can stall or go non-monotonic, defeating the console `?t=<gen>` cache defeat). Once CR-01
is fixed this is latent; flagging because the gen token's whole purpose is monotonicity.
**Fix:** Either guarantee single-writer (CR-01 fix) and document it, or bump `_gen` under
`self._lock` (it is cheap and off the tick).

### WR-03: `make_config(overrides=...)` does a shallow top-level `update`, silently dropping sibling keys

**File:** `tests/conftest.py:293-297` (consumed by `tests/test_latency.py:158-167, 261-270`)
**Issue:** `_build` applies overrides with `raw.update(copy.deepcopy(overrides))`, a SHALLOW
top-level replace. `make_config(overrides={"model": {"path": ..., "use_fp16": True}})` REPLACES
the entire `model` block rather than merging — any `model` sub-key not restated is reset to its
`ModelConfig` default. The GPU latency tests happen to restate `path`/`class_index`/`use_fp16`/
`engine_path`, so they pass, but this is a foot-gun: a future override of `{"thresholds": {...}}`
that omits one threshold would silently revert it, and the test would assert against a config
that does not match its stated intent. This weakens the latency tests' validity (they are the
gate proving preview-ON does not regress the budget).
**Fix:** Deep-merge nested override dicts instead of shallow `update`, or document loudly that an
override of a sub-block must restate the FULL block.

### WR-04: `_read_run_and_override` docstring claims a 3-tuple return; it returns a 2-tuple

**File:** `src/segugio/orchestrator/loop.py:424-434`
**Issue:** The docstring says *"Returns `(run, override, just_started)`"* but the function
returns `return run, override` (a 2-tuple). The caller at loop.py:560 correctly unpacks
`run, override = self._read_run_and_override()` and reads `run.just_started` separately, so there
is no runtime bug — but the docstring is wrong and will mislead the next editor into a 3-unpack
(an immediate `ValueError`). Stale contract on a robustness-critical helper.
**Fix:** Correct the docstring to `Returns ``(run, override)``.`

### WR-05: `offer()` stores `scores`/`dets` by reference with an undocumented mutation assumption

**File:** `src/segugio/orchestrator/preview.py:81-92` and `src/segugio/orchestrator/loop.py:573-576`
**Issue:** The module docstring carefully documents the frame-snapshot by-reference assumption
for the `frames` dict, but `offer()` also stores `scores` (a list) and `dets` (a dict) by
reference, read later on the daemon thread. Today `scorer.update()` and the fan-out produce a
FRESH list/dict each tick, and the records inside are frozen dataclasses, so there is no shared
mutation — but this safety rests on an undocumented invariant identical in spirit to the
frame-snapshot note. If a future scorer reuses/mutates its output buffer in place, the publisher
would read torn state off-thread.
**Fix:** Extend the frame-snapshot forward-assumption comment in the docstring to explicitly
cover `scores`/`dets` (fresh-per-tick, frozen elements), so the invariant is stated, not implied.

## Info

### IN-01: `numpy` imported lazily but only used via `cv2` — flagged `# noqa: F401`

**File:** `src/segugio/orchestrator/preview.py:163`
**Issue:** `import numpy as np  # noqa: F401` inside `_cv2_encode` is never referenced in that
method (cv2 handles the ndarray). It is carried only to assert the heavy pair is importable. The
`noqa` is honest but the import is dead within the function body.
**Fix:** Drop the `numpy` import here (cv2 already pulls numpy transitively), or add a one-line
comment that it is an intentional presence-probe, not a use.

### IN-02: `_supports_batched` re-checked every tick via `hasattr` over all trackers

**File:** `src/segugio/orchestrator/loop.py:256-270`
**Issue:** `_supports_batched()` runs `all(hasattr(t, "model") and hasattr(t, "update") ...)`
over every tracker on EVERY `_fan_out` call (every tick). The tracker set is fixed at
construction, so this is a constant result recomputed ~30×/s. Not a perf-scope concern per se,
but it is needless per-tick work on the hot path that could be resolved once in `__init__`.
**Fix:** Compute the batched-capability flag once in `__init__` and read the cached bool.

### IN-03: `_tick_once` probe key `"total"` is written without being in `_LATENCY_STAGES`

**File:** `src/segugio/orchestrator/loop.py:579-588`
**Issue:** `probe["total"].append(...)` assumes the caller pre-seeded a `"total"` key. Both
callers (`run` passes `probe=None`; `run_measured` seeds `probe["total"] = []` at line 658) do,
so it works — but `_LATENCY_STAGES` deliberately excludes `"total"`, and any new caller building
a probe from `{s: [] for s in _LATENCY_STAGES}` (as the instance accumulator at line 188 does)
would `KeyError` on `probe["total"]`. Implicit cross-function key contract.
**Fix:** Document that a probe dict must carry a `"total"` key, or seed it defensively with
`probe.setdefault("total", []).append(...)`.

### IN-04: `PreviewDoc.__post_init__` assumes each `cams` value is dict-coercible

**File:** `src/segugio/opcomm/records.py:200-201`
**Issue:** `{str(k): dict(v) for k, v in cams.items()}` calls `dict(v)` on each camera value. If a
torn/attacker-touched `preview.json` carried `cams: {"cam_a": 5}`, `dict(5)` raises `TypeError`.
This is CAUGHT by `read_preview`'s `except (ValueError, TypeError)` boundary (channel.py:222), so
it correctly degrades to `PreviewDoc()` and never reaches the loop — RBT-04 is upheld. Noting it
because the safety relies entirely on the channel boundary catching a constructor `TypeError`;
constructing a `PreviewDoc` directly (e.g. in the publisher with a malformed cam value) would
raise. Low risk given the publisher always builds well-formed dicts.
**Fix:** None required; optionally guard with `dict(v) if isinstance(v, dict) else {}` to make the
record self-defending independent of the channel boundary.

---

_Reviewed: 2026-06-13T11:54:52Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
