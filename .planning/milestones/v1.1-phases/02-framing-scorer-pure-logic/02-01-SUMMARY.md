---
phase: 02-framing-scorer-pure-logic
plan: 01
subsystem: scoring
tags: [pydantic, numpy, dataclasses, framing-scorer, gaussian, ema, z-score, synth-generator]

# Dependency graph
requires:
  - phase: 01-foundation-config-curated-clip-set
    provides: "typed pydantic Config (Role/Thresholds/framing_weights/FramingDefaults), frozen-dataclass + injected-rng determinism convention (score_stream/feed_death), conftest seeded_rng/valid_config_dict, lazy-import boundary"
provides:
  - "frozen DetectionSignal (scorer input, TRK-03 field set) + CameraScore (output) + ScorerStatus enum (segugio.framing.signals)"
  - "8 pure scoring term functions: gaussian_centeredness, gaussian_size_band, base_score, lead_room_target, zone_of, gate, conf_norm_step, plausibility_ok (segugio.framing.terms)"
  - "ScorerParams pydantic sub-model — 19 bounded tuning seeds incl. positive eps divisor floor — wired additively into Config.scoring, re-exported from segugio.config"
  - "detection_stream synthetic generator (raw DetectionSignal|None sequences with dropout/conf_bias/path knobs) re-exported from segugio.synth"
  - "scorer_params conftest fixture; 8 tests/test_framing_*.py files (base+shadow green, 6 skip-scaffolded for 02-02/03/04)"
affects: [02-02-base-ema-lead-conf-zone, 02-03-coast-ttl, 02-04-purity-gate, 04-yolo-tracker-wiring]

# Tech tracking
tech-stack:
  added: []   # no new packages — numpy/pydantic/pytest already vetted in Phase 1
  patterns:
    - "Pure-logic terms: numpy-only, divisor-guarded (max(w*h,0), h>0, sqrt(var+eps)), np.clip + float()-cast on exit, no rng/clock/I-O"
    - "Additive pydantic sub-model with bounded tuning-seed fields + cross-field @model_validator (w_c+w_s+w_conf==1)"
    - "Synthetic generator emitting None for dropout (coast/TTL substrate) — distinct from final-score score_stream"
    - "Wave-0 skip-scaffold: fix the test-file surface once; later plans remove the pytestmark skip and fill the body"

key-files:
  created:
    - src/segugio/framing/signals.py
    - src/segugio/framing/params.py
    - src/segugio/framing/__init__.py
    - src/segugio/framing/terms.py
    - src/segugio/synth/detection_stream.py
    - tests/test_framing_base.py
    - tests/test_framing_shadow.py
    - tests/test_framing_zone.py
    - tests/test_framing_ema.py
    - tests/test_framing_leadroom.py
    - tests/test_framing_confnorm.py
    - tests/test_framing_coast.py
    - tests/test_framing_purity.py
  modified:
    - src/segugio/config/models.py
    - src/segugio/config/__init__.py
    - src/segugio/synth/__init__.py
    - config.example.yaml
    - config.agility.example.yaml
    - tests/conftest.py

key-decisions:
  - "D-01 centeredness-dominant weights (w_c=0.5/w_s=0.3/w_conf=0.2, sum 1) enforced as a validated ScorerParams invariant (@model_validator)"
  - "D-02 size band is a Gaussian over sqrt(area) peaking at ideal_size (non-monotonic), proven by test_size_band_peak"
  - "eps is a bounded ScorerParams field (gt=0, default 1e-6), the sqrt(var+eps) conf-norm divisor floor — never hardcoded in terms.py"
  - "ScorerParams lives in segugio.framing.params; config.models imports it (arrow config→framing, never reverse) to avoid an import cycle"
  - "eps declared as Annotated[float, Field(gt=0.0)] (project Thresholds convention) rather than the plan's literal `eps: float = Field(...)` grep shape — same positive-bounded semantics"

