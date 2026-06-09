# Phase 3: Decision Engine FSM - Research

**Researched:** 2026-06-09
**Domain:** Pure, tick-driven finite state machine (camera-switching decision authority) on `transitions`
**Confidence:** HIGH (the FSM design, `transitions` API, and Phase-1/2 contracts are all verified against shipped source + Context7; only numeric tuning is intentionally out of scope)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (feed-death fallback):** When the **live** camera's feed dies, the FSM performs an **emergency cut to the highest-scoring camera whose feed is ALIVE**, dropping to **SAFE** only if no camera qualifies. The emergency cut **bypasses `min_dwell`/`cooldown`**. The newly-selected live camera then receives normal `min_dwell`/`cooldown` protection. A dead camera is never selected as live nor challenger (DEC-06). A recovered camera rejoins only after winning full hysteresis + dwell (rejoin orchestration RBT-02 is Phase 5; the FSM transition logic must support it).
- **D-02 (action / occlusion hold):** The FSM learns an action (catch/jump) or expected occlusion (tunnel/contact) is in progress from **explicit per-tick hold input(s) it exposes as first-class inputs** — NOT inferred from score dynamics. In Phase 3 these are driven by **synthetic hold windows** in tests. Real triggers deferred (pose/disc for action; detection-in-occlusion-zone for occlusion, Phase 4/5).
- **D-03 (override persists through feed-death):** Override **persists through a feed-death** of the forced camera. While the forced camera is dead, the FSM falls to **SAFE (or best live alternative per D-01)**, then **snaps back to the forced camera the instant its feed recovers**. Override ends ONLY on explicit release (or the operator forcing a different camera).
- **D-04 (manual release only):** Override release is **manual-only in v1** — no auto-expire timeout. (`override_timeout` is a deferred safety option.)
- **D-05 (force is immediate):** A manual force is applied **immediately** — it bypasses `min_dwell`/`debounce_N`/`cooldown`. Forcing an already-dead camera shows SAFE (or best live alternative) and waits for that camera to come alive — never airs the dead feed.
- **D-06 (auto-resume qualification, locked by ROADMAP):** Auto-resume fires only after the override is released **AND** the auto candidate has won the **full hysteresis + `min_dwell`** qualification — no snap to a flickery auto pick.
- **D-07 (deterministic tiebreaker):** The tiebreaker fires only for **near-exact** score ties inside the hysteresis dead-band. Resolution: the current live camera (**incumbent**) wins. With **no incumbent** (cold start / just returned from SAFE), fall back to the **first camera in config declaration order**. No new role-priority concept.

### Claude's Discretion

- **Hold input shape** — one generic `hold` flag vs two typed inputs (`action_hold` / `occlusion_hold`). **Mandatory guardrails:** (a) occlusion-hold MUST respect per-discipline `FramingDefaults.hold_length_s` (disc 2.5s / agility 1.5s) as its bound; (b) **every** hold MUST have a safety max-cap so a stuck/forgotten hold signal can never freeze the show indefinitely. Lean: two typed inputs.
- **Emitted decision contract** — event-on-change vs per-tick state; whether a reason/cause is attached. **SAFE is a selectable target** — FSM state or pseudo-camera, planner's choice.
- **Cold start** — FSM begins on **SAFE**; switches to the first camera that qualifies (feed-alive + `debounce_N` + clears hysteresis upper threshold).
- **Two-threshold hysteresis derivation** — dead-band built from `hysteresis_margin` around the incumbent's score; challenger must exceed incumbent by the margin AND sustain it `debounce_N` ticks; exact formula is planner's call.
- **Tick-driven determinism** — drive the FSM once per tick; time enters as injected tick (no wall-clock, no RNG). `transitions` is locked (ROADMAP).
- **Threshold tuning** — all numeric thresholds are config seeds already present; calibrate in Phase 4. α (Phase 2 D-07) tuned **jointly** with `debounce_N`/`min_dwell`/`hysteresis_margin`.

### Deferred Ideas (OUT OF SCOPE)

- `override_timeout` auto-release knob.
- Real action/occlusion triggers (pose/disc for action; detection-in-occlusion-zone for occlusion).
- Role-based tiebreaker priority (config declaration order is the v1 rule).
- Motion-adaptive α coupling (Phase 2 deferred; future joint re-tuning cross-dependency).
- Numeric threshold calibration (config seeds; calibrate on the curated clip set in Phase 4).
- No YOLO/tracker/detector, no OBS/obs-websocket, no feed watchdog impl (RBT-01), no orchestrator (RBT-04), no latency loop (RBT-05) — those DRIVE this FSM and live in Phase 5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEC-01 | FSM is the single source of truth on which camera is live; **no decision emitted outside a guarded transition** | §State Topology + §Pattern 1 (decision emitted ONLY from a `transitions` callback fired by a successful guarded trigger; tick-loop never writes the live target directly) |
| DEC-02 | Hysteresis (two-threshold dead-band) + `min_dwell` + `debounce_N` + `cooldown` → no flicker, no double-cut | §Two-Threshold Hysteresis + §Guard Clocks (dwell/cooldown in ticks; challenger debounce counter); §Pattern 2 |
| DEC-03 | Action-in-progress hold (catch/jump) → defer cut | §Hold Inputs (`action_hold`, while-set + max-cap) |
| DEC-04 | Expected-occlusion hold (tunnel/contact) → don't cut away | §Hold Inputs (`occlusion_hold`, auto-expires via `hold_length_s` bound + max-cap) |
| DEC-05 | Deterministic tiebreaker for near-tied scores (no ping-pong) | §Tiebreaker (incumbent-wins; no-incumbent → config order) |
| DEC-06 | Feed-alive guard — a dead feed is never live nor challenger | §Feed-Death Emergency Cut + §Guard: dead-feed exclusion in candidate selection |
| DEC-07 | FSM unit-testable on synthetic score + feed-death streams (ping_pong/tie/dropout/recovery/override/occlusion) | §Test Substrate (drive from `score_stream` + `feed_death`; zero-spurious-cut assertion; combined scenarios) |
| RBT-03 | Manual override + auto-resume | §Override + Auto-Resume (override mode layered on auto FSM) |
</phase_requirements>

