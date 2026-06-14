# Segugio

## What This Is

Sistema di **regia video automatica senza operatore** per gare di **disc dog** e **agility**. Più telefoni (3-4) pubblicano feed NDI HX3 su una rete WiFi 6 dedicata; OBS Studio fa da hub video, mentre un orchestratore Python traccia il cane sul campo con un modello YOLO su GPU, sceglie in tempo reale la telecamera con la miglior inquadratura e commuta la scena OBS via obs-websocket, sovrapponendo i punteggi della gara. È pensato per chi organizza/riprende gare cinofile e vuole una regia multi-camera senza un operatore dedicato.

## Core Value

**La camera giusta al momento giusto, in automatico.** Il sistema deve mantenere il cane ben inquadrato commutando tra le telecamere in modo fluido — senza operatore e senza cut tremolanti. Se tutto il resto fallisce, questo deve funzionare.

## Current State

**Shipped:** v1.1 "Console Regia" (2026-06-14) — software-complete, hardware/field validation pending on the rig.

- **v1.0 MVP** (Phases 1–6, 2026-06-13): operator-less multi-camera auto-director, software-complete on synthetic data (recorded clips as pseudo-cameras + mock NDI). Config contract → pure framing scorer → decision FSM → YOLO+per-camera tracking → end-to-end integration → latency optimization (RBT-05 met <300ms p95). Never separately git-tagged.
- **v1.1 Console Regia** (Phases 7–9, 2026-06-14): the operator console goes from a blind control panel to a true regia with live visibility — multiview of every camera, the plain-Italian *why* of each cut, a dog-lock bbox overlay, a score leaderboard, switch-history, informed tap-to-force override, a live OBS score preview, and a tablet-first restyle with long-run hygiene — all **without** touching the v1.0 crash-isolation guarantee (console imports only Flask + `segugio.opcomm`, never the orchestrator). Accepted on a real iPad. Tag: `v1.1`.

**Codebase:** ~7,900 LOC Python under `src/segugio/` (+ tests), the new `orchestrator/preview.py` publish channel and the `ui/` console (`app.py` + `templates/console.html`) the v1.1 work centered on. Full headless suite green; crash-isolation enforced by an import test with the heavy stack absent.

**Known carry-forwards (all hardware/field-gated, none a code gap):** on-rig PRV-01 p95-no-regression confirmation; real-YOLO/clip recall on the CUDA box (P04); NDI/OBS field validation (P05); preview-bandwidth false-death validation with real phones; 2 environmental NDI-loopback CI failures; thermal variance on the laptop GPU → prefer a desktop deploy GPU for sustained live. See STATE.md → Deferred Items and `milestones/v1.1-MILESTONE-AUDIT.md`.

**v1.2 progress:** Phase 10 complete & verified (2026-06-14, 4/4 must-haves) — the overlay data foundation: a NEW console-owned `overlay_run.json` stamps the run-start instant on the run edge (director-read `runstate.json` byte-for-byte untouched), and `GET /overlay-json` serves a boundary-safe `{discipline, fields, running, started_at, server_now, gen}` payload (`Cache-Control: no-store`, never-raises on torn/absent sources) with the clock-skew anchor (`server_now`) and monotonic `gen` in the contract from commit one. Crash-isolation re-verified (console imports only Flask + `segugio.opcomm`). No HTML yet (Phase 11). A post-execution code review found & fixed one Critical (NaN/Infinity escaping the never-raise boundary) + 4 warnings, with regression tests.

## Current Milestone: v1.2 Overlay Grafico Broadcast

**Goal:** Sostituire la sovrapposizione punteggi testo-su-file con un overlay grafico broadcast animato — renderizzato via OBS *browser-source* alimentata dalla console crash-isolated — e impacchettare un scene-collection OBS curato, senza mai toccare il director.

**Target features:**
- **Overlay grafico HTML/CSS** (lower-third per disciplina: disc T&F prese/zona/totale · freestyle nome/timer · agility tempo/SCT/faults) servito come **OBS browser-source** dalla console — nuove route `GET /overlay` (HTML) + `GET /overlay-json` (dati), sfondo trasparente per il compositing
- **Timer di run che conta da solo**, client-side, da `run_started_at` + `running` (dal `RunState` esistente) — zero compute sul tick del director
- **Animazioni**: ingresso/uscita del lower-third + pulse sul cambio punteggio; reazione agli edge run start/stop
- **Fallback degradato**: `overlay.txt` resta come fallback robusto (SCR-01)
- **SCV-01 semplificato**: console-preview e OBS-overlay condividono lo stesso renderer HTML (sparisce il mirror JS byte-exact di Python)
- **Scene OBS curate**: nuovo `obs/segugio-scene-collection.json` con la browser-source cablata in ogni scena CAM + layout/transizioni + `docs/obs-setup.md` aggiornato

