# Phase 2: framing-scorer-pure-logic - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 19 (12 new, 7 modified)
**Analogs found:** 19 / 19 (every new file has a direct Phase-1 analog — this is an additive phase in an established src-layout package)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/framing/__init__.py` | package re-export | — | `src/segugio/synth/__init__.py`, `src/segugio/config/__init__.py` | exact |
| `src/segugio/framing/signals.py` | model (frozen records) | transform | `src/segugio/synth/score_stream.py` (`ScoreSample`), `feed_death.py` (`FeedEvent`) | exact |
| `src/segugio/framing/terms.py` | utility (pure functions) | transform | `src/segugio/synth/score_stream.py` `_scenario_base` (pure, no-rng numpy helper) | role-match |
| `src/segugio/framing/scorer.py` | service (stateful per-camera object) | streaming / event-driven | `src/segugio/synth/score_stream.py` (tick loop + clip) + RESEARCH skeleton | role-match |
| `src/segugio/framing/params.py` | config (pydantic sub-model OR dataclass bridge) | — | `src/segugio/config/discipline.py` `FramingDefaults`, `models.py` `Thresholds` | exact |
| `src/segugio/synth/detection_stream.py` | utility (synthetic generator) | streaming | `src/segugio/synth/score_stream.py` | exact |
| `src/segugio/config/models.py` (MOD) | config (pydantic models) | — | itself — `Thresholds` sub-model + `_zones_are_weighted` validator | exact (in-file) |
| `config.example.yaml` (MOD) | config (YAML) | — | itself — `thresholds:` block | exact (in-file) |
| `config.agility.example.yaml` (MOD) | config (YAML) | — | itself — `thresholds:` block | exact (in-file) |
| `src/segugio/synth/__init__.py` (MOD) | package re-export | — | itself | exact (in-file) |
| `tests/conftest.py` (MOD) | test fixture | — | itself — `seeded_rng` / `valid_config_dict` fixtures | exact (in-file) |
| `tests/test_framing_base.py` | test (unit) | — | `tests/test_generators.py` (bounds/shape) | role-match |
| `tests/test_framing_ema.py` | test (unit) | — | `tests/test_generators.py` | role-match |
| `tests/test_framing_zone.py` | test (unit, config-driven) | — | `tests/test_config.py` + `valid_config_dict` | role-match |
| `tests/test_framing_leadroom.py` | test (unit) | — | `tests/test_generators.py` (shape assertions) | role-match |
| `tests/test_framing_coast.py` | test (unit, timeline) | — | `tests/test_generators.py::test_feeddeath_timeline_boundaries` | exact |
| `tests/test_framing_confnorm.py` | test (unit, two-stream) | — | `tests/test_generators.py::test_shape_*` | role-match |
| `tests/test_framing_shadow.py` | test (unit, gate) | — | `tests/test_config.py` (rejection cases) | role-match |
| `tests/test_framing_purity.py` | test (determinism + import-smoke) | — | `tests/test_generators.py::test_determinism_*` + `tests/test_imports.py` | exact |

---

## Pattern Assignments

### `src/segugio/framing/signals.py` (frozen records — `DetectionSignal`, `CameraScore`, `ScorerStatus`)

**Analog:** `src/segugio/synth/score_stream.py` (`ScoreSample`) + `src/segugio/synth/feed_death.py` (`FeedEvent`)

Both Phase-1 frozen records use the identical recipe. Copy it verbatim — the `frozen=True` + the `==`-is-the-determinism-assertion docstring is load-bearing (the FRM-07 purity test asserts `list(run(seq)) == list(run(seq))`, which only works because these are frozen and comparable).

**Module preamble + frozen dataclass pattern** (`score_stream.py:21-44`):
```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np  # only if the module needs it; signals.py may not need numpy

__all__ = ["ScoreSample", "score_stream", "SCENARIOS"]


@dataclass(frozen=True)
class ScoreSample:
    """One per-camera score reading at a synthetic tick.

    Frozen (hashable + comparable) so ``==`` over two ``list[ScoreSample]`` is the
    determinism assertion the downstream tests rely on. ``score`` is normalized [0..1].
    """

    tick: int
    cam_id: str
    score: float
