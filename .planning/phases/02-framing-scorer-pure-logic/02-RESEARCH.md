# Phase 2: Framing Scorer (pure logic) - Research

**Researched:** 2026-06-09
**Domain:** Pure, I/O-free per-camera framing scorer — geometric/statistical scoring of normalized detection signals (centeredness, size target-band, confidence, EMA, zone-gating, lead-room, coast/TTL, per-camera confidence normalization)
**Confidence:** HIGH on the math (formulas are standard signal-processing / cinematography conventions, cross-verified); HIGH on the Phase-1 contract (read directly from source); MEDIUM on the specific tuning *values* (heuristic seeds, tuned later on the clip set — flagged throughout as `[ASSUMED]`).

> No CONTEXT.md exists for Phase 2 yet (this is a standalone `--research-phase` run that precedes discuss-phase). This research therefore proposes concrete formulas and parameterizations for the user to confirm during discuss-phase. Every numeric default is tagged `[ASSUMED]` in the Assumptions Log; the *shapes* of the formulas are HIGH-confidence, the *constants* are tuning seeds.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FRM-01 | Normalized, resolution-independent base score from centeredness + size target-band + confidence | `## Architecture Patterns → Pattern 1 (base score)`; `## Code Examples → base_score`. All terms are functions of normalized [0..1] bbox signals → resolution-independent by construction. |
| FRM-02 | Per-camera EMA smoothing, alpha from config (`Thresholds.alpha`) | `## Architecture Patterns → Pattern 2 (EMA)`; `## Code Examples → CameraScorer.update`. Standard `s_t = α·raw + (1-α)·s_{t-1}`; cold-start + no-detection handling specified. |
| FRM-03 | Zone-gating: `score = base × framing_weights[role][zone]` | `## Architecture Patterns → Pattern 3 (zone lookup + multiply)`; consumes `Config.framing_weights[Role][zone]` + `Camera.zones` verbatim (ARCHITECTURE.md Part 3). Out-of-all-zones gate-down factor specified. |
| FRM-04 | Lead-room: ideal target shifts toward motion direction | `## Architecture Patterns → Pattern 4 (lead-room)`; sign convention proven; velocity from finite-difference of track history, clamped magnitude. Uses `FramingDefaults.lead_room` as the gain. |
| FRM-05 | Coast/TTL on dropout, then mark lost | `## Architecture Patterns → Pattern 5 (coast/TTL)`; hold-vs-decay recommendation; TTL in ticks derived from fps + config seconds; EMA interaction specified. |
| FRM-06 | Per-camera confidence normalization (brighter camera must not win on conf alone) | `## Architecture Patterns → Pattern 6 (streaming z-score)`; EMA-mean/variance streaming normalizer with clipping; recommended over min-max/rank with rationale. |
| FRM-07 | Pure, no I/O, fully unit-testable on synthetic sequences | `## Architecture Patterns → Pattern 7 (module shape)`; per-camera stateful object + pure free functions; injected synthetic detection sequence contract; `## Validation Architecture`. |
| (guard) | Shadow false-positive guard (Plan 02-03 / PITFALLS Pitfall 10) | `## Architecture Patterns → Pattern 8 (plausibility/shadow guard)`; cheap pure signals (aspect-ratio sanity, min-size gate, confidence floor). |
</phase_requirements>

## Summary

Phase 2 builds a **pure, deterministic, numpy-only** per-camera framing scorer that turns a stream of per-detection signals (normalized `cx, cy, w, h, conf, track_id`) into a single smoothed `[0,1]` per-camera score encoding the domain's hardest framing decisions. It imports nothing heavy (no torch/ultralytics/cv2 at module top-level) and consumes the **already-locked Phase-1 config contract** (`segugio.config.Config`, `Role`, `framing_weights[Role][zone]`, `Thresholds.alpha`, `FramingDefaults.lead_room`, normalized `Zone.rect`). Because every input is normalized, every formula is resolution-independent by construction — the single most important invariant to assert in tests.

The math decomposes into seven small, independently-testable pieces. The **base score** is a weighted sum of three terms each in `[0,1]`: a **Gaussian centeredness** falloff against an ideal point (more stable than a linear `1 - dist/maxdist`), a **Gaussian size target-band** over `sqrt(area)` (peaks at an ideal size, penalizes both too-small and too-big — the explicit fix for "bigger is not always better"), and a **normalized confidence** term. **EMA** (`s_t = α·raw + (1-α)·s_{t-1}`) smooths per camera with `α` from `Thresholds.alpha`; α must be tuned *jointly* with the Phase-3 FSM debounce/dwell (SUMMARY: alpha tuned with debounce/dwell). **Zone-gating** is a pure point-in-rect lookup → multiply by `framing_weights[role][zone]`, with a gate-down factor when the dog is outside all field bounds. **Lead-room** shifts the ideal centeredness target *toward* the motion direction (sign proof below) so the dog sits behind center with room ahead, magnitude ∝ clamped speed. **Coast/TTL** holds the last score (recommended over decay) through a short detection gap so the director never cuts away from the climax, then marks the subject lost after TTL. **Per-camera confidence normalization** is a streaming EMA-based z-score (with clipping) so a uniformly brighter camera does not win on raw confidence.

**Primary recommendation:** Implement a stateful per-camera `CameraScorer` object (holding EMA value, a small track-history ring buffer for velocity, a TTL counter, and a streaming conf-normalizer) plus a set of pure free functions (`centeredness`, `size_score`, `zone_lookup`, `lead_room_target`, …) that the object composes. Define a frozen `DetectionSignal` dataclass as the per-detection input contract so Phase-4 YOLO output can feed it unchanged. Add a **new synthetic detection-sequence generator** to `segugio.synth` (the existing `score_stream` emits *final* FSM scores, not raw detection signals — see Open Question 1). Score every formula in `[0,1]`, keep all tuning constants in config, and assert resolution-invariance, size-band peak, zone-multiplier, lead-room sign, coast-then-lost, and conf-norm anti-bias on seeded synthetic sequences.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Base score composition (FRM-01) | Pure-logic scorer (`segugio.framing`) | Config layer (weights/params) | Stateless math on normalized signals; no I/O. Owns the centeredness/size/conf math. |
| EMA smoothing (FRM-02) | Pure-logic scorer (per-camera state) | Config (`Thresholds.alpha`) | A scalar recurrence held in per-camera state; deterministic given the input stream. |
| Zone-gating (FRM-03) | Pure-logic scorer (lookup+multiply) | Config (`framing_weights`, `Camera.zones`) | Pure config-driven lookup; the entire sport→scorer coupling (ARCHITECTURE.md). |
| Lead-room target shift (FRM-04) | Pure-logic scorer (velocity from state) | Config (`FramingDefaults.lead_room`) | Velocity is a finite-difference of recent normalized centers held in per-camera history; pure. |
| Coast/TTL (FRM-05) | Pure-logic scorer (per-camera TTL counter) | Config (TTL seconds + fps) | A countdown over synthetic ticks; no wall-clock. The FSM (Phase 3) *consumes* the coasted score; the scorer *produces* it. |
| Per-camera conf normalization (FRM-06) | Pure-logic scorer (per-camera streaming stats) | — | Small streaming per-camera state (EMA mean/var); pure and deterministic. |
| Shadow-FP guard | Pure-logic scorer (per-detection gate) | Config (min-size/aspect/conf floor) | A cheap pre-score plausibility gate on a single detection; pure. |
| Synthetic detection-sequence generator | Test-support library (`segugio.synth`) | Phase-2 tests (consumers) | A NEW deterministic generator emitting raw per-detection signals (distinct from the existing final-score `score_stream`). |

## User Constraints (no CONTEXT.md yet — derived from locked project decisions)

These are not from a Phase-2 CONTEXT.md (none exists). They are the binding constraints the scorer inherits from STATE.md decisions, PROJECT.md, and the Phase-1 contract. The planner should treat them as locked; discuss-phase may refine the *values*.

- **Pure, no I/O (FRM-07, PROJECT/STATE):** the scorer imports nothing heavy and reads no files, clock, or network. Built and unit-tested in isolation on synthetic streams *before* YOLO is wired (Phase 4). The 01-01 import-smoke test boundary must remain green.
- **Resolution-independent (FRM-01):** all inputs normalized `[0..1]`; no pixel coordinates anywhere. Mirrors ARCHITECTURE.md Anti-Pattern 1 ("never define anything in pixels").
- **Consume the Phase-1 config verbatim:** `framing_weights[Role][zone]`, `Camera.zones` (normalized rects), `Thresholds.alpha`, `FramingDefaults.lead_room`. Do **not** redesign the config; *new* scorer params (size band, TTL, conf-norm window, gate-down factor, lead clamp) are additive config — see Open Question 3.
- **All tuning constants in config, never hardcoded (SUMMARY Gaps):** weights, alpha, size band, lead clamp, TTL windows are heuristics tuned on the clip set later; the scorer hardcodes none of them.
- **`main_wide` stays a neutral, floored SAFE net (ARCHITECTURE Anti-Pattern 3):** the scorer must not let weighting drive the wide below the SAFE floor; the floor itself is applied by the consumer/FSM, but the scorer must expose a clean base so the floor is meaningful.
- **Disc/agility parity:** the scorer is sport-agnostic; the only sport difference is the `framing_weights` table and `FramingDefaults` (data, not code). No `if sport == ...` branches.

## Standard Stack

