---
phase: 07-off-tick-frame-publishing-channel
verified: 2026-06-13T16:30:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "tests/test_fan_out_batched.py — 2 tests unpacked _fan_out as a 2-tuple; updated to 3-tuple (dets_by_cam, locked_energy, frames_by_cam) in commit 6d8ccf6. 378 passed, 3 skipped, 0 failures confirmed."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run the GPU latency no-regression gate on the deploy rig"
    expected: "python -m pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression passes — p95_on <= p95_off + noise_band, asserting the guarded offer() does not regress the 4-camera decision-loop p95 with PreviewPublisher active"
    why_human: "Requires the GPU stack (venv312, RTX 4000 Ada Laptop). This machine runs CPU-only venv/py3.14. The test is correctly written (derives noise band from two back-to-back preview-OFF runs — no magic number) and correctly gated @pytest.mark.gpu — auto-skips here."
---

# Phase 7: Off-Tick Frame-Publishing Channel Verification Report

**Phase Goal:** A new off-tick publishing channel exposes what the orchestrator already computes — downscaled per-camera JPEG thumbnails plus a per-camera "why" sidecar (framing score, tracking state, dog bbox, FSM auto-candidate, recent-cuts ring) — to the crash-isolated console, built so it provably never steals time from the director's critical tick and never widens the console's import surface.

**Verified:** 2026-06-13T16:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (commit 6d8ccf6)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | HARD GATE 1: With PreviewPublisher running, 4-camera p95 unchanged within noise — off-tick daemon, latest-only mailbox, never on the tick (PRV-01/SC1) | ? HUMAN | Test `test_loop_latency_p95_preview_on_no_regression` exists at `tests/test_latency.py:249-291`, decorated `@pytest.mark.gpu`, correctly derives noise band from two back-to-back preview-OFF runs (no magic number), asserts `p95_on <= p95_off + noise_band`. Auto-skips off-rig. Gap from prior run (2-tuple unpack in test_fan_out_batched.py) is now CLOSED (commit 6d8ccf6, 378 passed, 3 skipped, 0 failures). Awaiting GPU rig execution. |
| 2 | HARD GATE 2: `import segugio.ui` resolves and console STARTS with heavy stack absent — numpy blocked, create_app + GET /status → 200 (PRV-03) | ✓ VERIFIED | `test_app_imports_nothing_heavy` forces ultralytics/torch/numpy/cv2/cyndilib/obsws_python absent via monkeypatch.setitem, then `create_app(tmp_path)` + `client.get("/status")` asserts 200. Passes in headless run (378 passed). |
| 3 | Orchestrator writes downscaled per-camera JPEG thumbnails + preview.json via fixed-filename atomic overwrite into opcomm/preview/ (PRV-01/PRV-02/PRV-03) | ✓ VERIFIED | `test_preview_files_written_on_real_run` drives a real run with injected fake encoder, asserts `cam_{id}.jpg` files land with the fake bytes AND `read_preview(preview_json)` returns a PreviewDoc with the expected cams and gen >= 1. `atomic_write_bytes` uses temp→os.replace, fsync=False for JPEGs (D-04). Passes. |
| 4 | PreviewDoc sidecar carries per-camera framing score + tracking state + normalized dog bbox + FSM auto-candidate + ring of recent cuts — separate from status.json (PRV-02) | ✓ VERIFIED | `PreviewDoc` frozen dataclass at `records.py:162-203` with tick/gen/auto_candidate/cams/cuts fields. `_build_doc` maps all D-07 fields (score/ema/state/locked/track_id/energy/in_zone/box + auto_candidate + cuts). `test_payload_maps_every_d07_field` asserts all fields. write_preview/read_preview are separate from write_status/read_status. DirectorStatus/status.json untouched. Passes. |
| 5 | Publisher fault (encode/IO error) coasts and is logged without perturbing the director or crashing the process (RBT-04 extended, PRV-01 criterion 5) | ✓ VERIFIED | `test_preview_offer_fault_coasts` injects `_RaisingPreview` (offer always raises), drives 5 ticks via run_measured, asserts ticks complete and status.json is still written. The offer() sits inside the RBT-04 try in `_tick_once` (loop.py:590). `test_coast_encode_fault_does_not_raise` proves encoder raises → _run logs + continues. Both pass. |

