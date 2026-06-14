---
phase: 11-shared-graphical-renderer-overlay-page-branding
plan: 02
subsystem: ui-overlay
tags: [overlay, template, transparency, lower-third, branding, css-var, title-safe]
requires:
  - "GET /overlay route + render_template(overlay.html, **overlay_cfg) + no-store (Phase 11 / 11-01)"
  - "overlay_cfg render args: event_name/logo_path/theme_accent/theme_plate/theme_text/freestyle_duration_s (11-01)"
provides:
  - "src/segugio/ui/templates/overlay.html — transparent FOUC-free host page + DOM/CSS contract for 11-03"
  - "DOM contract ids: #lower-third / #identity / #timer / #cells / #logo-bug"
  - "CSS-var theme names: --accent / --plate / --text (Jinja-injected, console defaults)"
  - "Event-only animation keyframes: enter / exit / pulse (transform/opacity only, no loops)"
  - "window.OVERLAY_CFG.freestyleDurationS bootstrap (no run data baked in)"
  - "tests/test_ui_overlay_page.py — served-HTML contract test (12 assertions)"
affects:
  - "11-03 (overlay-render.js fills #timer/#cells/#identity via textContent, toggles enter/exit/pulse/is-stale classes)"
  - "Phase 12 (console-preview iframe renders this same page — system-font choice must match)"
tech-stack:
  added: []
  patterns:
    - "Single self-contained <!DOCTYPE html> with all critical CSS inlined (mirrors console.html, P5 FOUC-free)"
    - "Transparency contract first in the inlined style: html,body transparent + .lower-third opacity:0 start-hidden"
    - "CSS-var theme injected via Jinja `default(x, true)` filter so an empty var still falls back to the console palette"
    - "Conditional {% if logo_path %} block — absent path → no #logo-bug element in the DOM"
    - "Invariant-grep robustness: avoid the literal words `banner`/`infinite` even in comments so naive substring asserts stay clean"
key-files:
  created:
    - "src/segugio/ui/templates/overlay.html"
    - "tests/test_ui_overlay_page.py"
  modified: []
decisions:
  - "Font = SYSTEM STACK (system-ui, -apple-system, sans-serif), matching console.html — NO self-hosted woff2, so NO font-load FOUC and NO document.fonts.ready reveal gate is needed (a system font is present on first paint). Phase 12's console-preview iframe renders the same page, so the look matches by construction."
  - "DOM contract ids finalized as #lower-third / #identity / #timer / #cells / #logo-bug (#accent-bar / #plate / #score-row are structural, not renderer-filled)"
  - "Plate scrim via color-mix(in srgb, var(--plate) 86%, transparent) + text-shadow legibility backing (Claude discretion on opacity)"
  - "Animation state classes the renderer toggles: .is-entering / .is-live / .is-exiting / .pulse-once / .is-stale (the stale class is the OVD-03 client-degrade hook for 11-03)"
metrics:
  duration: 3min
  completed: "2026-06-14"
  tasks: 2
  files: 2
---

# Phase 11 Plan 02: Transparent /overlay Host Page & DOM Contract Summary

The front-half of the overlay page: a single self-contained, FOUC-free `overlay.html` that composits as pure alpha over live video, ships a title-safe left-accent-bar lower-third skeleton with a config-driven CSS-var theme and a conditional bottom-right logo bug, defines the events-only `enter`/`exit`/`pulse` animation vocabulary, and exposes the stable `#timer`/`#cells`/`#identity`/`#logo-bug` DOM contract that the 11-03 renderer fills via `textContent`.

## What Was Built

