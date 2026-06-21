# Phase 14: Fallback Coexistence & Degrade Hardening - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate the whole assembled live overlay path under failure — the **live-robustness gate** before field acceptance (RBT-06 acceptance). Prove the broadcast never goes scoreless, never shows a stale timer/score as live, and the safety-critical `/command` override is never starved. This is a **validation + hardening** phase: most underlying behavior already shipped (freshness/degrade, `textContent` sink, `overlay.txt` fallback, gen re-anchor, the UXT-02 concurrency pattern). The phase makes RBT-06 an explicit, self-contained gate and hardens any gaps found within the overlay-robustness domain.

**In scope:** the four success criteria — (1) console-down freezes timer + degrades while `overlay.txt` keeps airing; (2) LAN-drop stops the timer, restart re-anchors via `gen` with no phantom jump; (3) `/overlay-json` poll storm never starves `POST /command`; (4) operator score values HTML-escaped at the sink + crash-isolation stays green — plus the two-stage degrade hardening and the flagged NDI-source-name docs/config fix.

**Out of scope:** any NEW overlay feature (already shipped or deferred); WebSocket/MJPEG/SSE transport (rejected); automatic scoring/adjudication (SCR-04); auto-revealing the text fallback (architecturally impossible — a dead/crash-isolated console can't drive OBS); out-of-domain subsystems (YOLO/tracking/NDI-decode) — documented, not fixed here.
</domain>

<decisions>
## Implementation Decisions

### Acceptance & Validation
- **D-01:** RBT-06 passes via **BOTH** mediums. **Headless automation = the completion bar**: everything simulable gets a test — renderer stale/degrade (node fake-DOM), gen re-anchor (no phantom jump), `/overlay-json` poll-storm (extend the UXT-02 harness), HTML-escape sink. **On-rig `HUMAN-UAT.md` checklist** covers the genuinely physical scenarios: real OBS browser-source blanking/auto-hide, real LAN-cable drop, real `overlay.txt` airing the last score.
- **D-02:** The on-rig checklist does **NOT block** phase completion — it's a deferred hardware/field UAT carry-forward (same disposition as Phases 5/7). Phase 14 closes when the automation gate is green AND `HUMAN-UAT.md` is written and ready to run on the rig.
- **D-03:** Add **explicit, named gate regression tests for EACH success criterion** (console-stops-responding → timer stops + degrade; fetch-reject → degrade; gen-resume → no phantom jump) **even where the logic already exists and passes**. RBT-06 must be a self-contained named gate, not "trust the existing freshness tests." Reuse the alt-port-sandbox + node-fake-DOM method.

### Degrade behavior (dead-console look)
- **D-04:** **Two-stage degrade.** SHORT stale (≈600ms, existing `STALE_MS = 3×PUBLISH_MS`) keeps the current dim+grayscale (`opacity:0.55; filter:grayscale(0.4)`) — absorbs transient WiFi hiccups without flicker. A NEW longer "dead" threshold fully exits/hides the lower-third so **NO frozen score airs from the browser source** on a real death. (The timer already stops in all stale cases.)
- **D-05:** The dead→hide threshold is a **JS constant `DEAD_MS ≈ 3000ms`** added next to `STALE_MS`/`PUBLISH_MS` in `overlay-render.js` — mirrors how the existing freshness timing already lives as client constants; no new config/entrypoint surface. The hide must build on the **response-recency** watchdog (`everResponded`/`lastResponseAt`), not gen-age (per the 260615-tsi fix).

### Fallback coexistence / switchover
- **D-06:** **Simplified manual reveal.** Because the browser overlay now auto-hides on death (D-04), the operator's only manual step is **revealing the `Score Text` source**. `Score Text` stays `visible:false` while the console is alive (avoids a double-score). Update `docs/obs-setup.md` to the one-action procedure and **drop Phase-13's now-redundant "manually hide Score Overlay" step**. The on-rig UAT walks the operator through it.

### Remediation scope
- **D-07:** **Fix inline, domain-bounded.** Gaps WITHIN the overlay-robustness domain (degrade, gen re-anchor, concurrency, HTML-escape, fallback coexistence) get fixed in this phase. A gap OUTSIDE that domain (YOLO/tracking/NDI-decode) gets documented + deferred, not fixed here.
- **D-08:** **Fold in** the Phase-13-flagged NDI-source-name docs/config drift as a small operator-facing consistency fix (relates to the recurring exact-`ndi_source`-name-match gotcha — "OBS sees it but console blank").

### Carried forward (LOCKED — do not re-litigate)
- Console stays crash-isolated — imports only `Flask + segugio.opcomm`, director never touched (**RBT-07**, re-asserted as a success criterion of this phase).
- Transport = fetch-polling `/overlay-json` (WebSocket/MJPEG/SSE rejected — UXT-02 starvation).
- `overlay.txt` fallback = **manual-toggle** text source. The **console writes `overlay.txt` on every `POST /score`** via `atomic_write_text(_path("overlay.txt"), render_overlay_text(doc))` (`ui/app.py:210`) → the last score persists as a static file on disk, so OBS "read from file" keeps airing it when the console dies. This is the SC#1 coexistence proof.
- Score values sink via `textContent`, never `innerHTML` (Phase 11/12); `event_name`/`logo` are Jinja-autoescaped — SC#4 is a regression assertion, not new logic.

### Claude's Discretion
- Exact `DEAD_MS` tuning around ~3s; exact new test file names/structure; how the poll-storm test mirrors UXT-02's `< 1.0s` `/command` bar.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 14: Fallback Coexistence & Degrade Hardening" — goal + the 4 success criteria
- `.planning/REQUIREMENTS.md` — **RBT-06** (`overlay.txt` fallback acceptance), **RBT-07** (crash-isolation gate), **OVD-03** (freshness/degrade), and the **Out of Scope** table (no WebSocket/MJPEG/SSE; no scoring/adjudication; no removing `overlay.txt`)

### Overlay-robustness implementation (the code under test/hardening)
- `src/segugio/ui/static/overlay-render.js` — freshness watchdog (`everResponded`/`lastResponseAt` response-recency keying), `STALE_MS`/`PUBLISH_MS`, offset-cancellation timer, per-request `?t` nonce, `gen` re-anchor, `.is-stale` degrade, `textContent` sink — **where the new two-stage `DEAD_MS` hide lands (D-04/D-05)**
- `src/segugio/ui/templates/overlay.html` — `.is-stale` CSS (`opacity:0.55; grayscale(0.4)`, line ~201), enter/exit `@keyframes`, `event_name`/`logo` Jinja-autoescape sink, `body.preview` rules
- `src/segugio/ui/app.py` — `GET /overlay`, `GET /overlay-json` (boundary-safe), `POST /command` (safety-critical override), `POST /score` (writes `overlay.txt`, line ~210)
- `src/segugio/ui/score_render.py` — `render_overlay_text` (the `overlay.txt` fallback renderer; `_clean` sanitizer — the HTML-escape reference)

### Tests to extend / model after
- `tests/test_preview_concurrency.py` — the **UXT-02 harness** (real threaded `werkzeug` server on ephemeral port; concurrent GETs vs a timed `POST /command < 1.0s`) → **extend to an `/overlay-json` poll storm** (SC#3)
- `tests/test_ui_freshness.py` — existing gen-age staleness/degrade JS assertions
- `tests/test_ui_overlay_render.py` — node-executed renderer behavior (skew≈0, freeze-at-0, agility overtime, no-`innerHTML`)
- `tests/test_imports.py` — the RBT-07 crash-isolation gate (heavy stack absent)
- `tests/test_scene_template.py` — OBS scene-collection lockstep (browser source + text fallback in lockstep)

### OBS / operator docs (to update)
- `obs/segugio-scene-collection.json` — `Score Overlay` `browser_source` + `Score Text` fallback (`visible:false`), per-scene wiring
- `docs/obs-setup.md` — browser-primary / text-fallback coexistence policy → **update to the simplified manual-reveal procedure (D-06)**; also the NDI-source-name note (D-08)
- `docs/security.md` — LAN trust boundary / HTML-sink threat posture (re-affirm for SC#4)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_preview_concurrency.py` `live_server` fixture (`make_server("127.0.0.1", 0, app, threaded=True)` on a daemon thread) — directly reusable for the `/overlay-json` poll-storm test; copy the `_get`/`_post_command` pattern.
- `overlay-render.js` freshness watchdog (`isStale()` + `everResponded`/`lastResponseAt`) — the two-stage `DEAD_MS` hide extends this exact structure (one more threshold + the exit/hide call).
- `score_render.render_overlay_text` + `_clean` — the `overlay.txt` fallback renderer (stays unchanged) and the canonical sanitizer the HTML-escape assertion references.

### Established Patterns
- **Crash-isolation import gate** (`tests/test_imports.py`, RBT-07): every `segugio.ui` change must re-assert the console starts with `torch`/`cv2`/`ultralytics`/`numpy`/`cyndilib`/`obsws` absent.
- **Sandbox-repro for `/overlay` behavior** (project memory `overlay-bugs-sandbox-repro`): reproduce live-behavior bugs in an **alt-port sandbox + node fake-DOM** before shipping a fix; **never POST to the live `:8080` console**.
- **Freshness/degrade keyed on console RESPONSE recency**, not gen-age (the 260615-tsi fix) — `DEAD_MS` must build on response-recency so an idle live run doesn't false-hide.
- `gsd-tools` is sometimes **not on PATH** in this env (memory `gsd-execute-phase-env-gotchas`) — STATE/ROADMAP may need hand-edit + careful sign-off (don't pre-mark phase `[x]` before verify).

### Integration Points
- `overlay-render.js` `DEAD_MS` hide → reuse the existing exit-animation / `.is-stale` path (no new animation primitive).
- New poll-storm test → `segugio.ui.app.create_app` + the `/overlay-json` route.
- `overlay.txt` coexistence → `ui/app.py` `POST /score` writer. **Research item:** `orchestrator/runtime.py` also references `render_overlay_text`/`overlay.txt` — confirm there's no double-writer that would change the dead-console fallback behavior.
</code_context>

<specifics>
## Specific Ideas

- "**A frozen run is never shown as live**" (OVD-03) is the hard line; the two-stage degrade strengthens it — dim on a hiccup, hide on a death.
- **Broadcast cleanliness over completeness:** better to show NO score (browser hidden + operator reveals text) than a stale-looking "live" score.
- The phase is a **gate**, not a feature build — its primary artifact is named, self-contained robustness tests + a HUMAN-UAT checklist, with hardening fixes only where validation exposes a real gap.
</specifics>

<deferred>
## Deferred Ideas

- **On-rig HUMAN-UAT execution** on real OBS hardware — carry-forward (like Phases 5/7 field UAT); the checklist is authored in Phase 14, executed on the rig later.
- **OBS source-visibility hotkey for `Score Text`** — considered for the switchover; not adopted (simplified manual reveal chosen). Note for a future ops-polish pass if operators want a one-keypress fallback.
- **OVL-FUT-01** visual agility-vs-SCT under/over-time treatment — already deferred in `REQUIREMENTS.md` Future Requirements.
- Any **out-of-overlay-domain gap** surfaced during validation (YOLO/tracking/NDI-decode) — documented in the verification report, fixed in its own phase/quick-task, not here (per D-07).
</deferred>

---

*Phase: 14-fallback-coexistence-degrade-hardening*
*Context gathered: 2026-06-20*