**Score:** 5/5 truths verified (Truth 1 deferred to GPU rig — test correct and gated)

### Deferred Items

None — no phase 7 must-haves are scheduled for later milestone phases (phases 8/9 own console rendering, not the publisher internals).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/opcomm/atomic.py` | `atomic_write_bytes(path, data, *, fsync=True)` binary sibling | ✓ VERIFIED | Exists at L99-125, in `__all__`, routes through `_atomic_replace` verbatim, fsync gate honored, D-04 rationale in docstring. |
| `src/segugio/opcomm/records.py` | `PreviewDoc` frozen dataclass, full D-07 fields | ✓ VERIFIED | Exists at L162-203, frozen, normalizing `__post_init__`, tick/gen/auto_candidate/cams/cuts fields all present. |
| `src/segugio/opcomm/channel.py` | `read_preview`/`write_preview` safe-default boundary | ✓ VERIFIED | Both exist. write_preview uses `atomic_write_json` (always fsyncs). read_preview safe-defaults to `PreviewDoc()` on any absent/torn/malformed input, reuses `_read_json`. |
| `src/segugio/config/models.py` | `PreviewParams` additive sub-model + `Config.preview` field | ✓ VERIFIED | `PreviewParams` at L146-164 with `extra="forbid"`, bounded fields (enabled/fps/max_width/jpeg_quality). `Config.preview` at L179 with `default_factory=PreviewParams`. |
| `src/segugio/orchestrator/preview.py` | `PreviewPublisher` daemon: offer/start/stop + _run/_publish + _build_doc | ✓ VERIFIED | Exists, 287 lines. offer() is single locked assignment (never blocks). start() is idempotent (CR-01 fix applied). _run uses Event.wait(period) (WR-01 fix applied). _gen bumped under lock (WR-02 fix applied). cv2/numpy lazy inside _cv2_encode. |
| `src/segugio/orchestrator/loop.py` | `self._preview` collaborator + guarded offer() + _cuts_ring + _fan_out returns frames_by_cam | ✓ VERIFIED | self._preview at L157. _cuts_ring deque(maxlen=16) at L185. _fan_out returns 3-tuple at L272-327. Guarded offer() after _apply at L574-577 inside RBT-04 try. |
| `src/segugio/orchestrator/runtime.py` | preview_factory seam + guarded construction + preview/ dir | ✓ VERIFIED | `_default_preview_factory` at L122-133 (lazy import). `_channel_paths` returns preview_dir+preview keys at L76-85. preview_factory param in `build_orchestrator`. `os.makedirs(preview_dir)` at L199. Publisher constructed guarded by `config.preview.enabled` at L225-228. |
| `tests/test_preview_channel.py` | Round-trip + safe-default unit tests | ✓ VERIFIED | 6 tests: round-trip, insertion-order independence, absent→default, malformed→default, frozen/hashable, empty default round-trip. All pass. |
| `tests/test_preview_publisher.py` | Mailbox + payload + coast unit tests | ✓ VERIFIED | 11 tests covering offer-never-blocks, last-writer-wins, drain-then-None, _run bounded, start/stop no-hang, import-without-heavy-stack, D-07 field mapping, gen increments, auto_candidate SAFE, fsync=False spy, encode-fault coast. All pass. |
| `tests/test_ui_score.py` | Extended HARD GATE 2 with numpy + create_app start-check | ✓ VERIFIED | test_app_imports_nothing_heavy blocks all 6 heavy modules including numpy, calls create_app + GET /status, asserts 200. Passes. |
| `tests/test_orchestrator_runtime.py` | preview-files-written disk smoke + disabled=None test | ✓ VERIFIED | test_preview_files_written_on_real_run and test_preview_disabled_constructs_no_publisher both pass. |
| `tests/test_fault_isolation.py` | publisher-fault-coast: raising offer() rides RBT-04 try | ✓ VERIFIED | test_preview_offer_fault_coasts with _RaisingPreview passes. |
| `tests/test_latency.py` | HARD GATE 1 gpu test exists, correctly gated | ✓ VERIFIED | test_loop_latency_p95_preview_on_no_regression exists at L249-291, decorated @pytest.mark.gpu, derives noise band on-rig (no magic number), asserts p95_on <= p95_off + band. Auto-skips off-rig. |
| `tests/test_fan_out_batched.py` | 3-tuple unpack updated (gap from prior verification) | ✓ CLOSED | Commit 6d8ccf6: both test_fan_out_one_batched_forward_per_tick (line 171: `dets_by_cam, locked_energy, _frames_by_cam = orch._fan_out(tick=0)`) and test_fan_out_none_frame_coasts (line 351: `dets_by_cam, _, _ = orch._fan_out(tick=0)`) updated to 3-tuple unpack. 378 passed, 0 failures. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `atomic.py:atomic_write_bytes` | `atomic.py:_atomic_replace + _temp_path` | `_atomic_replace(tmp, path)` verbatim | ✓ WIRED | L119-125 confirmed. |
| `channel.py:read_preview` | `channel.py:_read_json` | single torn/absent→None boundary | ✓ WIRED | L209 confirmed. |
| `preview.py:_publish` | `atomic.py:atomic_write_bytes` | `fsync=False` for JPEG (D-04) | ✓ WIRED | L283 `atomic_write_bytes(..., fsync=False)` confirmed. Spy test confirms fsync=False. |
| `preview.py:_publish` | `channel.py:write_preview` | preview.json sidecar write | ✓ WIRED | L286 `write_preview(...)` confirmed. |
| `preview.py:_run` | `PreviewPublisher._publish` | `except Exception` coast | ✓ WIRED | L130-136: try: self._publish(*item) except Exception as exc: logger.warning(...). |
| `loop.py:_tick_once` | `PreviewPublisher.offer` | guarded offer() after _apply inside RBT-04 try | ✓ WIRED | L574-577 confirmed, inside the L590 `except Exception` catch. |
| `runtime.py:build_orchestrator` | `PreviewPublisher` via `_default_preview_factory` | guarded by `config.preview.enabled` | ✓ WIRED | L225-228 confirmed. |
| `loop.py:_apply` | `self._cuts_ring` | append on target-change edge | ✓ WIRED | L504-514 confirmed: reads prev live_cam from _last_status before reassigning. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `preview.py:_build_doc` | `cams` dict | scores (CameraScore list), dets (DetectionSignal dict) | Yes — from real scorer output | ✓ FLOWING |
| `channel.py:write_preview` | PreviewDoc | `_build_doc` output | Yes — real field mapping from tick data | ✓ FLOWING |
| `preview.py:_publish` | JPEG bytes | `enc(frame)` via cv2 or injected encode_fn | Yes — real cv2 resize/imencode in prod | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full headless suite (gap regression check) | `venv/Scripts/python.exe -m pytest -m "not ndi and not gpu" -q` | 378 passed, 3 skipped, 7 deselected in 6.42s | ✓ PASS |
| 3-tuple unpack confirmed in test_fan_out_batched.py | Read L171, L351 directly | `dets_by_cam, locked_energy, _frames_by_cam = ...` / `dets_by_cam, _, _ = ...` | ✓ PASS |
| HARD GATE 2 (crash-isolation import+start) | included in full suite above | passes | ✓ PASS |
| disk smoke (preview files on real run) | included in full suite above | passes | ✓ PASS |
| offer() fault coasts | included in full suite above | passes | ✓ PASS |
| HARD GATE 1 (GPU latency no-regression) | `pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression` | AUTO-SKIP on CPU box | ? HUMAN |

### Probe Execution

Step 7c: SKIPPED — no conventional `scripts/*/tests/probe-*.sh` probes declared for this phase. Phase uses pytest-based verification gates.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PRV-01 | 07-03, 07-04 | Off-tick JPEG thumbnails on daemon thread, p95 unchanged, latest-only mailbox | ✓ SATISFIED | Publisher built and wired correctly. HARD GATE 1 test exists, is correctly written and gated. The test_fan_out_batched.py regression is closed (commit 6d8ccf6). 378 passed. HARD GATE 1 execution deferred to GPU rig (human verification). |
| PRV-02 | 07-01, 07-03, 07-04 | PreviewDoc sidecar with full D-07 payload, separate from status.json | ✓ SATISFIED | PreviewDoc, write_preview/read_preview, _build_doc all implemented and tested. |
| PRV-03 | 07-01, 07-02 | atomic_write_bytes primitive + console crash-isolation test | ✓ SATISFIED | atomic_write_bytes with fsync gate implemented and tested. HARD GATE 2 passes: console imports AND starts with heavy stack absent. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No TBD/FIXME/XXX markers found in any Phase 7-modified source files. No unreferenced debt markers. The numpy import in `preview.py:_cv2_encode` (`# noqa: F401`) was flagged as INFO by the code review (IN-01) and is not a blocker. |

### Human Verification Required

1. **HARD GATE 1: GPU latency no-regression (PRV-01/SC1)**

   **Test:** `python -m pytest -m gpu tests/test_latency.py::test_loop_latency_p95_preview_on_no_regression` on the deploy rig (venv312, RTX 4000 Ada Laptop)

   **Expected:** p95_on <= p95_off + noise_band — the guarded offer() (single locked pointer swap) does not regress the 4-camera decision-loop p95 with PreviewPublisher active. The test derives the noise band from two back-to-back preview-OFF runs (no magic number), then runs the REAL PreviewPublisher ON under the SAME harness via build_orchestrator's DEFAULT factory (the prod wiring). Asserts `p95_on <= p95_off + noise_band`.

   **Why human:** Requires GPU stack (venv312). This machine is CPU-only venv/py3.14. The test is correctly written and correctly gated `@pytest.mark.gpu` — auto-skips here. The test proves the live production path, not a stub, because the publisher is constructed by build_orchestrator's default factory.

---

## Gaps Summary

**No remaining gaps.** The single BLOCKER from the prior verification (2-tuple unpack in `tests/test_fan_out_batched.py`) was fixed in commit `6d8ccf6`: both `test_fan_out_one_batched_forward_per_tick` (line 171) and `test_fan_out_none_frame_coasts` (line 351) were updated to unpack the `_fan_out` 3-tuple correctly. The full headless suite now passes: **378 passed, 3 skipped, 7 deselected** — zero failures.

**One rig-deferred human verification item remains** (HARD GATE 1 — GPU latency no-regression). This is a test-environment constraint, not a gap: the test exists, is correctly written (noise-band derived on-rig, no magic number), and is correctly gated `@pytest.mark.gpu`. It auto-skips on the CPU box by design.

**Everything else is fully implemented, wired, and verified headlessly:**
- All four leaf primitives (atomic_write_bytes, PreviewDoc, read_preview/write_preview, PreviewParams) exist and are unit-tested
- PreviewPublisher daemon is fully implemented with the correct non-blocking mailbox, idempotent start (CR-01), Event.wait stop (WR-01), locked _gen (WR-02), lazy cv2/numpy, and coast-on-fault
- All hot-path wiring (offer() inside RBT-04 try, _cuts_ring, frames_by_cam from fan-out, preview_factory seam, opcomm/preview/ dir) is present
- HARD GATE 2 (crash-isolation) passes: console imports AND starts with full heavy stack absent
- Publisher-fault-coast headless proof passes
- Disk-smoke proof passes

---

_Verified: 2026-06-13T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
