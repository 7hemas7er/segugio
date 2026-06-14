# Phase 3: Decision Engine FSM - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 builds a **`transitions`-based finite state machine that is the sole authority on which camera is live**. It consumes per-camera `CameraScore(tick, cam_id, score, status∈{tracking,coasting,lost})` plus feed-liveness events and emits **guarded, jitter-free switching decisions** — never double-cutting, never flickering, never selecting a dead feed, holding through climaxes and expected occlusions, and supporting manual override with automatic resume. Like the Phase-2 scorer it is **pure, tick-driven, and deterministic** (time enters as an injected tick; no wall-clock, no RNG), so its full behavior is unit-tested on the **synthetic score + feed-death streams already built in Phase 1** before any detector or OBS is wired.

Delivers DEC-01..07 + RBT-03:
- FSM as single source of truth; no switch decision emitted outside a guarded transition (DEC-01)
- Two-threshold hysteresis + `min_dwell` + `debounce_N` + `cooldown` → no flicker, no double-cut (DEC-02)
- Action-in-progress hold (DEC-03) and expected-occlusion hold (DEC-04)
- Deterministic tiebreaker for near-tied scores (DEC-05)
- Feed-alive guard: a dead feed is never live nor challenger (DEC-06)
- Unit-tested on synthetic score + feed-death streams: ping-pong/tie/dropout/recovery/override/occlusion (DEC-07)
- Manual override + auto-resume (RBT-03)

**NOT in this phase:**
- No YOLO/tracker/detector and no real action/occlusion triggers — the hold inputs are **explicit signals fed synthetically** here; pose/disc detection (action) and detection-in-occlusion-zone (occlusion) are wired in Phase 4/5.
- No OBS / obs-websocket — the FSM **emits a decision**; the orchestrator (Phase 5) turns it into an OBS scene cut.
- No feed watchdog implementation (RBT-01), no orchestrator/fault-isolation (RBT-04), no latency loop (RBT-05) — those DRIVE this FSM and live in Phase 5. Phase 3 consumes a liveness signal; it does not derive it from NDI.
- No numeric tuning — all thresholds are config seeds already present; calibration happens on the curated clip set in Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Feed-death fallback (DEC-06 / Success Criterion 2)
- **D-01:** When the **live** camera's feed dies, the FSM performs an **emergency cut to the highest-scoring camera whose feed is ALIVE**, dropping to the **SAFE** scene only if no camera qualifies. This emergency cut **bypasses `min_dwell`/`cooldown`** — a dead feed must never stay on air. The newly-selected live camera then receives normal `min_dwell`/`cooldown` protection. A dead camera is never selected as live nor as challenger (DEC-06). A recovered camera rejoins only after winning full hysteresis + dwell (the rejoin orchestration RBT-02 is Phase 5, but the FSM transition logic must support it).

### Action / occlusion hold (DEC-03, DEC-04)
- **D-02:** The FSM learns that an action (catch/jump) or an expected occlusion (tunnel/contact) is in progress from **explicit per-tick hold input(s) it exposes as first-class inputs** — NOT inferred from score dynamics. In Phase 3 these are driven by **synthetic hold windows** in tests. The real triggers are deferred: pose/disc detection for action (v2 differentiator), detection-in-occlusion-zone for occlusion (Phase 4/5 wiring). This keeps the FSM pure and fully unit-testable now.

### Manual override + auto-resume (RBT-03)
- **D-03:** Override **persists through a feed-death** of the forced camera. A dead feed is never aired: while the forced camera is dead the FSM falls to **SAFE (or the best live alternative per D-01)**, then **snaps back to the forced camera the instant its feed recovers**. Override ends ONLY on explicit release (or the operator forcing a different camera).
- **D-04:** Override release is **manual-only in v1** — no auto-expire timeout. (A config `override_timeout` auto-release is a deferred safety option — see Deferred.)
- **D-05:** A manual force is applied **immediately** — it bypasses `min_dwell`/`debounce_N`/`cooldown` (an operator command, not auto-switching noise). Forcing an already-dead camera shows SAFE (or the best live alternative) and waits for that camera to come alive — it never airs the dead feed.
- **D-06 (locked by ROADMAP, restated):** Auto-resume fires only after the override is released **AND** the auto candidate has won the **full hysteresis + `min_dwell`** qualification — no snap to a flickery auto pick.

### Deterministic tiebreaker (DEC-05)
- **D-07:** The tiebreaker fires only for **near-exact** score ties inside the hysteresis dead-band. Resolution: the current live camera (**incumbent**) wins the tie — stickiness that reinforces hysteresis and minimizes cuts. When there is **no incumbent** (cold start, or just returned from SAFE), fall back to the **first camera in config declaration order**. No new role-priority concept is introduced.

