# Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 18 new / 1 modified (config additive)
**Analogs found:** 14 / 19 (5 have no in-repo analog — Flask UI + OBS real client + cyndilib edges; planner uses RESEARCH.md Code Examples for those)

This is a **wiring phase**. The single load-bearing analog is `tracking/eval.py:run_clip_eval` — the orchestrator IS that function grown up (frame source swapped, output sink swapped, watchdog + operator channel added around the outside). Everything it calls (`MultiCamScorer`, `DecisionEngine`, `CompetitorLock`, `PlausibilityGate`, `PerCameraTracker`) is consumed UNCHANGED.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ndi/source.py` (FrameSource Protocol) | interface | streaming | `tracking/frame_source.py` `ClipFrameSource` | role-match (interface extraction) |
| `ndi/clip_source.py` (in-process mock) | provider | streaming | `tracking/frame_source.py` `ClipFrameSource` | **exact** (derive/wrap it) |
| `ndi/ndi_source.py` (real cyndilib) | provider | streaming | `ClipFrameSource` lazy-import shape only | role-match; impl body = RESEARCH only |
| `ndi/mock_sender.py` (NDI-02 Sender) | provider | streaming | — | **no analog** (E2E-only, RESEARCH Code Examples) |
| `obs/controller.py` (ObsController iface) | interface | request-response | `FrameSource` real/mock split | role-match (same seam pattern) |
| `obs/obsws_controller.py` (real obsws) | controller | request-response | — | **no analog** (RESEARCH Code Examples) |
| `obs/recording_fake.py` (fake) | controller (test double) | request-response | — | **no analog** (RESEARCH Pattern 2) |
| `watchdog_feed/liveness.py` (FeedWatchdog) | service | event-driven | `decision/` frozen-dataclass pure logic; `CompetitorLock._motion_energy` (pure windowed math) | role-match (pure injected-value math) |
| `opcomm/atomic.py` (atomic write) | utility | file-I/O | — | **no analog** (first atomic-write; RESEARCH Code Examples) |
| `opcomm/channel.py` (typed read/write) | utility | file-I/O | `opcomm/atomic.py` (sibling) | n/a |
| `opcomm/records.py` (frozen dataclasses) | model | — | `decision/signals.py` | **exact** (frozen-dataclass contract style) |
| `orchestrator/loop.py` (tick loop) | controller (I/O edge) | event-driven / request-response | `tracking/eval.py` `run_clip_eval` (~line 230) | **exact** (live successor) |
| `orchestrator/action_hold.py` (D-08) | service | transform | `CompetitorLock._motion_energy` (line 141) | role-match (reads its output) |
| `config/models.py` MODIFY (+ActionHoldParams) | config | — | `Thresholds`/`ModelConfig` additive sub-model (line 95/82) | **exact** |
| `ui/app.py` (Flask console) | route/controller | request-response | — | **no analog** (first web surface; RESEARCH Pattern 6) |
| `ui/templates/console.html` | component | — | — | **no analog** |

## Pattern Assignments

### `ndi/clip_source.py` (provider, streaming) — the in-process mock FrameSource

**Analog:** `src/segugio/tracking/frame_source.py` `ClipFrameSource` (the whole file, 118 lines). It already produces per-camera numpy BGR crops with an injected `tick`, a stride decimation, a zero-size-frame guard (the NDI-03 precursor), and the cv2-lazy-import boundary. The mock either derives it or wraps `.frames()` behind the `FrameSource.latest(cam_id)` interface.

**Lazy-import + empty-frame guard to copy** (`frame_source.py:76-89`):
```python
import cv2  # lazy — heavy import INSIDE the generator (the cv2 boundary)
cap = cv2.VideoCapture(self.clip_path)
...
ok, frame = cap.read()
if not ok or frame is None:
    break
if getattr(frame, "size", 0) == 0:   # NDI-03 precursor — skip blank, never raise
    raw_index += 1
    continue
```

**Determinism note to preserve** (`frame_source.py:11-14`): `tick` is the EMITTED frame index, NO wall-clock. The interface's `latest(cam_id)` is the live analogue (always-newest frame); the mock keeps the injected-tick determinism for headless tests.

---

### `ndi/source.py` (interface, streaming) — FrameSource Protocol

**Analog:** the lazy-import/`TYPE_CHECKING` header of `frame_source.py:29-36`:
```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:  # type-only — keeps numpy/cv2 off the import path
    import numpy as np
