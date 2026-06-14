---
status: testing
phase: 11-shared-graphical-renderer-overlay-page-branding
source: [11-VERIFICATION.md]
started: 2026-06-14T19:50:29.058Z
updated: 2026-06-14T19:50:29.058Z
---

## Current Test

number: 1
name: Confirm broadcast visual — load GET /overlay in OBS browser-source over a live NDI feed (transparency, enter/exit, pulse, timer, plate placement)
expected: |
  Transparent composite over live video; lower-third enters from left on run start and exits on run stop (edges only); a single pulse plays on score change; the timer counts correctly matching wall clock within human perception; the plate stays in the title-safe bottom band (~18% height) and never covers the action area.
awaiting: user response

## Tests

### 1. Confirm broadcast visual in OBS over a live NDI feed
expected: Transparent composite (no white box); lower-third enters from left on run start, exits on run stop; single pulse on score change; timer matches wall clock within human perception; plate stays in title-safe bottom band (~18% height).
result: [pending]

### 2. Verify agility SS.hh timer smoothness
expected: With discipline=agility, the #timer hundredths digit advances smoothly (~60fps) with no visible step/snap artifact every 200ms poll (WR-04 in 11-REVIEW.md).
result: [pending]

### 3. Verify stale degrade is visible
expected: With a running overlay, kill the console process — within STALE_MS (~600ms) the lower-third dims (`.is-stale`: opacity 0.55, grayscale) and the timer stops. Restart the console — the overlay un-dims and the timer re-anchors.
result: [pending]

### 4. Confirm code-review CR-01 CSS-injection gap is acceptable (or fix it)
expected: Deliberately set `SEGUGIO_OVERLAY_ACCENT='red; } body { background: red }'` and observe whether the program-feed background changes in OBS. Then decide — either accept the risk (config-boundary, isolated LAN, operator-trusted) and document it, OR add a `@field_validator` to `OverlayParams` rejecting non-safe CSS color tokens (the env-override path must route through the same validator). Decide before Phase 12 embeds this page as an iframe.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
