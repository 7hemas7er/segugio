---
phase: 17-console-modal-multi-throw-state-tablet-ux
verified: 2026-06-24T00:00:00Z
status: passed
uat_confirmed: 2026-06-26T21:18:09Z
status_history: [human_needed @2026-06-24, passed @2026-06-26 after automated browser UAT]
score: 4/4 truths verified (code level); 5/5 human-verification items confirmed via automated browser UAT
overrides_applied: 0
human_verification:
  - test: "Open the console (localhost:8080), click 'Inserisci / modifica punteggio' and interact with the score modal"
    expected: "Modal opens with the full score-entry form mounted (discipline selector, fields, advisory total); Escape closes; a second open re-mounts cleanly and restores any in-progress draft"
    why_human: "WR-01 (code review): autoMount() runs on DOMContentLoaded and mounts the component into the hidden dialog root before openScoreDialog() is called — the 'mount-on-open-NOT-on-load' contract is violated at runtime. The mount-on-open code exists and is correct, but autoMount() fires first unconditionally. Visually this may be transparent (mount() is re-mountable) but the hidden-mount side effects (global keydown listener on a non-visible subtree, restoreDraft() running against a closed dialog) need operator confirmation that they do not cause UX regressions on the tablet."
  - test: "On /score-entry: add 2 throws with distinct zone/midair/corridor settings, then hard-reload the page (Cmd+Shift+R / Ctrl+F5)"
    expected: "The two throw rows reappear with the same values and the advisory total matches pre-reload. No console exception."
    why_human: "localStorage draft restore is correct in code (try/caught, replays via addThrowRow, recompute() called after), but reload-safe behavior requires a real browser with a live localStorage — not verifiable via pytest or node fake-DOM tests."
  - test: "Corrupt the draft: open devtools > Application > localStorage, set 'segugio.score.draft' to '{' (invalid JSON), then reload /score-entry"
    expected: "Page mounts with an empty throw list, no console exception"
    why_human: "The never-raise reader is verified in code (JSON.parse inside try/catch, return on exception) but the exact browser behaviour with a torn value needs human confirmation."
  - test: "On /score-entry: click 'Manda in onda' once, observe it turns red / 'Conferma invio'. Wait 5 seconds without clicking."
    expected: "Button reverts to 'Manda in onda' (un-armed). No POST to /score occurred."
    why_human: "Auto-revert is coded correctly (4000ms setTimeout calling disarm()), but real-timer behaviour needs human confirmation."
  - test: "Press Enter while focused on any input in the score form (dedicated page and inside the modal)"
    expected: "Nothing is submitted, the button does not arm, no network request to /score"
    why_human: "The root keydown guard is correctly wired in code (e.key === 'Enter' -> preventDefault, no arm/submit path), but the interaction with different input types (select, checkbox) needs human confirmation."
---

# Phase 17: Console Modal, Multi-Throw State & Tablet UX — Verification Report