```
Interface shape is in RESEARCH Pattern 1 (`start()/latest(cam_id)/last_frame_ts(cam_id)/stop()`). The real impl body (`ndi_source.py`) is RESEARCH §Code Examples "cyndilib receiver → numpy BGR" — heavy imports go INSIDE `_receiver_loop`, mirroring the `import cv2` inside `frames()`.

---

### `orchestrator/loop.py` (controller / I/O edge, event-driven) — THE central file

**Analog:** `src/segugio/tracking/eval.py` `run_clip_eval` (line 230). This is the reference skeleton. Copy its three load-bearing structures:

**(1) Per-camera independence setup** (`eval.py:287-299`) — one tracker/lock/gate per `cam_id`, NEVER a frame list (#13107):
```python
for cam in cams:
    trackers[cam.id] = PerCameraTracker(model_cfg.path, model_cfg.class_index, "botsort_dog.yaml")
    locks[cam.id]    = CompetitorLock(cam, params)
    gates[cam.id]    = PlausibilityGate(params)
```

**(2) The per-camera fan-out** (`eval.py:321-348`) — the exact chain the orchestrator replicates per tick, swapping `frame_crops.get(cam_id)` for `source.latest(cam_id)`:
```python
results = tracker.track(crop)          # None on blank/decode-fail → coast
xywhn, ids, confs = _arrays_from_results(results)
candidates = signals_from_boxes(xywhn, ids, confs, tick, cam_id)
selected   = locks[cam_id].select(candidates, tick)
# re-acquire gate-reset only on a GENUINE locked-id change (not a transient coast):
if cur_sel_id is not None and cur_sel_id != prev_sel_id:
    gates[cam_id].reset()
signal = gates[cam_id].check(selected)   # → DetectionSignal | None
```

**(3) The once-before-loop HARD ReID gate** (`eval.py:303, 329-331`) — call ONCE, only after a warmup that ACTUALLY ran inference (`results is not None`), RAISES on the silent cls fallback:
```python
reid_checked = False
...
if not reid_checked and results is not None:
    assert_native_reid_engaged(tracker.model)  # tracking/reid_check.py:35 — RAISES
    reid_checked = True
