# Phase 8: Console Serving, Live Multiview & Safety Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 8-console-serving-live-multiview-safety-hardening
**Areas discussed:** Bandwidth-cap behavior, LIVE / dead-feed visuals, Layout scope now vs P9, Threat re-eval posture

---

## Bandwidth-cap behavior

### Cap mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Static engineered ceiling | Config defaults (fps × max_width × jpeg_quality) chosen so the COMPUTED total bitrate is provably ≤ ceiling; startup/config-validation rejects over-cap configs. No runtime feedback loop. | ✓ |
| Runtime-adaptive throttle | Publisher measures output bytes and dynamically drops fps/quality near the cap. More robust on contended WiFi, more moving parts, overlaps Phase 9 hygiene (UXT-03). | |

**User's choice:** Static engineered ceiling
**Notes:** Matches research "engineer to a hard ceiling (≤ 5–8 Mbps)"; keeps the never-crash side simple; avoids overlapping Phase 9's "preview degrades first."

### Cap proof (no real phones in dev)

| Option | Description | Selected |
|--------|-------------|----------|
| Computed-budget assertion + deferral | Headless test asserts configured fps×res×quality ≤ ceiling and over-cap config is rejected; real-WiFi-with-phones false-death validation documented as a hardware-milestone carry-forward. | ✓ |
| Simulated-contention harness | Build a synthetic network-contention/load harness without phones. More confidence, added build cost, questionable fidelity. | |

**User's choice:** Computed-budget assertion + documented deferral
**Notes:** Consistent with all of v1 being software-complete on synthetic data; roadmap criterion 4's "with phones live" validation waits for the hardware milestone.

---

## LIVE / dead-feed visuals

### Dead logic

| Option | Description | Selected |
|--------|-------------|----------|
| status.alive OR preview-stale | Tile reads MORTO if watchdog says dead OR preview hasn't refreshed within a freshness window. Belt-and-suspenders. | ✓ |
| status.alive only | Tile trusts the director's verdict, ignores preview age; defers all freshness to Phase 9. Risk: frozen-but-"alive" preview slips through. | |

**User's choice:** status.alive OR preview-stale
**Notes:** MVW-03 explicitly names both inputs; the deeper "never show a frozen frame as live" staleness overlay stays Phase 9 (UXT-03).

### Stale window

| Option | Description | Selected |
|--------|-------------|----------|
| ~2–3× publish interval | ~0.6–1 s at ~5 fps, computed FROM configured fps. Tolerates jitter / 1–2 dropped frames; flags a freeze within ~1 s. | ✓ |
| Tight (~1× interval) | Flag within one missed frame (~200–400 ms). Most responsive, false-MORTO-prone on jittery WiFi. | |
| Loose (~5× / ~1–2s+) | Few false positives, but a frozen tile can read "live" up to ~2 s. | |

**User's choice:** ~2–3× publish interval
**Notes:** On-air emphasis (red border + badge + "ON AIR: CAM X" banner) was not re-asked — already roadmap-specified and locked.

---

## Layout scope now vs P9

### Composition

| Option | Description | Selected |
|--------|-------------|----------|
| Grid on top, controls below | Multiview is primary; forms scroll beneath; cameras + banner in first viewport. Minimal restructure. | ✓ |
| Controls on top, grid below | Keeps page intact, appends grid; buries the cameras. | |
| Side-by-side columns | Two-column landscape; more layout work, arguably Phase 9 restyle territory. | |

**User's choice:** Grid on top, controls below

### Polish scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal responsive grid only | CSS-Grid auto-fit + LIVE/dead marking; tiles display-only (text override stays); full tablet restyle → Phase 9. | ✓ |
| Grid + opportunistic touch polish | Do the grid AND start enlarging touch targets / tidying the form now. Bleeds Phase 9 UXT-01 scope. | |

**User's choice:** Minimal responsive grid only
**Notes:** Keeps the phase boundary crisp against MVW-01/02/03 + UXT-02; clickable tiles + full restyle deferred to Phase 9.

---

## Threat re-eval posture

| Option | Description | Selected |
|--------|-------------|----------|
| Accept LAN boundary + mandate AP isolation | Written re-eval reaffirms v1.0's no-auth single-operator-LAN stance, adds the live-video exposure, mandates AP client-isolation + no internet bridge. No new code. | ✓ |
| Add a minimal in-code control now | Configurable bind host and/or optional shared-token / basic-auth gate on preview routes. Stronger, but adds code/config beyond the stated "written re-eval" and re-litigates the accepted posture. | |

**User's choice:** Accept LAN-as-trust-boundary + mandate AP client-isolation
**Notes:** Phase 7's `preview.enabled` already serves as the source-side off-switch (no JPEGs written → nothing to serve); no separate console-side kill-switch needed in Phase 8 (a live operator kill-switch is Phase 9 / UXT-03).

---

## Claude's Discretion

- Preview-route shape (`GET /preview/<cam>.jpg` whitelisted `send_file` + `GET /preview` `read_preview`), camera-id whitelist source, 404 behavior.
- Cache-bust mechanism (in-sidecar `gen`/`tick` token vs `Date.now()`).
- Freshness source for the stale window (preview `gen`/`tick` field vs served JPEG mtime); the ~2–3× window itself is locked.
- `Image()` preload-swap browser refresh cadence (bounded by publish fps).
- Where the `threaded=True`/Waitress entrypoint logic lives (import kept inside the entrypoint to preserve the lazy boundary).
- Threat re-eval doc location (existing threat-model doc vs new `docs/` file).
- The exact hard ceiling value (≤ 5–8 Mbps) and the computed-bitrate formula (anchor on research budget).

## Deferred Ideas

- Clickable-tile informed override — Phase 9 (MVW-04).
- Explainability render: score bars (WHY-02), plain-Italian reason (WHY-01), dog-lock bbox overlay (WHY-03), "auto wants vs aired" hint (WHY-04), switch-history strip (MVW-05) — Phase 9. Data already in `preview.json`.
- Live client-side score-overlay preview (SCV-01) — Phase 9.
- Full tablet-first restyle (UXT-01) — Phase 9.
- Long-run hygiene: soak/no-leak, sleep/wake resume, deep staleness overlay, live operator preview kill-switch (UXT-03) — Phase 9.
- Runtime-adaptive bandwidth throttle — declined for Phase 8; revisit only if real-WiFi UAT shows the static budget insufficient.
- Synthetic network-contention harness — declined; real validation is a hardware-milestone carry-forward.
- MJPEG / WebSocket transport — evidence-gated fallback only.
- In-code auth / configurable bind / shared-token gate — declined for v1.1; revisit only if the deployment stops being a dedicated single-operator LAN.