**Phase Goal:** The operator can enter and publish a score from inside the console via a popup that reuses the exact same component, accumulate multi-throw/round entries without losing them, and do it all reliably on the offline-rig tablet.
**Verified:** 2026-06-24
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The operator opens a console dialog modal and enters a score using the SAME component — both hosts share one Jinja partial (_score-entry-form.html) and one JS module (score-entry.js), so page and modal are byte-for-byte the same form (no duplicated calc/submit logic, no re-introduced mirror). | VERIFIED | `_score-entry-form.html` exists with the exact 4 host nodes + 2 script tags. `score-entry.html` contains `{% include "_score-entry-form.html" %}` and no inline host markup. `console.html` contains `{% include "_score-entry-form.html" %}` inside `<dialog id="score-dialog">`. One JS module (`score-entry.js`) is mounted by both hosts. |
| 2 | For multi-throw disc T&F the operator adds/edits throws across N rounds and sees a correct progressive running total; reloading the tablet mid-run restores the in-progress entry (no lost throws), and any persisted in-progress state is written atomically with a never-raise reader. | VERIFIED (code) | `DRAFT_KEY = "segugio.score.draft"` at score-entry.js:111. `saveDraft()` calls `localStorage.setItem` on every add/remove/input mutation (lines 311, 354, 366). `restoreDraft()` is called after `showFields()`/`recompute()` at line 258, wraps `JSON.parse(localStorage.getItem(DRAFT_KEY))` in try/catch (lines 269-273), returns silently on error. `localStorage.removeItem(DRAFT_KEY)` appears ONLY in the `resp.ok` branch of `submit()` (lines 616-622). Human confirmation needed for live browser behavior (see Human Verification). |
| 3 | Publishing to air is a deliberate, visually distinct action — a casual tap or Enter cannot put a half-entered score on air. | VERIFIED | Two-step arm gate: `publishBtn.addEventListener("click", ...)` — first tap sets `armed=true`, morphs button to "Conferma invio" + `classList.add("danger")`, starts 4000ms auto-revert timer, `return`s before any POST (lines 218-232). Second tap while armed calls `submit()` then `disarm()`. Enter guard: `root.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); return; } })` (lines 239-244) — never touches arm/submit path. Button is never set `disabled`. |
| 4 | The new page and modal load with ZERO external/CDN assets, all inputs are ≥16px (no iOS focus-zoom), and the modal traps focus and survives sleep/wake — code-time tablet contract met (real-iPad rig UAT deferred, non-blocking). | VERIFIED (code) | No `http://`/`https://` script or link src found in `_score-entry-form.html` or `console.html` (only comments contain the word "CDN"). `input, select { font-size: 1rem; }` in both console.html (line 29) and score-entry.html (line 26). `dialog.showModal()` called in `openScoreDialog()` (console.html:328) — native focus trap, no hand-rolled trap. Sleep/wake: `startPolling()`/`stopPolling()` wired to `visibilitychange` + `pagehide`/`pageshow.persisted`. Real-iPad UAT explicitly deferred (non-blocking per plan). |

