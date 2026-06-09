---
status: passed
phase: 01-foundation-config-curated-clip-set
source: [01-VERIFICATION.md]
started: 2026-06-09T00:00:00Z
updated: 2026-06-09T15:18:00Z
---

## Current Test

[complete — cataloguer mechanism verified on real footage AND a per-condition clip set was cut from the master recording]

## Tests

### 1. Clip coverage verification (curated clip set)
expected: After dropping real disc-dog and agility footage into the fixtures dir and running the cataloguer, the coverage gap report shows all 14 cells (7 conditions × 2 disciplines) covered; any missing cells are named explicitly.
steps: |
  1. Symlinked the owner's footage into `tests/fixtures/disc_dog/gara_full.mp4` (gitignored). It is ONE ~10h, 1080p50, single-fixed-camera full-day FIDASC disc-dog recording (not a clip set).
  2. Installed `opencv-python==4.13.0.92` into `.venv` (was missing → probe had failed).
  3. Auto-located active runs in the 10h file via a lower-third-graphic detector (no need to watch 10h), inspected frames, and cut **6 ~30s per-condition clips** with opencv VideoWriter (no ffmpeg):
     - `sprint_blur_01` (jump_sprint_blur), `handler_close_01` (handler_prominent), `distant_01` (distant), `crowd_distractor_01` (handler_prominent + spectator-crowd distractor), `warm_jump_01` (jump_sprint_blur + handler_prominent, warm light), `dusk_distant_01` (distant + backlit_dusk, golden evening light).
  4. Left `gara_full.mp4` untagged (master source, never selected per-condition).
  5. Ran the cataloguer → `clip_manifest.yaml` (7 clips) + coverage report; verified `select_clips` returns the right short clips and `resolve_clip_path` resolves the physical cut clips.
result: pass — Mechanism verified end-to-end, AND the 10h master is now a usable per-condition fixture set. disc_dog coverage = 4/7 conditions (jump_sprint_blur, distant, handler_prominent, backlit_dusk), each backed by ≥1 short clip; `select_clips`/`resolve_clip_path` work. The traversal-safe resolver correctly refuses the external `gara_full` symlink (security guard) but accepts the physical cut clips.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

Remaining corpus gaps (DATA-collection, not code; the mechanism + 4 disc_dog conditions are done):

- **agility (0/7)** — no agility footage exists. Need agility runs (own or CC0) for all 7 agility conditions.
- **disc_dog / multi_dog** — NOT present in this footage: disc-dog competition runs are one-dog-at-a-time; sampled "crowded" segments were multi-*person* warmups + spectator crowds, not 2+ dogs. Needs training/warmup footage, a pairs/relay event, or a CC0 multi-dog clip. (`crowd_distractor_01` captures the multi-*person* distractor case, which still stresses competitor-lock.)
- **disc_dog / tunnel_contact_occlusion** — intrinsically N/A for disc dog (tunnels/contacts are agility obstacles). Checklist quirk: this cell is only fillable by agility footage. Consider making `tunnel_contact_occlusion` agility-only (Phase-1 follow-up).
- **disc_dog / midfield_equidistant** — intrinsically needs MULTIPLE cameras (it is the inter-camera tie case); a single fixed-camera clip cannot demonstrate it.

Note: for later phases that READ frames, footage must live PHYSICALLY under `tests/fixtures/` (the resolver refuses symlinks escaping the root). The cut clips satisfy this; the 10h `gara_full` master is a symlink and is not resolvable (by design — it is only the cutting source).
