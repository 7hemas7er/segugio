# Requirements: Segugio

**Defined:** 2026-06-09
**Core Value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.

> **Milestone v1 = software completo su dati sintetici (Fasi 0-4).** Tutto verificabile su video registrati + sorgente NDI mock, senza hardware. Le voci hardware/campo sono in *Out of Scope* (milestone successive).

## v1 Requirements

### Configuration (CFG)

- [x] **CFG-01**: Esiste un file di config YAML centrale, validato all'avvio, con: numero camere e loro ruolo, zone del campo, disciplina, e tutte le soglie (alpha EMA, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer)
- [x] **CFG-02**: Le zone del campo sono modellate come rettangoli normalizzati [0..1] per camera (named bands: near/mid/far/stage) con una matrice `framing_weights[role][zone]`
- [x] **CFG-03**: Un selettore di disciplina (disc dog / agility) cambia i campi dell'overlay e i default di framing senza modifiche al codice
- [x] **CFG-04**: Path del modello YOLO e indice classe sono configurabili (default `yolo26s.pt`, `dog=16`), sostituibili con un `.pt` custom senza toccare il codice

### Tracking & Detection (TRK)

- [x] **TRK-01**: Il sistema integra un modello YOLO pre-addestrato su GPU CUDA con **un tracker per camera** (`persist=True`), eseguito su video registrati come pseudo-camere
- [x] **TRK-02**: Il tracking usa BoT-SORT con **ReID nativo** (`with_reid: True, model: auto`) e `track_buffer` esteso; l'avvio verifica che il ReID nativo sia effettivamente attivo
- [x] **TRK-03**: Per ogni detection il sistema estrae segnali normalizzati (centro cx/cy, dimensione w/h, confidence, track id) filtrati sulla classe cane
- [x] **TRK-04**: **Competitor-lock** — il sistema seleziona il track del cane "in gara" in modo robusto a handler, cani spettatori e persone (non sceglie semplicemente il più grande/centrale)
- [x] **TRK-05**: Un gate di plausibilità (teleport/size-jump) scarta cambi di track implausibili

### Framing (FRM)

- [x] **FRM-01**: Il framing scorer calcola un punteggio normalizzato resolution-independent da centratura + dimensione + confidence
- [x] **FRM-02**: Il punteggio è smussato con EMA per camera (alpha da config)
- [x] **FRM-03**: **Zone-gating** — il punteggio è pesato per la zona di campo in cui si trova il cane (`framing_weights`)
- [x] **FRM-04**: **Lead-room** — la posizione ideale è spostata verso la direzione di movimento del cane
- [x] **FRM-05**: **Coast/TTL** — durante brevi drop di detection (blur su salti/sprint) il punteggio non collassa subito, per non tagliare via dal climax
- [x] **FRM-06**: La confidence è normalizzata per camera per evitare che la regia favorisca la camera più luminosa
- [x] **FRM-07**: Il framing scorer è puro (nessun I/O) e unit-testabile su sequenze di detection sintetiche

### Decision Engine / Switching (DEC)

- [x] **DEC-01**: Una macchina a stati (FSM) è l'unica fonte di verità su quale camera è live; nessun comando OBS parte fuori da una transizione guardata
- [x] **DEC-02**: Lo switching applica isteresi (dead-band a due soglie), min_dwell (2-3s), debounce (N win consecutivi) e cooldown post-cut — niente flicker né doppio cut
- [x] **DEC-03**: Stato "azione in corso → tieni": durante un'azione (catch/salto rilevato) la FSM ritarda il cut
- [x] **DEC-04**: Hold da occlusione attesa (tunnel/contatti agility, da config-zone): la FSM non taglia via quando il cane è in un'occlusione prevista
- [x] **DEC-05**: Tiebreaker deterministico per camere con punteggio quasi pari (no ping-pong)
- [x] **DEC-06**: Feed-alive guard — una camera con feed morto non è mai selezionata come live né come challenger
- [x] **DEC-07**: La FSM è unit-testabile su stream di punteggi + eventi di feed-death sintetici (ping-pong/tie/dropout/recovery)

### NDI Ingest (NDI)

- [x] **NDI-01**: Modulo ingest via cyndilib (Finder/Receiver/FrameSync) → numpy BGR, un thread ricevitore supervisionato per camera
- [x] **NDI-02**: Una **sorgente NDI sintetica/mock** pubblica clip registrate come sorgenti NDI nominate, per integrazione end-to-end senza telefoni
- [x] **NDI-03**: Guard sui primi frame vuoti (loop finché risoluzione/dati non sono validi)

