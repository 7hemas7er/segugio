# Loop-test runbook — 4-camera NDI pipeline with NO phones

A repeatable desk demo that exercises the **full** Segugio pipeline — NDI receive →
AI tracking → OBS scene switching — using four **looping recorded clips** in place of
the iPhone HX3 feeds. No phone rig, no WiFi 6 network, just this dev box.

## Overview

This validates the core value — **"the right camera at the right time, automatically"** —
without any phones. Four local clips are published as named NDI sources by
`tools/ndi_loop_sender.py` (one cyndilib `Sender` per camera, looping forever). The
**real** `NdiFrameSource` receivers ingest them, the **real** orchestrator runs YOLO
tracking + the framing scorer + the FSM, and switches the OBS program scene live via
obs-websocket — exactly the production path, only the camera source is recorded instead
of live. If the program scene follows the on-screen dog across the four clips, the
switching logic is proven end-to-end.

What is real here: `NdiFrameSource`, the AI loop, the scorer, the FSM, OBS, the overlay.
What is faked: only the video source (looping clips, not phones).

## Prerequisites

- **NDI Discovery Server must be RUNNING — and (re)started FRESH each session.** Plain
  mDNS discovery is broken on this box (Tailscale interferes with the multicast), so
  discovery is served from `127.0.0.1`. Start it from:
  `C:\Program Files\NDI\NDI 6 Tools\Discovery Service\NDI Discovery Service.exe`
  **Gotcha:** a stale/previous instance can still be *listening* on `5959` yet fail to
  register senders (you see **0 ESTABLISHED** connections to `5959` and the finder discovers
  nothing). If discovery is empty, **kill and relaunch** the service before anything else:
  ```powershell
  Get-Process 'NDI Discovery Service' -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Process 'C:\Program Files\NDI\NDI 6 Tools\Discovery Service\NDI Discovery Service.exe'
  ```
- **`%APPDATA%\NDI\ndi-config.v1.json` must point discovery at 127.0.0.1**, i.e. contain:
  ```json
  {"ndi":{"networks":{"discovery":"127.0.0.1"}}}
  ```
  (Already written this session — verify it is still there.)
- **OBS Studio** with the **DistroAV (NDI)** plugin and **obs-websocket v5** enabled on
  `localhost:4455` with **no password**.

### The MASTER host-prefix gotcha (read before running)

A cyndilib `Sender("FOO")` is **discoverable on the network as `"<HOST> (FOO)"`**. This
box's NDI host name is **MASTER** (`socket.gethostname()` returns `"Master"`, which NDI
uppercases to `MASTER`). So:

- `tools/ndi_loop_sender.py` publishes the **bare** stream `PHONE-WIDE (NDI HX3)`.
- The network re-forms it as `MASTER (PHONE-WIDE (NDI HX3))` — which is exactly the
  `ndi_source` in `config.looptest.yaml` and the `ndi_source_name` in the scene JSON.

**If your `hostname` is NOT `MASTER`:** run `hostname`, uppercase the result, and replace
every `MASTER` prefix in **both** `config.looptest.yaml` (the 4 `ndi_source` values) **and**
`obs/segugio-looptest-scene-collection.json` (the 4 `ndi_source_name` values and the
`NDI - ...` source/item names). The sender's startup banner prints a HOST MISMATCH warning
if the discoverable name it would publish does not equal the config `ndi_source`.

## Step-by-step

**(a) Start the NDI Discovery Service** (see path above). Leave it running.

**(b) Terminal 1 — start the looping senders (CPU `venv`):**
```
venv\Scripts\python tools\ndi_loop_sender.py --config config.looptest.yaml --clips-dir tests\fixtures\looptest
```
The banner lists, per camera: the matched clip, frame count + fps, the published stream,
the expected discoverable name, and the config `ndi_source` it must equal. Keep this
terminal open (Ctrl-C stops all senders cleanly).

**(c) OBS — import the scene collection:** Scene Collection → Import →
`obs\segugio-looptest-scene-collection.json`, then switch to the `Segugio` collection.
Confirm the 4 NDI sources (Wide / Long / Low / Handler) show **looping video**.

