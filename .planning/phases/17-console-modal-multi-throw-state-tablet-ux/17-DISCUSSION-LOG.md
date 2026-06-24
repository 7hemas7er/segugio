# Phase 17: Console Modal, Multi-throw State & Tablet UX - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 17-console-modal-multi-throw-state-tablet-ux
**Areas discussed:** Rounds model, Reload-safe state scope, Restore UX, Clear draft, Deliberate publish UX, Enter-key behavior, Console surface

---

## Rounds model (SCC-05 data-model anchor)

| Option | Description | Selected |
|--------|-------------|----------|
| One flat set of throws | Single 60s round, best-5-of-N, progressive total — exactly what score_calc does today; no score_calc change | ✓ |
| Multiple rounds, combined | Throws grouped into rounds that combine; needs a round-grouping model AND a Phase-15 score_calc change | |
| Let me explain the format | User describes the real scoring format | |

**User's choice:** One flat set of throws
**Notes:** Confirms `score_calc` (Phase 15) stays unchanged; "across N rounds" is loose wording. Phase 17 only adds reload-safe persistence on top of the existing in-session throw list. Keeps blast radius minimal.

---

## Reload-safe state scope (SCC-05)

| Option | Description | Selected |
|--------|-------------|----------|
| localStorage only | Client-side, offline-native, zero server/crash-isolation risk; cache-clear/device-swap loses draft | ✓ |
| Server draft file too | Also persist score_draft.json (atomic + never-raise reader); survives cache-clear/device-swap; new route + import-allowlist cost | |
| You decide | Claude picks the best fit | |

**User's choice:** localStorage only
**Notes:** Fits a single-operator offline-rig tablet. "Atomic write + never-raise reader" reinterpreted client-side (atomic setItem; try/caught reader → empty draft).

---

## Restore UX (SCC-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Silent auto-restore | Throw list reappears as left, no prompt | ✓ |
| Restore + dismissible note | Auto-restore plus a small 'ripristinato' banner | |
| Prompt to restore | Ask before filling | |

**User's choice:** Silent auto-restore
**Notes:** Matches "no lost throws" and the calm-flow goal; zero clicks.

---

## Clear draft (SCC-05)

| Option | Description | Selected |
|--------|-------------|----------|
| On successful publish (2xx) | Wiped only when score airs; 400/network keeps draft | ✓ |
| Publish OR explicit reset | Also a 'svuota/nuovo' button | |
| Per discipline+run | Draft keyed by discipline/run | |

**User's choice:** On successful publish (2xx)
**Notes:** 400/network error keeps the draft (nothing lost). Explicit reset + per-discipline keying parked as deferred ideas.

---

## Deliberate publish UX (SCE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Two-step confirm | First tap morphs button to danger-styled 'Conferma invio' (with escape/auto-revert); second tap POSTs | ✓ |
| Hold-to-publish | Press-and-hold ~1s; harder for keyboard/a11y | |
| Arm toggle | Separate 'arma invio' switch before publish works | |

**User's choice:** Two-step confirm
**Notes:** Layers on top of the Phase-16 always-enabled button; works for touch + keyboard; accessible.

---

## Enter-key behavior (SCE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Enter never publishes | Enter never submits/arms-and-fires; only the two-tap button airs | ✓ |
| Enter = first step only | Enter arms the confirm but can't complete it | |
| You decide | Claude picks the safest mapping | |

**User's choice:** Enter never publishes
**Notes:** Literal reading of "Enter cannot put a score on air"; only path to air is two deliberate taps.

---

## Console surface (SCE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Readout + edit button | Compact read-only current-on-air score line + 'Inserisci/modifica' button opening the modal | ✓ |
| Button only | Just a button opening the modal; no in-card readout | |
| You decide | Claude picks the cleaner layout fit | |

**User's choice:** Readout + edit button
**Notes:** Console has no existing score readout today, so it's net-new; cleanest source is a poll of `/overlay-json` (discipline + total + gen). Operator always sees what's airing; edits in the popup.

---

## Claude's Discretion

- One shared Jinja form partial `{% include %}`'d by both hosts (D-08).
- Mount-on-dialog-open lifecycle for the modal; auto-mount stays on the dedicated page (D-09).
- Tablet contract verify-not-rebuild: ≥16px inputs + inline-SVG/no-CDN already met; native
  `dialog.showModal()` focus-trap; sleep/wake survival rides on localStorage restore (D-10).
- Full retirement of the legacy `#form-score` + the `_is_legacy_score_post` back-compat branch (D-11).
- Readout poll cadence/markup and `/overlay-json` alignment with the existing console poll loop (D-07a).

## Deferred Ideas

- Explicit "svuota / nuovo punteggio" reset button + per-discipline/per-run draft keying (clear-draft options not chosen).
- Server-side in-progress draft file (`score_draft.json`) — rejected for a single offline tablet; revisit only for cross-device continuity.
- Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression — Phase 18 (RBT-09).
- Multi-judge combiners, per-category overlay breakdown, roster/standings, CV auto-scoring — post-v1.3.