```

**Apply to `DetectionSignal`** (input contract — must match RESEARCH.md Pattern 7 / TRK-03 field set exactly so Phase-4 YOLO rows map unchanged):
```python
@dataclass(frozen=True)
class DetectionSignal:
    tick: int        # injected tick index — NO wall-clock (matches ScoreSample.tick)
    cam_id: str
    cx: float        # normalized [0,1]
    cy: float
    w: float
    h: float
    conf: float
    track_id: int
```

**`ScorerStatus`** — RESEARCH says `status ∈ {tracking, coasting, lost}`. Mirror the `Role(str, Enum)` pattern from `config/models.py:35-41` (string-valued enum, members lower_snake) so `CameraScore` is still `==`-comparable and YAML/JSON-friendly:
```python
# from config/models.py:35-41
class Role(str, Enum):
    """Camera roles → the keys of the framing_weights matrix (ARCHITECTURE.md Part 2)."""
    main_wide = "main_wide"
    long = "long"
    ...
```

**Landmine:** `ScoreSample` is the existing **output** record of the *score_stream FSM-feed generator* — `DetectionSignal` is a NEW, different record (more fields, raw detection signals). Do **not** reuse `ScoreSample` as the scorer input; do **not** name the new input `ScoreSample`.

---

### `src/segugio/framing/terms.py` (pure free functions)

**Analog:** `src/segugio/synth/score_stream.py` `_scenario_base` (`score_stream.py:46-104`) — the established "pure, deterministic, numpy-only, uses NO rng" helper convention.

The key conventions to copy from `_scenario_base`:
1. **Explicit "uses NO rng / pure" docstring** stating the function is a function of indices/inputs only (this is the determinism guarantee the FRM-07 test depends on).
2. **Guard every divisor** — `_scenario_base` does `span = max(n_ticks - 1, 1)` to avoid div-by-zero. The scorer terms must do the same (CONTEXT `<specifics>`: guard `h>0`, `speed≥deadzone`, `sqrt(var+ε)`).
3. **`np.clip(..., 0.0, 1.0)` on the way out** — `_scenario_base` returns `np.clip(base, 0.0, 1.0)` (`score_stream.py:104`); every term and the base score must clip to `[0,1]`.
4. **`float(np....)` casts** at the boundary — `score_stream.py:142` does `float(np.clip(b + j, 0.0, 1.0))` so the frozen dataclass holds a plain `float` (keeps `==` byte-identical, not a numpy scalar).

**Divisor-guard + clip pattern** (`score_stream.py:53-57, 104`):
```python
# Guard against a divide-by-zero on the phase term; one tick is degenerate but valid.
span = max(n_ticks - 1, 1)
phase = t / span
...
return np.clip(base, 0.0, 1.0)
```

The exact term skeletons (`gaussian_centeredness`, `gaussian_size_band`, `base_score`, `lead_room_target`, `zone_of`, `gate`, `conf_norm_step`, `plausibility_ok`) are already written in **RESEARCH.md `## Code Examples` (lines 450-515)** and `## Architecture Patterns` Patterns 1-8 — copy those shapes; this analog supplies the *coding conventions* (pure docstring, divisor guard, clip, `float()` cast) to wrap them in.

**`zone_of` reads the Phase-1 `Camera`/`Zone` contract directly** — `Zone.rect` is `[x0, y0, x1, y1]` already validated `x0<x1, y0<y1` (`config/models.py:48-65`); `Camera.zones` is the ordered list (`config/models.py:77`); `Role` is the enum key into `framing_weights` (`config/models.py:35-41`). Read these, do not redefine them.

---

### `src/segugio/framing/scorer.py` (`CameraScorer` + `MultiCamScorer`)

**Analog:** `src/segugio/synth/score_stream.py` `score_stream` (`score_stream.py:107-143`) for the tick-loop + clip + `float()` convention; the full `CameraScorer.update` skeleton is in **RESEARCH.md lines 517-553**.

**Conventions to copy from `score_stream`:**
- Per-tick loop emitting frozen records, ordered deterministically (`score_stream.py:138-142`).
- **Fail-fast on bad enum/string up front** — `score_stream.py:131-134` validates `scenario` before the loop with a `ValueError` listing valid options. Mirror for any string status/path arg.
- **No wall-clock, no global RNG** — time is the injected `tick` argument (CONTEXT `<code_context>` determinism convention).

**Output construction** (mirror `score_stream.py:142`):
```python
out.append(ScoreSample(t, cam, float(np.clip(b + j, 0.0, 1.0))))
```
→ scorer emits `CameraScore(tick, cam_id, float(np.clip(self.ema or 0.0, 0.0, 1.0)), status)`.

