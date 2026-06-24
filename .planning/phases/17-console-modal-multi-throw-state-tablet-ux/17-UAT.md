---
status: testing
phase: 17-console-modal-multi-throw-state-tablet-ux
source: [17-VERIFICATION.md]
started: 2026-06-24T20:42:44Z
updated: 2026-06-24T20:42:44Z
---

## Current Test

number: 1
name: Console modal opens and mounts the shared score-entry form
expected: |
  From the console (localhost:8080), clicking "Inserisci / modifica punteggio" opens the
  modal with the full score-entry form mounted (discipline selector, fields, advisory total);
  Escape closes it; a second open re-mounts cleanly and restores any in-progress draft.
awaiting: user response

## Tests

### 1. Console modal opens and mounts the shared score-entry form
expected: Modal opens with the full score-entry form mounted (discipline selector, fields, advisory total); Escape closes; a second open re-mounts cleanly and restores any in-progress draft. No visible duplicate form, no double-counted throws, no console exception. (Relates to code-review WR-01: autoMount() mounts the component into the hidden dialog on page load before the modal is opened; confirm the hidden mount causes no UX regression — stray global keydown handling or premature draft restore.)
result: [pending]

### 2. Reload-safe draft restore mid-entry
expected: On /score-entry, add 2 throws with distinct zone/midair/corridor settings, then hard-reload (Ctrl+F5). The two throw rows reappear with the same values and the advisory total matches the pre-reload total. No console exception.
result: [pending]

### 3. Corrupt draft yields a clean mount (never-raise reader)
expected: With devtools › Application › localStorage, set `segugio.score.draft` to `{` (invalid JSON), then reload /score-entry. The page mounts with an empty throw list and no console exception.
result: [pending]

### 4. Two-step publish auto-revert
expected: On /score-entry, click "Manda in onda" once — it turns red / shows "Conferma invio". Wait 5 seconds without clicking. The button reverts to "Manda in onda" (un-armed) and NO POST to /score occurred (verify in the Network tab).
result: [pending]

### 5. Enter never publishes
expected: Press Enter while focused on any input in the score form — on both the dedicated /score-entry page and inside the console modal (try text inputs, the discipline select, and a checkbox). Nothing is submitted, the button does not arm, and there is no network request to /score.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
