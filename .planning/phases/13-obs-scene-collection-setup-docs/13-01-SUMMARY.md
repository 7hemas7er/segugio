---
phase: 13-obs-scene-collection-setup-docs
plan: 01
subsystem: obs-scene-collection
tags: [obs, scene-collection, browser-source, overlay, lockstep-test]
requires:
  - "obs/segugio-scene-collection.json (7-scene curated collection with Score Text + NDI shared defs)"
  - "tests/test_scene_template.py (existing lockstep helpers _template_scene_names / _config_obs_scenes)"
  - "GET /overlay route live on console :8080 (Phase 11/12)"
provides:
  - "Score Overlay browser_source def (url http://localhost:8080/overlay, 1920x1080@30, shutdown:false, restart_when_active:false, css:'') wired LAST (z-order top) in all 7 scenes"
  - "Score Text flipped to visible:false in all 7 scenes (manual-toggle degraded fallback)"
  - "Build-time lockstep guard: _source_def + _scene_items helpers + 4 new tests asserting URL, real CEF keys, z-order, per-scene presence, fallback-hidden"
affects:
  - "obs/segugio-scene-collection.json"
  - "tests/test_scene_template.py"
tech-stack:
  added: []
  patterns:
    - "Shared source def in top-level sources + per-scene {name,visible} items reference (mirrors Score Text / NDI - PHONE-*)"
    - "Z-order = items array order, bottom-to-top: last element = top layer"
    - "Lockstep tests loop over _template_scene_names() so no scene can be silently skipped"
key-files:
  created: []
  modified:
    - "obs/segugio-scene-collection.json"
    - "tests/test_scene_template.py"
decisions:
  - "Used the REAL obs-browser JSON keys shutdown / restart_when_active, NOT the UI-label strings (Pitfall 2 — UI labels silently no-op)"
  - "Score Overlay kept LAST (topmost) in every scene; Score Text sits below it, hidden (D-03 manual-toggle fallback)"
  - "css ships as '' so the page owns transparency; no opaque OBS CSS injected (D-06)"
metrics:
  duration: ~6min
  completed: "2026-06-16T08:24:36Z"
  tasks: 2
  files: 2
requirements: [SCN-01, RBT-06]
---

# Phase 13 Plan 01: OBS Scene Collection Browser-Source Wiring Summary

Wired the transparent `/overlay` browser-source into the committed OBS scene-collection (one shared `Score Overlay` `browser_source` def, top of z-order in all 7 scenes, verified obs-browser CEF keys) and extended the pure-Python lockstep test to guard the URL, real CEF keys, z-order, and the present-but-hidden `overlay.txt` text fallback.

## What Was Built

**Task 1 — `obs/segugio-scene-collection.json` (commit `cf2e711`):**
- Added exactly ONE shared `Score Overlay` source def (`id`/`versioned_id` == `browser_source`) appended to the top-level `sources` array after `NDI - PHONE-HANDLER`, with the RESEARCH Pattern-1 verified settings: `url: http://localhost:8080/overlay` (bare path, D-02), `width:1920`, `height:1080`, `fps_custom:true`, `fps:30`, `shutdown:false`, `restart_when_active:false`, `reroute_audio:false`, `css:""`.
- In all 7 scenes (`SAFE`, `CAM Wide`, `CAM Long`, `CAM Low`, `CAM Handler`, `MULTIVIEW`, `PIP`): appended `{ "name": "Score Overlay", "visible": true }` as the LAST item (z-order top, above NDI) and flipped `Score Text` to `visible:false` (D-03 manual-toggle fallback). PIP's three originally-hidden NDI items were preserved verbatim.

**Task 2 — `tests/test_scene_template.py` (commit `270712c`):**
- Added two helpers mirroring the existing `_template_scene_names()` idiom: `_source_def(name)` (top-level sources entry by name) and `_scene_items(scene_name)` (that scene's `settings.items`).
- Added four tests, all per-scene assertions driven by looping over `_template_scene_names()`:
  - `test_score_overlay_source_def` — asserts the REAL keys `shutdown`/`restart_when_active` are `False`, the URL, and `css == ""`.
  - `test_every_scene_has_overlay_and_text` — both sources present in every scene.
  - `test_overlay_is_top_layer` — Score Overlay is the last item and above every `NDI - *` item.
  - `test_score_text_is_fallback_hidden` — Score Text `visible is False` in every scene.
- The pre-existing `test_template_exists` and `test_template_scene_names_match_config` (incl. the SAFE-first-class assertion) are unchanged.

## Verification

- `python -c "import json; json.load(...)"` — template is valid JSON. PASS.
- `python -m pytest tests/test_scene_template.py -q` — 7 passed (3 pre-existing + 4 new). PASS.
- Grep: `restart_when_active` asserted in the test; the UI-label strings `refresh_when_scene_is_active` / `shutdown_source_when_not_visible` are ABSENT from both the JSON and (as JSON keys/assertions) the test — they appear only inside a docstring "do NOT use" warning.
- Threat T-13-03 (mitigate) satisfied: the lockstep test now fails the build on a wrong URL or a wrong/UI-label CEF key.

## Deviations from Plan

None — both tasks executed exactly as written.

## Deferred Issues

- **`tests/test_fan_out_batched.py` (4 failures, OUT OF SCOPE):** these fail under the active py3.14 CPU-only `venv/` with `ModuleNotFoundError: No module named 'ultralytics'`. They are pre-existing, GPU-stack-dependent (run from `venv312/` per MEMORY.md), and completely unrelated to this plan (this plan touched only the OBS JSON and the scene-template test — confirmed by `git diff 47ad625 HEAD --stat`). Logged to `deferred-items.md`; not fixed (scope boundary).

## Notes for Next Plan (13-02)

- 13-02 owns the docs: `docs/obs-setup.md` (the "Score overlay — browser-source (primary path)" section, cross-machine LAN-IP URL, CEF cache-clear procedure, re-import-on-existing-box note, Browser-primary/Text-fallback manual-toggle coexistence policy) and the one-paragraph `docs/security.md` browser-source threat re-eval. The existing obs-setup "read-from-file (primary path, OBS-05)" framing should be re-labelled as the *fallback* path.

## Self-Check: PASSED
- FOUND: obs/segugio-scene-collection.json (modified, valid JSON, 1 Score Overlay def, 7 scenes overlay-last/text-hidden)
- FOUND: tests/test_scene_template.py (4 new tests + 2 helpers, 7 passed)
- FOUND commit: cf2e711 (feat 13-01 scene-collection)
- FOUND commit: 270712c (test 13-01 lockstep)
