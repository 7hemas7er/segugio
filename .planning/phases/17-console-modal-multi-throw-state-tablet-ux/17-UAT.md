---
status: complete
phase: 17-console-modal-multi-throw-state-tablet-ux
source: [17-VERIFICATION.md]
started: 2026-06-24T20:42:44Z
updated: 2026-06-26T21:18:09Z
method: automated-browser (Playwright msedge headless vs sandbox 127.0.0.1:8099; isolated from any live :8080 director)
---

## Current Test

[testing complete]

## Tests

### 1. Console modal opens and mounts the shared score-entry form
expected: Modal opens with the full score-entry form mounted (discipline selector, fields, advisory total); Escape closes; a second open re-mounts cleanly and restores any in-progress draft. No visible duplicate form, no double-counted throws, no console exception. (Relates to code-review WR-01: autoMount() mounts the component into the hidden dialog on page load before the modal is opened; confirm the hidden mount causes no UX regression — stray global keydown handling or premature draft restore.)
result: pass
evidence: |
  Exactly 1 #score-entry-root on the console page. WR-01 confirmed BENIGN: autoMount populates
  the closed dialog on load (5 child blocks) but re-opening yields exactly 1 discipline-block,
  1 root, 1 publish button — mount() clears the root and uses fresh closures, so NO doubling and
  NO double-count. Real click on "Inserisci / modifica punteggio" → dialog.open=true with the full
  form (discipline select + fields + total + publish). Adding a throw works (1 row). Escape closes
  (dialog.open=false). Re-open re-mounts cleanly (still 1 discipline-block). On-air readout polled
  /overlay-json 3×. Zero page errors and zero real resource 404s (only the browser's implicit
  /favicon.ico 404, which is app-wide and unrelated to phase 17).

### 2. Reload-safe draft restore mid-entry
expected: On /score-entry, add 2 throws with distinct zone/midair/corridor settings, then hard-reload (Ctrl+F5). The two throw rows reappear with the same values and the advisory total matches the pre-reload total. No console exception.
result: pass
evidence: |
  Added throw1 (zone 2, midair on, corridor off) + throw2 (zone 3, midair off, corridor on);
  advisory total 6.0; localStorage draft persisted the flat list verbatim. After a hard reload the
  two rows reappeared with identical zone/midair/corridor values and total 6.0. No console errors.

### 3. Corrupt draft yields a clean mount (never-raise reader)
expected: With devtools › Application › localStorage, set `segugio.score.draft` to `{` (invalid JSON), then reload /score-entry. The page mounts with an empty throw list and no console exception.
result: pass
evidence: |
  Set segugio.score.draft to "{" (invalid JSON) and reloaded: mounted with 0 throw rows, the
  empty-state visible, and NO console exception — the try/caught never-raise reader fell through
  to an empty draft as designed.

### 4. Two-step publish auto-revert
expected: On /score-entry, click "Manda in onda" once — it turns red / shows "Conferma invio". Wait 5 seconds without clicking. The button reverts to "Manda in onda" (un-armed) and NO POST to /score occurred (verify in the Network tab).
result: pass
evidence: |
  First real click → button text "Conferma invio" + .danger class (armed). After waiting 4.6 s
  (> the 4000 ms CONFIRM_WINDOW) the button reverted to "Manda in onda" with the .danger class
  removed. Network interception recorded ZERO POSTs to /score during the arm/revert window.

### 5. Enter never publishes
expected: Press Enter while focused on any input in the score form — on both the dedicated /score-entry page and inside the console modal (try text inputs, the discipline select, and a checkbox). Nothing is submitted, the button does not arm, and there is no network request to /score.
result: pass
evidence: |
  Enter pressed on the discipline <select>, a throw <select>, and a freestyle text input on
  /score-entry, then on an input inside the console modal — in every case the publish button
  stayed "Manda in onda" (never armed) and network interception recorded ZERO POSTs to /score.
  (There is no <form> element, so Enter has no implicit-submit path; the root keydown guard
  preventDefaults Enter.)

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

note: |
  All 5 items verified by automated browser UAT (Playwright, msedge headless) against an isolated
  sandbox at 127.0.0.1:8099 (scratch opcomm dir) — never any live :8080 director. Across the entire
  run, total POSTs observed to /score = 0, so broadcast integrity (a half-entered score cannot reach
  air on a casual tap or Enter) is proven, not assumed. Real-iPad rig UAT (touch ergonomics, OS
  virtual-keyboard "Go" key, sleep/wake) remains the only deferred, non-blocking item per the
  roadmap's code-time tablet contract (success criterion 4).

## Gaps

[none]