patterns-established:
  - "Pure scoring term: pure docstring + divisor guard + np.clip + float()-cast; zero rng/clock/I-O"
  - "Additive ScorerParams sub-model: ConfigDict(extra=forbid), bounded Field on every seed, cross-field validator, default_factory in Config (non-breaking)"
  - "detection_stream: injected-rng-only, None for dropout, path-guard ValueError — the raw-detection analog of score_stream"

requirements-completed: [FRM-01, FRM-07]

# Metrics
duration: 14min
completed: 2026-06-09
---

# Phase 2 Plan 01: Framing-scorer pure substrate Summary

**Frozen DetectionSignal/CameraScore records, 8 numpy-only scoring term functions (Gaussian centeredness + non-monotonic size band + clipped EMA z-score conf-norm + lead-room + zone gate + plausibility guard), an additive 19-field ScorerParams config sub-model, and a deterministic detection_stream generator — the pure substrate 02-02/03/04 compose.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-09T15:13Z (approx)
- **Completed:** 2026-06-09T15:27Z
- **Tasks:** 3
- **Files modified:** 19 (13 created, 6 modified)

## Accomplishments
- Frozen `DetectionSignal` (TRK-03 field set, so a Phase-4 YOLO row maps unchanged), `CameraScore`, and `ScorerStatus` enum — stdlib-only, comparable for the `==` determinism assertion.
- 8 pure scoring terms with divisor guards and clip-on-exit; FRM-01 (centeredness decay, non-monotonic size-band peak, resolution-invariance) and the plausibility guard proven green at the pure-function level.
- `ScorerParams` (19 bounded tuning seeds incl. the positive `eps` conf-norm divisor floor) wired additively into `Config.scoring`, present in both example YAMLs, re-exported from `segugio.config`, fail-fast on bad values (T-2-03 mitigated). The D-01 `w_c+w_s+w_conf==1` invariant is a validated `@model_validator`.
- `detection_stream` deterministic raw-detection generator (with `None` dropout windows) re-exported from `segugio.synth`.
- Full suite: 105 passed, 6 skipped (the 6 Wave-0 scaffolds owned by 02-02/03/04); no regression of the 94 Phase-1 tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Frozen records + ScorerParams config wiring + YAMLs + fixture + zone stub** — `db41e10` (feat)
2. **Task 2: Pure term functions + FRM-01 base test + shadow/plausibility guard test** — `57fec05` (feat)
3. **Task 3: detection_stream generator + synth re-export + 5 skip-scaffold tests** — `d0aa8d1` (feat)

_TDD note: Task 2 was authored RED (tests importing the absent terms.py fail) → GREEN (terms.py implemented, base+shadow pass). Tasks 1 and 3 verified via the config/import suite and inline determinism checks._

## Files Created/Modified
- `src/segugio/framing/signals.py` — frozen DetectionSignal/CameraScore + ScorerStatus (stdlib only).
- `src/segugio/framing/params.py` — ScorerParams (19 bounded seeds, weights-sum-to-1 validator).
- `src/segugio/framing/terms.py` — 8 pure scoring term functions.
- `src/segugio/framing/__init__.py` — re-exports the substrate symbols.
- `src/segugio/synth/detection_stream.py` — deterministic raw-detection generator.
- `src/segugio/config/models.py` — `scoring: ScorerParams = Field(default_factory=ScorerParams)`.
- `src/segugio/config/__init__.py`, `src/segugio/synth/__init__.py` — re-exports (ScorerParams, detection_stream).
- `config.example.yaml`, `config.agility.example.yaml` — identical `scoring:` seed block.
- `tests/conftest.py` — `scorer_params` fixture.
- `tests/test_framing_base.py`, `tests/test_framing_shadow.py` — green (FRM-01 + guard).
- `tests/test_framing_{zone,ema,leadroom,confnorm,coast,purity}.py` — skip-scaffolds owned by 02-02/03/04.

