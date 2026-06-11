---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 08
subsystem: opcomm + ndi (robustness gap-closure)
tags: [WR-04, CR-02, robustness, windows-file-sharing, ndi-reconnect, headless-regression]
requires:
  - segugio.opcomm.atomic._atomic_replace (the bounded MoveFileEx retry, 05-01)
  - segugio.ndi.ndi_source.NdiFrameSource._receiver_loop / _resolve_source (05-02)
provides:
  - atomic_write_text routed through _atomic_replace (overlay swap retries the Windows sharing-violation, no writer crash)
  - NdiFrameSource._run_receiver (headless seam: per-iteration loop with injected collaborators)
  - receiver disconnected branch sleeps (no busy-spin) + re-resolves/reconnects a late-appearing named source (auto-reconnect)
affects:
  - OBS read-from-file overlay write path (OBS-05) — no longer crashes when OBS holds the file at swap
  - per-camera NDI receiver CPU + reconnect behavior (NDI-01, RBT-01)
tech-stack:
  added: []
  patterns:
    - "Inject-collaborators seam: the testable while-loop (_run_receiver) takes finder/receiver/video_frame/cv2 as parameters; the lazy heavy imports stay in _receiver_loop"
    - "Bounded headless loop tests: a fake is_connected()/get_source_names() sequence drives one-or-two iterations and sets _stop, so a reintroduced busy-spin would hang"
key-files:
  created:
    - tests/test_ndi_receiver_loop.py
  modified:
    - src/segugio/opcomm/atomic.py
    - src/segugio/ndi/ndi_source.py
    - tests/test_atomic_io.py
decisions:
  - "atomic_write_text shares atomic_write_json's _atomic_replace retry path (WR-04) — the text overlay swap is now identical to the json swap on the Windows MoveFileEx sharing-violation."
  - "_RECEIVER_DISCONNECTED_SLEEP_S = 0.05 is the busy-spin FIX value, NOT a tuned hardware figure — the real near-zero-CPU measurement stays HARDWARE-deferred (@pytest.mark.ndi)."
  - "Extract _run_receiver as the headless seam rather than monkeypatching cyndilib — keeps the lazy-import boundary (cv2/cyndilib only in _receiver_loop) and gives a pure-fake-drivable loop."
metrics:
  duration: 8min
  completed: 2026-06-11
---

# Phase 05 Plan 08: NDI/overlay robustness gap-closure (WR-04 + CR-02) Summary

Closed the two HEADLESS-CLOSEABLE code-quality issues from the 05 code review: `atomic_write_text` now retries the Windows file-swap like `atomic_write_json` (WR-04), and the NDI receiver loop sleeps instead of busy-spinning while disconnected and auto-reconnects a late-appearing named source (CR-02 code fix), each with a real pure-fake headless regression test.

## What Was Built

**Task 1 — WR-04 (atomic.py):** `atomic_write_text` previously ended with a bare `os.replace(tmp, path)`; on Windows, if OBS holds the overlay file open at the instant of the swap, `MoveFileEx` raises `PermissionError` (sharing violation) and the writer crashes. Routed the final swap through the existing `_atomic_replace` (bounded retry on the transient PermissionError) — now byte-for-byte the same swap path as `atomic_write_json`. Added `test_atomic_write_text_retries_on_permission_error` (monkeypatch `os.replace` fail-then-succeed → assert ≥2 calls and the file lands) plus a parity test documenting the json path already survives the same fault.

**Task 2 — CR-02 (ndi_source.py):** The `_receiver_loop` `while` body busy-spun (`if not receiver.is_connected(): continue`) — pinning a CPU core per camera while a feed was down — and never re-resolved a source absent at thread start. Extracted the per-iteration loop into `_run_receiver(cam_id, source_name, finder, receiver, video_frame, cv2)`, the headless seam: the lazy `cv2`/cyndilib imports stay in `_receiver_loop`, and the testable loop takes every collaborator as a parameter. The disconnected branch now (1) `time.sleep(_RECEIVER_DISCONNECTED_SLEEP_S)` (no CPU pin), (2) re-resolves + `set_source` the named source (auto-reconnect without a stop()/start() cycle), then (3) `continue`. The connected-branch capture/NDI-03/NEW-frame/publish logic is unchanged. Added `tests/test_ndi_receiver_loop.py` with bounded pure-fake tests asserting the sleep and the late-source re-resolution (a reintroduced busy-spin would hang).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Route atomic_write_text through _atomic_replace + retry test (WR-04) | 47e8a88 | src/segugio/opcomm/atomic.py, tests/test_atomic_io.py |
| 2 | De-busy-spin + auto-reconnect the NDI receiver loop + headless test (CR-02) | ad4d998 | src/segugio/ndi/ndi_source.py, tests/test_ndi_receiver_loop.py |

## Verification

- `python -m pytest tests/test_atomic_io.py -q` → all pass (incl. the new retry tests).
- `python -m pytest tests/test_ndi_receiver_loop.py -q` → 3 pass (sleep / re-resolve / bounded-stop), NOT marked `ndi`.
- `python -m pytest -m "not gpu and not ndi and not obs"` → **302 passed, 3 skipped, 0 failures** (up from 297 in 05-07: +5 new tests, prior skips preserved, zero regression).
- `python -c "import segugio.opcomm.atomic, segugio.ndi.ndi_source"` → exits 0 with cyndilib/cv2/obsws ABSENT (lazy-import boundary intact; `time` at module top is stdlib).

### Acceptance grep checks
- `grep "_atomic_replace(tmp, path)" src/segugio/opcomm/atomic.py` → 2 matches (json + text); no bare `os.replace(tmp, path)` inside `atomic_write_text`.
- `_RECEIVER_DISCONNECTED_SLEEP_S` defined (line 49) and used in the disconnected branch (line 146).
- `_resolve_source` called pre-loop (line 117) AND inside the disconnected branch (line 149) — 2+ call sites.
- The disconnected `continue` (line 152) is preceded by `time.sleep` + a `_resolve_source` re-attempt — no longer a bare continue.

## Deviations from Plan

None — plan executed exactly as written. No bugs, missing functionality, or blocking issues surfaced; no architectural decisions required.

## Hardware-Deferred (NOT closed in code — remain human-verification, D-07)

These are the WHY behind the code fixes; the headless tests prove the LOGIC/code-path, the real measurement stays human on the Windows box:

- **Real NDI receiver CPU near-zero while disconnected + live cyndilib auto-reconnect** (VERIFICATION human-verification #2). The headless test proves the loop sleeps + re-resolves; the actual CPU figure and a real cyndilib reconnect need the Windows box + a real/mock NDI source.
- **Real Windows OBS-holds-the-overlay sharing-violation on the live path** — the headless test simulates the `PermissionError`; real-stack confirmation is part of the D-07 E2E run (human-verification #4).

## Threat Surface

No new network/auth/input-parsing surface. File-IO surface unchanged in shape (same temp+fsync+replace primitive; only the text path's retry was added). Threat register T-05-08-01 (overlay torn-read), T-05-08-02 (receiver busy-spin DoS), T-05-08-03 (source-absent-at-start availability) all `mitigate` — addressed by this plan's code fixes.

## Known Stubs

None. Both fixes are fully wired into the production code paths (`atomic_write_text` is the real OBS overlay writer; `_run_receiver` is the real per-camera capture loop called by `_receiver_loop`).

## Self-Check: PASSED

All created/modified files exist on disk; both task commits (47e8a88, ad4d998) present in git history.
