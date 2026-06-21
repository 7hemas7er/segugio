---
phase: 14
slug: fallback-coexistence-degrade-hardening
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-21
---

# Phase 14 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

This phase hardens the live-broadcast overlay coexistence/degrade path (RBT-06). The only
runtime code change is `src/segugio/ui/static/overlay-render.js` (the second `DEAD_MS` degrade
stage + the CR-01 recovery re-show); the rest is per-criterion named gates, docs, and a config
NDI-name alignment. Each declared mitigation was verified to be PRESENT in the implementation
(source grep + an executing gate), not merely documented or intended.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| console → OBS CEF browser source | served `overlay-render.js` + `/overlay-json` payload cross into the broadcast renderer; a frozen/stale render must never air as "live" | score values, run/timer state, gen, branding |
| operator/network → console | a LAN drop / console death is an untrusted liveness event the watchdog must detect via response-recency | poll-response recency (timing only) |
| operator → console → OBS overlay | operator-entered score values + static branding cross into the broadcast HTML/JS sink | untrusted operator text (score fields, `event_name`, `logo_path`) |
| tablet network → console | concurrent `/overlay-json` GETs (a poll storm) contend with the safety-critical `POST /command` override on the WSGI worker pool | HTTP GET/POST on the dedicated LAN |
| dead console → OBS read-from-file | `overlay.txt` on disk is the fallback airing path when the console stops answering | rendered last-score line |
| operator config/docs → OBS box | the operator copies an NDI source name + a fallback-reveal procedure from the repo into a live OBS profile; a drifted/ambiguous string blanks a feed on air | NDI source-name strings, reveal procedure |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-14-degrade | Information Disclosure / Tampering | overlay-render.js freshness watchdog (frozen score airs as live) | mitigate | Two-stage degrade: `isStale()` dims past `STALE_MS` (`is-stale`), `isDead()` HIDES past `DEAD_MS` (`is-exiting`) + stops rAF loop — `overlay-render.js:300-323,357-379,479-489`; gated by `test_two_stage_stale_then_dead_hides_lower_third` | closed |
| T-14-falsehide | DoS (self-inflicted) | `isDead()` mis-keyed on gen-age would false-hide a live idle run | mitigate | `isDead()` keyed on `everResponded && Date.now() - lastResponseAt > DEAD_MS` (response-recency, never gen-age) — `overlay-render.js:311-313`; `lastGenAt` ABSENT from source (grep: 0 hits); gated by `test_live_idle_run_is_not_dead` | closed |
| T-14-phantom | Tampering (broadcast integrity) | timer re-anchor on restart | mitigate | timer stops on stale; `currentElapsed()` re-measures skew from persisted `started_at` on resume (`overlay-render.js:325-330,402-446`); gated by `test_gen_reanchor_no_phantom_jump`. CR-01 recovery re-show at `overlay-render.js:419-432`, gated by `test_dead_then_recover_reshows_lower_third` | closed |
| T-14-xss | Tampering / Elevation | operator score / `event_name` / `logo` injected as markup in CEF overlay | mitigate | score values sink via `textContent` only (`overlay-render.js:114,117,149-161,351`); no `innerHTML =` / `.innerHTML` in source; `event_name`/`logo_path` Jinja-autoescaped (`overlay.html:244,255`, served via `app.py:302`); gated by `test_no_innerhtml_sink` + `test_overlay_jinja_autoescapes_branding` | closed |
| T-14-dos | Denial of Service | `/overlay-json` poll storm starves `POST /command` | mitigate | threaded WSGI: `waitress.serve` or `app.run(..., threaded=True)` fallback (`app.py:401-407`); gated by `test_command_not_blocked_during_overlay_json_storm` (real `make_server(threaded=True)`, 8 concurrent GETs, `POST /command < 1.0s` AND `force_cam` written) | closed |
| T-14-fallback | Tampering (broadcast integrity) | a second `overlay.txt` writer clears the last score on death | mitigate | `POST /score` is the SOLE `overlay.txt` writer (`app.py:210` `atomic_write_text`); orchestrator never writes `overlay.txt` (grep: declares the path only at `runtime.py:82`); gated by `test_overlay_txt_persists_last_score_after_simulated_death` (no second writer added) | closed |
| T-14-ndidrift | Tampering (feed blanks) | config/scene NDI source-name drift | mitigate | `config.example.yaml:27` `cam_wide.ndi_source = "PHONE-WIDE (NDI HX3)"` (LOCALHOST drift gone); byte-matches scene JSON `ndi_source_name` (`obs/segugio-scene-collection.json:126,132,138,144`); gated by `test_config_ndi_source_matches_scene_collection` (parametrized over both configs) | closed |
| T-14-revealgap | Repudiation / operational error | stale "hide Score Overlay" instruction conflicts with `DEAD_MS` auto-hide | mitigate | `docs/obs-setup.md:113-141` documents the single reveal-`Score Text` action + `DEAD_MS` auto-hide; old "hide Score Overlay" step explicitly "redundant and removed" (lines 134-136); auto-reveal-on-recovery documented (lines 126-132) | closed |
| T-14-iso | Elevation / DoS | `segugio.ui` import surface (RBT-07 crash-isolation) | mitigate | Phase change is pure client-JS / test / docs-config — no heavy import added; console imports only Flask (in-factory) + `segugio.opcomm`; gated by `test_console_resolves_with_heavy_stack_and_numpy_absent` (torch/cv2/numpy/cyndilib/obsws forced absent, GET /overlay-json + /overlay still 200) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Verification Notes

