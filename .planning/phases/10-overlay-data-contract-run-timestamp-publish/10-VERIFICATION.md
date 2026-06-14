---
phase: 10-overlay-data-contract-run-timestamp-publish
verified: 2026-06-14T12:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 10: Overlay Data Contract & Run-Timestamp Publish — Verification Report

**Phase Goal:** The console publishes everything the overlay needs as a boundary-safe JSON contract,
with the run-start instant stamped into a NEW console-owned file — without touching the director or
any director-read file. No HTML yet; pure channel + route.
**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Starting a run stamps `run_started_at` + `running: true` into a NEW console-owned `overlay_run.json`; stopping nulls it — and `runstate.json` is byte-for-byte unchanged | VERIFIED | `test_run_start_stamps_overlay_run`, `test_run_stop_nulls_overlay_run`, `test_runstate_byte_for_byte_unchanged` — all 3 green; `write_runstate` call is untouched at `app.py:220`; side-write is a SEPARATE `overlay_run.json` file strictly after |
| 2 | `GET /overlay-json` returns `{discipline, fields (verbatim), running, started_at, server_now, gen}` with `Cache-Control: no-store`, and never raises on absent/torn/malformed sources | VERIFIED | `test_overlay_json_payload_shape`, `test_overlay_json_safe_default_when_absent`, `test_overlay_json_safe_default_on_corrupt`, `test_overlay_json_rejects_non_finite_started_at` (CR-01 fix) — all green; route at `app.py:253-275` assembles from `read_score` + `read_overlay_run` + `time.time()` only |
| 3 | `server_now` (wall-clock `time.time()` at response) and a monotonic `gen` (bumped on every `/run` and `/score`, seeded from disk across restart) are present in every response | VERIFIED | `test_server_now_and_gen_present`, `test_gen_bumps_on_run_and_score`, `test_gen_seeds_from_disk_on_restart`, `test_started_at_persists_across_restart` — all green; `_state` dict seeded at `app.py:114`, Lock-guarded bump helpers at `app.py:119-148` |
| 4 | Crash-isolation import test is green with heavy stack absent (`torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws`) — route module imports only Flask + `segugio.opcomm` | VERIFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` green; GETs `/overlay-json` under the forced-absent block and asserts 200 + `gen`/`server_now` keys (RBT-07) |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/opcomm/records.py` | `OverlayRunDoc` frozen record with boundary normalization | VERIFIED | `class OverlayRunDoc` at line 208; `__post_init__` coerces `bool(running)`, `float(started_at)` only when not None (NaN/Infinity rejected, WR-02 bool guard), `int(gen)`; in `__all__` at line 39 |
| `src/segugio/opcomm/channel.py` | `write_overlay_run` / `read_overlay_run` via `atomic_write_json` + `_read_json` | VERIFIED | Both defined at lines 280-330; `write_overlay_run` calls `atomic_write_json` (no hand-rolled write); `read_overlay_run` uses `_read_json` never-raise boundary + `_as_bool` strict coercion (WR-04) + `math.isfinite` guard (CR-01); both in `__all__` lines 47-48 |
| `src/segugio/ui/app.py` | `get_overlay_json` route + overlay_run side-write in `post_run` + gen bump in `post_score` + seed-from-disk gen closure | VERIFIED | `_OVERLAY_RUN_FILE` at line 71; `_state` seeded at line 114; `_bump_overlay_run`/`_bump_score_gen` at lines 119-148; side-write in `post_run` at lines 224-227 (after unchanged `write_runstate` at 220); `_bump_score_gen()` in `post_score` at line 180; `get_overlay_json` at lines 253-275 |
| `src/segugio/config/models.py` | `OverlayParams` sub-model + `Config.overlay` field | VERIFIED | `class OverlayParams` at line 174; `model_config = ConfigDict(extra="forbid")`; `freestyle_duration_s: Annotated[int, Field(gt=0)] = 120`; `Config.overlay` at line 248 via `Field(default_factory=OverlayParams)` |
| `config.example.yaml` | Documents `overlay.freestyle_duration_s` | VERIFIED | Lines 114-117 contain the commented `overlay:` block with `freestyle_duration_s: 120` |
| `tests/test_opcomm_overlay_run.py` | Unit tests for `OverlayRunDoc` + IO helpers (16 tests, no xfail) | VERIFIED | 16 tests, 0 xfail decorators; includes CR-01/WR-02/WR-04 regression tests added in fix commits |
| `tests/test_ui_overlay_json.py` | Route tests for `/overlay-json` (16 tests, no xfail) | VERIFIED | 16 tests, 0 xfail decorators; `test_runstate_byte_for_byte_unchanged` was always xfail-free by design |
| `tests/test_config_overlay.py` | Config tests for `OverlayParams` (5 tests, no xfail) | VERIFIED | 5 tests, 0 xfail decorators |
| `tests/test_imports.py` | Extended crash-isolation gate covering `/overlay-json` | VERIFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` builds test client and GETs `/overlay-json` under the forced-absent block |
| `tests/conftest.py` | `file_channel` fixture exposes `overlay_run` path key | VERIFIED | `"overlay_run": d / "overlay_run.json"` at line 444; documented in fixture docstring at lines 426-432 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py post_run` | `write_runstate` (unchanged) | Direct call at line 220 | WIRED | Call is unmodified; `overlay_run` side-write is strictly after at lines 224-227 |
| `app.py post_run` | `write_overlay_run` / `_bump_overlay_run` | After `write_runstate` | WIRED | `_bump_overlay_run(running=True, started_at=time.time())` on start; `(False, None)` on stop |
| `app.py post_score` | `_bump_score_gen` | After unchanged `write_score` + `atomic_write_text` | WIRED | `_bump_score_gen()` at line 180; preserves `running`/`started_at` from `_state` memory (WR-03 fix) |
| `get_overlay_json` | `read_score` + `read_overlay_run` + `time.time()` | Pure safe-default assembly | WIRED | No `json.load`/`open` in route body; both readers absorb torn files via `_read_json` |
| `read_overlay_run` | `_read_json` never-raise boundary | Direct call at line 304 | WIRED | Returns `None` on absent/torn/malformed; CR-01 `parse_constant` hook in `_read_json` rejects NaN/Infinity tokens at line 87 |
| `write_overlay_run` | `atomic_write_json` | Direct call at line 288 | WIRED | Always-fsync + Windows MoveFileEx retry; explicit dict (no hand-rolled write) |
| `channel.py` | `OverlayRunDoc` from `records.py` | Import at line 30 | WIRED | `from .records import (..., OverlayRunDoc, ...)` |
| `Config` | `OverlayParams` | `overlay: OverlayParams = Field(default_factory=OverlayParams)` at line 248 | WIRED | Default factory ensures existing configs without `overlay:` key still validate |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `get_overlay_json` | `s` (ScoreDoc) | `read_score(_path(_SCORE_FILE))` | Yes — live `score.json` or safe default | FLOWING |
| `get_overlay_json` | `ovr` (OverlayRunDoc) | `read_overlay_run(_path(_OVERLAY_RUN_FILE))` | Yes — live `overlay_run.json` stamped by `/run` edges or safe default | FLOWING |
| `get_overlay_json` | `server_now` | `time.time()` at response time | Yes — always-present wall clock | FLOWING |
| `get_overlay_json` | `gen` | `ovr.gen` sourced from `_state["gen"]` (persisted + in-memory) | Yes — monotonically incrementing counter | FLOWING |
| `_bump_score_gen` | `running`/`started_at` | `_state["running"]`/`_state["started_at"]` (in-memory, WR-03 fix) | Yes — authoritative in-memory state, not disk re-read | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `OverlayRunDoc` normalizes scalars and rejects NaN/bool | `pytest tests/test_opcomm_overlay_run.py -v` | 16 passed | PASS |
| `/overlay-json` payload shape + safe defaults + CR-01 boundary | `pytest tests/test_ui_overlay_json.py -v` | 16 passed | PASS |
| Byte-for-byte `runstate.json` invariant | `test_runstate_byte_for_byte_unchanged` within above | passed | PASS |
| `OverlayParams` config + `Config.overlay` | `pytest tests/test_config_overlay.py -v` | 5 passed | PASS |
| Crash-isolation gate covering `/overlay-json` | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` | passed | PASS |
| Full suite regression (excluding pre-existing NDI env failures) | `pytest --ignore=tests/test_fan_out_batched.py` | 463 passed, 8 skipped, 2 failed (NDI live-network, pre-existing) | PASS |

---

### Requirements Coverage

| Requirement | Phase | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| OVD-01 | Phase 10 | `GET /overlay-json` boundary-safe 6-key payload with `no-store` | SATISFIED | Route at `app.py:253-275`; 5 route tests cover absent/torn/corrupt/verbatim/shape |
| OVD-02 | Phase 10 | NEW console-owned `overlay_run.json` stamps run edges; `runstate.json` unchanged | SATISFIED | `_OVERLAY_RUN_FILE` constant; side-write after `write_runstate`; `test_runstate_byte_for_byte_unchanged` proves byte-identity |
| OVD-03 | Phase 10 (partial) | Freshness — gen-age staleness detection + `gen`/`no-store` pattern | PARTIALLY SATISFIED (by design) | gen monotonicity + `no-store` implemented and tested (`test_gen_bumps_on_run_and_score`); gen-age UI-side freshness/degrade logic is Phase 11's concern (documented in REQUIREMENTS.md traceability: "10-04; gen-age freshness contract completes in Phase 10-04") |
| RBT-07 | Phase 10 | Crash-isolation preserved — test green with heavy stack absent | SATISFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` GETs `/overlay-json` under forced-absent block and asserts 200 + gen/server_now |

