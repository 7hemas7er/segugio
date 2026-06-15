---
phase: 12-scv-01-unification
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/segugio/ui/app.py
  - src/segugio/ui/templates/console.html
  - src/segugio/ui/templates/overlay.html
  - tests/test_ui_explainability.py
  - tests/test_ui_overlay_page.py
  - tests/test_ui_overlay_render.py
  - tests/test_ui_scv_unification.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

This phase (SCV-01 Unification) replaced the hand-maintained byte-exact Python↔JS score
mirror in the console with a same-origin `<iframe src="/overlay?preview=1">`, added a cosmetic
`preview=1` flag to `GET /overlay`, added preview-only CSS to `overlay.html`, and deleted the
`POST /score/preview` route plus the entire `gsd:scv01-mirror` JS block + its drift-guard
symbols.

The core implementation is **functionally correct and secure**. I verified at runtime:

- The `preview` flag is a CLOSED boolean (`request.args.get("preview") == "1"`). `preview=1` →
  `<body class="preview">`; bare `/overlay`, `preview=0`, and `preview=anything` all →
  `<body class="">`. The template output is one of two fixed server-controlled literals
  (`preview` or empty), so there is **no template-injection / XSS surface** from the new query
  param.
- The deleted route is fully unregistered (`POST /score/preview` → 404/405) and `tests/test_score_preview.py` is deleted.
- Every deleted mirror/drift symbol (`mirrorOverlayText`, `scvCurrentFields`,
  `updateScorePreview`, `scheduleScorePreview`, `driftCheck`, `setDrift`, the `gsd:scv01-mirror`
  block, `#drift-warning`, `#overlay-preview`, `/score/preview`) is absent from the served
  console HTML — no dangling references, no over-deletion (score POST / run buttons / discipline
  toggler all survive).
- `render_overlay_text` is still imported and still used by `POST /score` (line 210) — not a
  leftover unused import.
- The iframe is same-origin; the embedded `/overlay` page sanitizes every operator value via
  `textContent` (no `innerHTML`), so the preview path inherits the same XSS mitigation as the
  broadcast path.

The findings below are quality/robustness defects, not security or data-loss issues. The two
most important are a now-permanently-masked test (WR-01) and a cosmetic CSS override that
contradicts its own design comment (WR-02).

## Warnings

### WR-01: `test_preview_flag_threads_body_class` is permanently masked — gives zero regression protection

**File:** `tests/test_ui_overlay_page.py:179-187`
**Issue:** Six of the seven `xfail(strict=False)` implementation-target tests now XPASS (the
implementation landed). But `test_preview_flag_threads_body_class` **still genuinely fails** and
stays reported as `xfail` (expected-fail), so it is silently masked. The failing assertion is:

```python
assert "body.preview" not in bare_html and 'class="preview"' not in bare_html
```

