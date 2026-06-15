---
phase: 12
slug: scv-01-unification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
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

> Task IDs are assigned by the planner; rows below seed the required test coverage per
> requirement/decision. Each plan task must map to one of these test types.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD (planner) | — | 0 | SCV-02 | RBT-07 | console + `/overlay?preview=1` resolve with heavy stack (`torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws`) absent — no module-top heavy import | import gate | `python -m pytest tests/test_imports.py -x` | ✅ keep green | ⬜ pending |
| TBD (planner) | — | 0 | SCV-02 | — | `console.html` embeds `<iframe src="/overlay?preview=1">` + on-air label; mirror symbols (`mirrorOverlayText`/`updateScorePreview`/`scheduleScorePreview`/`scvCurrentFields`/`driftCheck`/`setDrift`/`gsd:scv01-mirror`/`#drift-warning`/`#overlay-preview`) and `/score/preview` string GONE | structural | `python -m pytest tests/test_ui_scv_unification.py -x` (new) | ❌ W0 | ⬜ pending |
| TBD (planner) | — | 0 | D-05 | — | `POST /score/preview` returns 404/405 (route unregistered) | structural | `python -m pytest tests/test_ui_scv_unification.py -x` (new) | ❌ W0 | ⬜ pending |
| TBD (planner) | — | 1 | SCV-02 | — | `/overlay?preview=1` returns 200 + `Cache-Control: no-store`; carries `body.preview` class; `/overlay` (no arg) does NOT; both share identical DOM ids (`#lower-third`/`#identity`/`#timer`/`#cells`) + `<script src="/static/overlay-render.js">` | structural | `python -m pytest tests/test_ui_overlay_page.py -x` | ✅ extend | ⬜ pending |
| TBD (planner) | — | 1 | SCV-02 / D-07 | — | served `overlay-render.js` (node) vs Python `render_overlay_text`/`_clean` produce identical sanitized field VALUES per discipline (incl. `sct`/`SCT` alias, control-char + >64-char inputs) | value cross-check | `python -m pytest tests/test_ui_overlay_render.py::test_value_crosscheck -x` (new) | ✅ extend | ⬜ pending |
| TBD (planner) | — | 1 | D-04 | — | under `preview=1` the lower-third is force-visible at rest (`body.preview #lower-third { opacity: 1 }`) AND the response-recency watchdog (`quick-260615-tsi`) does NOT add `.is-stale` while local poll answers instantly; poll nonce `++reqSeq` (`quick-260615-sod`) preserved | behavior (node fake-DOM, sandbox-first) | `python -m pytest tests/test_ui_overlay_render.py -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui_scv_unification.py` (new) — structural unification assertions: iframe embed + on-air label, mirror-symbols-gone, `/score/preview` → 404/405, `body.preview` class threading.
- [ ] `tests/test_ui_overlay_render.py` — new `test_value_crosscheck` (node-executed served JS sanitized values vs `render_overlay_text`), built on the existing `cleanField`↔`_clean` `_run_node`/`module.exports` harness.
- [ ] `tests/test_ui_overlay_page.py` — extend with `/overlay?preview=1` served-HTML assertions (no-store, preview class present/absent, shared DOM + script src).
- [ ] DELETE `tests/test_score_preview.py` (route removed — its byte-exact reference strings are subsumed by the value cross-check; optional Python-only `render_overlay_text` layout guard may be added since `score_render.py` is unchanged per D-06).
- [ ] No framework install needed (pytest + node already present).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The scaled 16:9 framed preview visually reads placement / title-safe band / transparency / relative scale over the neutral backdrop (D-03) | SCV-02 | Visual placement judgment can't be asserted in a headless DOM test | Launch a **sandbox** `create_app(tmp)` on a non-8080 port (NEVER POST to the live `:8080` console — auto-memory `overlay-bugs-sandbox-repro`), open the console, confirm the iframe shows the lower-third bottom-left inside the framed box over the neutral backdrop, visible at rest, scale reads true |

*All value/structural/crash-isolation behaviors have automated verification; only the visual placement judgment (D-03) is manual/UAT.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (new structural test + new value cross-check + test_score_preview.py deletion)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