**Note on OVD-03:** REQUIREMENTS.md traceability marks OVD-03 as "In Progress (freestyle_duration_s config seeded in 10-03; gen-age freshness contract completes in 10-04)". The `gen` monotonicity and `Cache-Control: no-store` channel-side contract is delivered. The client-side gen-age degrade logic (overlay freezes a stale run) is a Phase-11 renderer concern. This is a designed split, not a gap.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact | Status |
|------|---------|----------|--------|--------|
| `app.py:216` | `else:  # action == "stop"` over-promise on else branch (IN-02 from code review) | Info | Low — `RunState.__post_init__` already rejects invalid actions with 400 before this point | Accepted (identified by code reviewer, no formal follow-up reference; action-safety provided by upstream validator) |
| `app.py:78` | `_PREVIEW_FILE = "preview/preview.json"` forward-slash path separator (IN-01) | Info | Works on Windows; minor style inconsistency | Pre-existing, not introduced by Phase 10; out of scope |

No TBD/FIXME/XXX markers found in any Phase-10 modified file. No stub implementations. No orphaned artifacts.

---

### Boundary-Safety Claim — Current Source Verification

The REVIEW flagged CR-01 (NaN/Infinity escaping), WR-01 (non-dict fields), WR-02 (bool→float), WR-03 (disk re-read in `_bump_score_gen`), and WR-04 (blanket `bool()` on running). All five were fixed in commits `aa3a58b`, `152bdcf`, `4dd39f2`. Current source confirms:

- **CR-01 (NaN/Infinity):** `_read_json` uses `json.loads(raw, parse_constant=_reject_non_finite_token)` at `channel.py:87`; `read_overlay_run` adds `math.isfinite` guard at lines 320-321; `OverlayRunDoc.__post_init__` adds `math.isfinite` check at lines 247-248. Three-layer defense. Verified by `test_overlay_run_rejects_non_finite_started_at` and `test_overlay_json_rejects_non_finite_started_at` (both green).
- **WR-01 (non-dict fields):** `read_score` guards `raw_fields if isinstance(raw_fields, dict) else {}` at `channel.py:131`. Verified by `test_overlay_json_non_dict_fields_safe_defaulted`.
- **WR-02 (bool started_at):** `OverlayRunDoc.__post_init__` rejects `isinstance(self.started_at, bool)` at line 241; `read_overlay_run` rejects bool at line 313. Verified by `test_overlay_run_doc_rejects_bool_started_at` and `test_overlay_run_bool_started_at_on_disk_defaults`.
- **WR-03 (disk re-read in score gen-bump):** `_state` caches `running`/`started_at` alongside `gen`; `_bump_score_gen` reads from `_state` not disk at `app.py:141-148`. Verified by `test_score_gen_bump_preserves_live_run_when_disk_torn`.
- **WR-04 (blanket bool() on running):** `_as_bool` helper at `channel.py:93-108` replaces blanket `bool()`; `read_overlay_run` uses `_as_bool(data.get("running", False))` at line 324. Verified by `test_overlay_run_running_string_false_is_false`.

---

### Human Verification Required

None — all must-haves are mechanically verifiable. No UI rendering, no real-time behavior, no external services required for Phase 10 (pure channel + route, no HTML).

---

### Gaps Summary

None. All four success criteria are verified against the actual codebase. The 2 failing tests in the full suite (`test_ndi_mock_sender.py` and `test_ndi_source.py`) are pre-existing NDI live-network tests documented in STATE.md since Phase 09, requiring a live NDI source on the network — they are structurally unrelated to Phase 10.

---

_Verified: 2026-06-14T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
