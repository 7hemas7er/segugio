---
phase: 01-foundation-config-curated-clip-set
plan: 03
subsystem: test-fixtures
tags: [python, clip-set, manifest, opencv, lazy-import, yaml-safe-load, coverage-report, gitignore]

# Dependency graph
requires:
  - "01-01: src-layout package + pythonpath=src + conftest fixtures + .gitignore fixture-binary rules"
provides:
  - "segugio.fixtures: load_manifest / select_clips / coverage_report / resolve_clip_path + CONDITIONS/DISCIPLINES checklist (opencv-free, importable by P2/P3/P4 tests)"
  - "tools/catalog_clips.py: dev cataloguer (argparse CLI, footage dir at execution time, lazy cv2 probe) -> clip_manifest.yaml + condition-coverage gap report"
  - "tests/fixtures/README.md: license/consent table + no-hardcoded-path ingest procedure"
  - "tests/fixtures/clip_manifest.example.yaml: committed manifest schema example (binaries gitignored)"
  - "FixtureNotPresentError: typed 'fixture not present locally' signal for gitignored binaries"
affects: [02-framing-scorer, 03-decision-engine, 04-yolo-tracker, all-phases-querying-fixtures]

# Tech tracking
tech-stack:
  added: []
  patterns: [external-dir+committed-manifest, lazy-import-boundary, yaml-safe-load-only, traversal-safe-path-resolution, coverage-gap-report, sidecar-tags]

key-files:
  created:
    - src/segugio/fixtures.py
    - tools/__init__.py
    - tools/catalog_clips.py
    - tests/fixtures/README.md
    - tests/fixtures/clip_manifest.example.yaml
  modified:
    - tests/test_fixtures_catalogue.py

key-decisions:
  - "Cataloguer reads condition tags from a per-clip `<clip>.tags` sidecar (comma/newline-separated, validated against CONDITIONS) — keeps tagging out-of-band from the binaries and lets the manifest be regenerated deterministically"
  - "coverage_report / coverage_gaps live as the single source of truth in segugio.fixtures; the cataloguer imports them so the CLI report and the package query API can never drift"
  - "resolve_clip_path resolves RELATIVE to the fixtures root and refuses `..` traversal (raises ValueError) / absent binaries (raises FixtureNotPresentError) — mitigates T-01-03a without shelling out"
  - "Manifest `file` paths stored POSIX-relative (rel.as_posix()) so the committed YAML is OS-agnostic"
  - "A bad/unreadable clip yields zero-metadata + a logged warning instead of aborting the scan (threat T-01-03d accept: dev tool, re-runnable)"

requirements-completed: [TST-01]

# Metrics
duration: 5min
completed: 2026-06-09
---

# Phase 1 Plan 03: Curated Clip Set Substrate Summary

**A dev cataloguer (`tools/catalog_clips.py`) that scans a CLI-supplied footage directory, probes each clip via opencv (lazy `import cv2`, no ffprobe), and emits a queryable `clip_manifest.yaml` plus a condition-coverage gap report; an opencv-free package-side query API (`segugio.fixtures`: `load_manifest`/`select_clips`/`coverage_report`/`resolve_clip_path` + the 7×2 condition checklist) so later phases select clips by condition+discipline; a `tests/fixtures/README.md` documenting license/consent and the no-hardcoded-path ingest procedure; and the external-dir + committed-manifest pattern (binaries gitignored, no git-lfs).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-09T00:47:51Z
- **Completed:** 2026-06-09
- **Tasks:** 2
- **Files created:** 5 (+ 1 modified test file)

## Accomplishments

- **`segugio.fixtures`** — the package-side, opencv-free query API:
  - `CONDITIONS` (the 7-item checklist: multi_dog, handler_prominent, tunnel_contact_occlusion, jump_sprint_blur, distant, backlit_dusk, midfield_equidistant) and `DISCIPLINES` (disc_dog, agility) as module constants — the contract later phases filter against.
  - `load_manifest(path)` via `yaml.safe_load` only (never `yaml.load`); normalizes a missing/empty `clips` to `[]`.
  - `select_clips(manifest, discipline, conditions)` — filters by discipline and requires ALL requested conditions (superset match); empty filter returns all.
  - `coverage_report(manifest)` — the `discipline → condition → bool` matrix (covered = at least one tagged clip).
  - `resolve_clip_path(file, fixtures_root)` — resolves relative to the fixtures root, refuses `..` traversal (ValueError) and absent binaries (`FixtureNotPresentError`, a clear "fixture not present locally" signal since binaries are gitignored).
