---
phase: 18-rich-data-model-overlay-continuity-regression
verified: 2026-06-27T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 18: Rich Data Model & Overlay-Continuity Regression — Verification Report

**Phase Goal:** The richer structured score rides through the publish path additively, and every shipped overlay contract — graphical `/overlay`, `/overlay-json`, the `overlay.txt` text fallback, and the HTML sink — is verified unbroken.
**Verified:** 2026-06-27
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Phase Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After a rich POST /score, score.json and /overlay-json carry the structured subkeys (throws[]/criteria{}/faults_breakdown{}) ALONGSIDE all preserved flat summary keys; no legacy /overlay-json key is renamed or removed. | VERIFIED | `LEGACY_FLAT_KEYS` subset assertions in `test_ui_overlay_json.py` (lines 345, 371, 386); `test_overlay_json_envelope_frozen` asserts exactly the 6-key envelope. Per-throw `score=="4.5"`, `criteria["team"]=="8.50"`, `faults_breakdown=={"course":"5","time":"5"}` all asserted and green (86/86 pass). |
| 2 | overlay.txt is still written on every publish as a single non-empty line (length-bounded per field), and the OBS read-from-file text fallback shows the current score — regression-verified, not assumed. | VERIFIED | `test_overlay_txt_single_line_after_rich_post` in `test_overlay_fallback_gate.py` (lines 76-161): asserts `line` non-empty, `"\n" not in line`, `"\r" not in line`, byte-equal to `render_overlay_text(written)` per discipline (disc_tf multi-throw, freestyle with 80-char nome, agility count_up), and 64-char cap proven. `score_render.py` freeze target confirmed unmodified (`git diff f2408c8..HEAD -- src/segugio/ui/score_render.py` empty). |
| 3 | The /overlay graphical renderer still displays the score from the flat keys, and the host page bakes in NO score data (stays thin/poll-only). | VERIFIED | `test_overlay_bakes_no_score_after_rich_post` in `test_ui_overlay_page.py` (lines 159-191): after a rich POST with sentinel identity values (`RexSentinel`, `AnnaSentinel`, `GiudiceSentinel`), GET `/overlay` HTML contains none of those values; `Cache-Control: no-store` preserved; page references only the renderer script. 24 existing `test_ui_overlay_render.py` + `test_ui_score_entry.py` tests still green (flat-key display path unbroken). |
| 4 | New free-text fields (dog/handler name, judges) are HTML-escaped at the sink — no innerHTML, no `| safe`; a crafted `<script>` name renders as inert escaped text both on the overlay and in any form preview. | VERIFIED | `test_no_innerhtml_sink` asserts no `.innerHTML` sink in either `overlay-render.js` or `score-entry.js` (D-07a). `test_render_identity_script_payload_inert` and `test_form_preview_script_payload_inert` (D-07b node fake-DOM, ran green — node is present): `textContent === "<script>x</script>"` and `childElementCount === 0` / `children.length === 0` on both the lower-third and form preview. No `| safe` anywhere in Jinja templates (grep empty). |

**Score:** 4/4 truths verified

### Plan Must-Have Verification (Plans 18-01 + 18-02)

**Plan 18-01 must-haves (6/6 VERIFIED):**

| Must-Have | Status | Evidence |
|-----------|--------|----------|
| /overlay-json fields carry throws[].score / criteria{} / faults_breakdown{} ALONGSIDE every preserved flat key | VERIFIED | `test_ui_overlay_json.py` golden-snapshot tests |
| Every new subkey value is a Decimal STRING; no raw Decimal reaches json.dumps | VERIFIED | Code in `score_calc.py` lines 309, 331, 364, 372 all use `str(...)`. Heavy-absent gate (86/86 pass with no 500). |
| No legacy /overlay-json key is renamed or removed; 6-key envelope and per-discipline flat-key set frozen by CI snapshot | VERIFIED | `LEGACY_FLAT_KEYS` subset + envelope == assertion both green |
| Phase-16 round-trip equality still holds: disc_tf best-5 totale stays '19.0' byte-identical | VERIFIED | `test_score_calc.py` 17/17 pass including `test_csen_tf_best5` |
| Rich POST /score round-trips heavy-stack-absent; subkeys need no new import | VERIFIED | `test_imports.py` heavy-absent test with rich body + identity (26/26 pass) |
| Free-text identity keys cane/conduttore/giudici flow through _parse_structured_inputs on all three disciplines and echoed verbatim | VERIFIED | `app.py` lines 161-163; `test_imports.py` assertions `fields["cane"] == "Rex"`, `fields["conduttore"] == "Anna"` |

