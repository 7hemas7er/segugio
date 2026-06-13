---
phase: 09-explainability-informed-override-tablet-ux
plan: 04
subsystem: ui-console
status: checkpoint-pending
tags: [MVW-05, UXT-03, switch-history, freshness-watchdog, sleep-wake-resume, leak-free-refresh, tablet]
requires:
  - "09-01: GET /preview exposes the cuts ring"
  - "09-02: tablet-first console scaffold + setTileState (5 states) + #switch-history container"
  - "09-03: reasonToItalian map + pollPreview/markTiles lifecycle"
provides:
  - "MVW-05 switch-history strip (cuts ring, newest-first, Italian reasons)"
  - "UXT-03 leak-free decode-swap refresh (one persistent preloader per tile)"
  - "UXT-03 foreground gen-age staleness watchdog + freshness stamp"
  - "UXT-03 visibilitychange + pageshow/pagehide sleep/wake resume (deferred fetch, resumeAt gate)"
affects:
  - "src/segugio/ui/templates/console.html"
  - "tests/test_ui_freshness.py"
tech-stack:
  added: []
  patterns:
    - "Persistent off-DOM Image() preloader registry + decode()-before-swap (no new Image() per frame)"
    - "1x1 data-URI src for hidden/off tiles (deterministic decoded-bitmap free, not display:none)"
    - "gen-age-vs-local-clock foreground watchdog as the PRIMARY freshness signal"
    - "Named setInterval handles torn down on hide / restarted on resume; deferred first resume fetch"
key-files:
  created:
    - "tests/test_ui_freshness.py"
  modified:
    - "src/segugio/ui/templates/console.html"
decisions:
  - "HIST_SHOW = 6 rows for the switch-history strip (within the 5-8 sidebar discretion band)"
  - "RESUME_DEFER_MS = 200ms (mid 150-250ms band); exact 26.x value to be confirmed on-device (Task 3)"
  - "justResumed + resumeAt gate: a tile renders LIVE only once a frame whose local arrival post-dates the wake"
metrics:
  duration: 7min
  tasks_completed: 2
  tasks_total: 3
  files_touched: 2
  completed_date: 2026-06-13
---

# Phase 09 Plan 04: Switch-history + UXT-03 Tablet Hygiene Summary

MVW-05 switch-history strip + the UXT-03 long-run tablet hygiene (leak-free decode-swap refresh, a gen-age foreground staleness watchdog with the freshness stamp, and visibilitychange + pageshow/pagehide sleep/wake resume) landed and committed as Tasks 1-2; **Task 3 is a blocking on-device iPad acceptance checkpoint, still pending.**

## Status

**CHECKPOINT PENDING — Tasks 1 and 2 complete, Task 3 (blocking-human on-device acceptance) awaiting the physical iPad operator.** This plan is NOT complete; the on-device soak/sleep-wake/freshness proof (iOS-Safari-specific, not assertable by the headless Flask-test-client CI) must be signed off before 09-04 closes.

## What Was Built

### Task 1 — Switch-history strip (MVW-05) + flicker-free/leak-free decode-swap refresh (UXT-03) — commit 250a803
- `buildSwitchHistory(cuts)`: rebuilds `#switch-history` every poll from the `preview.json` cuts ring (exposed by 09-01), NEWEST-FIRST (reverses the newest-last ring), shows the most-recent `HIST_SHOW = 6` rows as `"{from} → {to} · {reason-it}"` with the reason mapped through the same `reasonToItalian` map as 09-03 WHY-01; empty ring → "Nessun cambio recente".
- `refreshTile` rewritten: ONE persistent off-DOM `Image()` preloader PER TILE (`preloaders` registry + `preloaderFor`, created once), `await preloader.decode()` BEFORE swapping the visible `<img>.src` — no `new Image()` per frame (the pre-09-04 leak). Decode reject is caught (silent coast). `?t=<gen>` nonce + the gen-strictly-advances gate (`p.gen > lastGen`) preserved. `decoding="sync"` added to the visible `<img>` as belt-and-suspenders.
- `blankTile(cam)`: hidden/off tiles (not in `cams`) get a 1×1 transparent data-URI src (NOT `display:none`) so the decoded bitmap frees deterministically.

