---
status: testing
phase: 14-fallback-coexistence-degrade-hardening
source: [14-VERIFICATION.md, 14-HUMAN-UAT.md]
started: 2026-06-20
updated: 2026-06-20
blocking: false
---

## Current Test

number: 1
name: Console death — browser overlay auto-hides within ~DEAD_MS, no frozen "live" score, D-06 reveal works
expected: |
  With a live score airing, kill the console. The OBS browser-source lower-third dims
  (.is-stale at STALE_MS) then fully HIDES within ~DEAD_MS (~3s). No frozen "live" score
  remains on screen. The operator's only manual step is revealing the `Score Text` source,
  which then airs the last score from overlay.txt (the old "hide Score Overlay" step is gone).
awaiting: user response

## Tests

### 1. Console death — browser overlay auto-hides, no frozen score (SC#1 browser half + D-06)
expected: Lower-third dims then auto-hides within ~DEAD_MS; no frozen live score; revealing `Score Text` airs the last score from overlay.txt.
result: [pending]

### 2. LAN-cable drop stops the timer; restart re-anchors with no phantom jump (SC#2)
expected: Pulling the LAN cable mid-run stops the timer and degrades the overlay (no stale "live" count). Reconnecting + restarting the console re-anchors the timer via `gen`/persisted started_at — continuous with true wall-clock elapsed, NOT an outage-sized phantom jump. The overlay re-appears (CR-01 fix: re-show on recovery).
result: [pending]

### 3. overlay.txt text source keeps airing the last score (SC#1 on-disk half / single-writer)
expected: After the console is killed and the browser overlay auto-hides, revealing `Score Text` airs the LAST operator score unchanged from overlay.txt — no second writer cleared it on death.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
