# Phase 15: Pure Calc + Validation Core & Scoring Profiles - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver `segugio/ui/score_calc.py` — the SINGLE authoritative, pure-stdlib scoring brain
for Segugio's score entry. It exposes `validate(discipline, fields, profile) → per-field errors`
and `compute(discipline, fields, profile) → totals`, driven by config-driven **scoring profiles**,
and is proven correct + crash-isolation-safe BEFORE any UI (Phase 16+) consumes it.

**In scope:**
- Pure-stdlib `score_calc.py` (validate + compute) for disc **Toss&Fetch (Distance)**, **Freestyle**,
  and **Agility** (engine only — see Agility decision).
- Config-driven scoring-profile schema extending the CFG-03 pydantic discriminated-union
  (`src/segugio/config/discipline.py`), with **fail-fast** validation at config-load.
- A shipped **CSEN 2026** disc-dog default profile + a **FIDASC** disc-dog profile + a generic
  **FCI-style agility example** profile.
- Per-discipline unit tests against the pinned CSEN rule tables.
- `score_calc` added to `PHASE1_SURFACE`; the heavy-absent import-smoke gate
  (`test_console_resolves_with_heavy_stack_and_numpy_absent`) extended to cover the new module
  and a `POST /score` round-trip with torch/cv2/ultralytics/numpy/cyndilib/obsws ABSENT.

**Out of scope (later phases / milestones):**
- Any UI: the shared `score-entry.js` component, dedicated page, console modal (Phase 16–17).
- Making `POST /score` authoritative / wiring compute into the route (Phase 16).
- Rich additive data-model subkeys through `/overlay-json` + overlay-continuity regression (Phase 18).
- Real Italian **agility** rule-table values (deferred until an agility event is actually run).
- Multi-judge combination beyond `sum` (average / drop-high-low), roster/standings, CV auto-scoring.

</domain>

<decisions>
## Implementation Decisions

### Default rule tables (REQ blocker — RESOLVED)
- **D-01:** The pinned built-in **default** is the **CSEN 2026** Italian disc-dog ruleset (the user
  organizes/films Italian events). International tables (UFO/USDDN/Skyhoundz) are NOT the default.
- **D-02 — CSEN Distance (Toss & Fetch):** 90-second round, **single disc**, unlimited throws but
  **only the best 5 throws count** toward the round total (`count_best_n: 5`, max round = 25).
  - Zone points by landing paw nearest the throw line, **meters**: `9m → 1`, `18m → 2`, `27m → 3`, `36m → 4`.
  - **Two independent +0.5 bonuses per catch**: all-four-paws-airborne, and catch-in-central-corridor.
  - **Per-throw cap = 5** (4 + 0.5 + 0.5). On-the-line → next-higher zone (a judging rule; operator
    picks the zone, the tool does NOT infer distance).
  - Per-throw input shape: `{zone: <points-band>, midair: bool, corridor: bool}`.
- **D-03 — CSEN Freestyle:** 120s routine (90s min to be valid). **4 judged categories, each 0–10,
  in 0.01 increments**, **total = sum (max 40)**: `Team Elements`, `Dog (Cane)`, `Player`,
  `Catch Ratio` (catches/throws, min-18 basis). Each category is owned by a distinct judge but the
  combine rule reduces to a plain **`sum`** — no multi-judge combiner needed in v1.3.

### Profile breadth
- **D-04:** Ship **two real disc-dog profiles**: CSEN (active default) **+ FIDASC** (alternate).
  Shipping a real second federation is what proves success-criterion 3 (swap changes the result with
  no code change) against REAL alternate rules, not a synthetic fixture.
- **D-05:** **FIDASC numbers are NOT yet extracted** — its rulebook endpoint
  (`fidasc.it/.../file.html`) returned HTTP 503 to automated fetch. The planner/researcher MUST
  source the exact FIDASC Distance zone table + Freestyle categories/scale before building that
  profile (see Canonical References). Treat FIDASC as a stub until its numbers are pinned.

