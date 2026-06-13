# Pitfalls Research

**Domain:** Live camera preview + richer operator UI added to a crash-isolated auto-director, served over contended WiFi to a tablet (Segugio v1.1 "Console Regia — visibilità live")
**Researched:** 2026-06-13
**Confidence:** HIGH (grounded in the actual repo code — `orchestrator/loop.py`, `opcomm/atomic.py`, `opcomm/channel.py`, `ui/app.py` — plus verified NDI HX3 / Flask-streaming facts)

> **The three invariants every pitfall here protects.** v1.1 must preserve what v1.0 earned:
> 1. **RBT-04 — "nessun crash ammesso."** The director (`Orchestrator`) NEVER exits; the console is a SEPARATE process importing only `Flask + segugio.opcomm` (lazy-import boundary verified in `loop.py:46-49` and `ui/app.py:9-11`).
> 2. **WiFi contention is the dominant domain risk.** 3-4 phones already push **20-50 Mbps each of NDI HX3** (verified) over the dedicated LAN — 60-200 Mbps of contended traffic before the console sends a single preview byte.
> 3. **The director's fixed-rate tick is sacred.** Everything the operator sees must be published OFF the critical path of `_tick_once` (`loop.py:492-540`).

---

## Critical Pitfalls

### Pitfall 1: Frame encoding/serving on the director's tick (blocking the critical path)

**What goes wrong:**
The "obvious" way to get a preview is to JPEG-encode the latest frame inside the loop — e.g. add `cv2.imencode(...)` per camera inside `_fan_out`/`_tick_once`, or expose a frame getter the Flask process calls synchronously into the orchestrator. Either way, encode/serve work lands on the fixed-rate tick. At 4 cameras × ~30 Hz, JPEG-encoding 4 frames per tick adds 5-20 ms of pure CPU to a budget that is already measured at **p95 ~256 ms** (Phase 6, RBT-05) and **spikes to ~546 ms heat-soaked** on the laptop GPU. The tick blows its period, switching gets sluggish, and the core value ("la camera giusta al momento giusto") degrades — the exact thing that must never fail.

**Why it happens:**
Preview feels like a "read-only" feature, so developers assume it's free. But any synchronous work on the tick — encode, disk write with `fsync`, a socket `send()` that blocks on a saturated NIC — serializes into the decision latency.

**How to avoid:**
- **Publish frames on a SEPARATE thread/cadence, never the tick.** The tick's only job re: preview is a cheap, non-blocking hand-off of a numpy reference (or a triple-buffer swap) to a publisher thread. The orchestrator already runs supervised threads (`loop.py` docstring §robustness) — add a preview-publisher thread that pulls `source.latest(cam)` independently of the decision tick.
- **Decouple the preview frame rate from the AI tick rate.** Preview at 5-10 fps and a smaller resolution is plenty for an operator; the AI tick stays at 30 Hz untouched.
- **Wrap the hand-off in try/except that can only drop a frame, never raise** into `_tick_once` (mirror the RBT-04 pattern: a failed publish coasts, the tick continues).
- **Re-run the RBT-05 latency harness (`run_measured`) with preview enabled** and assert p95 is unchanged within noise. This is the gate.

**Warning signs:**
- p95 tick latency rises when the console is open vs. closed.
- `cv2`/`imencode`/socket calls appear anywhere reachable from `_tick_once`.
- The decision loop's measured `total` correlates with the number of connected browser tabs.

**Phase to address:** Frame-publishing-channel phase (first preview phase) — establish the off-tick publisher BEFORE any encoding exists.

---

### Pitfall 2: Coupling the console back to the orchestrator (breaking RBT-04 isolation)

**What goes wrong:**
To get frames, someone imports a heavy module into the Flask process — `import cv2` for `imencode` in `ui/app.py`, or `from ..orchestrator.loop import Orchestrator` to "just grab the frame", or pulls in `numpy`/`ultralytics`/`cyndilib` transitively. The console is no longer crash-isolated: a cv2/torch segfault, a numpy version clash, or an OOM in the UI process now shares a fault domain with — or worse, is the same process as — the director. The verified contract (`ui/app.py:9-11`: "imports ONLY Flask + `segugio.opcomm` — never ultralytics/torch/cyndilib/obsws/cv2") is silently violated, and the whole v1.0 isolation guarantee evaporates.

