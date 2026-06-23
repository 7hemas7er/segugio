---
phase: 16-shared-entry-component-dedicated-page-server-authoritative-p
fixed_at: 2026-06-23T08:55:00Z
review_path: .planning/phases/16-shared-entry-component-dedicated-page-server-authoritative-p/16-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 16: Code Review Fix Report

**Fixed at:** 2026-06-23
**Source review:** .planning/phases/16-shared-entry-component-dedicated-page-server-authoritative-p/16-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (Critical + Warning): 6
- Fixed: 6
- Skipped: 0

All in-scope findings were applied in an isolated git worktree on branch
`gsd-reviewfix/16-49`, each committed atomically, then verified with the affected
test suite. Info findings (IN-01, IN-02, IN-03) were out of the `critical_warning`
scope and not addressed.

## Fixed Issues

### CR-01: Non-dict JSON body crashes `POST /score` (HTTP 500), bypassing the validate→400 contract

**Files modified:** `src/segugio/ui/app.py`
**Commit:** 0e69467
**Applied fix:** Changed `is_json = json_body is not None` to
`is_json = isinstance(json_body, dict)`. A non-object JSON body (`[1,2,3]`, `42`,
`true`, `"x"`) is no longer treated as a structured body that would crash on
`raw.get(...)`; it falls through to the empty-form / legacy path (now a no-op via
WR-04). Honours the project hard rule "nessun crash ammesso" — no unhandled 500 on
malformed input. Behaviorally verified: list and int JSON bodies now return 204
(was 500).

### CR-02: Non-iterable `throws` crashes `validate()` (HTTP 500) on the authoritative path

**Files modified:** `src/segugio/ui/score_calc.py`
**Commit:** 53f2085
**Applied fix:** Added an `elif not isinstance(throws, (list, tuple))` branch before
the `enumerate(throws)` loop that appends a `{"field": "throws", "message": "Formato
lanci non valido."}` error. A crafted authoritative POST `{"discipline":"disc_tf",
"throws":42}` now returns the contracted 400 + writes nothing instead of raising
`TypeError` → 500. Decimal/numeric paths untouched. Behaviorally verified: returns
400 with the `throws` error contract.

### WR-01: Python/JS validate DRIFT on a non-list `throws`

**Files modified:** `src/segugio/ui/static/score-calc.js`, `tests/_score_fixtures.py`
**Commit:** 0fdcfbd
**Applied fix:** Mirrored the CR-02 guard in the advisory JS port: added
`else if (!Array.isArray(throws))` pushing the identical `{field: "throws", message:
"Formato lanci non valido."}` so the JS no longer silently returns `[]` (valid) on a
non-array `throws` while Python rejects. Added a `{"throws": 42}` case (error_field
`"throws"`) to `INVALID_FIXTURES` so the node-vs-Python drift-guard
(`tests/test_ui_score_calc_js.py::test_validate_parity`) pins this parity. The
drift-guard test ran (node available) and confirms Python↔JS agreement on the
non-iterable path.

### WR-02: Agility `deduct_from_100` compute path unexercised by the drift-guard

**Files modified:** `tests/_score_fixtures.py`, `tests/test_ui_score_calc_js.py`
**Commit:** 1038cbf
**Applied fix:** Added `PROFILE_JSON_DEDUCT` (a `deduct_from_100` agility profile)
and an agility fixture carrying its own `profile_json` (tempo 00:34.50 / sct
00:30.00 / course_deductions 10 → 100 − 10 − 5 = 85). Added per-fixture profile
support to the three node parity tests via a `_profile_from_json` /
`_py_profile_for` helper (builds the Python `ScoringProfile` from the decimal-string
JSON, float-free) and `f.profile_json || _p` on the JS side. The
`100 - course_deductions - Decimal(time_faults)` branch is now compared
node-vs-Python (`result`/`totale`/`faults` keys), closing the silent-drift gap. The
parity test ran and passed.

### WR-03: `_compute_freestyle` nome/timer carry-over differs Python vs JS (latent)

**Files modified:** `src/segugio/ui/static/score-calc.js`
**Commit:** 1999756
**Applied fix:** Replaced `if (!("nome" in out)) out.nome = out.nome || "";` (and
likewise `timer`) with the direct mirror `if (!("nome" in out)) out.nome = "";`. The
old `|| out.nome` RHS read an always-undefined value (the guard had already proved
the key absent) and was misleading; the new form mirrors Python's
`out.setdefault("nome", out.get("nome", ""))` exactly. Behavior unchanged for
present/absent `nome`/`timer`; the misleading surface is removed.

### WR-04: Empty / no-body legacy POST silently writes an empty score and bumps gen

**Files modified:** `src/segugio/ui/app.py`
**Commit:** c00766b
**Applied fix:** Added `if not fields: return ("", 204)` in the legacy branch after
dropping empty values. An all-empty legacy POST (empty form, or only empties) is now
a no-op — it does NOT overwrite `score.json`, blank `overlay.txt`, or bump `gen`,
preserving the on-air score (the "previous score invariant"). Run-state
(running/started_at) is untouched by this path. Behaviorally verified: empty form
body returns 204 and writes nothing.

## Verification

3-tier verification applied to every fix:
- Tier 1 (re-read affected lines): passed for all 6.
- Tier 2 (syntax check): `ast.parse` for `.py` files, `node -c` for `score-calc.js`
  — all passed.
- Behavioral smoke test of CR-01 / CR-02 / WR-04 against the worktree app confirmed
  the malformed-input cases return 400/204, never 500.

**Affected test suite (run against the worktree code with the py3.14 `venv/`):**

```
tests/test_ui_score_authoritative.py
tests/test_ui_score_calc_js.py
tests/test_ui_score_entry.py
tests/test_ui_score.py
tests/test_imports.py
```

Result: **46 passed, 0 failed, 0 skipped** (2.21s). The node-vs-Python drift-guard
in `test_ui_score_calc_js.py` ran all 4 cases (node available — not skipped),
confirming the WR-01 non-list parity and WR-02 deduct-branch coverage.

**Logic-verification note:** All six fixes are guard/contract changes with explicit
behavioral confirmation (status-code smoke test + green drift-guard), so they are
recorded as `fixed` rather than `fixed: requires human verification`. The semantics
(reject-on-bad-shape, no-op-on-empty, byte-parity) were exercised directly.

---

_Fixed: 2026-06-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
