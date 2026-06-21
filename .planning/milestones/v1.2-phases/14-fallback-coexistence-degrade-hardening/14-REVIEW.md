---
phase: 14-fallback-coexistence-degrade-hardening
reviewed: 2026-06-20T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - config.example.yaml
  - docs/obs-setup.md
  - docs/security.md
  - src/segugio/ui/static/overlay-render.js
  - tests/test_overlay_degrade_gate.py
  - tests/test_overlay_fallback_gate.py
  - tests/test_overlay_html_sink_gate.py
  - tests/test_overlay_poll_storm.py
  - tests/test_scene_template.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-20
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 14 hardens the live-broadcast overlay with a second `DEAD_MS` (~3s) degrade stage on top of the existing `STALE_MS` dim stage, plus docs/config/test gates. The only runtime change is `overlay-render.js`. The new `isDead()` watchdog is correctly keyed on response-recency (`everResponded && now - lastResponseAt > DEAD_MS`), NOT gen-age — the 260615-tsi anti-pattern is avoided, and the live-idle-run regression guard confirms it. The two-stage ordering (`isDead()` checked before `isStale()`), the rAF stop condition, and the phantom-jump re-anchor all hold under the shipped tests. The config NDI-name change byte-matches the scene-collection JSON (verified), and the XSS posture (`textContent` only, no `innerHTML`) is intact.

However, the dead-path reuse of the `is-exiting` exit animation introduces a one-way state transition with **no recovery counterpart**: after a sustained (>3s) outage during a still-running run, when the console comes back the lower-third stays hidden for the rest of the run. This is a BLOCKER — the overlay silently disappears on air after a recoverable WiFi outage. The shipped degrade test never resumes after death, and the phantom-jump test resumes but asserts only the elapsed clock (not the visibility classes), so neither catches it.

## Critical Issues

### CR-01: Lower-third stays permanently hidden after a console death-and-recovery during a live run

**File:** `src/segugio/ui/static/overlay-render.js:318-323, 394-423`

**Issue:**
`applyDead()` removes `is-live`/`is-stale` and adds `is-exiting` (opacity:0). The ONLY code that removes `is-exiting` and restores `is-live` is the run-START edge in `animateRunEdge`:

```js
if (isRunning && !wasRunning) {
  lowerThird.classList.remove("is-exiting");
  retrigger(lowerThird, "is-entering");
  lowerThird.classList.add("is-live");
}
```

This branch only fires on a false→true `running` transition. When a console dies mid-run and later recovers, `wasRunning` is still `true` and the resume payload also has `running: true`, so `animateRunEdge(lowerThird, true, true)` takes NEITHER branch. `applyPayload` then calls `applyStale(false)`, which removes only `is-stale` — never `is-exiting`. Result: the run keeps ticking (rAF re-arms, `isDead()` returns false), but the lower-third remains at opacity:0 — invisible on air for the rest of the run.

Reproduced in a node fake-DOM harness (same harness as `test_overlay_degrade_gate.py`):
```
after live:     is-live=true  is-exiting=false
after death:    is-exiting=true  is-live=false  isDead=true
after recovery: is-exiting=true  is-live=false  isDead=false  rafArmed=true
```
After recovery the watchdog correctly reports alive and the timer counts, but `is-exiting=true`/`is-live=false` — the plate never comes back.

This directly contradicts the live-robustness goal of the phase and the coexistence story in `docs/obs-setup.md` (the browser overlay is supposed to be the primary on-air score; a >3s WiFi hiccup must not permanently kill it). The existing tests miss it: `test_two_stage_stale_then_dead_hides_lower_third` never resumes after death; `test_gen_reanchor_no_phantom_jump` resumes but asserts only `currentElapsed()`, not the visibility classes.

**Fix:**
On resume, the dead state must be cleared and the plate re-shown. When a payload arrives showing the run still live (or restarting) while `is-exiting` is present, restore the live state. Smallest correct fix — clear the dead-hide and re-enter whenever a live payload is consumed while the plate is hidden:

```js
// In applyPayload(), after animateRunEdge(...) / before startTimer():
if (running && lowerThird && lowerThird.classList.contains("is-exiting")) {
  // recovered from a DEAD_MS full-hide: re-show the plate (mirror the enter edge)
  lowerThird.classList.remove("is-exiting");
  retrigger(lowerThird, "is-entering");
  lowerThird.classList.add("is-live");
}
```

Add a regression test that drives live → death (past DEAD_MS) → recovery (running:true, bumped gen) and asserts the lower-third regains `is-live` and loses `is-exiting`.

## Warnings

### WR-01: No test covers dead → recovery re-show; degrade gate stops at "stays dead"

**File:** `tests/test_overlay_degrade_gate.py:164-243`

