---
phase: 01-foundation-config-curated-clip-set
verified: 2026-06-09T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm real footage actually covers all 7 conditions x 2 disciplines after drop-in"
    expected: "Running 'python tools/catalog_clips.py <footage_dir>' shows no missing cells in the coverage gap report"
    why_human: "The footage is user-provided at execution time and is intentionally not on disk. The mechanism (cataloguer, manifest, coverage report, README) is complete and verified; actual coverage depends on what clips are supplied."
---

# Phase 01: Foundation, Config & Curated Clip Set — Verification Report

**Phase Goal:** The config contract and test substrate every later module depends on exist and validate — a central YAML schema plus the curated multi-condition clip set and synthetic stream generators that make all downstream work hardware-free and pitfall-revealing.
**Verified:** 2026-06-09
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Loading a malformed config.yaml fails fast at startup with a clear validation error; a well-formed one parses cameras+roles, per-camera normalized zone rects, framing_weights[role][zone], all switching thresholds, and the YOLO model path + class index | VERIFIED | `load_config(config.example.yaml)` returns a typed `Config` with all fields. 9-way parametrized invalid matrix asserts `SystemExit(2)`. 36/36 tests pass in `test_config.py`. |
| 2 | Switching the discipline selector (disc dog / agility) in config changes overlay field set and framing defaults with zero code edits | VERIFIED | `FieldProfile = Annotated[DiscDogProfile \| AgilityProfile, Field(discriminator="sport")]` in `discipline.py`. Both example configs load and produce different `overlay_fields`/`framing_defaults`. `-k discipline` subset passes (6 tests). |
| 3 | tests/fixtures/ contains the curated clip-set infrastructure spanning the 7-condition checklist for both disciplines, with a cataloguer mechanism, coverage gap report, and license README | VERIFIED (mechanism) | `tools/catalog_clips.py` (argparse CLI, lazy cv2, `coverage_report` integration), `src/segugio/fixtures.py` (CONDITIONS, DISCIPLINES, load_manifest, select_clips, coverage_report), `tests/fixtures/README.md` (license table, ingest procedure), `tests/fixtures/clip_manifest.example.yaml` (3 entries, both disciplines). 20/20 tests pass. Real footage is intentionally deferred per documented design — see Human Verification. |
| 4 | Synthetic generators produce deterministic score-stream and feed-death sequences that the scorer, FSM and watchdog can be unit-tested against without any clip or hardware | VERIFIED | `score_stream(default_rng(7), ...) == score_stream(default_rng(7), ...)` (same-seed equality). `feed_death` produces exact alive/dead tick boundaries. No global RNG or wall-clock used (grep confirms 0). `import segugio.synth` succeeds without heavy deps. 25/25 tests pass. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Installable package metadata, pinned deps, `[tool.pytest.ini_options]` | VERIFIED | Contains `[tool.pytest.ini_options]` with `pythonpath = ["src"]`, `testpaths = ["tests"]`, `addopts = "-q"` |
| `requirements.txt` | Pinned dependency manifest | VERIFIED | `pydantic==2.13.4`, `numpy==2.4.6`, `loguru==0.7.3`, `ultralytics==8.4.62` confirmed; no `torch` pin |
| `src/segugio/__init__.py` | Package root with no heavy top-level imports | VERIFIED | Defines `__version__ = "0.1.0"`. Zero heavy imports (grep=0 for torch/ultralytics/cyndilib/obsws) |
| `src/segugio/logging.py` | configure_logging() loguru bootstrap | VERIFIED | `def configure_logging(level, *, force)` with idempotent module-level guard; light deps only |
| `tests/conftest.py` | Shared fixtures: seeded_rng, tmp_config, valid_config_dict | VERIFIED | All three fixtures present. `SEED = 1234`. `valid_config_dict` deep-copied per request. |
| `tests/test_imports.py` | Import-smoke test proving lazy-import boundary | VERIFIED | Parametrizes over `["segugio", "segugio.config", "segugio.synth", "segugio.logging"]` with `sys.modules` poisoning for all 4 heavy deps. 13 tests pass. |
| `src/segugio/config/models.py` | Pydantic v2 Config root with zone-weight cross-validator | VERIFIED | `class Config(BaseModel)` with `model_validator(mode="after")` enforcing CFG-02 typo guard and is_safe requirement. Confirmed via grep (3 occurrences of `model_validator`) and running tests. |
| `src/segugio/config/discipline.py` | Discipline discriminated union | VERIFIED | `discriminator="sport"` present. `DiscDogProfile \| AgilityProfile`. |
| `src/segugio/config/loader.py` | load_config(path) -> Config with safe_load | VERIFIED | `yaml.safe_load` used. `yaml.load(` count = 0. Raises `SystemExit(2)` on all failures. |
| `config.example.yaml` | Disc dog reference config | VERIFIED | Loads: `field.sport == 'disc_dog'`, `any(cam.is_safe)` = True |
| `config.agility.example.yaml` | Agility reference config | VERIFIED | Loads: `field.sport == 'agility'`, different `overlay_fields` than disc dog |
| `tests/test_config.py` | Parametrized valid/invalid + zones + discipline + model tests | VERIFIED | 36 tests, all passing. `grep -Ec "parametrize\|pytest\.raises"` = 12 (>= 2). No skipped placeholder. |
| `src/segugio/fixtures.py` | Manifest loader + query helpers + checklist constants | VERIFIED | Exports `load_manifest`, `select_clips`, `coverage_report`, `resolve_clip_path`, `CONDITIONS`, `DISCIPLINES`, `FixtureNotPresentError`. `midfield_equidistant` and `tunnel_contact_occlusion` present (count=4). `yaml.load(` = 0. No cv2 import. |
| `tools/catalog_clips.py` | Dev cataloguer with argparse CLI, lazy cv2 probe | VERIFIED | `import cv2` inside `probe()` (count=1). `argparse` + `add_argument` (count=6). No hardcoded absolute footage path. |
| `tests/fixtures/README.md` | License/consent doc + drop-location/ingest procedure | VERIFIED | Contains `## License`. Documents ingest procedure referencing `tools/catalog_clips.py`. No hardcoded absolute paths (grep=0). |
| `tests/fixtures/clip_manifest.example.yaml` | Example manifest schema | VERIFIED | 3 entries spanning both `disc_dog` and `agility` disciplines. Parses via `load_manifest`. |
| `tests/test_fixtures_catalogue.py` | Cataloguer + manifest-query + coverage-report tests | VERIFIED | 20 tests passing. opencv-absent import proof via subprocess. No skipped placeholder. |
| `src/segugio/synth/score_stream.py` | score_stream + ScoreSample dataclass | VERIFIED | Frozen `ScoreSample` dataclass. Four named scenarios. `SCENARIOS` tuple. `ValueError` on unknown scenario. |
| `src/segugio/synth/feed_death.py` | feed_death + FeedEvent dataclass | VERIFIED | Frozen `FeedEvent` dataclass. Fully deterministic on explicit `death_at`/`recover_after` path. |
| `src/segugio/synth/__init__.py` | Re-exports of generator functions + dataclasses | VERIFIED | Exports `score_stream`, `ScoreSample`, `feed_death`, `FeedEvent`, `SCENARIOS`. |
| `tests/test_generators.py` | Determinism + scenario-shape + feed-death tests | VERIFIED | 25 tests passing. `default_rng\|seeded_rng` = 26. `ping_pong\|tie\|dropout\|recovery` = 18. `ValueError` = 2. No skipped placeholder. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_imports.py` | `src/segugio` (config, synth, logging surface) | `sys.modules` poisoning + `importlib.import_module` | WIRED | Parametrized over 4 Phase-1 modules with all 4 heavy deps blocked |
| `pyproject.toml [tool.pytest.ini_options]` | `src/` layout | `pythonpath = ["src"]` | WIRED | Confirmed in pyproject.toml |
| `src/segugio/config/loader.py` | pyyaml + pydantic Config | `yaml.safe_load -> Config.model_validate` | WIRED | Both patterns confirmed. `safe_load` count >= 2. No bare `yaml.load`. |
| `src/segugio/config/models.py Config` | `src/segugio/config/discipline.py FieldProfile` | `field: FieldProfile` discriminated union | WIRED | `FieldProfile` imported from `.discipline` and used as `field: FieldProfile` in `Config`. |
| `tests/test_config.py` | `config.example.yaml` + `config.agility.example.yaml` | `load_config(path)` on both, overlay_fields compared | WIRED | Both example configs exercised in discipline tests. |
| `tools/catalog_clips.py` | opencv `cv2.VideoCapture` | lazy `import cv2` inside `probe()` | WIRED | `import cv2` at line 79, inside function body. |
| `src/segugio/fixtures.py select_clips` | clip manifest | `yaml.safe_load` + filter | WIRED | `load_manifest` uses `yaml.safe_load`. `select_clips` filters `manifest.get("clips", [])`. |
| `tools/catalog_clips.py coverage report` | 7-condition x 2-discipline checklist | imports `segugio.fixtures.coverage_report` | WIRED | Cataloguer imports `coverage_report` from the package; single source of truth confirmed in summary. |
| `src/segugio/synth/score_stream.py` | `numpy.random.Generator` | injected `rng` parameter (never global) | WIRED | `rng.normal(...)` is the sole RNG call. Global RNG grep = 0. |
| `tests/test_generators.py` | `score_stream` + `feed_death` | same-seed equality + different-seed inequality | WIRED | `default_rng\|seeded_rng` = 26 occurrences. Both same-seed-equal and different-seed-different asserted. |

### Data-Flow Trace (Level 4)

Not applicable — Phase 1 delivers pure logic modules and test infrastructure with no UI components rendering dynamic data. All outputs are programmatic (typed Python objects, YAML files). No dynamic rendering path to trace.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Package imports cleanly | `.venv/bin/python -c "import segugio; import segugio.config; import segugio.synth; import segugio.logging; print('OK')"` | OK | PASS |
| ModelConfig defaults to yolo26s.pt/16 | `.venv/bin/python -c "from segugio.config.models import ModelConfig; m=ModelConfig(); assert str(m.path)=='yolo26s.pt' and m.class_index==16; print('OK')"` | OK | PASS |
| Example disc_dog config loads with is_safe | `.venv/bin/python -c "from segugio.config import load_config; c=load_config('config.example.yaml'); print(c.field.sport, any(cam.is_safe for cam in c.cameras))"` | `disc_dog True` | PASS |
| Example agility config loads with correct sport | `.venv/bin/python -c "from segugio.config import load_config; c=load_config('config.agility.example.yaml'); print(c.field.sport)"` | `agility` | PASS |
| Determinism: same seed -> identical score_stream | `.venv/bin/python -c "import numpy as np; from segugio.synth import score_stream; a=score_stream(np.random.default_rng(7),'ping_pong',['a','b'],50); b=score_stream(np.random.default_rng(7),'ping_pong',['a','b'],50); assert a==b; print('OK')"` | OK | PASS |
| feed_death correct alive/dead tick boundaries | `.venv/bin/python -c "import numpy as np; from segugio.synth import feed_death; e=feed_death(np.random.default_rng(0),['a'],10,death_at={'a':4}); alive={ev.tick:ev.alive for ev in e if ev.cam_id=='a'}; assert alive[3] and not alive[4]; print('OK')"` | OK | PASS |
| segugio.fixtures importable without opencv | `.venv/bin/python -c "import sys; sys.modules['cv2'] = None; import segugio.fixtures; print('OK')"` | OK | PASS |
| Full test suite | `.venv/bin/python -m pytest -v` | 94 passed in 0.35s | PASS |

### Probe Execution

No `probe-*.sh` scripts declared or found in this phase. Step 7c skipped — no probe files exist.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CFG-01 | 01-02 | Malformed config.yaml fails fast; well-formed config parses into typed object with all schema fields | SATISFIED | Loader raises `SystemExit(2)`. 9-way parametrized invalid matrix. `test_config.py` 36 tests pass. |
| CFG-02 | 01-02 | Normalized [0..1] zone rects; out-of-range rejected; `framing_weights[role][zone]` cross-validated; typo'd zone rejected at startup | SATISFIED | `Zone` field_validator enforces ordering and [0,1]. `model_validator` cross-checks every camera zone against framing_weights. `-k zones` 5 tests pass. |
| CFG-03 | 01-02 | Discipline selector changes overlay fields + framing defaults with zero code edits | SATISFIED | `FieldProfile` discriminated union on `sport`. `DiscDogProfile`/`AgilityProfile` with different `overlay_fields` defaults. `-k discipline` 6 tests pass. |
| CFG-04 | 01-02 | Model path + class_index configurable; defaults to yolo26s.pt/16; YAML-overridable | SATISFIED | `ModelConfig` defaults `Path("yolo26s.pt")`/`16`. `-k model` 12 tests pass. Override round-trip tested. |
| TST-01 | 01-03 | Curated clip set mechanism: cataloguer, manifest, coverage gap report, license README | SATISFIED | `tools/catalog_clips.py`, `src/segugio/fixtures.py`, `tests/fixtures/README.md`, `tests/fixtures/clip_manifest.example.yaml`. 20 tests pass. Coverage gap report proven on empty dir. |
| TST-02 | 01-04 | Deterministic score-stream (ping_pong/tie/dropout/recovery) + feed-death; same seed -> byte-identical | SATISFIED | Both generators proven deterministic by same-seed-equal tests. Four scenarios structurally verified. Feed-death tick boundaries asserted. 25 tests pass. |

**Orphaned requirements from REQUIREMENTS.md for Phase 1:** None. All 6 (CFG-01..04, TST-01, TST-02) are claimed by plans and verified.

### Anti-Patterns Found

No debt markers (TBD/FIXME/XXX) found in any source file. No TODO/HACK/PLACEHOLDER markers found. No empty implementations (`return null`, `return {}`, `return []`) that represent stubs — all empty returns are either type defaults with upstream population (e.g., `data["clips"] = []` normalizing a missing manifest key) or intentional empty-dir behavior (cataloguer on zero footage). The `feed_death` `rng` parameter is intentionally unused on the explicit path (documented, no `pass` stub).

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

### Human Verification Required

ROADMAP success criterion 3 states: "tests/fixtures/ contains the curated clip set spanning multi-dog, handler-prominent, tunnel/contact occlusion, jump/sprint blur, distant, backlit/dusk and midfield-equidistant conditions for both disc dog and agility, with a license README."

The **mechanism** (cataloguer, manifest schema, coverage report, README with ingest procedure) is fully implemented and verified. The **actual footage** is deliberately user-provided at execution time (documented design decision in CONTEXT.md and explicitly noted in VALIDATION.md "Manual-Only Verifications"). No automated check can verify whether real clips have been dropped in, since the binaries are gitignored by design.

#### 1. Clip Coverage Verification

**Test:** Drop competition/stock footage into `tests/fixtures/disc_dog/` and `tests/fixtures/agility/`. Write a `<clip>.tags` sidecar per clip. Run `python tools/catalog_clips.py <footage_dir> --out tests/fixtures/clip_manifest.yaml`.

**Expected:** Coverage gap report shows all 7 conditions covered for both disciplines (14 cells = True). If cells are missing, the report names them explicitly so you know what CC0 clips to supplement from Pexels/Pixabay.

**Why human:** Footage is user-provided, intentionally gitignored, and not present in a fresh checkout. This is the documented design (external-dir + committed-manifest pattern). The cataloguer mechanism is verified; the coverage depends on what clips the user supplies.

---

## Gaps Summary

No gaps. All 4 ROADMAP success criteria are satisfied at the code and test level. The single human verification item is an intentional design constraint (user-provided footage), not a code deficiency. The VALIDATION.md explicitly lists it under "Manual-Only Verifications" with the same rationale.

---

_Verified: 2026-06-09_
_Verifier: Claude (gsd-verifier)_
