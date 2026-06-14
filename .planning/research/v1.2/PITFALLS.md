# Pitfalls Research

**Domain:** OBS browser-source broadcast overlay served by a crash-isolated Flask console (multi-machine LAN), client-side run timer, transparent CEF compositing — added to Segugio (operator-less auto-director for dog sports), milestone v1.2
**Researched:** 2026-06-14
**Confidence:** HIGH (system-specific behaviors read from source; OBS/CEF behaviors web-verified MEDIUM/HIGH)

> Scope note: this file targets pitfalls of adding a *browser-source graphical overlay* to **this** system (crash-isolated console, opcomm file IPC, `0.0.0.0` LAN trust, UXT-03 freshness discipline, SCV-01 parity contract), not generic web-overlay advice. The four highest-risk are **clock skew** (Pitfall 1), **OBS caching/refresh** (Pitfall 2), **crash-isolation breakage** (Pitfall 3), and **stale-as-live** (Pitfall 4).
>
> (Supersedes the v1.0/v1.1 CV-direction PITFALLS for this milestone's research cycle.)

## Critical Pitfalls

### Pitfall 1: Run-timer clock skew across console-host vs OBS-host (HIGHEST RISK)

**What goes wrong:**
The client-side run timer is meant to "count by itself" from `run_started_at` + `running`. The browser source runs inside OBS's embedded CEF on the **OBS box**, which `docs/security.md` and the milestone context confirm may be a **different machine** than the console. If the timer is computed as `Date.now() - run_started_at` where `run_started_at` is the console host's wall clock, any clock offset between the two machines is injected directly into the displayed time — a broadcast timer that reads e.g. 4s wrong from the first frame, or counts from a negative/huge value. Two unsynchronized consumer machines on a field LAN with no NTP can easily differ by seconds to minutes.

Worse: there is **no `run_started_at` field today**. `RunState` (records.py) currently carries only `action`/`just_started`/`just_stopped` — no absolute start timestamp, no `running` boolean. The milestone goal says "dal `RunState` esistente" but that data does not exist yet; it must be added, and *whose clock stamps it* is the whole pitfall.

**Why it happens:**
The naive design stamps `run_started_at` on the console (server) and subtracts it against the browser's local `Date.now()` (a different machine's clock). Developers assume "one LAN = one clock." It is not.

**How to avoid:**
- Make the timer **clock-offset-free by construction.** The console publishes BOTH `run_started_at` AND a `server_now` taken on the **same** machine in the **same** `/overlay-json` response. The client computes `offset = server_now − clientNow` once per poll and renders `elapsed = (clientNow + offset) − run_started_at`. The console's clock cancels out; only intra-poll latency (sub-second) leaks, not the absolute machine offset. This is the standard NTP-style "server time + local tick" pattern and is the single most important design decision in this milestone.
- Alternatively publish **`elapsed_ms` precomputed by the console** each poll (server measures `now − start` on its own clock) and the client free-runs between polls with a local `performance.now()` delta. Both designs keep the OBS box's clock out of the math.
- NEVER compute `Date.now() - run_started_at` directly when `run_started_at` came from the other host.
- Use a **monotonic** local base for the inter-poll free-run (`performance.now()`), not `Date.now()` (which can step on OS time sync).
- Pause/zero the timer on `running === false` and on the `just_stopped` edge; on `just_started` re-seed from the fresh `run_started_at`.

**Warning signs:**
- Timer shows a non-zero value the instant a run starts, or jumps when the page reloads.
- Timer differs from the operator's console preview by a constant offset.
- Set the two machines' clocks deliberately ~30s apart in a test → a correct design shows ~0 error, a broken one shows ~30s.

**Phase to address:**
The phase that introduces the run timer + `/overlay-json` contract. This must be the FIRST timer task; the offset-cancellation scheme is a design precondition, not a polish item.

---

### Pitfall 2: OBS browser-source caching — overlay never reflects new code or new data

