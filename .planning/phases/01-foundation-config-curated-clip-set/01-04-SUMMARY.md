---
phase: 01-foundation-config-curated-clip-set
plan: 04
subsystem: synth
tags: [python, numpy, dataclasses, determinism, seeded-rng, generators, tst-02]

# Dependency graph
requires:
  - "01-01 — src-layout package, pythonpath=src, seeded_rng conftest fixture, import-smoke lazy-import guard"
provides:
  - "segugio.synth.score_stream(rng, scenario, cam_ids, n_ticks, noise) -> list[ScoreSample] + frozen ScoreSample dataclass"
  - "segugio.synth.feed_death(rng, cam_ids, n_ticks, death_at, recover_after) -> list[FeedEvent] + frozen FeedEvent dataclass"
  - "SCENARIOS tuple (ping_pong, tie, dropout, recovery) re-exported from segugio.synth"
  - "Deterministic, injected-RNG synthetic substrate the P2 scorer / P3 FSM / P5 watchdog are unit-tested against (no clip, no GPU, no NDI)"
affects: [02-framing-scorer, 03-decision-fsm, 05-feed-watchdog]

# Tech tracking
tech-stack:
  added: []
  patterns: [injected-seeded-rng, pure-base-curve+rng-jitter, frozen-dataclass-samples, synthetic-tick-time]

key-files:
  created:
    - src/segugio/synth/score_stream.py
    - src/segugio/synth/feed_death.py
  modified:
    - src/segugio/synth/__init__.py
    - tests/test_generators.py

key-decisions:
  - "Scenario base curve is a PURE function of (scenario, t, n_cams, n_ticks) — zero randomness; jitter is the ONLY rng draw (rng.normal once per tick in fixed cam order) → same seed yields byte-identical list[ScoreSample]"
  - "ping_pong uses a square-wave leader swap on a ~n_ticks/4 period so the argmax flips >= 2 times (FSM-must-not-chase shape); extra cameras pinned low so they never lead"
  - "dropout/recovery use index-based windows (n_ticks//3 boundaries) so the collapse/gap is asserted with tight epsilons (jitter stddev 0.02 << the 0.2 band) without flaking"
  - "feed_death explicit death_at/recover_after path is fully deterministic and reads NO randomness; rng kept in the signature only for parity with score_stream and any future random-death path"
  - "Reworded the score_stream docstring so the grep guard (np.random.seed|np.random.rand|time.time|datetime.now) reads 0 — the prohibition is explained without embedding the literal forbidden tokens"

requirements-completed: [TST-02]

# Metrics
duration: 3min
completed: 2026-06-09
---

# Phase 1 Plan 04: Deterministic Synthetic Generators Summary

**Seedable, injected-RNG `score_stream` (ping_pong / tie / dropout / recovery) and `feed_death` (death + recovery liveness timelines) generators — pure base curve + rng-only jitter, frozen dataclass samples, byte-identical output per seed — the hardware-free substrate the Phase-2 scorer, Phase-3 FSM, and Phase-5 watchdog are unit-tested against (TST-02).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-09T00:56:54Z
- **Completed:** 2026-06-09
- **Tasks:** 2
- **Files:** 2 created, 2 modified

## Accomplishments
- `score_stream(rng, scenario, cam_ids, n_ticks, noise=0.02)` — a frozen `ScoreSample(tick, cam_id, score)` plus the four named scenarios. A pure `_scenario_base()` computes the deterministic per-camera curve from indices only; jitter (`rng.normal(0.0, noise, size=n_cams)`) is the single randomness source, clipped to [0,1]. Unknown scenario → `ValueError`.
- `feed_death(rng, cam_ids, n_ticks, death_at=None, recover_after=None)` — a frozen `FeedEvent(tick, cam_id, alive)` plus a fully deterministic death/recovery liveness timeline (alive until death tick; dead after; alive again at death+recover_after). Mirrors the domain's NDI "fallen feed looks alive" gotcha — the watchdog's test target.
- `segugio.synth` re-exports `score_stream`, `ScoreSample`, `feed_death`, `FeedEvent`, `SCENARIOS`; numpy + stdlib `dataclasses` only (the 01-01 import-smoke boundary stays intact).
- 25-test `tests/test_generators.py` suite: same-seed-equal AND different-seed-different for both generators (explicit `default_rng` + the `seeded_rng` conftest fixture), bounds/length/tick-coverage, the four scenario shapes asserted structurally, parametrized feed-death boundaries (death-only + death+recovery + multi-cam single death), and the unknown-scenario `ValueError`.

## Task Commits

Each task was committed atomically:

1. **Task 1: score_stream + feed_death generators (injected RNG, deterministic)** — `7e52155` (feat)
2. **Task 2: determinism + scenario-shape + feed-death suite (TST-02)** — `e96a4bd` (test)

**Plan metadata:** final docs commit — see below.

_Note: Task 1 was marked `tdd="true"`. tdd_mode is off at the orchestrator level, so the MVP+TDD runtime gate did not apply; the RED→GREEN flow was still followed — a failing RED contract test was written first (9 ImportError failures), then the two generator modules were implemented to green, then Task 2 replaced the RED scaffold with the full suite._

