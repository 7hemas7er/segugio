---
phase: 08-console-serving-live-multiview-safety-hardening
fixed_at: 2026-06-13T18:32:00Z
review_path: .planning/phases/08-console-serving-live-multiview-safety-hardening/08-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-06-13T18:32:00Z
**Source review:** .planning/phases/08-console-serving-live-multiview-safety-hardening/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (WR-01 .. WR-05; critical_warning scope, Info findings IN-01..IN-04 deferred)
- Fixed: 5
- Skipped: 0

All in-scope warning-level findings were applied, verified (Python `ast.parse` on the two
`.py` files; Tier-1 re-read on the Jinja `console.html` which has no standalone JS/HTML syntax
checker), and the full headless suite (`pytest -m "not ndi"`) plus the four Phase-8 test files
pass against the committed tree.

## Fixed Issues

### WR-01: Client multiview camera ids are hardcoded and diverge from the server whitelist

**Files modified:** `src/segugio/ui/app.py`, `src/segugio/ui/templates/console.html`
**Commit:** 5fd1be1
**Applied fix:** The `index()` route now passes `cam_ids=sorted(cam_ids)` into
`render_template("console.html", ...)`. The template renders the multiview tiles and the
`Forza <cam>` override buttons from a `{% for cam in cam_ids %}` loop, and the JS `CAMS`
constant is `{{ cam_ids | tojson }}` with `CAM_LABEL` derived from it
(`Object.fromEntries(CAMS.map(c => [c, c]))`). A non-default rig (3 cams, ids like
`cam_a`/`cam_b`) now renders the correct tiles, force buttons, and JS cam set, so the
configurable `cam_ids` arg is fully honoured by both the route and the page. The
crash-isolation contract is intact — no new heavy imports were added to `ui/app.py`; the only
new call is the existing `render_template` with extra kwargs.

### WR-02: First-load staleness false-positive marks every tile MORTO for ~600 ms

**Files modified:** `src/segugio/ui/templates/console.html`
**Commit:** 5fd1be1
**Applied fix:** Two belt-and-suspenders changes. (1) `lastGenAt` is seeded to `Date.now()` at
load time instead of epoch `0`. (2) `markTiles` now computes
`const stale = lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS;` so "no gen seen yet"
(`lastGen < 0`) is explicitly NOT stale. The immediate `pollStatus()` -> `markTiles()` that
runs before the first `pollPreview()` lands a gen no longer paints every healthy tile MORTO.

### WR-03: markTiles treats a missing per-cam alive entry as ALIVE, masking unknown feeds

**Files modified:** `src/segugio/ui/templates/console.html`
**Commit:** 5fd1be1
**Applied fix:** Liveness now fails safe. `markTiles` checks
`aliveKnown = status.alive && Object.prototype.hasOwnProperty.call(status.alive, cam)` and sets
`dead = (aliveKnown ? status.alive[cam] !== true : true) || stale`. A camera the orchestrator
does not report on (subset publish, or an id mismatch) is treated as MORTO rather than silently
shown healthy via `undefined === false`.

### WR-04: Bandwidth-cap estimator scales JPEG bytes linearly with quality, contradicting JPEG behavior

**Files modified:** `src/segugio/config/models.py`
**Commit:** a96ca03
**Applied fix:** Took the reviewer's lowest-risk option (option 2): documented the linear
`jpeg_quality / 55` term as a DELIBERATE over-estimate above q55 in both the function docstring
and an inline comment, explaining the safety direction (can over-reject, never under-budget)
and that the remediation for a spurious rejection is to raise `PreviewParams.max_total_mbps`.
The math is unchanged, so the safety behaviour (never admitting an over-budget preview onto the
contended WiFi) and the existing default-passes/cranked-fails test are preserved; capping the
ratio at 1.0 was deliberately NOT chosen because it would weaken the never-under-budget
guarantee for genuinely high-quality configs.

### WR-05: Score POST sweeps hidden/empty form fields into the OBS overlay, unbounded

**Files modified:** `src/segugio/ui/app.py`, `src/segugio/ui/templates/console.html`
**Commit:** 13ec61e
**Applied fix:** Server-side, `post_score` now drops empty values:
`fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS and v.strip()}`, so empty
keys from hidden disciplines never reach `ScoreDoc.fields`, the OBS overlay render, or
`score.json`. Client-side, the submit handler stops using `new FormData(e.target)` (which
serializes `display:none` inputs) and instead builds the body explicitly from `discipline` plus
only the inputs inside the `.campi[data-disc="<selected>"]` block, so the hidden disciplines'
fields are never posted in the first place.

## Notes on commit granularity

WR-04 and WR-05 landed as isolated atomic commits (a96ca03, 13ec61e). WR-01, WR-02, and WR-03
all touch overlapping hunks of `console.html` (the `CAMS`/`lastGenAt` block and the `markTiles`
body are interleaved across the same regions). Selective hunk staging was used to separate them,
but the final `git commit` for the multiview client changes folded WR-01, WR-02, and WR-03 into
a single commit (5fd1be1) — `git commit --only <path>` commits the path's full working-tree
state rather than only the index-staged hunks. All three fixes are present and verified; only
the per-finding commit boundary for the three console.html findings is coarser than one-commit-
per-finding. No history rewrite was attempted to avoid risking the verified tree.

---

_Fixed: 2026-06-13T18:32:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