**(d) Terminal 2 — start the orchestrator (GPU `venv312`):**
```
venv312\Scripts\python -m segugio config.looptest.yaml
```

**(e) Verify switching:** the OBS **program** scene should flip among **CAM Wide / CAM
Long / CAM Low / CAM Handler** following the on-screen dog. Cross-check the opcomm
`status.json` and the orchestrator logs to confirm the chosen camera matches what is on
air.

## Crops mode (1 clip → 4 crops) — camera-to-camera switch demo

When you have ONE good clip instead of four, `--crops-from CLIP` publishes the SAME clip as
four different crops (one per camera), so a different camera frames the dog best as it moves.
Crops default by role (wide = full, long = upper/far band, low = lower/near band, handler =
centre box); override any crop with `--crop CAMID=x0,y0,x1,y1` (normalized), and
`--phase-shift` time-staggers the feeds.

**Verified handoff demo** — base clip `cam_handler_32484430` has the widest horizontal sweep
(the dog runs across the field), so split it into left / centre / right crops:

```
venv\Scripts\python tools\ndi_loop_sender.py --config config.looptest.yaml ^
  --crops-from tests\fixtures\looptest\cam_handler_32484430.mp4 ^
  --crop cam_low=0.10,0.45,0.50,1.0 ^
  --crop cam_handler=0.35,0.45,0.72,1.0 ^
  --crop cam_long=0.55,0.40,0.95,1.0
```

Run the orchestrator as in step (d) and start a run. Observed program sequence:
`cam_long (right) → cam_handler (centre) → cam_low (left)` as the dog crosses — a clean
camera-to-camera handoff following the dog.

**These cuts are intentionally PACED, not rapid.** The core value is *stable framing, no
flickering cuts* — `min_dwell` / hysteresis / EMA deliberately hold a camera until another is
clearly and durably better. So expect a handful of well-timed handoffs as the dog traverses,
NOT constant rotation. If one camera "wins" the whole time that is **correct**: with a single
clip the dog is often best-framed by one crop. Continuous, organic switching is what real
multi-angle phone feeds produce on the rig (the dog physically leaves one camera's good
framing and enters another's).

## Clip provenance

All four clips are from **Pexels** (Pexels License — CC0-like, commercial use OK, no
attribution required). They live (gitignored) under `tests/fixtures/looptest/`:

| Camera      | Pexels ID | File                         |
|-------------|-----------|------------------------------|
| cam_wide    | 9898282   | `cam_wide_9898282.mp4`       |
| cam_long    | 18233295  | `cam_long_18233295.mp4`      |
| cam_low     | 16573252  | `cam_low_16573252.mp4`       |
| cam_handler | 32484430  | `cam_handler_32484430.mp4`   |

The sender matches them per camera by the `{cam.id}_*.<ext>` glob.

## Troubleshooting

- **"Console / orchestrator blank but OBS sees the feed"** → exact-name mismatch. The
  config `ndi_source` must **byte-match** the sender's host-prefixed stream **and** the
  scene JSON `ndi_source_name`. Re-check the `MASTER` prefix on all three sides (run
  `hostname` and confirm it uppercases to `MASTER`).
- **"Nothing discovered"** → the NDI Discovery Service is not running, is a **stale
  instance** (listening on `5959` but not registering senders), or
  `%APPDATA%\NDI\ndi-config.v1.json` is missing / not pointing discovery at `127.0.0.1`.
  Check registrations with `Get-NetTCPConnection -LocalPort 5959 -State Established` — if it
  returns **0** while a sender is up, **kill and relaunch** the Discovery Service (see
  Prerequisites), then restart the senders.
- **"Program stays on one camera"** → usually NOT a bug. Stable cuts are by design
  (`min_dwell` / hysteresis). With a single base clip one crop is often best-framed
  throughout; use the crops handoff demo above, or expect organic switching only with real
  multi-angle feeds.
- **"Feed death blips / watchdog trips"** → the cyndilib `Sender` must be built **once**
  per camera, not re-created per loop iteration. `tools/ndi_loop_sender.py` builds it once
  in `publish_loop`; do not change that.
