---
phase: 02-framing-scorer-pure-logic
plan: 04
subsystem: testing
tags: [purity, determinism, lazy-import, source-grep, coverage, pytest, frm-07]

# Dependency graph
requires:
  - phase: 02-framing-scorer-pure-logic
    provides: "02-03: the complete CameraScorer (present + coast/TTL/lost paths), MultiCamScorer fan-out, and ttl_ticks_from_seconds — the full segugio.framing surface this plan proves pure/deterministic/I-O-free"
  - phase: 01-foundation
    provides: "01-01: tests/test_imports.py lazy-import boundary harness (HEAVY_MODULES, PHASE1_SURFACE, _force_heavy_absent); 01-04: the assert run(seq)==run(seq) byte-identical-list determinism convention"
provides:
  - "FRM-07 proven: feeding the same DetectionSignal sequence (with a dropout window → coast/lost) through two fresh CameraScorers yields byte-identical list[CameraScore] (determinism, frozen records)"
  - "test_no_io_imports_in_framing: a word-boundary source-grep over src/segugio/framing/*.py rejecting any import of time/np.random/os/socket/requests + every heavy dep (torch/ultralytics/cyndilib/obsws_python/cv2) — structural no-I/O/no-clock/no-RNG invariant"
  - "segugio.framing added to PHASE1_SURFACE in test_imports.py — the pure scorer is now in the proven lazy-import surface (auto-covered by the parametrized heavy-absent import-smoke), plus an explicit import-with-heavy-absent test in the purity file"
  - "Phase coverage gate closed: scorer.py/signals.py/terms.py/__init__.py at 100% (only params.py:80, the _weights_sum_to_one config-load ValueError, intentionally uncovered as a defensive validator); full suite 124 passed, 0 skipped"
affects: [03-fsm-switching, 04-yolo-tracker-wiring, 05-orchestrator-wiring, verify-work]

# Tech tracking
tech-stack:
  added: []   # no new packages — pytest/pytest-cov already vetted in Phase 1
  patterns:
    - "Source-grep purity gate: read each src/segugio/framing/*.py (resolved via the package __file__) and assert word-boundary regexes (^\\s*import time, \\bnp\\.random\\b, etc.) match nothing — NEW for this phase, distinguishes real imports from docstring prose so descriptive 'never torch/cyndilib' lines don't false-positive"
    - "Determinism over the WHOLE state machine: the determinism sequence carries a dropout window so present → coast → lost → recovery are all inside the byte-identical assertion (not a present-only run)"
    - "Lazy-import surface extension: appending a package to PHASE1_SURFACE auto-runs the existing parametrized heavy-absent import-smoke — single-sourced harness, no duplicated force-absent logic"
    - "Coverage-gate triage: add focused tests only for real reachable behavior branches (overlap highest-weight, h<=0 divisor guard, dt<=0 velocity guard, new-track-after-lost cold-start); document config-load defensive validators as intentionally-uncovered rather than contriving an invalid-Config test"

key-files:
  created: []
  modified:
    - tests/test_framing_purity.py
    - tests/test_imports.py

key-decisions:
  - "Word-boundary source-grep (not bare substring) so the no-I/O test correctly ignores docstring prose: src/segugio/framing/__init__.py:8 and signals.py:17 contain the descriptive words 'torch / ultralytics / cyndilib' in prose — these are NOT imports. The test anchors on ^\\s*import / ^\\s*from ... import and \\bnp\\.random\\b, so the structural invariant (no real I/O/clock/RNG/heavy import) is what is enforced. The plan's broad acceptance grep matches the prose; the actual code invariant holds (verified: only __future__/relative/typing/collections/dataclasses/enum/pydantic/math/numpy imports exist)."
  - "Determinism sequence includes a dropout=(20,30) window over 60 ticks with ttl_ticks=4 so the coast→lost→recovery branches are exercised inside the byte-identical CameraScore-list assertion — proving the WHOLE state machine deterministic, not just the present path."
  - "params.py:80 (_weights_sum_to_one ValueError) left intentionally uncovered: it is a Phase-1-style pydantic config-load cross-field validator that only fires on an invalid Config (w_c+w_s+w_conf != 1), unreachable via valid Config-passed data and out of this phase's scorer-behavior scope. Per the plan, documented here rather than tested with a contrived invalid config."

