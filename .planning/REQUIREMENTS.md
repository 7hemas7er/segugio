# Requirements: Segugio — v1.2 Overlay Grafico Broadcast

**Defined:** 2026-06-14
**Core Value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.

> **Milestone v1.2 = overlay grafico broadcast.** Sostituire la sovrapposizione punteggi testo-su-file con un overlay grafico animato renderizzato via OBS *browser-source* alimentata dalla console crash-isolated, più un scene-collection OBS curato. **Vincolo HARD invariato**: la console resta crash-isolata (importa SOLO `Flask + segugio.opcomm`, mai l'orchestrator/director); è *publish-and-render* sopra il canale `opcomm` esistente (i dati `ScoreDoc`/`RunState` ci sono già), non compute. Il director non viene mai toccato. Vedi `.planning/research/v1.2/SUMMARY.md`. La numerazione delle fasi continua dalla v1.1 (parte da Phase 10).

## v1.2 Requirements

### Overlay Rendering (OVL)

- [ ] **OVL-01**: La console crash-isolated serve un overlay **browser-source trasparente** via due route — `GET /overlay` (pagina HTML/CSS/JS) + `GET /overlay-json` (dati) — importando solo `Flask + segugio.opcomm` (nessuna nuova dipendenza runtime)
- [ ] **OVL-02**: L'overlay rende un **lower-third per disciplina** (disc T&F: prese/zona/totale · freestyle: nome+timer · agility: tempo/SCT/faults) riusando la mappatura campi/disciplina esistente; valori mostrati **verbatim** (SCR-04), sanitizzati + length-bounded
- [ ] **OVL-03**: **Compositing leggibile** su video live — plate semi-opaco, contrasto, banda **title-safe** in basso (mai sopra l'area d'azione del campo), `<body>` trasparente per il compositing OBS
- [ ] **OVL-04**: **Animazioni sobrie** — enter/exit legato a run start/stop + un *pulse* breve sul cambio di un valore punteggio (niente over-animation, niente movimento costante)

### Run Timer (TMR)

- [ ] **TMR-01**: **Timer di run auto-contante** client-side (zero compute sul director), che ticchetta solo mentre la run è in corso (`running`)
- [ ] **TMR-02**: **Direzione per disciplina** — T&F conta alla rovescia da 60s, freestyle alla rovescia da una **durata configurabile** (90/120s, org-dependent), agility conta in su mostrato contro l'`SCT` digitato dall'operatore
- [ ] **TMR-03**: **Comportamento a fine tempo** — per T&F/freestyle il timer si **ferma a 0 e mostra "Tempo"**; agility prosegue oltre l'SCT (overtime), non si ferma all'SCT
- [ ] **TMR-04**: **Timer robusto allo skew di clock** tra macchine (console e OBS possono essere su host diversi) — `server_now` pubblicato ancora un offset client una-tantum; **mai** una sottrazione naive col clock locale del browser

### Overlay Data Channel (OVD)

- [x] **OVD-01**: `GET /overlay-json` assembla il payload (`discipline`, `fields` verbatim, `running`, `started_at`, `server_now`, `gen`) in modo **boundary-safe** (sorgente assente/malformata → default, non solleva mai nel server)
- [x] **OVD-02**: Un **NUOVO record overlay-run di proprietà della console** (es. `overlay_run.json`) stampa `run_started_at` + `running` sull'edge run start/stop; il `runstate.json` letto dal director ogni tick **non viene mai toccato** (director invariato)
- [ ] **OVD-03**: **Freschezza** — una sorgente dati stale/disconnessa è rilevata (gen-age) e l'overlay **degrada** (il timer si ferma, una run congelata non è MAI mostrata "live"), riusando il pattern `gen`/nonce/`no-store` di v1.1

### Score Preview Unification (SCV)

- [ ] **SCV-02**: La **preview punteggio della console riusa lo stesso renderer `/overlay`** (iframe), ritirando il mirror JS byte-exact di Python + il drift-guard `POST /score/preview` — il drift console↔OBS diventa strutturalmente impossibile

### Branding & Identity (BRD)

- [ ] **BRD-01**: **Logo + tema colori configurabili** (CSS variables + path logo da config); il logo sta nell'angolo/plate, mai sopra l'azione
- [ ] **BRD-02**: **Riga identità persistente** (nome cane/handler + nome evento) — freestyle usa `nome`; T&F/agility la prendono da config o da un campo opzionale (nessun cambio al modello dati)

### OBS Scene Collection & Setup (SCN)

- [ ] **SCN-01**: Un nuovo `obs/segugio-scene-collection.json` cabla la **browser-source** (URL http della console) in ogni scena CAM/SAFE, con **"shutdown when not visible"/"refresh on activate" OFF** (niente re-flash dell'overlay a ogni cut); la text source `overlay.txt` resta cablata come fallback
- [ ] **SCN-02**: `docs/obs-setup.md` aggiornato per l'overlay browser-source (URL, trasparenza, impostazioni sorgente, nota deploy console/OBS su macchine diverse)

### Robustness (RBT)

- [ ] **RBT-06**: `overlay.txt` **mantenuto come fallback degradato** (SCR-01) — browser-source primaria, text source "read from file" come fallback sempre-funziona se la browser-source muore/blanka on-air
- [x] **RBT-07**: **Crash-isolation della console preservata** — test di import verde con lo stack pesante assente (`torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws`); gate per ogni fase

## Future Requirements

Deferred to a future release. Tracked but not in the v1.2 roadmap.

### Overlay (v1.2.x / v2)

- **OVL-FUT-01**: **Visual agility vs SCT** (colore/barra under/over-time mentre il tempo sale) — rimandato; va inquadrato con cura per restare display-only (SCR-04, mostra il confronto, non emette un verdetto Q/NQ); la riga piatta Tempo/SCT/Faults è sufficiente prima

### Predictive & Domain Intelligence (v2 — invariati da v1)

- **PRED-01**: Predictive framing avanzato basato su velocità/traiettoria (anticipazione)
- **PRED-02**: Detection del disco/frisbee come predittore del punto di presa (disc dog)
- **PRED-03**: Framing obstacle-aware / anticipazione del prossimo ostacolo (agility, course-order noto)
- **PRED-04**: Replay markers / segnalazione momenti salienti

### Hardware / Field (milestone successiva)

- Validazione su campo con telefoni reali, NDI HX3, WiFi 6 dedicata; carry-forward hardware/field elencati in STATE.md → Deferred Items

## Out of Scope

Esplicitamente esclusi da v1.2. Documentati per prevenire scope creep.

| Feature | Reason |
|---------|--------|
| **Scoring / adjudication automatica** (CV conta prese, somma totali, deriva faults, decide Q/NQ o under/over SCT) | Viola SCR-04, la linea più dura del progetto: il giudice è autoritativo, un overlay in disaccordo è peggio di nessun overlay. L'overlay mostra i valori digitati **verbatim**, sempre |
| **Over-animation** (movimento costante, particelle, shimmer in loop, transizioni drammatiche a ogni tick, loghi che ruotano) | Distrae dal cane (core value); legge come amatoriale; costa CPU/GPU OBS sulla stessa macchina. Solo fade/slide sobrio + un pulse breve sul cambio valore |
| **Overlay che copre l'area d'azione** (banner full-width, scorebar top-center, grafica al centro, lower-third che sale oltre ~20% del frame) | Il cane è piccolo, veloce, ovunque sul campo; un overlay alto/centrato nasconde il soggetto che il sistema lavora per inquadrare. Solo banda title-safe in basso |
| **Qualsiasi compute sul director** (push del timer ogni frame dall'orchestrator, render dell'overlay nel processo director, composizione server-side per-frame, fan-out WebSocket dal director) | Rompe la crash-isolation e ruba al budget loop AI <300ms — gli stessi errori che il design preview di v1.1 ha respinto. Timer auto-contante client-side da un `run_started_at` + `running`; la console (solo Flask + opcomm) serve la pagina; zero lavoro per-frame del director |
| **Clock frame-accurate / NTP-synced** | È un auto-director hobby/club, non una regia TV; inseguire il sync sub-frame aggiunge enorme complessità per un valore impercettibile. L'offset una-tantum via `server_now` è accurato entro la percezione umana |
| **Rimozione del fallback `overlay.txt`** | Perde il path degradato robusto (SCR-01); se la browser-source crasha/blanka on-air non resta alcun punteggio. `overlay.txt` continua a essere scritto e resta sorgente di fallback in OBS |
| **Contenuto HTML libero autorato dall'operatore** (testo arbitrario lungo, immagini per run, annunci) | Superficie di injection, layout illimitato che rompe il lower-third, scope creep oltre i punteggi. Schema campi fisso per disciplina + sanitize/length-bound |
| **Leaderboard / classifica multi-competitor sull'overlay live** | Ingombra il lower-third live, compete con l'azione; le classifiche sono una preoccupazione da pagina-risultati, non da run live. L'overlay live mostra solo la run corrente |
| **Trasporto WebSocket / MJPEG / SSE per l'overlay** | Una connessione long-lived appende un worker thread Flask, re-introducendo la starvation che il controllo di sicurezza UXT-02 e il rifiuto MJPEG/WebSocket di v1.1 hanno costruito per prevenire. Il trasporto è **polling fetch** di `/overlay-json` |

## Traceability

Ogni requisito v1.2 → esattamente una fase. Coverage validata dal roadmap: 18/18 mappati (Phase 10–14, continuazione dalla v1.1). Nessun orfano, nessun duplicato.

| Requirement | Phase | Status |
|-------------|-------|--------|
| OVL-01 | Phase 11 | Pending |
| OVL-02 | Phase 11 | Pending |
| OVL-03 | Phase 11 | Pending |
| OVL-04 | Phase 11 | Pending |
| TMR-01 | Phase 11 | Pending |
| TMR-02 | Phase 11 | Pending |
| TMR-03 | Phase 11 | Pending |
| TMR-04 | Phase 11 | Pending |
| OVD-01 | Phase 10 | Complete |
| OVD-02 | Phase 10 | Complete |
| OVD-03 | Phase 10 | In Progress (freestyle_duration_s config seeded in 10-03; gen-age freshness contract completes in 10-04) |
| SCV-02 | Phase 12 | Pending |
| BRD-01 | Phase 11 | Pending |
| BRD-02 | Phase 11 | Pending |
| SCN-01 | Phase 13 | Pending |
| SCN-02 | Phase 13 | Pending |
| RBT-06 | Phase 13, Phase 14 | Pending |
| RBT-07 | Phase 10 | Complete |

**Note RBT-06:** the `overlay.txt` fallback is *wired* in Phase 13 (scene-collection text source retained) and *verified end-to-end under failure* in Phase 14 (the live-robustness degrade gate). The requirement is delivered by Phase 13; Phase 14 is its acceptance validation.

**Note RBT-07:** crash-isolation is the HARD invariant gated at Phase 10 and re-asserted as a success criterion of every subsequent v1.2 phase that touches `segugio.ui` (11, 12, 14).

**Coverage:** v1.2 requirements: 18 total — **18/18 mapped** (each to exactly one delivering phase). No orphans.

---
*Requirements defined: 2026-06-14 for milestone v1.2 "Overlay Grafico Broadcast" (continues phase numbering from v1.1; fresh REQUIREMENTS.md after the v1.1 close archived its requirements to milestones/v1.1-REQUIREMENTS.md). Traceability mapped to Phases 10–14 by the roadmapper 2026-06-14.*
