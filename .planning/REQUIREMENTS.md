# Requirements: Segugio — v1.3 Gestione Punteggi Avanzata

**Defined:** 2026-06-21
**Core Value:** La camera giusta al momento giusto, in automatico — cane sempre ben inquadrato, cut fluidi, senza operatore.

> **Milestone v1.3 = gestione punteggi avanzata.** La score-entry diventa un componente **ricco** e **condiviso** — stessa UI in una **pagina dedicata** e in un **popup/modal** della console — con totali **auto-calcolati**, **multi-lancio/round**, **validazione per disciplina** e **freestyle multi-criterio (giudice singolo)**. Continua a pubblicare il **singolo punteggio corrente** all'overlay (no roster/classifica).
>
> **Decisione keystone — SERVER-AUTORITATIVO:** il client POSTa input *grezzi*; `POST /score` valida (400 + nessuna scrittura su invalido) e **ricalcola** i totali in Python (`decimal`, mai float), poi scrive atomico `score.json` + `overlay.txt`. Il calcolo live lato client è **solo advisory** (parità garantita da un drift-guard test). Così il totale in onda e la validazione non possono divergere né essere bypassati.
>
> **Config-driven:** le regole di scoring (zone/punti T&F, criteri/scale freestyle, faults/SCT agility, modello agility) vivono in un **"profilo di scoring"** per disciplina/federazione (estende il discriminated-union pydantic CFG-03) — cambiare federazione non richiede codice.
>
> **Vincolo HARD invariato:** la console resta crash-isolated (importa SOLO `Flask + segugio.opcomm` + il nuovo modulo **puro** `score_calc` stdlib-only); il director non viene mai importato/toccato; *publish-and-render* sopra il canale `opcomm`-su-file; trasporto = fetch-polling (no WebSocket/SSE/MJPEG). Nessuna nuova dipendenza runtime. Vedi `.planning/research/v1.3/SUMMARY.md`. **Numerazione fasi continua da Phase 15.**

## v1.3 Requirements

### Componente score-entry condiviso (SCE)

- [ ] **SCE-01**: L'operatore inserisce il punteggio sia da una **pagina dedicata** sia da un **popup/modal** nella console, entrambi che montano lo **stesso** componente vanilla-JS condiviso → nessun drift (niente mirror byte-exact ri-introdotto, niente iframe per il form interattivo; lezione SCV-02 applicata a un form)
- [ ] **SCE-02**: Il componente mostra i **campi strutturati ricchi** della disciplina selezionata (disc Toss&Fetch, disc freestyle, agility), guidati dal profilo di scoring
- [ ] **SCE-03**: **Calcolo live advisory** lato client — il totale si aggiorna mentre l'operatore digita (feedback immediato), esplicitamente *non autorevole*
- [ ] **SCE-04**: **Pubblicazione esplicita** — un'azione chiara "manda in onda" il punteggio (nessuna messa in onda accidentale); UX tablet-first (input ≥16px anti-zoom iOS, focus-trap nel modal, **asset offline/no-CDN** per il rig senza internet)
- [ ] **SCE-05**: Gli **errori di validazione** sono mostrati per campo all'operatore prima/della pubblicazione

### Calcolo & validazione autorevoli (SCC)

