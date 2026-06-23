---
phase: 16-shared-entry-component-dedicated-page-server-authoritative-post
verified: 2026-06-23T10:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open /score-entry in a browser and interact with the disc T&F throw list"
    expected: "Discipline options match the sport (disc-dog → two choices); live advisory total updates as you add/change throws; per-field errors appear on blur; banner shows '✓ In onda' on submit and 'Errore — punteggio precedente invariato' on a 400; previously-aired score is unchanged after a rejected submit"
    why_human: "Subjective UX timing (live-total cadence, banner persistence, on-blur error timing on a real tablet) cannot be asserted by pytest. This is the one manual item in 16-VALIDATION.md."
    resolution: "APPROVED by the user (developer acknowledgment) during the Plan 16-02 Wave-2 execution checkpoint on 2026-06-23 — operator confirmed the live-total cadence, on-blur errors and persistent banner behave correctly. Per the verifier, developer acknowledgment closes this gate. Real-tablet UAT remains a non-blocking carry-forward to Phase 17."
---

# Phase 16: Shared Entry Component + Server-Authoritative POST Verification Report

**Phase Goal:** An operator can enter a score on a dedicated full-screen page using ONE shared component with live advisory feedback, and the server is the sole authority that validates and recomputes what airs.
**Verified:** 2026-06-23T10:00:00Z
**Status:** passed (operator-UX gate approved by the user during the Wave-2 execution checkpoint, 2026-06-23 — developer acknowledgment closes the sole human-verify item)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator opens /score-entry, picks discipline, sees rich per-discipline structured fields from the active profile | VERIFIED | `GET /score-entry` route in `app.py:323-331`; `test_disciplines_from_profile` passes: disc_dog → `["disc_tf","disc_freestyle"]`, agility → `["agility"]`; profile blob verified decimal-string (`per_throw_cap=="5"`, `bonuses[0][1]=="0.5"`, `zones[0][1]=="1"`) |
| 2 | As the operator types, a running total updates live (advisory); per-field validation errors appear before publishing | VERIFIED | `recompute()` in `score-entry.js:425-450` updates `totalValue.textContent` in place via SEGUGIO_SCORE_CALC; `validateOnBlur()` at line 478 paints chips via `textContent`; `test_live_total_advisory` and `test_no_innerhtml_sink` pass |
| 3 | Submitting POSTs RAW inputs only; server validates (returns 400 + writes NOTHING on invalid, leaving previous on-air score untouched); server recomputes total in Python before writing atomically | VERIFIED | `post_score` in `app.py:341-393`: `is_json = isinstance(json_body, dict)` (CR-01 fix); `score_calc.validate()` called before any write; `return (jsonify({"errors": errors}), 400)` on errors; `score_calc.compute()` called then `_write_score_doc`. Confirmed by probe: CR-01 list/int body → 204; CR-02 `throws=42` → 400 + score.json/overlay.txt byte-unchanged. `test_invalid_post_400_writes_nothing`, `test_invalid_fixtures_rejected` both pass. |
| 4 | For same inputs: form-displayed total === overlay.txt line === /overlay-json-rendered total; JS advisory calc never becomes a second authority (drift-guard green) | VERIFIED | `test_round_trip_total_equality` passes; `test_compute_byte_parity_with_python` and `test_validate_parity` pass with node v24 present (not skipped); all disciplines + deduct_from_100 + non-list throws CR-02 covered |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/static/score-calc.js` | Byte-exact advisory port + gsd:score-calc-mirror sentinel + dual export | VERIFIED | 483 lines; `gsd:score-calc-mirror:start/end` present; `window.SEGUGIO_SCORE_CALC` and `module.exports` exported; no `parseFloat`; BigInt+exponent Dec helper |
| `src/segugio/ui/app.py` | Authoritative POST /score (validate-before-write → Decimal recompute → atomic write) + additive create_app(profile, sport) | VERIFIED | `isinstance(json_body, dict)` CR-01 fix; `score_calc.validate()` call; `_write_score_doc` only reached after clean validate; `create_app(channel_dir, cam_ids=(), overlay_cfg=None, profile=None, sport="disc_dog")` |
| `src/segugio/ui/static/score-entry.js` | ONE shared mount(root,cfg) module; dual export; per-discipline fields; live total; RAW POST; persistent banner; no operator-value innerHTML | VERIFIED | 579 lines; `window.SEGUGIO_SCORE_ENTRY` and `module.exports`; `fetch("/score", ...)` posts RAW; banner textContent only; no `innerHTML =` sink |
| `src/segugio/ui/templates/score-entry.html` | Thin Jinja host; #score-cfg blob; #score-entry-root; #publish-banner; no <input> of its own | VERIFIED | 95 lines; `{{ score_cfg | tojson }}` in `<script type="application/json" id="score-cfg">`; `#score-entry-root`; `#publish-banner`; no `<input>` tag; two script tags pointing to score-calc.js then score-entry.js |
| `tests/test_ui_score_authoritative.py` | SCC-01 Flask-client round-trip tests | VERIFIED | 6 tests pass: 400-write-nothing, recompute, run-state preserve, round-trip equality, legacy round-trip, invalid fixtures rejected |
| `tests/test_ui_score_calc_js.py` | SCC-03 node-vs-Python drift-guard | VERIFIED | 4 tests pass with node v24 present (sentinel/dual-export static assert, compute parity, validate parity, valid-fixtures-clean) |
| `tests/test_ui_score_entry.py` | SCE-01..05 component gates | VERIFIED | 4 tests pass: dual-export/thin-host, disciplines-from-profile, no-innerHTML-sink, live-total-advisory |
| `tests/_score_fixtures.py` | Shared PROFILE_JSON (decimal strings) + FIXTURES + INVALID_FIXTURES | VERIFIED | PROFILE_JSON self-test `per_throw_cap=="5"` present; PROFILE_JSON_DEDUCT for deduct_from_100 (WR-02); 7 FIXTURES; 5 INVALID_FIXTURES including `throws:42` (CR-02/WR-01) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py POST /score` | `score_calc.validate/compute` | `score_calc.validate(discipline, fields, profile)` then `score_calc.compute(...)` | WIRED | Lines 388-392; validate called first, errors → 400, else compute → _write_score_doc |
| `score-calc.js` | `score_calc.py` | node-vs-Python shared-fixture drift-guard + gsd:score-calc-mirror sentinel | WIRED | Sentinel present; drift-guard runs (node v24) and passes all disciplines + deduct_from_100 + CR-02 |
| `score-entry.html` | `score-entry.js` | `JSON.parse(document.getElementById("score-cfg").textContent)` at autoMount | WIRED | `autoMount()` in score-entry.js:554-566 reads `#score-cfg`; template has `id="score-cfg"` blob + `<script src="/static/score-entry.js">` |
| `score-entry.js` | `score-calc.js` | `window.SEGUGIO_SCORE_CALC` advisory compute/validate for live total + on-blur errors | WIRED | `const calc = (typeof window !== "undefined" && window.SEGUGIO_SCORE_CALC) || ...` at mount line 101; `calc.compute(...)` in recompute(), `calc.validate(...)` in validateOnBlur() |
| `score-entry.js` | `app.py POST /score` | `fetch("/score", {method:"POST", ...JSON body of RAW inputs...})` | WIRED | `submit()` function at line 501: `fetch("/score", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(raw) })` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app.py _write_score_doc` | `computed` dict | `score_calc.compute(discipline, fields, profile)` → Decimal arithmetic | Yes — Python Decimal recompute from RAW inputs | FLOWING |
| `score-entry.js totalValue` | `result.totale` | `calc.compute(active, raw, profile)` advisory | Yes — Dec helper from profile strings | FLOWING |
| `score-entry.html #score-cfg` | `score_cfg` dict | `_profile_to_json(profile)` in `create_app` | Yes — decimal STRING serialization of CSEN_DISC_PROFILE | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01: non-dict JSON body (list) returns 204, not 500 | `c.post('/score', data='[1,2,3]', content_type='application/json')` | 204 | PASS |
| CR-01: non-dict JSON body (int) returns 204, not 500 | `c.post('/score', data='42', content_type='application/json')` | 204 | PASS |
| CR-02: non-list `throws=42` returns 400 + correct error, not 500 | `c.post('/score', json={"discipline":"disc_tf","throws":42})` | 400 + `{"errors":[{"field":"throws","message":"Formato lanci non valido."}]}` | PASS |
| validate-before-write: invalid POST leaves score.json+overlay.txt byte-unchanged | CR-02 probe + file comparison | score unchanged: True; overlay unchanged: True | PASS |
| deduct_from_100 JS branch: 100-10-5=85 | `node -e "calc.compute('agility', {tempo:'00:34.50', sct:'00:30.00', course_deductions:'10'}, deductProfile)"` | result=85, totale=85, faults=5 | PASS |
| Full phase gate set (14 tests) | `pytest test_ui_score_authoritative.py test_ui_score_calc_js.py test_ui_score_entry.py` | 14 passed, 0 failed | PASS |
| Legacy round-trips + crash-isolation (46 tests) | `pytest + test_ui_score.py + test_imports.py` | 46 passed, 0 failed | PASS |
| Full suite | `pytest tests/` | 542 passed, 5 failed, 8 skipped | PASS (5 failures are pre-existing, out-of-scope) |

