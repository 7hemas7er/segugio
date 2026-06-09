---
status: partial
phase: 03-decision-engine-fsm
source: [03-VERIFICATION.md]
started: 2026-06-09T21:23:33Z
updated: 2026-06-09T21:23:33Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. WR-01 liveness model is the intended Phase-2 → Phase-3 contract
expected: A camera the alive map reports alive but that sends no `CameraScore` row this tick is treated as live-but-not-eligible-challenger (NOT a dead feed). The alive map is the sole liveness authority; score-row absence does NOT trigger `feed_emergency`.
result: [pending]

### 2. WR-03 hold-cap semantics: inclusive `<=` means exactly `cap` suppressed ticks
expected: `action_hold_age` increments to 1 on the first held tick; the `<= cap` check keeps the hold active for ages 1..cap (exactly `cap` suppressed ticks); the cut fires at age `cap+1`. Symmetric with the occlusion path. Confirm "cap = suppressed tick count" is the intended meaning (the fix deliberately rejected the review's suggested `<` change).
result: [pending]

### 3. WR-05 feed_emergency source restricted to `auto`; OVERRIDE owns forced-but-dead in-place
expected: While in OVERRIDE mode, a dying forced camera is handled by the per-tick forced-but-dead reconciliation branch in `tick()`, not by the `feed_emergency` transition. `feed_emergency` now declares `source=["auto"]` only. Confirm in-override feed-death is intentionally reconciled in-place (D-03) rather than via a state-machine edge.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
