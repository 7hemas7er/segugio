# Phase 1: Foundation, Config & Curated Clip Set - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Source:** Light discussion (full discuss-phase judged unnecessary — Phase 1 ~80% specified by research)

<domain>
## Phase Boundary

Phase 1 builds the **contract + test substrate** every later module depends on, all hardware-free:
- The central `config.yaml` schema with startup validation (the contract every module consumes).
- A curated **multi-condition clip set** in `tests/fixtures/` (the decisive de-risk for the whole milestone).
- Synthetic stream generators (score-stream, feed-death) enabling hardware-free unit tests of the scorer/FSM/watchdog in later phases.
- Project scaffolding: package layout, dependencies, logging.

Requirements: CFG-01, CFG-02, CFG-03, CFG-04, TST-01, TST-02.

NOT in this phase: any scorer/FSM/YOLO/NDI/OBS logic (later phases) — Phase 1 only defines the substrate they consume.
</domain>

<decisions>
## Implementation Decisions

### Clip set source (01-03) — KEY DECISION
- The curated clip set uses **REAL footage provided by the user** (their own / the community's), NOT generic CC0 stock.
- The footage **path will be provided at execution time** (not yet known at plan time). The plan must NOT hardcode a path — it should define the ingest/organization procedure and a documented place to drop the footage.
- The plan must: organize footage into `tests/fixtures/`, **catalogue** each clip against the condition checklist (multi-dog, handler-prominent, tunnel/contact occlusion, jump/sprint blur, distant, backlit/dusk, midfield-equidistant — for BOTH disc dog and agility), document **license/consent** in a `tests/fixtures/README.md`, and **flag missing conditions** (only those gaps get supplemented with CC0/web clips later).
- A catalogue manifest (e.g. a small YAML/CSV mapping clip → conditions/discipline) is desirable so later phases can select clips by condition.

### Tooling (01-01)
- `requirements.txt` is a required deliverable (per brief). Provide it AND a minimal `pyproject.toml` for the installable package.
- Dev target: Python on a Linux + CUDA box. Pin the dependencies surfaced by research (ultralytics, cyndilib, obsws-python, transitions, opencv-python, numpy, pyyaml, loguru, watchdog) — but Phase 1 itself does not import the heavy GPU/NDI deps at runtime; keep heavy/optional deps importable lazily so config + generators run without a GPU.
- Logging via `loguru`.

### Config schema (01-02)
- Schema already designed by research (see `.planning/research/ARCHITECTURE.md`). Structure:
  - `field.{sport, event}` (discipline + event variant)
  - `cameras[]` each with `{role, obs_scene, is_safe, zones}` where `zones` are **normalized [0..1] rects** (named bands: near/mid/far/stage)
  - `framing_weights[role][zone]` multiplier matrix
  - switching thresholds: `alpha`, `hysteresis_margin`, `min_dwell`, `debounce_N`, `cooldown`, `watchdog_timeout`, `track_buffer`
  - model: `path` + `class_index` (default `yolo26s.pt`, `dog=16`) — swappable
  - `discipline` selector that switches overlay field set + framing defaults with ZERO code edits (CFG-03)
- Startup validation must **fail fast with a clear error** on malformed config (CFG-01).

### Code conventions
- **OS-agnostic** code: no hardcoded OBS text input kinds (`text_gdiplus`/`text_ft2`), use `pathlib`, discover platform specifics at runtime. (Matters more in later phases but establish the convention now.)

### Claude's Discretion
- The config-validation library/approach (e.g. pydantic v2 vs dataclasses+jsonschema vs voluptuous) — research should recommend; pick the one giving the clearest fail-fast errors and a typed config object.
- Exact package/module layout under `src/segugio/` (research folder structure is a strong guide).
- Synthetic generator API shape (deterministic, seedable; emit score streams and feed-death events).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project decisions & scope
- `.planning/PROJECT.md` — constraints, key decisions (OBS-as-hub, two-budget latency, native ReID in v1, yolo26s/dog=16)
- `.planning/REQUIREMENTS.md` — v1 requirement IDs (this phase: CFG-01..04, TST-01, TST-02)

### Research (stack locked + domain)
- `.planning/research/TECHNICAL-RESEARCH.md` — locked stack, library list, latency verdict
- `.planning/research/ARCHITECTURE.md` — **config schema design**, camera roles, field-zone model, OBS scene template
- `.planning/research/STACK.md` — concrete model (yolo26s), tracker config, dataset/fixture sourcing guidance
- `.planning/research/FEATURES.md` — per-discipline overlay field sets (informs the `discipline` selector schema)
- `.planning/research/PITFALLS.md` — the condition checklist the clip set must cover (multi-dog, occlusion, blur, distant, backlit, equidistant)
</canonical_refs>

<specifics>
## Specific Ideas

- The clip-set catalogue should make later phases able to query "give me the multi-dog + occlusion clips for agility" — a structured manifest, not just files on disk.
- Generators must be deterministic/seedable so unit tests are reproducible.
- Keep config + generators runnable on a machine with NO GPU and NO NDI (lazy-import heavy deps), so Phase 1 deliverables are testable anywhere.
</specifics>

<deferred>
## Deferred Ideas

- Choice of reference organization (Skyhoundz/USDDN/UpDog for disc; AKC/UKC/FCI for agility) — affects only config VALUES (zone distances, score fields) used in Phase 5, not the Phase 1 schema. Defer.
- Real NDI/OBS/hardware — later milestone.
- Actual scorer/FSM/YOLO logic — Phases 2-5.
</deferred>

---

*Phase: 01-foundation-config-curated-clip-set*
*Context gathered: 2026-06-09 via light discussion*
