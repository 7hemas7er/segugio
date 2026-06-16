# Phase 13 — Deferred Items (out-of-scope discoveries)

## Pre-existing test failures (NOT caused by this plan, NOT fixed — out of scope)

- **`tests/test_fan_out_batched.py` (4 tests fail):** `ModuleNotFoundError: No module named 'ultralytics'`.
  - **Discovered during:** 13-01 plan-level full-suite run (`python -m pytest -q`).
  - **Cause:** the active py3.14 `venv/` is CPU-only and does not install the heavy GPU stack (ultralytics/torch). Per MEMORY.md, GPU-dependent tests run only from `venv312/` (py3.12 + cu126). These tests import `ultralytics.trackers.bot_sort.ReID` inside `src/segugio/tracking/reid_check.py`.
  - **Scope:** this plan (13-01) edits one OBS JSON data file + extends a pure-Python test; it touches no runtime code and is unrelated to these failures. `git diff 47ad625 HEAD --stat` confirms only `obs/segugio-scene-collection.json` and `tests/test_scene_template.py` changed.
  - **Action:** none taken (deferred). The plan-relevant suite `tests/test_scene_template.py` is fully green (7 passed). Run the GPU suite from `venv312/` to exercise `test_fan_out_batched.py`.
