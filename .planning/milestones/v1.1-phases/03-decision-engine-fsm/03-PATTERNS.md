# Phase 3: Decision Engine FSM - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 12 (4 new package modules · 1 new package `__init__` · 7 new test files · 3 modified files)
**Analogs found:** 12 / 12 (every file has a same-role, same-data-flow shipped analog)

All analogs are read from the SHIPPED codebase (Phase 1 `segugio/config/` + `segugio/synth/`, Phase 2 `segugio/framing/`). Line numbers below are verified against the actual source.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/segugio/decision/__init__.py` | package barrel | re-export | `src/segugio/framing/__init__.py` | exact |
| `src/segugio/decision/signals.py` | model (frozen records + enums) | transform (input/output contracts) | `src/segugio/framing/signals.py` | exact |
| `src/segugio/decision/engine.py` | engine (stateful, tick-driven) | event-driven / transform (per-tick fan-in → 1 decision) | `src/segugio/framing/scorer.py` (`CameraScorer`/`MultiCamScorer`) | role-match (FSM vs scorer; identical purity/tick/injected-fps shape) |
| `src/segugio/decision/clocks.py` | utility (pure helper) | transform (seconds→ticks) | `ttl_ticks_from_seconds` in `src/segugio/framing/scorer.py:67-75` | exact |
| `tests/test_decision_invariants.py` | test (DEC-01 guard) | request-response (replay) | `tests/test_framing_purity.py` | role-match |
| `tests/test_decision_hysteresis.py` | test (DEC-02 no-chase) | request-response (tick-loop replay) | `tests/test_framing_coast.py` | role-match |
| `tests/test_decision_holds.py` | test (DEC-03/04) | request-response (tick-loop replay) | `tests/test_framing_coast.py` | role-match |
| `tests/test_decision_tiebreak.py` | test (DEC-05) | request-response | `tests/test_framing_coast.py` | role-match |
| `tests/test_decision_feeddeath.py` | test (DEC-06) | request-response (feed_death replay) | `tests/test_framing_coast.py` + `feed_death` substrate | role-match |
| `tests/test_decision_override.py` | test (RBT-03) | request-response | `tests/test_framing_coast.py` | role-match |
| `tests/test_decision_determinism.py` | test (DEC-07) | request-response (`==` over `list[Decision]`) | `tests/test_framing_purity.py::test_purity_determinism` | exact |
| `tests/conftest.py` *(modified)* | test fixtures | — | existing `seeded_rng` / `valid_config_dict` / `scorer_params` fixtures | exact (extend in place) |
| `tests/test_imports.py` *(modified)* | test (import boundary) | — | existing `PHASE1_SURFACE` / `HEAVY_MODULES` lists | exact (one-line edit) |
| `pyproject.toml` *(modified)* | config (deps) | — | existing `dependencies` / `[heavy]` blocks | exact (move one pin) |

---

## Pattern Assignments

### `src/segugio/decision/signals.py` (model — frozen records + enums)

**Analog:** `src/segugio/framing/signals.py` (read in full, 77 lines). This is the **exact** convention the new file must mirror — frozen dataclasses + str-Enum, stdlib-only, no numpy.

**Module header + imports** (`signals.py:20-25`) — copy this shape verbatim:
```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["DetectionSignal", "CameraScore", "ScorerStatus"]
```
Note: stdlib-only (`dataclasses` / `enum`), NO numpy, NO synth import. The module docstring (`signals.py:1-18`) explicitly states the one-way dependency rule ("this module must never import from `synth`"). The new `decision/signals.py` must likewise import nothing from `synth` and must keep the lazy-import boundary intact.

**str-Enum pattern** (`signals.py:28-38`) — the model for the new `Mode` and any `Reason` enum:
```python
class ScorerStatus(str, Enum):
    """A ``str`` Enum (mirrors ``config.models.Role``) so ``CameraScore`` stays
    ``==``-comparable and YAML/JSON-friendly."""
    tracking = "tracking"
    coasting = "coasting"
    lost = "lost"
