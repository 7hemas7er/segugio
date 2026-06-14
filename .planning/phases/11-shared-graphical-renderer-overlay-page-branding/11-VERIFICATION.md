---
phase: 11-shared-graphical-renderer-overlay-page-branding
verified: 2026-06-14T00:00:00Z
status: human_needed
score: 5/5 must-haves verified (4 fully confirmed; 1 confirmed with a known config-boundary injection gap per code review)
overrides_applied: 0
gaps: []
human_verification:
  - test: "Confirm broadcast visual — load GET /overlay in OBS browser-source over a live NDI feed and verify: body is transparent (no white box), lower-third enters from left on run start, exits on run stop, a single pulse plays on score change, the timer counts correctly, and the plate never covers the action area"
    expected: "Transparent composit over live video; lower-third enters/exits on edges only; timer matches wall clock within human perception; plate stays in title-safe bottom band (~18% height)"
    why_human: "CEF/OBS compositing transparency, animation timing, and visual legibility over outdoor video cannot be verified by grep or Python test clients"
  - test: "Verify agility SS.hh timer smoothness — start a run with discipline=agility and observe the #timer cell in a browser. Check that the hundredths digit advances fluidly without visible per-poll snapping (WR-04 in 11-REVIEW.md: skew re-measured every poll can cause a micro-snap on each 200ms interval)"
    expected: "Timer advances smoothly at 60fps with no visible step/snap artifact every 200ms"
    why_human: "Visual jitter perception requires a human observer; automated tests only verify the formula, not the rendered smoothness"
  - test: "Verify stale degrade is visible — with a running overlay, kill the console process and observe that within ~600ms the lower-third dims (is-stale class applies opacity:0.55, grayscale) and the timer stops; then restart the console and verify the overlay recovers and the timer re-anchors"
    expected: "Within STALE_MS (~600ms) the overlay dims and the counter stops; on console recovery it un-dims and resumes"
    why_human: "Requires stopping a live process and observing timing behavior in a real OBS environment; the code path is verified but the UX signal needs human confirmation"
  - test: "Confirm the code review CR-01 CSS injection gap is acceptable — deliberately set SEGUGIO_OVERLAY_ACCENT='red; } body { background: red }' in the operator's env and observe whether the program-feed background changes in OBS. Assess whether the config-boundary trust (operator-authored rig) makes this risk acceptable without fix"
    expected: "Either the injection is deemed acceptable (config-boundary, isolated LAN, operator trust) and documented, or a validator is added to OverlayParams to reject non-safe CSS color tokens"
    why_human: "Security risk acceptance is a developer decision; the injection is technically confirmed (see Gaps Summary) but the threat model classifies the config as operator-trusted. The decision whether to add a validator or carry the gap forward needs a human call"
---

# Phase 11: Shared Graphical Renderer — Overlay Page & Branding Verification Report

