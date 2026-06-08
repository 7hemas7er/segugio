# Requirements: Segugio

**Defined:** 2026-06-09
**Core Value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.

> **Milestone v1 = software completo su dati sintetici (Fasi 0-4).** Tutto verificabile su video registrati + sorgente NDI mock, senza hardware. Le voci hardware/campo sono in *Out of Scope* (milestone successive).

## v1 Requirements

### Configuration (CFG)

- [ ] **CFG-01**: Esiste un file di config YAML centrale, validato all'avvio, con: numero camere e loro ruolo, zone del campo, disciplina, e tutte le soglie (alpha EMA, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer)
- [ ] **CFG-02**: Le zone del campo sono modellate come rettangoli normalizzati [0..1] per camera (named bands: near/mid/far/stage) con una matrice `framing_weights[role][zone]`
- [ ] **CFG-03**: Un selettore di disciplina (disc dog / agility) cambia i campi dell'overlay e i default di framing senza modifiche al codice
- [ ] **CFG-04**: Path del modello YOLO e indice classe sono configurabili (default `yolo26s.pt`, `dog=16`), sostituibili con un `.pt` custom senza toccare il codice

### Tracking & Detection (TRK)

- [ ] **TRK-01**: Il sistema integra un modello YOLO pre-addestrato su GPU CUDA con **un tracker per camera** (`persist=True`), eseguito su video registrati come pseudo-camere
- [ ] **TRK-02**: Il tracking usa BoT-SORT con **ReID nativo** (`with_reid: True, model: auto`) e `track_buffer` esteso; l'avvio verifica che il ReID nativo sia effettivamente attivo
- [ ] **TRK-03**: Per ogni detection il sistema estrae segnali normalizzati (centro cx/cy, dimensione w/h, confidence, track id) filtrati sulla classe cane
- [ ] **TRK-04**: **Competitor-lock** — il sistema seleziona il track del cane "in gara" in modo robusto a handler, cani spettatori e persone (non sceglie semplicemente il più grande/centrale)
- [ ] **TRK-05**: Un gate di plausibilità (teleport/size-jump) scarta cambi di track implausibili

### Framing (FRM)

- [ ] **FRM-01**: Il framing scorer calcola un punteggio normalizzato resolution-independent da centratura + dimensione + confidence
- [ ] **FRM-02**: Il punteggio è smussato con EMA per camera (alpha da config)
- [ ] **FRM-03**: **Zone-gating** — il punteggio è pesato per la zona di campo in cui si trova il cane (`framing_weights`)
- [ ] **FRM-04**: **Lead-room** — la posizione ideale è spostata verso la direzione di movimento del cane
- [ ] **FRM-05**: **Coast/TTL** — durante brevi drop di detection (blur su salti/sprint) il punteggio non collassa subito, per non tagliare via dal climax
- [ ] **FRM-06**: La confidence è normalizzata per camera per evitare che la regia favorisca la camera più luminosa
- [ ] **FRM-07**: Il framing scorer è puro (nessun I/O) e unit-testabile su sequenze di detection sintetiche

### Decision Engine / Switching (DEC)

- [ ] **DEC-01**: Una macchina a stati (FSM) è l'unica fonte di verità su quale camera è live; nessun comando OBS parte fuori da una transizione guardata
- [ ] **DEC-02**: Lo switching applica isteresi (dead-band a due soglie), min_dwell (2-3s), debounce (N win consecutivi) e cooldown post-cut — niente flicker né doppio cut
- [ ] **DEC-03**: Stato "azione in corso → tieni": durante un'azione (catch/salto rilevato) la FSM ritarda il cut
- [ ] **DEC-04**: Hold da occlusione attesa (tunnel/contatti agility, da config-zone): la FSM non taglia via quando il cane è in un'occlusione prevista
- [ ] **DEC-05**: Tiebreaker deterministico per camere con punteggio quasi pari (no ping-pong)
- [ ] **DEC-06**: Feed-alive guard — una camera con feed morto non è mai selezionata come live né come challenger
- [ ] **DEC-07**: La FSM è unit-testabile su stream di punteggi + eventi di feed-death sintetici (ping-pong/tie/dropout/recovery)