**State held** (RESEARCH Pattern 7 table): `ema: float`, `history: collections.deque(maxlen=K+1)`, `ttl_counter: int`, `status: ScorerStatus`, conf-norm `μ/σ²/n`, `last_track_id`. RESEARCH already wrote the `__init__` and `update` (lines 522-553).

**Fail-safe, not fail-loud** (CONTEXT `<specifics>` + RESEARCH Security V5, lines 712-718): the scorer must **not throw** on data the validated `Config` already passed — `np.clip` outputs to `[0,1]`, default a missing `framing_weights` key to neutral `1.0` (RESEARCH Pattern 3, `gate()` uses `framing_weights[role].get(zone_name, 1.0)`), treat NaN/inf as "no detection" → coast. This is a NEW invariant (no Phase-1 analog throws-vs-clips in a hot loop); the `_scenario_base` clip-on-exit is the closest precedent.

**Landmine — coast scope:** the scorer's TTL covers only the **short blur gap** (~0.3–0.7 s). The **long expected-occlusion hold** (`FramingDefaults.hold_length_s`, disc 2.5 / agility 1.5) is a **Phase-3 FSM** concern — do NOT implement it here (CONTEXT D-04). `hold_length_s` exists in `discipline.py:31` but is NOT a scorer field; only read `FramingDefaults.lead_room`.

---

### `src/segugio/framing/params.py` (`ScorerParams` bridge)

**Analog:** `src/segugio/config/discipline.py` `FramingDefaults` (`discipline.py:22-31`) + `src/segugio/config/models.py` `Thresholds` (`models.py:93-107`) — the established additive pydantic sub-model with `Field(ge=, le=, gt=)` bounds and a "tuning seeds" docstring.

**`Thresholds` sub-model pattern** (`models.py:93-107`) — the closest analog; copy the `ConfigDict(extra="forbid")` + `Annotated[float, Field(...)]` defaults + the "values are tuning seeds, the schema is what's locked" docstring (this matches CONTEXT exactly: all `[ASSUMED]` constants, none hardcoded, all bounded in config):
```python
class Thresholds(BaseModel):
    """The seven switching parameters (CFG-01).

    Values are tuning *seeds* (A5: tuned on real footage in P2-P4); the SCHEMA and
    its bounds are what Phase 1 locks.
    """

    model_config = ConfigDict(extra="forbid")
    alpha: Annotated[float, Field(gt=0.0, le=1.0)] = 0.3
    hysteresis_margin: Annotated[float, Field(ge=0.0)] = 0.1
    ...
    track_buffer: Annotated[int, Field(ge=1)] = 60
```

**Normalized-coord type** — reuse the `Norm` alias from `models.py:45` for any `[0,1]` param (`ideal_size`, `sigma_*`, `lead_max`, `out_of_bounds_factor`, etc.):
```python
# models.py:45
Norm = Annotated[float, Field(ge=0.0, le=1.0)]
```

**The 18 params to define** (CONTEXT D / RESEARCH Open Q3): `sigma_c, ideal_size, sigma_s, w_c/w_s/w_conf, lead_max, v_deadzone, ttl_seconds, beta, z_clip, warmup, conf_floor, min_area, aspect_lo/hi, out_of_bounds_factor`. Seed defaults from RESEARCH Assumptions Log (lines 597-611). **Planner decides nesting** (top-level `scoring:` block vs under `thresholds:`); the *principle* (all in the one validated `Config`, fail-fast) is locked. `lead_room` stays per-discipline in `FramingDefaults`; do not duplicate it into `ScorerParams`.

**Reference for `w_c/w_s/w_conf` sum-to-1 cross-check** — the additive `model_validator(mode="after")` pattern is in `models.py:120-140` (`_zones_are_weighted`): a `@model_validator` that raises a descriptive `ValueError` on a cross-field invariant. Apply the same shape if the planner wants to assert `w_c + w_s + w_conf == 1`.

---

### `src/segugio/synth/detection_stream.py` (NEW synthetic generator)

**Analog:** `src/segugio/synth/score_stream.py` (whole file) — this is the **single most important analog**: `detection_stream` must mirror `score_stream`'s structure exactly (it lives in the same package, is re-exported the same way, and is the FRM test substrate). RESEARCH wrote the skeleton at lines 556-578.

