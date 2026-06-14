# Phase 11: Shared Graphical Renderer, /overlay Page & Branding - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 11-shared-graphical-renderer-overlay-page-branding
**Areas discussed:** Lower-third look, Timer presentation, Agility overtime, Branding & identity

---

## Lower-third look

### Q1 — Overall shape of the lower-third

| Option | Description | Selected |
|--------|-------------|----------|
| Left accent-bar plate | Colored vertical accent + compact dark plate, bottom-left, label row over value row, ~18% frame height, theme color in the accent bar | ✓ |
| Centered bottom band | Wider semi-opaque band centered along the bottom, values inline | |
| Minimal chip cluster | Small rounded chips floating bottom-left, no plate (rounded corners risk CEF gray-edge artifact) | |

**User's choice:** Left accent-bar plate.

### Q2 — Timer placement / prominence in the plate

| Option | Description | Selected |
|--------|-------------|----------|
| Timer leads, big | Large clock right after the accent bar, score cells to its right; agility Tempo IS the big timer | ✓ |
| Timer as last cell | Timer is just another field cell at the right, same size as score values | |
| You decide | Claude leans timer-prominent | |

**User's choice:** Timer leads, big.
**Notes:** Time is the through-line across all three disciplines (T&F race, freestyle routine, agility Tempo), so the clock is the hero.

---

## Timer presentation

### Q1 — Number format per discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Discipline-appropriate | T&F/freestyle `M:SS` (0:47); agility `SS.hh` hundredths for Tempo + SCT (34.57 vs 38.00) | ✓ |
| Uniform M:SS | Every discipline `M:SS` (agility loses 1/100s precision) | |
| You decide | Claude leans discipline-appropriate | |

**User's choice:** Discipline-appropriate.
**Notes:** Agility is officially timed to 1/100s; the disciplines read the way their judges/handlers expect.

### Q2 — Time's-up emphasis at 0 (countdown disciplines)

| Option | Description | Selected |
|--------|-------------|----------|
| Single pulse → 'Tempo' | One brief pulse at 0:00 (same vocabulary as score-change pulse), then rests showing 'Tempo' | ✓ |
| Static freeze | No animation — swaps to 'Tempo' and holds | |
| You decide | Claude leans single-pulse-then-Tempo | |

**User's choice:** Single pulse → 'Tempo'.
**Notes:** End-of-time is a genuine event; one pulse stays within OVL-04's events-only constraint.

---

## Agility overtime

### Q1 — How crossing SCT reads (display-only, SCR-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Plain keep-counting | Tempo increments past SCT in the same style, SCT a static reference beside it, no color | ✓ |
| Subtle over-time color | Tempo number shifts to amber once past SCT (starts interpreting — what OVL-FUT-01 deferred) | |
| You decide | Claude leans plain keep-counting | |

**User's choice:** Plain keep-counting.
**Notes:** Cleanest SCR-04 stance — the two numbers speak for themselves. The colored under/over bar stays deferred to OVL-FUT-01.

---

## Branding & identity

### Q1 — Default theme look

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse console palette | Dark plate #14161a + console green #34D399 accent; one coherent product identity; CSS-var overridable | ✓ |
| Neutral broadcast default | Near-black plate + white text + sober blue accent; brandable blank template | |
| You decide | Claude leans console-palette reuse | |

**User's choice:** Reuse console palette.
**Notes:** Console preview (Phase 12 iframe) and OBS overlay then look identical out of the box.

### Q2 — Logo placement

| Option | Description | Selected |
|--------|-------------|----------|
| Bottom-right corner bug | Small persistent logo in the bottom-right title-safe corner, separate from the plate (classic channel bug) | ✓ |
| On the plate, leading edge | Logo tucked into the plate's left edge, one bottom-left cluster | |
| You decide | Claude leans bottom-right corner bug | |

**User's choice:** Bottom-right corner bug.
**Notes:** Keeps the bottom-left plate clean next to the big timer.

### Q3 — Identity line content + source

| Option | Description | Selected |
|--------|-------------|----------|
| Competitor + event | Competitor from verbatim `nome` field (optional for T&F/agility, no model change), event from config `overlay.event_name`; hides name gracefully | ✓ |
| Event name only | Just the configured event name, always on; drops the dog/handler half for non-freestyle | |
| You decide | Claude leans competitor + event | |

**User's choice:** Competitor + event.
**Notes:** Sourced with zero data-model change — `nome` flows through the free `ScoreDoc.fields` dict; event is a new static config field.

---

## Claude's Discretion

- Exact plate dimensions, scrim/plate opacity, font sizes, accent-bar width, padding (within title-safe + legible-over-bright-grass + sober).
- Enter/exit animation direction & duration; exact pulse style (compositor-only `transform`/`opacity`).
- Font choice: self-hosted `.woff2` (FOUC reveal gate) vs system font stack — no CDN; must match Phase 12's console-preview iframe.
- CSS-variable naming; flat vars vs a theme block.
- `overlay-render.js` DOM/poll structure (gen-gated re-render; cold-start guard `lastGen < 0`).

## Deferred Ideas

- Agility under/over-SCT color bar — OVL-FUT-01 (explicitly not taken for v1).
- SCV-01 unification / console preview iframe of `/overlay` — Phase 12 (SCV-02).
- OBS scene-collection wiring + browser-source settings + setup docs — Phase 13 (SCN-01/02).
- End-to-end degrade / poll-storm / HTML-injection acceptance under failure — Phase 14 (RBT-06).
