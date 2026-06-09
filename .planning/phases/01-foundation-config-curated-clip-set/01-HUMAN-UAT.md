---
status: partial
phase: 01-foundation-config-curated-clip-set
source: [01-VERIFICATION.md]
started: 2026-06-09T00:00:00Z
updated: 2026-06-09T00:00:00Z
---

## Current Test

[awaiting human testing — depends on user-provided footage, available at a later time]

## Tests

### 1. Clip coverage verification (curated clip set)
expected: After dropping real disc-dog and agility footage into the fixtures dir and running the cataloguer, the coverage gap report shows all 14 cells (7 conditions × 2 disciplines) covered; any missing cells are named explicitly so they can be supplemented with CC0 clips.
steps: |
  1. Drop footage into `tests/fixtures/disc_dog/` and `tests/fixtures/agility/` (binaries are gitignored).
  2. Optionally add `.tags` sidecar files annotating conditions per clip.
  3. Run: `.venv/bin/python tools/catalog_clips.py <footage_dir> --out tests/fixtures/clip_manifest.yaml`
  4. Review the coverage gap report.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