**Score:** 4/4 truths verified at code level

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/templates/_score-entry-form.html` | Shared score-entry host markup partial | VERIFIED | Exists; contains `id="score-entry-root"`, `id="score-cfg"`, `id="publish-banner"`, `{{ score_cfg \| tojson }}`, `/static/score-calc.js`, `/static/score-entry.js`. 7 lines, zero external assets. |
| `src/segugio/ui/static/score-entry.js` | localStorage draft + two-step confirm + Enter-suppression in one mount() closure | VERIFIED | Contains `localStorage.setItem`, `localStorage.getItem`, `localStorage.removeItem`, `DRAFT_KEY`, "Conferma invio", `classList.add("danger")`, `keydown` + `"Enter"` check. No `innerHTML =` sink. |
| `src/segugio/ui/templates/score-entry.html` | Dedicated page includes the shared partial instead of inlining host markup | VERIFIED | Contains `{% include "_score-entry-form.html" %}` at line 81; no inline `id="score-entry-root"`. `<style>` block and `<h1>Inserimento punteggio</h1>` remain on the page. |
| `src/segugio/ui/templates/console.html` | On-air readout + modal-open button + native dialog including the shared partial; legacy form retired | VERIFIED | Contains `{% include "_score-entry-form.html" %}` inside `<dialog id="score-dialog">`. `id="form-score"` is absent (grep returns 0). `Inserisci / modifica punteggio` button present. `pollOverlayJson` function wired to `/overlay-json`. Legacy `showFields()`/`#form-score` submit JS absent. `post()`/`run-btn` preserved. |
| `src/segugio/ui/app.py` | `index()` renders console.html with score_cfg; legacy post_score branch removed | VERIFIED | `render_template("console.html", cam_ids=sorted(cam_ids), score_cfg=_score_cfg)` at line 297. `_is_legacy_score_post`, `_NON_SCORE_KEYS`, `_STRUCTURED_KEYS` all absent (grep returns 0 matches). |
| `tests/test_imports.py` | POST /score smoke updated to authoritative structured JSON | VERIFIED | Tests pass (26 passed). POST smoke sends structured JSON disc_tf body asserting 204/200. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `score-entry.html` | `_score-entry-form.html` | `{% include %}` | VERIFIED | Line 81 of score-entry.html |
| `console.html` | `_score-entry-form.html` | `{% include %}` inside `<dialog id="score-dialog">` | VERIFIED | Line 310 of console.html |
| `console.html` | `/overlay-json` | `pollOverlayJson` function in named-interval `overlayTimer` | VERIFIED | Lines 728-744, wired into startPolling()/stopPolling() and cold-started at line 828 |
| `app.py` `index()` | `console.html` | `render_template` with `score_cfg=_score_cfg` | VERIFIED | `render_template("console.html", ..., score_cfg=_score_cfg)` at line 297 |
| `score-entry.js` `submit()` | `localStorage.removeItem(DRAFT_KEY)` | ONLY in `resp.ok` branch | VERIFIED | Lines 616-622; 400 branch and `.catch()` branch leave draft intact |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `console.html` on-air readout | `#onair-discipline`, `#onair-total` | `GET /overlay-json` (app.py:441-463) | Yes — reads `overlay.txt` + `score.json` written by the authoritative `post_score` path | FLOWING |
| `score-entry.js` throwRows | `throwRows[]` (and localStorage draft) | Operator input via `addThrowRow()` + `localStorage.getItem(DRAFT_KEY)` on mount | Real operator data | FLOWING |
| `_score-entry-form.html` `#score-cfg` | `score_cfg` blob | `index()` and `score_entry()` in app.py (both pass `score_cfg=_score_cfg`) | Factory-time scoring profile (Decimal strings, stdlib only) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_is_legacy_score_post` removed from app.py | `grep -c '_is_legacy_score_post' src/segugio/ui/app.py` | 0 | PASS |
| Legacy `#form-score` removed from console.html | `grep -c 'id="form-score"' src/segugio/ui/templates/console.html` | 0 | PASS |
| No `innerHTML =` sink in score-entry.js | grep for `innerHTML\s*=` | No matches | PASS |
| Partial included by console.html | grep for `_score-entry-form.html` in console.html | Line 310 found | PASS |
| `showModal` present in console.html | grep for `showModal` | Lines 328, 329 found | PASS |
| Full test suite | `pytest -q` | 5 failed, 549 passed, 8 skipped — all 5 failures are pre-existing known failures (NDI hardware, node ESM, iframe, class="layout" staleness) | PASS |
| Test files for plan-01 behaviors | `pytest tests/test_ui_score_entry.py -q` | 11 passed | PASS |
| Import smoke gate | `pytest tests/test_imports.py -q` | 26 passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCE-04 | 17-01, 17-02 | Pubblicazione esplicita — azione chiara "manda in onda"; UX tablet-first (input ≥16px, focus-trap nel modal, asset offline/no-CDN) | SATISFIED | Two-step arm→confirm gate implemented; Enter-never-publishes guard implemented; input font-size 1rem (≥16px) in both templates; `showModal()` focus-trap; no external/CDN assets |
| SCC-05 | 17-01, 17-02 | Multi-lancio/round con totale progressivo; stato in-progress robusto (scrittura atomica; restore lato client su reload) | SATISFIED (code) | `saveDraft()` writes on every mutation; `restoreDraft()` is a never-raise reader called at end of `mount()`; draft cleared only on 2xx; human verification needed for live browser behavior |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `console.html` | 440-442 | `innerHTML = icon(...)` — static SVG string, then `.append(" " + score.toFixed(2))` / `" coast"` / `" lost"` (text nodes). Static markup, NO operator data interpolated into the markup string; value appended via `.append()` (text node). | INFO | Not an XSS risk: icon() returns a fixed SVG string, operator data is appended as a text node. Consistent with console.html's existing pattern for static icon glyphs. |
| `console.html` | 408, 607, 757 | `innerHTML = ""` — used to clear containers before rebuilding with DOM nodes | INFO | Clearing pattern, not a data-injection sink. Consistent with pre-existing console.html code. |
| `console.html` | 281 | `style="margin-top: 16px;"` on `#open-score` button | INFO | Inline style inconsistent with the token-based stylesheet. Matches WR-04 from code review. No functional impact. |
| `score-entry.js` | 667-679 | `autoMount()` does NOT guard against mounting into a hidden `<dialog>` | WARNING | WR-01 from code review: `autoMount()` runs on DOMContentLoaded and targets `document.getElementById("score-entry-root")` — on the console page this resolves to the root INSIDE the closed `<dialog>`. The component is fully mounted (keydown listener attached, `restoreDraft()` runs) before `openScoreDialog()` is called. `mount()` is re-mountable so no double-count or crash, but the "mount-on-OPEN, NOT on load" contract documented in console.html:303-304 is violated in code. Fix: add `if (root.closest && root.closest("dialog")) return null;` in `autoMount()`. |