- **`tools/catalog_clips.py`** — the dev cataloguer (argparse CLI, not runtime):
  - `probe(path)` lazily `import cv2` inside the function, reading `CAP_PROP_FRAME_WIDTH/HEIGHT/FPS/FRAME_COUNT`; `duration_s = frames/fps` (None when fps==0).
  - `catalog(footage_dir, out_manifest)` — `footage_dir` is a CLI argument, NEVER hardcoded (CONTEXT.md KEY DECISION); infers discipline from the sub-dir, reads `.tags` sidecars, probes metadata, writes `clip_manifest.yaml` with POSIX-relative paths. Empty dir → empty manifest + a written file.
  - `coverage_gaps` + `format_coverage_report` — flag every missing `{condition × discipline}` cell so the user knows what to supplement (Pitfall 6).
- **`tests/fixtures/README.md`** — `## License` table (per-clip source + consent), the "footage stays local/un-committed" statement (Pitfall 4), the drop-location convention, and the ingest procedure (drop → run the cataloguer with the footage dir as an arg → review gaps → supplement with CC0 Pexels/Pixabay). No hardcoded absolute path.
- **`tests/fixtures/clip_manifest.example.yaml`** — committed schema example with 3 entries (2 disc_dog, 1 agility) demonstrating conditions/source/license/metadata.
- **`tests/test_fixtures_catalogue.py`** — replaced the Wave-0 skip with 20 passing tests (no skipped placeholder remains): checklist constants, opencv-absent import proof, mocked `probe`, `catalog` over a temp dir, select/coverage/load, traversal + not-present-locally, README/example-manifest assertions, and the `git check-ignore` gitignore-policy proof.

## Task Commits

Each task was committed atomically:

1. **Task 1: Cataloguer (opencv probe) + manifest query API + checklist constants** — `735156e` (feat)
2. **Task 2: Fixtures README (license/consent + ingest), example manifest, gitignore proof** — `f30d683` (feat)

**Plan metadata:** final docs commit — see below.

_Note: Task 1 was marked `tdd="true"`. tdd_mode is off at the orchestrator level (MVP+TDD runtime gate did not apply), but the RED→GREEN flow was followed: the cataloguer/query tests were written first and confirmed failing (`ModuleNotFoundError: segugio.fixtures`) before `fixtures.py` / `catalog_clips.py` were implemented to green._

## Files Created/Modified

- `src/segugio/fixtures.py` — manifest loader + query helpers + checklist constants + `FixtureNotPresentError`. Imports only `pathlib`, `yaml`, `loguru` (no opencv).
- `tools/__init__.py` — makes `tools` an importable package so tests can `import tools.catalog_clips`.
- `tools/catalog_clips.py` — argparse dev cataloguer; lazy `import cv2` in `probe`; reuses `segugio.fixtures.coverage_report` for the gap report.
- `tests/fixtures/README.md` — license/consent + ingest procedure (no hardcoded path).
- `tests/fixtures/clip_manifest.example.yaml` — committed manifest schema example.
- `tests/test_fixtures_catalogue.py` — 20 tests (was a single Wave-0 skip).

## Decisions Made

- **Sidecar `.tags` for condition tags** — each clip's conditions live in a `<clip>.tags` file next to the binary (comma/newline-separated, validated against `CONDITIONS`, unknown tags dropped with a warning). Keeps tagging deterministic and lets the manifest be regenerated from footage + sidecars alone.
- **Coverage logic centralised in `segugio.fixtures`** — `coverage_report`/`coverage_gaps` are the single source of truth; the cataloguer imports them, so the CLI gap report and the package query API can never diverge from the checklist.
- **Traversal-safe, opencv-free resolver** — `resolve_clip_path` resolves under the fixtures root and refuses escapes/absent binaries via typed errors (T-01-03a), with no shell interpolation.
- **POSIX-relative manifest paths** — `rel.as_posix()` keeps the committed YAML OS-agnostic.

## Deviations from Plan

None — plan executed exactly as written. All Task 1 and Task 2 acceptance criteria and the plan-level verification passed on the first implementation pass; no Rule 1-4 deviations were triggered.

## Issues Encountered