**Why it happens:**
JPEG encoding "naturally" wants cv2/PIL/numpy. The path of least resistance is to add the import where the HTTP handler lives.

**How to avoid:**
- **Do the encoding on the ORCHESTRATOR side** (it already owns cv2/numpy) and pass the console only finished JPEG bytes — via files in the opcomm dir or an MJPEG endpoint the orchestrator serves. The console stays a dumb file/stream relay.
- **Keep the `import segugio.ui` Flask-free + heavy-free guarantee under test.** v1.0 already proves `import segugio.opcomm` succeeds with the heavy stack absent; add a regression test that **importing the console package raises ImportError-free with cv2/torch/numpy/cyndilib uninstalled** (or asserts they are never imported). This is the canary that catches coupling at CI time, not in the field.
- **If the console must decode anything**, restrict it to `Pillow`-free, cv2-free formats the browser handles natively (raw JPEG/PNG passthrough). The browser decodes; the console never does.
- **Decide the boundary topology explicitly:** option A — JPEG files in opcomm dir (console serves bytes via `send_file`, zero image libs); option B — orchestrator hosts its own MJPEG/WS endpoint on a different port and the console just links/embeds it (full process isolation, two servers). Prefer A or B over "import into the UI."

**Warning signs:**
- Any non-`flask`/non-`segugio.opcomm` import appears in `ui/`.
- `pip uninstall opencv-python torch numpy` breaks the console's startup or tests.
- The UI process RSS grows into hundreds of MB (a sign torch/cv2 got pulled in).

**Phase to address:** Frame-publishing-channel phase — the boundary decision is the FIRST design choice; everything else depends on it.

---

### Pitfall 3: Naive MJPEG/WebSocket multiview competing with NDI HX3 on the saturated WiFi

**What goes wrong:**
A multiview that pushes 4 cameras at full res/fps as MJPEG or binary WebSocket adds **tens of Mbps of new traffic onto a LAN already carrying 60-200 Mbps of NDI HX3** (verified: HX3 1080p ≈ 20-50 Mbps **per phone**, ×3-4 phones). The new traffic *contends with the phone uplinks*, inflating NDI jitter — which the locked research already names the #1 domain risk and which directly causes feed-death false positives and SAFE degrades. The preview feature you added to *help* the operator makes the *director itself* worse on the very network it has to survive.

**Why it happens:**
MJPEG is trivially easy to wire up in Flask, and developers test it on a quiet dev LAN where 40 Mbps of preview is invisible. The contention only appears with 3-4 phones live on the field WiFi — i.e. never in dev.

**How to avoid:**
- **Treat the preview byte budget as a first-class, capped resource.** Pick a hard ceiling (e.g. ≤ 5-8 Mbps total for ALL preview, well under the WiFi headroom left after NDI) and engineer to it: low fps (3-8), downscaled thumbnails (e.g. 320-480px wide), aggressive JPEG quality (50-70).
- **Single active preview by default, multiview on demand.** The operator usually needs the live cam + thumbnails of the rest, not 4 full streams. Serve full-rate preview only for the focused camera; serve the others as low-rate thumbnails.
- **Pull, don't push, and let the tablet set the pace.** Prefer `<img>` polling / `multipart` MJPEG the browser naturally throttles over an unbounded server-push WebSocket that floods a slow client (see Pitfall 8 backpressure).
- **Make preview degrade first, the director never.** Preview is the lowest-priority traffic; if WiFi is saturated, the operator gets a slower preview — the AI loop must not even notice. Never let preview traffic share a code path or buffer that can stall ingest.
- **Test on the contended network, or simulate it.** A field-representative test = phones live + console open; measure NDI jitter and feed-watchdog false-deaths with preview ON vs OFF.

**Warning signs:**
- Feed-watchdog SAFE degrades increase when the console is open.
- NDI frame-arrival jitter rises with the number of connected browsers.
- Preview bitrate is "whatever cv2 produces" rather than a configured cap.

**Phase to address:** Multiview/streaming phase — bandwidth budget is a stated acceptance criterion, validated on a contended (or simulated-contended) network.

---

### Pitfall 4: Torn / stale / non-atomic JPEG reads (and the wrong atomicity primitive for big binaries)