## Summary

Phase 3 is a **pure, deterministic, tick-driven decision engine** built on the locked `transitions` library. It is the single authority on which camera is live (a camera id or SAFE). Each tick the orchestrator (synthetic tests in Phase 3) feeds it: a `list[CameraScore]`, a per-camera feed-alive map, the explicit hold input(s), and an optional override command. The FSM evaluates **guards** (feed-alive, hysteresis dead-band, `debounce_N` sustain, `min_dwell`, `cooldown`, holds, override) and emits a switch decision **only** from inside a guarded `transitions` callback — the invariant that makes DEC-01 mechanically true. All "time" is the injected integer tick; seconds-valued config (`min_dwell`, `cooldown`, `hold_length_s`) is converted to ticks once via an injected `fps`. Same input stream → byte-identical decision sequence, mirroring the Phase-1 synth and Phase-2 scorer determinism contract.

The recommended topology is **operational-mode states** (`SAFE`, `LIVE`, `OVERRIDE`) with the **selected camera id held as a model attribute**, not one state per camera. This keeps the guarded-transition graph small (a handful of edges), keeps the emitted-decision contract trivial (`current_target = cam_id | SAFE`), and lets the auto-switching logic (hysteresis/dwell/debounce/cooldown), the feed-death emergency cut, the holds, and the override all be expressed as guards/clocks on a tiny set of transitions. The challenger/debounce counter and the dwell/cooldown clocks live as plain integer model attributes ticked by the engine — `transitions` provides the state/guard scaffolding, not the counters.

**Primary recommendation:** Build a thin `DecisionEngine` wrapper around a `transitions.Machine` with three operational states and a model attribute for the live camera id. Drive it with one `tick(scores, alive, holds, override)` method that (1) advances all integer clocks/counters, (2) computes the best **eligible** (alive, hold-permitting) candidate, (3) fires guarded triggers in a fixed priority order (override → feed-death emergency → hold → normal-switch), and (4) returns a frozen `Decision(tick, target, mode, reason)` record. Move `transitions==0.9.3` from the `heavy` optional group to the **light runtime `dependencies`** (it is pure-Python, no C/GPU deps) and add `segugio.decision` to the lazy-import-boundary surface test. The four plan stubs (03-01 core, 03-02 guards/holds/tiebreaker, 03-03 override, 03-04 test suite) map cleanly onto this design.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| "Which camera is live" decision | Decision FSM (`segugio.decision`) | — | DEC-01: the FSM is the sole authority; nothing else may emit a switch |
| Per-camera framing score | Framing scorer (`segugio.framing`, Phase 2) | — | Already shipped; FSM consumes `CameraScore`, does not compute it |
| Feed liveness signal | Feed watchdog (Phase 5, RBT-01) | Synthetic `FeedEvent.alive` (Phase 3 tests) | FSM **consumes** liveness; never derives it from NDI |
| Hold triggers (action/occlusion) | Detector/pose/zone logic (Phase 4/5) | Synthetic hold windows (Phase 3 tests) | D-02: FSM exposes explicit hold inputs; real triggers deferred |
| Override command | Operator UI / orchestrator (Phase 5) | Synthetic override events (Phase 3 tests) | FSM exposes an override input; UI is Phase 5 |
| Decision → OBS scene cut | OBS controller (Phase 5, OBS-01) | — | FSM emits a target id/SAFE; OBS coupling is explicitly NOT in Phase 3 |
| Tick scheduling / fault isolation | Orchestrator (Phase 5, RBT-04) | Test loop (Phase 3) | FSM is driven once per tick; it does not own the loop |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `transitions` | 0.9.3 | The finite state machine (states, guarded transitions, callbacks) | Locked by brief/ROADMAP. `[VERIFIED: PyPI]` exists, current (0.9.3 latest), pure-Python, no native/GPU deps, 6.5k-star actively-maintained `pytransitions/transitions`. Idiomatic `conditions`/`unless`/`prepare`/`before`/`after` callback model fits guarded-transition needs exactly. `[CITED: github.com/pytransitions/transitions]` |
| `numpy` | 2.4.6 | (test substrate only) drives `score_stream`/`feed_death`; argmax over eligible scores | Already a light runtime dep. The FSM core itself needs no numpy — selecting best-of can be plain Python `max(...)`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` (stdlib) | — | Frozen `Decision` output record (`==`-comparable for determinism assertions) | Always — mirrors `CameraScore`/`ScoreSample`/`FeedEvent` frozen-dataclass convention |
| `enum` (stdlib) | — | `Mode` enum (`SAFE`/`AUTO`/`OVERRIDE`) and any reason enum, str-Enum for `==`/JSON friendliness | Always — mirrors `ScorerStatus`/`Role` |
| `pytest` 9.0.3 + `pytest-cov` 7.1.0 | — | Test runner (already in `.venv`) | The DEC-07 synthetic-stream suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `transitions.Machine` | Hand-rolled `if/elif` state dispatch | Brief locks `transitions`; also, a hand-rolled switch is exactly the "no decision outside a guarded transition" footgun — `transitions` makes the guard the only path to a state change. **Do not hand-roll the FSM.** |
| Operational-mode states + cam-id attribute | One state per camera (`LIVE_cam0`, `LIVE_cam1`, …) | Per-camera states explode the transition graph to O(N²) edges, hardcode camera count into the state set (breaks 3-vs-4-camera config), and scatter the guard logic. Mode-states keep it O(1) edges + one attribute. **Recommend mode-states.** |
| `transitions.Machine` callbacks holding all logic | `Machine` for state only + guards evaluated in the tick-loop | Pure-condition callbacks (`conditions`/`unless`) are the cleanest DEC-01 enforcement (a failed condition is a silent no-op — verified in Context7). Keep the *guard predicates* as model methods referenced by `conditions`; keep the *clock/counter advancement* in the tick-loop before triggers fire. |

**Installation:**
```bash
# transitions is ALREADY pinned in pyproject.toml (currently in the `heavy` group).
# RECOMMENDED CHANGE: move it to the light runtime `dependencies` and install:
.venv/bin/pip install transitions==0.9.3
```

**Version verification:**
```bash
.venv/bin/pip index versions transitions   # → 0.9.3 (latest), full version list confirmed
```
`[VERIFIED: PyPI]` `transitions==0.9.3` is the latest release and resolves; the sdist downloads and builds metadata cleanly with no native build step.

## Package Legitimacy Audit

> slopcheck was **not available** at research time (`command -v slopcheck` empty; not installable in this sandbox). Per protocol, the package below is verified by registry + authoritative source + age/popularity instead, and is treated as legitimate (NOT auto-`[ASSUMED]`) because it is (a) already pinned in the committed `pyproject.toml`, (b) mandated by the brief/ROADMAP, and (c) confirmed via the official GitHub source repo and Context7. The planner should still gate the actual install behind the normal test-green wave, but no `checkpoint:human-verify` is required for this single, well-known, already-committed package.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `transitions` | PyPI | ~10 yrs (first release 0.1; latest 0.9.3) | ~2–3M/mo (widely used) | github.com/pytransitions/transitions (6.5k stars, actively maintained) | n/a (tool unavailable) | **Approved** — already pinned, brief-locked, source-verified |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

No `postinstall`/build-script concern: `transitions` is pure-Python, no native extension, no install hooks beyond standard wheel install.

## Architecture Patterns

### System Architecture Diagram

```
  PER TICK (one call to DecisionEngine.tick), time = injected integer tick:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ INPUTS (assembled by orchestrator/test for tick t):                      │
  │   scores:   list[CameraScore]              (from MultiCamScorer, Phase 2) │
  │   alive:    dict[cam_id -> bool]           (FeedEvent.alive, synth here)  │
  │   holds:    HoldInput(action: bool, occlusion: bool)   (synthetic here)   │
  │   override: OverrideCmd | None             (force cam_id | release | None)│
  └───────────────────────────────┬─────────────────────────────────────────┘
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ DecisionEngine.tick(...)  — the ONLY entry point:                         │
  │                                                                           │
  │ 1. ADVANCE CLOCKS/COUNTERS (plain ints on the model):                     │
  │      dwell_elapsed += 1 ; cooldown_remaining = max(0, cooldown-1)         │
  │      occlusion_hold_remaining = max(0, ...-1)   action_hold_age += 1      │
  │      update challenger debounce counter from this tick's scores           │
  │                                                                           │
  │ 2. COMPUTE ELIGIBLE CANDIDATES (pure):                                    │
  │      eligible = {cam : alive[cam]}   (DEC-06: dead feeds excluded here)   │
  │      best_eligible = argmax score over eligible (config order tiebreak)   │
  │                                                                           │
  │ 3. FIRE GUARDED TRIGGERS in fixed priority (each is a no-op if guard      │
  │    fails — DEC-01: a state/target change happens ONLY inside a callback): │
  │      a) override commands      (force / release)                          │
  │      b) feed-death emergency   (live feed died → cut now, bypass dwell)   │
  │      c) hold                   (suppress any switch this tick)            │
  │      d) normal auto-switch     (challenger cleared hysteresis+debounce    │
  │                                 AND dwell elapsed AND cooldown clear)     │
  │                                                                           │
  │ 4. EMIT: frozen Decision(tick, target, mode, reason)                      │
  │    (event-on-change semantics: reason="hold"/"none" when target unchanged)│
  └───────────────────────────────┬─────────────────────────────────────────┘
                                  ▼
            Decision(tick, target=cam_id|SAFE, mode, reason)  → (Phase 5) OBS cut
