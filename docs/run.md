# Running Segugio on the rig

This is the exact launch procedure for the live automatic director on the Windows / RTX box.
It makes **UAT Tests 1-4** (`.planning/phases/05-integration-ndi-mock-orchestrator-obs-score-ui/05-UAT.md`)
executable: the orchestrator now has a runnable entry point — `python -m segugio <config.yaml>`.

Two processes run side by side, coupled ONLY through the opcomm file channel:

1. the **operator console** (Flask) — writes score / run-state / override / status files;
2. the **orchestrator** (`python -m segugio`) — reads those files each tick and drives OBS.

They must point at the **same opcomm directory** (see "Channel directory" below).

---

## Prerequisites

- **Editable install WITH the heavy runtime stack** (the `src/`-layout package plus the
  lazy GPU/NDI/OBS deps the live director actually needs — ultralytics, cyndilib,
  obsws-python, opencv-python):
  `pip install -e ".[heavy]"`
  > `pip install -e .` (base deps only) is the **headless/dev** install — it runs the test
  > suite but NOT `python -m segugio`, which exits with an actionable
  > `Heavy runtime stack not installed (missing 'ultralytics')` message the moment it builds
  > the first tracker. cyndilib also needs a **system NDI runtime** installed on the box —
  > see the next bullet (this is what makes phone HX feeds decode).
- **NDI runtime on the rig — install NDI Tools (or the HX Driver).** Phone feeds are **NDI HX**,
  and HX decode is done by a separate, **version-paired** plugin (`Processing.NDI.Plugins.IPCam…`,
  v6.3.2) that only works when driven by a **matching system base runtime** (6.3.2). cyndilib
  bundles an older 6.1.1 base; on its own it *discovers* a phone but decodes **zero frames**.
  The orchestrator's `_prefer_system_ndi_runtime()` (in `src/segugio/ndi/ndi_source.py`) preloads
  the **system 6.3.2** base so cyndilib pairs base+plugin at 6.3.2 — but that only works **if a
  system NDI runtime is actually installed**. So:
  - **No NDI Tools / HX Driver on the box → no phone HX video** (mock-clip and full/uncompressed
    NDI still decode through the bundled runtime, which is why this can stay hidden until a real
    phone is tested). Install NDI Tools on the rig before the live run.
- **Config** points each camera's `ndi_source` at the discovered phone / mock sender name
  (the `ndi_source:` values in `config.example.yaml` — e.g. `"PHONE-WIDE (NDI HX3)"`). The names
  must match what the NDI senders actually advertise on the dedicated WiFi. Two field gotchas:
  - **Source names are not stable — discover them, don't hardcode.** Different sender apps/versions
    advertise different names for the *same* phone (e.g. `LOCALHOST (iPhone)` vs
    `LOCALHOST (iPhone Camera for OBS Studio App)`). Read the live name from NDI Studio Monitor /
    OBS source list and paste *that* into `ndi_source`; never assume a fixed string.
  - **The phone must have its camera view ACTIVE** in the sender app — a backgrounded or
    preview-paused app may register the source name but serve no frames.
  - **Discovery on a multi-homed PC needs NDI Access Manager.** Virtual NICs (VPN, Docker,
    Hyper-V, WSL) break the mDNS discovery cyndilib relies on. Use NDI Access Manager to bind
    discovery to the dedicated-WiFi NIC/subnet (or add the senders manually) so the phones appear.
- **OBS Studio** running with the DistroAV (NDI) plugin and the imported scene collection
  (one scene per camera + a SAFE scene). See [`docs/obs-setup.md`](obs-setup.md) for the scene
  collection, the obs-websocket v5 host/port/password, and the read-from-file overlay text source.
- **obs-websocket v5** enabled. The orchestrator reads the OBS host/port/password from the
  `SEGUGIO_OBS_HOST` / `SEGUGIO_OBS_PORT` / `SEGUGIO_OBS_PASSWORD` env vars (`build_orchestrator`
  threads them into `ObsWsController(host, port, password)`). When unset they default to
  `localhost` / `4455` / no password — so an all-defaults OBS on the same box needs no env at all.
  If you set an obs-websocket **password** in OBS, you MUST export `SEGUGIO_OBS_PASSWORD` to the
  same value (otherwise the controller connects unauthenticated and every scene cut fails). An
  empty `SEGUGIO_OBS_PASSWORD` is treated as "no password". `Config` has no `obs` block
  (`extra="forbid"`), so env is the wiring — not a YAML field.

