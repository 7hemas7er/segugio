# Phase 9: Explainability, Informed Override & Tablet UX - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

La console diventa una vera **regia**: l'operatore non solo vede le camere ma capisce *perché* l'auto-director ha scelto la live, e può fare override da ciò che vede. La fase è **puro publish-and-render + UX tablet + igiene robustezza** — NON apre nuovo backend.

Il contratto dati è già completo e bloccato da Phase 7 (`PreviewDoc`, "Carries the FULL D-07 payload so Phases 8/9 are pure render — this contract is not reopened later"). In scope (dal ROADMAP, requisiti MVW-04/05, WHY-01..04, SCV-01, UXT-01/03):
- **WHY-01** reason corrente in italiano chiaro (da `status.reason`)
- **WHY-02** barre score di framing per-camera (leaderboard live, stato track/coast/lost)
- **WHY-03** overlay bbox dog-lock sulla tile live (CSS/SVG dal `box` del sidecar, niente image-processing in Flask)
- **WHY-04** hint "auto vuole vs in onda" (da `auto_candidate`)
- **MVW-04** override informato: ogni tile cliccabile = forza quella camera; "Rilascia (auto)" controllo distinto
- **MVW-05** striscia cronologia switch (dal ring `cuts` in `preview.json`)
- **SCV-01** preview live del punteggio come apparirà sull'overlay OBS (riusa `render_overlay_text`, no round-trip all'orchestrator)
- **UXT-01** restyling responsive tablet-first (griglia reflow, touch target grandi, form punteggi una-mano)
- **UXT-03** igiene: no memory leak su multiview prolungata, resume su sleep/wake, freshness stamp (mai mostrare frame congelato come "live"); la preview degrada per prima, il director mai

**Fuori scope (appartiene ad altre fasi / non a v1.1):** qualsiasi nuovo dato non già in `preview.json`/`status.json`; image-processing lato Flask; modifiche all'orchestratore o al canale di pubblicazione (Phase 7, bloccato); rottura della crash-isolation della console (importa solo Flask + `segugio.opcomm` [+ `segugio.ui.score_render`, leggero]).
</domain>

<decisions>
## Implementation Decisions

### Layout della regia (UXT-01)
- **D-01:** Layout **"Multiview + sidebar"** (landscape). Griglia camere dominante a sinistra (riusa la CSS-grid già esistente, post-WR-01 con `cam_ids` dal server); colonna destra fissa con, dall'alto: **reason corrente** (WHY-01), **score leaderboard** (WHY-02), **hint "auto vuole"** (WHY-04), **striscia cronologia switch** (MVW-05), **form punteggi** (con preview SCV-01). Criterio: "live cam + reason sempre visibili". Scartati: program+strip stile broadcast (più rework) e a-schede (nasconde il contesto).