**Copy the full signature + determinism contract** (`score_stream.py:107-143`):
```python
def score_stream(
    rng: np.random.Generator,          # INJECTED — the ONLY randomness source
    scenario: str,
    cam_ids: list[str],
    n_ticks: int,
    noise: float = 0.02,
) -> list[ScoreSample]:
    ...
    n_cams = len(cam_ids)
    out: list[ScoreSample] = []
    for t in range(n_ticks):
        base = _scenario_base(scenario, t, n_cams, n_ticks)  # pure, no rng
        jitter = rng.normal(0.0, noise, size=n_cams)         # injected rng only
        for cam, b, j in zip(cam_ids, base, jitter):
            out.append(ScoreSample(t, cam, float(np.clip(b + j, 0.0, 1.0))))
    return out
```

**Determinism-contract docstring** (`score_stream.py:11-19`) — copy this block verbatim (adjust the record name); the FRM-07 purity test and the existing `test_determinism_*` tests assert exactly this:
```
Determinism contract (RESEARCH.md Pattern 4 + Pitfall 3):
  * the injected ``numpy.random.Generator`` is the ONLY source of randomness;
  * the module never seeds or calls the legacy global numpy RNG;
  * no wall-clock is read — ``t`` is the synthetic tick index.
  Same seed -> byte-identical list; different seed -> different.
```

**`detection_stream` knobs** (RESEARCH lines 562-567): `path` (motion path for lead-room: `"linear_right"`/`"static"`), `size`, `conf`, `conf_bias` (the `+0.2` "brighter camera" knob for the FRM-06 anti-bias test), `dropout: tuple[int,int]|None` (emit `None` for coast), `noise`, `track_id`. Returns `list[DetectionSignal | None]` (the `None` = no-detection-this-tick is NEW vs `score_stream`, which never emits `None`).

**Landmine (the load-bearing distinction):** `score_stream` emits **`ScoreSample(tick, cam_id, score)` — FINAL FSM scores** for Phase-3 testing. It is NOT the scorer's input and must NOT be reused as the detection generator (RESEARCH Open Q1, line 615; Anti-Pattern line 379). The whole reason `detection_stream` exists is that `score_stream` is the wrong layer.

**Import direction:** `detection_stream` imports `from segugio.framing.signals import DetectionSignal` (RESEARCH line 561) — so `framing.signals` must NOT import from `synth` (avoid a cycle). `framing` is the lower layer; `synth.detection_stream` depends up onto it.

---

### MODIFIED: `src/segugio/config/models.py` — add `ScorerParams` (if nested here)

**Analog:** itself — add the new sub-model alongside `Thresholds` (`models.py:93-107`) and reference it from `Config` exactly like `thresholds`/`model` are referenced (`models.py:117-118`):
```python
# models.py:110-118 — how Config aggregates sub-models with defaults:
class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: FieldProfile
    cameras: list[Camera] = Field(min_length=1)
    framing_weights: dict[Role, dict[str, float]]
    thresholds: Thresholds = Field(default_factory=Thresholds)
    model: ModelConfig = Field(default_factory=ModelConfig)
    # ADD:  scoring: ScorerParams = Field(default_factory=ScorerParams)
```
This is **additive** (a new optional field with `default_factory`) — existing configs that omit `scoring:` still validate (no breaking change, CONTEXT `<code_context>` "extend additively"). If `ScorerParams` lives in `params.py`, import it here or define it here — planner's call; either way wire it into `Config` and re-export via `config/__init__.py` (next).

---

### MODIFIED: `src/segugio/config/__init__.py` — re-export `ScorerParams`

**Analog:** itself (`config/__init__.py:9-25`) — append the new symbol to the import line and `__all__`, exactly as `Thresholds`/`FramingDefaults` are exported:
```python
from .models import Camera, Config, ModelConfig, Role, Thresholds, Zone  # + ScorerParams
__all__ = [ ..., "Thresholds", ..., "FramingDefaults" ]  # + "ScorerParams"
```

---

### MODIFIED: `config.example.yaml` / `config.agility.example.yaml` — `scoring:` defaults

**Analog:** the existing `thresholds:` block in both files (`config.example.yaml:65-75`, `config.agility.example.yaml:61-69`) — a commented YAML block with the "tuning seeds" framing. Add a parallel `scoring:` block with the 18 seed values from RESEARCH Assumptions Log. Match the existing comment style ("Values are starting points (tuned on real footage in later phases); the schema and bounds are what's locked here.").