**What goes wrong:**
Two distinct failures:
1. **Torn reads** — the orchestrator writes `cam1.jpg` with a plain `open(..., "wb")` while the console reads it; the browser shows a half-written, garbled, or zero-byte frame (gray/broken-image flashes). The repo *already solved this* for small JSON/text (`atomic.py`: temp + fsync + `os.replace`, with a documented Windows `MoveFileEx` sharing-violation retry) — but JPEGs are a *new, larger, binary* payload and the lesson must be re-applied, not assumed.
2. **Stale frames** — a crashed/paused publisher leaves the last JPEG on disk; the console keeps showing a frozen image that *looks live*. This is the exact NDI "75-minute frozen frame" gotcha (PROJECT.md context) re-appearing one layer up: a frozen preview lies to the operator about what's on air.

**Why it happens:**
`os.replace` atomicity is easy to forget for binary files; and `fsync` on a 50-200 KB JPEG every few frames is *heavier* than on a tiny JSON, tempting a non-atomic shortcut "for performance."

**How to avoid:**
- **Reuse the existing atomic write for the swap** (`atomic_write_*` pattern: same-directory temp → `os.replace`, with the Windows retry already implemented in `_atomic_replace`). Add an `atomic_write_bytes` sibling rather than inventing a new path. The reader (console `send_file` or the MJPEG relay) then never sees a partial JPEG.
- **Reconsider `fsync` for preview frames specifically.** Durability across a crash is irrelevant for an ephemeral preview frame (unlike a score that must survive). Dropping `fsync` for thumbnails (keeping the atomic `os.replace`) removes IO-thrash while keeping tear-free reads. Make this an explicit, documented decision — atomicity YES, durability NO, for preview only.
- **Stamp every preview frame with a monotonically increasing tick/timestamp and surface freshness in the UI.** If a frame's age exceeds a threshold, the console grays it out / shows "feed stale" — never a confidently-frozen image. Tie this to the existing `DirectorStatus.alive` map so preview-staleness and feed-death tell the same story.
- **Mirror the leading-dot same-directory temp convention** (`atomic.py:_temp_path`) so concurrent writers to `cam1.jpg`/`cam2.jpg` never collide and temps stay hidden.

**Warning signs:**
- Broken-image icons or gray flashes in the browser under load.
- The preview shows a confident image while `DirectorStatus.alive[cam]` is False.
- Any `open(path, "wb")` writing a preview file without going through the atomic swap.

**Phase to address:** Frame-publishing-channel phase (atomic binary write + freshness stamping land with the channel itself).

---

### Pitfall 5: JPEG files bloating / IO-thrashing the opcomm dir

**What goes wrong:**
The opcomm dir is currently a handful of tiny JSON/txt files swapped occasionally. Dropping 4 cameras × several-fps JPEGs into it turns it into a high-churn binary scratch space: hundreds of file writes/sec, temp files (`.cam1.jpg.tmp`) churning, possible accumulation if naming uses timestamps/tick-ids instead of overwriting a fixed name, and `fsync` storms competing with the *important* atomic writes (score/command/status) that the director and OBS depend on. On a slow SD card / USB stick (common on field machines) this IO contention can stall the score/command/status writes — coupling preview IO to the director's control channel, the thing isolation was supposed to prevent.

**Why it happens:**
The opcomm dir is the established channel, so "just put thumbnails there too" feels consistent. But it conflates a *control* channel (low-rate, durable, critical) with a *media* channel (high-rate, ephemeral, droppable).

**How to avoid:**
- **Fixed filenames, overwrite-in-place — never timestamped/tick-suffixed preview filenames.** `cam1.jpg` is always overwritten via atomic swap; there is nothing to clean up and the dir can't grow unbounded. (Timestamped names are the classic "fills the disk overnight" bug.)
- **Separate the media dir from the control dir** (e.g. `opcomm/preview/` or a distinct `preview_dir` config key), so high-rate JPEG churn and the temp files it spawns never contend on the same directory inode / fsync path as `score.json`/`command.json`/`status.json`. The console still reads from a known location; the channels stay independent.
- **Prefer a RAM-backed location where available** (tmpfs on Linux, or simply accept the OS page cache) so preview writes don't hit slow flash. Document that preview frames are ephemeral and safe to lose.
- **Bound the write rate at the source** (publisher cadence cap, Pitfall 1) so the dir sees ≤ N writes/sec by construction.
- **Drop `fsync` for preview** (see Pitfall 4) — the dominant IO-thrash cost is the fsync, not the write.

