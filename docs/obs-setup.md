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

> **The NDI name must BYTE-MATCH (D-08).** The OBS `NDI Source` `ndi_source_name`, the phone's
> published NDI sender name, and the camera's `ndi_source` in `config.example.yaml` /
> `config.agility.example.yaml` must be the **exact same string** — for example
> `"PHONE-WIDE (NDI HX3)"` (the canonical name in the committed scene collection and the
> agility config). A drifted or near-miss string is the recurring **"OBS sees it but the console
> is blank"** gotcha: OBS resolves and shows the feed, but the orchestrator/console — which
> matches on the config `ndi_source` — never decodes a frame. `tests/test_scene_template.py`
> asserts every example-config `ndi_source` byte-matches a scene `ndi_source_name` so this drift
> can never silently return; keep the live phone's published name aligned to it.

## Score overlay — browser-source (primary path)

The primary on-air score overlay is an OBS **Browser** source named **`Score Overlay`**, wired
into **all 7 scenes** (`SAFE`, `CAM Wide`, `CAM Long`, `CAM Low`, `CAM Handler`, `MULTIVIEW`,
`PIP`) **above** the NDI source (top of the scene's z-order). It loads the console's transparent
`/overlay` page, which renders the graphical lower-third and runs the run timer client-side. The
source ships in the committed `obs/segugio-scene-collection.json` and imports cleanly.

### URL — localhost default and the cross-machine edit

- **Default (single-box: OBS + console on the same Windows production PC):** the source ships
  with the URL exactly `http://localhost:8080/overlay` — the bare `/overlay` path on the
  console's serving port `:8080` (no `?preview=1`, no `?t=` cache-bust nonce; the page's own
  `/overlay-json` poll carries the freshness nonce). This imports cleanly and works as-is on the
  common single-box setup.
- **OBS and console on DIFFERENT machines:** when OBS runs on a separate box from the console
  (e.g. the console runs on its own host/tablet), **edit the `Score Overlay` source URL** to
  `http://<console-LAN-IP>:8080/overlay` — the console binds `0.0.0.0:8080` on the dedicated
  WiFi LAN, so use its LAN IP address. This is the one edit the cross-machine operator must make.

### Source / transparency settings

- **Resolution / FPS:** `1920×1080 @ 30 fps` (matches a standard OBS canvas and the ~30 Hz tick;
  light on the shared OBS box).
- **Transparency is page-owned:** the `/overlay` page sets `html, body { background: transparent }`
  itself, so do **NOT** inject any custom OBS CSS for transparency. Leave the source's **Custom
  CSS** at the OBS transparent default / empty (the committed source ships `css: ""`). Putting an
  opaque `background-color` in the source CSS would render the overlay on a black box over the
  video.
- **"Shutdown source when not visible" → OFF** and **"Refresh browser when scene becomes active"
  → OFF** (both unchecked). These keep the overlay from re-flashing or losing its timer state on a
  cut between cameras (SCN-01 rationale). In the scene-collection JSON these correspond to the
  obs-browser keys `shutdown: false` and `restart_when_active: false` respectively (note: the JSON
  keys differ from the UI labels).

### Re-import on an already-configured OBS box

Importing the collection **copies** the template into OBS's own profile — a later edit to the repo
`obs/segugio-scene-collection.json` does **NOT** auto-propagate into a running OBS install. On a
box that already imported an earlier collection, you must either **re-import** the updated
collection (*Scene Collection → Import*) **or** manually add the `Score Overlay` Browser source
(*Sources → + → Browser*) with the URL and settings above. Symptom of skipping this: "it works on
a fresh import but not on my box."

### CEF cache-clear (stale overlay after a renderer change)

The obs-browser (CEF) source can hold a stale copy of `/overlay` after the page is updated.

- **Per-source refresh (first try):** in OBS, right-click the **`Score Overlay`** source →
  *Properties* → **"Refresh cache of current page"**. (In some builds this behaves more like a
  reload than a full purge.)
- **Full cache purge (if a stale overlay persists):**
  1. Close OBS completely.
  2. Delete the cache folder under `%APPDATA%\obs-studio\plugin_config\obs-browser\` (the
     per-source CEF cache directories live here).
  3. Restart OBS — the browser source re-fetches `/overlay` fresh.

### Coexistence policy — Browser primary / Text fallback (manual toggle, RBT-06)

The browser overlay is the on-air score during normal operation. The `Score Text` read-from-file
source (see the fallback section below) stays wired in **every** scene but ships **`visible: false`**
by default — so there is never a double-score on air.

If the browser source **blanks or dies on-air**, the operator's **only** manual step is to toggle
`Score Text` **visible**. You do **not** also hide `Score Overlay` — the browser overlay
**auto-hides on death**: its client-side renderer (`overlay-render.js`) fully hides the lower-third
once the console stops answering polls past the `DEAD_MS` threshold (~3s, shipped in 14-01). So a
truly dead console's browser overlay vanishes on its own, leaving the revealed `Score Text` as the
single on-air score — no manual hide needed, no double-score.

**Auto-reveal on recovery.** If the console comes back during a still-running run (a recoverable
WiFi hiccup, not a true death), the browser overlay **auto-restores on its own**: the next
successful poll re-shows the lower-third (clears the death-hide and re-runs the enter animation),
so it resumes airing the live score with no operator action. If you manually revealed `Score Text`
during the outage, hide it again once the browser overlay is back to avoid a double-score (this is
the one manual cleanup step; revealing the text was the only manual action, and it does not
auto-hide).

(The earlier "also toggle `Score Overlay` hidden for a clean swap" step from Phase 13 is now
**redundant and removed**: the `DEAD_MS` auto-hide does the swap. Manually hiding the browser
source is harmless but unnecessary.)

There is still **no auto-reveal** of the text source — revealing `Score Text` is the operator's
deliberate one action; the text does not air on its own. Phase 14 validates this coexistence policy
end-to-end under console-death / browser-blank conditions.

## Score overlay — read-from-file (degraded fallback, OBS-05)

> **This is the fallback path, not the primary on-air overlay.** The primary on-air score is
> the **browser-source** documented above; this `Score Text` read-from-file source is the
> always-wired **degraded fallback** the operator manually toggles **visible** if the browser
> source blanks or dies on-air (RBT-06, see the coexistence policy above). It ships
> `visible: false` in every scene by default.

The fallback overlay uses an OBS **Text** source named **`Score Text`**, present inside every
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