**Nodo di design / vincolo HARD:** la console resta crash-isolata (importa solo `Flask + segugio.opcomm`); l'orchestrator/director non viene mai toccato. È *publish-and-render* sopra il canale `opcomm` già esistente (i dati `ScoreDoc`/`RunState` ci sono già), non compute — stesso pattern del canale preview di v1.1. Numerazione fasi continua dalla v1.1 (parte da Phase 10).

## Requirements

### Validated

- [x] Configurazione centrale YAML (camere/ruoli, zone del campo normalizzate, disciplina, tutte le soglie di switching: alpha EMA, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer) con validazione fail-fast — *validato in Phase 1 (CFG-01..04): root pydantic v2 tipato; disciplina disc dog/agility come discriminated union (swap overlay/framing senza modifiche al codice, CFG-03); loader `yaml.safe_load` con `SystemExit(2)` su qualsiasi errore di read/parse/validazione (CFG-01); zone come rettangoli normalizzati [0..1] per camera + `framing_weights[role][zone]` (CFG-02); path/classe modello da config, default `yolo26s.pt`/`dog=16` sostituibili senza codice (CFG-04).*
- [x] Framing scorer: score normalizzato (centratura + dimensione + confidence) resolution-independent, con smoothing EMA per camera — *validato in Phase 2 (FRM-01..07): scorer puro e I/O-free, zone-gating, lead-room, coast/TTL, conf-norm per camera; 124 test verdi su sequenze sintetiche, copertura framing 99%.*
- [x] Decision engine: FSM (`transitions`) come unica fonte di verità sulla camera live, con isteresi a due soglie + min_dwell + debounce + cooldown, feed-death emergency cut, action/occlusion hold con max-cap obbligatorio, tiebreaker deterministico, override manuale + auto-resume — *validato in Phase 3 (DEC-01..07, RBT-03): switch solo da transizioni guardate, zero cut spuri su ping-pong/tie, mai aria su feed morto, determinismo byte-identico; 167 test verdi su stream sintetici score + feed-death, copertura `segugio.decision` 100%; blocker CR-01 (cooldown spurio in uscita da SAFE) trovato in code review e corretto con test di regressione.*
- [x] YOLO + tracking per camera: modello pre-addestrato (path/classe da config) con **un tracker per camera** (`persist=True`, BoT-SORT ReID nativo), mapper segnali normalizzati, competitor-lock e plausibility gate su clip registrate come pseudo-camere — *validato in software in Phase 4 (TRK-01..05): logica pura (`signals_from_boxes`, `CompetitorLock` zona∧moto + sticky, `PlausibilityGate` teleport/size-jump→coast) unit-testata su stream multi-track sintetici; `PerCameraTracker` (cane risolto per nome da `model.names`, `end2end=False`) + hard gate ReID nativo (raise sul fallback silenzioso `yolo26n-cls.pt`) con boundary lazy-import; 208 test verdi, 3 GPU-gated SKIP. 2 blocker da code review (reset del gate su ogni coast; gate ReID su crop vuoto) corretti. Verifica reale-YOLO/clip rimandata alla CUDA box (`04-HUMAN-UAT.md`), per design "software-complete su dati sintetici".*
- [x] NDI ingest via cyndilib (Finder/Receiver/FrameSync → numpy BGR, un ricevitore supervisionato per camera) + **sorgente NDI sintetica/mock** che pubblica clip registrate come sorgenti nominate, guard sui primi frame vuoti — *validato in Phase 5 (NDI-01..03): integrazione end-to-end senza telefoni. (Nota campo: la decodifica HX dei telefoni reali richiede il runtime NDI 6.3.2 di sistema — vedi docs/run.md.)*
- [x] OBS controller via obs-websocket v5 (obsws-python): cut scena (`SetCurrentProgramScene`), PIP/multi-view (`SetSceneItemTransform` + `SetSceneItemEnabled` con `sceneItemId` cachati all'avvio), connessione persistente reconnect+reauth con `EventClient` per i cambi scena manuali dell'operatore, testi overlay via text source "read from file" (fallback `SetInputSettings`), template scene collection (`CAM *`/`SAFE`/`MULTIVIEW`/`PIP`) — *validato in Phase 5 (OBS-01..05); setup in `docs/obs-setup.md`.*
- [x] Score manager: **inserimento manuale** dei punteggi (UI/CLI con selettore disciplina e 3 set di campi: disc Toss&Fetch, disc freestyle, agility) → scrittura **atomica** (write temp + `os.replace`) su file letto da una text source OBS "read from file"; controllo manuale run start/stop con timer e reset overlay; il sistema **mostra** i punteggi, non li calcola né giudica (nessuna CV di scoring/prese/faults) — *validato in Phase 5 (SCR-01..04).*
- [x] Feed watchdog: liveness per-feed dedotta dal timestamp dell'ultimo frame **nuovo** (mai dallo stato sorgente NDI) con grazia anti-jitter → fallback automatico — *validato in Phase 5 (RBT-01/RBT-02): alla caduta di un feed fallback su scena SAFE o altra camera viva senza crash; rientro solo dopo feed vivo + piena isteresi+dwell.*
- [x] Orchestrator: tick a rate fisso, wiring dei moduli, fault isolation (try/except + restart supervisionati dei thread), shutdown su scena **SAFE**, mai crash del processo — *validato in Phase 5 (RBT-04): verifica 2026-06-11 (4/5; blocker CR-01 "startup fault-sink" trovato in code review e corretto). Entry point `python -m segugio <config.yaml>` (docs/run.md); harness `run_measured` di latenza (base per RBT-05/Phase 6).*
- [x] Loop decisionale AI (frame → YOLO → score → FSM → comando OBS) sotto **300ms** p95 (budget rivisto da <150ms) — *validato in Phase 6 (RBT-05): export engine TensorRT FP16 (`tools/build_engine.py`) + inferenza FP16 **batched** (un forward per tick al posto di 4 `model.track()` seriali) + loader engine-aware con fallback eager graceful (RBT-04). Path canonico = **FP16+batch eager** che PRESERVA la ReID nativa BoT-SORT, misurato p95 ~256ms cool < 300ms sul RTX 4000 Ada **Laptop** GPU (venv312, cu126 torch + tensorrt-cu12 10.x). Engine TensorRT ~197ms tenuto come leva opzionale a più margine. ⚠ Varianza termica sul Laptop GPU (~546ms heat-soaked) → per gare live prolungate preferire una GPU desktop di deploy (raggiungerebbe anche <150ms); spot-check recall FP16 su clip difficili rimandato.*

- [x] Console regia live: multiview CSS-Grid flicker-free di tutte le camere con indicatore LIVE/tally e marcatura feed morto (MORTO), servita dalla console crash-isolated via due nuove route GET (`/preview` sidecar JSON + `/preview/<cam>.jpg` `send_file` whitelisted, anti path-traversal); fix server multi-thread (`threaded=True`/Waitress) come **controllo di sicurezza** (l'override POST non può mai essere bloccato da uno stream preview); cap di banda preview come **garanzia config-time** (`PreviewParams.max_total_mbps` + `@model_validator` → `SystemExit(2)`: la preview degrada prima che i feed NDI sembrino morti); ri-valutazione minacce scritta (`docs/security.md`: video competitor live dietro `0.0.0.0`, isolamento client AP come requisito operativo HARD) — *validato in Phase 8 (MVW-01/02/03, UXT-02): 10/10 must-have verificati, 39 test specifici verdi, suite headless 394 passed/8 skipped/0 failures, crash-isolation preservata (import con torch/cv2/numpy/cyndilib/obsws assenti).*

- [x] Console regia — explainability, override informato & UX tablet: score-bar/leaderboard per-camera con stati tracking/coast/lost (WHY-02), motivo in italiano da `status.reason` via mappa (WHY-01), overlay bbox dog-lock per tile da `cams[].box` (WHY-03), hint "Auto vuole: {cam}" + marker tile durante override (WHY-04), striscia switch-history dal ring `cuts` di `/preview` newest-first (MVW-05); ogni tile del multiview è un controllo force-cam **informato** (tap-to-force sull'intera tile, pulsanti "Forza" ciechi rimossi, undo "Rilascia (auto)" sempre visibile) (MVW-04); anteprima live dell'overlay punteggio come apparirà su OBS — mirror JS **byte-exact** di `render_overlay_text` con drift-guard one-shot su `POST /score/preview` (rotta pura, nessuna scrittura canale) (SCV-01); restyling **tablet-first** landscape + contratto touch (viewport-fit, touch-action, target ≥44/48px, safe-area) (UXT-01); igiene long-run: refresh decode-swap **leak-free** (un preloader persistente per tile), watchdog di freschezza gen-age (un frame congelato non è MAI "live"), stamp "agg. {n}s fa"/"frame non aggiornato", resume sleep/wake `visibilitychange`+`pageshow`/`pagehide` con fetch differito ~200ms (UXT-03) — *validato in Phase 9 (MVW-04/05, WHY-01..04, SCV-01, UXT-01/03): 13/13 must-have, suite UI 76/76 verde, crash-isolation preservata; accettazione on-device su iPad reale (iPadOS 26.x: memoria flat, deferral 200ms ok); una review adversariale 10-agent ha trovato e corretto un bug WHY-02 — lo stato "coast" della leaderboard era morto sui dati live per mismatch `coasting`/`coast` (commit d6e7555). Review codice fase: 0 critical, 6 warning advisory (proprietà dello stato CSS tile markTiles/renderAutoWants, POST override silenziosi) — non bloccanti.*

### Active

<!-- Milestone v1.2 "Overlay Grafico Broadcast" in corso (Fasi da Phase 10). Requisiti dettagliati con REQ-ID in REQUIREMENTS.md. -->

- [ ] **Overlay grafico broadcast** servito come OBS browser-source dalla console crash-isolated (route `/overlay` + `/overlay-json`), lower-third per disciplina, sfondo trasparente — *v1.2*
- [ ] **Timer di run client-side** che conta da solo (da `run_started_at` + `running` del `RunState`), zero compute sul director — *v1.2*
- [ ] **Animazioni** ingresso/uscita lower-third + pulse sul cambio punteggio, reazione agli edge run start/stop — *v1.2*
- [ ] **`overlay.txt` come fallback degradato** mantenuto (SCR-01) — *v1.2*
- [ ] **SCV-01 unificato** — console-preview e OBS-overlay sullo stesso renderer HTML — *v1.2*
- [ ] **Scene OBS curate** — nuovo `obs/segugio-scene-collection.json` con browser-source cablata + `docs/obs-setup.md` aggiornato — *v1.2*
- [ ] Deliverable meta (carry-over v1): rifinire il README di progetto — *largamente presente (src-layout, requirements.txt/pyproject, docs/obs-setup.md, docs/run.md, entry point `python -m segugio`).*

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
- **Performance**: loop decisionale AI < **300ms** p95 (budget rivisto da <150ms il 2026-06-13 dopo la misura Phase 6: FP16+batch eager ~256ms con ReID nativa sul RTX 4000 Ada Laptop; engine TensorRT ~197ms opzionale; <150ms raggiungibile su GPU desktop di deploy); video glass-to-glass ~150-350ms accettato — Vincolo fisico riformulato ("<50ms" → "<150ms" → "<300ms").
- **Hardware**: GPU NVIDIA CUDA (disponibile in dev); produzione consigliata su Windows; codice OS-agnostic — Per maturità ecosistema NDI/OBS.
- **Dependencies**: OBS Studio + plugin DistroAV (NDI); obs-websocket v5; modello YOLO pre-addestrato fornito via config — Componenti esterni richiesti dal brief.
- **Robustezza live**: nessun crash ammesso; caduta feed → degrado a scena SAFE / fallback — Requisito live esplicito.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Milestone v1 = Fasi 0-4 (software su dati sintetici) | Testabile senza hardware su questo box; sblocca subito il lavoro | ✓ Good — v1.0 software-complete su clip + NDI mock, 6/6 fasi |
| OBS-as-hub + Python ingest NDI separato per l'AI | Mantiene OBS come hub video richiesto, cross-platform; accetta "decode due volte" | ✓ Good — wiring validato in Phase 5 |
| Latenza riformulata in due budget separati | <50ms end-to-end è impossibile (cattura smartphone ~57-106ms da sola) | ⚠️ Revisit — budget AI rivisto ancora (<150ms → <300ms) dopo la misura Phase 6; RBT-05 met <300ms |
| Un tracker YOLO per camera (no lista di frame a `track()`) | Una lista di frame costruisce un solo tracker e mescola gli ID tra camere (#13107) | ✓ Good — `PerCameraTracker` + batched-detect adapter #13107-safe |
| Liveness via timestamp ultimo frame, non stato NDI | NDI tiene la sorgente 75min ripetendo l'ultimo frame → falso "vivo" | ✓ Good — `FeedWatchdog` su last-NEW-frame ts (RBT-01) |
| Override manuale + auto-resume nonostante "senza operatore" | Sicurezza live: auto è il default, l'umano può forzare e poi rientra in auto | ✓ Good — RBT-03 in Phase 3; reso *informato* (tap-to-force) in v1.1 |
| Punteggi via inserimento manuale → file read-from-file | Tiene gli update fuori dal budget websocket; nessun sistema scoring esterno in v1 | ✓ Good — SCR-01..04 in Phase 5 |
| obsws-python (ReqClient sincrono) come canale di controllo | Semantica bloccante + timeout, EventClient thread-safe; ideale per un controller | ✓ Good — OBS-01..05 in Phase 5 |
| Output solo preview in v1 | Sufficiente a validare la regia automatica senza requisiti di rete/bitrate | ✓ Good — confermato |
| ReID nativo BoT-SORT incluso in v1 (no re-ID pesante) | Gratis (feature del detector, zero pesi) e contrasta il problema #1: cane che esce/rientra/occluso | ✓ Good — hard gate verifica l'engagement, no fallback silenzioso |
| Competitor-lock + zone-gating come feature di prima classe | Lo scorer size+centratura aggancia handler/cani spettatori → selezione del cane "in gara" va progettata, non emergente | ✓ Good — `CompetitorLock` + `PlausibilityGate` (TRK-04/05) |
| Curated multi-condition clip set assemblato in P0 | De-risk decisivo: clip pulite mascherano ogni pitfall fino al campo | ✓ Good — 7×2 condition checklist + cataloguer (TST-01) |
| Modello YOLO concreto v1 = yolo26s.pt, classe dog=16 | Small (non nano) per soggetto piccolo/distante; COCO dog sufficiente finché l'eval non prova il contrario | ⚠️ Revisit — recall debole su distante/crowd (UAT P04); candidato fine-tune dog detector |
| [v1.1] Console Regia = problema di *publish-and-render*, non di compute | L'orchestrator già calcola score/bbox/reason ogni tick e tiene i frame decodificati; v1.0 li scartava | ✓ Good — nuovo canale off-tick espone dati già esistenti |
| [v1.1] Trasporto preview = polling JPEG sul canale file opcomm | MJPEG/WebSocket/OBS-multiview-embed rompono/affaticano la crash-isolation o aggiungono un server di rete sul director (research RESPINTI) | ✓ Good — validato on-device su iPad (memoria flat) |
| [v1.1] "Why" data in un sidecar `preview.json` separato, non in `status.json` | `status.json` è safety-critical write-on-change; non va gonfiato con dati di preview | ✓ Good — PRV-02; `status.json` byte-stable |
| [v1.1] `threaded=True`/Waitress è un controllo di SICUREZZA, non polish | L'override POST non deve mai essere bloccato da uno stream preview | ✓ Good — UXT-02; provato con un test di concorrenza |
| [v1.1] Cap banda preview come garanzia config-time (no throttle runtime) | La preview deve degradare *prima* che i feed NDI sembrino morti; fail-fast è più semplice e onesto | ✓ Good — `max_total_mbps` + `@model_validator` → SystemExit(2) |

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
*Last updated: 2026-06-14 — **Phase 10 (Overlay Data Contract & Run-Timestamp Publish) complete & verified** (4/4 must-haves: `overlay_run.json` run-edge stamp with director-read `runstate.json` untouched, boundary-safe `GET /overlay-json` with `server_now`+`gen`, crash-isolation re-verified; code-review Critical NaN-boundary fix applied). Next: `/gsd-discuss-phase 11`. Earlier this milestone: **v1.2 "Overlay Grafico Broadcast" avviata** (overlay grafico via OBS browser-source dalla console crash-isolated, timer client-side, scene OBS curate; numerazione fasi continua da Phase 10). Stato precedente: after the **v1.1 "Console Regia" milestone** (Phases 7–9: PRV-01/02/03, MVW-01..05, WHY-01..04, SCV-01, UXT-01/02/03). Milestone audit `tech_debt` / `gaps: []`, 16/16 requirements satisfied in code, tagged `v1.1`. v1.0 MVP (Phases 1–6, software-complete on synthetic data) recorded retroactively at this close. Carry-forwards (all hardware/field-gated, tracked in STATE.md → Deferred Items): on-rig PRV-01 p95, real-YOLO/clip recall (P04), NDI/OBS field (P05), preview-bandwidth false-death with real phones, desktop deploy GPU for sustained live, 2 environmental NDI-loopback CI failures, 6 advisory Phase-9 code-review warnings. Next: `/gsd-new-milestone`.*
