---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 02
subsystem: ndi
tags: [ndi, cyndilib, frame-source, lazy-import, supervised-threads, new-frame-liveness, empty-frame-guard, mock-sender, pytest-markers]

# Dependency graph
requires:
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    plan: 01
    provides: FrameSource Protocol (start/latest/last_frame_ts/stop), ndi package light surface, ndi/obs pytest markers, Phase-5 conftest fixtures, the Wave-0 ndi test stubs
  - phase: 04-yolo-tracking
    provides: tracking.frame_source.ClipFrameSource (per-camera crops + injected tick + zero-size-frame skip + cv2-lazy frames() generator)
provides:
  - segugio.ndi.clip_source.ClipReplayFrameSource — in-process clip-replay mock FrameSource (headless, deterministic, NDI-03 empty-frame guard)
  - segugio.ndi.ndi_source.NdiFrameSource — real cyndilib FrameSource (1 supervised thread/cam, NEW-frame liveness stamping, lazy cyndilib/cv2)
  - segugio.ndi.mock_sender.publish_clip — NDI-02 named-source Sender (real-NDI side, E2E only, lazy cyndilib/cv2)
  - tests/conftest_tracking — ndi_available/obs_available stack probes; conftest hook auto-skips ndi/obs items when their stack is absent
affects: [05-04-watchdog, 05-06-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ClipReplayFrameSource: drive ClipFrameSource.frames() OR an injected (tick, {cam: frame}) iterator behind FrameSource.latest — cv2-free deterministic test path"
    - "NEW-frame liveness (RBT-01): publish + stamp last_frame_ts ONLY when ts != last_ts; a frozen feed stops advancing it (Pitfall 1, never receiver.is_connected())"
    - "NDI-03 empty-frame guard reproduced two ways: getattr(frame,'size',0)==0 skip (mock, mirrors frame_source.py:76-89) and min(xres,yres)!=0 guard (real receiver)"
    - "Supervised per-camera receiver threads: idempotent start() (re)creates only dead/missing threads; stop() sets event + joins + disconnects/closes (RBT-04 restart hook)"
    - "Hardware-marker auto-skip: ndi/obs marked tests skip when cyndilib/obsws absent (mirrors the gpu gate) so flipped real E2E tests never break the headless run"

key-files:
  created:
    - src/segugio/ndi/clip_source.py
    - src/segugio/ndi/ndi_source.py
    - src/segugio/ndi/mock_sender.py
  modified:
    - src/segugio/ndi/__init__.py
    - tests/test_frame_source_empty_guard.py
    - tests/test_ndi_source.py
    - tests/test_ndi_mock_sender.py
    - tests/conftest.py
    - tests/conftest_tracking.py

key-decisions:
  - "ClipReplayFrameSource accepts an INJECTED frames_iter so the NDI-03 headless test needs neither cv2 nor a real clip — the empty-frame guard is proven on the light side of the import boundary"
  - "last_frame_ts derived from the EMITTED tick (float = tick+1) not a wall-clock — preserves ClipFrameSource injected-tick determinism for headless tests"
  - "NdiFrameSource NOT re-exported at the ndi package top — package surface stays FrameSource + the two mock/E2E entry points; the real receiver is imported explicitly"
  - "[Rule 3] ndi/obs marker auto-skip added to the conftest collection hook (mirroring gpu) — flipping the Wave-0 ndi stubs to real assertions would otherwise fail the headless suite (cyndilib absent)"

requirements-completed: [NDI-01, NDI-02, NDI-03]

# Metrics
duration: ~14min
completed: 2026-06-11
---

# Phase 5 Plan 02: NDI Ingest Layer (mock + real receiver + mock Sender) Summary

**The `FrameSource` input edge: a deterministic in-process clip-replay mock (NDI-03 empty-frame guard, headless, cv2-free), the real cyndilib receiver (one supervised thread per camera, NEW-frame liveness stamping), and the NDI-02 named-source mock Sender — all keeping cyndilib/cv2 strictly inside their methods so `import segugio.ndi` stays light.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-11T08:36Z (approx)
- **Completed:** 2026-06-11T08:50Z
- **Tasks:** 3
- **Files modified:** 9 (3 src created, 1 src modified, 3 test files flipped, 2 conftest files)

## Accomplishments

- `ClipReplayFrameSource` (Task 1): the headless mock `FrameSource`. Drives either a wrapped `ClipFrameSource.frames()` (cv2 lazy inside the generator) or an injected `(tick, {cam_id: frame})` iterator. Reproduces the NDI-03 zero-size-frame skip exactly as `frame_source.py:76-89` (`getattr(frame, "size", 0) == 0` → coast), and advances `last_frame_ts` only on a NEW non-empty frame from a deterministic, wall-clock-free tick.
- `NdiFrameSource` (Task 2): the real cyndilib receiver. `start()` launches one supervised `threading.Thread` per camera; `_receiver_loop` lazy-imports cv2 + cyndilib (Finder/Receiver/VideoFrameSync/RecvColorFormat/RecvBandwidth), applies the `min(xres,yres)!=0` NDI-03 guard, and publishes (stamping `last_frame_ts`) ONLY when `ts != last_ts` — the RBT-01 / Pitfall-1 false-liveness defense. `stop()` sets the event, joins threads, disconnects the receiver, closes the Finder; `start()` is the idempotent restart hook (RBT-04).
- `publish_clip` (Task 3): the NDI-02 mock Sender. Lazy-imports cv2 + the cyndilib Sender/VideoSendFrame/FourCC, sets resolution/frame-rate/BGRA fourcc from the frames, and writes each BGR→BGRA frame async inside `with sender:`. The A2 [ASSUMED] 0.1.1 API caveat is documented in the docstring (E2E-only, confirm on Windows).
- The `ndi` package re-exports `FrameSource` + `ClipReplayFrameSource` + `publish_clip`, all proven to keep `import segugio.ndi` light with cyndilib/cv2 absent.
- All three Wave-0 ndi test stubs flipped to real assertions: the headless NDI-03 guard test (2 passing tests), and the two `@pytest.mark.ndi` Windows E2E tests (receiver-yields-BGR + sender→receiver round-trip), now auto-skipped when cyndilib is absent.

## Task Commits

1. **Task 1: In-process clip-replay mock + NDI-03 guard** (TDD) — `94be72f` (test RED) → `b1f3c1f` (feat GREEN)
2. **Task 2: Real cyndilib NdiFrameSource — supervised threads + NEW-frame liveness** — `8032b29` (feat)
3. **Task 3: Mock NDI Sender (NDI-02) + light package re-exports** — `a1bff0d` (feat)

## Files Created/Modified

- `src/segugio/ndi/clip_source.py` — `ClipReplayFrameSource` (FrameSource mock; `latest`/`last_frame_ts`/`pump`; zero-size skip; injected-or-clip generator).
- `src/segugio/ndi/ndi_source.py` — `NdiFrameSource` (real cyndilib receiver; `_receiver_loop` lazy heavy imports; supervised threads; NEW-frame liveness; NDI-03 guard).
- `src/segugio/ndi/mock_sender.py` — `publish_clip` (NDI-02 named-source Sender; lazy cyndilib/cv2; A2 caveat).
- `src/segugio/ndi/__init__.py` — re-export FrameSource + ClipReplayFrameSource + publish_clip (stays light).
- `tests/test_frame_source_empty_guard.py` — real NDI-03 assertions (blanks skipped, `last_frame_ts` advances only on real frames).
- `tests/test_ndi_source.py` — real `@pytest.mark.ndi` receiver assertion (BGR shape + advancing ts).
- `tests/test_ndi_mock_sender.py` — real `@pytest.mark.ndi` Sender→receiver round-trip assertion.
- `tests/conftest_tracking.py` — `ndi_available()` / `obs_available()` import-guarded stack probes.
- `tests/conftest.py` — collection hook extended to auto-skip `ndi`/`obs` items when their stack is absent (mirrors the existing `gpu` gate).

## Decisions Made

- **Injected `frames_iter` on the mock:** the NDI-03 headless test drives `[blank, blank, real, real]` directly, needing neither cv2 nor a real clip decode — the empty-frame guard is exercised purely on the light side of the import boundary.
- **`last_frame_ts` from the emitted tick (not wall-clock):** preserves the `ClipFrameSource` injected-tick determinism so the same construction yields the same per-camera sequence headless.
- **`NdiFrameSource` not re-exported at the package top:** the `ndi` package surface stays the interface + the mock + the E2E Sender; the real receiver is imported explicitly by the orchestrator (05-06).
- **`ndi`/`obs` marker auto-skip (Rule 3):** see Deviations — required so flipping the Wave-0 stubs to real assertions does not break the headless `python -m pytest` run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ndi`/`obs` marked tests had no auto-skip → flipped real tests broke the headless run**
- **Found during:** Task 2 (after flipping `test_ndi_source.py` from `@pytest.mark.xfail` to a real `@pytest.mark.ndi` assertion).
- **Issue:** The Wave-0 stubs stayed green in the default `python -m pytest` run via `@pytest.mark.xfail`. Once flipped to real assertions, the `@pytest.mark.ndi` tests RAN in the headless default run and failed with `ModuleNotFoundError: cyndilib` — the conftest collection hook only auto-skipped `@pytest.mark.gpu` (via `gpu_available()`); `ndi`/`obs` had no equivalent gate. The plan's verification (`-m ndi`) and the headless suite both assume these stay collected-but-skipped off-Windows.
- **Fix:** Added `ndi_available()` / `obs_available()` import-guarded probes to `tests/conftest_tracking.py` (cyndilib+cv2 / obsws-python) and extended the `pytest_collection_modifyitems` hook in `tests/conftest.py` to skip `ndi`/`obs` items with a reason when their stack is absent — directly mirroring the established `gpu` gate pattern.
- **Files modified:** `tests/conftest_tracking.py`, `tests/conftest.py`.
- **Verification:** `python -m pytest` → 233 passed, 9 skipped, 20 xfailed; the 3 ndi tests report `SKIPPED ... ndi E2E skipped: cyndilib not installed (heavy group absent) (D-05)`.
- **Committed in:** `8032b29` (Task 2).

---

**Total deviations:** 1 auto-fixed (1 blocking test-infra gate).
**Impact on plan:** Pure test-infrastructure correctness — it makes the plan's own `-m ndi` verification contract hold and keeps the headless suite green. No production-code or scope change.

## Authentication Gates

None.

## Issues Encountered

- The headless box genuinely lacks the heavy stack (`cyndilib`/`cv2` absent), which conveniently makes the lazy-import-boundary assertions real rather than mocked — every `import segugio.ndi.*` check is a true negative-dependency test.

## Verification Results

- `python -m pytest tests/test_frame_source_empty_guard.py -x` → **2 passed** (NDI-03 headless).
- `python -c "import segugio.ndi, segugio.ndi.clip_source, segugio.ndi.ndi_source, segugio.ndi.mock_sender"` → **OK** with cyndilib/cv2 absent.
- `python -m pytest tests/test_ndi_source.py tests/test_ndi_mock_sender.py -m ndi` → **collected**, auto-skipped off-Windows (`cyndilib not installed`); the real assertions run on the Windows E2E box against a live named source.
- Full headless suite: **233 passed, 9 skipped, 20 xfailed** — no regressions.

## Known Stubs

None introduced. The remaining 20 xfailed tests are the Wave-0 stubs for the still-pending Wave-2 plans (05-03 OBS, 05-04 watchdog, 05-05 UI, 05-06 orchestrator) — each flipped to real assertions by its implementer. The two `@pytest.mark.ndi` E2E tests are not stubs: they are real assertions gated to the Windows real-NDI run (D-07), auto-skipped headless.

## Threat Flags

None. The three registered threats for this plan are mitigated as planned:
- **T-05-02-01** (false NDI liveness): `last_frame_ts` advances only on `ts != last_ts` (NdiFrameSource) / a NEW non-empty frame (mock).
- **T-05-02-02** (empty-frame reshape crash): `min(xres,yres)!=0` (real) + `getattr(frame,"size",0)==0` skip (mock).
- **T-05-02-03** (dead receiver thread): supervised thread model, stop-event + join, idempotent `start()` restart hook (orchestrator drives the restart in 05-06).

## Next Phase Readiness

- The orchestrator (05-06) can now construct either ingest impl behind the same `FrameSource` Protocol: `ClipReplayFrameSource` for the headless loop, `NdiFrameSource` for Windows. The watchdog (05-04) reads `last_frame_ts(cam_id)` directly — the RBT-01 substrate is in place.
- The NDI-02 `publish_clip` is the E2E entry point for the on-Windows run (publish curated clips as named sources → real receive path, no phones).
- The `[ASSUMED]` items (A1 `get_timestamp_posix` advancing per NEW frame; A2 cyndilib 0.1.1 Sender API) remain to be confirmed on the Windows box during the E2E run — both are documented in the module docstrings and gated behind `@pytest.mark.ndi`.

## Self-Check: PASSED

All created files verified on disk and all 4 commits confirmed in git log (see below).

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*
