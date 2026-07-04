---
phase: quick-260704-9l5
verified: 2026-07-04T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Quick 260704-9l5: Item-1 Pre-Rig Fixes (7 Robustness & Security Fixes) Verification Report

**Phase Goal:** Land 7 atomic fixes hardening Segugio before its first hardware rig (real-frame GPU latency gates, self-healing NDI receiver + supervisor, OBS credential wiring, rotating post-mortem log, OBS-health badge, NDI discovery doctor, console auth/CSRF gate).
**Verified:** 2026-07-04
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GPU latency tests decode REAL dog frames from `tests/fixtures/looptest/*.mp4` (not np.random) so detections are non-zero and the batched BoT-SORT `update()` + native-ReID `result.feats` cost is timed | VERIFIED | `tests/test_latency.py` `_decode_looptest_frames`/`_looptest_frames` decode via `cv2.VideoCapture` from `tests/fixtures/looptest/cam_wide_9898282.mp4` (downscaled to 1080p); `_assert_nonzero_detection` warmup asserts `total >= 1` boxes before the timed loop; both `@pytest.mark.gpu` tests build `ClipReplayFrameSource(frames_iter=_looptest_frames(...))`. No `np.random` frame builder remains in the gpu tests. |
| 2 | GPU harness enforces a p99/max TAIL gate + an ABSOLUTE-headroom preview-regression check, replacing the flaky two-OFF-run noise-band | VERIFIED | `_TAIL_BUDGET_MS=400.0`, `_PREVIEW_REGRESSION_MARGIN_MS=15.0`, `_ABSOLUTE_HEADROOM_MS=20.0` constants; `test_loop_latency_p95_under_budget` asserts `total_p99_ms < _TAIL_BUDGET_MS` and `total_max_ms < _TAIL_BUDGET_MS`; `test_loop_latency_p95_preview_on_no_regression` asserts `p95_on <= p95_off + _PREVIEW_REGRESSION_MARGIN_MS` and `p95_on < 300.0 - _ABSOLUTE_HEADROOM_MS`. No `noise_band = abs(...)` / `p95_off_a`/`p95_off_b` remains. |
| 3 | A transient exception inside the NDI receiver per-iteration body is caught and the thread survives; the tick loop supervises the source and restarts a dead receiver via idempotent `start()` | VERIFIED | `ndi_source.py::_run_receiver`: the entire loop body (disconnected + connected branches) is wrapped in `try/except Exception as exc:` (line 343-392) that logs throttled and `continue`s/sleeps — never re-raises; the `while not self._stop.is_set()` guard is OUTSIDE the try, so a genuine stop is never swallowed. `loop.py::run()` calls `self._safe_startup("source.supervise", self.source.start)` every `_SOURCE_SUPERVISE_INTERVAL_TICKS` (30) ticks; `NdiFrameSource.start()` is idempotent per-camera (skips alive threads, recreates dead ones). |
| 4 | OBS host/port/password wireable via `SEGUGIO_OBS_HOST/PORT/PASSWORD` through `build_orchestrator` into `ObsWsController(password=...)`; a set password no longer silently breaks switching | VERIFIED | `runtime.py::_obs_credentials()` reads all three env vars (with defensive non-integer-port fallback); `build_orchestrator` calls `obs = obs_factory(obs_host, obs_port, obs_password)`; `_default_obs_factory` passes `password=password` into `ObsWsController(...)`. |
| 5 | `configure_logging()` invoked at BOTH entry points and installs a rotating file sink under the opcomm dir | VERIFIED | `logging.py::configure_logging(level, force, log_dir)` adds `logger.add(os.path.join(log_dir, "segugio.log"), rotation="10 MB", retention=5, enqueue=True, ...)` guarded by `_FILE_SINK_ID`. `__main__.py::main()` calls `configure_logging(log_dir=args.opcomm_dir)` as its first substantive line. `ui/app.py::run_console()` calls `configure_logging(log_dir=_dir)` before `create_app(...)`. |
| 6 | `status.json` and the console surface `obs_connected` so a down OBS is visible instead of silent | VERIFIED | `records.py::DirectorStatus.obs_connected: bool = True` (coerced to strict bool in `__post_init__`); `channel.py::write_status`/`read_status` round-trip the field (default `True` on legacy files); `loop.py::_status_for`/`_to_safe` set `obs_connected = bool(getattr(self.obs, "connected", True))`; `ui/app.py` `/status` route includes `"obs_connected": status.obs_connected`; `console.html` renders `#obs-health` from `s.obs_connected` via `textContent` (XSS-safe). `ObsWsController.connected` property added (`bool(self._connected and self._consec_failures == 0)`). |
| 7 | A startup NDI discovery doctor enumerates live sources and emits a per-camera "NOT FOUND" error | VERIFIED | `ndi_source.py::_diagnose_sources(configured, discovered_names)` (pure, exact-match against `_resolve_source`'s own match); `NdiFrameSource.preflight(wait_s, finder)` logs `logger.error("ndi_source '{}' (cam {}) NOT FOUND among discovered NDI sources: {}", ...)` for every missing entry; best-effort (never raises). `loop.py::run()` calls `self._safe_startup("source.preflight", preflight)` when the source exposes `preflight`. |
| 8 | Mutating console routes (`/score`,`/run`,`/command`) require a shared secret + Origin/CSRF check; console page authenticates its own POSTs; bind host overridable via `SEGUGIO_CONSOLE_HOST` | VERIFIED | `ui/app.py::create_app`'s `@app.before_request _console_auth_gate` is a no-op when `console_secret` is falsy; for POSTs it does `hmac.compare_digest` on `Authorization: Bearer <secret>` (401 on mismatch) then an Origin/host check via `urlparse(origin).netloc != request.host` (403 on mismatch). `console.html`/`score-entry.html` inline `window.__CONSOLE_SECRET` and add the `Authorization` header on their POST `fetch`es; `score-entry.js`'s `submit()` does the same. `_bind_host()` returns `os.environ.get("SEGUGIO_CONSOLE_HOST", "0.0.0.0")`, used by both the waitress `serve()` and the `app.run()` fallback. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_latency.py` | Real-frame GPU harness + tail/headroom gates | VERIFIED | Contains `looptest`, `_TAIL_BUDGET_MS`, `_PREVIEW_REGRESSION_MARGIN_MS`, `_ABSOLUTE_HEADROOM_MS`; 449 lines |
| `src/segugio/ndi/ndi_source.py` | Receiver try/except-continue + `_diagnose_sources`/`preflight` | VERIFIED | Contains `preflight`, `_diagnose_sources`; 504 lines |
| `src/segugio/orchestrator/loop.py` | Tick-loop supervisor + `obs_connected` threaded | VERIFIED | Contains `obs_connected`, `_SOURCE_SUPERVISE_INTERVAL_TICKS`, `self.source.start` call in supervisor branch |
| `src/segugio/orchestrator/runtime.py` | `SEGUGIO_OBS_*` env wired into `obs_factory(host,port,password)` | VERIFIED | Contains `SEGUGIO_OBS_PASSWORD`, `_obs_credentials()` |
| `src/segugio/logging.py` | `configure_logging()` with optional rotating file sink | VERIFIED | Contains `rotation="10 MB"` |
| `src/segugio/opcomm/records.py` | `DirectorStatus.obs_connected` field | VERIFIED | `obs_connected: bool = True` field + normalization |
| `src/segugio/ui/app.py` | before_request secret+CSRF gate, `SEGUGIO_CONSOLE_HOST`, `configure_logging`, `obs_connected` in `/status` | VERIFIED | Contains `SEGUGIO_CONSOLE_SECRET`, `_bind_host`, `configure_logging` call in `run_console`, `obs_connected` in `/status` jsonify |
| `tests/test_ndi_supervisor.py` | Receiver-coasts + supervisor-restart tests | VERIFIED | 155 lines (min 40); passes |
| `tests/test_runtime_obs_credentials.py` | Password threading test | VERIFIED | 120 lines (min 30); passes |
| `tests/test_logging_bootstrap.py` | Rotating sink + entrypoint tests | VERIFIED | 119 lines (min 30); passes |
| `tests/test_obs_health_status.py` | obs_connected end-to-end test | VERIFIED | 115 lines (min 40); passes |
| `tests/test_ndi_preflight.py` | Preflight NOT-FOUND test | VERIFIED | 110 lines (min 25); passes |
| `tests/test_ui_auth.py` | Auth/CSRF/bind-host tests | VERIFIED | 118 lines (min 40); passes |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `orchestrator/loop.py` | `ndi/ndi_source.py` | `run()` tick-loop supervisor calls `source.start()` | WIRED | `loop.py` line ~687: `self._safe_startup("source.supervise", self.source.start)` inside the `tick % _SOURCE_SUPERVISE_INTERVAL_TICKS == 0` branch |
| `orchestrator/runtime.py` | `obs/obsws_controller.py` | `obs_factory(host, port, password)` from `SEGUGIO_OBS_*` env | WIRED | `runtime.py::build_orchestrator` line ~244: `obs = obs_factory(obs_host, obs_port, obs_password)`; `_default_obs_factory` passes through to `ObsWsController(host=host, port=port, password=password)` |
| `orchestrator/loop.py` | `opcomm/records.py` | `_status_for` reads `obs.connected` and sets `DirectorStatus.obs_connected` | WIRED | `loop.py::_status_for` line ~509: `obs_connected = bool(getattr(self.obs, "connected", True))`; passed into `DirectorStatus(..., obs_connected=obs_connected, ...)` |
| `ui/app.py` | `ui/templates/console.html` | `/status` exposes `obs_connected`; console poll renders the badge; POST fetch sends the Bearer secret | WIRED | `/status` route jsonify includes `"obs_connected"`; `console.html` `pollStatus()` sets `#obs-health` text/class from `s.obs_connected`; POST helper adds `Authorization: Bearer ...` header from `window.__CONSOLE_SECRET` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 6 new headless test files pass | `venv\Scripts\python.exe -m pytest tests/test_ndi_supervisor.py tests/test_runtime_obs_credentials.py tests/test_logging_bootstrap.py tests/test_obs_health_status.py tests/test_ndi_preflight.py tests/test_ui_auth.py -q` | 42 passed | PASS |
| Crash-isolation import gate stays green | `venv\Scripts\python.exe -m pytest tests/test_imports.py -q` | 26 passed | PASS |
| GPU latency tests collect (not skipped/errored at collection) | `venv\Scripts\python.exe -m pytest -m gpu tests/test_latency.py -q --collect-only` | 2 items collected | PASS |
| The 2 non-gpu suite failures are genuinely pre-existing (independent re-check, not just trusting SUMMARY.md) | Checked out commit `5101824` (parent of this phase's first commit) into an isolated worktree and ran `test_ui_scv_unification.py::test_console_embeds_overlay_iframe` + `test_ui_tablet_layout.py::test_touch_action_and_targets` | Both FAIL identically on the pre-phase commit (missing `<iframe src="/overlay?preview=1"` / `class="layout"` — a template mojibake/markup issue unrelated to this phase's 7 fixes) | PASS (confirms pre-existing, not a regression introduced by this phase) |
| 7 atomic commits exist in the order the plan specifies | `git log --oneline` | `bfc844e`, `3c5c3d8`, `5ee9ac9`, `acade95`, `d598b49`, `1483259`, `9928d52` all present, in order | PASS |
| Docs reconciled (Fix #3) | grep `docs/run.md` + `docs/obs-setup.md` | Both reference `SEGUGIO_OBS_HOST`/`PORT`/`PASSWORD` consistently; no contradictory "future config-model change" language remains | PASS |
| No unresolved debt markers in the 10 modified source files | grep `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` | 0 hits (one benign "placeholder" in a UI comment about the browser's own broken-image icon, not a code stub) | PASS |

Note on the GPU harness (Task 1): the verifier ran on the same box the executor used (no separate GPU rig access in this verification pass), so the actual p95/p99/max numbers reported in SUMMARY.md (p50=143.7ms, p95=162.0ms, p99=174.4ms, max=203.8ms) were not independently re-measured here — only the test's *structure* (real-frame decode, non-zero-detection assertion, tail gate, absolute-headroom check) was verified by reading the code, and the test was confirmed to *collect* (2 items) under `-m gpu`. This is flagged as the one item resting partly on the executor's self-report rather than independent re-execution, but the code-level evidence (no `np.random`, well-constructed assertions, fixed constants) is unambiguous and directly readable — not a claim requiring trust.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| QUICK-260704-9l5 | 260704-9l5-PLAN.md | Land 7 atomic pre-rig hardening fixes | SATISFIED | All 7 fixes verified in code (see Observable Truths 1-8, Task Commits section) |

### Anti-Patterns Found

None. No unresolved `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in the 10 modified source files. No empty stub implementations, no hardcoded-empty data flowing to rendering, no orphaned artifacts.

### Human Verification Required

None. All 8 must-haves are verifiable by direct code inspection + automated test execution; no visual/UX/real-time/external-service behavior in this phase's scope required human judgment beyond what the automated test suite (Flask test client, pure fakes, headless NDI/OBS collaborator injection) already covers.

### Gaps Summary

No gaps. All 8 must-have truths verified directly against the modified source files (not inferred from SUMMARY.md prose); all 13 required artifacts exist, meet their line-count/content-pattern requirements, and are wired; all 4 key links confirmed by reading the actual call sites; the 6 new headless test files were independently executed and pass (42/42); the crash-isolation import gate passes; the 2 known non-gpu-suite failures were independently re-confirmed as pre-existing (present identically on the commit immediately preceding this phase's changes, via an isolated worktree checkout — not merely accepted from SUMMARY.md's stash-based claim); all 7 commits exist in the plan's dependency order; docs were reconciled; the GPU latency test's structural changes (real-frame decode, tail/headroom gates) are directly readable in code even though the exact measured ms figures were not independently re-run on GPU hardware in this verification pass.

---

*Verified: 2026-07-04*
*Verifier: Claude (gsd-verifier)*
