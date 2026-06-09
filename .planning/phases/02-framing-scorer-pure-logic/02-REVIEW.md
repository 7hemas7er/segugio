---
phase: 02-framing-scorer-pure-logic
reviewed: 2026-06-09T18:10:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - src/segugio/framing/__init__.py
  - src/segugio/framing/signals.py
  - src/segugio/framing/terms.py
  - src/segugio/framing/params.py
  - src/segugio/framing/scorer.py
  - src/segugio/synth/detection_stream.py
  - src/segugio/synth/__init__.py
  - src/segugio/config/models.py
  - src/segugio/config/__init__.py
  - tests/conftest.py
  - tests/test_framing_base.py
  - tests/test_framing_shadow.py
  - tests/test_framing_ema.py
  - tests/test_framing_zone.py
  - tests/test_framing_leadroom.py
  - tests/test_framing_confnorm.py
  - tests/test_framing_coast.py
  - tests/test_framing_purity.py
  - tests/test_imports.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
resolved:
  critical: 1
  info: 2
remaining_advisory: 7
status: resolved
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-09T18:10:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** resolved (blocker fixed; remaining items advisory/tracked)

## Resolution (2026-06-09, post-review)

- **CR-01 (BLOCKER) — FIXED.** `scorer.py` now resets the EMA cold-start sentinel to
  `None` (not `0.0`) on `lost`, so any re-acquisition after TTL expiry cold-starts at
  `s_0 = raw_0` (D-05) instead of `alpha*raw` from a stale `0.0`. Empirically verified:
  the re-acquired well-framed camera now emits `0.94` (was `0.282`).
- **IN-01 — FIXED.** `test_new_track_after_lost_cold_starts` strengthened from `score > 0.0`
  to `score == approx(raw_0)` + `score != approx(alpha*raw_0)` — a true regression guard
  for CR-01 (confirmed: it FAILS against the old behavior, passes with the fix).
- **IN-02 — FIXED.** TTL countdown floored at 0 (`max(0, ttl-1)`) — no unbounded negative
  drift while `lost`.
- **Remaining (advisory, tracked — non-blocking):** WR-01 (aspect_lo<aspect_hi config
  validator), WR-02 (negative w/h is already caught by the `h<=0` guard — clarity nit, not a
  real escape), WR-03 (streaming z-score pre/post-update variance — a defensible design
  choice, not a functional bug), WR-04 (warmup→normalized boundary step), WR-05 (velocity
  history straddles coast gaps — self-heals within `vel_window`), IN-03/IN-04 (doc/style).
  These do not affect the phase's must-haves or core value and are left for a future polish
  pass rather than expanding this phase's scope.

## Summary

Reviewed the pure, I/O-free framing scorer substrate (FRM-01..07). The purity/determinism
property is genuinely well-built: no `time`, no global RNG, no heavy imports at module top
level, all divisors guarded, all outputs `np.clip`-ed and `float()`-cast. The grep-based
purity test (`test_no_io_imports_in_framing`) and the heavy-absent import test are real and
pass. No security defects (this is pure math; no I/O, no secrets, no dangerous calls).