### OBS Control (OBS)

- [x] **OBS-01**: Il controller commuta la scena program su un OBS locale via `SetCurrentProgramScene`
- [x] **OBS-02**: PIP/multi-view via `SetSceneItemTransform` (bounds) + `SetSceneItemEnabled` usando `sceneItemId` numerici risolti e **cachati** all'avvio
- [x] **OBS-03**: Connessione persistente con reconnect+reauth; un `EventClient` su thread sincronizza i cambi scena manuali dell'operatore
- [x] **OBS-04**: È fornito un template di scene collection OBS (`CAM Wide`/`CAM Long`/`CAM Low`/`CAM Handler`, scena `SAFE`, `MULTIVIEW`, `PIP`)
- [x] **OBS-05**: I testi overlay si aggiornano via text source "read from file" (path primario) con fallback `SetInputSettings` per testi one-shot

### Score & Overlay (SCR)

- [x] **SCR-01**: Lo score manager scrive un file in modo atomico (write temp + `os.replace`) letto da una text source OBS "read from file"
- [x] **SCR-02**: Una UI/CLI di **inserimento manuale** dei punteggi offre un selettore disciplina e 3 set di campi (disc Toss&Fetch: conteggio prese/zona/totale; disc freestyle: nome+timer; agility: tempo vs SCT + faults)
- [x] **SCR-03**: Un controllo manuale di **run start/stop** resetta l'overlay, avvia/ferma un timer e funge da segnale di segmentazione della run
- [x] **SCR-04**: Il sistema **mostra** i punteggi inseriti, non li calcola né li giudica (nessuna CV di scoring/faults/prese)

### Override & Robustness (RBT)

- [x] **RBT-01**: Un feed watchdog deduce la liveness dal timestamp dell'ultimo frame *nuovo* (mai dallo stato sorgente NDI), con grazia anti-jitter
- [x] **RBT-02**: Alla caduta di un feed il sistema fa fallback automatico (scena SAFE o altra camera viva) senza crash; alla ripresa il feed rientra solo dopo essere vivo e aver vinto la piena isteresi+dwell
- [x] **RBT-03**: **Override manuale + auto-resume** — un operatore può forzare una camera specifica; poi il sistema rientra in automatico
- [x] **RBT-04**: L'orchestrator gira a tick a rate fisso, isola i guasti (try/except + restart supervisionati dei thread) e va in shutdown sulla scena SAFE; mai crash del processo
- [x] **RBT-05**: Il loop decisionale AI (frame → YOLO → score → FSM → comando OBS) è misurato e sta sotto **300ms** p95 (budget rivisto 2026-06-13 da <150ms — Phase 6: il path canonico FP16+batch eager con ReID nativa misura ~256ms cool sul RTX 4000 Ada Laptop, <300ms; engine TensorRT ~197ms come leva opzionale a più margine)

### Test Fixtures (TST)

- [x] **TST-01**: Esiste un **curated clip set** multi-condizione (multi-cane, handler prominente, occlusioni tunnel/contatti, blur, cane distante, controluce/dusk, camere equidistanti) per disc dog e agility
- [x] **TST-02**: Generatori sintetici (score-stream, feed-death) permettono test hardware-free di scorer, FSM e watchdog

## v1.1 Requirements — Console Regia (visibilità live)