### Core
| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| `numpy` | 2.4.6 `[VERIFIED: pip index versions, project .venv]` | Vector math for centeredness/size/velocity; the only numeric dep | Already a locked, installed dep; the determinism backbone. The scorer math is small-vector arithmetic — numpy is sufficient and idiomatic. |
| `dataclasses` (stdlib) | — | Frozen `DetectionSignal` / `CameraScore` input/output contracts | Matches the Phase-1 `ScoreSample`/`FeedEvent` pattern (frozen dataclasses for deterministic `==`). Zero new deps. |
| `pydantic` (via `segugio.config`) | 2.13.4 `[VERIFIED: project .venv]` | Reads the typed `Config` (weights, alpha, lead_room, new scorer params) | Already locked. The scorer *reads* a `Config`; it does not validate one. New scorer params are added to the existing pydantic models (Open Question 3). |

### Supporting
| Library | Version (verified) | Purpose | When to Use |
|---------|--------------------|---------|-------------|
| `pytest` | 9.0.3 `[VERIFIED: project .venv]` | Test runner for all FRM unit tests | Dev dep; the framework the Validation Architecture targets. |
| `pytest-cov` | 7.1.0 `[VERIFIED: project .venv]` | Coverage of the pure scorer module | Optional; the scorer is pure → should hit very high coverage easily. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| numpy scalar/small-array math | Pure Python `math` only | Viable (the per-camera math is a handful of scalars), but numpy is already a dep, gives clean vectorized centeredness/velocity, and matches the synth generators. Use numpy. |
| Stateful `CameraScorer` object | Fully pure functions threading an immutable state dict | Pure-functional is testable but verbose (every call returns `(score, new_state)`). A small stateful object with a deterministic `update()` is equally testable (same input stream → same output) and far more ergonomic. Recommend the object. |
| Gaussian centeredness | Linear `1 - dist/maxdist` | Linear is simpler but has a sharp gradient and a hard zero at the corner; Gaussian is smoother near the ideal and degrades gracefully — more stable under bbox jitter (see Pattern 1). Recommend Gaussian; keep linear as a documented fallback. |
| EMA z-score conf-norm | Welford sliding window / min-max / rank | Welford needs a bounded ring buffer (more state); min-max is outlier-fragile; rank loses magnitude. EMA z-score is O(1) state, streaming, and robust with clipping (Pattern 6). Recommend EMA z-score. |

**Installation:** No new packages. All deps (`numpy`, `pydantic`, `pytest`, `pytest-cov`) are already pinned and installed in the project `.venv` from Phase 1.

```bash
# Nothing to install — verify the existing venv:
.venv/bin/python -c "import numpy, pydantic, pytest; print(numpy.__version__, pydantic.__version__)"
# -> 2.4.6 2.13.4
```

**Version verification:** `numpy 2.4.6`, `pydantic 2.13.4`, `pytest 9.0.3` confirmed present in `/home/master/repos/segugio/.venv` on 2026-06-09 (Python 3.12.3). These are the exact pins Phase 1 locked.

## Package Legitimacy Audit

> Phase 2 installs **no new external packages**. It uses only already-installed, already-vetted Phase-1 deps. The Package Legitimacy Gate is therefore satisfied by the Phase-1 audit (01-RESEARCH.md `## Package Legitimacy Audit`): `numpy`, `pydantic`, `pytest`, `pytest-cov` are all mature, foundational, well-sourced packages.

| Package | Registry | Maturity | Source Repo | slopcheck | Disposition |
|---------|----------|----------|-------------|-----------|-------------|
| `numpy` | PyPI | foundational (20+ yrs) | github.com/numpy/numpy | unavailable → `[ASSUMED]` (locked dep, used in Phase 1) | Approved (already installed) |
| `pydantic` | PyPI | mature (v2 since 2023) | github.com/pydantic/pydantic | unavailable → `[ASSUMED]` (locked dep) | Approved (already installed) |
| `pytest` | PyPI | foundational | github.com/pytest-dev/pytest | unavailable → `[ASSUMED]` (dev dep) | Approved (already installed) |
| `pytest-cov` | PyPI | mature | github.com/pytest-dev/pytest-cov | unavailable → `[ASSUMED]` (dev dep) | Approved (already installed) |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none. No new installs in this phase; no `checkpoint:human-verify` needed.

## Architecture Patterns

### System Architecture Diagram

Data flow through the scorer (per camera, per tick). The scorer is the box; everything outside is Phase-1 (config, synth) or later phases (Phase-4 YOLO, Phase-3 FSM).

```
  Phase-1 Config (read once)                         Phase-4 YOLO (later)   /  Phase-2 synth generator (now)
   framing_weights[role][zone]                         per-detection signals normalized [0..1]
   Camera.zones (normalized rects)                     cx, cy, w, h, conf, track_id
   Thresholds.alpha                                            │
   FramingDefaults.lead_room                                   │  (DetectionSignal | None per camera per tick)
   + new: size_band, ttl_s, conf_norm, ...                     ▼
        │                              ┌───────────────────────────────────────────────────────────────┐
        │                              │  CameraScorer.update(det: DetectionSignal | None, tick) ──────► │
        ▼                              │                                                                 │
   (injected at construction)          │  ┌─ det present ────────────────────────────────────────────┐  │
        ─────────────────────────────► │  │ 0. shadow/plausibility gate (min-size, aspect, conf floor)│  │
                                        │  │     fail → treat as "no detection" this tick              │  │
                                        │  │ 1. conf_norm = streaming_zscore(camera, det.conf)         │  │  (FRM-06)
                                        │  │ 2. push (cx,cy) to history ring; velocity = finite-diff   │  │  (FRM-04)
                                        │  │ 3. ideal = (0.5,0.5) shifted TOWARD motion (lead-room)    │  │  (FRM-04)
                                        │  │ 4. c = gaussian_centeredness(cx,cy, ideal)                │  │  (FRM-01)
                                        │  │ 5. s = gaussian_size_band(sqrt(w*h))                      │  │  (FRM-01)
                                        │  │ 6. base = w_c·c + w_s·s + w_conf·conf_norm  (∈[0,1])      │  │  (FRM-01)
                                        │  │ 7. zone = point_in_rect(cx,cy, camera.zones)              │  │  (FRM-03)
                                        │  │    gated = base × weight[role][zone]  (or gate-down if    │  │
                                        │  │            outside all zones)                             │  │
                                        │  │ 8. raw = clip(gated, 0, 1); reset TTL; ema = α·raw+(1-α)ema│ │  (FRM-02)
                                        │  └───────────────────────────────────────────────────────────┘  │
                                        │  ┌─ det absent (dropout) ───────────────────────────────────┐  │
                                        │  │ TTL-- ; while TTL>0: COAST (hold ema, status=coasting)    │  │  (FRM-05)
                                        │  │ TTL==0: ema→0, status=lost                                │  │
                                        │  └───────────────────────────────────────────────────────────┘  │
                                        │                       │  emits CameraScore(cam_id, tick,         │
                                        │                       │       score=ema, status, debug…)         │
                                        └───────────────────────┼────────────────────────────────────────┘
                                                                ▼
                                              Phase-3 FSM (consumer): per-camera score → which camera is live
```

### Recommended Project Structure
```
src/segugio/framing/
├── __init__.py        # re-export DetectionSignal, CameraScore, CameraScorer, MultiCamScorer
├── signals.py         # frozen DetectionSignal (input contract) + CameraScore (output) + ScorerStatus enum
├── terms.py           # PURE free functions: gaussian_centeredness, gaussian_size_band,
│                      #   zone_of, lead_room_target, plausibility_ok, streaming_zscore step
├── scorer.py          # CameraScorer (per-camera stateful object) + MultiCamScorer (dict of them)
└── params.py          # ScorerParams dataclass/pydantic sub-model bridging Config → scorer
                       #   (size_band, ttl, conf_norm window, gate_down, lead clamp, term weights)
src/segugio/synth/
└── detection_stream.py  # NEW deterministic generator: emits raw DetectionSignal sequences
                         #   (resolution-tagged, motion paths, dropout windows, two-camera bias)
tests/
├── test_framing_base.py        # FRM-01: centeredness, size-band peak, resolution-invariance
├── test_framing_ema.py         # FRM-02: EMA lag/responsiveness, cold-start, no-detection
├── test_framing_zone.py        # FRM-03: zone lookup, multiplier, out-of-bounds gate-down
├── test_framing_leadroom.py    # FRM-04: target shifts TOWARD motion (sign), clamp, zero-speed
├── test_framing_coast.py       # FRM-05: coast-then-lost timeline, TTL boundary, EMA interaction
├── test_framing_confnorm.py    # FRM-06: brighter-camera anti-bias assertion
├── test_framing_shadow.py      # guard: aspect/min-size/conf-floor rejection
└── test_framing_purity.py      # FRM-07: determinism (same seq → same scores), no-I/O, import-smoke
```

### Pattern 1: Base score = weighted sum of Gaussian-centeredness + Gaussian-size-band + normalized-confidence (FRM-01)

**What:** `base = w_c·centeredness + w_s·size_score + w_conf·conf_norm`, all three terms in `[0,1]`, weights `w_c + w_s + w_conf = 1` so `base ∈ [0,1]`.

**Centeredness — recommend Gaussian over linear.** Both are resolution-independent (normalized coords). Linear `1 - dist/maxdist` has a constant gradient and hits exactly 0 at the farthest corner; it is fine but reacts sharply to bbox-center jitter near the edges. A **Gaussian falloff** is flatter near the ideal (so small jitter on a well-centered dog barely moves the score → less flicker, addressing PITFALLS Pitfall 8) and decays smoothly:

