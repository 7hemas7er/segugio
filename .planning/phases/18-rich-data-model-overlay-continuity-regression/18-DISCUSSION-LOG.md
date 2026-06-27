# Phase 18: Rich Data Model & Overlay-Continuity Regression - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-27
**Phase:** 18-rich-data-model-overlay-continuity-regression
**Areas discussed:** New free-text fields, Structured subkey shape, Regression gate strictness, XSS proof approach

---

## New Free-Text Fields (dog/handler name, judges)

| Option | Description | Selected |
|--------|-------------|----------|
| Map to existing identity line | Dog/handler feed the overlay's EXISTING competitor identity line; judges ride in score.json + entry form only (not on the single-score overlay). No new visible overlay element. | ✓ |
| Carry in data only | All new free-text in score.json + entry form; show none on the overlay; rendered overlay byte-unchanged. | |
| Display all on overlay | Add dog/handler AND a judges line as NEW visible overlay fields; richer broadcast but new visible capability + bigger surface. | |

**User's choice:** Map to existing identity line (Recommended)
**Notes:** Grounded by code reading — `overlay-render.js` already renders a `competitor`/`event` identity band via `createTextNode`, so a name field is not new ground. Judges are explicitly data-only for v1.3.

---

## Structured Subkey Shape & Authority

| Option | Description | Selected |
|--------|-------------|----------|
| Server-computed Decimal subkeys | compute() emits criteria{} (per-category snapped) + faults_breakdown{course,time} as Decimal strings; throws[] gains a per-throw computed score. Keystone-consistent, additive. | ✓ |
| Raw-echo only | Carry raw inputs verbatim with no new computed subkeys; smallest change, unprocessed data. | |
| You decide | Leave the exact subkey shape to research/planning. | |

**User's choice:** Server-computed Decimal subkeys (Recommended)
**Notes:** Today `compute()` does `out = dict(fields)` so disc_tf `throws[]` already survives; freestyle has flat category keys (no grouping); agility computes `time_faults` internally but exposes no breakdown. Literal key names/nesting left to Claude's discretion.

---

## Regression Gate Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Golden-snapshot + carried manual checklist | Automated golden-snapshot freezing the /overlay-json legacy key set + overlay.txt single-line regression, PLUS a documented NON-BLOCKING real-OBS rig checklist (D-02 deferral pattern). | ✓ |
| Automated-only | Automated regression tests only; no manual rig step. | |
| Automated + blocking rig UAT | Require real-OBS read-from-file verification before sign-off; blocks completion on hardware. | |

**User's choice:** Golden-snapshot + carried manual checklist (Recommended)
**Notes:** Matches the prior-phase non-blocking-UAT deferral; automated tests gate sign-off.

---

## XSS Proof Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Both guards | Extend the no-innerHTML served-JS grep to new templates/fields AND add a DOM-level crafted-<script> render assertion on BOTH overlay and form preview; confirm Jinja autoescape. | ✓ |
| DOM render test only | Crafted-<script> assertion on both sinks; skip the static grep. | |
| Grep guard only | Extend the no-innerHTML grep; no runtime render assertion. | |

**User's choice:** Both guards (Recommended)
**Notes:** Sink is already uniformly `textContent`/`createTextNode`; a served-JS test already forbids `innerHTML`. Work is proving inertness for the new fields, building on `test_overlay_html_sink_gate.py`. Matches success criterion #4 (inert on both overlay and form preview).

---

## Claude's Discretion

- Exact JSON key names / nesting for `criteria{}` and `faults_breakdown{}`, and the per-throw score field name (the shape *intent* is fixed; the literal key strings are not).
- Display formatting of the combined dog/handler identity string in the renderer.

## Deferred Ideas

- **Judges on the overlay** — considered, deferred (new visible capability; v1.3 stays single-score, uncluttered). Revisit with SCM-F1 (multi-judge freestyle).
- **Blocking real-OBS rig UAT** — considered, rejected to preserve the non-blocking-UAT pattern; rig checklist carried forward as non-blocking.
