---
id: harden-overlay-json-echo-length-cap
status: pending
created: 2026-06-27
source: .planning/phases/16-shared-entry-component-dedicated-page-server-authoritative-p/16-SECURITY.md
priority: low
tags: [security, hardening, overlay, input-validation]
---

# General echoed-value / request-body length cap on POST /score

Accepted residual **AR-16-01** from the Phase 16 adversarial security audit (2026-06-27), deferred
to a future hardening pass. Below `block_on: high`: it is **not** broadcast-aired and does **not**
crash; it is the pre-existing verbatim-echo property on the **accepted no-auth LAN** (T-05-05-04).

## The residual

`GET /overlay-json` returns `fields` verbatim (the Phase-10 data contract), and
`_parse_structured_inputs` (`src/segugio/ui/app.py`) echoes display-only fields unchanged
(Phase-18 `cane`/`conduttore`/`giudici`, arbitrary throw subkeys). So an oversized field value —
a numeric like `"0." + "0"*5000 + "1"` (1 sig digit, tiny magnitude → slips the numeric
`is_finite`/magnitude/precision bounds), or a 100 KB `cane` string — is written into `score.json`
and served verbatim in the `/overlay-json` JSON payload, growing both unboundedly.

**Not a broadcast airing:** `render_overlay_text._clean` caps every `overlay.txt` field at 64 chars;
the graphical `/overlay` (`overlay-render.js cleanField`) caps displayed cells at 64 and does not
read these raw keys. The visible on-air total is always bounded and sensible. No crash (204/400).

## Why a general cap (not another numeric bound)

The numeric validation gate is already fully closed (non-finite / magnitude / precision bounds,
commits `d797d98`/`f26bfa8`/`8642d39`). This residual is reachable via **many** fields including the
already-accepted display-only free-text, so the proper remedy is **one general cap**, not per-field
numeric metadata checks.

## Suggested fix

- A length cap on echoed field values in `_parse_structured_inputs` (drop or 400 any field value
  whose `len(str(v))` exceeds a sane bound, e.g. 256 chars — covers numeric AND free-text in one
  place), **and/or**
- Set Flask `MAX_CONTENT_LENGTH` on the console app to bound the whole request body.
- Add a regression asserting a `>N`-char field value is rejected/truncated and never reaches
  `score.json` / `/overlay-json`.

## Scope note

Revisit priority if/when auth or WAN exposure is added (the v1 acceptance rests on the dedicated
no-auth LAN trust boundary). Until then this is low-priority robustness, not a live broadcast risk.