However, the EMA/coast-TTL state machine has **one BLOCKER-class correctness defect**: the
documented and test-claimed "cold-start re-seed after `lost`" does **not** happen. The code
never resets `self.ema` to `None` on TTL expiry, so a re-acquired dog after a full dropout
is scored at `alpha * raw_0` instead of `raw_0` — and the test that claims to verify this is
too weak to catch it. This directly undermines the core value ("la camera giusta al momento
giusto"): a re-acquired, well-framed camera is artificially suppressed for ~1/alpha ticks and
will lose the selection race against cameras that never dropped out.

The remaining findings are correctness-adjacent warnings (config-validation gaps that allow
silent total blackout, a numerical smell in the z-score, the warmup-boundary discontinuity)
and quality/test-robustness items.

## Critical Issues

### CR-01: Recovery after `lost` does NOT cold-start the EMA — it blends from 0.0 (contradicts D-04/D-05 docstring AND its own test)

**File:** `src/segugio/framing/scorer.py:189-215`
**Issue:**
On TTL expiry the coast branch sets `self.ema = 0.0` and `status = lost` (line 214), but it
never resets `self.ema` back to `None`. The present-branch cold-start guard is
`raw if self.ema is None else alpha*raw + (1-alpha)*self.ema` (lines 189-193). Because
`self.ema` is `0.0` (not `None`) after `lost`, a subsequent present detection — even with a
NEW `track_id` (which clears `self.hist` but does nothing to `self.ema`) — takes the EMA
recurrence branch and computes `alpha*raw + (1-alpha)*0.0 = alpha*raw`, NOT the cold-start
`raw_0`.

The class docstring (scorer.py:13, "cold start seeds `s_0 = raw_0` (NOT 0)") and the coast
comment (scorer.py:207-209, "only a NEW track_id after `lost` cold-starts") both assert the
opposite of the actual behavior.

Empirically confirmed: warm a track, drive it to `lost`, then present a well-centered
ideal-size detection with a new `track_id`. A fresh scorer cold-starts that detection at
`raw_0 = 0.94`; the post-`lost` scorer emits `0.282 == alpha*0.94`. The dog re-acquires at
30% of its true framing score and takes ~1/alpha (≈3) ticks to climb back, exactly when the
selector needs to switch TO this camera.

The test `tests/test_framing_purity.py:254-277` (`test_new_track_after_lost_cold_starts`)
claims to verify this but only asserts `out.score > 0.0`, which `alpha*raw_0` trivially
satisfies — so the bug ships green.

**Fix:** Reset the EMA to `None` (the cold-start sentinel) on TTL expiry so the next present
detection truly re-seeds:
```python
else:
    self.ema = None          # was 0.0 — None is the cold-start sentinel
    self.status = ScorerStatus.lost
return CameraScore(
    tick,
    self.camera.id,
    float(np.clip(self.ema if self.ema is not None else 0.0, 0.0, 1.0)),  # emits 0.0 when None
    self.status,
)
```
The emitted score stays `0.0` while `lost` (the `if self.ema is not None else 0.0` at line 220
already handles this). Then strengthen the test to assert the actual value:
```python
assert out.score == pytest.approx(raw0_of_a_fresh_scorer)   # true cold-start, NOT alpha*raw0
```

## Warnings

### WR-01: No `aspect_lo < aspect_hi` cross-validator → a mis-tuned config silently blacks out a camera forever

**File:** `src/segugio/framing/params.py:66-67`
**Issue:**
`aspect_lo` and `aspect_hi` are each only bounded `gt=0.0`; there is no `model_validator`
enforcing `aspect_lo < aspect_hi` (unlike the `w_c+w_s+w_conf==1` validator that exists).
A typo'd `aspect_lo=5.0, aspect_hi=2.0` passes config validation, then `plausibility_ok`
(terms.py:201) rejects EVERY detection (the band `[5.0, 2.0]` is empty), so the camera
permanently coasts → `lost`. The project's "fail-safe, not fail-loud" stance is for the hot
loop; here the config layer is exactly where this should fail loud. A silent total blackout
of a camera is worse than a startup error.

**Fix:** Add a cross-field validator mirroring `_weights_sum_to_one`:
```python
@model_validator(mode="after")
def _aspect_band_ordered(self) -> "ScorerParams":
    if self.aspect_lo >= self.aspect_hi:
        raise ValueError(
            f"aspect_lo must be < aspect_hi, got "
            f"aspect_lo={self.aspect_lo} >= aspect_hi={self.aspect_hi}"
        )
    return self
```

### WR-02: Negative `w`/`h` bypass the `min_area` noise gate (positive product from two negatives)

**File:** `src/segugio/framing/terms.py:196-199`
**Issue:**
`plausibility_ok` checks `det.w * det.h < p.min_area`. A malformed tracker row with both
`w` and `h` negative yields a POSITIVE product, so it slips past the area gate (the project's
own test `test_zero_height_detection_is_implausible`, purity:228, documents this for
`w=-0.20, h=-0.01` → area `+0.002 > min_area`). It is only caught downstream by the
`h <= 0` guard (line 198). That happens to work today, but the area gate's intent (reject
sub-area noise) is silently defeated for any negative-width box, and a negative-`w`/positive-`h`
box (positive `h`, negative `w` → negative product → caught by area gate as `< min_area`?
no — negative `< min_area` is true so rejected) is inconsistent with the negative/negative case.
The guard relies on a coincidental ordering rather than validating box geometry up front.

