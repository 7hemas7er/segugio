---
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
plan: 03
subsystem: obs
tags: [obsws-python, obs-websocket-v5, lazy-import, recording-fake, reconnect, scene-template, protocol, pytest, tdd]

# Dependency graph
requires:
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    plan: 01
    provides: "segugio.obs.controller.ObsController Protocol (cut/set_pip/set_overlay_text/connect/close), atomic_write_text (read-from-file overlay), Phase-5 conftest fixtures (make_config/recording_obs/file_channel)"
  - phase: 03-decision-engine
    provides: "decision.signals.Decision (.target = camera id | SAFE sentinel) + Mode the scene_for mapping reads"
provides:
  - "segugio.obs.scene_for — pure Decision.target -> Camera.obs_scene mapping (SAFE -> is_safe camera's obs_scene); reused by the 05-06 orchestrator"
  - "segugio.obs.recording_fake.RecordingObsController — headless call-capturing double; connect() pre-seeds the numeric sceneItemId cache so set_pip records the cached int id"
  - "segugio.obs.obsws_controller.ObsWsController — real obsws-python v5 controller: lazy import, cut/cached-PIP/overlay-fallback, reconnect+reauth, EventClient manual-cut sync; injectable client_factory for headless tests"
  - "obs/segugio-scene-collection.json — OBS scene-collection template (CAM Wide/Long/Low/Handler + first-class SAFE + MULTIVIEW/PIP) matching config obs_scene names"
  - "docs/obs-setup.md — one-time Windows import + read-from-file overlay + v1 manual/idle PIP notes"
