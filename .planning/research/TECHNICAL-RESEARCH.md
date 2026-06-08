# Technical Research — Segugio

> Ricerca tecnica condotta a inizio progetto (multi-fonte: docs ufficiali via context7 + web). Lo **stack è considerato deciso**; gli agenti di dominio non devono ri-ricercarlo, solo completarlo lato dominio. Fonti chiave: docs obs-websocket v5, obsws-python, Ultralytics, NDI SDK/cyndilib.

## Stack tecnico (deciso)

| Modulo | Librerie | Note chiave |
|--------|----------|-------------|
| ndi_ingest | `cyndilib`, `opencv-python`, `numpy` | FrameSync (always-latest, droppa frame intermedi) perché l'AI gira <30fps; ricevi BGRA + un `cv2.cvtColor`. Runtime Linux: libndi 6 + avahi-daemon (mDNS) + ffmpeg. |
| yolo_inference | `ultralytics`, `torch`, `tensorrt` | **Un tracker per camera** (`model.track(frame, persist=True, classes=[dog_id])`), NON una lista di frame (mescola gli ID, issue #13107). Verifica l'indice classe via `model.names` (custom mono-classe ≈ 0, NON il 16 di COCO). Export `.pt`→engine TensorRT FP16 **sulla GPU di deploy**. |
| framing_scorer | `numpy` | Score da segnali normalizzati: `size = wn*hn`, `centeredness = 1 - dist((cxn,cyn),(0.5,0.5))`, gated by conf; EMA per camera (alpha ~0.3). Puro, no I/O → unit-testabile. |
| decision_engine | `transitions`, `pyyaml` | FSM unica fonte di verità. Guard LIVE_i→LIVE_j = (challenger-live)>hysteresis_margin AND time_in_state>=min_dwell AND consecutive_wins>=debounce_N AND cooldown_elapsed AND feed_j_alive. Dead-band a due soglie contro il ping-pong. |
| obs_controller | `obsws-python` | `ReqClient` sincrono (timeout integrato) + `EventClient` su thread. Cut = `SetCurrentProgramScene`. PIP/multi-view = `SetSceneItemTransform` (bounds) + `SetSceneItemEnabled` con **sceneItemId numerico cachato** (risolto via `GetSceneItemId` all'avvio). Testo = `SetInputSettings({"text":...}, overlay=True)`. |
| score_manager | `pyyaml`, `watchdog` | Overlay via text source OBS "read from file" + scrittura atomica (`os.replace`) → update fuori dal budget websocket. Path websocket solo per testi one-shot. |
| feed_watchdog | `numpy` | Liveness da timestamp ultimo frame **nuovo**, mai dallo stato sorgente NDI (TTL 75min, ripete l'ultimo frame). Morto dopo ~0.5-1.0s, con grazia anti-jitter (>25ms in contention). |
| orchestrator | `pyyaml`, `loguru` | Tick a rate fisso (~30Hz), try/except su ogni receive/websocket, restart supervisionati, scena SAFE su condizione irrecuperabile. |

**Cosa NON usare:** `obs-websocket-py` (Elektordi) è v4, non v5. Evitare `SetTextGDIPlusProperties` (rimosso in v5). Evitare di passare liste di frame a `model.track()`.

## Architettura — due pipeline disaccoppiate

- **VIDEO (non ottimizzata):** telefono HX3 → OBS (DistroAV) → program → output. Trattata come black-box ~150-350ms glass-to-glass.
- **CONTROL (l'unica ottimizzata):** ndi_ingest (ultimo frame) → yolo_inference → framing_scorer → decision_engine → obs_controller. Gira su frame che OBS ha già → budget indipendente dal glass-to-glass.

**Decisione OBS-as-hub:** i telefoni pubblicano NDI HX3; OBS riceve nativamente via DistroAV per il PROGRAM, Python riceve le stesse sorgenti via cyndilib **solo per l'AI** → "decode due volte" accettato (economico con NVDEC, cross-platform). Alternativa scartata (Python unico ricevitore + re-emit a OBS via Spout/virtual-cam): Windows-biased, single-instance virtual-cam caveat, hop di re-encode sul path PROGRAM critico.

## Verdetto latenza

- **sub-50ms end-to-end glass-to-glass = IMPOSSIBILE.** La sola cattura smartphone è ~57-106ms photon-to-frame; NDI HX3 ha target ~100ms solo camera→monitor.
- **Riformulazione in due budget:** (1) video glass-to-glass ~150-350ms inerente, si accetta; (2) loop decisionale AI ~70-150ms, ottimizzabile a ~50-80ms (TensorRT FP16 nano, NVDEC, comandi websocket async su connessione persistente — il round-trip obsws-python ~35-60ms è la coda dominante). Obiettivo prodotto: loop AI < ~150ms (ideale <80ms).

## Rischi tecnici principali

| Sev | Rischio | Mitigazione |
|-----|---------|-------------|
| 🔴 | Falsa liveness NDI (telefono caduto sembra vivo, TTL 75min) | feed_watchdog su timestamp ultimo frame; mai fidarsi dello stato sorgente NDI; FSM→FALLBACK su morte |
| 🔴 | Confusione track-ID multi-stream (#13107) | un tracker per camera; filtro classe cane; BoT-SORT per re-ID dopo occlusione |
| 🔴 | WiFi packet loss/jitter con 3-4 telefoni | SSID dedicato 5GHz/WiFi 6E solo telefoni; sender HX3 low-latency (I+P, no B-frame); reconnect supervisionato |
| 🟡 | Flicker/cut a raffica | tutti i cambi via FSM (dead-band isteresi + dwell 2-3s + debounce + cooldown); tunabili da config |
| 🟡 | Doppio decode HX3 (OBS + Python) | route il secondo decode su NVDEC; misurare utilizzo WiFi all'AP; eventualmente ridurre risoluzione/fps del solo path AI |
| 🟡 | Latenza/throughput websocket | connessione persistente con reconnect; comandi fuori dal loop di inferenza; <200 msg/s; transizioni cut |

## Dettagli obs-websocket v5 (verificati)

- Connessione `ws://localhost:4455` + handshake Hello/Identify/Identified; rpcVersion 1. obsws-python: `ReqClient(host, port, password, timeout)`.
- Text input kind platform-specific (`text_gdiplus_v2` Windows, `text_ft2_source_v3` Linux) ma il campo `text` è identico → **non hardcodare il kind**, `SetInputSettings({"text":...})` funziona comunque; scoprire via `GetInputKindList` se serve.
- `SetSceneItemEnabled`/`SetSceneItemTransform` richiedono `sceneItemId` numerico (non il nome) → risolvere e cachare, refresh su eventi SceneItemCreated/Removed.
- Latenza comando localhost ~1-10ms; su LAN dominata dall'RTT.

---
*Persisted: 2026-06-09 — technical research baseline (stack locked).*
