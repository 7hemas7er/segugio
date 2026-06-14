# Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 5-integration-ndi-mock-orchestrator-obs-score-ui
**Areas discussed:** Score-entry UI, Mock NDI + E2E bar, Hold-signal wiring, Run start/stop role, Operator override affordance

---

## Score-entry UI

### Form factor

| Option | Description | Selected |
|--------|-------------|----------|
| Local web page (Flask) | localhost HTTP page, openable on browser/tablet over WiFi; OS-agnostic; sidesteps WSL2-GUI | ✓ |
| Terminal TUI | keyboard full-screen terminal app; adds TUI dep; dev-terminal only | |
| Plain CLI prompts | stdlib input(); zero dep; clunky for live use | |
| Desktop GUI (tkinter) | stdlib Tk window; WSL2 GUI flagged problematic | |

**User's choice:** Local web page.
**Notes:** User first asked which UI this was — clarified it is the manual *score-entry* panel (SCR-02/03/04), the only human-operated surface; it writes scores into the OBS read-from-file overlay and does NOT control camera switching or show video. Then reformulated the options in Italian and the user picked the web page (preview chosen: discipline dropdown + Toss&Fetch fields + AVVIA/STOP + timer).

### Coupling to the system

| Option | Description | Selected |
|--------|-------------|----------|
| Separate process → writes file | UI is its own process; writes the score file atomically; OBS reads it; orchestrator never knows about it; a UI bug can't crash the director (RBT-04) | ✓ |
| Inside the orchestrator | web server as a thread of the orchestrator process; shared state but a UI bug risks the director | |

**User's choice:** Separate process → writes file.
**Notes:** Flagged that this implies run start/stop must reach the orchestrator some other way (resolved later via an atomic run-state file).

### Web stack

| Option | Description | Selected |
|--------|-------------|----------|
| Flask | synchronous, minimal, 1 dep; fits a tiny serve-page + POST + atomic-write app | ✓ |
| stdlib http.server | zero new deps; more manual routing/form parsing | |
| FastAPI + uvicorn | async, 2 deps; overkill for a file-writer | |
| You decide | defer to planner within "minimal, few deps, headless-testable" | |

**User's choice:** Flask.

---

## Mock NDI + E2E bar

### Environment given the WSL2 NDI/OBS caveat

| Option | Description | Selected |
|--------|-------------|----------|
| Interface + 2 implementations | FrameSource abstraction; mock in-process for WSL2/CI, real NDI gated like GPU | (offered) |
| Real-only on Windows | build only the real NDI path; most of Phase 5 runs only on a native host | (offered) |
| **(user-proposed) Continue from PowerShell / final environment** | move the work to Windows native where libndi/avahi + OBS run natively; real NDI+OBS testable inline | ✓ |

**User's choice:** "possiamo continuare questa chat da powershell, cosi siamo nell'ambiete finale" — develop/test Phase 5 on Windows native, the recommended prod env.
**Notes:** Reflected back the two practical implications (the user relaunches the session from PowerShell; Windows CUDA build of torch/ultralytics + re-verify the pytest gotcha). This reframed the abstraction question below rather than replacing it.

### Frame ingest abstraction (asked after the env shift)

| Option | Description | Selected |
|--------|-------------|----------|
| Interface + mock | FrameSource: real cyndilib receiver (default) + in-process clip-replay mock; headless-testable; real path = integration acceptance | ✓ |
| Real-only on Windows | no in-process mock; full loop verified only against real NDI+OBS | |

**User's choice:** Interface + mock (recommended).

### OBS controller testability

| Option | Description | Selected |
|--------|-------------|----------|
| Same pattern | controller behind interface; real obsws-python + recording fake for headless; real path = integration acceptance | ✓ (recommended on request) |
| Real OBS only | controller always talks to a live OBS; tests need OBS + scene collection | |

