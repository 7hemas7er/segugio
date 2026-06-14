---
phase: 09-explainability-informed-override-tablet-ux
plan: 02
subsystem: ui
tags: [flask, jinja, html, css, vanilla-js, svg, tablet, ipad, touch, accessibility]

# Dependency graph
requires:
  - phase: 09-explainability-informed-override-tablet-ux (09-01)
    provides: "GET /preview exposes the cuts ring + pure POST /score/preview render route"
  - phase: 08-console-serving-live-multiview
    provides: "console.html multiview grid + /preview + /status routes, WR-01 server-rendered cam whitelist"
provides:
  - "Tablet-first landscape two-region console: Multiview-LEFT + sidebar-RIGHT (D-01), single-column reflow below 1024px"
  - "iPad/Safari touch contract: viewport-fit=cover, touch-action manipulation, safe-area bottom cluster, >=44/48px tap targets, no-zoom-blocking-attrs"
  - "Status palette + typography migration: LIVE #34D399 / FORZATA #F0B429 / MORTO #FF6B6B / auto-wants #56B4E9 on #14161a; 4 sizes, weights 400+700 only; #b23b3b retired"
  - "5 grayscale-safe tile states (D-04) via setTileState dispatcher: live/forzata/auto-wants/dead/stale, 3 redundant channels (hue+border-style+label)"
  - "Tap-to-force gesture (MVW-04): whole tile is the force control on standard click; blind Forza buttons removed; large always-visible Rilascia (auto) undo (D-03)"
  - "Per-tile dog-lock bbox SVG scaffold (WHY-03): unit viewBox + xMidYMid meet + object-fit:contain = zero JS letterbox math; updateBbox hides on null/stale/dead"
  - "Five sidebar scaffold containers (#reason/#leaderboard/#auto-wants/#switch-history + score form) for 09-03/09-04"