```
The new `Mode(str, Enum)` (`safe`/`auto`/`override`) and optional `Reason(str, Enum)` follow this exactly. `config.models.Role` (`config/models.py:36-42`) is the third instance of the same idiom — three precedents agree.

**Frozen record pattern** (`signals.py:64-77`) — the model for the new `Decision`, `HoldInput`, `OverrideCmd`:
```python
@dataclass(frozen=True)
class CameraScore:
    """Frozen (hashable + comparable) so ``==`` over two ``list[CameraScore]`` is the
    determinism assertion ... ``score`` is the smoothed [0,1] value the Phase-3 FSM consumes."""
    tick: int
    cam_id: str
    score: float  # smoothed [0,1]
    status: ScorerStatus
```
The new `Decision(tick: int, target: str, mode: Mode, reason: str)` (RESEARCH.md §Code Examples lines 343-349) is this shape with a different field set. **Critical convention from the analog docstring (`signals.py:11-12`):** "All numeric fields are plain `float` (`float()`-cast at construction) so a numpy scalar never leaks into the `==`." If any `Decision` field can receive a numpy scalar (e.g. a score copied into a reason), `float()`-cast it at construction — this is load-bearing for the `==`-based determinism assertions.

**Consumed input type (do NOT redefine):** The FSM's per-camera input is `CameraScore` from `framing/signals.py:64-77` — import it, never re-declare. `decision/signals.py` adds only the FSM-specific records (`Decision`, `HoldInput`, `OverrideCmd`, `Mode`).

---

### `src/segugio/decision/clocks.py` (utility — seconds→ticks helper)

**Analog:** `ttl_ticks_from_seconds` in `src/segugio/framing/scorer.py:67-75`. This is the **exact precedent** RESEARCH.md (Pattern 2, lines 219-223) says to mirror — `fps` is an argument, NOT a config field (verified: `Thresholds` has no `fps`, `config/models.py:94-108`).

**Copy this signature and body shape** (`scorer.py:67-75`):
```python
def ttl_ticks_from_seconds(ttl_seconds: float, fps: float) -> int:
    """Convert a ``ttl_seconds`` coast window to whole ticks at ``fps`` (clock-free).

    Pure stdlib (``math.ceil``) ... ``ceil`` guarantees at least one coast tick for any
    positive ``ttl_seconds``.
    """
    return int(math.ceil(ttl_seconds * fps))
```
The new `ticks_from_seconds(seconds: float, fps: float) -> int` is byte-for-byte this (rename only). `math.ceil` → ≥1 for any positive seconds is the single source of rounding truth. Used to convert `min_dwell` (2.0s), `cooldown` (1.0s), and `hold_length_s` (disc 2.5 / agility 1.5, from `discipline.py:30-31`) to integer ticks once at construction.

**Test precedent for this helper** (`tests/test_framing_coast.py:236-240`):
```python
def test_ttl_ticks_from_seconds_ceils_positive() -> None:
    assert ttl_ticks_from_seconds(0.4, 30.0) == 12   # ceil(12.0)
    assert ttl_ticks_from_seconds(0.41, 30.0) == 13  # ceil(12.3) → 13
    assert ttl_ticks_from_seconds(0.001, 30.0) == 1  # ceil(0.03) → at least 1 tick
```
Mirror this exact table-style test for `ticks_from_seconds`.

---

### `src/segugio/decision/engine.py` (engine — the `transitions.Machine` wrapper + `tick()` loop)

**Primary analog:** `src/segugio/framing/scorer.py` — `CameraScorer`/`MultiCamScorer` (read in full, 278 lines). Same role: a stateful, per-tick, pure, injected-`fps`, deterministic object whose single `update(...)`-style method fans inputs in and emits a frozen record. The FSM differs only in using `transitions.Machine` for the state/guard scaffolding (RESEARCH.md §Pattern 1). The `transitions` idiom itself comes from RESEARCH.md §Code Examples (lines 305-332, Context7-verified) — there is no shipped `transitions` analog, so use RESEARCH for the library API and use `scorer.py` for everything else (purity, tick-injection, fan-out, fail-safe, docstring style).

**Imports + lazy-import discipline** (`scorer.py:40-64`) — mirror the structure:
```python
from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from .signals import CameraScore, ScorerStatus
from .terms import ( ... )

if TYPE_CHECKING:  # type-only imports — no runtime cost, no config↔framing cycle
    from .params import ScorerParams
    from .signals import DetectionSignal

