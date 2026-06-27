---
phase: 18-rich-data-model-overlay-continuity-regression
reviewed: 2026-06-27T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/segugio/ui/score_calc.py
  - src/segugio/ui/app.py
  - src/segugio/ui/static/overlay-render.js
  - src/segugio/ui/static/score-entry.js
  - tests/test_score_calc.py
  - tests/test_ui_overlay_json.py
  - tests/test_imports.py
  - tests/test_overlay_html_sink_gate.py
  - tests/test_overlay_fallback_gate.py
  - tests/test_ui_overlay_page.py
  - docs/obs-setup.md
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 18 adds (a) free-text identity keys (`cane`/`conduttore`/`giudici`) passed through the
write path on all three disciplines, (b) additive Decimal-string subkeys to `compute()`
(`throws[].score`, `criteria{}`, `faults_breakdown{}`), and (c) the overlay/form render sinks for
the identity competitor line. The diff is small (~67 production LOC) and the four phase invariants
hold under direct inspection:

- **str(Decimal) subkeys.** Every new subkey value is a string (`str(score)`, `str(snapped)`,
  `str(int(course_faults))`, `str(time_faults)`, `str(course_deductions)`). No raw `Decimal`
  reaches `json.dumps`; confirmed by the heavy-absent rich-POST round-trip in `test_imports.py`.
- **Additive-only `/overlay-json`.** The 6-key envelope is `==`-frozen and the legacy flat keys are
  subset-frozen in `test_ui_overlay_json.py`; identity + subkeys live inside `fields`, never at
  top level.
- **textContent-only identity sinks.** `renderIdentity` (overlay) builds the competitor via
  `createTextNode`; `score-entry.js` echoes via `textContent`. The grep gate + node fake-DOM
  `<script>` inertness proofs both cover the two served files. `giudici` is collected/stored but
  never rendered (no DOM sink at all).
- **Crash-isolation import surface.** No new module-top heavy import; `_parse_structured_inputs`
  whitelists keys so no arbitrary field can be injected into the compute dict.

No Critical defects found. One Warning (a latent validation gap now mirrored into the new
`faults_breakdown`) and three Info items.

## Warnings

### WR-01: count_up `course_faults` silently truncated to int — no integer validation, now mirrored into `faults_breakdown`

**File:** `src/segugio/ui/score_calc.py:359-364` (with `validate()` at `:249-260`)
**Issue:** For the `count_up` agility model, `validate()` accepts any non-negative number as
`course_faults` (it checks presence, numeric-parse, and `>= 0`, but **not** that the value is
integral). `compute()` then does `faults = int(course_faults) + time_faults`, where
`int(Decimal("5.5"))` truncates toward zero to `5`. The new subkey faithfully mirrors this:
`out["faults_breakdown"] = {"course": str(int(course_faults)), ...}`. So a valid POST of
`course_faults = "5.5"` passes validation and silently airs `faults = "5"` (and `course: "5"` in
the breakdown) with the `0.5` dropped and no error returned to the operator — a silent data-handling
discrepancy. Note the asymmetry: the `deduct_from_100` branch preserves the full Decimal
(`str(course_deductions)`), so the two models treat a fractional course value differently. The
truncation itself predates Phase 18 (the `int()` line is unchanged); 18-01 newly surfaces it inside
the additive breakdown.
**Fix:** Reject non-integral course faults in `validate()` for the `count_up` model so the operator
gets a per-field error instead of a silent truncation, e.g.:
```python
elif model == AgilityModel.count_up and value != value.to_integral_value():
    errors.append({"field": fault_field, "message": f"'{fault_field}' deve essere intero."})
```
(Alternatively, keep the Decimal verbatim in both the flat total and the breakdown so no precision
is silently discarded.)

## Info

### IN-01: free-text identity values are stored and re-emitted unbounded server-side

**File:** `src/segugio/ui/app.py:161-163`; `src/segugio/ui/score_calc.py` (passthrough via `dict(fields)`)
**Issue:** `cane`/`conduttore`/`giudici` are copied verbatim into `fields`, written to `score.json`,
and echoed on every `GET /overlay-json` (~5 fps) with no server-side length bound. On-air safety
relies entirely on render-time clamping (`cleanField` cap 64 in the overlay, `_clean` cap 64 in
`overlay.txt`). The dedicated-LAN single-operator trust boundary makes this acceptable for v1 (and
performance is out of scope), but a server-side cap would be cheap defense-in-depth against an
oversized stored value bloating the polled payload.
**Fix:** Optionally clamp identity values to a max length (e.g. 64) in `_parse_structured_inputs`
before they enter the persisted doc, mirroring the render-time cap.

### IN-02: redundant `setdefault` idiom in `_compute_freestyle`

**File:** `src/segugio/ui/score_calc.py:338-339`
**Issue:** `out.setdefault("nome", out.get("nome", ""))` — `setdefault` already returns the existing
value when the key is present and sets the default otherwise, so the inner `out.get("nome", "")`
collapses to the constant `""`. The line is equivalent to `out.setdefault("nome", "")` (same for
`timer`). Harmless but obscures intent. (Pre-existing; unchanged by Phase 18.)
**Fix:** Simplify to `out.setdefault("nome", "")` / `out.setdefault("timer", "")`.

### IN-03: combined competitor line bypasses the per-field 64-char discipline (CSS-mitigated)

**File:** `src/segugio/ui/static/overlay-render.js:150-156`
**Issue:** `renderIdentity` builds `cane + " / " + conduttore`; each half is `cleanField`-capped to
64, but the concatenation (~131 chars) is not re-capped — so the on-air competitor string can exceed
the single-field length discipline enforced elsewhere for broadcast text. Verified non-harmful:
`#identity` in `overlay.html` applies `white-space: nowrap; overflow: hidden; text-overflow:
ellipsis; max-width: 60vw`, so the line is clipped, not overflowed. Recorded for transparency given
the per-field cap is a deliberate on-air-text invariant; the combination quietly relaxes it.
**Fix:** None required (CSS clips it). If strict parity with the 64-char cap is desired, re-apply
`cleanField` to the combined string.

---

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
