# Architecture Research — v1.1 Console Regia (live-visibility data-flow)

**Domain:** Live-visibility data-flow for a crash-isolated operator console (Segugio v1.1 — Console Regia)
**Researched:** 2026-06-13
**Confidence:** HIGH (grounded in the v1.0 codebase, which is internally consistent and fully read; the one external claim — OBS multiview/screenshot — verified via obs-websocket docs)

> Scope note: this file is the **v1.1 milestone** architecture research. The v1.0 field/camera-mapping architecture lives in `ARCHITECTURE.md` (preserved, NOT overwritten). This document answers ONLY the new question: how do live frames + per-camera scores + dog tracking state get from the orchestrator to the separate crash-isolated Flask console.

---

## The Question, Restated

The orchestrator already holds, per tick, everything the console wants to show:

- per-camera **numpy BGR frames** (`source.latest(cam_id)` inside `_fan_out`),
- per-camera **scores** (`scores = self.scorer.update(...)`),
- per-camera **dog tracking state** (`dets_by_cam` — the `DetectionSignal | None` map, plus the `CompetitorLock` locked id + motion energy),
- the **alive map** and the **live cam + reason** (already serialized to `status.json`).

The console is a SEPARATE Flask process that may import **only `Flask + segugio.opcomm`** (D-03 / RBT-04). It currently sees the live cam through one tiny file, `status.json`, polled at 1 Hz. v1.1 wants the operator to *see the cameras* and *understand why*.

The hard invariant: **the console must never import the orchestrator or any heavy dep, and a console crash must never perturb the live director — nor must publishing-for-the-console steal time from the director's critical tick.**

---

## Standard Architecture (Recommended)

The recommendation is **(a) — the orchestrator publishes downscaled per-camera JPEG thumbnails + a scores/tracking sidecar into the existing opcomm directory, off the critical tick, and the console serves them as static-ish files.** This is the ONLY option that preserves the crash-isolation invariant *by construction* (the console keeps importing only `Flask + opcomm`, exactly as today) and extends the existing file-channel pattern rather than inventing a second IPC mechanism.

### System Overview

