---
phase: 16-shared-entry-component-dedicated-page-server-authoritative-post
plan: 02
subsystem: ui
tags: [flask, vanilla-js, score-entry, mount-factory, dual-export, decimal-string, jinja-host, xss-textcontent, throw-list, advisory-total]

# Dependency graph
requires:
  - phase: 16-01
    provides: "authoritative POST /score (JSON throws[]) + advisory score-calc.js (window.SEGUGIO_SCORE_CALC) + create_app(profile, sport) injection point + shared PROFILE_JSON/FIXTURES + entry-test stubs"
  - phase: 15-pure-calc-validation-core-scoring-profiles
    provides: "score_calc.ScoringProfile + CSEN_DISC_PROFILE + adapt_scoring_profile (the active-profile source injected into the page blob)"
  - phase: 11-overlay-renderer
    provides: "overlay-render.js IIFE + dual-export + autoMount skeleton and the fillCell textContent-only XSS-safe in-place sink cloned by score-entry.js"
provides:
  - "ONE shared vanilla-JS score-entry.js: mount(root, cfg) factory, dual export (window.SEGUGIO_SCORE_ENTRY + module.exports), re-mountable for the P17 console modal (SCE-01)"
  - "Per-discipline rich fields driven by the injected active profile: disc-T&F repeatable in-session throw list (live best-5-of-N), freestyle categories + nome, agility model fields (SCE-02/03)"
  - "Live advisory Totale (provvisorio) updated IN PLACE via textContent + on-blur per-field error chips; publish button always enabled; persistent banner (✓ In onda / Errore — punteggio precedente invariato) (SCE-03/05/D-04/D-05)"
  - "GET /score-entry route + _profile_to_json (decimal-as-string serializer) + D-06 valid-discipline derivation + lazy adapt_scoring_profile in __main__ (crash-isolation safe)"
  - "Thin Jinja host score-entry.html (inlined #score-cfg blob + two script srcs + #score-entry-root + #publish-banner; no form/calc logic of its own)"