affects: [09-03, 09-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Zero-JS-letterbox bbox: SVG viewBox=\"0 0 1 1\" preserveAspectRatio=xMidYMid meet over an <img> object-fit:contain — the SVG engine's meet-scaling IS the alignment"
    - "5-state tile dispatcher (setTileState) extends the existing classList.toggle mechanism, not a new framework"
    - "3-redundant-channel grayscale-safe status encoding (hue + border-style + text label) for CVD/WCAG 1.4.1"

key-files:
  created:
    - "tests/test_ui_tablet_layout.py"
  modified:
    - "src/segugio/ui/templates/console.html"
    - "tests/test_ui_score.py"

key-decisions:
  - "FORZATA vs LIVE are categorically distinct (amber+lock+ribbon vs green solid + dot), never the same treatment"
  - "Bind force/undo to the standard click event only; synthetic touch-event click handlers intentionally NOT used (double-fire on iOS, T-09-02-03)"
  - "object-fit:contain on the tile <img> is load-bearing — it is what makes the bbox SVG meet-scaling align with zero JS math"
  - "Sidebar's four why-blocks are empty scaffold containers here; 09-03/09-04 fill them"

patterns-established:
  - "Tablet two-region grid (1fr / 340px) with @media max-width:1024px single-column reflow, grid first"
  - "Bottom-trailing thumb-arc cluster with env(safe-area-inset-*) padding for one-handed reach"

requirements-completed: [UXT-01, MVW-04, WHY-03]

# Metrics
duration: 12min
completed: 2026-06-14
---

# Phase 9 Plan 02: Tablet-First Console Restyle + 5-State Tiles + Tap-to-Force + Bbox SVG Summary

**The console.html foundation restyled tablet-first into a landscape Multiview-LEFT + sidebar-RIGHT layout with the iPad/Safari touch contract, a migrated grayscale-safe status palette, 5-state tiles, whole-tile tap-to-force replacing the blind buttons, and a zero-JS-math dog-lock bbox SVG per tile.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2
- **Files modified:** 2 (+1 created)

## Accomplishments
- Landscape two-region layout (D-01) with single-column reflow below tablet width; live cam + reason stay visible.
- Full UXT-01 touch contract: `viewport-fit=cover` (no zoom-blocking attrs), `touch-action: manipulation`, safe-area-padded bottom cluster, >=44/48px targets, `:active` on every tap target, `user-select`/`tap-highlight` removed on tiles+buttons (not on score inputs).
- Palette migrated to the contrast-verified status hues on `#14161a`; typography reduced to 4 sizes / weights 400+700 only (legend 600->700, no 500/600 anywhere); `#b23b3b` retired for status.
- 5 grayscale-safe tile states (D-04) via `setTileState`, driven from `/status` (live_cam+reason+alive) and `/preview` (auto_candidate) — FORZATA (override) and LIVE (auto) are unmistakably distinct.
- Tap-to-force (MVW-04): the whole tile POSTs `/command {force_cam}` on a standard `click`; blind `.force-btn` text buttons + their handler removed; `#rilascia` enlarged to >=48px as the always-visible undo (D-03). `/command` route + `OperatorCommand` untouched.
- Per-tile inline bbox SVG (WHY-03) with `vector-effect="non-scaling-stroke"`; `updateBbox` sets the rect from normalized `[cx,cy,w,h]`, hides on null box, and the overlay is CSS-hidden on stale/dead tiles. Geometry updates only on `gen` advance.
- `tests/test_ui_tablet_layout.py` proves every served-HTML contract (8 tests).

## Task Commits

1. **Task 1 + Task 2: tablet restyle, 5-state tiles, tap-to-force, bbox SVG** - `9adac4a` (feat)
2. **Stale-assertion test fix** - `c90f34f` (test)

_Tasks 1 and 2 both rewrite the single `console.html` file (inline `<style>` + markup + `<script>`) as one atomic, coupled deliverable, so the implementation landed in one feat commit with the test file; the stale `test_ui_score` assertion fix is a separate test-scope commit._

## Files Created/Modified
- `src/segugio/ui/templates/console.html` - Tablet-first two-region layout, touch contract, palette/typography migration, 5-state tile classes + dispatcher, tap-to-force gesture, per-tile bbox SVG, five sidebar scaffold blocks.
- `tests/test_ui_tablet_layout.py` (new) - Served-HTML assertions: viewport, touch CSS + sidebar block ids, no 500/600 weights, palette migration, force-removal + tile-is-force-target, tile-state CSS, per-tile bbox SVG, Italian-controls no-regression.
- `tests/test_ui_score.py` - Retired the now-invalid `"Forza" in html` assertion (MVW-04 removed the blind buttons).

## Decisions Made
- See key-decisions in frontmatter. No architectural changes; no new dependency (HARD crash-isolation allowlist preserved — verified by `test_app_imports_nothing_heavy`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Retired the stale `"Forza" in html` assertion in test_ui_score.py**
- **Found during:** Task 1 verification (the plan's `<verify>` re-runs `test_index_serves_italian_console`)
- **Issue:** The existing `test_index_serves_italian_console` asserted `"Forza" in html`, which directly contradicts the locked plan's mandated removal of the blind "Forza {cam}" buttons (MVW-04, D-02/D-03). The plan's Task-1 note to "keep its strings present" is incompatible with its own Task-2 removal of that exact string.
- **Fix:** Removed the `"Forza"` clause from that assertion (kept all other Italian controls + `"Rilascia"`); the force gesture is now covered by `test_force_buttons_removed_tile_is_force_target` in the new test file.
- **Files modified:** tests/test_ui_score.py
- **Verification:** `pytest tests/test_ui_tablet_layout.py tests/test_ui_score.py -q` green (14 passed).
- **Committed in:** c90f34f

---

**Total deviations:** 1 auto-fixed (1 bug — stale test assertion contradicting the mandated removal).
**Impact on plan:** Necessary for correctness; the removal of the blind buttons is a core plan deliverable. No scope creep.

## Issues Encountered
- Several explanatory CSS/HTML/JS comments literally contained forbidden tokens (`user-scalable=no`, `#b23b3b`, `viewBox="0 0 1 1"`, touch-event names, "Forza") that the strict served-HTML substring assertions then caught. Resolved by rewording each comment so the served HTML contains the tokens ONLY where they are load-bearing markup, never in prose. No functional change.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The console shell is stable: 09-03 fills `#reason` (WHY-01), `#leaderboard` (WHY-02), `#auto-wants` (WHY-04) + finalizes the `/preview` `cams[id].box`/`auto_candidate` data wiring into `updateBbox`/`setTileState`, plus the UXT-03 persistent-img/decode-swap + lifecycle resume hygiene. 09-04 fills `#switch-history` (MVW-05) from the `cuts` ring (already served by 09-01).
- No blockers. The `setTileState`/`updateBbox` helpers are defined and exercised; later waves only feed them live data.

## Known Stubs
The four sidebar why-blocks (`#reason`, `#leaderboard`, `#auto-wants`, `#switch-history`) are intentional empty scaffold containers with placeholder Italian copy ("In attesa…", "Nessun dato di framing", "—", "Nessun cambio recente"). This is by design per the 09-02 plan objective ("The sidebar's five content blocks are SCAFFOLDED here; 09-03/09-04 fill them") — they are not goal-blocking for this plan, which delivers the layout/interaction/tile foundation. 09-03 and 09-04 wire their data sources.

## Self-Check: PASSED

- FOUND: src/segugio/ui/templates/console.html
- FOUND: tests/test_ui_tablet_layout.py
- FOUND: .planning/phases/09-explainability-informed-override-tablet-ux/09-02-SUMMARY.md
- FOUND commit: 9adac4a (feat — restyle + tiles + gesture + bbox)
- FOUND commit: c90f34f (test — stale assertion fix)

---
*Phase: 09-explainability-informed-override-tablet-ux*
*Completed: 2026-06-14*
