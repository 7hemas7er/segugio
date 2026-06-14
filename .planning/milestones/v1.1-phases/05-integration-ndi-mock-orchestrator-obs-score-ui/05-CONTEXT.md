# Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 wires every module built in Phases 1–4 into **one end-to-end, hardware-free loop** that closes the v1 milestone: a mock NDI source publishes recorded clips as named NDI sources, cyndilib ingest delivers numpy BGR frames per camera via supervised threads, a timestamp-based feed watchdog drives automatic fallback, an OBS controller cuts scenes / toggles PIP / updates overlays, a manual score-entry UI writes atomically to an OBS read-from-file text source, and a fault-isolated orchestrator ticks the full **frame → YOLO → score → FSM → OBS** loop within the latency budget and degrades to SAFE without ever crashing. Delivers NDI-01..03, OBS-01..05, SCR-01..04, RBT-01, RBT-02, RBT-04, RBT-05.

The orchestrator's per-tick pipeline is the **live successor of Phase 4's `run_clip_eval`** (`src/segugio/tracking/eval.py:230`): same per-camera fan-out (`PerCameraTracker` → `signals_from_boxes` → `CompetitorLock` → `PlausibilityGate` → `DetectionSignal | None`), now feeding `MultiCamScorer.update(...)` → `DecisionEngine.tick(...)` → OBS cut, with the clip frame source swapped for the NDI frame source.

**NOT in this phase:**
- **No new detection/tracking/scorer/FSM logic** — Phases 1–4 are locked. Phase 5 *wires* them; it does not change the brains.
- **No real phones / real WiFi / real field** — the mock NDI source replaces phones (milestones 6+).
- **No RTMP/YouTube output** — v1 is local preview only (OBS PROGRAM); real output is a later milestone.
- **No external scoring-system API** — scores are manual entry only (SCR-04: display, never adjudicate; no CV scoring/faults/catches).
- **No TensorRT FP16 export / production-GPU tuning** — hardware-milestone work.
- **No autonomous occlusion-hold** — deferred (needs config occluder-zones + agility/tunnel footage, both absent). Only action-hold from motion is wired (see D-08).
- **No disc/frisbee or pose signals** — v2 differentiators.

</domain>

<decisions>
## Implementation Decisions

### Development & test environment (the premise shift)
- **D-01: Phase 5 is developed and tested on Windows native (PowerShell), not WSL2.** PROJECT.md recommends Windows for the NDI/OBS ecosystem and flags WSL2 as problematic (mDNS discovery + OBS GUI). Rather than work around that, Phase 5 work moves to the **final environment** where libndi + avahi/Bonjour and OBS run natively, so **real NDI + real OBS are testable inline** instead of deferred. The user relaunches the Claude Code session from a **PowerShell** terminal on the repo; `.planning/` (including this CONTEXT) carries over. **Re-verify on Windows:** the Windows CUDA build of `torch`/`ultralytics` for the RTX 4000 Ada, and the ultralytics-pollutes-pytest gotcha (run `python -m pytest`).

### Score-entry / operator UI (SCR-02/03/04)
- **D-02: Local web page (Flask), served on localhost.** The manual score panel is an **HTML page served by a Flask app** on `http://localhost:<port>`, openable from a browser on the dev box OR from a tablet/phone over the dedicated WiFi. Chosen over CLI/TUI/tkinter because it is OS-agnostic, sidesteps the WSL2/desktop-GUI problem, and is ergonomic for live field entry. Italian labels (project convention). Flask specifically (synchronous, 1 dep, fits a tiny serve-page + POST + atomic-file-write app) over stdlib/FastAPI.
- **D-03: The UI is a SEPARATE PROCESS that writes files directly — never embedded in the orchestrator.** The Flask app writes the score file (and the run-state/override file, D-09/D-10) with the atomic temp + `os.replace` pattern (SCR-01); OBS reads the score file via a read-from-file text source; the orchestrator reads the run-state/override file each tick. **The orchestrator and the UI share no memory and no process.** Rationale: a bug in the UI can never crash the director (RBT-04 fault isolation), and the panel can run on a tablet while the orchestrator runs headless on the GPU box. All operator↔system communication is via **atomic files** — no new IPC, no websocket, decoupled by construction.
- **D-04: The web panel is a small OPERATOR CONSOLE, not just a scoreboard.** It carries four concerns on one page: (1) **score entry** — discipline selector + 3 per-discipline field sets (disc Toss&Fetch: prese/zona/totale; disc freestyle: nome+timer; agility: tempo vs SCT + faults); (2) **run start/stop** (D-09); (3) **override controls** (D-10); (4) a **live status read-back** (D-11). At a small event scorekeeper and director are usually the same person → one panel.