> **Milestone v1.1**: la console operatore passa da pannello "alla cieca" a regia con visibilità live (vedi le camere, capisci *perché* una è in onda, override informato). **Vincolo HARD invariato**: la console resta crash-isolata (importa SOLO Flask + `segugio.opcomm`, mai l'orchestrator — D-03/RBT-04); ogni dato live arriva via un nuovo canale pubblicato dall'orchestrator. È un problema di *publish-and-render*, non di compute (i dati esistono già). Vedi `.planning/research/v1.1/SUMMARY.md`.

### Canale di pubblicazione frame (PRV)

- [ ] **PRV-01**: L'orchestrator pubblica thumbnail JPEG downscalate per-camera **fuori dal tick critico** (thread daemon `PreviewPublisher` con mailbox latest-only, frame-drop ammesso) in una media dir **separata e limitata** — il p95 del gate RBT-05 resta invariato con la preview attiva (gate di latenza)
- [ ] **PRV-02**: Un sidecar `preview.json` (`PreviewDoc`, frozen + reader con default sicuro che non solleva mai) porta per-camera lo score di framing + lo stato tracking (tracking/coast/lost) + il bbox normalizzato del cane + il candidato-auto della FSM + un ring degli ultimi cut — **separato** da `status.json` (che resta invariato/safety-critical)
- [ ] **PRV-03**: Primitiva di scrittura atomica binaria (`atomic_write_bytes`, speculare alla testuale, senza fsync per i frame effimeri); la console continua a importare **solo Flask + `segugio.opcomm`** (test di crash-isolation: import OK con lo stack pesante assente)

### Multiview & override informato (MVW)

- [ ] **MVW-01**: La console mostra una **griglia multiview** live delle thumbnail di tutte le camere (CSS Grid responsive, refresh flicker-free via preload `Image()` + swap)
- [ ] **MVW-02**: Indicatore **LIVE/tally** chiaro sulla tile della camera in onda (bordo rosso/badge + banner "ON AIR: CAM X"), da `status.live_cam`
- [ ] **MVW-03**: Ogni feed **morto/stale** è marcato a colpo d'occhio sulla sua tile (grey-out/"MORTO"), legato a `status.alive` + freshness della preview
- [ ] **MVW-04**: **Override informato** — ogni tile è cliccabile = forza quella camera (sostituisce i bottoni testuali alla cieca); "Rilascia (auto)" resta un controllo distinto
- [ ] **MVW-05**: **Striscia cronologia switch** — timeline degli ultimi cut + motivi, per giudicare se il director è "nervoso" e intervenire (dal ring in `preview.json`)

### Spiegabilità ("e perché") (WHY)

- [ ] **WHY-01**: La console mostra il **motivo** della scelta corrente in italiano chiaro (rende `status.reason`: "Auto: miglior inquadratura" / "Override operatore" / "Soggetto perso → SAFE" …)
- [ ] **WHY-02**: **Barre di score di framing per-camera** (leaderboard live) con stato tracking/coast/lost — l'operatore *vede* perché una camera vince in questo istante
- [ ] **WHY-03**: **Overlay bbox dog-lock** sulla tile live (box normalizzato disegnato in CSS/SVG dal `preview.json`, nessun image-processing in Flask) — mostra che il sistema è agganciato al cane in gara
- [ ] **WHY-04**: Hint **"auto vuole vs in onda"** — durante un override mostra quale camera sceglierebbe l'auto-director adesso, così l'operatore sa quando è sicuro rilasciare (mantiene il sistema più spesso in auto)

### Preview punteggio (SCV)

- [ ] **SCV-01**: **Preview live del punteggio** come apparirà sull'overlay OBS mentre l'operatore digita (riusa `render_overlay_text`, nessun round-trip all'orchestrator)

### UX tablet & robustezza (UXT)

- [ ] **UXT-01**: **Restyling responsive tablet-friendly** (griglia che riflow, target touch grandi per l'override, form punteggi usabile una mano)
- [ ] **UXT-02**: **Fix server multi-thread** (`threaded=True`/Waitress) così che servire/streammare le thumbnail non blocchi mai il POST di `/command` (l'override è un controllo di **sicurezza**) — bug latente in `ui/app.py`
- [ ] **UXT-03**: **Igiene robustezza** — niente memory leak su multiview prolungata, resume su sleep/wake del tablet, indicatore di **freshness** (mai mostrare un frame congelato come "live"); preview che degrada per prima, il director mai

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
| MJPEG / WebSocket / OBS-multiview-embed come trasporto preview v1.1 | Research v1.1 li ha respinti: rompono/affaticano la crash-isolation o aggiungono un server di rete sul director; il trasporto v1.1 è polling di thumbnail JPEG sul canale file opcomm |
| Pannello di tuning live del director dalla console | Nuovo canale di scrittura nel core decisionale; contraddice il design read-mostly crash-isolato (anti-feature research) |

## Traceability

Ogni requisito v1 → esattamente una fase (100% coverage, nessun orfano).

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 1 | Complete |
| CFG-02 | Phase 1 | Complete |
| CFG-03 | Phase 1 | Complete |
| CFG-04 | Phase 1 | Complete |
| TST-01 | Phase 1 | Complete |
| TST-02 | Phase 1 | Complete |
| FRM-01 | Phase 2 | Complete |
| FRM-02 | Phase 2 | Complete |
| FRM-03 | Phase 2 | Complete |
| FRM-04 | Phase 2 | Complete |
| FRM-05 | Phase 2 | Complete |
| FRM-06 | Phase 2 | Complete |
| FRM-07 | Phase 2 | Complete |
| DEC-01 | Phase 3 | Complete |
| DEC-02 | Phase 3 | Complete |
| DEC-03 | Phase 3 | Complete |
| DEC-04 | Phase 3 | Complete |
| DEC-05 | Phase 3 | Complete |
| DEC-06 | Phase 3 | Complete |
| DEC-07 | Phase 3 | Complete |
| RBT-03 | Phase 3 | Complete |
| TRK-01 | Phase 4 | Complete |
| TRK-02 | Phase 4 | Complete |
| TRK-03 | Phase 4 | Complete |
| TRK-04 | Phase 4 | Complete |
| TRK-05 | Phase 4 | Complete |
| NDI-01 | Phase 5 | Complete |
| NDI-02 | Phase 5 | Complete |
| NDI-03 | Phase 5 | Complete |
| OBS-01 | Phase 5 | Complete |
| OBS-02 | Phase 5 | Complete |
| OBS-03 | Phase 5 | Complete |
| OBS-04 | Phase 5 | Complete |
| OBS-05 | Phase 5 | Complete |
| SCR-01 | Phase 5 (05-01) | Complete |
| SCR-02 | Phase 5 | Complete |
| SCR-03 | Phase 5 | Complete |
| SCR-04 | Phase 5 | Complete |
| RBT-01 | Phase 5 | Complete |
| RBT-02 | Phase 5 | Complete |
| RBT-04 | Phase 5 | Complete |
| RBT-05 | Phase 5 → met in Phase 6 (latency optimization, <300ms) | Complete |

### Traceability — v1.1 Console Regia

Ogni requisito v1.1 → esattamente una fase (100% coverage, nessun orfano). La numerazione delle fasi continua dalla v1.0 (parte da Phase 7).

| Requirement | Phase | Status |
|-------------|-------|--------|
| PRV-01 | Phase 7 | Pending |
| PRV-02 | Phase 7 | Pending |
| PRV-03 | Phase 7 | Pending |
| MVW-01 | Phase 8 | Pending |
| MVW-02 | Phase 8 | Pending |
| MVW-03 | Phase 8 | Pending |
| UXT-02 | Phase 8 | Pending |
| MVW-04 | Phase 9 | Pending |
| MVW-05 | Phase 9 | Pending |
| WHY-01 | Phase 9 | Pending |
| WHY-02 | Phase 9 | Pending |
| WHY-03 | Phase 9 | Pending |
| WHY-04 | Phase 9 | Pending |
| SCV-01 | Phase 9 | Pending |
| UXT-01 | Phase 9 | Pending |
| UXT-03 | Phase 9 | Pending |

**Coverage:**

- v1 requirements: 41 total — mapped 41 (100%), unmapped 0 ✓
- v1.1 requirements: 16 total — mapped 16 (100%), unmapped 0 ✓

**Per-phase counts (v1):**

- Phase 1 — Foundation, Config & Curated Clip Set: 6 (CFG-01..04, TST-01, TST-02)
- Phase 2 — Framing Scorer (pure logic): 7 (FRM-01..07)
- Phase 3 — Decision Engine FSM: 8 (DEC-01..07, RBT-03)
- Phase 4 — YOLO + Per-Camera Tracking on Clips: 5 (TRK-01..05)
- Phase 5 — Integration (NDI Mock, Orchestrator, OBS, Score UI): 15 (NDI-01..03, OBS-01..05, SCR-01..04, RBT-01, RBT-02, RBT-04, RBT-05)
- Phase 6 — Decision-loop latency optimization: RBT-05 met under the revised <300ms budget

**Per-phase counts (v1.1):**

- Phase 7 — Off-tick Frame-Publishing Channel: 3 (PRV-01, PRV-02, PRV-03)
- Phase 8 — Console Serving, Live Multiview & Safety Hardening: 4 (MVW-01, MVW-02, MVW-03, UXT-02)
- Phase 9 — Explainability, Informed Override & Tablet UX: 9 (MVW-04, MVW-05, WHY-01..04, SCV-01, UXT-01, UXT-03)

---
*Requirements defined: 2026-06-09*
*Last updated: 2026-06-13 after v1.1 roadmap creation (v1.1 traceability populated, 16/16 mapped to Phases 7–9)*
