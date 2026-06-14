---
phase: 09-explainability-informed-override-tablet-ux
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/segugio/ui/app.py
  - src/segugio/ui/templates/console.html
  - tests/test_preview_serving.py
  - tests/test_score_preview.py
  - tests/test_ui_explainability.py
  - tests/test_ui_freshness.py
  - tests/test_ui_score.py
  - tests/test_ui_tablet_layout.py
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase-9 live oversight console: `src/segugio/ui/app.py` (Flask factory, 6 routes
added/touched this phase) and the largely-rewritten `src/segugio/ui/templates/console.html`
(tablet UI + ~530 lines of inline JS), plus the six test modules that exercise them.

Both HARD invariants hold:

1. **Crash isolation (D-03/RBT-04) — PASS.** `app.py` module scope imports only `os`,
   `..opcomm.channel`, `..opcomm.records`, `.score_render`, `..opcomm.atomic`. The `config`
   import (line 233) and `waitress` (line 243) are lazy inside `__main__`. No torch/cv2/
   ultralytics/numpy/cyndilib at module scope. `test_app_imports_nothing_heavy` enforces this.
2. **Stale-never-live safety (UXT-03) — PASS.** `markTiles` forces `state = "stale"` whenever
   `frozen` (stale gen OR `justResumed`) and excludes frozen tiles from `isLiveCam`
   (console.html:780-783); the foreground gen-age watchdog (`isStale`) is primary; the freshness
   stamp turns red and shows "frame non aggiornato". A frozen frame is never labelled LIVE.

I verified the most fragile claimed invariant — byte-exact parity between JS `cleanField` and
Python `_clean` — by running both over adversarial Unicode (U+0020 space, NBSP, EM-space,
ZWJ U+200D, soft-hyphen U+00AD, variation-selector U+FE0F, lone surrogate). They agreed on every
case. The SCV-01 mirror is sound for practical inputs.

No Critical defects found. Findings are correctness/robustness warnings in the client JS and a
handful of quality items. The accepted no-auth LAN-trust posture was NOT flagged per scope.

## Structural Findings (fallow)

No structural-findings block was provided with this review.

## Warnings

### WR-01: `forceCam` fires on dead/stale tiles — operator can force a known-dead camera

**File:** `src/segugio/ui/templates/console.html:560-564`
**Issue:** Every tile gets an unconditional `click → forceCam(cam)` handler at wiring time. A
tile currently rendered `dead` (MORTO, `alive[cam] !== true`) or `stale` still POSTs
`/command {force_cam}` on tap. The UI explicitly signals these cameras as not-airable (dim +
desaturate, "MORTO" badge), so a tap-to-force on them contradicts the displayed state and asks
the director to cut to a feed the console itself believes is dead. The orchestrator may reject
it, but the console should not emit a command it has just told the operator is invalid — on a
field tablet a fat-finger on a greyed tile silently sends a bad override.
**Fix:** Guard the click on current tile state:
```js
CAMS.forEach(cam => {
  const tile = document.getElementById("tile-" + cam);
  if (tile) tile.addEventListener("click", () => {
    if (tile.classList.contains("dead") || tile.classList.contains("stale")) return;
    forceCam(cam);
  });
});
```

### WR-02: auto-wants tile marker is never cleared until the next 1 s status poll

**File:** `src/segugio/ui/templates/console.html:536-553, 700-712`
**Issue:** `renderAutoWants` is called from `pollPreview` (every `PUBLISH_MS` = 200 ms) and can
ADD `auto-wants` to the candidate tile via `setTileState(candidate, "auto-wants")`, but it never
REMOVES it. Removal only happens when `markTiles` runs and reclassifies the tile to `idle` —
and `markTiles` runs from `pollStatus` only every 1000 ms. When the candidate changes between
status polls (a new `auto_candidate` arrives at 5 Hz during an override), the previous
candidate's tile keeps its dashed-blue `auto-wants` border for up to ~1 s, and two tiles can
briefly show `auto-wants` simultaneously, contradicting the "auto wants exactly one cam" intent.
**Fix:** Have `renderAutoWants` clear the marker off non-candidate tiles, or drive the tile
marker exclusively from `markTiles` (single owner of tile state) and let `renderAutoWants` own
only the `#auto-wants` text line.

