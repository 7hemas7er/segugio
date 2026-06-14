# Phase 2: Framing Scorer (pure logic) - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 builds a **pure, I/O-free, deterministic per-camera framing scorer** (`segugio.framing`) that turns a stream of normalized detection signals (`cx, cy, w, h, conf, track_id`) into a single smoothed `[0,1]` per-camera score encoding the domain's hardest framing decisions. It imports nothing heavy (no torch/ultralytics/cv2 at module top-level) and consumes the **already-locked Phase-1 config contract** verbatim. Every formula is resolution-independent by construction (normalized inputs only). It is fully unit-tested on **synthetic detection sequences** before any detector is wired (Phase 4).

Delivers FRM-01..07 plus a cheap shadow/plausibility guard:
- Base score = centeredness + size target-band + per-camera normalized confidence (FRM-01)
- Per-camera EMA smoothing, `alpha` from config (FRM-02)
- Zone-gating: `score = base × framing_weights[role][zone]` (FRM-03)
- Lead-room: ideal target shifts toward motion direction (FRM-04)
- Coast/TTL on short dropout, then mark lost (FRM-05)
- Per-camera confidence normalization (FRM-06)
- Pure / no-I/O / unit-testable on synthetic sequences (FRM-07)
- A NEW `segugio.synth.detection_stream` generator (the test substrate — distinct from the existing `score_stream`, which emits *final* FSM scores, not raw detection signals)

**NOT in this phase:**
- No YOLO / tracker / detector wiring (Phase 4 maps a detection row → `DetectionSignal` unchanged).
- No FSM / switching logic (Phase 3 *consumes* the per-camera score).
- No long expected-occlusion hold for tunnels/contacts — that is the Phase-3 FSM's job (`FramingDefaults.hold_length_s` = disc 2.5 / agility 1.5). The scorer only handles the **short blur gap** (~0.3–0.7 s). This boundary is a hard scope line — do not double-implement coast.
- No SAFE-floor enforcement — the scorer exposes a clean base; the floor is applied by the FSM/consumer (`main_wide` stays neutral-weighted).

</domain>

<decisions>
## Implementation Decisions

All four forks below were discussed; **every one matched the research recommendation** (the formula *shapes* are HIGH-confidence; the numeric *constants* are `[ASSUMED]` tuning seeds, calibrated on the curated clip set in Phase 3/4 — none are hardcoded, all live in config).

### Framing priority (FRM-01 base-score weights)
- **D-01:** **Centeredness-dominant.** When two cameras both see the dog, *centeredness* decides the better shot; dog-size is a real but secondary preference; detection-confidence is only a **low-weight tiebreaker**. Default term weights `w_c=0.5, w_s=0.3, w_conf=0.2` (sum to 1), tuned later on clips. The low `w_conf` is deliberate — it prevents the "uniformly brighter camera wins on confidence alone" failure (works together with per-camera conf-normalization, FRM-06).

### Size preference (FRM-01 size term)
- **D-02:** **Gaussian single-ideal-size band** over `sqrt(area)` (apparent scale), NOT monotonic `w·h`. One ideal size with smooth falloff for both smaller and larger — fewer knobs, smoother gradient (helps EMA stability), and a genuinely distant small dog still scores meaningfully (σ_s kept wide). The size term must **peak** at the ideal and be non-monotonic (the explicit "bigger is not always better" guarantee). Trapezoid/plateau band deferred as the documented tunable alternative.

### Coast on blur (FRM-05)
- **D-03:** **Hold-last, then drop.** During a short detection gap (blur on a catch/jump apex — the worst moment to cut), freeze the EMA at its last value (status `coasting`) for a TTL window (~0.4 s seed, range 0.3–0.7 s), then set score to 0 and mark `lost` once TTL expires. Never feed `raw=0` into the EMA. Decay-toward-0 deferred as a tunable alternative.
- **D-04:** **Scorer/FSM coast boundary (locked scope line).** The scorer's TTL covers only the **short blur/miss** gap. The **longer expected-occlusion hold** (tunnels, contact equipment) is a Phase-3 FSM concern driven by `FramingDefaults.hold_length_s`. Phase 2 must not implement the long hold. On re-acquisition before TTL expiry, the EMA resumes from the held value (no cold-start re-seed); only a *new* track id after `lost` triggers a fresh cold-start.

### v1 scope (FRM-02 smoothing + FRM-04 lead-room)
- **D-05:** **Fixed α v1.** Ship a single fixed EMA `alpha` read from config (`Thresholds.alpha`, default 0.3), with a clean hook for a future upgrade. Cold-start seeds `s_0 = raw_0` (not 0).
- **D-06:** **Lead-room scales with speed, clamped.** The ideal centeredness target shifts **TOWARD** the motion direction (the proven sign — dog ends up behind center with empty space ahead). Magnitude ∝ clamped speed, using the per-discipline `FramingDefaults.lead_room` gain (disc 0.25 > agility 0.10); a resting dog (below a small velocity deadzone) gets no lead (center stays correct). Velocity is a finite difference over a short K-sample history of the locked track; track-id swap or short history → speed 0 until history rebuilds.
- **D-07:** **Defer motion-adaptive α** (α rises on fast motion, falls at rest) to a later milestone — it couples with lead-room and is best tuned after the fixed-α baseline is proven on real clips. α must be tuned **jointly** with the Phase-3 FSM `debounce_N` / `min_dwell` / `hysteresis_margin`; flag this cross-dependency to the Phase-3 planner (a smoother α permits a shorter debounce, a snappier α needs a longer one).