```

**(4) Per-frame coast-on-error fail-safe** — `run_clip_eval` skips a bad frame, never raises. Phase 5 hardens this to try/except EVERY stage → coast / SAFE (RESEARCH Pattern 4 sketch). The orchestrator OWNS the clock (`time.perf_counter` rate-limiter + latency probe); the pipeline stays clock-free.

**Outputs the loop produces** (downstream of the fan-out):
- `scores = self.scorer.update(dets_by_cam, tick)` — `MultiCamScorer.update(dict[str, DetectionSignal|None], tick) -> list[CameraScore]` (`framing/scorer.py:266`). A camera absent from the dict coasts via `.get(cam_id)` (line 275).
- `decision = self.engine.tick(scores, alive, holds, override)` — `DecisionEngine.tick(...)` (`decision/engine.py:428`). Pass: the watchdog `alive: dict[str,bool]` (RBT-01 — absent-from-map = NOT alive, DEC-06 fail-safe, line 488); the motion-derived `holds: HoldInput` (D-08); the panel's `override: OverrideCmd` (D-10).
- Map `decision.target` → `Camera.obs_scene` → `obs.cut(scene)`. `decision.target == "SAFE"` (sentinel `SAFE_TARGET`, `signals.py:35`) maps to the `is_safe` camera's `obs_scene`.

**`decision.reason` values the orchestrator maps to OBS actions** (`signals.py:66-70`): `"auto_switch" | "feed_emergency" | "hold" | "override" | "override_dead_fallback" | "none"`. Use `reason` (+ alive map) to write the D-11 status file: `auto` / `override` / `subject-lost` / `feed-dead`.

---

### `opcomm/records.py` (model) + `opcomm/channel.py` — operator↔system payloads

**Analog:** `src/segugio/decision/signals.py` (whole file). Copy its convention exactly:
- `@dataclass(frozen=True)`, stdlib-only (`dataclasses`/`enum`), NO heavy imports — keeps the lazy boundary (`signals.py:21-23`).
- `str`-Enum for any mode/discipline field (mirrors `Mode`, `signals.py:38`) so records stay `==`-comparable and JSON-friendly.
- `__post_init__` validation at the input BOUNDARY so malformed operator commands never reach the loop — directly mirror `OverrideCmd.__post_init__` (`signals.py:107-119`), which rejects `force_cam` + `release` both set. **The UI POST → `OperatorCommand` → `OverrideCmd` mapping MUST send EITHER a force OR a release, never both.**

`OverrideCmd` contract the panel targets (`signals.py:104-105`): `force_cam: str | None`, `release: bool`. `HoldInput` (`signals.py:83-84`): `action: bool`, `occlusion: bool` — Phase 5 sets only `action` (D-08).

---

### `watchdog_feed/liveness.py` (service, event-driven) — FeedWatchdog

**Analog:** the pure-windowed-math style of `CompetitorLock._motion_energy` (`tracking/competitor_lock.py:141`) and the frozen/injected-value convention of `decision/`. Liveness is PURE math on injected timestamps: compare the source's `last_frame_ts(cam)` against an injected `now`; dead if not advanced for > `Thresholds.watchdog_timeout` (`config/models.py:108`, =0.8) with an anti-jitter grace. Wall-clock lives only in the orchestrator caller, NEVER in the watchdog (RESEARCH Pattern 4; the `tick`-injected determinism convention). Output feeds `engine.tick(..., alive=...)`.

**Config field accessed:** `Thresholds.watchdog_timeout` (`config/models.py:108`) — already in the schema, no change.

---

### `orchestrator/action_hold.py` (service, transform) — D-08 motion → HoldInput.action

**Analog:** `CompetitorLock._motion_energy(track_id) -> float` (`tracking/competitor_lock.py:141`) — cumulative displacement over a K-tick window, deadzone-floored. **GAP (RESEARCH Open Q1 / Assumption A6 confirmed by inspection):** `_motion_energy` is PRIVATE. The planner must add a tiny ADDITIVE public accessor on `CompetitorLock` (no logic change) exposing the locked subject's motion energy, then threshold it: `action = energy >= ActionHoldParams.motion_threshold` sustained over `window_ticks` → `HoldInput(action=True)`. The FSM already carries the DEC-03 max-cap.

---

### `config/models.py` MODIFY — add `ActionHoldParams` (D-08 seeds)

**Analog (in-file, exact):** the additive sub-model pattern of `Thresholds`/`ModelConfig` (`config/models.py:82-109`) wired into `Config` via `Field(default_factory=...)` like `scoring`/`tracking` (`config/models.py:121-122`):
```python
model_config = ConfigDict(extra="forbid")   # every model uses this
...
scoring: ScorerParams = Field(default_factory=ScorerParams)      # the additive precedent
tracking: TrackingParams = Field(default_factory=TrackingParams)
# ADD: action_hold: ActionHoldParams = Field(default_factory=ActionHoldParams)
```
New `ActionHoldParams(BaseModel)` with `model_config = ConfigDict(extra="forbid")`, fields `motion_threshold` / `window_ticks` with `Field(gt=0/ge=1)` bounds (mirrors `Thresholds`). Pure additive — no schema break (existing `extra="forbid"` configs without the key default in).

**Config fields the controller/ingest consume (already present, NO change):** `Camera.obs_scene`, `Camera.ndi_source` (`str | None`), `Camera.is_safe`, `Camera.id`, `Camera.role`, `Camera.zones` (`config/models.py:70-79`).

---

### `ui/app.py` + `ui/templates/console.html` — NO ANALOG

First web surface in the repo. Use RESEARCH §Code Examples (Flask console) + Pattern 6 directly. Imports NOTHING heavy (Flask + `opcomm.channel` only) so a UI crash can never touch the director (D-03/RBT-04). Italian labels. Separate process (`python -m segugio.ui.app`).

## Shared Patterns

### Lazy-import boundary (applies to: ALL new files)
**Source:** `tracking/frame_source.py:24-36, 76` (the cv2 boundary) + `decision/signals.py:21-23` (stdlib-only records).
`import segugio.*` MUST succeed with `cyndilib`/`obsws`/`ultralytics`/`torch`/`cv2`/`Flask` ABSENT. Heavy imports live INSIDE the real impl methods only:
```python
def frames(self):
    import cv2          # heavy import INSIDE the method, never module-top
