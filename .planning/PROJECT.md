# Segugio

## What This Is

Sistema di **regia video automatica senza operatore** per gare di **disc dog** e **agility**. Più telefoni (3-4) pubblicano feed NDI HX3 su una rete WiFi 6 dedicata; OBS Studio fa da hub video, mentre un orchestratore Python traccia il cane sul campo con un modello YOLO su GPU, sceglie in tempo reale la telecamera con la miglior inquadratura e commuta la scena OBS via obs-websocket, sovrapponendo i punteggi della gara. È pensato per chi organizza/riprende gare cinofile e vuole una regia multi-camera senza un operatore dedicato.

## Core Value

**La camera giusta al momento giusto, in automatico.** Il sistema deve mantenere il cane ben inquadrato commutando tra le telecamere in modo fluido — senza operatore e senza cut tremolanti. Se tutto il resto fallisce, questo deve funzionare.

## Requirements

### Validated

(Nessuno ancora — si valida costruendo e provando)

### Active

<!-- Milestone v1: software completo su dati sintetici (Fasi 0-4). Testabile senza hardware. -->

- [ ] Configurazione centrale YAML (numero camere, zone del campo, soglie di switching, alpha EMA, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout) con validazione
- [ ] Framing scorer: score normalizzato (centratura + dimensione + confidence) resolution-independent, con smoothing EMA per camera
- [ ] Decision engine: macchina a stati (FSM) come unica fonte di verità su "quale camera è live", con isteresi + min_dwell + debounce + cooldown + feed-alive (mai doppio cut, mai flicker, mai cut su feed morto)
- [ ] Integrazione modello YOLO **pre-addestrato** (path + indice classe da config, nessun training) su GPU CUDA, con **un tracker per camera** (persist=True), su video registrati come pseudo-camere
- [ ] OBS controller via obs-websocket v5 (obsws-python): cut scena (SetCurrentProgramScene), PIP/multi-view (SetSceneItemTransform + SetSceneItemEnabled con sceneItemId cachato), testi (SetInputSettings), reconnect, EventClient
- [ ] Score manager: **inserimento manuale** dei punteggi (UI/CLI) → scrittura atomica su file letto da una text source OBS "read from file"
- [ ] NDI ingest via cyndilib (FrameSync → numpy BGR), in parallelo a OBS, + **sorgente NDI sintetica/mock** per test senza telefoni
- [ ] Feed watchdog: liveness per-feed basata sul timestamp dell'ultimo frame (NON sullo stato sorgente NDI), con grazia anti-jitter → fallback automatico
- [ ] **Override manuale + auto-resume**: un operatore può forzare una camera; poi il sistema rientra in automatico
- [ ] Orchestrator: tick a rate fisso, wiring dei moduli, fault isolation (try/except + restart supervisionati), shutdown su scena **SAFE**, mai crash
- [ ] Loop decisionale AI (frame → YOLO → score → FSM → comando OBS) sotto ~150ms (ideale <80ms)
- [ ] Deliverable: struttura progetto, codice Python, istruzioni setup OBS (scene, sorgenti NDI, websocket), requirements, README

### Out of Scope

<!-- Confini espliciti per questa milestone v1. -->

- **Hardware reale (telefoni/NDI/campo)** — rimandato a milestone successive (Fasi 5-7). Tutta la v1 è testabile con video registrati + sorgente NDI mock.
- **Output recording/streaming (RTMP/YouTube)** — in v1 solo preview locale; l'output reale si definisce dopo.
- **Integrazione sistema di scoring esterno (API)** — in v1 i punteggi sono a inserimento manuale.
- **Training/creazione del modello YOLO** — si usa un modello pre-addestrato (classe `dog` COCO o `.pt` custom drop-in via config).
- **Latenza <50ms end-to-end glass-to-glass** — fisicamente impossibile con questo stack (la sola cattura smartphone è ~57-106ms); riformulata in due budget separati.
- **Export engine TensorRT FP16 / tuning su GPU di produzione** — appartiene alle fasi hardware (6+); gli engine sono specifici per GPU/driver.
- **Re-ID *pesante* (modello ReID dedicato) e gestione multi-cane avanzata** — rimandata. ⚠️ Nota (research): il **ReID *nativo*** di BoT-SORT (`model: auto`, usa le feature del detector, zero pesi extra) è economico ed è **incluso in v1** perché contrasta il problema #1 del dominio; resta fuori scope solo il ReID con modello dedicato/pesante.

## Context