### Agility scope
- **D-06:** Build the **agility engine** (config-driven), defer the real profile. `score_calc`
  implements BOTH agility models so SCC-04 is satisfied and a future agility event needs zero code
  change:
  - `count_up` (FCI-style, lowest wins): `total_faults = course_faults + time_faults`;
    `time_faults = rate × max(0, run_time − SCT)` with whole-fault rounding via `ceil` at `rate = 1/sec`.
  - `deduct_from_100` (AKC-style): `score = 100 − course_deductions − time_faults`.
  - **Elimination** is a first-class flag that OVERRIDES the numeric result with a sentinel string
    (e.g. `"E"`) — the overlay renders "E", never a number.
- **D-07:** Ship only a **generic FCI-style example** agility profile (default model `count_up`).
  Real Italian agility rule numbers are **deferred** to a later milestone/phase. No roadmap re-scope.

### Freestyle penalties
- **D-08:** Freestyle `compute()` produces the **4-category sum only**. CSEN deductions (nature break
  −5, excess disc −1, safety contortion/compression/fall ranges) are NOT auto-modeled in v1.3 — they
  enter as a **single manual adjustment field** (default 0) subtracted from the total. Avoids a large
  judge-entered penalty + validation surface in this phase.

### Claude's Discretion (locked technical choices)
- **D-09 — Pure-stdlib + decimal:** `score_calc` imports only stdlib (`decimal`, `re`, `dataclasses`,
  `enum`). All arithmetic uses `decimal.Decimal`, quantized to the profile's increment (never float —
  avoids `0.1+0.2` broadcast drift). NO `import segugio.config`, NO numpy/cv2/torch at module top.
- **D-10 — Profile injection (resolves the SCP-01 ↔ crash-isolation tension):** the per-discipline/
  federation scoring profile is declared+validated by **pydantic in `segugio.config`** (extends the
  CFG-03 discriminated-union, fail-fast `SystemExit(2)` at config-load on a malformed profile), then
  **adapted to a plain stdlib object/dict and INJECTED** into `score_calc` — exactly the `cam_ids` /
  `overlay_cfg` plain-arg injection pattern already used in `app.py:create_app`. `score_calc` itself
  never imports the config models, so the import-surface allowlist holds.
- **D-11 — Validate-before-compute contract:** `validate()` returns per-field errors (out-of-range,
  missing required field, malformed `mm:ss(.cc)` time, increment mismatch). `compute()` runs only
  after validate passes (the Phase-16 `POST /score` flow: validate → 400 + write-nothing on errors →
  else compute). Success-criterion 2 = "reports per-field errors rather than computing".
- **D-12 — Time format:** parse `mm:ss` and `mm:ss.cc` (hundredths) via a strict regex; agility run
  time uses hundredths. Malformed time is a per-field validation error, never a silent 0.
- **D-13 — Zone model is an ordered band list, NOT a fixed 4-row table:** profile zones are an ordered
  list of `(band, points)` so UFO's 0-point near zone, Skyhoundz's jump-to-5 end zone, and CSEN's
  4 linear bands all express in config. Bonuses are a config-declared list (`[{key, value}]`) so
  CSEN's two +0.5 bonuses and a single-bonus federation both map without code edits.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pinned rule tables (the REQ blocker)
- `https://discdogcsen.it/media/documents/RegolamentoDiscDogCsen2026.pdf` — **CSEN 2026 disc-dog
  ruleset (the pinned DEFAULT profile).** Fully extracted into the D-02/D-03 decisions above
  (Distance: 90s, best-5, 9/18/27/36m → 1/2/3/4, two +0.5 bonuses, cap 5; Freestyle: 4×(0–10, 0.01)
  summed to 40). Source of truth for the CSEN profile fixture + unit-test expected values.
- `https://www.fidasc.it/en/cinofilia-sportiva/discdog/regolamenti-discdog/5699-discdog-2025/file.html`
  — **FIDASC disc-dog ruleset (the alternate profile).** **NOT yet extracted** (HTTP 503 to automated
  fetch). The planner MUST source FIDASC's exact Distance zone table + Freestyle categories/scale
  before building the FIDASC profile.

