# Phase 13: OBS Scene Collection & Setup Docs - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Package the transparent `/overlay` browser-source into the **existing** curated OBS scene-collection (`obs/segugio-scene-collection.json`), wired into every scene above the NDI source with CEF settings that prevent re-flash / timer-state loss on a cut; keep the already-wired `overlay.txt` "read from file" text source as the always-present degraded fallback (RBT-06); extend `tests/test_scene_template.py` to assert browser + text sources in lockstep with the scene names; and update operator docs (`docs/obs-setup.md` browser-source section + a one-paragraph threat re-eval appended to `docs/security.md`).

**Delivers:** SCN-01, SCN-02, RBT-06 (RBT-07 crash-isolation is unaffected — this phase writes NO `segugio.ui` code; it touches an OBS JSON, a test, and docs).

**This is a packaging/config + docs phase.** No runtime code path changes; the `/overlay` route already serves a live transparent page (Phase 11/12). Phase 14 is the live-failure acceptance gate for the coexistence policy decided here.
</domain>

<decisions>
## Implementation Decisions

### Browser-source URL
- **D-01:** The committed `obs/segugio-scene-collection.json` ships the browser-source URL as `http://localhost:8080/overlay` — the out-of-box default for the common single-box setup (OBS + console on the same Windows production box). The operator edits it once in OBS regardless; `docs/obs-setup.md` documents the cross-machine LAN-IP edit (`http://<console-LAN-IP>:8080/overlay`) prominently.
- **D-02:** Port is `:8080` (the console's serving port) and the path is the **bare** `/overlay` — NOT `?preview=1` (that flavour is console-iframe-only, locked in Phase 12). No `?t=` cache-bust nonce on the URL (the renderer's own `/overlay-json` poll carries the `++reqSeq` nonce; a host-URL nonce would force full reloads — the Phase-12 Pitfall-2 reasoning).

### Text-fallback coexistence (RBT-06 policy)
- **D-03:** The existing `Score Text` (`text_gdiplus_v2`, `read_from_file: overlay.txt`) stays wired in **every** scene but ships `visible: false` by default. The browser overlay is the primary on-air score; `Score Text` is the degraded fallback the operator toggles **visible** if the browser-source blanks/dies on-air. Rationale: avoids a double-score during normal operation; explicit, standard broadcast practice (a fallback you switch to).
- **D-04:** The Browser-primary / Text-fallback coexistence policy (including the manual toggle-on-failure step) is documented in `docs/obs-setup.md`. Phase 14 validates this policy end-to-end under console-death / browser-blank. NOTE for Phase 14: this is a *manual-toggle* fallback by default, not an auto-reveal — the planner/Phase-14 should treat "operator flips Score Text visible" as the documented response, not assume the text auto-airs while the browser source is still loaded-but-stale.

### Scene scope
- **D-05:** The browser-source is wired into **all 7 scenes** — `SAFE`, `CAM Wide`, `CAM Long`, `CAM Low`, `CAM Handler`, `MULTIVIEW`, `PIP` — matching ROADMAP SC-1 literally and the lockstep test. The full-frame lower-third over the `MULTIVIEW`/`PIP` grids is accepted as-is for v1 (those scenes are idle/manual-only; no per-scene transform tuning this phase).

### Render settings
- **D-06:** Browser-source render settings: `width: 1920, height: 1080, fps: 30`, relying on the page's own `html, body { background: transparent }` (no extra OBS custom CSS injected). 1080p matches a standard OBS canvas; fps 30 matches the ~30 Hz tick and is light on the shared OBS box.

### Claude's Discretion
- OBS source object shape: the browser-source is **one shared source definition** named `Score Overlay` (`id`/`versioned_id`: `browser_source`) referenced by an item in each scene's `items` — mirroring exactly how `Score Text` and the `NDI - PHONE-*` sources are single defs referenced per scene. Do NOT duplicate a full browser source per scene.
- CEF settings on that source: `shutdown_source_when_not_visible: false`, `refresh_when_scene_is_active: false` (SC-1 hard requirements — no re-flash / no timer-state loss on a cut), plus sober defaults (`reroute_audio: false`, `restart_when_active: false`, `css: ""` or the OBS default transparent CSS).
- **Z-order pitfall (research item):** the browser-source must render **above** the NDI source (and the hidden text). The OBS scene-collection `items` array order encodes z-order — the researcher/planner MUST verify whether index 0 is top or bottom in this `text_gdiplus_v2`-style export and place the `Score Overlay` item accordingly so the overlay is on top. Get this wrong and the NDI video covers the overlay.
- `docs/obs-setup.md` additions: a "Score overlay — browser-source (primary path)" section (URL + localhost default + cross-machine LAN-IP note + transparency/source settings + CEF cache-clear procedure) extending the existing "read-from-file" section; the CEF cache-clear steps are the real OBS procedure (delete the browser-source cache / "Refresh cache of current page").
- `docs/security.md`: append a one-paragraph threat re-evaluation for the new same-origin LAN browser-source consuming `GET /overlay` (single-operator LAN, no auth, reuses the established trust boundary; the overlay is display-only, values sanitized via `textContent`).
- `tests/test_scene_template.py` extension: assert the `Score Overlay` browser source exists with the URL + transparency/`shutdown_source_when_not_visible: false` + `refresh_when_scene_is_active: false`, and that **every** scene references both `Score Overlay` and `Score Text` in lockstep with the scene-name set (reuse the existing `_template_scene_names()` / `_config_obs_scenes()` helpers).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 13: OBS Scene Collection & Setup Docs" — Goal + the 3 Success Criteria (browser-source in every scene with CEF settings; `overlay.txt` text fallback retained + lockstep test; docs + security threat re-eval).
- `.planning/REQUIREMENTS.md` — SCN-01, SCN-02, RBT-06, RBT-07; and the **Out of Scope** row "Rimozione del fallback `overlay.txt`" (the fallback must stay) + the WebSocket/MJPEG/SSE rejection (transport stays fetch-polling).

