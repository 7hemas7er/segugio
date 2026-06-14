---
phase: 10-overlay-data-contract-run-timestamp-publish
plan: 04
subsystem: ui
tags: [overlay, flask, route, gen, crash-isolation, director-invariant, wave-2]
requires:
  - "10-01: tests/test_ui_overlay_json.py RED scaffold (xfail) + tests/test_imports.py crash-isolation gate"
  - "10-02: OverlayRunDoc + write_overlay_run/read_overlay_run in segugio.opcomm (imported, not redefined)"
  - "src/segugio/ui/app.py get_status/get_preview_jpg/post_run/post_score analogs"
provides:
  - "GET /overlay-json route — boundary-safe {discipline, fields, running, started_at, server_now, gen} + Cache-Control: no-store"
  - "overlay_run.json side-write on POST /run start/stop edges, STRICTLY after the unchanged write_runstate (D-03)"
  - "Lock-guarded monotonic gen seeded from disk at create_app build; bumps on /run AND /score"
  - "_OVERLAY_RUN_FILE constant + _bump_overlay_run/_bump_score_gen closures in create_app"
  - "Extended RBT-07 crash-isolation gate that GETs /overlay-json with the heavy stack absent"
affects:
  - "Phase 11 (JS overlay renderer consumes /overlay-json; offset-cancels skew via server_now/started_at same-clock-domain; resolves fields aliases client-side)"
tech-stack:
  added: []
  patterns:
    - "Closure-held Lock-guarded gen counter seeded from a persisted sidecar (never reset to 0 → restart re-anchors)"
    - "Run-edge side-write STRICTLY after the byte-for-byte-unchanged director read-write (separate file, D-03)"
    - "Route assembled exclusively from never-raise readers + time.time() — no json.load/open in the route (D-04/Pitfall 5)"
    - "Two wall-clock timestamps (started_at on START, server_now per response) in the SAME time.time() domain for skew cancellation (Pitfall 3)"
key-files:
  created: []
  modified:
    - "src/segugio/ui/app.py"
    - "tests/test_ui_overlay_json.py"
    - "tests/test_imports.py"
decisions:
  - "D-02: gen seeds from read_overlay_run(...).gen at create_app build (closure dict + threading.Lock), bumps on /run and /score; /score preserves running/started_at (Open Q1 — not a run edge)"
  - "D-03: write_runstate left byte-for-byte unchanged; overlay_run side-write is a SEPARATE file strictly AFTER it (director never touched — proven by test_runstate_byte_for_byte_unchanged)"
  - "D-04/D-08: /overlay-json assembled from read_score + read_overlay_run + time.time() only; fields verbatim, no server-side alias resolution; server_now+gen always set; Cache-Control: no-store"
  - "Pitfall 3: both started_at and server_now use time.time() (wall clock), never time.monotonic() — same domain so Phase 11 cancels skew"
metrics:
  duration: 9min
  tasks: 2
  files: 3
  completed: "2026-06-14"
---

# Phase 10 Plan 04: Overlay Data Contract Route & Run-Timestamp Publish Summary

The live overlay data contract wired into the crash-isolated console: `GET /overlay-json` serves the boundary-safe 6-key payload (`discipline`, verbatim `fields`, `running`, `started_at`, `server_now`, `gen`) with `Cache-Control: no-store`, assembled exclusively from the two never-raise opcomm readers plus `time.time()` so a torn/absent source returns 200-blank rather than a 500. `POST /run` stamps the NEW console-owned `overlay_run.json` (running/started_at/gen) on the start/stop edge STRICTLY AFTER the byte-for-byte-unchanged `write_runstate` (the director is never touched, D-03), `gen` seeds from disk on `create_app` build and bumps on every `/run` and `/score`, and the RBT-07 crash-isolation gate now serves the new route with the heavy stack forced absent. Flips `tests/test_ui_overlay_json.py` fully GREEN (no xfail remaining).

## What Was Built

- **`src/segugio/ui/app.py`** (Task 1):
  - Extended the channel import with `read_score`, `read_overlay_run`, `write_overlay_run`; extended the records import with `OverlayRunDoc`; added stdlib `time` + `threading` at module top. No heavy import and no `import segugio.config` — the crash-isolation allowlist (Flask in-factory + opcomm + stdlib) is intact.
  - Added the `_OVERLAY_RUN_FILE = "overlay_run.json"` constant beside the existing channel-file constants.
  - In `create_app`, after `os.makedirs`/`_path`: seeded `_state = {"gen": read_overlay_run(_path(_OVERLAY_RUN_FILE)).gen}` (D-02, never reset to 0), a `threading.Lock`, and two helpers — `_bump_overlay_run(running, started_at)` (run edge: gen+1 then persist the new running/started_at) and `_bump_score_gen()` (gen+1 only, re-persisting the CURRENT running/started_at unchanged, Open Q1).
  - `post_run`: left `write_runstate(_path(_RUNSTATE_FILE), run)` EXACTLY as-is; appended STRICTLY AFTER it — `start` → `_bump_overlay_run(running=True, started_at=time.time())`, `stop` → `_bump_overlay_run(running=False, started_at=None)`.
  - `post_score`: left `write_score` + `atomic_write_text(...render_overlay_text...)` unchanged; appended a `_bump_score_gen()` call.