### Claude's Discretion (implementation details — planner/executor decide)
- **Config nesting for new scorer params** — add an additive pydantic `ScorerParams` sub-model to the validated `Config` (research suggests a top-level `scoring:` block), keeping per-discipline knobs (`lead_room`, possibly `ideal_size`) under `FramingDefaults`. Principle locked (all params in validated config, fail-fast, none hardcoded); exact nesting is the planner's call. New params: `sigma_c, ideal_size, sigma_s, w_c/w_s/w_conf, lead_max, v_deadzone, ttl_seconds, beta, z_clip, warmup, conf_floor, min_area, aspect_lo/hi, out_of_bounds_factor`.
- **TTL plumbing** — scorer takes `fps` (or precomputed `ttl_ticks`) at construction to convert `ttl_seconds → ticks` while staying clock-free. Whether config stores `ttl_seconds`+fps or `ttl_ticks` directly is the planner's call.
- **Centeredness falloff** — Gaussian recommended over linear `1 - dist/maxdist` (smoother near ideal, less flicker); keep linear as a documented fallback.
- **Conf-normalization method** — streaming EMA z-score (O(1) state, clipped to ±z_clip, passthrough during ~10-sample warmup) recommended over min-max / rank / Welford-window. β slower than the score α so the baseline tracks the camera's lighting regime, not the instantaneous detection.
- **Zone-overlap rule** — highest-`framing_weights` match recommended over first-match (example configs are non-overlapping today so they coincide); keep first-match as an optional config flag. Outside all zones → multiply by a small `out_of_bounds_factor` (~0.15), NOT 0.
- **Shadow/plausibility guard** — cheap pure per-detection gate (conf floor, min-area, aspect-ratio sanity); a rejected detection is treated as "no detection" (→ coast). The rigid-shadow case (a ghost box moving with the real dog) needs cross-detection comparison and is deferred to Phase-4 subject-selection.
- **Module shape** — stateful per-camera `CameraScorer` object composing pure free functions, plus a `MultiCamScorer` fan-out; frozen `DetectionSignal` (input) / `CameraScore` (output) dataclasses matching the Phase-1 frozen-dataclass + injected-RNG/tick determinism convention.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-2 research (primary — read first)
- `.planning/phases/02-framing-scorer-pure-logic/02-RESEARCH.md` — the load-bearing doc: all 8 architecture patterns, the proven lead-room sign, formula skeletons (centeredness/size-band/EMA/lead-room/coast/conf-norm/zone-gate/plausibility), the `DetectionSignal`/`CameraScore` contracts, the recommended `src/segugio/framing/` layout, the FRM→test map and assertion patterns, and the Assumptions Log (every `[ASSUMED]` tuning seed + risk).

### Project decisions & scope
- `.planning/PROJECT.md` — constraints, key decisions (resolution-independent/normalized-only, competitor-lock + zone-gating first-class, two-budget latency, `main_wide` neutral SAFE).
- `.planning/REQUIREMENTS.md` — FRM-01..07 (this phase) + TRK-03 (the Phase-4 signal set the `DetectionSignal` contract must match).

### Domain research (the WHY behind each scorer term)
- `.planning/research/ARCHITECTURE.md` §Part 3 — the zone lookup + multiply = the entire FRM-03 mechanism; normalized per-camera zones (Option A); `main_wide` neutral/floored anti-pattern.
- `.planning/research/PITFALLS.md` — Pitfalls 1, 3, 4, 8, 9, 10 = the exact failure modes each FRM term counters ("hard-gate to 0 is never acceptable", "weight centeredness above size", lead-room sign, brightness bias).
- `.planning/research/SUMMARY.md` — α tuned **jointly** with Phase-3 debounce/dwell; coast/TTL 0.3–0.7 s; competitor-lock + zone-gating as first-class features.
- `.planning/research/FEATURES.md` — per-discipline overlay sets (informs the `lead_room` / discipline-knob semantics).
- `.planning/research/STACK.md` — concrete model/tracker context (Phase-4-facing; confirms `DetectionSignal` matches the YOLO+BoT-SORT output row).

