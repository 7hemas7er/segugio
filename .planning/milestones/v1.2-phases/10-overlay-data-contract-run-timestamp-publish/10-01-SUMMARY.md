---
phase: 10-overlay-data-contract-run-timestamp-publish
plan: 01
subsystem: tests
tags: [overlay, opcomm, flask, crash-isolation, test-scaffold, wave-0]
requires:
  - "tests/conftest.py file_channel fixture (05-01)"
  - "tests/test_preview_channel.py / test_ui_run.py / test_config_engine_keys.py (analog idioms)"
provides:
  - "tests/test_opcomm_overlay_run.py — OverlayRunDoc round-trip/safe-default/frozen/normalize scaffold (xfail->10-02)"
  - "tests/test_config_overlay.py — OverlayParams default/optional-block/explicit/gt0/extra-forbid scaffold (xfail->10-03)"
  - "tests/test_ui_overlay_json.py — /overlay-json route + gen-bump + byte-for-byte runstate scaffold (xfail->10-04)"
  - "file_channel['overlay_run'] fixture key pointing at overlay_run.json"
affects:
  - "Plan 10-02 (creates OverlayRunDoc + read/write_overlay_run; removes test_opcomm_overlay_run xfails)"
  - "Plan 10-03 (creates OverlayParams + Config.overlay; removes test_config_overlay xfails)"
  - "Plan 10-04 (creates /overlay-json + gen bump + overlay_run side-write; removes test_ui_overlay_json xfails)"
tech-stack:
  added: []
  patterns:
    - "RED-by-design test scaffold: xfail(strict=False) + missing-symbol imports INSIDE test bodies → collection stays green pre-implementation; ImportError under xfail = expected fail"
    - "stays-true regression guard (no xfail) for the byte-for-byte runstate.json invariant (D-03)"
key-files:
  created:
    - "tests/test_opcomm_overlay_run.py"
    - "tests/test_config_overlay.py"
    - "tests/test_ui_overlay_json.py"
  modified:
    - "tests/conftest.py"
decisions:
  - "test_runstate_byte_for_byte_unchanged carries NO xfail — it is a stays-true regression guard (the invariant holds today; Plan 10-04 must keep it holding), not a lands-later behavior"
  - "missing-symbol imports placed inside each xfail test body (not module-level) so collection never errors before the implementing plan lands the symbols"
metrics:
  duration: 8min
  tasks: 2
  files: 4
  completed: "2026-06-14"
---

# Phase 10 Plan 01: Wave-0 Overlay Test Surface Summary

Wave-0 test contract for the overlay data channel: 3 new RED-by-design test files (21 xfail tests + 1 stays-true guard) named 1:1 with 10-VALIDATION.md, plus the `overlay_run` `file_channel` fixture key — locking the validation contract before any implementation so Waves 1-2 cannot drift from the locked D-01..D-08 decisions or the byte-for-byte `runstate.json` invariant.

## What Was Built

- **`tests/conftest.py`** — added `"overlay_run": d / "overlay_run.json"` to the `file_channel` fixture (no existing key changed) so route tests can address the NEW console-owned `overlay_run.json` separately from the director-read `runstate.json`. Docstring updated to document the key and the separation rationale.
- **`tests/test_opcomm_overlay_run.py`** (NEW, 5 functions) — unit scaffold mirroring `test_preview_channel.py`: `test_overlay_run_round_trip`, `test_overlay_run_default_when_absent`, `test_overlay_run_default_when_malformed` (parametrized: torn JSON / binary garbage / wrong-shape / empty), `test_overlay_run_doc_is_frozen`, `test_overlay_run_doc_normalizes` (bool/float|None/int coercion + `started_at=None` survives). All xfail → Plan 10-02.
- **`tests/test_config_overlay.py`** (NEW, 5 functions) — pydantic scaffold mirroring `test_config_engine_keys.py`: `test_freestyle_duration_defaults_to_120`, `test_config_without_overlay_block_still_validates` (via `make_config`), `test_freestyle_duration_explicit_value`, `test_freestyle_duration_nonpositive_rejected` (parametrized 0 / -1), `test_overlay_params_extra_forbid`. All xfail → Plan 10-03.
- **`tests/test_ui_overlay_json.py`** (NEW, 11 functions) — Flask route scaffold mirroring `test_ui_run.py` (client fixture verbatim): the run-edge stamping pair, the 6-key payload + `no-store` shape, the two safe-default tests (absent + torn-both-sources), verbatim-fields (D-08), `server_now`+`gen` presence, gen-bumps-on-run/score, gen-seeds-from-disk + started_at-persist-across-restart (D-02), and `test_runstate_byte_for_byte_unchanged` (the HARD D-03 director-never-touched proof). 10 xfail → Plan 10-04; the byte-for-byte guard is a plain passing test.