**Issue:** The two-stage gate asserts death HIDES and stops the rAF loop, but never drives a resume. Combined with the phantom-jump test asserting only `currentElapsed()` (not classes), the suite has a blind spot that let CR-01 ship green. A degrade test that hides-on-death without asserting reveal-on-recovery only validates half the live failure mode (the dangerous half — never coming back — is untested).

**Fix:** Add a `test_dead_then_recover_reshows_lower_third` case: live polls → `fetchMode="down"`, `NOW += DEAD_MS + 500`, poll (assert `is-exiting`, `isDead()`) → `fetchMode="ok"`, bump gen, poll → assert `lowerThird.classList.contains("is-live")` and NOT `is-exiting`. This test should fail against current `overlay-render.js` and pass once CR-01 is fixed.

### WR-02: `docs/obs-setup.md` coexistence claim is incomplete — death auto-hide has no auto-reveal after recovery

**File:** `docs/obs-setup.md:119-132`

**Issue:** The docs state the browser overlay "auto-hides on death" so "a truly dead console's browser overlay vanishes on its own." They do not document what happens when the console recovers. Per CR-01, the browser overlay does NOT auto-reveal after a >3s outage during a live run — it stays hidden for the rest of the run, so the only on-air score is whatever the operator manually toggled (`Score Text`). An operator reading this doc would reasonably expect the browser overlay to reappear once the console is healthy again. This is operationally misleading on the safety-relevant coexistence path.

**Fix:** Once CR-01 is fixed (auto-reveal restored), this doc is correct as written. If CR-01 is deferred, add an explicit caveat: "after a sustained (>DEAD_MS) outage the browser overlay does not auto-restore for the remainder of the run — restart the OBS browser source or end/restart the run to bring it back." Prefer fixing CR-01 over documenting the defect.

### WR-03: `tick()` dead branch is effectively unreachable; `poll()` is the sole dead-applier

**File:** `src/segugio/ui/static/overlay-render.js:357-371`

**Issue:** `tick()` only runs while the rAF loop is armed, and the loop is armed only while `running && !isStale()`. On the first tick where the source becomes stale/dead it sets `rafId = null` and returns, so the loop is already stopped before `DEAD_MS` can elapse — meaning the `if (isDead()) applyDead()` branch in `tick()` is reached only in the rare case where a single frame straddles both thresholds (e.g. a multi-second main-thread stall). In practice the dead transition is driven entirely by `poll()` (lines 459-465). This is not incorrect, but the duplicated two-stage logic in `tick()` is dead-ish code that invites the reader to believe `tick()` participates in the dead transition. Note the harness in `test_overlay_degrade_gate.py:223` manually invokes the stored rAF frame to exercise this branch, masking that it never self-fires in production.

**Fix:** Either drop the `isDead()` check from `tick()` (let `tick()` only handle the dim/freeze on first stale, and let `poll()` own the dead escalation), or add a comment clarifying that `tick()`'s dead branch is a belt-and-suspenders path that normally never fires because the loop self-stops at the first stale frame. Keep `poll()` as the authoritative degrade driver.

## Info

### IN-01: `DEAD_MS` is a hardcoded literal while `STALE_MS` is derived from `PUBLISH_MS`

**File:** `src/segugio/ui/static/overlay-render.js:230, 235`

**Issue:** `STALE_MS = PUBLISH_MS * 3` is cadence-relative, but `DEAD_MS = 3000` is a bare magic number. If `PUBLISH_MS` is ever retuned, the stale/dead spacing relationship (`DEAD_MS` must stay `> STALE_MS`) is not expressed in code — it holds only by the current numeric coincidence (600 < 3000). A future cadence change could silently invert the ordering.

**Fix:** Express the invariant in code, e.g. `const DEAD_MS = Math.max(3000, STALE_MS * 5);` or at minimum add an inline assertion/comment that `DEAD_MS > STALE_MS` is a load-bearing precondition. The comment already says "MUST stay > STALE_MS" — encode it.

### IN-02: `renderOverlay` has a defensive `getElementById` fallback that never runs and is partly broken

**File:** `src/segugio/ui/static/overlay-render.js:207`

**Issue:**
```js
const lowerThird = root.querySelector("#lower-third") || root.getElementById && root.getElementById("lower-third");
```
Operator precedence makes this `querySelector(...) || (root.getElementById && root.getElementById(...))`. When `querySelector` returns null and `root.getElementById` is undefined, the expression yields `undefined` (the short-circuited `&&`), not a node. Also `createRenderer` already resolves `lowerThird` via `root.querySelector("#lower-third")` and that is the value actually used for animations; the `lowerThird` returned from `renderOverlay` is discarded by the caller (`applyPayload` uses `res.scoreChanged` only). Dead/confusing defensive code.

**Fix:** Drop the `getElementById` fallback and the unused `lowerThird` return from `renderOverlay`: `const lowerThird = root.querySelector("#lower-third");` (or remove it entirely since the return value is unused). Reduces confusion about which `lowerThird` reference drives the DOM.

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
