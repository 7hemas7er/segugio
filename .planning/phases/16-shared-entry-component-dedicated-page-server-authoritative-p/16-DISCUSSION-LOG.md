# Phase 16: Shared Entry Component, Dedicated Page & Server-Authoritative POST - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 16-shared-entry-component-dedicated-page-server-authoritative-post
**Areas discussed:** Disc T&F entry shape, Live advisory feedback UX, Publish result feedback, Discipline selection on page

---

## Disc T&F entry shape (Phase 16/17 boundary)

| Option | Description | Selected |
|--------|-------------|----------|
| Throw list now, persistence in 17 | Repeatable throw row (zone + midair + corridor); component computes best-5-of-N live via `score_calc` `throws[]`/`count_best_n`; submit all at once. Only reload-safe localStorage progressive state deferred to 17. | ✓ |
| Single-throw now, all multi to 17 | Phase 16 enters one throw → single score; entire multi-throw experience (entry AND state) lands in Phase 17. | |

**User's choice:** Throw list now, persistence in 17 (→ D-01 / D-01a)
**Notes:** Makes disc T&F genuinely usable after Phase 16; reuses Phase-15 `compute()` `throws[]`+`count_best_n` API. Planner must NOT build localStorage persistence here, and must NOT defer throw entry to 17. SCC-05 (progressive/reload-safe state) stays mapped to Phase 17.

---

## Live advisory feedback UX

| Option | Description | Selected |
|--------|-------------|----------|
| Live total, errors on blur, submit always on | Total recalcs live; per-field errors on blur; submit stays enabled (server is the authority). | ✓ |
| Live total, errors on blur, submit gated | Same, but submit disabled while any advisory error exists. | |
| Errors only on submit-attempt | Live total; errors surface only on submit. | |

**User's choice:** Live total, errors on blur, submit always on (→ D-02 / D-03 / D-04)
**Notes:** Least friction for a live operator; the server 400s if truly invalid so client never hard-blocks. Phase 17 adds the explicit danger-styled publish on top — do not add a gated/disabled state in 16.

---

## Publish result feedback (success + server-400)

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent inline banner | 2xx → "✓ In onda"; 400 → server per-field errors mapped to fields + explicit "punteggio precedente invariato". Stays until next action. | ✓ |
| Transient toast | Brief auto-dismissing toast; lighter but missable on a busy field. | |
| Inline errors only, quiet success | 400 errors inline; success silent. | |

**User's choice:** Persistent inline banner (→ D-05 / D-05a)
**Notes:** "Previous on-air score untouched on reject" is a broadcast-integrity guarantee, not a nicety. Server is the source of displayed errors on a 400; client advisory is a pre-filter only.

---

## Discipline selection on /score-entry

| Option | Description | Selected |
|--------|-------------|----------|
| Disciplines valid for configured sport | disc-dog → Toss&Fetch + Freestyle (one `DiscDogProfile.scoring`); agility → Agility only (`AgilityProfile.scoring`). Active profile always matches discipline. | ✓ |
| Free 3-way selector always | Always show all three regardless of config; needs an agility+disc coexistence/fallback profile story. | |
| Lock to one configured discipline | No selector; render exactly the single active discipline. | |

**User's choice:** Disciplines valid for configured sport (→ D-06)
**Notes:** Profile-consistent and matches the config discriminated-union (a config is EITHER disc-dog OR agility); no fallback-profile ambiguity. Profile + valid-discipline list injected via the `create_app`/`cam_ids` plain-arg precedent (D-07).

## Claude's Discretion

- D-07: profile + discipline-options reach the client via server injection (mirrors `create_app(cam_ids, overlay_cfg)`); exact transport (inlined JSON vs small GET) is a planning detail, kept crash-isolation-safe.
- D-08: `POST /score` accepts RAW structured inputs (throws[]/categories+adjustment/agility fields), validate→400-write-nothing→recompute→atomic write; retires the current manual-`totale` display-only path.
- D-09: `score-calc.js` is a byte-exact advisory port with the node-vs-Python drift-guard; never a second authority (Pitfall 2).
- D-10: reuse existing console CSS/markup for the dedicated-page baseline; full tablet-first hardening is Phase 17 (`/gsd-ui-phase 16` may refine).

## Deferred Ideas

- Reload-safe/progressive multi-throw STATE (localStorage restore, atomic in-progress persistence) — Phase 17 (SCC-05).
- Console `<dialog>` modal mount + single Jinja form partial — Phase 17 (SCE-04).
- Explicit danger-styled publish + full tablet contract (≥16px, focus-trap, offline assets) — Phase 17 (SCE-04).
- Rich additive `fields` subkeys through `/overlay-json` + overlay-continuity regression — Phase 18.
- Multi-judge combiners beyond `sum`, per-category overlay breakdown, more federation profiles, roster/standings — post-v1.3.