**Warning signs:**
- opcomm dir size grows over a session, or `.tmp` files accumulate.
- Score/command/status writes slow down or log Windows `PermissionError` retries more often when preview is active (control channel starved by media IO).
- `iostat`/disk-busy spikes correlated with preview fps.

**Phase to address:** Frame-publishing-channel phase — directory layout + overwrite-in-place + rate cap are part of the channel's definition.

---

### Pitfall 6: 0.0.0.0 no-auth exposure widening from "panel" to "live camera feed of the venue"

**What goes wrong:**
v1.0 documented `bind 0.0.0.0:8080` with no auth as an ACCEPTED decision (`ui/app.py:16-19`, threat T-05-05-04): the LAN is the trust boundary for a tiny control panel. v1.1 changes the *stakes* of that same exposure: anyone who joins the dedicated WiFi (or a misconfigured AP that bridges to a guest/venue network) now gets a **live video feed of the field and competitors**, plus override control. A control panel leaking is annoying; a live camera feed of minors/competitors leaking is a privacy/GDPR and reputational incident. The bind didn't change, but the blast radius did — and the v1.0 "no auth is fine" rationale was written before there were frames behind it.

**Why it happens:**
The decision was made and documented once; nobody re-evaluates it when the payload behind the endpoint changes from "a few buttons" to "live video + control."

**How to avoid:**
- **Re-affirm or revise the threat decision explicitly for v1.1**, in writing, now that the endpoint serves video. Don't let the old "accepted" silently carry over.
- **Harden the network assumptions, not necessarily add a login.** Cheapest high-value mitigations for a field tool: WPA2/WPA3 on the dedicated AP with a non-default passphrase; **no bridge from the dedicated VLAN to any internet/guest network**; document "this AP must be physically/RF-scoped to the crew."
- **If any auth is added, make it tablet-friendly and crash-safe:** a single shared token in the URL or a one-field passphrase gate — never something that can block/raise into the control POSTs (override must always work). Keep it in the Flask layer; it must not touch the director.
- **Consider binding preview to the LAN interface only, not 0.0.0.0**, if the host has a separate uplink — so a misconfigured second NIC doesn't expose video to a wider network.
- **Treat recorded/buffered preview frames as personal data**: don't persist them beyond the ephemeral overwrite-in-place file; no preview history on disk.

**Warning signs:**
- The dedicated AP has internet uplink / is bridged to a venue network.
- Preview frames are written to a persistent/timestamped path (a retention surface).
- The v1.1 plan reuses the v1.0 security note verbatim without re-evaluating video.

**Phase to address:** Multiview/streaming phase (the phase that introduces video behind the endpoint) — security re-evaluation is an acceptance criterion there.

---

### Pitfall 7: Flask dev server WITHOUT `threaded=True` — one MJPEG stream freezes the whole console (including override)

**What goes wrong:**
The current entrypoint is `create_app(_dir).run(host="0.0.0.0", port=8080)` (`ui/app.py:143`) — **no `threaded=True`**. The Werkzeug dev server is single-threaded by default: it handles ONE request at a time. An MJPEG `multipart/x-mixed-replace` response (or a long-poll, or a WebSocket) is a **connection that never returns** — it holds the single worker forever. The instant the tablet opens the multiview, **every other request blocks**: `/status` polling stalls, and — critically — the **override POST (`/command`) cannot be served**. The operator hits "Forza CAM2" during a crucial moment and nothing happens because the lone worker is pinned streaming JPEGs. This is a documented, classic Flask-MJPEG failure ("set threaded=True because each MJPEG request will occupy a thread; without it other requests get stuck").

**Why it happens:**
The v1.0 console only ever had short request/response handlers, so single-threaded was invisible. Adding the first long-lived streaming response exposes it instantly — and it's silent in single-tab dev testing where you don't try to POST while streaming.

