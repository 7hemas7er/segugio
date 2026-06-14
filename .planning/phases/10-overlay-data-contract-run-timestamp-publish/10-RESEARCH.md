# Phase 10: Overlay Data Contract & Run-Timestamp Publish - Research

**Researched:** 2026-06-14
**Domain:** Boundary-safe JSON data contract + console-owned run-timestamp sidecar over the existing `opcomm` atomic-file channel (no HTML, no director touch)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** ONE console-owned file `overlay_run.json` carries `{running, started_at, gen}`. Mirrors the single-sidecar `PreviewDoc` shape; one atomic write per `/run` and `/score`. Do NOT split `gen` into a separate counter file, and do NOT derive `gen` from file mtimes.
- **D-02:** `gen` is seeded from disk on `create_app` startup — read `overlay_run.json` back and continue the in-memory counter from the persisted value (never reset to 0). `gen` is a NEW console-owned counter, distinct from the orchestrator-side `PreviewDoc.gen`.
- **D-03:** `/run` keeps writing `runstate.json` **exactly as today** (byte-for-byte unchanged — director reads it every tick). The new `overlay_run.json` write is *additional*, alongside it, in the same `/run` handler. On START: `running=true`, `started_at=<console time.time()>`. On STOP: `running=false`, `started_at=null`.
- **D-04:** Blank-safe and **stateless**. A missing/torn/malformed source at poll time → empty `fields` / `running:false` / default `discipline`, exactly like the existing `read_score`/`read_runstate` pattern (pure functions over `_read_json`). NO in-memory "last-good" cache on the route. `server_now` + `gen` are ALWAYS set regardless.
- **D-05:** Add a NEW `overlay.*` config section (pydantic, in `config/models.py`). It will also be the future home of the BRD-01 logo path + CSS-var theme + identity line in Phase 11.
- **D-06:** Key = `overlay.freestyle_duration_s`, **default 120**. Defined now; **consumed in Phase 11**.
- **D-07:** The freestyle duration does NOT go into the `/overlay-json` poll payload. The contract stays exactly the locked 6 fields. The duration is *static config* injected into the `/overlay` page at render time in Phase 11 (entrypoint-resolved arg, same pattern as `cam_ids`).
- **D-08:** `/overlay-json` passes `score.fields` as the **raw verbatim dict** (operator-typed keys + values) alongside `discipline`. The server does NOT pre-resolve aliases or emit a discipline-normalized structure. The Phase-11 JS renderer owns per-discipline layout AND alias resolution.