---

## Channel directory (opcomm)

Both processes must use the SAME directory of operator↔system files
(`command.json` / `runstate.json` / `status.json` / `score.json` / `overlay.txt`):

- **default:** `./opcomm` next to the current working directory.
- **override:** set `SEGUGIO_OPCOMM_DIR` (the console reads it) **and** pass the matching
  `--opcomm-dir` to the orchestrator (below). Keep them identical or the console and the
  director will talk past each other.

---

## 1. Launch the operator console (separate process)

```bash
python -m segugio.ui.app
```

Binds `0.0.0.0:8080` — open it from the operator tablet on the dedicated WiFi. The `0.0.0.0`
bind exposes the console to anyone on that LAN; the LAN is the trust boundary (no auth in v1,
a documented field-tool decision). To colocate the channel with the orchestrator, set the env
var before launching:

```bash
# Windows PowerShell
$env:SEGUGIO_OPCOMM_DIR = "D:\segugio\opcomm"
python -m segugio.ui.app
```

---

## 2. Launch the orchestrator

### OBS UP (the normal live run)

```bash
python -m segugio config.example.yaml
```

Loads + validates the config, builds the real `NdiFrameSource` + `ObsWsController` +
one `PerCameraTracker` per camera, then ticks at 30 Hz pulling the newest frame per camera and
cutting OBS to the best-framed dog. **Ctrl-C** coasts OBS to the SAFE scene and stops the source
(the RBT-04 SAFE coast).

Useful flags:

```bash
python -m segugio config.example.yaml --rate 25                 # PAL 25p feeds
python -m segugio config.example.yaml --opcomm-dir D:\segugio\opcomm   # match the console's dir
```

### OBS DOWN at launch (must NOT crash — UAT Test 1 / CR-01 / RBT-04)

Start the SAME command **before** OBS is up:

```bash
python -m segugio config.example.yaml
```

It must **not crash**. The loop's `_safe_startup` (05-07) absorbs the failed `obs.connect()`
(and a failed NDI `source.start()`), coasts into the tick loop on SAFE, and the per-tick
`ObsWsController._safe_call` **reconnects automatically** once OBS comes up — no restart needed.
Same for a phone feed that appears late or drops: the watchdog declares it dead and the
`NdiFrameSource` receiver auto-reconnects when the named source reappears.

---

## What the UAT tests exercise from here

Run on the Windows / RTX box with live OBS + NDI senders
(`.planning/phases/05-integration-ndi-mock-orchestrator-obs-score-ui/05-UAT.md`):

| UAT Test | What it checks | How to launch |
|----------|----------------|---------------|
| **Test 1** | RBT-04 real-OBS startup + OBS-down coast / reconnect (CR-01) | the OBS-UP and OBS-DOWN commands above |
| **Test 2** | NDI feed-death → SAFE / other-live, auto-reconnect on recovery | pull a phone's cable mid-run |
| **Test 3** | Anti-jitter tuning (`watchdog_grace`, hysteresis/dwell) — no cut storm | observe cuts under jittery feeds |
| **Test 4** | Full D-07 E2E: dog tracked, best camera aired, scores overlaid, no crash | the full rig run with the console |

This plan makes the `python -m segugio config.example.yaml` command **exist and be launchable**;
actually running it against live hardware is UAT Tests 1-4, executed on the Windows / RTX box.

---

## Phase 8 — Console multiview live

Phase 8 turns the operator console into a **live multiview**: a grid of per-camera preview tiles
with LIVE/tally and dead-feed marking. The tiles are JPEG thumbnails the **orchestrator** publishes
off the decision tick (Phase 7); the **console** only serves the already-encoded bytes. Below is the
verified launch + troubleshooting procedure so the grid actually populates — and so the
"phone shows in OBS but not in the console" failure is diagnosable.

### 1. Two-process architecture (light console / heavy orchestrator)

The two processes are **crash-isolated** and couple **only** through the shared opcomm directory
(see "Channel directory (opcomm)" above — do not re-create it here):

- **Light console** — runs from the **CPU venv** (`venv`). `src/segugio/ui/app.py` imports ONLY
  Flask + `segugio.opcomm` (the crash-isolation contract); it never imports
  ultralytics / cyndilib / obsws-python / cv2. A UI exception can never reach the director.