**How to avoid:**
- **Run threaded** (`threaded=True`) at minimum, and size it: every concurrent MJPEG/WS connection eats one thread. A tablet with multiview = several long-lived connections; budget threads accordingly (and cap concurrent preview connections).
- **Better: use a small production-grade WSGI server** (`waitress` is pure-Python, Windows-friendly, and matches the "produzione su Windows" constraint) so long-lived streams and control POSTs don't fight over a dev-server worker. The WSGI server import stays inside the entrypoint to preserve the lazy boundary.
- **Keep control endpoints non-blocking and prioritized:** `/command`, `/run`, `/score`, `/status` must always be answerable even while preview streams. The simplest guarantee is "streaming connections capped, control handlers fast and on their own threads."
- **Time-box / heartbeat MJPEG generators** so a dead tablet's abandoned stream connection is reaped and its thread returned (see Pitfall 8).
- **Add a test that POSTs `/command` WHILE a preview stream is active** and asserts the override is written promptly. This catches the freeze deterministically.

**Warning signs:**
- Override / status feels frozen exactly while preview is on screen.
- `app.run()` with no `threaded` / no WSGI server in the v1.1 entrypoint.
- Console responsiveness degrades with each additional open tab.

**Phase to address:** Frame-publishing-channel / streaming phase — the serving model (threaded WSGI + connection caps) is decided when the first streaming endpoint is added.

---

### Pitfall 8: Browser/tablet memory leaks and stuck connections on long-running multiview

**What goes wrong:**
A gara runs for hours with the multiview open on a tablet. Common slow-death modes:
- **`img.src` churn** — repeatedly setting `img.src` to new blob/object URLs (or `URL.createObjectURL`) without `URL.revokeObjectURL` leaks memory until the tablet browser tab is killed by the OS mid-event.
- **Unclosed WebSockets / EventSources** — reconnect logic that opens a new socket on each tablet sleep/wake without closing the old one, accumulating zombie connections that also pin server threads (compounding Pitfall 7).
- **Detached DOM / unbounded logs** — a "switch history" or per-tick status list that grows without a cap.
- **MJPEG connections that never reconnect after a stall** — the stream silently dies (WiFi blip) and the `<img>` shows a frozen last frame with no recovery, looking live (Pitfall 4 staleness, browser side).

**Why it happens:**
These only manifest after hours; dev/demo sessions are minutes long, so the leak never shows. Tablets have far less RAM than dev laptops and reap background tabs aggressively.

**How to avoid:**
- **Prefer `multipart/x-mixed-replace` MJPEG into a single static `<img>`** — the browser manages the stream and frame buffers natively, no per-frame JS object-URL churn to leak. This is the lowest-leak option for continuous preview.
- **If using JS-driven frames**, always `revokeObjectURL` the previous URL before assigning the next; reuse one `<img>` element; never append.
- **One WebSocket/EventSource, with idempotent reconnect:** close-then-reopen, guard against double-open, exponential backoff. Close on `visibilitychange`/`pagehide` and reopen on resume (tablet sleep, Pitfall 9).
- **Cap any history/log list** (ring buffer, e.g. last 50 switches).
- **Client-side staleness watchdog:** if no new frame within N seconds, show a "preview stale / reconnecting" overlay and actively re-establish the stream — never trust a frozen `<img>`.
- **Soak test:** leave the multiview open for hours (or a fast-forwarded equivalent) and watch tab memory + server thread count flatline, not climb.

**Warning signs:**
- Tablet tab memory grows monotonically over a session; the tab gets reloaded by the OS.
- Server thread/connection count climbs over time (zombie sockets).
- Preview freezes after a WiFi blip and never recovers without a manual refresh.

**Phase to address:** Multiview/tablet-restyle phase — leak hygiene + reconnect + soak test are acceptance criteria for the long-running UI.

---

### Pitfall 9: Tablet-specific reality — sleep/reconnect, viewport, wake-lock, and false "live"

**What goes wrong:**
The operator's tablet is not a desktop: it sleeps/dims to save battery (killing streams + WebSockets mid-event), has a small/variable viewport that a desktop-first layout breaks, may zoom/scroll the override buttons off-screen at the worst moment, and (Safari/iOS especially) throttles or suspends background tabs and rate-limits timers. After a sleep/wake, a naive client shows the **last frame frozen** and a **stale `/status`**, so the operator trusts a UI that's lying about what's on air — then issues an override based on stale information.

**Why it happens:**
Built and tested on a desktop browser; tablet power-management and viewport behavior are never exercised in dev.

