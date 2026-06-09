---
status: passed
phase: 01-foundation-config-curated-clip-set
source: [01-VERIFICATION.md]
started: 2026-06-09T00:00:00Z
updated: 2026-06-09T15:05:00Z
---

## Current Test

[complete — cataloguer mechanism verified on real footage; corpus partial, gaps recorded below]

## Tests

### 1. Clip coverage verification (curated clip set)
expected: After dropping real disc-dog and agility footage into the fixtures dir and running the cataloguer, the coverage gap report shows all 14 cells (7 conditions × 2 disciplines) covered; any missing cells are named explicitly.
steps: |
  1. Symlinked the owner's footage into `tests/fixtures/disc_dog/gara_full.mp4` (gitignored).
  2. Installed `opencv-python==4.13.0.92` into `.venv` (was missing → probe had failed).
  3. Tagged the clip via frame inspection: `tests/fixtures/disc_dog/gara_full.tags` = jump_sprint_blur, distant, handler_prominent, backlit_dusk.
  4. Ran `.venv/bin/python tools/catalog_clips.py tests/fixtures --out tests/fixtures/clip_manifest.yaml`.
result: pass — MECHANISM verified end-to-end on real footage. opencv probe now returns real metadata (1920×1080, 49.5fps, 1.77M frames, ~10h). The cataloguer wrote a correct manifest and printed an accurate coverage report (4/14 covered). The traversal-safe resolver correctly REFUSED the external symlink (security guard T-01-03a working as designed). Corpus coverage is PARTIAL — the footage is a single 10-hour single-camera disc-dog recording; see Gaps for the data-collection work needed for full coverage.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

Corpus is partial (4/14 condition×discipline cells). These are DATA-collection gaps (not code defects); the cataloguer mechanism is verified. To reach full coverage:

- **agility footage (0/7)** — no agility clips at all. Need agility runs covering all 7 conditions.
- **disc_dog / multi_dog** — not present in the sampled frames (crowded frames were multi-*handler* warmups, not clearly multi-dog). Cut a multi-dog segment if one exists in the 10h recording, or supplement.
- **disc_dog / tunnel_contact_occlusion** — intrinsically N/A for disc dog (tunnels/contacts are agility obstacles). Checklist quirk: this cell can only be filled by agility footage. Consider making `tunnel_contact_occlusion` agility-only in the checklist (Phase-1 follow-up).
- **disc_dog / midfield_equidistant** — intrinsically needs MULTIPLE cameras (it is the inter-camera tie/contention case); a single fixed-camera clip cannot demonstrate it. Will be exercisable once multi-camera footage exists.

**Recommended next data steps:**
1. Cut the 10h `gara_full.mp4` into short (~10-30s) per-condition clips so later phases can select small, fast, single-condition fixtures (a 10h file is unwieldy for unit tests). Tag each cut clip.
2. Source agility footage (own or CC0 Pexels/Pixabay) covering the 7 agility conditions.
3. Add a multi-dog disc clip.
4. For later phases that must READ frames via `segugio.fixtures.resolve_clip_path`, footage must live PHYSICALLY under `tests/fixtures/` (the resolver refuses symlinks escaping the root) — or add an opt-in symlink-follow to the resolver.
