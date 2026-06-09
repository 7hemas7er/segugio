---
phase: 03-decision-engine-fsm
reviewed: 2026-06-09T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - src/segugio/decision/__init__.py
  - src/segugio/decision/clocks.py
  - src/segugio/decision/engine.py
  - src/segugio/decision/signals.py
  - tests/conftest.py
  - tests/test_decision_clocks.py
  - tests/test_decision_determinism.py
  - tests/test_decision_feeddeath.py
  - tests/test_decision_holds.py
  - tests/test_decision_hysteresis.py
  - tests/test_decision_imports.py
  - tests/test_decision_invariants.py
  - tests/test_decision_override.py
  - tests/test_decision_scenarios.py
  - tests/test_decision_tiebreak.py
  - tests/test_imports.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the Phase-3 decision-engine FSM (`segugio.decision`): the clocks bridge, the
`transitions.Machine` wrapper, the frozen I/O records, and the 10-file test suite. The full
decision test suite passes (39 tests green) and the headline safety invariants — never air a
dead feed, decision only from a guarded callback, deterministic replay — hold under the
scenarios the tests exercise.

However, the adversarial pass surfaced one CORRECTNESS BLOCKER in the SAFE-fallback path that
the existing tests do not cover, plus several robustness/quality warnings. The blocker
(CR-01) makes the system linger on the SAFE scene for ~1 extra second after a total-blackout
recovery — a direct hit on the project's core value ("la camera giusta al momento giusto") and
its live-robustness constraint. The warnings center on a liveness-vs-score-presence conflation
(WR-01), a documented reason string that the engine emits but never declares (WR-02), an
asymmetric hold-cap off-by-one (WR-03), silent override-input ambiguity (WR-04), and a dead
transition edge (WR-05).

All findings below were reproduced empirically against the running engine, not inferred from
reading alone.

## Critical Issues

### CR-01: SAFE fallback sets a spurious cooldown that blocks re-acquisition for ~1s after a blackout

**File:** `src/segugio/decision/engine.py:323-339`
**Issue:**
`_set_target_safe()` calls `_on_target_change()` whenever the target was not already SAFE, and
`_on_target_change()` unconditionally sets `self.cooldown_remaining = self.cooldown_ticks`
(30 ticks @ 30fps). The dwell guard `dwell_elapsed_ok()` deliberately exempts SAFE
(`if self.target == SAFE_TARGET: return True`, line 269), but the cooldown guard
`cooldown_clear()` (line 273) has **no such exemption** — it only checks
`cooldown_remaining == 0`.

Consequence: after the FSM drops to SAFE (e.g. all feeds die, then a feed-death emergency
routes to SAFE via the `unless=["has_alive_candidate"]` edge at lines 100-107), the SAFE target
carries a 30-tick cooldown. When a camera recovers and immediately qualifies (clears the margin
and sustains debounce_N), the `auto_switch` guard is **blocked by `cooldown_clear()`** for the
remainder of the cooldown — so the show holds on the SAFE/wide scene for ~1 extra second even
though a healthy, well-framed camera is available.

Reproduced: acquire `cam_b`, kill both feeds (target → SAFE, `cooldown_remaining == 30`), then
recover `cam_a` at score 0.95. Re-acquisition does not fire until i=29 (`cooldown_ticks - 1`).
Measured: ~29 ticks (~0.97s) of unnecessary SAFE airtime after recovery.

This violates the core value (the right camera at the right moment) and the live-robustness
constraint (degrade to SAFE, but recover the instant a feed returns). SAFE is a fallback, not
an incumbent to "protect" — it should carry no cooldown, exactly as it carries no dwell.

No existing test catches this: the feed-death suite only tests blackout *into* SAFE, never the
*recovery out of* SAFE under a fresh-cooldown condition.

**Fix:** Exempt SAFE from the cooldown gate, mirroring the existing dwell exemption. Either
guard `cooldown_clear()`:
```python
def cooldown_clear(self) -> bool:
    """True iff no post-cut cooldown is in effect (SAFE has no incumbent to protect)."""
    if self.target == SAFE_TARGET:
        return True
    return self.cooldown_remaining == 0
```
…or, better, do not arm dwell/cooldown clocks when the new target is SAFE (since SAFE is not a
camera being protected):
```python
def _on_target_change(self) -> None:
    self.dwell_elapsed = 0
    self.cooldown_remaining = 0 if self.target == SAFE_TARGET else self.cooldown_ticks
```
Note the second form must run AFTER `self.target` is set; `_set_target_safe()` currently calls
`_on_target_change()` BEFORE assigning `self.target = SAFE_TARGET` (lines 325-327), so reorder
those two statements if you take the target-aware approach.

## Warnings

### WR-01: An alive camera with no score row this tick is mistaken for a dead feed and emergency-cut

