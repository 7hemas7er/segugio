---
phase: 11-shared-graphical-renderer-overlay-page-branding
plan: 03
subsystem: ui-overlay
tags: [overlay, renderer, timer, clock-skew, freshness, sanitize, animation, html-injection]
requires:
  - "src/segugio/ui/templates/overlay.html DOM/CSS contract — #lower-third/#identity/#timer/#cells/#logo-bug + .is-entering/.is-exiting/.pulse-once/.is-live/.is-stale + window.OVERLAY_CFG.freestyleDurationS (11-02)"
  - "GET /overlay-json payload {discipline, fields (verbatim), running, started_at, server_now, gen} + no-store (Phase 10 / 11-01)"
  - "GET /overlay host page that loads /static/overlay-render.js + #identity[data-event] static event branding (11-01/11-02)"
  - "segugio.ui.score_render._clean/_get/render_overlay_text — the byte-exact per-discipline sanitize reference (Phase 9)"
provides:
  - "src/segugio/ui/static/overlay-render.js — the ONE shared score-to-DOM renderer (auto-served at /static/overlay-render.js)"
  - "JS sanitize mirror cleanField/scvGet (byte-exact ports of console.html SCV-01 / Python _clean/_get)"
  - "Offset-cancellation client timer (server_now skew-cancel; M:SS countdown freeze-at-0 / SS.hh agility overtime)"
  - "gen-age freshness watchdog isStale() that STOPS the rAF timer + applies .is-stale degrade (OVD-03 client half)"
  - "Event-only animation triggers (enter/exit on run edges, single pulse on score-change + end-of-countdown)"
  - "tests/test_ui_overlay_render.py — served-JS + node behavior assertions (sanitize parity, skew, freeze, overtime, no-innerHTML)"
affects:
  - "Phase 12 (console-preview iframe renders this same overlay.html + overlay-render.js — same timer/render behavior by construction)"
tech-stack:
  added: []
  patterns:
    - "Pure client-side ES2020 IIFE, no build step / no imports / no package install; dual export (window.SEGUGIO_OVERLAY + module.exports for node tests)"
    - "Sanitize mirror ported VERBATIM from console.html gsd:scv01-mirror block — single source of truth with Python _clean byte-exact"
    - "Every operator value written via node.textContent = cleanField(v) — NEVER innerHTML (HTML-context escape is the HIGH-severity sink mitigation)"
    - "Offset-cancellation timer: re-measure skew = server_now - Date.now()/1000 each poll, free-run on rAF between polls (never raw cross-machine subtraction, never per-poll snap)"
    - "gen-age watchdog + cold-start guard ported verbatim from console.html v1.1 freshness watchdog; stale STOPS the timer (frozen-but-ticking is the worst broadcast failure)"
    - "node-executed behavior tests (the console-test precedent) drive the served JS for byte-parity + the 30s-skew timer math"
key-files:
  created:
    - "src/segugio/ui/static/overlay-render.js"
    - "tests/test_ui_overlay_render.py"
  modified: []
decisions:
  - "Single IIFE namespace object exported as window.SEGUGIO_OVERLAY (browser) AND module.exports (node tests) — the renderer auto-mounts on DOMContentLoaded but no-ops under node (no document), so the same file is both the page script and the testable module"
  - "DISCIPLINE_CELLS table drives per-discipline cells (disc_tf prese/zona/totale; freestyle Timer; agility SCT(alias)/faults); the live elapsed clock is the separate #timer rAF — the agility SCT is a STATIC reference cell beside it with no verdict/color (D-05/SCR-04)"
  - "createRenderer(root, cfg) is the testable timer/poll instance; autoMount() wires it to document + window.OVERLAY_CFG. node behavior tests call createRenderer / the pure format helpers directly with a fake payload"
  - "Identity competitor half = verbatim scvGet(fields,'nome') for ALL disciplines; event half read from #identity[data-event] static branding (NOT /overlay-json) — empty halves hide via :empty CSS"
metrics:
  duration: 4min
  completed: "2026-06-14"
  tasks: 2
  files: 2
---

# Phase 11 Plan 03: Shared Graphical Renderer (overlay-render.js) Summary

The ONE shared score-to-DOM renderer that fills the 11-02 lower-third: it reproduces `render_overlay_text`'s per-discipline field selection plus the `_clean`/`_get` sanitize byte-exact and writes every operator value via `textContent` (closing the HIGH-severity HTML-injection sink), runs an offset-cancellation client timer that is correct across ~30s machine clock skew (T&F/freestyle count down and freeze at "Tempo"; agility counts up in `SS.hh` past SCT), and runs a gen-age freshness watchdog that STOPS the timer and degrades on stale — all pure client-side ES2020, zero director compute, zero new Python dependency.

## What Was Built

