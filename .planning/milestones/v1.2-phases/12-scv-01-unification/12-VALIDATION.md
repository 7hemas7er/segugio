---
phase: 12
slug: scv-01-unification
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-15
planned: 2026-06-15
validated: 2026-06-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `12-RESEARCH.md` → "Validation Architecture". This phase REUSES the Phase-11
> `/overlay` renderer; `preview=1` is a purely-presentational cosmetic fork. Parity is now a
> **build/test guarantee** (D-07), not a runtime drift-guard.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + node (subprocess-executed served JS behavior) |
| **Config file** | repo pytest defaults (no special config needed) |
| **Quick run command** | `python -m pytest tests/test_ui_overlay_page.py tests/test_ui_overlay_render.py tests/test_imports.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~15–30 seconds (quick); full suite excludes GPU `-m gpu` |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_ui_overlay_page.py tests/test_ui_overlay_render.py tests/test_imports.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (full suite — catches any console-wiring regression: score submit / run still work after the mirror deletion)
- **Before `/gsd-verify-work`:** Full suite must be green, plus a sandbox smoke that the iframe renders the framed preview (manual/UAT)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Task IDs assigned by the planner (plan-task). Wave 0 = `12-01`; implementation = `12-02` (server+overlay) and `12-03` (console).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-02-T1 | 12-02 | 2 | SCV-02 | RBT-07 / T-12-02-01 | console + `/overlay?preview=1` resolve with heavy stack (`torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws`) absent — no module-top heavy import; `preview` is a closed boolean | import gate | `python -m pytest tests/test_imports.py -x` | ✅ exists | ✅ green |
| 12-01-T1 | 12-01 | 0 | SCV-02 | — | `console.html` embeds `<iframe src="/overlay?preview=1">` + on-air label; mirror symbols (`mirrorOverlayText`/`updateScorePreview`/`scheduleScorePreview`/`scvCurrentFields`/`driftCheck`/`setDrift`/`gsd:scv01-mirror`/`#drift-warning`/`#overlay-preview`) and `/score/preview` string GONE | structural | `python -m pytest tests/test_ui_scv_unification.py -x` | ✅ exists | ✅ green |
| 12-01-T1 | 12-01 | 0 | D-05 | T-12-02-03 | `POST /score/preview` returns 404/405 (route unregistered) | structural | `python -m pytest tests/test_ui_scv_unification.py -x` | ✅ exists | ✅ green |
| 12-02-T2 | 12-02 | 2 | SCV-02 / D-03 | — | `/overlay?preview=1` returns 200 + `Cache-Control: no-store`; carries `body.preview` class; `/overlay` (no arg) does NOT; both share identical DOM ids (`#lower-third`/`#identity`/`#timer`/`#cells`) + `<script src="/static/overlay-render.js">` | structural | `python -m pytest tests/test_ui_overlay_page.py -x` | ✅ exists | ✅ green |
| 12-01-T2 | 12-01 | 0 | SCV-02 / D-07 | T-12-01 | served `overlay-render.js` (node) vs Python `render_overlay_text`/`_clean` produce identical sanitized field VALUES per discipline (incl. `sct`/`SCT` alias, control-char + >64-char inputs) | value cross-check | `python -m pytest tests/test_ui_overlay_render.py::test_value_crosscheck -x` | ✅ exists | ✅ green |
| 12-02-T2 | 12-02 | 2 | D-04 | — | under `preview=1` the lower-third is force-visible at rest (`body.preview #lower-third { opacity: 1 }`) AND the response-recency watchdog (`quick-260615-tsi`) does NOT add `.is-stale` while local poll answers instantly; poll nonce `++reqSeq` (`quick-260615-sod`) preserved | behavior (node fake-DOM, sandbox-first) | `python -m pytest tests/test_ui_overlay_render.py -x` | ✅ exists | ✅ green |
| 12-03-T1/T2 | 12-03 | 2 | SCV-02 / D-01 / D-05 | T-12-03-01/03 | iframe embed live; mirror block + wiring deleted; surviving `post("/score")`/run/`showFields` wiring intact (Pitfall 1) | structural | `python -m pytest tests/test_ui_scv_unification.py -x` | ✅ exists | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> **Audit note (2026-06-16):** the RED-by-design Wave-0 contract used `@pytest.mark.xfail(strict=False)` so the suite stayed green while implementation landed. Post-execution, 7 of those tests XPASSed (regression-blind) and `test_preview_flag_threads_body_class` was broken-and-masked (it asserted the static CSS selector `body.preview` instead of the body `class="preview"` attribute). The implementation was verified correct first-hand (`?preview=1` → `<body class="preview">`; bare `/overlay` → `<body class="">`). All 8 xfail markers were removed and the broken assertion rewritten; the 8 tests are now strict green regression guards (test-only edits, no impl change).

