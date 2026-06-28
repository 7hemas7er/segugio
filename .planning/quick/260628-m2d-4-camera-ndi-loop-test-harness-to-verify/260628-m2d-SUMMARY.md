---
phase: quick-260628-m2d
plan: 01
subsystem: ndi-looptest-harness
tags: [ndi, obs, dev-tooling, loop-test, no-phones]
requires: [segugio.config.load_config, cyndilib.Sender, NdiFrameSource, NDI-Discovery-Server]
provides: [config.looptest.yaml, tools/ndi_loop_sender.py, obs/segugio-looptest-scene-collection.json, docs/looptest.md]
affects: []
tech-stack:
  added: []
  patterns: [lazy-cv2-cyndilib-import, host-prefixed-ndi-name, one-Sender-per-camera-thread]
key-files:
  created:
    - config.looptest.yaml
    - tools/ndi_loop_sender.py
    - obs/segugio-looptest-scene-collection.json
    - docs/looptest.md
  modified: []
decisions:
  - "ndi_source values use the host-prefixed MASTER (...) form so the exact-match NdiFrameSource resolver finds the loop senders"
  - "stream_name_from_ndi_source uses a non-greedy host group so the published bare stream re-forms the config ndi_source exactly"
  - "cyndilib Sender built once per camera thread (never per loop iteration) to avoid flicker / watchdog trips"
metrics:
  completed: 2026-06-28
  tasks: 4
  files: 4
---

# Phase quick-260628-m2d Plan 01: 4-Camera NDI Loop-Test Harness Summary

No-phones, 4-camera NDI loop-test harness that drives the full Segugio pipeline (NDI receive → AI tracking → OBS scene switching) from four looping recorded clips, via four new files and zero edits to existing source.

## What Was Built

- **`config.looptest.yaml`** — copy of `config.example.yaml` with the 4 camera `ndi_source` values rewritten to the host-prefixed discoverable form (`MASTER (PHONE-X (NDI HX3))`) and four livelier demo thresholds (`min_dwell: 1.0`, `cooldown: 0.5`, `debounce_N: 2`, `hysteresis_margin: 0.08`). All other blocks byte-identical to the example; header documents the MASTER host-prefix gotcha and the byte-match requirement across sender / config / scene JSON.
- **`tools/ndi_loop_sender.py`** — dev CLI that loops local clips as named NDI sources. One daemon thread per camera, each building its cyndilib `Sender` exactly once; `cv2`/`cyndilib` imported lazily inside `decode_clip`/`publish_loop` so the module imports with the heavy stack absent. Pure helpers `stream_name_from_ndi_source` (non-greedy host-prefix strip) and `expected_discoverable` form the headless-testable seam. Startup banner prints discovery reminder, detected host, per-camera clip/stream/discoverable/config-ndi_source and a HOST MISMATCH warning; clean Ctrl-C shutdown via a shared stop `Event`.
- **`obs/segugio-looptest-scene-collection.json`** — copy of the production scene collection with the 4 NDI sources and every `NDI - ...` scene item rewritten to the `MASTER (...)` form. The 7 scene names + scene_order, `Score Text`, and `Score Overlay` are unchanged; every NDI scene item resolves to an existing renamed source.
- **`docs/looptest.md`** — end-to-end no-phones runbook: overview, prerequisites (discovery server + MASTER gotcha), 5-step procedure (CPU-venv senders → OBS import → venv312 orchestrator → verify), Pexels clip provenance (all 4 IDs), and 3 troubleshooting cases.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | config.looptest.yaml | 63bef9b | config.looptest.yaml |
| 2 | tools/ndi_loop_sender.py | 4c58b4e | tools/ndi_loop_sender.py |
| 3 | obs scene collection | e486bf9 | obs/segugio-looptest-scene-collection.json |
| 4 | docs/looptest.md | 5777bde | docs/looptest.md |

## Verification

- Task 1: `load_config('config.looptest.yaml')` succeeds; 4 ndi_source = MASTER-prefixed forms; 4 thresholds = (1.0, 0.5, 2, 0.08). PASS.
- Task 2: module imports cleanly; `stream_name_from_ndi_source` round-trips all 4 MASTER names back to phone streams + `PLAIN` unchanged; `expected_discoverable` re-forms the config value. PASS.
- Task 3: valid JSON; 7 scene names intact; 4 NDI sources all MASTER-prefixed; every NDI scene item resolves to an existing source. PASS.
- Task 4: runbook contains all required tokens (sender, config, scene JSON, 127.0.0.1, MASTER, venv312, 4 Pexels IDs, Discovery) and ≥50 lines. PASS.
- `git diff --name-status` across the 4 commits shows only 4 `A` (added) entries — no existing source file modified.

## Name Coherence (the harness's load-bearing invariant)

For each camera the chain holds: config `ndi_source` `MASTER (PHONE-X (NDI HX3))` → `stream_name_from_ndi_source` → bare `PHONE-X (NDI HX3)` (what `Sender` publishes) → network host-prefix → `expected_discoverable(..., "MASTER")` → `MASTER (PHONE-X (NDI HX3))` = config `ndi_source` = scene JSON `ndi_source_name`. Verified by the Task 2 round-trip and the Task 3 cross-reference.

## Deviations from Plan

None - plan executed exactly as written.

## Live Verification (manual, deferred)

The end-to-end OBS switching check (discovery server up, senders running, scene collection imported, `python -m segugio config.looptest.yaml`, program scene follows the dog) requires the running rig and is documented in `docs/looptest.md` step (e). Not run as part of this code task.

## Self-Check: PASSED

All 4 created files exist on disk; all 4 task commits (63bef9b, 4c58b4e, e486bf9, 5777bde) present in git history.
