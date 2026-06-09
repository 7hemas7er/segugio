---
phase: 01-foundation-config-curated-clip-set
plan: 02
subsystem: config
tags: [python, pydantic, pydantic-v2, yaml, discriminated-union, validation, fail-fast, loguru]

# Dependency graph
requires:
  - phase: 01-01
    provides: "src-layout package skeleton, pytest config (pythonpath=src), conftest fixtures (valid_config_dict, tmp_config, seeded_rng), empty src/segugio/config/ placeholder"
provides:
  - "Typed pydantic v2 Config root validating the full ARCHITECTURE.md schema (field/cameras/zones/framing_weights/thresholds/model)"
  - "load_config(path) -> Config — fail-fast loader (yaml.safe_load only; SystemExit(2) + loguru on any read/parse/validation error)"
  - "Discipline discriminated union FieldProfile (DiscDogProfile | AgilityProfile on field.sport) — zero-code-edit overlay/framing swap"
  - "ModelConfig with yolo26s.pt / class_index 16 defaults, YAML-overridable (CFG-04)"
  - "Cross-validator: every camera-referenced zone weighted in framing_weights[role] + >=1 is_safe camera"
  - "config.example.yaml (disc_dog) + config.agility.example.yaml (agility) reference configs"
  - "tests/test_config.py — 36 CFG-01..04 cases incl. parametrized invalid matrix"
affects: [01-03-clip-set, 01-04-generators, 02-framing-scorer, 03-decision-engine, 05-obs-orchestrator]

# Tech tracking
tech-stack:
  added: []  # all deps already pinned/installed in 01-01 (pydantic, pyyaml, loguru)
  patterns: [single-typed-config-root, discriminated-union-discipline-swap, normalized-zone-rects, model_validator-cross-check, safe_load-only-loader, fail-fast-SystemExit]

key-files:
  created:
    - src/segugio/config/models.py
    - src/segugio/config/discipline.py
    - src/segugio/config/loader.py
    - config.example.yaml
    - config.agility.example.yaml
  modified:
    - src/segugio/config/__init__.py
    - tests/test_config.py

key-decisions:
  - "Used Field(default_factory=...) for mutable list/sub-model defaults in the discipline profiles and Config (pydantic v2 best practice; avoids shared-mutable-default footguns)"
  - "Loader catches both (OSError, yaml.YAMLError) and ValidationError, mapping every failure to SystemExit(2) with a loguru-logged aggregated message (CFG-01 single fail-fast contract)"
  - "model.path kept as pathlib.Path (never shell-interpolated) per threat T-01-02c path-injection mitigation"
  - "Example configs use the exact ARCHITECTURE.md Part 3 framing_weights matrix and Part 5 OBS scene names (CAM Wide/Long/Low/Handler) so they are the documented contract, not throwaway fixtures"

patterns-established:
  - "Single typed Config root: one BaseModel aggregates every nested concept; consumers use attribute access, never dict-walking"
  - "Discipline as a discriminated union on field.sport: pydantic selects the sub-model; no consumer branches on `if sport ==` (CFG-03)"
  - "Normalized [0..1] image-space zone rects with field_validator ordering (x0<x1, y0<y1) — resolution-independent (ARCHITECTURE.md Option A)"
  - "model_validator(mode=after) cross-check turns config typos (unweighted zone) and missing SAFE camera into startup ValidationErrors, not silent scoring-time bugs"
  - "Loader uses yaml.safe_load exclusively (never yaml.load) — PyYAML RCE mitigation (threat T-01-02a)"

requirements-completed: [CFG-01, CFG-02, CFG-03, CFG-04]

# Metrics
duration: 5min
completed: 2026-06-09
---

# Phase 1 Plan 02: Config Contract Summary

**Typed pydantic v2 Config schema (cameras/zones/framing_weights/thresholds/model) with a fail-fast safe_load loader, a DiscDogProfile|AgilityProfile discriminated union that swaps overlay fields + framing defaults on field.sport with zero code edits, and two documented example configs (disc dog + agility) proving the swap from real files — CFG-01..04 covered by 36 passing tests.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-09T00:37:30Z
- **Completed:** 2026-06-09T00:42:xx Z
- **Tasks:** 2
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments
- `Config` root validates the entire ARCHITECTURE.md schema: `Role` enum, `Norm`-bounded `Zone` (4-element rect, ordered + [0..1]), `Camera` (extra=forbid, optional `ndi_source`), `ModelConfig` (yolo26s.pt/16), `Thresholds` (7 switching params with bounds), and a `framing_weights[Role][zone]` matrix.
- A `model_validator(mode="after")` cross-check fires at startup on a typo'd zone name (no `framing_weights[role]` entry) and on a config with no `is_safe` camera — CFG-02 typo guard + SAFE-fallback guard.
- `FieldProfile = Annotated[DiscDogProfile | AgilityProfile, Field(discriminator="sport")]` — switching `field.sport` selects a different `overlay_fields` set + `framing_defaults` with zero code branches (CFG-03). A bogus sport raises a discriminated-union error.
- `load_config(path)` reads via `yaml.safe_load` only, validates, and on ANY read/parse/validation failure logs the aggregated error via loguru and raises `SystemExit(2)` — a malformed config can never reach the live loop (CFG-01).
- Two documented reference configs: `config.example.yaml` (disc_dog, 4-cam rig, full framing_weights matrix, CAM Wide/Long/Low/Handler scenes) and `config.agility.example.yaml` (agility counterpart) — loading both and comparing `overlay_fields`/`framing_defaults` proves the discipline swap from real files.
- `tests/test_config.py`: 36 cases including a 9-way parametrized invalid-config matrix asserted against BOTH `Config.model_validate` (ValidationError) and `load_config` (SystemExit(2)). Full repo suite: 49 passed, 2 skipped (the skips are 01-03/01-04 placeholder scaffolds).