**How to avoid:**
- **Design tablet-first, touch-first:** large hit targets for override/run, the live-cam + reason always visible without scrolling, responsive grid for multiview (the v1.1 "restyling tablet-friendly" feature — make it a hard requirement, not polish).
- **Request a Screen Wake Lock** (`navigator.wakeLock`) while the console is the active director surface, with graceful fallback; document "keep the tablet awake / disable auto-lock" in the run book as the belt-and-suspenders.
- **Robust resume:** on `visibilitychange`→visible / `pagehide`→`pageshow`, force a fresh `/status` fetch AND tear down + re-establish the preview stream/socket. Never render a pre-sleep frame as current.
- **Surface connection + freshness state prominently** (Pitfall 4/8): "LIVE" vs "stale/reconnecting" must be unmistakable on the tablet, because the operator acts on it.
- **Set the viewport meta + prevent accidental pinch-zoom** on control surfaces; test on the actual tablet model and orientation that will be used at the event.
- **Account for iOS Safari quirks** (MJPEG support gaps, background-tab suspension): if targeting iPad/Safari, validate the chosen preview transport on that exact browser, not just Chrome.

**Warning signs:**
- After the tablet sleeps, preview/status is frozen until manual refresh.
- Override buttons require scrolling or are mis-tappable on the real device.
- The layout was only ever opened on a desktop browser window.

**Phase to address:** Tablet-restyle phase — device + sleep/wake + wake-lock validated on the real tablet as acceptance criteria.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Encode JPEG inside the director tick | One fewer thread; "simple" | Inflates RBT-05 p95, risks blowing the period under heat-soak; couples preview to core value | **Never** — off-tick publisher is mandatory |
| `import cv2`/`numpy` into the Flask process for encoding | Quick MJPEG endpoint | Breaks RBT-04 crash-isolation; shared fault domain | **Never** — encode orchestrator-side, console relays bytes |
| Plain `open(path,"wb")` for preview JPEGs | Skips fsync/temp overhead | Torn frames, broken-image flashes, racey reads | **Never** — reuse the atomic swap (atomicity), but DO drop fsync (durability) for preview |
| Timestamped/tick-suffixed preview filenames | Easy frame history / debugging | Unbounded opcomm-dir growth, fills disk overnight | Only in a short, manually-cleaned debug session — never in the live tool |
| Preview JPEGs in the SAME dir as score/command/status | One channel, "consistent" | High-rate media IO starves the critical control channel | **Never** — separate media dir / RAM-backed |
| `app.run()` single-threaded with a streaming endpoint | Default; "works on my tab" | One stream freezes override + status | **Never** once a long-lived response exists — threaded WSGI required |
| Full-res 30fps multiview to "look good" in the demo | Impressive on a quiet LAN | Competes with NDI HX3 → director instability on the field | Demo on isolated LAN only; never the field default |
| Reuse the v1.0 "no-auth is fine" note unchanged | No work | Blast radius silently grew to live video of competitors | **Never** — re-evaluate explicitly for v1.1 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Orchestrator → console frame channel | Synchronous getter the console calls into the orchestrator process | Off-tick publisher writes atomic JPEG files / serves its own stream; console reads bytes only |
| `opcomm/atomic.py` (binary reuse) | Assuming the JSON/text writers cover JPEGs, or writing JPEGs non-atomically | Add `atomic_write_bytes` (same temp→`os.replace`+Windows-retry), drop fsync for ephemeral frames |
| Werkzeug dev server | `app.run()` default single-thread with a streaming response | `threaded=True` minimum, prefer `waitress` (Windows-friendly), cap concurrent stream connections |
| NDI HX3 on the dedicated WiFi | Adding full-rate preview traffic that contends with phone uplinks | Hard preview-bitrate cap well under post-NDI headroom; preview degrades first, director never |
| Browser MJPEG (`<img>`) | JS object-URL churn without `revokeObjectURL`; no reconnect after stall | Native `multipart/x-mixed-replace` into one `<img>`; client staleness watchdog + reconnect |
| Tablet browser (iOS Safari esp.) | Desktop-only testing; assume MJPEG/timers run in background | Validate transport on the real tablet/browser; wake-lock; resume on `visibilitychange` |
| Flask control POSTs vs streaming | Override/status share the lone worker with the stream | Keep control handlers fast + on their own threads; cap streams; test POST-during-stream |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-tick JPEG encode on the critical path | Tick p95 rises with console open; switching laggy | Off-tick publisher, decoupled fps | 4 cams × 30Hz; worse heat-soaked (~546ms) |
| Preview bandwidth competing with NDI | More feed-watchdog false-deaths / SAFE degrades when console open | Capped low-rate/low-res preview; degrade-first | 3-4 phones live (60-200 Mbps NDI) + console |
| opcomm-dir fsync storm | Control writes (score/command/status) slow; more Windows replace-retries | Separate media dir, drop fsync for preview, RAM-backed | Several-fps × 4 cams of JPEG writes |
| Single-threaded Flask + streaming | Override/status freeze while preview streams | `threaded`/`waitress` + connection cap | First long-lived connection (multiview open) |
| Browser object-URL / socket leak | Tablet tab RAM climbs for hours → OS kills tab | `revokeObjectURL`, one `<img>`, one socket, soak test | Multi-hour gara session |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Carrying over "no-auth on 0.0.0.0 is fine" now that it serves live video | Privacy/GDPR incident: live feed of competitors/minors leaks to anyone on/near the LAN | Re-evaluate threat for v1.1; harden AP (WPA2/3, no internet bridge, scoped RF); optional tablet-friendly token |
| Persisting/timestamping preview frames | A retention surface of personal video data on disk | Ephemeral overwrite-in-place only; no preview history persisted |
| Bridging the dedicated VLAN to a venue/guest network | Wider, untrusted audience for video + override control | Keep the dedicated AP isolated; document as a setup requirement |
| Auth that can block the control POSTs | Override stops working = director uncontrollable in a crucial moment | Any auth lives in the Flask layer, must never raise/block `/command`; director untouched |
| Binding preview to 0.0.0.0 on a multi-NIC host | A second/misconfigured interface exposes video beyond the dedicated LAN | Bind to the dedicated-LAN interface specifically where possible |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Frozen preview/status after WiFi blip or tablet sleep, shown as "live" | Operator overrides based on a lying UI | Freshness stamp + staleness overlay; force resume on visibility/`pageshow` |
| "Camera live" without the *reason* | Operator can't tell auto vs override vs feed-dead vs subject-lost → distrusts the system | Render `DirectorStatus.reason` (auto/override/subject-lost/feed-dead/fault) next to the live cam — the v1.1 "camera live + perché" feature |
| Desktop-first layout on a tablet | Override buttons off-screen / mis-tappable at the worst moment | Tablet-first responsive layout; large touch targets; controls always visible |
| Override still "alla cieca" because thumbnails lag | Operator forces the wrong camera | Show the candidate-camera thumbnail on the override button; surface thumbnail freshness |
| Overlay score preview drifts from actual OBS overlay | Operator trusts a preview that doesn't match air | Render the preview from the SAME `render_overlay_text`/overlay source of truth |

