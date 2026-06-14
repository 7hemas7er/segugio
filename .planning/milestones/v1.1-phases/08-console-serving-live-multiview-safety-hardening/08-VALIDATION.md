---
phase: 8
slug: console-serving-live-multiview-safety-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-13
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md` §Validation Architecture. All Phase-8 tests are
> HEADLESS and CPU-only — no GPU, no cv2, no real network.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing suite; `tests/` ~60 files) |
| **Config file** | pytest config in `pyproject.toml` (existing) |
| **Quick run command** | `python -m pytest tests/test_preview_serving.py tests/test_preview_bitrate_cap.py tests/test_imports.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~30–60 seconds (full suite; quick ~5s) |

> Use the existing `file_channel` fixture (tmp_path-backed opcomm dir, `conftest.py:422`) and
> the Flask `test_client` pattern (`test_ui_run.py`). Add a `preview_channel` fixture: a
> `preview/` sub-dir + sample `cam_<id>.jpg` + `preview.json`.

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/test_preview_serving.py tests/test_preview_bitrate_cap.py tests/test_imports.py -x -q`
- **After every plan wave:** `python -m pytest tests/test_preview_serving.py tests/test_preview_concurrency.py tests/test_preview_bitrate_cap.py tests/test_imports.py tests/test_ui_run.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green (`python -m pytest -q`)
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. Rows below are the requirement→test contract from
> research; the planner maps each to a concrete task/plan/wave.

| Req / Decision | Behavior | Threat Ref | Test Type | Automated Command | File Exists | Status |
|----------------|----------|------------|-----------|-------------------|-------------|--------|
| MVW-01 | `GET /preview/<cam>.jpg` serves bytes at `preview/cam_<id>.jpg` (200, `image/jpeg`); `GET /preview` returns sidecar JSON (gen/tick/cams) | T-05-05-01 | unit (Flask test_client) | `pytest tests/test_preview_serving.py -k serve -x` | ❌ W0 | ⬜ pending |
| MVW-01 | unknown cam id → 404; `<cam>` cannot path-traverse (`../status`) → 404, never reads outside preview dir | T-05-05-01 | unit (security) | `pytest tests/test_preview_serving.py -k whitelist -x` | ❌ W0 | ⬜ pending |
| MVW-02 | `/status` exposes `live_cam`; `/preview` exposes `cams` keyed by same ids (LIVE data contract; render is client-side) | — | unit (contract) | `pytest tests/test_preview_serving.py -k live_contract -x` | ❌ W0 | ⬜ pending |
| MVW-03 | `/status` returns `alive[cam]`; `/preview` returns monotonic `gen` that advances on new publish, stable otherwise (freshness signal) | — | unit (contract) | `pytest tests/test_preview_serving.py -k freshness -x` | ❌ W0 | ⬜ pending |
| UXT-02 | POST `/command` returns promptly (no freeze) WHILE concurrent `/preview/<cam>.jpg` GETs are in flight | T-05-05-* | concurrency | `pytest tests/test_preview_concurrency.py -x` | ❌ W0 | ⬜ pending |
| D-01 / D-02 | default `PreviewParams` (≈5/384/q55) × N cams computed bitrate ≤ ceiling (passes); over-cap config raises `ValidationError` / `SystemExit(2)` at load | CFG-01 | unit (config) | `pytest tests/test_preview_bitrate_cap.py -x` | ❌ W0 | ⬜ pending |
| D-03 (regression) | `import segugio.ui` + `create_app(...)` resolve with `torch`/`cv2`/`numpy`/`cyndilib`/`obsws` forced absent, AFTER new routes added | — | import guard | `pytest tests/test_imports.py -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> **Concurrency test note (UXT-02):** the Flask `test_client` does NOT exercise the WSGI
> server's threading. Prefer running a real `app.run(threaded=True)` / `waitress` server on a
> background thread bound to an ephemeral port for a true concurrency proof; fall back to
> asserting the entrypoint sets `threaded=True` (inspect the call) only if the real-server
> approach is infeasible.

---

## Wave 0 Requirements

- [ ] `tests/test_preview_serving.py` — MVW-01/02/03 (serve, whitelist/404, live + freshness data contracts)
- [ ] `tests/test_preview_concurrency.py` — UXT-02 (override POST not blocked during preview GETs)
- [ ] `tests/test_preview_bitrate_cap.py` — D-01/D-02 (default passes, over-cap rejected)
- [ ] `tests/conftest.py` extension — `preview_channel` fixture (preview sub-dir + sample `cam_<id>.jpg` + `preview.json`); reuse existing `file_channel`
- [ ] `tests/test_imports.py` — extend the crash-isolation guard to re-assert after the new routes (confirm `create_app` + new routes import clean with the heavy stack absent)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flicker-free `Image()` preload-swap multiview renders smoothly at the configured cadence on a tablet | MVW-01 | Visual/perceptual; client-side render | Open the console on a tablet over the dedicated LAN; observe the grid refresh for visible flicker/tearing across 1→2→4 column reflow |
| LIVE/tally + "MORTO" tile marking reads unmistakably in field light | MVW-02 / MVW-03 | Visual/perceptual | Force a camera live (override) and kill a feed; confirm the red border + "ON AIR: CAM X" banner and the greyed "MORTO" tile are obvious at a glance |
| Real-WiFi-with-phones false-death-rate unchanged (preview degrades first, feeds never starve) | MVW success criterion 4 | **Hardware-milestone carry-forward (D-02)** — requires 3–4 real NDI phones on the dedicated AP + console open; cannot be validated headless. No synthetic contention harness is built (rejected, D-02). | Run the full rig on the dedicated AP with phones live + preview active; confirm feed-watchdog false-death rate is unchanged vs preview-off baseline |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