### Frame ingest & end-to-end testability (NDI-01/02/03, RBT-01/02)
- **D-05: A `FrameSource` interface with two implementations.** (a) the **real cyndilib receiver** (Finder/Receiver/FrameSync → numpy BGR, one supervised thread per camera; the default on Windows) and (b) an **in-process clip-replay mock** that yields numpy BGR frames from the curated clips with no network/libndi. The orchestrator, watchdog, scorer, FSM, and OBS controller depend only on the interface. Day-to-day unit/integration tests run headless against the mock (deterministic, no NDI/OBS required — preserves the lazy-import boundary); the real NDI path is the integration acceptance. **NDI-02's named-source mock-SENDER still exists** (a cyndilib `Sender` publishing the clips as named NDI sources) — it lives on the real-NDI side and is exercised by the on-Windows E2E run, not by the in-process unit tests.
- **D-06: The OBS controller sits behind the same interface pattern.** Real `obsws-python` `ReqClient`/`EventClient` (default) + a **recording fake** that captures commands (`SetCurrentProgramScene`, PIP `SetSceneItemTransform`/`SetSceneItemEnabled`, `SetInputSettings`) with no OBS running. Lets the orchestrator's camera-id→`obs_scene` mapping, PIP toggling via cached `sceneItemId`, and the **failure paths** (feed-death → SAFE, reconnect) be asserted headless and deterministically (`assert called SetCurrentProgramScene("CAM Long")`). Real obsws + the scene-collection template + EventClient = integration acceptance.
- **D-07: E2E acceptance bar = headless suite + one real on-Windows run.** CI/headless: the full loop against mock NDI + fake OBS (fault-isolation, watchdog fallback, camera→scene mapping, latency-measurement harness). Human UAT on Windows: mock-sender NDI publishes the clips as named sources → cyndilib ingest → YOLO → score → FSM → **real OBS** cuts scenes/PIP + overlay updates from the panel → a feed is cut/frozen → watchdog → SAFE → the frame→YOLO→score→FSM→OBS loop latency is measured under ~150ms (target <80ms) (RBT-05).

### Hold-signal wiring (Phase-4 deferral; Pitfalls 3/7)
- **D-08: v1 wires ACTION-hold from motion energy only; occlusion-hold stays deferred.** The orchestrator derives a simple action-hold from the **locked subject's motion energy** (already computed by `CompetitorLock`): sustained high motion = "action in progress" → arm the FSM `HoldInput` action-hold (which already carries a mandatory max-cap, DEC-03). This directly defends the core value ("never cut mid-catch/mid-jump") using a signal already on hand. **No autonomous occlusion-hold** — it needs config-marked occluder zones and agility/tunnel footage, both absent (same gap flagged UNVERIFIED in Phase 4). The action-hold threshold/window are **additive config seeds** (same additive pattern as `ScorerParams`/`TrackingParams`).