**Debt marker gate:** No TBD, FIXME, or XXX markers found in phase-17-modified files.

### Human Verification Required

#### 1. Console modal double-mount side effects (WR-01)

**Test:** Open the Segugio console at localhost:8080. Open browser devtools (Network tab). Click "Inserisci / modifica punteggio". Observe the modal and check: (a) the form mounts correctly with fields visible; (b) no duplicate network requests or duplicate event handlers cause unexpected behavior; (c) add a throw, close the modal (Escape or "Chiudi"), re-open — the throw is still there (draft restored on re-open).
**Expected:** Modal shows the full score-entry form correctly. The re-open mount replays the draft. No UX regression from the hidden load-time mount.
**Why human:** `autoMount()` unconditionally mounts into the hidden dialog root on DOMContentLoaded (WR-01). The second `openScoreDialog()` mount calls `mount()` again which clears and rebuilds root — re-mountable in code. But the net effects (a global keydown listener on a non-visible subtree from the first mount, `restoreDraft()` running while dialog is closed) need live-browser validation that they don't produce observable regressions on the tablet. The code review flagged this as a WARNING (not a blocker).

#### 2. Reload-safe localStorage draft restore (live browser)

**Test:** On /score-entry: add 2 throws (zone 2, midair checked; zone 4, corridor checked). Note the advisory total. Then hard-reload the page (Ctrl+Shift+R or Cmd+Shift+R to bypass cache).
**Expected:** Both throw rows reappear with the same zone/midair/corridor values. The advisory total matches the pre-reload value. No console exception.
**Why human:** The draft save/restore logic is correct in code and tested in the node fake-DOM harness, but live browser localStorage behavior (particularly after a hard reload) requires a real browser for confirmation.

#### 3. Corrupt draft — never-raise reader (live browser)

**Test:** Open devtools > Application > localStorage on any Segugio page. Set key `segugio.score.draft` to the string `{` (invalid JSON). Navigate to /score-entry.
**Expected:** The page mounts with an empty throw list and no JavaScript console exception.
**Why human:** The `try { JSON.parse(...) } catch { return; }` path is correct in code. Browser LocalStorage corruption edge-cases need real-browser confirmation.

#### 4. Two-step confirm auto-revert (live browser)

**Test:** On /score-entry, click "Manda in onda" ONCE. Observe it turns to a red-styled "Conferma invio". Wait 5 seconds without clicking.
**Expected:** The button reverts to "Manda in onda" with its normal blue style. No POST to /score was made (check devtools Network tab).
**Why human:** The 4000ms `setTimeout(disarm, CONFIRM_WINDOW_MS)` is correct in code and tested in the node harness with fake timers, but real browser timer behavior (especially under CPU pressure on a tablet) needs human confirmation.