### NDI Ingest (NDI)

- [ ] **NDI-01**: Modulo ingest via cyndilib (Finder/Receiver/FrameSync) → numpy BGR, un thread ricevitore supervisionato per camera
- [ ] **NDI-02**: Una **sorgente NDI sintetica/mock** pubblica clip registrate come sorgenti NDI nominate, per integrazione end-to-end senza telefoni
- [ ] **NDI-03**: Guard sui primi frame vuoti (loop finché risoluzione/dati non sono validi)

### OBS Control (OBS)

- [ ] **OBS-01**: Il controller commuta la scena program su un OBS locale via `SetCurrentProgramScene`
- [ ] **OBS-02**: PIP/multi-view via `SetSceneItemTransform` (bounds) + `SetSceneItemEnabled` usando `sceneItemId` numerici risolti e **cachati** all'avvio
- [ ] **OBS-03**: Connessione persistente con reconnect+reauth; un `EventClient` su thread sincronizza i cambi scena manuali dell'operatore
- [ ] **OBS-04**: È fornito un template di scene collection OBS (`CAM Wide`/`CAM Long`/`CAM Low`/`CAM Handler`, scena `SAFE`, `MULTIVIEW`, `PIP`)
- [ ] **OBS-05**: I testi overlay si aggiornano via text source "read from file" (path primario) con fallback `SetInputSettings` per testi one-shot

### Score & Overlay (SCR)

- [ ] **SCR-01**: Lo score manager scrive un file in modo atomico (write temp + `os.replace`) letto da una text source OBS "read from file"
- [ ] **SCR-02**: Una UI/CLI di **inserimento manuale** dei punteggi offre un selettore disciplina e 3 set di campi (disc Toss&Fetch: conteggio prese/zona/totale; disc freestyle: nome+timer; agility: tempo vs SCT + faults)
- [ ] **SCR-03**: Un controllo manuale di **run start/stop** resetta l'overlay, avvia/ferma un timer e funge da segnale di segmentazione della run
- [ ] **SCR-04**: Il sistema **mostra** i punteggi inseriti, non li calcola né li giudica (nessuna CV di scoring/faults/prese)

### Override & Robustness (RBT)

- [ ] **RBT-01**: Un feed watchdog deduce la liveness dal timestamp dell'ultimo frame *nuovo* (mai dallo stato sorgente NDI), con grazia anti-jitter
- [ ] **RBT-02**: Alla caduta di un feed il sistema fa fallback automatico (scena SAFE o altra camera viva) senza crash; alla ripresa il feed rientra solo dopo essere vivo e aver vinto la piena isteresi+dwell
- [ ] **RBT-03**: **Override manuale + auto-resume** — un operatore può forzare una camera specifica; poi il sistema rientra in automatico
- [ ] **RBT-04**: L'orchestrator gira a tick a rate fisso, isola i guasti (try/except + restart supervisionati dei thread) e va in shutdown sulla scena SAFE; mai crash del processo
- [ ] **RBT-05**: Il loop decisionale AI (frame → YOLO → score → FSM → comando OBS) è misurato e sta sotto ~150ms (ideale <80ms)

### Test Fixtures (TST)

- [ ] **TST-01**: Esiste un **curated clip set** multi-condizione (multi-cane, handler prominente, occlusioni tunnel/contatti, blur, cane distante, controluce/dusk, camere equidistanti) per disc dog e agility
- [ ] **TST-02**: Generatori sintetici (score-stream, feed-death) permettono test hardware-free di scorer, FSM e watchdog

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Predictive & Domain Intelligence

- **PRED-01**: Predictive framing avanzato basato su velocità/traiettoria (anticipazione)
- **PRED-02**: Detection del disco/frisbee come predittore del punto di presa (disc dog)
- **PRED-03**: Framing obstacle-aware / anticipazione del prossimo ostacolo (agility, course-order noto)
- **PRED-04**: Replay markers / segnalazione momenti salienti

## Out of Scope

Esplicitamente esclusi da v1. Documentati per prevenire scope creep.