### Override informato (MVW-04)
- **D-02:** **Tap singolo sulla tile = forza subito** quella camera (la regia dev'essere veloce, niente dialog di conferma). I bottoni testuali "Forza" alla cieca vengono **sostituiti** dal tap diretto sulla tile.
- **D-03:** Mitigazione tocchi accidentali su touch = **undo immediato**, non conferma preventiva: "**Rilascia (auto)**" resta un controllo distinto, grande e sempre a portata. La tile forzata ha una marcatura visiva inequivocabile.
- **D-04:** Tre stati visivamente distinti sulle tile: **LIVE (auto)**, **FORZATA (override operatore)**, **"auto-vuole-questa"** (WHY-04, evidenzia la tile che l'auto-director sceglierebbe ora durante un override → l'operatore sa quando è sicuro rilasciare). Lo stile esatto dei tre stati è a discrezione (vedi sotto), ma devono essere distinguibili a colpo d'occhio.

### Densità del pannello "perché" (WHY-02/03/04, MVW-05)
- **D-05:** **Tutto sempre visibile, compatto** (è una regia: decisioni rapide, nessuna interazione per vedere lo stato). Score leaderboard di **tutte** le camere (barre piccole, colore per stato track/coast/lost) + reason + auto-wants + **bbox dog-lock sempre acceso sulla tile live** + striscia cronologia switch sempre in vista.

### Tablet target & transport (UXT-01, UXT-03)
- **D-06:** Device operatore target = **iPad / Safari, landscape** (il più comune per un regista e il più esigente → progettare per questo copre il caso peggiore).
- **D-07:** **RESEARCH OBBLIGATORIO (carry-forward v1.1):** comportamento di Safari su tab in background (throttling dei timer `setInterval`/`setTimeout` → il polling JPEG può rallentare/fermarsi) e **resume su sleep/wake** dell'iPad (riprendere una preview fresca, non ripartire da un frame stantio). Verificare anche eventuali limiti Safari sul refresh `Image()` ad alta frequenza. Il researcher deve produrre la strategia di polling/resume robusta per Safari PRIMA del piano UXT-03.

### Claude's Discretion
- **Stile bbox dog-lock (WHY-03):** box normalizzato disegnato in CSS/SVG dal `box` `[cx,cy,w,h]`; track-id/etichetta opzionali; nessun image-processing in Flask. Solo sulla tile live (estendibile alle altre se `box` presente).
- **Soglia di freshness (UXT-03):** derivare la soglia di "stantio" da `preview.fps`/avanzamento di `gen`; marcare una tile STALE (dim + badge, mai "LIVE") quando `gen` non avanza entro N intervalli. Riusa il meccanismo `gen`/`markTiles` già presente.
- **Render preview punteggio (SCV-01):** `render_overlay_text` è stdlib-only e importabile dalla console crash-isolated → scegliere in fase di piano tra render server-side a ogni tasto (round-trip a Flask, NON all'orchestrator — consentito) e replica client-side del formato in JS per feedback istantaneo. In entrambi i casi: nessun round-trip all'orchestrator, fedeltà garantita riusando/rispecchiando `render_overlay_text`.
- **Color coding leaderboard (WHY-02):** colori/etichette per track / coast / lost a discrezione (coerenti con LIVE/MORTO già in uso).
- **Numero eventi cronologia (MVW-05):** il ring `cuts` ha depth ~16; mostrarne quanti a discrezione (compatibile con lo spazio sidebar).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contratto dati (già completo — la fase è pure render su questo)
- `src/segugio/opcomm/records.py` §`PreviewDoc` — schema del payload "perché": `tick`, `gen`, `auto_candidate`, `cams[id]={score,ema,state,locked,track_id,energy,in_zone,box}`, `cuts` ring (`{tick,from,to,reason}`). È il contratto che alimenta WHY-02/03/04 + MVW-05.
- `src/segugio/opcomm/records.py` §`DirectorStatus` — `live_cam`, `reason`, `alive` (WHY-01 + LIVE/MORTO).
- `src/segugio/opcomm/channel.py` — `read_preview`/`read_status` (reader safe-default, mai raise).

### Console da estendere (crash-isolated: solo Flask + opcomm [+ score_render])
- `src/segugio/ui/app.py` — `create_app(channel_dir, cam_ids)`; route `/status`, `/preview`, `/preview/<cam>.jpg`, `/command`, `/score`, `/run`; entrypoint `__main__` (env vars, waitress/threaded). NON aggiungere import pesanti.
- `src/segugio/ui/templates/console.html` — multiview CSS-grid attuale (post-WR-01: tile/force/`CAMS` da `cam_ids` server-render), `markTiles`/`pollStatus`/`pollPreview`, refresh `Image()` flicker-free con `?t=<gen>`.
- `src/segugio/ui/score_render.py` §`render_overlay_text` — stdlib-only (no Flask/numpy) → riusabile in-console per SCV-01.

### Requisiti & scope
- `.planning/ROADMAP.md` §"Phase 9" — Goal + 5 Success Criteria.
- `.planning/REQUIREMENTS.md` — MVW-04/05, WHY-01..04, SCV-01, UXT-01/03.
- `docs/run.md` §"Phase 8 — Console multiview live" — come si avvia console+orchestratore (per testare il rendering live).
- `docs/security.md` — postura LAN-trust / `0.0.0.0` (l'override informato resta dietro lo stesso endpoint, nessuna nuova auth in v1.1).

### Carry-forward / decisioni di milestone
- `.planning/phases/07-off-tick-frame-publishing-channel/07-SUMMARY.md` — il payload "why" e il ring cuts (origine dei dati).
- `.planning/STATE.md` §Blockers/Concerns — flag research iPad/Safari (MJPEG/background-tab); ⚠️ "Re-verify BoT-SORT native ReID engages on yolo26s before depending on `locked`/`track_id` stability for the dog-lock overlay" (rilevante per WHY-03).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`PreviewDoc` (preview.json):** porta GIÀ tutti i dati di Phase 9 (score/ema/state/locked/track_id/energy/in_zone/box per camera, `auto_candidate`, ring `cuts`). Zero lavoro backend: la console legge e renderizza.
- **`render_overlay_text` (score_render.py):** funzione pura stdlib-only → SCV-01 può riusarla senza rompere la crash-isolation e senza toccare l'orchestratore.
- **console.html attuale:** CSS-grid multiview con `cam_ids` server-render (post-WR-01), polling `/status` + `/preview`, refresh `Image()` flicker-free con cache-bust `?t=<gen>`, marcatura LIVE/MORTO via `markTiles`. Tutte le feature Phase 9 si innestano su questa base.
- **route `/command`:** già gestisce force/release override (l'override informato MVW-04 cambia il *gesto* UI, non il backend).

### Established Patterns
- **Crash-isolation (HARD):** la console importa SOLO Flask + `segugio.opcomm` (+ `segugio.ui.score_render`, leggero). Nessun import di torch/cv2/numpy/cyndilib/obsws. Da preservare e ri-testare (gate Phase 7/8).
- **Pure render:** nessun image-processing in Flask (WHY-03 bbox è CSS/SVG da coord normalizzate); nessun round-trip all'orchestrator (SCV-01).
- **Freshness via `gen`:** la liveness lato console è già gated sul token `gen`; UXT-03 estende questo a uno stato STALE esplicito.

### Integration Points
- `preview.json` + `opcomm/preview/cam_*.jpg` (scritti dall'orchestratore) → letti dalla console via `read_preview` + route `/preview*`.
- `status.json` → `reason`/`live_cam`/`alive` (WHY-01, LIVE/MORTO, stati override).
- `score.json` ← form punteggi console (SCV-01 ne fa la preview prima dello scrittura).
</code_context>

<specifics>
## Specific Ideas

- Layout di riferimento approvato dall'utente (mockup sidebar): griglia camere a sinistra; colonna destra = MOTIVO → SCORE leaderboard (`①▓▓▓ .81 / ②▓▓ .40 / ③·· lost`) → "auto → CAM②" → storia switch → form punteggi.
- "Rilascia (auto)" deve essere grande e sempre visibile (è l'undo del tap-to-force).
</specifics>

<deferred>
## Deferred Ideas

None — la discussione è rimasta dentro lo scope di fase.
</deferred>

---

*Phase: 9-explainability-informed-override-tablet-ux*
*Context gathered: 2026-06-13*