**File:** `src/segugio/decision/engine.py:299-301, 438-450`
**Issue:**
`live_feed_dead()` returns True when `self.target not in self._alive_eligible`, and
`_alive_eligible` is built **only** from cameras that have a finite score row in *this tick's*
`scores` list (`set(score_by_cam.keys())`, line 450). A camera that the alive map reports as
`alive=True` but that simply has **no `CameraScore` row this tick** is therefore treated as a
dead feed: `live_feed_dead()` fires and the engine emergency-cuts off it.

Reproduced: acquire `cam_a` as incumbent; on a tick where `cam_a`'s score row is omitted (but
`alive={"cam_a": True}`) and `cam_b` is a modest 0.30, the engine emits
`reason="feed_emergency"` and cuts to `cam_b`. The documented liveness authority is the alive
map (engine.py:410-411, "the FSM consumes liveness, it never derives it"), yet here liveness is
silently derived from score-row presence, contradicting the alive map.

In the intended Phase-2 pipeline a `CameraScore` row is emitted per camera per tick (even
`lost` → score 0.0, which stays eligible), so this does not fire today. But nothing at this
boundary enforces that contract, and the engine's own docstring claims the alive map is the
liveness source of truth. A dropped/sparse score row is a plausible upstream condition (coast
gap, batch hiccup) that would cause an unwanted emergency cut off a live camera.

**Fix:** Decouple liveness from score presence. Treat "alive per map but no/eligible score this
tick" as live-but-uneligible-as-challenger rather than dead. E.g. compute a separate `_alive`
set from the alive map (independent of `score_by_cam`) and key `live_feed_dead()` off that:
```python
# liveness is the alive map (or all-alive when no map), NOT score presence
self._alive = (
    {cam for cam, ok in alive.items() if ok} if has_alive_map else set(self.cam_ids)
)
...
def live_feed_dead(self) -> bool:
    if self.target == SAFE_TARGET:
        return False
    return self.target not in self._alive
```
Keep `_alive_eligible` (score-bearing) for challenger/argmax selection only.

### WR-02: Engine emits `reason="override_dead_fallback"` but the Decision contract never declares it

**File:** `src/segugio/decision/signals.py:66`, `src/segugio/decision/engine.py:569`
**Issue:**
`engine.py:569` emits `reason = "override_dead_fallback"`, and the scenarios test explicitly
expects it (`test_decision_scenarios.py:110` allows it in the no-change reason set). But the
`Decision.reason` docstring (signals.py:66) declares the legal set as
`"auto_switch" | "feed_emergency" | "hold" | "override" | "none"` — `override_dead_fallback` is
missing. A Phase-5 orchestrator that pattern-matches the documented reason set (the obvious way
to map reasons → OBS actions) would hit an unhandled value and mis-handle the forced-but-dead
fallback decision.

**Fix:** Add `"override_dead_fallback"` to the documented reason set in the `Decision` docstring
(signals.py:66), e.g.
`"auto_switch" | "feed_emergency" | "hold" | "override" | "override_dead_fallback" | "none"`.
Better still, promote the reason set to a `str` Enum (mirroring `Mode`) so the contract is
machine-checked rather than a comment.

### WR-03: Action-hold cap uses `<=`, so the force-release fires one tick LATER than the cap

**File:** `src/segugio/decision/engine.py:286-288`
**Issue:**
`holding()` computes `action_active = self._action_held_this_tick and (self.action_hold_age <= self.action_hold_cap_ticks)`.
Because `action_hold_age` is incremented to 1 on the first held tick (line 426) and the check is
`<=`, the hold stays active for ages `1..cap` (i.e. `cap` suppressed ticks) and only
force-releases at age `cap+1`. So with `action_hold_cap_ticks=5` the suppressed cut fires at the
6th held tick, not the 5th.

This is benign for the documented intent ("a stuck hold can never freeze the show") — it still
caps — but it is (a) off-by-one relative to a natural reading of "cap = N ticks", and (b)
asymmetric with the occlusion hold, which arms `remaining` and counts down to a strict
`remaining > 0` (line 289), giving exactly `bound` suppressed ticks. Two hold paths with
different boundary semantics is a maintenance hazard and makes the cap one tick "looser" than
configured.

**Fix:** Use a strict comparison so the cap means exactly `cap` suppressed ticks, matching the
occlusion path:
```python
action_active = self._action_held_this_tick and (self.action_hold_age < self.action_hold_cap_ticks)
```
(Confirm/adjust `test_decision_holds.py::test_action_hold_suppresses_and_caps`, whose
`cut_after_cap >= cap - 1` assertion tolerates either boundary.)

### WR-04: Ambiguous OverrideCmd (force_cam AND release both set) is resolved silently