### Claude's Discretion (planner/research decide the details)
- **Hold input shape** — one generic `hold` flag vs two typed inputs (`action_hold` / `occlusion_hold`) is the planner's call. **Guardrails (mandatory):** (a) occlusion-hold MUST respect the per-discipline config `FramingDefaults.hold_length_s` (disc 2.5s / agility 1.5s) as its bound; (b) **every** hold MUST have a safety max-cap so a stuck/forgotten hold signal can never freeze the show indefinitely. Lean: two typed inputs (occlusion auto-expires via `hold_length_s`; action holds while-set with a max cap) — unify if cleaner.
- **Emitted decision contract** — the FSM emits a guarded "live target" decision the Phase-5 orchestrator consumes; no OBS command is emitted outside a guarded transition (DEC-01). Exact shape (event-on-change vs per-tick state, whether a reason/cause is attached for logging/debug) is the planner's call. **SAFE is a selectable target** — modeled as an FSM state or a pseudo-camera, planner's choice.
- **Cold start** — the FSM begins on **SAFE** and switches to the first camera that qualifies (feed-alive + `debounce_N` + clears the hysteresis upper threshold). Sensible default; planner may refine.
- **Two-threshold hysteresis derivation** — the dead-band is built from `hysteresis_margin` around the incumbent's score (challenger must exceed incumbent by the margin AND sustain it `debounce_N` ticks); the exact upper/lower threshold formula is the planner's call.
- **Tick-driven determinism** — drive the FSM once per tick with time entering as an injected tick (no wall-clock, no RNG), mirroring the Phase-2 scorer / Phase-1 synth convention so behavior is byte-reproducible on synthetic streams (DEC-07). The `transitions` library is locked (ROADMAP).
- **Threshold tuning** — all numeric thresholds are config seeds already present; calibrate on clips in Phase 4, not here. α (Phase 2, D-07) must be tuned **jointly** with `debounce_N`/`min_dwell`/`hysteresis_margin` (a smoother α permits a shorter debounce; a snappier α needs a longer one).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-3 scope & requirements
- `.planning/ROADMAP.md` §"Phase 3: Decision Engine FSM" — goal, the 5 success criteria, and the 4 plan stubs (03-01 core FSM+hysteresis/dwell/debounce/cooldown · 03-02 feed-guard/action-hold/occlusion-hold/tiebreaker · 03-03 override+auto-resume · 03-04 synthetic-stream test suite).
- `.planning/REQUIREMENTS.md` — DEC-01..07 + RBT-03 (this phase). Also RBT-01/02/04/05 (Phase 5 — the watchdog + orchestrator that DRIVE this FSM) for awareness of the consumer contract.

### Project decisions & scope
- `.planning/PROJECT.md` — core value (right camera at the right moment, fluid cuts, no operator), the "no crash / SAFE fallback" robustness constraint, and key decisions (override+auto-resume despite "no operator"; liveness via last-frame timestamp, never NDI source state; two-budget latency).

### Domain research (the WHY behind each guard)
- `.planning/research/ARCHITECTURE.md` — FSM-as-single-source-of-truth, guarded transitions, SAFE scene.
- `.planning/research/PITFALLS.md` — the exact failure modes the guards counter (ping-pong, double-cut, flicker, cutting on a dead feed, cutting mid-climax).
- `.planning/research/SUMMARY.md` — the hysteresis + dwell + debounce + cooldown stack; α tuned jointly with debounce/dwell.
- `.planning/research/FEATURES.md` — per-discipline hold semantics (`hold_length_s`).

