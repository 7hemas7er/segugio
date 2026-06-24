---
phase: 17-console-modal-multi-throw-state-tablet-ux
reviewed: 2026-06-24T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/segugio/ui/templates/_score-entry-form.html
  - src/segugio/ui/templates/score-entry.html
  - src/segugio/ui/static/score-entry.js
  - src/segugio/ui/templates/console.html
  - src/segugio/ui/app.py
  - tests/test_ui_score_entry.py
  - tests/test_imports.py
  - tests/test_ui_score.py
  - tests/test_ui_score_authoritative.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-06-24
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 17 retired the legacy `#form-score` path and its `_is_legacy_score_post`
back-compat branch, moved score entry into a shared Jinja partial mounted both on
`/score-entry` and inside a console native `<dialog>`, added reload-safe
localStorage draft persistence, a two-step danger-styled publish confirm with
Enter-suppression, and a read-only on-air readout polling `/overlay-json`.

The three highest-risk concerns flagged for this review all hold up:

- **Broadcast integrity:** The two-step arm→confirm gate is correctly implemented
  (`score-entry.js:218-244`). A first tap only morphs/arms (returns before any
  POST); only a second tap while `armed` calls `submit()`. The `root` keydown
  handler swallows Enter unconditionally and never touches the submit path. This
  is well covered by tests.
- **XSS / innerHTML:** `score-entry.js` is genuinely free of any `innerHTML` sink;
  every operator value reaches the DOM via `textContent` / `createElementNS`, and
  the gate test (`test_no_innerhtml_sink`) enforces it. The console's `innerHTML`
  uses are confined to STATIC icon markup with operator data appended as text
  nodes (no interpolation of untrusted data into the markup string).
- **Server-side validation after legacy removal:** `POST /score` still validates
  RAW inputs first via `score_calc.validate` and writes nothing on any error
  (`app.py:348-354`). The non-`dict` JSON body guard (CR-01) and the non-list
  `throws` guard (CR-02 in `score_calc.py`) both correctly funnel malformed input
  to a 400 rather than a 500. No regression here.

The issues below are correctness/robustness defects of lower severity and a set
of maintainability items. No BLOCKER-class defects were found.

## Warnings

### WR-01: Console page double-mounts the score component into the hidden dialog on load

**File:** `src/segugio/ui/static/score-entry.js:685-691`, `src/segugio/ui/templates/console.html:325-339`
**Issue:** The shared partial `_score-entry-form.html` unconditionally loads
`score-entry.js`, whose IIFE runs `autoMount()` on `DOMContentLoaded`.
`autoMount()` does `mount(document.getElementById("score-entry-root"), cfg)` — and
on the console page the ONLY `#score-entry-root` is the one inside the still-closed
`<dialog>`. So the component is fully built (and `restoreDraft()` replays the saved
throw list) into a hidden dialog on every console load, then `openScoreDialog()`
mounts it a second time on open (`console.html:337`). Side effects of the
load-time mount that run while the dialog is hidden: the global `root` keydown
handler is attached, `recompute()` runs, and the draft is restored against a
non-visible surface. It is not a crash (the second `mount()` clears `root` and uses
a fresh closure, so no double-count), but it is unintended work and an attached
listener on a hidden subtree, and it means the documented "mount on OPEN, not
auto-mounted into a hidden dialog on load" contract (console.html:303-304, 322) is
violated in practice.
**Fix:** Make `autoMount()` skip a root that lives inside a closed `<dialog>`, or
gate auto-mount to the dedicated page only. E.g.:
```js
function autoMount() {
  if (typeof document === "undefined") return null;
  const root = document.getElementById("score-entry-root");
  if (!root) return null;
  // Do not auto-mount a root that lives inside a dialog — the host mounts it on open.
  if (root.closest && root.closest("dialog")) return null;
  const el2 = document.getElementById("score-cfg");
  let cfg = {};
  if (el2) { try { cfg = JSON.parse(el2.textContent); } catch (_e) { cfg = {}; } }
  return mount(root, cfg);
}
```

### WR-02: Draft restore replays throws regardless of the active discipline, and the draft is silently lost when entering on a non-T&F discipline

**File:** `src/segugio/ui/static/score-entry.js:114-128, 266-285`
**Issue:** `saveDraft()` serializes ONLY `throwRows` (the disc_tf list); on
freestyle or agility there is nothing to persist, so a reload-safe draft simply
does not exist for those disciplines — acceptable per the D-01 "flat throw list
only" scope. However the restore path is not discipline-aware: `restoreDraft()`
replays saved throws into `discTfList` whenever a draft exists, even if the user
switched `active` to `disc_freestyle`/`agility` after the rows were saved. Because
`addThrowRow` does not flip `active`, the restored disc_tf rows are appended (and
shown if disc_tf is the first discipline) but are invisible/ignored under another
active discipline, while `recompute()` still runs against the non-T&F surface.
This is a latent inconsistency: the persisted unit and the active surface can
diverge, and there is no discipline tag on the draft to detect it.
**Fix:** Tag the draft with the discipline it was captured under and only restore
when it matches the active discipline (or restore + switch `active` to disc_tf):
```js
function saveDraft() {
  if (!lsAvailable) return;
  const payload = { discipline: active, throws: throwRows.map(r => ({
    zone: r.zoneSel.value, midair: !!r.midair.checked, corridor: !!r.corridor.checked })) };
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(payload)); } catch (_e) {}
}
// restoreDraft: accept the legacy array shape AND the tagged object shape,
// and only replay throws when (saved.discipline || "disc_tf") === active.
```

