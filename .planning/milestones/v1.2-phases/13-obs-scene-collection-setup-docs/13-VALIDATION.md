---
phase: 13
slug: obs-scene-collection-setup-docs
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-16
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `13-RESEARCH.md` → "## Validation Architecture". This phase extends the existing
> pure JSON/YAML lockstep test `tests/test_scene_template.py` (no OBS runtime, no `segugio.ui`
> import, crash-isolation untouched). Real-OBS import + visual placement are manual/UAT
> (deferred to verify-work / Phase 14 acceptance).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (py3.14 `venv/`) |
| **Config file** | none dedicated — repo-root `pyproject.toml` pytest defaults |
| **Quick run command** | `python -m pytest tests/test_scene_template.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~2–3 seconds (quick); full suite excludes GPU `-m gpu` |

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/test_scene_template.py -q`
- **After every plan wave:** `python -m pytest -q` (full suite — proves no JSON/test regression elsewhere)
- **Before `/gsd-verify-work`:** Full suite green, plus a manual OBS import smoke (real OBS box)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner (`gsd-planner`). Rows below are keyed to the
> requirement behaviors from `13-RESEARCH.md` §"Phase Requirements → Test Map"; the planner
> binds each to a concrete plan/task and the executor flips Status to ✅.

| Behavior | Plan/Task | Requirement | Test Type | Automated Command | File Exists | Status |
|----------|-----------|-------------|-----------|-------------------|-------------|--------|
| `Score Overlay` `browser_source` def exists: `id=="browser_source"`, `settings.url=="http://localhost:8080/overlay"`, `shutdown is False`, `restart_when_active is False`, transparent (`css` empty/absent or obs-browser transparent default) | TBD (planner) | SCN-01 | unit | `python -m pytest tests/test_scene_template.py -q` | ✅ extend | ⬜ pending |
| `Score Overlay` referenced in EVERY scene, layered LAST (top of `items`, after any `NDI - *`) | TBD (planner) | SCN-01 | unit | same | ✅ extend | ⬜ pending |
| `Score Text` (`text_gdiplus_v2`, read_from_file overlay.txt) still referenced in EVERY scene, in lockstep with `_template_scene_names()` | TBD (planner) | RBT-06 | unit | same | ✅ extend | ⬜ pending |
| Both `Score Overlay` + `Score Text` present in every scene (lockstep with the scene-name set); `Score Text` ships `visible: false` (D-03) | TBD (planner) | SCN-01 / RBT-06 | unit | same | ⬜ pending |
| `docs/obs-setup.md` documents the browser-source URL + cross-machine LAN-IP + CEF cache-clear + coexistence policy; `docs/security.md` gains the one-paragraph re-eval | TBD (planner) | SCN-02 | doc-assert (grep) | `python -m pytest tests/test_scene_template.py -q` + doc grep | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] None — `tests/test_scene_template.py` already exists and is green (3 passed verified); this phase extends it in place. No new framework/fixture install. `_template_scene_names()` / `_config_obs_scenes()` helpers are reused to keep the new browser/text assertions in lockstep with the scene set.

*Existing infrastructure covers all automatable phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The scene collection imports cleanly into real OBS 28+/30+ (DistroAV) and the `Score Overlay` browser-source renders the transparent `/overlay` lower-third over the NDI video on every scene | SCN-01 | Requires a running OBS instance + console serving `/overlay`; not assertable from a headless JSON parse | On the OBS box: import `obs/segugio-scene-collection.json`, point the browser-source URL at the console LAN-IP, confirm transparent overlay over NDI, no re-flash on a cut between scenes |
| Full-frame lower-third placement reads acceptably over the MULTIVIEW (4-cam grid) / PIP scenes | SCN-01 | Visual placement judgment over a grid can't be asserted in a DOM/JSON test | Switch to MULTIVIEW/PIP in OBS, confirm the overlay placement is acceptable as-is (v1 accepts full-frame per D-05) |
| Browser-blank fallback: toggling `Score Text` visible (and `Score Overlay` hidden) airs the last score | RBT-06 | Live failure-mode behavior; validated end-to-end in Phase 14 | Documented in `docs/obs-setup.md`; Phase 14 is the acceptance gate |

*All JSON-structural behaviors (SCN-01 source/layer/lockstep, RBT-06 text-source retention) have automated verification via `test_scene_template.py`; only real-OBS import + visual placement + live-failure behavior are manual/UAT.*

---

## Validation Sign-Off

- [x] All automatable tasks have `<automated>` verify (the extended `test_scene_template.py`)
- [x] Sampling continuity: single test file, sub-5s feedback
- [x] Wave 0 covers all MISSING references (none — test exists, extended in place)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned — 2026-06-16