### WR-03: `renderAutoWants` can paint `auto-wants` over a tile `markTiles` just set to `live`

**File:** `src/segugio/ui/templates/console.html:545-552`
**Issue:** During an override (`status.reason === "override"`), `markTiles` sets the live cam to
`forzata` and other cams to `idle`/`auto-wants`. But `renderAutoWants` (also fired from
`pollStatus` at line 816, AFTER `markTiles`) re-applies `auto-wants` to `candidate` as long as
the candidate tile is not currently `forzata`/`dead`/`stale`. If the auto candidate equals the
auto-selected LIVE cam in a non-override frame… that path is guarded. But during the transition
tick where `pollPreview` updated `lastAutoCandidate` to a cam that `markTiles` just marked
`live` (override just released, preview not yet reflecting it), `renderAutoWants` overwrites the
green `live` tile with dashed-blue `auto-wants`. The two functions both mutate tile classes with
no single owner, producing a visibly flickering/incorrect tile during override on/off edges.
**Fix:** Make `markTiles` the sole writer of tile CSS state; reduce `renderAutoWants` to the
text line only (see WR-02 fix). Single-owner state removes the race entirely.

### WR-04: leaderboard `pct` width uses raw score without normalizing — bars assume score ∈ [0,1]

**File:** `src/segugio/ui/templates/console.html:498, 517`
**Issue:** `pct = Math.max(0, Math.min(1, score)) * 100` clamps the framing score to [0,1] for
the bar width. The framing scorer's published `score`/`ema` are described in
`records.PreviewDoc` only as per-camera numeric values with no documented [0,1] range
guarantee. If the publisher ever emits a score > 1 (or a raw, un-normalized magnitude), every
non-lost bar silently saturates to 100% and the leaderboard stops discriminating between cameras
— defeating the entire WHY-02 "which camera scores best" explainability. The clamp hides the
bug rather than surfacing it.
**Fix:** Either assert/normalize against the known scorer range, or scale bar width relative to
the max score in the current set so the leaderboard remains discriminating regardless of the
absolute scale:
```js
const maxScore = Math.max(1e-6, ...entries.map(([,c]) => scoreOf(c)));
const pct = Math.max(0, score / maxScore) * 100;
```

### WR-05: `live-cam` / `live-reason` render raw status verbatim — null/empty shows blank, not a sentinel

**File:** `src/segugio/ui/templates/console.html:802-803`
**Issue:** `pollStatus` sets `live-cam.textContent = s.live_cam` and
`live-reason.textContent = s.reason` directly. The server's `read_status` safe-default returns
`live_cam="SAFE"`, so this is normally fine — but if a torn/partial status JSON ever yields
`null`/`""` for either field (the JSON layer can produce `null` even though the dataclass
default is `"SAFE"`), the operator sees an empty live-camera readout with no indication anything
is wrong, while the rest of the UI (`onair-cam` uses `status.live_cam || "—"` at line 793)
shows the "—" sentinel. The inconsistency means the D-11 status panel can read blank where the
banner reads "—".
**Fix:** Mirror the banner's coalescing for both fields:
```js
document.getElementById("live-cam").textContent = s.live_cam || "—";
document.getElementById("live-reason").textContent = s.reason || "—";
```

### WR-06: `post()` ignores the fetch result everywhere — a failed override/score is silent

**File:** `src/segugio/ui/templates/console.html:318-322, 334, 339, 560, 565-566`
**Issue:** `post()` returns the fetch promise, but every call site for the live-action POSTs
(`/score`, `/run`, `/command` force, `/command` release) discards it — no `.then`/`.catch`, no
status check. If a `/command` POST fails (network blip on the contended WiFi, a 400 from a
contradictory command, a 5xx) the operator gets ZERO feedback: the tap appears to succeed. For
the override path this is a live-direction safety-relevant gap — the operator believes they
forced a camera when the command never landed. (`driftCheck` correctly inspects `r.ok`; the
action POSTs do not.) Note this is distinct from the documented no-auth posture.
**Fix:** At minimum surface failures for `/command` and `/run`:
```js
post("/command", { force_cam: cam }).then(r => {
  if (!r.ok) flashError("Comando non riuscito");
}).catch(() => flashError("Rete: comando non inviato"));
```

