# Phase 14: Fallback Coexistence & Degrade Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 14-fallback-coexistence-degrade-hardening
**Areas discussed:** Acceptance medium, Dead-console look, Fallback switchover, Gap remediation

---

## Acceptance medium

| Option | Description | Selected |
|--------|-------------|----------|
| Both | Headless automation for everything simulable + an on-rig HUMAN-UAT.md checklist for the physical OBS/LAN scenarios | ✓ |
| Headless only | Simulate every scenario in the test harness; no on-rig doc | |
| On-rig only | A manual checklist on the real rig is the gate; minimal automation | |

**User's choice:** Both.
**Notes:** Matches the project's established pattern (software-complete tests + deferred hardware UAT).

| Option | Description | Selected |
|--------|-------------|----------|
| Carry forward | Headless gate is the completion bar; on-rig is a deferred hardware/field UAT (Phases 5/7 disposition) | ✓ |
| Block on on-rig | Phase not complete until the on-rig checklist is actually run on real OBS | |

**User's choice:** Carry forward.

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit gate tests | Dedicated failure-scenario regression tests per success criterion, even where logic already exists | ✓ |
| Gaps only | Only write the genuinely-missing tests; rely on existing freshness/render tests for timer/degrade | |

**User's choice:** Explicit gate tests.
**Notes:** SC#1/#2 logic already shipped + bug-fixed in quick-tasks (260615-tsi response-recency watchdog; 260615-sod per-request nonce); the user still wants RBT-06 as a self-contained named gate.

---

## Dead-console look

| Option | Description | Selected |
|--------|-------------|----------|
| Two-stage | Short stale (~600ms) → keep dim+grayscale (no hiccup flicker); longer dead threshold (~few s) → fully exit/hide so no frozen score airs | ✓ |
| Keep current dim | Leave `.is-stale` = opacity 0.55 + grayscale; frozen score stays readable, stopped timer is the only not-live cue | |
| Hide on any stale | Any stale (even 600ms) hides the lower-third; flickers on transient hiccups | |

**User's choice:** Two-stage.
**Notes:** Genuine degrade-hardening (the phase namesake). Strengthens OVD-03's "a frozen run is never shown as live."

| Option | Description | Selected |
|--------|-------------|----------|
| JS constant ~3s | Add `DEAD_MS ≈ 3000ms` next to `STALE_MS` — mirrors existing freshness constants; no config surface | ✓ |
| Config knob, default 3s | Add `overlay.dead_hide_after_s` to OverlayParams (org-tunable) + entrypoint plumbing | |
| You decide | Let research/planning pick value + location | |

**User's choice:** JS constant ~3s.

---

## Fallback switchover

| Option | Description | Selected |
|--------|-------------|----------|
| Simplified manual reveal | Operator reveals Score Text when the graphic drops; Score Text stays hidden while console is alive; drop Phase-13's now-redundant "hide Score Overlay" step (auto-hide handles it) | ✓ |
| Add an OBS hotkey | Same reveal + a documented/pre-wired source-visibility hotkey for one-keypress switchover | |
| Keep Phase-13 two-action | Leave the reveal-text + hide-overlay procedure (now redundant given auto-hide) | |

**User's choice:** Simplified manual reveal.
**Notes:** Auto-reveal of the text source is architecturally impossible — a dead/crash-isolated console can't drive OBS via obs-websocket. The two-stage auto-hide (D-04) reduced the operator's job to a single reveal action.

---

## Gap remediation

| Option | Description | Selected |
|--------|-------------|----------|
| Fix inline, domain-bounded | Overlay-robustness gaps fixed in this phase; out-of-domain gaps documented + deferred | ✓ |
| Gate-and-document only | Phase 14 only proves + reports; every gap becomes a follow-up | |
| Fix inline, no boundary | Fix whatever surfaces regardless of domain | |

**User's choice:** Fix inline, domain-bounded.

| Option | Description | Selected |
|--------|-------------|----------|
| Fold in as small docs/config fix | The Phase-13-flagged NDI-source-name drift is fixed here (explicitly flagged for Phase 14; operator-facing consistency) | ✓ |
| Defer to a quick-task | Out of the RBT-06 domain (NDI source naming); handle separately | |

**User's choice:** Fold in as small docs/config fix.

---

## Claude's Discretion

- Exact `DEAD_MS` tuning around ~3s.
- Exact new test file names and structure.
- How the `/overlay-json` poll-storm test mirrors UXT-02's `< 1.0s` `/command` threshold.

## Deferred Ideas

- On-rig HUMAN-UAT execution on real OBS hardware (carry-forward; authored in Phase 14, run on the rig later).
- OBS source-visibility hotkey for Score Text (considered, not adopted).
- OVL-FUT-01 visual agility-vs-SCT under/over-time treatment (already deferred in REQUIREMENTS.md).
- Any out-of-overlay-domain gap surfaced during validation (documented, fixed in its own phase/quick-task).
