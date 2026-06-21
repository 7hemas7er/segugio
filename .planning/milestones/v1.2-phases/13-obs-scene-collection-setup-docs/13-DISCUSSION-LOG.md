# Phase 13: OBS Scene Collection & Setup Docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 13-obs-scene-collection-setup-docs
**Areas discussed:** Browser-source URL default, Text-fallback coexistence, Scene scope (MULTIVIEW/PIP), Browser render settings

---

## Browser-source URL default

| Option | Description | Selected |
|--------|-------------|----------|
| localhost:8080 | `http://localhost:8080/overlay` — works out-of-box when OBS + console share the Windows box; docs note the cross-machine LAN-IP edit | ✓ |
| CONSOLE-LAN-IP placeholder | `http://CONSOLE-LAN-IP:8080/overlay` — non-working placeholder forcing an explicit edit, like the NDI source names | |
| Sample 192.168.x.x IP | `http://192.168.1.50:8080/overlay` — concrete sample LAN IP the operator overwrites | |

**User's choice:** localhost:8080 (Recommended)
**Notes:** Operator edits the URL once in OBS regardless; the cross-machine LAN-IP edit is documented prominently. Bare `/overlay` path, port 8080, no `?t=` nonce.

---

## Text-fallback coexistence

| Option | Description | Selected |
|--------|-------------|----------|
| Wired, hidden by default | `Score Text` `visible:false`; operator toggles it on if the browser blanks/dies on-air. No double-score in normal op; standard practice | ✓ |
| Always visible underneath | `Score Text` `visible:true` beneath the browser layer; auto-airs if browser goes fully transparent, but risks double-display in normal op | |
| You decide | Pick the cleanest policy; would have defaulted to wired-but-hidden | |

**User's choice:** Wired, hidden by default (Recommended)
**Notes:** RBT-06 policy. Phase 14 validates end-to-end. Documented as a manual toggle-on-failure response, not an auto-reveal.

---

## Scene scope (MULTIVIEW/PIP)

| Option | Description | Selected |
|--------|-------------|----------|
| All 7 scenes | SAFE + 4 CAM + MULTIVIEW + PIP — matches ROADMAP SC-1 literally and the lockstep test | ✓ |
| Broadcast scenes only | SAFE + 4 CAM only; skip idle-only MULTIVIEW/PIP grids — would narrow SC-1 | |
| All 7, tweak grid placement | Present everywhere but with adjusted placement/scale on MULTIVIEW/PIP — more per-scene transform work | |

**User's choice:** All 7 scenes (Recommended)
**Notes:** Full-frame lower-third over the idle-only MULTIVIEW/PIP grids accepted as-is for v1; no per-scene transform tuning this phase.

---

## Browser render settings

| Option | Description | Selected |
|--------|-------------|----------|
| 1920x1080 @ 30fps | Matches a 1080p OBS canvas; page-owned transparency, no extra OBS custom CSS; fps 30 matches the tick | ✓ |
| 1280x720 @ 30fps | Lighter CEF load; mismatches a 1080p canvas (OBS would scale) | |
| You decide | Sober defaults matching the canvas | |

**User's choice:** 1920x1080 @ 30fps (Recommended)
**Notes:** Rely on the page's own `html, body { background: transparent }`; no injected OBS CSS.

---

## Claude's Discretion

- OBS browser-source object shape: one shared `Score Overlay` (`browser_source`) def referenced per scene (mirroring `Score Text` / `NDI - PHONE-*`), not per-scene duplication.
- CEF settings: `shutdown_source_when_not_visible:false`, `refresh_when_scene_is_active:false` (SC-1 hard), plus sober defaults.
- Z-order: browser-source must layer above the NDI source — researcher verifies the `items`-array z-order semantics in the OBS export.
- `docs/obs-setup.md` browser-source section (URL, localhost default, cross-machine LAN-IP note, CEF cache-clear procedure, coexistence policy) + one-paragraph `docs/security.md` threat re-eval.
- `tests/test_scene_template.py` extension asserting browser+text sources in lockstep with scene names.

## Deferred Ideas

- Per-scene placement/scale tuning of the overlay on MULTIVIEW/PIP — accepted as-is for v1.
- Auto-reveal text fallback (no operator toggle) — Phase-14/future consideration; v1 policy is a manual toggle.
