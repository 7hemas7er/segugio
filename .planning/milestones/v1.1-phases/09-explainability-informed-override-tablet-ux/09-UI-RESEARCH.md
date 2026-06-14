# Phase 9 — UI Research (iOS/iPadOS Safari + landscape-tablet constraints)

> **Source:** deep web-research + adversarial verification workflow (8 agents, 4 topics × research+verify), 2026-06-13.
> **Scope:** the genuinely-uncertain iOS-Safari/tablet technical constraints the Phase-9 UI-SPEC must encode. Layout/interaction *vision* is already locked in `09-CONTEXT.md` (D-01..D-07). This doc is the technical contract input for `gsd-ui-researcher`.
> **Target device (locked, D-06):** iPad / Safari (iPadOS), **landscape**, multi-hour live use on contended WiFi.
> **Versioning correction:** the target is **iPadOS/Safari 26.x** (year-based versioning), NOT "iOS 18". Items tagged `[ASSUMED]` below MUST be re-validated on the physical target iPad during Wave 0.

---

## 1. Lifecycle, freshness & sleep/wake resume (UXT-03) — the load-bearing risk

**Verdict: CORRECTED (substantially sound).** The freshness guarantee CANNOT rely on the poll loop ticking — on iPad sleep/app-switch the page is frozen into WebKit's bfcache and ALL `setInterval`/`setTimeout`/`requestAnimationFrame`/in-flight `fetch` callbacks are *suspended* (not throttled) and resume from where they stopped (no catch-up burst). Any `<img>` on screen at suspend is a frozen frame the page can't know is stale until JS runs again.

**Contract clauses for the UI-SPEC:**
- **Lifecycle wiring (mandatory):** register on BOTH `document` `visibilitychange` (read `document.visibilityState`) AND `window` `pageshow`/`pagehide` (read `event.persisted`). Do NOT use `focus`/`blur`, do NOT use `unload`, do NOT depend on the Page Lifecycle `freeze`/`resume` events — **VERIFIED** (caniuse, May 2026 dataset) Safari iOS through 26.5 does not implement them.
- **Resume fetch MUST be deferred:** never call `fetch()` synchronously inside the `visibilitychange`-to-visible (or `pageshow`) handler — wrap the first resume fetch in `setTimeout(fn, ~150–250ms)` to avoid the confirmed iOS `fetch` "Load failed" bug (`TypeError`, ~20–40s failure window; Apple Forums thread 771127). Retry once after a further delay on failure. `[ASSUMED]` exact delay + whether it still reproduces on iPadOS 26.x → measure on device Wave 0.
- **Freshness is server-timestamp-driven, NOT tick-driven:** the `/preview` sidecar already exposes the monotonic `gen` token. The client records a `resumeAt` on wake; a tile may render LIVE only once a frame whose `gen` post-dates `resumeAt` arrives. Any frame older than a staleness window → visible `STALE/RECONNECTING` overlay, never "live". (`gen`-gating already exists in `console.html`; extend it with the resume semantics.)
- **`?t=<gen>` nonce is the load-bearing refresh mechanism — NOT `Cache-Control: no-store`.** **CORRECTED PREMISE:** Safari is a documented outlier (Apple Forums 730319) that places `no-store` pages into bfcache and may restore a frozen image without refetching. `no-store` is necessary but **not sufficient** on Safari; the per-request unique `?t=<gen>` URL is what guarantees a fresh decode.
- **On hide:** `clearInterval` (or down-shift) the poll when `visibilityState==='hidden'`; record the hide time.
- **On resume** (`pageshow` `persisted===true` OR `visibilitychange`→visible): immediately mark ALL tiles stale + blank/dim; tear down the old interval and start a fresh one; clear the stale overlay per-tile only when a verified-fresh frame loads.
- **Foreground staleness WATCHDOG is MANDATORY and PRIMARY** (not the lifecycle hooks): Safari does NOT fire `pagehide` on the app-switch-then-kill path, and `pageshow.persisted` may be `false` under memory pressure (full reload, JS state reset). Run the `gen`-age-vs-local-clock staleness check on a foreground interval so a frozen frame is caught within one poll cycle even if NO lifecycle event fired. The page must reconstruct cleanly from `/status` on a COLD load.
- **Wake Lock (out of strict scope, note it):** Screen-Wake-Lock is Safari 16.4+; an installed-PWA bug was fixed in iOS 18.4; must be re-acquired on every `visibilitychange`→visible. If the console is added to the iPad Home Screen as a PWA and screen-on is required, ensure deploy iPadOS ≥ 18.4.