---

### Probe Execution

No conventional probe scripts found for this phase. Behavioral spot-checks above serve as the probe layer.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCE-01 | Plan 16-02 | ONE shared vanilla-JS component; same mount on dedicated page and console modal | SATISFIED | `score-entry.js` exports `window.SEGUGIO_SCORE_ENTRY = { mount }` + `module.exports`; `test_dual_export_and_thin_host` passes |
| SCE-02 | Plan 16-02 | Rich per-discipline structured fields driven by the active scoring profile | SATISFIED | `buildDiscTf()`, `buildFreestyle()`, `buildAgility()` in score-entry.js; `test_disciplines_from_profile` passes |
| SCE-03 | Plan 16-02 | Live advisory total updates as operator types, explicitly non-authoritative | SATISFIED | `recompute()` updates `totalValue.textContent` in place; "Calcolo live — non ufficiale" caption present in score-entry.js:165; `test_live_total_advisory` passes |
| SCE-05 | Plan 16-02 | Per-field validation errors shown before/during publishing | SATISFIED | `validateOnBlur()` on blur; per-field error chips via textContent; `test_no_innerhtml_sink` passes |
| SCC-01 | Plan 16-01 | POST /score authoritative: 400+write-nothing on invalid, Decimal recompute on valid | SATISFIED | All 4 SCC-01 gate tests pass; CR-01/CR-02 behavioral probes confirmed |
| SCC-03 | Plan 16-01 | score-calc.js advisory port with drift-guard against Python score_calc | SATISFIED | 4 drift-guard tests pass with node v24 (not skipped); gsd:score-calc-mirror sentinel present; all disciplines + CR-02 non-list throws + WR-02 deduct_from_100 covered |

