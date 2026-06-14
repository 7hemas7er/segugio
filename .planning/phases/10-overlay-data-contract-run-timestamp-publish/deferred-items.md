# Phase 10 — Deferred Items

## Out-of-scope test failures (environmental, NOT caused by Phase 10 changes)

- `tests/test_fan_out_batched.py` — 4 failures, all `ModuleNotFoundError: No module named 'ultralytics'`:
  - `test_fan_out_one_batched_forward_per_tick`
  - `test_fan_out_fp16_half_threaded`
  - `test_fan_out_none_frame_coasts`
  - `test_fan_out_dog_index_resolved_by_name`

  **Root cause:** the heavy GPU stack (`ultralytics`) is not installed in the active py3.14 CPU-only `venv/`. Per project MEMORY, GPU work runs from `venv312/` (py3.12 + cu126 torch + tensorrt). These tests exercise `src/segugio/tracking/reid_check.py` / fan-out batched inference — a GPU concern entirely unrelated to the Phase-10 crash-isolated console (`src/segugio/ui/app.py` imports only Flask + opcomm + stdlib).

  **Why deferred (not fixed):** scope boundary — Phase 10 modified only `ui/app.py` + test files; these failures pre-date this plan and are an environment/venv concern. Run the full suite from `venv312/` (or with `pip install ultralytics`) to clear them.