- **Heavy orchestrator** — runs from **`venv312`** (the GPU venv with the `[heavy]` stack:
  ultralytics / cyndilib / obsws-python / opencv-python). It decodes the NDI feeds, computes the
  per-camera scores, and writes the preview JPEGs + `preview/preview.json` into the opcomm dir.

The console **only renders what the orchestrator publishes**: with no orchestrator running there are
no JPEGs on disk and every tile stays dead (see Troubleshooting (d)).

> **On-this-box gotcha — running the orchestrator from `venv312`.** `python -m segugio` needs the
> `segugio` package importable in `venv312`. Either editable-install it once
> (`venv312\Scripts\python.exe -m pip install -e ".[heavy]"`) **or** set `$env:PYTHONPATH = "src"`
> per run before launching `python -m segugio`. If `python -m segugio` errors with
> `ModuleNotFoundError: segugio`, that import path is missing.

### 2. Launch the console (light, CPU venv)

```powershell
# Windows PowerShell — from the repo root, in the CPU venv
python -m segugio.ui.app
```

This binds `0.0.0.0:8080` — open it from the operator tablet on the dedicated WiFi. (The `0.0.0.0`
bind exposes the console to anyone on that LAN; see "Phase 8 — preview bandwidth cap" and
`docs/security.md` for the trust-boundary posture.)

To populate the multiview's **cam-id whitelist** (which ids `GET /preview/<cam>.jpg` will serve),
set ONE of these before launching — the console resolves the ids inside its entrypoint, never by
importing `segugio.config` (the crash-isolation contract):

- `SEGUGIO_OPCOMM_DIR` — the opcomm directory the console reads. **Must equal the orchestrator's
  `--opcomm-dir`** (defaults to `./opcomm` next to the cwd).
- `SEGUGIO_CAM_IDS` — a **comma-separated** list of cam ids. **Takes precedence** when set.
- `SEGUGIO_CONFIG` — a path to a config YAML; the cam ids are loaded from `config.cameras`
  (`[cam.id for cam in load_config(...).cameras]`). Used only if `SEGUGIO_CAM_IDS` is empty.

With **neither** `SEGUGIO_CAM_IDS` nor `SEGUGIO_CONFIG` set, the four default rig ids keep the
preview routes serving out of the box: `cam_wide`, `cam_long`, `cam_low`, `cam_handler`.

```powershell
# Windows PowerShell — colocate the channel + set the whitelist, then launch
$env:SEGUGIO_OPCOMM_DIR = "D:\segugio\opcomm"
$env:SEGUGIO_CAM_IDS = "cam_wide,cam_long,cam_low,cam_handler"
python -m segugio.ui.app
```

The entrypoint serves via **`waitress`** when installed (`serve(app, host="0.0.0.0", port=8080)`),
and otherwise falls back to Flask's dev server with **`threaded=True`**
(`app.run(host="0.0.0.0", port=8080, threaded=True)`). **`threaded=True` is the UXT-02 SAFETY
control, not cosmetic**: a slow preview `GET` can never pin the lone WSGI worker and block the
safety-critical override `POST /command`. For a production WSGI server, install the optional extra:

```powershell
pip install -e ".[console]"   # installs waitress==3.0.2
```

### 3. Routes served by the console

| Route | Serves | Notes |
|-------|--------|-------|
| `GET /preview` | the `preview.json` "why" sidecar (`gen` / `tick` / `auto_candidate` / `cams`) | via the safe-default never-raise `read_preview` (RBT-04): an absent/torn file → a default `PreviewDoc`, never an exception |
| `GET /preview/<cam>.jpg` | one whitelisted per-camera JPEG via `send_file` | `<cam>` is whitelisted against the configured `cam_ids` and **never used as a raw filesystem path** (anti path-traversal, T-08-03 / T-05-05-01); unknown id → **404**; `Cache-Control: no-store` |

The on-disk JPEG path is built from a **FIXED** `preview/cam_{id}.jpg` prefix, so id `cam_wide` maps
to the file `cam_cam_wide.jpg` (the Pitfall-3 double-prefix mapping). A frame the publisher hasn't
written yet → **404** (the browser shows its placeholder).

Tiles populate **only** when the orchestrator runs with preview **ENABLED** (default ON since
Phase 7) and writes JPEGs into the **same** opcomm dir. The console's `SEGUGIO_OPCOMM_DIR` MUST
equal the orchestrator's `--opcomm-dir`.

### 4. Preview bandwidth cap (config-time guarantee, not a runtime throttle)