**Both files must be edited identically** for the `scoring:` defaults — the only intended difference between the two example files is `field.sport` and the `framing_weights` magnitudes (`config.agility.example.yaml:1-9` documents that the files are "structurally identical"). `lead_room` already differs correctly via `FramingDefaults` defaults (disc 0.25 / agility 0.10) and need not be set in the YAML unless overriding.

---

### MODIFIED: `src/segugio/synth/__init__.py` — re-export `detection_stream`

**Analog:** itself (`synth/__init__.py:12-21`) — append the new generator and its record exactly as `score_stream`/`feed_death` are exported:
```python
from .detection_stream import detection_stream            # + DetectionSignal if re-exported here
from .feed_death import FeedEvent, feed_death
from .score_stream import SCENARIOS, ScoreSample, score_stream

__all__ = ["ScoreSample", "score_stream", "SCENARIOS", "FeedEvent", "feed_death",
           "detection_stream"]   # append
```

---

### MODIFIED: `tests/conftest.py` — add `scorer_params` fixture

**Analog:** itself — the `seeded_rng` fixture (`conftest.py:27-34`) and `valid_config_dict` fixture (`conftest.py:113-116`, backed by `_VALID_CONFIG` at lines 64-110). Add a `scorer_params` fixture beside them returning seeded `ScorerParams` defaults.

**Fixture pattern** (`conftest.py:27-34` for the seeded-singleton shape, `113-116` for the deep-copy-isolation shape):
```python
@pytest.fixture
def seeded_rng() -> np.random.Generator:
    """A fresh, deterministically-seeded ``numpy.random.Generator``."""
    return np.random.default_rng(SEED)

@pytest.fixture
def valid_config_dict() -> dict:
    """A minimal well-formed disc_dog config dict (deep-copied so tests can mutate)."""
    return copy.deepcopy(_VALID_CONFIG)
```

**Apply to `scorer_params`:**
```python
@pytest.fixture
def scorer_params():
    """Seeded ScorerParams defaults the FRM tests score against."""
    from segugio.config import ScorerParams   # or from segugio.framing.params
    return ScorerParams()   # all seeded defaults; pydantic validates at construction
```
**Reuse, don't redefine:** the `seeded_rng` and `valid_config_dict` fixtures already exist — the FRM tests consume them directly (`seeded_rng` → `detection_stream`; `valid_config_dict` → build a `Config` for the zone-multiplier test, see `tests/test_config.py` for how it is parsed). The `SEED = 1234` module constant (`conftest.py:24`) is the shared determinism baseline; do not introduce a second seed.

---

### `tests/test_framing_*.py` (8 test files)

**Analog:** `tests/test_generators.py` (whole file) for determinism/shape/timeline assertions; `tests/test_imports.py` for the import-smoke; `tests/test_config.py` for config-driven cases.

**Determinism assertion** (`test_generators.py:40-49`) → `test_framing_purity.py`:
```python
def test_determinism_score_stream_same_seed_identical(scenario):
    a = score_stream(np.random.default_rng(7), scenario, CAMS, N_TICKS)
    b = score_stream(np.random.default_rng(7), scenario, CAMS, N_TICKS)
    assert a == b  # byte-identical list of frozen ScoreSamples
```
→ FRM-07: `assert run(seq) == run(seq)` over `list[CameraScore]` (works because `CameraScore` is frozen).

**Timeline-boundary parametrize** (`test_generators.py:167-189`, `test_feeddeath_timeline_boundaries`) → `test_framing_coast.py`:
```python
@pytest.mark.parametrize(
    "death_at, recover_after, alive_ticks, dead_ticks",
    [ ({"a": 4}, None, [0, 3], [4, 5, 9]), ... ],
)
def test_feeddeath_timeline_boundaries(death_at, recover_after, alive_ticks, dead_ticks):
    events = feed_death(np.random.default_rng(0), ["a"], 10, death_at=death_at, ...)
    alive = _alive_by_tick(events, "a")
    assert all(alive[t] for t in alive_ticks)
    assert all(not alive[t] for t in dead_ticks)
```
→ coast-then-lost: feed `[det×5, None×ttl_ticks]`, assert `status==coasting` for ticks `< ttl`, then `score==0.0 and status==lost` (RESEARCH line 690).