```
Interfaces (`source.py`, `controller.py`), the mock/fake, records, watchdog math, atomic helper, and the orchestrator wiring all stay on the LIGHT side. Real `ndi_source.py` / `obsws_controller.py` import their heavy clients inside methods (RESEARCH Code Examples).

### Atomic file write (applies to: `opcomm/*`, score/runstate/command/status files)
**Source:** RESEARCH §Code Examples (no in-repo analog — first atomic-write). Temp IN THE SAME DIRECTORY → `flush()` + `os.fsync()` → `os.replace(tmp, target)`. ONE helper reused for all four operator↔system files (D-03/09/10/11 + SCR-01). Windows: `os.replace` → `MoveFileEx`, atomic only on the same drive — never a cross-volume temp (Pitfall 6).

### Frozen-dataclass record convention (applies to: `opcomm/records.py`)
**Source:** `decision/signals.py` (whole file). `@dataclass(frozen=True)`, `str`-Enum modes, `__post_init__` boundary validation, stdlib-only. The `==`-comparability is what makes headless determinism tests possible.

### Determinism / injected-clock (applies to: watchdog, fan-out, scorer/engine calls)
**Source:** `frame_source.py:11-14` (injected `tick`), `decision/engine.py:428` (`tick` index). The orchestrator owns the clock + threads (it is the I/O edge); everything it calls stays clock-free and injected-value-testable.

### Per-camera fan-out (NEVER a frame list) (applies to: `orchestrator/loop.py`)
**Source:** `eval.py:287-299, 321-348`. One `PerCameraTracker.track(persist)` per camera (#13107). Already enforced in `run_clip_eval`; preserve it.

### Hard ReID gate once-before-loop (applies to: `orchestrator/loop.py`)
**Source:** `eval.py:303, 329-331` + `tracking/reid_check.py:35` (`assert_native_reid_engaged(model)`). Call ONCE after a real-inference warmup; RAISES on the silent `yolo26n-cls.pt` fallback (TRK-02). This is a startup hard gate, not a per-tick check.

## No Analog Found

Planner uses RESEARCH.md §Code Examples / §Architecture Patterns for these:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `ndi/ndi_source.py` (real cyndilib) | provider | streaming | No real-NDI receiver exists; body = RESEARCH "cyndilib receiver → numpy BGR". Only the lazy-import SHAPE is borrowed from `ClipFrameSource`. |
| `ndi/mock_sender.py` | provider | streaming | First cyndilib `Sender`; E2E-only (real-NDI side). RESEARCH Code Examples (`[ASSUMED]` API — verify on `cyndilib==0.1.1`). |
| `obs/obsws_controller.py` (real obsws) | controller | request-response | First obs-websocket client; RESEARCH Code Examples (cut/cached-PIP-id/EventClient/reconnect). |
| `obs/recording_fake.py` | controller (double) | request-response | First OBS fake; RESEARCH Pattern 2. |
| `ui/app.py` + `console.html` | route / component | request-response | First web surface; RESEARCH Pattern 6 (Flask). |
| `opcomm/atomic.py` | utility | file-I/O | First atomic-write helper; RESEARCH Code Examples (the only pattern, but trivial). |

**OBS scene-collection template (OBS-04):** not code — a one-time manual import on the Windows box per ARCHITECTURE Part 5 (`CAM Wide/Long/Low/Handler`, first-class `SAFE`, optional `MULTIVIEW`/`PIP`). Scene names must match `Camera.obs_scene` in `config.example.yaml`.

## Metadata

**Analog search scope:** `src/segugio/{tracking,framing,decision,config}/`
**Files scanned:** `tracking/frame_source.py`, `tracking/eval.py`, `tracking/competitor_lock.py`, `tracking/reid_check.py`, `config/models.py`, `framing/scorer.py`, `decision/engine.py`, `decision/signals.py`
**Pattern extraction date:** 2026-06-11
