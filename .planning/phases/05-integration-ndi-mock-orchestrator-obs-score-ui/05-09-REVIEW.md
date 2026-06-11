---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/segugio/orchestrator/runtime.py
  - src/segugio/__main__.py
  - src/segugio/orchestrator/__init__.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 05-09: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the gap-closure wiring added by plan 05-09: the runtime compose/factory
`build_orchestrator` (`src/segugio/orchestrator/runtime.py`), the `python -m segugio`
entry point (`src/segugio/__main__.py`), and the package re-export
(`src/segugio/orchestrator/__init__.py`).

The lazy-import boundary is correctly preserved — all heavy deps (cyndilib / obsws-python /
cv2 / ultralytics / torch) are imported only inside the default factory bodies, and the
existing import-smoke tests (Test 5 / Test 9) cover that contract. The argparse wiring,
exit-code behaviour, the OBS-default seam, and the per-camera tracker mapping are correct.
The dog-class-by-name concern raised in the prompt is a non-issue: the factory seeds
`PerCameraTracker` with `config.model.class_index`, but the loop overwrites `tracker.dog_idx`
via `resolve_dog_index(...)` at first inference (`loop.py:260-264`), so 16 is never
hardcoded into the live path.

The dominant defect is a **launch-order coupling**: neither `build_orchestrator` nor
`main()` creates `channel_dir`, so when the orchestrator is started before (or without) the
Flask console, every D-11 status write silently fails forever — the operator panel's reverse
channel is dead. A secondary robustness gap: heavy-collaborator construction inside
`build_orchestrator` runs OUTSIDE the loop's RBT-04 fault isolation, so a YOLO load failure
crashes the entry point with a traceback despite the "never crash" framing.

## Critical Issues

### CR-01: `channel_dir` is never created — D-11 status reverse-channel silently dies when the orchestrator launches before/without the UI

**File:** `src/segugio/orchestrator/runtime.py:67-76`, `138`; `src/segugio/__main__.py:82`
**Issue:**
`build_orchestrator` derives `channel_paths` under `channel_dir` (`_channel_paths`) and the
entry point passes `args.opcomm_dir` straight through, but **nothing ever creates that
directory**. Directory creation lives ONLY in the UI: `create_app` does
`os.makedirs(channel_dir, exist_ok=True)` (`src/segugio/ui/app.py:69`). The orchestrator
writes its D-11 status into the same dir via `write_status` → `atomic_write_json` →
`_temp_path` → `open(tmp, "w")` (`src/segugio/opcomm/atomic.py:74-79`), which raises
`FileNotFoundError` when the parent dir does not exist.

This is the normal field/launch order: the operator may start `python -m segugio` before the
console process, or point `--opcomm-dir` at a fresh path. The default opcomm dir
(`./opcomm`, `__main__.py:38-40`) does not exist on a clean checkout.