| Feature | Reason |
|---------|--------|
| Hardware reale (telefoni, NDI HX3, rete, campo) | Milestone successive (Fasi 5-7); v1 usa clip registrate + NDI mock |
| Export engine TensorRT FP16 / tuning su GPU di produzione | Appartiene alle fasi hardware; engine specifici per GPU/driver |
| Output recording / streaming (RTMP/YouTube) | v1 è preview-only; output reale definito dopo |
| Integrazione sistema di scoring esterno (API) | v1 usa inserimento manuale |
| Training / fine-tune del modello YOLO | Si usa pre-addestrato; fine-tune solo se l'eval su footage reale lo richiede |
| Calibrazione campo / homography / world-coords | Upgrade da campo reale; v1 usa zone normalizzate per camera |
| Re-ID con modello dedicato/pesante | Il ReID *nativo* (cheap) è in v1; quello pesante no |
| Latenza <50ms end-to-end glass-to-glass | Fisicamente impossibile; riformulata in due budget |
| Adjudication automatica (scoring/faults/prese via CV) | Il giudice è autoritativo; un overlay in disaccordo è peggio di nessun overlay |

## Traceability

Ogni requisito v1 → esattamente una fase (100% coverage, nessun orfano).

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 1 | Pending |
| CFG-02 | Phase 1 | Pending |
| CFG-03 | Phase 1 | Pending |
| CFG-04 | Phase 1 | Pending |
| TST-01 | Phase 1 | Pending |
| TST-02 | Phase 1 | Pending |
| FRM-01 | Phase 2 | Pending |
| FRM-02 | Phase 2 | Pending |
| FRM-03 | Phase 2 | Pending |
| FRM-04 | Phase 2 | Pending |
| FRM-05 | Phase 2 | Pending |
| FRM-06 | Phase 2 | Pending |
| FRM-07 | Phase 2 | Pending |
| DEC-01 | Phase 3 | Pending |
| DEC-02 | Phase 3 | Pending |
| DEC-03 | Phase 3 | Pending |
| DEC-04 | Phase 3 | Pending |
| DEC-05 | Phase 3 | Pending |
| DEC-06 | Phase 3 | Pending |
| DEC-07 | Phase 3 | Pending |
| RBT-03 | Phase 3 | Pending |
| TRK-01 | Phase 4 | Pending |
| TRK-02 | Phase 4 | Pending |
| TRK-03 | Phase 4 | Pending |
| TRK-04 | Phase 4 | Pending |
| TRK-05 | Phase 4 | Pending |
| NDI-01 | Phase 5 | Pending |
| NDI-02 | Phase 5 | Pending |
| NDI-03 | Phase 5 | Pending |
| OBS-01 | Phase 5 | Pending |
| OBS-02 | Phase 5 | Pending |
| OBS-03 | Phase 5 | Pending |
| OBS-04 | Phase 5 | Pending |
| OBS-05 | Phase 5 | Pending |
| SCR-01 | Phase 5 | Pending |
| SCR-02 | Phase 5 | Pending |
| SCR-03 | Phase 5 | Pending |
| SCR-04 | Phase 5 | Pending |
| RBT-01 | Phase 5 | Pending |
| RBT-02 | Phase 5 | Pending |
| RBT-04 | Phase 5 | Pending |
| RBT-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 41 total
- Mapped to phases: 41 (100%)
- Unmapped: 0 ✓

**Per-phase counts:**
- Phase 1 — Foundation, Config & Curated Clip Set: 6 (CFG-01..04, TST-01, TST-02)
- Phase 2 — Framing Scorer (pure logic): 7 (FRM-01..07)
- Phase 3 — Decision Engine FSM: 8 (DEC-01..07, RBT-03)
- Phase 4 — YOLO + Per-Camera Tracking on Clips: 5 (TRK-01..05)
- Phase 5 — Integration (NDI Mock, Orchestrator, OBS, Score UI): 15 (NDI-01..03, OBS-01..05, SCR-01..04, RBT-01, RBT-02, RBT-04, RBT-05)

---
*Requirements defined: 2026-06-09*
*Last updated: 2026-06-09 after roadmap creation (traceability populated, 41/41 mapped)*