## Info

### IN-01: `decoding="sync"` is not a standard HTML attribute value

**File:** `src/segugio/ui/templates/console.html:187`
**Issue:** `<img ... decoding="sync">`. The HTML `decoding` attribute accepts `sync`, `async`,
`auto` — `sync` is in fact valid, but the inline comment (line 642-644) calls it
"belt-and-suspenders" while the real flicker control is `await preloader.decode()`. The attribute
is harmless but the comment overstates that `decode()` is "the real flicker control" while the
visible swap (`visible.src = pre.src`) happens after decode of the *preloader*, not the visible
img — a tiny second decode of the visible element can still occur. Cosmetic; behavior is correct
in practice because the bytes are warm in cache.
**Fix:** None required; consider trimming the comment claim or noting the second decode is
cache-warm.

### IN-02: `CAM_LABEL` is an identity map — dead indirection

**File:** `src/segugio/ui/templates/console.html:450, 507, 594`
**Issue:** `const CAM_LABEL = Object.fromEntries(CAMS.map(c => [c, c]))` maps every cam id to
itself, then `CAM_LABEL[cam] || cam` is used in three places — always equal to `cam`. This is
scaffolding for future friendly labels but currently adds a lookup and a misleading
`|| cam` fallback that can never trigger.
**Fix:** Either drop `CAM_LABEL` and use `cam` directly, or add a comment that it is a
placeholder for future human-readable labels.

### IN-03: `lastAutoCandidate` seeded to `"SAFE"` participates in tile-id comparison

**File:** `src/segugio/ui/templates/console.html:619, 786`
**Issue:** `lastAutoCandidate = "SAFE"` initially. In `markTiles`,
`else if (overriding && cam === lastAutoCandidate)` compares a cam id against `"SAFE"`. `"SAFE"`
is never a tile id (it is the SAFE sentinel), so the comparison never matches — correct by
accident. If a camera were ever literally named `SAFE` this would mis-mark it. Harmless given
the sentinel convention but relies on an implicit naming taboo.
**Fix:** Guard explicitly: `else if (overriding && lastAutoCandidate !== "SAFE" && cam === lastAutoCandidate)`.

### IN-04: `updateBbox` writes raw numeric attributes without bounds for off-frame boxes

**File:** `src/segugio/ui/templates/console.html:608-613`
**Issue:** `x = cx - w/2`, `y = cy - h/2` can be negative and `width`/`height` are taken
verbatim from the normalized box. SVG clips to the viewBox so this renders correctly, but no
validation rejects a malformed box like negative width or values far outside [0,1] (e.g. a torn
preview file the `read_preview` safe-default cannot catch at the per-element level). The rect
just draws garbage rather than hiding. Low risk because the box originates from a trusted
publisher.
**Fix:** Optionally clamp/validate components to a sane range before drawing, falling back to
`visibility:hidden` on out-of-range values.

### IN-05: magic timing constants duplicated across comments and code

**File:** `src/segugio/ui/templates/console.html:622-623, 634, 679`
**Issue:** `PUBLISH_MS=200`, `STALE_MS=PUBLISH_MS*3`, `RESUME_DEFER_MS=200`, `HIST_SHOW=6`,
`SCV_MAX_FIELD_LEN=64`, and the 200 ms preview debounce (line 415) are each declared once but
their rationale ("~5 fps", "150–250ms band", "5–8 rows") lives only in prose comments. The
debounce literal `200` at line 415 is NOT tied to `RESUME_DEFER_MS`/a named const, so the two
"200ms" values can drift apart silently. Minor maintainability.
**Fix:** Name the debounce interval as a const alongside the others
(`const SCORE_DEBOUNCE_MS = 200;`).

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
