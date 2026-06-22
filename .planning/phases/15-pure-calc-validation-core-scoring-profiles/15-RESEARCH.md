# Phase 15: Pure Calc + Validation Core & Scoring Profiles - Research

**Researched:** 2026-06-22
**Domain:** Pure-stdlib scoring engine (validate + compute) for disc-dog & agility, config-driven scoring profiles, crash-isolation import surface
**Confidence:** HIGH (architecture, decimal patterns, crash-isolation, CSEN numbers) / MEDIUM (FIDASC Distance numbers — cross-corroborated from snippets, official PDF 503-blocked) / LOW (FIDASC Freestyle category breakdown — multiple conflicting judging systems cited, not authoritatively pinned)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Default rule tables:**
- **D-01:** Pinned built-in **default = CSEN 2026** Italian disc-dog ruleset. International tables (UFO/USDDN/Skyhoundz) are NOT the default.
- **D-02 — CSEN Distance (Toss & Fetch):** 90-second round, **single disc**, unlimited throws but **only the best 5 count** (`count_best_n: 5`, max round = 25). Zones by meters: `9m→1`, `18m→2`, `27m→3`, `36m→4`. **Two independent +0.5 bonuses per catch**: all-four-paws-airborne, and catch-in-central-corridor. **Per-throw cap = 5**. Per-throw input shape: `{zone: <points-band>, midair: bool, corridor: bool}`.
- **D-03 — CSEN Freestyle:** 120s routine (90s min). **4 judged categories, each 0–10, in 0.01 increments, total = sum (max 40)**: `Team Elements`, `Dog (Cane)`, `Player`, `Catch Ratio`. Combine rule reduces to plain **`sum`**.

**Profile breadth:**
- **D-04:** Ship **two real disc-dog profiles**: CSEN (active default) **+ FIDASC** (alternate).
- **D-05:** **FIDASC numbers NOT yet extracted** (HTTP 503 to automated fetch). Source exact FIDASC Distance zone table + Freestyle categories/scale before building, else ship as a clearly-marked stub.

**Agility scope:**
- **D-06:** Build the **agility engine** (config-driven), defer real profile. Implement BOTH models: `count_up` (`total_faults = course_faults + time_faults`; `time_faults = rate × max(0, run_time − SCT)` with `ceil` at `rate = 1/sec`) and `deduct_from_100` (`score = 100 − course_deductions − time_faults`). **Elimination** = first-class flag overriding the numeric result with a sentinel string (e.g. `"E"`).
- **D-07:** Ship only a **generic FCI-style example** agility profile (default model `count_up`). Real Italian agility numbers deferred.

**Freestyle penalties:**
- **D-08:** Freestyle `compute()` = **4-category sum only**. CSEN deductions enter as a **single manual adjustment field** (default 0) subtracted from the total.

**Claude's Discretion (locked technical choices):**
- **D-09 — Pure-stdlib + decimal:** `score_calc` imports only stdlib (`decimal`, `re`, `dataclasses`, `enum`). All arithmetic uses `decimal.Decimal`, quantized to the profile's increment (never float). NO `import segugio.config`, NO numpy/cv2/torch at module top.
- **D-10 — Profile injection:** scoring profile declared+validated by **pydantic in `segugio.config`** (extends CFG-03 discriminated-union, fail-fast `SystemExit(2)` at config-load on malformed profile), then **adapted to a plain stdlib object/dict and INJECTED** into `score_calc` — mirroring the `cam_ids` / `overlay_cfg` plain-arg injection in `app.py:create_app`. `score_calc` never imports config models.
- **D-11 — Validate-before-compute:** `validate()` returns per-field errors (out-of-range, missing required field, malformed `mm:ss(.cc)` time, increment mismatch). `compute()` runs only after validate passes.
- **D-12 — Time format:** parse `mm:ss` and `mm:ss.cc` (hundredths) via strict regex. Agility run time uses hundredths. Malformed time → per-field validation error, never silent 0.
- **D-13 — Zone model is an ordered band list:** profile zones are an ordered list of `(band, points)`. Bonuses are a config-declared list (`[{key, value}]`).

### Claude's Discretion (research recommendations welcome)

- Exact `decimal.Decimal` quantization pattern (per-throw caps, best-N, increment rounding 0.01 / 0.5).
- Exact regex for `mm:ss` / `mm:ss.cc` and the per-field error contract shape.
- The plain-dict/dataclass shape the pydantic profile adapts into for injection.
- How `tests/test_imports.py` is extended (PHASE1_SURFACE + heavy-absent gate + POST /score round-trip).

### Deferred Ideas (OUT OF SCOPE)

