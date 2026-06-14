# Phase 10: Overlay Data Contract & Run-Timestamp Publish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 10-overlay-data-contract-run-timestamp-publish
**Areas discussed:** Run/gen file layout, Safe-default on torn/missing source, Freestyle duration config, fields exposure shape

---

## Run-state + gen file layout

| Option | Description | Selected |
|--------|-------------|----------|
| One file: `overlay_run.json` | running + started_at + gen all in one console-owned file; gen seeded from disk on startup → restart re-anchors with no phantom jump; mirrors single-sidecar PreviewDoc | ✓ |
| Split: `overlay_run.json` + `overlay_gen.json` | run-state separate from a standalone gen counter; two atomic writes to coordinate; marginal isolation benefit | |
| Derive gen from mtimes (no counter) | compute gen from file mtimes; fragile across restart/clock changes; fights offset-cancellation | |

**User's choice:** One file: `overlay_run.json` (Recommended)
**Notes:** gen is a NEW console-owned counter, distinct from the orchestrator-side `PreviewDoc.gen`. Seed-from-disk on `create_app` startup is what sets up the Phase-14 restart re-anchor criterion.

---

## Safe-default on a torn/missing source

| Option | Description | Selected |
|--------|-------------|----------|
| Blank-safe | empty fields / running:false / default discipline; pure & stateless; matches existing read_*; server_now + gen always set | ✓ |
| Last-good cached | console holds last good read in memory; avoids one-poll blank but adds route state + risks airing stale past a fault | |
| Blank-safe + degrade flag | blank-safe plus a `source_ok:false` boolean so the client distinguishes empty-run vs source-failed | |

**User's choice:** Blank-safe (Recommended)
**Notes:** Atomic os.replace writes make torn reads near-impossible, so this only fires on genuine corruption where blanking is honest. Consistent with the whole channel's pure read_* pattern.

---

## Freestyle round-duration config (flagged blocker)

### Where the duration reaches the timer

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 11 /overlay HTML render | keep Phase-10 contract to the 6 live fields; inject duration once at /overlay render (entrypoint arg, like cam_ids); poll=live, page=static; Phase 10 just names the key | ✓ |
| Carry in /overlay-json now | extend the contract with the duration; uniform but re-sends static config every poll and widens the locked contract | |
| Defer entirely to Phase 11 | don't decide the key or touch config now; leaves the flagged blocker open past Phase 10 planning | |

**User's choice:** Phase 11 /overlay HTML render (Recommended)

### Config key placement + name

| Option | Description | Selected |
|--------|-------------|----------|
| New `overlay.*` section | `overlay.freestyle_duration_s`; forward-looking, also future home of BRD logo/theme/identity; defined now, consumed Phase 11 | ✓ |
| Under disc-dog discipline profile | `DiscDogProfile.freestyle_duration_s`; next to the sport, but T&F is fixed 60s and BRD config has no home there | |
| New `timer.*` section | `timer.freestyle_duration_s`; narrowly scoped, but logo/theme then need a separate block | |

**User's choice:** New `overlay.*` section (Recommended)

### Default value

| Option | Description | Selected |
|--------|-------------|----------|
| 90s | common on several circuits; conservative default | |
| 120s | two-minute routines; the user's circuit norm | ✓ |
| No default — required field | mandatory, fail-fast if absent; safer vs wrong silent default but every config must set it | |

**User's choice:** 120s
**Notes:** Org-dependent; user confirmed 2-minute freestyle routines. Orgs running 90s override in config.

---

## `fields` exposure shape

| Option | Description | Selected |
|--------|-------------|----------|
| Raw `ScoreDoc.fields` dict, verbatim | pass fields as-is + discipline; shared Phase-11 JS renderer owns layout + alias resolution; smallest RBT-07 surface; one rendering brain client-side | ✓ |
| Discipline-normalized, server-side | server resolves aliases + emits clean per-discipline structure; dumb JS but adds logic into the crash-isolated console + duplicates layout knowledge | |
| Raw dict + discipline field-schema hint | raw verbatim plus a static per-discipline key list so the contract self-describes | |

**User's choice:** Raw ScoreDoc.fields dict, verbatim (Recommended)
**Notes:** "Verbatim" governs the values (SCR-04, operator-typed, never computed); raw keys are consistent with that. Renderer must encode per-discipline layout anyway, so it also owns the `sct`/`SCT` alias resolution (mirroring `score_render._get`).

---

## Claude's Discretion

- Exact module placement/naming of the new overlay-run read/write helpers + `OverlayRunDoc` record (strongly implied to mirror `PreviewDoc`/`read_preview`).
- Whether `gen` is a record field vs a route-local counter persisted via the record (must end up in `overlay_run.json` either way).
- Precise safe-default `discipline` when `score.json` is absent (lean to the `ScoreDoc()` default `disc_tf`).

## Deferred Ideas

- Freestyle-duration consumption (the counting-down timer) → Phase 11.
- BRD logo path / CSS-var theme / identity line → Phase 11 (share the new `overlay.*` section).
- `source_ok` explicit degrade flag → not taken; revisit only if Phase 11/14 shows the client can't distinguish empty-run vs source-failed.
- Discipline field-schema hint in the contract → not taken (renderer owns the schema).
