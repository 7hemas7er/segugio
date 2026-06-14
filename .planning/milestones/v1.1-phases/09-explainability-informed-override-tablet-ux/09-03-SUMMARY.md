---
phase: 09-explainability-informed-override-tablet-ux
plan: 03
subsystem: ui-console
tags: [explainability, scv-01, why-01, why-02, why-03, why-04, tablet, drift-guard]
requires:
  - "09-01: POST /score/preview (text/plain render_overlay_text) + GET /preview cuts ring"
  - "09-02: tablet-first console.html (sidebar scaffolds #reason/#leaderboard/#auto-wants, setTileState, updateBbox, 5 tile states)"
provides:
  - "reasonToItalian map + renderReason -> #reason plain-Italian copy (WHY-01)"
  - "buildLeaderboard: per-camera framing-score leaderboard, sorted, tracking/coast/lost fill (WHY-02)"
  - "renderAutoWants: 'Auto vuole: {cam}' sidebar line + dashed-blue auto-wants tile marker (WHY-04)"
  - "pollPreview-driven live dog-lock bbox via updateBbox(cam, cams[cam].box) (WHY-03)"
  - "SCV-01 client mirror: cleanField/mirrorOverlayText (byte-exact render_overlay_text) + debounced #overlay-preview + driftCheck POST /score/preview"
affects:
  - "src/segugio/ui/templates/console.html"
  - "tests/test_ui_explainability.py"
tech-stack:
  added: []
  patterns:
    - "JS-exercised parity tests: extract delimited gsd:<name>:start/end JS blocks from served HTML, run via node, assert == Python render_overlay_text (Wave-0 CI parity)"
    - "node stdout captured as raw UTF-8 bytes via a temp .mjs file (cp1252 Windows host would mangle the non-ASCII reason/overlay chars on the command line)"
key-files:
  created:
    - "tests/test_ui_explainability.py"
  modified:
    - "src/segugio/ui/templates/console.html"
decisions:
  - "Drift-guard fires ONCE on blur AND on submit (POST /score/preview, Flask only); the debounced preview is pure client-side JS with NO per-keystroke fetch (T-09-03-01/03/04)"
  - "cleanField mirrors Python str.isprintable() via a Unicode-property regex dropping Cc/Cf/Cs/Co/Cn/Zl/Zp/Zs while explicitly keeping U+0020 (matches `ch == ' ' or ch.isprintable()`)"
  - "Byte-parity is verified by EXECUTING the served JS in node against the imported Python render_overlay_text across all 3 disciplines (not a string-compare of source) — the only way to prove server === client"
  - "#reason renders the mapped Italian copy; the separate #live-reason 'Stato live' readback keeps the raw advisory tag (technical readout)"
metrics:
  duration: "~25 min"
  tasks: 2
  files: 2
  completed: "2026-06-14"
---

# Phase 9 Plan 3: Explainability Sidebar + SCV-01 Score-Overlay Mirror Summary

Filled the four 09-02 sidebar why-blocks with live explainability (plain-Italian reason WHY-01,
per-camera framing-score leaderboard WHY-02, "auto vuole" hint + dashed-blue tile marker WHY-04,
live dog-lock bbox wired from the sidecar WHY-03) and added the SCV-01 client-side score-overlay
preview: a byte-exact JS mirror of `render_overlay_text`, debounced into "Anteprima overlay", with
a once-on-blur/submit drift-guard against `POST /score/preview` — proven byte-identical to the
Python renderer by executing the served JS in node (Wave-0 CI parity).

## What Was Built

### Task 1 — WHY-01/02/03/04 sidebar fill (commit 089059a)
- **`reasonToItalian(reason)`** + **`renderReason(status)`** (WHY-01): maps `status.reason` → the
  exact UI-SPEC Italian copy (`auto`→"Auto: miglior inquadratura", `override`→"Override operatore",
  `subject-lost`→"Soggetto perso → SAFE", `feed-dead`→"Feed morto → fallback", `shutdown`→"Arresto →
  SAFE", `none`/unknown→"In attesa…"), written into `#reason` from `pollStatus`. The map lives in a
  delimited `gsd:why-mirror` block so the parity test executes it in node.
- **`buildLeaderboard(cams)`** (WHY-02): one `.lb-row` per cam, sorted highest-first by `score`
  (fallback `ema`), proportional fill from a zero baseline, 2-decimal tabular value; fill treatment
  by `cams[id].state` — `tracking` solid green `●`, `coast` hatched neutral `◐ coast`, `lost`
  empty/outline `·· lost`. The lost-row LABEL uses `#E6E9EF` (checker note); the dim-gray lost hue
  is NEVER used as text. Empty/absent → "Nessun dato di framing". All cams shown (D-05). Driven
  every `pollPreview` tick.
- **`renderAutoWants(status, preview)`** (WHY-04): during `reason==="override"` writes "Auto vuole:
  {auto_candidate}" into `#auto-wants` and flags the candidate tile `auto-wants` (dashed-blue ▸,
  coexists with the FORZATA tile); cleared otherwise. Called from both polls.