```
┌──────────────────────── ORCHESTRATOR PROCESS (heavy: torch/cv2/cyndilib/obsws) ───────────────────────┐
│                                                                                                         │
│   CRITICAL TICK (fixed-rate, RBT-05 budget)            PUBLISH (off critical path)                     │
│   ┌──────────────────────────────────────┐            ┌──────────────────────────────────────────┐    │
│   │ source.latest(cam) → YOLO+BoT-SORT    │            │  PreviewPublisher (own daemon thread)      │    │
│   │ → CompetitorLock/Gate → MultiCamScorer│  hand-off  │  • throttle to ~3-6 fps                     │    │
│   │ → FeedWatchdog → DecisionEngine (FSM)  │ ────────►  │  • cv2.resize → cv2.imencode('.jpg', q~55)  │    │
│   │ → ObsController.cut → write_status()   │  (latest- │  • atomic_write_bytes(cam_<id>.jpg)         │    │
│   └──────────────────────────────────────┘   only,    │  • atomic_write_json(preview.json sidecar)  │    │
│          │ writes status.json (D-11, unchanged)        └──────────────┬─────────────────────────────┘    │
│          │                                                            │ writes into opcomm dir          │
└──────────┼────────────────────────────────────────────────────────────┼────────────────────────────────┘
           │                                                            │
           ▼  ── opcomm DIRECTORY (the ONLY coupling — atomic files) ──  ▼
     status.json   command.json   runstate.json   score.json   overlay.txt   ◄ existing
     preview.json (scores+tracking sidecar)   cam_<id>.jpg × N   gen.txt (generation counter)  ◄ NEW
           ▲                                                            ▲
┌──────────┼──────────────── CONSOLE PROCESS (light: Flask + segugio.opcomm ONLY) ───────────┼────────────┐
│          │ read_status() (today)                                                            │            │
│   ┌──────┴───────────────────────────────────────────────────────────────────────────────┴────────┐   │
│   │ Flask routes:  GET /status (today)                                                               │   │
│   │                GET /preview              → read_preview() sidecar JSON (scores+tracking)         │   │
│   │                GET /preview/<cam>.jpg    → send_file the latest cam_<id>.jpg (whitelisted id)    │   │
│   │ console.html:  <img> tags per camera refreshed ~3-6 fps + status/scores poll                    │   │
│   └────────────────────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Where it lives / how built |
|-----------|----------------|----------------------------|
| **PreviewPublisher** (NEW) | Owns the frame→JPEG→disk publish loop. Throttles fps, downscales, encodes, atomic-writes `cam_<id>.jpg` + `preview.json` + bumps `gen.txt`. | NEW module `orchestrator/preview.py`, run on its own daemon thread *inside the orchestrator process*. Imports cv2 (already a heavy dep there). NEVER on the tick thread. |
| **Tick → publisher hand-off** (NEW, tiny) | After the FSM decides, the tick drops the latest frames + scores + tracking snapshot into a single-slot `latest` buffer (overwrite, never block). | A few lines in `loop.py::_tick_once`; a `threading.Lock`-guarded "latest-only" mailbox (1 slot, last-writer-wins). Cost ≈ a dict assignment under a lock — negligible vs YOLO. |
| **atomic_write_bytes** (NEW) | Binary sibling of `atomic_write_text` — temp-in-dir + fsync + `os.replace` for the JPEG. | Add to `opcomm/atomic.py` (stdlib only — keeps the leaf clean). |
| **preview.json record** (NEW) | Typed per-camera scores + tracking snapshot the console renders ("why"). | NEW frozen record in `opcomm/records.py` + `read_preview`/`write_preview` in `opcomm/channel.py` (mirrors `DirectorStatus` exactly). |
| **Console preview routes** (NEW) | `GET /preview` (sidecar JSON) + `GET /preview/<cam>.jpg` (whitelisted static file). | NEW routes in `ui/app.py`; still `Flask + opcomm` only. |
| **status.json** (MODIFIED — see §"Extending the reverse channel") | Stays the D-11 live-cam+reason+alive channel; per-camera *scores* go in the **preview.json sidecar**, NOT bloated into status.json. | `opcomm` unchanged for status; new sidecar alongside. |

---

## Recommended Project Structure (the delta)

```
src/segugio/
├── opcomm/
│   ├── atomic.py        # + atomic_write_bytes()  (NEW — binary atomic write)
│   ├── records.py       # + PreviewDoc frozen record (NEW)
│   └── channel.py       # + write_preview / read_preview (NEW)
├── orchestrator/
│   ├── loop.py          # + latest-only mailbox publish() call in _tick_once (MODIFIED, ~6 lines)
│   ├── preview.py       # PreviewPublisher daemon thread (NEW)
│   └── runtime.py       # wire PreviewPublisher into build_orchestrator (MODIFIED)
└── ui/
    ├── app.py           # + GET /preview, GET /preview/<cam>.jpg (MODIFIED)
    └── templates/
        └── console.html # multiview <img> grid + scores/“why” render + tablet restyle (MODIFIED)
```

### Structure Rationale

- **Keep everything new in `opcomm/` and `orchestrator/`, nothing new the console imports.** The console gains only *routes* and *template* — it still imports `Flask + segugio.opcomm`. The crash-isolation proof is unchanged: `import segugio.ui` resolves with torch/cv2/cyndilib absent, because the JPEG encode happens in the orchestrator and the console only `send_file`s bytes off disk.
- **PreviewPublisher is a peer of the tick, not part of it.** A separate daemon thread means a slow/raised encode coasts (caught, logged) without touching the FSM. The publish loop reads a *latest-only* mailbox, so it can run at its own (slower) cadence and is allowed to *drop* frames — it must never back-pressure the director.

---

## Architectural Patterns

### Pattern 1: Latest-only single-slot mailbox (tick → publisher hand-off)

**What:** The tick writes the most recent `(frames_by_cam, scores, tracking_snapshot)` into a 1-slot buffer under a short lock; the publisher reads-and-clears it on its own clock. Last-writer-wins; the tick *never waits* on the publisher.

**When to use:** Exactly this producer/consumer-at-different-rates situation where the producer (30 Hz tick, latency-critical) must not be throttled by the consumer (3-6 fps JPEG encode + disk).

**Trade-offs:** Dropped intermediate frames (fine — previews don't need every frame). The alternative, a `queue.Queue(maxsize=1)` with `put_nowait` + `except queue.Full: pass`, is equivalent and arguably clearer.

**Example:**
```python
# loop.py — inside _tick_once, AFTER self._apply(decision, alive):
# Cost: a dict ref-assignment under a non-contended lock. Off the YOLO/FSM hot math.
if self._preview is not None:
    self._preview.offer(frames_by_cam, scores, dets_by_cam)  # never blocks, may overwrite

