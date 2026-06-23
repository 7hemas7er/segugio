---
phase: 16-shared-entry-component-dedicated-page-server-authoritative-post
plan: 01
subsystem: ui
tags: [flask, score_calc, decimal, server-authoritative, drift-guard, vanilla-js, bigint, csen]

# Dependency graph
requires:
  - phase: 15-pure-calc-validation-core-scoring-profiles
    provides: "score_calc.validate/compute authority + ScoringProfile + CSEN_DISC_PROFILE (the engine this plan wires to the route)"
  - phase: 11-overlay-renderer
    provides: "overlay-render.js node-vs-Python drift-guard precedent (gsd:scv01-mirror) cloned for score-calc.js"
provides:
  - "Authoritative POST /score: validate RAW -> 400-write-nothing on invalid -> Decimal recompute -> atomic write (SCC-01)"
  - "Additive create_app(profile, sport) signature (default CSEN_DISC_PROFILE, crash-isolation safe)"
  - "Byte-exact advisory score-calc.js port pinned by a node-vs-Python compute/validate drift-guard (SCC-03)"
  - "Thin legacy back-compat branch keeping the pre-Phase-16 display-only console form round-tripping (Open Q1 (a))"
  - "Wave 0 test scaffolds + shared PROFILE_JSON/FIXTURES for Plan 16-02 to consume"
affects: [16-02-shared-entry-component, 17-console-modal, 18-overlay-fields]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Decimal-equivalent JS arithmetic via a coefficient(BigInt)+exponent helper (mirrors Python decimal.Decimal __str__) — never Number float math"
    - "validate-before-write authoritative route ordering (400 + write nothing keeps prev on-air byte-identical)"
    - "wire-shape discriminated /score route: JSON/structured -> authoritative; urlencoded display-only -> legacy back-compat"

key-files:
  created:
    - "src/segugio/ui/static/score-calc.js"
    - "tests/_score_fixtures.py"
    - "tests/test_ui_score_authoritative.py"
    - "tests/test_ui_score_calc_js.py"
    - "tests/test_ui_score_entry.py"
  modified:
    - "src/segugio/ui/app.py"

key-decisions:
  - "score-calc.js uses a BigInt coefficient + exponent Decimal helper to match Python Decimal string output byte-for-byte (18.0, 30.00, 40)"
  - "Legacy detector routes ANY urlencoded body lacking a structured key to the display-only back-compat branch (Open Q1 (a)), not a narrow flat-key allowlist"
  - "Tasks 3 and 4 co-implemented (legacy branch built alongside the authoritative path) to avoid leaving test_ui_score.py red between commits"

patterns-established:
  - "BigInt fixed-scale Decimal port for byte-exact JS<->Python numeric parity"
  - "Authoritative route = validate-before-write; client port is advisory-only, pinned honest by a drift-guard"

requirements-completed: [SCC-01, SCC-03]

# Metrics
duration: ~25min
completed: 2026-06-23
---

# Phase 16 Plan 01: Server-Authoritative POST /score + Advisory score-calc.js Summary

**POST /score is now the SOLE authority (validate RAW -> 400-write-nothing -> Decimal recompute -> atomic write), and score-calc.js is a BigInt-Decimal byte-exact advisory port pinned by a live node-vs-Python compute/validate drift-guard.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-23T00:00:00Z (approx)
- **Completed:** 2026-06-23T00:20:00Z
- **Tasks:** 4
- **Files modified:** 6 (5 created, 1 modified)