__all__ = ["CameraScorer", "MultiCamScorer", "ttl_ticks_from_seconds"]
```
For `engine.py`: `from transitions import Machine` at module top level (now legal — see pyproject change below), `from .signals import Decision, Mode, HoldInput, OverrideCmd` and `from .clocks import ticks_from_seconds`, plus `from ..framing.signals import CameraScore` for the input type (or via `TYPE_CHECKING` if only annotated). The FSM core needs NO numpy (RESEARCH.md line 82: "selecting best-of can be plain Python `max(...)`"); keep numpy out unless a test substrate forces it.

**Injected-fps constructor pattern** (`scorer.py:110-131`) — `fps` and all seconds-valued config enter the constructor and are converted to ticks ONCE; counters are plain ints initialized here:
```python
    def __init__(self, camera, params, framing_weights, alpha, lead_gain, ttl_ticks) -> None:
        self.camera = camera
        self.p = params
        ...
        self.ttl_ticks = ttl_ticks
        self.ema: float | None = None
        self.status: ScorerStatus = ScorerStatus.lost
        self.ttl: int = 0
        self.last_track: int | None = None
```
For `DecisionEngine.__init__(self, cameras, thresholds, fps, hold_length_s, ...)`: call `ticks_from_seconds(...)` to derive `min_dwell_ticks`, `cooldown_ticks`, `occlusion_cap_ticks`, etc.; initialize the integer clocks/counters (`dwell_elapsed=0`, `cooldown_remaining=0`, `challenger_id=None`, `challenger_streak=0`, `occlusion_hold_remaining=0`, `action_hold_age=0`, `override_cam=None`, `target` = SAFE sentinel) as plain attributes — this is RESEARCH.md §Pattern 2 (clocks are ordinary ints on the model, not managed by `transitions`).

**Deterministic camera ordering** (`scorer.py:258-264`) — the FSM's "first camera in config declaration order" tiebreaker (DEC-05 / D-07 no-incumbent fallback) reuses this exact precedent:
```python
        # dict preserves insertion order → deterministic per-tick output ordering.
        self.scorers: dict = {
            cam.id: CameraScorer(cam, params, framing_weights, alpha, lead_gain, ttl_ticks)
            for cam in cameras
        }
```
Build an insertion-ordered `cam_ids` (or dict) from `cameras` and use it as the tiebreak order — `config/models.py:116` declares `cameras: list[Camera]`, so declaration order is the list order.

**The single-method-per-tick fan-out** (`scorer.py:266-277`) — `MultiCamScorer.update(dets_by_cam, tick) -> list[CameraScore]` is the structural model for `DecisionEngine.tick(scores, alive, holds, override) -> Decision`:
```python
    def update(self, dets_by_cam, tick) -> list[CameraScore]:
        """Score one tick across all cameras → one ``CameraScore`` per camera (in order)."""
        return [
            scorer.update(dets_by_cam.get(cam_id), tick)
            for cam_id, scorer in self.scorers.items()
        ]
```
Mirror the `.get(cam_id)` defensive-default style for the `alive` map: a camera absent from `alive` must default to a safe value (treat absent as NOT-alive → excluded candidate, per DEC-06 fail-safe), never `KeyError` (`scorer.py:236-238` documents the never-KeyError contract).

**Fail-safe (never raise) + finite-guard pattern** (`scorer.py:78-86`, `225`) — mirror for poisoned scores (RESEARCH.md §Security V5, threat T-2-01):
```python
def _is_finite_detection(det) -> bool:
    """A NaN/inf detection must be treated as "no detection" rather than poisoning the EMA."""
    return all(math.isfinite(v) for v in (det.cx, det.cy, det.w, det.h, det.conf))
# ... and the emitted value is clamped:
float(np.clip(self.ema if self.ema is not None else 0.0, 0.0, 1.0))
```
For the FSM: a NaN/inf/out-of-range `CameraScore.score` → treat as an ineligible candidate (never challenger, never target), never raise. The FSM "never raises on data the validated `Config` already passed" (`scorer.py:30-33`). Robustness constraint: "nessun crash ammesso."

**The decision-only-from-a-guard invariant (DEC-01)** — NO shipped analog; use RESEARCH.md §Code Examples (lines 305-323, Context7-verified):
```python
m = Machine(model=engine, states=["safe","auto","override"], initial="safe",
            transitions=[{"trigger":"auto_switch","source":["auto","safe"],"dest":"auto",
                          "conditions":["challenger_qualified"],"before":"_promote"}])