## "Looks Done But Isn't" Checklist

- [ ] **Live preview:** Often missing the off-tick publisher — verify RBT-05 `run_measured` p95 is UNCHANGED with preview enabled (director never blocked).
- [ ] **Crash isolation:** Often missing the import guard — verify the console package imports/starts with cv2/torch/numpy/cyndilib UNINSTALLED (RBT-04 canary test).
- [ ] **Atomic frames:** Often missing tear-free binary write — verify rapid writer + concurrent reader never yields a partial/zero-byte JPEG (and fsync dropped for preview).
- [ ] **opcomm-dir bounding:** Often missing overwrite-in-place — verify the dir size is flat over a session and no `.tmp`/timestamped files accumulate; control writes not slowed.
- [ ] **Threaded serving:** Often missing `threaded`/WSGI — verify `/command` is written promptly WHILE a preview stream is active.
- [ ] **Bandwidth cap:** Often missing the contended-network test — verify preview stays under budget and feed-watchdog false-deaths don't rise with phones live + console open.
- [ ] **Tablet sleep/wake:** Often missing resume logic — verify preview + `/status` refresh after the real tablet sleeps and wakes (no frozen "live").
- [ ] **Long-run hygiene:** Often missing leak control — verify multi-hour soak: tab memory + server thread count flat, not climbing.
- [ ] **Security re-eval:** Often missing — verify the v1.1 threat decision for live-video-behind-0.0.0.0 is explicitly written, not carried over.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Encoding crept onto the tick | MEDIUM | Move encode to a publisher thread; re-run `run_measured`; assert p95 restored |
| Heavy import coupled into console | MEDIUM | Move encoding orchestrator-side; restore Flask+opcomm-only imports; add the uninstall canary test |
| Preview saturating WiFi | LOW | Lower fps/res/quality to the cap; switch to single-active + thumbnails; re-test contended |
| opcomm dir bloated/thrashing | LOW | Switch to fixed-name overwrite + separate media dir; drop fsync; purge stray temps |
| Single-thread freeze | LOW | Enable `threaded`/`waitress`; cap stream connections; add POST-during-stream test |
| Browser/tablet leak | LOW-MEDIUM | Add `revokeObjectURL` + single-socket reconnect + history cap; soak-test to confirm flat |
| Security blast-radius grew | LOW | Harden AP/network; document; bind to dedicated NIC; (optional) add non-blocking token |