- **Live bbox wiring** (WHY-03): `pollPreview` calls `updateBbox(c, (cams[c]||{}).box)` on a gen
  advance; draws nothing when `box` is null (native-ReID lock dropped); the 09-02 CSS hides the
  overlay on STALE/MORTO.

### Task 2 — SCV-01 byte-exact mirror + drift-guard (TDD: RED 2bb53de → GREEN cdd8218)
- **`cleanField(value)`**: mirrors Python `_clean` — drops non-printable / CR-LF / non-space
  separators (Unicode-property regex), keeps U+0020, `.trim()`, caps at 64.
- **`mirrorOverlayText(discipline, fields)`**: mirrors the 3 `render_overlay_text` f-strings
  CHARACTER-EXACT (including the double spaces) + the `sct`/`SCT` alias via the same first-present
  `scvGet` lookup as `_get`. Lives in a delimited `gsd:scv01-mirror` block.
- **`updateScorePreview()`**: writes the mirror into `#overlay-preview` ("Anteprima overlay"),
  debounced 200ms on `input`, NO per-keystroke fetch, NEVER the orchestrator.
- **`driftCheck()`**: POSTs the same fields to Flask `/score/preview` ONCE on blur + submit,
  compares `server === client`, toggles "⚠ Anteprima non allineata — verifica".
- Score inputs confirmed `type="text"` + `inputmode` + `enterkeyhint` + decimal helper copy
  (already laid by 09-02; the touch-contract test pins them).

## Verification

- `pytest tests/test_ui_explainability.py -k "reason or leaderboard or auto_wants or bbox"` — 6 passed
- `pytest tests/test_ui_explainability.py -k scv01` — 5 passed (incl. node byte-parity across 3 disciplines)
- `pytest tests/test_ui_explainability.py tests/test_score_preview.py tests/test_ui_score.py tests/test_ui_tablet_layout.py tests/test_ui_run.py` — 39 passed
- Full headless suite: **421 passed, 8 skipped, 2 failed** — the 2 failures are the pre-existing
  environmental NDI loopback tests (`test_ndi_mock_sender`, `test_ndi_source`), documented in STATE
  ("2 test NDI loopback ambientali"), require a live NDI runtime, and are unrelated to this plan
  (template + Flask-test-client only).

## Deviations from Plan

None — plan executed exactly as written. The plan named the JS-exercised parity tests; this
environment has Node 24 LTS on PATH, so the parity is proven by running the served JS in node
(rather than a weaker source string-compare), satisfying the "drives the JS mirror against the
Python renderer" acceptance criterion directly.

## TDD Gate Compliance

Task 2 (`tdd="true"`): RED gate `2bb53de` (`test(...)`, 4 failing SCV-01 tests — `gsd:scv01-mirror`
block + functions absent) → GREEN gate `cdd8218` (`feat(...)`, all SCV-01 tests pass). No REFACTOR
commit needed. Gate sequence satisfied.

## Notes / Carry-forward

- The bbox depends on BoT-SORT native-ReID `box` stability on yolo26s (STATE blocker); the overlay
  renders `box` when present and draws nothing on `None` — it does not assume a box is always there.
- 09-04 owns the switch-history strip (`#switch-history` from the `cuts` ring) + UXT-03 freshness /
  leak / sleep-wake hygiene; those scaffolds are untouched here.
- On-device iPad validation (Wave-0 `[ASSUMED]` items: fetch-in-visibilitychange deferral, memory
  soak, decode-before-swap zero-flash, decimal separator in it-IT) remains a hardware-milestone
  carry-forward per the UI-SPEC checklist.

## Self-Check: PASSED

- FOUND: src/segugio/ui/templates/console.html
- FOUND: tests/test_ui_explainability.py
- FOUND: .planning/phases/09-explainability-informed-override-tablet-ux/09-03-SUMMARY.md
- FOUND commit: 089059a (Task 1), 2bb53de (RED), cdd8218 (GREEN)