```
dx = cx - ideal_x ;  dy = cy - ideal_y
centeredness = exp( -(dx² + dy²) / (2·σ_c²) )        # σ_c ≈ 0.25  [ASSUMED]
```
`σ_c` controls how forgiving "centered" is: σ_c≈0.25 means a dog ~one σ (¼ frame) off-ideal still scores ~0.61. Tune on clips. `ideal_x, ideal_y` default to `(0.5, 0.5)` and are **shifted by lead-room** (Pattern 4) — this is the single coupling point between FRM-01 and FRM-04.

**Size target-band — recommend Gaussian over `sqrt(area)` (NOT monotonic `w·h`).** This is the explicit fix for PITFALLS Pitfall 4 ("bigger is not always better"): too-small = lost in a wide shot, too-big = clipped/over-tight. Model a band with an **ideal size** and tolerance. Operate on **`sqrt(area) = sqrt(w·h)`** (a linear "scale" measure) rather than raw area, so the penalty is symmetric in apparent size, not skewed by the quadratic of area:

```
size = sqrt(w · h)                                   # apparent scale, ∈[0,1] (w,h normalized)
size_score = exp( -(size - ideal_size)² / (2·σ_s²) ) # peaks at ideal_size
```
Config parameterization (recommend `(ideal_size, sigma)` — clean, one peak, smooth):
- `ideal_size` ≈ 0.30 `[ASSUMED]` (dog occupies ~30% of frame height/width → comfortable medium shot)
- `σ_s` ≈ 0.18 `[ASSUMED]` (tolerance; wide enough that a small distant dog at size 0.10 still scores ~0.45, not 0)

**Alternative band parameterization the user may prefer** (offer at discuss-phase): a **trapezoidal/plateau** band `(lo, ideal_lo, ideal_hi, hi)` that scores 1.0 across a *flat ideal plateau* `[ideal_lo, ideal_hi]` and ramps linearly to 0 at `lo`/`hi`. Trapezoid is more interpretable ("anything between 25% and 40% is perfect") and avoids over-penalizing a range; Gaussian is smoother and has one fewer knob. **Recommend Gaussian for v1** (fewer params, smooth gradient helps EMA stability); document the trapezoid as the tunable alternative. The config should store whichever as named params, never hardcoded.

**Why `sqrt(area)` not `area`:** area scales as size², so a dog going from 20%→30% linear scale quadruples nothing-intuitive in area units; `sqrt(area)` restores a linear "how big does it look" axis on which a symmetric Gaussian is meaningful. `[CITED: standard practice — object-size scoring via Gaussian PDF over a scale measure, ScienceDirect "Gaussian Shape" overview]`

**Confidence term:** use the **per-camera normalized** confidence (Pattern 6), NOT raw `det.conf`. Once a detection clears the plausibility floor (Pattern 8), confidence enters as a *mild* term (low `w_conf`) — PITFALLS Pitfall 10 is explicit that raw confidence must not dominate, or the brightest camera wins.

**Default term weights** (sum to 1): `w_c = 0.5, w_s = 0.3, w_conf = 0.2` `[ASSUMED]` — centeredness dominant (framing correctness), size a real but secondary preference, confidence a light tiebreaker. PITFALLS Pitfall 4 says "weight centeredness above raw size"; this honors that.

### Pattern 2: Per-camera EMA smoothing with explicit cold-start and no-detection handling (FRM-02)

**What:** the standard first-order exponential moving average, one state scalar per camera:
```
s_t = α · raw_t + (1 - α) · s_{t-1}
```
`α = Thresholds.alpha` (config; default 0.3). **α semantics:** larger α = more responsive, less lag, more flicker; smaller α = smoother, more lag (dog reaches frame edge before score catches up). The equivalent "time constant" is ≈ `1/α` ticks; at 30 Hz, α=0.3 ≈ a ~100 ms smoothing window. The **responsiveness/flicker tradeoff** (PITFALLS Pitfall 8) is fundamental: a single fixed α cannot be both snappy on a sprint and calm at rest.

**Joint tuning with the FSM (SUMMARY, PITFALLS Pitfall 8):** α must be tuned *together with* the Phase-3 `debounce_N`, `min_dwell`, `hysteresis_margin`. A smoother α (smaller) lets the FSM debounce be shorter; a snappier α needs a longer debounce to avoid cut-storms. The scorer cannot tune α in isolation — flag this cross-dependency to the planner so Phase-3 validation re-checks the pair on the clip set. (A *motion-adaptive* α — higher when velocity is high — is the documented upgrade PITFALLS Pitfall 8 recommends; **recommend shipping fixed-α v1** and exposing the hook, since motion-adaptive α interacts with lead-room and is best tuned after the fixed baseline is proven. Mark motion-adaptive α as an explicit deferred item.)

**Cold start (first detection):** initialize `s_0 = raw_0` (seed with the first real score), NOT 0. Seeding with 0 makes the first ~`1/α` ticks artificially low and would lose the camera at the very start of a run. `[CITED: nestedsoftware.com EMA-on-streaming-data — y₀ = x₀]`

**No detection this tick:** do NOT feed `raw = 0` into the EMA (that hard-collapses the score — PITFALLS Pitfall 3 says this is *never* acceptable). Instead enter the **coast path** (Pattern 5): hold the EMA, decrement TTL. Only after TTL expiry does the score go to 0. The EMA and the coast logic are deliberately separated: EMA smooths *present* detections; coast handles *absent* ones.

### Pattern 3: Zone-gating as a pure point-in-rect lookup × multiplier (FRM-03)

**What:** `gated = base × framing_weights[camera.role][zone_name]`. Map the bbox center `(cx, cy)` to a zone via point-in-rect over `camera.zones` (the ARCHITECTURE.md Part 3 mechanism, already in config). This is a pure lookup — no I/O, no state.

```
def zone_of(cx, cy, camera) -> str | None:
    for z in camera.zones:          # ordered as in YAML
        x0, y0, x1, y1 = z.rect
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return z.name           # FIRST match wins (see overlap rule)
    return None                     # outside ALL zones
```

**Overlapping rects — recommend "highest weight" with a documented fallback to "first match".** The example configs have *non-overlapping* bands (near/mid/far tile the frame), so first-match and highest-weight coincide today. But nothing in the schema forbids overlap. The robust rule for the auto-director's intent ("pick the most favorable interpretation of where the dog is") is: among all rects containing the point, pick the one whose `framing_weights[role][zone]` is **highest**. This avoids a config author accidentally suppressing a camera by listing a low-weight zone first. **Recommend highest-weight; keep first-match as a config flag** if determinism-by-author-order is ever wanted. Both are pure.

**Outside all zones → gate-DOWN, not zero (PITFALLS Pitfall 1):** when `zone_of` returns `None`, the dog's center is outside every declared band for this camera — likely ringside / adjacent ring / crowd. Multiply by a small **`out_of_bounds_factor`** (≈ 0.15 `[ASSUMED]`) rather than 0, so a dog momentarily clipping a zone edge isn't instantly disqualified, but an off-field dog is heavily suppressed. This is the scorer-side half of competitor-lock (the continuity half lives in Phase 3/4). Do **not** drop to exactly 0 — that interacts badly with EMA cold-start and coast.

**Missing weight entry:** Phase-1's `model_validator` already guarantees every *referenced* zone name has a `framing_weights[role]` entry, so `weight[role][zone]` is always present for a matched zone. For belt-and-suspenders purity, default a missing key to `1.0` (neutral) and never raise inside the scorer (a scorer must not throw on data the config already validated).

### Pattern 4: Lead-room — shift the ideal target TOWARD the motion direction (FRM-04)

**The sign convention (the load-bearing detail the objective asks to nail).** Cinematography "lead room / nose room": the subject is placed on the side of the frame *opposite* the direction it moves, leaving empty space (lead room) *ahead* in the direction of travel. `[CITED: neiloseman.com, nofilmschool.com, expertphotography.com — "a subject moving/looking screen-left should be placed toward the right edge"]`

Now map that to *our* `ideal` point used by centeredness. The dog is scored on how close `(cx, cy)` is to `ideal`. To put the dog *behind* center (room ahead), we want `ideal` to sit *ahead of center, in the direction of motion* — so that a dog which is slightly *behind* that forward-shifted ideal still scores high. Concretely:

> **The ideal point shifts TOWARD the motion direction.** Dog moving right (`vx > 0`) → `ideal_x = 0.5 + lead` (ideal moves right). A dog that is at, say, `cx = 0.42` (left of the shifted ideal, i.e. behind center) now scores best — which is exactly "dog behind center, empty space to the right where it's heading." This is the correct sign. (The common verbal trap is to say "offset the subject opposite its motion"; that describes where the *subject* ends up relative to *frame center*, but the *ideal target we score against* moves the *same* direction as motion. Both statements describe the identical picture — the dog ends up on the trailing side with lead room ahead. We implement it as a forward shift of `ideal`.)

```
# velocity from track history (finite difference of normalized centers, see below)
speed = hypot(vx, vy)
if speed < v_deadzone:                     # resting dog → no lead, center is correct (PITFALL 9)
    ideal = (0.5, 0.5)
else:
    ux, uy = vx / speed, vy / speed        # unit motion direction
    lead = min(lead_gain · speed, lead_max)  # magnitude ∝ speed, CLAMPED
    ideal = (clip(0.5 + lead · ux, 0, 1),
             clip(0.5 + lead · uy, 0, 1))
```
- `lead_gain` = `FramingDefaults.lead_room` (config; disc=0.25, agility=0.10 already in `discipline.py`). This is the per-discipline knob — disc dogs sprint straight downfield (more lead), agility turns tighter (less). Reusing `lead_room` here is the intended consumer of that field.
- `lead_max` ≈ 0.25 `[ASSUMED]` clamp so a very fast dog can't push the ideal off-frame (PITFALL 9: "keep lead-room modest and clamp it").
- `v_deadzone` ≈ 0.005 normalized-units/tick `[ASSUMED]` — below this the dog is effectively stationary; lead-room disabled (avoids twitch on a resting dog).

