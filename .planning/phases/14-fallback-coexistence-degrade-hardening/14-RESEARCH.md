# Phase 14: Fallback Coexistence & Degrade Hardening - Research

**Researched:** 2026-06-20
**Domain:** Client-side overlay robustness (JS freshness watchdog + two-stage degrade), Flask concurrency-starvation testing, OBS read-from-file fallback coexistence, HTML-sink injection regression, docs/config consistency
**Confidence:** HIGH (all findings verified by direct codebase read; no external dependencies introduced)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Acceptance & Validation**
- **D-01:** RBT-06 passes via BOTH mediums. Headless automation = the completion bar (everything simulable gets a test: renderer stale/degrade via node fake-DOM, gen re-anchor / no phantom jump, `/overlay-json` poll-storm extending the UXT-02 harness, HTML-escape sink). On-rig `HUMAN-UAT.md` checklist covers the physical scenarios (real OBS browser-source blanking/auto-hide, real LAN-cable drop, real `overlay.txt` airing the last score).
- **D-02:** The on-rig checklist does NOT block phase completion — deferred hardware/field UAT carry-forward (same disposition as Phases 5/7). Phase 14 closes when the automation gate is green AND `HUMAN-UAT.md` is written and ready to run on the rig.
- **D-03:** Add explicit, named gate regression tests for EACH success criterion (console-stops-responding → timer stops + degrade; fetch-reject → degrade; gen-resume → no phantom jump) even where the logic already exists and passes. RBT-06 must be a self-contained named gate, not "trust the existing freshness tests." Reuse the alt-port-sandbox + node-fake-DOM method.

**Degrade behavior (dead-console look)**
- **D-04:** Two-stage degrade. SHORT stale (≈600ms, existing `STALE_MS = 3×PUBLISH_MS`) keeps the current dim+grayscale (`opacity:0.55; filter:grayscale(0.4)`) — absorbs transient WiFi hiccups without flicker. A NEW longer "dead" threshold fully exits/hides the lower-third so NO frozen score airs from the browser source on a real death. (The timer already stops in all stale cases.)
- **D-05:** The dead→hide threshold is a JS constant `DEAD_MS ≈ 3000ms` added next to `STALE_MS`/`PUBLISH_MS` in `overlay-render.js` — mirrors how the existing freshness timing already lives as client constants; no new config/entrypoint surface. The hide must build on the response-recency watchdog (`everResponded`/`lastResponseAt`), NOT gen-age (per the 260615-tsi fix).

**Fallback coexistence / switchover**
- **D-06:** Simplified manual reveal. Because the browser overlay now auto-hides on death (D-04), the operator's only manual step is revealing the `Score Text` source. `Score Text` stays `visible:false` while the console is alive (avoids a double-score). Update `docs/obs-setup.md` to the one-action procedure and drop Phase-13's now-redundant "manually hide Score Overlay" step. The on-rig UAT walks the operator through it.

**Remediation scope**
- **D-07:** Fix inline, domain-bounded. Gaps WITHIN the overlay-robustness domain (degrade, gen re-anchor, concurrency, HTML-escape, fallback coexistence) get fixed in this phase. A gap OUTSIDE that domain (YOLO/tracking/NDI-decode) gets documented + deferred, not fixed here.
- **D-08:** Fold in the Phase-13-flagged NDI-source-name docs/config drift as a small operator-facing consistency fix (the recurring exact-`ndi_source`-name-match gotcha — "OBS sees it but console blank").

**Carried forward (LOCKED — do not re-litigate)**
- Console stays crash-isolated — imports only `Flask + segugio.opcomm`, director never touched (RBT-07, re-asserted as a success criterion of this phase).
- Transport = fetch-polling `/overlay-json` (WebSocket/MJPEG/SSE rejected — UXT-02 starvation).
- `overlay.txt` fallback = manual-toggle text source. The console writes `overlay.txt` on every `POST /score` via `atomic_write_text(_path("overlay.txt"), render_overlay_text(doc))` (`ui/app.py:210`) → the last score persists as a static file. This is the SC#1 coexistence proof.
- Score values sink via `textContent`, never `innerHTML` (Phase 11/12); `event_name`/`logo` are Jinja-autoescaped — SC#4 is a regression assertion, not new logic.

### Claude's Discretion
- Exact `DEAD_MS` tuning around ~3s; exact new test file names/structure; how the poll-storm test mirrors UXT-02's `< 1.0s` `/command` bar.

### Deferred Ideas (OUT OF SCOPE)
- On-rig HUMAN-UAT execution on real OBS hardware — carry-forward (like Phases 5/7 field UAT); the checklist is authored in Phase 14, executed on the rig later.
- OBS source-visibility hotkey for `Score Text` — considered for the switchover; not adopted (simplified manual reveal chosen). Note for a future ops-polish pass.
- OVL-FUT-01 visual agility-vs-SCT under/over-time treatment — already deferred in `REQUIREMENTS.md` Future Requirements.
- Any out-of-overlay-domain gap surfaced during validation (YOLO/tracking/NDI-decode) — documented in the verification report, fixed in its own phase/quick-task, not here (per D-07).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RBT-06 | `overlay.txt` maintained as the degraded fallback (SCR-01) — browser-source primary, text "read from file" as the always-works fallback if the browser-source dies/blanks on-air. Phase 14 = its acceptance validation under failure. | The `overlay.txt` writer is confirmed single-writer (`ui/app.py:210` POST /score); the dead-console fallback is structurally sound (no second writer clears it). The two-stage degrade (D-04/D-05) plus the named gate tests (D-03) make RBT-06 a self-contained gate. Every success criterion maps to an established simulation method (node fake-DOM, UXT-02 live_server harness) documented in `## Validation Architecture`. |
</phase_requirements>