affects: [05-06-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy obsws boundary: import obsws_python lives ONLY inside build_obsws_clients (called from connect()); the controller module imports light"
    - "Injectable client_factory: connect() takes a (host,port,password)->(ReqClient,EventClient) callable so reconnect+overlay are driven headless with fake clients (no obsws, no OBS)"
    - "Coast-on-failure OBS wrapper (_safe_call): every OBS op reconnects+reauths once on a transient failure then coasts — never raises into the tick (RBT-04/Pitfall 4)"
    - "Cached numeric sceneItemId (resolve-once at connect): PIP ops never pass the source name (OBS-02/Pitfall 3); recording fake mirrors the same cache semantics headless"
    - "Pure scene_for mapping as a free function: real + fake controllers share ONE camera->scene contract; SAFE -> is_safe camera's obs_scene"

key-files:
  created:
    - src/segugio/obs/recording_fake.py
    - src/segugio/obs/mapping.py
    - src/segugio/obs/obsws_controller.py
    - obs/segugio-scene-collection.json
    - docs/obs-setup.md
  modified:
    - src/segugio/obs/__init__.py
    - tests/test_obs_mapping.py
    - tests/test_obs_reconnect.py
    - tests/test_overlay.py
    - tests/test_scene_template.py

key-decisions:
  - "scene_for placed as a pure free function in segugio.obs.mapping (not a controller method) so the real client + the fake share one camera->scene contract; 05-06 imports it directly"
  - "ObsWsController takes an injectable client_factory (default = the real lazy obsws builder) so reconnect+reauth and the overlay fallback are asserted HEADLESS with fake ReqClient/EventClient — no obsws, no OBS, no mock-patching the import"
  - "Real ObsWsController is NOT re-exported from segugio.obs.__init__ — only the interface, fake, and mapping are; importing the package never touches the heavy client module path"
  - "_safe_call retries each OBS op exactly ONCE after a reconnect, then coasts (logs + swallows) — a persistent OBS outage can never crash the director (RBT-04)"

patterns-established:
  - "Injectable-client-factory test seam for a lazy heavy-client edge (mirrors the FrameSource real/mock split for OBS)"
  - "Recording double mirrors the real controller's cache semantics (numeric sceneItemId) so OBS-02 is provable without OBS"

requirements-completed: [OBS-01, OBS-02, OBS-03, OBS-04, OBS-05]

# Metrics
duration: 19min
completed: 2026-06-11
---

# Phase 5 Plan 03: OBS Control Layer Summary

**The OBS output edge behind the `ObsController` interface — a real obsws-python v5 controller (cut / cached-PIP-id / read-from-file-overlay + one-shot fallback / reconnect+reauth / EventClient manual-cut sync, all with obsws lazily imported), a call-capturing recording fake that proves the camera→scene mapping and cached-PIP-id semantics headless, the pure `scene_for` mapping, and the config-matching OBS scene-collection template with a first-class SAFE scene.**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-06-11T08:40:xxZ
- **Completed:** 2026-06-11T08:58:49Z
- **Tasks:** 3 (Task 1 TDD: RED→GREEN)
- **Files modified:** 10 (5 src/asset created, 1 src modified, 4 test files flipped)

## Accomplishments

- **`RecordingObsController`** (`obs/recording_fake.py`): the headless mirror of the real controller — every call (`connect`/`cut`/`set_pip`/`set_overlay_text`/`close`) is captured in `self.calls`. `connect()` pre-seeds a `{(scene,source): numeric id}` cache so `set_pip` records the CACHED **int** id, proving OBS-02 (the source name is never the id) with no OBS.
- **`scene_for(decision, cameras)`** (`obs/mapping.py`): the pure camera-id→OBS-scene mapping the orchestrator's output edge uses — `target=="SAFE"` → the `is_safe` camera's `obs_scene`, any camera id → its `obs_scene` (OBS-01). Reused unchanged by 05-06.
- **`ObsWsController`** (`obs/obsws_controller.py`): the real obsws-python v5 controller. `import obsws_python` lives inside `build_obsws_clients` (called from `connect()`) — the lazy boundary. `connect()` builds `ReqClient`+`EventClient`, registers `_on_scene_changed` (OBS-03 manual-cut sync), and `_cache_pip_ids()` resolves `get_scene_item_id(...).scene_item_id` once (OBS-02). `cut`→`set_current_program_scene`; `set_pip`→`set_scene_item_enabled`(+transform) on the cached id; `set_overlay_text`→`set_input_settings(input,{"text":...},overlay=True)` one-shot fallback (kind never hardcoded, Pitfall 5). Every op is wrapped by `_safe_call` → reconnect+reauth once then coast, never raises (RBT-04/Pitfall 4).
- **`obs/segugio-scene-collection.json`** (OBS-04): scenes `CAM Wide/Long/Low/Handler` + a first-class `SAFE` + `MULTIVIEW`/`PIP`; each `CAM`/`SAFE` scene carries a read-from-file `Score Text` source + its NDI source. Names match `config.example.yaml` AND `config.agility.example.yaml` `obs_scene` values.
- **`docs/obs-setup.md`**: the one-time Windows import (Scene Collection → Import), DistroAV/obs-websocket v5 prerequisites, the read-from-file overlay wiring (atomic `overlay.txt`), the password-as-trust-boundary note (T-05-03-03), and that PIP/MULTIVIEW are manual/idle-only in v1.

## Task Commits

1. **Task 1: Recording fake + camera→scene mapping + cached PIP id (OBS-01/02)** (TDD) — `ba9280f` (test RED) → `9e7c14e` (feat GREEN)
2. **Task 2: Real obsws-python v5 controller — cut/cached-PIP/overlay/reconnect/EventClient (OBS-01/02/03/05)** — `a3ed1a7` (feat)
3. **Task 3: OBS scene-collection template (OBS-04) + setup notes + name-match test** — `680fbd3` (feat)

## Files Created/Modified

- `src/segugio/obs/recording_fake.py` — `RecordingObsController` call-capturing double; connect-time numeric sceneItemId cache.
- `src/segugio/obs/mapping.py` — pure `scene_for(decision, cameras)` (SAFE→is_safe obs_scene; camera id→obs_scene).
- `src/segugio/obs/obsws_controller.py` — real v5 controller (lazy obsws, cached PIP, overlay fallback, reconnect+reauth, EventClient sync, coast-on-failure); injectable `client_factory`.
- `src/segugio/obs/__init__.py` — re-export `RecordingObsController` + `scene_for` (real client stays off the light import path).
- `obs/segugio-scene-collection.json` — the OBS scene-collection template (OBS-04).
- `docs/obs-setup.md` — one-time Windows OBS setup notes.
- `tests/test_obs_mapping.py` / `test_obs_reconnect.py` / `test_overlay.py` / `test_scene_template.py` — flipped from Wave-0 xfail stubs to real passing assertions (9 tests).

## Decisions Made

- `scene_for` is a pure free function (one camera→scene contract shared by the real client and the fake), not a controller method.
- `ObsWsController.connect()` accepts an injectable `client_factory` so reconnect+reauth and the overlay fallback are tested headless with fake `ReqClient`/`EventClient` — no obsws install, no OBS, and no monkeypatching of the lazy import.
- The real controller is deliberately NOT re-exported from `segugio.obs.__init__`, keeping the package import on the light side of the lazy boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added an explicit "failed cut coasts without raising" test**
- **Found during:** Task 2
- **Issue:** The Wave-0 stub covered only reconnect-after-drop; the threat register's T-05-03-01 (websocket drop mutes the director) requires asserting that a PERSISTENT failure (drop on every cut, including the reconnect retry) still coasts and never raises into the loop (RBT-04). The mitigation existed in code (`_safe_call`) but was unasserted.
- **Fix:** Added `test_failed_cut_coasts_without_raising` driving an always-failing ReqClient; asserts `cut()` returns without raising.
- **Files modified:** tests/test_obs_reconnect.py
- **Commit:** `a3ed1a7`

**2. [Rule 2 - Missing critical functionality] Cross-referenced BOTH example configs (disc_dog + agility) in the template name-match test**
- **Found during:** Task 3
- **Issue:** The stub checked one config; OBS-04's lockstep guarantee must hold for every shipped config (`config.agility.example.yaml` also exists and is part of the CFG-03 zero-code-edit discipline swap). Checking only disc_dog would let an agility-only `obs_scene` drift unnoticed.
- **Fix:** Parametrized `test_template_scene_names_match_config` over both `config.example.yaml` and `config.agility.example.yaml`.
- **Files modified:** tests/test_scene_template.py
- **Commit:** `680fbd3`

---

**Total deviations:** 2 auto-fixed (both Rule 2 — additive test coverage for already-implemented threat mitigations; no production-logic change).
**Impact on plan:** None on scope — both strengthen the headless assertions the plan's threat model (T-05-03-01) and CFG-03 discipline-swap invariant already require.

## Threat Surface Notes (from `<threat_model>`)

- **T-05-03-01 (DoS — websocket drop):** mitigated + now asserted — `_safe_call` reconnects+reauths once then coasts; `test_failed_cut_coasts_without_raising` proves a persistent outage never raises (RBT-04).
- **T-05-03-02 (Tampering — wrong text-input kind):** mitigated — `set_overlay_text` sets only the generic `{"text": ...}` field via `set_input_settings`; the input kind is never referenced in code (Pitfall 5). Primary overlay path is read-from-file.
- **T-05-03-03 (Info disclosure — obs-ws password):** the password is a constructor argument (config/env on the box), never committed; `docs/obs-setup.md` documents the localhost/dedicated-LAN bind as the trust boundary.

No NEW security surface beyond the plan's threat model was introduced.

## Verification

```
python -m pytest tests/test_obs_mapping.py tests/test_obs_reconnect.py tests/test_overlay.py tests/test_scene_template.py -q   # 9 passed
python -c "import segugio.obs, segugio.obs.obsws_controller, segugio.obs.recording_fake"                                       # succeeds with obsws ABSENT
python -m pytest tests/test_imports.py -q                                                                                      # import-smoke regression: passed
```

The on-Windows D-07 E2E (`import obs/segugio-scene-collection.json` into a running OBS, confirm names + a real cut/reconnect) is deferred to the marked `obs` E2E run — its prerequisites are documented in `docs/obs-setup.md`.

## Known Stubs

None. All four OBS Wave-0 stubs were flipped to real passing assertions. The scene-collection template carries placeholder NDI source names (the operator points them at the discovered NDI senders during the one-time import) — this is documented expected setup, not a product stub.

## Next Phase Readiness

- The 05-06 orchestrator can now drive the OBS output edge against stable contracts: `scene_for(decision, cameras)` maps `Decision.target` → scene; `ObsWsController` (real) or `RecordingObsController` (headless tests) consume the identical `ObsController` surface; reconnect/coast behavior is built and asserted.
- The real obsws path + the scene-collection import remain on-Windows E2E (`obs` marker) work, with setup documented.

## Self-Check: PASSED

All created files verified on disk (recording_fake.py, mapping.py, obsws_controller.py, segugio-scene-collection.json, obs-setup.md, this SUMMARY) and all 4 task commits (ba9280f, 9e7c14e, a3ed1a7, 680fbd3) confirmed in git log.

---
*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Completed: 2026-06-11*