```

### Recommended Project Structure
```
src/segugio/decision/
├── __init__.py        # re-exports DecisionEngine, Decision, Mode, HoldInput, OverrideCmd
├── signals.py         # frozen records: Decision, HoldInput, OverrideCmd + Mode/Reason enums
├── engine.py          # DecisionEngine: the transitions.Machine wrapper + tick() loop + guards
└── clocks.py          # ticks_from_seconds(seconds, fps) helper (mirrors ttl_ticks_from_seconds)
```
(Mirror the `segugio/framing/` split: `signals.py` = frozen contracts, `engine.py` = the stateful object, a tiny pure helpers file. Add `segugio.decision` to `PHASE1_SURFACE`-style import test.)

### Pattern 1: The decision is emitted ONLY from a guarded transition (DEC-01)

**What:** The live target (`model.target`) is mutated **only** inside a `transitions` callback (`before`/`after`/`on_enter`) that runs as the body of a transition whose `conditions` already passed. The tick-loop never writes `model.target = x` directly. A trigger whose condition fails is a **silent no-op** (Context7-verified: "No cars waiting - transition fails silently … state unchanged").

**When to use:** Always — it is the mechanical guarantee behind DEC-01.

**Example (idiomatic `transitions`, shape only — not final code):**
```python
# Source: Context7 /pytransitions/transitions — conditions/unless + before callback
from transitions import Machine

STATES = ["safe", "auto", "override"]