patterns-established:
  - "Purity gate trio (FRM-07): determinism (same seq → byte-identical CameraScore list) + source-grep no-I/O + import-with-heavy-absent — the template a future pure module copies to join the lazy-import surface"
  - "Reuse the test_imports HEAVY_MODULES / _force_heavy_absent helper across purity tests so the heavy-dep set is single-sourced"

requirements-completed: [FRM-07]

# Metrics
duration: 6min
completed: 2026-06-09
---

# Phase 2 Plan 04: FRM-07 Purity Gate + Lazy-Import Boundary Summary

**FRM-07 locked: the entire `segugio.framing` scorer is proven PURE, DETERMINISTIC, and I/O-FREE — the same `DetectionSignal` sequence (driven through present → coast → lost → recovery) yields byte-identical `CameraScore` lists across two fresh scorers; a word-boundary source-grep rejects any `time`/`np.random`/I/O/heavy import in `framing/*.py`; and `import segugio.framing` is now in the proven lazy-import surface (`PHASE1_SURFACE`), succeeding with torch/ultralytics/cyndilib/obsws_python forced absent — closing Phase 2 at 124 passed / 0 skipped, 99% framing coverage.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-06-09
- **Tasks:** 2
- **Files modified:** 2 (0 created, 2 modified)

## Accomplishments
- **FRM-07 determinism (`test_purity_determinism`):** built a 60-tick `detection_stream(np.random.default_rng(SEED), …, dropout=(20,30))` sequence (dropout window > `ttl_ticks=4`, so the coast→lost→recovery path is inside the check), fed it through TWO freshly-constructed `CameraScorer`s, and asserted the two `list[CameraScore]` are `==` (byte-identical — works because `CameraScore` is frozen). The synth input itself is asserted deterministic first (the precondition), and the run is asserted non-vacuous (a `coasting`/`lost` status actually occurs).
- **No-I/O source-grep (`test_no_io_imports_in_framing`):** enumerates every `src/segugio/framing/*.py` via the package `__file__` and asserts a set of **word-boundary** regexes match nothing — `^\s*import time`, `\bnp.random\b`, `^\s*import os/socket/requests`, and `import`/`from … import` of every `HEAVY_MODULES` name + `cv2`. This is NEW for the phase (no Phase-1 test greps source). Word-boundary anchoring is deliberate: it distinguishes real imports from docstring **prose** (the modules' descriptive "never torch / ultralytics / cyndilib" lines are not imports).
- **Lazy-import boundary (`test_imports.py` + `test_framing_imports_with_heavy_absent`):** appended `"segugio.framing"` to `PHASE1_SURFACE`, so the existing parametrized `test_phase1_surface_imports_with_heavy_deps_absent` now auto-covers `import segugio.framing` with the heavy runtime blocked. Added an explicit purity-file test that force-absents torch/ultralytics/cyndilib/obsws_python (`sys.modules[name]=None`), drops cached `segugio.*`, and asserts `importlib.import_module("segugio.framing")` returns a module exposing `CameraScorer`/`MultiCamScorer`.
- **Phase coverage gate closed (99% framing, 0 skips):** added four focused assertions for the real reachable branches the FRM-01..06 suites missed — `zone_of` overlap→highest-weight (`terms.py:130-131`) + missing-weight neutral-1.0 fallback; `plausibility_ok`'s `h<=0` divisor guard (`terms.py:199`, reached via a negative-dimension box with positive area); `_velocity`'s `dt<=0` divisor guard (`scorer.py:146`, T-2-01); and the new-`track_id`-after-`lost` EMA cold-start (D-04 boundary). Result: `scorer.py`/`signals.py`/`terms.py`/`__init__.py` all 100%; only `params.py:80` (a defensive config-load validator) uncovered.
- **Full suite green:** **124 passed, 0 skipped** (up from the 116/1 baseline — the purity scaffold's last skip is gone and the framing suite has zero remaining skips). Every FRM-01..07 VALIDATION.md behavior command passes in one run.

## Task Commits

Each task was committed atomically:

1. **Task 1: lock FRM-07 purity gate + add segugio.framing to lazy-import surface** — `c065904` (test)
2. **Task 2: close framing coverage gate to 99%** — `e57da5d` (test)

_TDD note: this is a test-locking plan — the implementation (the pure `segugio.framing` scorer) shipped in 02-01..02-03; this plan adds the FRM-07 purity/determinism/lazy-import assertions and the coverage-gate tests against that already-green surface, so the commits are `test(...)` only._

## Files Created/Modified
- `tests/test_framing_purity.py` — **modified.** Removed the `pytestmark = pytest.mark.skip` scaffold + the placeholder `test_purity_determinism` raise. Wrote the FRM-07 trio (`test_purity_determinism`, `test_no_io_imports_in_framing`, `test_framing_imports_with_heavy_absent`) plus four coverage-gate tests (`test_zone_overlap_picks_highest_weight`, `test_zero_height_detection_is_implausible`, `test_velocity_guards_nonpositive_tick_span`, `test_new_track_after_lost_cold_starts`). Reuses the `test_imports` `HEAVY_MODULES`/`_force_heavy_absent` helpers and the `test_framing_coast` single-full-frame-neutral-zone scorer construction convention.
- `tests/test_imports.py` — **modified.** Appended `"segugio.framing"` to `PHASE1_SURFACE` (the only change) — the existing parametrized heavy-absent import-smoke now covers the framing package.

## Decisions Made
- **Word-boundary source-grep over bare substring (so prose isn't a false positive):** the framing modules' docstrings contain descriptive prose like "never torch / ultralytics / cyndilib" and start-of-line "from the per-tick map …". A bare-substring grep (as in the plan's broad acceptance command) matches these; my test anchors on `^\s*import` / `^\s*from … import` and `\bnp.random\b`, enforcing the actual structural invariant (no real I/O/clock/RNG/heavy **import**). Verified at the command line that the only real imports in `framing/` are `__future__`, relative `.`, `typing`, `collections`, `dataclasses`, `enum`, `pydantic`, `math`, and `numpy`.
- **Determinism check spans the full state machine:** the `detection_stream` sequence carries a dropout window (longer than `ttl_ticks`) so present, coast, lost, and recovery are all inside the byte-identical `list[CameraScore]` assertion — not a present-only run.
- **`params.py:80` intentionally uncovered:** the `_weights_sum_to_one` `raise ValueError` is a config-load cross-field validator (Phase-1-style) reachable only by an invalid `Config`; per the plan's "do NOT add tests for unreachable defensive lines that cannot be triggered by valid Config-passed data", it is documented here rather than contrived.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added the `DetectionSignal` import to test_framing_purity.py**
- **Found during:** Task 2 (running the coverage-gate suite)
- **Issue:** The new coverage-gate tests construct `DetectionSignal(...)` directly, but the file's top-level import pulled in only `CameraScore` → `NameError: name 'DetectionSignal' is not defined`.
- **Fix:** Changed `from segugio.framing.signals import CameraScore` to `from segugio.framing.signals import CameraScore, DetectionSignal`.
- **Files modified:** tests/test_framing_purity.py
- **Verification:** the three failing coverage-gate tests turned green; full suite 124 passed, 0 skipped.
- **Committed in:** `e57da5d` (Task 2 commit)

**2. [Rule 2 - Missing test coverage for a named behavior branch] Re-targeted the `h<=0` guard test to actually reach terms.py:199**
- **Found during:** Task 2 (reading the term-missing report after the first coverage pass)
- **Issue:** My initial zero-height test (`h=0.0`) is caught by the earlier `min_area` gate (`w*h = 0 < 0.0004`, `terms.py:196`), so it never reached the explicit `h<=0` guard at `terms.py:199` (still flagged missing). The plan names the divisor guards as real branches to cover.
- **Fix:** Added a degenerate negative-dimension box (`w=-0.20, h=-0.01`) whose **positive** area (`0.002 > min_area`) slips past the conf-floor and min-area gates, so plausibility falls through to and is caught by the `h<=0` guard (which also guards the `w/h` aspect division). Kept the original zero-height end-to-end coast assertion too.
- **Files modified:** tests/test_framing_purity.py
- **Verification:** `terms.py` coverage rose to 100% (line 199 hit); `plausibility_ok(neg_box, …) is False`.
- **Committed in:** `e57da5d` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking import fix, 1 coverage-branch re-targeting).
**Impact on plan:** Both necessary to make the named coverage branches actually green. No scope change, no behavior change to any `src/segugio/framing/` module — this plan touches tests only.

## Issues Encountered
None beyond the two auto-fixed items above. The `segugio.framing` surface was already pure/deterministic/heavy-import-free as 02-01..02-03 built it, so the FRM-07 assertions passed first-try once written; the only friction was the missing test-file import and the min-area-vs-height-guard ordering in `plausibility_ok`.

## User Setup Required
None — no external service configuration. Phase 2 installs no new packages (pytest/pytest-cov vetted in Phase 1).

## Threat Flags
None — this plan adds no network endpoints, auth paths, file access, or trust-boundary schema; it adds **test assertions** that ENFORCE the plan's threat register. T-2-01 (hidden non-determinism — clock/RNG/global state) is mitigated by `test_purity_determinism` (byte-identical output) + `test_no_io_imports_in_framing` (source-greps out any `time`/`np.random`/I/O source) + the `_velocity` `dt<=0` divisor-guard test. T-2-03 (a heavy/I-O dep creeping into `framing/`) is mitigated by adding `segugio.framing` to `PHASE1_SURFACE` (heavy-absent import-smoke) + the source-grep rejecting every heavy import. T-2-SC (installs) — no new packages.

## Known Stubs
None. `test_framing_purity.py`'s skip scaffold is removed and the file is fully filled. There are zero `pytest.mark.skip` markers across all eight `tests/test_framing_*.py` files.

## Intentionally-Uncovered Lines
- `src/segugio/framing/params.py:80` — the `_weights_sum_to_one` `raise ValueError(...)`. A pydantic config-load cross-field validator (`w_c + w_s + w_conf != 1`); it fires only on an invalid `Config` and is unreachable via valid `Config`-passed data. Out of this phase's scorer-behavior scope (config validation belongs to the Phase-1 config layer). All other `segugio.framing` lines are covered (100% on `scorer.py`/`signals.py`/`terms.py`/`__init__.py`).

## Next Phase Readiness
- **Phase 2 is COMPLETE and ready for `/gsd:verify-work`:** all of FRM-01..07 are green; the full suite is 124 passed / 0 skipped; `segugio.framing` coverage is 99% (the single uncovered line is a documented defensive config-load validator).
- **Phase 3 (FSM):** consumes the deterministic `CameraScore.status ∈ {tracking, coasting, lost}` stream the now-purity-locked scorer emits; FRM-07 guarantees the FSM's unit tests on synthetic sequences are byte-reproducible across runs and parallel workers. The Phase-3 cross-dependency flagged in 02-02/02-03 (fixed EMA `alpha` tuned jointly with `debounce_N`/`min_dwell`/`hysteresis_margin`; the long expected-occlusion hold `hold_length_s` the scorer deliberately does NOT implement, D-04) still stands.
- **Phase 4/5:** map a YOLO+BoT-SORT result row → `DetectionSignal` (or `None`) and drive `MultiCamScorer.update(dets_by_cam, tick)`; the lazy-import boundary (now proven for `segugio.framing`) means the scorer imports and runs CPU-only before any GPU/NDI runtime is present.
- No blockers.

## Self-Check: PASSED

- `tests/test_framing_purity.py` exists and contains `def test_purity_determinism`, `def test_no_io_imports_in_framing`, and `def test_framing_imports_with_heavy_absent` (verified on disk).
- `tests/test_imports.py` has `"segugio.framing"` in `PHASE1_SURFACE` (verified).
- Both task commits are in `git log`: `c065904` (Task 1) and `e57da5d` (Task 2).
- Full suite: **124 passed, 0 skipped** (no regression; FRM-07 green; zero `pytest.mark.skip` across all `tests/test_framing_*.py`). Framing coverage 99% (only the documented `params.py:80` defensive validator uncovered).

---
*Phase: 02-framing-scorer-pure-logic*
*Completed: 2026-06-09*