engine.auto_switch()   # → no-op if challenger_streak < 3; target unchanged (DEC-01)
```
`self.target` is mutated ONLY inside a `before`/`after`/`on_enter` callback whose `conditions` passed. The `tick()` loop computes the *candidate* (a pure `max(...)` over eligible scores) but NEVER assigns `self.target` directly. Trigger fire order is the fixed priority list (RESEARCH.md §Pattern 3 lines 227-233): override → feed-death emergency → hold → normal-switch.

**Module docstring style** — `scorer.py:1-38` is the gold-standard format: a one-line summary, then per-decision (D-01…D-07) traceability, then an explicit purity/determinism/lazy-import paragraph (`scorer.py:36-37`: "Clock-free and RNG-free … time is the injected `tick`; there is zero randomness and zero wall-clock here. Imports only … no heavy deps at module top level"). Write the `engine.py` docstring in this exact style, tracing DEC-01…07 + RBT-03.

---

### `src/segugio/decision/__init__.py` (package barrel — re-export)

**Analog:** `src/segugio/framing/__init__.py` (read in full, 31 lines). Copy the shape exactly.
```python
"""segugio.decision — ... (one-line summary). ... pure ... no heavy deps ... lazy-import boundary."""
from __future__ import annotations

from .signals import CameraScore  # if re-exported for convenience
from .signals import Decision, HoldInput, Mode, OverrideCmd
from .engine import DecisionEngine
from .clocks import ticks_from_seconds

__all__ = [
    "DecisionEngine", "Decision", "Mode", "HoldInput", "OverrideCmd", "ticks_from_seconds",
]
```
The analog docstring (`framing/__init__.py:1-14`) is the template: summarize the package, state purity ("imports only numpy + stdlib + pydantic … never torch / ultralytics / cyndilib"), and list which plan added which symbol. For `decision/`: "imports only `transitions` + stdlib (+ the pure `segugio.framing`/`segugio.config` surfaces)".

---

### `tests/test_decision_*.py` (7 new test files)

**Primary analogs:**
- `tests/test_framing_coast.py` (read in full, 240 lines) — the **tick-loop replay** pure-logic style (warm-up loop, then a stimulus loop, then frozen-record `==`/`pytest.approx` assertions on the per-tick outputs). This is the model for hysteresis / holds / tiebreak / feeddeath / override replay tests.
- `tests/test_framing_purity.py` (read in full, 293 lines) — the **determinism gate** (`assert run(seq) == run(seq)` over frozen records) and the **heavy-absent import** test. Model for `test_decision_determinism.py` and the invariants file.

**Determinism replay pattern** (`test_framing_purity.py:83-119`) — the model for `test_decision_determinism.py`:
```python
def _run(seq: list) -> list[CameraScore]:
    """Drive a freshly-constructed scorer over the whole sequence → its CameraScore list."""
    sc = _scorer()
    return [sc.update(det, t) for t, det in enumerate(seq)]

def test_purity_determinism() -> None:
    seq_a = detection_stream(np.random.default_rng(SEED), CAM_ID, N_TICKS, dropout=DROPOUT)
    seq_b = detection_stream(np.random.default_rng(SEED), CAM_ID, N_TICKS, dropout=DROPOUT)
    assert seq_a == seq_b               # input is itself deterministic (precondition)
    assert _run(seq_a) == _run(seq_b)   # byte-identical CameraScore lists (frozen records)
```
For `test_decision_determinism.py`: drive `DecisionEngine` over the same `score_stream`/`feed_death` substrate twice, assert `list[Decision] == list[Decision]`. Reuse `from tests.conftest import SEED` and `np.random.default_rng(SEED)` exactly as `test_framing_purity.py:43,106-107` does.

**Tick-loop warm-up-then-stimulus pattern** (`test_framing_coast.py:69-107`) — the model for hysteresis/hold/override timing tests:
```python
def test_coast_then_lost(scorer_params) -> None:
    sc = _scorer(scorer_params)
    # --- Warm-up loop ---
    held = None
    for t in range(5):
        out = sc.update(_det(t), t)
        assert out.status is ScorerStatus.tracking
        held = out.score
    # --- Stimulus loop with per-tick assertions ---
    statuses, scores = [], []
    for i in range(TTL_TICKS):
        out = sc.update(None, 5 + i)
        statuses.append(out.status); scores.append(out.score)
    # explicit per-tick clock walk in comments (lines 83-87) — replicate this for dwell/cooldown
