---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 09
subsystem: orchestrator
gap_closure: true
tags: [entry-point, runtime-factory, lazy-import, rbt-04, uat-gap]
requires:
  - "segugio.orchestrator.loop.Orchestrator.from_config (the signature the factory calls — unchanged)"
  - "segugio.config.loader.load_config (fail-fast SystemExit(2) on a bad config)"
  - "segugio.ndi.ndi_source.NdiFrameSource / segugio.obs.obsws_controller.ObsWsController / segugio.tracking.detector.PerCameraTracker (the real collaborators, built lazily)"
provides:
  - "segugio.orchestrator.runtime.build_orchestrator(config, channel_dir, *, fps, grace, source_factory, obs_factory, tracker_factory) -> Orchestrator"
  - "python -m segugio <config.yaml> [--rate R] [--opcomm-dir DIR] (segugio.__main__.main)"
  - "docs/run.md — the exact OBS-up / OBS-down rig launch making UAT Tests 1-4 executable"
affects:
  - "the D-07 hardware E2E (UAT Tests 1-4) — now launchable on the Windows/RTX rig"
tech-stack:
  added: []
  patterns:
    - "injectable construction seam: the three *_factory params default to real LAZY builders, overridable with fakes for headless unit tests (same pattern as ObsWsController.client_factory / NdiFrameSource._run_receiver)"
    - "lazy-import boundary held: heavy deps (cyndilib/obsws/cv2/ultralytics/torch) live ONLY inside the default factory bodies — module-top imports stay light"
key-files:
  created:
    - src/segugio/orchestrator/runtime.py
    - src/segugio/__main__.py
    - tests/test_orchestrator_runtime.py
    - docs/run.md
  modified:
    - src/segugio/orchestrator/__init__.py
    - tests/test_imports.py
decisions:
  - "OBS creds hardcoded to localhost/4455/None (Config has no obs block, extra=\"forbid\"); sourcing from YAML is a future Config-model change, out of scope for this thin-wiring plan"
  - "channel filenames defined as runtime.py constants IDENTICAL to ui/app.py so the console and the orchestrator share one channel dir (no re-invented names)"
  - "tracker seeded with config.model.class_index (never hardcoded 16); the loop resolves the dog index BY NAME at first inference (CFG-04)"
  - "no crash handling around run() beyond KeyboardInterrupt — the loop is already fault-isolated (RBT-04) and _safe_startup (05-07) absorbs a down OBS/NDI at launch"
metrics:
  duration: 4min
  completed: 2026-06-11
---

# Phase 05 Plan 09: Runnable Entry Point (UAT gap closure) Summary

`python -m segugio <config.yaml>` now exists: a `build_orchestrator` runtime factory composes the
real `NdiFrameSource` + `ObsWsController` + per-camera `PerCameraTracker` from a validated `Config`
and calls `Orchestrator.run()`, closing the one UAT gap that blocked the D-07 hardware E2E.

## What was built

The UAT gap (status: failed, severity: major) was that Phase 05 verified the orchestrator loop
LOGIC headlessly (5/5) but shipped NO runnable entry point — `Orchestrator.from_config(...)`
deliberately requires the real `source`/`obs`/`trackers`/`channel_paths` to be built and injected
by a caller that did not exist. This plan adds exactly that caller, plus the entry point and the
rig launch doc. `from_config`'s signature is unchanged — the new factory CALLS it.

### Task 1 — `build_orchestrator` runtime factory (commit a6a8a66)

`src/segugio/orchestrator/runtime.py`: `build_orchestrator(config, channel_dir, *, fps=30.0,
grace=None, source_factory=None, obs_factory=None, tracker_factory=None) -> Orchestrator`.

- Maps `config.cameras` onto ONE `NdiFrameSource` over all cameras, ONE `ObsWsController`
  (localhost/4455/None), and ONE `PerCameraTracker` per camera (seeded with `config.model.path` +
  `class_index`, tracker yaml `"botsort_dog.yaml"`), then `return Orchestrator.from_config(...)`.
- Channel paths built from `channel_dir` with the SAME constant filenames as `ui/app.py`
  (`command.json` / `runstate.json` / `status.json` + `score.json` / `overlay.txt`).
- The three `*_factory` params default to real LAZY builders (heavy imports inside the builder
  bodies) and are INJECTABLE — so the headless test passes fakes with no cyndilib/obsws/cv2/ultralytics.
- Re-exported `build_orchestrator` from `orchestrator/__init__.py`.
- 6 headless regression tests: compose-one-tracker-per-camera, channel paths point at the constant
  filenames, obs_factory called with the OBS defaults, source_factory called with all cameras,
  tracker seeded with config.model, and `import segugio.orchestrator.runtime` succeeds heavy-absent.

### Task 2 — `python -m segugio` entry point + run doc + import-smoke (commit 9ec23ca)

`src/segugio/__main__.py`: `main(argv=None) -> int` + the `if __name__ == "__main__"` guard.

- argparse: positional `config` + `--rate` (default 30.0) + `--opcomm-dir` (default
  `SEGUGIO_OPCOMM_DIR` env or `./opcomm`, mirroring `ui/app.py`).
- `load_config(args.config)` (fails fast on a bad config) → `build_orchestrator(config,
  args.opcomm_dir)` → `try: orch.run(args.rate) except KeyboardInterrupt: orch.shutdown()`.
  Ctrl-C coasts OBS to SAFE (RBT-04). Light imports only at module top.
- 4 main() wiring tests (arg→factory→run, KeyboardInterrupt→shutdown, --rate/--opcomm-dir flow,
  lazy-import boundary) with `build_orchestrator` monkeypatched — no heavy deps imported.
- Added `segugio.__main__` + `segugio.orchestrator.runtime` to the heavy-absent import-smoke
  surface in `tests/test_imports.py`.
- `docs/run.md`: the exact OBS-up and OBS-down launch commands, the operator-console launch, the
  opcomm dir contract, and a table mapping the commands to UAT Tests 1-4.

## Verification

- `pytest tests/test_orchestrator_runtime.py tests/test_imports.py -m "not gpu and not ndi and not obs" -q` → all green (10 runtime tests + import-smoke).
- `python -c "import segugio.__main__, segugio.orchestrator.runtime"` → succeeds with cyndilib/obsws/cv2/ultralytics/torch absent (lazy boundary intact).
- Full headless suite: **314 passed, 3 skipped, 0 failures** (baseline was 302 passed; +12 new, zero regression).
- `docs/run.md` contains the literal `python -m segugio` launch commands (9 occurrences) for both OBS-up and OBS-down.

HARDWARE-DEFERRED (D-07, unchanged): actually running `python -m segugio config.example.yaml` on
the Windows/RTX rig against live OBS + NDI senders is UAT Tests 1-4 — this plan makes that command
EXIST and be launchable.

## Deviations from Plan

None - plan executed exactly as written. No auto-fixes, no architectural changes, no auth gates.

## Self-Check: PASSED
