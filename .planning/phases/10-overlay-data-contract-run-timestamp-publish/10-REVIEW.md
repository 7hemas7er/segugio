---
phase: 10-overlay-data-contract-run-timestamp-publish
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/segugio/config/models.py
  - src/segugio/opcomm/channel.py
  - src/segugio/opcomm/records.py
  - src/segugio/ui/app.py
  - tests/conftest.py
  - tests/test_config_overlay.py
  - tests/test_imports.py
  - tests/test_opcomm_overlay_run.py
  - tests/test_ui_overlay_json.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-14
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 10 adds the `/overlay-json` data contract, the console-owned `overlay_run.json`
sidecar (`OverlayRunDoc` + `read/write_overlay_run`), the `OverlayParams` config sub-model,
and run-edge gen-stamping in the Flask console. The crash-isolation invariant (RBT-07),
the byte-for-byte `runstate.json` separation (D-03), the never-raise read boundary (RBT-04),
and the wall-clock `started_at`/`server_now` skew anchor are all implemented as designed and
covered by tests. The accepted LAN/no-auth posture and the deliberate same-domain `time.time()`
choices were not re-litigated, per the phase context.

One real defect escapes the never-raise boundary: a torn/poisoned `overlay_run.json` (or a
score file) containing `NaN`/`Infinity` passes the `float(...)` coercion silently and is then
re-emitted by `/overlay-json` as literal `NaN` — which is **invalid JSON** and breaks the
Phase-11 overlay client's parse. This is a NEW exposure introduced by the route (info from a
torn/attacker-touched sidecar propagated into a poisoned response) and is the kind of
boundary defeat RBT-04 / D-04 exists to prevent. Several warnings concern inconsistent
boundary hardening between the sibling readers and silent bool→float coercion.

## Critical Issues

### CR-01: `NaN`/`Infinity` in `overlay_run.json` defeats the never-raise boundary and poisons `/overlay-json` with invalid JSON

**File:** `src/segugio/opcomm/channel.py:269` (and the response path `src/segugio/ui/app.py:259`)
**Issue:**
`read_overlay_run` coerces `started_at` with `float(started)`. Python's `json.loads` accepts
the non-standard tokens `NaN`, `Infinity`, `-Infinity` by default, and `float(nan)` /
`float(inf)` succeed without raising — so a torn, legacy, or attacker-touched
`overlay_run.json` like `{"running": true, "started_at": NaN, "gen": 0}` flows straight
through the "safe-default" reader as a valid `OverlayRunDoc(started_at=nan)`. The
`/overlay-json` route then serializes it via Flask `jsonify`, which emits literal
`{"started_at":NaN,...}` — confirmed:

```
flask jsonify({'started_at': float('nan')}) -> {"started_at":NaN}
```

`NaN` is **not valid JSON** (RFC 8259). The Phase-11 overlay client's `await resp.json()` /
`JSON.parse` throws on it, breaking the live overlay — exactly the "a torn/absent source must
never break the consumer" guarantee RBT-04 / D-04 promise. This is also the NEW route-level
exposure the phase context asked to be flagged: a poisoned sidecar leaks an
unparseable payload out of `/overlay-json` instead of degrading to a safe default. The same
hole exists for any future float-typed field on this channel; `gen`/`tick` are protected only
incidentally because `int(nan)` raises (and is caught), but `started_at` is not.

**Fix:** Reject non-finite floats at the read boundary so they collapse to the safe default
(`None`), keeping the reader truly never-poison:

```python
import math
...
started = data.get("started_at")
if started is None:
    started_val = None
else:
    started_val = float(started)
    if not math.isfinite(started_val):
        raise ValueError(f"non-finite started_at {started_val!r}")  # caught below -> default
return OverlayRunDoc(
    running=bool(data.get("running", False)),
    started_at=started_val,
    gen=int(data.get("gen", 0)),
)
```