## Decisions Made
- **eps as a bounded config field, not a literal** (CONTEXT `<specifics>`): `eps: Annotated[float, Field(gt=0.0)] = 1e-6` in `ScorerParams`, passed into `conf_norm_step`'s `sqrt(var+eps)`. Used the project's `Annotated[float, Field(...)]` `Thresholds`-style declaration rather than the plan's literal `eps: float = Field(...)` grep shape — identical positive-bounded semantics, consistent with the existing config models.
- **ScorerParams home = `segugio.framing.params`**, imported by `config.models` (dependency arrow config → framing, never the reverse) — keeps the framing layer lower and avoids an import cycle (`framing.signals`/`params` never import `synth` or `config`).
- **Task 2 `test_resolution_invariant` builds DetectionSignal sequences directly** via a small local helper rather than calling `detection_stream` (Task 3's artifact). This keeps Task 2 self-contained at its commit boundary; the helper emits the identical normalized shape `detection_stream` produces. See Deviations (Rule 3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 2 base test decoupled from the Task 3 generator**
- **Found during:** Task 2 (FRM-01 base test authoring)
- **Issue:** The plan's `<interfaces>` has `test_framing_base.py::test_resolution_invariant` consume `detection_stream`, but `detection_stream` is created in Task 3. Importing it in the Task 2 test would make the Task 2 commit fail in isolation (the per-task green-at-commit contract).
- **Fix:** Added a small local `_linear_right_seq(rng, ...)` helper in `test_framing_base.py` that builds the identical normalized `DetectionSignal` sequence directly (same `0.2 + 0.6*frac` rightward path, injected-rng-only jitter). The resolution-invariance assertion (`scores(seq) == scores(seq)`) is unchanged and equally strong.
- **Files modified:** tests/test_framing_base.py
- **Verification:** `pytest tests/test_framing_base.py tests/test_framing_shadow.py -x -q` green at the Task 2 commit; full suite green after Task 3.
- **Committed in:** `57fec05` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** No scope change. Preserves the per-task commit-isolation contract; the resolution-invariance behavior asserted is identical to the plan's intent. `detection_stream` is still delivered in Task 3 and exercised by the full suite.

## Issues Encountered
None — the substrate is greenfield additive pure code; the 94-test Phase-1 baseline stayed green throughout.

## User Setup Required
None — no external service configuration required. Phase 2 installs no new packages (all deps vetted in Phase 1).

## Threat Flags
None — no new network endpoints, auth paths, file access, or trust-boundary schema beyond the plan's `<threat_model>` (the additive `scoring:` YAML block is the one new config-boundary surface, already covered by T-2-03 and validated fail-fast).

## Known Stubs
The 6 skip-scaffolded test files (`test_framing_{zone,ema,leadroom,confnorm,coast,purity}.py`) are **intentional** Wave-0 contract stubs, each `pytest.mark.skip`-ed with a reason naming the owning plan (02-02/03/04). They are not data-flow stubs — they fix the test-file surface so later plans fill bodies without re-touching the file list. This is the plan's explicit substrate shape (see `<objective>` scope note); no plan goal is blocked.

## Next Phase Readiness
- 02-02 can compose base+EMA+lead+conf-norm+zone: it has `DetectionSignal`/`CameraScore`/`ScorerStatus`, all 8 terms, `ScorerParams` (incl. `eps`, `vel_window`, `beta`, `z_clip`, `warmup`), `detection_stream`, and the `scorer_params` fixture — and fills `test_framing_{zone,ema,leadroom,confnorm}.py`.
- 02-03 fills `test_framing_coast.py` (TTL countdown over `ttl_seconds`/fps → `ttl_ticks`); 02-04 fills `test_framing_purity.py` and adds `segugio.framing` to the import-smoke `PHASE1_SURFACE`.
- No blockers. The FRM-07 lazy-import boundary already holds (verified: `import segugio.framing` + `import segugio.synth.detection_stream` with torch/ultralytics/cyndilib absent).

## Self-Check: PASSED

All 13 created files and the SUMMARY exist on disk; all 3 task commits (db41e10, 57fec05, d0aa8d1) are in the git log. Full suite: 105 passed, 6 skipped (no regression of the 94-test Phase-1 baseline).

---
*Phase: 02-framing-scorer-pure-logic*
*Completed: 2026-06-09*