## Files Created/Modified
- `src/segugio/synth/score_stream.py` — `ScoreSample` frozen dataclass + `score_stream()`; pure `_scenario_base()` helper (no rng) + rng-only jitter; `SCENARIOS` tuple; `ValueError` on unknown scenario.
- `src/segugio/synth/feed_death.py` — `FeedEvent` frozen dataclass + `feed_death()` deterministic liveness timeline.
- `src/segugio/synth/__init__.py` — re-exports the four public symbols + `SCENARIOS` (was an empty placeholder from 01-01).
- `tests/test_generators.py` — replaced the 01-01 skipped scaffold with the full 25-test TST-02 suite (no skips remain).

## Decisions Made
- **Pure base curve, single jitter draw:** the per-scenario shape is a deterministic function of `(scenario, t, n_cams, n_ticks)`; the only `rng` call is one `rng.normal(...)` per tick over the cameras in fixed order. This is what makes same-seed output byte-identical and keeps the generators reproducible under pytest parallelism (RESEARCH.md Pattern 4 / Pitfall 3).
- **Scenario shapes chosen to be assertable without flaking:** `dropout`/`recovery` use `n_ticks//3` index windows that collapse the leader to 0.0 base; with jitter stddev 0.02 the post-collapse max stays well under the 0.2 assertion band. `ping_pong` uses a ~`n_ticks/4` square-wave so the leader flips ≥ 2 times; `tie` holds both cameras within a <0.05 mean epsilon.
- **`feed_death` rng is signature-only:** the explicit `death_at`/`recover_after` path reads no randomness, so the timeline is identical across seeds (asserted). The `rng` parameter is kept for parity with `score_stream` and a future random-death path.
- **Docstring worded to satisfy the grep guard:** the acceptance criterion greps both modules for `np.random.seed|np.random.rand|time.time|datetime.now` and requires 0. The score_stream docstring originally explained the prohibition using those literal tokens (matching at count 1); it was reworded to state the prohibition without embedding the forbidden strings. No behavior change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docstring tripped the grep guard**
- **Found during:** Task 1 acceptance-criteria check.
- **Issue:** The score_stream module docstring explained the determinism prohibition with the literal phrase `NO np.random.seed / global np.random.*`, so the acceptance grep `np.random.seed|np.random.rand|time.time|datetime.now` returned count 1 instead of the required 0 — a documentation false-positive, not actual global-RNG usage.
- **Fix:** Reworded the docstring to state the same prohibition ("never seeds or calls the legacy global numpy RNG", "no wall-clock is read") without embedding the forbidden tokens. Re-ran the grep guard → 0 across both modules; suite still green.
- **Files modified:** `src/segugio/synth/score_stream.py`
- **Commit:** `7e52155` (fixed before the Task 1 commit was made)

---

**Total deviations:** 1 (Rule 3, doc-level, fixed inline before commit).
**Impact on plan:** None. Plan executed as written; all success criteria met.

## Issues Encountered
- None beyond the docstring grep false-positive above (resolved inline).

## Verification Evidence
- `python -m pytest tests/test_generators.py -q` → green, 25 passed, 0 skipped.
- Full Phase-1 suite (`python -m pytest -q`) → green, 94 passed, 0 skipped (no regression).
- `grep -Ec "np\.random\.seed|np\.random\.rand|time\.time|datetime\.now"` across both generator modules → 0.
- `python -c "import segugio.synth"` → OK (numpy-only; heavy deps absent, lazy-import boundary intact).
- Determinism one-liner (`score_stream(default_rng(7),...) == score_stream(default_rng(7),...)`) exits 0; feed-death boundary one-liner (`alive[3] and not alive[4]`) exits 0.
- Task 2 grep ACs: `default_rng|seeded_rng` = 26 (≥2); `ping_pong|tie|dropout|recovery` = 18 (≥4); `ValueError` = 2 (≥1).

## Threat Surface
No new security surface. Per the plan's threat model: T-01-04a (non-determinism) is **mitigated** — the injected `numpy.random.Generator` is the sole randomness source, the grep guard for global-RNG/wall-clock reads 0, and same-seed-equality tests enforce byte-reproducibility (correctness-as-security: a non-deterministic substrate would silently corrupt every downstream phase's test integrity). T-01-04b (unbounded inputs) and T-01-SC (numpy install) are accepted as planned; no fresh installs occurred. No threat flags raised.

## Known Stubs
None. Both generators are fully implemented (no placeholder values, no TODO/FIXME, no empty returns); all four scenarios and the death/recovery timeline produce real, asserted output.

## Next Phase Readiness
- The deterministic synthetic substrate is in place: Phase-2 scorer tests can feed `score_stream(...)` ping_pong/tie/dropout/recovery streams; Phase-3 FSM tests can assert no-flicker/hysteresis against the same; Phase-5 watchdog tests can assert liveness handling against `feed_death(...)` death/recovery timelines.
- All deterministic by construction — no global RNG, no wall-clock — so downstream unit tests are reproducible across runs and parallel workers.
- Run via the project `.venv` (`.venv/bin/python -m pytest`); the package is editable-installed there (from 01-01).

## Self-Check: PASSED

All 4 plan files present on disk (`score_stream.py`, `feed_death.py`, `synth/__init__.py`, `test_generators.py`); both task commits (`7e52155`, `e96a4bd`) exist in the repo. No missing items.

---
*Phase: 01-foundation-config-curated-clip-set*
*Completed: 2026-06-09*