**Plan 18-02 must-haves (6/6 VERIFIED):**

| Must-Have | Status | Evidence |
|-----------|--------|----------|
| /overlay lower-third builds competitor identity from cane/conduttore via createTextNode ONLY; giudici never rendered | VERIFIED | `overlay-render.js` lines 150-156 (combine), 161-170 (createTextNode); grep for `giudici` in overlay-render.js: no matches |
| Crafted `<script>` renders as inert text on BOTH lower-third AND form preview | VERIFIED | D-07b node tests pass: `childElementCount === 0`, `children.length === 0` |
| No innerHTML / insertAdjacentHTML / `| safe` anywhere in overlay-render.js or score-entry.js | VERIFIED | `test_no_innerhtml_sink` passes; both JS files use only `textContent` / `createTextNode` / `createElementNS` |
| After a rich POST /score, overlay.txt is still a single non-empty line, length-bounded by _clean | VERIFIED | `test_overlay_txt_single_line_after_rich_post` green per all 3 disciplines; 64-char cap proven on 80-char nome |
| /overlay host page bakes in NO score/run data — thin/poll-only | VERIFIED | `test_overlay_bakes_no_score_after_rich_post` passes; no identity sentinel value in served HTML |
| Non-blocking real-OBS rig checklist documented; automated tests gate sign-off | VERIFIED | `docs/obs-setup.md` contains "Phase 18 — rich-POST overlay.txt rig check (NON-BLOCKING)" section (line 164+); explicitly states automated tests gate sign-off |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/score_calc.py` | Additive Decimal-string subkeys in `_compute_disc_tf` / `_compute_freestyle` / `_compute_agility` | VERIFIED | `faults_breakdown` present (lines 364, 372); `criteria` (line 331); `new_throws` with `score` (line 309) |
| `src/segugio/ui/app.py` | Free-text identity passthrough (cane/conduttore/giudici) in `_parse_structured_inputs` | VERIFIED | `conduttore` present at line 161; shared tuple loop for all three disciplines |
| `tests/test_ui_overlay_json.py` | D-05 golden-snapshot + 6-key envelope + subset assertions | VERIFIED | `LEGACY_FLAT_KEYS` at line 318; 4 new test functions all present and green |
| `tests/test_score_calc.py` | Per-discipline subkey unit assertions | VERIFIED | 4 new test functions at lines 104, 160, 230, 242; all pass |
| `src/segugio/ui/static/overlay-render.js` | `renderIdentity` builds from cane/conduttore via createTextNode; giudici excluded | VERIFIED | `conduttore` at lines 150-155; no `giudici` match; createTextNode at lines 161-169 |
| `src/segugio/ui/static/score-entry.js` | Universal identity inputs (cane/conduttore/giudici) with textContent-only preview | VERIFIED | All three `data-field` inputs at lines 170-185; `identity-echo` preview node wired |
| `tests/test_overlay_html_sink_gate.py` | D-07a grep both JS + D-07b node fake-DOM inertness proof | VERIFIED | `children.length` / `childElementCount` assertions present; 4/4 tests green |
| `tests/test_overlay_fallback_gate.py` | `test_overlay_txt_single_line_after_rich_post` per discipline | VERIFIED | Function present at line 76; asserts single-line + byte-equality + 64-cap; passes |
| `tests/test_ui_overlay_page.py` | `test_overlay_bakes_no_score_after_rich_post` | VERIFIED | Function at line 159; no-store + no sentinel values in HTML; passes |
| `docs/obs-setup.md` | D-08 NON-BLOCKING rich-POST overlay.txt rig checklist section | VERIFIED | "Phase 18 — rich-POST overlay.txt rig check (NON-BLOCKING)" at line 164 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `score_calc._compute_disc_tf` | `score.json` / `/overlay-json` throws[].score | `out["throws"] = new_throws` (rebuilt dicts with `"score": str(score)`) | VERIFIED | Line 317 assigns rebuilt throws; `str()` wraps at line 309 |
| `score_calc._compute_freestyle` | `score.json` / `/overlay-json` criteria{} | `out["criteria"] = criteria` dict of `str(snapped)` values | VERIFIED | Lines 327-331; `criteria[name] = str(snapped)` |
| `score_calc._compute_agility` | `score.json` / `/overlay-json` faults_breakdown{} | `out["faults_breakdown"] = {"course": str(...), "time": str(...)}` | VERIFIED | Lines 364, 372; elimination branch returns early (no `faults_breakdown`) |
| `app._parse_structured_inputs` cane/conduttore/giudici | `compute()` out (verbatim via `out = dict(fields)`) → `/overlay-json` echo | Identity allowlist loop after discipline branches; `get_overlay_json` returns `s.fields` verbatim | VERIFIED | `app.py` lines 161-163; route line 422 `"fields": s.fields` |
| `overlay-render.js renderIdentity` | DOM lower-third competitor line | `scvGet(fields,"cane")` + `scvGet(fields,"conduttore")` combined → `document.createTextNode(competitor)` | VERIFIED | Lines 150-156 (combine), 161-168 (createTextNode append) |
| `test_overlay_html_sink_gate.py` | renderIdentity + nomeEcho | node fake-DOM crafted-`<script>` render assertion | VERIFIED | D-07b tests at lines 87, 144; `textContent|children.length` assertions present |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `overlay-render.js renderIdentity` | `fields["cane"]`, `fields["conduttore"]` | `/overlay-json` poll → `s.fields` → `compute()` output → `_parse_structured_inputs` | Yes — POST /score writes real operator input through `_parse_structured_inputs` | FLOWING |
| `/overlay-json` route | `s.fields` dict | `score.json` on disk written by `post_score` → `compute()` | Yes — `compute()` calculates subkeys from real throw/score inputs | FLOWING |
| `overlay.txt` | flat scalar keys only | `render_overlay_text(written)` reads `throws`/`prese`/`zona`/`totale`/`nome`/`faults`/etc. (no dict/list subkeys) | Yes — flat keys byte-identical; subkeys never reach the flat renderer | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Subkey unit assertions (4 new) | `venv/Scripts/python.exe -m pytest tests/test_score_calc.py -k "subkey or criteria or breakdown or elimination" -v` | 5 passed in 1.37s | PASS |
| All 86 phase-18 target tests | `venv/Scripts/python.exe -m pytest tests/test_score_calc.py tests/test_ui_overlay_json.py tests/test_imports.py tests/test_overlay_html_sink_gate.py tests/test_overlay_fallback_gate.py tests/test_ui_overlay_page.py -v` | 86 passed in 2.80s | PASS |
| Overlay render + score-entry regressions | `venv/Scripts/python.exe -m pytest tests/test_ui_overlay_render.py tests/test_ui_score_entry.py -v` | 24 passed in 2.45s | PASS |
| D-07b node fake-DOM XSS tests | Included in 86-test run above (node present on dev box) | 2/2 node tests passed (not skipped) | PASS |
| score_render.py freeze target | `git diff f2408c8..HEAD -- src/segugio/ui/score_render.py` | Empty diff | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files declared or found for this phase. Automated test suite is the designated sign-off gate (D-08).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RBT-09 | 18-01, 18-02 | Fallback `overlay.txt` and contracts `/overlay` + `/overlay-json` remain invariant; new free-text fields HTML-escaped at the sink | SATISFIED | All 4 phase success criteria verified. 86 phase-target tests + 24 regression tests green. Freeze target `score_render.py` unmodified. XSS inertness proven at source (D-07a grep) and DOM level (D-07b node render). Note: `REQUIREMENTS.md` checkbox `[ ]` still Pending — explicitly deferred to verifier/orchestrator per scope guard in both summaries; no sign-off was done by the executor. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app.py` | 466 | `placeholder` (comment about browser 404 placeholder) | Info | Not an implementation stub; refers to browser behavior. |
| `score-entry.js` | 484, 496 | `placeholder: "mm:ss.cc"` | Info | HTML input `placeholder` attribute (UI pattern). Not a code stub. |

No TBD, FIXME, or XXX markers found in any phase-18 modified file.

### Human Verification Required

None. The only manual item (D-08 real-OBS read-from-file rig check) is explicitly designated NON-BLOCKING in the plan and in `docs/obs-setup.md`, with the automated test suite as the sole sign-off gate. The graphical `/overlay` display behavior is verified via: (a) the existing renderer test suite (24 tests green), (b) D-07b DOM render proof that `renderIdentity` builds the identity line correctly via `createTextNode`, and (c) `test_overlay_bakes_no_score_after_rich_post` confirming the host page stays thin/poll-only.

### Gaps Summary

No gaps. All phase success criteria and plan must-haves are verified against the actual codebase. The 5 pre-existing full-suite failures documented in `.planning/phases/18-rich-data-model-overlay-continuity-regression/deferred-items.md` (NDI hardware x2, node `mirror.mjs` ESM harness, two cp1252-mojibake console.html reads) are confirmed pre-existing at commit `f2408c8` and are not attributable to phase 18.

---

_Verified: 2026-06-27_
_Verifier: Claude (gsd-verifier)_