Sources: web.dev/articles/bfcache · developer.apple.com/forums/thread/771127 · /thread/730319 · MDN Page_Visibility_API · MDN pageshow_event / pagehide_event · caniuse wf-page-lifecycle · webkit.org/blog/16574 (Wake Lock).

---

## 2. Flicker-free, leak-free `<img>` refresh over a multi-hour soak (UXT-03)

**Verdict: CORRECTED (design sound; framing fixed).** Dominant risk = decoded-image memory growth. Each decoded JPEG costs `W×H×4` bytes regardless of file size; WebKit runs tiered memory pressure (≈65% "strict" → discards decoded data; 100% → kills/reloads the tab). iOS enforces a decoded-image/GPU ceiling (community-reported ~10MB GPU-image budget; newer devices a per-image area cap of 5,242,880 px). Absolute MB ceiling is **unpublished** → confirm via on-device soak; do NOT hard-code it.

**Contract clauses:**
- **Plain `?t=gen` src-swap on ONE persistent `<img>` per tile.** FORBID `fetch→Blob→URL.createObjectURL` for live tiles (historically leak-prone on older Safari 11–15; unnecessary complexity here — kept out on simplicity grounds, not a confirmed current leak).
- **Flicker control = `decode()`-before-swap** (NOT the `decoding` attribute, which does not prevent the empty-image flash): keep ONE reused off-DOM `Image()` preloader per tile created **once**; per tick `preloader.src = '/preview/<cam>.jpg?t='+gen; await preloader.decode(); visibleImg.src = sameUrl;`. On `decode()` reject (`EncodingError` when `src` superseded mid-decode, or request fail) skip the frame without throwing. `decoding="sync"` on the visible `<img>` is belt-and-suspenders (matches Safari/Chrome default).
- **Never `new Image()` per frame** — reassign the one preloader's `.src`. Steady state = at most 2 decoded bitmaps per tile.
- **`gen`-gating:** only swap when polled `gen` strictly > last rendered `gen`; never re-fetch the same `gen`.
- **Hidden/off tiles** (camera dropped to SAFE) → set `src` to a **1×1 transparent data-URI**, NOT `display:none` (a `display:none` eager `<img>` still holds fetched bytes + may hold a decoded bitmap until WebKit's pressure handler reclaims it; the data-URI deterministically frees it).
- **Memory-budget contract:** target ONE decoded bitmap per tile steady-state. Recompute `W×H×4` against the ACTUAL JPEG dimensions the orchestrator emits (640×360 ≈ 0.92MB/tile; 1280×720 quadruples it).
- **Soak acceptance test (UXT-03):** multi-hour 4-tile run on **physical iPad** hardware (simulators differ) proving flat tab memory (no monotonic growth) AND confirming the real ceiling + resume-after-sleep behavior.

Sources: MDN HTMLImageElement.decode · tunetheweb.com decoding-attribute · WebKit MemoryPressureHandler / webkit.org/b/158941 · GoogleChromeLabs/page-lifecycle#2 · MDN createObjectURL/revokeObjectURL.

---

## 3. Dog-lock bbox overlay (WHY-03) + landscape touch UX (UXT-01)

**Verdict: CORRECTED (two pillars VERIFIED HIGH; two citations fixed).**

**Bbox overlay (WHY-03) — VERIFIED HIGH, zero JS math:**
- Render one inline `<svg viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet">` per tile, positioned with the EXACT same box geometry (width/height/position, zero padding/border) as the tile's `<img style="object-fit:contain">`. `xMidYMid meet` (the default) letterboxes identically to `object-fit:contain`, so the normalized `[cx,cy,w,h]` becomes a plain `<rect x="cx-w/2" y="cy-h/2" width="w" height="h" vector-effect="non-scaling-stroke">` — **no JavaScript letterbox math in the live path**; the engine's meet-scaling IS the alignment guarantee.
- **Fallback** (only if SVG repaint ever proves problematic): div-with-% formula `s=min(Cw/imgW,Ch/imgH); Rw=imgW*s; Rh=imgH*s; ox=(Cw-Rw)/2; oy=(Ch-Rh)/2; left=ox+(cx-w/2)*Rw; top=oy+(cy-h/2)*Rh; width=w*Rw; height=h*Rh`, recomputed on resize+orientationchange+visibilitychange.
- Update geometry ONLY on `gen` advance (1–4 Hz). Animate via a CSS transform on a WRAPPER element + GPU-promote it (`translateZ(0)`/`will-change:transform`); promote only VISIBLE overlays (iOS renders promoted layers even off-viewport). Hide/grey the overlay whenever its tile is STALE (don't draw a stale box on a stale frame). The "fill/stroke mutation triggers full repaint" detail is `[ASSUMED]/LOW` — validate on device; at 1–4 Hz cost is negligible regardless.

**Touch UX (UXT-01) — VERIFIED HIGH:**
- Tap targets ≥ **44×44 CSS px** (Apple HIG, authoritative); destructive/critical controls + score steppers ≥48px; ≥8px inter-target spacing. The whole camera **tile** is the tap-to-force target (`role="button"`, visible `:active`).
- `touch-action: manipulation` on body/interactive elements kills double-tap-zoom AND the click delay (supported since Safari 13/iOS 13). Do NOT use the viewport meta to block zoom — iOS 10+ ignores `user-scalable=no`/`maximum-scale=1`. Viewport = `width=device-width, initial-scale=1, viewport-fit=cover`; pair `viewport-fit=cover` with `env(safe-area-inset-*)` padding so bottom controls clear the home indicator.
- `{ -webkit-user-select:none; user-select:none; -webkit-touch-callout:none; -webkit-tap-highlight-color:transparent }` on tiles/buttons/labels (NOT on the score numeric input); provide an explicit `:active` visual since the native highlight is removed.
- Bind force-camera + undo to the standard **`click`** event (Pointer Events only if hold/drag is ever needed). FORBID FastClick-style `touchstart`/`touchend` synthetic-click handlers — they double-fire live actions on current iOS.
- **Reachability** `[ASSUMED]` (HIG is qualitative): dock "Rilascia (auto)" undo + the one-handed score form to the **bottom-trailing thumb arc** with safe-area padding; keep freshness indicator + status read-outs at the top; make the side (left/right) configurable for grip; separate undo from score-confirm by ≥8–16px and give undo a large/confirmed target (it changes live program output).
- **Memory note (corrected citation):** the persistent-`<img>`/swap-`src`/1×1-data-URI strategy is kept but tagged `[ASSUMED]/MEDIUM`; the real constraint is the decoded-image/GPU ceiling (§2), not a removed-node deallocation bug — confirm via the on-device soak.

Sources: MDN preserveAspectRatio / object-fit / touch-action / user-select / Viewport_meta_tag · Apple HIG layout+accessibility · WCAG 2.5.8.

---

## 4. Accessible status color coding + score-preview fidelity (WHY-01/02/04, SCV-01)

**Verdict: CONFIRMED (color math + source-of-truth re-verified; 3 refinements).**

**Status encoding (WHY-01/02/04) — 3 redundant channels, never color alone (WCAG 1.4.1):**
- Each state = **hue + shape/icon + text label**, distinguishable in grayscale. Border-style is itself a non-color cue and is **load-bearing** (covers achromatopsia), not decorative:
  - **LIVE (auto)** = solid green border + ● + "LIVE"
  - **FORZATA (override)** = solid amber border + lock/pin icon + "FORZATA" + corner stripe/ribbon
  - **MORTO (dead feed)** = dimmed/desaturated tile (50–60% opacity) + ✕/no-signal + "MORTO"
  - **auto-wants (WHY-04)** = **dashed** blue outline + ▸ chevron + "auto →" tag
  - leaderboard sub-states: tracking = solid filled bar + ●; coast = hatched bar + ◐; lost = empty/outline bar + "··" + "lost"
- **Verified hues on dark panel `#11151c`** (contrast ratios recomputed with WCAG sRGB linearization): LIVE green `#34D399` (9.52:1) · FORZATA amber `#F0B429` (9.81:1) [or IBM `#FFB000` 9.99:1] · MORTO red `#FF6B6B` (6.59:1) [or `#F87171` 6.61:1] · auto-wants blue `#56B4E9` (7.93:1) · coast neutral `#9CA3AF` (7.21:1) · lost dimmed `#6B7280` (3.78:1 — non-text/de-emphasized only) · body text `#E6E9EF` (15.04:1). Green(LIVE)/red(MORTO) MUST also differ by border-style+icon+label (red-green is the primary CVD confusion axis). `[ASSUMED]` panel bg `#11151c` — re-run contrast if the implemented tile/panel bg differs (MORTO red + the 3.78:1 lost-gray have the least headroom). NOTE the existing console uses bg `#14161a`/danger `#b23b3b` — reconcile: keep the existing LIVE-red border language OR migrate to the verified palette; the UI-SPEC must pick one and state contrast for the chosen bg.
- **Contrast targets:** status/badge TEXT ≥4.5:1 (≥3:1 only if large ≥24px); borders/bar-fills/icons ≥3:1 (WCAG 1.4.3/1.4.11), no rounding. When a hue is borderline, render the LABEL in offwhite `#E6E9EF` and use the hue only on the border/badge.

**Leaderboard (WHY-02):** horizontal bars 24–32px tall, gap ≈ half bar height, fixed full-width track anchored at zero baseline, camera label left / proportional 0..1 fill / 2-decimal value right-aligned (e.g. `.81`), sorted highest-first. Bar fill treatment encodes state (solid green track / hatched amber coast / empty gray + "··" lost). Matches the approved mockup `①▓▓▓ .81 / ②▓▓ .40 / ③·· lost`.

**SCV-01 score-overlay preview — render CLIENT-SIDE, drift-guarded:**
- `render_overlay_text` (verified in `src/segugio/ui/score_render.py`) is exactly 3 deterministic f-strings: `disc_tf` → `"Prese: {prese}  Zona: {zona}  Totale: {totale}"`; `disc_freestyle` → `"{nome}  Timer: {timer}"`; `agility` → `"Tempo: {tempo} / SCT: {sct}  Faults: {faults}"`, with `_clean()` stripping CR/LF/control chars and capping at 64 (`_MAX_FIELD_LEN`), stdlib-only.
- **Mirror these 3 formats + the same sanitize in client JS**, debounce 150–250ms, for instant zero-latency feedback. Do NOT round-trip per keystroke (LAN spikes on contended WiFi couple feedback to the network) and **never** to the orchestrator. **Drift-guard:** on input `blur` AND on `submit`, call a tiny Flask render endpoint ONCE and assert `server === client`, surfacing a visible mismatch warning. **Wave-0 CI parity test:** feed identical `ScoreDoc`s to the Python fn and the JS mirror.

**Score form (UXT-01 one-handed):**
- All score `<input>` computed font-size ≥16px (the template already uses `1rem`; preserve it — never drop to 0.9rem on inputs) to block iOS focus-zoom. The threshold is the RENDERED size. FORBID `maximum-scale=1`/`user-scalable=no` (fails WCAG 1.4.4/1.4.10).
- Use `type="text"` + `inputmode`, **NEVER `type="number"`** — on iOS Safari `type=number` raises no numeric keypad and silently drops non-numeric input. integer fields (Prese, Totale, Faults) `inputmode="numeric"`; decimal fields (Tempo, SCT, Timer) `inputmode="decimal"` (template already does this). `enterkeyhint="next"` on all fields except the last; `"send"`/`"done"` on the final (iOS Safari 13.4+).
- **Italian decimal:** the iOS decimal keypad separator is unreliable per-locale (interchangeable comma/period; documented iPadOS 26.2+ regression inserts the wrong separator). The renderer is verbatim so display is safe, but any client-side numeric validation MUST accept BOTH `,` and `.`; instruct operators toward `.` in UI copy.

Sources: W3C WCAG22 (1.4.1/1.4.3/1.4.11/2.5.8) · Okabe-Ito palette · css-tricks 16px-form-zoom · MDN inputmode/enterkeyhint · soledadpenades.com (type=number on iOS) · developer.apple.com/forums/thread/818268 (decimal separator).

---

## 5. Wave-0 on-device validation checklist (the `[ASSUMED]` items)

These survived verification but are device/version-sensitive — confirm on the physical target iPad (iPadOS 26.x) before treating as proven:
1. iOS `fetch`-in-`visibilitychange` "Load failed" bug: still present on 26.x? exact safe `setTimeout` deferral (150 vs 250ms)?
2. Multi-hour 4-tile **memory soak** is flat (Web Inspector/Instruments); the real decoded-image/GPU ceiling for the target iPad.
3. Sleep/wake path: does app-switch vs device-lock produce `pageshow persisted===true` vs `visibilitychange`-hidden? (handle both).
4. `decode()`-before-swap is truly zero-flash on the target Safari build.
5. Overlay compositing: many promoted overlay layers don't grow memory over the soak (promote only visible).
6. Touch: no residual click delay with `touch-action:manipulation`; reachability of bottom-trailing controls with the actual operator grip/stand.
7. Score input: no focus-zoom at ≥16px; decimal separator behavior in it-IT.
8. Status palette contrast holds against the FINAL implemented panel/tile background (reconcile existing `#14161a` vs researched `#11151c`).
