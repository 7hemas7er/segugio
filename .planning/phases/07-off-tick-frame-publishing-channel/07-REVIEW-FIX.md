---
phase: 07-off-tick-frame-publishing-channel
fixed_at: 2026-06-13T12:20:00Z
review_path: .planning/phases/07-off-tick-frame-publishing-channel/07-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-06-13T12:20:00Z
**Source review:** .planning/phases/07-off-tick-frame-publishing-channel/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 6
- Skipped: 0
- Info findings (IN-01..IN-04): out of scope this pass, not attempted.

**Domain invariants preserved:** `offer()` stays a non-blocking locked pointer swap (RBT-04
coast-on-fault); cv2/numpy imports remain lazy inside `_publish`/`_cv2_encode` (no heavy import
hoisted to module top-level); `atomic_write_bytes(fsync=False)` for ephemeral JPEGs left intact;
the disabled-publisher (`config.preview.enabled=False`) path remains a `None` publisher,
byte-identical to v1.0.

## Fixed Issues

### CR-01: Repeated `start()` leaks a daemon and two publishers race on the same atomic temp path

**Files modified:** `src/segugio/orchestrator/preview.py`
**Commit:** dfd2c51
**Applied fix:** Made `PreviewPublisher.start()` idempotent — it now early-returns when
`self._thread is not None and self._thread.is_alive()`, so a second back-to-back `start()`
(as `Orchestrator.run_measured` drives in `tests/test_latency.py`) never overwrites
`self._thread`, never orphans the first daemon, and never lets two daemons race on the fixed
atomic temp path. The defense-in-depth unique-temp-name suggestion was not added; the idempotent
guard is the primary, sufficient fix and keeps the atomic primitive unchanged.

### WR-01: `stop()` can block up to one full publish period

**Files modified:** `src/segugio/orchestrator/preview.py`
**Commit:** 86500eb
**Applied fix:** In `_run`, replaced both `time.sleep(self._period)` calls with a single
period wait on the stop event — `if self._stop.wait(self._period): break`. `Event.wait` returns
immediately when `stop()` fires, so the RBT-04 SAFE shutdown path is no longer blocked by a long
(low-fps) publish period. The loop was restructured to `while True` (the wait subsumes the old
top-of-loop `_stop.is_set()` check). The now-unused `import time` was removed to keep the module
lint-clean. Behaviour on the publish path is unchanged: drain → publish-if-present → wait period.

### WR-02: `_gen` increment is a non-atomic read-modify-write outside the lock

**Files modified:** `src/segugio/orchestrator/preview.py`
**Commit:** a9a64a4
**Applied fix:** `_build_doc` now bumps `self._gen` under `self._lock` and snapshots the value
into a local `gen`, which is passed to `PreviewDoc(gen=gen, ...)`. The lock is cheap and off the
tick; this makes the cache-bust token's monotonicity robust to any future second writer rather
than relying solely on the CR-01 single-writer guarantee.

### WR-03: `make_config(overrides=...)` shallow top-level `update` drops sibling keys

**Files modified:** `tests/conftest.py`
**Commit:** 80e534c
**Applied fix:** `_build` now deep-merges overrides via a new local `_deep_merge` helper
(dict-into-dict recursion; scalars/lists/type-mismatches replace wholesale) instead of the
shallow `raw.update(...)`. A nested override such as `{"model": {"use_fp16": True}}` now updates
only that sub-key and preserves sibling `model` keys. The fixture docstring was updated to state
the deep-merge semantics. All GPU latency tests that restate full blocks remain valid; future
single-sub-key overrides no longer silently reset siblings.

### WR-04: `_read_run_and_override` docstring claims a 3-tuple; it returns a 2-tuple

**Files modified:** `src/segugio/orchestrator/loop.py`
**Commit:** 8b48318
**Applied fix:** Corrected the docstring to state `Returns (run, override)` — a 2-tuple — and
noted that `just_started` is read off the returned `run` record, not returned separately.
Docstring-only change; no runtime behaviour affected.

### WR-05: `offer()` stores `scores`/`dets` by reference with an undocumented mutation assumption

**Files modified:** `src/segugio/orchestrator/preview.py`
**Commit:** bbe2d0b
**Applied fix:** Extended the module-level frame-snapshot forward-assumption docstring to
explicitly cover `scores` (list) and `dets` (dict): both are stored by reference in `offer()` and
read off-thread by the daemon; the safety rests on the scorer/fan-out producing a fresh list/dict
each tick with frozen-dataclass elements. The docstring now instructs a future in-place-mutating
scorer/fan-out to snapshot `scores`/`dets` the same way frame buffers would need copying.
Docstring-only change; no runtime behaviour affected.

## Skipped Issues

None — all six in-scope findings were fixed.

## Verification

- **Per-fix:** Tier 1 (re-read modified section) + Tier 2 (`ast.parse` syntax check) passed for
  every commit. WR-02's lock change is structural (not a logic-condition change), so no
  human-verification flag was required.
- **Regression suite (CPU venv, headless):** `venv/Scripts/python.exe -m pytest` across
  `tests/test_preview_publisher.py`, `tests/test_atomic_io.py`, `tests/test_preview_channel.py`,
  `tests/test_orchestrator_runtime.py`, `tests/test_fault_isolation.py`, `tests/test_ui_score.py`
  → **58 passed in 5.16s**, 0 failed. The gpu-marked `tests/test_latency.py` auto-skips on the
  CPU venv as expected (not forced).

---

_Fixed: 2026-06-13T12:20:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
