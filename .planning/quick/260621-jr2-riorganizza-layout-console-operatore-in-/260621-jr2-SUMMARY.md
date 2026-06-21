---
phase: quick-260621-jr2
plan: 01
subsystem: ui/console
tags: [ui, layout, css, tablet, console]
requires: [src/segugio/ui/templates/console.html]
provides: ["Console operatore a stack verticale 3 fasce (info / ON AIR / multiview / controlli)"]
affects: [src/segugio/ui/templates/console.html]
tech-stack:
  added: []
  patterns: ["CSS grid single-page vertical stack", "responsive collapse at 1024px breakpoint"]
key-files:
  created: []
  modified: [src/segugio/ui/templates/console.html]
decisions:
  - "Solo ristrutturazione contenitori + CSS: blocco <script> byte-identico, nessun id rinominato/rimosso"
  - "info-strip 4 colonne / control-strip 3 colonne, collassano (2col / 1col) sotto il @media (max-width:1024px) riusato"
  - "safe-area-inset-bottom/right migrati da .cluster-bottom (rimossa) a .control-strip"
metrics:
  duration: ~6min
  completed: 2026-06-21
requirements: [UXT-01]
---

# Quick 260621-jr2: Riorganizza layout console operatore (single-page 3 fasce) Summary

Ristrutturata `console.html` da griglia 2-colonne (multiview + sidebar in overflow "multi-pagina") a uno stack verticale a 3 fasce — 4 card info in orizzontale → banner ON AIR → multiview centrato → 3 card controllo in orizzontale — così su tablet landscape la console sta in una sola schermata senza scroll della sidebar. Solo markup contenitori + CSS; `<script>` invariato.

## What Was Built

- **BAND 1 — `.info-strip`**: 4 `<section class="sidebar-block">` in riga (4 colonne) sopra il banner ON AIR, nell'ordine Motivo (`#reason`) / Punteggi framing (`#leaderboard`) / Auto vuole (`#auto-wants`) / Cambi recenti (`#switch-history`). Riusa `.sidebar-block`.
- **BAND 2 — banner ON AIR** (`.onair` / `#onair-cam`) spostato sotto la info-strip.
- **BAND 3 — multiview** (`#multiview` col loop Jinja `{% for cam in cam_ids %}` e tutti i per-tile id) centrato sotto ON AIR (`margin: 0 auto; justify-content: center; max-width: 1280px`).
- **BAND 4 — `.control-strip`**: 3 card in riga (3 colonne) sotto il multiview:
  - (a) Punteggio: `#form-score` con dentro selettore `#disciplina`, le 3 `.campi`, l'anteprima overlay (`iframe src="/overlay?preview=1"`) e il submit.
  - (b) Run + Rilascia: i due `.run-btn` (start/stop) e `#rilascia` uniti in UNA sola `<fieldset><legend>Run + Rilascia</legend>`.
  - (c) Stato live: `<fieldset>` con `#stato`/`#live-cam`/`#live-reason`/`#feeds`/`#freshness`.
- **CSS**: aggiunte `.info-strip` (grid 4col, gap 16px) e `.control-strip` (grid 3col, gap 16px, safe-area padding); multiview centrato; rimossa la regola `.layout` (2col) e la `.cluster-bottom` (non più usata, safe-area migrato su `.control-strip`); il `@media (max-width: 1024px)` riusato ora fa collassare info-strip→2col e control-strip→1col.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Ristruttura body in stack verticale 3 fasce | 33379b1 | src/segugio/ui/templates/console.html |
| 2 | CSS responsivo strisce (4col/3col → collasso 1024px), niente font-weight 500/600 | 33379b1 | src/segugio/ui/templates/console.html |
| 3 | Verifica statica finale (import + render + grep id + niente 500/600) | (no code) | — |

Le modifiche di Task 1 e Task 2 sono nello stesso file e committate insieme in un unico commit atomico `33379b1` (come da vincolo: commit del solo `console.html`).

## Verification

Tutte le verifiche STATICHE (read-only), senza alcuna interazione col processo live :8080 né con l'orchestratore (PID `run-logs/orch.pid`):

- Render Jinja con `cam_ids=['cam_wide','cam_long','cam_low','cam_handler']` → OK, nessuna eccezione.
- `import segugio.ui.app` (venv CPU `venv\Scripts\python.exe`) → OK.
- Tutti gli id referenziati dallo `<script>` presenti: `onair-cam, reason, leaderboard, auto-wants, switch-history, multiview, form-score, disciplina, rilascia, stato, live-cam, live-reason, feeds, freshness` + per-tile (`tile-/img-/badge-/bbox-/rect-/ribbon-/autotag-/stale-{cam}`) per ogni cam + iframe `/overlay?preview=1`.
- `.info-strip` grid 4 colonne, `.control-strip` grid 3 colonne, breakpoint `@media (max-width: 1024px)` riusato.
- Nessun `font-weight: 500` o `font-weight: 600` nel file (solo 400 e 700).
- `<script>` invariato: il diff non tocca nessuna riga `getElementById`/`addEventListener`/`<script>`/`function`.

## Deviations from Plan

**1. [Rule 3 - Blocking cleanup] Rimossa la regola CSS `.cluster-bottom`**
- **Found during:** Task 2
- **Issue:** il wrapper `.cluster-bottom` è stato eliminato dal markup (Task 1), lasciando la sua regola CSS orfana; conteneva il `safe-area-inset-bottom/right` da preservare.
- **Fix:** rimossa la regola morta e migrato `padding-bottom/padding-right: env(safe-area-inset-*)` su `.control-strip` (come indicato dal Task 2), mantenendo intatto `#rilascia` (min 48px).
- **Files modified:** src/segugio/ui/templates/console.html
- **Commit:** 33379b1

Per il resto il plan è stato eseguito esattamente come scritto.

## Manual Step (optional, NOT performed)

Per **vedere** il nuovo layout, il processo console va riavviato manualmente (Flask/Jinja può aver cache-ato il template):

```
venv\Scripts\python.exe -m segugio.ui.app
```

PID in `run-logs/console.pid`. Il riavvio NON è stato eseguito automaticamente; nessun POST verso :8080; l'orchestratore (`run-logs/orch.pid`) non è stato toccato.

## Self-Check: PASSED

- FOUND: src/segugio/ui/templates/console.html (modificato, render+import OK)
- FOUND: commit 33379b1
