# Phase 1: Foundation, Config & Curated Clip Set - Research

**Researched:** 2026-06-09
**Domain:** Python project scaffolding · typed/validated YAML config · tagged video-fixture corpus · deterministic synthetic stream generators
**Confidence:** HIGH (config lib + stack versions verified on PyPI + Context7; clip-set/generator patterns MEDIUM-HIGH, synthesized from standard practice + project research docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Clip set source (01-03) — KEY DECISION**
- The curated clip set uses **REAL footage provided by the user** (their own / the community's), NOT generic CC0 stock.
- The footage **path will be provided at execution time** (not yet known at plan time). The plan must NOT hardcode a path — it should define the ingest/organization procedure and a documented place to drop the footage.
- The plan must: organize footage into `tests/fixtures/`, **catalogue** each clip against the condition checklist (multi-dog, handler-prominent, tunnel/contact occlusion, jump/sprint blur, distant, backlit/dusk, midfield-equidistant — for BOTH disc dog and agility), document **license/consent** in a `tests/fixtures/README.md`, and **flag missing conditions** (only those gaps get supplemented with CC0/web clips later).
- A catalogue manifest (e.g. a small YAML/CSV mapping clip → conditions/discipline) is desirable so later phases can select clips by condition.

**Tooling (01-01)**
- `requirements.txt` is a required deliverable (per brief). Provide it AND a minimal `pyproject.toml` for the installable package.
- Dev target: Python on a Linux + CUDA box. Pin the dependencies surfaced by research (ultralytics, cyndilib, obsws-python, transitions, opencv-python, numpy, pyyaml, loguru, watchdog) — but Phase 1 itself does not import the heavy GPU/NDI deps at runtime; keep heavy/optional deps importable lazily so config + generators run without a GPU.
- Logging via `loguru`.

**Config schema (01-02)**
- Schema already designed by research (see `.planning/research/ARCHITECTURE.md`). Structure: `field.{sport, event}`; `cameras[]` each `{role, obs_scene, is_safe, zones}` where `zones` are normalized [0..1] rects (named bands: near/mid/far/stage); `framing_weights[role][zone]` multiplier matrix; switching thresholds `alpha, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer`; model `path` + `class_index` (default `yolo26s.pt`, `dog=16`) — swappable; a `discipline` selector that switches overlay field set + framing defaults with ZERO code edits (CFG-03).
- Startup validation must **fail fast with a clear error** on malformed config (CFG-01).

**Code conventions**
- **OS-agnostic** code: no hardcoded OBS text input kinds (`text_gdiplus`/`text_ft2`), use `pathlib`, discover platform specifics at runtime. (Matters more in later phases but establish the convention now.)

### Claude's Discretion
- The config-validation library/approach (e.g. pydantic v2 vs dataclasses+jsonschema vs voluptuous) — research should recommend; pick the one giving the clearest fail-fast errors and a typed config object.
- Exact package/module layout under `src/segugio/` (research folder structure is a strong guide).
- Synthetic generator API shape (deterministic, seedable; emit score streams and feed-death events).

### Deferred Ideas (OUT OF SCOPE)
- Choice of reference organization (Skyhoundz/USDDN/UpDog for disc; AKC/UKC/FCI for agility) — affects only config VALUES (zone distances, score fields) used in Phase 5, not the Phase 1 schema. Defer.
- Real NDI/OBS/hardware — later milestone.
- Actual scorer/FSM/YOLO logic — Phases 2-5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-01 | Validated central YAML config, fail-fast on malformed input, with camera count/roles, field zones, discipline, and all thresholds (alpha, hysteresis_margin, min_dwell, debounce_N, cooldown, watchdog_timeout, track_buffer) | **Standard Stack → pydantic v2**; `## Code Examples → Config models + loader`; `## Validation Architecture → malformed-config rejection tests`. `ValidationError` aggregates ALL errors in one message → fail-fast with a clear report. |
| CFG-02 | Per-camera normalized [0..1] zone rects (named bands near/mid/far/stage) + `framing_weights[role][zone]` matrix | `## Code Examples → Zone & framing_weights models`; rect bounds + ordering enforced by `field_validator`; `framing_weights` keyed by `role` enum × `zone` name with a `model_validator` cross-check that every referenced zone name is weighted. |
| CFG-03 | Discipline selector swaps overlay fields + framing defaults with ZERO code edits | `## Architecture Patterns → Pattern 3: Discipline profile as discriminated union`; overlay field set + framing-default sub-config selected by `field.sport`/`field.event`. Switching is a YAML value change; no code path branches on a hardcoded discipline. |
| CFG-04 | Configurable YOLO model path + class index (default `yolo26s.pt`, `dog=16`), swappable without code edits | `## Code Examples → ModelConfig`; `path: Path` + `class_index: int` in config; STACK.md note that index must be re-verified against `model.names` at model-load time (Phase 4), not Phase 1. |
| TST-01 | Curated multi-condition clip set from REAL user footage, catalogued + license README | `## Architecture Patterns → Clip-set layout & manifest`; `## Don't Hand-Roll → metadata probing`; `## Environment Availability → ffprobe MISSING`. Manifest schema (YAML) maps clip → {discipline, conditions[], notes, source, license}; `tests/fixtures/README.md` for consent/license; cataloguer script + condition-coverage gap report. |
| TST-02 | Deterministic synthetic score-stream + feed-death generators | `## Architecture Patterns → Generator API (seedable, injected RNG)`; `## Code Examples → generators`; `## Validation Architecture → determinism tests`. Seeded `numpy.random.Generator` injected; scenarios ping-pong/tie/dropout/recovery + feed-death event sequences; no global RNG / no wall-clock. |
</phase_requirements>

## Summary

Phase 1 is a **pure-Python, hardware-free substrate** phase. It produces four deliverables that every later module consumes: (1) an installable `src/segugio/` package with pinned deps; (2) a typed, fail-fast-validated `config.yaml` contract; (3) a catalogued multi-condition video fixture corpus assembled from user-provided footage; (4) deterministic, seedable synthetic generators for score streams and feed-death events. Nothing here imports torch/ultralytics/cyndilib at runtime — those are declared in deps but lazily imported in later phases, so Phase 1 deliverables run and test on any machine with no GPU or NDI.

The single highest-leverage decision is the **config-validation library**. The choice is **pydantic v2** (verified current: 2.13.4 on PyPI). It uniquely satisfies all four config requirements at once: a *typed config object* (attribute access, IDE/type-checker support), *fail-fast aggregated errors* (one `ValidationError` lists every problem with a JSON-path `loc`), nested-model validation for `cameras[].zones[]` and `framing_weights[role][zone]`, cross-field checks via `model_validator`, and **discriminated unions** (`Field(discriminator=...)`) — the exact mechanism that lets a `discipline`/`sport` value swap overlay-field and framing-default sub-configs with zero code branches (CFG-03). dataclasses+jsonschema and voluptuous can validate but produce a *dict*, not a typed object, and give weaker nested/discriminated-union ergonomics.

**Primary recommendation:** Scaffold a `src/`-layout package with **pydantic v2** config models loaded from YAML via `yaml.safe_load` → `Config.model_validate(...)`; assemble the clip corpus as **external files + a YAML manifest** (do NOT commit large binaries — `git-lfs` is not installed and a manifest-over-external-dir pattern keeps the repo lean) catalogued by a small `ffprobe`-or-`opencv`-based cataloguer (note: `ffprobe` is NOT installed — see Environment Availability); and build generators as pure functions/classes that take an injected `numpy.random.Generator(seed)` — never the global RNG, never `time.time()`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Config schema + validation (CFG-01..04) | Application / Config layer (`segugio.config`) | — | Pure in-process validation at startup; no I/O beyond reading one YAML file. Owns the contract all other modules import. |
| Discipline → overlay/framing defaults swap (CFG-03) | Config layer (data-driven profile) | Score/Overlay layer (Phase 5 consumer) | The *selection* is config (a discriminated sub-model); the *consumption* (rendering overlay fields) is a Phase-5 concern. Phase 1 only defines the swappable schema. |
| Clip corpus + manifest (TST-01) | Test-fixture / data layer (`tests/fixtures/`) | Dev tooling (cataloguer script) | Fixtures are test data, not runtime code. The cataloguer is a one-shot dev tool that runs at ingest time, not in the live loop. |
| Synthetic generators (TST-02) | Test-support library (`segugio.testing` or `segugio.synth`) | Phase 2/3/5 unit tests (consumers) | Pure-logic, deterministic data producers. Must be importable by tests with zero heavy deps. Belongs in the package (importable) not in `tests/` (so any phase can import it). |
| Package scaffolding + deps (01-01) | Build / packaging tier (`pyproject.toml`, `requirements.txt`) | — | Defines the installable unit and the lazy-import boundary that keeps heavy deps out of Phase-1 runtime. |
| Logging setup (loguru) | Cross-cutting (application bootstrap) | — | A thin `segugio.logging` configuring loguru once; every module imports the configured logger. |

## Standard Stack

### Core
| Library | Version (verified PyPI 2026-06-09) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.13.4 `[VERIFIED: PyPI pip index]` `[CITED: docs.pydantic.dev]` | Typed config object + fail-fast validation (CFG-01..04) | De-facto Python data-validation standard. Single `ValidationError` aggregates all failures with JSON-path `loc`; nested models, `Field` constraints, `field_validator`/`model_validator`, and discriminated unions cover the entire config schema. Verified via Context7 (`/pydantic/pydantic`). |
| `pyyaml` | 6.0.3 `[VERIFIED: PyPI]` | Parse `config.yaml` and the clip manifest into dicts | Locked stack dep. Use `yaml.safe_load` only (never `load`). pydantic does the validation; pyyaml only parses. |
| `numpy` | 2.4.6 `[VERIFIED: PyPI]` | Seeded RNG for generators (`numpy.random.Generator`), score arrays | Locked stack dep. `default_rng(seed)` gives a reproducible, injectable RNG — the determinism backbone for TST-02. |
| `loguru` | 0.7.3 `[VERIFIED: PyPI]` | Structured logging across all modules | Locked decision. Configure once in a `segugio.logging` bootstrap; import the shared logger everywhere. |

### Supporting
| Library | Version (verified) | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.0.3 `[VERIFIED: PyPI]` | Test runner for all Phase 1 validation/determinism tests | Dev dependency. The framework the Validation Architecture targets. |
| `pytest-cov` | 7.1.0 `[VERIFIED: PyPI]` | Coverage measurement | Dev dependency. Optional but recommended to prove generator/config paths are exercised. |
| `ffprobe` (via system `ffmpeg`) OR `opencv-python` | ffmpeg system pkg / opencv 4.13.0.92 `[VERIFIED: PyPI]` | Probe clip metadata (resolution, fps, duration, codec) for the cataloguer | **`ffprobe` is NOT installed** (see Environment Availability). Two viable paths: install system `ffmpeg`, OR probe with `opencv-python` (already a locked dep) via `cv2.VideoCapture` properties. **Recommend opencv** for the cataloguer to avoid a new system dependency — `cv2.CAP_PROP_FRAME_WIDTH/HEIGHT/FPS/FRAME_COUNT` give what the manifest needs without ffprobe. |

### Locked Runtime Deps (declared now, NOT imported in Phase 1)
These are pinned in `requirements.txt`/`pyproject.toml` per the brief but are **lazily imported** in later phases. Phase 1 code must not import them at module top-level. Versions verified on PyPI 2026-06-09:

| Library | Version (latest verified) | Imported By Phase | Lazy-import note |
|---------|---------|-------------------|------------------|
| `ultralytics` | 8.4.62 `[VERIFIED: PyPI]` | Phase 4 | Pulls torch transitively (heavy). Import inside the yolo module's functions, never at package import. STACK.md: pin `ultralytics` new enough to resolve `yolo26s.pt`. |
| `cyndilib` | 0.1.1 `[VERIFIED: PyPI]` | Phase 5 | NDI bindings; needs libndi at runtime. Import inside ndi_ingest only. |
| `obsws-python` | 1.8.0 `[VERIFIED: PyPI]` | Phase 5 | obs-websocket v5 client. Import inside obs_controller only. |
| `transitions` | 0.9.3 `[VERIFIED: PyPI]` | Phase 3 | FSM library. Pure-Python (light) but still scope it to the FSM module. |
| `watchdog` | 6.0.0 `[VERIFIED: PyPI]` | Phase 5 | Filesystem watcher for score_manager. Import inside that module. |
| `opencv-python` | 4.13.0.92 `[VERIFIED: PyPI]` | Phase 4/5 (+ optional Phase 1 cataloguer) | Light enough to use in the Phase-1 cataloguer; still import lazily in the cataloguer function. |
| `torch` | (transitive via ultralytics) `[ASSUMED]` | Phase 4 | Do NOT pin torch directly in Phase 1 unless a specific CUDA build is required; let ultralytics pull it, or pin in a later phase with the CUDA index URL. Flag for Phase 4. |

### Alternatives Considered (config validation)
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **pydantic v2** | `dataclasses` + `jsonschema` (4.26.0) | jsonschema validates against a JSON Schema doc and reports errors, but you get a *plain dict* back, not a typed object — every consumer then does `cfg["cameras"][0]["role"]` with no autocomplete/type-check, and you maintain the schema separately from the dataclasses. Discriminated-union / cross-field logic is clumsy. Use only if a hard "no pydantic" constraint existed (it does not). |
| **pydantic v2** | `voluptuous` (0.16.0) | Lightweight schema-as-Python-dict validator; coerces and validates, but again yields a dict, has weaker nested-model ergonomics, no first-class discriminated unions, and a smaller ecosystem. Fine for flat configs; under-powered for this nested `cameras[].zones[]` + `framing_weights[role][zone]` + discipline-discriminator schema. |
| **pydantic v2** | `pydantic-settings` | A pydantic add-on for env-var/.env layering. Not needed — config is a single YAML file, not env-driven. Could be added later if env overrides are wanted; do not pull into Phase 1. |
| `yaml.safe_load` | `ruamel.yaml` (0.19.1) | Preserves comments/round-trips YAML. Only useful if the app must *rewrite* the user's YAML preserving formatting. Phase 1 only *reads* config → plain `pyyaml` is sufficient. |

**Installation:**
```bash
# Runtime (config + generators run with NO GPU/NDI):
pip install "pydantic==2.13.4" "pyyaml==6.0.3" "numpy==2.4.6" "loguru==0.7.3"

# Dev / test:
pip install "pytest==9.0.3" "pytest-cov==7.1.0"

# Heavy/optional (declared but lazily imported; install on the CUDA box):
pip install "ultralytics==8.4.62" "cyndilib==0.1.1" "obsws-python==1.8.0" \
            "transitions==0.9.3" "watchdog==6.0.0" "opencv-python==4.13.0.92"
```

**Version verification:** all versions above confirmed via `pip index versions <pkg>` on 2026-06-09 (Python 3.12.3 environment). pydantic v2 API patterns (discriminated unions, `model_validate`, `field_validator`/`model_validator`, `extra='forbid'`, `Field(ge=...,le=...)`) confirmed against Context7 `/pydantic/pydantic`.

## Package Legitimacy Audit

> slopcheck could NOT be installed in this environment (no network access to PyPI for install; `pip install slopcheck` unavailable). Per the graceful-degradation rule, packages discovered fresh this session are tagged `[ASSUMED]`. **However**, every package below is a pre-LOCKED dependency from the project's own TECHNICAL-RESEARCH.md / STACK.md (already vetted in prior research with HIGH confidence and source repos), OR is the canonical, ubiquitous tool for its job — not a fresh discovery. Registry existence + multi-year history + known source repos were confirmed via `pip index versions`.

| Package | Registry | Age / Maturity | Source Repo | slopcheck | Disposition |
|---------|----------|----------------|-------------|-----------|-------------|
| `pydantic` | PyPI | mature (v2 since 2023; v1 since 2017) | github.com/pydantic/pydantic | unavailable → `[ASSUMED]` but pre-vetted (Context7 confirms) | Approved |
| `pyyaml` | PyPI | mature (10+ yrs) | github.com/yaml/pyyaml | unavailable → `[ASSUMED]` (locked dep) | Approved |
| `numpy` | PyPI | mature (foundational) | github.com/numpy/numpy | unavailable → `[ASSUMED]` (locked dep) | Approved |
| `loguru` | PyPI | mature (7+ yrs) | github.com/Delgan/loguru | unavailable → `[ASSUMED]` (locked dep) | Approved |
| `pytest` | PyPI | mature (foundational) | github.com/pytest-dev/pytest | unavailable → `[ASSUMED]` | Approved |
| `pytest-cov` | PyPI | mature | github.com/pytest-dev/pytest-cov | unavailable → `[ASSUMED]` | Approved |
| `ultralytics` | PyPI | mature, very high downloads | github.com/ultralytics/ultralytics | unavailable → `[ASSUMED]` (locked dep, Context7-confirmed in STACK.md) | Approved (Phase 4 install) |
| `cyndilib` | PyPI | small but real (NDI bindings); newest 0.1.1 | github.com/nocarryr/cyndilib | unavailable → `[ASSUMED]` (locked dep) | Approved (Phase 5 install); low download count is expected for niche NDI bindings — verify source repo before install |
| `obsws-python` | PyPI | mature for its niche | github.com/aatikturk/obsws-python | unavailable → `[ASSUMED]` (locked dep) | Approved (Phase 5 install) |
| `transitions` | PyPI | mature (8+ yrs) | github.com/pytransitions/transitions | unavailable → `[ASSUMED]` (locked dep) | Approved (Phase 3 install) |
| `watchdog` | PyPI | mature | github.com/gorakhargosh/watchdog | unavailable → `[ASSUMED]` (locked dep) | Approved (Phase 5 install) |
| `opencv-python` | PyPI | mature (foundational) | github.com/opencv/opencv-python | unavailable → `[ASSUMED]` (locked dep) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none from registry data, but `cyndilib` has an inherently low download count (niche NDI binding, newest release 0.1.1) — the planner should add a `checkpoint:human-verify` before its Phase-5 install confirming the GitHub source repo `nocarryr/cyndilib` matches the locked-stack expectation. This is a Phase-5 concern; Phase 1 does not install it.

*Because slopcheck was unavailable, the planner should treat all installs as `[ASSUMED]` and may gate fresh installs behind a `checkpoint:human-verify`. The Phase-1 runtime set (`pydantic`, `pyyaml`, `numpy`, `loguru`, `pytest`, `pytest-cov`) are universally-known, low-risk packages and need no per-package checkpoint.*

## Architecture Patterns

### System Architecture Diagram

How Phase-1 deliverables produce/consume data (and how later phases consume them):

```
                    ┌─────────────────────────────────────────────────────────┐
   user-provided    │  CONFIG SUBSYSTEM (segugio.config)                       │
   config.yaml ─────┼─► yaml.safe_load() ──► dict ──► Config.model_validate()  │
                    │                                       │                  │
                    │            fail-fast ◄── ValidationError (all errors,    │
                    │          (clear startup error)         JSON-path loc)    │
                    │                                       │ ok               │
                    │                                       ▼                  │
                    │                              typed Config object ────────┼──► framing_scorer (P2)
                    │              (field, cameras[], zones[], framing_weights,│──► decision_engine (P3)
                    │               thresholds, model{path,class_index},       │──► obs_controller   (P5)
                    │               discipline-profile sub-config)             │──► orchestrator     (P5)
                    └─────────────────────────────────────────────────────────┘

   user footage      ┌────────────────────────────────────────────────────────┐
   dir (path given ──┼─► cataloguer (opencv probe) ──► clip_manifest.yaml ─────┼──► clip-selection by
   at run time)      │   tests/fixtures/<discipline>/<clip>     │ + README.md   │    {condition,discipline}
                     │                          condition-coverage gap report  │    (P2/P3/P4 eval)
                     └────────────────────────────────────────────────────────┘

   seed (int) ───────�Generators (segugio.synth)──────────────────────────────┐
                     │ score_stream(rng, scenario) ─► [(cam,t,score)...] ──────┼──► scorer/FSM tests (P2/P3)
                     │ feed_death(rng, events)     ─► [(cam,t,alive)...] ──────┼──► watchdog tests   (P3/P5)
                     │   injected numpy Generator → byte-identical per seed     │
                     └────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (`src`-layout)
```
segugio/
├── pyproject.toml              # installable package metadata + pinned deps + pytest cfg
├── requirements.txt            # required deliverable per brief (pins; mirrors pyproject runtime deps)
├── config.example.yaml         # documented reference config (the ARCHITECTURE.md schema, filled)
├── src/
│   └── segugio/
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── models.py       # pydantic models: Config, FieldProfile, Camera, Zone, Thresholds, ModelConfig, framing_weights
│       │   ├── loader.py       # load_config(path) -> Config : safe_load + model_validate + clear error formatting
│       │   └── discipline.py   # discipline/sport discriminated-union profiles (overlay fields + framing defaults)
│       ├── synth/
│       │   ├── __init__.py
│       │   ├── score_stream.py # deterministic score-stream generators (ping-pong/tie/dropout/recovery)
│       │   └── feed_death.py   # deterministic feed-death event generators
│       ├── logging.py          # configure_logging() : loguru bootstrap (call once)
│       └── (placeholders for later phases: framing/, decision/, ndi/, obs/, score/, watchdog/, orchestrator.py)
├── tools/
│   └── catalog_clips.py        # dev cataloguer: scan a footage dir → clip_manifest.yaml + coverage gap report
└── tests/
    ├── conftest.py             # shared fixtures (seeded rng, tmp config files)
    ├── fixtures/
    │   ├── README.md           # license/consent per clip (TST-01)
    │   ├── clip_manifest.yaml  # clip → {discipline, conditions[], notes, source, license, metadata}
    │   ├── disc_dog/           # (gitignored binaries; manifest + README committed)
    │   └── agility/
    ├── test_config_valid.py
    ├── test_config_invalid.py  # malformed-config rejection (CFG-01)
    ├── test_config_zones.py    # zone-rect + framing_weights assertions (CFG-02)
    ├── test_discipline_switch.py # discipline swap assertions (CFG-03)
    ├── test_model_config.py    # model path/class swap (CFG-04)
    ├── test_synth_score.py     # determinism + scenario shape (TST-02)
    └── test_synth_feeddeath.py # determinism + event shape (TST-02)
```

### Pattern 1: Single typed `Config` root + nested pydantic models
**What:** One `Config(BaseModel)` aggregating `field`, `cameras: list[Camera]`, `framing_weights`, `thresholds`, `model`. Each nested concept is its own `BaseModel` with `Field` constraints and validators. Load via `Config.model_validate(yaml.safe_load(...))`.
**When to use:** Always — this is the CFG-01 contract.
**Example:** see `## Code Examples → Config models + loader`.

### Pattern 2: Normalized-rect zones with ordering + bounds validators
**What:** `Zone.rect = [x0, y0, x1, y1]` each in `[0,1]` with `x0<x1`, `y0<y1` enforced by a `field_validator`. `framing_weights` is `dict[Role, dict[str, float]]`; a `model_validator(mode='after')` on `Config` asserts every zone *name* referenced in any camera is present (or defaulted to 1.0) in `framing_weights[role]`, so a typo'd zone fails fast at startup, not silently at scoring time (Phase 2).
**When to use:** CFG-02. The cross-check is the difference between "fails clearly now" and "scorer silently uses weight 1.0 forever."
**Trade-off:** + catches config typos at startup; − requires the cross-field `model_validator` (slightly more code than per-field checks).

### Pattern 3: Discipline profile as a discriminated union (zero-code-edit swap)
**What:** Model the discipline-specific bundle (overlay field set + framing defaults) as a discriminated union keyed on `field.sport` (and/or `event`). `Config.discipline_profile: DiscDogProfile | AgilityProfile = Field(discriminator='sport')`. pydantic selects the right sub-model from the YAML value. Consumers read `config.discipline_profile.overlay_fields` / `.framing_defaults` — **the engine never branches on a hardcoded `if sport == 'disc_dog'`.**
**When to use:** CFG-03 — this IS the mechanism that makes discipline a data switch.
**Example:** see `## Code Examples → Discipline discriminated union`.
**Why discriminated union over a plain enum + dict:** the union gives each discipline its *own validated shape* (disc-dog has Toss&Fetch vs Freestyle overlay fields per FEATURES.md; agility has SCT/faults). A bare enum would force one flat overlay schema and lose per-discipline validation. Context7-verified the `Field(discriminator=...)` + `Literal` tag pattern and its `union_tag_invalid`/`union_tag_not_found` errors (clear fail-fast on a bad discipline value).

### Pattern 4: Generators take an injected `numpy.random.Generator` (determinism)
**What:** Every generator is `def score_stream(rng: np.random.Generator, scenario: str, n_cams: int, n_ticks: int, **params) -> list[ScoreSample]`. The caller constructs `rng = np.random.default_rng(seed)` and passes it. No module-level RNG, no `np.random.seed()` (global), no `time.time()`/`datetime.now()`. Time is a synthetic tick counter passed in or derived from the loop index.
**When to use:** TST-02 — determinism is the requirement.
**Trade-off:** + byte-identical output per seed → reproducible tests in P2/P3/P5; − callers must remember to construct the rng (mitigated by a default-seed convenience wrapper for non-test use).

### Pattern 5: Fixtures as external files + committed YAML manifest (NOT git-lfs)
**What:** Video binaries live in `tests/fixtures/<discipline>/` but are **gitignored**; only the `clip_manifest.yaml` + `README.md` are committed. The manifest is the queryable index (clip → discipline, conditions[], metadata, source, license). Later phases load the manifest and resolve clip paths relative to the fixtures dir; a missing binary surfaces a clear "fixture not present locally" message.
**When to use:** TST-01 — the user's REAL footage may be large and/or not redistributable (consent/copyright). Manifest-over-external-dir keeps the repo small, avoids committing footage that may not be license-clear, and doesn't require `git-lfs` (which is NOT installed — see Environment Availability).
**Trade-off:** + repo stays lean, no LFS dependency, license-safe; − binaries aren't version-controlled (acceptable: they're external test inputs, and the manifest+README capture provenance). Document the drop-location and ingest procedure so a fresh checkout knows where to place footage.

### Anti-Patterns to Avoid
- **Importing torch/ultralytics/cyndilib at package top-level:** breaks the "runs with no GPU/NDI" requirement. Import heavy deps *inside* the functions that use them, in later-phase modules only. A Phase-1 import-smoke test should assert `import segugio` and `import segugio.config` succeed with torch/cyndilib *uninstalled*.
- **Returning a `dict` from config validation:** loses the typed-object benefit. Return the pydantic `Config` instance; consumers use attribute access.
- **`yaml.load` without `safe_load`:** arbitrary-object deserialization risk. Always `safe_load`.
- **Hardcoding the OBS text input kind / OS paths now:** even though OBS is Phase 5, establish `pathlib` + runtime-discovery conventions in Phase 1 so they propagate (CONTEXT.md code conventions).
- **`pydantic.BaseSettings`/env-var coupling for the config:** config is a file, not env. Keep it a plain `BaseModel`.
- **Global `np.random.seed()` in generators:** non-deterministic under parallel tests and leaks state across tests. Inject a `Generator`.
- **Committing footage binaries / using git-lfs unprompted:** license risk + git-lfs not installed. External dir + manifest.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config validation + typed access | Custom dict-walking validator with manual `if "role" not in cam: raise` | **pydantic v2** `BaseModel` + `Field` + validators | Aggregated multi-error reporting, JSON-path locations, type coercion, nested models, discriminated unions — all battle-tested. Hand-rolled validators report one error at a time and drift from the schema. |
| Clear "all errors at once" startup report | Manually collecting error strings | pydantic `ValidationError` (catch it, print `e.errors()` or `str(e)`) | One exception already lists every failure with location and input. Wrap it in a clear "config invalid:" banner; don't re-implement aggregation. |
| Discipline-swap dispatch | `if sport == "disc_dog": ... elif "agility": ...` scattered across modules | pydantic **discriminated union** sub-config | Centralizes the per-discipline data; consumers read fields, never branch on the discipline string (CFG-03 = zero code edits). |
| Clip metadata (resolution/fps/duration/codec) | Parsing container headers by hand | `opencv-python` `cv2.VideoCapture` props (or `ffprobe -show_streams -of json` if ffmpeg installed) | Robust across containers. opencv is already a dep; ffprobe needs a system install that isn't present. |
| Seeded reproducible RNG | Custom LCG / hashing for "random" scores | `numpy.random.default_rng(seed)` | PCG64, well-distributed, explicitly reproducible, injectable. Custom RNGs are a determinism/quality footgun. |
| YAML parsing | Regex/line parsing of YAML | `yaml.safe_load` | Obvious, but worth stating: never parse YAML by hand. |
| Logging setup | `print()` or a custom logger | `loguru` (one `configure_logging()`) | Locked decision; loguru gives leveled, structured, sink-configurable logging with near-zero boilerplate. |

**Key insight:** Phase 1 is mostly *gluing the right libraries to a well-specified schema*. The schema is already designed (ARCHITECTURE.md); the libraries are mature. The only genuinely custom code is the synthetic generators and the cataloguer — and even those lean on numpy/opencv. Resist building bespoke validation or RNG.

## Runtime State Inventory

> Phase 1 is **greenfield scaffolding** — there is no pre-existing code, datastore, service, or registered state to migrate. This section is included for completeness and to confirm nothing is being silently missed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by `ls` of working dir (only `.git`, `.planning`, `CLAUDE.md`; no `src/`, no DB, no datastore). | None |
| Live service config | None — no NDI/OBS/n8n/scheduler services touched in Phase 1 (hardware/services deferred to Phase 5). | None |
| OS-registered state | None — no scheduled tasks, services, or daemons registered. | None |
| Secrets/env vars | None — config is a plain YAML file with no secrets in scope (obs-websocket password is a Phase-5 concern). | None |
| Build artifacts | None yet — `src/segugio.egg-info/` will be created on first `pip install -e .`; that's a fresh artifact, not stale state. | None |

**Nothing found in any category** — Phase 1 is greenfield; no migration or runtime-state reconciliation needed.

## Common Pitfalls

### Pitfall 1: Heavy deps imported at module top-level break the "no-GPU/NDI" requirement
**What goes wrong:** A top-level `import ultralytics` (or `cyndilib`) in any module on the `import segugio` path makes config + generators un-importable on a machine without torch/CUDA/libndi — defeating the entire hardware-free Phase-1 goal.
**Why it happens:** Habit of putting imports at the top of files.
**How to avoid:** Heavy deps imported *inside functions* in later-phase modules only. Phase-1 modules (`config`, `synth`, `logging`) import nothing heavy. Add an import-smoke test (Validation Architecture) that imports the Phase-1 surface and asserts success.
**Warning signs:** `pip uninstall torch cyndilib` then `python -c "import segugio.config"` fails.

### Pitfall 2: Config validation that returns a dict, or validates only shallowly
**What goes wrong:** Using jsonschema/voluptuous (or a partial pydantic model) leaves nested structures (`zones[]`, `framing_weights[role][zone]`) unvalidated or untyped; bad zone rects or a typo'd zone name slip through to Phase 2 and fail obscurely during scoring.
**Why it happens:** Shallow schemas are easier; nested validation is skipped.
**How to avoid:** Full nested pydantic models + the `model_validator` cross-check (Pattern 2) that every referenced zone name is weighted. Fail at startup with a JSON-path error, not at scoring time.
**Warning signs:** A camera references zone `"middle"` but `framing_weights` only has `"mid"` — silently weighted 1.0 instead of erroring.

### Pitfall 3: Non-deterministic generators (global RNG or wall-clock leak)
**What goes wrong:** A generator that uses `np.random.seed()` globally, the module-global RNG, or `time.time()` produces different output across runs / under pytest parallelism → flaky scorer/FSM/watchdog tests in P2/P3/P5.
**Why it happens:** Reaching for `np.random.rand()` (global) instead of an injected `Generator`; using real time for "timestamps."
**How to avoid:** Inject `rng = np.random.default_rng(seed)`; use a synthetic tick counter for time. Add a determinism test: same seed → identical output (assert array/list equality across two calls).
**Warning signs:** A test passes alone but fails under `pytest -n auto`; two generator calls with the same seed differ.

### Pitfall 4: Committing large/undclear-license footage to git (and assuming git-lfs)
**What goes wrong:** Dropping the user's real footage into a tracked `tests/fixtures/` dir bloats the repo and may redistribute footage that isn't license-clear (PITFALLS/STACK: keep real competition footage local/un-committed). Assuming `git-lfs` is available also fails — it is NOT installed.
**Why it happens:** Treating fixtures like normal source files.
**How to avoid:** Gitignore the binaries; commit only `clip_manifest.yaml` + `README.md`. Document the drop-location and ingest procedure. The manifest carries provenance; the README carries license/consent.
**Warning signs:** `git status` shows multi-MB `.mp4` files staged; repo clone is slow.

### Pitfall 5: Cataloguer depends on `ffprobe` which isn't installed
**What goes wrong:** A cataloguer shelling out to `ffprobe` fails on this box (ffmpeg/ffprobe absent — verified).
**Why it happens:** ffprobe is the "obvious" metadata tool but is a system dependency, not a pip package.
**How to avoid:** Probe metadata with `opencv-python` (already a dep) via `cv2.VideoCapture` properties, OR make ffprobe optional with an opencv fallback and a clear "install ffmpeg for richer metadata" note. Recommend opencv-first.
**Warning signs:** `FileNotFoundError: ffprobe` at catalogue time.

### Pitfall 6: Condition checklist drift — fixtures don't actually cover the required conditions
**What goes wrong:** The corpus looks populated but silently misses required conditions (multi-dog, tunnel occlusion, backlit/dusk, midfield-equidistant) for one discipline, so later phases' hard cases stay untested — exactly the "looks done but isn't" trap from PITFALLS.
**Why it happens:** No coverage check; manual tagging is incomplete.
**How to avoid:** The cataloguer emits a **coverage gap report**: a matrix of {condition × discipline} marked covered/missing from the manifest tags. Phase 1's TST-01 acceptance includes "gaps flagged" so the user knows which CC0/web clips to supplement later.
**Warning signs:** Manifest has 20 clips but the coverage matrix shows agility/backlit and disc/midfield-equidistant empty.

## Code Examples

> These are *reference patterns* for the planner, verified against Context7 `/pydantic/pydantic` and the numpy/pyyaml standard APIs. They are illustrative skeletons, not the final implementation.

### Config models + loader (CFG-01, CFG-02, CFG-04)
```python
# src/segugio/config/models.py
# Source: pydantic v2 patterns verified via Context7 /pydantic/pydantic
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class Role(str, Enum):
    main_wide = "main_wide"
    long = "long"
    low = "low"
    handler_side = "handler_side"

Norm = Annotated[float, Field(ge=0.0, le=1.0)]      # normalized [0..1]

class Zone(BaseModel):
    model_config = ConfigDict(extra="forbid")        # reject unknown keys → clear error
    name: str
    rect: list[Norm] = Field(min_length=4, max_length=4)  # [x0,y0,x1,y1]

    @field_validator("rect", mode="after")
    @classmethod
    def _ordered(cls, v: list[float]) -> list[float]:
        x0, y0, x1, y1 = v
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"rect must have x0<x1 and y0<y1, got {v}")
        return v

class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    role: Role
    obs_scene: str
    is_safe: bool = False
    ndi_source: str | None = None
    zones: list[Zone] = Field(min_length=1)

class ModelConfig(BaseModel):                        # CFG-04
    model_config = ConfigDict(extra="forbid")
    path: Path = Path("yolo26s.pt")                  # swappable, no code edit
    class_index: int = 16                            # COCO dog; re-verify vs model.names at load (Phase 4)

class Thresholds(BaseModel):                         # all CFG-01 switching params
    model_config = ConfigDict(extra="forbid")
    alpha: Annotated[float, Field(gt=0.0, le=1.0)] = 0.3
    hysteresis_margin: Annotated[float, Field(ge=0.0)] = 0.1
    min_dwell: Annotated[float, Field(ge=0.0)] = 2.0
    debounce_N: Annotated[int, Field(ge=1)] = 3
    cooldown: Annotated[float, Field(ge=0.0)] = 1.0
    watchdog_timeout: Annotated[float, Field(gt=0.0)] = 0.8
    track_buffer: Annotated[int, Field(ge=1)] = 60

class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: "FieldProfile"                            # discriminated union, see discipline.py
    cameras: list[Camera] = Field(min_length=1)
    framing_weights: dict[Role, dict[str, float]]    # role -> {zone_name: multiplier}
    thresholds: Thresholds = Thresholds()
    model: ModelConfig = ModelConfig()

    @model_validator(mode="after")
    def _zones_are_weighted(self) -> "Config":       # CFG-02 cross-check (fail fast on typos)
        for cam in self.cameras:
            weights = self.framing_weights.get(cam.role, {})
            for z in cam.zones:
                if z.name not in weights:
                    raise ValueError(
                        f"camera '{cam.id}' (role={cam.role.value}) references zone "
                        f"'{z.name}' with no framing_weights[{cam.role.value}][{z.name}]"
                    )
        if not any(c.is_safe for c in self.cameras):
            raise ValueError("at least one camera must have is_safe: true (SAFE fallback)")
        return self
```
```python
# src/segugio/config/loader.py
import sys, yaml
from pathlib import Path
from pydantic import ValidationError
from loguru import logger
from .models import Config

def load_config(path: str | Path) -> Config:
    """Load + validate config. Fails FAST with a clear, aggregated error (CFG-01)."""
    p = Path(path)
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Cannot read/parse config '{p}': {e}")
        raise SystemExit(2) from e
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        logger.error(f"Invalid config '{p}': {e.error_count()} error(s):\n{e}")
        raise SystemExit(2) from e   # clear startup failure, non-zero exit
```

### Discipline discriminated union (CFG-03)
```python
# src/segugio/config/discipline.py
# Source: discriminated-union pattern verified via Context7 /pydantic/pydantic
from typing import Annotated, Literal
from pydantic import BaseModel, Field

class FramingDefaults(BaseModel):
    lead_room: float = 0.0
    hold_length_s: float = 2.0

class DiscDogProfile(BaseModel):
    sport: Literal["disc_dog"]
    event: Literal["distance_accuracy", "freestyle", "xtreme"] = "distance_accuracy"
    overlay_fields: list[str] = ["team", "round", "timer", "catch_count", "zone", "total"]
    framing_defaults: FramingDefaults = FramingDefaults(lead_room=0.25, hold_length_s=2.5)

class AgilityProfile(BaseModel):
    sport: Literal["agility"]
    event: Literal["agility_standard"] = "agility_standard"
    overlay_fields: list[str] = ["dog", "sct", "running_time", "faults", "result"]
    framing_defaults: FramingDefaults = FramingDefaults(lead_room=0.10, hold_length_s=1.5)

# pydantic picks the sub-model from the `sport` value — zero code branches downstream:
FieldProfile = Annotated[DiscDogProfile | AgilityProfile, Field(discriminator="sport")]
# In YAML:  field: { sport: disc_dog, event: freestyle }
# Consumer: config.field.overlay_fields / config.field.framing_defaults  (no if/elif on sport)
```

### Deterministic score-stream generator (TST-02)
```python
# src/segugio/synth/score_stream.py
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class ScoreSample:
    tick: int
    cam_id: str
    score: float          # normalized [0..1]

def score_stream(
    rng: np.random.Generator,          # INJECTED — determinism (TST-02)
    scenario: str,                     # "ping_pong" | "tie" | "dropout" | "recovery"
    cam_ids: list[str],
    n_ticks: int,
    noise: float = 0.02,
) -> list[ScoreSample]:
    """Emit a reproducible per-camera score stream. Same seed -> identical output."""
    out: list[ScoreSample] = []
    for t in range(n_ticks):
        base = _scenario_base(scenario, t, len(cam_ids), n_ticks)  # pure, no rng
        jitter = rng.normal(0.0, noise, size=len(cam_ids))         # injected rng only
        for cam, b, j in zip(cam_ids, base, jitter):
            out.append(ScoreSample(t, cam, float(np.clip(b + j, 0.0, 1.0))))
    return out

# usage in a test:  rng = np.random.default_rng(1234); s = score_stream(rng, "ping_pong", ["a","b"], 100)
```

### Deterministic feed-death generator (TST-02)
```python
# src/segugio/synth/feed_death.py
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class FeedEvent:
    tick: int
    cam_id: str
    alive: bool

def feed_death(
    rng: np.random.Generator,
    cam_ids: list[str],
    n_ticks: int,
    death_at: dict[str, int] | None = None,   # explicit deaths; rng fills any random ones
    recover_after: int | None = None,
) -> list[FeedEvent]:
    """Reproducible feed liveness timeline (death + optional recovery)."""
    death_at = death_at or {}
    out: list[FeedEvent] = []
    for t in range(n_ticks):
        for cam in cam_ids:
            d = death_at.get(cam)
            alive = True
            if d is not None and t >= d:
                alive = recover_after is not None and t >= d + recover_after
            out.append(FeedEvent(t, cam, alive))
    return out
```

### Cataloguer metadata probe (TST-01) — opencv, no ffprobe needed
```python
# tools/catalog_clips.py  (dev tool; opencv imported lazily inside the function)
def probe(path: str) -> dict:
    import cv2                              # lazy — keeps Phase-1 runtime import-clean
    cap = cv2.VideoCapture(path)
    meta = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": round(cap.get(cv2.CAP_PROP_FPS), 3),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    meta["duration_s"] = round(meta["frames"] / meta["fps"], 2) if meta["fps"] else None
    return meta
```

### Clip manifest schema (TST-01)
```yaml
# tests/fixtures/clip_manifest.yaml  (committed; binaries are gitignored)
clips:
  - file: disc_dog/toss_fetch_multidog_01.mp4
    discipline: disc_dog
    event: distance_accuracy
    conditions: [multi_dog, handler_prominent, distant]   # from the checklist
    source: user_footage                                  # user_footage | pexels | pixabay | yt_dlp_cc
    license: user_consent_README                          # points to README entry
    notes: "two dogs warming up ringside; competitor downfield"
    metadata: { width: 1920, height: 1080, fps: 29.97, duration_s: 41.2 }
# condition checklist (both disciplines): multi_dog, handler_prominent,
#   tunnel_contact_occlusion, jump_sprint_blur, distant, backlit_dusk, midfield_equidistant
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pydantic v1 (`@validator`, `.parse_obj`, `Config` inner class) | pydantic v2 (`@field_validator`/`@model_validator`, `.model_validate`, `model_config = ConfigDict(...)`) | v2.0 (mid-2023), now 2.13.4 | Use v2 idioms only. v1 patterns in training data are deprecated. `model_validate` replaces `parse_obj`; `ConfigDict(extra="forbid")` replaces the inner `Config` class. |
| `np.random.seed()` + `np.random.rand()` (global legacy) | `np.random.default_rng(seed)` → `Generator` methods | numpy ≥1.17 (now 2.4.6) | Inject the `Generator`; the legacy global RNG is discouraged and non-reproducible under parallelism. |
| flat-layout package (`segugio/` at repo root) | `src/`-layout (`src/segugio/`) | PyPA recommendation, stable | Prevents accidental imports of the un-installed package during tests; matches CONTEXT.md's `src/segugio/` decision. |
| git-lfs for test media | external dir + committed manifest (for license-sensitive/large media) | n/a (project constraint) | git-lfs not installed; user footage may be license-restricted → manifest-over-external-dir. |

**Deprecated/outdated:**
- pydantic v1 `@validator` / `parse_obj` / inner `class Config`: replaced by v2 equivalents above.
- `yaml.load(...)` without `Loader`: use `yaml.safe_load`.

## Assumptions Log

> Claims tagged `[ASSUMED]` that need user/planner confirmation before becoming locked.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | slopcheck results unavailable → all packages tagged `[ASSUMED]`; mitigated because every package is a pre-locked, well-known dep. | Package Legitimacy Audit | LOW — packages are from prior HIGH-confidence research; cyndilib (niche) flagged for a Phase-5 human-verify checkpoint. |
| A2 | `opencv-python` is the recommended cataloguer metadata source (over ffprobe) because ffprobe is not installed. | Standard Stack / Don't Hand-Roll | LOW — opencv is a locked dep; if richer metadata (codec/bitrate) is needed, user can install ffmpeg. Note: opencv `CAP_PROP_FPS` can be slightly off for VFR clips; acceptable for cataloguing. |
| A3 | torch is left to be pulled transitively by ultralytics (not pinned directly in Phase 1). | Standard Stack (locked deps) | MEDIUM — on a CUDA box the correct torch+CUDA build may need an explicit index URL; this is a Phase-4 concern, flagged there. Phase 1 doesn't install/import torch. |
| A4 | Discipline discriminated-union keyed on `sport` (with `event` as a per-profile field) is the right granularity for CFG-03. | Architecture Pattern 3 | LOW — matches ARCHITECTURE.md (`field.sport`/`field.event`) and FEATURES.md (per-discipline overlay sets). If the user wants `event` itself to be the discriminator (e.g. separate Toss&Fetch vs Freestyle profiles), that's a nested union — easily added. |
| A5 | Default threshold values in the example config (alpha=0.3, track_buffer=60, etc.) are seeds for tuning, not locked tuned values. | Code Examples (Thresholds) | LOW — values come from TECHNICAL-RESEARCH/STACK as starting points; real tuning happens in P2-P4 on the clip set. The *schema* is what Phase 1 locks, not the values. |
| A6 | Synthetic generators live in the package (`src/segugio/synth/`) so any phase can import them, not under `tests/`. | Project Structure | LOW — standard practice for shared test-support code; alternative is `tests/_support/` but that's harder to import cross-phase. |

**If this table is empty:** it is not — six assumptions are flagged, all LOW/MEDIUM risk, none blocking. A3 (torch/CUDA) is the one to carry into Phase 4.

## Open Questions

1. **Exact footage drop-location convention and ingest trigger**
   - What we know: footage path is user-provided at execution time; goes into `tests/fixtures/<discipline>/`; cataloguer scans it.
   - What's unclear: whether the cataloguer should *copy* footage into the fixtures tree or *reference* it in place (symlink/abs-path in manifest). Copying is simpler/portable; referencing avoids duplicating large files.
   - Recommendation: cataloguer copies (or hardlinks) into `tests/fixtures/<discipline>/` and records the relative path in the manifest; document the source path in the README. Confirm with user during planning if footage is too large to copy.

2. **Manifest format: YAML vs CSV**
   - What we know: CONTEXT.md says "small YAML/CSV mapping clip → conditions/discipline."
   - What's unclear: which the user prefers for hand-editing.
   - Recommendation: **YAML** (nested `conditions: [...]` and `metadata: {...}` are awkward in CSV; YAML matches the config tooling already in the package). Provide a CSV export helper only if requested.

3. **Whether `config.example.yaml` should be the disc-dog or agility default**
   - What we know: both disciplines must be expressible.
   - Recommendation: ship `config.example.yaml` for disc-dog (the range-dominated primary case) AND a brief `config.agility.example.yaml`, so CFG-03's swap is demonstrable and testable from two real example files.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All Phase-1 code | ✓ | 3.12.3 | — |
| pip | Installing deps | ✓ | 24.0 | — |
| git | Repo (already initialized) | ✓ | 2.43.0 | — |
| `ffprobe`/`ffmpeg` | Clip cataloguer (richer metadata) | ✗ | — | **Use `opencv-python` `cv2.VideoCapture` props** (recommended primary, not just fallback) |
| `git-lfs` | (Hypothetical) committing media binaries | ✗ | — | **External dir + committed YAML manifest** (recommended pattern anyway; LFS not needed) |
| CUDA / GPU | NOT needed in Phase 1 (heavy deps lazy) | n/a | — | Phase 1 runs CPU-only by design |
| NDI / libndi | NOT needed in Phase 1 (cyndilib lazy) | n/a | — | Phase 1 runs without NDI by design |

**Missing dependencies with no fallback:** none — every Phase-1 capability has a working path on this machine.
**Missing dependencies with fallback:**
- `ffprobe`/`ffmpeg`: cataloguer uses `opencv-python` (a locked dep) for metadata. This is the *recommended* approach, not a degraded fallback — avoids adding a system dependency.
- `git-lfs`: not used; external-dir + manifest is the chosen pattern regardless.

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (+ pytest-cov 7.1.0) |
| Config file | none yet — add `[tool.pytest.ini_options]` to `pyproject.toml` in Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=segugio --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | Valid config loads into a typed `Config`; full example parses | unit | `pytest tests/test_config_valid.py -x` | ❌ Wave 0 |
| CFG-01 | Malformed config (missing field, bad type, unknown key, no safe cam) FAILS with aggregated `ValidationError`/SystemExit | unit | `pytest tests/test_config_invalid.py -x` | ❌ Wave 0 |
| CFG-02 | Zone rect out of [0,1] or unordered → rejected; `framing_weights[role][zone]` multiplier present for every referenced zone; typo'd zone name → rejected | unit | `pytest tests/test_config_zones.py -x` | ❌ Wave 0 |
| CFG-03 | Setting `field.sport: disc_dog` vs `agility` yields different `overlay_fields` + `framing_defaults` with no code change; bad sport value → `union_tag_invalid` error | unit | `pytest tests/test_discipline_switch.py -x` | ❌ Wave 0 |
| CFG-04 | Default model path/class = `yolo26s.pt`/16; overriding both in YAML changes the typed `ModelConfig` (no code edit) | unit | `pytest tests/test_model_config.py -x` | ❌ Wave 0 |
| TST-01 | Cataloguer probes a sample clip → manifest entry with metadata; coverage-gap report lists missing {condition×discipline} cells; README+manifest committed, binaries gitignored | unit + smoke | `pytest tests/test_catalog.py -x` | ❌ Wave 0 |
| TST-02 | Same seed → byte-identical generator output (score_stream + feed_death); each scenario (ping_pong/tie/dropout/recovery) has the expected structural shape; feed-death + recovery timeline correct | unit | `pytest tests/test_synth_score.py tests/test_synth_feeddeath.py -x` | ❌ Wave 0 |
| 01-01 | `import segugio`, `import segugio.config`, `import segugio.synth` succeed with torch/cyndilib/ultralytics UNINSTALLED (lazy-import boundary) | unit (import smoke) | `pytest tests/test_import_smoke.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ --cov=segugio --cov-report=term-missing`
- **Phase gate:** full suite green before `/gsd:verify-work`; coverage of `segugio.config` and `segugio.synth` should be high (these are the load-bearing, pure modules).

### Specific assertion patterns (how each criterion is observably verified)
- **Malformed-config rejection (CFG-01):** parametrized cases — missing required key, wrong type (string where float expected), `extra` key, zero cameras, no `is_safe` camera, zone name not in `framing_weights`. Each asserts `pytest.raises((ValidationError, SystemExit))` and (for ValidationError) that `e.error_count()` / `loc` points at the offending path.
- **Zone-weight multiplier (CFG-02):** assert `config.framing_weights[Role.long]["far"] == 1.6` from a known example; assert a config referencing an unweighted zone raises.
- **Discipline-switch (CFG-03):** load two configs differing only in `field.sport`; assert `cfg.field.overlay_fields` and `cfg.field.framing_defaults` differ as specified; assert no `if sport ==` branch exists in consumer code (grep-style or by construction).
- **Generator determinism (TST-02):** `a = score_stream(default_rng(7), ...); b = score_stream(default_rng(7), ...); assert a == b`; and `assert score_stream(default_rng(7),...) != score_stream(default_rng(8),...)`.
- **Import smoke (01-01):** run the import test in an environment (or via monkeypatched `sys.modules` blocking) where heavy deps are absent; assert Phase-1 imports succeed.

### Wave 0 Gaps
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` (testpaths, `pythonpath = ["src"]` or install `-e .`)
- [ ] `tests/conftest.py` — shared fixtures: `seeded_rng`, `tmp_config(yaml_str)` writer, `valid_config_dict`
- [ ] `tests/test_config_valid.py`, `tests/test_config_invalid.py`, `tests/test_config_zones.py`
- [ ] `tests/test_discipline_switch.py`, `tests/test_model_config.py`
- [ ] `tests/test_synth_score.py`, `tests/test_synth_feeddeath.py`
- [ ] `tests/test_catalog.py` (uses a tiny generated/sample clip or mocks `cv2.VideoCapture`)
- [ ] `tests/test_import_smoke.py` (lazy-import boundary)
- [ ] Framework install: `pip install pytest==9.0.3 pytest-cov==7.1.0`

## Security Domain

> `security_enforcement` is not set in config.json (no explicit `false`) → included. Phase 1 is local, no-PII, no-network, no-auth — the security surface is minimal but two real items apply.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in Phase 1 (obs-websocket password is Phase 5). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Local single-user dev tool. |
| V5 Input Validation | **yes** | The config file is untrusted input → **pydantic v2** validates it fully and fails fast. The clip manifest is also parsed → `yaml.safe_load` only. |
| V6 Cryptography | no | No crypto/secrets in Phase 1. |

### Known Threat Patterns for Phase 1 stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary-object deserialization via `yaml.load` | Tampering / RCE | Use `yaml.safe_load` exclusively (config + manifest). Never `yaml.load` without SafeLoader. |
| Malformed config crashing the live director later | Denial of Service | Fail-fast at startup with a clear error (CFG-01) so a bad config never reaches the live loop. |
| Path injection via config `model.path` / clip paths | Tampering | Treat as `pathlib.Path`; resolve and (where appropriate) validate existence at load time; do not `eval`/shell-interpolate paths. |
| License/consent leakage by committing user footage | Information disclosure (rights) | Gitignore binaries; commit only manifest+README with documented consent (TST-01). |

## Sources

### Primary (HIGH confidence)
- Context7 `/pydantic/pydantic` — discriminated unions (`Field(discriminator=...)`, `Literal` tags, `union_tag_invalid`/`union_tag_not_found`), `model_validate` from YAML dict, `field_validator`/`model_validator(mode='after')`, `Field(ge=,le=)`, `ConfigDict(extra='forbid')`, custom error messages. Verified 2026-06-09.
- `pip index versions` (PyPI, 2026-06-09) — exact current versions for pydantic 2.13.4, pyyaml 6.0.3, numpy 2.4.6, loguru 0.7.3, pytest 9.0.3, pytest-cov 7.1.0, ultralytics 8.4.62, cyndilib 0.1.1, obsws-python 1.8.0, transitions 0.9.3, watchdog 6.0.0, opencv-python 4.13.0.92, jsonschema 4.26.0, voluptuous 0.16.0, ruamel.yaml 0.19.1.
- Project research docs (`.planning/research/`): ARCHITECTURE.md (config schema design), STACK.md (model/fixture/license guidance), PITFALLS.md (condition checklist), FEATURES.md (per-discipline overlay field sets), TECHNICAL-RESEARCH.md (locked module/dep list).
- Local environment probe (2026-06-09) — confirmed Python 3.12.3, pip 24.0, git 2.43.0 present; ffprobe/ffmpeg and git-lfs ABSENT.

### Secondary (MEDIUM confidence)
- numpy `default_rng` reproducibility and `src/`-layout packaging are standard, well-established practices (not separately re-verified this session; consistent with current numpy 2.x and PyPA guidance).

### Tertiary (LOW confidence)
- None — no claims rest on unverified single-source web results.

## Metadata

**Confidence breakdown:**
- Standard stack (config lib + versions): HIGH — every version verified on PyPI; pydantic v2 API verified via Context7.
- Architecture / patterns: HIGH — config schema is pre-designed in ARCHITECTURE.md; discriminated-union and validator patterns Context7-verified; clip-set + generator patterns are standard practice.
- Pitfalls: HIGH — drawn from project PITFALLS.md + concrete environment findings (ffprobe/lfs absent) + verified pydantic/numpy idioms.
- Environment availability: HIGH — directly probed this machine.

**Research date:** 2026-06-09
**Valid until:** ~2026-07-09 (30 days; stack is stable. pydantic/numpy/pytest may bump patch versions — re-check exact pins before install, but the v2/Generator/pytest-9 idioms are stable.)