**Task 1 — overlay.html transparent FOUC-free lower-third skeleton, commit `9a2c737`**
- Single `<!DOCTYPE html>` document with ALL critical CSS inlined in `<head><style>` (mirrors console.html — never an external stylesheet that loads a frame late, Pitfall 5).
- Transparency contract first: `html, body { background: transparent !important; margin: 0; padding: 0; }` and `.lower-third { opacity: 0; }` (start hidden — a delayed/partial first paint shows NOTHING, never a white box over bright grass or a dark dog).
- CSS-var theme on `.lower-third`: `--accent`/`--plate`/`--text` injected via Jinja `{{ theme_* | default('<console-color>', true) }}` so an absent/empty var still falls back to the console palette (`#34D399`/`#14161a`/`#E6E9EF`).
- Title-safe lower-third (D-01/D-02/OVL-03): `position: fixed; left: 4.5vw; bottom: 6vh; max-width: 60vw; max-height: 18vh` — a left `#accent-bar` (`background: var(--accent)`) + a semi-opaque `#plate` (`color-mix` scrim over `var(--plate)` + `text-shadow` legibility backing). The band is capped at 18vh and the plate never rises past ~20vh — the action area stays clear.
- Plate contents: an `#identity` line (`{competitor} · {event}`; the event half pre-seeded by Jinja, the competitor half added client-side), a `#score-row` with a BIG leading `#timer` (`tabular-nums`, `min-width: 4.5ch` to hold `SS.hh`/`M:SS`) and a `#cells` per-discipline container the renderer rebuilds (`.cell` = label-over-value, two-row, D-01).
- Conditional logo bug (D-07): `{% if logo_path %}<img id="logo-bug" src="{{ logo_path }}" alt="">{% endif %}` — bottom-right title-safe corner; an empty/absent path renders NO element at all.
- Event-only animations (OVL-04): `@keyframes enter` (slide-from-left + fade), `@keyframes exit`, and ONE reused `@keyframes pulse` (score-change AND end-of-countdown, D-04) — every keyframe touches only `transform`/`opacity` (compositor-only); state classes `.is-entering`/`.is-live`/`.is-exiting`/`.pulse-once` each run once, plus an `.is-stale` degrade hook. No looping animation anywhere.
- `<script src="/static/overlay-render.js">` bootstrap (the 11-03 renderer) + a thin inline `window.OVERLAY_CFG = { freestyleDurationS: {{ freestyle_duration_s }} }` — config NUMBERS only, NO score/run/timer data baked in (the page polls `/overlay-json` and never reloads on a score change).

**Task 2 — served-HTML contract test (tdd), commit `27c7b04`**
- `tests/test_ui_overlay_page.py`: 12 assertions building `create_app(tmp, cam_ids=[...], overlay_cfg={...})` with a FULLY non-default branding config and GETting `/overlay`.
- Pins: transparency (`html, body { background: transparent`) + `opacity: 0;` start-hidden; the CSS-var theme reflects the INJECTED custom colors (`#FF00AA`/`#102030`/`#FAFAFA`, and the `#34D399` default does NOT leak); the DOM contract ids; the event in the identity line; the logo bug present-with-path / absent-without-path (D-07); the `/static/overlay-render.js` script src; `Cache-Control: no-store`; title-safe (band-cap present, no `top: 0`/`width: 100vw`/`banner`); events-only keyframes with no `infinite`; no `.innerHTML` config sink; and `event_name` autoescaped (`<script>` → `&lt;script&gt;`).
- TDD: the test was written and run against the Task-1 template; the title-safe assertion went RED on a stray `banner` word in a template comment, which was reworded (see Deviations), then GREEN.

## Renderer Interface Contract (READ — 11-03 and Phase 12 depend on this)

**DOM ids the renderer fills (via `textContent`, never `innerHTML`):**
| Selector | Role | Renderer behavior (11-03) |
|----------|------|---------------------------|
| `#lower-third` | host element; carries the theme vars + animation state classes | toggle `.is-entering`/`.is-live`/`.is-exiting`/`.pulse-once`/`.is-stale` on events |
| `#identity` | `{competitor} · {event}` line; event half pre-seeded by Jinja (`data-event` attr also holds it) | prepend the verbatim `nome` + `·` separator via `textContent`; hide gracefully when empty |
| `#timer` | the big leading clock | `textContent` in place via rAF — `M:SS` (countdown) / `SS.hh` (agility); never node-rebuild |
| `#cells` | per-discipline score-cell container | rebuild `.cell` children (`.cell-label` over `.cell-value`) per discipline |
| `#logo-bug` | bottom-right config logo (present only when `logo_path` set) | static — no renderer action |