TRANSITIONS = [
    # cold start / no eligible camera → SAFE
    {"trigger": "to_safe", "source": "*", "dest": "safe",
     "before": "_set_target_safe"},

    # normal auto switch: only if challenger cleared hysteresis+debounce AND dwell+cooldown ok
    {"trigger": "auto_switch", "source": ["auto", "safe"], "dest": "auto",
     "conditions": ["challenger_qualified", "dwell_elapsed", "cooldown_clear"],
     "unless": ["holding"],
     "before": "_promote_challenger"},          # ← the ONLY place target changes on a normal cut

    # feed-death emergency: live feed died → cut to best-alive (or safe), bypass dwell/cooldown
    {"trigger": "feed_emergency", "source": ["auto", "override"], "dest": "auto",
     "conditions": ["live_feed_dead", "has_alive_candidate"],
     "before": "_emergency_cut"},
    {"trigger": "feed_emergency", "source": ["auto", "override"], "dest": "safe",
     "conditions": ["live_feed_dead"], "unless": ["has_alive_candidate"],
     "before": "_set_target_safe"},

    # override force (immediate, bypasses dwell/debounce/cooldown — D-05)
    {"trigger": "force", "source": "*", "dest": "override",
     "before": "_apply_force"},
    {"trigger": "release", "source": "override", "dest": "auto",
     "before": "_begin_resume_qualification"},
]
```
The tick-loop calls these triggers in priority order; each is a no-op unless its `conditions` hold, so `model.target` can never change except through a passed guard. `dest` may equal the source state ("internal-ish" reflexive transition) — the callback still fires only when the guard passes.

### Pattern 2: Integer clocks/counters on the model, advanced before triggers

**What:** `dwell_elapsed`, `cooldown_remaining`, `occlusion_hold_remaining`, `action_hold_age`, and the `challenger_id`/`challenger_streak` counter are plain `int`/`str|None` attributes on the model. The tick-loop advances them at the **top** of `tick()` (step 1), then guards read them.

**When to use:** Always. `transitions` does not manage counters; it manages states and guard dispatch. Keeping clocks as ordinary ints (a) preserves determinism (no timers, no wall-clock), (b) makes them trivially assertable in tests, and (c) keeps `min_dwell`/`cooldown`/`hold_length_s` measured **in ticks** (converted once from seconds via `fps`).

**Tick↔seconds bridge:** Config holds `min_dwell`, `cooldown`, `hold_length_s` in **seconds**; `debounce_N` is already in **ticks**. There is **no `fps` field in the current config** (verified: `Thresholds` has alpha/hysteresis_margin/min_dwell/debounce_N/cooldown/watchdog_timeout/track_buffer; no fps). Phase 2 solved the identical seconds→ticks problem with `ttl_ticks_from_seconds(ttl_seconds, fps)` taking `fps` as an **argument**, not from config. **Recommendation:** mirror exactly — add `decision/clocks.py::ticks_from_seconds(seconds, fps) -> int` (`math.ceil`, ≥1 for any positive seconds) and inject `fps` into the `DecisionEngine` constructor (the orchestrator/test supplies it, default e.g. 30.0). Do **not** add `fps` to `Thresholds` in Phase 3 unless the planner deliberately chooses to (it would be a config schema change touching Phase-1 contracts; the inject-as-arg path is the established convention and keeps Phase 3 config-change-free).

### Pattern 3: Fixed-priority trigger evaluation order (determinism + correctness)

**What:** Per tick, evaluate triggers in a **fixed, documented order**, highest-authority first:
1. **Override commands** (force/release) — operator intent dominates.
2. **Feed-death emergency** — a dead live feed must never stay on air (DEC-06 + D-01); this can fire even while in OVERRIDE (D-03: forced-but-dead → SAFE/best-live, override mode retained).
3. **Hold** — if a hold is active, suppress the normal auto-switch (DEC-03/04). (Hold does NOT suppress feed-death emergency — death wins over hold; see Pitfall "hold over a dying feed".)
4. **Normal auto-switch** — only if no higher-priority transition changed the target this tick.

**When to use:** Always. Determinism (DEC-07) requires that two triggers that could both fire resolve in a defined order; this priority list is that definition. Document it in code and in the test suite.

### Anti-Patterns to Avoid
- **Writing `model.target = cam` outside a transition callback.** Breaks DEC-01. The tick-loop computes the *candidate* but never assigns the *target* — only a guarded transition's callback assigns it.
- **One FSM state per camera.** O(N²) edges, hardcodes camera count, scatters guards. Use mode-states + a cam-id attribute.
- **Measuring dwell/cooldown/holds in seconds or wall-clock.** Destroys determinism. Everything is integer ticks; convert seconds→ticks once at construction.
- **Letting a hold suppress the feed-death emergency cut.** A dead feed held on air is the catastrophic failure DEC-06 exists to prevent. Death > hold.
- **Re-deriving feed liveness inside the FSM.** Phase 3 *consumes* `alive`; it must not look at NDI or last-frame timestamps (that's RBT-01, Phase 5).
- **A hold with no max-cap.** A stuck `action_hold` would freeze the show forever — every hold needs a tick cap (mandatory guardrail).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State + guarded-transition dispatch | A custom `if state == ... and guard_a and guard_b` switch | `transitions.Machine` with `conditions`/`unless` | Brief-locked; also the library guarantees "guard fails → no-op", which is the DEC-01 invariant. A hand-rolled switch invites direct target mutation (the exact DEC-01 violation). |
| "All conditions must pass else no transition" logic | Manual boolean chaining + manual rollback | `conditions=[...]` / `unless=[...]` on the transition dict | Context7-verified: ALL `conditions` must be True and ALL `unless` False; a failed guard leaves state unchanged with no side effects. |
| Seconds→ticks conversion | Inline `int(s * fps)` scattered across guards | One `ticks_from_seconds(s, fps)` helper (mirrors `ttl_ticks_from_seconds`) | Single source of rounding truth (`math.ceil`, ≥1); matches the shipped Phase-2 helper signature. |
| Deterministic test streams | New ad-hoc score/feed generators | The shipped `score_stream` (`SCENARIOS`) + `feed_death` | DEC-07 *names these exact substrates*; they are already frozen-dataclass, injected-RNG, tick-deterministic. |

**Key insight:** The single most valuable property of using `transitions` here is *negative*: it makes "change the live camera without passing a guard" structurally awkward, so DEC-01 falls out of the design instead of relying on developer discipline.

## Runtime State Inventory

> Phase 3 is **greenfield pure logic** (a new `segugio.decision` package), not a rename/refactor/migration. This section is included only to record that the standard rename inventory categories were considered and found N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — the FSM is stateless across runs; all state is in-memory per tick. | none |
| Live service config | None — no external service touched in Phase 3 (OBS/NDI are Phase 5). | none |
| OS-registered state | None — no daemons, tasks, or services registered. | none |
| Secrets/env vars | None — no secrets or env vars consumed. | none |
| Build artifacts | One **expected, intentional** change: `pyproject.toml` dependency reclassification (move `transitions` from `[heavy]` to runtime `dependencies`) → after the edit, run `.venv/bin/pip install -e .` (or `pip install transitions==0.9.3`) so the new light-dep is present. This is a build/install action, not stale-artifact cleanup. | `pip install transitions==0.9.3` into `.venv` |

**Nothing found in categories Stored data / Live service config / OS-registered state / Secrets:** verified by inspection — Phase 3 imports only `transitions` + stdlib + the existing pure `segugio.config`/`segugio.framing`/`segugio.synth` surfaces.

## Common Pitfalls

### Pitfall 1: `transitions` is currently classified `heavy` and is NOT installed — the lazy-import boundary will reject `segugio.decision` if imported eagerly
**What goes wrong:** The brief assumes `transitions` is "on the LIGHT/eager-import side." It is **not**: in `pyproject.toml` it sits in `[project.optional-dependencies].heavy` alongside `ultralytics`/`cyndilib`/`obsws-python`, and `.venv/bin/python -c "import transitions"` raises `ModuleNotFoundError` (verified). If `segugio.decision` imports `transitions` at module top level (which it must — the FSM is pure logic that should import CPU-only), and the import-boundary test still treats it as heavy, you get a contradiction: either the FSM can't import in the pure environment, or the heavy-absent test fails.
**Why it happens:** `transitions` was bucketed with the genuinely heavy GPU/NDI deps during Phase 1, before any FSM code existed. But `transitions` is pure-Python with **no native/GPU/C-extension dependency** (verified: sdist builds metadata with no compiler), so it belongs with `pydantic`/`numpy`/`loguru` on the light side.
**How to avoid:** In Phase 3, **move `transitions==0.9.3` from `[heavy]` to the light runtime `dependencies`** in `pyproject.toml`, install it into `.venv`, add `"segugio.decision"` to the `PHASE1_SURFACE` list in `tests/test_imports.py`, and **leave `transitions` OUT of `HEAVY_MODULES`** (it is now a legitimate light runtime dep, importable with torch/ultralytics/cyndilib/obsws absent). Verify `import segugio.decision` succeeds under the heavy-absent monkeypatch.
**Warning signs:** `ModuleNotFoundError: No module named 'transitions'` when running the Phase-3 tests; or `test_phase1_surface_imports_with_heavy_deps_absent` failing on `segugio.decision`.

### Pitfall 2: `ScoreSample` (from `score_stream`) carries NO status — feeding it raw to a FSM that expects `CameraScore.status` will break
**What goes wrong:** DEC-07 says drive the FSM from `score_stream`'s `SCENARIOS`. But `ScoreSample(tick, cam_id, score)` has **no `status` field**, whereas the production input is `CameraScore(tick, cam_id, score, status∈{tracking,coasting,lost})` (verified against shipped `signals.py`). A test that passes `ScoreSample` where `CameraScore` is expected will `AttributeError` on `.status`, or — worse — the FSM ignores status entirely and the production contract drifts from what's tested.
**Why it happens:** `score_stream` was built (Phase 1) to test the *scorer*'s downstream, emitting final scores only; the FSM input contract gained `status` in Phase 2.
**How to avoid (recommendation):** The FSM's public input contract is `list[CameraScore]`. In the DEC-07 test substrate, **wrap each `ScoreSample` as a `CameraScore` with a default status** — use `status=ScorerStatus.tracking` for a present (non-zero) sample and `status=ScorerStatus.lost` for a zero/absent sample (matching how the scorer would have labeled a dropout). A 3-line adapter (`_as_camera_scores(samples) -> list[CameraScore]`) keeps the FSM consuming the real production type while reusing the shipped scenarios. **Decision for the planner:** does the FSM's switching logic *read* `status` at all, or only `score`? Recommendation: the FSM keys its hysteresis/debounce on **`score`** (the smoothed value already encodes coast/TTL — a coasting camera holds its score, a lost one is at 0), and treats `status` as **advisory/logging only** in v1 (e.g., surfaced in `Decision.reason` for debug). This keeps the FSM simple and avoids double-counting coast logic the scorer already did. (Flag `A1` in Assumptions Log.)

### Pitfall 3: The "zero spurious cuts" assertion is the headline test and is easy to get subtly wrong
**What goes wrong:** DEC-02's defining property is that replaying `ping_pong` and `tie` produces **near-zero cuts**, not "the right camera each tick." A test that asserts "live == argmax(score)" every tick will *pass on a broken flicker-prone FSM* and *fail on a correct hysteretic one* (the correct FSM deliberately lags the argmax). The real assertion is **count the emitted transitions and assert it stays at or below a small bound** (ideally the FSM holds the incumbent through the whole ping_pong/tie run → 0 or 1 cuts after the initial acquisition).
**Why it happens:** "Pick the best camera" intuition leads to per-tick argmax assertions; the whole point of the FSM is to *not* chase the per-tick argmax.
**How to avoid:** Emit decisions with **event-on-change** semantics (or post-process the per-tick decision list into a transition list) and assert `num_transitions(ping_pong) <= 1` after warm-up, `num_transitions(tie) <= 1`. The `ping_pong` base curve flips the leader ~4× across the run (verified in `score_stream._scenario_base`), so a flicker-prone FSM would cut ~4–8×; a correct one with `hysteresis_margin=0.1` + `debounce_N=3` + `min_dwell` should not chase the 0.85↔0.35 swing at all once it has settled (the swing magnitude 0.5 > margin 0.1, so tune the *scenario noise* and margins jointly — the cut count is the assertion, exact value tuned in Phase 4). Make this the primary regression metric.

### Pitfall 4: Cooldown vs min_dwell double-counting, and the emergency cut bypassing both
**What goes wrong:** `min_dwell` (min time on a camera before you may leave it) and `cooldown` (min time after a cut before another cut) are easy to conflate, producing either too-sticky (can't switch when you should) or too-loose (double-cut) behavior. Separately, the feed-death emergency cut must **bypass both** (D-01) but the *newly-selected* camera must then get **normal** dwell/cooldown — getting the reset wrong either lets the emergency target be immediately abandoned or freezes it.
**Why it happens:** Two independent clocks gating one decision; the emergency path is an exception that resets them.
**How to avoid:** Model them as two separate integer clocks. `dwell_elapsed` resets to 0 on **every** target change (including emergency). `cooldown_remaining` is set to `cooldown_ticks` on **every normal/override/emergency** target change. The normal-switch guard requires `dwell_elapsed >= min_dwell_ticks AND cooldown_remaining == 0`. The emergency-cut guard ignores both (it fires on `live_feed_dead`), but its callback **resets both clocks** for the new target — so the emergency target is protected going forward (D-01 "newly-selected live camera then receives normal min_dwell/cooldown"). Unit-test: feed-death at tick T cuts immediately (dwell/cooldown ignored), then a competing higher score at T+1 does NOT steal it (new dwell active).

### Pitfall 5: Override + feed-death interaction (D-03) is the subtle one
**What goes wrong:** Override must *persist through* the forced camera's feed-death: while forced-but-dead, show SAFE/best-live, but **stay in OVERRIDE mode** and snap back to the forced camera the instant it recovers (D-03). A naive implementation either (a) drops out of override on death (wrong — operator never released), or (b) airs the dead forced feed (catastrophic, violates DEC-06).
**Why it happens:** Override "target" and override "mode" are conflated. The forced *camera id* is sticky (operator's choice), but the *aired target* must follow liveness.
**How to avoid:** Keep two attributes: `override_cam` (the operator's forced id, cleared only on explicit release) and `target` (what's actually aired). In OVERRIDE mode each tick: if `alive[override_cam]` → `target = override_cam`; else → `target = best_eligible or SAFE` (the same emergency-fallback selection as D-01) **without leaving OVERRIDE**. On `release`, begin auto-resume qualification (D-06). Unit-test the exact sequence: force cam_X → cam_X dies (target→SAFE/best-live, mode stays OVERRIDE) → cam_X recovers (target snaps to cam_X) → release (auto-resume only after a candidate wins full hysteresis+min_dwell).

### Pitfall 6: Auto-resume that snaps to a flickery pick (D-06)
**What goes wrong:** On override release, jumping straight to the current argmax can land on a camera that's only momentarily ahead — re-introducing the flicker the FSM exists to prevent.
**Why it happens:** "Resume = go back to auto" is read as "go to best camera now."
**How to avoid:** On `release`, do NOT immediately set a target from argmax. Re-enter AUTO mode but require the normal-switch guard to fully qualify the candidate (challenger cleared hysteresis + sustained `debounce_N` + `min_dwell` since it became live-candidate). Until a candidate qualifies, hold the last aired target (or SAFE if none is eligible). This is literally "reuse the normal auto-switch transition after release" — no special-case resume logic, which is the cleanest design.

## Code Examples

Verified patterns from official sources:

### Guarded transition that is a silent no-op when the guard fails (DEC-01 mechanism)
```python
# Source: Context7 /pytransitions/transitions — "Implement Conditional Transitions"
from transitions import Machine