**File:** `src/segugio/decision/engine.py:506-509`, `src/segugio/decision/signals.py:96-97`
**Issue:**
`tick()` checks `override.force_cam is not None` first, then `elif override.release`. An
`OverrideCmd(force_cam="cam_b", release=True)` therefore silently applies the force and ignores
the release, with no validation or log. `OverrideCmd` (signals.py:96-97) places no constraint on
the two fields being mutually exclusive. An operator UI sending a malformed/contradictory
command gets a silently-chosen branch — a latent footgun for the one human-in-the-loop affordance
in the system.

Reproduced: `force_cam="cam_b", release=True` → engine enters OVERRIDE on cam_b, release
discarded.

**Fix:** Make the contract explicit — reject the ambiguous combination at the input boundary,
e.g. a `__post_init__` on `OverrideCmd`:
```python
def __post_init__(self) -> None:
    if self.force_cam is not None and self.release:
        raise ValueError("OverrideCmd cannot set both force_cam and release")
```
(Keep `tick()` exception-free per T-3-04 by validating the command before calling `tick`, or
document the force-wins precedence explicitly if silent resolution is the deliberate choice.)

### WR-05: `feed_emergency` declares `source=["auto","override"]` but the `override` source is unreachable

**File:** `src/segugio/decision/engine.py:92-97, 539`
**Issue:**
The `feed_emergency` transition lists `"source": ["auto", "override"]`, but `tick()` only calls
`self.feed_emergency()` when `self.state in ("auto", "override") and not forced_this_tick and not in_override_no_command`
(line 539). While in OVERRIDE with no command, `in_override_no_command` is True → the call is
skipped; with a command, `forced_this_tick`/release handling owns the tick. After a `release`,
the state is already `auto` before line 539 runs. So `feed_emergency` can only ever fire from the
`auto` state — the `"override"` source is dead. This is misleading: a reader will believe
feed-death can emergency-cut directly from OVERRIDE (it cannot; the in-override reconciliation
path at lines 512-524 handles forced-but-dead instead).

**Fix:** Drop `"override"` from the `feed_emergency` source list (keep only `"auto"`) to match
actual reachability, OR add a clarifying comment that the override branch is intentionally
handled by the in-override reconciliation and the listed source is vestigial.

## Info

### IN-01: The `to_safe` transition is defined but never triggered (dead edge)

**File:** `src/segugio/decision/engine.py:80-86`
**Issue:** The `to_safe` transition exists in `_TRANSITIONS`, but `tick()` never calls
`self.to_safe()`. All SAFE routing happens via the `feed_emergency` → `_set_target_safe`
unless-edge (lines 100-107) and the override paths. Verified by grep: only `feed_emergency()`
and `auto_switch()` are fired in `tick()`. Dead transition graph edge.
**Fix:** Remove the `to_safe` transition, or wire it as the explicit cold-start/no-candidate
route and stop overloading `feed_emergency`'s SAFE edge for that purpose.

### IN-02: Stale 03-01-scoped docstring in `tick()` contradicts the shipped behavior

**File:** `src/segugio/decision/engine.py:399-405`
**Issue:** The `tick()` docstring still reads "fire the guarded trigger(s) — only `auto_switch`
this plan (override/feed-death/hold edges land in 03-02/03-03)". The full engine already
implements override, feed-death, and hold edges, so this is stale 03-01 text describing a state
the code has moved past. Misleads a reader about what `tick()` actually does.
**Fix:** Update the `tick()` docstring to describe the full priority ladder (override →
feed-death → auto_switch with hold suppression) as actually implemented.

### IN-03: Empty `scores` list silently emits `tick=0`

**File:** `src/segugio/decision/engine.py:407`
**Issue:** `tick_idx = scores[0].tick if scores else 0`. An empty `scores` list yields a
`Decision(tick=0, ...)` regardless of the real frame index. The FSM never raises (good,
T-3-04), but a downstream log/recorder keying on `Decision.tick` would see a spurious 0 on any
no-detections tick, corrupting the timeline. Reproduced: `eng.tick([])` → `Decision(tick=0, target="SAFE", reason="none")`.
**Fix:** Pass the current tick explicitly into `tick()` (it is the orchestrator's clock anyway)
rather than deriving it from `scores[0]`, so an empty batch still carries the correct index.

### IN-04: Unused import `SAFE_TARGET` in two test modules

**File:** `tests/test_decision_hysteresis.py:25`, `tests/test_decision_holds.py:24`
**Issue:** `from segugio.decision.signals import SAFE_TARGET` (hysteresis) and
`... import SAFE_TARGET, HoldInput` (holds) — `SAFE_TARGET` is imported but only
`test_cold_start_is_safe` in hysteresis uses it; in `test_decision_holds.py` `SAFE_TARGET` is
not referenced at all. Minor lint noise; not a correctness issue.
**Fix:** Drop the unused `SAFE_TARGET` import from `test_decision_holds.py`.

---

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