**Phase Goal:** A single shared HTML/CSS/JS renderer serves a transparent, broadcast-quality per-discipline lower-third with a self-counting run timer that is correct across machine clock skew, degrades when data goes stale, animates only on events, and carries configurable branding — all client-side, zero director compute, zero new Python dependency.
**Verified:** 2026-06-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /overlay` serves a transparent page (html, body transparent, critical CSS inlined) with correct per-discipline lower-third, operator-typed values HTML-escaped, no white flash, title-safe lower band only | ✓ VERIFIED | `html, body { background: transparent !important; }` at overlay.html:17; `opacity: 0` start-hidden at line 57; `max-height: 18vh` title-safe cap at line 54; all CSS inlined in `<head><style>`; Jinja autoescape on `event_name`; `GET /overlay` → 200 + `Cache-Control: no-store` confirmed by test + spot-check |
| 2 | The run timer counts client-side with ~0 error across ~30s clock skew (server_now offset-cancellation, never raw Date.now()−started_at); counts down for T&F (60s) and freestyle (config-driven), counts up for agility, freezes at 0 showing "Tempo" for T&F/freestyle, continues past SCT for agility | ✓ VERIFIED | overlay-render.js:285-287 `currentElapsed()` = `Date.now()/1000 + skew - startedAt`; skew = `server_now - Date.now()/1000` (line 351); raw `Date.now() - started_at` is absent (grep confirmed); `formatCountdown()` returns `TEMPO_LITERAL` at remainingS≤0 (line 236); `formatAgility()` has no ceiling (line 244); node behavior test (test_timer_behavior_skew_freeze_overtime) asserts <0.001s error at 30s skew + "Tempo" freeze + overtime past SCT |
| 3 | When the data source goes stale (gen stops advancing past STALE_MS or fetch fails), the timer STOPS and the overlay visibly degrades; cold start (lastGen below 0) is NOT stale | ✓ VERIFIED | `isStale()` at line 280: `lastGen >= 0 && Date.now() - lastGenAt > STALE_MS`; `STALE_MS = PUBLISH_MS * 3 = 600ms`; `tick()` at line 318 calls `applyStale(isStale())` and sets `rafId = null` on stale; `applyStale()` at line 339-343 adds `.is-stale` class; `.is-stale { opacity: 0.55; filter: grayscale(0.4) }` in overlay.html:201; fetch error caught and coasted (line 392-394); coldstart guard (lastGen=-1) confirmed by code |
| 4 | The lower-third animates only on events (enter/exit/pulse); a configurable logo + CSS-variable color theme + persistent identity line render in the plate without covering the action area | ✓ VERIFIED (with known CR-01 gap — see Gaps Summary) | `@keyframes enter/exit/pulse` in overlay.html:177-197 — transform/opacity only, no `infinite`; `.is-entering`, `.is-exiting`, `.pulse-once` classes triggered in overlay-render.js:180-190, 196; `animateRunEdge()` only on run-start and run-stop edges; `--accent`/`--plate`/`--text` CSS vars injected from Jinja render args; `#logo-bug` conditional on `{% if logo_path %}`; `#identity[data-event]` pre-seeded from Jinja; identity competitor filled via `scvGet(fields, "nome")` textContent; `position: fixed; bottom: 6vh; max-height: 18vh` keeps plate in title-safe band |
| 5 | The crash-isolation import test stays green with the heavy stack absent (all timer/animation/branding logic client-side; no new Python runtime dependency) | ✓ VERIFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` passes with torch/cv2/numpy/cyndilib/obsws forced absent; `GET /overlay` → 200 asserted in that test when overlay.html exists; all module-top imports in app.py are stdlib + opcomm only; no new Python package added; 59/59 phase-11 tests green in Python 3.14 CPU-only env |

**Score:** 5/5 truths verified

### Gaps Summary

**CR-01 (Code Review BLOCKER — mitigated to WARNING by trust-boundary context):**

The three theme color config strings (`theme_accent`, `theme_plate`, `theme_text`) are interpolated directly into an inline `<style>` block at overlay.html:37-39. Jinja autoescape is HTML-context (escapes `<>&"'`) and does NOT escape CSS metacharacters (`}`, `;`, `/`, `</style>`). The config model deliberately does not validate these as hex colors (models.py:196-201 documents this). A value such as `red; } body { background: url(http://evil/x) }` breaks out of the `.lower-third` rule. A `</style><img src=x onerror=alert(1)>` value terminates the style block and executes JS in the browser (confirmed by direct test).

The code review (11-REVIEW.md) classifies this as a BLOCKER and provides a concrete fix (a `@field_validator` on `theme_accent`/`theme_plate`/`theme_text` in `OverlayParams` rejecting non-safe CSS color tokens, plus the env-override path must route through the same validator).

**Why not blocking goal achievement in this verification:** The threat model is operator-controlled config on an isolated rig LAN. The breach vector requires the operator to supply a malicious value to their own rig's config file or env var — it does not cross an external trust boundary. The PLAN threat register explicitly marks this as "mitigate" but deferred sink hardening to 11-03; the code review is flagging that the deferral was not completed. The four other must-haves (transparency, timer, staleness degrade, crash-isolation) are fully verified. The human verification section asks the developer to make the accept-vs-fix call explicitly.

