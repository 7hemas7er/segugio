# Phase 2: Framing Scorer (pure logic) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-09
**Phase:** 02-framing-scorer-pure-logic
**Areas discussed:** Framing priority, Size preference, Coast on blur, v1 scope / defer

> Context: a thorough `02-RESEARCH.md` already existed (standalone `--research-phase` run preceding discuss). It locks the formula *shapes* (HIGH confidence) and proposes *tuning seeds* (all `[ASSUMED]`, calibrated on clips in Phase 3/4). The discussion confirmed the policy/shape forks baked into code; every user choice matched the research recommendation.

---

## Framing priority

| Option | Description | Selected |
|--------|-------------|----------|
| Centered above all (rec) | Centeredness dominates; dog-size secondary; confidence a light tiebreaker (~0.5/0.3/0.2). Safest for fluid cuts; avoids brightest-camera-wins. | ✓ |
| Centered + well-sized, ~equal | Tight well-sized shot counts nearly as much as centered (~0.4/0.4/0.2). More dynamic, risks favoring the closest camera. | |
| Let me set the emphasis | User describes the ranking. | |

**User's choice:** Centered above all (rec)
**Notes:** Centeredness-dominant `w_c=0.5, w_s=0.3, w_conf=0.2`; low `w_conf` works with FRM-06 conf-normalization to defeat brightness bias. Exact weights tuned later on clips.

---

## Size preference

| Option | Description | Selected |
|--------|-------------|----------|
| One ideal size, smooth (rec) | Gaussian band over `sqrt(area)`; single ideal size, smooth falloff; fewer knobs, EMA-friendly; distant dog still scores. | ✓ |
| A 'perfect band' plateau | Trapezoid; flat 1.0 across a size range, ramps outside. More interpretable, one extra knob, non-smooth gradient. | |

**User's choice:** One ideal size, smooth (rec)
**Notes:** Non-monotonic peak is the "bigger-is-not-better" guarantee. Trapezoid kept as a documented tunable alternative (deferred).

---

## Coast on blur

| Option | Description | Selected |
|--------|-------------|----------|
| Hold steady, then drop (rec) | Hold-last: freeze EMA through the ~0.4s blur window, then mark lost / drop to 0. Most directly prevents cutting the climax. | ✓ |
| Gently decay, then drop | Ramp toward 0 over the window. More "honest" but can dip below a rival mid-climax; adds a decay knob. | |

**User's choice:** Hold steady, then drop (rec)
**Notes:** Confirmed the scope boundary embedded in the question — scorer handles only the **short blur** (~0.3–0.7s); the **long expected-occlusion hold** (tunnels/contacts, `hold_length_s` 1.5–2.5s) is the Phase-3 FSM's job. No double-implement.

---

## v1 scope / defer

| Option | Description | Selected |
|--------|-------------|----------|
| Lean v1, defer fancy (rec) | Fixed α from config + clean hook; lead-room speed-proportional & clamped, per-discipline gain (disc 0.25 > agility 0.10); defer motion-adaptive α. | ✓ |
| Build motion-adaptive α now | α rises on fast motion, falls at rest. Better in theory but more complex, couples with lead-room, hard to tune without a baseline. | |

**User's choice:** Lean v1, defer fancy (rec)
**Notes:** Motion-adaptive α deferred to a later milestone. α must be tuned jointly with Phase-3 debounce/dwell — cross-dependency flagged for the Phase-3 planner.

---

## Claude's Discretion

Implementation details left to planner/executor (recorded in CONTEXT.md `### Claude's Discretion`): config nesting for the new `ScorerParams` sub-model; `ttl_seconds`+fps vs `ttl_ticks` plumbing; Gaussian-vs-linear centeredness falloff; conf-normalization method (EMA z-score vs alternatives); zone-overlap rule (highest-weight vs first-match) + `out_of_bounds_factor`; shadow/plausibility guard params; module shape (`CameraScorer` object + pure free functions + frozen `DetectionSignal`/`CameraScore`); the new `synth.detection_stream` generator location.

## Deferred Ideas

- Motion-adaptive α (later milestone; expose a hook in v1).
- Trapezoid/plateau size band (tunable alternative to Gaussian).
- Score-decay coast (tunable alternative to hold-last).
- Rigid-shadow false-positive defense (moves-with-dog) → Phase-4 subject-selection.
- Long expected-occlusion hold (`hold_length_s`) → Phase-3 FSM.
- All numeric tuning constants → calibrated on the curated clip set in Phase 3/4.
