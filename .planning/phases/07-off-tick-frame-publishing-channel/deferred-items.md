# Phase 07 — Deferred Items (out-of-scope discoveries)

| Discovered during | Item | Reason deferred |
|-------------------|------|-----------------|
| 07-01 full-suite regression | `tests/test_fan_out_batched.py` (4 tests) fail with `ModuleNotFoundError: No module named 'ultralytics'` in the CPU-only py3.14 `venv/`. | PRE-EXISTING and environmental, NOT caused by this plan. The file predates 07-01 (present at `0b88c07`). It transitively imports `segugio.tracking.reid_check`, which needs the heavy GPU stack (`ultralytics`/`torch`). Per MEMORY.md, GPU-dependent tests run from `venv312/` (py3.12 + cu126 torch); the py3.14 `venv/` is CPU-only and these collect-fail there. This plan touches only `opcomm/` + `config/models.py` — none of the fan-out surface. Out of scope per the scope-boundary rule. |
