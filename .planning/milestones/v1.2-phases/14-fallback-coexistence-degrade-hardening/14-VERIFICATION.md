---
phase: 14-fallback-coexistence-degrade-hardening
verified: 2026-06-20
verifier: inline (orchestrator, gsd-execute-phase)
requirements: [RBT-06]
status: human_needed
must_haves_total: 12
must_haves_verified: 12
automated_gate: passed
human_verification_items: 3
human_verification_blocking: false
---

# Phase 14 — Verification Report

**Goal (ROADMAP):** Validate the whole assembled live path under failure — the live-robustness
gate before field acceptance — proving the broadcast never goes scoreless, never shows a stale
timer as live, and the safety-critical override path is never starved.

**Outcome:** Automated gate fully GREEN (12/12 must-have truths verified against the live
codebase). One code-review BLOCKER (CR-01) was found and fixed during this run. The only
remaining items are the three **physical on-rig UAT scenarios**, which are an explicit
**non-blocking carry-forward** per decisions D-01/D-02 (same disposition as the Phase 5/7
hardware UATs). → `status: human_needed`.

## Requirement Traceability

| Req | Disposition | Evidence |
|-----|-------------|----------|
| RBT-06 | Accounted for | Delivered in Phase 13 (overlay.txt fallback *wired* into the scene collection); Phase 14 is its acceptance validation. REQUIREMENTS.md line 46 `[x]` + traceability note. Phase-14 automation gate green; physical acceptance = the deferred HUMAN-UAT. |

Every requirement ID in the Phase-14 PLAN frontmatter (`RBT-06`) is accounted for. No orphans.

## Must-Have Verification (goal-backward)

### 14-01 — two-stage degrade (overlay-render.js)
| # | Truth | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | Console death past DEAD_MS → lower-third fully HIDES (no frozen score airs) | ✓ | `applyDead()` + `is-exiting` reuse (`overlay-render.js:318-323,459-461`); `test_two_stage_stale_then_dead_hides_lower_third` |
| 2 | Short stale (STALE_MS<t<DEAD_MS) only dims (is-stale), never hard-hides | ✓ | `DEAD_MS=3000 > STALE_MS=600`; stage-1 assert in the two-stage gate |
| 3 | Live console with FLAT gen is NEVER dead (response-recency, not gen-age) | ✓ | `isDead()`/`isStale()` keyed on `everResponded && now-lastResponseAt`; `lastGenAt` absent (grep=0); `test_live_idle_run_is_not_dead` |
| 4 | LAN drop → timer stops; resume with same started_at + bumped gen re-anchors continuous (no phantom jump) | ✓ | `currentElapsed()` offset-cancellation; `test_gen_reanchor_no_phantom_jump` |

### 14-02 — RBT-06 per-criterion gates + HUMAN-UAT
| # | Truth | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | overlay.txt holds last score; simulated death leaves it intact (single-writer) | ✓ | `test_overlay_txt_persists_last_score_after_simulated_death` (no 2nd writer) |
| 2 | Poll storm: POST /command < 1.0s AND override written (never starved) | ✓ | `test_command_not_blocked_during_overlay_json_storm` via real `make_server(threaded=True)` |
| 3 | Score sinks via textContent (never innerHTML); GET /overlay autoescapes branding | ✓ | `test_no_innerhtml_sink` + `test_overlay_jinja_autoescapes_branding` |
| 4 | On-rig HUMAN-UAT checklist exists, covers physical scenarios, non-blocking | ✓ | `14-HUMAN-UAT.md` (cites RBT-06; D-01/D-02 non-blocking) |

### 14-03 — operator-facing consistency
| # | Truth | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | obs-setup.md = D-06 simplified reveal (browser auto-hides via DEAD_MS; old hide step gone) | ✓ | `docs/obs-setup.md` (DEAD_MS/auto-hide present, hide step removed) |
| 2 | config.example.yaml cam_wide ndi_source = "PHONE-WIDE (NDI HX3)" (no drift) | ✓ | `config.example.yaml:27`; LOCALHOST drift gone |
| 3 | Consistency test asserts config↔scene NDI-name match (catches future drift) | ✓ | `test_config_ndi_source_matches_scene_collection` |
| 4 | security.md re-affirms SC#4 HTML-sink posture | ✓ | `docs/security.md` (textContent / Jinja autoescape paragraph) |

## Code Review (gate)

Standard-depth review of the 9 changed files surfaced **1 BLOCKER + 3 Warning + 2 Info**
(`14-REVIEW.md`). The blocker was fixed in-run:

- **CR-01 (BLOCKER, FIXED):** the DEAD_MS dead-hide was a one-way `is-exiting` transition — on a
  console death+recovery during a *still-running* run (`running:true→true`), `animateRunEdge`
  never re-showed the plate, so the overlay stayed hidden on air for the rest of the run while
  the timer ticked. The SC#2 gate false-passed it (asserted clock continuity, not visibility).
  Fix: `applyPayload()` now re-shows the lower-third (clear `is-exiting`, restore `is-live`) when
  a live payload is consumed while hidden — keyed on the current class state, NOT gen-age
  (`overlay-render.js:419-432`, commit `be7ef7e`). Regression test
  `test_dead_then_recover_reshows_lower_third` confirmed to FAIL pre-fix / PASS post-fix
  (commit `d3dfa62`). WR-01/WR-02/WR-03 also addressed; IN-01/IN-02 left as-is (cosmetic).

## Test Evidence

Full Phase-14 domain + source-harness regression suite GREEN under the heavy-stack venv
(`venv312`): `test_overlay_degrade_gate.py`, `test_overlay_fallback_gate.py`,
`test_overlay_poll_storm.py`, `test_overlay_html_sink_gate.py`, `test_ui_overlay_render.py`,
`test_ui_freshness.py`, `test_scene_template.py`, `test_imports.py` → all pass.

Full-suite caveat: 3 PRE-EXISTING hardware-rig failures (`test_latency.py` measured-GPU p95,
`test_ndi_mock_sender.py`, `test_ndi_source.py` — need a live NDI sender / measured GPU). These
are untouched by and unrelated to Phase 14 (Phase 14 changed only client JS, overlay/scene
tests, docs, and one config value). Not attributable to this phase.

## Human Verification Required (non-blocking carry-forward, D-01/D-02)

The three physical scenarios in `14-HUMAN-UAT.md` need a real CEF browser-source, a real OBS
text source, and a real LAN interruption — not simulable headlessly:

1. Console death → browser overlay auto-hides within ~DEAD_MS, no frozen "live" score, D-06 reveal works.
2. LAN-cable drop stops the timer; reconnect+restart re-anchors via `gen` with no phantom jump.
3. `overlay.txt` text source keeps airing the last score (single-writer coexistence).

Per D-02 these do NOT block phase completion; they are a hardware/field carry-forward like the
Phase 5/7 UATs. Run them on the rig via `/gsd-verify-work 14`.

**Recurring gotcha to check on the rig:** exact `ndi_source` byte-match (D-08) — "OBS sees it but
the console feed is blank" is an exact-name mismatch.