**Task 1 — sanitize mirror + per-discipline DOM render + identity line + event-only animation triggers (OVL-02/OVL-04/BRD-02), commit `0fcf618`**
- `src/segugio/ui/static/overlay-render.js` created (auto-served at `/static/overlay-render.js` by Flask's default static folder — the path the 11-02 template already references).
- Sanitize mirror copied VERBATIM from the console.html `gsd:scv01-mirror` block: `SCV_MAX_FIELD_LEN = 64`, the `SCV_NONPRINT` Unicode-property regex (keep `U+0020`, strip `\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}\p{Zs}`), `cleanField(value)` (trim + cap 64), and `scvGet(fields, ...keys)` (first-present alias) — byte-exact with Python `_clean`/`_get`.
- `DISCIPLINE_CELLS` table reproduces `render_overlay_text` field selection in DOM cells: `disc_tf` → prese/zona/totale; `disc_freestyle` → Timer (name flows to the identity line); `agility` → SCT (via `scvGet(fields,"sct","SCT")` alias) + faults. The agility SCT is a STATIC reference cell — no verdict, no color shift (D-05/SCR-04).
- Every operator value is written with `node.textContent = cleanField(v)` and updated IN PLACE on the existing cell node (FOUC/flicker avoidance — never node-rebuild on a value change). There is NO `innerHTML` anywhere (T-11-03-01 HIGH sink closed).
- Identity line (D-08/BRD-02): competitor from `scvGet(fields,"nome")` for ALL disciplines joined with the STATIC event read from `#identity[data-event]` (NOT from `/overlay-json`); empty competitor → just the event, both empty → the `:empty` CSS hides the line. Built from `textContent` nodes + a `<span class="sep">·</span>` separator.
- Event-only animation triggers (OVL-04): `animateRunEdge` adds `is-entering` on the run-start edge and `is-exiting` on the run-stop edge (+ toggles `is-live`); `pulseOnce` fires the single `pulse-once` on a score-VALUE change. One-shot classes re-trigger via remove → forced reflow → re-add. No `setInterval` visual loop, no perpetual motion.
- `tests/test_ui_overlay_render.py` Task-1 assertions: served at `/static/overlay-render.js`; the sanitize-mirror symbols + the `sct`/`SCT` alias pair present; NO `innerHTML` sink; all per-discipline field tokens referenced; and a **node-executed byte-parity check** running the served `cleanField` against `score_render._clean` across control-char / over-64-char / unicode samples.

**Task 2 — offset-cancellation timer + per-discipline direction/format + freeze-at-0/overtime + gen-age freshness watchdog + degrade + poll loop (TMR-01/02/03/04, OVD-03 client half), commit `2233106`**
- Offset-cancellation timer (TMR-04 / Pitfall 1): on each poll `skew = server_now - Date.now()/1000` is re-measured; the displayed elapsed is `Date.now()/1000 + skew - started_at`, advanced LOCALLY on a `requestAnimationFrame` loop between polls so it never snaps. NO raw cross-machine `Date.now() - started_at`.
- Per-discipline direction/format (D-03/TMR-02/TMR-03): `disc_tf` counts DOWN from 60s, `disc_freestyle` counts down from the injected `window.OVERLAY_CFG.freestyleDurationS` — both render `M:SS`, clamp at 0, fire ONE pulse at the 0 crossing, then FREEZE showing the literal "Tempo" (never negative). `agility` counts UP in `SS.hh` hundredths and CONTINUES past the operator-typed SCT into overtime (plain count-up, no color/verdict). The `#timer` cell is updated `textContent` IN PLACE via rAF (never node-rebuilt).
- gen-age freshness watchdog (OVD-03 client half / Pitfall 4): `PUBLISH_MS = 200`, `STALE_MS = PUBLISH_MS * 3`, `lastGen = -1`/`lastGenAt`; `isStale()` ported verbatim (`lastGen >= 0 && Date.now() - lastGenAt > STALE_MS`) — cold start (`lastGen < 0`) is NOT stale. When stale (or a fetch reject) the rAF timer STOPS (no free-run forever) and the `.is-stale` degrade class is applied; a fresh gen re-anchors cleanly (re-measures skew, restarts rAF, clears degrade).
- Poll loop: `GET /overlay-json?t=<lastGen>` nonce (load-bearing in CEF — Pitfall 2) at `PUBLISH_MS` cadence (NOT 60fps — DoS guard), re-rendering ONLY on `p.gen > lastGen`; a fetch error COASTS (never throws out of the loop).
- The same file dual-exports as `window.SEGUGIO_OVERLAY` (browser) and `module.exports` (node tests) and auto-mounts on `DOMContentLoaded` (no-op under node — no `document`).
- `tests/test_ui_overlay_render.py` Task-2 assertions: the offset-cancellation formula present + no raw subtraction; the `?t=` nonce + `> lastGen` gate; `isStale()`/`STALE_MS`/`PUBLISH_MS`/cold-start guard; `.is-stale` + the "Tempo" literal; and a **node-executed behavior test** proving ~30s skew reads near-0 elapsed error, the countdown freezes at 0 on "Tempo", and agility renders `SS.hh` overtime past SCT.

## Renderer Interface (final symbol names — for Phase 12 + drift verification)

- File: `src/segugio/ui/static/overlay-render.js` (one IIFE; namespace `SEGUGIO_OVERLAY` / `module.exports`).
- Sanitize: `cleanField`, `scvGet`, `SCV_MAX_FIELD_LEN` (64), `SCV_NONPRINT`.
- Render: `renderOverlay(root, payload)`, `renderCells`, `renderIdentity`, `DISCIPLINE_CELLS`.
- Timer/format: `formatCountdown(remainingS)` (M:SS, "Tempo" at 0), `formatAgility(elapsedS)` (SS.hh).
- Animation: `animateRunEdge(lowerThird, wasRunning, isRunning)`, `pulseOnce(lowerThird)`.
- Lifecycle: `createRenderer(root, cfg)` → `{ start, stop, applyPayload, isStale, currentElapsed, paintTimer }`; `autoMount()` (auto on DOMContentLoaded).
- Constants: `PUBLISH_MS` (200), `STALE_MS` (600).

## Verification

- `python -m pytest tests/test_ui_overlay_render.py -x -q` — 11 passed (includes the two node-executed behavior tests: `cleanField` byte-parity vs `score_render._clean`, and the 30s-skew / freeze-at-0 / agility-overtime timer math).
- `python -m pytest tests/ -k "ui or import or overlay or config" -q` — all passed (1 pre-existing skip). The 11-02 served-HTML contract test stays green (the renderer file the template references now exists).
- node v24 available in the environment; node stdout is decoded as UTF-8 explicitly so the byte-parity unicode samples (e.g. `café`) compare correctly on Windows (see Deviations).
- Manual invariant checks: no `innerHTML` in the served JS; the offset-cancellation formula present and no raw `Date.now() - started_at`; `?t=` nonce + `gen > lastGen` gate; `isStale()` cold-start guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Decode node subprocess stdout as UTF-8 (Windows locale-encoding mangle)**
- **Found during:** Task 1 (the `cleanField` byte-parity node test went RED on the `café münchen` sample)
- **Issue:** `subprocess.run(..., text=True)` decodes the child's stdout with the host locale encoding (cp1252 on this Windows box), corrupting node's UTF-8 output (`café` → `caf?`), so the byte-parity assertion failed on a NON-ASCII printable sample even though `cleanField` was correct.
- **Fix:** Run node with `capture_output=True` (bytes) and decode stdout/stderr as `utf-8` explicitly in the `_run_node` helper. No renderer behavior changed — purely the test harness's child-process decoding. This keeps the node behavior tests (the established console-test precedent) reliable cross-platform.
- **Files modified:** `tests/test_ui_overlay_render.py`
- **Commit:** `0fcf618` (folded into the Task-1 commit alongside the test)

## Authentication Gates

None.

## Known Stubs

None. The renderer wires live data from `/overlay-json` into the DOM via `textContent`; the `#timer` `--` placeholder shipped by 11-02 is filled on the first poll (owned by this plan), and the `#cells` container is populated per discipline. No hardcoded/empty value flows to a rendered surface.

## Threat Flags

None. No new security surface beyond the plan's `<threat_model>`: no new endpoints (pure consumer of the existing `/overlay-json`), no new auth path, no file access, no schema change. The dominant phase threats are mitigated as specified — T-11-03-01 (textContent-only, no innerHTML), T-11-03-02 (stale stops the timer + degrades), T-11-03-03 (offset-cancellation), T-11-03-04 (PUBLISH_MS poll + rAF freezes on stop/stale), T-11-03-SC (no package installs).

## TDD Gate Compliance

Both tasks are `tdd="true"`. Each ran RED → GREEN: Task-1 behavior tests were written against the renderer and went RED on the node UTF-8 decoding, fixed, then GREEN; Task-2 tests referenced `formatCountdown`/`formatAgility` (absent until Task 2) and the offset-cancellation formula, RED before the Task-2 implementation, GREEN after. Per the repo convention for additive renderer+test work (mirroring 11-01/11-02), each task's implementation and its test extension land in a single `feat(...)` commit; RED was observed before each GREEN.

## New Symbols Introduced (created-here, not drift)

- Static asset: `src/segugio/ui/static/overlay-render.js` (auto-served at `/static/overlay-render.js`).
- JS functions: `cleanField`, `scvGet`, `renderOverlay`, `renderCells`, `renderIdentity`, `fillCell`, `retrigger`, `animateRunEdge`, `pulseOnce`, `formatCountdown`, `formatAgility`, `createRenderer`, `autoMount` (+ the inner `poll`/`tick`/`applyPayload`/`isStale`/`paintTimer`).
- JS constants/tables: `SCV_MAX_FIELD_LEN` (64), `SCV_NONPRINT`, `DISCIPLINE_CELLS`, `PUBLISH_MS` (200), `STALE_MS` (600), `TEMPO_LITERAL`, `DISC_TF_COUNTDOWN_S` (60).
- JS namespace: `window.SEGUGIO_OVERLAY` / `module.exports`.
- Test file: `tests/test_ui_overlay_render.py`.
- (`cleanField`/`scvGet`/`isStale`/`PUBLISH_MS`/`STALE_MS` are PORTS of existing console.html symbols — not novel behavior; the genuinely new behavior is the offset-cancellation timer.)

## Self-Check: PASSED

Both created files and this SUMMARY exist on disk; both task commits (`0fcf618`, `2233106`) are in the git log.