Because every status write happens inside the RBT-04 try/except (`_apply` inside
`_tick_once`, and `_to_safe`'s own guarded write, `loop.py:360-392`), the loop does NOT
crash — but it **never writes a single status file**. The operator panel polls `status.json`
(D-11) and sees nothing forever: the reverse channel is permanently dead, and the failure is
invisible (only debug/warning logs). The opcomm channel is the single coupling between the two
processes (`opcomm/channel.py:1-14`), so this defeats the panel read-back the gap plan exists
to enable.

Note the command/runstate READ side degrades gracefully (`_read_json` returns `None` on
`FileNotFoundError` → safe default), so the orchestrator still *runs*; only the operator's
visibility silently breaks. That asymmetry is exactly why this is easy to miss in the
`tmp_path`-based tests (`test_orchestrator_runtime.py` always passes a dir pytest already
created).

**Fix:** Create the channel dir at compose time, mirroring the UI:
```python
# runtime.py, inside build_orchestrator before _channel_paths(channel_dir):
import os
os.makedirs(channel_dir, exist_ok=True)
channel_paths = _channel_paths(channel_dir)
```
(Equivalently, call `os.makedirs(args.opcomm_dir, exist_ok=True)` in `__main__.main` before
`build_orchestrator`.) Add a regression test that builds against a non-existent nested path
and asserts a status write lands.

## Warnings

### WR-01: Heavy-collaborator construction runs OUTSIDE RBT-04 fault isolation — a YOLO/weights failure crashes `python -m segugio` at launch

**File:** `src/segugio/__main__.py:82-89`; `src/segugio/orchestrator/runtime.py:93-97,142-152`
**Issue:**
`__main__.main` calls `orch = build_orchestrator(config, args.opcomm_dir)` BEFORE the
`try/except KeyboardInterrupt`. Inside, `_default_tracker_factory` constructs one
`PerCameraTracker` per camera, and `PerCameraTracker.__init__` does `YOLO(str(model_path))`
(`detector.py:147`), which can raise on a missing/corrupt weight file, an offline first-use
download, or a CUDA/driver init error. `_default_source_factory` likewise constructs the real
`NdiFrameSource`. None of this is wrapped.

The `__main__` and `loop.py` docstrings frame launch robustness as satisfied because
`_safe_startup` absorbs `source.start()` / `obs.connect()` (`loop.py:453-465`). But that only
covers the *start/connect* calls — the *construction* of the heavy clients happens earlier, in
`build_orchestrator`, and is unprotected. A misconfigured deploy box (no GPU, bad
`model.path`, no network for the auto-download) therefore crashes the director with a raw
traceback and a non-zero exit, contradicting the RBT-04 "nessun crash ammesso" framing the
module advertises.

**Fix:** Either wrap construction so a build failure logs and exits cleanly (deliberate fast
fail with a clear message and a documented non-zero code), or move the heavy client
construction behind the loop's lifecycle (lazy-construct on first `start()`). At minimum,
narrow the `__main__`/`loop` docstrings so they do not claim launch-time crash-immunity that
the construction path does not provide.

### WR-02: A camera with `ndi_source: None` still loads a full YOLO model that can never receive a frame

**File:** `src/segugio/orchestrator/runtime.py:149-152`
**Issue:**
`build_orchestrator` builds one tracker for EVERY `config.cameras` entry, but `NdiFrameSource`
only spawns a receiver thread for cameras whose `ndi_source is not None`
(`ndi_source.py:63-65`). `Camera.ndi_source` defaults to `None` (`config/models.py:78`), and
the schema permits a camera with no source (e.g. a SAFE-only camera). For such a camera,
`source.latest(cam_id)` returns `None` forever → the per-camera fan-out always coasts, yet the
factory has already paid the full cost of loading a YOLO model for it. On a constrained deploy
GPU this is a wasted model load (and on the real path, an unnecessary native-ReID gate target).

The example config (`config.example.yaml`) gives every camera a source, so this is latent, not
currently triggered — but it is a correctness/robustness smell the moment a SAFE-only or
source-less camera is configured.

**Fix:** Build a tracker only for cameras that actually have a feed, e.g.
`{cam.id: tracker_factory(...) for cam in config.cameras if cam.ndi_source is not None}` —
and confirm the loop tolerates a missing tracker for source-less cameras (today `_fan_out`
does `self.trackers[cam_id]` unconditionally, `loop.py:255`, so the loop would need the same
guard, or the source-less camera must be excluded from the fan-out). Decide one consistent
rule across `runtime.py` and `loop.py`.

### WR-03: `_DEFAULT_OPCOMM_DIR` is frozen at import time and may diverge from the UI's runtime-resolved default

**File:** `src/segugio/__main__.py:38-40`
**Issue:**
`_DEFAULT_OPCOMM_DIR` is computed at module-import time using `os.getcwd()`. The UI resolves
its equivalent default at run-time inside the `if __name__ == "__main__"` block
(`ui/app.py:142`). If anything changes the working directory between import and use (a launcher
script, a test harness, an embedding host), the two processes silently resolve DIFFERENT
default opcomm dirs and stop sharing a channel — exactly the failure mode the comment claims to
prevent ("share ONE channel dir out of the box"). Import-time cwd capture is fragile for a
value whose whole purpose is cross-process agreement.

**Fix:** Resolve the default lazily inside `_parse_args`/`main` (compute the `default=` when
parsing, not at import), so it reflects the cwd at invocation and matches the UI's run-time
resolution. Also prefer reading `SEGUGIO_OPCOMM_DIR` at call time so an env change after import
is honoured.

### WR-04: `main()` returns exit code 0 even when the run loop terminates abnormally

**File:** `src/segugio/__main__.py:83-89`
**Issue:**
`main` only distinguishes a clean stop from a `KeyboardInterrupt`; both return 0. But
`Orchestrator.run()` is an infinite loop that exits only via `stop()` (never wired here) or by
an exception. The `_tick_once` body is fault-isolated, but `run()` itself is not fully
guarded: e.g. a `BaseException` other than `KeyboardInterrupt` (or a failure in the
`finally: shutdown()` path) would propagate out of `try`, skip the `except KeyboardInterrupt`,
and crash `main` — which then yields a non-zero traceback exit rather than a controlled code.
More subtly, if `run()` ever returns normally (rate loop exits), `main` returns 0 with no
signal that the director stopped unexpectedly. For a "never crash" live tool, the entry point
should classify *why* the loop ended.

**Fix:** Broaden handling: catch `KeyboardInterrupt` (clean, rc 0) separately from any other
`Exception` (log + best-effort `shutdown()` + return a non-zero rc), and treat an unexpected
normal return from `run()` as an abnormal stop. Keep `shutdown()` best-effort in every branch.

## Info

### IN-01: `_default_tracker_factory` parameter named `class_index` while the constructed `PerCameraTracker` calls it `dog_idx`

**File:** `src/segugio/orchestrator/runtime.py:93-97`
**Issue:**
The factory signature uses `class_index`, but `PerCameraTracker.__init__(model_path, dog_idx,
tracker_yaml)` (`detector.py:130`) and the test fake both treat the 2nd positional as the dog
index. The wiring is correct (positional), but the name mismatch obscures that this value is
the *configured seed* the loop later overwrites by name. Aligning the name (or a one-line
comment) reduces the chance a future edit passes it by keyword to the wrong param.
**Fix:** Rename to `dog_idx` (or `class_index_seed`) and note that `loop._fan_out` resolves the
real index by name at first inference.

### IN-02: `_DEFAULT_OBS_PASSWORD` is an unused module constant

**File:** `src/segugio/orchestrator/runtime.py:61,145`
**Issue:**
`_DEFAULT_OBS_PASSWORD` is defined and passed to `obs_factory`, which is correct, but it is a
plain `None` constant that duplicates `ObsWsController`'s own default (`obsws_controller.py:67`)
and the `_DEFAULT_OBS_HOST`/`_DEFAULT_OBS_PORT` triple is purely a placeholder until a
`config.obs` model exists (acknowledged in the module docstring). Not a defect — flagged only
so the intentional hardcoded-default seam is visible to the next reviewer and gets revisited
when OBS creds move into `Config`.
**Fix:** None required; leave a `# TODO(config.obs)` marker so the temporary hardcoding is
greppable when the Config model gains an `obs` block.

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
