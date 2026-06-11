# OBS setup (Segugio) — one-time manual import (OBS-04)

Segugio drives OBS Studio over **obs-websocket v5**. OBS, its plugins, and the scene
collection are configured **once** on the Windows production box; the orchestrator only
*controls* the already-imported collection (cut / PIP / overlay), it never creates scenes.

This is a manual, one-time step (RESEARCH §Runtime State Inventory): the scene-collection
template is OS-level state on the OBS box, not a code-migrated artifact.

## Prerequisites

1. **OBS Studio 28+** (ships obs-websocket v5 built in).
2. **DistroAV** (formerly obs-ndi) NDI plugin — provides the `NDI Source` input kind the
   phone feeds appear under. Install the NDI runtime it depends on.
3. **obs-websocket v5 enabled**: *Tools → WebSocket Server Settings* →
   - Enable WebSocket server (default port **4455**).
   - Set a server password and inject it into the orchestrator via the controller
     constructor (config/env on the box). **Never commit the password** — the
     localhost / dedicated-LAN bind is the documented trust boundary (T-05-03-03).

## Import the scene collection

1. *Scene Collection → Import*.
2. Select `obs/segugio-scene-collection.json` from this repo.
3. *Scene Collection → switch to "Segugio"*.

The collection ships these scenes — the names match `Camera.obs_scene` in
`config.example.yaml` / `config.agility.example.yaml` exactly (the orchestrator cuts by these
names; `tests/test_scene_template.py` keeps them in lockstep):

| Scene         | Role                                                              |
| ------------- | ---------------------------------------------------------------- |
| `SAFE`        | First-class fallback scene — the `is_safe` camera (RBT-02).      |
| `CAM Wide`    | `cam_wide` — also the SAFE camera in the reference config.       |
| `CAM Long`    | `cam_long`.                                                      |
| `CAM Low`     | `cam_low`.                                                       |
| `CAM Handler` | `cam_handler` (optional 4th).                                    |
| `MULTIVIEW`   | All feeds in a grid — **manual / idle-only in v1**.              |
| `PIP`         | Picture-in-picture composite — **manual / idle-only in v1**.     |

After import you must point each `NDI Source` at the actual NDI sender name your phones
publish (the `ndi_source` values in config, e.g. `PHONE-WIDE (NDI HX3)`): select the source →
*Properties* → pick the discovered NDI source. The template carries placeholder source names so
the structure imports cleanly.

## Score overlay — read-from-file (primary path, OBS-05)

The score overlay uses an OBS **Text** source named **`Score Text`**, present inside every
`CAM *` / `SAFE` scene, configured with **Read from file** pointing at the orchestrator's
atomic overlay file (`overlay.txt`).

- The score manager (05-05) writes the rendered Italian overlay line atomically
  (`segugio.opcomm.atomic.atomic_write_text` → temp + fsync + `os.replace`), so OBS never reads
  a half-written or blank line (SCR-01 / Pitfall 6).
- Set the **Read from file** path on the `Score Text` source to the same `overlay.txt` the
  orchestrator writes (absolute path on the box).
- The text input **kind is never hardcoded** in code — the controller's
  `set_overlay_text(...)` one-shot fallback only sets the generic `{"text": ...}` field via
  `set_input_settings`, which is identical across text-source kinds (Pitfall 5). The
  read-from-file source is the steady-state path; `set_overlay_text` is for one-shots only.

## PIP / MULTIVIEW — manual / idle-only in v1

The controller builds the PIP machinery (it caches the numeric `sceneItemId` of each PIP source
at connect, OBS-02), but v1 does **not** auto-drive PIP/MULTIVIEW (ARCHITECTURE Part 5). Switch
to these scenes manually (e.g. between runs) if desired. Auto-driven PIP/MULTIVIEW is a deferred
v2 idea.

## Verify (D-07 E2E, on the Windows box)

```powershell
python -c "import obsws_python as o; print(o.__version__)"   # expect 1.8.0
```

With OBS running and the collection active, the orchestrator's `ObsWsController.connect()`
caches the PIP `sceneItemId`s, registers the EventClient (so a manual scene change syncs back
into the FSM, OBS-03), and `cut("CAM Long")` switches the program scene. A websocket drop
(close/reopen OBS) must trigger reconnect+reauth and resume cutting without crashing the
director (RBT-04 / Pitfall 4).
