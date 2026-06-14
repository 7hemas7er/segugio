# Phase 11: Shared Graphical Renderer, /overlay Page & Branding - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

A single shared HTML/CSS/JS renderer served at `GET /overlay` — a **transparent, broadcast-quality per-discipline lower-third** with a **self-counting, clock-skew-safe run timer** that degrades on stale data, animates only on events, and carries **configurable branding**. Everything is **client-side**: zero director compute, **no new Python runtime dependency**, the crash-isolated console still imports only `Flask + segugio.opcomm`. This is the core deliverable of milestone v1.2, built on Phase 10's `/overlay-json` data contract.

**In scope (Phase 11):**
- `GET /overlay` route + `ui/templates/overlay.html` + `ui/static/overlay-render.js` (new shared renderer).
- Transparent, FOUC-free, title-safe per-discipline lower-third (OVL-01/02/03) rendering operator-typed values **verbatim + sanitized + HTML-escaped** (`textContent`, never `innerHTML`).
- Self-counting client timer with offset-cancellation (TMR-01/02/03/04).
- gen-age freshness watchdog → stop timer + degrade on stale (OVD-03 client half; reuse `isStale()`).
- Sober event-only animations: enter on run start, exit on run stop, pulse on score-value change (OVL-04).
- Config logo + CSS-variable theme + persistent identity line (BRD-01/02), folded into the existing `overlay.*` config section.
- Crash-isolation import test stays green (RBT-07).

**Out of scope (deferred to later v1.2 phases / future):**
- Console preview iframe reuse / mirror retirement → **Phase 12** (SCV-02).
- OBS scene-collection wiring + setup docs → **Phase 13** (SCN-01/02).
- End-to-end live degrade / poll-storm / injection acceptance → **Phase 14** (RBT-06).
- Agility under/over-SCT color bar → **OVL-FUT-01** (explicitly deferred; see D-08).
- Any change to the director, `runstate.json`, the opcomm records, or the score data-model (HARD invariant — never).
</domain>

<decisions>
## Implementation Decisions

### Lower-third look (OVL-02/03)
- **D-01:** **Left accent-bar plate.** A colored vertical accent bar + a compact semi-opaque dark plate anchored **bottom-left** in the title-safe band (~18% frame height, the rest of the frame kept clear for the dog). Two-row layout: **label row over value row**. The theme color lives in the accent bar. (Rejected: centered bottom band; minimal chip cluster — chips also risk the CEF border-radius-over-transparency gray-edge artifact flagged in research.)
- **D-02:** **Timer leads, big.** A large timer block sits right after the accent bar; the score-field cells sit to its right at normal size. The clock is the visual hero across all three disciplines (T&F race, freestyle routine, agility Tempo). For **agility, Tempo IS this big timer**, with SCT and Faults as the score cells beside it.

### Timer presentation (TMR-02/03)
- **D-03:** **Discipline-appropriate number format.** Countdown disciplines (T&F, freestyle) render `M:SS` whole seconds (e.g. `0:47`). Agility renders **`SS.hh` seconds-with-hundredths** for both Tempo and SCT (e.g. `34.57` vs `38.00`) to match official agility timing precision. (Note for planner: hundredths means the agility timer text updates many times/sec — drive it with `requestAnimationFrame`, update `textContent` in place, never rebuild the DOM node.)
- **D-04:** **Single pulse → static "Tempo"** at end of a countdown. When a T&F/freestyle countdown reaches 0, the timer does ONE brief pulse (reusing the same sober pulse vocabulary as the score-change animation, D-06), then **freezes showing "Tempo"** (TMR-03). End-of-round is a genuine event, so one pulse is consistent with OVL-04's "animate only on events" — no perpetual motion.