### Existing artifacts this phase extends (NOT creates)
- `obs/segugio-scene-collection.json` — the 7-scene collection to extend; shows the shared-source-def + per-scene-`items` pattern, the `Score Text` (`text_gdiplus_v2`, `read_from_file: overlay.txt`) analog, and the `ndi_source` placeholder-name convention.
- `tests/test_scene_template.py` — the lockstep test to extend (`_template_scene_names()`, `_config_obs_scenes()`, scene-name ⊆ source-name assertions, SAFE-first-class assertion).
- `docs/obs-setup.md` — the operator setup doc to extend (already has the "Score overlay — read-from-file (primary path, OBS-05)" section + the scene table + the obs-websocket :4455 setup).
- `docs/security.md` — the v1.1 threat re-eval to append the one-paragraph browser-source re-evaluation to.
- `docs/run.md` — context on the console serving on :8080 + the 2-process console/orchestrator split (LAN-IP context for the URL doc).

### Locked upstream decisions
- `.planning/phases/12-scv-01-unification/12-CONTEXT.md` — bare `/overlay` vs `?preview=1` (OBS loads bare); no `?t=` nonce (Pitfall 2); the single-renderer-at-one-URL contract.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `obs/segugio-scene-collection.json`: the `Score Text` source object (`text_gdiplus_v2`, `read_from_file: true`, `file: overlay.txt`) is the structural analog for the new `Score Overlay` `browser_source` def; the per-scene `items` arrays already list `{ name, visible }` references — add a `Score Overlay` item to each.
- `tests/test_scene_template.py`: `_template_scene_names()` parses scenes from `sources` where `id == "scene"` and cross-checks `scene_order`; reuse this to drive the per-scene "both sources present" lockstep assertion.

### Established Patterns
- **Shared source def + per-scene reference** (not per-scene duplication) — `Score Text` and every `NDI - PHONE-*` source is defined once and referenced by name in each scene's `items`. The browser-source follows the same shape.
- **Placeholder values that import cleanly, operator edits once** — NDI source names ship as `PHONE-WIDE (NDI HX3)` placeholders; the `localhost:8080` URL follows the same "imports cleanly, edit-once" convention.
- **Lockstep test guards template↔config drift** — scenes in the template must match `Camera.obs_scene` across `config.example.yaml` + `config.agility.example.yaml`; SAFE is a first-class scene. The new browser/text lockstep assertions extend this guard.

### Integration Points
- The browser-source URL targets the console's `GET /overlay` route (`src/segugio/ui/app.py`) on `:8080` — already live (Phase 11/12). No code change to the route this phase.
- `overlay.txt` is written atomically by the orchestrator's score manager (`segugio.opcomm.atomic.atomic_write_text`) — unchanged; the text source just reads it.

</code_context>

<specifics>
## Specific Ideas

- Default URL exactly `http://localhost:8080/overlay` (bare path, port 8080, no query string, no nonce).
- `Score Text` ships `visible: false`; operator toggles it visible as the documented browser-blank failure response.
- All 7 scenes carry the `Score Overlay` item; no per-scene transform tuning for MULTIVIEW/PIP in v1.
- 1920×1080 @ 30fps browser source; page-owned transparency, no injected OBS CSS.

</specifics>

<deferred>
## Deferred Ideas

- Per-scene placement/scale tuning of the overlay on `MULTIVIEW`/`PIP` (so the lower-third doesn't sit over a grid quadrant) — accepted as-is for v1; revisit if/when MULTIVIEW/PIP become auto-driven (already a deferred v2 idea in `docs/obs-setup.md`).
- Auto-reveal text fallback (Score Text auto-airs without an operator toggle when the browser source goes stale/blank) — the v1 policy is a manual toggle; an automatic switch is a Phase-14 / future consideration, not this phase.

None of the above is in Phase 13 scope.

</deferred>

---

*Phase: 13-obs-scene-collection-setup-docs*
*Context gathered: 2026-06-16*