## Accomplishments
- `POST /score` rewritten authoritative: a JSON body's RAW structured inputs (`throws[]`, freestyle categories + adjustment, agility time/SCT/faults-or-deductions + elimination) are validated FIRST; on any error the route returns `400 {"errors": [...]}` and writes NOTHING (the previous on-air `score.json`/`overlay.txt` stays byte-identical); on valid input the total is recomputed in Python (`score_calc.compute`, Decimal) and atomically written. The operator can never air a client-computed total (SCC-01).
- `create_app` gained additive `profile=None, sport="disc_dog"` args (lazy `score_calc` import, default `CSEN_DISC_PROFILE`) — every existing single-/triple-arg caller stays green and the crash-isolation allowlist holds.
- `score-calc.js` shipped as a byte-exact advisory port of `score_calc.compute`/`validate` inside a `gsd:score-calc-mirror` sentinel block, using a coefficient(BigInt)+exponent Decimal helper so totals match Python's `Decimal` string output exactly (`18.0`, `30.00`, `40`). Pinned by a node-vs-Python drift-guard across best-N, the 0.5 bonus, CR-01 `"false"`/`"on"` flags, freestyle cap, agility ceil, and the elimination sentinel (SCC-03).
- A thin, P17-marked legacy back-compat branch keeps the pre-Phase-16 display-only console form (and every prior urlencoded display-only POST) round-tripping (Open Q1 (a)).
- All Wave 0 scaffolds landed: 3 test files + the shared `PROFILE_JSON` (decimal-string CSEN profile) + `FIXTURES`/`INVALID_FIXTURES`, with the Plan-02 entry tests skipping cleanly so the file collects green now.

## Task Commits

1. **Task 1: Wave 0 scaffolds + shared PROFILE_JSON fixture (RED)** - `b9c75a9` (test)
2. **Task 2: score-calc.js byte-exact advisory port + drift-guard** - `aecebe3` (feat)
3. **Task 3: authoritative POST /score + additive create_app(profile, sport)** - `1024747` (feat)
4. **Task 4: legacy back-compat fix (Open Q1) + crash-isolation re-verify** - `9b93c32` (fix)

_TDD note: the RED scaffolds (Task 1) and the GREEN implementations (Tasks 2-3) are split across commits per the plan's `tdd="true"` tasks. The `test(...)` -> `feat(...)` gate sequence is present in the log._

## Files Created/Modified
- `src/segugio/ui/static/score-calc.js` - Advisory client port of compute/validate; BigInt+exponent Decimal helper; dual-exported on `window.SEGUGIO_SCORE_CALC` + `module.exports`; `gsd:score-calc-mirror` sentinel block.
- `src/segugio/ui/app.py` - Additive `create_app(profile, sport)`; rewritten authoritative `post_score`; new `_parse_structured_inputs` / `_is_legacy_score_post` helpers; `_write_score_doc` write consolidation.
- `tests/_score_fixtures.py` - `PROFILE_JSON` (CSEN as decimal strings, self-tested `per_throw_cap == "5"`), `FIXTURES`, `INVALID_FIXTURES`.
- `tests/test_ui_score_authoritative.py` - SCC-01 Flask-client gates (400-write-nothing, recompute, run-state preserve, round-trip total equality, legacy round-trip).
- `tests/test_ui_score_calc_js.py` - SCC-03 node-vs-Python compute/validate drift-guard + sentinel/dual-export static asserts.
- `tests/test_ui_score_entry.py` - Plan 16-02 stubs (skip until the component exists; file collects green).

## Decisions Made
- **BigInt Decimal port:** Python's `Decimal` preserves operand scale in its string output (`Decimal("0")+...` -> `18.0`; quantized sums -> `30.00`). A JS `Number` port would drift and mis-format. The port tracks `(coef: BigInt, exp, sign)` and replicates Decimal add/sub (result exp = min operand exp), quantize-half-up, ceiling-to-integral, and the fixed-point `__str__` for `exp <= 0` (every scoring value qualifies).
- **Legacy detector breadth:** routing ONLY a fixed flat-key allowlist to back-compat 400'd legitimate pre-existing display-only POSTs (e.g. `{"points": "10"}`). Corrected to: any urlencoded body WITHOUT a structured key is legacy display-only; JSON bodies and structured keys are authoritative.
- **Tasks 3 & 4 co-implemented:** the legacy branch was built in the same change as the authoritative path so `tests/test_ui_score.py` never went red between task commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Invalid freestyle "cap" fixture exceeded per-category range**
- **Found during:** Task 2 (score-calc.js parity)
- **Issue:** The freestyle cap fixture used `catch="10.5"`, but each category is itself bounded 0-10, so `validate` (correctly) rejected it — the "valid fixture validates clean" parity assert failed on both Python and JS.
- **Fix:** Changed the fixture to four maxed `10` categories (sum 40 == `freestyle_max`), exercising the clamp at its boundary with valid inputs.
- **Files modified:** tests/_score_fixtures.py
- **Verification:** `test_validate_parity_valid_fixtures_clean` + `test_compute_byte_parity_with_python` green.
- **Committed in:** `aecebe3` (Task 2 commit)