## Summary

Phase 14 is a **validation + hardening gate**, not a feature build. Every underlying behavior already ships: the response-recency freshness watchdog (`everResponded`/`lastResponseAt`), the `.is-stale` dim+grayscale degrade, the offset-cancellation timer, the `gen` re-anchor on console restart, the `overlay.txt` text fallback (single-writer, `ui/app.py:210`), the `textContent` HTML sink + Jinja-autoescaped `event_name`/`logo`, and the UXT-02 concurrency harness (`tests/test_preview_concurrency.py`). The phase's job is to (a) add ONE named regression gate per success criterion even where the logic passes today, (b) add the two-stage `DEAD_MS` hide so a real console death fully removes the lower-third (no frozen score airs from the browser), (c) fold in the small NDI-source-name docs/config consistency fix, and (d) author a `HUMAN-UAT.md` checklist for the physical scenarios.

The two open research questions with material risk both resolved cleanly. **Double-writer (Q1): RESOLVED — no risk.** The orchestrator (`runtime.py`) only declares the `overlay.txt` path string for channel-bundle completeness (line 82, comment line 49-51: "score/overlay are written by the UI… harmless to the loop, which only reads the three it needs"). The orchestrator `loop.py` never writes `overlay.txt` and never calls `set_overlay_text` (zero callers in `src/`). The console's `POST /score` is the sole writer; a dead console simply stops updating the file, so the last score persists on disk for OBS — exactly the SC#1 coexistence proof. **NDI drift (Q5): FOUND.** `config.example.yaml:27` sets `cam_wide`'s `ndi_source` to `"LOCALHOST (iPhone Camera for OBS Studio App)"`, but the scene-collection JSON's `ndi_source_name` and `config.agility.example.yaml` both use `"PHONE-WIDE (NDI HX3)"`. The doc cites `PHONE-WIDE (NDI HX3)` as the example. This is the exact "OBS sees it but console blank" mismatch.

