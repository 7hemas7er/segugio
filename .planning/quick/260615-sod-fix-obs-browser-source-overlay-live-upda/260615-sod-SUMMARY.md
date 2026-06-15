---
phase: quick-260615-sod
plan: 01
subsystem: ui-overlay
tags: [overlay, obs, cef, cache, polling, bugfix]
requires:
  - "src/segugio/ui/static/overlay-render.js poll() loop (11-03)"
provides:
  - "Per-request unique ?t= cache-buster nonce that defeats OBS CEF URL caching"
affects:
  - "/overlay browser-source live updates inside OBS"
tech-stack:
  added: []
  patterns:
    - "Per-request monotonic counter (++reqSeq) as a URL cache-buster, distinct from the gen-advance render gate"
key-files:
  created: []
  modified:
    - src/segugio/ui/static/overlay-render.js
    - tests/test_ui_overlay_render.py
decisions:
  - "?t= is a pure cache-buster the server ignores; it is NOT the render gate (p.gen > lastGen). Decoupling the two is what fixes the stall."
metrics:
  duration: ~6min
  completed: 2026-06-15
requirements: [OVD-03, OVL-02]
---

# Quick Task 260615-sod: Fix OBS Browser-Source Overlay Live-Update Stall Summary

Made the `/overlay-json` poll nonce a per-request monotonic counter (`++reqSeq`) so every poll URL is unique, defeating OBS CEF's URL-keyed cache that ignores `Cache-Control: no-store` and was masking gen advances — restoring live overlay updates without touching the gen-advance render gate or the offset-cancellation timer.

## What Changed

**Root cause (confirmed by diagnosis):** `poll()` fetched `/overlay-json?t=" + lastGen`. `lastGen` only changes when the server's monotonic `gen` advances, so between gen advances every poll request had an IDENTICAL URL. OBS's embedded Chromium (CEF) browser source ignores `Cache-Control: no-store` and caches by URL — once it cached `?t=N` it kept serving that stale body and never observed the next gen bump, stalling the overlay permanently. The server side was already verified correct (fresh no-store data per request, gen advances on `/run` and `/score`).

**Fix (src/segugio/ui/static/overlay-render.js):**
- Added `let reqSeq = 0;` to the `createRenderer` state vars (next to `lastGen` / `lastGenAt` / `skew` / `startedAt`).
- Changed the fetch URL from `fetch("/overlay-json?t=" + lastGen, ...)` to `fetch("/overlay-json?t=" + (++reqSeq), ...)` — pre-increment so the first request sends `?t=1` and every subsequent request URL is unique.
- Rewrote the comment block above `poll()` to accurately state the nonce is now UNIQUE PER REQUEST to defeat CEF's URL-keyed caching, and to clarify `?t=` is purely a cache-buster the server ignores — NOT the gen-advance gate.

**Unchanged (verified byte-for-byte):** the gen-gate `if (p.gen > lastGen) { ... }`, the `lastGen` / `lastGenAt` assignments inside it, the freshness watchdog (`isStale`, `STALE_MS`, `lastGenAt` age check), and the offset-cancellation timer (`skew`, `currentElapsed`, rAF loop).

**Test (tests/test_ui_overlay_render.py):** Strengthened `test_poll_nonce_and_gen_gate_present` — retains the existing `?t=`, `lastGen`, and `> lastGen` (gen-gate) assertions and ADDS `assert "reqSeq" in js` plus `assert '?t=" + (++reqSeq)' in js` to pin the per-request nonce. A regression back to a per-gen nonce now fails the suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test nonce-expression assertion substring corrected to match the actual quoted literal**
- **Found during:** Task 1 (test run)
- **Issue:** The plan suggested asserting the substring `"?t=\" + (++reqSeq)"` (with `?t=` as a standalone quoted token). But the actual fetch literal is `"/overlay-json?t=" + (++reqSeq)`, where `?t=` lives inside the larger `"/overlay-json?t="` string — so `"?t=" + (++reqSeq)` (with a leading quote before `?t=`) never appears in the served JS. The first test run FAILED on that exact assertion.
- **Fix:** Changed the asserted substring to `?t=" + (++reqSeq)` (dropping the spurious leading quote), which matches the real expression. This also exactly matches the plan's own `key_links` regex pattern `overlay-json\?t=" \+ \(\+\+reqSeq\)`.
- **Files modified:** tests/test_ui_overlay_render.py
- **Commit:** 63713d8

## Verification

- `python -m pytest tests/test_ui_overlay_render.py -q` → 11 passed (served-JS asserts + node-executed cleanField byte-parity + skew/freeze/overtime behavior + no-innerHTML sink + the strengthened nonce/gen-gate assertions).
- `git status --short` confirms the diff touches ONLY `src/segugio/ui/static/overlay-render.js` and `tests/test_ui_overlay_render.py`. The pre-existing uncommitted `.planning/config.json` and untracked `10-PATTERNS.md` were left exactly as found (not staged, not modified).
- `git diff --diff-filter=D HEAD~1 HEAD` → no file deletions.

## Self-Check: PASSED

- FOUND: src/segugio/ui/static/overlay-render.js (modified, `reqSeq` + `(++reqSeq)` present)
- FOUND: tests/test_ui_overlay_render.py (modified, `reqSeq` assertions present)
- FOUND: commit 63713d8