**CSS vars:** `--accent` / `--plate` / `--text` (on `.lower-third`).
**Animation classes:** `.is-entering` (enter), `.is-exiting` (exit), `.pulse-once` (the single pulse primitive — score change AND end-of-countdown), `.is-live` (steady shown), `.is-stale` (OVD-03 degrade).
**Bootstrap:** `window.OVERLAY_CFG.freestyleDurationS` (countdown length; no run data).
**Structural (not renderer-filled):** `#accent-bar`, `#plate`, `#score-row`.

## Decisions Made

- **Font = system stack** (`system-ui, -apple-system, sans-serif`), same as console.html. No self-hosted `.woff2`, therefore no font-load FOUC and no `document.fonts.ready` reveal gate — a system font paints on the first frame. Phase 12's console-preview iframe renders this exact page, so the look matches without extra work.
- DOM contract ids finalized (above); `#accent-bar`/`#plate`/`#score-row` kept structural.
- Plate scrim = `color-mix(in srgb, var(--plate) 86%, transparent)` + `text-shadow` legibility backing (Claude discretion on the 86% opacity).

## Verification

- Task 1 verify command — `GET /overlay` returns 200; served HTML contains `background: transparent`, `--accent`, `static/overlay-render.js` — OK.
- `python -m pytest tests/test_ui_overlay_page.py -q` — 12 passed.
- `python -m pytest tests/ -k "ui or import or overlay or config" -q` — all passed (1 pre-existing skip). The 11-01 gated `/overlay` 200+no-store assertion in `test_imports.py` auto-activated now that the template exists, and stays green.
- Manual invariant checks: logo bug present with `logo_path` / absent when empty; no `infinite`; `max-height: 18vh` present; `event_name` autoescaped (`<script>` → `&lt;script&gt;`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded template comments to keep invariant greps robust**
- **Found during:** Task 2 (RED on the title-safe assertion)
- **Issue:** The Task-1 template carried the literal words `banner` and `infinite` inside explanatory comments stating those layouts/animations are NOT present. The acceptance criteria and the natural served-HTML test assert these words are absent from the page; a naive substring check trips on the comment even though the actual CSS has no banner class and no looping animation.
- **Fix:** Reworded the two comments (`top-anchored banner` → `top-anchored strip`; `no \`infinite\`` → `zero looped keyframes` / `every animation runs once — no loops`). No CSS/DOM behavior changed — purely comment wording so the invariant holds under a substring grep.
- **Files modified:** `src/segugio/ui/templates/overlay.html`
- **Commit:** `27c7b04` (folded into the Task-2 commit alongside the test)

## Authentication Gates

None.

## Known Stubs

None. The `#cells` container ships empty by design (the renderer rebuilds its children per discipline — this is the documented interface contract, not a stub) and the `#timer` shows a `--` placeholder until the first poll (filled by 11-03). No hardcoded data flows to a rendered surface.

## TDD Gate Compliance

Task 2 is `tdd="true"`. The test was written against the Task-1 template and exercised RED → GREEN: the title-safe assertion went RED on a stray comment word, the template comment was reworded, then GREEN. Per the repo convention for additive template/test work (mirroring 11-01), the test + the one-line template comment fix land in a single `test(...)` commit. No behavior-adding production source was written in Task 2 itself (Task 1 already shipped the template under a `feat(...)` commit), so the RED/GREEN feat-gate is satisfied by the Task-1 `feat` + Task-2 `test` pair.

## New Symbols Introduced (created-here, not drift)

- Template file: `src/segugio/ui/templates/overlay.html`
- CSS vars: `--accent`, `--plate`, `--text`
- DOM ids: `#lower-third`, `#identity`, `#timer`, `#cells`, `#logo-bug` (+ structural `#accent-bar`, `#plate`, `#score-row`)
- CSS keyframes: `enter`, `exit`, `pulse`
- Animation state classes: `.is-entering`, `.is-live`, `.is-exiting`, `.pulse-once`, `.is-stale`
- JS global: `window.OVERLAY_CFG` (`freestyleDurationS`)
- Test file: `tests/test_ui_overlay_page.py`

## Self-Check: PASSED

Both created files and this SUMMARY exist on disk; both task commits (`9a2c737`, `27c7b04`) are in the git log.