```
The inline tick-by-tick clock walk in the comment (`test_framing_coast.py:83-87`) is exactly how to document the `min_dwell`/`cooldown`/`debounce_N` countdown in the DEC-02 tests. Reuse `pytest.approx` for any float comparison (`test_framing_coast.py:98,103,125,137,154`).

**Small Camera/Zone stand-in builder** (`test_framing_coast.py:45-62`, `173-184`) — the model for building the FSM's `cameras` list in tests:
```python
def _two_cameras() -> list[Camera]:
    return [
        Camera(id=cid, role=Role.main_wide, obs_scene="WIDE", is_safe=True,
               zones=[Zone(name="all", rect=[0.0, 0.0, 1.0, 1.0])])
        for cid in (_CAM_A, _CAM_B)
    ]
```
The FSM needs `cameras` for declaration-order tiebreak (D-07) and the SAFE flag (`Camera.is_safe`); build them with this same `Camera(...)` stand-in. Note `is_safe=True` here is for a neutral test; the FSM tiebreak/SAFE tests will need at least one `is_safe=True` camera (the cross-validator guarantees ≥1 in real config, `config/models.py:138-141`).

**Driving from the synth substrate (DEC-07)** — the `ScoreSample`→`CameraScore` adapter (RESEARCH.md Pitfall 2, lines 276-279): `ScoreSample` (`score_stream.py:33-43`) has NO `status` field, but the FSM consumes `CameraScore` (`framing/signals.py:64-77`) which requires `status`. The adapter wraps each sample:
```python
# Recommended adapter (lives in conftest.py — see below):
def _as_camera_scores(samples, status_default=ScorerStatus.tracking) -> list[CameraScore]:
    return [CameraScore(s.tick, s.cam_id, s.score, status_default) for s in samples]