### Task 2 — Freshness watchdog + freshness stamp + sleep/wake resume (UXT-03) — commit 122557c
- `isStale()`: the FOREGROUND gen-age-vs-local-clock watchdog (PRIMARY) — `lastGen >= 0 && (now - lastGenAt) > STALE_MS`. WR-02 load-time seed preserved (a cold load with `lastGen < 0` is never stale → no false MORTO on first paint).
- `freshnessStamp()`: writes "agg. {n}s fa" (seconds since last fresh frame) / "frame non aggiornato" when stale; `#freshness` turns red while stale.
- Per-tile STALE overlay copy via `setStaleOverlay`: "RICONNESSIONE…" right after a wake (`justResumed`), else "STALE" — NEVER "LIVE" on a frozen tile. `markTiles` now forces the `stale` state whenever the channel is stale OR `justResumed` and excludes a frozen tile from `live`/`forzata`.
- Named interval handles `previewTimer` / `statusTimer` + `startPolling()` / `stopPolling()`; `onHide()` tears the polls down on hide, `onResume()` records `resumeAt`, marks all tiles stale, restarts fresh intervals, and DEFERS the first resume fetch in `setTimeout(RESUME_DEFER_MS)` with one retry (iOS "Load failed" dodge). A tile renders LIVE only once a frame whose local arrival post-dates `resumeAt` clears `justResumed`.
- Lifecycle registration: `document` `visibilitychange` + `window` `pageshow`/`pagehide` ONLY; `focus`/`blur`/`unload`/`freeze`/`resume` are NOT registered on document/window (the SCV-01 input `blur` drift-check is unrelated). Wake Lock noted out-of-scope.

## Tests (tests/test_ui_freshness.py — NEW, 10 tests, all green)
- `test_switch_history_renders_from_cuts`, `test_switch_history_empty`
- `test_no_new_image_per_frame`, `test_decode_before_swap`, `test_hidden_tile_data_uri`
- `test_lifecycle_wiring_present`, `test_resume_defers_fetch`, `test_gen_age_staleness_watchdog`, `test_freshness_stamp_copy`, `test_resume_marks_all_stale_and_named_intervals`

These are served-HTML / served-script assertions via the Flask test client (no heavy deps). The behaviors they cover that are iOS-Safari-specific (real memory soak, real sleep/wake recovery, the working `fetch`-deferral value, zero-flash decode on the device) are CANNOT be asserted headless — they are the subject of the Task 3 on-device checkpoint.

## Verification
- `pytest tests/test_ui_freshness.py tests/test_preview_serving.py tests/test_ui_score.py -q` → 26 passed.
- Broader `pytest -k "ui or import or preview"` → all passed (1 environmental skip). Crash-isolation gate `test_app_imports_nothing_heavy` (heavy stack absent) green — the hygiene layer is template/JS only; app.py untouched (threat T-09-04-05 holds).
- 2 pre-existing environmental failures (`test_ndi_mock_sender.py`, `test_ndi_source` — live NDI loopback, documented STATE blocker) are NOT in scope and were not run/affected.

## Deviations from Plan
- **[Test scope refinement — not a code deviation]** `test_lifecycle_wiring_present` initially banned any `addEventListener("blur"...)`; the pre-existing SCV-01 input-field `blur` drift-check (09-03) legitimately uses it. Scoped the forbidden-events ban to the `document.`/`window.` lifecycle surface, matching the UI-SPEC intent (forbid `focus`/`blur` as lifecycle/resume triggers, not as input events). No production-code change.
- **[Comment reword]** Reworded one `console.html` comment from "new Image()" to "fresh Image" so the `test_no_new_image_per_frame` exact-count contract (`new Image()` appears exactly once, inside `preloaderFor`) is not tripped by prose. No behavior change.

Otherwise the plan executed as written.

## Task 3 — Pending Blocking Checkpoint (on-device iPad acceptance)
**Type:** checkpoint:human-verify, gate="blocking-human". MUST be performed on the REAL operator iPad (iPadOS 26.x, Safari, LANDSCAPE) per `docs/run.md` (console + orchestrator, 4 cameras). Cannot be auto-approved. Acceptance criteria (UI-RESEARCH §5):
1. Multi-hour memory soak: tab memory FLAT + server thread count FLAT (record the real decoded-image/GPU ceiling).
2. Sleep/wake (device-lock AND app-switch): resumes a FRESH frame; tiles briefly STALE/RICONNESSIONE…; LIVE only once new frames arrive; both `pageshow persisted===true` and `visibilitychange`-hidden paths recover.
3. Freshness guarantee: freeze one feed → that tile flips STALE/MORTO ("frame non aggiornato") within ~one poll cycle, NEVER "live".
4. No "Load failed" storm on resume; record whether 150ms or 250ms deferral is needed on 26.x (currently `RESUME_DEFER_MS = 200`).
5. Tap-to-force responsive, bottom-trailing "Rilascia (auto)" reachable one-handed, decode-swap zero-flash.

**Resume signal:** "approved" (with the observed memory ceiling + deferral value), or a description of failures to feed a gap-closure plan.

## Known Stubs
None. The switch-history strip is wired to the live `cuts` ring (09-01 data source); the freshness/refresh/resume code is fully wired. No placeholder/empty-data stubs introduced.

## Self-Check: PASSED
- FOUND: src/segugio/ui/templates/console.html
- FOUND: tests/test_ui_freshness.py
- FOUND commit 250a803 (Task 1)
- FOUND commit 122557c (Task 2)