---

## Wave 0 Requirements

- [x] `tests/test_ui_scv_unification.py` (new, 12-01-T1) — structural unification assertions: iframe embed + on-air label, mirror-symbols-gone, `/score/preview` → 404/405, `body.preview` class threading. **Exists, 4/4 green (xfail markers removed 2026-06-16).**
- [x] `tests/test_ui_overlay_render.py` (12-01-T2) — new `test_value_crosscheck` (node-executed served JS sanitized values vs `render_overlay_text`), built on the existing `cleanField`↔`_clean` `_run_node`/`module.exports` harness. **Exists, green.**
- [x] `tests/test_ui_overlay_page.py` (12-01-T2) — extend with `/overlay?preview=1` served-HTML assertions (no-store, preview class present/absent, shared DOM + script src, force-visible rule). **Exists, green (body-class assertion fixed + xfail markers removed 2026-06-16).**
- [x] DELETE `tests/test_score_preview.py` (12-01-T1; route removed in 12-02 — its byte-exact reference strings are subsumed by the value cross-check; `score_render.py` unchanged per D-06). **Confirmed deleted.**
- [x] No framework install needed (pytest + node already present).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The scaled 16:9 framed preview visually reads placement / title-safe band / transparency / relative scale over the neutral backdrop (D-03) | SCV-02 | Visual placement judgment can't be asserted in a headless DOM test | Launch a **sandbox** `create_app(tmp)` on a non-8080 port (NEVER POST to the live `:8080` console — auto-memory `overlay-bugs-sandbox-repro`), open the console, confirm the iframe shows the lower-third bottom-left inside the framed box over the neutral backdrop, visible at rest, scale reads true |

*All value/structural/crash-isolation behaviors have automated verification; only the visual placement judgment (D-03) is manual/UAT.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (new structural test + new value cross-check + test_score_preview.py deletion)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned (3 plans, 2 waves) — 2026-06-15; validated 2026-06-16

---

## Validation Audit 2026-06-16

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |

**Coverage result:** all 7 mapped tasks COVERED with green automated verification (66 passed, 0 xfailed, 0 xpassed across `test_ui_scv_unification` / `test_ui_overlay_page` / `test_ui_overlay_render` / `test_imports` / `test_ui_explainability`). Only D-03 visual placement remains Manual-Only (UAT).

**Gaps fixed (test-only, no impl change — auditor: gsd-nyquist-auditor / sonnet):**
1. PARTIAL → green: `test_preview_flag_threads_body_class` asserted the static CSS selector `body.preview` (present in both pages) rather than the body `class="preview"` attribute; rewrote the assertion and removed its stale `xfail` (impl verified correct first-hand).
2. Regression-blind → green guards: removed stale `xfail(strict=False)` from 7 XPASSing tests (4 in `test_ui_scv_unification.py`, 3 in `test_ui_overlay_page.py`) so they now fail the suite on regression.

**Out of scope (unchanged):** pre-existing `tests/test_fan_out_batched.py` ultralytics `ModuleNotFoundError` failures (CPU-only `venv`; GPU work runs from `venv312/`), logged in `deferred-items.md`.