WiFi contention is the #1 domain risk (3-4 phones already push tens-to-hundreds of Mbps of NDI HX3),
so the preview must **degrade before** it can starve the NDI feeds. This is enforced **at config
load**, fail-fast, not by a runtime throttle:

- `PreviewParams.max_total_mbps` (default **`8.0`** Mbps) is the cap.
- `Config._preview_bitrate_within_cap` (a `@model_validator(mode="after")`) computes the worst-case
  bitrate `est_bytes_per_frame × 8 × fps × N_cams` and **rejects** any over-cap config with a
  `ValueError` that aggregates into the loader's `SystemExit(2)`. An over-budget preview is a
  **startup error**, not a live surprise.
- `preview.enabled: false` **short-circuits** the check (no JPEGs published → nothing to budget — the
  source-side off-switch).

For the `0.0.0.0` / LAN-trust posture (T-08-03 live-video exposure; **AP client-isolation + no
internet/guest bridge** as the HARD operational mitigation), see `docs/security.md` — do not
duplicate it here.

### 5. Troubleshooting "il telefono si vede in OBS ma non nella console"

The phone renders in OBS (DistroAV decodes it independently) but its console tile stays dead. Likely
causes, in order:

**(a) The `ndi_source` name does not EXACTLY match.** `src/segugio/ndi/ndi_source.py` `_resolve_source`
does a literal `source_name in names` match against `finder.get_source_names()`. A near-miss name
(`LOCALHOST (iPhone)` vs `LOCALHOST (iPhone Camera for OBS Studio App)`) silently never resolves, so
that camera coasts with no frames. Discover the live name and paste **that** exact string into
`ndi_source` (see the Prerequisites "discover them, don't hardcode" bullet).

**(b) Confirm HX decode + frame count with the diagnostic.** Run it from the venv that has cyndilib +
the system NDI 6.3.2 runtime (this box: **`venv312`**) with the phone's camera view ACTIVE:

```powershell
# Windows PowerShell — venv312 has cyndilib + the system NDI runtime; segugio is editable-installed
# there, so a plain invocation works:
venv312\Scripts\python.exe tools\verify_ndi_hx_decode.py "LOCALHOST (iPhone)"
# If `segugio` is NOT importable in the venv you run this from, prepend the src path:
$env:PYTHONPATH = "src"; venv312\Scripts\python.exe tools\verify_ndi_hx_decode.py "LOCALHOST (iPhone)"
```

Pass the **exact** advertised NDI source name as the first argument (default: `"LOCALHOST (iPhone)"`).
`PASS` = the version-pairing fix decodes the HX phone (frames at res > 0); `FAIL` (still 0x0) means
HX decode is not happening — re-check the system NDI runtime (Prerequisites) before blaming the
console.

**(c) List the live source names to copy the exact string.** A short cyndilib `Finder` discovery
one-liner prints the names the senders actually advertise:

```powershell
# Windows PowerShell — same venv as (b)
venv312\Scripts\python.exe -c "from cyndilib.finder import Finder; f=Finder(); f.open(); import time; time.sleep(2); print(f.get_source_names()); f.close()"
```

Copy the EXACT advertised name into the camera's `ndi_source` in config.

**(d) The load-bearing reminder — the console only RENDERS what the orchestrator PUBLISHES.** With no
orchestrator running (or with `preview.enabled: false`), no JPEGs are written, so every tile stays
DEAD (404 placeholders) **even when OBS sees the phone**. Start the orchestrator (Section 2 above),
preview-enabled, pointed at the SAME opcomm dir as the console.

For the NDI runtime / Access Manager / active-camera-view prerequisites, see the "Prerequisites" NDI
bullets above — they apply here unchanged.

---

## GPU latency env (Phase 6)

The decision-loop latency work (TensorRT FP16 + batched inference for RBT-05, `<150ms` p95)
needs a **CUDA-enabled** torch + a TensorRT runtime — neither is in the headless dev venv. The
current py3.14 venv has **CPU-only torch** (`2.12.0+cpu`) and **no `tensorrt` cp314 wheel**, so
every `-m gpu` test SKIPs there and nothing is measurable (project memory
`gpu-torch-cpu-only-py314.md`). Stand up a **py3.12** venv on the RTX 4000 Ada rig first.

> **Run all GPU work on AC power.** On battery the box throttles hard and inflates every
> CPU/latency reading — a measurement taken on battery is meaningless (project memory
> `dev-box-perf-on-ac.md`).

