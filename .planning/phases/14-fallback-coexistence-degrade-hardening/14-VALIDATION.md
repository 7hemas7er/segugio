---
phase: 14
slug: fallback-coexistence-degrade-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `14-RESEARCH.md` §"Validation Architecture". Task IDs below are
> criterion-anchored; the planner refines them to real `14-NN-MM` IDs.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + Node.js v24.16.0 (ES2020 fake-DOM execution via `subprocess`; node behavior tests gate on `shutil.which("node")`) |
| **Config file** | pytest configured at repo root (existing — no install needed) |
| **Quick run command** | `python -m pytest tests/test_overlay_degrade_gate.py tests/test_overlay_fallback_gate.py tests/test_overlay_poll_storm.py tests/test_overlay_html_sink_gate.py tests/test_imports.py -x` *(final filenames at planner discretion)* |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~20–40 seconds (overlay gate subset); full suite per existing baseline |

---

## Sampling Rate

- **After every task commit:** Run the relevant gate file(s) for the task **plus** `python -m pytest tests/test_imports.py -x` (crash-isolation / RBT-07 must never regress).
- **After every plan wave:** Run the overlay gate set + `tests/test_scene_template.py tests/test_ui_overlay_render.py tests/test_ui_freshness.py`.
- **Before `/gsd-verify-work`:** `python -m pytest` fully green AND `14-HUMAN-UAT.md` authored and ready to run on the rig.
- **Max feedback latency:** ~40 seconds (overlay gate subset).

---

## Per-Task Verification Map

| Criterion | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| SC#1 — console-down: timer freezes + degrades; `overlay.txt` keeps last score | RBT-06 / OVD-03 | T-14-degrade | Browser lower-third hides on death (no frozen "live" score); single-writer `overlay.txt` retains last score on disk | unit (node fake-DOM) + integration (Flask test_client) | `pytest tests/test_overlay_degrade_gate.py tests/test_overlay_fallback_gate.py -x` | ❌ W0 | ⬜ pending |
| SC#2 — LAN drop stops timer; restart re-anchors via `gen`, no phantom jump | RBT-06 / OVD-03 | — | Timer never airs stale "live" during drop; resumed timer continuous, not outage-sized jump | unit (node fake-DOM) | `pytest tests/test_overlay_degrade_gate.py::test_gen_reanchor_no_phantom_jump -x` | ❌ W0 | ⬜ pending |
| SC#3 — `/overlay-json` poll storm never starves `POST /command` | RBT-06 (UXT-02 extension) | T-14-dos | `threaded=True`/waitress: GET flood cannot block the safety override `< 1.0s` | integration (live_server harness) | `pytest tests/test_overlay_poll_storm.py -x` | ❌ W0 | ⬜ pending |
| SC#4 — operator score values HTML-escaped at the sink | RBT-06 / RBT-07 | T-14-xss | `textContent` sink (never `innerHTML`); Jinja autoescape for `event_name`/`logo`; `_clean`/`cleanField` length+control-char bound | unit (JS source assert) + integration (Flask render) | `pytest tests/test_overlay_html_sink_gate.py tests/test_imports.py -x` | ❌ W0 (sink) / ✅ imports | ⬜ pending |
| RBT-07 — crash-isolation preserved across every `segugio.ui` edit | RBT-07 | T-14-iso | Console imports only `Flask + segugio.opcomm`; heavy stack (torch/cv2/ultralytics/numpy/cyndilib/obsws) absent | import gate | `pytest tests/test_imports.py -x` | ✅ Exists | ⬜ pending |
| D-08 — NDI source-name consistency (config ↔ scene JSON) | RBT-06 (operator-facing) | — | Example config `cameras[].ndi_source` matches scene `ndi_source_name` (no "OBS sees it but console blank") | integration (consistency assert) | `pytest tests/test_scene_template.py -x` (extend) | ⚠️ Partial | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_overlay_degrade_gate.py` — SC#1 two-stage stale→dead (`STALE_MS` dim → `DEAD_MS` hide) + SC#2 `gen` re-anchor with no phantom jump (node fake-DOM; reuse the `tests/test_ui_overlay_render.py` harness verbatim).
- [ ] `tests/test_overlay_fallback_gate.py` — SC#1 `overlay.txt` on-disk persistence after `POST /score` + simulated death (single-writer proof; Flask test_client).
- [ ] `tests/test_overlay_poll_storm.py` — SC#3 `/overlay-json` storm vs `POST /command < 1.0s` (copy the `live_server` fixture + `_get`/`_post_command` from `tests/test_preview_concurrency.py`).
- [ ] `tests/test_overlay_html_sink_gate.py` — SC#4 `textContent` sink + Jinja-autoescape regression assertions.
- [ ] (optional) extend `tests/test_scene_template.py` — D-08 `ndi_source` ↔ scene `ndi_source_name` consistency assertion.
- [ ] No framework install needed — pytest + node v24.16.0 already present.

*Existing infrastructure (`test_imports.py`, `test_ui_overlay_render.py`, `test_preview_concurrency.py`, `test_scene_template.py`) covers the harnesses; only the named gate files are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real OBS browser-source blanking / auto-hide airing on death | RBT-06 | A real CEF browser source + OBS can't be simulated headlessly (D-01/D-02 split) | `14-HUMAN-UAT.md`: kill console, observe lower-third hides on-air within `DEAD_MS`, no frozen score |
| Real LAN-cable drop stops the timer (never stale "live") | RBT-06 | Physical network interruption on the rig | `14-HUMAN-UAT.md`: pull LAN cable mid-run, confirm timer stops + degrades; reconnect + restart console, confirm re-anchor with no phantom jump |
| `overlay.txt` "read from file" text source keeps airing the last score | RBT-06 | Requires real OBS text source reading the on-disk file | `14-HUMAN-UAT.md`: simplified manual reveal (D-06) — reveal `Score Text` when graphic drops; confirm last score airs |

*On-rig HUMAN-UAT is a deferred hardware/field carry-forward (D-02) — authored in Phase 14, executed on the rig later. It does NOT block phase completion.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