class Engine:
    def __init__(self):
        self.target = None
        self.challenger_streak = 0
    def challenger_qualified(self):          # a `conditions` predicate (pure read)
        return self.challenger_streak >= 3   # debounce_N
    def _promote(self):                      # the ONLY place target changes on a cut
        self.target = self._challenger_id

m = Machine(model=Engine_instance, states=["safe","auto","override"], initial="safe",
            transitions=[{"trigger":"auto_switch","source":["auto","safe"],"dest":"auto",
                          "conditions":["challenger_qualified"],"before":"_promote"}])
Engine_instance.auto_switch()   # → no-op if challenger_streak < 3; target unchanged (DEC-01)
```

### prepare/conditions/before ordering (clocks read AFTER prepare, target set in before)
```python
# Source: Context7 /pytransitions/transitions — callback execution order
# machine.prepare_event → transition.prepare → transition.conditions
#   → before_state_change → state.on_exit → state.on_enter
#   → transition.after → after_state_change
# => put pure guard reads in `conditions`; mutate target in `before` (runs only if conditions pass).
```

### Frozen decision output (mirrors CameraScore/ScoreSample convention)
```python
# Pattern from shipped src/segugio/framing/signals.py (frozen, ==-comparable, str-Enum)
from dataclasses import dataclass
from enum import Enum