- **Ambiente di sviluppo:** box Linux (WSL2) con GPU NVIDIA CUDA disponibile → adatto alle Fasi 0-4 (logica pura + YOLO su video + OBS locale + NDI mock), tutte hardware-free.
- **Ambiente di produzione (futuro):** consigliato **Windows** per la maturità dell'ecosistema NDI/OBS/DistroAV; il codice è scritto **OS-agnostic** (scoperta dell'input-kind a runtime, niente `text_gdiplus`/`text_ft2` hardcoded, `pathlib`). ⚠️ Il testing NDI/OBS reale va su host nativo, non dentro WSL2 (discovery mDNS e GUI OBS problematiche in WSL2).
- **Architettura a hub:** OBS resta l'hub video (riceve i feed via DistroAV per il PROGRAM); Python riceve le **stesse** sorgenti di rete in modo indipendente via cyndilib **solo per l'AI** → si decodifica due volte (tradeoff accettato: economico su GPU con NVDEC, mantiene tutto cross-platform).
- **Latenza in due budget:** (1) video glass-to-glass ~150-350ms — inerente all'IP/NDI, si accetta; (2) loop decisionale AI ~70-150ms (ottimizzabile a ~50-80ms con TensorRT FP16, NVDEC, comandi websocket async) — l'unico da ottimizzare, disaccoppiato dal video perché gira su frame che OBS ha già.
- **Gotcha NDI critico:** NDI tiene una sorgente per ~75 minuti ripetendo l'ultimo frame come fermo immagine → un telefono caduto sembra "vivo". La liveness va dedotta dal timestamp dell'ultimo frame *nuovo*, mai dallo stato sorgente NDI.
- **Ricerca:** decisioni tecniche fondate su una ricerca multi-fonte (obs-websocket v5, ingest NDI in Python, YOLO multi-stream, latenza/robustezza) condotta a inizio progetto.

## Constraints

- **Tech stack**: Python orchestratore; `ultralytics` + `torch` (+ `tensorrt` per prod) per YOLO; `cyndilib` per ingest NDI; `obsws-python` per obs-websocket v5; `transitions` per la FSM; `opencv-python`, `numpy`, `pyyaml`, `loguru`, `watchdog` — Vincolo da brief: stack imposto, integrare YOLO esistente.
- **Performance**: loop decisionale AI < ~150ms (ideale <80ms); video glass-to-glass ~150-350ms accettato — Vincolo fisico riformulato dal "<50ms" originale.
- **Hardware**: GPU NVIDIA CUDA (disponibile in dev); produzione consigliata su Windows; codice OS-agnostic — Per maturità ecosistema NDI/OBS.
- **Dependencies**: OBS Studio + plugin DistroAV (NDI); obs-websocket v5; modello YOLO pre-addestrato fornito via config — Componenti esterni richiesti dal brief.
- **Robustezza live**: nessun crash ammesso; caduta feed → degrado a scena SAFE / fallback — Requisito live esplicito.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Milestone v1 = Fasi 0-4 (software su dati sintetici) | Testabile senza hardware su questo box; sblocca subito il lavoro | — Pending |
| OBS-as-hub + Python ingest NDI separato per l'AI | Mantiene OBS come hub video richiesto, cross-platform; accetta "decode due volte" | — Pending |
| Latenza riformulata in due budget separati | <50ms end-to-end è impossibile (cattura smartphone ~57-106ms da sola) | — Pending |
| Un tracker YOLO per camera (no lista di frame a `track()`) | Una lista di frame costruisce un solo tracker e mescola gli ID tra camere (#13107) | — Pending |
| Liveness via timestamp ultimo frame, non stato NDI | NDI tiene la sorgente 75min ripetendo l'ultimo frame → falso "vivo" | — Pending |
| Override manuale + auto-resume nonostante "senza operatore" | Sicurezza live: auto è il default, l'umano può forzare e poi rientra in auto | — Pending |
| Punteggi via inserimento manuale → file read-from-file | Tiene gli update fuori dal budget websocket; nessun sistema scoring esterno in v1 | — Pending |
| obsws-python (ReqClient sincrono) come canale di controllo | Semantica bloccante + timeout, EventClient thread-safe; ideale per un controller | — Pending |
| Output solo preview in v1 | Sufficiente a validare la regia automatica senza requisiti di rete/bitrate | — Pending |
| ReID nativo BoT-SORT incluso in v1 (no re-ID pesante) | Gratis (feature del detector, zero pesi) e contrasta il problema #1: cane che esce/rientra/occluso | — Pending |
| Competitor-lock + zone-gating come feature di prima classe | Lo scorer size+centratura aggancia handler/cani spettatori → selezione del cane "in gara" va progettata, non emergente | — Pending |
| Curated multi-condition clip set assemblato in P0 | De-risk decisivo: clip pulite mascherano ogni pitfall fino al campo | — Pending |
| Modello YOLO concreto v1 = yolo26s.pt, classe dog=16 | Small (non nano) per soggetto piccolo/distante; COCO dog sufficiente finché l'eval non prova il contrario | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-09 after initialization*