### Phase research (already produced — read first)
- `.planning/research/v1.3/SUMMARY.md` — keystone (server-authoritative), build order, pitfalls.
- `.planning/research/v1.3/FEATURES.md` — per-federation rule tables + config-driven implications.
- `.planning/research/v1.3/ARCHITECTURE.md` — component layout, `score_calc.py` contract.
- `.planning/research/v1.3/PITFALLS.md` — the 8 named pitfalls (esp. #2 double-source, #5 crash-iso).
- `.planning/research/v1.3/STACK.md` — zero-new-dependency confirmation (stdlib `decimal`).

### In-repo code the phase extends / must not break
- `src/segugio/config/discipline.py` — the CFG-03 pydantic discriminated-union the scoring profile extends.
- `src/segugio/config/loader.py` / `models.py` — fail-fast `yaml.safe_load` + `SystemExit(2)` config-load path.
- `src/segugio/ui/app.py` — `create_app` plain-arg injection (`cam_ids`/`overlay_cfg`) precedent for D-10;
  the current display-only `POST /score` (`post_score`, ~line 193) that Phase 16 makes authoritative.
- `src/segugio/ui/score_render.py` — `render_overlay_text` display-only invariant (SCR-04).
- `tests/test_imports.py` — `PHASE1_SURFACE`, `CONSOLE_HEAVY_MODULES` (numpy+cv2 forced absent),
  the heavy-absent smoke gate to extend.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **CFG-03 discriminated-union** (`config/discipline.py`): `DiscDogProfile | AgilityProfile` on the
  `sport` tag. The scoring profile attaches here so a bad `sport`/profile raises `union_tag_invalid`
  at config-load — the fail-fast surface SCP-02 requires already exists.
- **Plain-arg injection** (`app.py:create_app(channel_dir, cam_ids=(), overlay_cfg=None)`): the exact,
  already-proven mechanism for handing config-derived data to the crash-isolated console without
  importing `segugio.config`. The active scoring profile is injected the same way (D-10).
- **Fail-fast loader** (`config/loader.py`): `yaml.safe_load` + `SystemExit(2)` on any parse/validate
  error — malformed-profile rejection rides this existing path.

### Established Patterns
- **Crash-isolation allowlist** (`tests/test_imports.py`): every `segugio.ui` module must import clean
  with the heavy stack + numpy + cv2 absent. `score_calc` joins `PHASE1_SURFACE`; this is a HARD gate.
- **Display-only renderer** (`score_render.py`, SCR-04): `render_overlay_text` summarizes; it never
  computes. `score_calc` is the compute authority; the renderer stays dumb.
- **decimal-not-float for broadcast numbers** (project decision): the on-air total must be exact.

### Integration Points
- `score_calc.compute/validate` are consumed by Phase-16 `POST /score` (validate → 400 → compute →
  atomic write). This phase builds + unit-tests them standalone; no route wiring here.
- The scoring profile is loaded/validated in `segugio.config` and injected into the console at
  `create_app` time (entrypoint), mirroring `cam_ids`.

</code_context>

<specifics>
## Specific Ideas

- The user pinned the default to **CSEN 2026** and the alternate to **FIDASC** by direct URL — these
  are the federations they actually film. Do NOT default to the international (UFO/USDDN/Skyhoundz)
  tables; they are reference-only.
- CSEN's **best-5-of-N throw cap** and **Catch Ratio as a scored freestyle category** are
  CSEN-specific and surprised the generic research — both must be config-expressible, not hardcoded.
- Agility is explicitly "not of interest right now" — build the engine, ship a generic example, do not
  spend effort pinning Italian agility numbers this milestone.

</specifics>

<deferred>
## Deferred Ideas

- **Real Italian agility rule tables** — defer until an agility event is actually run (D-07).
- **Freestyle penalty auto-modeling** (nature break / excess disc / safety contortion-compression-fall
  ranges) — v1.3 uses a manual adjustment field; auto-modeling is a later enhancement (D-08).
- **Multi-judge combination** beyond `sum` (`average`, `drop_high_low` for UFO Comprehensive) — design
  the combiner seam, ship `sum` only now.
- **Per-category freestyle breakdown on the overlay**, **auto-SCT from course length × speed**,
  **more built-in federation profiles** — post-v1.3 once the core entry path is proven live.
- **Combined division** (freestyle×1.5 + best distance) and roster/standings — cross-run aggregation,
  out of scope (single on-air score only).

</deferred>

---

*Phase: 15-pure-calc-validation-core-scoring-profiles*
*Context gathered: 2026-06-21*