### Agility overtime (SCR-04 hard line)
- **D-05:** **Plain keep-counting past SCT.** When agility Tempo passes the operator-typed SCT, it keeps incrementing in the same style; SCT sits beside it as a **static reference number**. **No color shift, no interpretation** — the two numbers speak for themselves. This is the cleanest SCR-04 stance (the overlay shows, never judges). The colored under/over-time bar stays deferred to **OVL-FUT-01** (it "needs careful framing to stay display-only").

### Branding & identity (BRD-01/02)
- **D-06:** **Default theme reuses the console palette.** Dark plate `#14161a`, text `#E6E9EF`, accent bar in the established console green `#34D399` — one coherent Segugio product identity across the operator console and the broadcast overlay. The theme is **CSS-variable driven** (e.g. `--accent`, `--plate`, `--text`) so an org overrides colors per event in config (BRD-01). The score-state palette (greens/amber/blue) carries over for any state cues.
- **D-07:** **Logo = bottom-right corner bug.** A small, optional, configurable logo "bug" in the **bottom-right** title-safe corner — the classic TV channel-logo placement — separate from the bottom-left score plate, keeping the plate clean. Present whenever the overlay is shown; **never over the action area**. Sourced from a config logo path (BRD-01); absent path → no bug rendered.
- **D-08:** **Identity line = competitor + event.** A persistent secondary line attached to the plate shows `{competitor} · {event}` (e.g. `Rex & Anna · Disc Dog Italia 2026`). **Competitor** comes from the verbatim **`nome`** field — already present in the freestyle field set; the operator can optionally type `nome` for T&F/agility too, and it flows through the free `ScoreDoc.fields` dict with **zero data-model change** (BRD-02). **Event** comes from a NEW config field (e.g. `overlay.event_name`). If no name is present, the line shows just the event; it hides gracefully.

### New `overlay.*` config fields (planner — grow the existing `OverlayParams` sub-model in `config/models.py`)
- The Phase-10 `OverlayParams` (`freestyle_duration_s: int = 120`) is the home for Phase-11 branding config (D-05 of Phase 10 anticipated this). Add: **logo path** (D-07), **theme color variables / theme block** (D-06), **event name** (D-08). All additive, `extra="forbid"`, defaults so a config without these still validates under the fail-fast `SystemExit(2)` loader. These are **static config**, injected into `/overlay` at render time via an **entrypoint arg like `cam_ids`** (D-07 of Phase 10) — NEVER `import segugio.config` in the crash-isolated module, and NOT in the `/overlay-json` poll payload.

### Claude's Discretion
- Exact plate dimensions, scrim/plate opacity, font sizes, accent-bar width, internal padding — within "title-safe lower band, legible over bright outdoor grass, sober."
- Enter/exit animation direction & duration (slide-from-left vs fade-up) and the exact pulse style (scale bump vs background flash) — within OVL-04's "sober, events-only, compositor-only `transform`/`opacity` props, no layout/paint thrash."
- Font choice: a self-hosted `.woff2` bundled as a Flask static asset (with `font-display: block` + `document.fonts.ready` reveal gate to kill FOUC) **vs** a system font stack. No CDN (no internet on the field LAN). Must match what Phase 12's console preview will iframe.
- Exact CSS-variable names and whether the theme is flat vars or a small theme block.
- The DOM/poll structure of `overlay-render.js` (one shared render function; gen-gated re-render `p.gen > lastGen`; cold-start guard `lastGen < 0` is NOT stale).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements, roadmap & milestone shape
- `.planning/REQUIREMENTS.md` — OVL-01/02/03/04, TMR-01/02/03/04, BRD-01/02 (the ten Phase-11 requirements), the **Out of Scope** table (over-animation, action-area coverage, director compute, WS/MJPEG/SSE, free-form HTML, leaderboard — all HARD-rejected), and **OVL-FUT-01** (the deferred agility under/over bar, see D-05).
- `.planning/ROADMAP.md` §"Phase 11" — the goal + 5 success criteria this phase is graded against; the v1.2 build-order rationale (data → renderer → SCV → OBS → robustness).