All nine threats are disposed `mitigate` and were verified PRESENT in implementation, not merely
in docs. Verification was run with `./venv312/Scripts/python.exe` (the active system python is
CPU-only and lacks ultralytics; the gates here need only Flask/werkzeug + node, both available).

- **42/42 gate tests PASS** (`test_overlay_degrade_gate.py`, `test_overlay_fallback_gate.py`,
  `test_overlay_poll_storm.py`, `test_overlay_html_sink_gate.py`, `test_scene_template.py`,
  `test_imports.py`). Node 24.16 is present, so the four fake-DOM degrade gates EXECUTED (did
  not skip).
- **CR-01 (the REVIEW blocker — lower-third permanently hidden after a recoverable >DEAD_MS
  outage during a live run) is FIXED in code** at `overlay-render.js:419-432`: when a live
  payload (`running:true`) is consumed while the plate carries `is-exiting`, the dead-hide is
  cleared and `is-live` restored. Verified PRESENT and gated by the EXECUTING node test
  `test_dead_then_recover_reshows_lower_third`, which asserts `is-exiting` is cleared and
  `is-live` restored on recovery. This directly closes the T-14-degrade / T-14-phantom
  broadcast-integrity gap the REVIEW raised.
- **T-14-falsehide negative check:** grep for `lastGenAt` in `overlay-render.js` → 0 hits; the
  gen-age anti-pattern (260615-tsi) is confirmed ABSENT. `gen`/`lastGen` exist only to gate the
  DOM re-render, never liveness.
- **T-14-fallback single-writer:** repo-wide grep confirms `atomic_write_text(_OVERLAY_FILE)`
  appears ONLY at `app.py:210`; the orchestrator (`runtime.py`) declares the `overlay.txt` path
  string in its channel-bundle dict but never writes it (it writes only preview JPEGs/JSON via
  `atomic_write_bytes` / `write_preview`).

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| (inherited) | T-05-05-04 | No-auth on the `0.0.0.0:8080` console — accepted single-operator dedicated-LAN field-tool posture; documented in `docs/security.md` and `app.py` docstrings. Reaffirmed, not changed, by Phase 14 (no new route, no new exposure). | v1.0 / reaffirmed Phase 8 (`docs/security.md`) | (pre-Phase-14) |

*No NEW accepted risks introduced by Phase 14 — all nine phase threats are mitigated and closed.*
*Pre-existing accepted risks (T-05-05-04 LAN/no-auth and T-08-03 live-video exposure) are
documented in `docs/security.md` and are out of scope for this phase's register.*

---

## Unregistered Flags

The three SUMMARY files report **no new security-relevant attack surface**:
- `14-01-SUMMARY.md` — `tech-stack.added: []`; pure client-JS + node-gate edit.
- `14-02-SUMMARY.md` — "## Threat Surface: No new security-relevant surface introduced" — all
  four artifacts are tests/docs; the gates ASSERT existing mitigations (T-14-xss / T-14-dos /
  T-14-fallback) and stay Flask-test_client / werkzeug only (T-14-iso clean).
- `14-03-SUMMARY.md` — "No new security surface introduced"; docs/config-only.

No SUMMARY `## Threat Flags` entry lacks a threat mapping. **No unregistered flags.**

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-21 | 9 | 9 | 0 | gsd-security-auditor (Claude) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-21