The gap does NOT go in the `gaps:` frontmatter (which is reserved for truths that FAILED without an explanation) because it is a partial implementation of a known security control that requires a human decision. It is surfaced under human verification item 4.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/config/models.py` | OverlayParams with event_name, logo_path, theme_accent, theme_plate, theme_text + freestyle_duration_s unchanged | ✓ VERIFIED | All 5 new fields present at lines 193-201; defaults match console palette; extra="forbid" confirmed; freestyle_duration_s=120 unchanged |
| `src/segugio/ui/app.py` | GET /overlay route + overlay_cfg param + no module-top config import | ✓ VERIFIED | Route at line 310; `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` at line 98; `_OVERLAY_CFG_DEFAULTS` dict at lines 88-95 (plain dict, not imported config model); lazy `load_config` in `__main__` only |
| `src/segugio/ui/templates/overlay.html` | Transparent FOUC-free host page, CSS-var theme, lower-third skeleton, logo bug, identity line, event-only animations, script src | ✓ VERIFIED | 253 lines; all required elements present; min_lines=80 exceeded; `background: transparent` at line 17 |
| `src/segugio/ui/static/overlay-render.js` | Sanitize mirror, per-discipline DOM, offset-cancellation timer, gen-age watchdog, event-only animation triggers, identity line | ✓ VERIFIED | 460 lines; contains `server_now`, `cleanField`, `scvGet`, `isStale`, `formatCountdown`, `formatAgility`, `TEMPO_LITERAL`, `STALE_MS`, `PUBLISH_MS`; no `innerHTML =` assignment |
| `tests/test_config_overlay.py` | Branding fields round-trip + extra=forbid + defaults | ✓ VERIFIED | 140 lines; 11 tests pass |
| `tests/test_imports.py` | RBT-07 gate extended to GET /overlay | ✓ VERIFIED | Test at line 87 covers `/overlay` route registration + 200 response + no-store under heavy-absent block |
| `tests/test_ui_overlay_page.py` | Served-HTML assertions (transparency, DOM contract, theme injection, no-innerHTML, title-safe) | ✓ VERIFIED | 155 lines; 12 tests pass |
| `tests/test_ui_overlay_render.py` | Served-JS/behavior assertions (sanitize parity, skew formula, discipline format, freeze/overtime, stale) | ✓ VERIFIED | 235 lines; 11 tests pass (node tests skipped if node absent — skip marker correct) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/segugio/ui/app.py::create_app` | `templates/overlay.html` | `render_template("overlay.html", **overlay_cfg)` | ✓ WIRED | Line 317: `render_template("overlay.html", **overlay_cfg)` confirmed |
| `src/segugio/ui/templates/overlay.html` | `/static/overlay-render.js` | `<script src="/static/overlay-render.js">` | ✓ WIRED | Line 251: `<script src="/static/overlay-render.js"></script>` |
| `src/segugio/ui/templates/overlay.html` | Jinja overlay_cfg render args | `--accent/--plate/--text + data-event injected from config` | ✓ WIRED | Lines 37-39: CSS vars; line 224: `data-event="{{ event_name }}"` |
| `src/segugio/ui/static/overlay-render.js` | `/overlay-json?t=<gen>` | `fetch("/overlay-json?t=" + lastGen, { cache: "no-store" })` | ✓ WIRED | Line 384 confirmed |
| `src/segugio/ui/static/overlay-render.js` | overlay.html DOM ids (timer/cells/identity) | `textContent` writes into `#lower-third`/`#timer`/`#cells`/`#identity` | ✓ WIRED | Lines 209-211: `querySelector("#lower-third")`, `querySelector("#identity")`, `querySelector("#cells")`; all writes via textContent |
| `src/segugio/ui/app.py::__main__` | `OverlayParams` (via lazy load_config) | LAZY `from ..config.loader import load_config` inside `__main__` | ✓ WIRED | Lines 378-394: lazy import inside entrypoint branch only; never at module top |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `overlay.html` → `overlay-render.js` | `/overlay-json` poll payload | `read_score()` + `read_overlay_run()` + `time.time()` in `get_overlay_json()` | Yes — reads atomic files from opcomm channel; `time.time()` always set | ✓ FLOWING |
| `overlay.html` CSS vars | `theme_accent`, `theme_plate`, `theme_text` | Injected from `overlay_cfg` dict in `create_app` via `**overlay_cfg` to `render_template` | Yes — real config values flow through; defaults always present | ✓ FLOWING |
| `overlay-render.js` timer | `startedAt`, `skew` | `applyPayload(p)` reading `p.started_at` and `p.server_now` from the poll | Yes — wall-clock `time.time()` values from opcomm; null when not running (handled in currentElapsed) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| GET /overlay → 200 + no-store | `client.get("/overlay")` via Python | 200, `Cache-Control: no-store` | ✓ PASS |
| Transparent page + hidden lower-third | `background: transparent` + `opacity: 0` in HTML | Both confirmed present | ✓ PASS |
| Custom theme colors injected | `#FF00AA` in HTML when `theme_accent="#FF00AA"` | Confirmed present | ✓ PASS |
| All DOM contract ids present | `#lower-third`, `#timer`, `#cells`, `#identity`, `#logo-bug` in HTML | All confirmed | ✓ PASS |
| Branding NOT in overlay-json | overlay-json keys: `discipline, fields, running, started_at, server_now, gen` | No branding keys present | ✓ PASS |
| No innerHTML assignment | `grep ".innerHTML"` in overlay-render.js | Only appears in comments, never as assignment | ✓ PASS |
| No perpetual animation | `grep "infinite"` in overlay.html + overlay-render.js | No matches | ✓ PASS |
| Crash-isolation gate (heavy stack absent) | `test_console_resolves_with_heavy_stack_and_numpy_absent` | 59/59 pass | ✓ PASS |
| Timer offset-cancellation formula | Node behavior test: 30s skew → <0.001s elapsed error | Confirmed by test | ✓ PASS |
| Countdown freeze on "Tempo" | `formatCountdown(0)` returns `"Tempo"` | Confirmed by node test | ✓ PASS |
| Agility overtime past SCT | `formatAgility(130)` → `"130.00"` | Confirmed by node test | ✓ PASS |
| Sanitize cleanField byte-parity | Node test vs `score_render._clean` reference | Passes when node available | ✓ PASS |