# preview.py — PreviewPublisher
def offer(self, frames, scores, dets):
    with self._lock:
        self._latest = (frames, scores, dets)   # overwrite previous, last-wins

def _run(self):                                   # own daemon thread
    while not self._stop:
        with self._lock:
            item = self._latest; self._latest = None
        if item is None:
            time.sleep(self._period); continue
        try:
            self._publish(*item)                  # resize → imencode → atomic_write_bytes
        except Exception as exc:                  # RBT-04: an encode/IO fault coasts
            logger.warning("preview publish coasted: {}", exc)
        time.sleep(self._period)                  # ~1/5 s → 5 fps cap
```

### Pattern 2: Atomic binary publish (reuse the proven write primitive)

**What:** Write each JPEG via the same **temp-in-same-dir → flush → fsync → os.replace** dance `atomic.py` already uses, so the console's `send_file` never reads a half-written image (no torn JPEG, no Windows sharing-violation crash — the existing `_atomic_replace` retry covers the open-read-close race).

**When to use:** Any time a separate process reads a file a writer rewrites continuously. This is the file-channel pattern the whole system is built on — extend it, don't replace it.

**Trade-offs:** N small files rewritten ~5×/s. `os.fsync` per image adds a few ms of disk time *on the publisher thread* — acceptable because it is off the tick. (If profiling shows fsync cost, the JPEGs can skip fsync: they are disposable/regenerated each frame, unlike score/command files where durability matters. Keep fsync for `preview.json`, optionally drop it for the throwaway JPEGs.)

**Example:**
```python
# opcomm/atomic.py — binary sibling of atomic_write_text
def atomic_write_bytes(path: str, data: bytes) -> None:
    tmp = _temp_path(path)
    with open(tmp, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    _atomic_replace(tmp, path)        # Windows MoveFileEx + retry, same volume
```

### Pattern 3: Sidecar typed record for scores + tracking (don't bloat status.json)

**What:** A NEW `preview.json` carrying the per-camera "why" — score, smoothed/EMA score, whether the dog is locked, locked track id, motion energy, in-zone flag, normalized box — as its own atomic file, mirroring `DirectorStatus` exactly (frozen dataclass, safe-default reader, never raises into the loop).

**When to use:** When a new payload has a *different update cadence and consumer* than an existing one. `status.json` is "write-on-change" (only when the live cam/reason flips); per-camera scores change every tick. Mixing them would force status.json to rewrite every tick and would couple two unrelated concerns. Separate files = independent atomic swaps (the project's own RESEARCH "Pattern 3", cited throughout `channel.py`).

**Trade-offs:** One more file + reader. Trivially worth it; it is the documented house style.

**Example:**
```python
# opcomm/records.py
@dataclass(frozen=True)
class PreviewDoc:
    """Per-camera scores + tracking snapshot the console renders ('camera live + perché')."""
    tick: int = 0
    cams: dict = field(default_factory=dict)   # {cam_id: {"score": float, "ema": float,
                                               #  "locked": bool, "track_id": int|None,
                                               #  "energy": float, "in_zone": bool,
                                               #  "box": [x,y,w,h]|None}}
    def __post_init__(self):                    # normalize like DirectorStatus.alive
        object.__setattr__(self, "cams",
            {str(k): dict(v) for k, v in dict(self.cams).items()})
```

---

## Data Flow

### Live-visibility flow (the new path)

```
[orchestrator tick]
  source.latest(cam) ─► YOLO+BoT-SORT ─► scorer ─► FSM ─► OBS cut ─► write_status()  (UNCHANGED, on tick thread)
        │ frames_by_cam        │ scores          │ dets_by_cam
        └──────────────┬───────┴─────────────────┘
                       ▼  publisher.offer(...)   (1-slot, last-wins, non-blocking)
              [PreviewPublisher daemon thread, ~5 fps]
                       │  cv2.resize(→ ~320–480px wide) ─► cv2.imencode('.jpg', q≈55)
                       ├─► atomic_write_bytes(opcomm/cam_<id>.jpg)
                       ├─► write_preview(opcomm/preview.json)   (scores + tracking)
                       └─► bump gen.txt                          (monotonic generation)
                                     │
        ── opcomm dir ──────────────┘
                                     │
              [console Flask process]  (Flask + opcomm only)
        GET /preview/<cam>.jpg ─► send_file(cam_<id>.jpg)     ◄ browser <img> refresh ~5 fps
        GET /preview           ─► read_preview() → JSON       ◄ browser poll ~2–4 Hz ("why")
        GET /status            ─► read_status()  → JSON       ◄ unchanged 1 Hz
```

### Extending the reverse channel (status.json + sidecar) — concrete

Two clean choices; **recommend the sidecar (B)**:

- **(A) Inline into status.json.** Add an optional `scores: {cam_id: {...}}` key to `DirectorStatus`. *Reject for v1.1* because status.json is deliberately *write-on-change*; per-tick scores would turn it into a per-tick rewrite and couple "live cam" (rarely changing, safety-critical) to "scores" (always changing, cosmetic). It also widens the torn-write surface on the one file the FSM relies on.
- **(B) Sidecar `preview.json` (recommended).** `PreviewDoc` as above, written by the publisher thread (off-tick), read by `GET /preview`. status.json stays *exactly as-is* — the safety-critical reverse channel keeps its small, stable, write-on-change shape. The console correlates the two by `live_cam` (highlight the live tile) + the per-cam `locked`/`score` to show *why*.

Backward-compatible by construction: `read_preview` returns an empty default if absent, so an old console + new orchestrator (or vice-versa) degrades to "no thumbnails, status still works."

---

## Option Comparison

| Criterion | **(a) JPEG files in opcomm** ✅ | (b) MJPEG / WebSocket endpoint | (c) Embed OBS multiview / virtual-cam |
|-----------|-------------------------------|--------------------------------|----------------------------------------|
| **Crash-isolation (console imports only Flask+opcomm)** | **Preserved by construction** — console just `send_file`s bytes; no new import, no socket to the heavy process. | **Broken or strained.** A WebSocket/MJPEG server *inside* the console would need the frames pushed to it; if the orchestrator runs the streaming server, the browser talks to the *orchestrator* port — but that puts a long-lived network server *on the director process* (new failure surface, threads, back-pressure). A console-hosted relay would need the frames in-process → import pressure. | **Mostly out of console's hands**, but couples the console UX to OBS being up, and obs-websocket `GetSourceScreenshot` runs over the obs-websocket connection — which the **console is forbidden to open** (it would need obsws). |
| **Keeps publish OFF the director's critical tick** | **Yes** — separate daemon thread + latest-only mailbox; tick cost ≈ one locked dict assignment. | Harder — an MJPEG/WS server pinned to the orchestrator must be fed from a non-tick thread anyway; you end up building the *same* off-tick publisher PLUS a network server. | OBS does the compositing; zero orchestrator cost — but you lose AI-overlay control and gain an OBS dependency. |
| **Frame-rate / bandwidth to a tablet on contended WiFi** | Tunable: 4 cams × ~320–480px JPEG q≈55 ≈ 15–40 KB each → at 5 fps ≈ **0.3–0.8 MB/s total**. Browser `<img>` pulls only what it can; naturally degrades. | MJPEG ≈ same bytes but a *persistent* connection per tile; WebSocket can push binary frames efficiently but adds protocol + reconnect logic. Marginally more efficient steady-state, far more moving parts. | OBS multiview **cannot be embedded in a browser natively** (verified — no NDI/browser multiview output); needs a screen-share/Spacedesk hack or a separate full-res NDI/virtual-cam feed → *more* bandwidth, Windows-only, not tablet-friendly. |
| **Thread-safety** | One writer thread, atomic swaps, readers open-read-close. Already proven by the existing channel. | Needs a thread-safe frame fan-out to N client connections + per-client back-pressure handling. | N/A in our process; OBS-internal. |
| **Decoupling (console crash never touches director)** | **Total** — no shared runtime; the dir is the only contact. | A WS/MJPEG server on the orchestrator means a misbehaving browser client can occupy orchestrator threads/sockets (slowloris-style), i.e. a *client* can now touch the director's process. | Total, but at the cost of the feature (no AI "why" overlay, OBS-coupled). |
| **Fits the existing file-channel pattern** | **Exactly** — it *is* the pattern, extended with bytes + one sidecar. | New IPC mechanism alongside the file channel (two paradigms to reason about). | Bypasses the channel entirely; different product. |
| **Latency (glass-to-preview)** | ~1 frame + publish period (≤200 ms at 5 fps) + disk + HTTP. Fine for an *operator monitor* (not the program feed). | Slightly lower steady-state; not meaningfully better for an operator preview. | Lowest (OBS native), but irrelevant given the coupling cost. |

**Recommendation: (a).** It is the only option that keeps the crash-isolation invariant *trivially provable* (the console's import set does not change), reuses the atomic-file primitive the whole system already trusts, and keeps frame publishing on a droppable off-tick thread. (b) is a reasonable *future* optimization if 5 fps file-thumbnails ever feel sluggish on the tablet, but it trades the invariant's simplicity for marginal efficiency and a network server on the director — not worth it for v1.1. (c) is the wrong tool: OBS can't feed a browser multiview without bypassing the very obs-websocket boundary the console is forbidden to cross.

> **Hybrid note for "preview del punteggio":** the score-overlay *preview* (how the score will look on OBS) does **not** need a camera frame at all — the console already owns `score.json`/`overlay.txt` and `score_render.py`. Render the overlay-text preview client-side from the score form. Reserve the JPEG channel for the *camera* multiview only.

---

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| 3–4 cameras (the v1 rig), 1 tablet | The recommended design as-is. ~0.3–0.8 MB/s, 4 small files rewritten 5×/s. Comfortable on a dedicated WiFi 6 LAN. |
| 1 tablet + 1 laptop watching | Two HTTP readers off the same files — fine; static `send_file` scales trivially, no per-client state. |
| Higher preview fps wanted (8–10) | First lower JPEG quality/size, then consider dropping `fsync` on the throwaway JPEGs. Only if *still* sluggish, graduate to option (b) WebSocket — but isolate it on a third tiny process that imports only opcomm, never fold it into the director. |
| Many viewers (unlikely in this domain) | Put a thumbnail behind the OS file cache; or a reverse proxy serving the opcomm dir statically. Still no orchestrator coupling. |

### Scaling priorities

1. **First "bottleneck" is perceptual, not throughput:** 5 fps thumbnails on contended WiFi will feel fine for an operator deciding overrides; tune fps/quality before changing architecture.
2. **Disk churn second:** if the opcomm dir is on slow/network storage, the per-image fsync dominates — drop fsync on JPEGs (regenerated next frame) before anything else.

---

## Anti-Patterns

### Anti-Pattern 1: Letting the console import cv2/numpy to decode/encode frames

**What people do:** "Just pass the numpy frame to the console and JPEG-encode it there."
**Why it's wrong:** It breaks D-03/RBT-04 — the console would import a heavy dep, and a frame in a numpy array can't cross a process boundary without serialization anyway. It also couples a console crash to image-processing code.
**Do this instead:** Encode in the orchestrator (cv2 already lives there); the console only moves *bytes off disk* via `send_file`.

### Anti-Pattern 2: Publishing thumbnails on the tick thread

**What people do:** Add `cv2.imencode` + `imwrite` straight inside `_tick_once`.
**Why it's wrong:** JPEG-encoding 4 frames + 4 fsync'd writes per tick adds tens of ms to the RBT-05 budget — directly stealing from the <300 ms decision loop and varying with disk weather.
**Do this instead:** Hand off via the latest-only mailbox to the `PreviewPublisher` daemon thread; the tick pays only a locked dict assignment.

### Anti-Pattern 3: Bloating status.json with per-camera scores

**What people do:** Stuff `{cam: score}` into `DirectorStatus` so there's "one file."
**Why it's wrong:** status.json is the safety-critical, *write-on-change* reverse channel; per-tick scores force a per-tick rewrite and widen the torn-write/lock-contention surface on the one file the FSM and watchdog depend on.
**Do this instead:** A separate `preview.json` sidecar (the project's own "separate files / independent atomic swaps" pattern).

### Anti-Pattern 4: A long-lived streaming socket on the director process

**What people do:** Run an MJPEG/WebSocket server inside the orchestrator so the browser connects directly for low latency.
**Why it's wrong:** It puts a network server (threads, accept loops, per-client buffers, slowloris exposure) onto the *never-crash* director — a misbehaving browser client can now touch the live director. That is exactly the coupling D-03 forbids.
**Do this instead:** Files in the opcomm dir; if you ever need push, isolate the streamer in its own opcomm-only process.

### Anti-Pattern 5: Reusing a single mutable frame buffer without a snapshot

**What people do:** Have the publisher read the *same* numpy array the tick is about to overwrite next frame.
**Why it's wrong:** A torn read of a half-overwritten frame (if the source reuses buffers) → garbled JPEG or a data race on the array.
**Do this instead:** The mailbox hands off a *reference snapshot* under a lock; if the source reuses frame buffers, `.copy()` when offering (a memcpy, cheap vs YOLO) or copy on the publisher right after grabbing the slot.

---

## Integration Points

### Internal boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| tick thread ↔ PreviewPublisher thread | in-process latest-only mailbox (lock or `Queue(maxsize=1)`) | Last-writer-wins, non-blocking; the ONLY back-pressure rule that matters: the tick never waits. |
| orchestrator ↔ console | **opcomm directory only** (atomic files: `cam_<id>.jpg`, `preview.json`, `gen.txt` + existing status/command/runstate/score/overlay) | The single, unchanged trust boundary. Console import set stays `Flask + segugio.opcomm`. |
| console ↔ browser/tablet | HTTP: `GET /preview/<cam>.jpg` (img), `GET /preview` (JSON), `GET /status` (JSON) | `<cam>` MUST be whitelisted against config camera ids server-side (path-traversal mitigation, same posture as the existing fixed-filename writes, T-05-05-01). |

### External services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| OBS (obs-websocket v5) | Stays the orchestrator's *control* channel only. | `GetSourceScreenshot` (base64 JPEG, scalable via `imageWidth/Height`) exists but runs over obs-websocket — the console can't use it without importing obsws, so it's not a console-side option. Could in principle be an *orchestrator-side* thumbnail source, but re-using `source.latest` frames is cheaper and keeps OBS out of the preview path. |

---

## Build Order (dependency-ordered, for the roadmapper)

Each step is independently shippable and preserves the invariant at every stage.

1. **`atomic_write_bytes` in `opcomm/atomic.py`** (NEW, leaf, stdlib-only). No dependants yet; unit-test torn-write/Windows-retry like the text writer. *Foundation.*
2. **`PreviewDoc` record + `read_preview`/`write_preview`** in `opcomm/records.py` + `channel.py` (NEW). Mirror `DirectorStatus`: frozen, safe-default reader, never raises. Unit-test round-trip + malformed→default. *Defines the contract both sides share.*
3. **`PreviewPublisher` (`orchestrator/preview.py`)** (NEW): mailbox + daemon thread + resize/encode/atomic-write + fault-coast. Unit-test with a fake frame source (inject the encoder so no real cv2 is needed in tests). *The producer.*
4. **Wire publisher into `loop.py` + `runtime.py`** (MODIFIED): the `offer(...)` call in `_tick_once` (guarded by `if self._preview`), construct+start/stop the publisher in `build_orchestrator` and `shutdown()`. Verify RBT-05 latency *unchanged* (the offer must not regress the budget — measure with `run_measured`). *The hand-off; the one place that touches the hot path — measure it.*
5. **Console routes `GET /preview` + `GET /preview/<cam>.jpg`** in `ui/app.py` (MODIFIED): `read_preview` + whitelisted `send_file`. Confirm `import segugio.ui` still resolves with torch/cv2/cyndilib absent (the crash-isolation regression test). *The consumer side; the invariant gate.*
6. **`console.html` multiview grid + "why" render + tablet restyle** (MODIFIED): per-camera `<img>` refreshed ~5 fps (cache-bust by `gen.txt` or `?t=`), highlight the `live_cam` tile, render score/locked/energy from `/preview`, client-side score-overlay preview from the existing form. *The UX.*
7. **(Deferred / optional)** override-with-thumbnail polish, and *only if needed* the option-(b) WebSocket streamer as a separate opcomm-only process. *Out of v1.1 critical path.*

**Critical dependencies:** 1 → 2 → 3 → 4 (4 needs the publisher and the record); 5 needs 2; 6 needs 5. Step 4 is the only one touching the director's hot path and MUST be gated by a re-run of the RBT-05 latency harness. Step 5 MUST be gated by the crash-isolation import test (console resolves with the heavy stack absent).

---

## Why this provably respects the invariants

- **Crash-isolation (console = Flask + opcomm only):** the new console code adds *routes and a template*, not imports. JPEG encoding lives in the orchestrator (which already imports cv2); the console only `send_file`s bytes and `read_preview`s JSON via `opcomm`. The existing `import segugio.ui` "resolves with heavy stack absent" property still holds — make it a CI gate (step 5).
- **Publishing off the critical tick:** the tick's only added cost is a non-blocking `offer()` (a locked dict assignment); all resize/encode/fsync/IO happen on a *separate daemon thread* reading a droppable single-slot mailbox. The director never waits on, and never crashes from, the preview path (each publish wrapped in a coast like every other stage, RBT-04).
- **Console crash never touches director:** there is no shared runtime, no socket from the console into the orchestrator — only the opcomm directory, exactly as today. A dead/looping console leaves the director untouched; a dead/looping director leaves the console serving the last-good JPEGs until they go stale (and `read_preview` safe-defaults).

---

## Sources

- v1.0 codebase (read in full): `opcomm/atomic.py`, `opcomm/channel.py`, `opcomm/records.py`, `orchestrator/loop.py`, `orchestrator/runtime.py`, `ui/app.py`, `ui/templates/console.html`, `.planning/PROJECT.md` — the existing atomic-file channel, the D-03/RBT-04 crash-isolation contract, the tick structure, and the D-11 reverse channel — **HIGH**
- [obs-websocket v5 protocol — `GetSourceScreenshot`](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md) — base64 JPEG, `imageWidth/imageHeight` "scale to inner"; runs over the obs-websocket connection (the console is forbidden to open it) — **HIGH**
- [OBS forum — display multiview in browser](https://obsproject.com/forum/threads/display-multiview-screen-in-browser.95361/) and [multiview to virtualcam](https://obsproject.com/forum/threads/possible-to-send-multiview-to-virtualcam.141424/) — OBS multiview cannot be embedded in a browser natively; needs Spacedesk/screen-share or a separate full feed (Windows-coupled) — **MEDIUM**

---
*Architecture research for: live-visibility data-flow on a crash-isolated console (Segugio v1.1)*
*Researched: 2026-06-13*
