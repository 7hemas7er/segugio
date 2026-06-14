---
phase: 01-foundation-config-curated-clip-set
plan: 01
subsystem: infra
tags: [python, src-layout, pydantic, pytest, loguru, numpy, packaging, lazy-import]

# Dependency graph
requires: []
provides:
  - "Installable src/segugio/ package skeleton (src-layout, editable-installable)"
  - "requirements.txt (deliverable) + pyproject.toml with identical runtime pins, torch excluded"
  - "configure_logging() — idempotent single-sink loguru bootstrap"
  - "tests/conftest.py shared fixtures: seeded_rng, tmp_config, valid_config_dict"
  - "Import-smoke test proving the lazy-import boundary (heavy deps absent)"
  - "Wave-0 test scaffolds test_config.py / test_fixtures_catalogue.py / test_generators.py"
  - "[tool.pytest.ini_options] pythonpath=src — the test substrate downstream plans run against"
affects: [01-02-config, 01-03-clip-set, 01-04-generators, all-phase-1-plans]

# Tech tracking
tech-stack:
  added: [pydantic==2.13.4, pyyaml==6.0.3, numpy==2.4.6, loguru==0.7.3, pytest==9.0.3, pytest-cov==7.1.0]
  patterns: [src-layout, lazy-import-boundary, injected-seeded-rng, idempotent-bootstrap, external-dir+committed-manifest]

key-files:
  created:
    - pyproject.toml
    - requirements.txt
    - .gitignore
    - src/segugio/__init__.py
    - src/segugio/config/__init__.py
    - src/segugio/synth/__init__.py
    - src/segugio/logging.py
    - tests/conftest.py
    - tests/test_imports.py
    - tests/test_config.py
    - tests/test_fixtures_catalogue.py
    - tests/test_generators.py
  modified: []

key-decisions:
  - "Editable install (pip install -e .) so `python -c 'import segugio'` works outside pytest, not only via pythonpath=src"
  - "Created a .venv (gitignored) for the light Phase-1 deps because the system has no `python` on PATH and no pre-existing venv"
  - "configure_logging() uses a module-level guard + logger.remove() to guarantee exactly one sink (idempotent)"
  - "valid_config_dict shaped to the 01-02 schema (safe main_wide cam, near/mid/far zones, long cam, full framing_weights matrix, disc_dog field, thresholds, model) so 01-02 reuses it as the canonical happy-path"

patterns-established:
  - "Lazy-import boundary: Phase-1 modules import nothing heavy; an import-smoke test forces torch/ultralytics/cyndilib/obsws_python absent and asserts the surface still imports"
  - "Injected seeded numpy.random.Generator via the seeded_rng fixture (no global RNG, no wall-clock) — the determinism baseline for TST-02"
  - "External-dir + committed-manifest fixtures: .gitignore ignores video binaries under tests/fixtures/ but negates README.md and clip_manifest.yaml"

requirements-completed: [TST-02]

# Metrics
duration: 4min
completed: 2026-06-09
---

# Phase 1 Plan 01: Foundation Scaffolding Summary

**Installable src/segugio/ package with pinned requirements.txt + pyproject.toml (torch-free), an idempotent loguru bootstrap, shared pytest fixtures (seeded_rng/tmp_config/valid_config_dict), and an import-smoke test that proves the Phase-1 lazy-import boundary holds with torch/ultralytics/cyndilib/obsws absent.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-09T00:29:35Z
- **Completed:** 2026-06-09T00:34:xx Z
- **Tasks:** 2
- **Files created:** 12 (plus a gitignored .venv for light deps)

## Accomplishments
- src-layout package `src/segugio/` with `__version__` and empty `config/` + `synth/` placeholders, editable-installed so it imports anywhere.
- `requirements.txt` (the brief deliverable) and a minimal `pyproject.toml` carry identical runtime pins (pydantic/pyyaml/numpy/loguru); the heavy/lazy stack is declared but not installed/imported; torch is intentionally excluded.
- `configure_logging()` — an idempotent single-sink loguru bootstrap (light import only).
- `tests/conftest.py` shared fixtures `seeded_rng` (deterministic numpy Generator), `tmp_config` (YAML writer factory), and `valid_config_dict` (canonical disc_dog config 01-02 reuses).
- `tests/test_imports.py` proves the lazy-import boundary: with the four heavy modules forced absent, the whole Phase-1 surface still imports. Plus logging-idempotency and fixture-determinism self-checks (13 passing assertions).
- Wave-0 scaffolds (`test_config.py`, `test_fixtures_catalogue.py`, `test_generators.py`) exist and collect, each with one skipped placeholder for 01-02/03/04 to fill.

## Task Commits

Each task was committed atomically:

1. **Task 1: Package skeleton, pinned dependency manifests, pytest config** - `d450626` (feat)
2. **Task 2: loguru bootstrap, shared conftest fixtures, import-smoke test, Wave-0 test scaffolds** - `e18e80f` (feat)

**Plan metadata:** (final docs commit — see below)

_Note: Task 2 was marked `tdd="true"`. tdd_mode is off at the orchestrator level, so the MVP+TDD runtime gate did not apply; the RED→GREEN flow was still followed (failing import/logging tests written first, then `logging.py` implemented to green)._