### Research (milestone v1.2) — patterns are direct, no research-phase flagged
- `.planning/research/v1.2/SUMMARY.md` — publish-and-render decision, the **offset-cancellation timer formula** (`skew = server_now − Date.now()/1000`), transport = fetch-polling, the Phase-11 deliverables list, and the "Gaps to Address" (timer-at-zero + over-SCT, now resolved here in D-04/D-05).
- `.planning/research/v1.2/PITFALLS.md` — the seven critical pitfalls; for Phase 11 especially **P1 clock skew**, **P4 stale-as-live**, **P5 transparency/white-flash**, plus the performance traps (animate on events only; poll at publish cadence; rAF off the gen-age watchdog) and the HTML-injection security note (`textContent` not `innerHTML`).
- `.planning/research/v1.2/ARCHITECTURE.md` — contract/route architecture, the renderer component breakdown, and the `?t=<gen>` nonce + `Cache-Control: no-store` fetch discipline.

### Code this phase extends / mirrors
- `src/segugio/ui/app.py` — the crash-isolated console; where `GET /overlay` lands. **Study:** the import allowlist (Flask + `segugio.opcomm` only, Flask imported inside `create_app`), the existing `GET /overlay-json` route (the data source: `discipline`, `fields` verbatim, `running`, `started_at`, `server_now`, `gen` + `no-store`), and the `create_app(channel_dir, cam_ids=())` **entrypoint-arg pattern** — the model for injecting `freestyle_duration_s` + logo/theme/event config WITHOUT importing config.
- `src/segugio/ui/templates/console.html` — **reuse**: `isStale()` (line ~738: `lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS`), `STALE_MS = PUBLISH_MS * 3` (~600ms), `freshnessStamp()`, the gen-gated poll loop, and the inlined-CSS single-self-contained-HTML convention (FOUC-free). Also the `gsd:scv01-mirror` block — its `cleanField`/`scvGet`/`mirrorOverlayText` per-discipline layout + `sct`/`SCT` alias is the exact behavior the new renderer must reproduce (and which Phase 12 will retire in favor of this renderer).
- `src/segugio/ui/score_render.py` — `render_overlay_text` + `_get` alias resolution + `_clean` (`_MAX_FIELD_LEN = 64`, control-char strip, keep `U+0020`). Survives unchanged as the `overlay.txt` fallback (RBT-06). Its per-discipline layout is the reference the JS renderer mirrors (D-08 of Phase 10).
- `src/segugio/config/models.py` — `class OverlayParams` (line ~174): the additive `extra="forbid"` sub-model to grow with the logo/theme/event fields; `Config.overlay` wiring; the fail-fast `SystemExit(2)` loader convention.
- `src/segugio/opcomm/records.py` / `channel.py` — `ScoreDoc`/`Discipline` and the never-raise read boundary feeding `/overlay-json` (read-only here; **not modified** — no data-model change, D-08/BRD-02).

### Crash-isolation gate (RBT-07 — re-asserted as a Phase-11 success criterion)
- `docs/security.md` — the LAN-trust-boundary threat model.
- The `test_app_imports_nothing_heavy`-style import test (forces `torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws` absent AND proves the console starts) — must stay green; extend it to cover the new `/overlay` route.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `console.html::isStale()` / `STALE_MS` / `freshnessStamp()` / gen-gated poll loop — copy verbatim into the overlay for the OVD-03 freshness watchdog + degrade (the proven UXT-03 discipline; cold-start guard `lastGen < 0` is NOT stale).
- `console.html` inlined-critical-CSS, single self-contained HTML — the FOUC-free / no-white-flash pattern to follow (Pitfall 5).
- `console.html::mirrorOverlayText` + `cleanField` + `scvGet` — the per-discipline layout + `sct`/`SCT` alias + sanitize logic the renderer reproduces (and centralizes; Phase 12 deletes the console copy).
- `app.py` `create_app(..., cam_ids=())` entrypoint-arg pattern — the precedent for injecting `freestyle_duration_s` + logo/theme/event without a config import.
- `OverlayParams` (config/models.py) — extend in place; `freestyle_duration_s` already lives here.

