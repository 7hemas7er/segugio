---
phase: 16-shared-entry-component-dedicated-page-server-authoritative-p
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/segugio/ui/app.py
  - src/segugio/ui/static/score-calc.js
  - src/segugio/ui/static/score-entry.js
  - src/segugio/ui/templates/score-entry.html
  - tests/_score_fixtures.py
  - tests/test_ui_score_authoritative.py
  - tests/test_ui_score_calc_js.py
  - tests/test_ui_score_entry.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-06-23
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase-16 server-authoritative `POST /score` work: the new authoritative route in
`app.py`, the advisory `score-calc.js` Decimal port, the shared `score-entry.js` component, the
thin `score-entry.html` host, and the four test files. Cross-referenced the JS port against the
Python authority `src/segugio/ui/score_calc.py`, the record/channel serializers
(`opcomm/records.py`, `opcomm/channel.py`), and the renderer (`score_render.py`).

The security posture of the phase's headline threat (XSS at the new free-text sink) is genuinely
clean: `score-entry.js` and `score-entry.html` contain no `innerHTML` / `dangerouslySetInnerHTML`
sink and no `| safe` Jinja filter; every operator value reaches the DOM via `textContent` /
`createTextNode` / `createElementNS`, and the profile blob is injected with `| tojson` inside a
`<script type="application/json">` (the correct, escaped sink). The Decimal-equivalence port is
also correct on every path the drift-guard exercises.

However, the authoritative route is NOT robust against malformed request bodies: two distinct
hand-crafted POSTs reach an unguarded `.get()` / `enumerate()` and raise an unhandled exception
(HTTP 500). These bypass the "validate → 400 → write-nothing" contract by crashing before it. There
is also a real validate-parity DRIFT between Python and JS on a non-list `throws` value that the
existing fixtures do not cover, and the entire agility `deduct_from_100` compute path is unexercised
by the byte-parity drift-guard despite being a shipped code path.

## Critical Issues

### CR-01: Non-dict JSON body crashes `POST /score` (HTTP 500), bypassing the validate→400 contract

**File:** `src/segugio/ui/app.py:347-356`
**Issue:** The route does `json_body = request.get_json(silent=True)` then `is_json = json_body is
not None` and `raw = json_body`. `get_json(silent=True)` returns whatever the body parsed to — for a
body like `[1,2,3]`, `42`, `true`, or `"x"` it returns a list / int / bool / str (all non-`None`),
so `is_json` is `True` and `raw` is that non-dict. The very next line calls
`raw.get("discipline", ...)`, which raises `AttributeError` on a list/int/str. There is no
`@app.errorhandler` registered (confirmed: none in the file), so Flask returns a 500. The phase's
core contract is "invalid input → 400 + write nothing"; a 500 is neither, and a crafted body
trivially triggers it. Because the console is multi-threaded with `threaded=True`, this is an
availability defect on the operator console (not a director crash, but still a live-tool failure).

**Fix:**
```python
json_body = request.get_json(silent=True)
is_json = isinstance(json_body, dict)
raw = json_body if is_json else request.form
```
Use `isinstance(json_body, dict)` instead of `json_body is not None` so any non-object JSON body
falls through to the form path (which is an empty `ImmutableMultiDict` → legacy branch → harmless),
or alternatively return `("corpo non valido", 400)` when a JSON body is present but not an object.

### CR-02: Non-iterable `throws` crashes `validate()` (HTTP 500) on the authoritative path

**File:** `src/segugio/ui/score_calc.py:197-206` (reached from `app.py:375-376`)
**Issue:** A crafted authoritative POST `{"discipline":"disc_tf","throws":42}` flows through
`_parse_structured_inputs` (which passes `throws` through verbatim) into `validate`. There,
`throws = fields.get("throws")` is `42`; `if not throws:` is `False` (42 is truthy), so it enters
`for i, throw in enumerate(throws):` → `enumerate(42)` raises `TypeError: 'int' object is not
iterable`. With no error handler this is an unhandled 500 — again bypassing the validate→400→
write-nothing contract by crashing before validation can return errors. (A string `throws:"abc"`
does NOT crash because the per-item `isinstance(throw, dict)` guard absorbs it, but a number/bool/
object does.)