- Real Italian **agility** rule tables (until an agility event is run).
- Freestyle penalty auto-modeling (nature break / excess disc / safety ranges).
- Multi-judge combination beyond `sum` (`average`, `drop_high_low`).
- Per-category freestyle overlay breakdown; auto-SCT from course length; more federation profiles.
- Combined division (freestyle×1.5 + best distance) and roster/standings.
- Any UI (Phase 16+); making `POST /score` authoritative / wiring compute into the route (Phase 16); rich additive data-model subkeys through `/overlay-json` (Phase 18).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCC-02 | Pure `score_calc` module (stdlib only, no heavy dep) encapsulating compute + validation, shared by the server and **added to the crash-isolated import surface** (covered by the import-smoke gate). | `## Architecture Patterns` (module layout, stdlib-only contract), `## Common Pitfalls` (Pitfall 1 crash-isolation), `## Validation Architecture` (import-smoke extension). |
| SCC-04 | **Per-discipline auto-calculated totals** — disc T&F: throws×zone sum (+ bonus); freestyle: single-judge criteria sum; agility: configurable model (count-up faults OR deduct) + time-faults vs SCT. | `## Code Examples` (compute per discipline), `## Architecture Patterns` (decimal quantization, best-N, ceil time-faults). |
| SCP-01 | Scoring rules are **config-driven** via a per-discipline/federation "scoring profile" (extends CFG-03 discriminated-union) so zones/points/criteria/faults/model change with no code edits. | `## Architecture Patterns` (profile schema, ordered band list D-13), `## Code Examples` (CSEN vs FIDASC profiles). |
| SCP-02 | A sensible **default profile** ships with v1.3; the profile is validated **fail-fast at config-load** (clear error on malformed profile). | `## Architecture Patterns` (pydantic discriminated-union, fail-fast loader `SystemExit(2)`), `## Don't Hand-Roll` (reuse loader). |
| RBT-08 | **Crash-isolation preserved & re-verified** — console imports only `Flask + segugio.opcomm + score_calc` (pure); import-smoke test extended to new modules/routes; `POST /score` resolves with the heavy stack absent (torch/cv2/ultralytics/numpy/cyndilib/obsws). | `## Common Pitfalls` (Pitfall 1), `## Validation Architecture` (gate extension), `## Code Examples` (test extension). |
</phase_requirements>

## Summary

Phase 15 builds `segugio/ui/score_calc.py`: a single, pure-stdlib (`decimal`, `re`, `dataclasses`, `enum`) authority that exposes `validate(discipline, fields, profile) → per-field errors` and `compute(discipline, fields, profile) → totals` for three disciplines (disc Toss&Fetch, disc Freestyle, agility), driven entirely by an injected **scoring profile**. Every pattern this phase needs already exists in the shipped v1.2 codebase: the pydantic discriminated-union config (`config/discipline.py`), the fail-fast `SystemExit(2)` loader (`config/loader.py`), the plain-arg injection precedent (`app.py:create_app(channel_dir, cam_ids=(), overlay_cfg=None)`), the display-only renderer (`score_render.py`), and the heavy-absent import-smoke gate (`tests/test_imports.py`). There is **zero new external dependency** — all arithmetic is `decimal.Decimal` per D-09. This is "standard pure-logic work" (SUMMARY.md research flag); the only real research risk was sourcing FIDASC's numbers, addressed below.

The keystone tension SCP-01 (config-driven profile, ideally pydantic) vs RBT-08 (crash-isolation, `score_calc` must NOT import `segugio.config`) is resolved by D-10: pydantic validates the profile **in `segugio.config`**, then the profile is **adapted to a plain stdlib object/dict and injected** into `score_calc` exactly like `cam_ids`/`overlay_cfg`. `score_calc` stays import-clean; the pydantic model lives in the config layer where heavy deps are tolerated. The FIDASC sourcing (D-05) succeeded **partially**: the Distance zone bands are cross-corroborated from two independent snippets of the official PDF (`9/18/27/36m → 1/2/3/4`, 5th-zone field at 45m, a **+1 central-corridor bonus only in the 5th zone**, 60s, no visible best-N), but the official PDF endpoint stays HTTP 503 to all automated fetch paths (including Wayback, which the harness cannot reach), and the **Freestyle category breakdown is NOT authoritatively pinned** — sources cite three different judging systems. Recommendation: ship FIDASC Distance as a **real-but-FLAGGED** profile (numbers from snippets, `[ASSUMED]`, gated behind a `checkpoint:human-verify`) and FIDASC Freestyle as a **clearly-marked stub** (40-max sum confirmed; the 4 category names/scale are a TODO). Critically, FIDASC's structure differs materially from CSEN (5 zones not 4, single +1 bonus not two +0.5, 60s not 90s, no best-5) — which is exactly the cross-federation divergence that **proves** success-criterion 3 (swap changes the result with no code edit).

