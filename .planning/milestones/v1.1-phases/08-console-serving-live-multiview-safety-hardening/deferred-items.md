# Phase 08 — Deferred / Out-of-Scope Items

Discovered during execution; NOT caused by the current plan's changes.

## 08-01

- **`tests/test_fan_out_batched.py` — 4 failures (pre-existing, environmental).**
  `ModuleNotFoundError: No module named 'ultralytics'` raised from
  `src/segugio/tracking/reid_check.py:113`. The heavy GPU/tracking stack (ultralytics/torch)
  is not installed in the active CPU-only py3.14 venv — per project MEMORY it lives in
  `venv312/`. These tests touch none of the 08-01 files (console/opcomm) and fail identically
  on the baseline commit `4997e51`. Out of scope for this plan (run under `venv312` or guard
  with a heavy/gpu skip marker — a separate concern). Affected tests:
  `test_fan_out_one_batched_forward_per_tick`, `test_fan_out_fp16_half_threaded`,
  `test_fan_out_none_frame_coasts`, `test_fan_out_dog_index_resolved_by_name`.