## Task Commits

Each task was committed atomically:

1. **Task 1: Config models + discipline discriminated union + loader** - `151c94b` (feat)
2. **Task 2: Example configs (disc dog + agility) + fail-fast & discipline-swap test suite** - `df76f04` (feat)

**Plan metadata:** (final docs commit — see below)

_Note: Task 1 was marked `tdd="true"`. tdd_mode is off at the orchestrator level, so the MVP+TDD runtime gate did not apply; the RED→GREEN flow was still followed in-process (model/zone/discipline/model-default tests written and confirmed failing on the missing imports, then models/discipline/loader implemented to green). RED and GREEN landed in one atomic `feat` commit per the per-task-commit contract._

## Files Created/Modified
- `src/segugio/config/models.py` - pydantic v2 models: `Role` enum, `Norm` annotated float, `Zone` (ordered rect validator), `Camera`, `ModelConfig`, `Thresholds`, and the `Config` root with the zone-weight + is_safe cross-validator.
- `src/segugio/config/discipline.py` - `FramingDefaults`, `DiscDogProfile`, `AgilityProfile`, and the `FieldProfile` discriminated union (`discriminator="sport"`).
- `src/segugio/config/loader.py` - `load_config(path) -> Config` via `yaml.safe_load` + `Config.model_validate`; fails fast with `SystemExit(2)` + loguru on read/parse/validation error.
- `src/segugio/config/__init__.py` - re-exports `load_config`, `Config`, `Role` (+ `Camera`, `Zone`, `ModelConfig`, `Thresholds`, discipline profiles).
- `config.example.yaml` - documented disc_dog reference config (ARCHITECTURE.md Part 3 schema, filled).
- `config.agility.example.yaml` - agility counterpart; only meaningful diff is `field.sport`, proving CFG-03.
- `tests/test_config.py` - replaced the Wave-0 skip with the full CFG-01..04 suite (valid, invalid matrix, zones, discipline, model).

## Decisions Made
- **`Field(default_factory=...)` for mutable defaults** (overlay_fields lists, FramingDefaults sub-models, Thresholds/ModelConfig in Config): the pydantic v2 idiom for non-shared mutable defaults; avoids the class-level shared-instance footgun the RESEARCH skeleton's bare `= [...]` / `= FramingDefaults(...)` would risk.
- **Single SystemExit(2) contract in the loader**: both the read/parse path and the validation path map to exit code 2, so callers (Phase-5 orchestrator) get one fail-fast signal regardless of why the config is bad (CFG-01).
- **Example configs are the contract, not throwaway fixtures**: they use the exact framing_weights matrix and OBS scene names from ARCHITECTURE.md Parts 3 & 5, so later phases (obs_controller, framing_scorer) can read them as the reference.

## Deviations from Plan

None - plan executed exactly as written. The RESEARCH.md code skeletons were followed with one idiomatic refinement (default_factory for mutable defaults, documented above as a decision, not a deviation — it is the correct pydantic v2 form of the same intent).

## Issues Encountered
None. The `valid_config_dict` conftest fixture from 01-01 matched the implemented schema exactly (including the optional `ndi_source` field being absent), so it served directly as the canonical happy-path base that the invalid cases mutate.

## Threat Surface
No new security surface beyond the plan's threat model. The two mitigations the threat register marks `mitigate` are both implemented and test-verified:
- **T-01-02a (PyYAML RCE):** loader uses `yaml.safe_load` exclusively; `grep -Ec "yaml\.load\(" loader.py` == 0 (acceptance-verified).
- **T-01-02b (malformed-config DoS):** loader fails fast with `SystemExit(2)` on every malformed case (9-way parametrized test asserts exit code 2).
- **T-01-02c (path injection):** `model.path` is a `pathlib.Path`, never shell-interpolated; existence/class-index verification is correctly deferred to Phase 4.

## User Setup Required
None - no external service configuration required. Config + loader run CPU-only with the light Phase-1 deps already installed in the gitignored `.venv`.

## Next Phase Readiness
- The config contract every later module consumes is locked and typed. 01-03 (clip set) and 01-04 (generators) can proceed independently; 02 (framing_scorer) can import `Config`/`Role` and the `framing_weights` matrix directly.
- `config.example.yaml` is the documented reference the Phase-5 OBS setup and the framing_scorer will read (scene names + weight matrix are the contract).
- Run tests via the project `.venv` (`.venv/bin/python -m pytest`); the package is editable-installed there.

## Self-Check: PASSED

All 5 created files + 2 modified files present on disk; both task commits (`151c94b`, `df76f04`) exist in the repo. Full suite 49 passed / 2 skipped. No missing items.

---
*Phase: 01-foundation-config-curated-clip-set*
*Completed: 2026-06-09*
