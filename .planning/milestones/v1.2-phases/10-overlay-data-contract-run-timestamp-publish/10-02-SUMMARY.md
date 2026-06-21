---
phase: 10-overlay-data-contract-run-timestamp-publish
plan: 02
subsystem: opcomm
tags: [overlay, opcomm, record, channel, crash-isolation, wave-1]
requires:
  - "src/segugio/opcomm/records.py PreviewDoc/ScoreDoc frozen-record idiom (analog)"
  - "src/segugio/opcomm/channel.py write_preview/read_preview + _read_json + atomic_write_json (analog)"
  - "tests/test_opcomm_overlay_run.py RED scaffold (10-01)"
provides:
  - "OverlayRunDoc frozen record {running, started_at, gen} with nullable started_at + scalar coercion"
  - "write_overlay_run(path, doc) — atomic always-fsync write of overlay_run.json"
  - "read_overlay_run(path) — never-raise safe-default reader (absent/torn/malformed → OverlayRunDoc())"
  - "OverlayRunDoc in records.__all__; write_overlay_run/read_overlay_run in channel.__all__"
affects:
  - "Plan 10-04 (/overlay-json route + post_run side-write + post_score gen-bump assemble from these readers/writers)"
tech-stack:
  added: []
  patterns:
    - "Frozen-record object.__setattr__ boundary normalization with a NULLABLE field (started_at: None survives un-coerced)"
    - "Never-raise file-read boundary over _read_json → OverlayRunDoc() safe default + logger.warning on invalid"
    - "Atomic always-fsync write via atomic_write_json (no hand-rolled open().write)"
key-files:
  created: []
  modified:
    - "src/segugio/opcomm/records.py"
    - "src/segugio/opcomm/channel.py"
    - "tests/test_opcomm_overlay_run.py"
decisions:
  - "started_at is nullable: __post_init__ and read_overlay_run preserve None (the STOP/not-started state, D-03) — never float(None) → never silently 0.0"
  - "OverlayRunDoc is a SEPARATE console-owned file (overlay_run.json); runstate.json/RunState untouched — the director never reads this sidecar (HARD D-03 invariant)"
metrics:
  duration: 4min
  tasks: 2
  files: 3
  completed: "2026-06-14"
---

# Phase 10 Plan 02: Overlay-Run Sidecar Record & IO Helpers Summary

OverlayRunDoc with refresh-safe IO: a frozen, ==-comparable `{running, started_at, gen}` record plus `write_overlay_run`/`read_overlay_run` riding the existing always-fsync `atomic_write_json` writer and the `_read_json` never-raise boundary — the durable, torn-safe carrier of the run-start instant and monotonic gen (D-01), a NEW console-owned file the director never touches (D-03). Flips `tests/test_opcomm_overlay_run.py` from the 10-01 RED scaffold to fully GREEN.

## What Was Built

- **`src/segugio/opcomm/records.py`** — added `@dataclass(frozen=True) class OverlayRunDoc` after `PreviewDoc`, a line-for-line analog of the `PreviewDoc`/`ScoreDoc` frozen-record idiom: fields `running: bool = False`, `started_at: float | None = None`, `gen: int = 0`, with a `__post_init__` that coerces via `object.__setattr__` — `running → bool`, `gen → int`, and `started_at → float` ONLY when not None (a `None` survives as the STOP/absent state). No Enum field, no container normalization (scalar-only). Exported via `records.__all__`. No new imports (`dataclass`/`field` already present).
- **`src/segugio/opcomm/channel.py`** — extended the `.records` import to include `OverlayRunDoc`; added `write_overlay_run(path, doc)` (an explicit dict through `atomic_write_json`, mirroring `write_preview`) and `read_overlay_run(path)` (reads via `_read_json`; non-dict → `OverlayRunDoc()`; else coerces inside a `try`, preserving nullable `started_at`; on `(ValueError, TypeError)` logs `logger.warning` and returns `OverlayRunDoc()`). Both names appended to `channel.__all__`. No new external import (json/loguru/atomic_write_json already present).
- **`tests/test_opcomm_overlay_run.py`** — removed all five `@pytest.mark.xfail(... Plan 10-02 ...)` markers, flipping the round-trip / safe-default-absent / safe-default-malformed (4 params) / frozen / normalize tests into permanent regression guards.

## How It Works

`OverlayRunDoc` normalizes its three scalars once at construction so two equal-content docs compare `==` (the round-trip equality contract). The nullable `started_at` is the only departure from a plain coercion: `None` is the run-not-started / stopped state and must never become `0.0`, so both `__post_init__` and `read_overlay_run` short-circuit the `float()` cast on `None`.

`write_overlay_run` serializes an explicit `{running, started_at, gen}` dict through `atomic_write_json` (same-dir temp + fsync + Windows MoveFileEx sharing-violation retry), so a reader never observes a partially-written run-edge file (T-10-02-02). `read_overlay_run` assembles exclusively over the single `_read_json` never-raise boundary: absent/empty/torn/binary-garbage/wrong-shape all collapse to `None` → `OverlayRunDoc()`, and any residual coercion failure is logged and safe-defaulted (T-10-02-01 / D-04). Nothing in this triad can raise into the future `/overlay-json` route or the director loop.

This is a SEPARATE file from `runstate.json` — `RunState`/`write_runstate` are entirely untouched, preserving the HARD D-03 invariant that the director reads runstate every tick and never the overlay sidecar.

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed as written.

### Notes (non-deviation)

- The plan's regression-verification line named `tests/test_opcomm_records.py`, which does not exist in the repo (no separate records test file). Ran the existing named regression target `tests/test_preview_channel.py` (green) plus the broader opcomm/UI/crash-isolation suite instead. No code change implied; this is a documentation note, not a deviation.

## Verification

- `python -m pytest tests/test_opcomm_overlay_run.py -q -rX` → 8 passed, zero xfail, zero XPASS (all 5 functions + 4 malformed params now real assertions).
- `python -m pytest tests/test_preview_channel.py -q` → green (the new record/helpers did not regress the existing opcomm surface).
- `python -m pytest tests/test_imports.py tests/test_ui_run.py tests/test_ui_score.py -q` → 39 passed (crash-isolation allowlist RBT-07 intact; UI routes unaffected).
- Crash-isolation: no new external import entered `records.py` or `channel.py` — both stay stdlib (`dataclasses`/`json`) + loguru + the in-repo `atomic_write_json`.
- `write_overlay_run` body references `atomic_write_json` (channel.py L247), not `open(...).write` (grep-verified) — T-10-02-02 mitigation present.

## Self-Check: PASSED

- FOUND: src/segugio/opcomm/records.py (contains `class OverlayRunDoc`)
- FOUND: src/segugio/opcomm/channel.py (defines write_overlay_run + read_overlay_run)
- FOUND commit a1d9398 (Task 1: OverlayRunDoc record)
- FOUND commit 0dc2cfb (Task 2: channel helpers)