### WR-03: localStorage draft key is shared across every mount, so the dedicated page and the console modal cross-contaminate

**File:** `src/segugio/ui/static/score-entry.js:110, 256-285`
**Issue:** `DRAFT_KEY = "segugio.score.draft"` is a single fixed key with no host
scoping. The dedicated `/score-entry` page and the console `<dialog>` modal share
the same browser origin and the same key. A half-entered draft started in the
modal will silently appear in the dedicated page (and vice-versa) on next mount,
and — combined with WR-01 — a draft is restored into the hidden console dialog on
every console load. For the broadcast-integrity goal this is mostly benign (the
two-step confirm still gates air), but it means an operator can open the modal and
unexpectedly see throws they entered earlier on the standalone page, which is a
confusing state for a live tool. The "one fixed key, one atomic setItem" comment
(line 110) presents this as intentional, but the cross-surface implication is not
analyzed.
**Fix:** If cross-surface sharing is genuinely desired, document it as a decision
and keep it; otherwise scope the key per host (e.g. derive a suffix from a host
attribute on `#score-cfg` such as `data-host="page"` vs `data-host="modal"`), or
clear the draft on dialog close so the modal never resurrects a stale page draft.

### WR-04: On-air readout total fallback can show a stale total when only `faults` updates

**File:** `src/segugio/ui/templates/console.html:738-742`
**Issue:** `pollOverlayJson()` picks the displayed total as
`fields.totale != null ? fields.totale : (fields.faults != null ? fields.faults : null)`
and, when `total` is null/empty, leaves the previous value (safe-coast). For
count_up agility the score doc carries `faults` and NO `totale` (see
`score_calc._compute_agility`, which sets `out["faults"]` only for count_up). That
is handled. But the readout never clears: when a new score with neither `totale`
nor `faults` airs (e.g. an eliminated agility run uses `totale = sentinel`, which
is fine, but a discipline switch from agility-count_up back to a disc score where
the prior `faults` was shown), the `#onair-total` retains the last value until a
new non-null total arrives. Since this is a read-only mirror of what is airing,
showing a stale number from a previous, different score is a (mild) integrity
concern for the operator's situational awareness. The discipline label updates
independently of the total, so the two can briefly disagree (new discipline, old
total).
**Fix:** When `d.discipline` changes between polls, reset `#onair-total` to "—"
before applying the new total, so a discipline switch never shows the prior
discipline's number:
```js
// track the last discipline; on change, clear the total before re-deriving it
if (discEl && d && d.discipline && discEl.dataset.disc !== d.discipline) {
  discEl.dataset.disc = d.discipline;
  if (totEl) totEl.textContent = "—";
}
```

## Info

### IN-01: `_parse_structured_inputs` still whitelists `timer`, a field the new form no longer renders

**File:** `src/segugio/ui/app.py:144`
**Issue:** The freestyle key whitelist includes `"timer"`, but the retired
`#form-score` was the only producer of a `timer` field; the new shared component
(`score-entry.js buildFreestyle`) renders no `timer` input. The key is now dead on
the input boundary (harmless — `if key in raw` simply never matches), and
`_compute_freestyle` still `setdefault`s `timer`. Leftover from the legacy path.
**Fix:** Drop `"timer"` from the freestyle whitelist in `_parse_structured_inputs`
(and consider dropping the `timer` setdefault in `score_calc._compute_freestyle`)
unless a future producer is planned.

### IN-02: Stale/contradictory docstring references to the retired legacy path

**File:** `src/segugio/ui/app.py:200-201`, `src/segugio/ui/score_calc.py:16` (module docstring of `tests/test_ui_score_authoritative.py`)
**Issue:** `create_app`'s docstring still says the `profile=None` default keeps
"the legacy console form" green (app.py:200-201), and the authoritative test file's
module docstring still describes the legacy flat-key form "round-tripping until P17
retires it" (test_ui_score_authoritative.py:14-16) even though the body now asserts
the opposite (`test_legacy_flat_keys_now_rejected`). These comments now misdescribe
the shipped behavior.
**Fix:** Update the docstrings to reflect that the legacy form/path is retired and
the authoritative structured path is the sole producer.

### IN-03: `decoding="sync"` on every preview `<img>` is a non-standard/deprecated value

**File:** `src/segugio/ui/templates/console.html:254`
**Issue:** `<img ... decoding="sync">` — `sync` is an accepted enum value but the
file's own comment (console.html:563-564) calls it "only belt-and-suspenders"
because the real flicker control is the off-DOM `preloader.decode()` swap. Setting
`decoding="sync"` forces synchronous decode on the visible element, which can block
the main thread on a large frame and is at odds with the async-decode strategy the
rest of the refresh path uses. Not introduced this phase, but it sits directly in
the modified template region.
**Fix:** Consider `decoding="async"` (or removing the attribute) since the preload
`decode()`-then-swap already eliminates the flash; verify on-device.

### IN-04: `open-score` button uses an inline `style` attribute, inconsistent with the token-based stylesheet

**File:** `src/segugio/ui/templates/console.html:281`
**Issue:** `<button ... id="open-score" style="margin-top: 16px;">` uses an inline
style where the rest of the file uses the documented 4px-multiple spacing tokens in
the `<style>` block (the file explicitly forbids ad-hoc weights/sizes; inline
spacing is the same class of drift). Minor consistency issue only.
**Fix:** Move `margin-top: 16px` into a small rule (e.g. `#open-score { margin-top: 16px; }`)
alongside the other component rules.

---

_Reviewed: 2026-06-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
