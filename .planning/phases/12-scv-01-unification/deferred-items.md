# Phase 12 — Deferred Items (out-of-scope discoveries)

These were observed during execution but are NOT caused by Phase-12 changes. Logged per the
executor scope boundary; left unfixed.

## 12-02

- **4 failing tests in `tests/test_fan_out_batched.py`** (`test_fan_out_one_batched_forward_per_tick`,
  `test_fan_out_fp16_half_threaded`, `test_fan_out_none_frame_coasts`,
  `test_fan_out_dog_index_resolved_by_name`). All fail with
  `ModuleNotFoundError: No module named 'ultralytics'` raised inside
  `src/segugio/tracking/reid_check.py` (the heavy GPU stack). This is an environment artifact of
  the CPU-only `venv` (per MEMORY: GPU work runs from `venv312/` which has `ultralytics`/torch);
  the tests last changed in Phase 06/07 and are wholly unrelated to the UI/overlay surface this
  phase touches. Out of scope for 12-02 — do NOT fix here. Re-run under `venv312/` if a GPU-path
  regression is suspected.