### Phase-1/2 contracts the FSM consumes verbatim (read directly)
- `src/segugio/config/models.py` — `Thresholds` (`hysteresis_margin=0.1`, `min_dwell=2.0`, `debounce_N=3`, `cooldown=1.0`, `watchdog_timeout=0.8`, `alpha=0.3`); `Camera.is_safe` (≥1 guaranteed by the SAFE-fallback cross-validator).
- `src/segugio/config/discipline.py` — `FramingDefaults.hold_length_s` (disc 2.5 / agility 1.5) = the occlusion-hold bound.
- `src/segugio/framing/signals.py` — `CameraScore(tick:int, cam_id:str, score:float, status:ScorerStatus)`, `ScorerStatus ∈ {tracking, coasting, lost}` — the FSM's per-camera input record.
- `src/segugio/framing/scorer.py` — `MultiCamScorer.update(dets_by_cam, tick) -> list[CameraScore]` — the per-tick fan-out the FSM consumes.
- `src/segugio/synth/score_stream.py` — `ScoreSample(tick:int, cam_id:str, score:float)` + `SCENARIOS = (ping_pong, tie, dropout, recovery)` — the DEC-07 score-stream test substrate (note: this emits final scores; the FSM may consume `ScoreSample.score` directly or wrap as `CameraScore` — planner's call).
- `src/segugio/synth/feed_death.py` — `FeedEvent(tick:int, cam_id:str, alive:bool)` + `feed_death(...)` — the DEC-06 / DEC-07 feed-liveness test substrate (death + optional recovery, fully deterministic).
- `tests/conftest.py` — `seeded_rng` / `valid_config_dict` fixtures to reuse; add an FSM-config / thresholds fixture.

### Prior phase context
- `.planning/phases/02-framing-scorer-pure-logic/02-CONTEXT.md` — the scorer's output contract and the α↔FSM joint-tuning cross-dependency (D-07).
- `.planning/phases/01-foundation-config-curated-clip-set/01-CONTEXT.md` — the determinism convention (frozen dataclasses + injected tick/RNG), config schema, and lazy-import boundary this phase must honor.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`segugio.config` (Phase 1):** typed, validated `Config` — `Thresholds.*` (all FSM knobs), `Camera.is_safe` (SAFE target guaranteed), `FramingDefaults.hold_length_s` (occlusion bound). The FSM reads these; no new config is strictly required (the FSM seeds already exist).
- **`segugio.framing` (Phase 2):** `CameraScore` / `ScorerStatus` (the FSM input), `MultiCamScorer` (the per-tick fan-out). The FSM sits directly downstream of `MultiCamScorer.update(...)`.
- **`segugio.synth` (Phase 1):** `score_stream` (ping_pong/tie/dropout/recovery) + `feed_death` (per-cam liveness) are the **ready-made DEC-07 test substrate** — same frozen-dataclass + injected-`Generator` + injected-tick determinism pattern the FSM tests mirror.
- **`tests/conftest.py`:** reuse `seeded_rng` / `valid_config_dict`; add an FSM/thresholds fixture.
- **`pyproject.toml`:** `pythonpath=["src"]`, `testpaths=["tests"]` already set; the src-layout editable install auto-discovers a new `segugio/decision/` (or similar) package — verify with one import.

### Established Patterns
- **Lazy-import boundary:** the FSM module must import cleanly with torch/ultralytics/cyndilib/obsws absent (it's pure logic, CPU-only). `transitions` is a light pure-Python dep — confirm it's not on the heavy/lazy list.
- **Determinism convention:** frozen dataclasses for `==`-based assertions; zero randomness and zero wall-clock; time = injected tick. Same seed → byte-identical decision sequence (DEC-07).
- **Run tests via `.venv/bin/pytest`** (or `.venv/bin/python -m pytest`) — system `python`/`python3` is not on PATH / does not see numpy.

### Integration Points
- **Input (scorer → FSM):** `list[CameraScore]` per tick (from `MultiCamScorer`) + a per-camera feed-alive signal (synthetic `FeedEvent.alive` in Phase 3; Phase-5 watchdog later) + the explicit hold input(s) + the manual override command.
- **Output (FSM → orchestrator):** a guarded "live target" decision (a camera id or the SAFE scene). Phase 5 maps this to an OBS scene cut. No OBS coupling in Phase 3.

</code_context>

<specifics>
## Specific Ideas

- **Test the absence of cuts, not just their presence.** The headline DEC-02 assertion is *zero spurious cuts* replaying `ping_pong` and `tie` streams — the FSM must NOT chase an alternating leader or oscillate on equidistant noise. Count emitted transitions and assert it stays minimal.
- **Two safety invariants to assert hard:** (1) no switch decision is EVER emitted outside a guarded transition (DEC-01); (2) a camera whose `FeedEvent.alive` is false is NEVER the emitted live target nor a challenger (DEC-06) — including the override case (D-03: a forced-but-dead camera shows SAFE).
- **Override + occlusion + feed-death are the high-value scenario tests** (DEC-07): force-then-release-then-resume; hold-through-occlusion-then-release; live-feed-death-mid-hold (death wins — a dead feed is never held on air).

</specifics>

<deferred>
## Deferred Ideas

- **`override_timeout` auto-release** — a config knob that auto-releases a forgotten manual override after N seconds. Considered; v1 is manual-release-only. Revisit if operators report forgotten-override incidents.
- **Real action/occlusion triggers** — pose/disc detection driving `action_hold` (v2 differentiator), and detection-in-occlusion-zone driving `occlusion_hold` (Phase 4/5 wiring). Phase 3 ships the explicit hold inputs only.
- **Role-based tiebreaker priority** — a role ranking for the no-incumbent case. Rejected for v1 in favor of config declaration order (no new concept). Revisit only if config order proves unintuitive.
- **Motion-adaptive α coupling** (Phase 2 deferred) — when α becomes motion-adaptive, the FSM `debounce_N`/`min_dwell` will need joint re-tuning. Noted as a future cross-dependency.
- **Numeric threshold calibration** — `hysteresis_margin`, `min_dwell`, `debounce_N`, `cooldown`, `watchdog_timeout` are config seeds; calibrate on the curated clip set in Phase 4.

</deferred>

---

*Phase: 03-decision-engine-fsm*
*Context gathered: 2026-06-09*