- **`src/segugio/ui/app.py`** (Task 2): added `@app.get("/overlay-json") def get_overlay_json()` mirroring `get_status` — assembles `{discipline: s.discipline.value, fields: s.fields, running, started_at, server_now: time.time(), gen}` from `read_score` + `read_overlay_run`, sets `Cache-Control: no-store`. No `json.load`/`open` in the route, no server-side alias resolution.
- **`tests/test_ui_overlay_json.py`**: removed all 10 `@pytest.mark.xfail` markers (the 11th test, `test_runstate_byte_for_byte_unchanged`, was already marker-free as designed) — all 11 route tests are now permanent regression guards.
- **`tests/test_imports.py`**: extended `test_console_resolves_with_heavy_stack_and_numpy_absent` to build a test client and `GET /overlay-json` under the forced-absent block, asserting 200 + `gen`/`server_now` keys (RBT-07).

## How It Works

`create_app` reads the persisted `overlay_run.json` once at build time through the never-raise `read_overlay_run` boundary and seeds the closure `_state["gen"]` from it — a fresh console over a dir holding `gen=7` continues from 7, and the on-disk `started_at` survives, so a restart re-anchors the Phase-11 freestyle timer (D-02). Every `gen` mutation runs under a `threading.Lock` because the production entrypoint serves multi-threaded (`waitress`/`threaded=True`), so the read-modify-write bump is race-free.

The run-edge stamping is a SEPARATE file from the safety-critical `runstate.json`. `write_runstate` is untouched and runs first every POST; the `overlay_run.json` side-write lands strictly after it. `test_runstate_byte_for_byte_unchanged` baselines the exact bytes `write_runstate` produces for the start/stop edge and asserts `post_run` produces byte-identical files — the literal director-never-touched proof (D-03).

`/overlay-json` assembles its payload only from `read_score` + `read_overlay_run` (both collapse absent/torn/malformed → safe defaults via `_read_json`) plus `time.time()`. `server_now` and `gen` are therefore always present regardless of source state, so a corrupt `score.json`/`overlay_run.json` mid-run yields a 200 blank-safe payload, never a 500 (D-04). `fields` is the raw operator-typed dict (D-08 — the Phase-11 JS renderer owns aliases/layout). Both `started_at` (on START) and `server_now` (per response) use `time.time()` — the same wall-clock domain — so the client can offset-cancel skew (Pitfall 3).

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed as written.

### Notes (non-deviation)

- The plan's Task-1 `<verify>` block listed `test_gen_bumps_on_run_and_score`, `test_gen_seeds_from_disk_on_restart`, and `test_started_at_persists_across_restart` among the Task-1 targets, but all three read `gen`/`started_at` THROUGH `GET /overlay-json`, which lands in Task 2. They remained red after Task 1's route-independent changes (the three pure ones — `test_run_start_stamps_overlay_run`, `test_run_stop_nulls_overlay_run`, `test_runstate_byte_for_byte_unchanged` — passed) and turned green together once the route was added in Task 2. This is an ordering nuance in the plan's per-task verify list, not a behavior deviation; the full `tests/test_ui_overlay_json.py` suite is green at the end of Task 2 as the plan's overall verification requires.
- The `file_channel` conftest fixture already carried the `overlay_run` key (added upstream), so no fixture adaptation was needed.

## Out-of-Scope / Deferred Issues

- 4 pre-existing environmental failures in `tests/test_fan_out_batched.py` (`ModuleNotFoundError: No module named 'ultralytics'`) — the heavy GPU stack is absent in the active py3.14 CPU-only `venv/` (per project MEMORY, GPU tests run from `venv312/`). Unrelated to this plan's UI/opcomm changes (the console imports only Flask + opcomm + stdlib). Logged to `.planning/phases/10-overlay-data-contract-run-timestamp-publish/deferred-items.md`. Not fixed (scope boundary).

## Verification

- `python -m pytest tests/test_ui_overlay_json.py -q` → 11 passed, zero xfail remaining.
- `python -m pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -q` → passed (RBT-07: `/overlay-json` served with torch/cv2/numpy/cyndilib/obsws forced absent).
- `python -m pytest tests/test_imports.py tests/test_ui_run.py tests/test_ui_score.py -q` → 39 passed (`/run` + `/score` unchanged for existing consumers; the side-write/gen-bump is additive; crash-isolation allowlist intact).
- `python -m pytest -q` (full suite) → all pass EXCEPT the 4 pre-existing `test_fan_out_batched.py` ultralytics-absent failures documented above (environmental, not a regression).
- Director invariant: `test_runstate_byte_for_byte_unchanged` green — `runstate.json` bytes identical to the baseline `write_runstate` (D-03 HARD invariant holds).

## Threat Surface

No new threat surface beyond the plan's `<threat_model>`. T-10-04-01 (fixed write path via `_OVERLAY_RUN_FILE` + `_path`), T-10-04-02 (never-raise readers → 200 not 500), T-10-04-03 (byte-for-byte runstate), and T-10-04-05 (no heavy import; RBT-07 gate extended) are all mitigated as planned. T-10-04-04 (verbatim fields → future HTML sink) is the accepted Phase-11/14 sink concern, not introduced here.

## Self-Check: PASSED

- FOUND: src/segugio/ui/app.py (contains `get_overlay_json` + `_OVERLAY_RUN_FILE`)
- FOUND: tests/test_imports.py (GETs `/overlay-json` under the heavy-absent block)
- FOUND: tests/test_ui_overlay_json.py (all xfail markers removed)
- FOUND commit d5d1026 (Task 1: gen seed + overlay_run side-write + /score gen bump)
- FOUND commit 43dae13 (Task 2: GET /overlay-json route + extended crash-isolation gate)
