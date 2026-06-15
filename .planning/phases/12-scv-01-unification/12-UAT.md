---
status: testing
phase: 12-scv-01-unification
source: [12-VERIFICATION.md]
started: 2026-06-16T00:00:00Z
updated: 2026-06-16T00:00:00Z
---

## Current Test

number: 1
name: Visual 16:9 preview fidelity (D-03)
expected: |
  The overlay lower-third is visible inside the 16:9 iframe, positioned at the
  bottom-left with the plate transparency and font readable. The neutral gray
  backdrop (#6b6f76) lets the operator judge plate opacity. The on-air badge
  reads '● ON AIR'.
awaiting: user response

## Tests

### 1. Visual 16:9 preview fidelity (D-03)
expected: Open a browser to the console (or use a `create_app` sandbox on an alt port per the `overlay-bugs-sandbox-repro` memory). The 16:9 preview box renders the lower-third over the neutral backdrop (#6b6f76), the plate is visible, the title-safe band placement looks correct, and the on-air badge reads '● ON AIR'.
result: [pending]

### 2. Live score update flow across all three disciplines
expected: With the console open, enter a score in all three disciplines in turn. The iframe updates within the poll interval (~200ms) showing the correct sanitized values for each discipline, with no JS `ReferenceError` from deleted mirror symbols, and the score form + run buttons still work.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