### Stand up the py3.12 cu12x-torch + tensorrt venv

```bash
# 0. Install Python 3.12 if absent (py3.14 / 3.13-Store have no cu12x torch + tensorrt cp wheels)
winget install Python.Python.3.12
# 1. Create a py3.12 venv
py -3.12 -m venv venv312
venv312\Scripts\activate
python -m pip install --upgrade pip
# 2. Install the CUDA-enabled torch + torchvision FIRST (NOT the +cpu wheel), matching the
#    deploy CUDA, so the next step's ultralytics does not drag in a CPU torch override.
#    Confirm the channel against the installed NVIDIA driver (596.36) on the rig — cu126
#    runs fine under driver 596.36 (driver >> CUDA 12.6 requirement).
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
# 3. Install Segugio's pinned stack (ultralytics sees the cu126 torch already present)
pip install -r requirements.txt
# 4. Install the TensorRT runtime wheel — pin the cu12 10.x variant to MATCH torch's CUDA 12.6.
#    NOTE: bare `pip install tensorrt` now resolves to 11.x pulling cu13 (CUDA 13) libs, which
#    mismatches the cu126 torch — use the explicit cu12 package instead:
pip install "tensorrt-cu12<11"
```

### Verify the GPU path is live BEFORE any export / measurement

```bash
# torch sees the CUDA device
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
#   → True   NVIDIA RTX 4000 Ada Generation
# tensorrt imports at a 10.x version
python -c "import tensorrt; print(tensorrt.__version__)"
#   → 10.x
# the gpu-marked latency test COLLECTS on this env (proves the marker resolves)
pytest tests/test_latency.py -m gpu --co -q
```

If `torch.cuda.is_available()` is **False** or `import tensorrt` fails, resolve the wheel/driver
mismatch (the cu12x channel vs. the installed driver) before doing any GPU work — every
downstream latency measurement is blocked until both probes pass.

### The `.engine` artifact is GPU-specific — rebuild per rig, never commit

A TensorRT `.engine` (and the intermediate `.onnx`) is **specific to the exact GPU + driver +
TensorRT version it was built on**. It is **never committed and never copied between GPUs** —
copying a foreign `.engine` either fails to load or silently mis-runs. Build it **on the deploy
rig** from the trusted locked `.pt`, as a one-time cached artifact beside the weights. The
`.engine`/`.onnx` files are gitignored so a foreign binary is never tracked.

### Build the engine (one-time, on the rig)

On the py3.12 GPU venv, on the RTX 4000 Ada, **on AC power**:

```bash
# Default: yolo26s.pt, imgsz=640, static batch=4, FP16, end2end=False, device=0
venv312\Scripts\python.exe tools/build_engine.py
```

It runs for **minutes** (the export compiles a GPU-specific engine) and writes
`yolo26s.engine` beside the weights — note the printed `engine written: <path>`. Flags:

```bash
venv312\Scripts\python.exe tools/build_engine.py --weights yolo26s.pt --imgsz 640 --batch 4
venv312\Scripts\python.exe tools/build_engine.py --dynamic   # dynamic-batch (reduced-camera op)
```

> The Ultralytics `format="engine"` export may pull in `onnx` / `onnxslim` / `onnxruntime`. If
> the export errors asking for them, install into the GPU venv and retry:
> `venv312\Scripts\python.exe -m pip install onnx onnxslim onnxruntime`.

**Caveats (do NOT skip):**

- **GPU-specific — rebuild per rig.** The engine binds to this exact GPU + driver (596.36) +
  TensorRT (10.16.x) combo. A new rig (or a driver/TensorRT upgrade) needs a fresh build.
- **AC power only.** On battery the box throttles and the build (and any subsequent latency
  measurement) is meaningless (project memory `dev-box-perf-on-ac.md`).
- **Static `batch=4`** matches the 4-cam fan-out; the loop pads dead-camera slots with a blank
  frame, so a static batch is valid. Use `--dynamic` only if reduced-camera operation must run
  on the engine.

### Point the loop at the engine

Set `model.engine_path` to the built `yolo26s.engine` in the config (and keep
`model.use_fp16: true`). `PerCameraTracker` loads the engine when `engine_path` is set and the
file exists, and on **any** load failure (missing / incompatible / wrong-GPU) degrades
gracefully to the eager `.pt` — it **never crashes** (RBT-04). A missing/incompatible engine is
the staleness signal; just rebuild and relaunch.