- [ ] **SCC-01**: `POST /score` è **autorevole**: valida gli input grezzi (400 + niente scrittura su invalido), **ricalcola** i totali in Python (`decimal`), e solo allora scrive atomicamente `score.json` + `overlay.txt`
- [x] **SCC-02**: Modulo **puro** `score_calc` (solo stdlib, nessuna heavy dep) che incapsula calcolo + validazione, condiviso dal server e **aggiunto alla superficie import crash-isolated** (coperto dall'import-smoke gate) — *Plan 15-01: modulo puro stdlib costruito (import allowlist = decimal/re/dataclasses/enum + opcomm.records, zero `float(`). Plan 15-03: `segugio.ui.score_calc` aggiunto a `PHASE1_SURFACE` (parametrized heavy-deps-absent import) — chiuso.*
- [ ] **SCC-03**: Port client `score-calc.js` per il calcolo advisory, con **drift-guard test** che ne garantisce la **parità** col modulo Python (no doppia verità)
- [x] **SCC-04**: **Totali auto-calcolati per disciplina** — disc T&F: somma lanci×zone (+ bonus); freestyle: somma criteri (giudice singolo); agility: modello configurabile (count-up faults *oppure* deduct) + time-faults vs SCT — *Plan 15-01: `score_calc.compute()` Decimal-exact per le 3 discipline, 11/11 unit test verdi vs tabelle CSEN pinnate.*
- [ ] **SCC-05**: **Multi-lancio/round** con totale progressivo (disc T&F a N lanci); stato in-progress robusto (scrittura atomica; restore lato client su reload)

### Profili di scoring config-driven (SCP)

- [x] **SCP-01**: Le regole di scoring sono **config-driven** via un "profilo di scoring" per disciplina/federazione (estende il pattern discriminated-union CFG-03), così zone/punti/criteri/faults/modello cambiano senza modifiche al codice — *Plan 15-02: sub-model pydantic `ScoringProfile` aggiunto additivamente all'union CFG-03 + adapter `adapt_scoring_profile` (D-10); fixture CSEN/FIDASC/FCI; `test_profile_swap_changes_result` prova lo swap CSEN→FIDASC (totale CSEN `23.5` ≠ FIDASC, 4 divergenze strutturali) senza modifiche al codice.*
- [x] **SCP-02**: Un **profilo di default** sensato ship con v1.3; il profilo è validato **fail-fast** a config-load (errore chiaro su profilo malformato) — *Plan 15-02: default CSEN 2026 pinnato; `test_malformed_profile_fails_fast` → `SystemExit(2)` su profilo malformato; rafforzato in code-review fix (CR-02/CR-03: `count_best_n` `Field(ge=1)`, `per_throw_cap` `Field(gt=0)` → fail-fast su valori negativi/zero).*

### Continuità & robustezza (RBT)

- [x] **RBT-08**: La **crash-isolation è preservata e ri-verificata** — la console importa solo `Flask + segugio.opcomm` + `score_calc` (puro); l'import-smoke test è esteso ai nuovi moduli/route e `POST /score` risponde anche con lo stack pesante assente (torch/cv2/ultralytics/numpy/cyndilib/obsws) — *Plan 15-03: `test_console_resolves_with_heavy_stack_and_numpy_absent` esteso con `import segugio.ui.score_calc` + round-trip `POST /score` (200/204) sotto il blocco heavy+numpy+cv2 forced-absent.*
- [ ] **RBT-09**: Il **fallback degradato `overlay.txt`** e i contratti **`/overlay` + `/overlay-json`** restano invariati (regressione verificata); i nuovi campi free-text (es. nome cane/handler, giudici) sono **HTML-escaped al sink** dell'overlay

## Future Requirements

Rimandati a una release futura. Tracciati ma non nella roadmap v1.3.

### Score Management avanzato

- **SCM-F1**: Freestyle **multi-giudice** (media / scarta-alto-basso) + breakdown per-categoria nell'overlay
- **SCM-F2**: **Roster / start-list** concorrenti (cani/conduttori) + **classifica/standings** persistenti

## Out of Scope

Esclusioni esplicite per la v1.3. Documentate per prevenire scope creep.

| Feature | Reason |
|---------|--------|
| Roster concorrenti / classifica / standings | Confine di milestone: la v1.3 gestisce solo il **singolo punteggio in onda**. Rimandato (SCM-F2). |
| Freestyle multi-giudice (media / drop-high-low) | v1.3 = multi-criterio **giudice singolo**; la combinazione multi-giudice è additiva, rimandata (SCM-F1). |
| Adjudication via CV (calcolo automatico di prese/zone/faults dal video) | Hard line di progetto (SCR-04): il sistema **mostra** i punteggi, non li giudica. |
| WebSocket / SSE / MJPEG per il canale punteggi | Romperebbe la crash-isolation / affamerebbe `POST /command` (UXT-02); resta fetch-polling + file opcomm (rifiuto v1.1/v1.2 ri-applicato). |
| Nuove dipendenze runtime | Non necessarie: stdlib + pydantic (già presente) lato server, vanilla JS + native `<dialog>` lato client. |
| Tocco/import del director-orchestrator | Vincolo HARD: la console resta *publish-and-render* sul canale opcomm; il director non viene mai importato o modificato. |

## Traceability

Quali fasi coprono quali requisiti. Popolata durante la creazione della roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCE-01 | Phase 16 | Pending |
| SCE-02 | Phase 16 | Pending |
| SCE-03 | Phase 16 | Pending |
| SCE-04 | Phase 17 | Pending |
| SCE-05 | Phase 16 | Pending |
| SCC-01 | Phase 16 | Pending |
| SCC-02 | Phase 15 | Complete (15-01 module; 15-03 import gate) |
| SCC-03 | Phase 16 | Pending |
| SCC-04 | Phase 15 | Complete (15-01) |
| SCC-05 | Phase 17 | Pending |
| SCP-01 | Phase 15 | Complete (15-02) |
| SCP-02 | Phase 15 | Complete (15-02) |
| RBT-08 | Phase 15 | Complete (15-03) |
| RBT-09 | Phase 18 | Pending |

**Coverage:**
- v1.3 requirements: 14 total
- Mapped to phases: 14 ✓ (100% — no orphans, no duplicates)
- Unmapped: 0

**Per-phase mapping:**
- **Phase 15** (Pure Calc + Validation Core & Scoring Profiles): SCC-02, SCC-04, SCP-01, SCP-02, RBT-08
- **Phase 16** (Shared Entry Component, Dedicated Page & Server-Authoritative POST): SCE-01, SCE-02, SCE-03, SCE-05, SCC-01, SCC-03
- **Phase 17** (Console Modal, Multi-throw State & Tablet UX): SCE-04, SCC-05
- **Phase 18** (Rich Data Model & Overlay-Continuity Regression): RBT-09

---
*Requirements defined: 2026-06-21*
*Last updated: 2026-06-21 — traceability popolata dalla roadmap v1.3 (Phasi 15–18, 14/14 mappati)*
