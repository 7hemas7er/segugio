# Architecture Patterns

**Domain:** OBS browser-source graphical overlay served by a crash-isolated Flask console (Segugio v1.2)
**Researched:** 2026-06-14

---

## Recommended Architecture

v1.2 is a **publish-and-render extension of the existing opcomm-over-files pattern** — the same shape v1.1 used for the preview channel. The console gains two GET routes that turn data it ALREADY has on disk (`score.json` written by `POST /score`, plus a NEW console-owned `overlay_run.json`) into a transparent animated HTML page that OBS loads as a Browser source. **No new write-path touches the director, and the console still imports only Flask + `segugio.opcomm`.**

The single hard architectural constraint that shapes every decision below: **the director reads `runstate.json` every tick** (`orchestrator/loop.py` → `read_runstate` → acts on `just_started`/`just_stopped`). Therefore the run-start *timestamp* the timer needs must NOT be added to `runstate.json` — that would mutate a safety-critical file the director parses each tick. The console stamps it into a **separate new file** it owns end-to-end.

```
                    ┌─────────────────────── DIRECTOR (orchestrator) — NEVER TOUCHED ─────────┐
                    │  loop.py: read_runstate(runstate.json) each tick                         │
                    │           reads score? NO. reads overlay_run.json? NO.                   │
                    └──────────────────────────────▲───────────────────────────────────────────┘
                                                    │ runstate.json (UNCHANGED contract)
                                                    │
   OPERATOR (tablet) ──POST /run──────────► CONSOLE (Flask, separate process)
                     ──POST /score─────────►  • write_runstate(runstate.json)   ← existing, untouched
                                              • write_overlay_run(overlay_run.json) ← NEW (start ts / clear)
                                              • write_score(score.json) + overlay.txt ← existing
                                              ─────────────────────────────────────────────
                                              GET /overlay        → templates/overlay.html (shared renderer)
                                              GET /overlay-json    → {score, run, server_now, gen} (NEW)
                                                    │
                                                    │ HTTP over LAN (OBS may be a DIFFERENT machine)
                                                    ▼
                              OBS Browser source "Score Overlay" (transparent) — PRIMARY
                              OBS Text source "Score Text" (overlay.txt)        — FALLBACK
```

### Component Boundaries

| Component | Responsibility | Communicates With | New/Modified |
|-----------|---------------|-------------------|--------------|
| `opcomm/records.py` :: `OverlayRun` | Frozen record: `started_at: float\|None`, `running: bool`, `gen: int` — the run-timer source of truth | console writer/reader | **NEW** |
| `opcomm/channel.py` :: `write_overlay_run` / `read_overlay_run` | Atomic write + safe-default never-raise read of `overlay_run.json` | `atomic_write_json`, console | **NEW** |
| `ui/app.py` :: `POST /run` | Existing run write **plus** a side-write of `overlay_run.json` on the edge | `write_runstate`, `write_overlay_run` | **MODIFIED** |
| `ui/app.py` :: `GET /overlay` | Serve the transparent overlay HTML page (the shared renderer host) | `render_template` | **NEW** |
| `ui/app.py` :: `GET /overlay-json` | Assemble `{score, run, server_now, gen}` from `read_score` + `read_overlay_run` | channel readers | **NEW** |
| `ui/templates/overlay.html` | The transparent animated lower-third + client-side timer + freshness logic | GET /overlay-json | **NEW** |
| `ui/static/overlay-render.js` | The ONE shared score→DOM renderer imported by both `overlay.html` and `console.html` (SCV-01 unification) | both pages | **NEW (shared asset)** |
| `ui/templates/console.html` | Live preview now `<iframe src="/overlay?preview=1">` OR imports the shared renderer; the byte-exact JS mirror of `render_overlay_text` is RETIRED | shared renderer | **MODIFIED** |
| `ui/score_render.py` :: `render_overlay_text` | Stays as the **fallback** `overlay.txt` plain-text renderer (degraded path) | `POST /score` | **UNCHANGED** |
| `obs/segugio-scene-collection.json` | Add a `browser_source` "Score Overlay" item to every `CAM *`/`SAFE`/`MULTIVIEW`/`PIP` scene, above the NDI source | OBS import | **MODIFIED (or NEW versioned file)** |
| `docs/obs-setup.md` | Document the Browser source URL, transparency/`shutdown_source` settings, console-IP-on-LAN | operator | **MODIFIED** |

### Data Flow

