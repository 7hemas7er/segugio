# Phase 3: Decision Engine FSM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-09
**Phase:** 03-decision-engine-fsm
**Areas discussed:** Feed-death fallback, Action/occlusion hold, Override + resume, Tiebreaker rule

---

## Feed-death fallback (DEC-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Best live alternative, else SAFE | Cut to the highest-scoring alive camera; SAFE only if none qualify | ✓ |
| Always SAFE first | Cut to SAFE on any live-feed death, re-pick next live camera on following ticks | |
| Live alt only if already qualifying | Cut to an alt only if it already passed full hysteresis; else SAFE | |

**User's choice:** Best live alternative, else SAFE
**Notes:** Emergency cut bypasses min_dwell/cooldown (a dead feed can't stay on air); new live camera then gets normal dwell protection; recovered camera rejoins only via full hysteresis+dwell.

---

## Action / occlusion hold (DEC-03, DEC-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit hold input(s) | FSM exposes a per-tick hold signal; real triggers (pose/disc, occlusion-zone) wired Phase 4/5 | ✓ |
| Infer from score dynamics | FSM infers action from the live camera's score behavior; no external signal | |
| Defer hold to later phase | Drop DEC-03/04 from Phase 3 scope | |

**User's choice:** Explicit hold input(s)
**Notes:** Follow-up on shape (one generic flag vs two typed inputs) → user chose **"You decide"** → Claude's discretion with guardrails (occlusion respects hold_length_s; every hold has a safety cap).

---

## Override + resume (RBT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Persist; show SAFE meanwhile | Keep override intent through a feed-death; show SAFE/alt while dead; snap back on recovery | ✓ |
| Death breaks override | A feed-death on the forced camera cancels override; return to full auto | |

**User's choice:** Persist; show SAFE meanwhile
**Notes:** Follow-up on release model → user chose **"Manual release only (v1)"** (config auto-expire timeout deferred). Captured without asking: a force is immediate (bypasses dwell/debounce); forcing an already-dead camera shows SAFE until it recovers; resume = released AND auto candidate won full hysteresis+dwell (locked by ROADMAP).

---

## Tiebreaker rule (DEC-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Incumbent wins; else config order | Current live camera wins near-ties; no incumbent → first camera in config order | ✓ |
| Incumbent wins; else role priority | Incumbent wins; no-incumbent fallback uses a role-based priority | |
| Fixed priority order always | A fixed priority decides every tie; incumbent gets no advantage | |

**User's choice:** Incumbent wins; else config order
**Notes:** Tiebreaker only fires for near-exact ties inside the hysteresis dead-band.

---

## Claude's Discretion

- **Hold input shape** — one generic vs two typed hold inputs (guardrails: occlusion respects `hold_length_s`; every hold has a safety max-cap; lean = two typed).
- **Emitted decision contract** — guarded "live target" decision shape; SAFE as state vs pseudo-camera.
- **Cold-start state** — begin on SAFE; first qualifying camera wins.
- **Two-threshold hysteresis derivation** and **tick-driven determinism** structure.
- **Threshold tuning** — config seeds calibrated on clips in Phase 4 (α tuned jointly with debounce_N/min_dwell/hysteresis_margin).

## Deferred Ideas

- `override_timeout` auto-release (v1 is manual-release-only).
- Real action/occlusion triggers (pose/disc, occlusion-zone) — Phase 4/5.
- Role-based tiebreaker priority — rejected for v1 in favor of config order.
- Motion-adaptive α coupling re-tuning — future cross-dependency.
- Numeric threshold calibration — Phase 4 clip set.