class Mode(str, Enum):
    safe = "safe"; auto = "auto"; override = "override"

@dataclass(frozen=True)
class Decision:
    tick: int
    target: str          # a camera id, or the SAFE sentinel (e.g. "SAFE")
    mode: Mode
    reason: str          # "auto_switch" | "feed_emergency" | "hold" | "override" | "none"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FSM logic in `if/elif` ladders | Declarative `transitions` machine with `conditions`/`unless` | n/a (project choice, locked) | Guard-failure-is-no-op gives DEC-01 for free |
| `transitions` v0.8.x `@machine.add_transition` style | v0.9.x dict-based `transitions=[...]` + `prepare`/`conditions`/`before`/`after` | 0.9.x (current 0.9.3) | Use the dict/list form shown above; `prepare` callback (run before conditions) is available |

**Deprecated/outdated:** none relevant — `transitions` 0.9.3 is the current release; the dict-based transition + callback API used here is the documented, current idiom.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The FSM keys switching on `CameraScore.score` only and treats `status` as advisory/logging (not a guard input) in v1 | Pitfall 2 | LOW — if status should gate switching (e.g., never challenge with a `coasting` camera), add a `unless=[challenger_is_coasting]` guard; localized change. Worth a one-line confirm with the planner/user. |
| A2 | `fps` is injected as a constructor/method argument (not added to `Thresholds` config) for the seconds→ticks bridge | Pattern 2 | LOW — matches the shipped `ttl_ticks_from_seconds(seconds, fps)` precedent; if the user wants `fps` in config it's a Phase-1 schema change to weigh deliberately. |
| A3 | Two typed hold inputs (`action_hold` while-set + max-cap; `occlusion_hold` bounded by `hold_length_s` + max-cap) is cleaner than one generic `hold` | Hold Inputs | LOW — CONTEXT marks this planner's discretion and *leans* two-typed; the guardrails (bound + max-cap) are mandatory regardless of shape. |
| A4 | SAFE is modeled as an FSM **state** with a SAFE-target sentinel string (e.g. `"SAFE"`) emitted as `Decision.target`, rather than as a pseudo-camera id pulled from `Camera.is_safe` | State Topology | LOW-MEDIUM — CONTEXT allows either. If the planner prefers the SAFE *camera id* (the `is_safe` camera) as the emitted target, that's a trivial swap; but a distinct `"SAFE"` sentinel cleanly separates "deliberately safe" from "happened to pick the wide cam" (matches ARCHITECTURE.md's "SAFE is first-class, not just the wide camera"). |
| A5 | `override` is modeled as a third FSM **mode-state** (not just a model flag) | Override + Auto-Resume | LOW — both work; a state makes the "force bypasses dwell/cooldown" and "release → resume-qualify" edges explicit and testable, and keeps the priority ordering visible in the transition table. |