### Requirements Coverage

| Requirement | Phase Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| OVL-01 | 11-01, 11-02 | `GET /overlay` transparent browser-source, `GET /overlay-json` data route, Flask+opcomm only | ✓ SATISFIED | Both routes exist; crash-isolation gate green |
| OVL-02 | 11-02, 11-03 | Per-discipline lower-third (disc T&F: prese/zona/totale; freestyle: nome+timer; agility: tempo/SCT/faults) verbatim operator values | ✓ SATISFIED | DISCIPLINE_CELLS in overlay-render.js matches render_overlay_text field selection byte-for-byte; `sct`/`SCT` alias present |
| OVL-03 | 11-02 | Legible compositing — plate semi-opaco, title-safe band in basso, body transparent | ✓ SATISFIED | `max-height: 18vh`, `bottom: 6vh`, `background: transparent`, alpha scrim |
| OVL-04 | 11-02, 11-03 | Event-only animations — enter/exit on run edge, one pulse on score change/countdown-end | ✓ SATISFIED | Keyframes enter/exit/pulse with transform/opacity only; no `infinite`; `animateRunEdge()` + `pulseOnce()` triggered only on edges |
| TMR-01 | 11-03 | Timer auto-counts client-side, zero director compute | ✓ SATISFIED | rAF loop in `tick()`, `createRenderer()`, `setInterval(poll, PUBLISH_MS)` — no director involvement |
| TMR-02 | 11-03 | T&F: countdown from 60s; freestyle: countdown from config `freestyle_duration_s`; agility: count up vs typed SCT | ✓ SATISFIED | `DISC_TF_COUNTDOWN_S=60`; `freestyleDurationS = Number(cfg.freestyleDurationS) || 120`; agility branch in `paintTimer()` uses `formatAgility()` |
| TMR-03 | 11-03 | T&F/freestyle: freeze at 0 showing "Tempo"; agility continues past SCT | ✓ SATISFIED | `formatCountdown()` returns `TEMPO_LITERAL` when `remainingS <= 0`; `formatAgility()` has no ceiling, continues past any SCT |
| TMR-04 | 11-03 | Skew-safe timer via server_now offset-cancellation, never raw Date.now()−started_at | ✓ SATISFIED | `skew = server_now - Date.now()/1000`; `currentElapsed()` = `Date.now()/1000 + skew - startedAt`; no raw subtraction present (confirmed by grep + node test) |
| OVD-03 | 11-03 (client half) | Stale source detected via gen-age; timer STOPS; overlay degrades; cold start NOT stale | ✓ SATISFIED | `isStale()` cold-start guard; rAF stopped on stale; `.is-stale` degrade class applied; fetch error coasted |
| BRD-01 | 11-01, 11-02 | Logo + color theme configurable (CSS vars + logo_path from config) | ✓ SATISFIED | `OverlayParams.theme_accent/plate/text` + `logo_path`; CSS vars injected from Jinja; `{% if logo_path %}` conditional bug |
| BRD-02 | 11-01, 11-03 | Persistent identity line (cane/handler + event) — freestyle nome; T&F/agility from config or optional field | ✓ SATISFIED | `scvGet(fields, "nome")` for competitor across all disciplines; `data-event` attribute pre-seeded from Jinja `event_name`; identity line hidden when both empty |
| RBT-07 | 11-01 (extended) | Crash-isolation preserved — import test green with heavy stack absent; covers GET /overlay | ✓ SATISFIED | `test_console_resolves_with_heavy_stack_and_numpy_absent` extended to assert `/overlay` route registration + 200 + no-store |