**Import-smoke with heavy deps absent** (`test_imports.py:18-48`) → `test_framing_purity.py` must add `segugio.framing` to the proven-importable surface:
```python
HEAVY_MODULES = ["torch", "ultralytics", "cyndilib", "obsws_python"]
PHASE1_SURFACE = ["segugio", "segugio.config", "segugio.synth", "segugio.logging"]
# ADD: "segugio.framing"

@pytest.mark.parametrize("module_name", PHASE1_SURFACE)
def test_phase1_surface_imports_with_heavy_deps_absent(monkeypatch, module_name):
    _force_heavy_absent(monkeypatch)
    ...
    module = importlib.import_module(module_name)
    assert module is not None
```
The FRM-07 purity test should ALSO assert `framing/` imports neither `time` nor `np.random` (a source-grep style check) — this is NEW (no Phase-1 test greps source), CONTEXT `<specifics>` and RESEARCH line 692 require it.

**Config-driven case** (`tests/test_config.py` parses `valid_config_dict` via `Config.model_validate`) → `test_framing_zone.py`: build a `Config`, place a detection center in a known band, assert `gated == base × framing_weights[role][zone]`; place outside all bands → `gated == base × out_of_bounds_factor` (RESEARCH line 688). Reuse `valid_config_dict` (its `framing_weights` are `main_wide{near1.2,mid1.0,far0.8}`, `long{mid1.1,far1.6}` — `conftest.py:93-96`).

**Conventions to copy from `test_generators.py`:** module-level `CAMS`/`N_TICKS` constants (`test_generators.py:30-31`); `@pytest.mark.parametrize` over scenarios; building the RNG explicitly via `np.random.default_rng(seed)` so the seed is visible (`test_generators.py:41`); at least one test consuming the shared `seeded_rng` fixture (`test_generators.py:52-61`).

---

## Shared Patterns

### Frozen-dataclass determinism contract
**Source:** `src/segugio/synth/score_stream.py:33-44`, `src/segugio/synth/feed_death.py:31-42`
**Apply to:** `framing/signals.py` (`DetectionSignal`, `CameraScore`), and as the `==` assertion basis in every FRM test.
```python
@dataclass(frozen=True)
class ScoreSample:
    """Frozen (hashable + comparable) so ``==`` over two lists is the determinism assertion."""
    tick: int
    cam_id: str
    score: float
```
`frozen=True` makes the records hashable + comparable; the FRM-07 test `assert run(seq) == run(seq)` depends on it. `float()`-cast all numeric fields at construction (`score_stream.py:142`) so a numpy scalar never leaks into the `==`.

### Injected-RNG + injected-tick, zero global state
**Source:** `src/segugio/synth/score_stream.py:11-19, 107-143`, `src/segugio/synth/feed_death.py:12-18`
**Apply to:** `synth/detection_stream.py` (injected `rng`), `framing/scorer.py` and `framing/terms.py` (injected `tick`, NO rng at all).
- Randomness lives ONLY in the synth generator, via an **injected `numpy.random.Generator`** — never `np.random.seed()`, never the legacy global RNG (`score_stream.py:14`, `feed_death.py:15-16`).
- Time is the **injected `tick`** integer — never `time.time()` (`score_stream.py:14`).
- The scorer has **zero randomness** (RESEARCH Anti-Pattern line 378; the scorer is the consumer of the rng-driven stream, not a producer).

### Lazy-import boundary (no heavy deps at module top-level)
**Source:** `src/segugio/synth/__init__.py:7-10`, `tests/test_imports.py:18-48`, `pyproject.toml:25-34` (heavy deps in `[heavy]` extra, imported lazily)
**Apply to:** every `framing/` and `synth/detection_stream.py` module — import only `numpy` + stdlib `dataclasses`/`collections`/`enum` + `pydantic` (via `segugio.config`). NO `torch`/`ultralytics`/`cv2`/`cyndilib` at module top-level. The `test_framing_purity.py` must add `segugio.framing` to `PHASE1_SURFACE` (`test_imports.py:20`) and keep the heavy-absent smoke green.