**Primary recommendation:** Plan ~2-3 plans: (1) the `DEAD_MS` two-stage hide hardening in `overlay-render.js` + its node fake-DOM gate test; (2) the four named gate regression tests (SC#1 coexistence-on-disk, SC#2 gen re-anchor/no-phantom-jump, SC#3 `/overlay-json` poll-storm extending the live_server harness, SC#4 HTML-sink regression) + the `HUMAN-UAT.md` checklist; (3) the D-06 docs simplification + D-08 NDI-name consistency fix. No new runtime dependency, no director change, crash-isolation preserved.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Two-stage degrade (`STALE_MS` dim → `DEAD_MS` hide) | Browser / Client (`overlay-render.js`) | — | All freshness/timer logic is client-side by locked design (zero director compute); the hide is one more threshold on the existing watchdog |
| `overlay.txt` text fallback write | API / Console (`ui/app.py` POST /score) | — | The crash-isolated Flask console is the sole writer; the director never touches it |
| `overlay.txt` airing when console dead | OBS / Static (read-from-file source) | — | Static file on disk; OBS reads it independently of the console's liveness |
| `/command` non-starvation under poll storm | API / Console (Flask `threaded=True` / waitress) | — | The safety-critical override route must never be blocked by `/overlay-json` GETs; a WSGI-threading concern, not a client one |
| HTML-escape of operator score values | Browser / Client (`textContent` sink) + API (Jinja autoescape) | — | Score values flow client-side via `textContent`; static branding (`event_name`/`logo`) is server-rendered + Jinja-autoescaped |
| Crash-isolation invariant (RBT-07) | API / Console (import surface) | — | The console imports only Flask + `segugio.opcomm`; every `segugio.ui` edit must keep `tests/test_imports.py` green |
| NDI-source-name consistency (D-08) | Config + Docs + OBS scene JSON | — | Operator-facing config/doc artifact, not runtime code |

## Standard Stack

No new packages. This phase adds tests + one client-side JS constant + docs/config edits. The relevant existing stack:

### Core (already installed, no version change)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | The crash-isolated console serving `/overlay`, `/overlay-json`, `/command`, `/score` | Locked; imported INSIDE `create_app` so `import segugio.ui` stays Flask-free |
| werkzeug (`werkzeug.serving.make_server`) | bundled with Flask | The real threaded ephemeral-port server for the UXT-02 / poll-storm concurrency test | Already the proven harness in `tests/test_preview_concurrency.py` — copy it |
| pytest | (repo standard) | Test runner; `@pytest.mark.skipif(node is None)` gate for node behavior tests | Established convention |
| Node.js | v24.16.0 (verified present this session) | Headless ES2020 execution of `overlay-render.js` against a fake DOM (the gate-test method) | The locked sandbox-repro method; `subprocess.run([node, ...])` with explicit UTF-8 decode (`tests/test_ui_overlay_render.py:_run_node`) |

**Installation:** None. `pip index versions` / `npm view` not applicable — no package is added or changed.

## Package Legitimacy Audit

> Not applicable — this phase installs NO external packages. It adds test files, one JS constant (`DEAD_MS`), and docs/config edits. No registry interaction, no `[SLOP]`/`[SUS]` surface.

## Architecture Patterns

### System Architecture Diagram

```
                         OPERATOR (tablet, dedicated WiFi LAN)
                                      │  POST /score, /run, /command
                                      ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  CONSOLE (Flask, crash-isolated: Flask + segugio.opcomm ONLY)     │
   │                                                                    │
   │  POST /score ──► write_score(score.json)                          │
   │              └─► atomic_write_text(overlay.txt, render_overlay_text)│  ◄── SOLE writer (ui/app.py:210)
   │              └─► _bump_score_gen()  (gen++, preserves running)     │
   │  POST /run   ──► write_runstate + _bump_overlay_run (gen++, started_at)
   │  GET /overlay-json ──► {discipline, fields verbatim, running,      │
   │                          started_at, server_now, gen}  no-store    │
   │  GET /overlay      ──► overlay.html (Jinja: event_name/logo autoescaped)
   │  POST /command     ──► write_command  (SAFETY-CRITICAL, must not starve)
   └───────────┬───────────────────────────────────┬──────────────────┘
               │ overlay.txt (static file on disk)  │ HTTP poll /overlay-json (?t=++reqSeq, no-store)
               ▼                                     ▼
   ┌────────────────────────┐         ┌──────────────────────────────────────┐
   │ OBS "Score Text"       │         │ OBS "Score Overlay" (CEF browser src) │
   │ read-from-file source  │         │  overlay-render.js poll loop:         │
   │  visible:false (D-06)   │         │   • lastResponseAt advances per poll  │
   │  manual reveal on death │         │   • isStale() = everResponded &&      │
   │  AIRS LAST SCORE when   │         │       now-lastResponseAt > STALE_MS   │
   │  console dead           │         │   • [NEW] isDead() = everResponded && │
   │                        │         │       now-lastResponseAt > DEAD_MS     │
   │                        │         │   • stale → .is-stale (dim+grayscale) │
   │                        │         │   • dead  → exit/hide lower-third     │
   │                        │         │   • timer stops (never frozen "live") │
   └────────────────────────┘         └──────────────────────────────────────┘

   DIRECTOR / orchestrator (loop.py): NEVER touched. runtime.py declares the
   overlay.txt path only for bundle completeness; never writes it. set_overlay_text
   exists on the OBS controller but has ZERO callers (built-but-idle OBS-API fallback).
```

### Recommended Project Structure (files this phase touches)
```
src/segugio/ui/static/overlay-render.js   # ADD DEAD_MS constant + isDead() + hide-on-dead (reuse .is-exiting / exit @keyframes)
tests/test_overlay_degrade_gate.py        # NEW (suggested) — node fake-DOM: SC#1 stale-then-dead, SC#2 gen re-anchor
tests/test_overlay_fallback_gate.py       # NEW (suggested) — SC#1 overlay.txt on-disk persistence after a /score then "death"
tests/test_overlay_poll_storm.py          # NEW (suggested) — SC#3 extend live_server harness to /overlay-json storm vs /command < 1.0s
tests/test_overlay_html_sink_gate.py      # NEW (suggested) — SC#4 textContent sink + Jinja autoescape regression
docs/HUMAN-UAT.md                         # NEW — the on-rig physical-scenario checklist (D-01/D-02)
docs/obs-setup.md                         # EDIT — D-06 one-action reveal; D-08 NDI-name note
config.example.yaml                       # EDIT — D-08 cam_wide ndi_source consistency
docs/security.md                          # re-affirm SC#4 HTML-sink posture (one line, if needed)
```
(Test file names are Claude's discretion per D-03; the above is a suggested split that keeps each criterion a self-contained named gate.)

### Pattern 1: Node fake-DOM gate test (the locked sandbox-repro method)
**What:** Execute the real, FROZEN `overlay-render.js` under Node against a minimal hand-rolled fake DOM + controllable `Date.now()`/`requestAnimationFrame`/`setInterval`/`fetch`, then assert observable state (`isStale()`, classList membership, rAF armed/stopped).
**When to use:** SC#1 (stale→dead degrade) and SC#2 (gen re-anchor / no phantom jump) — anything testing client timer/watchdog behavior.
**Example:** `tests/test_ui_overlay_render.py::test_live_idle_run_not_stale_but_console_down_is_stale` is the canonical harness — it already proves "console down → isStale True, .is-stale applied, rAF stopped." The new `DEAD_MS` gate extends this exact harness: advance `NOW` past `DEAD_MS` and assert the lower-third loses `is-live`/gains the exit/hidden state.
```python
# Source: tests/test_ui_overlay_render.py (the _run_node + fake-DOM harness, verified this session)
# Reuse verbatim: makeEl/makeClassList fake DOM, global.Date.now = () => NOW,
# global.fetch stub with a STATIC gen, drain() microtask pump, _run_node UTF-8 decode.
```

### Pattern 2: Real threaded server concurrency proof (UXT-02 harness)
**What:** Bind a real `werkzeug` server on an ephemeral port (`make_server("127.0.0.1", 0, app, threaded=True)`) on a daemon thread, fire N concurrent GETs, time a `POST /command`, assert `< 1.0s` AND the command was written.
**When to use:** SC#3 — the `/overlay-json` poll storm must not starve `/command`.
**Example:**
```python
# Source: tests/test_preview_concurrency.py (verified this session)
# Extend: replace the N concurrent "/preview/cam_wide.jpg" GETs with N concurrent
# "/overlay-json" GETs (the new route). Keep the identical _post_command timing + the
# `assert elapsed < 1.0` bar + `read_command(...).force_cam == "cam_long"` write check.
# The live_server fixture + _get/_post_command helpers copy directly.
```

### Pattern 3: HTML-sink regression assertion (SC#4)
**What:** Assert the renderer writes operator values via `textContent` (never `innerHTML`) and that Jinja autoescapes `event_name`/`logo`.
**When to use:** SC#4 — a precise named regression, not new logic.
**Example:**
```python
# Source: tests/test_ui_overlay_render.py::test_no_innerhtml_sink (verified this session)
#   asserts "innerHTML =" / ".innerHTML" absent from overlay-render.js.
# For the Jinja half: render /overlay with event_name="<script>x</script>" via the test
# client and assert the served HTML contains the ESCAPED form (&lt;script&gt;), proving
# autoescape is on at the #identity[data-event] + logo src sinks.
```

### Anti-Patterns to Avoid
- **Keying the `DEAD_MS` hide on gen-age** instead of response-recency — this is the exact 260615-tsi bug. `gen` stays FLAT during a normal live run (no heartbeat: it only advances on `/run` and `/score`). A gen-age hide would false-hide an idle-but-live overlay. `DEAD_MS` MUST use `everResponded && now - lastResponseAt > DEAD_MS`, mirroring `isStale()`.
- **Inventing a new animation primitive for the hide** — D-04 says reuse the existing exit path (`.is-exiting` / `@keyframes exit` in `overlay.html` lines 181-184/196). The dead state should drive the same exit-then-hidden visual, not a new keyframe.
- **Adding a `gen` heartbeat to make staleness "simpler"** — explicitly rejected; the response-recency design is the correct liveness signal. Do not reintroduce `lastGenAt` (the freshness test asserts `"lastGenAt" not in js`).
- **Testing the poll storm with Flask's in-process `test_client`** — it does NOT exercise WSGI threading; the real `make_server(..., threaded=True)` harness is mandatory for a true starvation proof (the `test_preview_concurrency.py` docstring calls this out).
- **A second `overlay.txt` writer** — do not add an orchestrator-side write; it would clear/overwrite the last score on console death and break the SC#1 coexistence proof. The single-writer property is load-bearing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Headless DOM for the renderer | A full jsdom/puppeteer harness or a new test framework | The existing minimal fake-DOM in `test_ui_overlay_render.py` | Zero new deps; proven; matches the locked sandbox-repro method (project memory `overlay-bugs-sandbox-repro`) |
| Concurrency/starvation proof | A custom thread-pool + ad-hoc server | The `live_server` fixture + `_get`/`_post_command` from `test_preview_concurrency.py` | Already the UXT-02 gold standard; the `< 1.0s` bar is the established contract |
| Atomic `overlay.txt` write | A new write path / a direct `open().write()` | The existing `atomic_write_text` (temp + fsync + `os.replace` with MoveFileEx retry) at `ui/app.py:210` | OBS read-from-file must never see a half-written line; the retry handles Windows reader contention |
| HTML escaping of branding | Manual `.replace("<","&lt;")` | Jinja autoescape (already on for `event_name`/`logo`) + `textContent` for score values | Hand-rolled escaping misses contexts; the framework sink is the verified mitigation |

**Key insight:** Every robustness behavior this phase validates already exists and is unit-tested. The risk is NOT missing logic — it is (a) a `DEAD_MS` hide that false-hides if mis-keyed, and (b) tests that pass for the wrong reason. The Validation Architecture section below pins what each gate must actually assert so a regression cannot pass silently.

## Runtime State Inventory

> Phase 14 is primarily a validation/hardening phase, but D-08 touches operator-facing config/scene state and the `overlay.txt` fallback is OS-level read-from-file state. Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `overlay.txt` on disk — the last rendered score line, written by `ui/app.py:210` POST /score, read by OBS "Score Text". A dead console leaves the LAST value in place (this is the desired fallback behavior, not a leak). | None — single-writer confirmed; do NOT add a second writer. The SC#1 test should assert the file still holds the last score after a /score followed by a simulated console "death" (no further write clears it). |
| Live service config | OBS scene collection (`obs/segugio-scene-collection.json`) carries `ndi_source_name: "PHONE-WIDE (NDI HX3)"` and `Score Text` `visible:false` per scene. This is COPIED into OBS's own profile on import — a repo edit does NOT auto-propagate to a running OBS box. | D-08: align the config example's `cam_wide` ndi_source to match the scene JSON / agility config. D-06: doc the simplified reveal. No JSON `visible` change needed (already `false`). |
| OS-registered state | None — no Task Scheduler / pm2 / systemd entries embed any renamed string in this phase. | None — verified by absence of any service-registration code touching overlay strings. |
| Secrets/env vars | None affected. The overlay path is fixed server-side; no env var names change. | None. |
| Build artifacts / installed packages | None — no package rename, no egg-info, no compiled artifact carries an overlay string. The renderer is a static `.js` served by Flask (no build step). | None. |

**The canonical rename question (D-08):** after every file is consistent, the only runtime risk is the OPERATOR's manual step — pointing each OBS `NDI Source` at the actual phone NDI name. The config/scene/doc must agree on ONE example name so the operator copies a consistent string (the "OBS sees it but console blank" gotcha). The fix is a config-example edit + a doc note; the live OBS box is re-pointed manually per the on-rig UAT.

## Common Pitfalls

### Pitfall 1: `DEAD_MS` hide keyed on gen-age (re-introducing 260615-tsi)
**What goes wrong:** The new dead-state hide fires during a normal idle-but-live run, blanking a working overlay.
**Why it happens:** `gen` only advances on `/run`/`/score` (no heartbeat); it is FLAT during a live run with no new score. A gen-age timer therefore "ages out" a live overlay.
**How to avoid:** Key `isDead()` on `everResponded && Date.now() - lastResponseAt > DEAD_MS`, identical structure to `isStale()`. The watchdog already stamps `lastResponseAt` on EVERY successful poll (`overlay-render.js:414-415`), so a live console answering polls is never dead.
**Warning signs:** A node fake-DOM test where a STATIC-gen, still-answering console goes dead after advancing the clock — that is the regression. The new gate must include the "live idle run is NOT dead" assertion (mirror `test_live_idle_run_not_stale_but_console_down_is_stale`).

### Pitfall 2: Poll-storm test using `test_client` (false green)
**What goes wrong:** The starvation test passes even on a single-worker non-threaded server because `test_client` short-circuits WSGI threading.
**Why it happens:** Flask's in-process test client does not spawn real concurrent workers.
**How to avoid:** Use `make_server("127.0.0.1", 0, app, threaded=True)` on a daemon thread (the `live_server` fixture). Fire concurrent real HTTP GETs via `urllib`/`ThreadPoolExecutor`.
**Warning signs:** No `make_server`/`threaded=True` in the new test → it is not proving starvation.

### Pitfall 3: Phantom timer jump on console restart
**What goes wrong:** After a LAN drop + console restart, the timer "jumps" to a wrong elapsed value.
**Why it happens (and why it does NOT here):** A naive timer that free-runs during the outage would jump. Segugio's timer STOPS on stale (`tick()` returns and nulls `rafId` when `isStale()`), and on the next successful poll `applyPayload` RE-MEASURES `skew` and recomputes `currentElapsed()` from the persisted `started_at`. The console restart re-seeds `gen`/`running`/`started_at` from `overlay_run.json` on disk (`ui/app.py:138-147`), so the resumed timer shows the TRUE elapsed — no jump. The client's `lastGen` resets to `-1` on a page reload, but the server `gen` persists and only advances, so `p.gen > lastGen` re-renders cleanly.
**How to avoid / assert:** SC#2 gate must drive the fake-DOM through: running → stale (fetch rejects) → resume (fetch ok again, possibly with a bumped gen + the SAME started_at) and assert `currentElapsed()` is continuous with the true wall-clock elapsed, NOT a jump equal to the outage duration.
**Warning signs:** A test that only checks "timer resumes" without comparing the resumed value to the true elapsed.

### Pitfall 4: NDI-source-name drift silently blanks a feed
**What goes wrong:** OBS lists the NDI source, but the camera shows blank because the configured `ndi_source` string does not byte-match the phone's published NDI name.
**Why it happens:** The example config, the scene JSON `ndi_source_name`, and the doc each carry an example name; if they disagree, the operator copies an inconsistent string. `config.example.yaml:27` (`"LOCALHOST (iPhone Camera for OBS Studio App)"`) disagrees with the scene JSON (`"PHONE-WIDE (NDI HX3)"`).
**How to avoid:** D-08 — pick ONE canonical example name (`"PHONE-WIDE (NDI HX3)"` to match the scene JSON + agility config) and make `config.example.yaml` consistent; add a doc note that the operator must byte-match the actual phone name.
**Warning signs:** Any divergence between `cameras[].ndi_source` in the example configs and `sources[].settings.ndi_source_name` in the scene JSON.

## Code Examples

### Two-stage degrade — where `DEAD_MS` hooks in (the existing watchdog)
```javascript
// Source: src/segugio/ui/static/overlay-render.js (verified this session)
// Existing constants (lines 229-230):
const PUBLISH_MS = 200;              // ~5 fps publish cadence
const STALE_MS = PUBLISH_MS * 3;     // dim+grayscale threshold (≈600ms) — KEEP
// ADD (D-05), next to the above:
// const DEAD_MS = 3000;             // full hide threshold (~3s) — exits the lower-third

// Existing watchdog (lines 295-297) — response-recency, the structure isDead() mirrors:
function isStale() {
  return everResponded && Date.now() - lastResponseAt > STALE_MS;
}
// ADD: function isDead() { return everResponded && Date.now() - lastResponseAt > DEAD_MS; }

// Existing degrade (lines 355-359) reuses .is-stale; the dead path reuses the EXIT animation:
function applyStale(stale) {
  if (!lowerThird) return;
  if (stale) lowerThird.classList.add("is-stale");
  else lowerThird.classList.remove("is-stale");
}
// The exit/hide primitive already exists (overlay.html: .is-exiting → @keyframes exit → opacity:0).
// On isDead(): remove is-live/is-stale, retrigger("is-exiting") so the plate slides out and stays hidden.
```

### Single-writer `overlay.txt` (the SC#1 coexistence proof — do NOT duplicate)
```python
# Source: src/segugio/ui/app.py:208-210 (verified this session) — the SOLE writer
write_score(_path(_SCORE_FILE), doc)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))  # last score persists on disk
# runtime.py declares _OVERLAY_FILE only for the channel bundle (comment lines 49-51); loop.py
# never writes it; set_overlay_text has zero callers — confirmed no double-writer.
```

### Jinja autoescape sinks (SC#4 server half)
```html
<!-- Source: src/segugio/ui/templates/overlay.html (verified this session) -->
<div id="identity" data-event="{{ event_name | default('', true) }}">{{ event_name | default('', true) }}</div>
{% if logo_path %}<img id="logo-bug" src="{{ logo_path }}" alt="">{% endif %}
<!-- Jinja autoescape is ON; a crafted event_name renders &lt;…&gt; not executable markup. -->
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| gen-age staleness (`lastGenAt`) | response-recency staleness (`everResponded`/`lastResponseAt`) | Phase 11 + 260615-tsi fix | A flat-gen live run is correctly NOT stale; `DEAD_MS` MUST follow this same keying |
| Single-stage degrade (dim only) | Two-stage: dim (`STALE_MS`) → hide (`DEAD_MS`) | Phase 14 (this phase) | A real death removes the frozen score from the browser source; the text fallback carries it |
| Phase-13 reveal = reveal Text + hide Overlay | Phase-14 reveal = reveal Text only (browser auto-hides on death) | Phase 14 (D-06) | One operator action; drop the redundant hide step from the docs |

**Deprecated/outdated:**
- The "hide Score Overlay" manual step in `docs/obs-setup.md` (lines 109-112) — redundant once `DEAD_MS` auto-hides. Drop per D-06.
- `config.example.yaml` `cam_wide` ndi_source `"LOCALHOST (iPhone Camera for OBS Studio App)"` — inconsistent placeholder; align to `"PHONE-WIDE (NDI HX3)"` per D-08.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DEAD_MS ≈ 3000ms` is a reasonable hide threshold (Claude's discretion per D-05). | Two-stage degrade | If too short, a long WiFi hiccup hides a recoverable overlay; if too long, a frozen score airs longer. Tunable; the on-rig UAT validates the feel. Low risk — it is an explicit discretion area. |
| A2 | The canonical D-08 example name should be `"PHONE-WIDE (NDI HX3)"` (matching the scene JSON + agility config), not `"LOCALHOST (iPhone Camera for OBS Studio App)"`. | NDI drift | If the team prefers the LOCALHOST iPhone-app name as canonical, the fix direction flips (edit the scene JSON instead). Low risk — either way the artifacts must AGREE; the planner/discuss can confirm direction. |

**Note:** A2 is a direction choice, not a correctness question — the requirement is internal consistency. All other findings are VERIFIED by direct codebase read.

## Open Questions

1. **Should the SC#1 `overlay.txt` gate also assert OBS-side airing, or only on-disk persistence?**
   - What we know: The headless gate can prove the file persists the last score after a /score then a simulated console death (no second writer clears it).
   - What's unclear: Real OBS "read from file" airing is a physical scenario.
   - Recommendation: Headless gate asserts on-disk persistence + single-writer; the real OBS airing is a `HUMAN-UAT.md` item (D-01/D-02). This matches the locked split.

2. **D-06 doc edit direction for the redundant "hide Score Overlay" step.**
   - What we know: `docs/obs-setup.md:111-112` currently instructs "toggle Score Overlay hidden" for a clean swap.
   - What's unclear: Whether to delete it outright or note it as auto-handled.
   - Recommendation: Delete the hide instruction; replace with "the browser overlay auto-hides on death (DEAD_MS) — reveal Score Text only." Keep the `visible:false`-while-alive note.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | The node fake-DOM gate tests (SC#1/SC#2/SC#4 JS half) | ✓ | v24.16.0 | Tests `@pytest.mark.skipif(node is None)` — skip cleanly if absent (existing convention in `test_ui_overlay_render.py`) |
| Flask 3.1.3 + werkzeug | The `/overlay-json` poll-storm harness (SC#3) | ✓ | installed | — |
| pytest | All gates | ✓ | repo standard | — |
| OBS Studio + DistroAV | Real on-rig UAT (HUMAN-UAT.md) | ✗ (dev box) | — | Deferred to on-rig field UAT (D-02) — does NOT block phase completion |

**Missing dependencies with no fallback:** None that block — the only missing piece (real OBS hardware) is an explicitly-deferred on-rig UAT carry-forward.
**Missing dependencies with fallback:** OBS hardware → `HUMAN-UAT.md` checklist authored now, executed on the rig later (D-02).

## Validation Architecture

> nyquist_validation is ENABLED (`.planning/config.json: workflow.nyquist_validation: true`). This section enumerates observable failure modes, observation points, and the minimum assertions so a regression cannot pass silently. Consumed downstream to generate VALIDATION.md.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + Node.js v24.16.0 (ES2020 fake-DOM execution via `subprocess`) |
| Config file | pytest configured at repo root (existing); node behavior tests gate on `shutil.which("node")` |
| Quick run command | `python -m pytest tests/test_overlay_degrade_gate.py tests/test_overlay_fallback_gate.py tests/test_overlay_poll_storm.py tests/test_overlay_html_sink_gate.py tests/test_imports.py -x` (final names at planner discretion) |
| Full suite command | `python -m pytest` |

### Phase Requirements / Success Criteria → Test Map
| Criterion | Observable Failure Mode | Observation Point | Test Type | Automated Command | File Exists? |
|-----------|-------------------------|-------------------|-----------|-------------------|-------------|
| SC#1 (console-down: timer freezes + degrades; overlay.txt keeps last score) | Timer keeps free-running past death (frozen "live"); OR browser keeps showing a frozen score on a real death; OR a second writer clears overlay.txt | (a) node fake-DOM: `isStale()`/`isDead()`, `.is-stale` class, lower-third hidden, `rafId === null`; (b) on-disk `overlay.txt` content after /score + simulated death | unit (node fake-DOM) + integration (Flask test_client write) | `pytest tests/test_overlay_degrade_gate.py tests/test_overlay_fallback_gate.py -x` | ❌ Wave 0 |
| SC#2 (LAN drop stops timer; restart re-anchors via gen, no phantom jump) | Timer airs a stale "live" during the drop; OR resumed timer jumps by the outage duration | node fake-DOM: drive running→fetch-reject→fetch-ok(same started_at, bumped gen); assert `currentElapsed()` continuous with true elapsed, NOT outage-sized jump; `is-stale`/hide applied during the drop then cleared | unit (node fake-DOM) | `pytest tests/test_overlay_degrade_gate.py::test_gen_reanchor_no_phantom_jump -x` | ❌ Wave 0 |
| SC#3 (`/overlay-json` poll storm never starves `/command`) | `POST /command` blocked > 1.0s while N concurrent `/overlay-json` GETs are in flight | real `make_server(threaded=True)` ephemeral-port server; time `POST /command` under 8 concurrent `/overlay-json` GETs | integration (live_server harness) | `pytest tests/test_overlay_poll_storm.py -x` | ❌ Wave 0 (copy `test_preview_concurrency.py`) |
| SC#4 (operator score values HTML-escaped at the sink) | A crafted score value executes as markup in the broadcast overlay; OR a heavy import sneaks into `segugio.ui` breaking crash-isolation | (a) `overlay-render.js` has no `innerHTML`/`.innerHTML`; values via `textContent`; (b) GET /overlay with a crafted `event_name` renders ESCAPED; (c) `test_imports.py` green | unit (JS source assert) + integration (Flask render) + import gate | `pytest tests/test_overlay_html_sink_gate.py tests/test_imports.py -x` | ❌ Wave 0 (sink test) / ✅ `test_imports.py` exists |
| RBT-07 (crash-isolation preserved across every segugio.ui edit) | A `segugio.ui` change pulls in torch/cv2/numpy/cyndilib/obsws | `test_imports.py` forces the heavy stack absent, builds create_app, serves /overlay-json + /overlay | import gate | `pytest tests/test_imports.py -x` | ✅ Exists — must stay green |
| D-08 (NDI-name consistency) | Example config disagrees with the scene JSON `ndi_source_name` (operator copies a mismatched string) | parse `config.example.yaml` cameras[].ndi_source vs `obs/segugio-scene-collection.json` ndi_source_name | integration (consistency assert, optional but recommended) | `pytest tests/test_scene_template.py -x` (extend) or a new small test | ⚠️ Partial — `test_scene_template.py` checks scene NAMES, not ndi_source_name vs config |

### Sampling Rate
- **Per task commit:** the relevant gate file(s) for the task + `test_imports.py` (crash-isolation must never regress).
- **Per wave merge:** full overlay gate set + `test_scene_template.py` + `test_ui_overlay_render.py` + `test_ui_freshness.py`.
- **Phase gate:** `python -m pytest` fully green before `/gsd-verify-work`; `HUMAN-UAT.md` authored and ready.

### Wave 0 Gaps
- [ ] `tests/test_overlay_degrade_gate.py` — SC#1 stale→dead two-stage + SC#2 gen re-anchor (node fake-DOM; reuse the `test_ui_overlay_render.py` harness verbatim).
- [ ] `tests/test_overlay_fallback_gate.py` — SC#1 `overlay.txt` on-disk persistence after /score + simulated death (single-writer proof; Flask test_client).
- [ ] `tests/test_overlay_poll_storm.py` — SC#3 `/overlay-json` storm vs `/command < 1.0s` (copy the `live_server` fixture + `_get`/`_post_command` from `test_preview_concurrency.py`).
- [ ] `tests/test_overlay_html_sink_gate.py` — SC#4 textContent sink + Jinja autoescape regression.
- [ ] (optional) ndi_source ↔ scene `ndi_source_name` consistency assertion (D-08) — extend `test_scene_template.py`.
- [ ] No framework install needed — pytest + node already present.

## Security Domain

> `security_enforcement` is ABSENT in config → treated as ENABLED. SC#4 is itself a security criterion (HTML-injection at the broadcast sink).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | LAN trust boundary is the documented v1 posture (no auth; T-05-05-04 accepted) — unchanged by this phase |
| V3 Session Management | no | Stateless poll/render; no sessions |
| V4 Access Control | no | Single-operator field tool on a dedicated LAN; path-traversal already mitigated (fixed server-side filenames) |
| V5 Input Validation / Output Encoding | **yes** | **The core SC#4 concern.** Output encoding at the HTML sink: `textContent` for operator score values (never `innerHTML`), Jinja autoescape for `event_name`/`logo`. Input is also length-bounded + control-char-stripped by `_clean`/`cleanField`. |
| V6 Cryptography | no | No crypto introduced |

### Known Threat Patterns for this stack (Flask console + OBS/CEF browser source)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator-entered score value injected as markup into the broadcast overlay (XSS in CEF) | Tampering / Elevation | `textContent` sink (never `innerHTML`); `cleanField`/`_clean` drops control chars + caps length; SC#4 gate asserts both `innerHTML` absence and Jinja-escaped branding (T-11-03-01 / T-11-02-01) |
| Crafted `event_name`/`logo_path` static branding injected via the host page | Tampering | Jinja autoescape ON at `#identity[data-event]`, identity text, and `<img src>` |
| `/overlay-json` poll storm denies the safety-critical `/command` override | Denial of Service | `threaded=True` / waitress so a GET flood cannot starve the lone WSGI worker (UXT-02); SC#3 gate proves `< 1.0s` |
| Heavy import sneaking into `segugio.ui` (breaks crash-isolation; a director crash could reach the console) | Elevation / DoS | `test_imports.py` (RBT-07) forces the heavy stack absent and asserts the console builds + serves; re-asserted as an SC#4 sub-criterion |
| `overlay.txt` half-write / blank read during a swap | Tampering (broadcast integrity) | `atomic_write_text` (temp + fsync + `os.replace` with MoveFileEx retry) — already in place; single-writer keeps the last score intact on death |

## Sources

### Primary (HIGH confidence) — direct codebase read this session
- `src/segugio/ui/static/overlay-render.js` — full read: `PUBLISH_MS`/`STALE_MS`, `everResponded`/`lastResponseAt`, `isStale()`, `.is-stale` toggle, `tick()`/`startTimer()`/`stopTimer()`, poll loop, `createRenderer` API surface — the exact `DEAD_MS` hook points.
- `src/segugio/ui/app.py` — POST /score sole `overlay.txt` writer (line 210), `_seed`/gen re-anchor on restart (lines 138-147), `/overlay-json` boundary-safe payload, `/command`, `/overlay` Jinja render, `threaded=True`/waitress entrypoint.
- `src/segugio/ui/templates/overlay.html` — `.is-stale` CSS (line 201), `@keyframes exit`/`.is-exiting` (lines 181-184/196), `event_name`/`logo` Jinja-autoescaped sinks (lines 244/255).
- `src/segugio/ui/score_render.py` — `_clean` sanitizer + `render_overlay_text` (the unchanged `overlay.txt` renderer).
- `src/segugio/orchestrator/runtime.py` (lines 17/49-56/82) + `loop.py` — confirmed the orchestrator declares but never writes `overlay.txt`; `set_overlay_text` has zero callers (double-writer RESOLVED: no risk).
- `tests/test_preview_concurrency.py` — the UXT-02 `live_server` harness (copy for SC#3).
- `tests/test_ui_overlay_render.py` — the node fake-DOM harness + `test_no_innerhtml_sink` + `test_live_idle_run_not_stale_but_console_down_is_stale` (the SC#1/SC#2/SC#4 model).
- `tests/test_imports.py` — RBT-07 crash-isolation gate (heavy stack + numpy/cv2 forced absent; /overlay-json + /overlay served under the block).
- `tests/test_scene_template.py` — scene/text-fallback lockstep; `Score Text visible:false`.
- `tests/conftest.py` (lines 422-479) — `file_channel`/`preview_channel` fixtures (overlay + overlay_run keys).
- `config.example.yaml` (line 27) vs `config.agility.example.yaml` (line 24) vs `obs/segugio-scene-collection.json` (lines 123-126) — the D-08 NDI-name drift, located.
- `docs/obs-setup.md` (lines 42-44, 103-135) — the coexistence policy + NDI-name example to update (D-06/D-08).

### Secondary (MEDIUM confidence)
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` — phase scope, RBT-06/RBT-07/OVD-03 contracts, Out-of-Scope table (no WebSocket/MJPEG/SSE, no scoring, no overlay.txt removal).
- Project memory (`overlay-bugs-sandbox-repro`, `phase8-live-multiview-on-rig`, `gsd-execute-phase-env-gotchas`) — the sandbox-repro method, the ndi_source exact-match gotcha, and the gsd-tools-not-on-PATH / STATE-hand-edit caution.

### Tertiary (LOW confidence)
- None — no WebSearch was required; this phase introduces no external dependency and every claim is codebase-verified.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing libs verified present (Flask 3.1.3, node v24.16.0).
- Architecture / hook points: HIGH — `DEAD_MS` hook, single-writer `overlay.txt`, gen re-anchor, and all four sinks read directly from source this session.
- Pitfalls: HIGH — each pitfall traces to a specific verified code location or an existing regression test.
- Double-writer (Q1) + NDI drift (Q5): HIGH — both resolved by direct grep + read.

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (stable; the overlay renderer and console are frozen by Phase 12 unification — re-verify only if `overlay-render.js`, `ui/app.py`, or the scene collection change before planning).