The implementation inlines the preview CSS rules (`body.preview { ... }`,
`body.preview #lower-third { ... }`) into the `<style>` block of **every** `/overlay` response,
including the broadcast page. So the literal substring `body.preview` is present in `bare_html`
and the assertion can never pass as written. Because the marker is `strict=False`, this test
will report green forever — even if a real regression made the broadcast `<body>` carry
`class="preview"`. The invariant it was meant to guard ("the broadcast page is NOT in preview
mode") is now unprotected.

Runtime behavior is actually correct (`<body class="">` on the broadcast page,
`<body class="preview">` only on `preview=1`), so this is a test defect, not a product defect —
but it leaves a hole in the regression net for exactly the "drift is structurally impossible"
guarantee this phase exists to provide.

**Fix:** Tighten the assertion to check the rendered `<body>` tag (the runtime state), not a CSS
substring, and drop the stale `xfail` marker now that the feature has shipped:

```python
def test_preview_flag_threads_body_class() -> None:
    preview_html, _ = _serve_preview()
    bare_html, _ = _serve(_CFG)
    import re
    assert re.search(r'<body class="preview"', preview_html)
    # The broadcast page body must NOT be in preview mode (CSS rule text is allowed to exist).
    assert re.search(r'<body class="">', bare_html)
```

### WR-02: preview `opacity: 1 !important` overrides `.is-stale` opacity — contradicts the design comment

**File:** `src/segugio/ui/templates/overlay.html:216` (interacting with `:201`)
**Issue:** The preview force-visible rule is:

```css
body.preview #lower-third { opacity: 1 !important; }
```

and the degrade rule is:

```css
.lower-third.is-stale { opacity: 0.55; filter: grayscale(0.4); }   /* no !important */
```

Because `!important` beats any non-`!important` declaration regardless of specificity, when the
renderer applies `is-stale` **inside the console preview iframe** (it polls `/overlay-json`
same-origin and can legitimately go stale on a poll failure), the opacity dim to `0.55` is
suppressed — only `grayscale(0.4)` survives. The inline comment at line 219 explicitly claims
"`.is-stale` degrade logic is untouched (D-04)", but the opacity half of that degrade IS
overridden under preview. Result: a stale overlay in the console preview reads as more "live"
(full opacity) than it would on-air, partially defeating the "looks exactly like what airs"
goal of the unification.

**Fix:** Scope the force-visible override away from the stale state, e.g.:

```css
body.preview #lower-third:not(.is-stale) { opacity: 1 !important; }
```

so `.is-stale` can still dim the plate to `0.55` in preview, matching the broadcast render. (Or
correct the comment to acknowledge the opacity override if the current behavior is intended.)

### WR-03: Six shipped-feature tests left as `xfail(strict=False)` now silently XPASS — convert to plain asserts

**File:** `tests/test_ui_scv_unification.py:62,78,95,113`; `tests/test_ui_overlay_page.py:190,213,227`
**Issue:** `test_console_embeds_overlay_iframe`, `test_mirror_symbols_gone`,
`test_surviving_console_wiring_intact`, `test_score_preview_route_removed`,
`test_preview_shares_dom_and_script`, `test_preview_force_visible_rule_present`, and
`test_preview_no_store` are all `xfail(strict=False)` but now XPASS because the implementation
landed. With `strict=False`, an XPASS is reported as a pass and never fails the suite — but the
tests no longer assert anything enforceably: if the feature regressed (mirror reintroduced,
iframe removed, route resurrected), each test would simply flip back to `xfail` and still report
"passing". These are the structural-contract tests this phase relies on; leaving them as `xfail`
discards the protection they were written to provide.

**Fix:** Now that 12-02/12-03 have shipped, remove the `@pytest.mark.xfail(...)` decorators so
these become hard assertions (matching the Wave-0 "flip to PASS once the work ships" intent
stated in each test's own docstring).

## Info

### IN-01: Broadcast page renders an empty `class=""` attribute

**File:** `src/segugio/ui/templates/overlay.html:224`
**Issue:** `<body class="{{ 'preview' if preview else '' }}">` emits `<body class="">` on the
broadcast page — a harmless but untidy empty attribute on the CEF browser-source page.
**Fix:** Optional cosmetic cleanup, e.g. `<body{{ ' class="preview"' | safe if preview else '' }}>`
to omit the attribute entirely when not in preview. Low priority.

### IN-02: Preview-label `<label>` lost its `for` target without a wrapped control

**File:** `src/segugio/ui/templates/console.html:275`
**Issue:** The old preview label was `<label for="overlay-preview">`; the rewrite drops the
`for` (correct, since `#overlay-preview` is deleted) but leaves a bare `<label>` that labels no
form control:
`<label>Anteprima overlay — come va in onda<span class="on-air-tag">...</span></label>`.
A `<label>` with no associated control is semantically inert (minor a11y smell). The adjacent
`.on-air-tag` is decorative-only.
**Fix:** Demote to a non-label element (e.g. `<div class="field-label">` or a heading) since it
no longer labels an input. Cosmetic / accessibility nicety only.

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