**Note:** All numeric thresholds (`hysteresis_margin=0.1`, `min_dwell=2.0`, `debounce_N=3`, `cooldown=1.0`, `hold_length_s` 2.5/1.5) are **config seeds**, already shipped and validated — they are NOT assumptions; calibration is explicitly Phase 4. The assumptions above are *design-shape* choices CONTEXT delegated to the planner, each low-risk and locally reversible.

## Open Questions (RESOLVED)

1. **(RESOLVED — A1)** **Does any FSM guard need to read `CameraScore.status`, or is `score` sufficient?**
   - What we know: the scorer already folds coast/TTL into `score` (a coasting camera holds its score; a lost camera is at 0). So `score` alone encodes "is this camera currently a viable target."
   - What's unclear: whether the user wants an explicit rule like "a `coasting` camera may remain live but may NOT become a new challenger" (intuitive — don't cut *to* a camera that's mid-blur).
   - Recommendation: default to `score`-only switching (A1); add a `challenger must be tracking` guard only if a clip-review in Phase 4 shows cuts landing on coasting cameras. Confirm the default with the planner.

2. **(RESOLVED — A3)** **Hold input shape: confirm two-typed vs one generic.**
   - What we know: CONTEXT leans two-typed; guardrails (occlusion bounded by `hold_length_s`, every hold max-capped) are mandatory either way.
   - What's unclear: whether action and occlusion ever need to be *distinguished* downstream (e.g., different max-caps). They do: occlusion's natural bound is `hold_length_s` (discipline-specific), action's is a separate safety cap.
   - Recommendation: two typed inputs with independent caps (A3). This is the planner's locked-in default unless the user objects.

3. **(RESOLVED — A4)** **What exactly is the SAFE emitted target?**
   - Recommendation: a distinct `"SAFE"` sentinel string (A4), with the orchestrator (Phase 5) mapping it to the `SAFE` OBS scene. If the user prefers the `is_safe` camera id, note it's a one-line change.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `transitions` | The FSM itself | ✗ (in `[heavy]`, not installed) | target 0.9.3 | none — must install (pure-Python, trivial) |
| `pytest` / `pytest-cov` | DEC-07 test suite | ✓ | 9.0.3 / 7.1.0 | — |
| `numpy` | test substrate (`score_stream`/`feed_death`) | ✓ | 2.4.6 | — |
| `pydantic` | `segugio.config` (Thresholds, FramingDefaults read) | ✓ | 2.13.4 | — |
| `.venv/bin/pytest` | running tests | ✓ | — | `.venv/bin/python -m pytest` |

**Missing dependencies with no fallback:**
- `transitions==0.9.3` — **must be installed** before Phase-3 code runs. This is the one required setup action (Wave 0): move it to light `dependencies` in `pyproject.toml` and `pip install transitions==0.9.3` into `.venv`.

**Missing dependencies with fallback:** none.

## Validation Architecture