### Additive pydantic sub-model with bounded "tuning-seed" fields
**Source:** `src/segugio/config/models.py:93-107` (`Thresholds`), `src/segugio/config/discipline.py:22-31` (`FramingDefaults`), `src/segugio/config/models.py:113-118` (`Config` aggregation with `default_factory`)
**Apply to:** `ScorerParams` (`params.py` or `models.py`).
- `model_config = ConfigDict(extra="forbid")` (reject typo'd keys, fail-fast).
- `Annotated[float, Field(ge=, le=, gt=)]` bounds on every param; reuse `Norm = Annotated[float, Field(ge=0.0, le=1.0)]` (`models.py:45`) for `[0,1]` params.
- Wire into `Config` with `Field(default_factory=ScorerParams)` so it is **additive** (omittable; existing YAML still validates).
- "Values are tuning seeds; the schema/bounds are what's locked" docstring (matches CONTEXT: none hardcoded, all in validated config).

### Re-export via package `__init__`
**Source:** `src/segugio/synth/__init__.py:12-21`, `src/segugio/config/__init__.py:9-25`
**Apply to:** new `framing/__init__.py` (export `DetectionSignal`, `CameraScore`, `ScorerStatus`, `CameraScorer`, `MultiCamScorer`, `ScorerParams`); modified `synth/__init__.py` (add `detection_stream`); modified `config/__init__.py` (add `ScorerParams`). Pattern: `from .module import Symbol` lines + explicit `__all__` list.

### Fail-safe (clip, don't throw) in the scoring hot loop
**Source:** `src/segugio/synth/score_stream.py:53-57` (`max(n_ticks-1, 1)` divisor guard), `:104, :142` (clip-on-exit), `src/segugio/config/models.py:120-140` (validation happens at config-load, NOT in the hot loop)
**Apply to:** `framing/scorer.py`, `framing/terms.py`.
The config is validated **once** at load (the `_zones_are_weighted` validator, `models.py:120-140`); the scorer therefore must NOT re-validate or throw on data the config already passed (CONTEXT `<specifics>`, RESEARCH Security V5). Instead: `np.clip` outputs to `[0,1]`, `framing_weights[role].get(zone, 1.0)` defaults a missing key to neutral, guard every divisor (`h>0`, `speed≥deadzone`, `sqrt(var+ε)`), treat NaN/inf as "no detection" → coast. This is a NEW invariant the planner must enforce; the Phase-1 clip-on-exit convention is its closest precedent.

---

## No Analog Found

None. Every new file has a direct Phase-1 analog. Two areas are *partially new* (the analogs supply conventions, not the algorithm) — flagged so the planner pulls the algorithm from RESEARCH, not from a misfit analog:

| File | Role | Data Flow | Note |
|------|------|-----------|------|
| `src/segugio/framing/scorer.py` | service (stateful) | streaming | No stateful per-camera object exists in Phase 1 (the synth generators are stateless functions). The tick-loop/clip/float **conventions** come from `score_stream`; the **state machine + EMA + TTL + conf-norm algorithm** comes from RESEARCH.md lines 517-553 (Patterns 2/5/6/7). |
| `src/segugio/framing/terms.py` | utility (pure math) | transform | The Gaussian/lead-room/z-score **formulas** are new (no Phase-1 math analog); `_scenario_base` supplies the pure-function/guard/clip **conventions** only. Formulas are in RESEARCH.md `## Code Examples` (lines 450-515). |

---

## Metadata

**Analog search scope:** `src/segugio/` (all 10 modules), `tests/` (4 test files + conftest), `config*.example.yaml`, `pyproject.toml`. Read directly: `synth/score_stream.py`, `synth/feed_death.py`, `synth/__init__.py`, `config/models.py`, `config/discipline.py`, `config/__init__.py`, `tests/conftest.py`, `tests/test_generators.py`, `tests/test_imports.py`, both example YAMLs, `pyproject.toml`.
**Files scanned:** 22
**Key determinism/lazy-import conventions to replicate:** injected `numpy.random.Generator` (synth only) + injected integer `tick` (scorer); zero global RNG / zero wall-clock; frozen `@dataclass` with `float()`-cast fields; numpy + stdlib + pydantic only (no heavy deps at top-level); `np.clip` + divisor-guard fail-safe; additive `ConfigDict(extra="forbid")` pydantic sub-model.
**Landmines flagged:** (1) `score_stream`/`ScoreSample` emit FINAL FSM scores — NOT raw detection signals; build `detection_stream`/`DetectionSignal` fresh. (2) `FramingDefaults.hold_length_s` is a Phase-3 FSM field — the scorer reads only `lead_room`; do not implement the long occlusion hold. (3) `framing.signals` must not import `synth` (cycle) — `synth.detection_stream` depends up onto `framing.signals`.
**Pattern extraction date:** 2026-06-09
```