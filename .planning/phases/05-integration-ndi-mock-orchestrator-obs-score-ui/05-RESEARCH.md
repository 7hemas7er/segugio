# Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI - Research

**Researched:** 2026-06-11
**Domain:** End-to-end wiring of locked Phase 1–4 brains into one hardware-free orchestrator loop — NDI ingest (cyndilib), OBS control (obsws-python v5), a Flask operator console, an atomic-file operator↔system channel, a timestamp watchdog, and a fixed-rate tick under latency budget.
**Confidence:** HIGH on the wiring contracts and the obsws-python/cyndilib concrete APIs; MEDIUM on the few hardware-only details (real NDI timecode behavior, the 75-min freeze) that only the on-Windows E2E run can finally confirm.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 5 is developed and tested on **Windows native (PowerShell)**, not WSL2 — so real NDI + real OBS are testable inline. Re-verify on Windows: the Windows CUDA `torch`/`ultralytics` build for the RTX 4000 Ada, and the ultralytics-pollutes-pytest gotcha (run `python -m pytest`).
- **D-02:** Local web page (**Flask**), served on localhost. Italian labels. Flask chosen (synchronous, 1 dep, serve-page + POST + atomic-file-write) over stdlib/FastAPI/tkinter.
- **D-03:** The UI is a **SEPARATE PROCESS that writes files directly** — never embedded in the orchestrator. All operator↔system communication via **atomic files** (temp + `os.replace`). No websocket, no shared memory. A UI bug can never crash the director (RBT-04).
- **D-04:** The web panel is a small **OPERATOR CONSOLE**, four concerns on one Italian page: (1) score entry (discipline selector + 3 per-discipline field sets), (2) run start/stop, (3) override controls, (4) live status read-back.
- **D-05:** A `FrameSource` interface with **two implementations**: (a) real cyndilib receiver (Finder/Receiver/FrameSync → numpy BGR, one supervised thread per camera, default on Windows); (b) in-process clip-replay mock (no network/libndi). NDI-02's named-source mock **Sender** (cyndilib `Sender` publishing clips as named NDI sources) lives on the real-NDI side, exercised by the on-Windows E2E run only.
- **D-06:** The OBS controller sits behind the same interface pattern: real `obsws-python` `ReqClient`/`EventClient` (default) + a **recording fake** capturing commands. Camera-id→`obs_scene` mapping, PIP via cached `sceneItemId`, and failure paths (feed-death→SAFE, reconnect) asserted headless.
- **D-07:** E2E acceptance bar = **headless suite** (mock NDI + fake OBS) + **one real on-Windows run**. Latency measured under ~150ms (target <80ms) (RBT-05).
- **D-08:** v1 wires **ACTION-hold from motion energy only** (locked subject's motion energy from `CompetitorLock` → FSM `HoldInput.action`, carries the mandatory max-cap DEC-03). Occlusion-hold stays deferred. Action-hold threshold/window are **additive config seeds**.
- **D-09:** Manual run start/stop **STEERS** the pipeline: START resets `CompetitorLock` + drives overlay/timer; STOP parks the director on **SAFE** + stops the timer. Run-state reaches the orchestrator via a small atomic run-state file read each tick.
- **D-10:** Override exposed on the same panel ("Regia"): buttons "Forza CAM Wide/Long/Low/Handler" + "Rilascia (auto)" write the override command into the operator-command file; the orchestrator passes an `OverrideCmd` into `DecisionEngine.tick(...)`. RBT-03 already built; this only WIRES it live.
- **D-11:** The panel shows **LIVE DIRECTOR STATUS** (reverse channel): the orchestrator writes a small atomic status file on each change — current live camera + reason (`auto`/`override`/`subject-lost`/`feed-dead`) + per-feed alive/dead — which the panel polls.

### Claude's Discretion
- **Orchestrator threading & per-tick inference strategy** — supervised per-camera receiver threads + the fixed-rate (~30 Hz) tick pulling latest frames; per-camera YOLO sequential vs batched to hold <150ms with 3–4 cameras; the degradation ladder if over budget (yolo26n, fewer cams, lower AI-path imgsz/fps per STACK.md). Keep `tick` an injected index.
- **Exact FSM "between-runs → SAFE" mechanism** (D-09) — a dedicated between-runs hold vs forcing the SAFE target. Override (RBT-03) must still win.
- **File layout for operator↔system channel** — one combined "operator commands" file vs separate score/run-state/override files; the status read-back file format. All via atomic temp + `os.replace`; keep each write atomic.
- **Action-hold seed placement** (D-08) — additive config sub-model location + the motion threshold/window constants.
- **Score file content / overlay layout** — exact text written per discipline for the OBS read-from-file source.
- **PIP / MULTIVIEW usage** — build the PIP machinery (cached `sceneItemId`) but drive MULTIVIEW/PIP **manually / idle-only** in v1 (ARCHITECTURE Part 5). Honor that default unless research shows otherwise.

### Deferred Ideas (OUT OF SCOPE)
- **Autonomous occlusion-hold** (config occluder-zones → hold through tunnels/contacts) — needs marked zones + agility/tunnel footage, both absent.
- **Disc/frisbee lead-the-dog prediction** (`classes=[16,29]`) — v2.
- **Pose-based heading/intent action-hold** (`yolo26s-pose`) — v2.
- **RTMP/YouTube output engine** — v1 is preview-only.
- **Auto-driven MULTIVIEW/PIP** — PIP machinery built but driven manually/idle-only in v1.
- **TensorRT FP16 export / production-GPU latency tuning** — hardware milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NDI-01 | cyndilib ingest (Finder/Receiver/FrameSync → numpy BGR, one supervised thread/camera) | §Standard Stack (cyndilib), §Code Examples (cyndilib receiver), §Pattern 1 (FrameSource interface), §Pattern 4 (supervised thread) |
| NDI-02 | Mock NDI source publishes recorded clips as named NDI sources | §Code Examples (cyndilib Sender), §Pattern 5 (mock sender — real-NDI side, on-Windows E2E only) |
| NDI-03 | Guard first empty frames (loop until resolution/data valid) | §Code Examples (the `min(xres,yres)!=0` guard), §Common Pitfalls (Pitfall 2) |
| OBS-01 | `SetCurrentProgramScene` cut on a local OBS | §Code Examples (obsws `set_current_program_scene`), §Pattern 2 (OBS controller interface) |
| OBS-02 | PIP via `SetSceneItemTransform`+`SetSceneItemEnabled`, `sceneItemId` resolved & cached at startup | §Code Examples (PIP cached id), §Common Pitfalls (Pitfall 3) |
| OBS-03 | Persistent connection w/ reconnect+reauth; `EventClient` thread syncs manual scene changes | §Code Examples (EventClient), §Pattern 2, §Common Pitfalls (Pitfall 4 reconnect) |
| OBS-04 | OBS scene-collection template provided (`CAM *`, `SAFE`, `MULTIVIEW`, `PIP`) | §Architecture Patterns (scene template from ARCHITECTURE Part 5) |
| OBS-05 | Overlay text via "read from file" text source (primary) + `SetInputSettings` fallback for one-shots | §Code Examples (read-from-file + set_input_settings), §Common Pitfalls (Pitfall 5 don't hardcode input kind) |
| SCR-01 | Score manager writes atomically (temp + `os.replace`) read by OBS read-from-file | §Code Examples (atomic write), §Pattern 3 (atomic-file channel), §Common Pitfalls (Pitfall 6 Windows os.replace) |
| SCR-02 | Manual score-entry UI: discipline selector + 3 field sets (disc T&F; freestyle; agility) | §Pattern 6 (Flask console), §Code Examples (Flask app) |
| SCR-03 | Manual run start/stop resets overlay, starts/stops timer, segments the run | §Pattern 3 (run-state file), §Pattern 6, D-09 wiring |
| SCR-04 | System DISPLAYS scores, never adjudicates | §Architecture (score file is display-only; no CV scoring) |
| RBT-01 | Watchdog deduces liveness from the last *NEW* frame timestamp (never NDI source state), anti-jitter grace | §Code Examples (watchdog on `get_timestamp_posix`), §Pattern 4, §Common Pitfalls (Pitfall 1 false liveness) |
| RBT-02 | Feed-death → automatic fallback (SAFE / other live cam) w/o crash; rejoin only after alive + full hysteresis+dwell | §Pattern 2/4 (alive map → DecisionEngine.tick), §Architecture (FSM consumes `alive`) |
| RBT-04 | Orchestrator fixed-rate tick, fault isolation (try/except + supervised thread restart), SAFE shutdown, never crash | §Pattern 4 (orchestrator tick), §Common Pitfalls (Pitfall 7 fault isolation), §Validation Architecture |
| RBT-05 | AI loop (frame→YOLO→score→FSM→OBS) measured < ~150ms (target <80ms) | §Validation Architecture (latency harness), §State of the Art (latency budget) |
</phase_requirements>

## Summary

Phase 5 is **wiring, not invention**. Every "brain" — `MultiCamScorer`, `DecisionEngine`, `CompetitorLock`, `PlausibilityGate`, the per-camera `PerCameraTracker` fan-out, the config schema — already exists and is consumed UNCHANGED. The orchestrator's per-tick body is the live successor of `tracking/eval.py:run_clip_eval` (the per-camera fan-out, the once-before-loop `assert_native_reid_engaged` hard gate, the per-frame coast-on-error fail-safe). The job is to (1) replace `ClipFrameSource` with a `FrameSource` interface that has a real cyndilib impl and an in-process mock; (2) put OBS behind an interface with a real obsws-python impl and a recording fake; (3) build the atomic-file operator↔system channel and a Flask console on top of it; (4) add a timestamp watchdog that feeds the FSM's `alive` map; and (5) own the clock and threads in a fault-isolated fixed-rate loop that degrades to SAFE and never crashes.

The three concrete library deltas the existing project research did NOT pin down are now verified: **cyndilib** capture (`receiver.frame_sync.capture_video()` → `VideoFrameSync.get_array()` → reshape `(yres, xres, 4)` → `cv2.cvtColor`; NDI-03 guard is `min(video_frame.xres, video_frame.yres) != 0`; liveness via `get_timestamp_posix()` / `get_timecode_posix()` comparison — the load-bearing RBT-01 detail); **obsws-python v5** snake_case methods (`set_current_program_scene`, `get_scene_item_id`, `set_scene_item_enabled`, `set_scene_item_transform`, `set_input_settings`, `EventClient` + `callback.register`); and the **atomic-write** pattern (same-directory temp + `flush`+`os.fsync` + `os.replace`, with the Windows MoveFileEx same-drive caveat).

**Primary recommendation:** Introduce two small interfaces (`FrameSource`, `ObsController`) at the lazy-import boundary, write the orchestrator against them as a faithful grown-up `run_clip_eval`, and route the entire operator surface through one atomic-file module. Keep `cyndilib`/`obsws-python`/`cv2` imports strictly inside the real implementations so `import segugio.*` still succeeds with the heavy stack absent and the whole loop stays headless-testable against the mock + fake. Add exactly one new runtime dependency: **Flask 3.1.3**.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| NDI frame ingest (real + mock) | I/O edge (orchestrator-owned receiver threads) | — | Threads + libndi are the I/O boundary; the pure pipeline never touches the network. Lazy-import inside the real impl. |
| Per-tick frame→YOLO→score→FSM | Compute (pure logic + GPU inference) | — | Reuses locked Phase 1–4 logic; orchestrator only sequences it. Inference is the only heavy compute. |
| Feed liveness / watchdog | Compute (pure liveness math on injected timestamps) | I/O edge (reads receiver-thread timestamps) | Liveness MATH is pure + injected-timestamp-testable; only the timestamp source is I/O. |
| OBS scene cut / PIP / overlay update | I/O edge (obsws-python client) | — | Websocket I/O behind an interface; the recording fake makes the mapping logic headless-testable. |
| Operator console (score/run/override) | Separate process (Flask) | File channel | D-03: crash-isolated separate process; communicates only via atomic files. |
| Operator↔system channel | Persistence (atomic files) | — | One file pattern (temp+`os.replace`) is the only IPC; decoupled by construction. |
| Orchestrator clock/tick/fault isolation | I/O edge (owns clock + threads) | — | The one component allowed wall-clock + threads; everything it calls stays deterministic. |

## Standard Stack

### Core (all already pinned in `pyproject.toml [heavy]` except Flask)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cyndilib` | `0.1.1` | NDI ingest (Finder/Receiver/FrameSync) + mock Sender | The locked NDI binding; FrameSync gives always-latest frames (drops intermediates) which is exactly right when the AI tick runs <30Hz. `[VERIFIED: pip index versions — 0.1.1 is latest]` |
| `obsws-python` | `1.8.0` | obs-websocket v5 client (`ReqClient`+`EventClient`) | The maintained v5 binding (NOT `obs-websocket-py`, which is v4). Synchronous ReqClient with built-in timeout fits the control path. `[VERIFIED: pip index versions — 1.8.0 is latest]` |
| `opencv-python` | `4.13.0.92` | `cvtColor` (RGBA→BGR), the mock clip reader | Already used by `ClipFrameSource`; lazy-imported inside `frames()`. `[VERIFIED: pyproject pin]` |
| `numpy` | `2.4.6` | Frame arrays + pure watchdog liveness math | Light runtime dep, already core. `[VERIFIED: pyproject pin]` |
| `watchdog` | `6.0.0` | (Optional) filesystem-event read of operator files | Declared in `[heavy]`. NOTE: polling the operator files each tick is simpler and deterministic; `watchdog` is only needed if event-driven reads are preferred. `[VERIFIED: pyproject pin]` |
| `transitions` | `0.9.3` | FSM (consumed unchanged) | Already core; Phase 3 built the engine. `[VERIFIED: pyproject pin]` |
| `loguru` | `0.7.3` | Structured logging incl. "WHY went to SAFE" lines (PITFALLS UX) | Already core. `[VERIFIED: pyproject pin]` |
| **`Flask`** | **`3.1.3`** | The operator console (serve page + POST + atomic write), separate process | **NEW dep.** Synchronous, 1 dependency tree, ideal for a tiny serve-page + POST app (D-02). Pallets project, ~14 yrs, github.com/pallets/flask. `[VERIFIED: pip index versions — 3.1.3 is latest]` |

### Supporting (stdlib — no install)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `os` (`os.replace`, `os.fsync`) | Atomic file replace + durability flush | The whole operator↔system channel (SCR-01 + D-09/10/11) |
| `tempfile` / manual temp name | Same-directory temp file for the atomic write | Every atomic write (temp MUST be on the same volume as target) |
| `threading` | Supervised per-camera receiver threads + restart | NDI-01 ingest; orchestrator fault isolation (RBT-04) |
| `time` (`time.monotonic`, `time.perf_counter`) | The orchestrator's wall-clock (the ONE place clock lives) + latency measurement | RBT-04 fixed-rate tick; RBT-05 latency harness |
| `json` | Status / run-state / operator-command file payloads | The file channel (a tiny JSON doc per file is the simplest atomic-write payload) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Flask | stdlib `http.server` | Zero new dep, but hand-rolled routing/POST parsing/templating — more code, more bug surface, for no benefit on a localhost tool. Flask is the locked choice (D-02). |
| Flask | FastAPI + uvicorn | Async + 3+ deps for a synchronous form-POST app; overkill. Rejected in D-02. |
| Polling the operator files each tick | `watchdog` observer thread | Polling is deterministic and trivially testable; `watchdog` adds a thread + event timing nondeterminism. Prefer polling unless profiling shows the (tiny) read cost matters. |
| `RecvColorFormat.RGBX_RGBA` + `cvtColor(RGBA2BGR)` | `RecvColorFormat.BGRX_BGRA` | BGRX avoids one channel swap, but the canonical gist + most examples use RGBX→BGR via `cvtColor`. Either works; pick BGRX to skip the swap, OR RGBX+cvtColor for parity with the documented example. `[CITED: cyndilib gist]` |

**Installation:**
```bash
# Add Flask to runtime deps; the rest are already in pyproject [heavy].
pip install Flask==3.1.3
# On the Windows/CUDA box, the [heavy] stack must be present:
pip install -e ".[heavy]"   # cyndilib==0.1.1 obsws-python==1.8.0 opencv-python==4.13.0.92 watchdog==6.0.0 ultralytics==8.4.62
# Windows CUDA torch (D-01 re-verify): install the CUDA wheel matching the RTX 4000 Ada driver, then:
python -c "import torch; print(torch.cuda.is_available())"   # must print True
```

**Version verification (run on the Windows box before locking the plan):**
```bash
python -c "import cyndilib; print(cyndilib.__version__)"     # expect 0.1.1
python -c "import obsws_python as o; print(o.__version__)"   # expect 1.8.0
python -c "import flask; print(flask.__version__)"           # expect 3.1.3
python -c "import cv2; print(cv2.__version__)"               # expect 4.13.0
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `Flask` | PyPI | ~15 yrs | ~100M+/mo | github.com/pallets/flask | OK | Approved (new dep) |
| `cyndilib` | PyPI | active | low (niche NDI) | github.com/nocarryr/cyndilib | OK | Already pinned 0.1.1 |
| `obsws-python` | PyPI | active | moderate | github.com/aatikturk/obsws-python | OK | Already pinned 1.8.0 |
| `opencv-python` | PyPI | mature | very high | github.com/opencv/opencv-python | OK | Already pinned |
| `watchdog` | PyPI | mature | very high | github.com/gorakhargosh/watchdog | OK | Already pinned (optional) |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none. `cyndilib` has lower downloads (niche NDI binding) but is the locked project dependency from the original technical research with an identified source repo and an existing pin — not a new/hallucinated choice. The legitimacy seam was unavailable on PATH in this session; verdicts are from `pip index versions` (all resolve to the pinned/latest version) + known-good source repos. The planner may run `gsd-tools query package-legitimacy check --ecosystem pypi flask` on the Windows box to confirm Flask before adding it.

## Architecture Patterns

### System Architecture Diagram

```
  OPERATOR PROCESS (Flask, separate)            ORCHESTRATOR PROCESS (headless GPU box)
  ┌───────────────────────────────┐
  │ Italian console (one page):   │             ┌──────────────────────────────────────────────┐
  │  • score entry (3 field sets) │             │           fixed-rate ~30Hz tick loop          │
  │  • run start/stop             │             │                                                │
  │  • override (Forza/Rilascia)  │  atomic     │  NDI in ──► FrameSource.latest(cam) ──┐        │
  │  • live status read-back ◄────┼──files──────┤                                        ▼        │
  └───────────┬───────────────────┘   (temp+    │   ┌─ per camera (fan-out, like run_clip_eval) ─┐│
              │ POST                   os.replace)│   │ crop ► PerCameraTracker.track(persist) ►   ││
              ▼                                   │   │ signals_from_boxes ► CompetitorLock ►      ││
   ┌──────────────────────┐                      │   │ PlausibilityGate ► DetectionSignal|None    ││
   │ score.json    ───────┼──► OBS read-from-file│   │  └─ motion energy ─► HoldInput.action (D-08)││
   │ runstate.json ───────┼──► read each tick    │   └──────────────────┬─────────────────────────┘│
   │ command.json  ───────┼──► OverrideCmd       │                      ▼                          │
   │ status.json   ◄──────┼──◄ orchestrator      │      MultiCamScorer.update(dets, tick)          │
   └──────────────────────┘                      │                      ▼                          │
                                                 │   Watchdog.alive(cam) ─► DecisionEngine.tick(   │
   PHONE/CLIP (NDI source) ──► cyndilib Receiver │      scores, alive, holds, override) ─► Decision│
        ▲ (mock Sender publishes clips,          │                      ▼                          │
        │  real-NDI side, E2E only)              │   Decision.target ─► Camera.obs_scene ─►        │
        └── one supervised thread per camera ────┤      ObsController.cut() / SAFE on death        │
                                                 │                      │                          │
                                                 │   try/except per stage ─► coast / SAFE, never   │
                                                 │   crash; SAFE on shutdown (RBT-04)              │
                                                 └──────────────────────┴──► OBS PROGRAM ─► preview│
                                                                                                   │
```

Trace the primary use case: an NDI frame enters via a supervised receiver thread → the orchestrator pulls the latest frame per camera → runs the unchanged Phase 1–4 fan-out → derives an action-hold from motion energy → scores all cameras → asks the watchdog which feeds are alive → the FSM picks a target → the OBS controller cuts to that camera's scene; meanwhile the Flask console writes score/run/override files the loop reads, and the loop writes a status file the console polls.

### Recommended Project Structure
```
src/segugio/
├── ndi/                  # NEW — NDI ingest package (lazy cyndilib edge)
│   ├── __init__.py       #   light re-exports only (interface + mock; NOT the real impl symbols at top)
│   ├── source.py         #   FrameSource Protocol/ABC (the interface D-05 depends on)
│   ├── clip_source.py    #   in-process clip-replay mock FrameSource (wraps/derives ClipFrameSource)
│   ├── ndi_source.py     #   real cyndilib FrameSource: Finder/Receiver/FrameSync, 1 thread/cam (lazy import)
│   └── mock_sender.py    #   NDI-02 named-source Sender (real-NDI side; lazy import; E2E only)
├── obs/                  # NEW — OBS control package (lazy obsws edge)
│   ├── __init__.py       #   light re-exports (interface + fake)
│   ├── controller.py     #   ObsController Protocol/ABC (cut/pip/overlay/connect)
│   ├── obsws_controller.py#  real obsws-python impl: ReqClient+EventClient, cached sceneItemId, reconnect (lazy import)
│   └── recording_fake.py  #  RecordingObsController capturing calls (no OBS) — headless assertions
├── watchdog_feed/        # NEW — feed liveness (pure math + timestamp source)
│   └── liveness.py       #   FeedWatchdog: alive(cam, now) from last-NEW-frame timestamp + grace (pure, injected ts)
├── opcomm/               # NEW — atomic-file operator↔system channel
│   ├── atomic.py         #   atomic_write_json(path, obj): temp+fsync+os.replace (Windows-aware)
│   ├── channel.py        #   typed read/write for score/runstate/command/status files
│   └── records.py        #   frozen dataclasses: ScoreDoc, RunState, OperatorCommand, DirectorStatus
├── orchestrator/         # NEW — the tick loop (I/O edge; owns clock+threads)
│   ├── loop.py           #   Orchestrator: fixed-rate tick, fault isolation, SAFE shutdown, latency probe
│   └── action_hold.py    #   motion-energy → HoldInput.action derivation (D-08), config-seeded
├── ui/                   # NEW — Flask operator console (separate process)
│   ├── app.py            #   Flask app: GET page, POST score/run/override → atomic files; GET status
│   └── templates/        #   one Italian HTML page (Jinja or a static string) + a tiny poll script
└── config/models.py      # EXTEND additively: ActionHoldParams sub-model (D-08 seeds) — no schema break
```

### Pattern 1: `FrameSource` interface + two implementations (D-05)
**What:** A minimal interface every downstream component depends on, with a real cyndilib impl and an in-process mock. Heavy imports live ONLY inside the real impl.
**When to use:** Always — this is the structural seam that keeps the orchestrator + its unit tests on the light side of the lazy-import boundary.
**Example:**
```python
# src/segugio/ndi/source.py — light, no cyndilib import
from __future__ import annotations
from typing import Protocol, TYPE_CHECKING
if TYPE_CHECKING:
    import numpy as np

class FrameSource(Protocol):
    """Per-camera latest-frame provider. The orchestrator depends ONLY on this."""
    def start(self) -> None: ...                # spin up receiver thread(s) (no-op for the mock)
    def latest(self, cam_id: str) -> "np.ndarray | None": ...  # newest BGR frame, or None (coast)
    def last_frame_ts(self, cam_id: str) -> float | None: ...  # POSIX ts of last NEW frame (RBT-01)
    def stop(self) -> None: ...
```
The clip mock derives the existing `ClipFrameSource` semantics (it already produces per-camera numpy crops with an injected tick + empty-frame guard — NDI-03 analogue). The real impl wraps the cyndilib loop (§Code Examples).

### Pattern 2: `ObsController` interface + recording fake (D-06)
**What:** Cut / PIP / overlay behind an interface; a fake records every call so the camera-id→scene mapping and failure paths are asserted without OBS.
**When to use:** Always — lets `assert called set_current_program_scene("CAM Long")` run headless.
**Example:**
```python
# src/segugio/obs/recording_fake.py — captures calls, no OBS
class RecordingObsController:
    def __init__(self): self.calls = []
    def connect(self): self.calls.append(("connect",))
    def cut(self, scene_name): self.calls.append(("cut", scene_name))
    def set_pip(self, scene, item_id, enabled): self.calls.append(("pip", scene, item_id, enabled))
    def set_overlay_text(self, input_name, text): self.calls.append(("overlay", input_name, text))
```

### Pattern 3: One atomic-file operator↔system channel (D-03/09/10/11, SCR-01)
**What:** Every operator↔system message (score, run-state, override command, director status) is a small JSON doc written via temp + `os.replace`. No websocket, no shared memory.
**When to use:** The entire operator surface. **Recommendation:** use **separate files** (`score.json`, `runstate.json`, `command.json`, `status.json`) rather than one combined file — independent atomic writes avoid a UI score write racing the orchestrator's status write, and each consumer reads only what it needs. (Claude's discretion in D-03 explicitly allows this; separate files is the lower-risk default.) `score.json` is ALSO consumable as the OBS read-from-file overlay text (OBS-05) if its on-disk form is the rendered overlay string; if a richer JSON is needed for the UI, write a sibling plain-text `overlay.txt` for OBS and the JSON for the UI.
**Example:** see §Code Examples (atomic write).

### Pattern 4: Supervised per-camera receiver thread + fixed-rate tick (NDI-01, RBT-04)
**What:** One thread per camera owns a cyndilib `Receiver`; it captures the latest frame and stamps `last_frame_ts` on each NEW frame. The orchestrator's main thread ticks at a fixed rate, pulls `source.latest(cam)` for each camera, runs the pipeline, and restarts any dead receiver thread. Every stage is wrapped in try/except → coast / SAFE, never crash.
**When to use:** The orchestrator core. Keep `tick` an injected integer index (determinism convention) — the wall-clock lives only in the loop's rate-limiter and the latency probe, never in the pure pipeline.
**Example:**
```python
# orchestrator/loop.py (sketch — the grown-up run_clip_eval)
import time
def run(self):
    self.source.start(); self.obs.connect()
    self._reid_checked = False
    tick = 0
    try:
        while not self._stopping:
            t0 = time.perf_counter()
            try:
                dets, holds = self._fan_out(tick)            # per-cam: tracker→lock→gate (+motion→HoldInput)
                scores = self.scorer.update(dets, tick)
                alive = {c.id: self.watchdog.alive(c.id, time.monotonic()) for c in self.cameras}
                cmd = self.channel.read_command(); run = self.channel.read_runstate()
                if run.just_started: self._reset_locks()     # D-09 START
                override = cmd.to_override() if cmd else None
                target = "SAFE" if run.stopped else None      # D-09 STOP parks on SAFE (planner picks mechanism)
                decision = self.engine.tick(scores, alive, holds, override)
                self._apply(decision, run)                    # cut OBS to Camera.obs_scene / SAFE; write status
            except Exception as exc:                          # RBT-04 fault isolation
                logger.exception("tick {} failed → SAFE coast", tick); self._to_safe(reason="error")
            self._sleep_to_rate(t0)                           # fixed-rate ~30Hz
            tick += 1
    finally:
        self._to_safe(reason="shutdown"); self.source.stop(); self.obs.close()  # SAFE shutdown, never crash
```

### Pattern 5: Mock NDI Sender (NDI-02, real-NDI side, E2E only)
**What:** A cyndilib `Sender` per camera publishes the curated clip frames as a named NDI source (the `ndi_source` name from config), so the real cyndilib receive path is exercised end-to-end without phones.
**When to use:** The on-Windows E2E run only — NOT the headless unit tests (those use the in-process clip mock). Gate it behind a real-NDI marker (extend the `@pytest.mark.gpu` precedent with a `@pytest.mark.ndi` / `@pytest.mark.obs` split).

### Pattern 6: Flask operator console (separate process, D-02/04)
**What:** A tiny Flask app: `GET /` serves one Italian page (discipline selector + 3 field sets + run start/stop + override buttons + a status panel); `POST` endpoints write `score.json` / `runstate.json` / `command.json` atomically; `GET /status` returns `status.json` for the page to poll. Runs as its own process (`python -m segugio.ui.app`).
**When to use:** The only human surface. It imports NOTHING heavy (just Flask + the `opcomm` channel) so a UI crash can never touch the director.

### Anti-Patterns to Avoid
- **Passing a list of frames to `model.track()`** — builds ONE tracker, mixes IDs across cameras (#13107). One `PerCameraTracker.track(persist=True)` per camera (already enforced in `run_clip_eval`).
- **`obs-websocket-py` (v4) or `SetTextGDIPlusProperties`** — wrong major version / removed in v5. Use `obsws-python` 1.8.0 and `set_input_settings({"text": ...})`.
- **Hardcoding the text input kind** (`text_gdiplus_v2` vs `text_ft2_source_v3`) — platform-specific; the `text` field is identical. Prefer the read-from-file source for the overlay; use `set_input_settings` only for one-shots, and discover the kind via `get_input_kind_list` if ever needed.
- **Trusting the NDI source "connected" state for liveness** — a dropped phone repeats its last frame for ~75 min (TTL). Liveness MUST come from the last *NEW* frame timestamp (Pitfall 1).
- **Importing `cyndilib` / `obsws_python` / `cv2` at a module top level** — breaks the lazy-import boundary. Heavy imports live INSIDE the real implementations only.
- **Embedding the UI in the orchestrator process** — a UI exception would crash the director (violates D-03/RBT-04). Separate process, files only.
- **A cross-volume temp file for the atomic write** — `os.replace` is only atomic on the same filesystem; the temp MUST be created in the target's directory.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NDI receive + always-latest frame | A custom NDI/socket reader | `cyndilib` Receiver + `FrameSync` | FrameSync handles buffering/jitter and gives the most-recent frame, dropping intermediates — exactly the <30Hz AI need. |
| obs-websocket v5 protocol (Hello/Identify, rpcVersion, reauth) | A raw websocket client | `obsws-python` `ReqClient`/`EventClient` | Handshake, auth, request matching, and event dispatch are all handled; v5-correct. |
| Atomic file replace | A lock file / rename dance | `os.replace` (temp in same dir) | Single OS primitive; atomic on same volume (`MoveFileEx` on Windows). |
| HTTP serving + form POST + templating | stdlib `http.server` plumbing | `Flask` | Routing, request parsing, and templating in 1 dep; the locked choice (D-02). |
| The detection/tracking/scoring/FSM logic | Anything | `segugio.tracking` / `framing` / `decision` (UNCHANGED) | Phases 1–4 are locked. Phase 5 only supplies their inputs and routes their outputs. |
| Subject motion energy | A new velocity estimator | The value already computed inside `CompetitorLock` (D-08) | The action-hold signal is "already on hand"; derive `HoldInput.action` from it, don't recompute. |

**Key insight:** This phase's failure mode is *re-implementing a locked brain while wiring it*. Treat `run_clip_eval` as the reference skeleton, swap only the frame source and the output sink, and add the watchdog + operator channel around the outside.

## Runtime State Inventory

> Phase 5 is greenfield wiring (new packages), not a rename/refactor — no stored data, live-service config, OS-registered state, secrets, or build artifacts carry an old string. **None — verified by inspection:** the new packages add no migrations and reuse the existing config schema additively. The only OS-level surface is the OBS **scene-collection template** (OBS-04), which is a one-time manual import on the Windows box, documented in setup notes, not a code-migrated artifact.

## Common Pitfalls

### Pitfall 1: False NDI liveness (the 75-minute freeze) — RBT-01 🔴
**What goes wrong:** A phone drops/falls but its NDI source keeps "looking connected"; the receiver keeps returning the SAME last frame for up to ~75 min (NDI TTL). A naive watchdog (checking source/connection state) never declares it dead, and the director keeps airing a frozen feed.
**Why it happens:** NDI repeats the last frame on a stalled source; `receiver.is_connected()` and source presence stay true.
**How to avoid:** Liveness comes ONLY from the last *NEW* frame timestamp. Compare `video_frame.get_timestamp_posix()` (or `get_timecode_posix()`) between captures; if it hasn't advanced for > `watchdog_timeout` (=0.8s, RBT-01) with an anti-jitter grace, mark the feed DEAD → the `alive` map flips → `DecisionEngine.tick` excludes it (DEC-06) → fallback to SAFE/other live cam (RBT-02).
**Warning signs:** A feed stays "live" with a visibly static frame; `alive[cam]` never goes False in a pull-the-cable test.

### Pitfall 2: First NDI frames are empty / zero-resolution — NDI-03
**What goes wrong:** Right after `set_source`, `capture_video()` returns a frame with `xres==0`/`yres==0`; reshaping it crashes.
**How to avoid:** Guard exactly as the canonical example does: `if min(video_frame.xres, video_frame.yres) != 0:` before `get_array().reshape(...)`. This mirrors `ClipFrameSource`'s existing zero-size-frame skip (NDI-03 precursor).
**Warning signs:** A reshape `ValueError` on startup; a black frame for the first few ticks.

### Pitfall 3: PIP/scene-item ops need a NUMERIC sceneItemId, not a name — OBS-02
**What goes wrong:** Passing the source NAME to `set_scene_item_enabled` / `set_scene_item_transform` fails; these require the numeric `sceneItemId`.
**How to avoid:** Resolve `get_scene_item_id(scene_name, source_name)` ONCE at startup and CACHE the numeric ids; refresh on `SceneItemCreated`/`SceneItemRemoved` events. Build the PIP machinery but drive it manually/idle-only in v1 (ARCHITECTURE Part 5).
**Warning signs:** OBS request errors referencing an unknown scene item; PIP toggles silently doing nothing.

### Pitfall 4: Websocket drop mid-event mutes the director — OBS-03
**What goes wrong:** A transient websocket disconnect (OBS restart, network blip) leaves the controller unable to cut; if unhandled, the loop either crashes or silently stops switching.
**How to avoid:** Persistent connection with reconnect+reauth; wrap every OBS call in try/except so a failed cut coasts the loop (never crashes — RBT-04). An `EventClient` on its own thread syncs the operator's MANUAL scene changes back into the FSM's notion of the current scene.
**Warning signs:** Cuts stop after an OBS restart; no reconnect attempts in the log.

### Pitfall 5: Hardcoding the text input kind — OBS-05
**What goes wrong:** Assuming `text_gdiplus_v2` (Windows) and calling kind-specific settings breaks cross-platform; the wrong kind name 404s.
**How to avoid:** Prefer the read-from-file text source for the overlay (the score manager just writes the file atomically). For one-shot text, `set_input_settings(input_name, {"text": ...})` — the `text` field is identical across kinds. Discover the kind via `get_input_kind_list` only if strictly necessary.

### Pitfall 6: Non-atomic / cross-volume file writes corrupt the overlay — SCR-01 🔴
**What goes wrong:** Writing the score file in place lets OBS / the orchestrator read a half-written file; or the temp file is on a different drive so `os.replace` silently degrades to a non-atomic copy (Windows `MoveFileEx`).
**How to avoid:** Write to a temp file IN THE SAME DIRECTORY as the target, `flush()` + `os.fsync()` it, then `os.replace(tmp, target)`. On Windows `os.replace` → `MoveFileEx`, atomic on the same drive. Never construct the temp in `/tmp` or a different volume.
**Warning signs:** OBS overlay flickers to blank; readers occasionally see truncated/empty content; intermittent `PermissionError` on Windows when a reader holds the target open (mitigate: readers open-read-close quickly; the orchestrator reads its files with retry-on-`PermissionError`).

### Pitfall 7: An exception anywhere crashes the live director — RBT-04 🔴
**What goes wrong:** A decode error, a websocket timeout, a malformed operator file, or a receiver-thread death propagates and kills the process — the "nessun crash ammesso" violation.
**How to avoid:** Try/except EVERY stage of the tick (mirror `run_clip_eval`'s per-frame coast-on-error). On an unrecoverable stage, degrade to SAFE and keep ticking. Supervise receiver threads and restart a dead one. On shutdown, cut to SAFE explicitly. Malformed operator files are caught at the channel boundary (return the last-good value, log, never raise into the loop).
**Warning signs:** The process exits on a single bad frame / bad file; no SAFE cut on shutdown.

### Pitfall 8: Cutting away mid-catch/mid-jump (the core-value failure) — D-08
**What goes wrong:** Motion blur at a disc-catch apex drops detection for a few frames; a naively-wired loop reads "subject gone" and cuts away from the climax.
**How to avoid:** Derive `HoldInput.action` from the locked subject's motion energy (D-08); the FSM's existing hold suppression (with the DEC-03 max-cap) holds the cut through the action. The scorer's coast/TTL (FRM-05) already protects the score; the action-hold protects the CUT decision. (PITFALLS Pitfall 3/7.)

## Code Examples

### cyndilib receiver → numpy BGR (NDI-01 / NDI-03)
```python
# src/segugio/ndi/ndi_source.py — heavy imports INSIDE the method (lazy boundary)
# Source: cyndilib gist (royshil) + cyndilib docs (examples + video_frame reference)
def _receiver_loop(self, cam_id, source_name):
    import cv2
    from cyndilib.finder import Finder
    from cyndilib.receiver import Receiver
    from cyndilib.video_frame import VideoFrameSync
    from cyndilib.wrapper.ndi_recv import RecvColorFormat, RecvBandwidth

    finder = Finder()
    receiver = Receiver(color_format=RecvColorFormat.RGBX_RGBA, bandwidth=RecvBandwidth.highest)
    video_frame = VideoFrameSync()
    receiver.frame_sync.set_video_frame(video_frame)
    finder.open()
    # ... resolve `source_name` from finder.get_source_names(); receiver.set_source(src) ...
    last_ts = None
    while not self._stop.is_set():
        if receiver.is_connected():
            receiver.frame_sync.capture_video()
            if min(video_frame.xres, video_frame.yres) != 0:          # NDI-03 empty-frame guard
                ts = video_frame.get_timestamp_posix()                # RBT-01 NEW-frame detection
                if ts != last_ts:                                     # only a NEW frame updates liveness
                    arr = video_frame.get_array().reshape(video_frame.yres, video_frame.xres, 4)
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                    self._publish(cam_id, bgr, ts)                    # store latest frame + last_frame_ts
                    last_ts = ts
    receiver.disconnect(); finder.close()
```
> The `ts != last_ts` check is the crux of RBT-01: a frozen feed keeps returning the same timestamp, so `last_frame_ts` stops advancing → the watchdog declares it dead.

### cyndilib mock Sender (NDI-02 — real-NDI side, E2E only)
```python
# src/segugio/ndi/mock_sender.py — publishes a clip as a named NDI source
# Source: cyndilib docs (sender reference)
from fractions import Fraction
def publish_clip(source_name, bgr_frames, fps=30):
    import cv2
    from cyndilib.sender import Sender
    from cyndilib.video_frame import VideoSendFrame
    from cyndilib.wrapper.ndi_recv import FourCC  # FourCC.BGRA / RGBA
    sender = Sender(source_name)                                   # the config `ndi_source` name
    vf = VideoSendFrame()
    h, w = bgr_frames[0].shape[:2]
    vf.set_resolution(w, h); vf.set_frame_rate(Fraction(fps, 1)); vf.set_fourcc(FourCC.BGRA)
    sender.set_video_frame(vf)
    with sender:
        for bgr in bgr_frames:
            bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
            sender.write_video_async(bgra)
```
> `[ASSUMED]` exact `VideoSendFrame` / `FourCC` import paths and `write_video_async` signature — confirm against the installed `cyndilib==0.1.1` on Windows (the docs example is the basis; the 0.1.1 API may differ slightly). Gate behind a real-NDI test marker.

### obsws-python v5: cut, cached PIP id, overlay, EventClient, reconnect (OBS-01/02/03/05)
```python
# src/segugio/obs/obsws_controller.py — heavy import inside (lazy boundary)
# Source: obsws-python README (aatikturk/obsws-python)
def connect(self):
    import obsws_python as obs
    self._req = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=3)
    self._evt = obs.EventClient(host=self.host, port=self.port, password=self.password)
    self._evt.callback.register(self._on_scene_changed)           # OBS-03 sync manual cuts
    self._cache_pip_ids()                                         # OBS-02 resolve+cache numeric ids

def _cache_pip_ids(self):
    # cache {(scene, source): numeric id} once at startup; refresh on SceneItemCreated/Removed
    self._item_ids = {("PIP", src): self._req.get_scene_item_id("PIP", src).scene_item_id
                      for src in self.pip_sources}

def cut(self, scene_name):
    self._req.set_current_program_scene(scene_name)              # OBS-01

def set_pip(self, scene, source, enabled, transform=None):       # OBS-02
    item_id = self._item_ids[(scene, source)]
    self._req.set_scene_item_enabled(scene, item_id, enabled)
    if transform: self._req.set_scene_item_transform(scene, item_id, transform)

def set_overlay_text(self, input_name, text):                    # OBS-05 one-shot fallback
    self._req.set_input_settings(input_name, {"text": text}, overlay=True)
```
> `[CITED: obsws-python README]` method names verified; the exact response attribute for the id (`.scene_item_id`) and `set_input_settings(..., overlay=True)` arg should be confirmed against `obsws-python==1.8.0` on Windows.

### Atomic write (SCR-01 + the whole operator↔system channel)
```python
# src/segugio/opcomm/atomic.py
import json, os
def atomic_write_json(path: str, obj: dict) -> None:
    d = os.path.dirname(os.path.abspath(path))                   # temp MUST be in the same dir/volume
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
        f.flush(); os.fsync(f.fileno())                          # durability before the swap
    os.replace(tmp, path)                                        # atomic on same volume (Windows: MoveFileEx)

def atomic_write_text(path: str, text: str) -> None:             # for the OBS read-from-file overlay
    d = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
```

### Flask operator console (separate process, D-02/04, Italian labels)
```python
# src/segugio/ui/app.py — imports NOTHING heavy
from flask import Flask, request, jsonify, render_template
from segugio.opcomm.channel import write_score, write_runstate, write_command, read_status
app = Flask(__name__)

@app.get("/")
def index():
    return render_template("console.html")                       # discipline selector + 3 field sets,
                                                                 # Avvia/Ferma, Forza/Rilascia, stato live
@app.post("/score")
def post_score():
    write_score(request.form.to_dict())                          # atomic write → score.json / overlay.txt
    return ("", 204)

@app.post("/run")
def post_run():
    write_runstate({"action": request.form["action"]})          # "start" | "stop" (D-09)
    return ("", 204)

@app.post("/command")
def post_command():
    write_command({"force_cam": request.form.get("force_cam"),  # "Forza CAM Long" → cam id
                   "release": request.form.get("release") == "1"})  # D-10 → OverrideCmd
    return ("", 204)

@app.get("/status")
def get_status():
    return jsonify(read_status())                               # D-11 live director status (page polls)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)                          # tablet over the dedicated WiFi
```
> The page POSTs map directly to the locked `OverrideCmd(force_cam=..., release=...)` contract (note: the two are mutually exclusive — `OverrideCmd.__post_init__` rejects both set, so the UI must send EITHER a force OR a release, never both).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `obs-websocket-py` (Elektordi, v4 protocol) | `obsws-python` 1.8.0 (v5 protocol) | obs-websocket v5 (OBS 28+) | Must use the v5 client; v4 method/protocol won't connect. |
| `SetTextGDIPlusProperties` for overlay text | read-from-file text source + `set_input_settings({"text":...})` | obs-websocket v5 | The GDI+ request was removed in v5; use read-from-file (primary) + generic settings (one-shot). |
| Polling NDI source "connected" state for liveness | Last-NEW-frame timestamp (`get_timestamp_posix`) | NDI design (TTL repeats frames) | The only correct liveness signal (RBT-01). |
| Frame-list `model.track([f1,f2,...])` for multi-cam | One `PerCameraTracker.track(persist=True)` per camera | Ultralytics issue #13107 | Already enforced in `run_clip_eval`; preserve it. |

**Deprecated/outdated:**
- `obs-websocket-py`, `SetTextGDIPlusProperties` — do not use.
- WSL2 for this phase — superseded by Windows-native dev (D-01) so real NDI/OBS run inline.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `VideoFrameSync.get_timestamp_posix()` advances per NEW frame and stalls on a repeated/frozen frame | §Code Examples, Pitfall 1 | If it advances on repeats, RBT-01 needs the timecode instead — try `get_timecode_posix()`; verify on Windows with a pull-cable test. Load-bearing for liveness. |
| A2 | cyndilib `Sender` API (`VideoSendFrame`, `FourCC`, `write_video_async`) matches the docs example on `0.1.1` | §Code Examples (mock Sender) | NDI-02 mock-sender code may need API adjustments; it's E2E-only, low blast radius. Confirm on the installed version. |
| A3 | `set_input_settings(input_name, {"text":...}, overlay=True)` and `get_scene_item_id(...).scene_item_id` are the exact 1.8.0 surfaces | §Code Examples (obsws) | Method names verified; the precise response attribute / kwarg may differ — confirm against `obsws-python==1.8.0`. |
| A4 | Flask is acceptable to add as a new runtime dep (not just `[heavy]`/dev) | §Standard Stack | D-02 locks Flask; the planner should decide whether it lands in core `dependencies` (UI is a runtime tool) or a new `[ui]` extra. |
| A5 | Polling the operator files each tick (no `watchdog`) is sufficient and preferred over event-driven reads | §Standard Stack, Pattern 3 | If per-tick file reads measurably hurt the latency budget, switch to `watchdog`. Low risk at ~30Hz over tiny JSON files. |
| A6 | The motion-energy value for D-08 action-hold is already exposed by `CompetitorLock` (not only computed internally) | §Don't Hand-Roll, Pattern 4 | If it's internal-only, a small additive accessor is needed on `CompetitorLock` — verify the exact attribute/return on the Windows box. |

## Open Questions (RESOLVED)

1. **Where does `CompetitorLock` expose the locked subject's motion energy for the D-08 action-hold?**
   - What we know: D-08 says the value is "already computed by `CompetitorLock`"; the action-hold derivation is a thin threshold/window over it.
   - What's unclear: the exact attribute/method name and whether it's on the returned `DetectionSignal` or the lock object.
   - Recommendation: planner inspects `src/segugio/tracking/competitor_lock.py` first; if it's internal-only, add a tiny pure accessor (additive, no logic change). Seed `ActionHoldParams{motion_threshold, window_ticks}` additively in config (mirrors `ScorerParams`/`TrackingParams`).

2. **Does `score.json` double as the OBS overlay, or is a separate `overlay.txt` needed?**
   - What we know: OBS read-from-file wants a plain rendered string; the UI may want structured JSON.
   - Recommendation: write BOTH atomically — `overlay.txt` (the rendered Italian overlay line for OBS-05) and `score.json` (structured, for the UI/status). Both via the same atomic helper. (Score-file content is Claude's discretion per CONTEXT.)

3. **D-09 STOP→SAFE mechanism: a dedicated between-runs hold, or force the SAFE target?**
   - Recommendation (planner's call per CONTEXT): the simplest correct option is to pass a synthetic "park" into the tick that drives the FSM toward SAFE while STOP is latched, with Override still winning (RBT-03 is the top tier). Avoid a new FSM state if forcing the SAFE target through the existing surface suffices.

## Environment Availability

| Dependency | Required By | Available (this session) | Version | Fallback |
|------------|------------|--------------------------|---------|----------|
| Python | All | ✓ | 3.12 (`requires-python>=3.12`) | — |
| `cyndilib` + libndi runtime | NDI-01/02 (real path, E2E) | ✗ (not installed here; on Windows box) | 0.1.1 (pinned) | In-process clip mock (D-05) for all headless tests |
| `obsws-python` + running OBS | OBS-01..05 (real path, E2E) | ✗ (Windows box) | 1.8.0 (pinned) | Recording fake (D-06) for all headless tests |
| OBS Studio + DistroAV + obs-websocket v5 | OBS-04 real cuts (E2E) | ✗ (Windows box) | OBS 28+ | Fake controller; manual scene-template import on Windows |
| `Flask` | SCR-02/03, D-10/11 UI | ✗ (must add) | 3.1.3 | none — required (small, safe to add) |
| CUDA `torch` + `ultralytics` + `yolo26s.pt` | the YOLO stage | ✗ here; ✓ on RTX 4000 Ada (D-01) | torch CUDA / ultralytics 8.4.62 | `@pytest.mark.gpu`-gated; mock frames for non-GPU tests |
| `opencv-python` | mock reader, cvtColor | ✗ here; ✓ Windows | 4.13.0.92 | — |

**Missing dependencies with no fallback:** Flask (add it; trivial). The real NDI/OBS/CUDA stack has NO fallback for the on-Windows E2E acceptance (D-07) — that run must happen on the Windows box.
**Missing dependencies with fallback:** All headless work runs against the in-process clip mock + recording OBS fake + GPU-marker-gated inference; the entire suite is green with cyndilib/obsws/OBS/CUDA absent (the lazy-import boundary guarantees imports succeed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest==9.0.3` (+ `pytest-cov==7.1.0`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`, marker `gpu`) |
| Quick run command | `python -m pytest tests/ -q -m "not gpu and not ndi and not obs"` |
| Full suite command | `python -m pytest tests/ -q` (on Windows; runs gpu/ndi/obs-marked tests where the env is present) |
| New markers (extend the `gpu` precedent) | `ndi` (real cyndilib path), `obs` (real OBS path) — registered in `[tool.pytest.ini_options].markers` |

> **D-01 gotcha:** run `python -m pytest` (never bare `pytest`) — ultralytics pollutes the bare-`pytest` entry point. Re-verify the equivalent on Windows.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NDI-01 | Real cyndilib receiver yields BGR frames + last-NEW-frame ts | integration (real NDI) | `python -m pytest tests/test_ndi_source.py -m ndi -x` | ❌ Wave 0 |
| NDI-02 | Mock Sender publishes a named source consumable by the receiver | integration (real NDI) | `python -m pytest tests/test_ndi_mock_sender.py -m ndi -x` | ❌ Wave 0 |
| NDI-03 | Empty/zero-res first frames are skipped (mock yields blanks then frames) | unit | `python -m pytest tests/test_frame_source_empty_guard.py -x` | ❌ Wave 0 |
| OBS-01 | `cut("CAM Long")` → recording fake records `set_current_program_scene("CAM Long")` | unit | `python -m pytest tests/test_obs_mapping.py::test_cut -x` | ❌ Wave 0 |
| OBS-02 | PIP toggles use the CACHED numeric id; id resolved once at connect | unit | `python -m pytest tests/test_obs_mapping.py::test_pip_cached_id -x` | ❌ Wave 0 |
| OBS-03 | Reconnect path re-creates the client after a simulated drop | unit (fake) / integration | `python -m pytest tests/test_obs_reconnect.py -x` | ❌ Wave 0 |
| OBS-04 | Scene-template file exists + names match config `obs_scene`/`SAFE` | unit | `python -m pytest tests/test_scene_template.py -x` | ❌ Wave 0 |
| OBS-05 | Overlay write hits the read-from-file path; `set_input_settings({"text":...})` one-shot fallback | unit | `python -m pytest tests/test_overlay.py -x` | ❌ Wave 0 |
| SCR-01 | Atomic write: a concurrent reader never sees a partial file; round-trips | unit | `python -m pytest tests/test_atomic_io.py -x` | ❌ Wave 0 |
| SCR-02 | Flask POST /score for each discipline writes the expected file content | unit (Flask test client) | `python -m pytest tests/test_ui_score.py -x` | ❌ Wave 0 |
| SCR-03 | Run start/stop writes runstate; START flags lock-reset, STOP flags SAFE-park | unit | `python -m pytest tests/test_ui_run.py -x` | ❌ Wave 0 |
| SCR-04 | No scoring/adjudication code path exists (display-only) | unit (assert no compute) | `python -m pytest tests/test_score_display_only.py -x` | ❌ Wave 0 |
| RBT-01 | Watchdog liveness on INJECTED timestamps: stalled ts → dead after timeout+grace | unit (pure) | `python -m pytest tests/test_watchdog.py -x` | ❌ Wave 0 |
| RBT-02 | Feed-death → `alive[cam]=False` → FSM excludes it → SAFE/other-live; rejoin after full hysteresis | unit | `python -m pytest tests/test_fallback_rejoin.py -x` | ❌ Wave 0 |
| RBT-04 | A thrown error in any stage (UI file / decode / OBS) → loop coasts to SAFE, never crashes; SAFE on shutdown | unit (inject-throwing fakes) | `python -m pytest tests/test_fault_isolation.py -x` | ❌ Wave 0 |
| RBT-05 | Latency harness: frame→YOLO→score→FSM→OBS p95 < 150ms (target <80ms) | integration (gpu) / unit (mock-timed) | `python -m pytest tests/test_latency.py -m gpu -x` | ❌ Wave 0 |
| D-08 | Sustained motion energy → `HoldInput.action=True` → FSM holds the cut (DEC-03 cap) | unit | `python -m pytest tests/test_action_hold.py -x` | ❌ Wave 0 |
| D-11 | Orchestrator writes status (live cam + reason + per-feed alive/dead) the UI reads | unit | `python -m pytest tests/test_status_channel.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -q -m "not gpu and not ndi and not obs"` (fast, deterministic, headless).
- **Per wave merge:** full headless suite `python -m pytest tests/ -q -m "not ndi and not obs"` (+ `-m gpu` on the GPU box for latency).
- **Phase gate:** full suite green on Windows (incl. `-m "gpu or ndi or obs"`) PLUS the one human E2E run (D-07) before `/gsd-verify-work`.

### Latency-measurement harness (RBT-05, the focus of this integration phase)
- Wrap each tick stage with `time.perf_counter()` deltas (ingest-pull, YOLO, score, FSM, OBS-cut); record per-stage + total; assert total **p95 < 150ms** (target <80ms) over a sustained window.
- Two modes: (1) **mock-timed** — substitute a fixed-cost inference stub so the harness validates the *wiring overhead* deterministically off-GPU; (2) **gpu** — real `yolo26s.pt` on the RTX 4000 Ada for the true number (D-07/RBT-05). The OBS round-trip (~35–60ms, the dominant tail per TECHNICAL-RESEARCH) is measured but kept off the inference critical path (cut command is the cheap localhost op).
- Record the degradation ladder trigger points (if total > budget → yolo26n → fewer cams → lower AI-path imgsz/fps, per STACK.md).

### Fault-isolation assertions (RBT-04)
- Inject throwing fakes at each seam (a `FrameSource` that raises on `latest`, an `ObsController` that raises on `cut`, a channel that returns a malformed command) and assert: the loop logs, coasts to SAFE, and continues ticking — process never exits. Assert a SAFE cut is emitted on shutdown.

### Watchdog liveness math (RBT-01)
- Pure test on INJECTED `(now, last_frame_ts)` pairs: ts advancing → alive; ts stalled for `> watchdog_timeout` (0.8s) with anti-jitter grace → dead; ts resuming → alive again only after a fresh frame. No wall-clock, no real NDI — the math is clock-free and deterministic.

### Camera-id→obs_scene mapping (D-06)
- Drive the orchestrator with the recording OBS fake; for a `Decision(target="cam_long")` assert the fake recorded `cut("CAM Long")` (the config `obs_scene`), and for `target="SAFE"` assert `cut("SAFE")`.

### Atomic-file round-trips (SCR-01 + channel)
- Write each record type via the atomic helper; assert a reader interleaved with a writer never observes a partial/empty file (stress with many rapid writes); assert the temp file lands in the SAME directory as the target.

### Wave 0 Gaps
- [ ] `tests/test_atomic_io.py` — covers SCR-01 (atomic round-trip + same-dir temp)
- [ ] `tests/test_watchdog.py` — covers RBT-01 (injected-timestamp liveness math)
- [ ] `tests/test_obs_mapping.py` — covers OBS-01/02 (recording fake: cut + cached PIP id)
- [ ] `tests/test_obs_reconnect.py` — covers OBS-03 (reconnect)
- [ ] `tests/test_overlay.py` — covers OBS-05
- [ ] `tests/test_scene_template.py` — covers OBS-04 (template names match config)
- [ ] `tests/test_frame_source_empty_guard.py` — covers NDI-03
- [ ] `tests/test_fallback_rejoin.py` — covers RBT-02
- [ ] `tests/test_fault_isolation.py` — covers RBT-04 (throwing fakes → SAFE coast)
- [ ] `tests/test_latency.py` — covers RBT-05 (mock-timed + gpu-marked)
- [ ] `tests/test_ui_score.py`, `tests/test_ui_run.py` — cover SCR-02/03 (Flask test client)
- [ ] `tests/test_score_display_only.py` — covers SCR-04
- [ ] `tests/test_action_hold.py` — covers D-08
- [ ] `tests/test_status_channel.py` — covers D-11
- [ ] `tests/test_ndi_source.py`, `tests/test_ndi_mock_sender.py` — cover NDI-01/02 (`@pytest.mark.ndi`, Windows-only)
- [ ] `tests/conftest.py` — shared fixtures: a tiny `Config` builder, a fake `FrameSource`, a `RecordingObsController`, an injected-timestamp clock, a tmp_path file channel
- [ ] Register `ndi` + `obs` markers in `pyproject.toml [tool.pytest.ini_options].markers`
- [ ] Framework install: none needed (pytest present); add `Flask==3.1.3` for the UI tests

## Sources

### Primary (HIGH confidence)
- `src/segugio/tracking/eval.py` (`run_clip_eval`), `frame_source.py`, `decision/engine.py`, `decision/signals.py`, `framing/scorer.py`, `config/models.py`, `config.example.yaml` — the locked Phase 1–4 contracts the orchestrator wires (read directly this session).
- `.planning/research/TECHNICAL-RESEARCH.md` — locked per-module stack, two-pipeline architecture, latency verdict, obs-websocket v5 details, risk table.
- `.planning/research/ARCHITECTURE.md` §Part 5 — the concrete OBS scene template + SAFE/PIP/MULTIVIEW guidance.
- `.planning/research/PITFALLS.md` — Pitfall 3/7 (coast/action-hold) + the UX pitfalls (surface WHY → SAFE; fast override) → D-08/D-10/D-11.
- cyndilib docs — `video_frame` reference (`get_array`, `xres`/`yres`, `get_timestamp_posix`/`get_timecode_posix`, `get_fourcc`) and examples; the royshil gist (Finder/Receiver/VideoFrameSync → numpy → cv2). `[VERIFIED: cyndilib readthedocs + gist]`
- obsws-python README (aatikturk/obsws-python) — `ReqClient`/`EventClient`, `set_current_program_scene`, `get_scene_item_id`, `set_scene_item_enabled`, `set_scene_item_transform`, `set_input_settings`, `callback.register`. `[VERIFIED: GitHub README]`
- `pip index versions` — cyndilib 0.1.1, obsws-python 1.8.0, Flask 3.1.3 confirmed latest/pinned. `[VERIFIED: PyPI]`

### Secondary (MEDIUM confidence)
- zetcode / python-atomicwrites / bugs.python.org#8828 — `os.replace` atomicity, same-volume requirement, Windows `MoveFileEx` "usually atomic" caveat, fsync durability. `[CITED]`

### Tertiary (LOW confidence)
- cyndilib `Sender` exact 0.1.1 API (`VideoSendFrame`/`FourCC`/`write_video_async`) — docs-example-based; confirm on the installed version (A2).
- The precise NEW-frame liveness signal (`get_timestamp_posix` vs `get_timecode_posix`) — confirm with a Windows pull-cable test (A1).

## Metadata

**Confidence breakdown:**
- Wiring contracts (orchestrator = grown-up `run_clip_eval`; scorer/FSM/config signatures): HIGH — read directly from source this session.
- cyndilib receive + NDI-03 guard + obsws-python v5 calls + atomic write: HIGH — verified against docs/gist/README + PyPI pins.
- cyndilib Sender API + exact liveness timestamp behavior: MEDIUM/LOW — confirm on the installed `0.1.1` + a Windows pull-cable test (A1/A2).
- Latency number under load with 3–4 cameras: MEDIUM — only the on-Windows GPU E2E run gives the real figure (RBT-05/D-07).

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable; obs-websocket v5 / cyndilib / Flask are mature — re-verify only the pinned versions and the two LOW-confidence items on the Windows box).