> `workflow.nyquist_validation` config not located as explicitly `false`; treated as enabled. This section seeds `03-VALIDATION.md`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (+ pytest-cov 7.1.0) — already in `.venv` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`) — already present |
| Quick run command | `.venv/bin/python -m pytest tests/test_decision_*.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ --cov=segugio.decision --cov-report=term-missing` |
| Estimated runtime | ~5s (pure CPU unit tests, no heavy deps) |

> Run via `.venv/bin/python -m pytest` — system `python3` does not see numpy.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEC-01 | The live target changes ONLY via a guarded transition; a failed guard is a silent no-op (assert target unchanged when guard predicate false) | unit | `.venv/bin/python -m pytest tests/test_decision_invariants.py::test_no_decision_outside_guard -x` | ❌ Wave 0 |
| DEC-02 | Replay `ping_pong` → transition count ≤ 1 after warm-up; replay `tie` → ≤ 1 (zero-spurious-cut) | unit | `.venv/bin/python -m pytest tests/test_decision_hysteresis.py::test_no_chase_pingpong -x` | ❌ Wave 0 |
| DEC-02 | Challenger must exceed incumbent by `hysteresis_margin` AND sustain `debounce_N` ticks before a cut; cut blocked while `dwell_elapsed < min_dwell` and during `cooldown` | unit | `.venv/bin/python -m pytest tests/test_decision_hysteresis.py::test_dwell_debounce_cooldown -x` | ❌ Wave 0 |
| DEC-03 | While `action_hold` set, no auto-switch fires even if a challenger qualifies; max-cap forces release after the cap | unit | `.venv/bin/python -m pytest tests/test_decision_holds.py::test_action_hold_suppresses_and_caps -x` | ❌ Wave 0 |
| DEC-04 | `occlusion_hold` suppresses switching, auto-expires after `hold_length_s`-derived ticks (disc 2.5 / agility 1.5), and is max-capped | unit | `.venv/bin/python -m pytest tests/test_decision_holds.py::test_occlusion_hold_bounded -x` | ❌ Wave 0 |
| DEC-05 | Near-tie inside dead-band → incumbent wins; no incumbent → first camera in config order | unit | `.venv/bin/python -m pytest tests/test_decision_tiebreak.py -x` | ❌ Wave 0 |
| DEC-06 | A camera with `alive=False` is NEVER emitted as target and NEVER counted as challenger; live-feed-death cuts to best-alive (or SAFE) bypassing dwell/cooldown | unit | `.venv/bin/python -m pytest tests/test_decision_feeddeath.py::test_dead_never_live_nor_challenger -x` | ❌ Wave 0 |
| DEC-07 | Same seed + same scenario → byte-identical `list[Decision]` (determinism); all four `SCENARIOS` + override + occlusion drive without error | unit | `.venv/bin/python -m pytest tests/test_decision_determinism.py -x` | ❌ Wave 0 |
| RBT-03 | force→ (cam dies → SAFE/best-live, mode stays OVERRIDE) → recovers (snaps back) → release → auto-resume only after full hysteresis+min_dwell | unit | `.venv/bin/python -m pytest tests/test_decision_override.py::test_force_death_recover_release_resume -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_decision_*.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ --cov=segugio.decision --cov-report=term-missing`
- **Phase gate:** Full suite green + high `segugio.decision` coverage (pure module → approach 100%) before `/gsd:verify-work`.

### Two hard safety invariants (assert explicitly, every scenario)
1. **Never emit a decision outside a guarded transition (DEC-01):** in every test, assert the target only ever changes on a tick where a named guard passed; expose the firing transition's name in `Decision.reason` and assert `reason != "none"` on exactly the ticks where `target` changed.
2. **Never air a dead feed (DEC-06):** in every scenario that includes `feed_death`, assert `alive[decision.target] is True OR decision.target == "SAFE"` for **all** ticks — including override scenarios (the forced-but-dead case).

### Wave 0 Gaps
- [ ] `src/segugio/decision/__init__.py`, `signals.py`, `engine.py`, `clocks.py` — the module under test
- [ ] `pyproject.toml` — move `transitions==0.9.3` to light `dependencies`; `pip install` into `.venv`
- [ ] `tests/test_imports.py` — add `"segugio.decision"` to `PHASE1_SURFACE` (and keep `transitions` out of `HEAVY_MODULES`)
- [ ] `tests/conftest.py` — add a `thresholds`/`decision_config` fixture (reuse `valid_config_dict`, `seeded_rng`); a `fps` constant; a `_as_camera_scores(samples, status_default)` adapter helper
- [ ] `tests/test_decision_invariants.py`, `test_decision_hysteresis.py`, `test_decision_holds.py`, `test_decision_tiebreak.py`, `test_decision_feeddeath.py`, `test_decision_override.py`, `test_decision_determinism.py`
- [ ] No framework install needed — pytest/pytest-cov already in `.venv`

## Security Domain

> `security_enforcement` not explicitly `false`; included for completeness. This is a pure, local, no-I/O, no-PII decision module — the security surface is effectively nil. (PITFALLS.md "Security Mistakes" reaches the same conclusion for the whole project: no domain-specific security axis.)

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in a pure FSM |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No external actors; override is an in-process input, gated by orchestrator in Phase 5 |
| V5 Input Validation | yes (light) | Inputs are typed (`CameraScore`, bool maps, enums). Fail-safe like the scorer: a NaN/inf or malformed score must degrade to "ineligible candidate" → at worst SAFE, never a crash (robustness constraint: "nessun crash ammesso"). Mirror the scorer's `_is_finite_detection` guard for scores. |
| V6 Cryptography | no | No crypto |

### Known Threat Patterns for {pure tick-driven FSM}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| NaN/inf or out-of-range score poisoning the selection (DoS-of-correctness) | Tampering / DoS | Treat non-finite/out-of-range scores as an ineligible candidate (never a challenger, never a target); clamp/guard before argmax — mirrors Phase-2 `T-2-01`. LOW severity. |
| Stuck/forgotten hold freezing the show indefinitely | Denial of Service (availability of the broadcast) | **Mandatory** per-hold tick max-cap (CONTEXT guardrail) — a hold can never persist past its cap regardless of the input signal. |
| Override left on, aired feed dies | Denial of Service | D-03 design: forced-but-dead → SAFE/best-live (never airs a dead feed) while retaining override; manual release is the only exit (v1). |

None of these meet a `high` block threshold; all are LOW and handled by the fail-safe/guardrail design above.

## Sources

### Primary (HIGH confidence)
- `/pytransitions/transitions` (Context7) — conditional transitions (`conditions`/`unless` semantics; failed guard = silent no-op), `prepare`/`before`/`after`/`conditions` callbacks, callback execution order.
- Shipped source (read directly, repo `/home/master/repos/segugio/src/segugio/`): `config/models.py` (`Thresholds`, `Camera.is_safe`, no `fps` field — verified), `config/discipline.py` (`FramingDefaults.hold_length_s` disc 2.5 / agility 1.5), `framing/signals.py` (`CameraScore`/`ScorerStatus`), `framing/scorer.py` (`ttl_ticks_from_seconds(seconds, fps)` precedent, `MultiCamScorer.update`), `synth/score_stream.py` (`ScoreSample` has NO status; `SCENARIOS`; ping_pong ~4 leader flips), `synth/feed_death.py` (`FeedEvent`/`feed_death`), `tests/conftest.py`, `tests/test_imports.py` (`PHASE1_SURFACE`/`HEAVY_MODULES` boundary), `pyproject.toml` (`transitions` in `[heavy]`, NOT light — verified).
- PyPI (`.venv/bin/pip index versions transitions`) — `transitions==0.9.3` is latest; sdist builds metadata with no native step.
- `.planning/research/{ARCHITECTURE,PITFALLS,SUMMARY,FEATURES}.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `03-CONTEXT.md`, Phase-2 `02-VALIDATION.md` (Nyquist format).

### Secondary (MEDIUM confidence)
- [github.com/pytransitions/transitions](https://github.com/pytransitions/transitions) (6.5k stars, actively maintained; 0.9.3 changelog) — library maturity, maintenance, release notes — verified via WebSearch.

### Tertiary (LOW confidence)
- None — every load-bearing claim is grounded in shipped source or Context7/PyPI.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `transitions` locked, verified on PyPI + Context7 + official repo; only the `[heavy]`→light reclassification is a (verified-necessary) action item.
- Architecture (topology, guards, clocks, holds, override): HIGH — derived directly from `transitions` semantics + shipped Phase-1/2 contracts; design-shape choices flagged in the Assumptions Log are low-risk and CONTEXT-delegated.
- Pitfalls: HIGH — each pitfall is grounded in a concrete shipped-source fact (transitions classified heavy; `ScoreSample` lacks status; emergency-cut clock reset; override/feed-death interaction).
- Numeric thresholds: intentionally NOT researched (config seeds; calibrated in Phase 4 per CONTEXT/SUMMARY).

**Research date:** 2026-06-09
**Valid until:** ~2026-07-09 (stable — `transitions` is a mature library; the Phase-1/2 contracts are shipped and frozen). Re-verify only if `transitions` major version or the Phase-1 config schema changes.