## Pitfall-to-Phase Mapping

> Suggested v1.1 phase shape (continues numbering from Phase 7): **(A) Frame-publishing channel** → **(B) Multiview/streaming + bandwidth** → **(C) Tablet restyle + camera-live-&-why + override thumbnails + score preview**. The first phase MUST establish the off-tick + isolation-preserving channel before any UI consumes it.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Encoding on the tick | A (frame channel) | `run_measured` p95 unchanged with preview on |
| 2. Console coupled to orchestrator | A (frame channel) | Console imports/starts with heavy stack uninstalled |
| 3. Preview vs NDI bandwidth | B (multiview/streaming) | Contended-network test: bitrate ≤ cap, no rise in feed false-deaths |
| 4. Torn/stale JPEG reads | A (frame channel) | Writer+reader race → never partial; staleness overlay fires |
| 5. opcomm-dir bloat/thrash | A (frame channel) | Flat dir size, no temp accumulation, control writes not slowed |
| 6. 0.0.0.0 video exposure | B (streaming, video behind endpoint) | Written v1.1 threat re-eval; AP isolation documented |
| 7. Single-threaded freeze | A/B (serving model) | POST `/command` succeeds during an active stream |
| 8. Browser/tablet leaks | C (tablet/multiview UI) | Multi-hour soak: flat memory + thread count |
| 9. Tablet sleep/viewport | C (tablet restyle) | Real-tablet sleep/wake resume; touch layout validated |

## Sources

- **Repo code (HIGH, primary):** `src/segugio/orchestrator/loop.py` (the sacred fixed-rate tick, RBT-04 fault-isolation, RBT-05 `run_measured` p95 ~256ms / ~546ms heat-soaked, lazy-import boundary); `src/segugio/opcomm/atomic.py` (temp→fsync→`os.replace` atomic swap + Windows `MoveFileEx` PermissionError retry — the pattern to mirror for binary frames); `src/segugio/opcomm/channel.py` + `records.py` (the four-file control channel + `DirectorStatus.reason`/`alive`); `src/segugio/ui/app.py` (Flask+opcomm-only isolation contract, `0.0.0.0:8080` no-auth accepted decision, single-threaded `app.run()`); `.planning/PROJECT.md` (v1.1 goal, WiFi-contention + crash-isolation constraints, NDI 75-min frozen-frame gotcha).
- **NDI HX3 bandwidth (HIGH):** docs.ndi.video + JEM Productions "NDI Bandwidth Explained" — HX3 1080p ≈ 20-50 Mbps per stream (H.265/H.264), ×3-4 phones = 60-200 Mbps contended on the dedicated WiFi.
- **Flask/Werkzeug MJPEG serving (HIGH/MEDIUM):** miguelgrinberg flask-video-streaming issue #16 + py-mjpeg docs — `threaded=True` required because each MJPEG/long-lived request occupies a worker; single-threaded dev server blocks all other requests (override/status) while streaming; prefer a real WSGI server for long-lived connections.
- **Browser MJPEG / object-URL leaks + tablet sleep (MEDIUM):** general web-platform behavior (`URL.revokeObjectURL`, `navigator.wakeLock`, `visibilitychange`/`pageshow`, iOS Safari background-tab suspension) — cross-checked against the long-running-multiview failure pattern.

---
*Pitfalls research for: live preview + richer operator UI across a crash-isolation boundary over contended WiFi (Segugio v1.1)*
*Researched: 2026-06-13*