- **opencv not installed in `.venv`** — expected and by design (01-01 installed only the light Phase-1 deps; the plan's AC explicitly requires `import segugio.fixtures` to succeed with opencv UNINSTALLED). Handled exactly as the plan intended: `fixtures.py` imports no opencv, and the cataloguer's `probe` is the sole `import cv2` (lazy, inside the function). Tests mock `cv2.VideoCapture` (a fake module injected via `monkeypatch.setitem(sys.modules, "cv2", ...)`), so the whole suite runs with no opencv present.

## Verification Evidence

- `python -m pytest tests/test_fixtures_catalogue.py -q` → 20 passed, 0 skipped.
- `python -m pytest -q` (full Phase-1 suite) → all green; the only skip is `test_generators.py` (plan 01-04's Wave-0 placeholder, out of scope).
- Task 1 ACs: `grep -Ec "midfield_equidistant|tunnel_contact_occlusion" src/segugio/fixtures.py` = 4 (≥2); `grep -Ec "yaml\.load\(" src/segugio/fixtures.py` = 0; `grep -c "import cv2" tools/catalog_clips.py` = 1; `grep -Ec "argparse|add_argument" tools/catalog_clips.py` = 6; `import segugio.fixtures` succeeds with `cv2` forced to `None`.
- Task 2 ACs: `grep -c "## License" tests/fixtures/README.md` = 1; README references `tools/catalog_clips.py`; `grep -Ec "^/|[A-Za-z]:\\\\" tests/fixtures/README.md` = 0; example manifest parses to 3 clips spanning both disciplines; `git check-ignore tests/fixtures/disc_dog/sample.mp4` returns the path (ignored) while `git check-ignore tests/fixtures/README.md` is empty (not ignored).
- End-to-end smoke: `python tools/catalog_clips.py <empty_dir> --out <tmp>/clip_manifest.yaml` produced an empty manifest + an all-14-missing coverage gap report (no footage needed).

## Threat Surface

All four threat-register items addressed as the model prescribes:
- **T-01-03a (path traversal):** `resolve_clip_path` resolves relative to the fixtures root and refuses `..`-escape / absolute paths (ValueError); footage dir is an argparse arg, never shell-interpolated. Tested.
- **T-01-03b (YAML RCE):** `load_manifest` uses `yaml.safe_load` exclusively; `grep` for `yaml.load(` is 0. Tested.
- **T-01-03c (footage rights):** binaries gitignored, only manifest + README committed; README documents consent/license; `git check-ignore` test proves the policy. Tested.
- **T-01-03d (corrupt clip DoS — accept):** `catalog` wraps each `probe` in try/except, recording zero-metadata + a logged warning rather than aborting the scan.

No new security surface beyond the plan's threat model.

## Known Stubs

None. The cataloguer + query API are fully implemented and tested; the empty manifest / all-missing coverage report on an empty footage dir is the *designed* zero-footage behaviour (the mechanism is complete; real footage is dropped in at execution time per the locked CONTEXT.md decision), not a stub.

## User Setup Required

- **At ingest time (when real footage is available):** drop competition footage into `tests/fixtures/disc_dog/` and `tests/fixtures/agility/`, write a `<clip>.tags` sidecar per clip, then run `python tools/catalog_clips.py <footage_dir> --out tests/fixtures/clip_manifest.yaml` and review the printed coverage gap report; supplement any missing `{condition × discipline}` cells with CC0 Pexels/Pixabay clips. Footage stays local/un-committed. (`opencv-python` must be installed in the run environment for `probe` — it is one of the locked heavy/optional deps, installed on the CUDA box; not needed to run the tests.)

## Next Phase Readiness

- Phases 2/3/4 can now `from segugio.fixtures import select_clips, coverage_report, CONDITIONS, DISCIPLINES` to pull condition-specific clip subsets in their eval tests (e.g. "agility tunnel-occlusion clips"), with `resolve_clip_path` surfacing a clear signal when the footage hasn't been dropped in locally.
- The TST-01 mechanism (cataloguer + manifest + coverage report + README) is complete; the coverage gap report is the tool that flags exactly which conditions the user's real footage is missing.
- Plan 01-04 (synthetic generators, TST-02) is the remaining Phase-1 plan; its `test_generators.py` scaffold is the only remaining skipped placeholder.

## Self-Check: PASSED

All 5 created files present on disk; the modified test file present; both task commits (`735156e`, `f30d683`) exist in the repo. Full suite green. No missing items.

---
*Phase: 01-foundation-config-curated-clip-set*
*Completed: 2026-06-09*