## How It Works

Each lands-later test imports its not-yet-existing production symbol (`OverlayRunDoc`, `OverlayParams`, `read/write_overlay_run`, the `/overlay-json` route) **inside the test body**, never at module top. Combined with `@pytest.mark.xfail(strict=False)`, this means: collection never errors (no top-level import of a missing symbol), and at run-time the `ImportError` is absorbed as an expected fail. The suite stays green. When the implementing plan lands the symbol, the test starts genuinely passing and that plan REMOVES the xfail marker, flipping it into a permanent regression guard.

The one exception, `test_runstate_byte_for_byte_unchanged`, carries no xfail: the invariant it asserts (POST `/run` writes `runstate.json` byte-identically to a baseline `write_runstate`) is true *today* because `post_run` already calls the unchanged `write_runstate`. It is a stays-true guard — Plan 10-04 must append its `overlay_run` side-write strictly AFTER `write_runstate` without perturbing a single byte of the director-read file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_runstate_byte_for_byte_unchanged` removed from the xfail set**
- **Found during:** Task 2 verification (`pytest -rX` reported 1 XPASS)
- **Issue:** The plan instructed marking *every* test in `test_ui_overlay_json.py` with xfail. But the byte-for-byte runstate invariant already holds in the current codebase (Phase 10 hasn't touched `post_run` yet), so the test passes today — it XPASSed, which silently contradicts the must-have "never silently passing on absent implementation" and would have hidden a future D-03 regression behind a non-strict xfail.
- **Fix:** Removed the xfail marker from that one test so it is a true green stays-true regression guard; updated the module docstring to document the single exception. The other 10 lands-later tests keep their xfail markers.
- **Files modified:** tests/test_ui_overlay_json.py
- **Commit:** 3043b38

## Verification

- `pytest tests/test_opcomm_overlay_run.py tests/test_ui_overlay_json.py tests/test_config_overlay.py --collect-only -q` → exit 0 (all three scaffolds collect; 6 + 11 + 8 = 25 items).
- `pytest <all three> -q` → exit 0: 24 xfail + 1 pass (the byte-for-byte guard), zero error, zero XPASS.
- `pytest tests/test_ui_run.py tests/test_ui_score.py -q` → still green (the `file_channel` fixture change did not regress existing route tests).
- No `import numpy` / `import cv2` / `import torch` in any of the three new files (crash-isolation allowlist preserved — RBT-07).

## Validation Map Coverage

Every Wave-0 behavior row in 10-VALIDATION.md (lines 44-57) has its named test function present in a new file. The crash-isolation row (L58, `test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent`) is explicitly out of scope for this plan — it EXTENDS an existing test that lives in the same file as the `/overlay-json` route it exercises, so it is owned by Plan 10-04.

## Self-Check: PASSED

- FOUND: tests/conftest.py, tests/test_opcomm_overlay_run.py, tests/test_config_overlay.py, tests/test_ui_overlay_json.py
- FOUND commits: 145c26c (Task 1), 3043b38 (Task 2)