1. Operator taps **Avvia run** → `POST /run {action: start}`. Console writes `runstate.json` (unchanged) AND `overlay_run.json = {started_at: time.time(), running: true, gen: gen+1}`.
2. Operator types a score, submits → `POST /score`. Console writes `score.json` + `overlay.txt` (both unchanged), and bumps a monotonic `gen` so pollers see a new revision.
3. OBS Browser source has loaded `GET /overlay` once at scene activation. Its JS polls `GET /overlay-json` ~2–4 Hz.
4. `/overlay-json` returns the current `ScoreDoc` fields + `{started_at, running}` + **`server_now` (the console's `time.time()` at response time)** + a monotonic `gen`.
5. The page renders the lower-third via the shared renderer, and runs the timer **client-side** off `started_at` corrected by a server/client clock offset (see clock-skew below).
6. Operator taps **Ferma run** → `overlay_run.json = {started_at: null, running: false, gen++}`; the timer freezes/clears, exit animation plays.

---

## (a) Route design — what `/overlay-json` returns

`GET /overlay` is a thin host page: it returns `templates/overlay.html` with a transparent body, links `static/overlay-render.js`, and starts the poll loop. No data is baked in (so the page need not reload when scores change). A `?preview=1` query can suppress animations / fit the console iframe if desired.

`GET /overlay-json` is the data channel. Recommended payload:

```jsonc
{
  "discipline": "disc_tf",                 // from read_score (drives layout)
  "fields": { "prese": "7", "zona": "3", "totale": "10" },  // verbatim, display-only (SCR-04)
  "running": true,                         // from read_overlay_run
  "started_at": 1749902400.123,            // epoch seconds, console clock; null when stopped
  "server_now": 1749902412.456,            // console's time.time() AT RESPONSE — the skew anchor
  "gen": 42,                               // monotonic; bumps on every /run and /score write
  "text": "Prese: 7  Zona: 3  Totale: 10"  // OPTIONAL: the render_overlay_text() string, kept
                                           //   so degraded clients / parity tests have it
}
```

`fields` is passed through verbatim (the renderer formats, never computes — SCR-04 invariant preserved). `server_now` is the **only addition that exists purely to solve clock skew** (see (c)). `gen` carries the freshness contract (see (d)). The route is a pure read of two opcomm files via the existing safe-default readers — no IO into any safety-critical file, no director import. Set `Cache-Control: no-store` (mirrors the preview-JPEG route) so OBS/CEF never serves a stale cached poll.

---

## (b) Where the run start time comes from — a NEW console-owned file

**Do NOT extend `runstate.json`.** The director reads it every tick (`loop.py` line ~432, `read_runstate`); adding a timestamp field changes a safety-critical file's contract and risks "director touched." Instead:

- Add a frozen `OverlayRun(started_at: float|None, running: bool, gen: int)` record + `write_overlay_run`/`read_overlay_run` (mirroring `PreviewDoc`/`read_preview` exactly: normalizing `__post_init__`, safe-default never-raise read).
- In `POST /run`, AFTER the existing `write_runstate(...)`, side-write `overlay_run.json`:
  - on `action == "start"` (the `just_started` edge): `started_at = time.time()`, `running = True`, `gen += 1`.
  - on `action == "stop"` (the `just_stopped` edge): `started_at = None`, `running = False`, `gen += 1`.
- Seed `gen` from the file on startup (read current, increment) so it survives a console restart — the same approach `preview.py` uses.

This gives the timer an authoritative start instant **owned entirely by the console**, with zero director compute and zero new director read. It is the v1.1 "publish-and-render, no new write-path into the safety-critical core" precedent applied to a console-internal file.

**Edge correctness:** `POST /run` is edge-driven today (`just_started`/`just_stopped` are one-tick flags consumed by the director). The console writing an absolute `started_at` is idempotent and survives the director consuming the edge — the timestamp is the durable state the edge produced.

---

## (c) The clock-skew problem — RECOMMENDATION: option (ii), offset-once

OBS may run on a different machine than the console (KEY DEPLOYMENT FACT). Three options evaluated:

| Option | Mechanism | Verdict |
|--------|-----------|---------|
| (i) server elapsed-seconds + client interpolate | `/overlay-json` returns `elapsed = server_now - started_at`; client adds its own `Date.now()` delta between polls | Works, but every poll **snaps** the displayed time → visible jitter/jumps if a poll is late. Snapping a broadcast timer looks broken. |
| **(ii) start_ts + server_now → compute offset** ✅ | Client uses `server_now` to anchor: `skew = server_now - Date.now()/1000`, then displays `(Date.now()/1000 + skew) - started_at`, counting locally between polls; re-measures `skew` each poll. | **RECOMMENDED.** The timer counts on the browser's own smooth `requestAnimationFrame`/`setInterval` tick (no per-poll snapping), while the offset removes absolute clock skew between the two machines. Sub-second accuracy; immune to the boxes' wall clocks differing by minutes. |
| (iii) WebSocket / SSE push of a server tick | Director/console pushes time | Rejected: adds a network/streaming server path, fights crash-isolation, overkill for a once-per-run anchor. |

**Recommended formula (option ii):**

```js
// On each /overlay-json poll:
//   skew    = server_now - (Date.now()/1000)      // server-minus-client offset, re-measured each poll
//   elapsed = (Date.now()/1000 + skew) - started_at
// The DISPLAYED timer advances off the local rAF/interval between polls, so it never visibly snaps;
// the re-measured skew silently self-corrects clock drift on every poll.
```

Why this beats (i): a late/dropped poll never makes the timer jump backward or freeze — it keeps counting smoothly and re-aligns on the next poll. This serves the "broadcast-quality, no tremble" core value applied to the timer. Subtlety: `started_at` and `server_now` are BOTH the console's clock, so `(server_now - started_at)` is already clean elapsed on the server; the client only needs the offset to keep counting locally. Robust even with no NTP on either box.

---

## (d) Freshness — never show a frozen overlay as live (UXT-03 principle)

Reuse v1.1's proven `gen`-strictly-advances staleness gate (already in `console.html` `isStale()`/`pollPreview`):

- `/overlay-json` carries a monotonic `gen` (bumped on every `/run` and `/score` write).
- The overlay JS records `lastGenAt = Date.now()` whenever `gen` advances.
- `isStale()` = `lastGen seen AND (Date.now() - lastGenAt) > STALE_MS`. On a cold load (no gen yet) it is NOT stale (WR-02 — never falsely degrade the first paint).
- **Two staleness sources to degrade on:**
  1. **Poll failure / no advance** → console process died or LAN dropped. After `STALE_MS`, **stop the client timer** and dim/hide the dynamic parts. A frozen timer that keeps ticking is the worst broadcast failure — it must STOP and visibly degrade.
  2. **HTTP error / unreachable** → CEF `fetch` rejects; coast (never throw) and treat as stale after the window.
- **Degrade behavior:** stop the timer, freeze the last-known score, apply a "degraded" visual. Crucially, the **`overlay.txt` Text source remains underneath** so OBS still airs *a* score even if the Browser source goes stale (see (f)). The Browser overlay must never present a stale timer as live — matching UXT-03 "a frozen frame is NEVER live."

This is the same watchdog discipline the multiview already ships, applied to the overlay's timer and score block.

---

## (e) SCV-01 unification — ONE renderer, two hosts

Today there are TWO renderers that must stay byte-identical: Python `render_overlay_text` and a hand-maintained byte-exact JS mirror inside `console.html` (the `gsd:scv01-mirror` block, lines 341–391), policed by a `/score/preview` drift-guard. v1.2 collapses the graphical path to a single JS renderer:

**Mechanism: a shared static asset, imported by both pages.**

- Create `ui/static/overlay-render.js` exporting one function, e.g. `renderOverlay(rootEl, {discipline, fields, running, elapsedSeconds})`, that builds the graphical lower-third DOM (and formats the timer). This is the SINGLE source of truth for the graphical overlay's appearance.
- `GET /overlay` (the OBS page) loads it and calls it on each poll.
- `console.html` (the live preview) loads the **same** file. Two viable wirings:
  1. **iframe reuse (strongest guarantee):** the console preview is literally `<iframe src="/overlay?preview=1">`. Console and OBS then render through the identical page — drift is structurally impossible, no mirror, no drift-guard. **Recommended.**
  2. **shared-module reuse:** the console imports `overlay-render.js` directly and renders into a preview node. Lighter-weight; one asset, one renderer, still no second implementation.

Either way, **the byte-exact JS-mirror-of-Python and the `/score/preview` drift-guard are retired** for the graphical path — there is no second renderer left to drift from. `render_overlay_text` (Python) survives ONLY as the independent `overlay.txt` fallback renderer; an optional parity test can keep `overlay.txt` and the graphical text roughly aligned, but they are no longer required byte-identical because they feed different sources.

Recommendation: **iframe reuse (option 1)** — it makes "they can't drift" a property of the architecture, not of a test.

---

## (f) overlay.txt fallback coexistence — Browser primary, Text fallback, both wired

**Both paths stay active. Browser source is primary; the Text source is the degraded fallback.**

- `POST /score` continues to write BOTH `score.json` (structured, now also feeding `/overlay-json`) and `overlay.txt` (rendered plain line). Zero change to the existing write — the graphical path is purely additive.
- In OBS, every scene gets the new transparent **"Score Overlay" Browser source** wired ABOVE the existing **"Score Text"** source.
- Coexistence policy (operator-selectable, documented in `docs/obs-setup.md`):
  - **Normal:** Browser source visible (graphical lower-third), Text source hidden or behind it. The graphical overlay airs.
  - **Degraded:** if the Browser source goes stale/blank (console down, CEF crash, LAN drop), the Text source — fed by the atomically-written `overlay.txt`, which has no network dependency and survives a console restart — guarantees a readable score still airs (SCR-01 robustness preserved).
- This honors the live-robustness constraint: the *richer* path can fail without leaving the broadcast scoreless, because the *simpler, file-only* path is still there.

---

## Patterns to Follow

### Pattern 1: Console-owned side-file for derived state
**What:** When the overlay needs state derived from an operator action (run start instant), the console writes it to a NEW file it solely owns (`overlay_run.json`), never into a file the director reads.
**When:** Any v1.2 state the timer/animations need that isn't already in `score.json`.
**Example:** `POST /run` → `write_runstate(...)` (director's file, unchanged) + `write_overlay_run(...)` (console's file).

### Pattern 2: Mirror the PreviewDoc record contract
**What:** New `OverlayRun` record copies `PreviewDoc` exactly — frozen dataclass, normalizing `__post_init__`, `gen` cache-bust token, and a `read_overlay_run` that safe-defaults on absent/torn/malformed and NEVER raises.
**When:** The new opcomm record + reader/writer.

### Pattern 3: gen-strictly-advances freshness watchdog
**What:** Reuse `console.html`'s `isStale()` gate verbatim for the overlay's timer/score.
**When:** The overlay's staleness/degrade logic.

### Pattern 4: One renderer, hosted twice
**What:** A single `overlay-render.js` (or a shared `/overlay` page via iframe) renders both the OBS overlay and the console preview.
**When:** SCV-01 unification.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Putting `started_at` in `runstate.json`
**What:** Adding a timestamp field to the director-read run file.
**Why bad:** Mutates a safety-critical file the director parses every tick → breaks "director never touched," risks a parse edge in the loop.
**Instead:** A separate console-owned `overlay_run.json`.

### Anti-Pattern 2: Client timer off raw server timestamp minus local clock
**What:** `elapsed = Date.now()/1000 - started_at` with no offset.
**Why bad:** OBS on a different machine drifts by the two clocks' difference (could be minutes) → wrong timer.
**Instead:** Option (ii) offset-once (re-measured each poll), counting locally between polls.

### Anti-Pattern 3: Keeping the byte-exact Python↔JS mirror
**What:** Maintaining two renderers + a drift-guard for the graphical overlay.
**Why bad:** Defeats the SCV-01-simplification goal; reintroduces drift risk.
**Instead:** One shared renderer; `render_overlay_text` survives only for `overlay.txt`.

### Anti-Pattern 4: A streaming server (WebSocket/SSE) on the console for the timer
**What:** Pushing time to the overlay.
**Why bad:** Adds a network-server path, complicates crash-isolation, unnecessary for a once-per-run anchor.
**Instead:** Polling `/overlay-json` + client-side counting.

### Anti-Pattern 5: Letting the graphical overlay be the ONLY score path
**What:** Removing/ignoring `overlay.txt`.
**Why bad:** A CEF crash or LAN drop would air a scoreless broadcast.
**Instead:** Keep `overlay.txt` as the always-on file-only fallback.

## Scalability / Robustness Considerations

| Concern | Behavior |
|---------|----------|
| OBS on a different box | Solved by clock-offset (c) + the overlay polling the console's LAN IP (document in obs-setup.md). |
| Console process dies | Browser overlay goes stale → degrades (d); `overlay.txt` Text source keeps last score (f). |
| CEF Browser source crash | OBS `shutdown_source_when_not_visible` off so it reloads; Text fallback covers the gap. |
| Concurrent `/run` + `/overlay-json` poll | `threaded=True`/Waitress already required (v1.1 UXT-02 safety control) — a poll never starves the override POST. Atomic writes mean a poll never reads a torn file. |
| Score updates ~Hz | Bandwidth trivial (small JSON), unlike the preview JPEGs; no cap needed. |

---

## Suggested Build Order (phases respect crash-isolation + "director never touched")

Numbering continues from v1.1 (project is at Phase 10).

1. **Phase 10 — opcomm record + run-timestamp publish (data foundation).**
   Add `OverlayRun` record + `write_overlay_run`/`read_overlay_run` (mirror `PreviewDoc`). Modify `POST /run` to side-write `overlay_run.json` on the start/stop edge with a monotonic `gen`. Add `GET /overlay-json` returning `{discipline, fields, running, started_at, server_now, gen}`. Crash-isolation re-verified (import test with heavy stack absent). *No HTML yet — pure channel + route.* Deps: none. Unblocks everything.

2. **Phase 11 — the shared graphical renderer + `GET /overlay` page.**
   Build `static/overlay-render.js` (the lower-third per discipline) + `templates/overlay.html` (transparent body, poll loop, client timer with the option-(ii) offset, animations: entry/exit + score-pulse + run-edge reaction). Wire the freshness/degrade watchdog (`gen`-advance gate). Deps: Phase 10's `/overlay-json`.

3. **Phase 12 — SCV-01 unification (retire the mirror).**
   Repoint `console.html`'s live preview to the shared renderer (iframe `/overlay?preview=1` recommended). Remove the byte-exact JS mirror block + the `/score/preview` drift-guard (or downgrade `/score/preview` to a parity sanity test for `overlay.txt` only). Deps: Phase 11 (the shared renderer must exist first).

4. **Phase 13 — OBS scene-collection + docs.**
   Add the transparent "Score Overlay" Browser source (URL = `http://<console-ip>:8080/overlay`, transparency on, FPS/size set, `shutdown_source_when_not_visible` off) to every `CAM *`/`SAFE`/`MULTIVIEW`/`PIP` scene, layered above the NDI source and the Text fallback. Ship as a new versioned `obs/segugio-scene-collection.json` (or v1.2 variant) and update `docs/obs-setup.md` (Browser-source URL, cross-machine-IP note, Browser-primary/Text-fallback policy). Keep `test_scene_template.py` in lockstep. Deps: Phase 11 (the URL must serve something).

5. **Phase 14 — fallback-coexistence + degrade hardening (field-facing robustness).**
   Verify Browser-primary / Text-fallback end-to-end: console-down → overlay degrades and Text keeps last score; LAN-drop → timer stops, no stale "live"; restart → re-anchors via `gen`. The live-robustness gate before field acceptance. Deps: Phases 11 + 13.

**Why this order:** data contract before renderer (a renderer needs `/overlay-json`); renderer before unification (the console preview repoints to it); renderer before OBS wiring (the Browser source needs a live URL); robustness last (it tests the whole assembled path). Phases 10–12 never touch the director or any director-read file; Phases 13–14 are OBS/docs/validation only. Crash-isolation is re-asserted at Phase 10 and stays green because every new code path imports only Flask + `segugio.opcomm`.

---

## Sources

- `src/segugio/ui/app.py`, `ui/score_render.py`, `ui/templates/console.html` (lines 255–446, 700–877) — existing routes, the SCV-01 mirror block, the `gen`-advance freshness watchdog, the threaded-server safety control — **HIGH** (in-repo, read directly)
- `src/segugio/opcomm/records.py`, `opcomm/channel.py`, `opcomm/atomic.py` — record/reader/writer patterns to mirror (`PreviewDoc`/`read_preview`), atomic write + Windows MoveFileEx retry — **HIGH** (in-repo)
- `src/segugio/orchestrator/loop.py` (lines 31–34, 60–64, 424–565) — proves the director reads `runstate.json` every tick → the run-start timestamp must go in a separate file — **HIGH** (in-repo)
- `obs/segugio-scene-collection.json`, `docs/obs-setup.md` — current scene structure (`Score Text` text source per scene) the Browser source plugs into — **HIGH** (in-repo)
- `.planning/PROJECT.md` — v1.2 goal, target features, the crash-isolation HARD constraint, cross-machine OBS deployment fact — **HIGH** (in-repo)