### Phase-1 contract the scorer consumes verbatim (read directly)
- `src/segugio/config/models.py` — `Role`, `Zone`, `Camera`, `Thresholds.alpha`, `Config.framing_weights[Role][zone]`, the zone→weight cross-validator (guarantees every referenced zone has a weight).
- `src/segugio/config/discipline.py` — `FramingDefaults.lead_room` (disc 0.25 / agility 0.10) + `hold_length_s` (disc 2.5 / agility 1.5; **Phase-3 FSM** field, not scorer TTL).
- `src/segugio/synth/score_stream.py`, `src/segugio/synth/feed_death.py` — the frozen-dataclass + injected-`Generator` determinism contract to mirror; confirms `score_stream` emits *final* scores (NOT detection signals) → a new `detection_stream` is required.
- `tests/conftest.py` — reusable `seeded_rng` / `valid_config_dict` fixtures.
- `config.example.yaml`, `config.agility.example.yaml` — the `framing_weights` matrix the scorer multiplies by (used directly in zone-multiplier tests).

### Prior phase
- `.planning/phases/01-foundation-config-curated-clip-set/01-CONTEXT.md` — locked Phase-1 decisions (config schema, lazy-import boundary, determinism convention).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`segugio.config` (Phase 1):** the typed, validated `Config` — `framing_weights[Role][zone]`, `Thresholds.alpha`, `FramingDefaults.lead_room`/`hold_length_s`, normalized `Zone.rect`. The scorer *reads* it; new `ScorerParams` extend it additively (no breaking change).
- **`segugio.synth` (Phase 1):** `score_stream` / `feed_death` establish the frozen-dataclass + injected-`numpy.random.Generator` + injected-tick determinism pattern. Phase 2 adds `detection_stream` alongside them and re-exports from `synth/__init__.py`.
- **`tests/conftest.py`:** `seeded_rng` and `valid_config_dict` fixtures reused; add a `scorer_params` fixture (seeded defaults).
- **`pyproject.toml` pytest config:** `pythonpath=["src"]`, `testpaths=["tests"]` already present; src-layout editable install auto-discovers the new `segugio/framing/` package (no reinstall — verify with one `import segugio.framing`).

### Established Patterns
- **Lazy-import boundary (01-01 smoke test):** `segugio.framing` must import cleanly with torch/ultralytics/cyndilib **absent**. No heavy deps at module top-level. The pure scorer runs CPU-only.
- **Determinism convention:** frozen dataclasses for `==`-based assertions; zero randomness and zero wall-clock in the scorer (time = injected `tick`; randomness lives only in the synthetic generator via an injected `Generator`).
- **Run tests via `.venv/bin/python -m pytest`** — system `python3` does not see numpy.

### Integration Points
- **Input (Phase 4 → scorer):** a YOLO+BoT-SORT result row maps to a frozen `DetectionSignal(tick, cam_id, cx, cy, w, h, conf, track_id)` unchanged. `None` for a tick = no dog detected this camera → coast path.
- **Output (scorer → Phase 3 FSM):** a frozen `CameraScore(tick, cam_id, score, status)` where `status ∈ {tracking, coasting, lost}`; `score` is the smoothed `[0,1]` value the FSM consumes.

</code_context>

<specifics>
## Specific Ideas

- The three correctness points to spend test care on (research): (a) the **lead-room sign** (dog moving right → `ideal_x > 0.5`, and a dog behind the shifted ideal outscores the same dog dead-center), (b) every term **normalized and in `[0,1]`** (resolution-invariance: same normalized sequence at two "resolutions" → identical scores — there is no resolution variable in the scorer to break), (c) **never collapse to 0** on a miss (coast-then-lost timeline asserted explicitly).
- Fail-safe, not fail-loud, in the live loop: the scorer must **not throw** on data the config already validated — `np.clip` outputs to `[0,1]`, default a missing weight to neutral `1.0`, guard every divisor (`h>0`, `speed≥deadzone`, `sqrt(var+ε)`), treat NaN/inf as "no detection" (coast).

</specifics>

<deferred>
## Deferred Ideas

- **Motion-adaptive α** (α scales with velocity) — later milestone; couples with lead-room, tune after the fixed-α baseline is proven on the clip set. Expose a clean hook in v1.
- **Trapezoid/plateau size band** `(lo, ideal_lo, ideal_hi, hi)` — documented tunable alternative to the Gaussian size term.
- **Score-decay coast** (ramp toward 0 over the TTL) — documented tunable alternative to hold-last.
- **Rigid-shadow false-positive defense** (a ghost box that moves with the real dog) — needs cross-detection comparison → Phase-4 subject-selection / competitor-lock.
- **Long expected-occlusion hold** (tunnels/contacts, `hold_length_s`) — Phase-3 FSM, not the scorer.
- All numeric tuning constants (`σ_c, ideal_size, σ_s, w_c/w_s/w_conf, lead_max, v_deadzone, ttl_seconds, β, z_clip, warmup, conf_floor, min_area, aspect, out_of_bounds_factor`) — calibrated on the curated clip set in Phase 3/4; v1 ships sane seeds in config.

</deferred>

---

*Phase: 02-framing-scorer-pure-logic*
*Context gathered: 2026-06-09*
