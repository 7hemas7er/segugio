---
phase: 13-obs-scene-collection-setup-docs
plan: 02
subsystem: operator-docs
tags: [docs, obs-setup, security, browser-source, cef-cache, coexistence-policy]
requires:
  - "docs/obs-setup.md (existing OBS-04 import doc + read-from-file OBS-05 section + scene table)"
  - "docs/security.md (existing v1.1 threat re-eval with T-05-05-04 / T-08-03 trust boundary)"
  - "13-01 Score Overlay browser_source wired into the committed scene-collection (the JSON these docs describe)"
provides:
  - "docs/obs-setup.md '## Score overlay — browser-source (primary path)' operator section: localhost default URL + cross-machine LAN-IP edit + 1920x1080@30 page-owned transparency + shutdown/refresh OFF + CEF cache-clear procedure + re-import note + manual-toggle coexistence policy"
  - "docs/obs-setup.md read-from-file section reframed as the degraded fallback (no longer primary path)"
  - "docs/security.md '## What changed in v1.2 — browser-source overlay (Phase 13)' one-paragraph threat re-eval reusing T-05-05-04 / T-08-03, reaffirmed-not-changed"
affects:
  - "docs/obs-setup.md"
  - "docs/security.md"
tech-stack:
  added: []
  patterns:
    - "Reuse the existing '## ... (path note)' header + bullet idiom (obs-setup) for the new primary-path section"
    - "Reuse the existing STRIDE + threat-id + 'reaffirmed, not changed' prose (security) for the v1.2 re-eval paragraph"
key-files:
  created: []
  modified:
    - "docs/obs-setup.md"
    - "docs/security.md"
decisions:
  - "Used the REAL obs-browser JSON keys shutdown / restart_when_active when documenting shutdown/refresh OFF (noted UI labels differ from JSON keys — Pitfall 2)"
  - "Documented the manual-toggle Browser-primary / Text-fallback coexistence (no auto-reveal) and the research-recommended clean-swap (toggle Score Text visible AND Score Overlay hidden) — D-04 / Open-Q1"
  - "Security re-eval frames the browser-source as a same-origin LAN consumer of an already-assessed read endpoint — no new surface, posture reaffirmed not changed"
metrics:
  duration: ~5min
  completed: "2026-06-16T08:40:00Z"
  tasks: 2
  files: 2
requirements: [SCN-02, RBT-06]
---

# Phase 13 Plan 02: OBS Setup & Security Docs Summary

Documented the operator setup and security posture for the new transparent `/overlay`
browser-source: added a browser-source primary-path section to `docs/obs-setup.md` (URL,
transparency/source settings, CEF cache procedure, re-import note, manual-toggle coexistence
policy), reframed the read-from-file section as the degraded fallback, and appended a
one-paragraph browser-source threat re-evaluation to `docs/security.md` reusing the established
T-05-05-04 / T-08-03 LAN trust boundary.

## What Was Built

**Task 1 — `docs/obs-setup.md` (commit `b483248`):**
- Added a new `## Score overlay — browser-source (primary path)` section (placed before the
  read-from-file section) covering:
  - **URL:** the `http://localhost:8080/overlay` single-box default (bare path, no `?preview=1`,
    no `?t=` nonce — D-01/D-02) and the prominent cross-machine edit to
    `http://<console-LAN-IP>:8080/overlay` when OBS and the console run on different machines.
  - **Source/transparency settings:** 1920×1080 @ 30 fps; transparency is page-owned
    (`html, body { background: transparent }`) so NO custom OBS CSS is injected (D-06); the
    committed source ships `css: ""`. "Shutdown source when not visible" OFF and "Refresh browser
    when scene becomes active" OFF, mapped to the REAL obs-browser JSON keys `shutdown: false` /
    `restart_when_active: false` (noted the UI labels differ from the JSON keys — Pitfall 2).
  - **Re-import-on-existing-box note** (RESEARCH Pitfall 4): the repo JSON edit does not
    auto-propagate; on an already-configured box the operator must re-import the collection or
    manually add the `Score Overlay` Browser source.
  - **CEF cache-clear procedure:** per-source "Refresh cache of current page" first; full purge =
    close OBS, delete `%APPDATA%\obs-studio\plugin_config\obs-browser\`, restart OBS.
  - **Coexistence policy (RBT-06, D-03/D-04):** `Score Text` ships `visible: false` in every
    scene; the browser overlay is the on-air score. On a browser blank/death the operator
    MANUALLY toggles `Score Text` visible (and toggles `Score Overlay` hidden for a clean swap) —
    a manual-toggle fallback, NOT an auto-reveal. Phase 14 validates it end-to-end.
- Reframed the existing `## Score overlay — read-from-file (primary path, OBS-05)` heading to
  `(degraded fallback, OBS-05)` with a callout that it is the fallback the operator toggles to;
  the read-from-file mechanics bullets (atomic write, set the path, kind-agnostic
  `set_overlay_text`) are unchanged. The scene table and obs-websocket prerequisites are
  untouched.

**Task 2 — `docs/security.md` (commit `dd125e4`):**
- Appended a `## What changed in v1.2 — browser-source overlay (Phase 13)` section with ONE
  paragraph reusing the existing STRIDE + threat-id + "reaffirmed, not changed" framing. It
  states the browser-source is a same-origin LAN consumer of the existing `GET /overlay` route
  (Phase 11) — no new server route, no new code path; display-only (SCR-04), values sanitized at
  the HTML sink via `textContent` (never `innerHTML`); reuses the established trust boundary
  unchanged (T-05-05-04 / T-08-03) — no new auth, no configurable bind, no new exposure beyond
  `0.0.0.0:8080`; the documented URL carries no secret and the obs-websocket :4455 password stays
  out of the docs. The v1.1 posture is reaffirmed, not changed. The existing v1.1 paragraphs are
  unmodified.

## Verification

- Task 1 automated assert: `browser-source (primary path)` header, `http://localhost:8080/overlay`,
  `http://<console-LAN-IP>:8080/overlay`, `obs-browser` + `Refresh cache of current page`,
  `Score Text` + `visible`, and a re-import note all present. PASS (`obs-setup.md OK`).
- Task 2 automated assert: `browser-source`, both `T-08-03` and `T-05-05-04`, `textContent`,
  `/overlay`, and the `reaffirm`/`not changed` framing all present. PASS (`security.md OK`).
- `python -m pytest tests/test_scene_template.py -q` — 7 passed (no runtime code touched;
  docs-only plan, the lockstep test stays green).
- Scope confirmation (`git diff 47ad625 HEAD --stat`): this plan changed exactly `docs/obs-setup.md`
  and `docs/security.md`; all other changed files are 13-01's artifacts.

## Deviations from Plan

None — both tasks executed exactly as written.

## Deferred Issues

- **`tests/test_fan_out_batched.py` (pre-existing, OUT OF SCOPE):** fails under the active py3.14
  CPU-only `venv/` with `ModuleNotFoundError: No module named 'ultralytics'` (GPU-stack tests run
  from `venv312/` per MEMORY.md). Unrelated to this docs-only plan (no runtime code touched).
  Already logged to `deferred-items.md` by 13-01; not fixed (scope boundary).

## Self-Check: PASSED
- FOUND: docs/obs-setup.md (browser-source primary-path section + reframed fallback)
- FOUND: docs/security.md (v1.2 browser-source threat re-eval paragraph)
- FOUND commit: b483248 (docs 13-02 obs-setup.md)
- FOUND commit: dd125e4 (docs 13-02 security.md)