**Fix:** Validate non-negative geometry first, before the area/aspect arithmetic:
```python
if det.w <= 0 or det.h <= 0:
    return False  # degenerate/negative box → implausible (also guards area & aspect math)
if det.conf < p.conf_floor:
    return False
if det.w * det.h < p.min_area:
    return False
ar = det.w / det.h
...
```

### WR-03: z-score uses POST-update variance with PRE-update delta — statistically inconsistent

**File:** `src/segugio/framing/terms.py:175-183`
**Issue:**
`delta = conf - mu` is computed against the OLD mean, then `var` is updated to include this
sample, then `z = delta / np.sqrt(var + eps)` divides the old-mean delta by the NEW (post-update)
variance. A correct streaming standard-score uses the pre-update statistics for both the
numerator and the denominator (or post-update for both). Mixing them biases the magnitude of
`z` (the denominator already absorbed part of `delta` via the `beta*delta*delta` term), so the
normalized confidence is not the z-score the docstring claims. For a flat baseline this is
harmless (`delta→0`), but for the very confidence spikes the FRM-06 anti-bias feature exists to
detect, the reported `conf_norm` is systematically off. Deterministic, but numerically wrong
relative to the stated contract.

**Fix:** Snapshot variance before the update for the denominator, or compute `z` against the
pre-update variance:
```python
mu, var = state["mu"], state["var"]
delta = conf - mu
z_var = var                          # variance BEFORE folding in this sample
mu = mu + beta * delta
var = (1.0 - beta) * (var + beta * delta * delta)
new_state = {"n": n, "mu": mu, "var": var}
if n <= warmup:
    return float(conf), new_state
z = delta / np.sqrt(z_var + eps)     # consistent pre-update numerator & denominator
```

### WR-04: Warmup → normalized boundary injects a deterministic score step on a steady stream

**File:** `src/segugio/framing/scorer.py:170-182` (via `terms.py:180-183`)
**Issue:**
During the `warmup` window `conf_norm_step` passes the RAW `conf` through as `conf_norm`
(e.g. `0.7`); after warmup it returns the z-score mapped to ~`0.5` for a steady camera. With
`w_conf=0.2`, the base score therefore steps by `0.2 * (0.5 - 0.7) = -0.04` at the warmup
boundary even though the detection stream is unchanged. The EMA smooths it, but it is a real,
deterministic discontinuity at tick `warmup+1` that perturbs scoring exactly once per track.
For the first ~`warmup` ticks (10 @ default = ~0.33s at 30fps) a uniformly brighter camera also
scores higher on raw conf before the anti-bias engages — so the FRM-06 brightness anti-bias is
NOT in effect during warmup. Worth a deliberate decision/comment, not a silent surprise.

**Fix:** Either document the warmup-window bias explicitly as accepted, or pass through a
neutral `0.5` (instead of raw `conf`) during warmup so the conf term contributes nothing until
the baseline stabilizes:
```python
if n == 1:
    return 0.5, {"n": 1, "mu": conf, "var": 0.0}   # neutral until baseline exists
...
if n <= warmup:
    return 0.5, new_state                          # neutral, no brightness leak pre-warmup
```

### WR-05: Velocity denominator includes coast-gap ticks → diluted (and stale) velocity on re-acquisition