### Claude's Discretion
- Exact module placement of the new route(s) and the overlay-run read/write helpers (new `read_overlay_run`/`write_overlay_run` in `opcomm/channel.py` + a frozen `OverlayRunDoc` record in `opcomm/records.py`, mirroring the `PreviewDoc`/`read_preview` precedent — planner finalizes naming).
- Whether `gen` lives as a field on `OverlayRunDoc` or as a route-local counter persisted via that record (D-01/D-02 require it persisted in `overlay_run.json`; the in-memory holding mechanism is the planner's call).
- The precise safe-default `discipline` value when `score.json` is absent — lean to the existing `ScoreDoc()` default (`disc_tf`) per D-04's "match existing pattern".

### Deferred Ideas (OUT OF SCOPE)
- Freestyle-duration consumption (timer counts down from it) — Phase 11. Phase 10 only defines the config key + default.
- BRD logo path / CSS-var theme / identity line — Phase 11 (will share the `overlay.*` section created here).
- `source_ok` / explicit degrade flag in the payload — considered and NOT taken; the contract stays the locked 6 fields.
- Discipline field-schema hint in the contract — considered and NOT taken (D-08 keeps raw verbatim).
- Any HTML/CSS/JS overlay page, the self-counting timer, animations, branding render → Phase 11.
- **Any compute on the director / any change to `runstate.json`** (HARD invariant — never).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OVD-01 | `GET /overlay-json` assembles `{discipline, fields verbatim, running, started_at, server_now, gen}` boundary-safe (absent/malformed source → default, never raises) | Route assembles from `read_score` + `read_overlay_run` + `time.time()`; both readers reuse `_read_json` never-raise boundary (channel.py L42-63). Route adds `Cache-Control: no-store` like `get_preview_jpg` (app.py L196). |
| OVD-02 | A NEW console-owned overlay-run record (`overlay_run.json`) stamps `run_started_at` + `running` on the run start/stop edge; `runstate.json` (director-read) is never touched | New `OverlayRunDoc` mirrors `PreviewDoc` (records.py L162-203); `write_overlay_run`/`read_overlay_run` mirror `write_preview`/`read_preview` (channel.py L182-224). Side-write in `post_run` AFTER the existing `write_runstate` call (app.py L156). |
| OVD-03 | Freshness — a stale/disconnected source is detectable (gen-age) and the overlay degrades, reusing the v1.1 `gen`/nonce/`no-store` pattern | Phase 10's responsibility is ONLY to publish a monotonic `gen` + `server_now` so Phase 11's client-side `isStale()` watchdog (test_ui_freshness.py L207-228) has its inputs. No client code here. `gen` bumps on every `/run` and `/score` (D-02). |
| RBT-07 | Crash-isolation preserved — import test green with heavy stack absent; the overlay route imports only Flask + `segugio.opcomm` | Extend `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` (L87-107) to exercise the new route via the test client. No new top-level imports in `ui/app.py` (Flask stays inside `create_app`; `time` is stdlib). |
</phase_requirements>

## Summary

Phase 10 is a **pure additive extension** of the proven v1.1 publish-and-render pattern. It introduces (1) a new console-owned `OverlayRunDoc` frozen record + `write_overlay_run`/`read_overlay_run` helpers that mirror the `PreviewDoc`/`read_preview`/`write_preview` triad exactly; (2) a side-write of `overlay_run.json` inside the existing `POST /run` handler — placed AFTER the untouched `write_runstate` call so the director-read `runstate.json` byte stream is provably unchanged; (3) a new `GET /overlay-json` route that assembles `{discipline, fields, running, started_at, server_now, gen}` from two never-raise reads plus `time.time()`, with `Cache-Control: no-store`; (4) a new `overlay.*` pydantic config section defining only `freestyle_duration_s: int = 120`; and (5) an extension of the crash-isolation import test to cover the new route.

There are **zero new Python dependencies** and **zero director touches**. Every primitive needed already exists in the codebase: the never-raise `_read_json` boundary, the always-fsync `atomic_write_json` with Windows MoveFileEx retry, the frozen-record `__post_init__` normalization convention, the `cam_ids`-style entrypoint-arg injection pattern, and the `no-store`/`gen` cache-bust hygiene. The single genuinely new behavior is the **console-owned `gen` counter** that seeds from disk on startup (D-02) and bumps on every `/run` and `/score` write — this is what lets a mid-run console restart re-anchor the Phase-14 timer without a phantom jump.

The clock-skew contract setup is minimal at this phase: both `started_at` (written on `/run` START) and `server_now` (computed at `/overlay-json` response) are read from the **same console clock** (`time.time()`). Phase 10 only places both timestamps in the contract from the first commit; the offset-cancellation math is entirely Phase 11 (client-side). No HTML, CSS, or JS is written in this phase.

**Primary recommendation:** Replicate the `PreviewDoc` triad verbatim for `OverlayRunDoc`, hold the console `gen` as a closure variable inside `create_app` (seeded from `read_overlay_run` at build time), bump-and-persist it on every `/run` and `/score`, and assemble `/overlay-json` from two safe-default reads + `time.time()`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Run-start timestamp persistence | Frontend Server (Flask console) | Database / Storage (`overlay_run.json` on disk) | Console owns the run edge (`POST /run`); the file is the only durable carrier. Director never reads it (HARD invariant). |
| `gen` monotonic counter | Frontend Server (console in-memory + sidecar) | Database / Storage (persisted in `overlay_run.json`) | Counter lives in `create_app` closure, persisted to disk so a restart re-seeds (D-02). Distinct from the orchestrator-side `PreviewDoc.gen`. |
| `server_now` clock anchor | Frontend Server (console `time.time()`) | — | Single clock domain; computed at response time. Phase 11 client cancels skew against it. |
| `/overlay-json` payload assembly | Frontend Server (Flask route) | Database / Storage (reads `score.json` + `overlay_run.json`) | Pure read + repack; no compute, no adjudication (SCR-04 / D-08). |
| `overlay.*` config schema | API / Backend (pydantic `config/models.py`) | — | Validated at load; injected into the console via entrypoint arg (NOT imported at module top — crash-isolation). |
| Overlay rendering (HTML/CSS/JS) | Browser / Client (Phase 11) | — | OUT OF SCOPE this phase. Director compute forbidden. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.x (already pinned) | The two new GET route + the modified `/run` POST | Already the console's only web dep; imported INSIDE `create_app` to keep `import segugio.ui` Flask-free [VERIFIED: src/segugio/ui/app.py L80]. No version change. |
| `segugio.opcomm` | in-repo | `OverlayRunDoc` record + `write_overlay_run`/`read_overlay_run` + `atomic_write_json` + `_read_json` | The crash-isolation allowlist permits ONLY Flask + `segugio.opcomm` [VERIFIED: src/segugio/ui/__init__.py L4-8]. |
| `time` (stdlib) | — | `time.time()` for `started_at` (on `/run` START) and `server_now` (at `/overlay-json` response) | Same clock domain for both timestamps (the skew-cancellation precondition). stdlib — no import-boundary risk. |
| `pydantic` v2 | already pinned | The new `overlay.*` config sub-model | The established config convention (`ConfigDict(extra="forbid")`, `Field(...)` bounds) [VERIFIED: src/segugio/config/models.py L9-15]. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `loguru` | already pinned | Logging a malformed `overlay_run.json` at the read boundary | Inside `read_overlay_run`, mirroring `read_preview`'s `logger.warning` on invalid data [VERIFIED: src/segugio/opcomm/channel.py L223]. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Side-file `overlay_run.json` | Extend `runstate.json` with `started_at`/`running` | REJECTED by D-03 + HARD invariant: director reads `runstate.json` every tick; any byte change risks the director. Side-file keeps "director never touched" literally true. |
| `gen` persisted inside `overlay_run.json` | Separate `gen.txt` counter file or mtime-derived gen | REJECTED by D-01: single file, not a separate counter, not mtime-derived. |
| Verbatim `fields` dict in payload | Server-side per-discipline alias resolution / normalized structure | REJECTED by D-08: the Phase-11 JS renderer owns layout + alias resolution; the console stays a dumb data pipe (smallest RBT-07 surface). |

**Installation:**
```bash
# Zero new packages. All primitives already in the locked stack.
```

**Version verification:** No new packages to verify — this phase adds only in-repo modules and stdlib `time`. The crash-isolation guarantee is that NO new external import enters `segugio.ui` or `segugio.opcomm`.

## Package Legitimacy Audit

> Not applicable — this phase installs **no external packages**. All code is in-repo (`segugio.opcomm`, `segugio.ui`, `segugio.config`) plus stdlib (`time`, `json`, `os`) and the already-pinned Flask/pydantic/loguru.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         CONSOLE PROCESS (Flask, crash-isolated: Flask + segugio.opcomm only)
                         ┌───────────────────────────────────────────────────────────────┐
 Operator tablet         │                                                                 │
   │                     │   create_app(channel_dir, cam_ids=()):                          │
   │  POST /run          │     gen = read_overlay_run(overlay_run.json).gen   ◄── seed (D-02)
   ├────────────────────►│        (on startup, from disk)                                  │
   │  action=start|stop  │                                                                 │
   │                     │   ┌── POST /run handler ──────────────────────────────────┐    │
   │                     │   │  1. write_runstate(runstate.json, run)  ◄── UNCHANGED  │    │
   │                     │   │     (byte-for-byte; director reads this every tick)    │    │
   │                     │   │  2. gen += 1                                           │    │
   │                     │   │  3. write_overlay_run(overlay_run.json,               │    │
   │                     │   │       OverlayRunDoc(running=(action==start),          │────┼──► overlay_run.json
   │                     │   │         started_at=time.time() if start else None,    │    │   {running, started_at, gen}
   │  POST /score        │   │         gen=gen))                                     │    │
   ├────────────────────►│   └────────────────────────────────────────────────────┘    │
   │  discipline+fields  │   ┌── POST /score handler (MODIFIED) ─────────────────────┐    │
   │                     │   │  write_score(score.json, doc)  ◄── UNCHANGED          │────┼──► score.json
   │                     │   │  atomic_write_text(overlay.txt, render) ◄── UNCHANGED │────┼──► overlay.txt (fallback)
   │                     │   │  gen += 1; write_overlay_run(... gen ...)  ◄── NEW    │    │
   │                     │   └────────────────────────────────────────────────────┘    │
   │                     │                                                                 │
   │  GET /overlay-json  │   ┌── GET /overlay-json handler (NEW) ────────────────────┐    │
   ├────────────────────►│   │  s   = read_score(score.json)        ◄── never raises │◄───┼─── score.json
   │                     │   │  ovr = read_overlay_run(overlay_run.json) ◄── never   │◄───┼─── overlay_run.json
   │◄────────────────────┤   │  return jsonify({                                     │    │
   │  {discipline,fields,│   │    discipline: s.discipline.value,                    │    │
   │   running,started_at│   │    fields:     s.fields,            ◄── verbatim (D-08)│    │
   │   server_now,gen}   │   │    running:    ovr.running,                            │    │
   │  Cache-Control:     │   │    started_at: ovr.started_at,                        │    │
   │    no-store         │   │    server_now: time.time(),        ◄── console clock  │    │
   │                     │   │    gen:        ovr.gen,                                │    │
   │                     │   │  }), headers Cache-Control: no-store                   │    │
   │                     │   └────────────────────────────────────────────────────┘    │
                         └───────────────────────────────────────────────────────────────┘
        DIRECTOR PROCESS (orchestrator) ── reads runstate.json/score.json/command.json each tick ──
        NEVER reads overlay_run.json.  NEVER touched by this phase.
```

### Component Responsibilities
| File | Change | Responsibility |
|------|--------|----------------|
| `src/segugio/opcomm/records.py` | ADD `OverlayRunDoc` frozen record | `{running: bool, started_at: float\|None, gen: int}` with normalizing `__post_init__`; mirrors `PreviewDoc`. Add to `__all__`. |
| `src/segugio/opcomm/channel.py` | ADD `write_overlay_run` / `read_overlay_run` | Atomic write via `atomic_write_json`; safe-default never-raise read via `_read_json`. Add both to `__all__`. Import `OverlayRunDoc`. |
| `src/segugio/ui/app.py` | MODIFY `create_app`, `post_run`, `post_score`; ADD `get_overlay_json` | Seed `gen` from disk; bump+persist on `/run`+`/score`; assemble `/overlay-json`. Add `_OVERLAY_RUN_FILE = "overlay_run.json"` constant. Import `OverlayRunDoc`, `read_overlay_run`, `write_overlay_run`, and stdlib `time`. |
| `src/segugio/config/models.py` | ADD `OverlayParams` sub-model + `overlay` field on `Config` | `freestyle_duration_s: int = 120`; `Field(default_factory=OverlayParams)` so an existing `extra="forbid"` config without an `overlay:` block still validates. |
| `tests/test_imports.py` | EXTEND `test_console_resolves_with_heavy_stack_and_numpy_absent` | Exercise the new route via the test client under the heavy-absent block. |

### Pattern 1: Frozen sidecar record mirroring PreviewDoc
**What:** A new `@dataclass(frozen=True)` with a normalizing `__post_init__`, paired with `write_*`/`read_*` helpers over the atomic-write + `_read_json` boundaries.
**When to use:** For `OverlayRunDoc` — this is the exact template D-01/D-04 mandate.
**Example:**
```python
# Source: pattern derived from src/segugio/opcomm/records.py L162-203 (PreviewDoc)
#         and src/segugio/opcomm/channel.py L182-224 (write_preview/read_preview)
@dataclass(frozen=True)
class OverlayRunDoc:
    """Console-owned run-edge snapshot the overlay polls (SIDECAR — director never reads it)."""
    running: bool = False
    started_at: float | None = None
    gen: int = 0

    def __post_init__(self) -> None:
        # Normalize types at the boundary (a torn/hand-written file value is coerced loudly).
        object.__setattr__(self, "running", bool(self.running))
        if self.started_at is not None:
            object.__setattr__(self, "started_at", float(self.started_at))
        object.__setattr__(self, "gen", int(self.gen))
```
```python
# write_overlay_run / read_overlay_run mirror write_preview / read_preview exactly.
def write_overlay_run(path: str, doc: OverlayRunDoc) -> None:
    atomic_write_json(path, {"running": doc.running,
                             "started_at": doc.started_at, "gen": doc.gen})

def read_overlay_run(path: str) -> OverlayRunDoc:
    data = _read_json(path)
    if not isinstance(data, dict):
        return OverlayRunDoc()
    try:
        started = data.get("started_at")
        return OverlayRunDoc(
            running=bool(data.get("running", False)),
            started_at=None if started is None else float(started),
            gen=int(data.get("gen", 0)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("opcomm invalid OverlayRunDoc at {} → default ({})", path, exc)
        return OverlayRunDoc()
```

### Pattern 2: Console-owned `gen` counter — seed from disk, bump-and-persist
**What:** A monotonic int held in the `create_app` closure, seeded from disk at build time, incremented before each persist, written into `overlay_run.json`.
**When to use:** On every `/run` and `/score` write (D-02).
**Example:**
```python
# Source: pattern derived from src/segugio/orchestrator/preview.py L84,L248-254 (gen bump)
#         and src/segugio/ui/app.py L82,L84 (create_app closure-state precedent)
def create_app(channel_dir: str, cam_ids=()):
    from flask import Flask, jsonify, request   # ... (existing imports)
    import time                                  # stdlib — safe at module top OR here
    os.makedirs(channel_dir, exist_ok=True)

    # D-02: seed gen from the persisted overlay_run.json so a mid-run restart continues the
    # counter (never resets to 0 → Phase-14 timer re-anchors with no phantom jump).
    _state = {"gen": read_overlay_run(_path(_OVERLAY_RUN_FILE)).gen}

    def _bump_overlay_run(running: bool, started_at):
        _state["gen"] += 1
        write_overlay_run(_path(_OVERLAY_RUN_FILE),
                          OverlayRunDoc(running=running, started_at=started_at,
                                        gen=_state["gen"]))
```
> **Discretion note (D-02):** the planner may hold `gen` as a closure dict (shown) or as a tiny route-local object. The single requirement: it is read back from `overlay_run.json` at startup and persisted there on each bump — NOT a separate file, NOT mtime-derived.

> **Thread-safety note:** Flask runs `threaded=True` (dev fallback) or Waitress (multi-thread) [VERIFIED: src/segugio/ui/app.py L243-249]. The `gen` read-modify-write is non-atomic. The `PreviewPublisher` precedent guards its gen bump with a `Lock` "to make monotonicity robust to any future second writer" [CITED: src/segugio/orchestrator/preview.py L248-254]. The planner SHOULD wrap the bump in a `threading.Lock` for the same reason — concurrent `/run`+`/score` POSTs are possible under multi-thread serving. Monotonicity (not exact contiguity) is what the Phase-11 watchdog needs.

### Pattern 3: Side-write AFTER the unchanged director write (the byte-for-byte invariant)
**What:** In `post_run`, the existing `write_runstate(...)` line is left EXACTLY as-is; the `overlay_run.json` write is appended after it.
**When to use:** Always — this is how the HARD "director never touched" invariant stays literally true (D-03).
**Example:**
```python
# Source: src/segugio/ui/app.py L143-157 (existing post_run) — only the marked line is ADDED
@app.post("/run")
def post_run():
    action = request.form.get("action", "")
    try:
        run = RunState(action=action, just_started=(action == "start"),
                       just_stopped=(action == "stop"))
    except ValueError:
        return ("azione non valida", 400)
    write_runstate(_path(_RUNSTATE_FILE), run)            # UNCHANGED — director reads this
    # NEW (D-03): additional side-write, AFTER write_runstate.
    if action == "start":
        _bump_overlay_run(running=True, started_at=time.time())
    else:  # "stop"
        _bump_overlay_run(running=False, started_at=None)
    return ("", 204)
```

### Anti-Patterns to Avoid
- **Extending `runstate.json`:** adding `started_at`/`running`/`gen` to the director-read file. Violates D-03 + HARD invariant. The director reads `runstate.json` every tick.
- **In-memory last-good cache on `/overlay-json`:** D-04 mandates stateless safe-default. A torn read → blank fields, never a stale value served as live.
- **Server-side alias/discipline resolution in `/overlay-json`:** D-08 keeps `fields` verbatim. The renderer (Phase 11) owns layout.
- **Adding a `source_ok`/degrade flag to the payload:** explicitly NOT taken (Deferred Ideas). Contract stays the locked 6 fields.
- **Importing config at module top in `ui/app.py`:** breaks crash-isolation. The freestyle duration (when consumed in Phase 11) flows in as an entrypoint arg like `cam_ids`, never via `import segugio.config`.
- **A separate `gen` file or mtime-derived gen:** violates D-01.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic, never-partial file write | A naive `open(...).write()` | `atomic_write_json` [VERIFIED: src/segugio/opcomm/atomic.py L66-79] | Always-fsync + same-dir temp + Windows MoveFileEx sharing-violation retry already solved. A torn `overlay_run.json` would mislead the overlay. |
| Never-raise file read | Bare `json.load` with try/except scattered | `_read_json` [VERIFIED: src/segugio/opcomm/channel.py L42-63] | The single boundary that absorbs absent/empty/torn/malformed → `None`. D-04's blank-safe semantics fall out for free. |
| Safe-default typed read | Manual dict-poking in the route | `read_overlay_run` mirroring `read_preview` [VERIFIED: src/segugio/opcomm/channel.py L202-224] | The route stays a pure assembler; the boundary owns validation + logging. |
| Cache-bust on a live data fetch | Custom ETag logic | `Cache-Control: no-store` header (+ Phase-11 `?t=<gen>`) [VERIFIED: src/segugio/ui/app.py L196] | Exact precedent on the preview-JPEG route. |
| Run-edge mapping | New verb parsing | The existing `RunState(action, just_started, just_stopped)` construction [VERIFIED: src/segugio/ui/app.py L148-155] | `post_run` already validates the verb; reuse `action` for the overlay-run write. |

**Key insight:** Every primitive this phase needs is already proven in v1.0/v1.1. The work is composition, not invention — the `PreviewDoc` triad is a line-by-line template.

## Runtime State Inventory

> This phase is NOT a rename/refactor/migration. It is purely additive (new file, new record, new route, new config key). No existing stored data, live service config, OS-registered state, secrets/env vars, or build artifacts carry a value that changes.
>
> **Stored data:** None — `overlay_run.json` is a NEW file; no existing datastore is renamed or re-keyed. Verified: the only files written by the console are `score.json`/`overlay.txt`/`runstate.json`/`command.json`/`status.json` [VERIFIED: src/segugio/ui/app.py L51-62].
> **Live service config:** None — no OBS/external service config changes this phase (scene-collection wiring is Phase 13).
> **OS-registered state:** None.
> **Secrets/env vars:** None new. `SEGUGIO_OPCOMM_DIR` / `SEGUGIO_CAM_IDS` / `SEGUGIO_CONFIG` unchanged [VERIFIED: src/segugio/ui/app.py L222-235].
> **Build artifacts:** None — no package rename; no egg-info impact.

## Common Pitfalls

### Pitfall 1: Accidentally touching `runstate.json` semantics
**What goes wrong:** A refactor of `post_run` reorders or rewrites the `write_runstate` call, changing the on-disk bytes the director reads every tick.
**Why it happens:** Treating the run handler as "the run state writer" and consolidating writes.
**How to avoid:** Leave the `write_runstate(_path(_RUNSTATE_FILE), run)` line EXACTLY as-is; append the overlay-run write strictly after it. Add a test asserting `runstate.json` content is byte-identical to the v1.1 baseline for the same POST.
**Warning signs:** `runstate.json` JSON key order or value shape differs from `write_runstate`'s `{action, just_started, just_stopped}` [VERIFIED: src/segugio/opcomm/channel.py L94-103].

### Pitfall 2: `gen` resetting to 0 on console restart
**What goes wrong:** `create_app` seeds `gen = 0` instead of reading it back from disk; a mid-run restart restarts the counter, and the Phase-14 timer sees a phantom jump.
**Why it happens:** Forgetting D-02's seed-from-disk requirement; treating gen as ephemeral.
**How to avoid:** `_state["gen"] = read_overlay_run(...).gen` at build time. Test: write `overlay_run.json` with `gen=7`, build a fresh app, POST `/run`, assert the new gen is `>= 8`.
**Warning signs:** A restart test shows gen dropping below the persisted value.

### Pitfall 3: Two timestamps from two clock domains
**What goes wrong:** `started_at` written from one source and `server_now` from another (e.g. monotonic vs wall) breaks the Phase-11 offset-cancellation precondition.
**Why it happens:** Reaching for `time.monotonic()` for one and `time.time()` for the other.
**How to avoid:** BOTH `started_at` (on `/run` START) and `server_now` (at `/overlay-json` response) use `time.time()` — the wall clock — so they are the same domain. Phase 11 cancels skew with `skew = server_now - Date.now()/1000`. Do NOT use `time.monotonic()` (it is not comparable to the client's `Date.now()`).
**Warning signs:** `started_at` values that are tiny (seconds since boot) rather than a Unix epoch.

### Pitfall 4: A new heavy import sneaking into the route
**What goes wrong:** Importing something at `ui/app.py` module top (or pulling `segugio.config` for the freestyle duration) breaks crash-isolation; the import test goes red.
**Why it happens:** Convenience — wanting the config value in the route.
**How to avoid:** Only Flask (inside `create_app`) + `segugio.opcomm` + stdlib (`os`, `time`). The freestyle duration is NOT in the `/overlay-json` payload (D-07) and is NOT needed this phase — it is a config KEY only, consumed in Phase 11 via an entrypoint arg (like `cam_ids`). Extend the import test as the gate.
**Warning signs:** `import segugio.config` or any heavy name at module top in `ui/app.py`.

### Pitfall 5: `/overlay-json` raising on a torn source
**What goes wrong:** The route reads `score.json`/`overlay_run.json` directly with `json.load` and a corrupt file 500s the overlay mid-run.
**Why it happens:** Bypassing the `read_*` safe-default helpers.
**How to avoid:** Assemble ONLY from `read_score(...)` and `read_overlay_run(...)` (both never raise). `server_now` and `gen` are always set regardless (D-04). Test: corrupt both files, assert 200 + safe-default payload.
**Warning signs:** Any direct `json.load`/`open` inside the route.

## Code Examples

### `GET /overlay-json` route (the full assembler)
```python
# Source: pattern derived from src/segugio/ui/app.py L173-215 (get_status / get_preview)
#         + L194-197 (Cache-Control: no-store precedent)
@app.get("/overlay-json")
def get_overlay_json():
    # D-04 / OVD-01: pure safe-default reads — neither raises on absent/torn/malformed.
    s = read_score(_path(_SCORE_FILE))            # discipline + verbatim fields (D-08)
    ovr = read_overlay_run(_path(_OVERLAY_RUN_FILE))
    payload = {
        "discipline": s.discipline.value,          # ScoreDoc() default disc_tf when absent
        "fields": s.fields,                         # raw verbatim dict (D-08)
        "running": ovr.running,
        "started_at": ovr.started_at,              # None when stopped/absent
        "server_now": time.time(),                 # console wall clock (skew anchor) — ALWAYS set
        "gen": ovr.gen,                            # monotonic, ALWAYS set
    }
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "no-store"     # never cache live state (OVD-03)
    return resp
```

### Modified `POST /score` (the gen bump)
```python
# Source: src/segugio/ui/app.py L99-117 (existing post_score) — only the marked lines are ADDED
@app.post("/score")
def post_score():
    form = request.form
    raw_discipline = form.get("discipline", Discipline.disc_tf.value)
    try:
        discipline = Discipline(raw_discipline)
    except ValueError:
        return ("disciplina sconosciuta", 400)
    fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS and v.strip()}
    doc = ScoreDoc(discipline=discipline, fields=fields)
    write_score(_path(_SCORE_FILE), doc)                            # UNCHANGED
    atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # UNCHANGED
    # NEW (D-02): bump gen on every /score write, preserving running/started_at unchanged.
    _bump_score_gen()   # reads current overlay_run, re-writes with running/started_at kept, gen+1
    return ("", 204)
```
> **Discretion note (the `/score` bump shape):** the bump on `/score` must NOT flip `running` or clear `started_at` — only `gen` advances. The cleanest implementation reads the current `OverlayRunDoc`, then re-persists it with `running`/`started_at` preserved and `gen` incremented. The planner finalizes whether this is a distinct `_bump_score_gen()` helper or a parametrized `_bump_overlay_run(...)`.

### The new `overlay.*` config sub-model
```python
# Source: pattern derived from src/segugio/config/models.py L146-171 (PreviewParams) + L227 (Config field)
class OverlayParams(BaseModel):
    """Overlay config (D-05/D-06). Defined now; freestyle_duration_s consumed in Phase 11.

    Additive sub-model — an existing extra='forbid' config WITHOUT an `overlay:` block still
    validates (default_factory fills it), exactly like preview/scoring/tracking/action_hold.
    Future home of the BRD-01 logo path + CSS-var theme + identity line (Phase 11).
    """
    model_config = ConfigDict(extra="forbid")
    freestyle_duration_s: Annotated[int, Field(gt=0)] = 120  # D-06: 2-min routines; orgs override

# On Config:
#   overlay: OverlayParams = Field(default_factory=OverlayParams)
```
> **Note:** because the loader is fail-fast `SystemExit(2)` on any `ValidationError` [VERIFIED: src/segugio/config/loader.py L42-44], the `extra="forbid"` + `default_factory` pattern is mandatory so existing configs without an `overlay:` block keep loading. `config.example.yaml` SHOULD gain a commented `overlay:` block documenting `freestyle_duration_s` (note: `config.example.yaml` shows as modified in git status — the planner should reconcile).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Run state lives only in `runstate.json` (director-consumed) | Console-owned `overlay_run.json` sidecar carries the run-start instant + gen | This phase (v1.2) | The one genuine data-model addition of the milestone; keeps director untouched. |
| `gen` is orchestrator-owned (in `PreviewDoc`) | A SECOND, console-owned `gen` for the overlay channel | This phase | Distinct counter; seeded from disk for restart re-anchoring (D-02). |
| Overlay = `overlay.txt` rendered server-side | `overlay.txt` retained as fallback; new JSON contract for the (Phase-11) browser-source overlay | v1.2 milestone | `render_overlay_text` survives unchanged; `/overlay-json` is additive. |

**Deprecated/outdated:** Nothing is removed or deprecated in this phase. `overlay.txt` + `render_overlay_text` are retained (RBT-06; out of scope to change).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The planner SHOULD guard the `gen` bump with a `threading.Lock` because the console serves multi-threaded (Waitress / `threaded=True`). | Pattern 2 thread-safety note | LOW — without the lock, a rare concurrent `/run`+`/score` could skip a gen value; monotonicity (what the watchdog needs) still holds. The lock makes it robust, matching the PreviewPublisher precedent. |
| A2 | The safe-default `discipline` when `score.json` is absent is `ScoreDoc()`'s default (`disc_tf`). | /overlay-json route | LOW — D-04 + the discretion note both lean to "match existing pattern" (`read_score` returns `ScoreDoc()` on absent). Confirmed against `read_score` [VERIFIED: channel.py L76-88]. |
| A3 | `config.example.yaml` should gain a documented (commented) `overlay:` block. | OverlayParams note | LOW — cosmetic/docs; the `default_factory` means configs without it still load. The file is already modified in git status; planner reconciles. |

**Note:** All structural claims (record shapes, signatures, route patterns, the byte-for-byte `runstate.json` write, the crash-isolation test) are `[VERIFIED]` against the read source files — no assumptions there.

## Open Questions

1. **Does the `/score` gen bump need to preserve the exact prior `started_at`/`running`, or re-derive from `runstate.json`?**
   - What we know: D-02 says bump on every `/score`; D-03 says `/run` owns the running/started_at edges.
   - What's unclear: whether a `/score` arriving while stopped should keep `running=false`/`started_at=null` (it must — `/score` is not a run edge).
   - Recommendation: the `/score` bump reads the current `OverlayRunDoc` and re-persists with `running`/`started_at` UNCHANGED, only `gen+1`. This is the safest reading of D-02/D-03 and is reflected in the discretion note above.

2. **Lock granularity for the `gen` counter** (closure dict + `threading.Lock` vs a small object).
   - What we know: multi-thread serving makes the RMW non-atomic; the PreviewPublisher uses a Lock.
   - Recommendation: a single `threading.Lock` around read-current → bump → persist. Planner's call on exact shape (A1).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Flask | the two routes + `/run` modification | ✓ (pinned) | 3.1.x | — |
| pydantic v2 | `overlay.*` config sub-model | ✓ (pinned) | v2 | — |
| Python stdlib `time`/`json`/`os` | timestamps + atomic IO | ✓ | — | — |

**Missing dependencies with no fallback:** none — this phase is in-repo + stdlib only.
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `tests/conftest.py` (shared fixtures: `file_channel`, `tmp_config`, `make_config`) [VERIFIED] |
| Quick run command | `python -m pytest tests/test_ui_overlay_json.py -x -q` (new file) |
| Full suite command | `python -m pytest -q` |

> Run perf-sensitive checks on AC power per project memory; these tests are pure CPU/IO and not latency-gated.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OVD-02 | `/run` START stamps `running:true` + `started_at` (epoch) into `overlay_run.json` | route (Flask test client) | `pytest tests/test_ui_overlay_json.py::test_run_start_stamps_overlay_run -x` | ❌ Wave 0 |
| OVD-02 | `/run` STOP nulls it (`running:false`, `started_at:null`) | route | `pytest tests/test_ui_overlay_json.py::test_run_stop_nulls_overlay_run -x` | ❌ Wave 0 |
| OVD-02 | `runstate.json` is byte-for-byte identical to the v1.1 write for the same POST (director invariant) | route + byte compare | `pytest tests/test_ui_overlay_json.py::test_runstate_byte_for_byte_unchanged -x` | ❌ Wave 0 |
| OVD-01 | `/overlay-json` returns the 6-key payload with `Cache-Control: no-store` | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_payload_shape -x` | ❌ Wave 0 |
| OVD-01 | `/overlay-json` never raises on absent source → safe-default payload | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_safe_default_when_absent -x` | ❌ Wave 0 |
| OVD-01/D-04 | `/overlay-json` never raises on torn/malformed source → safe-default; `server_now`+`gen` still set | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_safe_default_on_corrupt -x` | ❌ Wave 0 |
| OVD-01/D-08 | `fields` returned verbatim (operator-typed keys + values, no alias resolution) | route | `pytest tests/test_ui_overlay_json.py::test_overlay_json_fields_verbatim -x` | ❌ Wave 0 |
| OVD-03/D-02 | `server_now` present + monotonic `gen` present on every response | route | `pytest tests/test_ui_overlay_json.py::test_server_now_and_gen_present -x` | ❌ Wave 0 |
| OVD-03/D-02 | `gen` bumps on `/run` AND on `/score` | route | `pytest tests/test_ui_overlay_json.py::test_gen_bumps_on_run_and_score -x` | ❌ Wave 0 |
| OVD-03/D-02 | `gen` seeds from disk across restart (write gen=N, fresh `create_app`, next gen > N) | route + fresh app | `pytest tests/test_ui_overlay_json.py::test_gen_seeds_from_disk_on_restart -x` | ❌ Wave 0 |
| D-02 | `started_at` persists across console restart while running (restart keeps running:true + same started_at) | route + fresh app | `pytest tests/test_ui_overlay_json.py::test_started_at_persists_across_restart -x` | ❌ Wave 0 |
| OVD-01/D-04 | `read_overlay_run`/`write_overlay_run` round-trip + safe-default (pure unit) | unit | `pytest tests/test_opcomm_overlay_run.py -x` | ❌ Wave 0 |
| OVD-02 | `OverlayRunDoc` frozen-record normalization + equality (pure unit) | unit | `pytest tests/test_opcomm_overlay_run.py::test_overlay_run_doc_normalizes -x` | ❌ Wave 0 |
| D-05/D-06 | `overlay.freestyle_duration_s` defaults to 120; config without `overlay:` block still validates; `<=0` rejected | unit (pydantic) | `pytest tests/test_config_overlay.py -x` | ❌ Wave 0 |
| RBT-07 | crash-isolation import test green with heavy stack absent AND `/overlay-json` served | import-isolation | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ✅ extend existing (L87-107) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_ui_overlay_json.py tests/test_opcomm_overlay_run.py tests/test_config_overlay.py -x -q`
- **Per wave merge:** `python -m pytest tests/test_ui_overlay_json.py tests/test_opcomm_overlay_run.py tests/test_config_overlay.py tests/test_imports.py tests/test_ui_run.py tests/test_ui_score.py -q`
- **Phase gate:** Full suite `python -m pytest -q` green before `/gsd-verify-work` (proves no regression to `runstate.json`/`/score`/`/run` and the import boundary).

### Wave 0 Gaps
- [ ] `tests/test_opcomm_overlay_run.py` — unit tests for `OverlayRunDoc` + `read_overlay_run`/`write_overlay_run` (round-trip, safe-default on absent/torn, normalization). Covers OVD-01/OVD-02/D-04.
- [ ] `tests/test_ui_overlay_json.py` — Flask-test-client route tests (uses the existing `file_channel` fixture). Covers OVD-01/OVD-02/OVD-03/D-02/D-03/D-04/D-08.
- [ ] `tests/test_config_overlay.py` — pydantic tests for the `overlay.*` section (default 120, optional block, bound rejection). Covers D-05/D-06. (May extend an existing config test file instead of a new one — planner's call.)
- [ ] Extend `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` to GET `/overlay-json` via the test client under the heavy-absent block. Covers RBT-07.
- [ ] No framework install needed — pytest + the `file_channel` fixture already exist.

> **The byte-for-byte `runstate.json` invariant** deserves a dedicated assertion: capture the `runstate.json` bytes a v1.1-equivalent `write_runstate` produces for `action=start`, then assert the Phase-10 `post_run` produces the identical bytes — this is the literal proof of the HARD "director never touched" invariant.

## Security Domain

> `security_enforcement` is not explicitly disabled in config; the project carries a documented LAN-trust-boundary threat model (`docs/security.md`). This phase adds one read-only GET route and one console-owned write — small surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Accepted no-auth on the LAN trust boundary (documented, `docs/security.md` T-05-05-04) — unchanged. |
| V3 Session Management | no | Stateless routes; no sessions. |
| V4 Access Control | no | LAN-as-trust-boundary; AP client-isolation is the control (unchanged). |
| V5 Input Validation | yes (minimal) | `/overlay-json` is read-only (no input). `/run` action already whitelisted to `start`/`stop` (existing). The freestyle config value is bounded `Field(gt=0)`. |
| V6 Cryptography | no | No crypto in scope. |
| V12 File Resources | yes | Write path is FIXED server-side (`channel_dir` + constant `overlay_run.json`) — operator never supplies a path (T-05-05-01 path-traversal mitigation, same as existing files [VERIFIED: src/segugio/ui/app.py L51-62]). |

### Known Threat Patterns for the console (Flask + opcomm, LAN)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overlay-JSON injection (operator-typed values reach a future HTML sink) | Tampering | `fields` carried verbatim here; HTML-escaping is the Phase-11/Phase-14 sink concern (Jinja autoescape / `textContent`). NOT this phase — but note for the planner that the contract carries raw values by design (D-08). |
| Path traversal via the new file write | Tampering | Fixed `_OVERLAY_RUN_FILE` constant + `_path()` join; never operator-supplied (T-05-05-01). |
| `/overlay-json` poll storm starving `/command` | Denial of Service | Out of scope this phase (Phase 14 / UXT-02 extends the concurrency test to the new route). The route is pure read — no long-lived connection (no SSE/WS — rejected transport). |
| Crash via torn source file | Denial of Service | `read_*` safe-default never-raise boundary (D-04) — route returns 200 + blank, never 500. |

## Sources

### Primary (HIGH confidence)
- `src/segugio/ui/app.py` — `create_app(channel_dir, cam_ids=())`, import allowlist (Flask inside factory), `post_run`/`post_score` handlers, `Cache-Control: no-store` precedent, `get_status`/`get_preview` route shape, entrypoint cam_ids resolution — full read
- `src/segugio/opcomm/channel.py` — `_read_json` never-raise boundary, `write_*`/`read_*` safe-default pattern, `write_preview`/`read_preview` template, `__all__` — full read
- `src/segugio/opcomm/records.py` — `ScoreDoc`/`RunState`/`PreviewDoc` frozen-record + `__post_init__` normalization convention, `ScoreDoc()` default discipline (`disc_tf`) — full read
- `src/segugio/opcomm/atomic.py` — `atomic_write_json` (always-fsync, same-dir temp, Windows MoveFileEx retry) — full read
- `src/segugio/orchestrator/preview.py` — `PreviewDoc.gen` precedent: closure-held counter, Lock-guarded bump, persisted in sidecar — full read
- `src/segugio/ui/score_render.py` — `render_overlay_text` + `_get` alias resolution + `_clean` (survives as overlay.txt fallback; out of scope to change) — full read
- `src/segugio/config/models.py` + `config/loader.py` — `PreviewParams`/`ActionHoldParams` additive-sub-model precedent, `ConfigDict(extra="forbid")`, `default_factory`, fail-fast `SystemExit(2)` — full read
- `tests/test_imports.py` — the crash-isolation gate `test_console_resolves_with_heavy_stack_and_numpy_absent` (L87-107) + `CONSOLE_HEAVY_MODULES` — full read
- `tests/test_ui_run.py`, `tests/test_ui_score.py`, `tests/conftest.py` (`file_channel` fixture L422-439) — the route-test + fixture patterns to replicate — full read
- `.planning/phases/10-.../10-CONTEXT.md` — D-01..D-08 locked decisions — full read
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` §Phase 10 — OVD-01/02/03, RBT-07, success criteria, Out-of-Scope — full read

### Secondary (MEDIUM confidence)
- `.planning/research/v1.2/SUMMARY.md` — the publish-and-render decision, clock-skew offset-cancellation strategy, transport=fetch-polling, the `overlay_run.json`/`OverlayRun` design (corroborates CONTEXT)
- `docs/security.md` — LAN-trust-boundary posture, no-auth accepted decision, path-traversal mitigation pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; all primitives read directly from source.
- Architecture: HIGH — every integration point (route signatures, record shapes, write order, gen mechanics) verified against the existing code; the `PreviewDoc` triad is a line-by-line template.
- Pitfalls: HIGH — derived from the verified HARD invariants (director-untouched, crash-isolation) and the documented v1.2 research pitfalls (P1/P3/P5).

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable — in-repo patterns, no external version drift; the only dependency is Flask, already pinned).