**Primary recommendation:** Build `score_calc.py` as a pure stdlib module with a `dataclass`-typed `ScoringProfile` (ordered `(band, points)` zone list + bonus list + freestyle category list + agility model enum), `validate()` returning `list[{field, message}]`, and `compute()` returning the existing flat summary keys (`prese`/`zona`/`totale` for T&F, `nome`/`timer`/`totale` for freestyle, `tempo`/`sct`/`faults`/`result` for agility) via `decimal.Decimal`. Ship CSEN as the verified default, FIDASC Distance flagged + FIDASC Freestyle stubbed, a generic FCI agility example. Extend `PHASE1_SURFACE` and the heavy-absent gate.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Score validation (ranges, time format, increments) | `score_calc.py` (pure compute) | — | Authority must be the same code path the server trusts; pure & testable with no UI risk. |
| Score computation (sums, best-N, time-faults) | `score_calc.py` (pure compute) | — | Single authority (Pitfall 2 double-source). `decimal.Decimal` arithmetic stays on one path. |
| Profile schema declaration + validation | `segugio.config` (pydantic) | — | Heavy-dep-tolerant tier; CFG-03 discriminated-union + fail-fast loader live here (SCP-02). |
| Profile injection into the calc | `app.py:create_app` entrypoint (plain-arg) | `segugio.config` (loads), `__main__` (resolves) | D-10: mirrors `cam_ids`/`overlay_cfg`; keeps `score_calc` import-surface clean (RBT-08). |
| Overlay text rendering | `score_render.py` (display-only) | — | SCR-04 invariant: renderer formats, never computes. `score_calc` is the compute authority. |
| Crash-isolation enforcement | `tests/test_imports.py` (gate) | — | Build-time gate; every `segugio.ui` module must import with the heavy stack + numpy absent. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `decimal` | 3.12 (CPython, already present) | Exact arithmetic for all scoring totals (D-09 — never float) | Avoids `0.1+0.2` broadcast drift; the on-air total must be exact. Already the project decision. `[VERIFIED: python 3.12.10 in venv]` |
| Python stdlib `re` | 3.12 | Strict `mm:ss(.cc)` time parsing (D-12) | One regex, no dependency; rejects `99:60`/`2:5`/single-digit cc (verified below). `[VERIFIED: this session]` |
| Python stdlib `dataclasses` | 3.12 | `ScoringProfile` plain-object shape + frozen records (mirrors `opcomm/records.py`) | The in-repo convention for typed records that import clean (`@dataclass(frozen=True)`). `[CITED: src/segugio/opcomm/records.py]` |
| Python stdlib `enum` | 3.12 | `Discipline` reuse + `AgilityModel` enum (`count_up` / `deduct_from_100`) | `str`-Enum convention already used by `Discipline` in `opcomm/records.py`. `[CITED: src/segugio/opcomm/records.py]` |
| pydantic | 2.13.4 (already pinned, both venvs) | Declarative profile validation **in `segugio.config` ONLY** (D-10) — never imported by `score_calc` | CFG-03 discriminated-union pattern already in `config/discipline.py`; fail-fast `SystemExit(2)` already in `config/loader.py`. `[CITED: src/segugio/config/models.py]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `math` | 3.12 | `ceil` for time-faults (D-06) — OR use `Decimal.to_integral_value(ROUND_CEILING)` | Time-fault whole-fault rounding. Decimal-native ceil preferred to stay float-free (verified equal below). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `decimal.Decimal` | `float` | REJECTED by D-09 — float drift on a broadcast total is the exact bug the project pays to avoid. |
| Inject a plain dict/dataclass | `import segugio.config` in `score_calc` | REJECTED by D-10/RBT-08 — breaks crash-isolation (Pitfall 1). The pydantic model stays in the config tier. |
| `math.ceil(float(over))` | `Decimal.to_integral_value(ROUND_CEILING)` | Both give the same result (verified); the Decimal-native path avoids a float round-trip entirely — prefer it for purity. |

**Installation:**

```bash
# NO new packages. Everything is Python stdlib or already-pinned pydantic 2.13.4.
# Verify pydantic presence (already used by segugio.config):
python -c "import pydantic; print(pydantic.VERSION)"   # → 2.13.4
```

**Version verification:** `python --version` → 3.12.10 (venv312) `[VERIFIED: this session]`. `decimal`, `re`, `dataclasses`, `enum`, `math` are all stdlib — no registry check needed. pydantic 2.13.4 is already imported by `segugio.config` (no new install).

## Package Legitimacy Audit

> This phase installs **NO external packages**. All code is Python stdlib (`decimal`, `re`, `dataclasses`, `enum`, `math`) plus the already-pinned pydantic 2.13.4 used only in the `segugio.config` tier (not by `score_calc`).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | No new dependency introduced |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         CONFIG LOAD TIME (heavy-dep-tolerant tier)
  config.yaml ──► config/loader.load_config (yaml.safe_load)
                       │  pydantic Config.model_validate  ── malformed → SystemExit(2) (SCP-02, fail-fast)
                       ▼
                  Config.field (CFG-03 discriminated union: DiscDogProfile | AgilityProfile)
                       │  + NEW: scoring sub-model (zones/bonuses/freestyle cats/agility model)
                       ▼
  __main__ / create_app entrypoint ── adapt pydantic profile ──► plain dict / ScoringProfile dataclass
                       │  (D-10: EXACTLY the cam_ids / overlay_cfg plain-arg injection)
                       ▼
  ════════════════════ CRASH-ISOLATION BOUNDARY (segugio.ui: Flask + opcomm + score_calc only) ════════════════════
                       │
  POST /score (Phase 16 wires this; Phase 15 builds the callee)
        raw fields ────┼────► score_calc.validate(discipline, fields, profile)
                       │            │ errors? ──► [{field, message}, ...]  (Phase 16: 400, write nothing — D-11)
                       │            ▼ valid
                       └────► score_calc.compute(discipline, fields, profile)
                                    │ Decimal arithmetic, quantized to profile increment (D-09)
                                    ▼
                              fields + FLAT summary keys (prese/zona/totale | nome/timer/totale | tempo/sct/faults/result)
                                    │
                                    ▼
                              score_render.render_overlay_text  (display-only, reads flat keys — SCR-04)
                                    ▼
                              overlay.txt (OBS fallback) + score.json + /overlay-json
```

### Recommended Project Structure

```
src/segugio/
├── config/
│   ├── discipline.py     # MODIFIED: add a scoring sub-model to DiscDogProfile/AgilityProfile (CFG-03 union)
│   ├── models.py         # (Config root already aggregates field: FieldProfile — scoring rides the union)
│   └── loader.py         # UNCHANGED: fail-fast SystemExit(2) already rejects a malformed profile (SCP-02)
└── ui/
    ├── score_calc.py     # NEW: pure stdlib validate() + compute() + ScoringProfile dataclass + builtin profiles
    └── score_render.py   # UNCHANGED: display-only renderer reads the flat keys compute() produces

tests/
├── test_score_calc.py    # NEW: per-discipline validate/compute unit tests vs pinned CSEN rule tables
├── test_score_profiles.py# NEW: profile-swap (CSEN vs FIDASC changes result) + malformed-profile fail-fast
└── test_imports.py       # MODIFIED: score_calc → PHASE1_SURFACE; heavy-absent gate + POST /score round-trip
```

### Pattern 1: Pydantic-validate-in-config, plain-inject-into-calc (D-10 — resolves SCP-01 ↔ RBT-08)