**User's choice:** User asked "cosa consigli?"; Claude recommended the same pattern (consistency, deterministic failure-path tests, RBT-04, speed, low cost) and the user accepted. E2E bar derived: headless mock+fake suite in CI + one real on-Windows end-to-end run as human UAT (incl. feed-kill → SAFE + loop latency measurement).

---

## Hold-signal wiring

| Option | Description | Selected |
|--------|-------------|----------|
| Action-hold from motion | derive action-hold from CompetitorLock motion energy → FSM HoldInput (max-cap already in FSM); no autonomous occlusion-hold | ✓ |
| Holds off in v1 | ship holds=None; rely on min_dwell/cooldown/debounce/coast | |
| Action + occlusion full | wire both; needs occluder zones + agility footage (absent) | |

**User's choice:** Action-hold from motion (recommended).
**Notes:** Occlusion-hold stays deferred (no occluder zones / no agility-tunnel footage, carried from Phase 4). Action-hold threshold/window as additive config seeds (Claude discretion).

---

## Run start/stop role

| Option | Description | Selected |
|--------|-------------|----------|
| Drive the pipeline | START resets competitor-lock + STOP parks SAFE between runs; run-state via atomic file the orchestrator reads | ✓ |
| Overlay/timer only | start/stop touches only the overlay; pipeline stays Phase-4 autonomous | |
| Lock-reset on start only | reset lock on START via run-state file but don't force SAFE on STOP | |

**User's choice:** Drive the pipeline (recommended).
**Notes:** Resolves the decoupled-UI tension — run-state reaches the orchestrator through the same atomic-file mechanism as the score file. Operator override stays top-tier in the FSM and wins even between runs (Claude discretion on the exact FSM "between-runs → SAFE" mechanism).

---

## Operator override affordance

### Where to expose force/release

| Option | Description | Selected |
|--------|-------------|----------|
| Same web panel ("Regia" section) | force/release buttons write the override command into the run-state/command file → OrchestratorCmd → FSM | ✓ |
| Separate operator console | a second page/process for direction; cleaner roles but doubles UI surface | |
| Defer past v1 | leave override unexposed; accept the UX gap | |

**User's choice:** Same web panel (recommended).
**Notes:** RBT-03 (override) is already built in the FSM (Phase 3) and not in Phase 5's requirement list — this is exposing an existing capability, not adding one (PITFALLS UX gap).

### Live status read-back

| Option | Description | Selected |
|--------|-------------|----------|
| Show live status | orchestrator writes an atomic status file (live camera + reason auto/override/subject-lost/feed-dead + per-feed alive); panel polls & shows it | ✓ |
| Blind commands | panel only writes commands; no status return | |

**User's choice:** Show live status (recommended).
**Notes:** Closes the PITFALLS UX gap ("operator can't tell subject-lost from feed-dead") and tells the operator when forcing is worth it. Reverse channel reuses the atomic-file pattern. The web panel thus becomes a small operator console (scores + run lifecycle + override + status).

---

## Claude's Discretion

- Orchestrator threading + per-camera inference strategy vs the <150ms budget (sequential vs batched; degradation ladder yolo26n / fewer cams / lower imgsz-fps).
- Exact FSM "between-runs → SAFE" mechanism (override must still win).
- File layout for the operator↔system channel (combined vs separate score/run-state/override/status files); all atomic temp + os.replace.
- Action-hold seed placement + motion threshold/window constants (config seeds).
- Score-file content / overlay layout per discipline.
- PIP/MULTIVIEW: build the machinery but keep it manual/idle-only in v1 (ARCHITECTURE Part 5).

## Deferred Ideas

- Autonomous occlusion-hold (occluder zones + agility/tunnel footage absent).
- Disc/frisbee lead-the-dog prediction (v2).
- Pose-based heading/intent action-hold (v2).
- RTMP/YouTube output engine (v1 preview-only).
- Auto-driven MULTIVIEW/PIP (manual/idle-only in v1).
- TensorRT FP16 export / production-GPU tuning (hardware milestone).
