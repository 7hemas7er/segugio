---
phase: 09-explainability-informed-override-tablet-ux
verified: 2026-06-14T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
re_verification: null
---

# Phase 9: Explainability, Informed Override & Tablet UX — Verification Report

**Phase Goal:** The console becomes a true regia — the operator not only sees the cameras but understands *why* the auto-director chose the live one and can override from what they see. This phase publishes-and-renders the explainability layer (per-camera score bars, the plain-Italian reason, the dog-lock bbox overlay, the "auto wants vs aired" hint, the switch-history strip), turns every multiview tile into an informed force-cam control, shows a live preview of how the score will appear on the OBS overlay as the operator types, restyles the whole console tablet-first, and adds the long-run hygiene that keeps a tablet on contended WiFi honest (no leaks, sleep/wake resume, and a freshness stamp so a frozen frame is never shown as "live").

**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Test Execution

All Phase 9 test targets run cleanly. Command executed:

```
venv/Scripts/python.exe -m pytest tests/test_ui_explainability.py tests/test_ui_freshness.py tests/test_ui_tablet_layout.py tests/test_score_preview.py tests/test_preview_serving.py tests/test_ui_score.py tests/test_imports.py -v
```

Result: **76 passed in 5.63s** (0 failures, 0 errors).

Pre-existing environmental failures (`test_ndi_mock_sender.py::test_mock_sender_publishes_named_source`, `test_ndi_source.py::test_receiver_yields_bgr_and_new_frame_ts`) are NDI loopback tests last touched in Phase 5 (commit a1bff0d); Phase 9 touched only `console.html`, the `/preview` and `/score/preview` routes, and UI tests — not the NDI receiver path. These two are not counted against Phase 9.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /preview returns a `cuts` array so the switch-history strip (MVW-05) has its data source | VERIFIED | `app.py` line 213: `"cuts": [dict(c) for c in doc.cuts]`; `test_preview_serving.py::test_serve_preview_sidecar_exposes_cuts` passes |
| 2 | POST /score/preview returns the exact `render_overlay_text` line WITHOUT writing any channel file (SCV-01 server-side drift-guard) | VERIFIED | `app.py` lines 119-141: pure render route with no `write_score`/`atomic_write_text`; all 6 `test_score_preview.py` tests pass including `test_score_preview_writes_no_file` and byte-exact discipline assertions |
| 3 | Console import surface stays Flask + segugio.opcomm + segugio.ui.score_render only — crash-isolation gate green | VERIFIED | `test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` passes; no heavy import (`ultralytics`, `torch`, `cv2`, `cyndilib`, `obsws`) in `app.py` |
| 4 | Console is a landscape multiview-LEFT + sidebar-RIGHT layout that reflows to single-column below tablet width (UXT-01, D-01) | VERIFIED | `console.html` lines 53-63: `.layout { grid-template-columns: 1fr 340px; gap: 32px }` + `@media (max-width: 1024px) { .layout { grid-template-columns: 1fr } }`; `test_viewport_meta_is_tablet_safe` + `test_touch_action_and_targets` pass |
| 5 | Tapping a multiview tile POSTs /command {force_cam} immediately; blind "Forza" buttons removed; "Rilascia (auto)" is a distinct large always-visible undo (MVW-04) | VERIFIED | `console.html` line 559: `function forceCam(cam) { post("/command", { force_cam: cam }); }` bound via standard `click` only; no "Forza" string appears in served HTML; `#rilascia` ≥48px; `test_force_buttons_removed_tile_is_force_target` passes |
| 6 | Tiles carry 5 grayscale-safe states (LIVE/FORZATA/MORTO/auto-wants/idle) via 3 redundant channels: hue + border-style + text label (D-04, WHY-03) | VERIFIED | `console.html` CSS lines 80-103: `.tile.live` (solid #34D399), `.tile.forzata` (solid #F0B429 + ribbon), `.tile.auto-wants` (dashed #56B4E9), `.tile.dead` (dim+desaturate), `.tile.stale`; `test_tile_state_css_present` passes |
| 7 | The dog-lock bbox overlay renders as one inline SVG per tile from normalized [cx,cy,w,h] with zero JS letterbox math, hidden on STALE/MORTO (WHY-03) | VERIFIED | `console.html` line 188: `<svg class="bbox-overlay" viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet">`; CSS line 128: `.tile.dead .bbox-overlay, .tile.stale .bbox-overlay { display: none }`; `updateBbox` sets rect from normalized coords; `test_bbox_svg_per_tile` passes |
| 8 | Sidebar renders the current choice's reason in plain Italian from status.reason (WHY-01) | VERIFIED | `console.html` lines 454-466: `REASON_IT` map with all 6 reason keys + `reasonToItalian` function; `renderReason` writes to `#reason` from `pollStatus`; `test_reason_strings_italian` (JS-exercised via node) + `test_reason_wired_into_pollstatus` pass |
| 9 | Sidebar renders a per-camera framing-score leaderboard sorted highest-first with tracking/coast/lost fill states (WHY-02) | VERIFIED | `console.html` lines 478-531: `buildLeaderboard(cams)` sorts by score desc, renders `.lb-fill.tracking`/`.coast`/`.lost`; lost LABEL uses `#E6E9EF` not `#6B7280`; `test_leaderboard_renders_sorted` (JS-exercised) + `test_leaderboard_css_and_wiring` pass |
| 10 | During override the console shows which camera the auto-director wants now ("Auto vuole: {cam}" + dashed-blue auto-wants tile marker) from auto_candidate (WHY-04) | VERIFIED | `console.html` lines 533-551: `renderAutoWants` writes "Auto vuole: {candidate}" when `status.reason === "override"` and calls `setTileState(candidate, "auto-wants")`; `test_auto_wants_line` passes |
| 11 | As the operator types a score, "Anteprima overlay" shows a byte-exact client-side mirror of render_overlay_text, drift-guarded against POST /score/preview on blur/submit (SCV-01) | VERIFIED | `console.html` lines 341-391: `gsd:scv01-mirror` block with `cleanField`/`mirrorOverlayText` byte-exact to Python; debounced 200ms; drift-guard POSTs `/score/preview` once on blur/submit; `test_scv01_mirror_matches_render_overlay_text` (node-executed byte parity across 3 disciplines + aliases + sanitize) passes |
| 12 | Switch-history strip renders recent cuts newest-first with Italian reasons from preview.json cuts ring (MVW-05) | VERIFIED | `console.html` lines 679-697: `buildSwitchHistory` reverses ring, renders `"{from} → {to} · {reason-it}"`, uses `reasonToItalian`; `test_switch_history_renders_from_cuts` + `test_switch_history_empty` pass |
| 13 | Long-run tablet hygiene: leak-free decode-swap refresh, gen-age freshness watchdog, sleep/wake resume, freshness stamp — a frozen frame is never shown as "live" (UXT-03) | VERIFIED | `console.html`: one persistent `Image()` preloader per tile (`preloaderFor`, `preloaders` registry), `await pre.decode()` before swap, `blankTile` with 1x1 data-URI; `isStale()` watchdog; `visibilitychange`/`pageshow`/`pagehide` lifecycle (no focus/blur/freeze/resume); `resumeAt`/`justResumed`/`RESUME_DEFER_MS=200ms` gates; all 10 `test_ui_freshness.py` tests pass; on-device iPad acceptance APPROVED by operator (iPadOS 26.x, verbatim: "approved — memory flat, 200ms deferral fine") |

**Score:** 13/13 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/segugio/ui/app.py` | `/preview` route exposing cuts; pure `/score/preview` route | VERIFIED | `cuts` in jsonify (line 213); `post_score_preview` at line 119 with no file writes |
| `src/segugio/ui/templates/console.html` | Tablet-first two-region layout, 5-state tiles, tap-to-force, bbox SVG, sidebar blocks, explainability JS, SCV-01 mirror, switch-history, UXT-03 hygiene | VERIFIED | 877-line fully implemented template; all contracted JS functions present and wired |
| `tests/test_score_preview.py` | Flask-test-client coverage for /score/preview across all 3 disciplines + byte-parity reference | VERIFIED | 6 tests, all pass |
| `tests/test_preview_serving.py` | Cuts ring exposure test added | VERIFIED | 10 tests total (8 Phase-8 + 2 Phase-9 cuts tests), all pass |
| `tests/test_ui_tablet_layout.py` | Viewport meta, touch CSS, sidebar block ids, no 500/600 weights, palette migration, force-removal, tile-state CSS, bbox SVG | VERIFIED | 8 tests, all pass |
| `tests/test_ui_explainability.py` | WHY-01/02/03/04 sidebar assertions; SCV-01 byte-parity (node-executed); drift-check behavior | VERIFIED | 11 tests, all pass (includes node-exercised JS parity) |
| `tests/test_ui_freshness.py` | Switch-history, persistent-preloader/decode, lifecycle, staleness watchdog, freshness stamp | VERIFIED | 10 tests, all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py /preview` | `PreviewDoc.cuts` | `[dict(c) for c in doc.cuts]` in jsonify | WIRED | Line 213; `test_serve_preview_sidecar_exposes_cuts` confirms round-trip |
| `app.py /score/preview` | `segugio.ui.score_render.render_overlay_text` | pure render, no file write | WIRED | Lines 119-141; `test_score_preview_byte_reference` confirms byte-exact output |
| `console.html tile element` | `/command {force_cam}` | `forceCam` bound to standard `click` on each tile | WIRED | Lines 559-562; `test_force_buttons_removed_tile_is_force_target` confirms |
| `console.html tile SVG overlay` | `preview.json cams[id].box` | `updateBbox(c, (cams[c]||{}).box)` in `pollPreview` | WIRED | Lines 727; `test_bbox_data_wired_from_preview` confirms |
| `console.html pollStatus` | `status.reason` → Italian string map | `reasonToItalian` via `REASON_IT` | WIRED | Lines 454-472; node-executed `test_reason_strings_italian` confirms all 6 mappings |
| `console.html pollPreview` | `preview.json cuts ring` | `buildSwitchHistory(p.cuts)` at line 709 | WIRED | `test_switch_history_renders_from_cuts` confirms data + render contract |
| `console.html score form` | `render_overlay_text` mirror + POST /score/preview | `mirrorOverlayText` debounced + `driftCheck` once on blur/submit | WIRED | Lines 341-446; node-executed byte parity confirmed across 3 disciplines |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `console.html #reason` | `status.reason` | `GET /status` → `read_status` → `DirectorStatus.reason` | Yes — live opcomm channel | FLOWING |
| `console.html #leaderboard` | `p.cams` (score/ema/state) | `GET /preview` → `read_preview` → `PreviewDoc.cams` | Yes — preview sidecar written by orchestrator | FLOWING |
| `console.html #auto-wants` | `p.auto_candidate` + `status.reason` | `GET /preview` + `GET /status` | Yes — live opcomm channels | FLOWING |
| `console.html bbox-overlay` | `cams[cam].box` | `GET /preview` → `PreviewDoc.cams[id].box` | Yes — bbox written by orchestrator when dog is locked | FLOWING (null when ReID lock dropped — handled) |
| `console.html #switch-history` | `p.cuts` | `GET /preview` → `PreviewDoc.cuts` (ring) | Yes — cuts ring exposed by 09-01; `test_serve_preview_sidecar_exposes_cuts` verifies round-trip | FLOWING |
| `console.html #overlay-preview` | `mirrorOverlayText(discipline, fields)` | Client-side JS mirror (no network call per keystroke) | Yes — byte-exact; drift-guarded via POST /score/preview on blur | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 9 tests pass | `venv/Scripts/python.exe -m pytest tests/test_ui_explainability.py tests/test_ui_freshness.py tests/test_ui_tablet_layout.py tests/test_score_preview.py tests/test_preview_serving.py tests/test_ui_score.py tests/test_imports.py -q` | 76 passed, 0 failures | PASS |
| Crash-isolation guard | `pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` | 1 passed | PASS |
| JS mirror byte parity (node-executed) | `test_scv01_mirror_matches_render_overlay_text` (via node subprocess in pytest) | 11 parity cases across 3 disciplines, aliases, sanitize — byte-identical | PASS |
| POST /score/preview writes no file | `test_score_preview_writes_no_file` | PASS — score.json and overlay.txt do not exist after route call | PASS |
| No `new Image()` per frame | `test_no_new_image_per_frame` | `new Image()` appears exactly once in script (inside `preloaderFor`) | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MVW-04 | 09-02 | Informed override — every tile is the force control; blind buttons removed | SATISFIED | `forceCam` bound to tile click; no "Forza" in HTML; `test_force_buttons_removed_tile_is_force_target` |
| MVW-05 | 09-01, 09-04 | Switch-history strip from cuts ring, newest-first | SATISFIED | `GET /preview` exposes cuts (09-01); `buildSwitchHistory` renders newest-first (09-04); tests pass |
| WHY-01 | 09-03 | Plain-Italian reason in sidebar from status.reason | SATISFIED | `reasonToItalian` map + `renderReason` writing to `#reason`; node-exercised byte parity |
| WHY-02 | 09-03 | Per-camera framing-score leaderboard with tracking/coast/lost fill | SATISFIED | `buildLeaderboard`; sorted highest-first; lost LABEL in #E6E9EF; tests pass |
| WHY-03 | 09-02, 09-03 | Dog-lock bbox overlay on live tile from preview.json normalized box | SATISFIED | SVG `viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet"` per tile; `updateBbox` driven from `pollPreview` |
| WHY-04 | 09-03 | "auto vuole vs in onda" hint during override | SATISFIED | `renderAutoWants`; "Auto vuole: {cam}" + dashed-blue tile marker; `test_auto_wants_line` |
| SCV-01 | 09-01, 09-03 | Live score-overlay preview — byte-exact mirror + drift-guard | SATISFIED | `mirrorOverlayText`/`cleanField` mirror; POST /score/preview pure render; node byte-parity confirmed |
| UXT-01 | 09-02 | Tablet-first responsive restyle; touch targets; safe-area | SATISFIED | viewport-fit=cover; touch-action:manipulation; ≥44/48px targets; 4 sizes weights 400+700 only |
| UXT-03 | 09-04 | Leak-free refresh; freshness watchdog; sleep/wake resume; freshness stamp | SATISFIED | Persistent preloader + decode-before-swap; `isStale()` watchdog; visibilitychange/pageshow/pagehide; on-device acceptance APPROVED |

All 9 Phase 9 requirement IDs confirmed present and implemented. REQUIREMENTS.md traceability table marks all 9 as Complete.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/segugio/ui/app.py` | 192 | `placeholder` in a comment ("Publisher hasn't written this frame yet → 404 (the browser shows its placeholder).") | Info | Comment-only; refers to browser image placeholder behavior, not a code stub |
| `console.html` | 255 | `placeholder="mm:ss"` HTML attribute on timer input | Info | Legitimate UX placeholder text for the mm:ss timer format; not a stub |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 9 file. No unresolved debt markers. No `return null`/`return {}`/`return []` stubs in implementation paths. No hardcoded-empty data flowing to rendered output.

---

## Human Verification Required

The only human verification item for this phase was the blocking on-device iPad acceptance checkpoint (Task 3, plan 09-04), which required physical iPadOS 26.x, Safari, landscape validation of:

1. Multi-hour memory soak — flat tab memory + flat server thread count
2. Sleep/wake resume on both device-lock and app-switch paths
3. Freshness guarantee — frozen feed marked STALE/MORTO, never "live"
4. fetch-in-resume "Load failed" behavior and safe deferral value
5. Touch reachability + decode-swap zero-flash

**This checkpoint was completed and APPROVED** by the operator on the physical iPad (iPadOS 26.x). Verbatim sign-off: "approved — memory flat, 200ms deferral fine." All five criteria passed. The `RESUME_DEFER_MS = 200` value is confirmed working on the target device.

No remaining human verification items. The `human_needed` status does not apply.

---

## Gaps Summary

No gaps. All 13 observable truths verified, all 9 requirement IDs satisfied, all 7 artifacts substantive and wired, all key links confirmed, no debt markers, no stub patterns in dynamic data paths. The on-device acceptance checkpoint (the one `checkpoint:human-verify` task in phase 9) was completed and signed off.

---

---

## Addendum — Post-Verification Adversarial Review (2026-06-14)

After the gsd-verifier pass above (which reported "no gaps"), an independent 10-agent adversarial
verification workflow (one skeptic per requirement + the crash-isolation invariant, each tasked to
*refute* delivery against the served code) found **one real defect the single-pass verifier missed**:

- **WHY-02 — leaderboard "coast" state was dead against live data.** The publisher writes the
  canonical enum value `ScorerStatus.coasting.value` = `"coasting"` (`orchestrator/preview.py:228`),
  but the served `buildLeaderboard` JS compared `state === "coast"` (`console.html`), so a genuinely
  coasting camera fell through to the `lost` branch (empty bar + `·· lost`) and the mandated hatched
  `◐ coast` bar never rendered. The leaderboard test masked this by feeding the short form `"coast"`
  the JS expected rather than the real enum value.

**Resolution (commit `d6e7555`):** aligned the JS to the canonical enum (`state === "coasting"`,
keeping the `.lb-fill.coast` class + `◐ coast` label), and pinned `test_ui_explainability.py` to
`ScorerStatus.coasting.value` from the Python source of truth so the parity cannot silently drift
again. The guard was proved genuine (reverting the JS reproduces the live bug and fails the test).
Post-fix: `tests/test_ui_explainability.py` 11/11 green; full Phase-9 UI surface 76/76 green.

With this fix, WHY-02 is fully delivered against live data. Phase status remains **passed**.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier) + adversarial verification workflow_