**Fix:** Guard the `throws` shape before iterating:
```python
throws = fields.get("throws")
if not throws:
    errors.append({"field": "throws", "message": "Almeno un lancio è richiesto."})
elif not isinstance(throws, (list, tuple)):
    errors.append({"field": "throws", "message": "Formato lanci non valido."})
else:
    for i, throw in enumerate(throws):
        ...
```
Note this file is outside the literal phase file-list but is the validation authority the phase's
route delegates to and the one the drift-guard pins; the crash is reachable only via the Phase-16
authoritative route, so it is in scope for this review.

## Warnings

### WR-01: Python/JS validate DRIFT on a non-list `throws` (one crashes, the other says "valid")

**File:** `src/segugio/ui/static/score-calc.js:251-267` vs `src/segugio/ui/score_calc.py:196-206`
**Issue:** For `throws = 42` (or any non-iterable non-list), the JS port computes
`!throws` → `false`, `throws.length === 0` → `false` (length is `undefined`), enters the else, then
`for (let i = 0; i < throws.length; i++)` with `throws.length === undefined` → `0 < undefined` is
`false`, so the loop never runs and `validate` returns `[]` (VALID). Python on the same input raises
(see CR-02). This is a genuine drift: the advisory port and the authority disagree on the same
input, violating the "byte-exact mirror" invariant the drift-guard is meant to protect. The
existing `INVALID_FIXTURES`/`FIXTURES` never feed a non-list `throws`, so the guard does not catch
it. Fixing CR-02 (Python rejects with a `throws` error) requires the JS port to mirror it (add a
non-array branch that pushes the same `throws` error) to keep parity.

**Fix:** After fixing CR-02 in Python, mirror in JS:
```js
const throws = fields.throws;
if (!throws || throws.length === 0) {
  errors.push({ field: "throws", message: "Almeno un lancio è richiesto." });
} else if (!Array.isArray(throws)) {
  errors.push({ field: "throws", message: "Formato lanci non valido." });
} else {
  for (let i = 0; i < throws.length; i++) { ... }
}
```
…and add a non-list `throws` case to `INVALID_FIXTURES` so the drift-guard pins the new parity.

### WR-02: Agility `deduct_from_100` compute path is shipped but unexercised by the drift-guard

**File:** `src/segugio/ui/static/score-calc.js:441-451`, `tests/_score_fixtures.py:54-121`
**Issue:** `FIXTURES` only covers agility with `agility_model: "count_up"`. The
`deduct_from_100` branch in both `compute` implementations (`100 - course_deductions -
Decimal(time_faults)`) is never compared node-vs-Python, so any future drift there ships silently.
The JS branch also routes `timeFaults` (a `BigInt`) through `_decFromInt(Number(timeFaults))` — a
`BigInt→Number→Dec` round-trip that diverges from Python's `Decimal(time_faults)` for values above
`2**53`; not reachable with realistic time faults, but untested and asymmetric with the count_up
branch, which keeps `BigInt` arithmetic throughout. Manual trace shows the path is currently correct
for realistic inputs, but "correct + untested on a money/score path" is exactly what the drift-guard
exists to prevent.

**Fix:** Add at least one `deduct_from_100` fixture (a profile with
`agility_model: "deduct_from_100"` and `course_deductions`) to `FIXTURES`/`INVALID_FIXTURES` so
`test_compute_byte_parity_with_python` / `test_validate_parity` cover the branch. Optionally replace
`_decFromInt(Number(timeFaults))` with a BigInt-direct `Dec` constructor for symmetry with the
count_up branch.

### WR-03: `_compute_freestyle` nome/timer carry-over differs Python vs JS (latent, not yet drift-tested)