**What goes wrong:**
After you change the overlay HTML/CSS/JS (or the served data), OBS keeps showing the OLD version. CEF caches aggressively, and OBS's "Refresh cache of current page" button is effectively just an F5 reload — it does NOT reliably evict cached sub-resources (CSS/JS/fonts) and does not clear the on-disk CEF cache. Operators then "fix" things by editing files that OBS silently ignores, or ship a stale overlay to air. Two distinct caching layers bite: (a) CEF's HTTP cache for `http://console-host/overlay*`, and (b) CEF's page/render state.

There is also the **`/overlay-json` data refresh** problem: if the JSON is fetched without cache-busting and served without `no-store`, CEF may serve a cached body and the overlay freezes on stale scores while looking live.

**Why it happens:**
Browser sources are "set once, forget" in most OBS workflows. The Refresh button's name implies it clears cache; it does not. The console already learned this for preview JPEGs (`?t=<gen>` nonce + `Cache-Control: no-store`, app.py line 196) — the overlay must apply the SAME discipline and the team must not assume the browser source behaves like a normal browser tab.

**How to avoid:**
- Serve `/overlay` and `/overlay-json` with `Cache-Control: no-store` (mirror the existing `get_preview_jpg` header).
- Cache-bust the data fetch URL with a nonce (`/overlay-json?t=<gen-or-tick>`), exactly as the preview JPEG path already does — this is the **load-bearing** control, not `no-store` alone (the console.html comment at line 656 already notes Safari/CEF may cache a `no-store` resource).
- Do the data polling **inside the page JS** (one long-lived page, JSON re-fetched on a nonce), so the page itself never needs an OBS-level refresh once loaded — only code changes do.
- For code changes during setup, document the reliable refresh: delete `%appdata%\obs-studio\plugin_config\obs-browser\cache` before launch, OR bump a version query string on the source URL, rather than trusting the Refresh button. Put this in `docs/obs-setup.md`.
- If serving the overlay as a versioned URL, change the URL (`?v=2`) on each scene-collection update so a stale CEF cache can't win.

**Warning signs:**
- "I changed the CSS but OBS still shows the old colors."
- Scores update on the console preview but freeze on the OBS output.
- The overlay works after deleting the CEF cache folder but not after the Refresh button.

**Phase to address:**
The phase wiring `/overlay` + `/overlay-json` (apply no-store + nonce there) AND the scene-collection/docs phase (document the real refresh procedure).

---

### Pitfall 3: Breaking crash-isolation by importing something heavy to build the overlay

**What goes wrong:**
The console's HARD invariant (app.py docstring, D-03/RBT-04) is that it imports ONLY `Flask + segugio.opcomm` — never ultralytics/torch/cv2/cyndilib/obsws. An import test with the heavy stack ABSENT must stay green. Building a "nicer" overlay tempts adding a templating/asset/charting/timezone dependency (e.g. a server-side chart renderer, a date library imported at module top, `jinja2` extensions pulling transitive deps, or — most insidiously — `import segugio.config` to get cam ids/discipline). Any module-top import of something not in the leaf set, or anything that transitively drags in the heavy stack, silently breaks the isolation guarantee and a UI/overlay exception can now reach the director path.

**Why it happens:**
The overlay is "just rendering" so a dev reaches for a convenience lib without realizing the console is deliberately import-starved. The existing code already had to fight this: Flask is imported INSIDE `create_app` (not module top) and cam ids are passed as a plain arg, explicitly NOT via `import segugio.config` (app.py lines 68–79, 223–237).

**How to avoid:**
- Keep `/overlay` rendering **stdlib + Flask templating only**, exactly like `score_render.py` (which documents "stdlib only — no Flask, no numpy, no heavy deps" and is import-safe with the whole stack absent).
- Any new config-derived data (discipline, cam ids) must be **passed into `create_app` as plain args** or read from the opcomm channel — never imported from `segugio.config` at module top.
- Keep the crash-isolation import test in CI and ADD the overlay route module to it: import `segugio.ui` with torch/cv2/numpy/cyndilib/obsws/jinja-extras absent must still succeed.
- Do animations/timer/chart work **client-side in the browser** (CSS/JS), not server-side — this also serves the "publish-and-render, not compute" principle.
- The run timer is client-side; the console only publishes `run_started_at`/`server_now`/`running` from data it already has — zero new compute, zero new deps.

