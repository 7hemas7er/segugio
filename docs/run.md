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

- **Editable install done** (the `src/`-layout package is importable):
  `pip install -e .`
- **Config** points each camera's `ndi_source` at the discovered phone / mock sender name
  (the `ndi_source:` values in `config.example.yaml` — e.g. `"PHONE-WIDE (NDI HX3)"`). The names
  must match what the NDI senders actually advertise on the dedicated WiFi.
- **OBS Studio** running with the DistroAV (NDI) plugin and the imported scene collection
  (one scene per camera + a SAFE scene). See [`docs/obs-setup.md`](obs-setup.md) for the scene
  collection, the obs-websocket v5 host/port/password, and the read-from-file overlay text source.
- **obs-websocket v5** enabled. v1 uses the defaults `localhost:4455`, no password (the
  orchestrator passes `host="localhost", port=4455, password=None` — `Config` has no `obs`
  block yet). If your OBS uses a different host/port/password, that is a future config-model
  change; for now run OBS with the defaults on the same box.

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