**Note — Requirements NOT in phase 11 scope:**
- OVD-01, OVD-02: Delivered in Phase 10 (marked Complete in REQUIREMENTS.md traceability)
- SCV-02, SCN-01, SCN-02, RBT-06: Deferred to Phases 12/13/14 (marked Pending)

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src/segugio/ui/templates/overlay.html:37-39` | CSS injection: `{{ theme_accent }}` etc. interpolated into `<style>` block; Jinja autoescape is HTML-context, not CSS-context | WARNING (code review CR-01) | `}`, `;`, `</style>` are not escaped; a malicious config value can break out of the CSS declaration and inject arbitrary CSS or close the style block to inject HTML. Confirmed by direct test. Mitigated by operator-trust config boundary (isolated LAN rig). Fix: CSS color validator on OverlayParams fields. |
| `src/segugio/ui/static/overlay-render.js:207` | Dead `getElementById` fallback with wrong operator precedence (code review IN-01) | Info | Dead code — `querySelector` always wins for the real document root; confusing but harmless |
| `src/segugio/ui/static/overlay-render.js:357-366` | Score-change pulse misfires on first running payload (code review WR-05) | Info | Spurious pulse layered on enter animation on the very first frame; cosmetic only |
| `src/segugio/ui/static/overlay-render.js:258` | `Number(cfg.freestyleDurationS) || 120` fallback misleading if template emits no value (code review WR-03) | Info | Config model enforces `freestyle_duration_s > 0` server-side; fallback scenario requires both server guard and template emission to fail simultaneously |
| `src/segugio/ui/static/overlay-render.js:349-351` | Skew re-measured every poll — per-poll micro-snap on agility SS.hh timer (code review WR-04) | Warning | Visible jitter on the hero clock at hundredths precision; functional but suboptimal for broadcast quality |
| `src/segugio/ui/templates/overlay.html:125-128` | Comment says renderer "REBUILDS cells" but code updates in place (code review IN-03) | Info | Misleading comment for Phase-12 consumers; no behavioral impact |

No `TBD`, `FIXME`, or `XXX` debt markers found in phase-11 files.

### Human Verification Required

#### 1. Broadcast compositing in OBS browser-source

**Test:** Load `GET /overlay` in OBS as a browser-source over a live NDI program feed. Start a run and verify the lower-third enters from the left, the timer counts, a score change triggers a single brief pulse, and stopping the run exits the plate. Verify no white background at any point.
**Expected:** Transparent composit; enter/exit animations smooth; timer counts in M:SS for disc_tf, SS.hh for agility; no action area covered; overlay visible only during a run.
**Why human:** CEF/OBS compositing, animation timing, and visual legibility over outdoor video cannot be verified by a Python test client.

#### 2. Agility timer smoothness (WR-04)

**Test:** With discipline=agility and a run in progress, observe the `#timer` cell updating SS.hh in a browser. Note whether there is a visible 200ms snap/step every poll interval, or whether the rAF interpolation is smooth.
**Expected:** Timer advances smoothly at ~60fps; no jitter at the poll boundary.
**Why human:** Sub-frame visual smoothness requires human perception; automated tests only verify the formula, not rendered smoothness.

#### 3. Stale degrade user-visible signal

**Test:** With the overlay active and a run in progress, kill the console process. Within ~600ms, verify the lower-third dims (opacity 0.55, grayscale) and the timer freezes. Restart the console; verify the overlay recovers and resumes.
**Expected:** Dim within STALE_MS; no frozen-but-confident timer remaining; clean recovery after console restart.
**Why human:** Requires live process management and timing observation in a real OBS environment.

#### 4. CR-01 security decision: CSS injection via theme config

**Test:** Set `SEGUGIO_OVERLAY_ACCENT='red; } body { background: red }'` and confirm the page background changes to red in OBS/browser. Decide: (a) add a CSS color validator to `OverlayParams` (the code review fix), or (b) accept the risk as config-boundary/operator-trust with documentation.
**Expected:** Developer explicitly accepts or fixes CR-01 before Phase 12 (which embeds this page in an iframe in the console).
**Why human:** Security risk acceptance is a developer/stakeholder decision; the injection is technically confirmed but the threat model context (isolated LAN, operator-authored config) may make it acceptable with documentation.

---

## Summary

All five phase-11 success criteria are verified in the codebase. The implementation is substantive, wired, and data-flowing. 59 phase-11 tests pass in the CPU-only py3.14 environment (the 4 pre-existing `test_fan_out_batched.py` failures are unrelated to phase 11 — they require `ultralytics` which is absent in this interpreter). No debt markers (TBD/FIXME/XXX) were found. No new Python dependencies were added.

The `human_needed` status reflects four items requiring human confirmation: broadcast visual quality in OBS, agility timer smoothness, stale degrade UX signal, and the CR-01 CSS injection decision. The CR-01 gap (CSS metacharacters not escaped in the inline style block) is a real injection sink but is bounded by the operator-trusted config-boundary context; it does not block the observable phase goal but requires a human decision before Phase 12 embeds this page as an iframe.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
