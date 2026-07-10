# Requirements: Segugio — Milestone v1.4 "Validazione sul Campo" (Field Readiness)

**Defined:** 2026-07-09
**Core Value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.

**Milestone goal:** Portare Segugio da *software-complete* a *field-proven* — misurare la detection su footage reale e decidere il fine-tune, poi provare l'intero rig fisico (telefoni NDI HX3 + WiFi + OBS + GPU di deploy) in una gara reale/simulata, chiudendo le UAT hardware finora rimandate.

> **Nota di esecuzione:** le categorie **RIG** e **UAT** richiedono hardware fisico (telefoni, WiFi dedicata, OBS, GPU di deploy) e vanno eseguite **sul rig**, non sul box di sviluppo. **DET**, **CAL** e **SEC** sono lavoro da scrivania (footage reale + codice) eseguibile senza il rig completo, ma DET/CAL richiedono footage reale procurato.

## v1 Requirements

Requisiti per questa milestone. Ognuno mappa a una fase della roadmap.

### DET — Eval Detection & Decisione Fine-tune

- [ ] **DET-01**: Un corpus di footage reale multi-venue è catalogato via `tools/catalog_clips.py` con una checklist di condizioni — disc **e** agility, coprendo il cane distante/piccolo, il controluce, il motion-blur, il multi-cane e l'occlusione tunnel (oggi il corpus è UN solo clip `gara_full.mp4`).
- [ ] **DET-02**: Un sottoinsieme rappresentativo del corpus ha ground-truth etichettata (bbox del cane "in gara") come riferimento per misurare recall e precision reali.
- [ ] **DET-03**: Recall **e** precision sono misurate sul path **FP16 batched shipped** (non l'eager FP32 seriale della UAT P04) — recall sul cane distante e false-lock su conduttore/ombra, riportate per condizione (non solo il proxy `lock_held`).
- [ ] **DET-04**: È documentata una decisione motivata sul fine-tune di `yolo26s` (fine-tune vs no) basata sulle metriche DET-03; se si decide il fine-tune, il weight è drop-in via la config `path` senza modifiche al codice.

### CAL — Calibrazione Framing/Tracking

- [ ] **CAL-01**: I seed di framing (`ideal_size`, `motion_deadzone`, lead-room) sono ri-calibrati sulla scala reale del cane distante (2-5% del frame, non 0.30) e validati mantenendo l'inquadratura su clip reali.
- [ ] **CAL-02**: I seed di tracking (`track_buffer`, `max_displacement`, plausibility gate) sono tarati su occlusioni/tunnel reali senza ID-churn spurio (il cane che esce/rientra resta lo stesso track).

### RIG — Rig Hardware End-to-End *(richiede hardware sul rig)*

- [ ] **RIG-01**: L'orchestratore decodifica feed NDI HX3 reali da 3-4 telefoni (NDICam iOS / NDI Camera Android, runtime NDI 6.3.2) — feed vivi, liveness dedotta dal timestamp dell'ultimo frame *nuovo* (mai dallo stato sorgente NDI).
- [ ] **RIG-02**: La pipeline gira end-to-end sul rig — telefoni → OBS+DistroAV (PROGRAM) + Python ingest indipendente (AI) → switching della scena OBS via obs-websocket — commutando la camera giusta senza operatore.
- [ ] **RIG-03**: Il p95 del loop decisionale è confermato < 300ms sulla **GPU di deploy** sotto carico sostenuto (nessun throttle termico come sul laptop); se si usa l'engine TensorRT, è esportato sulla GPU target.
- [ ] **RIG-04**: Robustezza WiFi reale — con 3-4 feed che contendono la rete, la caduta di un feed degrada a scena SAFE / altra camera viva senza crash; la preferenza Ethernet (adattatore USB-C/Lightning) dove il telefono è tetherabile è documentata come mitigazione.

### UAT — Chiusura UAT On-rig Deferite *(richiede hardware sul rig)*

- [ ] **UAT-01**: Le UAT overlay v1.2 sono firmate con OBS reale — console-death auto-hide (nessun punteggio congelato in onda), LAN-drop re-anchor del timer via `gen`, e coesistenza `overlay.txt` text-source come fallback.
- [ ] **UAT-02**: La console tablet-UX è confermata su un iPad reale (iPadOS) in sessione prolungata — multiview, tap-to-force override e score-entry modal usabili, memoria flat, resume sleep/wake ok.
- [ ] **UAT-03**: Il preview-bandwidth false-death è validato con telefoni veri — la preview degrada *prima* che i feed NDI sembrino morti (il cap `max_total_mbps` protegge i feed reali).

### SEC — Hardening Security Residui

- [ ] **SEC-01**: La scoring-validation ha bounds espliciti (residual P15) — input numerici fuori-range rifiutati con il contratto 400 + write-nothing, senza toccare il punteggio in onda.
- [ ] **SEC-02**: L'echo di `/overlay-json` ha un length-cap (residual P16) — i campi free-text riflessi sono troncati a un limite bounded.

## v2 Requirements

Riconosciuti ma rimandati; non in questa roadmap.

### SCM — Roster / Classifica / Multi-giudice

- **SCM-F2**: Roster concorrenti + classifica/standings (oggi solo singolo punteggio in onda).
- **SCM-F1**: Freestyle multi-giudice (oggi single-judge multi-criterio).

### PRED — Framing Predittivo & Disc

- **PRED-01**: Framing predittivo da velocità/traiettoria del cane.
- **PRED-02**: Disc/frisbee-detection come predittore del punto di presa (pre-frame catch zone).
- **PRED-03**: Framing obstacle-aware con ordine del percorso agility.
- **PRED-04**: Replay/highlight markers.

### POSE — Pose & Intent

- **POSE-01**: Dog-pose (heading/intent) per framing/anticipazione (modello `yolo26s-pose` + Dog-Pose dataset).

## Out of Scope

Esclusioni esplicite per questa milestone.

| Feature | Motivo |
|---------|--------|
| Nuove feature utente (roster, PRED, pose) | v1.4 è validazione/hardening di ciò che esiste, non nuove capability — restano in v2. |
| Output recording/streaming (RTMP/YouTube) | Fuori scope da v1; l'output reale si definisce dopo. |
| Integrazione scoring esterno (API) | Punteggi restano a inserimento manuale. |
| Re-ID pesante (modello dedicato) | Il ReID nativo BoT-SORT resta sufficiente per singolo cane; il fine-tune DET-04 riguarda il detector, non il ReID. |
| Modifiche architetturali al director oltre a quanto serve per il rig | La console resta crash-isolated; v1.4 non ridisegna, valida. |

## Traceability

Quali fasi coprono quali requisiti. Popolato dal roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DET-01 | Phase 19 | Pending |
| DET-02 | Phase 19 | Pending |
| DET-03 | Phase 19 | Pending |
| DET-04 | Phase 19 | Pending |
| CAL-01 | Phase 20 | Pending |
| CAL-02 | Phase 20 | Pending |
| SEC-01 | Phase 21 | Pending |
| SEC-02 | Phase 21 | Pending |
| RIG-01 | Phase 22 | Pending |
| RIG-02 | Phase 22 | Pending |
| RIG-03 | Phase 22 | Pending |
| RIG-04 | Phase 22 | Pending |
| UAT-01 | Phase 23 | Pending |
| UAT-02 | Phase 23 | Pending |
| UAT-03 | Phase 23 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15 ✓ (Phase 19: DET-01..04 · Phase 20: CAL-01/02 · Phase 21: SEC-01/02 · Phase 22: RIG-01..04 · Phase 23: UAT-01..03)
- Unmapped: 0 ✓ (no orphans, no duplicates)

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 — roadmap mapped (Phases 19–23, numbering continued from v1.3); 15/15 requirements covered.*