Belt-and-suspenders (defends every float field at once): also disallow the non-standard tokens
on read with `json.loads(raw, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))`
inside `_read_json`, so `NaN`/`Infinity` never even enter a record.

## Warnings

### WR-01: `read_score` does not guard `fields` to a dict — a non-dict leaks through to `/overlay-json`

**File:** `src/segugio/opcomm/channel.py:91-94` (echoed at `src/segugio/ui/app.py:257`)
**Issue:**
`read_score` builds `fields=data.get("fields", {}) or {}`. If the on-disk `score.json` has
`"fields": [1,2,3]` (or a string/number), the truthy non-dict value is kept verbatim and
`ScoreDoc(fields=[...])` accepts it — `ScoreDoc.__post_init__` validates only `discipline`,
never the `fields` type (confirmed: `ScoreDoc(fields=[1,2,3]).fields == [1,2,3]`). `/overlay-json`
then echoes a list as `fields`, violating the documented `{label: value}` dict contract the
Phase-11 renderer iterates. The sibling readers DO guard their containers
(`read_status`: `alive if isinstance(alive, dict) else {}`; `read_preview`:
`cams if isinstance(cams, dict) else {}`), so this reader is the odd one out.
**Fix:** Mirror the sibling guard:
```python
raw_fields = data.get("fields", {})
fields = raw_fields if isinstance(raw_fields, dict) else {}
return ScoreDoc(discipline=data.get("discipline", ScoreDoc().discipline), fields=fields)
```

### WR-02: `OverlayRunDoc.__post_init__` silently coerces a bool `started_at` to `1.0`/`0.0`

