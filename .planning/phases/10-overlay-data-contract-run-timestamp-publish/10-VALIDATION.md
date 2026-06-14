---
phase: 10
slug: overlay-data-contract-run-timestamp-publish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` § Validation Architecture (HIGH confidence; all primitives verified against source).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `tests/conftest.py` (shared fixtures: `file_channel`, `tmp_config`, `make_config`) |
| **Quick run command** | `python -m pytest tests/test_ui_overlay_json.py tests/test_opcomm_overlay_run.py tests/test_config_overlay.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~10–20 seconds (pure CPU/IO; not latency-gated — AC-power note from project memory does not apply) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_ui_overlay_json.py tests/test_opcomm_overlay_run.py tests/test_config_overlay.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/test_ui_overlay_json.py tests/test_opcomm_overlay_run.py tests/test_config_overlay.py tests/test_imports.py tests/test_ui_run.py tests/test_ui_score.py -q`
- **Before `/gsd-verify-work`:** Full suite `python -m pytest -q` must be green (proves no regression to `runstate.json` / `/score` / `/run` and the crash-isolation import boundary)
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. Rows below map each phase requirement / locked decision to its concrete automated proof so every planned task can claim an `<automated>` verify (or a Wave-0 dependency). The crash-isolation row EXTENDS an existing test; all others are NEW Wave-0 files.

| Behavior | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| `/run` START stamps `running:true` + `started_at` (epoch) into `overlay_run.json` | 1 | OVD-02 | Write path fixed server-side (`_OVERLAY_RUN_FILE` const + `_path()`); operator never supplies a path (T-05-05-01) | route | `pytest tests/test_ui_overlay_json.py::test_run_start_stamps_overlay_run -x` | ❌ W0 | ⬜ pending |
| `/run` STOP nulls it (`running:false`, `started_at:null`) | 1 | OVD-02 | N/A | route | `pytest tests/test_ui_overlay_json.py::test_run_stop_nulls_overlay_run -x` | ❌ W0 | ⬜ pending |
| `runstate.json` is byte-for-byte identical to the v1.1 write for the same POST (HARD director invariant) | 1 | OVD-02 / RBT-07 | Director-read file untouched — no new attack/regression surface on the director | route + byte compare | `pytest tests/test_ui_overlay_json.py::test_runstate_byte_for_byte_unchanged -x` | ❌ W0 | ⬜ pending |
| `/overlay-json` returns the 6-key payload with `Cache-Control: no-store` | 1 | OVD-01 | Live state never cached by intermediaries | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_payload_shape -x` | ❌ W0 | ⬜ pending |
| `/overlay-json` never raises on absent source → safe-default payload | 1 | OVD-01 / D-04 | Torn source → 200 + blank, never 500 (DoS-via-corrupt-file mitigation) | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_safe_default_when_absent -x` | ❌ W0 | ⬜ pending |
| `/overlay-json` never raises on torn/malformed source → safe-default; `server_now`+`gen` still set | 1 | OVD-01 / D-04 | Same as above; anchors always present | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_safe_default_on_corrupt -x` | ❌ W0 | ⬜ pending |
| `fields` returned verbatim (operator-typed keys+values, no alias resolution) | 1 | OVD-01 / D-08 | Contract carries raw values by design; HTML-escaping is the Phase-11 sink concern | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_fields_verbatim -x` | ❌ W0 | ⬜ pending |
| `server_now` present + monotonic `gen` present on every response | 1 | OVD-03 / D-02 | N/A | route | `pytest tests/test_ui_overlay_json.py::test_server_now_and_gen_present -x` | ❌ W0 | ⬜ pending |
| `gen` bumps on `/run` AND on `/score` | 1 | OVD-03 / D-02 | N/A | route | `pytest tests/test_ui_overlay_json.py::test_gen_bumps_on_run_and_score -x` | ❌ W0 | ⬜ pending |
| `gen` seeds from disk across restart (write gen=N, fresh `create_app`, next gen > N) | 1 | OVD-03 / D-02 | N/A | route + fresh app | `pytest tests/test_ui_overlay_json.py::test_gen_seeds_from_disk_on_restart -x` | ❌ W0 | ⬜ pending |
| `started_at` persists across console restart while running (restart keeps `running:true` + same `started_at`) | 1 | D-02 | N/A | route + fresh app | `pytest tests/test_ui_overlay_json.py::test_started_at_persists_across_restart -x` | ❌ W0 | ⬜ pending |
| `read_overlay_run`/`write_overlay_run` round-trip + safe-default (pure unit) | 1 | OVD-01 / D-04 | Boundary owns validation + logs malformed input | unit | `pytest tests/test_opcomm_overlay_run.py -x` | ❌ W0 | ⬜ pending |
| `OverlayRunDoc` frozen-record normalization + equality (pure unit) | 1 | OVD-02 | Types coerced loudly at the boundary | unit | `pytest tests/test_opcomm_overlay_run.py::test_overlay_run_doc_normalizes -x` | ❌ W0 | ⬜ pending |
| `overlay.freestyle_duration_s` defaults to 120; config without `overlay:` block still validates; `<=0` rejected | 1 | (D-05/D-06 — supports OVD-03) | Bounded `Field(gt=0)`; fail-fast `SystemExit(2)` on invalid | unit (pydantic) | `pytest tests/test_config_overlay.py -x` | ❌ W0 | ⬜ pending |
| Crash-isolation import test green with heavy stack absent AND `/overlay-json` served | 1 | RBT-07 | Route imports only Flask + `segugio.opcomm` + stdlib; no heavy import sneaks in | import-isolation | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ✅ extend existing (L87-107) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_opcomm_overlay_run.py` — unit tests for `OverlayRunDoc` + `read_overlay_run`/`write_overlay_run` (round-trip, safe-default on absent/torn, normalization). Covers OVD-01 / OVD-02 / D-04.
- [ ] `tests/test_ui_overlay_json.py` — Flask-test-client route tests (reuses the existing `file_channel` fixture). Covers OVD-01 / OVD-02 / OVD-03 / D-02 / D-03 / D-04 / D-08, incl. the **byte-for-byte `runstate.json` invariant** assertion.
- [ ] `tests/test_config_overlay.py` — pydantic tests for the `overlay.*` section (default 120, optional block, `<=0` bound rejection). Covers D-05 / D-06. *(May extend an existing config test file instead — planner's call.)*
- [ ] Extend `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` to GET `/overlay-json` via the test client under the heavy-absent block. Covers RBT-07.
- [ ] No framework install needed — pytest + the `file_channel` fixture already exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All Phase-10 behaviors have automated verification. (HTML/visual overlay verification belongs to Phase 11; live degrade/poll-storm acceptance to Phase 14 — both out of scope here.)*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new test files + 1 import-test extension)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