**2. [Rule 1 - Bug] Legacy back-compat branch too narrow -> pre-existing display-only POSTs 400'd**
- **Found during:** Task 4 (full-suite wave-merge run)
- **Issue:** `_is_legacy_score_post` only recognized a fixed flat-key allowlist. Pre-existing tests POST arbitrary display-only keys (`{"discipline": "disc_tf", "points": "10"}`); these fell into the authoritative path, failed `disc_tf` validation (empty `throws`), returned 400, and skipped the gen-bump write — breaking `test_ui_overlay_json::test_gen_bumps_on_run_and_score` and `::test_score_gen_bump_preserves_live_run_when_disk_torn`.
- **Fix:** Widened the detector: any urlencoded body lacking a structured key routes to the display-only back-compat branch.
- **Files modified:** src/segugio/ui/app.py
- **Verification:** `tests/test_ui_overlay_json.py`, `tests/test_ui_score.py`, `tests/test_ui_score_authoritative.py` all green.
- **Committed in:** `9b93c32` (Task 4 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug). **Impact:** Both essential for correctness (fixture validity; broadcast-integrity gen-bump round-trip). No scope creep.

## Issues Encountered
- The shared fixtures module required a `from tests._score_fixtures import ...` form: `pyproject.toml` sets `pythonpath=["src"]` only and `tests/` is a package (has `__init__.py`), so a bare `from _score_fixtures import ...` did not resolve. Switched to the `tests.` package-qualified import (verified working).
- A `git checkout`/`stash` round-trip (used to confirm the 5 failing UI/NDI tests were pre-existing at phase-start `0958d94`) briefly surfaced an old copy of `app.py`; the fix was restored from stash and re-verified present before committing.

## Known Stubs
- `tests/test_ui_score_entry.py` defines Plan-02 component tests that `pytest.skip("implemented in 16-02")`. Intentional Wave-0 scaffold — `score-entry.js` / `score-entry.html` / `GET /score-entry` are explicitly reserved for Plan 16-02 (documented in the plan's `<artifacts_this_phase_produces>`). The gates exist so 16-02 has its acceptance targets ready.

## Pre-existing Failures (out of scope)
Five suite failures were confirmed failing identically at the phase-start commit `0958d94` (logged in `deferred-items.md`), unrelated to this plan: 2 NDI hardware tests, the explainability leaderboard node test, and the `console.html` scv-unification + tablet-layout template tests (the P17 console surface this plan deliberately does not touch).

## Next Phase Readiness
- Plan 16-02 can wire the shared `score-entry.js` component against a proven, locked contract: the authoritative `POST /score` (JSON `throws[]` + per-discipline raw inputs), the advisory `score-calc.js` (`window.SEGUGIO_SCORE_CALC.compute/validate`), and the shared `PROFILE_JSON`/`FIXTURES`.
- The `create_app(profile, sport)` injection point and the entry-test stubs are in place. The `_profile_to_json` / `_score_cfg` injection helper, `GET /score-entry` route, and `score-entry.html` remain reserved for 16-02.

## Self-Check: PASSED
- Created files verified present: `src/segugio/ui/static/score-calc.js`, `tests/_score_fixtures.py`, `tests/test_ui_score_authoritative.py`, `tests/test_ui_score_calc_js.py`, `tests/test_ui_score_entry.py`.
- Commits verified in `git log`: `b9c75a9`, `aecebe3`, `1024747`, `9b93c32`.

---
*Phase: 16-shared-entry-component-dedicated-page-server-authoritative-post*
*Completed: 2026-06-23*