## Files Created/Modified
- `pyproject.toml` - setuptools src-layout package metadata, runtime/dev/heavy dep groups, `[tool.pytest.ini_options]` with `pythonpath=["src"]`, `testpaths`, `addopts="-q"`.
- `requirements.txt` - pinned runtime + dev + heavy-lazy deps (grouped, commented); no torch pin.
- `.gitignore` - Python build artifacts, `.venv/`, and the fixture-binary ignore (`tests/fixtures/**/*.{mp4,mov,avi,mkv,...}`) with `!README.md` / `!clip_manifest.yaml` negations.
- `src/segugio/__init__.py` - package root, `__version__ = "0.1.0"`, no heavy imports.
- `src/segugio/config/__init__.py`, `src/segugio/synth/__init__.py` - empty placeholders for 01-02 / 01-04.
- `src/segugio/logging.py` - `configure_logging(level="INFO", force=False)` idempotent loguru bootstrap.
- `tests/conftest.py` - `seeded_rng`, `tmp_config`, `valid_config_dict` fixtures + module-level `SEED=1234`.
- `tests/test_imports.py` - lazy-import boundary guard, logging idempotency, fixture self-checks.
- `tests/test_config.py`, `tests/test_fixtures_catalogue.py`, `tests/test_generators.py` - Wave-0 skipped scaffolds.

## Decisions Made
- **Editable install** (`pip install -e .`): the acceptance criteria call `python -c "import segugio"` directly, which `pythonpath=src` (a pytest-only setting) does not satisfy. An editable install makes the package importable everywhere. The egg-info is gitignored.
- **`.venv` for light deps**: the box has no `python` on PATH (only `python3`) and no pre-existing virtualenv. Per the environment note, a venv was created and only the LIGHT Phase-1 deps (pydantic, pyyaml, numpy, loguru, pytest, pytest-cov) were installed so the acceptance pytest commands pass. No heavy GPU/NDI deps were installed. The venv is gitignored.
- **Idempotent logging via guard + `logger.remove()`**: removing all handlers before adding one, behind a module-level flag, guarantees exactly one sink no matter how many times `configure_logging()` is called.

## Deviations from Plan

### Sequencing observation (not a code change)

**1. [Sequencing] Task 1 `--collect-only` exit code**
- **Found during:** Task 1 verification.
- **Issue:** The Task 1 acceptance criterion expects `python -m pytest --collect-only -q` to exit 0, but pytest returns exit 5 ("no tests collected") when zero test items exist — and Task 1 creates no test files (Task 2 does). Exit 5 is *not* a collection error (that would be exit 2); collection itself succeeded.
- **Resolution:** No code change. The instant Task 2 added the test files, `--collect-only` returned exit 0 (verified). This is a plan-internal sequencing artifact between the two tasks, not a defect — the plan-level success criterion ("collection succeeds even before tests exist") is met.
- **Files modified:** none.

---

**Total deviations:** 0 code deviations (1 sequencing observation, no fix required).
**Impact on plan:** None. Plan executed essentially as written; all success criteria met.

## Issues Encountered
- **No `python` / no test deps on the box:** resolved by creating a gitignored `.venv` and installing only the light Phase-1 deps (documented above). All plan verify commands were run via `.venv/bin/python` and pass.

## Verification Evidence
- `python -m pytest -q` → green: `sss.............` (3 skipped Wave-0 placeholders + 13 passing).
- `import segugio` (+ `.config`/`.synth`/`.logging`) succeeds in a subprocess with `torch/ultralytics/cyndilib/obsws_python` forced to `None` in `sys.modules`.
- `requirements.txt` and `pyproject.toml` runtime pins identical; `grep '^torch'` empty in both.
- `git check-ignore`: `tests/fixtures/clip_x.mp4` ignored; `README.md` and `clip_manifest.yaml` NOT ignored.

## Threat Surface
No new security surface beyond the plan's threat model. The only trust boundary is PyPI installs (T-01-SC, accepted — light, universally-known packages). The lazy-import boundary (T-01-01) is now actively enforced by `tests/test_imports.py`, exactly as the mitigation prescribed. torch (T-01-02) remains unpinned/uninstalled/unimported.

## User Setup Required
None - no external service configuration required. (Heavy GPU/NDI deps are deferred to later phases; Phase 1 runs CPU-only.)

## Next Phase Readiness
- The src-layout, pytest substrate, shared fixtures, and Wave-0 scaffolds are in place. Plans 01-02 (config), 01-03 (clip set), 01-04 (generators) have a known file to populate and a green harness to verify against.
- `valid_config_dict` already encodes the 01-02 config shape (safe cam, zones, framing_weights matrix, disc_dog field, thresholds, model) — 01-02 can reuse it as its canonical happy-path.
- **Note for downstream agents:** run tests via the project `.venv` (`.venv/bin/python -m pytest`) or any env with the pinned light deps; the package is editable-installed there.

## Self-Check: PASSED

All 12 plan files created and present on disk; both task commits (`d450626`, `e18e80f`) exist in the repo. No missing items.

---
*Phase: 01-foundation-config-curated-clip-set*
*Completed: 2026-06-09*
