---
phase: 08-console-serving-live-multiview-safety-hardening
plan: 03
subsystem: docs
tags: [docs, security, threat-model, lan-trust-boundary, d-09]

# Dependency graph
requires:
  - phase: 07-off-tick-frame-publishing-channel
    provides: preview.enabled source-side off-switch + the preview.json/JPEG channel the console now serves
  - phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
    provides: v1.0 T-05-05-* security posture (LAN-as-trust-boundary, no-auth single-operator console) documented as ui/app.py docstrings
provides:
  - "docs/security.md: written v1.1 threat re-evaluation (D-09, Phase 8 success criterion 5)"
  - "Documented HARD operational requirement: AP client-isolation + no internet/guest bridge"
  - "Cross-reference of v1.0 T-05-05-01..04 threats + the new T-08-03 live-video Information-Disclosure exposure"
affects: [09-explainability-informed-override-tablet-ux, milestone-v1.1-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operational+documented mitigation (network setup) over in-code auth/bind/token for a single-operator LAN field tool"

key-files:
  created:
    - docs/security.md
  modified: []

key-decisions:
  - "D-09: v1.1 reaffirms LAN-as-trust-boundary no-auth posture; mitigation is operational+documented, NOT in-code (no new auth/bind/token)"
  - "preview.enabled (Phase 7) is the source-side off-switch; no separate console-side kill-switch in Phase 8 (deferred to Phase 9 UXT-03)"

patterns-established:
  - "Threat re-evaluations live in docs/security.md cross-referencing the T-05-05-* ids that live as docstrings in ui/app.py"

requirements-completed: [MVW-01]

# Metrics
duration: 3min
completed: 2026-06-13
---

# Phase 8 Plan 03: v1.1 Threat Re-evaluation Summary

**Written v1.1 threat re-evaluation (`docs/security.md`) reaffirming the LAN-as-trust-boundary no-auth posture, adding the live-competitor-video-behind-`0.0.0.0` exposure, and mandating AP client-isolation + no-bridge as a HARD operational requirement — with no new in-code auth/bind/token (D-09).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-13T15:20:00Z
- **Completed:** 2026-06-13T15:23:07Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Created `docs/security.md`, the phase's pure-documentation deliverable and Phase 8 success criterion 5.
- Reaffirmed the v1.0 accepted posture (dedicated WiFi LAN = trust boundary; no auth for a single-operator field tool) and restated all four v1.0 threats (T-05-05-01 path-traversal/whitelisted-paths, T-05-05-02 overlay sanitization, T-05-05-03 contradictory-command rejection, T-05-05-04 LAN trust boundary / no-auth).
- Added the new v1.1 exposure (T-08-03, STRIDE Information Disclosure): live competitor video now sits behind the `0.0.0.0:8080` endpoint via `GET /preview` + `GET /preview/<cam>.jpg`; documented the path-traversal mitigation (whitelist → fixed `cam_{id}.jpg`) and the override-availability control (`threaded=True`/Waitress).
- Documented the HARD operational requirement: the dedicated AP MUST enforce client isolation and MUST NOT be bridged to the internet or other networks.
- Recorded `preview.enabled` as the source-side off-switch and explicitly declined new auth / configurable bind / shared-token for v1.1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write docs/security.md — the v1.1 threat re-evaluation (D-09)** - `8a224c0` (docs)

**Plan metadata:** _(final docs commit below)_

## Files Created/Modified
- `docs/security.md` - The v1.1 written threat re-evaluation: reaffirms the LAN-trust-boundary no-auth posture (T-05-05-*), adds the live-video-behind-`0.0.0.0` exposure (T-08-03), mandates AP client-isolation + no-bridge as a hard operational requirement, names `preview.enabled` as the off-switch, and explicitly declines new auth/bind/token.

## Decisions Made
None beyond the plan — the content contract was fully specified by D-09 (08-CONTEXT.md) and rendered faithfully into prose.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The Task-1 verify command (`os.path.exists` + grep for `0.0.0.0`, `T-05-05`, `client isolation`, `preview.enabled`) passed on the first write. Confirmed no pre-existing `SECURITY.md`/`security.md`/`THREAT_MODEL.md` existed (only `docs/run.md` + `docs/obs-setup.md`); confirmed the `T-05-05-*` ids live in `ui/app.py`'s docstring and not in `orchestrator/loop.py`, so the cross-reference points at the correct source.

## User Setup Required
None - no external service configuration required. The document records a HARD *operational* requirement for the field deployment (dedicated AP must enforce client isolation and must not be bridged) — this is an at-the-venue network-setup obligation, not a code/config step.

## Next Phase Readiness
- Phase 8's documentation deliverable (success criterion 5) is complete; MVW-01 marked complete.
- No blockers. The hardware-milestone carry-forward (real-WiFi false-death validation with phones live) is unrelated to this doc and tracked separately.

## Self-Check: PASSED

- FOUND: docs/security.md
- FOUND: .planning/phases/08-console-serving-live-multiview-safety-hardening/08-03-SUMMARY.md
- FOUND commit: 8a224c0

---
*Phase: 08-console-serving-live-multiview-safety-hardening*
*Completed: 2026-06-13*