affects: [17-console-modal, 18-overlay-fields]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mount(root, cfg) factory + dual export + autoMount reading JSON.parse(#score-cfg.textContent) — one re-mountable module, no window-global cfg (cloned from overlay-render.js but config-injected)"
    - "decimal-as-string profile injection (_profile_to_json): every Decimal serialized as str(...) so the JS BigInt-Decimal helper parses strings and never inherits float drift"
    - "operator/echoed values written exclusively via textContent/createTextNode; only static icon SVG via innerHTML (T-16-07 XSS gate carried forward)"
    - "client POSTs RAW structured inputs (throws[]/cats/agility raw) as JSON — never a client-computed total (T-16-08 double-source-of-truth gate)"

key-files:
  created:
    - "src/segugio/ui/static/score-entry.js"
    - "src/segugio/ui/templates/score-entry.html"
  modified:
    - "src/segugio/ui/app.py"
    - "tests/test_ui_score_entry.py"

key-decisions:
  - "score-entry.js reads its cfg from JSON.parse(#score-cfg.textContent) (NOT a window global) so the same module re-mounts cleanly in the P17 console modal with a different blob"
  - "profile injected as decimal STRINGS via _profile_to_json so the advisory JS total parses the same BigInt-Decimal representation as Python and cannot float-drift (T-16-10)"
  - "publish button is ALWAYS enabled (D-04); pre-submit advisory validation is a pre-filter only — the server 400 is authoritative and its per-field errors are what the banner surfaces (D-05a)"

patterns-established:
  - "Shared mount(root,cfg) component proven on the simpler dedicated page first, ready to be a SECOND mount of the SAME code in the console modal (SCV-02 lesson applied to a form — drift structurally impossible)"
  - "Thin Jinja host carries the inlined decimal-string profile blob + mount node only; all form/calc logic lives in the one shared JS module"

requirements-completed: [SCE-01, SCE-02, SCE-03, SCE-05]

# Metrics
duration: ~20min (Tasks 1-2 prior session) + continuation close-out
completed: 2026-06-23
---

# Phase 16 Plan 02: Shared Entry Component & Dedicated Page Summary

**ONE re-mountable `mount(root, cfg)` `score-entry.js` (dual export) renders per-discipline rich fields from the server-injected decimal-string profile — disc-T&F repeatable throw list with a LIVE best-5-of-N advisory total, on-blur per-field errors, RAW-JSON POST to the authoritative route, and a persistent publish banner — proven on the thin Jinja `/score-entry` host.**

## Performance

- **Duration:** ~20 min implementation (Tasks 1-2, prior session) + continuation close-out (this session)
- **Completed:** 2026-06-23
- **Tasks:** 3 (2 auto + 1 blocking human-verify)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- **Task 1 — `GET /score-entry` route + decimal-string profile injection + lazy adapter** (`e8e5646`): added a stdlib-only `_profile_to_json(profile)` to `app.py` that serializes the plain `score_calc.ScoringProfile` with every Decimal as `str(...)` (zones / bonuses / freestyle_cats as nested string-tuples, `per_throw_cap` / `freestyle_max` as decimal strings, `count_best_n` kept int). `create_app` builds `_score_cfg = {sport, disciplines, profile}` with the D-06 discipline derivation (`disc_dog` → `["disc_tf","disc_freestyle"]`, else `["agility"]`) and serves it via a new `@app.get("/score-entry")` route (mirroring `index`). `__main__` resolves `adapt_scoring_profile(cfg.field.scoring)` + `cfg.field.sport` LAZILY (mirroring the existing lazy `load_config` block) so no `from ..config` leaks into the crash-isolated console module top. Created the thin `score-entry.html` host. `test_disciplines_from_profile` un-skipped and green; crash-isolation gate stays green.
- **Task 2 — `score-entry.js` shared `mount(root,cfg)` component** (`5c70829`): a 579-line IIFE with `function mount(root, cfg)`, dual export (`window.SEGUGIO_SCORE_ENTRY = { mount }` + `module.exports`), and an `autoMount()` reading `JSON.parse(document.getElementById("score-cfg").textContent)`. Renders the discipline control (select for 2+, static label for 1) + a `.campi[data-disc]` show/hide toggle; disc T&F repeatable in-session throw list (`+ Aggiungi lancio` add, per-row `×` remove, `Zona`/`Al volo`/`Corridoio`, NO localStorage — D-01a) with best-5-of-N reflected in the advisory `Totale (provvisorio)`; freestyle categories + free-text `nome`; agility fields per `cfg.profile.agility_model`. `input` → recompute the advisory total IN PLACE via `SEGUGIO_SCORE_CALC.compute` (textContent, "non ufficiale" caption); `blur` → per-field error chips via `SEGUGIO_SCORE_CALC.validate`; submit (button always enabled) POSTs RAW structured inputs as JSON to `/score`; the persistent `#publish-banner` shows `✓ In onda` on 2xx and the server's per-field errors + `Errore — punteggio precedente invariato` on 400. All operator/echoed values via `textContent`; only static icon SVG via `innerHTML`.
- **Task 3 — Manual UX verification** (human-verify, gate=blocking): the operator opened `/score-entry`, manually verified the live-total cadence, on-blur per-field error timing, and persistent result-banner behavior, and responded **"approved"**. This is the single manual item in `16-VALIDATION.md` (Manual-Only Verifications). No code change — the gate is satisfied by operator sign-off.

## Task Commits

1. **Task 1: GET /score-entry route + decimal-string profile injection + lazy adapter** - `e8e5646` (feat)
2. **Task 2: score-entry.js shared mount(root,cfg) component (SCE-01..05)** - `5c70829` (feat)
3. **Task 3: Manual UX verification (human-verify, blocking)** - approved by operator (no commit; subjective UX sign-off)

## Files Created/Modified
- `src/segugio/ui/static/score-entry.js` (579 lines) - The ONE shared vanilla-JS component: `mount(root,cfg)` factory + dual export + `autoMount()`; per-discipline fields incl. the disc-T&F in-session throw list; live advisory total (in-place textContent); on-blur error chips; RAW-JSON POST to `/score`; persistent publish banner. No operator-value innerHTML sink.
- `src/segugio/ui/templates/score-entry.html` (95 lines) - Thin full-screen Jinja host: `{{ score_cfg | tojson }}` `#score-cfg` blob, `score-calc.js` then `score-entry.js` script srcs, `#score-entry-root` mount node + `#publish-banner`; reuses console CSS tokens; no `<input>`/calc logic of its own.
- `src/segugio/ui/app.py` - Added `_profile_to_json` (decimal-as-string serializer), `_score_cfg`/D-06 discipline derivation + `GET /score-entry` route in `create_app`, and the lazy `adapt_scoring_profile`/`cfg.field.sport` resolution in `__main__`.
- `tests/test_ui_score_entry.py` - Un-skipped + finished the Plan-02 gates (`test_dual_export_and_thin_host`, `test_no_innerhtml_sink`, `test_live_total_advisory`, `test_disciplines_from_profile`).

## Verification (continuation re-confirmation)
Re-ran the plan gate tests this session (Python 3.12 venv, `node` present so the parity gates actually run):
- `tests/test_ui_score_entry.py` — **4 passed** (the SCE gates).
- Full 16-0x gate set (`test_ui_score_entry.py` + `test_ui_score_authoritative.py` + `test_ui_score_calc_js.py` + `test_ui_score.py` + `test_imports.py` + `test_ui_overlay_json.py`) — **62 passed, 0 failed, 0 skipped** in 2.56s.

The 5 remaining full-suite failures are the documented pre-existing set (2 NDI hardware, explainability node, console scv-unification + tablet-layout templates) tracked in `deferred-items.md` — NOT regressions, confirmed identical at phase-start.

## Decisions Made
- **cfg from `#score-cfg.textContent`, not a window global:** the component parses its config from the inlined JSON blob rather than a `window.SCORE_CFG`, so the SAME module re-mounts in the P17 console modal with a different blob — drift structurally impossible (SCV-02 lesson on a form).
- **Profile injected as decimal strings:** `_profile_to_json` emits every numeric as `str(Decimal)` so the JS BigInt-Decimal helper parses the identical representation Python uses and the advisory total never inherits `0.1+0.2` float drift (T-16-10).
- **Publish button always enabled (D-04):** client advisory validation is only a pre-filter; the authoritative server 400 is what the banner surfaces (`Errore — punteggio precedente invariato`), keeping the previous on-air score the single source of truth (D-05).

## Deviations from Plan
None — plan executed as written across all three tasks. (Auto-fix deviations from this phase were confined to Plan 16-01.)

## Threat Mitigations Confirmed
- **T-16-07 (XSS):** all operator/echoed values via `textContent`; `test_no_innerhtml_sink` green — a crafted `<script>` `nome` renders inert.
- **T-16-08 (double source of truth):** the component POSTs RAW inputs (`throws[]`/cats/agility raw) — never a client-computed total.
- **T-16-09 (crash-isolation):** `adapt_scoring_profile` resolved LAZILY in `__main__` only; `test_console_resolves_with_heavy_stack_and_numpy_absent` green.
- **T-16-10 (float drift):** decimal-string profile blob; the advisory JS total agrees with Python.
- **T-16-11 (broadcast integrity on 400):** the banner shows the server per-field errors + "punteggio precedente invariato"; no local write.

## Known Stubs
None. The thin host carries no form/calc logic by design (that lives in `score-entry.js`); this is the intended architecture, not a stub.

## Next Phase Readiness
- Phase 17 can mount the SAME `score-entry.js` (`window.SEGUGIO_SCORE_ENTRY.mount(root, cfg)`) in a native `<dialog>` in `console.html` against a `#score-cfg` blob — no new component, no fork. The dual export + cfg-from-blob design is the proof point that the console modal is a second mount of identical code (SCV-02).
- The authoritative `POST /score` contract (RAW `throws[]` + per-discipline raw inputs) and the advisory `score-calc.js` are both already wired and exercised by this component.

## Self-Check: PASSED
- Created files verified present: `src/segugio/ui/static/score-entry.js` (579 lines), `src/segugio/ui/templates/score-entry.html` (95 lines).
- Modified files verified present: `src/segugio/ui/app.py`, `tests/test_ui_score_entry.py`.
- Commits verified in `git log`: `e8e5646` (Task 1), `5c70829` (Task 2).
- Plan gate tests re-run green this session: `tests/test_ui_score_entry.py` 4 passed; full 16-0x gate set 62 passed / 0 failed / 0 skipped.
- Manual UX checkpoint (Task 3, blocking human-verify): operator response "approved".

---
*Phase: 16-shared-entry-component-dedicated-page-server-authoritative-post*
*Completed: 2026-06-23*
