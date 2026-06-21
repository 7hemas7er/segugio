# Phase 10: Overlay Data Contract & Run-Timestamp Publish - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

The console publishes everything the future overlay needs as a **boundary-safe JSON contract** (`GET /overlay-json`), and stamps the run-start instant into a **NEW console-owned `overlay_run.json`** — without touching the director or any director-read file. This is the *gating data foundation* of milestone v1.2: pure data channel + route, **zero HTML** (the renderer is Phase 11).

**In scope:**
- New console-owned `overlay_run.json` carrying `{running, started_at, gen}`, stamped on the `/run` start/stop edge.
- New `GET /overlay-json` route returning `{discipline, fields (verbatim), running, started_at, server_now, gen}` with `Cache-Control: no-store`, never raising on absent/torn/malformed sources.
- `server_now` (console `time.time()` at response — the clock-skew anchor) + monotonic `gen` (bumped on every `/run` and `/score` write, seeded from disk across restart) present in every response.
- A new `overlay.*` config section (pydantic) defining `overlay.freestyle_duration_s` (default 120) — **defined now, consumed in Phase 11.**
- Crash-isolation re-verified: the overlay route code imports only `Flask + segugio.opcomm` (RBT-07).

**Out of scope (deferred to later v1.2 phases):**
- Any HTML/CSS/JS overlay page, the self-counting timer, animations, branding render → Phase 11.
- Console-preview iframe reuse / mirror retirement → Phase 12.
- OBS scene-collection wiring + setup docs → Phase 13.
- End-to-end live degrade/poll-storm acceptance → Phase 14.
- **Any compute on the director / any change to `runstate.json`** (HARD invariant — never).

</domain>

<decisions>
## Implementation Decisions

### Run-state + gen file layout
- **D-01:** ONE console-owned file `overlay_run.json` carries `{running, started_at, gen}`. Mirrors the single-sidecar `PreviewDoc` shape; one atomic write per `/run` and `/score`. Do NOT split `gen` into a separate counter file, and do NOT derive `gen` from file mtimes.
- **D-02:** `gen` is seeded from disk on `create_app` startup — read `overlay_run.json` back and continue the in-memory counter from the persisted value (never reset to 0). This is what lets a mid-run console restart re-anchor the Phase-14 timer with no phantom jump. `gen` is a NEW console-owned counter, distinct from the orchestrator-side `PreviewDoc.gen`.
- **D-03:** `/run` keeps writing `runstate.json` **exactly as today** (byte-for-byte unchanged — the director reads it every tick). The new `overlay_run.json` write is *additional*, alongside it, in the same `/run` handler. On START: `running=true`, `started_at=<console time.time()>`. On STOP: `running=false`, `started_at=null`.

### Safe-default payload semantics
- **D-04:** Blank-safe and **stateless**. A missing/torn/malformed source at poll time → empty `fields` / `running:false` / default `discipline`, exactly like the existing `read_score`/`read_runstate` pattern (pure functions over `_read_json`). NO in-memory "last-good" cache on the route. Atomic `os.replace` writes make torn reads near-impossible, so this only triggers on genuine corruption — where blanking is the honest signal. `server_now` + `gen` are ALWAYS set regardless.