**File:** `src/segugio/opcomm/records.py:236-237` (reader path `src/segugio/opcomm/channel.py:269`)
**Issue:**
`started_at` is coerced with `float(self.started_at)` whenever it is not `None`. JSON `true`/`false`
are valid Python bools, and `float(True) == 1.0`, `float(False) == 0.0`. A torn/hand-edited
`overlay_run.json` with `"started_at": true` is therefore silently accepted as a "run started at
epoch 1.0" instead of being rejected to the safe default. Because the `started_at > 1_000_000_000`
sanity used in tests only runs on the WRITE path, this bad value would survive a read and feed
Phase-11's skew math a garbage anchor. `bool` is a subclass of `int`, so an `isinstance` check
must explicitly exclude it.
**Fix:** Reject bools (and, with CR-01, non-finite) at the boundary:
```python
if self.started_at is not None:
    if isinstance(self.started_at, bool):
        raise ValueError("started_at must be a number, not bool")
    object.__setattr__(self, "started_at", float(self.started_at))
```
(The reader's `except (ValueError, TypeError)` already collapses a raise to the safe default.)

### WR-03: `_bump_score_gen` re-reads `overlay_run.json` from disk under lock — a stale/torn round-trip can drop `running`/`started_at`

**File:** `src/segugio/ui/app.py:125-138`
**Issue:**
`/score` is documented as "NOT a run edge: preserve running/started_at" but it preserves them by
reading the CURRENT doc back from disk (`current = read_overlay_run(...)`) and re-writing it with
`gen+1`. `read_overlay_run` is never-raise: if the file is momentarily torn, absent, or was
externally clobbered between the run-edge write and this read, `current` collapses to the DEFAULT
`OverlayRunDoc(running=False, started_at=None)`. A `/score` POST during a live run would then
silently flip the overlay to `running=False, started_at=None` while a run is active — a wrong,
data-losing state, not a safe coast. The in-process `_state["gen"]` is already the source of
truth for `gen`; the running/started_at should likewise come from authoritative in-memory state
rather than a re-read that can degrade.
**Fix:** Cache the last-known running/started_at in `_state` alongside `gen` and re-persist from
memory, so `/score` never depends on a disk re-read that can default:
```python
_state = {"gen": _seed.gen, "running": _seed.running, "started_at": _seed.started_at}
...
def _bump_score_gen():
    with _gen_lock:
        _state["gen"] += 1
        write_overlay_run(_path(_OVERLAY_RUN_FILE),
            OverlayRunDoc(running=_state["running"], started_at=_state["started_at"], gen=_state["gen"]))
# and have _bump_overlay_run update _state["running"]/_state["started_at"] too.
```

### WR-04: `read_overlay_run`/`OverlayRunDoc` accept a numeric `running` from disk (`running: 1` → `True`) with no shape check, unlike the JSON-shape guard elsewhere

**File:** `src/segugio/opcomm/channel.py:268`, `src/segugio/opcomm/records.py:233`
**Issue:**
`running` is coerced via `bool(data.get("running", False))` then again via `bool(self.running)`.
Any truthy non-bool on disk (`"running": "false"` — a non-empty string — or `"running": 1`)
becomes `True`. `"false"` (string) → `True` is a classic footgun for a hand-edited/legacy file:
the operator intends "stopped" but the overlay reads "running". The test
`test_overlay_run_doc_normalizes` actually pins `running=1 -> True`, treating coercion as desired,
but does not cover the dangerous `"false"`→`True` string case. Given this is a run-state flag the
overlay UI keys off, a stricter "only real bool / 0|1 / true|false-string accepted, else default"
read is safer than blanket `bool()`.
**Fix:** Normalize known string/int forms explicitly and default the rest:
```python
def _as_bool(v, default=False):
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return bool(v)
    if isinstance(v, str): return v.strip().lower() in ("1","true","yes","on")
    return default
```
Apply in `read_overlay_run` for `running`.

## Info

### IN-01: `_PREVIEW_FILE` hardcodes a forward-slash path separator

**File:** `src/segugio/ui/app.py:78`
**Issue:** `_PREVIEW_FILE = "preview/preview.json"` is joined via `os.path.join(channel_dir, name)`.
It works on Windows (the OS accepts `/`), but it is inconsistent with the `os.path.join`-based
`get_preview_jpg` route just below it (which builds `os.path.join(_PREVIEW_SUBDIR, ...)`), and
mixing styles invites a future cross-platform surprise.
**Fix:** Build it from the subdir constant: `_PREVIEW_FILE = os.path.join(_PREVIEW_SUBDIR, "preview.json")`
(or compute it inside the route via `_path(os.path.join(_PREVIEW_SUBDIR, "preview.json"))`).

### IN-02: `post_run` comment `# action == "stop"` is an over-promise on the `else` branch

**File:** `src/segugio/ui/app.py:216`
**Issue:** The `else:  # action == "stop"` branch is reached for `action == "stop"` only because
`RunState(action=...)` already rejected everything except `"start"`/`"stop"` (raising → 400). The
comment reads as a hard guarantee but is really a consequence of the upstream validator; if the
`_RUN_ACTIONS` set ever grows (e.g. `"pause"`), this `else` silently treats the new verb as STOP.
**Fix:** Make the branch explicit and fail-closed for unexpected verbs:
```python
if action == "start":
    _bump_overlay_run(running=True, started_at=time.time())
elif action == "stop":
    _bump_overlay_run(running=False, started_at=None)
# (any future verb falls through with no overlay_run side-write rather than being mislabeled stop)
```

### IN-03: `_estimate_jpeg_bytes` is untouched by Phase 10 but its linear-quality over-estimate is undocumented at the call site

**File:** `src/segugio/config/models.py:211-232`, used at `:290`
**Issue:** Not a Phase-10 change, noted for completeness since `models.py` is in scope: the
`jpeg_quality / 55.0` linear term is a deliberate, documented over-estimate (WR-04 docstring). The
math checks out (default config lands ~3.98 Mbps inside the 8 Mbps cap) and the direction is safe
(over-reject, never under-budget). No action required; flagged only so a future reader does not
"fix" the intentional conservatism. The added `OverlayParams` sub-model itself is correct and
mirrors the established additive `extra="forbid"` + `default_factory` idiom.

---

_Reviewed: 2026-06-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
