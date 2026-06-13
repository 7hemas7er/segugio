# Phase 9: Explainability, Informed Override & Tablet UX - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 9-explainability-informed-override-tablet-ux
**Areas discussed:** Layout della regia, Override: gesto + stati, Tablet target, Densità pannello "perché"

---

## Layout della regia (tablet landscape)

| Option | Description | Selected |
|--------|-------------|----------|
| Multiview + sidebar | Griglia camere dominante a sx; colonna dx fissa con reason/score/auto-wants/storia/punteggi. Riusa la CSS-grid esistente, meno rework. | ✓ |
| Program + strip (regia TV) | Una camera LIVE grande + strip anteprime sotto + perché in fascia bassa. Più rework. | |
| A schede (Multiview/Perché/Punteggi) | Tre tab; nasconde il contesto, contro il criterio "live cam + reason sempre visibili". | |

**User's choice:** Multiview + sidebar
**Notes:** Mockup ASCII approvato (vedi `<specifics>` in CONTEXT.md). Tutto visibile insieme, riusa la griglia post-WR-01.

---

## Override: gesto + stati (MVW-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Tap singolo = forza subito | Tap sulla tile forza immediatamente; niente dialog; undo via "Rilascia (auto)" sempre grande. | ✓ |
| Tap-and-hold (~0.5s) | Tap normale inerte; press lungo per forzare. Meno immediato/scopribile. | |
| Tap → mini-conferma sulla tile | Due tocchi; più sicuro contro errori ma rallenta la regia. | |

**User's choice:** Tap singolo = forza subito
**Notes:** Mitigazione tocchi accidentali = undo immediato ("Rilascia (auto)" distinto e sempre a portata), non conferma preventiva. Tre stati tile distinti: LIVE-auto / FORZATA / auto-vuole-questa (WHY-04).

---

## Tablet target

| Option | Description | Selected |
|--------|-------------|----------|
| iPad / Safari, landscape | Device più comune + più esigente → copre il caso peggiore. Attiva research Safari (MJPEG/background-tab + sleep/wake). | ✓ |
| Android / Chrome, landscape | Meno gotcha di transport; research Safari saltabile. | |
| PC/laptop browser | Tablet-first diventa desktop-primario. | |

**User's choice:** iPad / Safari, landscape
**Notes:** Decisione che ATTIVA il research flaggato dal v1.1 (Safari background-tab timer throttling + resume sleep/wake) come prerequisito di UXT-03 — vedi D-07 in CONTEXT.md.

---

## Densità pannello "perché" (WHY-02/03/04, MVW-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Tutto sempre visibile, compatto | Score leaderboard tutte le camere + reason + auto-wants + bbox sempre acceso + storia sempre in vista. | ✓ |
| Essenziale sempre + dettagli a scomparsa | Reason+live+auto-wants sempre; score/storia espandibili on-demand. | |
| Solo on-demand | Multiview pulito; perché su tap. | |

**User's choice:** Tutto sempre visibile, compatto
**Notes:** È una regia: l'operatore decide in fretta e deve vedere tutto senza interazioni.

---

## Claude's Discretion

- Stile bbox dog-lock (CSS/SVG da `box` normalizzato; track-id opzionale; no image-processing in Flask).
- Soglia di freshness/STALE (derivata da `preview.fps`/avanzamento `gen`; riusa `markTiles`).
- Render preview punteggio SCV-01 (server-side via `render_overlay_text` vs replica client-side JS; mai round-trip all'orchestrator).
- Color coding leaderboard track/coast/lost; numero eventi cronologia mostrati (ring depth ~16).

## Deferred Ideas

None — la discussione è rimasta dentro lo scope di fase.
