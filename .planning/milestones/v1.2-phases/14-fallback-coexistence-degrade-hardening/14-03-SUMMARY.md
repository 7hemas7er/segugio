---
phase: 14-fallback-coexistence-degrade-hardening
plan: 03
subsystem: operator-docs-config
tags: [overlay-robustness, obs-setup, ndi, security, coexistence, D-06, D-08, SC4, RBT-06]
requires:
  - "14-01: DEAD_MS / isDead() client auto-hide in overlay-render.js (cited as the reason the manual hide step is redundant)"
  - "obs/segugio-scene-collection.json: per-camera ndi_source_name (canonical)"
  - "config.agility.example.yaml: cam_wide ndi_source PHONE-WIDE (NDI HX3) (canonical pair)"
provides:
  - "config.example.yaml cam_wide ndi_source aligned to the canonical scene-JSON name"
  - "test_scene_template.py: per-camera config<->scene ndi_source consistency assertion (drift guard)"
  - "docs/obs-setup.md: D-06 simplified-reveal coexistence section + D-08 byte-match NDI-name note"
  - "docs/security.md: SC#4 HTML-sink posture re-affirmation (textContent / Jinja autoescape)"
affects:
  - "operator OBS setup procedure (one reveal step, one consistent NDI name)"
tech-stack:
  added: []
  patterns:
    - "scene-JSON + agility config are canonical; example config is the outlier to align (RESEARCH A2 / Pitfall 4)"
    - "config ndi_source must byte-match the scene ndi_source_name AND the phone's published name (D-08)"
key-files:
  created: []
  modified:
    - config.example.yaml
    - tests/test_scene_template.py
    - docs/obs-setup.md
    - docs/security.md
decisions:
  - "Direction NOT flipped: cam_wide LOCALHOST drift aligned UP to PHONE-WIDE (NDI HX3) (the other 3 cams + scene JSON + agility config were already canonical)"
  - "D-06 manual hide step removed (not just deprecated): the 14-01 DEAD_MS ~3s auto-hide performs the swap; manual hide is harmless but unnecessary"
  - "security.md added a NEW one-paragraph SC#4 section rather than editing the Phase-13 paragraph (that one covered textContent only; the new section adds the event_name/logo Jinja-autoescape half + the 14-02 test gate)"
metrics:
  duration: ~7min
  tasks: 2
  files: 4
  completed: "2026-06-20"
---

# Phase 14 Plan 03: Operator-Facing Consistency Fixes (D-06 / D-08 / SC#4) Summary

Folded in the operator-facing consistency fixes the Phase-14 validation surfaced — a one-line config NDI-name alignment with a permanent drift-guard test, a simplified single-step coexistence reveal procedure that matches the shipped 14-01 auto-hide behavior, an exact-NDI-name-match doc note, and a re-affirmation of the SC#4 HTML-sink posture. Docs/config only; no code touched (RBT-07 import surface unaffected).

## What Shipped

### Task 1 — D-08 config/scene NDI-name alignment + consistency test (commit 6e473cc)

- **`config.example.yaml` line 27:** `cam_wide.ndi_source` changed from the drift value `"LOCALHOST (iPhone Camera for OBS Studio App)"` to the canonical `"PHONE-WIDE (NDI HX3)"`, matching the scene JSON, the agility config, and the other three cameras. Added an inline `# MUST byte-match the scene JSON's wide ndi_source_name (D-08)` comment. **Direction NOT flipped** (RESEARCH A2 / Pitfall 4 confirmed: the scene JSON + agility config are canonical; the example config cam_wide was the outlier).
- **`tests/test_scene_template.py`:** added two helpers (`_scene_ndi_source_names()` parsing every `id == "ndi_source"` source's `settings.ndi_source_name`; `_config_ndi_sources()` mapping camera id -> config `ndi_source`) and a parametrized `test_config_ndi_source_matches_scene_collection` over both example configs. It asserts every config `ndi_source` byte-matches a scene `ndi_source_name` — catching the "OBS sees it but console blank" drift (T-14-ndidrift). Reused the existing `json.loads(_TEMPLATE.read_text)` / `yaml.safe_load` helpers; no new dependency. Existing scene-name lockstep tests left untouched.

### Task 2 — D-06 simplified-reveal docs + D-08 NDI note + SC#4 re-affirm (commit 979f612)

- **`docs/obs-setup.md` (D-06):** rewrote the coexistence procedure (formerly lines 109-112). The operator's ONLY manual step on a browser-source death is now revealing `Score Text` visible. Removed the redundant "(and, for a clean swap, toggles `Score Overlay` **hidden**)" clause and explained that the browser overlay auto-hides on death via the client `DEAD_MS` threshold (~3s, shipped in 14-01 in `overlay-render.js`). Kept the `Score Text` `visible: false`-while-alive note (avoids a double-score), the read-from-file fallback section, and the "no auto-reveal of the text" guarantee.
- **`docs/obs-setup.md` (D-08):** added a byte-match note near the NDI source setup step — OBS `ndi_source_name`, the phone's published name, and the config `ndi_source` must be the exact same string (`"PHONE-WIDE (NDI HX3)"` cited), warning about the recurring "OBS sees it but the console is blank" gotcha and pointing at the new consistency test.
- **`docs/security.md`:** added a new one-paragraph "HTML-sink output encoding re-affirmed (SC#4, Phase 14)" section: operator score values sink via `textContent` (never `innerHTML`); `event_name` / `logo_path` are Jinja-autoescaped; gated by the SC#4 named test from 14-02. (The Phase-13 paragraph already covered the `textContent` half only; this adds the Jinja-autoescape half + the test-gate cross-reference without duplicating.)

## Deviations from Plan

None — plan executed exactly as written. Direction was confirmed and not flipped; security.md required a genuine addition (the Phase-13 paragraph covered only the `textContent` half), so a non-duplicating new section was added per the plan's "only add the line if not already stated" guidance.

## Threat Model

All threat-register dispositions honored:
- **T-14-ndidrift (mitigate):** config cam_wide aligned to canonical scene name; per-camera config<->scene consistency test added; doc byte-match note added.
- **T-14-revealgap (mitigate):** redundant hide step dropped; single reveal-Score-Text action + auto-hide documented to match shipped behavior.
- **T-14-xss (accept/documented):** SC#4 posture re-affirmed in docs/security.md; no new control.
- **T-14-iso (mitigate):** docs/config-only; no code touched; `test_imports.py` green per task.

No new security surface introduced.

## Verification

- `python -m pytest tests/test_scene_template.py -x` — green (9 tests incl. the new parametrized drift assertion)
- `python -m pytest tests/test_scene_template.py tests/test_imports.py -x` — green (34 tests; RBT-07 import surface unaffected)
- Grep: `config.example.yaml` cam_wide `ndi_source` == `"PHONE-WIDE (NDI HX3)"`; LOCALHOST string absent (0 occurrences)
- Grep: `docs/obs-setup.md` mentions `DEAD_MS` / auto-hide / `PHONE-WIDE (NDI HX3)` (5 occurrences) and no longer instructs hiding `Score Overlay` as a required step

## Self-Check: PASSED

- config.example.yaml — FOUND, cam_wide ndi_source = "PHONE-WIDE (NDI HX3)", LOCALHOST absent
- tests/test_scene_template.py — FOUND, test_config_ndi_source_matches_scene_collection present and green
- docs/obs-setup.md — FOUND, DEAD_MS auto-hide + byte-match note present
- docs/security.md — FOUND, SC#4 section present
- Commit 6e473cc — FOUND (Task 1)
- Commit 979f612 — FOUND (Task 2)
