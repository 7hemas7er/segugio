# Phase 12: SCV-01 Unification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 12-scv-01-unification
**Areas discussed:** Preview semantics, Panel presentation, /score/preview + parity

---

## Preview semantics

### Q1 — What should the iframe preview show?

| Option | Description | Selected |
|--------|-------------|----------|
| Published only | Iframe shows exactly /overlay-json (last submitted score + live run timer), byte-identical to OBS by construction; as-you-type text preview retired with the JS mirror. Truest unification — drift impossible. | ✓ |
| Keep as-you-type too | Re-introduce a preview-only data path so unsubmitted edits render before /score; keeps instant feedback but re-opens a second data source / partial drift. | |

**User's choice:** Published only
**Notes:** Accepts losing the instant as-you-type text preview. For a live operator, "what's on air right now" is the more useful and the only honest unification.

### Q2 — Cue so the preview reads as live/published, not a draft?

| Option | Description | Selected |
|--------|-------------|----------|
| Label "come va in onda" | Relabel the preview area (e.g. ON-AIR tag) so it's clearly the live published overlay OBS renders, not a typing draft. Cheap; kills the "why isn't my typing showing?" confusion. | ✓ |
| No cue needed | Keep the panel minimal with just "Anteprima overlay". Less chrome, small risk of momentary confusion. | |

**User's choice:** Label "come va in onda"
**Notes:** —

---

## Panel presentation

### Q1 — How should preview=1 present the transparent 1080p-sized lower-third in the small sidebar?

| Option | Description | Selected |
|--------|-------------|----------|
| Scaled 16:9 frame, neutral backdrop | Fit-to-panel 16:9 box with a neutral mid-gray/checkerboard backdrop so position, title-safe band, transparency, and scale all read as over real video. | ✓ |
| Plain plate on the dark panel | Drop the overlay onto the existing dark sidebar, no 16:9 framing. Simplest, but placement/scale/transparency don't read. | |
| Representative grass still | Real sample outdoor still as backdrop for max realism; needs a committed image asset. | |

**User's choice:** Scaled 16:9 frame, neutral backdrop
**Notes:** —

### Q2 — Idle state: hidden until run start (like OBS) or visible for pre-run score entry?

| Option | Description | Selected |
|--------|-------------|----------|
| Force plate visible in preview | preview=1 keeps the lower-third shown between runs; only the run-edge hide/show animation is suppressed; content/layout/sanitize stay byte-identical to OBS. | ✓ |
| Mirror OBS exactly | Lower-third hidden until run start; maximally faithful but no feedback while entering a score before a run. | |

**User's choice:** Force plate visible in preview
**Notes:** Scoped cosmetic fork — does not reopen content/value drift.

---

## /score/preview + parity

### Q1 — Fate of the POST /score/preview route (no caller after the mirror is deleted)?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the route + mirror | Remove POST /score/preview with the gsd:scv01-mirror block, mirrorOverlayText/updateScorePreview/driftCheck, and #drift-warning. render_overlay_text (Python) stays unchanged for overlay.txt. Cleanest — no dead endpoint. | ✓ |
| Downgrade to overlay.txt parity | Keep a thin POST /score/preview repurposed as an overlay.txt parity check; a runtime endpoint with no live UI caller. | |

**User's choice:** Delete the route + mirror
**Notes:** —

### Q2 — How deep should the parity check go?

| Option | Description | Selected |
|--------|-------------|----------|
| Structural + value cross-check | Assert the structural unification (iframe src=/overlay?preview=1, mirror gone, one renderer, crash-isolation green) AND that overlay-render.js and render_overlay_text/overlay.txt render the same sanitized field values for the same /overlay-json — no silent divergence. | ✓ |
| Structural only | Assert just the iframe src + mirror deleted + crash-isolation green; lean on the existing cleanField↔_clean byte-parity test (11-03) for value safety. | |

**User's choice:** Structural + value cross-check
**Notes:** —

---

## Claude's Discretion

- Exact iframe dimensions, 16:9 box CSS (aspect-ratio vs padding hack), the precise neutral backdrop (flat mid-gray vs checkerboard), and the scaling approach for the 1080p lower-third.
- The exact ON-AIR label copy/styling (Italian, matching console.html).
- How `preview=1` is detected/threaded (query arg → render flag / body class / JS bootstrap) — keeping the renderer's content logic untouched, the fork purely presentational.
- Whether the value cross-check extends `tests/test_ui_overlay_render.py` or lands in a new parity module.

## Deferred Ideas

- OBS scene-collection wiring + browser-source settings + `docs/obs-setup.md` → Phase 13 (SCN-01/02).
- End-to-end degrade / poll-storm vs `/command` starvation / HTML-injection acceptance under failure → Phase 14 (RBT-06, UXT-02 extension).
- Agility under/over-SCT color bar → OVL-FUT-01 (already deferred at Phase 11).
