# Phase 15: Pure Calc + Validation Core & Scoring Profiles - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21
**Phase:** 15-pure-calc-validation-core-scoring-profiles
**Areas discussed:** Default rule tables, Built-in profile breadth, Freestyle judging scope, Agility calc specifics

---

## Default rule tables (REQ blocker)

### Disc dog Toss & Fetch — zone table + bonus
| Option | Description | Selected |
|--------|-------------|----------|
| UFO | Meters 0/1/2/3, +1 bonus zone, 60s | |
| USDDN | Yards 1/2/3/4, +0.5 mid-air, 60s | |
| Skyhoundz | Yards 1/2/3/5 end-zone, +0.5, 60s | |
| **CSEN 2026 (user-supplied URL)** | Meters 9/18/27/36→1/2/3/4, two +0.5 bonuses (mid-air + central corridor), 90s, best-5-of-N (max 25) | ✓ |

**User's choice:** Provided two Italian rulebook URLs instead of the international options —
`discdogcsen.it/.../RegolamentoDiscDogCsen2026.pdf` and
`fidasc.it/.../discdog-2025/file.html`. CSEN extracted and pinned as the default.
**Notes:** The user organizes/films Italian disc-dog events, so the relevant rules are the Italian
federations (CSEN, FIDASC), not the US/international tables. CSEN PDF was fully extracted via
`pdftotext`; FIDASC endpoint returned HTTP 503 and remains to be extracted in planning.

### Freestyle — categories + scale
| Option | Description | Selected |
|--------|-------------|----------|
| UFO | 4 cat ×0.1, sum 40 | |
| Skyhoundz PAWS | 4 cat ×0.25, sum 40 | |
| USDDN | Canine sub-elements + Player + Team | |
| **CSEN (same rulebook)** | 4 cat (Team Elements, Dog, Player, Catch Ratio) ×0.01, 0–10, sum 40 | ✓ |

**User's choice:** "stesse pagine web" — same CSEN/FIDASC rulebooks.
**Notes:** CSEN freestyle = 4 judged values 0–10 to two decimals, summed; Catch Ratio is itself a
scored category (catches/throws, min-18 basis).

### Agility — scoring model
| Option | Description | Selected |
|--------|-------------|----------|
| FCI count-up | 5/fault, 1/sec, lowest wins, E on 3 refusals/over-MCT | (engine default) |
| AKC deduct-from-100 | 100-base, ≥85 qualifies, rate by class | (engine supports) |

**User's choice:** "area non di interesse per ora" (not an area of interest right now).
**Notes:** Resolved under the Agility scope question below — engine built, real profile deferred.

---

## Built-in profile breadth

| Option | Description | Selected |
|--------|-------------|----------|
| CSEN default + FIDASC example | Two real federations; proves config-swap on real alternate rules | ✓ |
| CSEN only | Single default; swap proven by a synthetic test profile | |

**User's choice:** CSEN default + FIDASC example.
**Notes:** FIDASC numbers must be sourced during planning (automated fetch blocked, HTTP 503).

---

## Freestyle judging scope

| Option | Description | Selected |
|--------|-------------|----------|
| 4-category sum only | Total = sum of the 4 values (0–10, hundredths, max 40); penalties as manual adjustment | ✓ |
| Sum + penalty modeling | Also auto-model nature break / excess disc / safety deductions | |

**User's choice:** 4-category sum only.
**Notes:** Keeps the freestyle validation surface small for v1.3; penalties enter as a single manual
adjustment field rather than modeled rules.

---

## Agility calc specifics / scope

| Option | Description | Selected |
|--------|-------------|----------|
| Build engine, defer profile | Config-driven count-up + deduct-from-100, time-faults, elimination; ship a generic FCI-style example, pin real Italian numbers later | ✓ |
| Defer agility entirely | Drop the agility branch; re-scope SCC-04 to a later milestone | |
| Full agility now | Pin a real Italian agility ruleset and build fully | |

**User's choice:** Build engine, defer profile.
**Notes:** Satisfies SCC-04 (both models supported, config-driven) without a roadmap re-scope and
without forcing the user to source agility numbers they don't need yet. Elimination → "E" sentinel;
time-fault rounding via ceil at 1/sec for the count-up model; agility time format mm:ss.cc.

---

## Claude's Discretion

- `decimal.Decimal` arithmetic throughout, quantized to the profile increment (no float drift).
- Profile injected as a plain stdlib object (pydantic validation in `segugio.config`, fail-fast at
  load) so `score_calc` never imports config models — mirrors the `cam_ids`/`overlay_cfg` pattern.
- `validate()` → per-field errors; `compute()` runs only after validate passes.
- Time parsing via strict `mm:ss(.cc)` regex.
- Zone bands modeled as an ordered `(band, points)` list + a config bonus list, not a fixed table.

## Deferred Ideas

- Real Italian agility rule tables (until an agility event is run).
- Freestyle penalty auto-modeling (nature break / excess disc / safety ranges).
- Multi-judge combination beyond `sum` (`average`, `drop_high_low`).
- Per-category freestyle overlay breakdown; auto-SCT from course length; more federation profiles.
- Combined division (freestyle×1.5 + best distance) and roster/standings (cross-run, out of scope).
