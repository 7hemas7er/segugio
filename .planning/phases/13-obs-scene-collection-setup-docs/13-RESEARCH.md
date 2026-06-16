# Phase 13: OBS Scene Collection & Setup Docs - Research

**Researched:** 2026-06-16
**Domain:** OBS Studio scene-collection JSON (obs-browser source schema, scene-item z-order), operator docs, pure-Python lockstep test extension, LAN browser-source threat re-eval
**Confidence:** HIGH

<user_constraints>
## User Constraints (from 13-CONTEXT.md)

### Locked Decisions
- **D-01:** The committed `obs/segugio-scene-collection.json` ships the browser-source URL as `http://localhost:8080/overlay` — the out-of-box default for the common single-box setup (OBS + console on the same Windows production box). `docs/obs-setup.md` documents the cross-machine LAN-IP edit (`http://<console-LAN-IP>:8080/overlay`) prominently.
- **D-02:** Port is `:8080` and the path is the **bare** `/overlay` — NOT `?preview=1` (console-iframe-only, locked Phase 12). No `?t=` cache-bust nonce on the host URL (the renderer's own `/overlay-json` poll carries the `++reqSeq` nonce; a host-URL nonce would force full reloads — Phase-12 Pitfall-2).
- **D-03:** The existing `Score Text` (`text_gdiplus_v2`, `read_from_file: overlay.txt`) stays wired in **every** scene but ships `visible: false` by default. Browser overlay is primary; `Score Text` is the degraded fallback the operator toggles **visible** if the browser blanks/dies on-air.
- **D-04:** The Browser-primary / Text-fallback coexistence policy (manual toggle-on-failure) is documented in `docs/obs-setup.md`. Phase 14 validates it end-to-end. It is a *manual-toggle* fallback by default, not an auto-reveal.
- **D-05:** The browser-source is wired into **all 7 scenes** — `SAFE`, `CAM Wide`, `CAM Long`, `CAM Low`, `CAM Handler`, `MULTIVIEW`, `PIP`. Full-frame lower-third over MULTIVIEW/PIP grids accepted as-is for v1 (no per-scene transform tuning this phase).
- **D-06:** Browser-source render settings: `width: 1920, height: 1080, fps: 30`, relying on the page's own `html, body { background: transparent }` — no extra OBS custom CSS injected.

### Claude's Discretion
- OBS source object shape: ONE shared source definition named `Score Overlay` (`id`/`versioned_id`: `browser_source`) referenced by an item in each scene's `items` — mirroring `Score Text` / `NDI - PHONE-*`. Do NOT duplicate a full browser source per scene.
- CEF settings on that source: shutdown-when-not-visible OFF, refresh-on-active OFF (SC-1 hard reqs — no re-flash / no timer-state loss on a cut), plus sober defaults (reroute_audio false, restart_when_active false, css default-transparent or empty).
- **Z-order:** the browser-source must render **above** the NDI source (and the hidden text). Verify whether index 0 is top or bottom and place accordingly. (RESOLVED — see Pitfall 1.)
- `docs/obs-setup.md`: a "Score overlay — browser-source (primary path)" section (URL + localhost default + cross-machine LAN-IP note + transparency/source settings + CEF cache-clear procedure) extending the existing "read-from-file" section.
- `docs/security.md`: append a one-paragraph threat re-evaluation for the same-origin LAN browser-source consuming `GET /overlay`.
- `tests/test_scene_template.py` extension: assert `Score Overlay` browser source exists with URL + transparency + shutdown-off + refresh-off, and that **every** scene references both `Score Overlay` and `Score Text` in lockstep with the scene-name set (reuse `_template_scene_names()` / `_config_obs_scenes()`).

### Deferred Ideas (OUT OF SCOPE)
- Per-scene placement/scale tuning of the overlay on MULTIVIEW/PIP — accepted as-is for v1.
- Auto-reveal text fallback (Score Text auto-airs without an operator toggle) — v1 is manual toggle; auto-switch is a Phase-14 / future consideration.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCN-01 | `obs/segugio-scene-collection.json` cables the browser-source (console http URL) into every CAM/SAFE scene with "shutdown when not visible" / "refresh on activate" OFF (no re-flash); `overlay.txt` text source stays wired as fallback | Exact `browser_source` JSON schema + verified setting keys (Standard Stack, Pattern 1); z-order placement (Pitfall 1); shared-def + per-scene-item pattern (Pattern 2) |
| SCN-02 | `docs/obs-setup.md` updated for the browser-source overlay (URL, transparency, source settings, cross-machine console/OBS deploy note) | CEF cache-clear procedure + cache path (Code Examples §CEF cache); transparency confirmation (Pitfall 3); cross-machine URL (D-01/D-02) |
| RBT-06 | `overlay.txt` retained as degraded fallback — browser primary, text "read from file" fallback if browser dies on-air | Score Text stays in all 7 scenes `visible:false` (D-03); lockstep test asserts both sources present (Validation Architecture) |
</phase_requirements>

## Summary

Phase 13 is a **packaging/config + docs** phase. It extends three existing artifacts — `obs/segugio-scene-collection.json`, `tests/test_scene_template.py`, and `docs/obs-setup.md` — and appends one paragraph to `docs/security.md`. No `segugio.ui` (Python) code changes; the `/overlay` route (port 8080) already serves a live transparent page (verified in `src/segugio/ui/app.py:286` and the page's `html, body { background: transparent !important }` at `overlay.html:17`). Crash-isolation (RBT-07) is therefore structurally unaffected.

The single highest-risk item is **the exact obs-browser JSON setting key names**: the human-facing OBS UI labels in the ROADMAP/CONTEXT ("shutdown when not visible", "refresh on activate") map to **different** JSON keys in the actual obs-browser plugin source — the keys are `shutdown` and `restart_when_active`, NOT `shutdown_source_when_not_visible` / `refresh_when_scene_is_active`. The second-highest-risk item, **z-order**, is now resolved authoritatively from the OBS scene save/load source: the FIRST element of a scene's `items` array is the BOTTOM layer and the LAST is the TOP — so `Score Overlay` must be appended **after** the NDI source in each scene's `items` (which is exactly why the existing `Score Text`, listed last, currently renders over the video).

**Primary recommendation:** Add ONE shared `browser_source` def named `Score Overlay` (keys: `url`, `width:1920`, `height:1080`, `fps:30`, `fps_custom:true`, `shutdown:false`, `restart_when_active:false`, `reroute_audio:false`, `css:""`) and append a `{ "name": "Score Overlay", "visible": true }` item as the **last** entry of every scene's `items` array (above NDI; above/with the hidden Score Text). Keep Score Text wired in all 7 scenes but flip its per-scene item to `visible: false`. Extend the lockstep test to parse and assert both source defs + per-scene presence. Document the URL/transparency/CEF-cache procedure and append a security paragraph reusing the established T-05-05-04 / T-08-03 LAN trust boundary.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Render the score overlay on-air | OBS (obs-browser CEF) loading `GET /overlay` | Console (Flask serves the page + `/overlay-json`) | The browser source is an OBS-side consumer of an already-live console route; this phase only configures the OBS side. |
| Degraded fallback overlay | OBS (`text_gdiplus_v2` reading `overlay.txt`) | Orchestrator (atomic write of `overlay.txt`) | The text source is OBS state; the file is written off-tick by the orchestrator (unchanged this phase). |
| Template↔config lockstep guard | Test harness (pure json/yaml parse) | — | A build-time invariant; no OBS runtime, no `segugio.ui` import. |
| Operator setup knowledge | Docs (`docs/obs-setup.md`, `docs/security.md`) | — | One-time manual OS-level state on the OBS box; documented, not code-migrated. |

## Standard Stack

This phase introduces **no new runtime dependencies** and **no new packages**. It edits a JSON data file, a Markdown doc pair, and a pure-Python test that already uses `pytest` + `pyyaml` (`tests/test_scene_template.py:13-15`).

### Core (existing, used by the artifacts touched)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest` | already in dev env (py3.14 `venv/`) | Runs the lockstep test | Existing test framework; `tests/test_scene_template.py` already green (3 passed, verified this session) [VERIFIED: `python -m pytest tests/test_scene_template.py -q` → 3 passed] |
| `pyyaml` | existing | Parse `config.example.yaml` / `config.agility.example.yaml` for the scene-name cross-check | Already imported as `yaml` in the test [VERIFIED: codebase grep] |
| Python `json` (stdlib) | 3.14 | Parse the scene-collection template | Already used by `_template_scene_names()` |

### Runtime targets (external, operator-installed — not Python deps)
| Component | Version | Purpose | Notes |
|-----------|---------|---------|-------|
| OBS Studio | 28+ (docs target; 30+/32.x current) | Hosts the browser source via the bundled obs-browser (CEF) plugin | obs-browser ships built-in since OBS 28 [CITED: obsproject/obs-browser] |
| DistroAV (obs-ndi) | current | Provides the `ndi_source` input kind already in the collection | Already documented in `docs/obs-setup.md:13` |

## Package Legitimacy Audit

> **Not applicable.** This phase installs no external packages. It edits an OBS JSON data file, two Markdown docs, and extends an existing pure-Python test that uses already-present `pytest` + `pyyaml`. No npm/PyPI/crates install occurs.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Orchestrator (director)                Console (Flask + segugio.opcomm only)
   │ atomic_write_text(overlay.txt)        │  GET /overlay      → overlay.html (transparent, polls /overlay-json)
   │ atomic publish overlay_run.json ──────┤  GET /overlay-json → {discipline, fields, running, server_now, gen}
   ▼                                        ▼  (binds 0.0.0.0:8080)
overlay.txt (on disk)                  http://<host>:8080/overlay
   │                                        │
   │  [degraded fallback path]              │  [primary path]
   ▼                                        ▼
 OBS Studio  ── scene "CAM Wide" (and 6 others) ──────────────────────────────
   items array (z-order: index 0 = BOTTOM ─────────────► last = TOP):
     [0] NDI - PHONE-* (ndi_source)          ◄── video base layer
     [1] Score Text (text_gdiplus_v2)        ◄── read_from_file overlay.txt, visible:false (fallback)
     [2] Score Overlay (browser_source)      ◄── url=http://localhost:8080/overlay, visible:true (PRIMARY, TOP)
   ───────────────────────────────────────────────────────────────────────────
   composited program output ──► OBS program / stream
```

Data flow: the dog/score data enters from the orchestrator and console; OBS composits the browser overlay (and, when the operator toggles it on, the text fallback) over the NDI video, bottom-to-top, into the program output.

### Recommended "Project Structure" (files this phase touches)
```
obs/
└── segugio-scene-collection.json   # ADD one Score Overlay browser_source def; ADD a per-scene item to all 7 scenes; flip Score Text items to visible:false
tests/
└── test_scene_template.py          # EXTEND: helpers to read source defs + per-scene items; new lockstep assertions
docs/
├── obs-setup.md                    # ADD "Score overlay — browser-source (primary path)" section + cross-machine URL + CEF cache + coexistence policy
└── security.md                     # APPEND one-paragraph browser-source threat re-eval
```

### Pattern 1: The exact obs-browser source object shape
**What:** A scene-collection source whose `id`/`versioned_id` is `browser_source`, with `settings` carrying the verified obs-browser keys.
**When to use:** The single shared `Score Overlay` def (Discretion: shared def, not per-scene duplication).
**Example (imports cleanly into OBS 28+/30+):**
```json
{
  "name": "Score Overlay",
  "id": "browser_source",
  "versioned_id": "browser_source",
  "settings": {
    "url": "http://localhost:8080/overlay",
    "width": 1920,
    "height": 1080,
    "fps_custom": true,
    "fps": 30,
    "shutdown": false,
    "restart_when_active": false,
    "reroute_audio": false,
    "css": ""
  }
}
```
- `url` [VERIFIED: obsproject/obs-browser `obs-browser-source.cpp` `BrowserSource::Update` reads `obs_data_get_string(settings, "url")`]
- `width` / `height` (ints; default 800/600) [VERIFIED: obs-browser `browser_source_get_defaults`]
- `fps_custom` (bool; default false). **Set `true`** so the explicit `fps:30` (D-06) actually applies; with shared-texture builds the FPS field is otherwise ignored unless `fps_custom` is on [VERIFIED: obs-browser defaults]. With `fps_custom:false` OBS renders the browser at the canvas/output FPS — acceptable, but to *guarantee* 30 per D-06, set `fps_custom:true`.
- `fps` (int; default 30) [VERIFIED: obs-browser defaults]
- `shutdown` (bool; default false) — this is the JSON key for the UI's **"Shutdown source when not visible"**. SC-1 requires it OFF → `false`. [VERIFIED: obs-browser `Update`/defaults]
- `restart_when_active` (bool; default false) — this is the JSON key for the UI's **"Refresh browser when scene becomes active"**. SC-1 requires it OFF → `false`. [VERIFIED: obs-browser `Update`/defaults]
- `reroute_audio` (bool; default false) → `false` [VERIFIED: obs-browser defaults]
- `css` (string). obs-browser default is `"body { background-color: rgba(0, 0, 0, 0); margin: 0px auto; overflow: hidden; }"`. Per D-06 we rely on the page's own transparency and inject NO extra CSS → ship `""` (empty) OR omit the key entirely so OBS applies its own transparent default. **Either is transparent** (see Pitfall 3). [VERIFIED: obs-browser default css string]

> **Naming gotcha resolved:** the ROADMAP/CONTEXT use the *UI labels* "shutdown_source_when_not_visible" and "refresh_when_scene_is_active". The actual obs-browser **JSON keys are `shutdown` and `restart_when_active`.** Using the UI-label strings as JSON keys would silently no-op (OBS would fall back to defaults — which happen to be `false` here, so it would *look* correct but be untested/unportable). The plan MUST use `shutdown` / `restart_when_active`.

### Pattern 2: Shared source def + per-scene item reference
**What:** Define `Score Overlay` ONCE in the top-level `sources` array; reference it by name in each scene's `settings.items`.
**When to use:** Always here — mirrors how `Score Text` and `NDI - PHONE-*` are already done (`segugio-scene-collection.json:106-138`).
**Example (per-scene item, appended LAST so it's on top):**
```json
"items": [
  { "name": "NDI - PHONE-WIDE (NDI HX3)", "visible": true },
  { "name": "Score Text", "visible": false },
  { "name": "Score Overlay", "visible": true }
]
```
For MULTIVIEW/PIP, the four NDI items stay first (bottom), then `Score Text` (`visible:false`), then `Score Overlay` last (top).

### Anti-Patterns to Avoid
- **Duplicating a full `browser_source` def per scene** — bloats the file and breaks the established single-def pattern; the lockstep test should assert exactly one `Score Overlay` source def.
- **Placing the `Score Overlay` item FIRST in `items`** — that's the BOTTOM layer; the NDI video would cover the overlay (see Pitfall 1).
- **Using the UI-label strings (`shutdown_source_when_not_visible`, `refresh_when_scene_is_active`) as JSON keys** — they are not the real keys; OBS ignores them.
- **Adding a `?t=` nonce or `?preview=1` to the host URL** — locked OUT by D-02 (Phase-12 reasoning).
- **Injecting custom OBS CSS for transparency** — locked OUT by D-06; the page owns transparency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transparency over NDI video | Custom OBS CSS or a chroma-key filter | The page's own `html, body { background: transparent }` (already present, `overlay.html:17`) + obs-browser's default transparent body | obs-browser composits the page alpha natively; extra CSS is redundant and risks a non-transparent override (Pitfall 3). |
| Verifying browser/text sources per scene | Ad-hoc string matching | Extend `_template_scene_names()` + add a per-scene `items` parser that reuses the existing scene-name set | The existing helper already establishes the scene set and the `scene_order ⊆ sources` invariant; build on it, don't reinvent. |
| Knowing the obs-browser setting keys | Guessing from the UI labels | The verified keys (`shutdown`, `restart_when_active`, etc.) | UI labels ≠ JSON keys — the #1 silent-failure vector here. |

**Key insight:** Every "build it" temptation in this phase already has a verified primitive (page transparency, the lockstep helper, the obs-browser default CSS). The work is wiring, not building.

## Runtime State Inventory

> This is a packaging/config + docs phase touching an OBS JSON, a test, and docs — but it DOES change OS-level / operator-imported state. Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore stores the new source name as a key/id. The `overlay.txt` content contract is unchanged (orchestrator still writes it atomically). | None — verified: this phase writes no orchestrator code and changes no on-disk data contract. |
| Live service config | **The OBS scene collection itself is operator-imported OS-level state** on the production box (`%APPDATA%/obs-studio/basic/scenes/*.json` after import). The committed `obs/segugio-scene-collection.json` is the *template*; the operator must **re-import** (or hand-add the source) for changes to take effect on an already-configured box. | Document in `docs/obs-setup.md` that an existing install must re-import the updated collection (or manually add the `Score Overlay` browser source) — the file edit does not auto-propagate into a running OBS profile. |
| OS-registered state | None — no Task Scheduler / pm2 / service registration references the overlay source. | None — verified: no scheduler/service touches OBS source names. |
| Secrets / env vars | None new. The obs-websocket :4455 password (`docs/obs-setup.md:18-19`) is unchanged; the browser URL carries no secret. | None. |
| Build artifacts / installed packages | **obs-browser CEF cache** (`%APPDATA%/obs-studio/plugin_config/obs-browser/`) can hold a stale copy of `/overlay` after a renderer change. | Document the CEF cache-clear procedure (Code Examples §CEF cache) — this is the real "stale overlay after a fix" gotcha for the operator. |

**The canonical question** — *after the repo file is updated, what runtime systems still have the old state?* Answer: (1) an already-imported OBS scene collection on the box (must re-import / hand-edit), and (2) the obs-browser CEF cache of the previous page (must "Refresh cache of current page" or delete the cache dir). Both are operator actions, documented in `docs/obs-setup.md`.

## Common Pitfalls

### Pitfall 1: Z-order — placing the overlay item at the wrong end of `items`
**What goes wrong:** The browser overlay is hidden behind the NDI video and never appears on-air.
**Why it happens:** A scene's `settings.items` array is ordered **bottom-to-top**: index 0 is the BOTTOM (rendered first, behind everything), the LAST element is the TOP (rendered last, in front). This is the OPPOSITE of how the OBS UI Sources list reads (top of the UI list = front), which causes the confusion.
**Authoritative basis:** OBS `scene_save` iterates `scene->first_item` forward through the linked list (first_item = bottom-most), and `scene_load` re-inserts each item appended to the end with `insert_after=NULL`, preserving saved order — so the first array element loads as the bottom layer. [VERIFIED: obsproject/obs-studio `libobs/obs-scene.c` `scene_save`/`scene_load`]
**Confirmation in our own file:** the existing `Score Text` is listed LAST in every scene's `items` and currently renders OVER the NDI video (the score is visible) — empirical proof that last = top in this exact file.
**How to avoid:** Append `{ "name": "Score Overlay", ... }` as the **last** element of every scene's `items` array. Keep NDI first (bottom). `Score Text` sits between (visible:false). When the operator toggles `Score Text` visible, it will render below `Score Overlay` if you keep Overlay last — acceptable (a hidden browser blank shows the text behind it). If you want the text fallback to sit ON TOP when toggled, place `Score Text` last instead and `Score Overlay` second; **recommended: keep `Score Overlay` last** so the primary path is always frontmost during normal operation.
**Warning signs:** Overlay invisible in program but the source shows content in Properties; reordering in the UI "fixes" it (a tell that the JSON order was wrong).

### Pitfall 2: UI label vs JSON key mismatch (the silent no-op)
**What goes wrong:** SC-1's "shutdown OFF / refresh OFF" requirement is written into the JSON under the wrong key, OBS ignores it, and the setting silently takes its (coincidentally `false`) default — untested, and brittle if defaults ever change.
**Why it happens:** The ROADMAP/CONTEXT name the settings by their **UI labels** (`shutdown_source_when_not_visible`, `refresh_when_scene_is_active`).
**How to avoid:** Use the real obs-browser keys: `shutdown` and `restart_when_active`. [VERIFIED: obs-browser source]
**Warning signs:** The lockstep test passing only because it asserts the wrong key name — assert the REAL keys.

### Pitfall 3: Transparency override
**What goes wrong:** The overlay renders on an opaque (black/white) box, covering the video.
**Why it happens:** A non-transparent `css` value injected into the source, OR a page that doesn't set a transparent body.
**How to avoid:** Our page already sets `html, body { background: transparent !important }` (`overlay.html:17`). obs-browser's **default** `css` is also transparent (`body { background-color: rgba(0,0,0,0); ... }`). Ship `css: ""` (empty) or omit `css` so OBS uses its transparent default — D-06 forbids injecting custom CSS. Either path is transparent; do NOT put an opaque background in `css`.
**Warning signs:** Black rectangle in the lower-third on-air; a `css` value containing a non-zero-alpha `background-color`.

### Pitfall 4: Operator forgets to re-import on an already-configured box
**What goes wrong:** The repo JSON is updated, but the OBS box still runs the old imported collection — the overlay never appears.
**Why it happens:** Importing copies the template into OBS's own profile; the file edit doesn't propagate.
**How to avoid:** `docs/obs-setup.md` must state explicitly: on an existing install, re-import the updated collection (or manually add the `Score Overlay` browser source via *Sources → + → Browser*).
**Warning signs:** "It works on a fresh import but not on my box."

## Code Examples

### Extended scene-collection scene (one CAM scene, after edit)
```json
{
  "name": "CAM Wide",
  "id": "scene",
  "versioned_id": "scene",
  "settings": {
    "custom_size": false,
    "items": [
      { "name": "NDI - PHONE-WIDE (NDI HX3)", "visible": true },
      { "name": "Score Text", "visible": false },
      { "name": "Score Overlay", "visible": true }
    ]
  }
}
```

### CEF cache-clear procedure (for `docs/obs-setup.md`)
```
Per-source refresh (first try):
  In OBS, right-click the "Score Overlay" source → Properties → "Refresh cache of current page".
  (Note: this behaves more like a reload than a full cache purge in some builds.)

Full cache purge (if a stale overlay persists after a renderer change):
  1. Close OBS completely.
  2. Delete the cache folder under:  %APPDATA%\obs-studio\plugin_config\obs-browser\
     (the per-source CEF cache directories live here).
  3. Restart OBS — the browser source re-fetches /overlay fresh.
```
[CITED: auctionslive.com refresh-obs-browser-cache; obsproject.com/forum thread 55222 — cache at `%appdata%\obs-studio\plugin_config\obs-browser`]

### Cross-machine URL note (for `docs/obs-setup.md`)
```
Default (single-box: OBS + console on the same Windows PC):
  http://localhost:8080/overlay   ← ships in the committed collection, imports cleanly.

OBS and console on DIFFERENT machines (console on a separate box/tablet host):
  Edit the "Score Overlay" source URL to:
  http://<console-LAN-IP>:8080/overlay
  (the console binds 0.0.0.0:8080 on the dedicated WiFi LAN — use its LAN IP).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Text-on-file score overlay only (`Score Text`, OBS-05) | Browser-source graphical lower-third primary + text-on-file as degraded fallback | v1.2 (Phases 10–14) | Text source is retained, not replaced (RBT-06); this phase wires the browser source above it. |
| obs-ndi | DistroAV (rebrand) | 2024 | Same `ndi_source` kind; already in the collection — no change this phase. |

**Deprecated/outdated:**
- Treating the OBS UI labels as JSON keys — never correct; use `shutdown` / `restart_when_active`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fps_custom: true` is required for the explicit `fps:30` to apply on the operator's OBS build (shared-texture builds ignore `fps` unless `fps_custom` is on). | Pattern 1 | LOW — if wrong, OBS renders at canvas FPS (still fine for a lower-third). Verified the default keys exist; the *conditional* ignore behavior is build-dependent. Mitigation: set `fps_custom:true` (safe either way). |
| A2 | Re-importing the collection (vs OBS auto-detecting the file change) is required on an already-configured box. | Runtime State Inventory / Pitfall 4 | LOW — standard OBS import semantics (import copies into the profile); documented as an operator step regardless. |

**All other claims are VERIFIED against obs-browser / obs-studio source or CITED.** A1/A2 are operationally conservative (the recommended setting is safe under either truth value).

## Open Questions

1. **Should `Score Overlay` or `Score Text` be the topmost (last) item when both are present?**
   - What we know: both render above NDI; `Score Text` ships `visible:false`, so during normal operation only `Score Overlay` is visible regardless of relative order.
   - What's unclear: when the operator toggles `Score Text` visible (browser-blank failure), do they want text ON TOP of the (blank/stale) browser, or is hiding the browser part of the manual procedure?
   - Recommendation: keep `Score Overlay` LAST (topmost) for the primary path; document that the browser-blank response is "toggle `Score Text` visible AND toggle `Score Overlay` hidden" (clean swap). This keeps z-order unambiguous and matches D-04's manual-toggle policy. (Planner/Phase-14 decision; not blocking.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + `pytest` + `pyyaml` | Running the extended lockstep test | ✓ | py3.14 `venv/`, test green (3 passed) | — |
| OBS Studio 28+ + obs-browser (CEF) | Hosting the browser source (operator box, runtime) | n/a in dev (validated on the OBS box, Phase 14) | — | Text fallback (`overlay.txt`) airs if browser fails — RBT-06 |
| Console serving `:8080/overlay` | The browser-source target | ✓ (route live, `app.py:286`) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** OBS-side validation of the actual import/render is deferred to Phase 14 (the live gate); this phase's deliverables are file/test/doc edits verifiable in the dev env.

## Validation Architecture

> nyquist_validation = true in `.planning/config.json` — this section is required and read by the Nyquist gate. The test stays PURE (json/yaml parse only, no OBS runtime, no `segugio.ui` import).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (py3.14 `venv/`) |
| Config file | none dedicated — repo-root pytest invocation |
| Quick run command | `python -m pytest tests/test_scene_template.py -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCN-01 | `Score Overlay` browser_source def exists with url=`http://localhost:8080/overlay`, `shutdown:false`, `restart_when_active:false`, transparent (`css` empty/absent or default), `id==browser_source` | unit | `python -m pytest tests/test_scene_template.py -q` | ✅ extend |
| SCN-01 | `Score Overlay` is referenced (item) in EVERY scene, layered LAST (top) in each scene's `items` | unit | same | ✅ extend |
| RBT-06 | `Score Text` (`text_gdiplus_v2`, read_from_file overlay.txt) still referenced in EVERY scene (lockstep with the scene-name set) | unit | same | ✅ extend |
| SCN-01/RBT-06 | Both `Score Overlay` and `Score Text` present in every scene, in lockstep with `_template_scene_names()` | unit | same | ✅ extend |

### How `tests/test_scene_template.py` is extended
- Add a helper `_scene_items(scene_name) -> list[dict]` (or `_template_scene_items() -> dict[str, list[name]]`) that reads each scene source's `settings.items` from the SAME parsed JSON `_TEMPLATE` already loaded by `_template_scene_names()`.
- Add a helper `_source_def(name) -> dict | None` returning the top-level `sources` entry whose `name == name` (used to fetch the `Score Overlay` settings and assert keys/values).
- New tests (reusing `_template_scene_names()` to drive the per-scene loop so the assertions stay in LOCKSTEP with the scene set):
  - `test_score_overlay_source_def`: one source named `Score Overlay`, `id == "browser_source"`, `settings.url == "http://localhost:8080/overlay"`, `settings.shutdown is False`, `settings.restart_when_active is False`, and transparency holds (`settings.get("css", "")` contains no opaque `background` — assert it is empty/absent OR exactly the obs-browser transparent default).
  - `test_every_scene_has_overlay_and_text`: for each scene in `_template_scene_names()`, its `items` contains BOTH `"Score Overlay"` and `"Score Text"`.
  - `test_overlay_is_top_layer`: for each scene, the `"Score Overlay"` item is the LAST element of `items` (top of z-order) and appears AFTER any `NDI - *` item.
  - `test_score_text_is_fallback_hidden` (optional, encodes D-03): the `"Score Text"` item ships `visible: false` in every scene.
- The existing `test_template_scene_names_match_config` and `test_template_exists` are unchanged; the SAFE-first-class assertion remains.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_scene_template.py -q`
- **Per wave merge:** `python -m pytest -q`
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- None — `tests/test_scene_template.py` exists and is green; this phase extends it in place. No new framework/fixture install needed.

## Security Domain

> security_enforcement is absent in config (= enabled). This phase writes NO new code surface; the security work is the one-paragraph `docs/security.md` re-eval.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Accepted no-auth LAN field tool (T-05-05-04) — unchanged |
| V3 Session Management | no | No sessions; stateless GET |
| V4 Access Control | no | LAN trust boundary (operational, AP client isolation) — unchanged |
| V5 Input Validation | yes (reused) | Overlay values sanitized at the HTML sink via `textContent` (Phase 11) — display-only, no adjudication |
| V6 Cryptography | no | No secrets in the browser URL; obs-websocket password unchanged |

### Known Threat Patterns for the new browser-source surface
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LAN peer reads the overlay/score | Information Disclosure (T-08-03) | Already-accepted LAN trust boundary + mandatory AP client isolation (operational, documented) |
| HTML injection of operator-typed values into the broadcast | Tampering | `textContent` sink in `overlay-render.js` (Phase 11, frozen); Phase 14 acceptance |
| Poll storm starving `/command` | Denial of Service | `threaded=True`/Waitress (UXT-02); browser polls `/overlay-json` only — Phase 14 extends the concurrency test |

### What the one-paragraph `docs/security.md` re-eval should say
Append (after the v1.1 content, e.g. a short "Phase 13 — browser-source overlay" note): the new OBS browser-source is a **same-origin LAN consumer** of the existing `GET /overlay` route — it adds **no new server route and no new code path** (the route shipped in Phase 11). It is **display-only** (SCR-04): it renders operator-typed score values **verbatim**, sanitized at the HTML sink via `textContent` (never `innerHTML`), and never adjudicates. It reuses the established trust boundary unchanged: the dedicated WiFi LAN with AP client isolation (T-05-05-04 / T-08-03); **no new authentication, no configurable bind, no new exposure** beyond what `0.0.0.0:8080` already serves. The browser source is just another client of an already-exposed, already-assessed read endpoint — the v1.1 posture is reaffirmed, not changed. Revisit only if Segugio stops being a single-operator-LAN field tool.

## Sources

### Primary (HIGH confidence)
- obsproject/obs-browser `obs-browser-source.cpp` (`BrowserSource::Update`) — exact setting keys: `url`, `width`, `height`, `fps`, `fps_custom`, `shutdown`, `restart_when_active`, `reroute_audio`, `css`.
- obsproject/obs-browser `browser_source_get_defaults` — default values: width 800, height 600, fps 30, fps_custom false, shutdown false, restart_when_active false, reroute_audio false, css `body { background-color: rgba(0,0,0,0); margin:0px auto; overflow:hidden; }`.
- obsproject/obs-studio `libobs/obs-scene.c` (`scene_save` / `scene_load`) — items array order = bottom-to-top; first element = bottom layer, last = top.
- `obs/segugio-scene-collection.json` (this repo) — empirical confirmation: `Score Text` listed last renders over NDI video.
- `src/segugio/ui/app.py:286,403` — `/overlay` route + 0.0.0.0:8080 bind; `overlay.html:17` — page transparency.
- `python -m pytest tests/test_scene_template.py -q` → 3 passed (this session).

### Secondary (MEDIUM confidence)
- auctionslive.com "How to Refresh Browser Source Cache in OBS Studio (Windows)" + obsproject.com/forum thread 55222 — CEF cache at `%APPDATA%\obs-studio\plugin_config\obs-browser`.
- OBS docs reference-scenes / libobs enumeration "bottom-most to top-most" — corroborates z-order direction.

### Tertiary (LOW confidence)
- General OBS forum/blog z-order discussion (contradictory; superseded by the obs-scene.c source read above).

## Metadata

**Confidence breakdown:**
- Standard stack / browser_source schema: HIGH — verified against obs-browser source for both keys and defaults.
- Z-order placement: HIGH — verified against obs-scene.c save/load AND corroborated by the existing file's working Score Text.
- CEF cache procedure: MEDIUM — consistent across multiple operator guides + forum, not a single canonical doc.
- Security re-eval scope: HIGH — reuses the already-written v1.1 trust boundary; no new surface.

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (stable; obs-browser keys are long-lived. Re-verify only if targeting a future OBS that renames the browser source keys.)

## RESEARCH COMPLETE

**Phase:** 13 - OBS Scene Collection & Setup Docs
**Confidence:** HIGH

### Key Findings
- The obs-browser JSON keys are `shutdown` and `restart_when_active` — NOT the UI-label strings in the ROADMAP/CONTEXT. Using the UI labels silently no-ops. This is the #1 correctness item.
- Z-order RESOLVED authoritatively: in a scene's `items` array, **index 0 = BOTTOM, last = TOP** (verified in obs-scene.c `scene_save`/`scene_load`, and confirmed by the existing file where `Score Text` is last and renders over NDI). `Score Overlay` must be appended LAST in every scene.
- Verified full `browser_source` def with exact defaults (width/height/fps/css transparent default); ship `css:""` (page owns transparency per D-06).
- CEF cache lives at `%APPDATA%\obs-studio\plugin_config\obs-browser\`; per-source "Refresh cache of current page" + full-purge procedure documented.
- No new packages, no new code surface; crash-isolation (RBT-07) structurally unaffected; existing lockstep test green and extensible in place.

### File Created
`.planning/phases/13-obs-scene-collection-setup-docs/13-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack (browser_source schema) | HIGH | Verified key names + defaults from obs-browser source |
| Architecture (z-order, shared-def pattern) | HIGH | Verified from obs-scene.c + empirical existing-file confirmation |
| Pitfalls | HIGH | Each pitfall traced to a verified source or the existing file |

### Open Questions
- Topmost layer between `Score Overlay` and the (toggled-on) `Score Text` fallback — recommendation: keep `Score Overlay` last and document "toggle text visible AND overlay hidden" as the failure response. Non-blocking; planner/Phase-14 decision.

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