**File:** `src/segugio/ui/static/score-calc.js:416-417` vs `src/segugio/ui/score_calc.py:324-325`
**Issue:** Python uses `out.setdefault("nome", out.get("nome", ""))` (a no-op when present, sets
`""` when absent). JS uses `if (!("nome" in out)) out.nome = out.nome || "";` — when `nome` is
absent the RHS reads `out.nome` (undefined) `|| ""` → `""`, matching; but the two expressions are
structurally different and easy to break in future edits. The drift-guard only asserts the FLAT
summary keys (`totale`/`prese`/`zona`/`faults`/`result` at `test_ui_score_calc_js.py:111`) — `nome`
and `timer` are NOT compared, so a real divergence in these carried-over fields would not be caught.
Today's behavior is equivalent; the risk is the unguarded surface.

**Fix:** Either add `nome`/`timer`/`tempo`/`sct` to the parity key list in
`test_compute_byte_parity_with_python`, or simplify the JS to a direct mirror:
`if (!("nome" in out)) out.nome = "";` (and likewise `timer`), removing the misleading `|| out.nome`.

### WR-04: Empty / no-body legacy POST silently writes an empty score and bumps gen

**File:** `src/segugio/ui/app.py:363-370`
**Issue:** A `POST /score` with an empty form body (or any urlencoded body with no structured key
and only empties) is classified legacy (`_is_legacy_score_post` returns `True` because
`keys & _STRUCTURED_KEYS` is empty), then `fields` is built dropping empties (WR-05 comment), so
`fields == {}`, and `_write_score_doc(ScoreDoc(discipline=disc_tf, fields={}))` runs: it overwrites
`score.json`, rewrites `overlay.txt` to a blank-valued line (`"Prese:   Zona:   Totale: "`), and
bumps `gen`. An accidental empty POST therefore clobbers the on-air score with blanks — the opposite
of the phase's "previous score invariant" intent for the authoritative path. The authoritative path
correctly write-nothing on empty; the legacy path does not.

**Fix:** Treat an all-empty legacy body as a no-op:
```python
if _is_legacy_score_post(raw, is_json):
    fields = {k: v for k, v in raw.items() if k not in _NON_SCORE_KEYS and str(v).strip()}
    if not fields:
        return ("", 204)  # nothing to write; leave the on-air score untouched
    _write_score_doc(ScoreDoc(discipline=discipline, fields=fields))
    return ("", 204)
```

## Info

### IN-01: `recompute()` catches and swallows compute errors with a bare `catch (_e)`

**File:** `src/segugio/ui/static/score-entry.js:429-433`, `:483-487`
**Issue:** Both `recompute` and `validateOnBlur` wrap the calc in `try { ... } catch (_e) {}`
discarding the error. This is intentional (advisory UI must never throw) and acceptable, but it
silently masks a real port bug during development — e.g. the WR-01 non-list case or a future
`Dec`-helper exception would just show "—" with no console trace. Consider
`console.debug(_e)` inside the catch so dev builds surface a broken advisory calc without affecting
operator UX.

### IN-02: Duplicated `_TIME_RX` / Decimal helper logic across Python and JS is inherent but unflagged

**File:** `src/segugio/ui/static/score-calc.js:31-243` mirrors `src/segugio/ui/score_calc.py:58-177`
**Issue:** The entire Decimal helper + time/zone/increment logic is hand-duplicated in two languages.
This is a deliberate design (the sentinel `gsd:score-calc-mirror` block + drift-guard), not a defect
— but the only thing keeping them in sync is the node-vs-Python test, which (per WR-01/WR-02/WR-03)
does not cover every branch. No action beyond closing the WR gaps; noted so the coupling is explicit
in the substrate.

### IN-03: `started_at` skew anchor relies on operator-console wall clock matching client `Date.now()`

**File:** `src/segugio/ui/app.py:401`, `:445`
**Issue:** `_bump_overlay_run(running=True, started_at=time.time())` and `server_now: time.time()`
assume the console host clock and the overlay client clock are comparable for the Phase-11 timer skew
math. This is documented (comments at `:399`, `:445`) and out of this phase's compute scope, but on a
field rig with un-synced device clocks the freestyle timer offset can be wrong. No fix required in
Phase 16; flagging for the Phase-11 timer milestone.

---

_Reviewed: 2026-06-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