**Velocity computation (pure, from per-camera track history):**
```
# history = ring buffer of recent (tick, cx, cy) for the LOCKED track id
# finite difference over a short smoothing window (e.g. last K=3 samples), normalized per tick:
vx = (cx_now - cx_kago) / (tick_now - tick_kago)
vy = (cy_now - cy_kago) / (tick_now - tick_kago)
```
Use a small `K`-sample lookback (K≈3 `[ASSUMED]`) rather than the single previous frame, to smooth bbox-center jitter (PITFALL 8). If the track id changed (a swap) or history is shorter than K, treat speed as 0 (no lead) until history rebuilds — this also degrades gracefully across the Phase-4 ID-swap case. Velocity is in **normalized units per tick**; because positions are normalized, it is resolution-independent.

### Pattern 5: Coast/TTL on dropout — hold, then mark lost (FRM-05)

**What:** when a detection is absent for a tick (blur on a catch/jump — PITFALLS Pitfall 3, the *worst* time to cut), the score must **COAST** for a TTL window instead of collapsing, then mark lost.

**Recommend HOLD-LAST over decay (for v1).** Two options:
- **Hold-last:** while coasting, keep `ema` frozen at its last value; status = `coasting`. Simple, and it most directly prevents the cut-away (the camera's score stays competitive through the gap). Recommend this.
- **Linear/exponential decay:** ramp `ema` down toward 0 over the TTL. More "honest" (signals rising uncertainty) but adds a parameter and can still dip the camera below a challenger mid-climax — the exact failure we're preventing. Defer decay as a tunable alternative.

```
TTL_ticks = ceil(ttl_seconds · fps)        # config seconds → ticks; fps from config/orchestrator
# on detection present:  reset ttl_counter = TTL_ticks; status = tracking
# on detection absent:
ttl_counter -= 1
if ttl_counter > 0:    status = coasting   # HOLD ema (do not feed 0 into EMA)
else:                  ema = 0.0; status = lost
```
- `ttl_seconds` ≈ 0.4 s `[ASSUMED]` for general blur (PITFALL 3: 0.3–0.7 s). PITFALL 5 notes agility *tunnels* need a longer window (1–3 s) — but **expected-occlusion hold is a Phase-3 FSM concern** (the FSM holds the exit-framing camera), not the scorer's TTL. The scorer's TTL covers the short *blur/miss* gap; the FSM covers the long *known-occluder* gap. Keep them separate; document the boundary so the planner doesn't conflate them.
- **fps:** the scorer needs ticks, not seconds. Recommend the scorer take `fps` (or directly `ttl_ticks`) at construction so it stays pure (no clock). The synthetic tests pass a fixed fps; Phase-4 passes the real loop rate. Flag as Open Question 2.

**EMA interaction:** coast freezes the EMA state; it does not advance it. On re-acquisition the EMA resumes from the held value with the new `raw` — no cold-start re-seed (the track is the same subject). Only a *new* track id (post-`lost`) triggers a fresh cold-start.

### Pattern 6: Per-camera confidence normalization — streaming EMA z-score with clipping (FRM-06)

**The problem (PITFALLS Pitfall 10):** a uniformly brighter/clearer camera yields systematically higher YOLO confidence, so a raw-confidence term biases selection toward the bright camera regardless of framing. Normalize confidence *per camera* before it enters the base score, so we judge *relative* confidence (is this a confident detection *for this camera*) not absolute brightness.

**Recommend a streaming EMA-based z-score (O(1) state, robust with clipping).** Maintain per-camera running mean and variance via EMA, then z-score and squash to `[0,1]`:
```
# per-camera streaming state: mean μ, variance σ² (init μ=conf₀, σ²=small ε on first sample)
# update (EMA of mean and of squared deviation — "incremental EMA variance"):
δ = conf - μ
μ   ← μ + β · δ
σ²  ← (1 - β) · (σ² + β · δ²)        # EMA variance (West/Finch streaming form)
z   = δ / sqrt(σ² + ε)
conf_norm = clip(0.5 + z / (2·z_clip), 0, 1)   # map z∈[-z_clip, +z_clip] → [0,1], 0.5 = "typical for this camera"
```
- `β` (conf-norm adaptation rate) ≈ 0.05 `[ASSUMED]` — *slower* than the score EMA α, so the baseline tracks the camera's lighting regime, not the instantaneous detection. (Web research: "variance should adapt more cautiously than the mean"; a slow β makes the baseline a true per-camera lighting estimate.)
- `z_clip` ≈ 2.0 `[ASSUMED]` — clip z to ±2σ so one spike doesn't dominate (web research: "z-scores can be clipped to a fixed magnitude").
- Output `0.5` = "a typical-confidence detection for this camera"; >0.5 = unusually confident; <0.5 = unusually weak. This removes the absolute-brightness bias by construction.

**Why EMA z-score over the alternatives** (the objective asks to recommend one):
- **min-max over recent history:** fragile to a single outlier (one spurious 0.99 rescales everything); needs a window buffer.
- **rank over a window:** loses magnitude, needs a sorted window buffer, ties are awkward.
- **Welford sliding window:** exact mean/var but needs a bounded ring buffer of confidences (more state) and a window-length param.
- **EMA z-score:** O(1) state (two scalars), streaming, naturally down-weights old lighting, robust once clipped. **Recommend it.** `[CITED: nestedsoftware.com (EMA streaming), Welford/West streaming-variance discussions]`

**Cold start:** for the first few samples per camera, σ² is tiny → z is unstable. Guard with `ε` and optionally return `conf_norm = conf` (raw, passthrough) for the first `N_warmup ≈ 10` samples `[ASSUMED]`, then switch to the normalized value. Keep this deterministic (count samples, no clock).

### Pattern 7: Module shape — stateful per-camera object + pure free functions (FRM-07)

**Recommend a small per-camera `CameraScorer` object** holding the four pieces of state, composing **pure free functions** for all the math:

| State held per camera | Type | Used by |
|-----------------------|------|---------|
| `ema` (last smoothed score) | `float` | FRM-02, FRM-05 |
| `history` (recent `(tick, cx, cy)` for the locked track) | bounded ring buffer (`collections.deque(maxlen=K+1)`) | FRM-04 velocity |
| `ttl_counter`, `status` | `int`, enum | FRM-05 |
| conf-norm `μ`, `σ²`, `n_samples` | `float, float, int` | FRM-06 |
| `last_track_id` | `int | None` | reset detection on swap / new track |

**Determinism / testability:** the object is deterministic given its input *stream* — feed the same sequence of `DetectionSignal | None` and it produces the same `CameraScore` sequence. No wall-clock (time is the injected `tick`), no global RNG, no I/O. This is the same contract as the Phase-1 synth generators, so the same determinism test pattern applies (`assert run(seq) == run(seq)`).

**Input contract — the frozen `DetectionSignal` dataclass** (so Phase-4 YOLO output feeds it unchanged):
```python
@dataclass(frozen=True)
class DetectionSignal:
    tick: int            # synthetic tick index (Phase 2) / frame index (Phase 4) — NO wall-clock
    cam_id: str
    cx: float            # normalized bbox center x ∈ [0,1]
    cy: float            # normalized bbox center y ∈ [0,1]
    w: float             # normalized bbox width  ∈ [0,1]
    h: float             # normalized bbox height ∈ [0,1]
    conf: float          # raw detector confidence ∈ [0,1]
    track_id: int        # tracker-assigned id (advisory; used for velocity continuity)
```
This is **exactly** the TRK-03 signal set ("centro cx/cy, dimensione w/h, confidence, track id"), so Phase 4 maps a YOLO+BoT-SORT result row to a `DetectionSignal` with no scorer change. `None` for a tick means "no dog detected on this camera this tick" → coast path.

**Output contract — a frozen `CameraScore`:**
```python
@dataclass(frozen=True)
class CameraScore:
    tick: int
    cam_id: str
    score: float                 # smoothed [0,1] — what the FSM consumes
    status: ScorerStatus         # tracking | coasting | lost
    # optional debug fields (base, centeredness, size_score, conf_norm, zone, lead) for tests/telemetry
```
A `MultiCamScorer` is just a `dict[cam_id, CameraScorer]` with an `update(dets_this_tick) -> list[CameraScore]` fan-out. Pure, deterministic, trivially testable.

### Pattern 8: Shadow / plausibility guard — a cheap pure pre-score gate (PITFALLS Pitfall 10)

**What:** before scoring, reject implausible detections (shadow blobs, dark false-positives) with cheap, pure, scorer-side signals. A rejected detection is treated as "no detection this tick" (→ coast), not scored:
```
def plausibility_ok(det, p) -> bool:
    if det.conf < p.conf_floor:                      # confidence floor (recall gate)
        return False
    if det.w * det.h < p.min_area:                   # too tiny → noise/far-noise
        return False
    ar = det.w / det.h if det.h > 0 else 0
    if not (p.aspect_lo <= ar <= p.aspect_hi):        # implausible aspect → shadow streak / clip
        return False
    return True
```
- `conf_floor` ≈ 0.25 `[ASSUMED]` (matches the tracker's `new_track_thresh` order of magnitude from STACK.md; a *continuation* floor can be lower per PITFALL 3, but that's a Phase-4 tracker concern).
- `min_area` ≈ 0.0004 `[ASSUMED]` (≈ a 2%×2% box; below this it's almost certainly noise — but note PITFALL 4: a genuinely distant dog is small, so keep this floor *low*, it's a noise gate not a size-preference; the size-preference lives in the size-band term).
- `aspect_lo, aspect_hi` ≈ `(0.3, 3.5)` `[ASSUMED]` — a dog box is roughly within this range; a long thin shadow streak or a clipped sliver falls outside. PITFALL 10: "penalize boxes with implausible aspect ratio."

**Scope note:** the full shadow-FP defense (a ghost box that *moves rigidly with* the real dog) needs cross-detection comparison and is better handled in Phase-4 subject-selection / competitor-lock. The scorer's cheap per-detection gate (aspect/min-size/conf-floor) is the v1 pure piece; flag the rigid-shadow case as Phase-4. Keep this gate's params in config.

### Anti-Patterns to Avoid
- **Monotonic `w·h` size term** ("bigger is always better"): rewards a close bystander over the small real competitor (PITFALL 4). Use the target-band.
- **Feeding `raw=0` into the EMA on a missed detection:** hard-collapses the score, cuts away from the climax (PITFALL 3). Use coast/TTL.
- **Raw confidence as a dominant term:** brightest camera wins regardless of framing (PITFALL 10). Normalize per camera; keep `w_conf` low.
- **Centering the dog dead-center for a fast subject:** no lead room, dog pinned to the leading edge (PITFALL 9). Shift the ideal toward motion.
- **Pixel coordinates anywhere:** breaks resolution-independence (ARCHITECTURE Anti-Pattern 1). Normalized only.
- **`if sport == 'disc_dog'` branches in the scorer:** the sport difference is data (`framing_weights`, `FramingDefaults`), not code.
- **Wall-clock or global RNG in the scorer:** breaks determinism/purity (FRM-07). Time = injected tick; no randomness in the scorer at all (randomness lives only in the *synthetic generator* via an injected `Generator`).
- **Reusing the existing `score_stream` as scorer input:** it emits *final* scores for FSM tests, not raw detection signals (see Open Question 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Smoothed running mean/variance for conf-norm | A growing list of confidences you re-`np.mean`/`np.std` each tick | Streaming EMA mean/variance (two scalars) — Pattern 6 | O(1) state vs O(n) memory; naturally forgets old lighting; matches "streaming" determinism. |
| Vector distance / norm for centeredness & velocity | Manual `sqrt(dx*dx+dy*dy)` everywhere | `numpy.hypot` / small `np.array` ops | Already a dep; clearer, less error-prone, vectorizes the per-camera math. |
| Seeded reproducible synthetic detections | Custom RNG / hand-built "random" paths | `numpy.random.default_rng(seed)` injected into a new `detection_stream` generator | Matches the Phase-1 `synth` determinism contract; reproducible tests. |
| Ring buffer for track history | Manual list slicing / index bookkeeping | `collections.deque(maxlen=K+1)` | Bounded, O(1) append, the idiomatic fixed-window buffer. |
| Frozen input/output records | Mutable dicts / tuples-by-position | `@dataclass(frozen=True)` (matches `ScoreSample`/`FeedEvent`) | Hashable, comparable (`==` is the determinism assertion), typed, self-documenting. |
| Config plumbing for new scorer params | Reading a raw YAML dict in the scorer | Extend the Phase-1 pydantic models (a `ScorerParams` sub-model) | Keeps the single validated `Config` contract; fail-fast on bad scorer params too. |

**Key insight:** every novel-sounding piece (size band, lead-room, conf-norm, coast) reduces to a *small, standard* numeric primitive — a Gaussian, a finite difference, an EMA, a clamp, a countdown. The risk is not algorithmic complexity; it is (a) getting the **lead-room sign** right, (b) keeping every term **normalized and in `[0,1]`**, and (c) **not collapsing the score to 0** on a miss. The implementation should lean on numpy/stdlib for the primitives and spend its care on those three correctness points and on the config-driven parameterization.

## Runtime State Inventory

> Phase 2 is **greenfield pure-logic** — a new `segugio.framing` module and a new `segugio.synth.detection_stream` generator. There is no pre-existing scorer code, datastore, service, or registered state to migrate.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by `find src -name '*.py'`: no `framing*` module exists; no DB/datastore in the repo. | None |
| Live service config | None — Phase 2 touches no NDI/OBS/scheduler/service (all hardware/services deferred to Phase 5). | None |
| OS-registered state | None — no scheduled tasks, daemons, or services registered or referenced. | None |
| Secrets/env vars | None — the scorer reads only an in-memory `Config` object; no secrets, no env. | None |
| Build artifacts | None stale — `src/segugio.egg-info/` is the existing editable-install artifact from Phase 1; adding `segugio/framing/` to it requires no reinstall (editable install picks up new modules). Verify with one `import segugio.framing` after creating the package. | Confirm editable install resolves the new sub-package (add to `__init__` re-exports). |

**Nothing requiring migration in any category** — Phase 2 is additive pure code. The only build-adjacent note: the new `segugio/framing/` package is auto-discovered by the existing editable install (src-layout), so no `pip install -e .` re-run is needed unless `pyproject.toml` package discovery is explicit (verify it isn't pinning a package list).

## Common Pitfalls

### Pitfall 1: Size term that punishes the real distant dog (PITFALLS Pitfall 4)
**What goes wrong:** a monotonic `w·h` size term scores a small-but-correct competitor low and a large nearby bystander high → the director picks the camera with the biggest dog-shaped blob, not the one with the action.
**Why it happens:** "bigger box = better shot" is true for cinematography framing but couples subject-*distance* to camera-*selection*.
**How to avoid:** the **Gaussian/trapezoid size target-band** (Pattern 1) — peaks at an ideal size, and crucially keeps `size_score` *non-zero and meaningful* for a small distant dog (σ_s wide). Weight centeredness above size (`w_c > w_s`).
**Warning signs:** size-band test shows the score *increasing monotonically* with size instead of peaking; a distant-dog synthetic sequence scores below a large-bystander sequence.

### Pitfall 2: Lead-room sign inverted (FRM-04)
**What goes wrong:** shifting the ideal *opposite* the motion (a common misreading of "place subject opposite motion") pins the dog against the *leading* edge with empty space *behind* — the exact "trailing" failure lead-room is meant to fix (PITFALLS Pitfall 9).
**Why it happens:** conflating "where the subject sits relative to frame center" with "which way the scored ideal point moves." They point the same physical direction but the verbal shorthand inverts easily.
**How to avoid:** the proof in Pattern 4 — **ideal shifts TOWARD motion**; assert it directly in a test (dog moving right → `ideal_x > 0.5`; a dog at `cx` slightly *less* than the shifted ideal scores *higher* than the same dog dead-center).
**Warning signs:** lead-room test asserts `ideal_x < 0.5` for rightward motion; rendered/synthetic check shows space *behind* the dog.

### Pitfall 3: Score collapses to 0 on a missed detection (PITFALLS Pitfall 3 — "never acceptable")
**What goes wrong:** feeding `raw=0` (or no-detection → 0) into the EMA makes the score crater during the blur at a catch/jump apex; the FSM cuts away from the climax.
**Why it happens:** treating "no detection" as "score 0" instead of "subject momentarily occluded."
**How to avoid:** the **coast/TTL** path (Pattern 5) — hold the EMA through the TTL window; only go to 0 after expiry, status `lost`.
**Warning signs:** coast test shows the score dropping during a single-tick gap; no `coasting` status ever emitted.

### Pitfall 4: Confidence bias toward the brightest camera (PITFALLS Pitfall 10)
**What goes wrong:** a camera with systematically higher YOLO confidence (better lit) always wins, regardless of framing quality.
**Why it happens:** raw `conf` is an absolute image-quality signal, not a relative framing signal.
**How to avoid:** **per-camera streaming z-score** (Pattern 6) + low `w_conf`. Score relative confidence, not brightness.
**Warning signs:** the conf-norm anti-bias test (two cameras, identical framing, one with +0.2 confidence offset) shows the brighter camera winning after normalization.

### Pitfall 5: Resolution leak (FRM-01)
**What goes wrong:** any pixel value, frame width/height, or aspect-dependent constant sneaks into a formula → the score changes when the same scene is fed at a different resolution.
**Why it happens:** habit of thinking in pixels; or computing area as `w_px·h_px`.
**How to avoid:** every input is normalized `[0..1]`; the **resolution-invariance test** feeds the *same normalized sequence* twice (conceptually "640p" and "1080p" → identical normalized signals) and asserts identical scores. There is literally no resolution variable in the scorer.
**Warning signs:** any `1920`, `1080`, `width`, `aspect` literal in `framing/`; the invariance test isn't present.

### Pitfall 6: Non-deterministic scorer (FRM-07)
**What goes wrong:** any randomness, wall-clock, or global state in the scorer makes tests flaky and breaks reproducibility.
**Why it happens:** reaching for `time.time()` for "now", or `np.random` for jitter inside the scorer.
**How to avoid:** the scorer has **zero randomness** and **zero clock** — time is the injected `tick`. All randomness lives only in the synthetic *generator* (injected `numpy.random.Generator`). Determinism test: same input sequence → identical output, run twice.
**Warning signs:** `import time` or `np.random` in `framing/`; a test passes alone but fails under `pytest -n auto`.

## Code Examples

> Reference skeletons for the planner. Math verified against cinematography lead-room conventions (cited) and standard streaming-statistics forms (cited). Not the final implementation.

### Base score terms (FRM-01) — pure functions
```python
# src/segugio/framing/terms.py
import numpy as np

def gaussian_centeredness(cx: float, cy: float, ideal: tuple[float, float], sigma_c: float) -> float:
    dx, dy = cx - ideal[0], cy - ideal[1]
    return float(np.exp(-(dx * dx + dy * dy) / (2.0 * sigma_c * sigma_c)))  # ∈(0,1]

def gaussian_size_band(w: float, h: float, ideal_size: float, sigma_s: float) -> float:
    size = float(np.sqrt(max(w * h, 0.0)))          # apparent scale ∈[0,1]; NOT monotonic area
    d = size - ideal_size
    return float(np.exp(-(d * d) / (2.0 * sigma_s * sigma_s)))  # peaks at ideal_size

def base_score(c: float, s: float, conf_norm: float, w_c: float, w_s: float, w_conf: float) -> float:
    return float(np.clip(w_c * c + w_s * s + w_conf * conf_norm, 0.0, 1.0))  # weights sum to 1
```

### Lead-room ideal target (FRM-04) — TOWARD motion, clamped
```python
# Source: cinematography lead/nose-room convention (neiloseman.com, nofilmschool.com)
def lead_room_target(vx: float, vy: float, lead_gain: float, lead_max: float,
                     v_deadzone: float) -> tuple[float, float]:
    speed = float(np.hypot(vx, vy))
    if speed < v_deadzone:
        return (0.5, 0.5)                      # resting dog → center (PITFALL 9)
    ux, uy = vx / speed, vy / speed            # unit motion direction
    lead = min(lead_gain * speed, lead_max)    # ∝ speed, clamped
    return (float(np.clip(0.5 + lead * ux, 0.0, 1.0)),   # ideal shifts TOWARD motion
            float(np.clip(0.5 + lead * uy, 0.0, 1.0)))
```

### Zone lookup + gate (FRM-03)
```python
def zone_of(cx: float, cy: float, camera) -> str | None:
    matches = [(z.name, z.rect) for z in camera.zones
               if z.rect[0] <= cx <= z.rect[2] and z.rect[1] <= cy <= z.rect[3]]
    if not matches:
        return None                            # outside all zones → gate-down
    return matches[0][0]                        # or: pick highest framing_weights[role][name]

def gate(base: float, camera, zone_name: str | None, framing_weights, out_of_bounds_factor: float) -> float:
    if zone_name is None:
        return base * out_of_bounds_factor      # ringside/adjacent-ring suppression (NOT 0)
    weight = framing_weights[camera.role].get(zone_name, 1.0)
    return base * weight
```

### Streaming per-camera confidence z-score (FRM-06)
```python
# Source: EMA streaming mean/variance (nestedsoftware.com) + clipped z-score (web research)
def conf_norm_step(state, conf: float, beta: float, z_clip: float, eps: float, warmup: int) -> tuple[float, dict]:
    n = state["n"] + 1
    if n == 1:
        state = {"n": 1, "mu": conf, "var": 0.0}
        return conf, state                       # passthrough on first sample
    mu, var = state["mu"], state["var"]
    delta = conf - mu
    mu = mu + beta * delta
    var = (1.0 - beta) * (var + beta * delta * delta)
    state = {"n": n, "mu": mu, "var": var}
    if n <= warmup:
        return conf, state                       # passthrough until baseline stabilizes
    z = delta / np.sqrt(var + eps)
    return float(np.clip(0.5 + z / (2.0 * z_clip), 0.0, 1.0)), state
```

### CameraScorer.update — composition (FRM-02, FRM-05, FRM-07)
```python
# src/segugio/framing/scorer.py  (skeleton)
from collections import deque

class CameraScorer:
    def __init__(self, camera, params, framing_weights, alpha, lead_gain, ttl_ticks):
        self.camera = camera; self.p = params; self.fw = framing_weights
        self.alpha = alpha; self.lead_gain = lead_gain; self.ttl_ticks = ttl_ticks
        self.ema = None; self.status = "lost"
        self.hist = deque(maxlen=self.p.vel_window + 1)
        self.ttl = 0; self.last_track = None
        self.conf_state = {"n": 0, "mu": 0.0, "var": 0.0}

    def update(self, det, tick) -> "CameraScore":
        if det is not None and plausibility_ok(det, self.p):
            if det.track_id != self.last_track:        # new/swapped track → reset velocity history
                self.hist.clear(); self.last_track = det.track_id
            conf_norm, self.conf_state = conf_norm_step(self.conf_state, det.conf, self.p.beta,
                                                         self.p.z_clip, self.p.eps, self.p.warmup)
            self.hist.append((tick, det.cx, det.cy))
            vx, vy = self._velocity()
            ideal = lead_room_target(vx, vy, self.lead_gain, self.p.lead_max, self.p.v_deadzone)
            c = gaussian_centeredness(det.cx, det.cy, ideal, self.p.sigma_c)
            s = gaussian_size_band(det.w, det.h, self.p.ideal_size, self.p.sigma_s)
            base = base_score(c, s, conf_norm, self.p.w_c, self.p.w_s, self.p.w_conf)
            zone = zone_of(det.cx, det.cy, self.camera)
            raw = gate(base, self.camera, zone, self.fw, self.p.out_of_bounds_factor)
            self.ema = raw if self.ema is None else self.alpha * raw + (1 - self.alpha) * self.ema
            self.ttl = self.ttl_ticks; self.status = "tracking"
        else:                                          # dropout → coast then lost
            self.ttl -= 1
            if self.ema is not None and self.ttl > 0:
                self.status = "coasting"               # HOLD ema (do NOT feed 0)
            else:
                self.ema = 0.0; self.status = "lost"
        return CameraScore(tick, self.camera.id, float(self.ema or 0.0), self.status)
```

### NEW synthetic detection-sequence generator (FRM-07 test substrate)
```python
# src/segugio/synth/detection_stream.py  (NEW — distinct from score_stream which emits FINAL scores)
import numpy as np
from segugio.framing.signals import DetectionSignal

def detection_stream(rng: np.random.Generator, cam_id: str, n_ticks: int, *,
                     path: str = "linear_right",       # motion path for lead-room tests
                     size: float = 0.30,               # constant or ramped apparent size
                     conf: float = 0.7, conf_bias: float = 0.0,  # +bias = "brighter camera" for FRM-06
                     dropout: tuple[int, int] | None = None,     # (start, end) ticks of missed detection
                     noise: float = 0.01, track_id: int = 1) -> list[DetectionSignal | None]:
    out: list[DetectionSignal | None] = []
    for t in range(n_ticks):
        if dropout and dropout[0] <= t < dropout[1]:
            out.append(None); continue                 # coast/TTL case
        frac = t / max(n_ticks - 1, 1)
        cx = {"linear_right": 0.2 + 0.6 * frac, "static": 0.5}[path]
        cy = 0.5
        jx, jy = rng.normal(0, noise, 2)                # injected rng only — determinism
        out.append(DetectionSignal(t, cam_id, float(np.clip(cx + jx, 0, 1)), float(np.clip(cy + jy, 0, 1)),
                                   size, size, float(np.clip(conf + conf_bias, 0, 1)), track_id))
    return out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monotonic `size = w·h` ("bigger better") | Gaussian/trapezoid **target band** over `sqrt(area)` | This phase (per PITFALLS) | Distant real dog scores well; close bystander doesn't auto-win. |
| Center dead-center (`ideal = 0.5,0.5`) | **Lead-room**: ideal shifts toward motion, ∝ clamped speed | This phase (per PITFALLS 9 + cinematography) | Space ahead of a moving dog; shot leads instead of trails. |
| Hard-gate score to 0 on a miss | **Coast/TTL** hold-last, then lost | This phase (per PITFALL 3) | No cut-away at the climax (blur on catch/jump). |
| Raw confidence in the score | **Per-camera streaming z-score** (EMA mean/var, clipped) | This phase (per PITFALL 10) | Brightest camera no longer wins on conf alone. |
| `np.random.seed()` global / wall-clock time | Injected `Generator` (in the generator only) + injected `tick` | numpy ≥1.17; project convention | Deterministic, parallel-safe, reproducible scorer tests. |

**Deprecated/outdated:** none specific to this phase — the math primitives (Gaussian, EMA, finite-difference, z-score) are long-stable. The only "old approaches" are the naive scorer choices the PITFALLS doc explicitly warns against (above).

## Assumptions Log

> Every numeric default below is a **tuning seed**, not a verified value. The *formula shapes* are HIGH-confidence; the *constants* are `[ASSUMED]` and should be confirmed at discuss-phase and re-tuned on the clip set in Phase 3/4. None block planning — they are config values.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Gaussian centeredness (σ_c≈0.25) preferred over linear `1-dist/maxdist`. | Pattern 1 | LOW — both work; Gaussian is smoother. Swap is one function. Confirm preference at discuss. |
| A2 | Size band: Gaussian over `sqrt(area)` with `ideal_size≈0.30, σ_s≈0.18`. Trapezoid `(lo,ideal_lo,ideal_hi,hi)` offered as alternative. | Pattern 1 | MEDIUM — the *ideal size* depends on real footage (how big the dog actually appears on each camera). The *shape* is safe; the *value* needs the clip set. User may prefer trapezoid for interpretability. |
| A3 | Term weights `w_c=0.5, w_s=0.3, w_conf=0.2`. | Pattern 1 | MEDIUM — drives "centeredness vs size vs conf" balance. PITFALLS says `w_c>w_s` and low `w_conf`; the *ordering* is safe, the *exact split* is a tuning seed. |
| A4 | Lead-room reuses `FramingDefaults.lead_room` as `lead_gain` (disc 0.25 / agility 0.10); `lead_max≈0.25`, `v_deadzone≈0.005`/tick. | Pattern 4 | MEDIUM — sign is proven; magnitudes are seeds. Over-large lead pushes the dog to the edge; clamp mitigates. Confirm the `lead_room`-as-gain interpretation at discuss (it could instead be a fixed offset). |
| A5 | Coast TTL `ttl_seconds≈0.4` (range 0.3–0.7), hold-last (not decay). Tunnel-length occlusion is a Phase-3 FSM concern, not scorer TTL. | Pattern 5 | MEDIUM — too short cuts at the climax; too long holds a truly-gone dog. The scorer/FSM TTL split must be confirmed so Phase 3 doesn't double-implement coast. |
| A6 | Conf-norm: EMA z-score, `β≈0.05`, `z_clip≈2.0`, `warmup≈10`, passthrough during warmup. | Pattern 6 | MEDIUM — chosen over min-max/rank/Welford on O(1)-state grounds; β controls how fast the per-camera baseline adapts to changing light. Values are seeds. |
| A7 | Shadow guard: `conf_floor≈0.25, min_area≈0.0004, aspect∈(0.3,3.5)`. Rigid-shadow (moves-with-dog) deferred to Phase 4. | Pattern 8 | MEDIUM — too-tight a gate drops real distant/odd-pose dogs (PITFALL 4); keep loose. Confirm the scorer-vs-Phase-4 split. |
| A8 | `out_of_bounds_factor≈0.15` (gate-down, not 0) when outside all zones. | Pattern 3 | LOW — magnitude is a seed; the *non-zero* choice is the important, safe part. |
| A9 | New scorer params live in an additive pydantic `ScorerParams` sub-model on `Config`/`Thresholds`. | Open Q3 / Don't Hand-Roll | LOW — keeps the validated single-Config contract; exact nesting (top-level vs under thresholds vs under discipline) is a small design choice for the planner. |
| A10 | A NEW `segugio.synth.detection_stream` generator is required (the existing `score_stream` emits final FSM scores, not raw detection signals). | Open Q1 | LOW — verified by reading `score_stream.py`; it returns `ScoreSample(tick,cam_id,score)`, not detection signals. Building the new generator is in-scope for this phase. |
| A11 | The scorer takes `fps` (or `ttl_ticks` directly) at construction to convert TTL seconds → ticks, staying clock-free. | Open Q2 / Pattern 5 | LOW — keeps purity; fps is a config/orchestrator value. |

**If this table is empty:** it is not — eleven assumptions, all LOW/MEDIUM, none blocking. The MEDIUM ones (A2, A3, A4, A5, A6, A7) are all *tuning values* that the clip set in Phase 3/4 will calibrate; the *formula shapes* they sit inside are HIGH-confidence.

## Open Questions

1. **The existing `score_stream` is NOT the scorer's input — a new detection generator is needed.**
   - What we know: `segugio.synth.score_stream` emits `ScoreSample(tick, cam_id, score)` — *final* per-camera scores for testing the Phase-3 FSM. The scorer's input is *raw per-detection signals* (`cx, cy, w, h, conf, track_id`).
   - What's unclear: nothing — confirmed by reading the source. The question is only *where* the new generator lives.
   - Recommendation: add `segugio.synth.detection_stream` (NEW, alongside `score_stream`/`feed_death`), emitting `list[DetectionSignal | None]` with knobs for motion path, size ramp, confidence bias (for the FRM-06 anti-bias test), and dropout windows (for coast). In-scope for Phase 2. Re-export from `segugio.synth.__init__`.

2. **How does the scorer get `fps` to convert TTL seconds → ticks while staying pure?**
   - What we know: TTL is naturally specified in seconds (config), but the scorer counts ticks (no clock allowed).
   - What's unclear: whether to pass `fps` at construction, pass `ttl_ticks` precomputed, or store `ttl_ticks` in config directly.
   - Recommendation: scorer constructor takes `fps` (or `ttl_ticks`); the orchestrator/test supplies it. Keeps the scorer clock-free and deterministic. Confirm at discuss whether config stores `ttl_seconds` (human-friendly) + fps elsewhere, or `ttl_ticks` directly.

3. **Where do the new scorer parameters live in the config schema?**
   - What we know: `Thresholds` has `alpha`; `FramingDefaults` has `lead_room`. The scorer needs more: `sigma_c, ideal_size, sigma_s, w_c/w_s/w_conf, lead_max, v_deadzone, ttl_seconds, beta, z_clip, warmup, conf_floor, min_area, aspect_lo/hi, out_of_bounds_factor`.
   - What's unclear: nesting — a new top-level `scoring:` block? under `thresholds:`? per-discipline under `FramingDefaults`?
   - Recommendation: a new additive pydantic sub-model (e.g. `ScorerParams`) referenced from `Config` (top-level `scoring:` block), with the *per-discipline* knobs (`lead_room`, maybe `ideal_size`) staying in `FramingDefaults`. This extends the Phase-1 contract additively (no breaking change) and keeps everything in the one validated `Config`. The exact split is a small planner/discuss decision; the *principle* (all in validated config, none hardcoded) is locked.

4. **Fixed-α vs motion-adaptive α for v1?**
   - What we know: SUMMARY/PITFALLS recommend motion-adaptive α eventually; a single fixed α can't be both snappy on a sprint and calm at rest.
   - What's unclear: whether to ship the adaptive form in Phase 2 or defer.
   - Recommendation: **ship fixed-α v1** (α from config), expose a clean hook, and defer motion-adaptive α as an explicit item — it interacts with lead-room and is best tuned after the fixed baseline is validated on the clip set. Confirm at discuss.

## Environment Availability

> The scorer has **no external dependencies** beyond the already-installed Phase-1 stack. This section confirms the toolchain is present.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All Phase-2 code | ✓ | 3.12.3 | — |
| `numpy` | Scorer math + synth generator | ✓ | 2.4.6 (project `.venv`) | — |
| `pydantic` | Reading the typed `Config` | ✓ | 2.13.4 (`.venv`) | — |
| `pytest` (+ `pytest-cov`) | Unit tests | ✓ | 9.0.3 / 7.1.0 (`.venv`) | — |
| `segugio.config` (Phase 1) | `Config`/`Role`/`framing_weights`/`Thresholds`/`FramingDefaults` | ✓ | in-repo, editable-installed | — |
| `segugio.synth` (Phase 1) | extends with new `detection_stream` | ✓ | in-repo | — |
| GPU / CUDA / torch / NDI | NOT needed (scorer is pure, pre-YOLO) | n/a | — | by design — runs CPU-only, no GPU |

**Missing dependencies with no fallback:** none — every Phase-2 capability runs on this machine with the existing `.venv`.
**Missing dependencies with fallback:** none needed.

> Note: the system `python3` does not see numpy (it's in the project `.venv`). All Phase-2 work/tests must run via `.venv/bin/python -m pytest` (the Phase-1 convention from 01-02-SUMMARY).

## Validation Architecture

> `nyquist_validation` is enabled (`config.json workflow.nyquist_validation: true`). Each FRM behavior maps to an observable unit assertion on a seeded synthetic detection sequence.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (+ pytest-cov 7.1.0) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`) — already present |
| Quick run command | `.venv/bin/python -m pytest tests/test_framing_*.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ --cov=segugio.framing --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FRM-01 | Same normalized sequence at two "resolutions" → identical scores (resolution-invariance); base ∈ [0,1] | unit | `pytest tests/test_framing_base.py::test_resolution_invariant -x` | ❌ Wave 0 |
| FRM-01 | Size score PEAKS at `ideal_size` and is lower for both smaller and larger (NOT monotonic) | unit | `pytest tests/test_framing_base.py::test_size_band_peak -x` | ❌ Wave 0 |
| FRM-01 | Centeredness max at ideal point, decays with distance; perfectly-centered resting dog scores highest | unit | `pytest tests/test_framing_base.py::test_centeredness -x` | ❌ Wave 0 |
| FRM-02 | Cold start seeds `s_0 = raw_0` (not 0); smaller α lags more than larger α on a step input | unit | `pytest tests/test_framing_ema.py -x` | ❌ Wave 0 |
| FRM-03 | A center in `far` band × `long` role yields `base × 1.6`; outside-all-zones → `base × out_of_bounds_factor` | unit | `pytest tests/test_framing_zone.py::test_zone_multiplier -x` | ❌ Wave 0 |
| FRM-04 | Dog moving right → `ideal_x > 0.5` (shift TOWARD motion); a dog behind the shifted ideal outscores the same dog dead-center; zero speed → ideal=(0.5,0.5); lead clamped at `lead_max` | unit | `pytest tests/test_framing_leadroom.py::test_target_shifts_toward_motion -x` | ❌ Wave 0 |
| FRM-05 | A dropout window holds the score (status `coasting`) for `ttl_ticks`, then drops to 0 (status `lost`); recovery before TTL resumes `tracking` without cold-start | unit | `pytest tests/test_framing_coast.py::test_coast_then_lost -x` | ❌ Wave 0 |
| FRM-06 | Two cameras, identical framing, one with +conf bias → after normalization they score within ε (brighter camera does NOT win); the same camera's relative spikes still register | unit | `pytest tests/test_framing_confnorm.py::test_brightness_anti_bias -x` | ❌ Wave 0 |
| (guard) | Implausible aspect / sub-min-size / sub-conf-floor detection is rejected → treated as no-detection (coast) | unit | `pytest tests/test_framing_shadow.py -x` | ❌ Wave 0 |
| FRM-07 | Same `DetectionSignal` sequence → byte-identical `CameraScore` list across two runs; no `time`/`np.random`/I/O imports in `framing/`; `import segugio.framing` works with torch/cyndilib uninstalled | unit + smoke | `pytest tests/test_framing_purity.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_framing_*.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ --cov=segugio.framing --cov-report=term-missing`
- **Phase gate:** full suite green + high coverage of `segugio.framing` (pure module → should approach 100%) before `/gsd:verify-work`.

### Specific assertion patterns (how each criterion is observably verified)
- **Resolution-invariance (FRM-01):** because inputs are normalized, "different resolution" = the *same* normalized sequence. Assert `scores(seq) == scores(seq)` and, stronger, that scaling the *generator's* nominal pixel resolution (a generator param that only affects how it would denormalize — but it doesn't) leaves the emitted normalized `DetectionSignal`s, hence the scores, identical. There is no resolution variable in the scorer to break.
- **Size-band peak (FRM-01):** `assert size_score(ideal) > size_score(ideal-Δ) and size_score(ideal) > size_score(ideal+Δ)` — proves non-monotonic peak, the anti-"bigger-better" guarantee.
- **Zone multiplier (FRM-03):** construct a `Config` (reuse `config.example.yaml`), place a detection center in a known band, assert `gated == base × framing_weights[role][zone]`; place it outside all bands, assert `gated == base × out_of_bounds_factor`.
- **Lead-room sign (FRM-04):** `vx>0 → ideal_x>0.5`; and `centeredness(cx=0.42, ideal_x=0.5+lead) > centeredness(cx=0.42, ideal=0.5)` for rightward motion (dog behind center scores better with lead than without) — directly asserts the corrected sign.
- **Coast-then-lost (FRM-05):** feed `[det×5, None×ttl_ticks, None]`; assert score held (≈ last EMA) and status `coasting` for the first `ttl_ticks-1` Nones, then `score==0.0` and status `lost`. Then `[det×5, None×(ttl_ticks-1), det]` → status returns to `tracking`, EMA continuous (no re-seed).
- **Conf-norm anti-bias (FRM-06):** two `detection_stream`s identical except `conf_bias=+0.2`; run both through their own `CameraScorer`s past warmup; assert `abs(score_bright - score_dim) < ε` (normalization removed the brightness advantage), while an *intra-camera* spike in one still raises its `conf_norm`.
- **Determinism / purity (FRM-07):** `assert list(run(seq)) == list(run(seq))`; a `grep`-style assert that `framing/` imports neither `time` nor `np.random` nor any heavy dep; run the existing 01-01 import-smoke style check with heavy deps absent.

### Wave 0 Gaps
- [ ] `src/segugio/framing/__init__.py`, `signals.py`, `terms.py`, `scorer.py`, `params.py` (the module under test)
- [ ] `src/segugio/synth/detection_stream.py` + re-export in `synth/__init__.py` (NEW input generator)
- [ ] `ScorerParams` pydantic sub-model added to `segugio.config` (+ defaults in `config.example.yaml`)
- [ ] `tests/test_framing_base.py`, `test_framing_ema.py`, `test_framing_zone.py`, `test_framing_leadroom.py`, `test_framing_coast.py`, `test_framing_confnorm.py`, `test_framing_shadow.py`, `test_framing_purity.py`
- [ ] conftest: a `scorer_params` fixture (seeded defaults) + reuse of `valid_config_dict`/`seeded_rng` from Phase 1
- [ ] No framework install needed — pytest/pytest-cov already in `.venv`.

## Security Domain

> `security_enforcement` not set to `false` in config.json → included. Phase 2 is pure in-process math on already-validated config + synthetic data — the security surface is minimal.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth (no network/identity in a pure scorer). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Local single-process pure function. |
| V5 Input Validation | **yes (light)** | Scorer inputs are either the Phase-1-validated `Config` or synthetic `DetectionSignal`s. The scorer must **not throw** on out-of-range data the config already validated; it should `clip` to `[0,1]` defensively and default a missing weight to neutral `1.0` (Pattern 3) — fail-safe, not fail-loud, in the live loop. |
| V6 Cryptography | no | No crypto/secrets. |

### Known Threat Patterns for the scorer
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| NaN/inf propagation (e.g. div-by-zero in aspect or velocity) | Denial of Service (poisons the score, could wedge the FSM) | Guard every divisor (`h>0`, `speed≥v_deadzone`, `sqrt(var+eps)`); `np.clip` all outputs to `[0,1]`; treat NaN as "no detection" (coast). |
| Score collapse cutting away at the climax | (Availability/UX, not security) | Coast/TTL (Pattern 5) — listed here because "never collapse" is a robustness invariant the live director depends on. |
| Unvalidated new scorer params reaching the live loop | Tampering / DoS | Add `ScorerParams` to the pydantic `Config` so bad scorer params fail fast at startup (CFG-01's fail-fast contract extends to them). |

## Sources

### Primary (HIGH confidence)
- **Phase-1 source code (read directly, 2026-06-09):** `src/segugio/config/models.py` (`Role`, `Zone`, `Camera`, `ModelConfig`, `Thresholds.alpha`, `Config.framing_weights[Role][zone]`, the zone-weight cross-validator), `src/segugio/config/discipline.py` (`FramingDefaults.lead_room` disc=0.25/agility=0.10), `src/segugio/synth/score_stream.py` + `feed_death.py` (frozen-dataclass + injected-`Generator` determinism contract; confirmed `score_stream` emits *final* scores, not detection signals), `tests/conftest.py` (`seeded_rng`/`valid_config_dict` fixtures), `config.example.yaml`/`config.agility.example.yaml` (the framing_weights matrix the scorer multiplies by).
- **Project research docs:** `ARCHITECTURE.md` Part 3 (zone lookup + multiply = the entire FRM-03 mechanism; Option A normalized per-camera zones; `main_wide` neutral/floored), `PITFALLS.md` (Pitfalls 1,3,4,8,9,10 — the exact failure modes each FRM term counters; "hard-gate to 0 is never acceptable"; "weight centeredness above size"), `SUMMARY.md` (competitor-lock + zone-gating first-class; α tuned jointly with debounce/dwell; coast/TTL 0.3–0.7s), `REQUIREMENTS.md` (FRM-01..07 + TRK-03 signal set), `STATE.md` (Phase-2 flagged dense/novel for research).
- **Local environment probe (2026-06-09):** confirmed `.venv` has numpy 2.4.6, pydantic 2.13.4, pytest 9.0.3, pytest-cov 7.1.0; no `framing*` module exists (greenfield); `pyproject.toml` pytest config present.

### Secondary (MEDIUM confidence — verified against the above + cross-source agreement)
- Cinematography lead/nose-room convention (sign of the offset): neiloseman.com/lead-room-nose-room-or-looking-space, nofilmschool.com/nose-room-shot-example, expertphotography.com/lead-room-principle-photography — "subject placed opposite the direction of motion/gaze, leaving space ahead" (proves the FRM-04 sign). Cross-agrees with PITFALLS Pitfall 9 and Sony PTZ auto-framing.
- PTZ/virtual-camera auto-framing (centeredness/size/smoothing/confidence as the standard scoring axes; smoothing to avoid jumpiness): pro.sony PTZ Auto Framing, ptzoptics.com, telycam.com — confirms the four scoring inputs and the need for position smoothing (EMA).
- Streaming statistics (EMA mean/variance, clipped z-score, Welford as the windowed alternative): nestedsoftware.com EMA-on-streaming-data (y₀=x₀ cold-start; EMA recurrence), Welford/West streaming-variance discussions, emergentmind z-score normalization (clip to fixed magnitude; sliding-window/EMA for non-stationary data) — supports the FRM-06 EMA z-score recommendation and the EMA cold-start choice.
- Gaussian-over-scale object-size scoring: ScienceDirect "Gaussian Shape" overview + object-tracking 2D-area-as-Gaussian-PDF — supports the size target-band as a Gaussian over a scale measure.

### Tertiary (LOW confidence)
- None — every recommendation rests on either the in-repo contract (HIGH) or cross-agreeing secondary sources (MEDIUM). All numeric constants are explicitly flagged `[ASSUMED]` tuning seeds, not source-backed values.

## Metadata

**Confidence breakdown:**
- Formula shapes (centeredness/size-band/EMA/lead-room/coast/conf-norm): **HIGH** — standard primitives, cross-verified; the lead-room sign is proven and cited.
- Phase-1 contract the scorer consumes: **HIGH** — read directly from source this session.
- Numeric tuning constants (σ_c, ideal_size, weights, TTL, β, …): **LOW–MEDIUM by design** — heuristic seeds tagged `[ASSUMED]`, to be tuned on the clip set in Phase 3/4; the requirement is only that they live in config and have sane shapes.
- Validation architecture: **HIGH** — each FRM behavior has a concrete, observable assertion on a seeded synthetic sequence.

**Research date:** 2026-06-09
**Valid until:** ~2026-09-09 (90 days — the math is stable; only the tuning values will move, and those are expected to during Phase 3/4 clip-set calibration). Re-verify `.venv` package versions before implementation if the environment is rebuilt.