**Note:** SCE-04 (tablet UX hardening: focus-trap, offline assets) is correctly mapped to Phase 17 in REQUIREMENTS.md — not a gap for Phase 16.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `score-entry.js` | 431,485 | `catch (_e) {}` bare swallow in advisory recompute/validateOnBlur | Info (IN-01 from code review) | Intentional: advisory UI must never throw. Dev-mode loss of error visibility only. No operator-facing impact. |
| `score-calc.js` | 455 | `_decFromInt(Number(timeFaults))` — BigInt→Number round-trip in deduct_from_100 | Info (WR-02 from code review) | Acceptable for realistic time faults (far below 2**53); the path is now covered by the drift-guard (WR-02 fixture added). Not a blocker. |

No TBD/FIXME/XXX/PLACEHOLDER markers found in phase-16 files. No unguarded stubs. No hardcoded empty returns on production paths.

---

### Pre-existing Failures (Out of Scope)

The full suite shows exactly 5 failures, all confirmed pre-existing at phase-start commit `0958d94` and documented in `deferred-items.md`:

| Test | Reason |
|------|--------|
| `test_ndi_mock_sender.py::test_mock_sender_publishes_named_source` | NDI hardware not available |
| `test_ndi_source.py::test_receiver_yields_bgr_and_new_frame_ts` | NDI hardware not available |
| `test_ui_explainability.py::test_leaderboard_renders_sorted` | Node ESM leaderboard JS (mirror.mjs:65) — unrelated to score-calc |
| `test_ui_scv_unification.py::test_console_embeds_overlay_iframe` | console.html P17 surface |
| `test_ui_tablet_layout.py::test_touch_action_and_targets` | console.html P17 surface |

None are regressions introduced by Phase 16.

---

### Human Verification Required

#### 1. Operator UX Feel — Live Total Cadence, On-Blur Errors, Persistent Banner

**Test:** Start the console (`python -m segugio.ui.app`) and open `http://localhost:8080/score-entry` in a browser. Perform the following sequence:
1. Confirm discipline options match the configured sport (disc-dog → "Disc — Toss & Fetch" + "Disc — Freestyle").
2. On Toss & Fetch: click "+ Aggiungi lancio" several times, set zone bands and Al volo/Corridoio checkboxes — confirm "Totale (provvisorio)" updates LIVE as you interact, shows "Migliori 5 di N lanci" once N > 5, and carries the "non ufficiale / ricalcolato dal server" caption.
3. Tab out of a zone left blank — confirm a red per-field error chip appears ON BLUR (not while typing).
4. Click "Manda in onda" with valid input — confirm the banner shows "✓ In onda" and STAYS visible; verify /overlay-json shows the same total.
5. Submit an invalid entry — confirm the banner shows "Errore — punteggio precedente invariato", per-field chips appear, and the previously-aired score is unchanged.

**Expected:** All behaviors described above. Banner persists until the next submit action.

**Why human:** Subjective UX timing (live-total cadence, blur vs. type event timing, banner persistence duration on a real device) cannot be asserted programmatically. This is the one manual item declared in `16-VALIDATION.md`.

**Context note:** The SUMMARY.md for Plan 16-02 Task 3 reports "approved by operator" for this human-verify checkpoint. The verifier cannot independently confirm this — it requires developer acknowledgment to close.

---

### Gaps Summary

No gaps blocking goal achievement. All 4 observable truths are VERIFIED by direct code inspection and passing tests. The `status: human_needed` is triggered exclusively by the one deliberately-deferred manual UX verification item from `16-VALIDATION.md` — automated correctness is fully established.

---

_Verified: 2026-06-23T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