**Warning signs:**
- A new `import` appears at the top of any `segugio.ui` module.
- The import-isolation test starts requiring a package to be installed.
- `pip install segugio[console]` starts pulling numpy/torch transitively.

**Phase to address:**
Every phase that touches `segugio.ui`. Make the crash-isolation import test a **success criterion** of the first overlay phase and re-run it as a gate on each subsequent one.

---

### Pitfall 4: Stale/disconnected `/overlay-json` shown as "live" (the UXT-03 analogue)

**What goes wrong:**
If the console process dies, the opcomm `score.json`/`runstate.json` stops updating, or the OBS box loses the LAN, CEF keeps rendering the LAST overlay frame indefinitely — a frozen score/timer presented on-air as current. This is the exact failure class the project already fights everywhere: the NDI "75-minute frozen frame looks alive" gotcha, and the UXT-03 console rule "never show a frozen frame as live." A broadcast overlay frozen on a stale score is a credibility failure during a live competition.

**Why it happens:**
The overlay polls JSON and renders whatever it last got; absent a freshness signal it cannot tell "no change because nothing changed" from "no change because the source is dead." A running CSS timer makes it WORSE — the timer keeps ticking visually even after data goes stale, strongly implying liveness.

**How to avoid:**
- Publish a **monotonically advancing freshness token** in `/overlay-json` — reuse the existing `gen`/`tick` discipline from the preview channel (PreviewDoc already has `gen`/`tick`). The overlay tracks gen-age against its local clock exactly like console.html's `isStale()` (line 738) / `freshnessStamp()` (line 745).
- On stall past a window (mirror `STALE_MS = PUBLISH_MS * 3`), the overlay must **degrade**: stop the run timer from advancing (freeze it, don't let it free-run forever), and/or hide the score block, rather than display stale data as authoritative. Decide the broadcast-appropriate degrade (hide lower-third vs. dim it) — but it must NOT keep ticking as if live.
- Reuse the proven `?t=<gen>` nonce so a fetch that returns the same gen is correctly read as "no new frame," and apply the WR-02 cold-start guard (lastGen < 0 is NOT stale — the first frame simply hasn't arrived; never paint stale on first paint).
- Apply the UXT-03 sleep/wake lifecycle lessons (visibilitychange/pageshow, deferred resume fetch) IF the OBS box can sleep — usually it can't (a live production box), so this is lower priority than the gen-age watchdog, which is the PRIMARY signal.

**Warning signs:**
- Killing the console leaves the overlay showing the last score with the timer still counting.
- Pulling the OBS box's network cable does not change the overlay.
- No `gen`/`tick` in `/overlay-json`.

**Phase to address:**
The `/overlay-json` contract phase (publish gen/tick) and the overlay-client phase (gen-age watchdog + degrade behavior). Make "frozen overlay degrades, never shows stale-as-live" an explicit success criterion.

---

### Pitfall 5: Transparency setup — white flash on load, opaque background on air

**What goes wrong:**
Two failures: (a) the lower-third renders on an opaque (white/black) box instead of compositing over the program video, because the page background is not actually transparent or OBS is forcing a background; (b) a **white flash** when the source loads/reloads (scene activation, OBS launch, cache refresh) before CSS applies — a full-frame white flash over live video is a glaring broadcast defect.

**Why it happens:**
CEF defaults to an opaque white page background. `background: transparent` on a child element is not enough — the `html`/`body` must be transparent, and OBS's "custom CSS" default (`body { background-color: rgba(0,0,0,0); }`) must be present/not overridden. The flash happens during the unstyled window between document load and first paint of the (possibly external) stylesheet.

**How to avoid:**
- Set `html, body { background: transparent !important; margin: 0; }` in the overlay's own HTML, and keep the OBS browser-source default custom CSS (`body { background-color: rgba(0,0,0,0) !important }`). Verify the local file/page itself carries NO background image/color (the WP Reset/OBS-forum guidance).
- Inline the critical CSS (background + layout + initial hidden state) in a `<style>` in `<head>` so the first paint is already transparent — do NOT rely solely on an external stylesheet that loads a frame late. (Segugio already inlines all CSS in console.html — follow that pattern, single self-contained HTML.)
- Start the lower-third **hidden** (entrance animation reveals it) so even a delayed first paint shows nothing, never a white box.
- Test against a bright AND a dark program background; a wrong alpha shows as a faint gray box only over certain backgrounds (the v27 transparency-blend bugs in the OBS tracker).

**Warning signs:**
- A white rectangle blinks when switching to a CAM scene or after a refresh.
- The lower-third sits on a visible box rather than floating over video.
- Looks fine over black, shows a gray haze over bright grass (a disc-dog field is bright outdoor grass).

**Phase to address:**
The overlay HTML/CSS phase. Add "no white flash on scene activate/refresh; transparent over bright and dark backgrounds" to its visual acceptance.

---

### Pitfall 6: SCV-01 parity drift between console preview and the OBS overlay after "unification"

**What goes wrong:**
Today SCV-01 guarantees the console's score preview matches the OBS overlay byte-for-byte (a JS mirror of `render_overlay_text`, drift-guarded against `POST /score/preview`). The milestone "simplifies" SCV-01 by having console-preview and OBS-overlay **share one HTML renderer**. The trap: "unified" on paper, two divergent code paths in practice — e.g. the console embeds the overlay via an `<iframe>`/shared partial but the OBS browser-source loads a slightly different route, different CSS, different font, or the timer/animation logic differs. The operator's preview then lies about what airs. Removing the byte-exact JS mirror also removes the existing drift-guard, so drift becomes SILENT.

**Why it happens:**
"Share the renderer" is easy to claim and hard to enforce. Subtle divergence creeps in: the preview is sized differently, fonts resolve differently (system font in preview vs web font in OBS), or the preview renders a snapshot while OBS renders the animated/timer version.

**How to avoid:**
- Make the console preview load the **exact same `/overlay` route** the OBS browser-source loads (e.g. an `<iframe src="/overlay">` in the console, or both pointing at one self-contained template) — one renderer, one URL, no second copy.
- Keep a **drift/parity test** even after dropping the JS mirror: a test that asserts the console preview and the OBS-served overlay resolve to the same template + same `/overlay-json` shape. Don't delete the SCV-01 guard without a replacement check.
- Pin fonts so preview and OBS render identically (see Pitfall 8 — prefer a self-hosted/system font, no CDN).
- If the preview is a live iframe of `/overlay`, the timer/animation parity is automatic; if it is a re-implementation, you have re-created the very drift SCV-01 existed to prevent.

**Warning signs:**
- The overlay route HTML and the console-embedded preview are two separate files.
- The preview shows static text but OBS shows an animated/timer overlay.
- Fonts/spacing differ between the iPad preview and the OBS output.

**Phase to address:**
The phase that unifies SCV-01. Success criterion: one renderer/URL; an automated parity check replaces the retired byte-exact JS mirror.

---

### Pitfall 7: file:// local-file source vs http://console-host URL — wrong choice strands the data fetch

**What goes wrong:**
Two ways to wire the browser source, each with a failure mode:
- **`file://` local HTML on the OBS box**: the static HTML loads, but its `fetch('/overlay-json')` or `fetch('http://console-host/overlay-json')` is a **cross-origin request from a `file://` origin** — CEF blocks it (CORS / mixed-origin), so the overlay renders the template but never gets live data. It looks like it works (HTML shows) then never updates.
- **`http://console-host:8080/overlay` URL**: same-origin fetch of `/overlay-json` works cleanly, BUT now the overlay hard-depends on the console being reachable from the OBS box; if the console is down or the LAN drops, the source shows nothing/last-frame.

**Why it happens:**
`file://` feels simpler (drop an HTML file next to OBS, no server dependency) and the cross-origin block isn't obvious until the data won't load. Teams also mix them (local HTML that fetches a remote JSON) which is the worst case.

**How to avoid:**
- **Use the `http://console-host:8080/overlay` URL** so the page and its `/overlay-json` fetch are **same-origin** — this is the clean, CORS-free design and matches "served by the console" in the milestone goal. The console is already the live data source the OBS box depends on for cuts/scores, so this adds no NEW availability dependency beyond what the system already has.
- If a `file://` fallback is ever wanted, it must fetch from `http://console-host` AND the console must send permissive CORS headers (`Access-Control-Allow-Origin`) — but this re-opens a `0.0.0.0` route to arbitrary cross-origin readers (see Pitfall 10/Security). Prefer NOT to.
- Keep `overlay.txt` + the read-from-file TEXT source as the documented **degraded fallback** (SCR-01) for when the browser source / console is unreachable — this is already a milestone requirement; make sure the scene-collection keeps the text source present (hidden/below) so an operator can fall back without rebuilding scenes.
- Document the exact source URL in `docs/obs-setup.md` including the console host/IP and that the OBS box must be able to reach it (same LAN, AP client-isolation must still permit console↔OBS-box, per security.md).

**Warning signs:**
- Overlay HTML appears but data never updates (file:// CORS block).
- Overlay disappears entirely when the console restarts (no text-source fallback wired).
- The browser-source URL is a `file:///C:/...` path.

**Phase to address:**
The scene-collection + `docs/obs-setup.md` phase (choose http URL, wire text-source fallback) and the `/overlay-json` route phase (same-origin design).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Compute `Date.now() - run_started_at` directly (ignore clock skew) | Trivial timer code | Wrong on-air time whenever OBS box clock ≠ console clock; silent, hard to spot in dev (same machine) | **Never** — offset-cancellation is the design baseline (Pitfall 1) |
| Skip `no-store` + nonce on `/overlay-json` | Less code | OBS shows frozen scores; "works on my browser tab" but not in CEF | Never — reuse the preview JPEG discipline that already exists |
| Re-implement the overlay in the console preview instead of iframing `/overlay` | Quick visual preview | SCV-01 drift returns, silently (Pitfall 6) | Never without a replacement parity test |
| Add a date/chart/font lib to make the overlay nicer | Faster nice-looking overlay | Can break crash-isolation if it (transitively) drags heavy deps or imports at module top | Only if stdlib-pure AND covered by the import-isolation test |
| Ship a CDN web font | Pretty typography | Font-load flash + offline failure on a field LAN with no internet (Pitfall 8/UX) | Never on a no-internet field LAN — self-host or use system fonts |
| Let the run timer free-run forever once started | Smooth ticking | Keeps "counting" after the data source dies → stale-as-live (Pitfall 4) | Never — freeze on stale/stop |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OBS browser source (CEF) | Trusting "Refresh cache of current page" to load new CSS/JS | It's just F5; bump a `?v=` on the URL or clear `%appdata%\obs-studio\plugin_config\obs-browser\cache`; poll data in-page via nonce so no manual refresh is needed (Pitfall 2) |
| OBS browser source transparency | `background: transparent` on a div only | `html, body { background: transparent }` + keep OBS default custom CSS `body{background-color:rgba(0,0,0,0)}`; no page background anywhere (Pitfall 5) |
| OBS source visibility settings | Leaving "Shutdown source when not visible" + "Refresh browser when scene becomes active" ON | "Shutdown when not visible" destroys the page when its scene isn't program → re-init flash + lost timer state on every CAM cut (the overlay is in EVERY CAM scene, cuts are frequent). Turn it OFF so one persistent page free-runs. "Refresh when scene becomes active" re-runs the entrance animation on every cut — usually want it OFF too. Set both deliberately in the scene-collection JSON. |
| OBS scene-collection JSON | Hand-editing the exported JSON and breaking `Camera.obs_scene` name lockstep | `tests/test_scene_template.py` already keeps scene names in lockstep; extend it to assert the browser source exists in each CAM/SAFE scene with the agreed URL + transparency + shutdown=false settings |
| opcomm RunState | Assuming `run_started_at`/`running` already exist | They do NOT (records.py) — add them; decide they are stamped on the console's clock and published with `server_now` (Pitfall 1) |
| Flask threading | A polling overlay GET pinning the worker | Already mitigated (`threaded=True`/Waitress, UXT-02) — keep it; verify the new `/overlay`+`/overlay-json` polling can't starve `/command` (Security table) |
| cross-origin fetch | `file://` overlay fetching `/overlay-json` | Serve the overlay from `http://console-host` so the fetch is same-origin (Pitfall 7) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Always-running CSS animations in CEF on a transparent full-frame source | OBS encode/render lag, GPU spikes, dropped frames, fan ramp on the production box | Animate only on EVENTS (score-change pulse, run start/stop entrance/exit) — NOT a perpetual loop; use `transform`/`opacity` (compositor-only) not layout/paint props; the run timer is a 1Hz `textContent` update, not an animation; size the source to the overlay region, not full 1080p of empty transparent pixels if avoidable | Worse on a laptop GPU (the project already flags thermal throttling on the RTX 4000 Ada Laptop — the OBS box may share the GPU with NVDEC/encode) |
| Polling `/overlay-json` too fast | Extra load on the contended field WiFi + console worker | Poll at the publish cadence (~5fps / 200ms, matching PUBLISH_MS) not 60fps; only re-render on a gen advance (the console.html `p.gen > lastGen` gate already models this) | When the AP is saturated by 3–4 NDI HX feeds; overlay polling must not compete with feed bandwidth |
| `requestAnimationFrame` timer loop running while data is stale | CPU burn + the stale-as-live problem | Drive the timer off the gen-age watchdog; freeze on stale (Pitfall 4) | On long idle stretches between runs |
| Heavy reflow on every score update | Layout thrash, flicker (FOUC) | Update text in place; pre-size the lower-third; animate with transform/opacity only | At high score-update frequency |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Adding `/overlay` + `/overlay-json` on `0.0.0.0` without re-confirming the trust posture | Another route exposing live competition scores/run state to anyone on the LAN (Information Disclosure, the T-08-03 class) | Reaffirm the security.md posture: dedicated AP with client isolation, no internet bridge; the new routes inherit the same LAN-trust boundary — write a one-paragraph threat re-eval like the v1.1 one. Scores are less sensitive than the live video already exposed, so the blast radius does not grow, but document it. |
| Enabling permissive CORS (`Access-Control-Allow-Origin: *`) to make a `file://` overlay work | Any cross-origin page/script on the LAN can scrape live scores | Don't — use same-origin http overlay (Pitfall 7). If CORS is ever needed, scope it to the OBS box origin, not `*`. |
| The new routes letting overlay polling starve the safety-critical `/command` POST | Operator override becomes unanswerable while OBS hammers `/overlay-json` | Keep `threaded=True`/Waitress (already a HARD UXT-02 control); add a concurrency test that an `/overlay-json` poll storm never blocks `/command` (extend the existing UXT-02 test) |
| Reflecting operator-entered score fields into the overlay HTML without escaping | HTML/JS injection into the broadcast overlay (the overlay is HTML now, not plain text) | The TEXT path already sanitizes via `render_overlay_text` (`_clean`, T-05-05-02). The HTML overlay MUST escape values for the HTML context (Jinja autoescape ON, or escape in JS via `textContent` not `innerHTML`) — the plain-text `_clean` is NOT sufficient for an HTML sink. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| FOUC / flicker when the score data updates | Lower-third blinks/jumps on every score entry | Update text in place; animate the pulse with transform/opacity; don't rebuild the DOM node |
| Web-font loading flash (FOIT/FOUT) | Text reflows / blinks to a different font a frame after load — visible on air | Self-host the font (no internet on field LAN), preload it, set `font-display: swap` or use a system font; inline `@font-face`. Match the font the console preview uses (Pitfall 6) |
| Entrance animation replays on every CAM cut | The lower-third "flies in" again each time the director cuts cameras (frequent) | Persistent single page + "Shutdown when not visible"/"Refresh on activate" OFF so the overlay survives cuts; animate entrance only on run start, not scene activation |
| Timer keeps counting after the run is stopped or data goes stale | Viewers see a live-looking timer that is wrong | Freeze on `running===false`/`just_stopped` and on stale (Pitfalls 1, 4) |
| Lower-third illegible over bright grass | Outdoor disc-dog field is bright; thin white text vanishes | Add a backing scrim/shadow (the console already uses `text-shadow` on its stale overlay); test over real field footage from the Pexels fixtures |

## "Looks Done But Isn't" Checklist

- [ ] **Run timer:** Often missing the server-time/offset-cancellation — verify it reads ~0 error when the two machine clocks are deliberately set ~30s apart (Pitfall 1).
- [ ] **`/overlay-json` freshness:** Often missing a `gen`/`tick` token + degrade — verify killing the console FREEZES the timer and degrades the overlay, never shows stale-as-live (Pitfall 4).
- [ ] **Caching:** Often "works in a browser tab" but stale in CEF — verify in the actual OBS browser source that a score change and a CSS change both appear (Pitfall 2).
- [ ] **Crash-isolation:** Often broken by a new import — verify the import-isolation test (heavy stack absent) is still green AFTER the overlay work (Pitfall 3).
- [ ] **Transparency:** Often a white flash on scene activate/refresh — verify no flash over live video, transparent over both bright and dark backgrounds (Pitfall 5).
- [ ] **SCV-01 unification:** Often two diverging renderers — verify console preview iframes/serves the SAME `/overlay` URL and a parity test exists (Pitfall 6).
- [ ] **Source wiring:** Often a `file://` source whose data never loads — verify the browser source uses `http://console-host:8080/overlay` and data updates live (Pitfall 7).
- [ ] **Text fallback:** Often dropped during "upgrade" — verify `overlay.txt` + the read-from-file text source still present in the scene collection as the SCR-01 degraded fallback.
- [ ] **OBS source settings:** Often left at defaults — verify "Shutdown source when not visible" and "Refresh when scene becomes active" are deliberately set in the scene-collection JSON.
- [ ] **HTML injection:** Often the plain-text `_clean` is reused for an HTML sink — verify score values are HTML-escaped (autoescape / `textContent`).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Clock-skew timer wrong on air | LOW (once detected) | Switch to server-time + offset cancellation; add `server_now` to `/overlay-json`; re-test with skewed clocks. Operationally, NTP-sync both boxes as a stopgap. |
| OBS showing stale overlay code/data | LOW | Add `no-store` + URL nonce; clear CEF cache folder; bump `?v=` |
| Crash-isolation broken by an import | LOW–MEDIUM | Move the import inside the entrypoint/`create_app`, pass config as args, or drop the lib; re-run the import-isolation test |
| Stale-as-live on air | MEDIUM (reputational if it happened live) | Ship the gen-age watchdog + degrade; until then, operator falls back to the `overlay.txt` text source |
| SCV-01 drift discovered | MEDIUM | Re-unify on one `/overlay` URL; add the parity test that replaces the retired JS mirror |
| White flash on cut | LOW | Inline critical CSS, start hidden, turn OFF shutdown/refresh-on-activate |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls. (Phase numbering continues from v1.1; v1.2 starts at Phase 10. Names below are indicative groupings, not fixed numbers.)

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Run-timer clock skew | First timer / `/overlay-json` contract phase | Timer ~0 error with machine clocks set 30s apart |
| 2. OBS caching/refresh | `/overlay`+`/overlay-json` route phase + scene-collection/docs phase | Score change AND CSS change both appear in the real OBS source |
| 3. Crash-isolation breakage | Every `segugio.ui` phase; gate from the first overlay phase | Import-isolation test green with heavy stack absent |
| 4. Stale-as-live | `/overlay-json` (publish gen) + overlay-client phase | Killing the console freezes timer + degrades overlay |
| 5. Transparency / white flash | Overlay HTML/CSS phase | No flash on activate/refresh; transparent over bright+dark |
| 6. SCV-01 drift | SCV-01 unification phase | One renderer/URL; automated parity test replaces the JS mirror |
| 7. file:// vs http source | Scene-collection + docs phase | Source uses http URL; data updates live; text fallback wired |
| Always-on CSS animation perf | Overlay HTML/CSS phase | OBS render/encode stable with overlay active (no dropped frames) |
| `0.0.0.0` data exposure / CORS | `/overlay-json` route phase | One-paragraph threat re-eval appended to docs/security.md |
| Polling starves `/command` | Route phase | Extend the UXT-02 concurrency test to `/overlay-json` |
| HTML injection of score fields | Overlay HTML/CSS phase | Score values HTML-escaped (autoescape/textContent) |

## Sources

- `src/segugio/ui/app.py`, `src/segugio/ui/templates/console.html`, `src/segugio/ui/score_render.py`, `src/segugio/opcomm/records.py`, `src/segugio/opcomm/channel.py` (read directly) — existing crash-isolation contract, `?t=<gen>`+`no-store` preview discipline, UXT-03 `isStale`/`freshnessStamp` watchdog, SCV-01 byte-exact mirror, `RunState` has NO `run_started_at`/`running` today — **HIGH**
- `.planning/PROJECT.md`, `docs/security.md`, `docs/obs-setup.md` — LAN-trust posture, `0.0.0.0` no-auth accepted decision, NDI "frozen-frame-looks-alive" gotcha, scene-name lockstep test, read-from-file text source as fallback — **HIGH**
- OBS Forums / OBS Studio + obs-browser issue trackers — "Refresh cache of current page" is effectively F5 and does not clear sub-resource/disk cache; clear `%appdata%\obs-studio\plugin_config\obs-browser\cache`; local-file source reads stale cache — **MEDIUM/HIGH**
- WP Reset + OBS Forums (browser-source transparency) — `html/body` must be transparent, OBS default custom CSS `body{background-color:rgba(0,0,0,0)}`, white-flash from default white page background / late CSS — **MEDIUM**
- General CEF/NTP-pattern knowledge — server-time + local-tick offset cancellation for cross-machine timers; same-origin vs file:// CORS fetch behavior — **MEDIUM/HIGH**

Reference links:
- [OBS Forums — local file browser source](https://obsproject.com/forum/threads/why-doesnt-the-local-file-work-with-a-browser-source.194083/)
- [AuctionsLive — Refresh OBS browser cache](https://auctionslive.com/en/knowledge-hub/refresh-obs-browser-cache)
- [OBS Forums — auto-refresh browser source cache](https://obsproject.com/forum/threads/how-to-automaticcaly-refresh-cache-of-browser-source.129093/)
- [WP Reset — transparent browser source in OBS](https://wpreset.com/how-to-make-browser-source-transparent-in-obs-studio/)
- [OBS Forums — make browser source background transparent](https://obsproject.com/forum/threads/how-to-make-the-background-of-a-browser-source-transparent.165226/)
- [obs-browser #443 — transparency blend](https://github.com/obsproject/obs-browser/issues/443)
- [obs-studio #5347 — alpha channel rendering](https://github.com/obsproject/obs-studio/issues/5347)

---
*Pitfalls research for: OBS browser-source broadcast overlay on the Segugio crash-isolated console (v1.2)*
*Researched: 2026-06-14*