#### 5. Enter-never-publishes (live browser, both hosts)

**Test:** (a) On /score-entry: focus any input field (zone select, or a freestyle/agility text field) and press Enter. (b) Repeat inside the console score modal.
**Expected:** In both cases: the form is not submitted, no network request to /score is visible in devtools, and the "Manda in onda" button does not change to "Conferma invio".
**Why human:** The `root.addEventListener("keydown", ...)` guard is correct in code. But keyboard interaction on mobile/tablet — especially with OS virtual keyboard "Go"/"Enter" keys — needs on-device confirmation.

### Gaps Summary

No blocking gaps were found. All 4 roadmap success criteria are verifiably met at code level:

1. One shared Jinja partial (`_score-entry-form.html`) is included by both `score-entry.html` and `console.html` inside `<dialog id="score-dialog">` — structural anti-drift confirmed.
2. Multi-throw reload-safe state: `saveDraft()` wired to all mutations, `restoreDraft()` is a never-raise reader called at end of `mount()`, draft cleared only on 2xx.
3. Two-step publish confirm with auto-revert + Enter-never-publishes: both implemented correctly, button never disabled.
4. Zero external/CDN assets, inputs ≥16px, `showModal()` focus-trap, sleep/wake lifecycle wired.

The five human verification items are behavioral runtime confirmations, not code defects. The code review WR-01 (autoMount into hidden dialog) is the highest-priority item to confirm — if the double-mount causes observable side effects on the tablet, a one-line fix in `autoMount()` resolves it (add `if (root.closest && root.closest("dialog")) return null;`).

The 5 test failures in the full suite are exactly the 5 pre-existing known failures confirmed in `test_context` — no phase-17 regression.

---

## Automated UAT Confirmation (2026-06-26)

All 5 human-verification items were subsequently confirmed via **automated browser UAT** (Playwright,
msedge headless) driving an **isolated sandbox** at `127.0.0.1:8099` (scratch opcomm dir) — never any
live `:8080` director. Full results recorded in `17-UAT.md` (status: complete, 5/5 pass).

| # | Item | Result | Key evidence |
|---|------|--------|--------------|
| 1 | Console modal open/mount/close/re-open (WR-01) | PASS | 1 `#score-entry-root`; clean re-mount (1 discipline-block/1 root/1 publish on re-open); on-air readout polled `/overlay-json` 3×; no real errors. **WR-01 is benign** — hidden mount on load, but `mount()` clears the root + fresh closures ⇒ no doubling/double-count. |
| 2 | Reload-safe draft restore | PASS | 2 throws (zone 2 midair / zone 3 corridor), total 6.0; after hard reload rows + total restored identically; no errors. |
| 3 | Corrupt draft → clean mount | PASS | `segugio.score.draft="{"` → 0 rows, empty-state visible, never-raise reader caught it, no exception. |
| 4 | Two-step publish auto-revert | PASS | first tap → "Conferma invio"/.danger; after 4.6 s reverted; **0 POSTs** to `/score`. |
| 5 | Enter never publishes/arms | PASS | Enter on select/select/text input + modal input → button stays "Manda in onda"; **0 POSTs**. |

**Broadcast integrity proven:** total POSTs to `/score` observed across the entire UAT run = **0**.

Only remaining deferred (non-blocking) item: real-iPad rig ergonomics / OS virtual-keyboard / sleep-wake —
the code-time tablet contract (success criterion 4) is met; physical-device UAT is explicitly deferred per the roadmap.

---

_Verified: 2026-06-24 (code) · UAT confirmed: 2026-06-26 (automated browser)_
_Verifier: Claude (gsd-verifier) · UAT: Claude (gsd-verify-work, Playwright)_
