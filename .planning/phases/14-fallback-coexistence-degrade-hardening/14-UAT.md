---
status: partial
phase: 14-fallback-coexistence-degrade-hardening
source: [14-VERIFICATION.md, 14-HUMAN-UAT.md]
started: 2026-06-20
updated: 2026-06-21
blocking: false
---

## Current Test

[testing complete — physical scenarios 2 & 3 deferred to a rig session (non-blocking carry-forward, D-02)]

## Tests

### 1. Console death — browser overlay auto-hides, no frozen score (SC#1 browser half + D-06)
expected: Lower-third dims then auto-hides within ~DEAD_MS; no frozen live score; revealing `Score Text` airs the last score from overlay.txt.
result: pass

### 2. LAN-cable drop stops the timer; restart re-anchors with no phantom jump (SC#2)
expected: Pulling the LAN cable mid-run stops the timer and degrades the overlay (no stale "live" count). Reconnecting + restarting the console re-anchors the timer via `gen`/persisted started_at — continuous with true wall-clock elapsed, NOT an outage-sized phantom jump. The overlay re-appears (CR-01 fix: re-show on recovery).
result: blocked
blocked_by: physical-device
reason: "Requires a real LAN-cable interruption + OBS rig. Deferred to a rig session (non-blocking carry-forward, D-02); covered headless by test_gen_reanchor_no_phantom_jump + test_dead_then_recover_reshows_lower_third."

### 3. overlay.txt text source keeps airing the last score (SC#1 on-disk half / single-writer)
expected: After the console is killed and the browser overlay auto-hides, revealing `Score Text` airs the LAST operator score unchanged from overlay.txt — no second writer cleared it on death.
result: blocked
blocked_by: physical-device
reason: "Requires a real OBS read-from-file text source. Deferred to a rig session (non-blocking carry-forward, D-02); single-writer property proven headless by test_overlay_fallback_gate.py."

## Summary

total: 3
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 2

## Gaps