### Freestyle round-duration config (resolves the flagged blocker)
- **D-05:** Add a NEW `overlay.*` config section (pydantic, in `config/models.py`). It will also be the future home of the BRD-01 logo path + CSS-var theme + identity line in Phase 11 — so the model grows in one place.
- **D-06:** Key = `overlay.freestyle_duration_s`, **default 120** (the user's circuit runs 2-minute freestyle routines; orgs running 90s override in config). Defined now; **consumed in Phase 11**.
- **D-07:** The freestyle duration does NOT go into the `/overlay-json` poll payload. The contract stays exactly the locked 6 live fields. The duration is *static config* and will be injected once into the `/overlay` page at render time in Phase 11 (entrypoint-resolved arg, the same pattern as `cam_ids` today — the console never `import`s config at module top). Rationale: poll = live state, page = static config.

### `fields` exposure shape
- **D-08:** `/overlay-json` passes `score.fields` as the **raw verbatim dict** (operator-typed keys + values) alongside `discipline`. The server does NOT pre-resolve aliases or emit a discipline-normalized structure. The shared Phase-11 JS renderer owns per-discipline layout AND alias resolution (`sct`/`SCT`) — it must encode the layout anyway to build the lower-third. This keeps the crash-isolated console a dumb data pipe (smallest RBT-07 surface) and keeps a single rendering brain client-side (the v1.2/SCV direction). "Verbatim" governs the *values* (operator-typed, never computed — SCR-04); raw keys are consistent with that.

### Claude's Discretion
- Exact module placement of the new route(s) and the overlay-run read/write helpers (new `read_overlay_run`/`write_overlay_run` in `opcomm/channel.py` + a frozen `OverlayRunDoc` record in `opcomm/records.py`, mirroring the `PreviewDoc`/`read_preview` precedent — strongly implied by D-01/D-04 but the planner finalizes naming).
- Whether `gen` lives as a field on the `OverlayRunDoc` record or as a small route-local counter persisted via that record (D-01/D-02 require it persisted in `overlay_run.json`; the in-memory holding mechanism is the planner's call).
- The precise safe-default `discipline` value when `score.json` is absent (the `ScoreDoc()` default `disc_tf`, vs echoing a configured discipline) — lean to the existing `ScoreDoc()` default per D-04's "match existing pattern".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements & milestone shape
- `.planning/REQUIREMENTS.md` — OVD-01/02/03 + RBT-07 (the four Phase-10 requirements), and the **Out of Scope** table (esp. "no compute on the director", "WebSocket/MJPEG/SSE rejected", "no removal of `overlay.txt` fallback").
- `.planning/ROADMAP.md` §"Phase 10" — the goal + 4 success criteria this phase is graded against; also the v1.2 milestone build-order rationale.

### Research (milestone v1.2)
- `.planning/research/v1.2/SUMMARY.md` — the publish-and-render decision, clock-skew/offset-cancellation strategy, transport=fetch-polling.
- `.planning/research/v1.2/ARCHITECTURE.md` — contract/route architecture for the overlay channel.
- `.planning/research/v1.2/PITFALLS.md` — known traps (incl. the CEF border-radius gray-edge note for later phases).

### Code this phase extends (the publish-and-render precedent)
- `src/segugio/ui/app.py` — the crash-isolated console; where `GET /overlay-json` and the `overlay_run.json` write land. NOTE the import allowlist (Flask + `segugio.opcomm` only) and the entrypoint `cam_ids` arg pattern (the model for injecting config-derived values without importing config).
- `src/segugio/opcomm/channel.py` — `_read_json` never-raise boundary + the `write_*`/`read_*` safe-default pattern to mirror for `overlay_run.json` (D-04).
- `src/segugio/opcomm/records.py` — `ScoreDoc`/`RunState`/`PreviewDoc` frozen-record + normalizing `__post_init__` convention; the new `OverlayRunDoc` record follows it.
- `src/segugio/orchestrator/preview.py` — the `PreviewDoc.gen` **precedent** (orchestrator-side monotonic gen + `?t=<gen>` cache-bust). The Phase-10 `gen` is the console-owned analog (D-02), NOT the same counter.
- `src/segugio/ui/score_render.py` — `render_overlay_text` + `_get` alias resolution (`sct`/`SCT`) + `_clean` length-bound/sanitize. Survives as the `overlay.txt` fallback renderer; its per-discipline layout is the reference the Phase-11 JS renderer mirrors (D-08).
- `src/segugio/config/models.py` (+ `config/discipline.py`) — where the new `overlay.*` pydantic section is added (D-05/D-06); `extra=forbid` + fail-fast `SystemExit(2)` loader convention applies.

### Crash-isolation gate
- `docs/security.md` — the LAN-trust-boundary threat model; RBT-07 crash-isolation posture.
- Crash-isolation import test (the `test_app_imports_nothing_heavy`-style gate that forces `torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws` absent AND proves the console starts) — must stay green; extend it to cover the new route.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `opcomm/channel.py::_read_json` — the single never-raise read boundary; reuse it for `read_overlay_run` so a torn/absent file → safe default (D-04).
- `opcomm/atomic.py::atomic_write_json` — always-fsync atomic writer (handles the Windows `MoveFileEx` sharing-violation retry); the `overlay_run.json` write rides this.
- `PreviewDoc` + `write_preview`/`read_preview` — the exact template for a new `OverlayRunDoc` + `write_overlay_run`/`read_overlay_run` (frozen, normalizing `__post_init__`, safe-default reader).
- `create_app(channel_dir, cam_ids=())` entrypoint arg pattern — the precedent for injecting config-derived values (freestyle duration in Phase 11) WITHOUT importing config inside the crash-isolated module.

### Established Patterns
- **Director untouched / separate files per message** (RESEARCH Pattern 3): `overlay_run.json` is a NEW file; `runstate.json` write path is unchanged (D-03). This is what keeps "director never touched" literally true.
- **`gen`/nonce/`no-store`** cache-bust pattern from v1.1 preview — re-applied here (server-side `Cache-Control: no-store` + client `?t=<gen>` later).
- **Display-only verbatim (SCR-04)** — the contract carries operator-typed values unmodified; no summing/judging anywhere (D-08).
- **Crash-isolation allowlist** — `import segugio.ui` is Flask-free (Flask imported inside `create_app`); the new route must not add any heavy import.

### Integration Points
- `POST /run` handler (`app.py`) — add the `overlay_run.json` write here, alongside the existing `write_runstate` call (D-03).
- `POST /score` handler (`app.py`) — must bump `gen` on every write (D-02); the score values flow into `/overlay-json` via `read_score` (verbatim, D-08).
- New `GET /overlay-json` route — assembles the payload from `read_score` (discipline+fields) + `read_overlay_run` (running+started_at+gen) + `time.time()` (server_now).
- `config/models.py` — new `overlay.*` section (D-05/D-06); the entrypoint that already resolves `cam_ids` will later also resolve `overlay.freestyle_duration_s` for Phase 11.

</code_context>

<specifics>
## Specific Ideas

- The clock-skew solution is offset-cancellation only: the client (Phase 11) computes `skew = server_now − Date.now()/1000` per poll and counts locally — **never** a naive `Date.now() − started_at` across two machines. Phase 10's sole job for this is to put `server_now` (console clock) + `started_at` (console clock) in the contract from the first commit. Both timestamps are the SAME (console) clock domain.
- `started_at` persists across a console restart while a run is in progress (it's on disk in `overlay_run.json`), so a restart keeps `running=true` + the original `started_at` and re-seeds `gen` from disk (D-02) → the Phase-14 "restart re-anchors via gen without a phantom jump" success criterion is set up here.

</specifics>

<deferred>
## Deferred Ideas

- **Freestyle-duration consumption** (timer counts down from it) — Phase 11. Phase 10 only defines the config key + default.
- **BRD logo path / CSS-var theme / identity line** — Phase 11. They will share the new `overlay.*` config section created here (D-05), but no branding fields are added in Phase 10.
- **`source_ok` / explicit degrade flag in the payload** — considered (option in the safe-default discussion) and not taken; the contract stays the locked 6 fields. Revisit only if Phase 11/14 finds the client genuinely cannot distinguish "empty run" from "source failed" using `running` + fetch-failure + gen-age.
- **Discipline field-schema hint in the contract** — considered and not taken (D-08 keeps raw verbatim); the renderer owns the schema.

*Discussion otherwise stayed within phase scope.*

</deferred>

---

*Phase: 10-overlay-data-contract-run-timestamp-publish*
*Context gathered: 2026-06-14*
