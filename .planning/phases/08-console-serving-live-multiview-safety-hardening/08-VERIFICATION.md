---
phase: 08-console-serving-live-multiview-safety-hardening
verified: 2026-06-13T17:00:00Z
status: passed
score: 10/10
overrides_applied: 0
re_verification: false
---

# Phase 8: Console Serving, Live Multiview & Safety Hardening — Verification Report

**Phase Goal:** The crash-isolated console consumes the new Phase-7 publishing channel and renders a live, flicker-free multiview of every camera with an unmistakable LIVE/tally indicator and at-a-glance dead-feed marking — landing in the same phase the two safety controls the streaming endpoint makes mandatory: the multi-threaded server (threaded=True/Waitress) so a preview stream can never block an override POST, and a hard preview-bandwidth cap so the preview degrades on contended WiFi before the NDI feeds ever appear to die. Because this is the phase that first puts live competitor video behind the 0.0.0.0 endpoint, a written threat re-evaluation is an acceptance criterion.
**Verified:** 2026-06-13T17:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Truths derived from the five ROADMAP Success Criteria and the merged PLAN must_haves.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Console serves responsive CSS-Grid multiview of all cameras via `GET /preview/<cam>.jpg` + `GET /preview`, import set still Flask + opcomm only | VERIFIED | `app.py` L152-181: whitelisted `send_file` + `read_preview` routes. `console.html` L31-32: `repeat(auto-fit, minmax(240px, 1fr))`. `test_imports.py`: `segugio.ui` in `PHASE1_SURFACE`; dedicated guard with numpy+cv2 forced absent passes. |
| 2 | On-air tile carries LIVE/tally indicator (red border/badge + "ON AIR" banner) from `status.live_cam`; dead/stale feeds MORTO-marked from `status.alive` + preview freshness | VERIFIED | `console.html` L35-36: `.tile.live { border-color: #b23b3b; }`, `.tile.dead { opacity: 0.5; }`. L187-201: `markTiles(status)` sets `.live`/`.dead` + badge text "LIVE"/"MORTO". `test_live_contract` and `test_freshness_gen_advances` pass. |
| 3 | POST `/command` is served promptly with concurrent preview GETs in flight (override never blocked — UXT-02); `threaded=True`/Waitress in place | VERIFIED | `app.py` L210-215: `app.run(..., threaded=True)` fallback + `from waitress import serve` optional entrypoint. `test_command_not_blocked_during_preview_gets` proves < 1.0 s on a real ephemeral-port threaded server. |
| 4 | Unknown cam id and `../status` path-traversal both 404; `<cam>` never used as raw path | VERIFIED | `app.py` L158-160: whitelist check + fixed `cam_{cam}.jpg` prefix. `test_whitelist_unknown_cam_404` + `test_whitelist_path_traversal_404` pass. |
| 5 | `GET /preview` returns sidecar JSON with gen/tick/auto_candidate/cams | VERIFIED | `app.py` L169-181: `read_preview` wrapper returns those four keys. `test_serve_preview_sidecar_json` passes. |
| 6 | `GET /status` exposes `live_cam` + `alive`; LIVE/MORTO data contract holds | VERIFIED | `app.py` L143-150: `/status` route returns `{live_cam, reason, alive}`. `test_live_contract` verifies both endpoints share the same cam id set. |
| 7 | Preview bandwidth cap: `PreviewParams.max_total_mbps` field + config-time `@model_validator` rejects over-cap config; disabled preview skips check | VERIFIED | `models.py` L171: `max_total_mbps = 8.0`. L241-268: `_preview_bitrate_within_cap` validator. Five cap tests pass: default passes, cranked rejected, disabled skips, cap tunable, loader aborts SystemExit(2). |
| 8 | Flicker-free Image() preload-swap with `?t=<gen>` cache-bust; refresh only on genuine new frame | VERIFIED | `console.html` L163-170: `new Image()` preload + `?t=<gen>` + `onload` swap. `pollPreview()` compares `p.gen !== lastGen`. |
| 9 | `import segugio.ui` + `create_app` resolve with torch/cv2/numpy/cyndilib/obsws forced absent (crash-isolation) | VERIFIED | `test_imports.py` `CONSOLE_HEAVY_MODULES = HEAVY_MODULES + ["numpy", "cv2"]`. `test_console_resolves_with_heavy_stack_and_numpy_absent` passes. |
| 10 | Written v1.1 threat re-evaluation for live-video-behind-`0.0.0.0` with AP-isolation hard requirement exists in project docs | VERIFIED | `docs/security.md` exists: contains `0.0.0.0`, all four T-05-05-* cross-references, AP client-isolation hard requirement, `preview.enabled` off-switch, explicit no-new-auth declaration. |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/app.py` | GET /preview + GET /preview/\<cam\>.jpg routes, cam_ids whitelist, threaded/waitress entrypoint, read_preview import | VERIFIED | All routes present (L152-181), `cam_ids=frozenset(cam_ids)` whitelist, `threaded=True` fallback + optional waitress (L206-215), `read_preview` imported at module top (L35). |
| `src/segugio/ui/templates/console.html` | CSS-Grid multiview ON TOP + Image() preload-swap + LIVE/MORTO marking | VERIFIED | `repeat(auto-fit` (L32), `new Image()` (L167), `?t=` (L169), `.tile.live` / `.tile.dead` (L35-36), "ON AIR" banner (L49), grid before `#form-score` (L50-55). |
| `tests/test_preview_serving.py` | MVW-01/02/03 serve + whitelist/404 + live + freshness tests | VERIFIED | 8 test functions covering all selectors; all pass. |
| `tests/test_preview_concurrency.py` | UXT-02 override-POST-not-blocked proof on real ephemeral-port threaded server | VERIFIED | Uses `make_server("127.0.0.1", 0, app, threaded=True)`, 8 concurrent GETs + timed POST; passes. |
| `tests/conftest.py` | `preview_channel` fixture with `cam_cam_wide.jpg` + `preview.json` | VERIFIED | `def preview_channel` at L442; writes `cam_cam_wide.jpg` + `cam_cam_long.jpg` + `preview.json` via `write_preview`. |
| `pyproject.toml` | `[project.optional-dependencies].console = ["waitress==3.0.2"]` | VERIFIED | L31-33: `console = ["waitress==3.0.2"]`; `waitress` NOT in `[project].dependencies`. |
| `src/segugio/config/models.py` | `PreviewParams.max_total_mbps` + `_estimate_jpeg_bytes` + `Config._preview_bitrate_within_cap` | VERIFIED | `max_total_mbps = 8.0` (L171), `_JPEG_BYTES_PER_PIXEL = 0.30` + `_estimate_jpeg_bytes` (L188-202), `_preview_bitrate_within_cap` validator (L241-268). |
| `tests/test_preview_bitrate_cap.py` | D-01/D-02 config-cap tests | VERIFIED | 5 tests; all pass. |
| `docs/security.md` | v1.1 threat re-evaluation: 0.0.0.0 exposure, T-05-05 cross-ref, AP client-isolation, preview.enabled off-switch, no-new-auth statement | VERIFIED | All 6 content clauses from 08-03 plan present in the file. |
| `tests/test_imports.py` | `segugio.ui` in PHASE1_SURFACE; dedicated console guard with numpy forced absent | VERIFIED | `segugio.ui` at L36; `CONSOLE_HEAVY_MODULES` at L25; `test_console_resolves_with_heavy_stack_and_numpy_absent` at L87. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/segugio/ui/app.py` | `preview/cam_{id}.jpg` on disk | `send_file` of fixed `cam_{cam}.jpg` built from whitelisted `cam` id | VERIFIED | L160: `_path(os.path.join(_PREVIEW_SUBDIR, f"cam_{cam}.jpg"))` — `<cam>` only used after whitelist check |
| `src/segugio/ui/app.py` | `segugio.opcomm.channel.read_preview` | `GET /preview` thin wrapper | VERIFIED | `read_preview` imported at L35; used at L173 |
| `tests/test_imports.py` | `segugio.ui` | PHASE1_SURFACE crash-isolation guard | VERIFIED | `"segugio.ui"` at L36 |
| `src/segugio/config/models.py Config._preview_bitrate_within_cap` | `PreviewParams.max_total_mbps` | computed fps×res×quality×N_cams compared to ceiling | VERIFIED | L261: `if total_mbps > p.max_total_mbps: raise ValueError(...)` |
| `console.html markTiles()` | `/status` `live_cam` + `alive` | `pollStatus()` calls `markTiles(s)` after parsing response | VERIFIED | L219: `markTiles(s)` inside `pollStatus()` |
| `console.html pollPreview()` | `/preview` sidecar `gen` | tile refresh only on `p.gen !== lastGen` | VERIFIED | L176-180: gen comparison + `CAMS.forEach(c => refreshTile(c, p.gen))` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `console.html` (img tiles) | `p.gen`, `p.cams` | `GET /preview` → `read_preview` → `preview.json` written by Phase-7 `PreviewPublisher` | Yes — `read_preview` deserializes the atomic-written file; `test_freshness_gen_advances` verifies gen advances on each `write_preview` call | FLOWING |
| `console.html` (LIVE/MORTO marking) | `s.live_cam`, `s.alive` | `GET /status` → `read_status` → `status.json` written by orchestrator | Yes — `test_live_contract` writes a `DirectorStatus` and confirms the route reflects it | FLOWING |
| `GET /preview/<cam>.jpg` | JPEG bytes | `send_file(path)` where path = `preview/cam_{id}.jpg` on disk | Yes — `test_serve_preview_jpg_returns_bytes` confirms exact bytes round-trip | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| GET /preview/cam_wide.jpg → 200 image/jpeg with exact bytes | `pytest tests/test_preview_serving.py::test_serve_preview_jpg_returns_bytes -x -q` | 1 passed | PASS |
| POST /command not blocked while 8 concurrent preview GETs | `pytest tests/test_preview_concurrency.py -x -q` | 1 passed | PASS |
| Over-cap preview config rejected with ValidationError + SystemExit(2) | `pytest tests/test_preview_bitrate_cap.py -x -q` | 5 passed | PASS |
| segugio.ui imports cleanly with heavy stack + numpy forced absent | `pytest tests/test_imports.py -x -q` | 25 passed | PASS |
| Full headless suite (no regression) | `pytest -m "not ndi" -q` | 394 passed, 8 skipped, 0 failures | PASS |

---

### Probe Execution

No `scripts/tests/probe-*.sh` files declared for Phase 8. The equivalent validation is the test suite above. SKIPPED (no conventional probes).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MVW-01 | 08-01, 08-03 | CSS-Grid multiview + flicker-free Image() refresh via two new routes | SATISFIED | `console.html` + `GET /preview/<cam>.jpg` + `GET /preview` routes; `test_preview_serving.py` passing; `docs/security.md` (08-03 claims MVW-01 for the written threat re-eval cross-link) |
| MVW-02 | 08-01 | LIVE/tally indicator on on-air tile from `status.live_cam` | SATISFIED | `.tile.live` CSS + `markTiles()` JS + `test_live_contract` |
| MVW-03 | 08-01, 08-02 | Dead/stale feed MORTO marking (alive + freshness); preview degrades before feeds | SATISFIED | `status.alive` + gen-staleness path in `markTiles()`; `PreviewParams.max_total_mbps` validator |
| UXT-02 | 08-01 | `threaded=True`/Waitress so preview GETs never block override POST | SATISFIED | `app.py` entrypoint + `test_command_not_blocked_during_preview_gets` |

All four Phase-8 requirements from REQUIREMENTS.md traceability table are SATISFIED with no orphans.

---

### Anti-Patterns Found

No `TBD`, `FIXME`, `XXX`, `HACK`, or `PLACEHOLDER` markers found in any of the seven files modified by this phase (`app.py`, `console.html`, `pyproject.toml`, `conftest.py`, `test_imports.py`, `models.py`, `docs/security.md`). No stub returns. No empty data sources.

One intentional deviation from the PLAN was auto-fixed by the executor (documented in 08-01-SUMMARY.md): `numpy` was NOT added to the global `HEAVY_MODULES` (which would have broken unrelated surface modules that legitimately import numpy), but was instead added to a `CONSOLE_HEAVY_MODULES` set used only by the dedicated console guard test. This correctly preserves the plan's intent.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

---

### Human Verification Required

No items require human verification. All behavioral truths are testable with the headless test suite (no visual UI checks, no external services, no real-time behavior that requires manual inspection for this phase's scope).

Note: Phase 8 SC-4 ("with phones live the feed-watchdog false-death rate is unchanged") has a hardware-milestone sub-clause requiring 3-4 real NDI phones on the dedicated AP. This is a DOCUMENTED carry-forward (D-02 in 08-02-PLAN.md) — the config-time bandwidth cap enforces the guarantee by construction (an over-budget preview config is a startup error, not a live surprise). The real-WiFi validation is tracked in the ROADMAP as a hardware-milestone item, not a Phase-8 headless gap.

---

### Deferred Items

No items are deferred. The hardware-milestone WiFi validation was explicitly scoped as a carry-forward (D-02) in the PLAN itself and is not a verification gap for Phase 8.

---

### Gaps Summary

No gaps. All 10 observable truths are VERIFIED. All 10 required artifacts exist, are substantive, and are wired. All key links trace correctly. All four requirements (MVW-01, MVW-02, MVW-03, UXT-02) are satisfied. The full headless test suite runs 394 passed / 8 skipped / 0 failures with no NDI or GPU hardware required.

---

_Verified: 2026-06-13T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
