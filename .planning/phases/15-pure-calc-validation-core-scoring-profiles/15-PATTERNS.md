# Phase 15: Pure Calc + Validation Core & Scoring Profiles - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 6 (2 NEW src, 1 MODIFY src, profile fixtures, 2 NEW tests, 1 MODIFY test)
**Analogs found:** 6 / 6 (every file has a strong in-repo precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/ui/score_calc.py` (NEW) | utility (pure compute authority) | transform / request-response | `src/segugio/ui/score_render.py` + `src/segugio/opcomm/records.py` | exact (same crash-isolated surface, stdlib-only, frozen-dataclass) |
| `src/segugio/config/discipline.py` (MODIFY) | config / model (pydantic discriminated-union) | config-load validation | self (CFG-03 union) + `config/models.py` additive sub-models (`PreviewParams`/`OverlayParams`/`ActionHoldParams`) | exact |
| Profile→stdlib adapter (D-10) | utility (adapter, lives in `segugio.config`) | transform (pydantic → plain dataclass) | `app.py:create_app(..., cam_ids=(), overlay_cfg=None)` plain-arg injection + `__main__` lazy `load_config` | role-match (injection precedent exact; adapter fn is new) |
| Default profile YAML fixtures (CSEN/FIDASC/FCI) | config (example data) | file-I/O (yaml.safe_load → fail-fast) | `config.example.yaml` + `config.agility.example.yaml` + `config/loader.py` | exact |
| `tests/test_score_calc.py` (NEW) | test (unit) | request-response | existing `tests/` unit tests + `tests/conftest.py` fixtures | exact |
| `tests/test_score_profiles.py` (NEW) | test (unit) | config-load | `config/loader.py` `SystemExit(2)` + `conftest.tmp_config`/`valid_config_dict` | exact |
| `tests/test_imports.py` (MODIFY) | test (import-smoke gate) | request-response | self — `PHASE1_SURFACE` list + `test_console_resolves_with_heavy_stack_and_numpy_absent` | exact |

---

## Pattern Assignments

### `src/segugio/ui/score_calc.py` (NEW — utility, transform)

**Analogs:** `src/segugio/ui/score_render.py` (module shape + crash-isolation discipline), `src/segugio/opcomm/records.py` (frozen-dataclass + str-Enum conventions).

**Import discipline — mirror `score_render.py` lines 20-22** (stdlib + opcomm leaf ONLY; NO `..config`, NO numpy/cv2/torch at module top — D-09/RBT-08/Pitfall 1):
```python
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import re

from ..opcomm.records import Discipline   # str-Enum, stdlib-only leaf — already imported by score_render
```
`score_render.py` imports `from ..opcomm.records import Discipline, ScoreDoc` and nothing else — `score_calc` must stay equally clean. Reuse `Discipline` (Pitfall: do NOT define a new discipline string set — "Don't Hand-Roll" row).

**Module docstring invariant — copy `score_render.py` lines 16-18 verbatim-style** ("stdlib only — no Flask, no numpy, no heavy deps. `import ... score_calc` succeeds with the whole heavy stack absent"). This is the contract the import-smoke gate enforces.

**Frozen-dataclass `ScoringProfile` — mirror `records.py` `@dataclass(frozen=True)` style** (lines 60-77, `ScoreDoc`): frozen, `==`-comparable, immutable tuple fields (NOT dict/list — `DirectorStatus.alive` lines 149-161 and `PreviewDoc.cuts` line 205 show the tuple-of-pairs normalization that keeps a frozen dataclass hashable). The RESEARCH-recommended shape (RESEARCH lines 204-217):
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ScoringProfile:
    units: str
    zones: tuple              # ((band, Decimal(points)), ...) ordered — D-13, NOT a fixed 4-row table
    bonuses: tuple            # ((key, Decimal(value)), ...) — D-13 config-declared bonus list
    per_throw_cap: Decimal | None
    count_best_n: int | None
    freestyle_cats: tuple     # ((name, Decimal(min), Decimal(max), Decimal(increment)), ...)
    freestyle_max: Decimal
    agility_model: str        # "count_up" | "deduct_from_100"
    time_fault_rate: Decimal
    fault_value: Decimal
    elimination_sentinel: str # "E"
```

**Decimal arithmetic — exact, quantize ONLY at increment boundaries (D-09, Pitfall 4, RESEARCH lines 226-234)**:
```python
# T&F: zone points + EXACT bonus constants (never quantize a 0.5 add), cap with min(), then best-N
throw_score = zone_points + sum(bonus_values, Decimal("0"))
throw_score = min(throw_score, profile.per_throw_cap)            # cap = Decimal("5") — min(), NOT quantize
round_total = sum(sorted(throw_scores, reverse=True)[:n], Decimal("0"))   # best-N (CSEN best-5)
# Freestyle: snap each category to its 0.01 grid, then sum
cat = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
# Agility time-faults: Decimal-native ceil, no float round-trip
over = max(Decimal("0"), run - sct)
time_faults = int((over * rate).to_integral_value(rounding=ROUND_CEILING))
```

**Strict time regex (D-12, Pitfall 6, RESEARCH line 245)** — anchored, `[0-5]\d` seconds, exactly-2-digit centiseconds; a non-match is a per-field error, never a coerced 0:
```python
_TIME_RX = re.compile(r"^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$")
```

**Validate-before-compute contract (D-11, RESEARCH lines 363-376)** — `validate()` returns `list[{field, message}]` (empty == valid); `compute()` assumes valid input and returns `dict(fields)` PLUS the FLAT summary keys the renderer already reads:
```python
def validate(discipline, fields: dict, profile) -> list[dict]: ...   # [{'field': name, 'message': msg}, ...]
def compute(discipline, fields: dict, profile) -> dict:              # out = dict(fields); out['totale'] = str(total)
```
**Flat-key contract is fixed by `score_render.py`** — `render_overlay_text` reads (lines 67-82): T&F → `prese`/`zona`/`totale`; freestyle → `nome`/`timer`; agility → `tempo`/`sct`(or `SCT`)/`faults`. `compute()` MUST emit these exact keys so the display-only renderer (SCR-04) stays dumb. Elimination (D-06, Pattern 4): check the flag FIRST; if set, `result = profile.elimination_sentinel` ("E") — a string, never a number.

---

### `src/segugio/config/discipline.py` (MODIFY — config/model)

**Analog:** self (the CFG-03 `DiscDogProfile | AgilityProfile` discriminated union, lines 34-66) + the additive sub-model precedent in `config/models.py` (`PreviewParams` 146-171, `OverlayParams` 174-202, `ActionHoldParams` 128-143).

**Pydantic v2 idioms ONLY** (mandated `config/models.py` lines 9-14; v1 `class Config`/`@validator`/`parse_obj` are forbidden repo-wide — RESEARCH lines 397-400). Every sub-model uses `model_config = ConfigDict(extra="forbid")` (discipline.py lines 29, 37, 51).

**Additive sub-model with defaults so existing configs stay valid** — mirror the `OverlayParams` precedent (models.py lines 183-188): `Field(default_factory=...)` so an existing `extra="forbid"` config WITHOUT a `scoring` block still validates. The scoring sub-model attaches to the union members (`DiscDogProfile`/`AgilityProfile`) so a bad `sport`/profile raises `union_tag_invalid` at the existing fail-fast loader — no new fail-fast surface (SCP-02, "Don't Hand-Roll").

**Decimal-typed bounded fields** (RESEARCH lines 190-200):
```python
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

class ZoneBand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    band: int
    points: Annotated[Decimal, Field(ge=0)]

class Bonus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    value: Annotated[Decimal, Field(ge=0)]
# ScoringProfile pydantic model: zones: list[ZoneBand], bonuses: list[Bonus],
#   per_throw_cap, count_best_n, freestyle cats, agility model + fault/rate tables.
```
Constraint style mirrors `discipline.py` `FramingDefaults` (lines 30-31: `Annotated[float, Field(ge=0.0, le=1.0)]`) and `models.py` `Thresholds` (lines 114-125). Cross-field invariants (e.g. zones non-empty, agility_model ∈ {count_up, deduct_from_100}) go in a `@field_validator`/`@model_validator` like `models.py` `Zone._ordered` (lines 61-67) and `Config._zones_are_weighted` (lines 260-280).

---

### Profile→stdlib adapter (D-10 — utility, lives in `segugio.config`)

**Analog:** `app.py:create_app(channel_dir, cam_ids=(), overlay_cfg=None)` (line 98) — the proven plain-arg injection that hands config-derived data to the crash-isolated console WITHOUT the console importing `segugio.config`. The active profile is injected the same way.

**Adapter placement (RESEARCH Open Q3, lines 423-426):** put the adapter (`pydantic ScoringProfile → score_calc.ScoringProfile`) IN `segugio.config` (heavy tier — it may reference the pydantic model), called by the entrypoint. The console route receives only the plain frozen dataclass.

**Injection precedent — `app.py` lines 110-112 + 128-131** (the exact discipline the adapter rides):
```python
# create_app comment: overlay_cfg is "a plain dict ... resolved by the entrypoint EXACTLY like cam_ids
#   (NEVER `import segugio.config` at module top ...)"
cam_ids = frozenset(cam_ids)
overlay_cfg = {**_OVERLAY_CFG_DEFAULTS, **(overlay_cfg or {})}
```
**Entrypoint resolves it lazily** — `app.py` `__main__` block (lines 355-382) loads config inside the entrypoint and folds it into `_overlay_cfg`/`_cam_ids`; add a `profile = adapt_scoring_profile(_cfg.field.scoring)` resolution there and pass it to `create_app`. `score_calc` NEVER sees the pydantic model — only the injected dataclass arg (Pitfall 1 / RBT-08).

---

### Default scoring-profile YAML fixtures (CSEN / FIDASC / FCI — config data)

**Analogs:** `config.example.yaml` (disc_dog reference, lines 1-40) + `config.agility.example.yaml` (the `sport`-swap sibling) + `config/loader.py` (the loader they ride).

**Loader contract — `config/loader.py` lines 36-44** (`yaml.safe_load` ONLY, never `yaml.load` — T-01-02a PyYAML RCE; any parse/validation error → `SystemExit(2)`):
```python
data = yaml.safe_load(p.read_text(encoding="utf-8"))   # safe_load ONLY
...
return Config.model_validate(data)                      # ValidationError → SystemExit(2)
```
**YAML shape — mirror `config.example.yaml` lines 12-18** (the `field:` discipline block with header comments documenting the swap). The scoring sub-model nests under `field:` (it attaches to the discriminated-union member). CSEN is the shipped DEFAULT (D-01: 9/18/27/36m→1/2/3/4, two +0.5 bonuses, per_throw_cap 5, count_best_n 5; freestyle 4×(0-10, 0.01) sum to 40). FIDASC numbers are snippet-sourced — tag every value `[ASSUMED]` in comments and gate behind `checkpoint:human-verify` (D-05, RESEARCH Open Q1/Q2, Pitfall 5: FIDASC is 5 zones / single +1 / 60s / no best-N — do NOT clone CSEN's shape). FCI agility is a generic example (D-07): `count_up`, `fault_value 5`, `time_fault_rate 1/sec`, `E` sentinel.

---

### `tests/test_score_calc.py` (NEW — unit test)

**Analog:** existing `tests/` unit tests + `tests/conftest.py` fixtures (`valid_config_dict` line 148, `tmp_config` line 72; pattern: `@pytest.fixture` returning a deep-copied dict).

**Test map (RESEARCH lines 452-463)** — per-discipline validate/compute vs the pinned CSEN tables: `test_csen_tf_best5`, `test_csen_freestyle_sum`, `test_agility_count_up`, `test_agility_deduct`, `test_agility_elimination`, `test_validation_errors`, `test_decimal_exactness` (assert best-5 == `Decimal("19.0")` NOT `19.000…04` — D-09). Shared CSEN + FIDASC profile fixtures go in `conftest.py` or inline (RESEARCH Wave 0 note line 474). Run: `python -m pytest tests/test_score_calc.py -x -q`.

---

### `tests/test_score_profiles.py` (NEW — unit test, config-load)

**Analog:** `config/loader.py` `SystemExit(2)` path + `conftest.tmp_config` (writes a YAML temp file).

**Tests:** `test_profile_swap_changes_result` (SCP-01 — CSEN→FIDASC changes the computed result with NO code change, the success-criterion-3 proof) and `test_malformed_profile_fails_fast` (SCP-02 — assert `pytest.raises(SystemExit)` with code 2 on a malformed profile, riding the existing loader). Use `tmp_config(yaml_text)` (conftest line 72) to materialize a malformed profile and feed `load_config`.

---

### `tests/test_imports.py` (MODIFY — import-smoke gate)

**Analog:** self. Two concrete edits (RESEARCH lines 381-389):

1. **Extend `PHASE1_SURFACE`** (lines 27-43) — append `"segugio.ui.score_calc"` to the list (parametrized `test_phase1_surface_imports_with_heavy_deps_absent` picks it up automatically).

2. **Extend `test_console_resolves_with_heavy_stack_and_numpy_absent`** (lines 87-137) — under the existing `CONSOLE_HEAVY_MODULES` (line 25: heavy + numpy + cv2) forced-absent block, add `import segugio.ui.score_calc` (must not raise) and a `POST /score` round-trip via `app.test_client()` (the block already builds `create_app` at line 106 and exercises `client.get(...)` at line 113 — add `client.post("/score", data={...})` and assert `resp.status_code in (204, 200)`; the display-only route returns 204 today per `app.py` line 214). This proves RBT-08: the route resolves with torch/cv2/ultralytics/numpy/cyndilib/obsws absent.

---

## Shared Patterns

### Crash-isolation import discipline (RBT-08 / Pitfall 1)
**Source:** `src/segugio/ui/score_render.py` lines 16-22 (docstring contract + `from ..opcomm.records import ...` only).
**Apply to:** `score_calc.py` (module top), enforced by `tests/test_imports.py`.
`score_calc` imports ONLY `decimal`/`re`/`dataclasses`/`enum`/`math` + `opcomm.records.Discipline`. Any `from ..config` or `import numpy` at module top is a hard gate failure.

### Frozen typed records
**Source:** `src/segugio/opcomm/records.py` lines 60-77 (`@dataclass(frozen=True)`, `__post_init__` boundary coercion, str-Enum), DirectorStatus normalization 149-161, PreviewDoc 198-205.
**Apply to:** `score_calc.ScoringProfile` (use immutable tuple fields, not dict/list, so it stays hashable + `==`-comparable for round-trip tests).

### Fail-fast config validation
**Source:** `src/segugio/config/loader.py` lines 35-44 (`yaml.safe_load` + `Config.model_validate` → `SystemExit(2)`).
**Apply to:** the scoring sub-model (rides this path — no new surface) and `test_score_profiles.py::test_malformed_profile_fails_fast`.

### Additive pydantic sub-model (existing configs stay valid)
**Source:** `src/segugio/config/models.py` `OverlayParams` 174-202 + `Config` field defaults 252-258 (`Field(default_factory=...)`, `ConfigDict(extra="forbid")`, pydantic v2 idioms).
**Apply to:** the scoring sub-model in `discipline.py`.

### Plain-arg injection (config-derived data into the crash-isolated console)
**Source:** `src/segugio/ui/app.py` `create_app` line 98 + lines 110-131 + `__main__` resolution 355-382.
**Apply to:** the profile→stdlib adapter (D-10) and how `create_app`/`__main__` hands the profile to `score_calc`.

### Display-only renderer flat-key contract (SCR-04 / Pitfall 2)
**Source:** `src/segugio/ui/score_render.py` lines 67-82 (the exact flat keys `prese`/`zona`/`totale` | `nome`/`timer` | `tempo`/`sct`/`faults` the renderer reads).
**Apply to:** `compute()` output keys — `score_calc` is the SOLE compute authority; the renderer never computes.

## No Analog Found

None. Every file has a strong in-repo precedent (RESEARCH "Key insight": this phase is almost entirely assembly of existing patterns; the only genuinely new code is the `Decimal` arithmetic in `compute()` and the per-field error contract in `validate()`).

## Metadata

**Analog search scope:** `src/segugio/ui/`, `src/segugio/config/`, `src/segugio/opcomm/`, `tests/`, repo-root `config*.yaml`.
**Files scanned:** score_render.py, records.py, discipline.py, loader.py, models.py, app.py, test_imports.py, conftest.py, config.example.yaml.
**Pattern extraction date:** 2026-06-22