```
`feed_death` (`feed_death.py:44-87`) already emits `list[FeedEvent]` (`tick, cam_id, alive`) — group by tick into the `alive: dict[cam_id->bool]` the engine's `tick()` consumes. `SCENARIOS` (`score_stream.py:30`) = `("ping_pong","tie","dropout","recovery")` is the named substrate DEC-07 drives.

**Source-grep purity test (NEW in Phase 2, reuse for Phase 3)** (`test_framing_purity.py:122-156`) — port this to assert `src/segugio/decision/*.py` imports no `time`/`np.random`/`os`/`socket`/`requests` and no heavy dep. `transitions` is now LIGHT (allowed); keep it OUT of the forbidden set. The helper `_framing_py_files()` (`test_framing_purity.py:89-94`) becomes `_decision_py_files()` over `Path(importlib.import_module("segugio.decision").__file__).parent`.

**Heavy-absent import test** (`test_framing_purity.py:158-179`) — port for `segugio.decision`:
```python
def test_framing_imports_with_heavy_absent(monkeypatch):
    _force_heavy_absent(monkeypatch)               # from tests.test_imports
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)
    module = importlib.import_module("segugio.framing")
    assert hasattr(module, "CameraScorer")
```
Reuse `from tests.test_imports import HEAVY_MODULES, _force_heavy_absent` (`test_framing_purity.py:47`) — keep the boundary single-sourced. Assert `import segugio.decision` succeeds with torch/ultralytics/cyndilib/obsws absent and that `transitions` (the now-light dep) is still importable.

---

### `tests/conftest.py` (MODIFIED — add fixtures)

**Analog:** the existing fixtures in the same file (read in full, 128 lines). Extend in place following the established style.

**Existing reusable fixtures** to consume directly:
- `seeded_rng` (`conftest.py:27-34`) → drives `score_stream`/`feed_death` in the DEC-07 tests.
- `valid_config_dict` (`conftest.py:113-116`) + the `_VALID_CONFIG` dict (`conftest.py:64-110`) → has a `thresholds` block (`conftest.py:97-105`: `hysteresis_margin: 0.1, min_dwell: 2.0, debounce_N: 3, cooldown: 1.0`) and two cameras (one `is_safe: True`). Build the FSM thresholds fixture from this.
- `scorer_params` (`conftest.py:119-128`) — the model for a lazily-imported, validated fixture.

**New fixture, mirroring `scorer_params`** (`conftest.py:119-128`) — a `thresholds` (and/or `decision_config`) fixture that constructs from the canonical config:
```python
@pytest.fixture
def thresholds(valid_config_dict):
    """Validated ``Thresholds`` the FSM reads (mirrors ``scorer_params``)."""
    from segugio.config import Config           # imported in-body to keep conftest light
    return Config.model_validate(valid_config_dict).thresholds
```
Add a module-level `FPS` constant next to `SEED` (`conftest.py:24`: `SEED = 1234`) — e.g. `FPS = 30.0` — the injected fps the `DecisionEngine` constructor and `ticks_from_seconds` use (RESEARCH.md A2: fps is injected, never added to `Thresholds`).

Add the `_as_camera_scores(samples, status_default=...)` adapter (RESEARCH.md Pitfall 2) here so every `test_decision_*.py` shares it. Follow the in-body lazy-import style (`conftest.py:126`) for the `CameraScore`/`ScorerStatus` import to keep conftest heavy-import-free.

---

### `tests/test_imports.py` (MODIFIED — extend the surface list)

**Analog:** the file itself (read in full, 141 lines). The Phase-2 precedent is already in place: `"segugio.framing"` was added to `PHASE1_SURFACE` with an inline comment (`test_imports.py:25`).

**One-line edit** — add `segugio.decision` exactly as Phase 2 added framing (`test_imports.py:20-26`):
```python
PHASE1_SURFACE = [
    "segugio",
    "segugio.config",
    "segugio.synth",
    "segugio.logging",
    "segugio.framing",   # 02-04: the pure framing scorer joins the proven lazy-import surface
    "segugio.decision",  # 03-xx: the pure FSM joins the proven lazy-import surface
]
```
**Do NOT touch `HEAVY_MODULES`** (`test_imports.py:18`): `transitions` is now a light runtime dep and must NOT be added to `["torch", "ultralytics", "cyndilib", "obsws_python"]`. The parametrized `test_phase1_surface_imports_with_heavy_deps_absent` (`test_imports.py:43-54`) auto-covers `segugio.decision` once it is in the list — it forces the 4 heavy modules absent and asserts the surface still imports. This mechanically proves `transitions` is NOT on the heavy/lazy path (RESEARCH.md Pitfall 1).

---

### `pyproject.toml` (MODIFIED — reclassify `transitions`)

**Analog:** the file itself (read in full). `transitions==0.9.3` is currently in `[project.optional-dependencies].heavy` (`pyproject.toml:31`) alongside the genuinely heavy GPU/NDI deps.

**The edit (RESEARCH.md Pitfall 1 + Wave 0):** move `"transitions==0.9.3"` from the `heavy` group (`pyproject.toml:27-34`) to the light runtime `dependencies` list (`pyproject.toml:12-17`):
```toml
dependencies = [
    "pydantic==2.13.4",
    "pyyaml==6.0.3",
    "numpy==2.4.6",
    "loguru==0.7.3",
    "transitions==0.9.3",   # pure-Python FSM (Phase 3); no native/GPU/C deps → light side
]
```
…and delete the `"transitions==0.9.3"` line from `heavy`. `transitions` is pure-Python (no native build step — RESEARCH.md verified the sdist builds metadata with no compiler), so it belongs with `pydantic`/`numpy`/`loguru`. After the edit, install into the venv: `.venv/bin/pip install transitions==0.9.3` (or `.venv/bin/pip install -e .`). The `[tool.pytest.ini_options]` (`pyproject.toml:39-42`: `pythonpath=["src"]`, `testpaths=["tests"]`, `addopts="-q"`) already auto-discovers the new `src/segugio/decision/` package — no change needed there.

---

## Shared Patterns

### Frozen-dataclass `==`-determinism contract
**Source:** `src/segugio/framing/signals.py:41-77` (also `synth/score_stream.py:33-43`, `synth/feed_death.py:31-42`, `config/models.py:36-42`)
**Apply to:** `decision/signals.py` (`Decision`, `HoldInput`, `OverrideCmd`, `Mode`) and every `test_decision_*.py` assertion.
Every record is `@dataclass(frozen=True)`; every status/mode is a `str`-`Enum`. The frozen records make `list[Decision] == list[Decision]` the determinism assertion (DEC-07). `float()`-cast any numeric field that could receive a numpy scalar at construction (`signals.py:11-12`).

### Injected-tick / injected-fps, clock-free, RNG-free purity
**Source:** `src/segugio/framing/scorer.py:36-37, 67-75, 149` ; `synth/score_stream.py:11-19` ; `synth/feed_death.py:12-18`
**Apply to:** `decision/engine.py`, `decision/clocks.py`, and all `test_decision_*.py`.
Time is the injected integer `tick`; seconds→ticks conversion happens once via `ticks_from_seconds(seconds, fps)` with `fps` as an argument (NOT in `Thresholds`). No wall-clock, no `np.random`, no global RNG. Same input stream → byte-identical output (DEC-07). The source-grep purity test (`test_framing_purity.py:122-156`) structurally enforces this — port it.

### Lazy-import boundary (heavy deps absent)
**Source:** `tests/test_imports.py:18-54` ; `src/segugio/framing/__init__.py:1-14` ; every Phase-1/2 module docstring
**Apply to:** `decision/__init__.py`, `decision/*.py` module top levels, `test_imports.py` edit, the ported heavy-absent test.
`segugio.decision` must import with `torch`/`ultralytics`/`cyndilib`/`obsws_python` absent. `transitions` is now a LIGHT dep (importable in that environment) and stays OUT of `HEAVY_MODULES`. No torch/ultralytics/cyndilib/obsws/cv2 at any `decision/*.py` top level.

### Fail-safe, never fail-loud (robustness: "nessun crash ammesso")
**Source:** `src/segugio/framing/scorer.py:30-33, 78-86, 225, 236-238`
**Apply to:** `decision/engine.py`.
Never raise on data the validated `Config` already passed. NaN/inf/out-of-range score → ineligible candidate (never challenger/target), mirroring `_is_finite_detection` (`scorer.py:78-86`). A camera absent from the `alive`/`scores` map degrades safely (excluded), never `KeyError` — mirror the `.get(cam_id)` defensive default (`scorer.py:275, 236-238`). Every hold has a mandatory tick max-cap (RESEARCH.md anti-pattern lines 241; CONTEXT D-02 guardrail) so a stuck signal can never freeze the show.

### Deterministic config-declaration ordering
**Source:** `src/segugio/framing/scorer.py:258-264` (insertion-ordered dict) ; `config/models.py:116` (`cameras: list[Camera]`)
**Apply to:** `decision/engine.py` tiebreaker (D-07 no-incumbent → first camera in config order).
Build the candidate iteration order from `cameras` list order (insertion-ordered dict or the list itself) so the tiebreak is deterministic and matches config declaration order.

### Pytest tick-loop replay + frozen-record assertions
**Source:** `tests/test_framing_coast.py:69-107` (warm-up + stimulus loop, inline clock walk, `pytest.approx`) ; `tests/test_framing_purity.py:83-119` (`assert _run(seq) == _run(seq)`)
**Apply to:** all 7 `test_decision_*.py` files.
Build a tiny `_engine()` factory (mirror `_scorer()` `test_framing_coast.py:45-62`), a `_run(...)` driver returning `list[Decision]`, drive over the synth substrate, and assert with `==`/`pytest.approx`. For DEC-02 assert the **transition count** stays minimal (RESEARCH.md Pitfall 3) — NOT per-tick argmax. Reuse `from tests.conftest import SEED`.

---

## No Analog Found

None. Every Phase-3 file maps to a shipped Phase-1/2 analog. The single genuinely-new mechanic — the `transitions.Machine` guarded-transition wiring (DEC-01) — has no codebase analog (it is the first FSM in the repo); for that one capability the executor follows **RESEARCH.md §Pattern 1 + §Code Examples (lines 176-215, 305-332)**, which are Context7-verified against `/pytransitions/transitions`. All surrounding concerns (purity, tick-injection, frozen records, fan-out, fail-safe, lazy-import, test style, fixtures, deps) have exact shipped analogs above.

---

## Metadata

**Analog search scope:** `src/segugio/config/`, `src/segugio/framing/`, `src/segugio/synth/`, `tests/`, `pyproject.toml`
**Files scanned (read in full):** `framing/signals.py`, `framing/scorer.py`, `framing/__init__.py`, `config/models.py`, `config/discipline.py`, `config/__init__.py`, `synth/score_stream.py`, `synth/feed_death.py`, `synth/__init__.py`, `tests/conftest.py`, `tests/test_imports.py`, `tests/test_framing_purity.py`, `tests/test_framing_coast.py`, `pyproject.toml` (14 files)
**Pattern extraction date:** 2026-06-09