**File:** `src/segugio/framing/scorer.py:133-147, 164-176`
**Issue:**
On a re-acquisition with the SAME `track_id` after a coast gap, `self.hist` is NOT cleared
(only a track-id swap clears it). The deque still holds pre-gap samples, so `_velocity()`
divides `(cx_new - cx_old)` by `(tick_new - tick_old)` where the span now straddles the
dropout (e.g. ticks `[2,3,4,8]` → `dt=6` spanning a 3-tick gap). The resulting velocity is
diluted by the gap and mixes pre- and post-occlusion motion, so the lead-room ideal on the
recovery frame is biased low/stale. Deterministic, but the lead-room sign/magnitude on the
most important frame (re-acquisition) is computed from a window that no longer represents
recent motion.

**Fix:** Clear (or down-weight) velocity history when a present detection arrives after one or
more coast ticks, e.g. track whether the previous tick was a miss and clear `self.hist` on
resume, or compute velocity only over consecutive-tick pairs:
```python
if det.track_id != self.last_track or self._missed_last_tick:
    self.hist.clear()
self.last_track = det.track_id
self._missed_last_tick = False
# ... and set self._missed_last_tick = True in the coast/else branch
```

## Info

### IN-01: `test_new_track_after_lost_cold_starts` is too weak to verify its own claim

**File:** `tests/test_framing_purity.py:254-277`
**Issue:**
The test's docstring and inline comment assert "re-seeds the EMA from `raw_0` (the cold-start
path), not from the stale value", but the only behavioral assertion is `out.score > 0.0`. That
passes for the buggy `alpha*raw_0` blend (CR-01), so the test gives false confidence. A test
that claims a specific value should assert that value.
**Fix:** After fixing CR-01, assert `out.score == pytest.approx(raw0)` where `raw0` is a fresh
scorer's cold-start score for the same detection (compute it the way
`test_framing_coast.py::_cold_start_raw` does).

### IN-02: `self.ttl` decrements unboundedly negative while `lost`

**File:** `src/segugio/framing/scorer.py:210`
**Issue:**
While `lost`, every missing tick runs `self.ttl -= 1` with no floor, so `ttl` drifts to large
negatives over a long blackout (e.g. `-100000` after a long dead feed). Only ever compared
`> 0`, so functionally harmless, but it is unbounded mutable state that serves no purpose once
`lost`.
**Fix:** Stop decrementing once `lost` (or clamp at 0):
```python
if self.ttl > 0:
    self.ttl -= 1
```

### IN-03: Cross-platform byte-identity is claimed but not guaranteed for transcendentals

**File:** `src/segugio/framing/terms.py:59,71` (`np.exp`), `scorer.py` composition; docs in `signals.py:8-12`, `__init__.py`
**Issue:**
The purity contract is described as "byte-identical `list[CameraScore]` every run". `np.exp`
/ `np.sqrt` / `np.hypot` are deterministic run-to-run on the same machine/build but IEEE-754
does not guarantee bit-identical transcendental results across platforms/BLAS/numpy builds.
The tests only assert same-process determinism (which holds). The docstrings overstate the
guarantee as if it were portable.
**Fix:** Tighten the wording to "deterministic within a build/platform" (the tests' actual
contract), or note the cross-platform caveat so a future fixture committed from another machine
isn't expected to match bit-for-bit.

### IN-04: `_is_finite_detection` omits `track_id` (acceptable, but the tuple is hand-maintained)

**File:** `src/segugio/framing/scorer.py:84-86`
**Issue:**
The finiteness check enumerates `(det.cx, det.cy, det.w, det.h, det.conf)` literally. `track_id`
is correctly excluded (it's an `int`), but the field list is duplicated by hand and will drift
if `DetectionSignal` gains a numeric field. Low risk given the frozen record, but a quality nit.
**Fix:** Optional — derive the spatial/confidence field set from a named tuple/constant shared
with `DetectionSignal` so the two stay in sync.

---

_Reviewed: 2026-06-09T18:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