**What:** The profile is a pydantic sub-model attached to the CFG-03 discriminated union in `config/discipline.py` (so a malformed profile raises a `ValidationError` aggregated into the loader's `SystemExit(2)` — SCP-02, no new fail-fast surface needed). The entrypoint adapts the validated pydantic object into a plain `ScoringProfile` dataclass (or dict) and passes it into `score_calc` functions as an argument.

**When to use:** Always — this is the keystone that keeps `score_calc` import-clean.

**Example:**
```python
# config/discipline.py — pydantic profile (heavy tier; fail-fast at load)
# Source: extends the CFG-03 union in src/segugio/config/discipline.py
class ZoneBand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    band: int                      # ordinal/label (D-13: ordered list, NOT a fixed 4-row table)
    points: Annotated[Decimal, Field(ge=0)]
class Bonus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str                       # e.g. "midair", "corridor"
    value: Annotated[Decimal, Field(ge=0)]
# ... ScoringProfile pydantic model with zones: list[ZoneBand], bonuses: list[Bonus],
#     per_throw_cap, count_best_n, freestyle categories, agility model + fault/rate tables.
```
```python
# score_calc.py — plain stdlib mirror INJECTED in (NO pydantic, NO config import)
# Source: mirrors @dataclass(frozen=True) convention in src/segugio/opcomm/records.py
@dataclass(frozen=True)
class ScoringProfile:
    units: str
    zones: tuple              # ((band, Decimal(points)), ...) ordered
    bonuses: tuple            # ((key, Decimal(value)), ...)
    per_throw_cap: Decimal | None
    count_best_n: int | None
    freestyle_cats: tuple     # ((name, Decimal(min), Decimal(max), Decimal(increment)), ...)
    freestyle_max: Decimal
    agility_model: str        # "count_up" | "deduct_from_100"
    time_fault_rate: Decimal
    fault_value: Decimal      # or a {fault_name: value} map
    elimination_sentinel: str # "E"
```

### Pattern 2: Decimal quantization — quantize sums, NOT bonuses (D-09)

**What:** Add per-throw zone points + bonuses as exact `Decimal` literals; quantize only at the increment boundaries the profile defines. **Do NOT quantize a 0.5 bonus to a 0.5 grid** — quantizing `4.25 → 0.5` yields `4.3` (wrong, verified below). Bonuses are exact additive `Decimal("0.5")` constants; the freestyle sum quantizes to `0.01`.

**When to use:** Every arithmetic step in `compute()`.

**Example:**
```python
# Source: verified in this session (see Code Examples)
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
# T&F per-throw: zone points + exact bonuses, capped, then best-N
throw_score = zone_points + sum(bonus_values, Decimal("0"))          # exact, no quantize on a 0.5 add
throw_score = min(throw_score, profile.per_throw_cap)                # cap = Decimal("5")
round_total = sum(sorted(throw_scores, reverse=True)[:n], Decimal("0"))  # best-N
# Freestyle: snap each category to its 0.01 increment, then sum
cat = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### Pattern 3: Strict `mm:ss(.cc)` parse → per-field error, never silent 0 (D-12)

**What:** One anchored regex; centiseconds are exactly two digits when present; seconds are `00–59`. A non-match is a validation error, not a coerced 0.

**Example:**
```python
# Source: verified in this session
import re
_TIME_RX = re.compile(r"^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$")
# matches "01:30", "1:05.47"; rejects "99:60", "2:5", "01:30.4" (single-digit cc)
```

### Pattern 4: Elimination sentinel overrides the numeric result (D-06)

**What:** Agility `compute()` checks the elimination flag FIRST; if set, `result = profile.elimination_sentinel` (`"E"`) — a string the overlay renders verbatim, never a number. The numeric branch (`count_up` or `deduct_from_100`) only runs when not eliminated.

### Anti-Patterns to Avoid

- **Importing `segugio.config` into `score_calc`** (Pitfall 1 / RBT-08): breaks crash-isolation. Inject a plain object instead (D-10).
- **Computing in `float`** (D-09): broadcast totals must be exact. Use `Decimal` end-to-end.
- **Quantizing a bonus to its own grid**: `Decimal("4.25").quantize(Decimal("0.5"))` → `4.3` (wrong). Add bonuses as exact constants; quantize only the freestyle category to `0.01`.
- **Hard-coding 4 zone rows**: D-13 mandates an ordered band list so FIDASC's 5 bands and CSEN's 4 both express. A fixed table breaks the moment FIDASC loads.
- **Coercing a malformed time to 0** (D-12): a silent 0 airs a wrong score. Return a per-field error.
- **Computing in the renderer**: `score_render.py` is display-only (SCR-04). Keep it dumb.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Malformed-profile rejection | A new validation/exit path in `score_calc` | The existing `config/loader.py` fail-fast `SystemExit(2)` + pydantic `ValidationError` | SCP-02 is already satisfied by the CFG-03 union + loader; a malformed profile rides the existing path. `[CITED: src/segugio/config/loader.py]` |
| Profile injection plumbing | A bespoke config-passing mechanism | The `cam_ids` / `overlay_cfg` plain-arg pattern in `create_app` | D-10 — already proven, keeps the import surface clean. `[CITED: src/segugio/ui/app.py:98]` |
| Frozen typed records | Ad-hoc tuples/dicts everywhere | `@dataclass(frozen=True)` (the `opcomm/records.py` convention) | Hashable + `==`-comparable so round-trip equality tests work; matches the in-repo style. `[CITED: src/segugio/opcomm/records.py]` |
| Exact decimal rounding | Float math + manual `round()` | `Decimal.quantize(..., ROUND_HALF_UP)` / `to_integral_value(ROUND_CEILING)` | Stdlib does it correctly and float-free. `[VERIFIED: this session]` |
| Discipline enum | A new string set | Reuse `opcomm.records.Discipline` (`disc_tf`/`disc_freestyle`/`agility`) | Already the closed enum the renderer + ScoreDoc use; `validate(discipline, ...)` should accept it. `[CITED: src/segugio/opcomm/records.py]` |

**Key insight:** This phase is almost entirely assembly of existing in-repo patterns. The only genuinely new code is the `Decimal` arithmetic in `compute()` and the per-field error contract in `validate()` — everything structural (discriminated union, fail-fast loader, plain-arg injection, frozen records, display-only renderer, import-smoke gate) is reused.

## Runtime State Inventory

> Greenfield additive phase (new pure module + new config sub-model + extended tests). No rename/refactor/migration. **No stored data, live-service config, OS-registered state, secrets, or build artifacts carry a renamed string** — verified: this phase adds files and a config sub-model, it does not rename anything. Section otherwise omitted.

## Common Pitfalls

### Pitfall 1: Crash-isolation breach — a heavy import sneaks into `score_calc`

**What goes wrong:** `score_calc.py` imports `segugio.config` (for the profile), or numpy/cv2/torch, and the heavy-absent import-smoke gate fails — or worse, the console process pulls in the AI stack.
**Why it happens:** The profile schema is pydantic and lives in `segugio.config`; the naive move is to import it.
**How to avoid:** D-10 — pydantic validates in `segugio.config`; the profile is adapted to a plain dataclass/dict and **injected** as an argument. `score_calc` imports only `decimal`/`re`/`dataclasses`/`enum`/`math` (+ `opcomm.records.Discipline`, which is stdlib-only). Add `score_calc` to `PHASE1_SURFACE`.
**Warning signs:** Any `from ..config` or `import numpy` at `score_calc` module top; the gate test going red.

### Pitfall 2: Double source of truth — the displayed total disagrees with what airs

**What goes wrong:** A second place computes the total (a JS port in Phase 16, or the renderer) and drifts from `score_calc`.
**Why it happens:** Convenience live-feedback math duplicated outside the authority.
**How to avoid:** `score_calc.py` is the SOLE compute authority this phase. The renderer stays display-only (SCR-04). Phase 16's JS port is advisory + drift-guarded; Phase 15 simply must not put any compute in the renderer.
**Warning signs:** `totale` computed anywhere other than `score_calc.compute()`.

### Pitfall 3: Float drift on the broadcast total

**What goes wrong:** `0.5 + 0.5 + 4` or a `0.01`-increment sum accumulates float error; an "impossible" total airs.
**Why it happens:** Defaulting to `float`.
**How to avoid:** D-09 — `Decimal` end-to-end, quantized to the profile increment. Verified patterns in `## Code Examples`.
**Warning signs:** Any `float(...)` in the arithmetic path; a test total like `19.000000000000004`.

### Pitfall 4: Quantizing a bonus to its own grid

**What goes wrong:** `Decimal("4.25").quantize(Decimal("0.5"))` → `4.3`, silently wrong; per-throw cap math then misbehaves.
**Why it happens:** Over-applying `quantize` to every step.
**How to avoid:** Add bonuses as exact `Decimal` constants; quantize ONLY where the profile defines an increment (freestyle `0.01`). Cap with `min(...)`, not quantize.
**Warning signs:** A bonus catch scoring `4.3` instead of `4.5`/`5`.

### Pitfall 5: FIDASC's structural divergence treated as "same as CSEN"

**What goes wrong:** The FIDASC profile is built as a CSEN clone with swapped numbers, but FIDASC actually uses **5 zones (45m field), a single +1 corridor bonus only in the 5th zone, 60s, and no visible best-N** — materially different shape.
**Why it happens:** The official PDF is 503-blocked; the temptation is to assume CSEN's shape.
**How to avoid:** The D-13 ordered-band-list + config-bonus-list design already accommodates this. Mark FIDASC numbers `[ASSUMED]` (snippet-sourced) and gate behind a `checkpoint:human-verify`. Treat FIDASC Freestyle's category breakdown as a stub (see Open Questions).
**Warning signs:** FIDASC profile hardcodes `count_best_n: 5` or two +0.5 bonuses (those are CSEN-only).

### Pitfall 6: `mm:ss.cc` regex too loose

**What goes wrong:** `99:60` or `01:30.4` (single-digit cc) parses as valid; a garbage time produces a garbage SCT comparison.
**Why it happens:** A permissive `\d+:\d+` regex.
**How to avoid:** Anchored regex with `[0-5]\d` seconds and exactly-two-digit centiseconds (verified). Malformed → per-field error.
**Warning signs:** A test feeding `2:5` or `01:30.4` returns a parsed time instead of an error.

## Code Examples

Verified patterns (all run in this session against Python 3.12.10):

### Decimal quantization, best-N, increment-mismatch, ceil, time-regex
```python
# Source: verified in this session (gsd research bash run)
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import re

# 1) Freestyle category snap to 0.01 (HALF_UP)
Decimal("8.005").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)   # → 8.01

# 2) T&F best-5-of-N (CSEN D-02), per-throw already capped at 5
throws = [Decimal("4.5"), Decimal("5"), Decimal("1"), Decimal("3.5"), Decimal("2"), Decimal("4")]
sum(sorted(throws, reverse=True)[:5], Decimal("0"))                   # → 19.0

# 3) Increment-mismatch validation (is x a multiple of the increment?)
def on_increment(x: Decimal, inc: Decimal) -> bool:
    q = x / inc
    return q == q.to_integral_value()
on_increment(Decimal("8.00"),  Decimal("0.01"))                      # → True
on_increment(Decimal("8.005"), Decimal("0.01"))                     # → False (error: not on grid)

# 4) Agility time-faults, ceil at rate (D-06) — Decimal-native, no float
def time_faults(rate: Decimal, run: Decimal, sct: Decimal) -> int:
    over = max(Decimal("0"), run - sct)
    return int((over * rate).to_integral_value(rounding=ROUND_CEILING))
time_faults(Decimal("1"), Decimal("52.40"), Decimal("50"))           # → 3

# 5) Strict mm:ss(.cc) parse (D-12)
_TIME_RX = re.compile(r"^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$")
bool(_TIME_RX.match("1:05.47"))   # True
bool(_TIME_RX.match("99:60"))     # False
bool(_TIME_RX.match("2:5"))       # False
bool(_TIME_RX.match("01:30.4"))   # False (centiseconds must be 2 digits)
```

### Validate-before-compute contract shape (D-11)
```python
# Source: derived from D-11 + the existing _NON_SCORE_KEYS / ScoreDoc.fields shape in app.py
def validate(discipline, fields: dict, profile) -> list[dict]:
    """Return [{'field': name, 'message': msg}, ...]; empty list == valid."""
    errors: list[dict] = []
    # ... per-discipline: required fields present, ranges, increment snap, mm:ss(.cc) time ...
    return errors

def compute(discipline, fields: dict, profile) -> dict:
    """Caller runs validate() FIRST; compute() assumes valid input (Phase-16 flow:
       validate → 400 + write-nothing on errors → else compute). Returns fields PLUS
       the flat summary keys score_render reads (totale / result / etc.)."""
    out = dict(fields)
    # ... Decimal arithmetic per discipline; set out['totale'] = str(round_total) ...
    return out
```

### Import-smoke gate extension (RBT-08)
```python
# Source: extends tests/test_imports.py (read 2026-06-22)
# 1) Add to PHASE1_SURFACE:
PHASE1_SURFACE = [ ..., "segugio.ui", "segugio.ui.score_calc", ... ]
# 2) In test_console_resolves_with_heavy_stack_and_numpy_absent, under the heavy-absent block:
import segugio.ui.score_calc  # must not raise with torch/cv2/ultralytics/numpy/cyndilib/obsws absent
# 3) POST /score round-trip under the same block (Phase 15 keeps the display-only route;
#    Phase 16 makes it authoritative). With the heavy stack absent:
resp = client.post("/score", data={"discipline": "disc_tf", "prese": "3", "zona": "2", "totale": "6"})
assert resp.status_code in (204, 200)   # route resolves with no heavy import
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Display-only `/score` (operator types the total; renderer formats verbatim) | Server-authoritative `score_calc.compute()` (operator posts raw inputs; server computes) | v1.3 (Phase 15 builds the calc; Phase 16 wires the route) | The total becomes computed, not typed — broadcast integrity. Phase 15 builds the authority standalone. |
| Hardcoded per-discipline field sets | Config-driven scoring profiles (per federation) | v1.3 | One tool covers CSEN/FIDASC/FCI without code edits (SCP-01). |
| pydantic v1 idioms | pydantic v2 (`ConfigDict(extra="forbid")`, `field_validator`, `model_validate`) | Already adopted repo-wide | The scoring sub-model MUST use v2 idioms (`config/models.py` docstring mandates it). `[CITED: src/segugio/config/models.py:9-14]` |

**Deprecated/outdated:**
- pydantic v1 `class Config` / `@validator` / `parse_obj` — forbidden repo-wide; use v2 idioms for the new sub-model.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FIDASC Distance zones = `9/18/27/36m → 1/2/3/4`, 5th zone to 45m, **+1 central-corridor bonus only in the 5th zone**, 60s, single disc, no visible best-N. | Open Questions / Code Examples | A wrong FIDASC profile airs a wrong score at a FIDASC event. Snippet-corroborated (two independent official-PDF snippets agree) but the PDF is 503-blocked — gate behind `checkpoint:human-verify`. |
| A2 | FIDASC Freestyle = 4-category sum to max 40 (the 40-max is confirmed; the **category names + per-category scale/increment are NOT pinned** — sources cite UFO-D.I.S.C. ×0.1, Judge'n'Play multi-element, and UISP SEIS ×0.1 systems). | Open Questions | Building the wrong category set/scale. Ship as a clearly-marked stub (D-05 fallback); do NOT invent the 4 names. |
| A3 | The generic FCI agility example uses `fault_value = 5`, `time_fault_rate = 1/sec`, `count_up` default, `E` on 3 refusals/over-MCT. | Code Examples | Low — D-07 explicitly ships a *generic example*, not a pinned federation; the engine (both models) is what SCC-04 requires. Real numbers deferred. |
| A4 | Adding the scoring sub-model to the CFG-03 union does not require a new fail-fast surface (rides the existing loader `SystemExit(2)`). | Don't Hand-Roll | Low — verified the loader aggregates any `ValidationError` into `SystemExit(2)`; an additive `extra="forbid"` sub-model with defaults keeps existing configs valid (the `scoring`/`preview`/`overlay` precedent). |

## Open Questions

1. **FIDASC Distance exact table (D-05 — the REQ blocker for the "two real federations" success path)**
   - What we know: Cross-corroborated from two independent snippets of the official FIDASC 2025 PDF: **5 zones on a 45m field (9/18/27/36/45m), points 1/2/3/4 for zones 1–4, a 6m-wide central bonus corridor in the 5th zone granting +1, 60s, single disc, "paw nearest the throw line counts" on-the-line rule, a throw is null if the dog steps on/over the field boundary.** No `count_best_n` rule appears in the snippets.
   - What's unclear: Whether the 5th zone itself scores base points (snippets imply the +1 bonus *adds to the 5th-zone score* but the 5th-zone base value is not explicit), and whether there is any best-N cap.
   - Recommendation: Ship FIDASC Distance as a **real-but-FLAGGED** profile using `9/18/27/36→1/2/3/4` + a 5th band + a single `+1` corridor bonus, tag every number `[ASSUMED]`, and gate the profile behind a `checkpoint:human-verify` task that re-fetches the PDF manually (the user has the URL). The D-13 ordered-band-list design accommodates whatever the manual check confirms with no code change. This still proves success-criterion 3 because FIDASC's shape (5 zones, single +1, 60s, no best-5) genuinely differs from CSEN.

2. **FIDASC Freestyle categories + scale (D-05)**
   - What we know: Max 40, 90s routine (per the search snippet of the FIDASC PDF), 10 discs max. The 4-category-sum-to-40 *shape* matches CSEN.
   - What's unclear: The **exact category names and per-category increment** are NOT authoritatively pinned — sources cite three different judging systems (UFO D.I.S.C. ×0.1, Judge'n'Play multi-element, UISP SEIS ×0.1). The official PDF (503) is the only authority.
   - Recommendation: Ship FIDASC Freestyle as a **clearly-marked stub** with a `TODO` and the confirmed `freestyle_max = 40`; do NOT invent the 4 category names. Same `checkpoint:human-verify` gate. CSEN Freestyle (4×0–10 ×0.01 sum) is fully pinned and is the verified default — the milestone's freestyle correctness is proven against CSEN, not FIDASC.

3. **Where the adapted plain profile lives (the adapter function)**
   - What we know: D-10 says adapt pydantic → plain object at the entrypoint, mirroring `cam_ids`/`overlay_cfg`.
   - What's unclear: Whether the adapter (`pydantic ScoringProfile → score_calc.ScoringProfile`) lives in `segugio.config` (heavy tier) or in `__main__`/`create_app`.
   - Recommendation: Put the adapter in `segugio.config` (it may reference the pydantic model) and have `create_app`/`__main__` call it, exactly as `__main__` already calls `load_config` lazily inside the entrypoint and passes `overlay_cfg` plain dicts to `create_app`. `score_calc` only ever sees the plain dataclass.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib (`decimal`/`re`/`dataclasses`/`enum`/`math`) | `score_calc.py` | ✓ | 3.12.10 (venv312) | — |
| pydantic | `segugio.config` profile sub-model | ✓ | 2.13.4 (both venvs) | — |
| pytest | unit + import-smoke tests | ✓ | (in venv) | — |
| FIDASC official rulebook PDF (`fidasc.it/.../file.html`) | FIDASC profile exact numbers (D-05) | ✗ | — | Snippet-sourced numbers `[ASSUMED]` + `checkpoint:human-verify`; FIDASC Freestyle stubbed. CSEN (fully pinned) carries the milestone's correctness proof. |

**Missing dependencies with no fallback:** none (all code deps present).
**Missing dependencies with fallback:** the FIDASC PDF — fallback is the flagged/stub profile + human-verify gate (see Open Questions 1 & 2).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already the project framework; `tests/test_imports.py`, `tests/conftest.py` present) |
| Config file | `pyproject.toml` / existing pytest setup (tests run from venv312) |
| Quick run command | `python -m pytest tests/test_score_calc.py -x -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCC-04 | CSEN T&F best-5 sum + per-throw cap 5 + two +0.5 bonuses against pinned table | unit | `python -m pytest tests/test_score_calc.py::test_csen_tf_best5 -x` | ❌ Wave 0 |
| SCC-04 | CSEN Freestyle 4×(0–10, 0.01) sum to max 40 | unit | `python -m pytest tests/test_score_calc.py::test_csen_freestyle_sum -x` | ❌ Wave 0 |
| SCC-04 | Agility `count_up`: course_faults + ceil(rate×max(0,run−SCT)) | unit | `python -m pytest tests/test_score_calc.py::test_agility_count_up -x` | ❌ Wave 0 |
| SCC-04 | Agility `deduct_from_100`: 100 − deductions − time_faults | unit | `python -m pytest tests/test_score_calc.py::test_agility_deduct -x` | ❌ Wave 0 |
| SCC-04 | Agility elimination flag → `"E"` sentinel (never a number) | unit | `python -m pytest tests/test_score_calc.py::test_agility_elimination -x` | ❌ Wave 0 |
| SCC-04/D-11 | Invalid input (out-of-range, missing required, malformed `mm:ss(.cc)`, off-increment) → per-field error, NO compute | unit | `python -m pytest tests/test_score_calc.py::test_validation_errors -x` | ❌ Wave 0 |
| SCP-01 | Swapping CSEN→FIDASC profile changes the computed result with NO code change | unit | `python -m pytest tests/test_score_profiles.py::test_profile_swap_changes_result -x` | ❌ Wave 0 |
| SCP-02 | Malformed profile fails fast at config-load with a clear error (`SystemExit(2)`) | unit | `python -m pytest tests/test_score_profiles.py::test_malformed_profile_fails_fast -x` | ❌ Wave 0 |
| SCC-02/RBT-08 | `score_calc` imports clean with the full heavy stack + numpy absent | import-smoke | `python -m pytest tests/test_imports.py -k score_calc -x` | ⚠️ extend existing |
| RBT-08 | `POST /score` round-trip resolves with the heavy stack + numpy absent | import-smoke | `python -m pytest tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent -x` | ⚠️ extend existing |
| D-09 | Totals are exact `Decimal` (no float drift; e.g. best-5 == `19.0` not `19.000…04`) | unit | `python -m pytest tests/test_score_calc.py::test_decimal_exactness -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_score_calc.py tests/test_score_profiles.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite, incl. import-smoke gate)
- **Phase gate:** Full suite green (incl. the extended crash-isolation gate) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_score_calc.py` — per-discipline validate/compute vs pinned CSEN rule tables (covers SCC-04, D-09, D-11)
- [ ] `tests/test_score_profiles.py` — profile-swap (SCP-01) + malformed-profile fail-fast (SCP-02)
- [ ] `tests/test_imports.py` — extend `PHASE1_SURFACE` with `segugio.ui.score_calc` + add `import segugio.ui.score_calc` and a `POST /score` round-trip to the heavy-absent gate (RBT-08, SCC-02)
- [ ] No framework install needed (pytest already present). Shared fixtures: a CSEN profile fixture + a FIDASC profile fixture (in `conftest.py` or inline).

## Security Domain

> `security_enforcement` is not disabled in config; included. This phase is pure compute with no auth/session/network surface, but two input-boundary controls apply.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | The console LAN is the trust boundary (D-02, accepted no-auth); unchanged by this phase. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No access control surface. |
| V5 Input Validation | **yes** | `validate()` rejects out-of-range/missing/malformed inputs (D-11). The renderer already length-bounds + strips control chars (`score_render._clean`, T-05-05-02) — preserve that; `compute()` outputs feed it. |
| V6 Cryptography | no | No crypto. |
| V12 Files/Resources | **yes** | Profile is config-loaded via `yaml.safe_load` ONLY (never `yaml.load` — T-01-02a PyYAML RCE) — the existing loader already enforces this; the new sub-model rides it. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed profile YAML reaching the live loop | Tampering / DoS | Fail-fast `SystemExit(2)` at config-load (CFG-01, existing loader) — SCP-02. |
| Crafted score value injecting extra overlay lines | Tampering | `score_render._clean` strips CR/LF + control chars + length-caps (T-05-05-02) — already shipped; `compute()` must not bypass it. |
| Heavy import breaking crash-isolation | DoS (AI loop starvation via UI process) | `score_calc` stdlib-only + import-smoke gate (RBT-08, Pitfall 1). |
| Float drift airing an impossible total | Integrity | `Decimal` end-to-end (D-09). |

## Sources

### Primary (HIGH confidence — in-repo, read 2026-06-22)
- `src/segugio/config/discipline.py` — CFG-03 discriminated union the scoring profile extends
- `src/segugio/config/loader.py` — fail-fast `yaml.safe_load` + `SystemExit(2)` (SCP-02 path)
- `src/segugio/config/models.py` — `Config` root, pydantic v2 idioms mandate, additive-sub-model precedent (`scoring`/`preview`/`overlay`)
- `src/segugio/ui/app.py` — `create_app(channel_dir, cam_ids=(), overlay_cfg=None)` plain-arg injection (D-10 precedent), the display-only `POST /score` (`post_score`, line 193)
- `src/segugio/ui/score_render.py` — `render_overlay_text` display-only invariant (SCR-04), flat summary keys, `_clean` sanitizer
- `src/segugio/opcomm/records.py` — `Discipline` enum, `@dataclass(frozen=True)` convention, `ScoreDoc{discipline, fields}`
- `tests/test_imports.py` — `PHASE1_SURFACE`, `CONSOLE_HEAVY_MODULES`, the heavy-absent smoke gate to extend
- `.planning/research/v1.3/{SUMMARY,ARCHITECTURE,FEATURES}.md` — keystone server-authoritative decision, component contract, federation rule tables
- This session's verified decimal/regex runs (Python 3.12.10) — `## Code Examples`

### Secondary (MEDIUM confidence — external, snippet-corroborated)
- FIDASC Disc Dog 2025 rulebook (`fidasc.it/.../5699-discdog-2025/file.html`) — Distance zones `9/18/27/36→1/2/3/4`, 5th-zone +1 central-corridor bonus, 60s, single disc; **cross-corroborated from two independent WebSearch snippets of the official PDF** (the PDF itself returned HTTP 503 to every automated fetch path including Wayback). FIDASC Freestyle: max 40, 90s, 10 discs — category breakdown NOT authoritatively pinned. `[ASSUMED — gate behind checkpoint:human-verify]`

### Tertiary (LOW confidence — web-only, conflicting)
- FIDASC Freestyle judging system — UFO D.I.S.C. (×0.1), Judge'n'Play (multi-element), UISP SEIS (×0.1) variously cited across `ilovediscdog`, `harddiscdogs`, `guidapet`; no single authoritative category list. Treat FIDASC Freestyle as a STUB.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib + already-pinned pydantic; zero new install; verified in-session.
- Architecture: HIGH — every structural pattern (discriminated union, fail-fast loader, plain-arg injection, frozen records, display-only renderer, import-smoke gate) has a shipped in-repo precedent.
- Pitfalls: HIGH — anchored to named project decisions (D-09/D-10, SCR-04, RBT-08) and verified decimal behavior.
- CSEN numbers: HIGH — fully extracted + pinned in CONTEXT (D-02/D-03).
- FIDASC Distance: MEDIUM — cross-corroborated snippets, PDF 503-blocked → `[ASSUMED]` + human-verify gate.
- FIDASC Freestyle: LOW — category breakdown not pinned → ship as stub.

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable domain — stdlib + in-repo patterns; the only volatile item is the FIDASC PDF, which a human-verify gate covers)