### Run start/stop drives the pipeline (SCR-03)
- **D-09: Manual run start/stop STEERS the pipeline, not just the overlay.** START resets the `CompetitorLock` (fresh subject re-acquisition — avoids dragging the previous dog's lock into a new run; a manual start is a more reliable acquisition trigger than autonomous zone+motion) AND drives the overlay/timer. STOP parks the director on **SAFE** between runs (the natural idle scene per ARCHITECTURE Part 5) and stops the timer. Run-state reaches the orchestrator via a **small atomic run-state file** written by the UI and read each tick — same file mechanism as the score file, UI stays decoupled (D-03).

### Operator override affordance (exposing the built RBT-03 live)
- **D-10: Override is exposed on the same web panel ("Regia" section).** Buttons "Forza CAM Wide/Long/Low/Handler" + "Rilascia (auto)" write the override command into the run-state/operator-command file; the orchestrator reads it each tick and passes an `OverrideCmd` into `DecisionEngine.tick(...)`. RBT-03 (force + manual-release auto-resume) is already built and is the **top-priority FSM tier** — it wins even between runs (e.g., during a course walk). This closes the PITFALLS UX gap ("operator watches it film the wrong dog with no recourse"). Not a new capability — wiring an existing one into the live loop.
- **D-11: The panel shows LIVE DIRECTOR STATUS (reverse channel).** The orchestrator writes a small **atomic status file** on each change — current live camera + reason (`auto` / `override` / `subject-lost` / `feed-dead`) + per-feed alive/dead — which the panel polls and displays (e.g. "Live: CAM Long — auto", "Live: SAFE — feed morto cam_low"). Closes the other PITFALLS UX gap ("operator can't tell 'lost the dog' from 'feed died'") and tells the operator *when* forcing is worth it. Lightweight: orchestrator → file → panel polling, reusing the atomic-file pattern.

### Claude's Discretion (planner / research decide the details)
- **Orchestrator threading & per-tick inference strategy** — supervised per-camera receiver threads + the fixed-rate (~30 Hz) tick pulling latest frames; whether per-camera YOLO inference is sequential vs batched to hold the <150ms budget with 3–4 cameras, and the degradation ladder if over budget (yolo26n, fewer cams, lower AI-path imgsz/fps per STACK.md). Keep `tick` an injected index (determinism convention).
- **Exact FSM "between-runs → SAFE" mechanism** (D-09) — a dedicated between-runs hold vs forcing the SAFE target; planner's call. Override (RBT-03) must still win.
- **File layout for operator↔system channel** — one combined "operator commands" file vs separate score / run-state / override files, and the status read-back file format; all via atomic temp + `os.replace`. Planner's call; keep each write atomic.
- **Action-hold seed placement** (D-08) — additive config sub-model location and the motion threshold/window constants (config seeds, tuned opportunistically).
- **Score file content / overlay layout** — exact text written per discipline for the OBS read-from-file source; not pinned in discussion.
- **PIP / MULTIVIEW usage** — ARCHITECTURE Part 5 recommends building the PIP machinery (cached `sceneItemId`) but driving MULTIVIEW/PIP **manually / idle-only** in v1, not from the auto-director. Honor that default unless research shows otherwise.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-5 scope & requirements
- `.planning/ROADMAP.md` §"Phase 5: Integration — NDI Mock, Orchestrator, OBS & Score UI" — goal, the 5 success criteria, and the 6 plan stubs (05-01 NDI ingest · 05-02 mock NDI source · 05-03 OBS controller + scene template + read-from-file overlay · 05-04 feed watchdog + fallback + guarded rejoin · 05-05 score manager + manual UI · 05-06 orchestrator tick + fault isolation + SAFE shutdown + latency).
- `.planning/REQUIREMENTS.md` — NDI-01..03, OBS-01..05, SCR-01..04, RBT-01, RBT-02, RBT-04, RBT-05 (this phase). RBT-03 (override) is already complete in Phase 3 but is **exposed** here (D-10).

### Locked technical stack (the WHY behind every integration choice)
- `.planning/research/TECHNICAL-RESEARCH.md` — **the load-bearing Phase-5 doc**: per-module library table (cyndilib FrameSync, obsws-python ReqClient+EventClient, watchdog/numpy timestamp-liveness, orchestrator fixed-rate tick), the two-decoupled-pipelines architecture (VIDEO vs CONTROL), the latency verdict + two budgets, the verified obs-websocket v5 details (don't hardcode the text input kind; resolve+cache numeric `sceneItemId`; reconnect), and the risk table (NDI false-liveness, #13107, WiFi jitter, websocket throughput). **What NOT to use:** `obs-websocket-py` (v4), `SetTextGDIPlusProperties` (removed in v5), frame lists to `model.track()`.
- `.planning/research/ARCHITECTURE.md` §"Part 5 — OBS scene set" — the concrete default scene template (`CAM Wide/Long/Low/Handler`, `SAFE` as first-class scene, optional `MULTIVIEW`/`PIP`), scene-name conventions, score-overlay-inside-each-CAM-scene, and the "PIP/MULTIVIEW manual/idle-only in v1" guidance. Part 3 = the per-camera normalized zone model the loop consumes.
- `.planning/research/PITFALLS.md` — UX Pitfalls table (surface WHY it went to SAFE; fast override; auto-resume must not immediately re-make the mistake → D-10/D-11) and Pitfalls 3/7 (coast/TTL + action-suppression → D-08). The "Looks Done But Isn't" checklist is the integration review lens.

### Project decisions & scope
- `.planning/PROJECT.md` — OBS-as-hub + separate Python NDI ingest (decode twice); liveness via last-new-frame timestamp (75-min NDI freeze gotcha); manual scores → read-from-file; obsws-python sync ReqClient; output-preview-only v1; Windows-recommended / OS-agnostic code; the Out-of-Scope boundaries this phase must respect.

### Phase 1–4 contracts the orchestrator wires (read directly)
- `src/segugio/tracking/eval.py` §`run_clip_eval` (line 230) — **the live loop's precursor**: the exact per-camera fan-out the orchestrator replicates (tracker → `signals_from_boxes` → `CompetitorLock` → `PlausibilityGate` → `DetectionSignal | None`), the once-before-loop `assert_native_reid_engaged` hard gate (TRK-02), and the per-frame fail-safe (decode/inference error → coast, never crash).
- `src/segugio/framing/scorer.py` §`MultiCamScorer.update(dets_by_cam, tick) -> list[CameraScore]` (line 266) — the scorer the loop feeds (per-camera `DetectionSignal | None` in, `CameraScore` list out; coast/TTL already handled).
- `src/segugio/decision/engine.py` §`DecisionEngine.tick(scores, alive, holds, override) -> Decision` (line 428) and `src/segugio/decision/signals.py` (`Decision`, `HoldInput`, `OverrideCmd`) — the FSM the loop drives: pass the watchdog's `alive` map (D-05/RBT-01), the motion-derived `HoldInput` (D-08), and the panel's `OverrideCmd` (D-10); cut OBS to `Decision.target`'s `obs_scene`.
- `src/segugio/config/models.py` — `Camera{id, role, obs_scene, is_safe, ndi_source, zones}` (the id→scene + id→NDI-source + SAFE mapping the controller/ingest consume), `Thresholds.watchdog_timeout` (=0.8, RBT-01), `ModelConfig`. `config.example.yaml` / `config.agility.example.yaml` — the 4-camera rig with `obs_scene` names matching the ARCHITECTURE scene template and `ndi_source` names matching the mock sender.

### Prior phase context
- `.planning/phases/04-yolo-per-camera-tracking-on-recorded-clips/04-CONTEXT.md` — the per-camera pipeline + the explicitly-deferred "detection-in-occlusion-zone → FSM occlusion_hold wiring" now resolved here as **action-hold only** (D-08); the GPU UAT note (native-ReID verified on RTX 4000 Ada; COCO-dog recall weak on distant/crowd).
- `.planning/phases/03-decision-engine-fsm/03-CONTEXT.md` — the FSM authority + override (RBT-03) semantics this phase exposes live (D-10).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`segugio.tracking.eval.run_clip_eval` (Phase 4):** the per-camera fan-out + hard ReID gate + per-frame fail-safe is the orchestrator's template — swap `ClipFrameSource` for the `FrameSource` NDI implementation (D-05), then continue into `MultiCamScorer` + `DecisionEngine`.
- **`segugio.tracking.frame_source.ClipFrameSource` (Phase 4):** the existing clip → crop reader is the natural basis for the **in-process clip-replay mock** `FrameSource` implementation (D-05) — it already produces per-camera numpy frames with an injected tick + empty-frame guard (NDI-03 analogue).
- **`segugio.framing.scorer.MultiCamScorer` + `segugio.decision.DecisionEngine` (Phases 2/3):** consumed unchanged. The scorer's coast/TTL and the FSM's guards/holds/override already exist — Phase 5 only supplies their inputs (signals, alive map, holds, override).
- **`segugio.config` (Phase 1):** `Camera.obs_scene` / `Camera.ndi_source` / `Camera.is_safe` and `Thresholds.watchdog_timeout` are already in the contract — the controller, ingest, watchdog, and SAFE fallback read them with no schema change (action-hold seeds extend config additively).
- **Atomic-write convention:** the score manager's temp + `os.replace` (SCR-01) is the SAME mechanism reused for the run-state, override-command, and status read-back files (D-03/D-09/D-10/D-11) — one file pattern for the whole operator↔system channel.

### Established Patterns
- **Lazy-import boundary (since 01-01):** `import segugio.<pkg>` must succeed with `cyndilib`/`obsws`/`ultralytics`/`torch`/`cv2` ABSENT. The `FrameSource`/OBS interfaces + in-process/fake implementations (D-05/D-06) keep the orchestrator and its unit tests on the light side of that boundary; heavy clients load only inside the real implementations.
- **GPU-marker test split (Phase 4 `@pytest.mark.gpu`):** the precedent for gating heavy/environment-dependent tests. Phase 5 adds the analogous gating for the real-NDI / real-OBS paths (headless mock+fake tests always run; real-stack tests run only where the environment is present — now Windows native).
- **Determinism convention:** frozen dataclasses, injected `tick`, no wall-clock in pure logic. The orchestrator owns the clock/threads (it is the I/O edge), but the watchdog's liveness math and the loop wiring should stay testable on injected timestamps.
- **Run tests via the venv interpreter (`python -m pytest`)** — ultralytics pollutes a bare `pytest`; re-verify the equivalent on Windows.

### Integration Points
- **Input edge:** mock/real NDI → `FrameSource` → per-camera numpy BGR (supervised threads) → the orchestrator tick.
- **Operator edge:** Flask panel (separate process) → atomic score / run-state / override files → orchestrator reads each tick; orchestrator → atomic status file → panel polls (D-11).
- **Output edge:** `DecisionEngine.tick` → `Decision.target` → `Camera.obs_scene` → OBS controller cut/PIP; score file → OBS read-from-file text source overlay.

</code_context>

<specifics>
## Specific Ideas

- **One atomic-file channel for everything operator↔system.** Scores, run start/stop, override commands, and the director status read-back all flow through atomic temp + `os.replace` files — no websocket, no shared memory, no new IPC. This is the spine that keeps the UI a crash-isolated separate process (D-03) and is the single most repeated decision of this phase.
- **The orchestrator IS `run_clip_eval` grown up.** Reviewers should treat `eval.py:run_clip_eval` as the reference for the live loop's structure (per-camera fan-out, the once-before-loop hard ReID gate, the per-frame coast-on-error fail-safe) — the integration is wiring, not reinvention.
- **Move to the final environment instead of mocking around WSL2.** The biggest premise change: do Phase 5 on Windows native so real NDI + OBS are inline, while the interface+mock pattern keeps everything headless-testable anyway (D-01/D-05/D-06). Best of both — fidelity on Windows, deterministic CI everywhere.
- **The web panel is the project's only human surface — make it an honest operator console.** Score entry + run lifecycle + override + live status, all on one Italian page (D-04/D-09/D-10/D-11), directly serving the two PITFALLS UX gaps (fast override; show WHY it cut to SAFE).

</specifics>

<deferred>
## Deferred Ideas

- **Autonomous occlusion-hold** (config occluder-zone marking → "hold the exit-framing camera" through tunnels/contacts) — needs marked occluder zones + agility/tunnel footage, both still absent (carried from Phase 4). Action-hold from motion ships in v1 (D-08); occlusion-hold revisits when real agility footage arrives.
- **Disc/frisbee lead-the-dog prediction** (`classes=[16,29]`, catch anticipation) — v2 differentiator; keep disc logic out of shared/agility paths.
- **Pose-based heading/intent action-hold** (`yolo26s-pose`) — v2.
- **RTMP/YouTube output engine** — v1 is preview-only; real output defined later.
- **Auto-driven MULTIVIEW/PIP** — PIP machinery is built (cached `sceneItemId`) but driven manually/idle-only in v1 per ARCHITECTURE Part 5; auto-PIP for long throws is a later nicety.
- **TensorRT FP16 export / production-GPU latency tuning** — hardware milestone (GPU-specific engines).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 05-integration-ndi-mock-orchestrator-obs-score-ui*
*Context gathered: 2026-06-10*