### Established Patterns
- **Crash-isolation allowlist** — `import segugio.ui` is Flask-free (Flask imported inside `create_app`); the new route/template/static must add **no** module-top heavy import (Pitfall 3). All timer/animation/branding logic is client-side JS/CSS.
- **`?t=<gen>` nonce + `Cache-Control: no-store`** — the load-bearing CEF cache-bust on every `/overlay-json` fetch (Pitfall 2); `no-store` alone is not sufficient in CEF.
- **Display-only verbatim (SCR-04)** — operator-typed values shown unmodified; the renderer never sums/judges/derives. HTML sink demands `textContent` (or Jinja autoescape), NOT the plain-text `_clean` alone (security note).
- **Offset-cancellation timer (Pitfall 1)** — `skew = server_now − Date.now()/1000` per poll; render `elapsed = (Date.now()/1000 + skew) − started_at`; free-run between polls; freeze on `running === false` and on stale. NEVER raw `Date.now() − started_at` across machines.

### Integration Points
- New `GET /overlay` route in `app.py` — `render_template("overlay.html", ...)` with the static config (freestyle duration, logo path, theme vars, event name) passed as render args resolved by the entrypoint (like `cam_ids`).
- New `ui/static/` dir (does not exist yet) for `overlay-render.js` and any self-hosted font.
- Data source = the existing `GET /overlay-json` (Phase 10) — no route change needed there; the renderer is a pure consumer.
- `config/models.py` `OverlayParams` + the `__main__` entrypoint in `app.py` — resolve the new static config (env vars / config load, lazily, inside the entrypoint).
</code_context>

<specifics>
## Specific Ideas

- Reference look chosen: **classic sports-broadcast left lower-third** — colored accent bar + dark plate, bottom-left, with a **big leading clock**. Concrete mock the user approved:
  ```
  Rex & Anna · Disc Dog Italia 2026
  ██  0:47   PRESE  ZONA  TOTALE              [LOGO]
  ██         12     3      27
  plate bottom-left                      bug bottom-right
  ```
- Agility renders to **hundredths** (`34.57`) — the only discipline that does; the planner must size the timer field for the wider `SS.hh` string and update it via rAF.
- The single end-of-countdown pulse reuses the **same** pulse vocabulary as the score-change pulse — one animation primitive, two triggers.
- Theme default is the console's own dark palette (`#14161a` / `#34D399`) so console preview (Phase 12 iframe) and OBS overlay look identical out of the box.
</specifics>

<deferred>
## Deferred Ideas

- **Agility under/over-SCT color bar (OVL-FUT-01)** — considered (the "subtle over-time color" option) and **explicitly NOT taken for v1**; D-05 keeps plain keep-counting. It must be framed carefully to stay display-only (SCR-04) before it ships.
- **SCV-01 unification / console preview iframe of `/overlay`** — Phase 12 (SCV-02). This renderer is built to be the single shared one, but the repointing + mirror retirement is out of Phase 11 scope.
- **OBS scene-collection wiring, browser-source settings, setup docs** — Phase 13 (SCN-01/02).
- **End-to-end degrade / poll-storm / HTML-injection acceptance under failure** — Phase 14 (RBT-06). Phase 11 builds the client-side degrade; Phase 14 validates the assembled live path.
- **Font decision (self-hosted woff2 vs system stack)** — left to the planner/implementer (Claude's discretion), but must be settled so Phase 12's console-preview iframe renders identically (Pitfall 6).

*Discussion otherwise stayed within phase scope.*
</deferred>

---

*Phase: 11-shared-graphical-renderer-overlay-page-branding*
*Context gathered: 2026-06-14*
