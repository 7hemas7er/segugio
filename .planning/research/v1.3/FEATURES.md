# Feature Research — v1.3 Gestione Punteggi Avanzata

**Domain:** Structured score ENTRY + auto-calc + validation for disc-dog & agility competitions (display/broadcast, NOT CV adjudication)
**Researched:** 2026-06-21
**Confidence:** HIGH (scoring formulas) / MEDIUM (cross-federation completeness — agility fault values verified for AKC; FCI verified for structure, exact pole-fault number is community/secondary-sourced)

---

## Scope frame (read first)

This milestone builds a **richer manual score-ENTRY tool** that auto-calculates totals, validates input, and publishes the single on-air score. It does **not** judge anything via computer vision. Every formula below is something a **human judge/operator types in or selects**; Segugio only does the **arithmetic, validation, and rendering**.

The single most important domain finding for the roadmap: **every number in these rules varies by federation.** Zone distances, zone point values, mid-air bonus size, time limits, number of throws, freestyle category names/counts/scales, agility fault values, and even the *scoring model itself* (agility = "count up faults, lowest wins" vs. "start at 100, deduct") all differ. Therefore the entry tool must be **config-driven (a YAML "scoring profile" per discipline/federation)**, not hardcoded to one ruleset. This matches the existing v1 pattern: disciplines are already a pydantic *discriminated union* (CFG-03), and field-sets already swap by discipline (SCR-01..04). v1.3 extends that with a per-discipline **scoring profile** that carries the federation-specific tables.

---

## Domain reference: how scoring actually works

### (1) DISC DOG — Toss & Fetch / Distance & Accuracy (D/A)

A timed round (almost universally **60 seconds, one disc**). The handler throws repeatedly; each **successful catch** scores points based on the **distance zone** the dog is in at the catch, plus an optional **mid-air bonus**. The round total is the **sum of per-throw scores**. This is the canonical "multi-throw with running total" the milestone calls out.

**Per-throw score = zone_points(distance) + midair_bonus(if all-4-paws-off-ground)**
**Round total = Σ per-throw scores** over the 60 s window.

Federation zone tables differ substantially — concrete examples:

| Federation | Units | Zone bands → points | Mid-air bonus | Time / discs | Notes |
|---|---|---|---|---|---|
| **UFO** (Throw & Catch) | meters | 0–15 m = **0**; 15–25 = **1**; 25–35 = **2**; 35–50 = **3** | **+1** (bonus landing zone: half-circle r=5 m on the 35 m line, beyond 35 m) → effectively a 4-pt completion | 60 s, 1 disc | Zone set by **rear-most paw** fully on/over the line. |
| **USDDN** (Throw & Catch) | yards | 10 yd = **1**; 20 = **2**; 30 = **3**; 40 = **4** (zone starts on the line, runs to next line) | **+0.5** (all four paws off ground); max per throw **4.5** | 60 s, 1 disc | Scored where **trailing paw** lands; "on the line" = next (higher) zone. |
| **Skyhoundz** (Distance/Accuracy) | yards (m equiv) | <10 yd = 0; 10–20 = **1**; 20–30 = **2**; 30–40 = **3**; 40–50 End Zone = **5** | **+0.5** (all paws off, obvious upward jump, land in zone) | 60 s, 1 disc | All paws must land **within** a scoring zone. Note the non-linear jump to 5 in the end zone. |
| **UpDog** (e.g. Throw N Go / Boom) | yards | 0–10 = **1**; 10–20 = **3**; 20–30 = **4**; 30–40 = **5**; 40–50 = **6** | varies by game (some games double/"rack") | 60 s, 1–4 discs depending on game | Some games auto-"Boom" (bank) at the top zone; sequences can run 1,2,2,5,10,20,25,35. Very different model — treat as its own profile. |

**Config-driven implications:**
- Zone boundaries are an **ordered list of (max_distance, points)** — *not* a fixed 4-row table. UFO has a 0-point near zone; Skyhoundz jumps to 5; UpDog has 5 bands starting at 1.
- Units differ (**meters vs yards**) — store the unit in the profile; never assume.
- Mid-air bonus is a **flat add per qualifying catch** but the *value differs* (+0.5 USDDN/Skyhoundz, +1/bonus-zone UFO) and some federations gate it on a geometric bonus zone.
- "Which paw decides the zone" (rear-most/trailing) is a **judging** rule, not a math rule — irrelevant to the entry tool *except* it tells us the judge enters one zone per catch (operator picks the zone; tool doesn't infer distance).
- Time limit and disc count are profile constants.

### (2) DISC DOG — Freestyle

A choreographed routine (typically ~90–120 s) scored on **multiple subjective criteria/categories**, each on a fixed scale, **summed** into a routine total. Multi-judge is common, with a defined **combination rule** (sum, average, or drop-high/low). Federations differ in category **names, count, scale, and judge math**:

| Federation | Categories | Scale per category | Combine | Judges | Max |
|---|---|---|---|---|---|
| **Skyhoundz** (PAWS) | **P**resentation, **A**thleticism, **W**ow! Factor, **S**uccess (4) | 1–10, **0.25 increments** | sum of 4 | (per judge) | 40 / judge |
| **UFO** | Drive & Athleticism, Ingenuity, Sequences & Flow, Comprehensive (4) | 1–10, **0.1 increments** | sum of 4 | mixed: one judge per category; **Comprehensive scored by 3 judges, drop high+low**, keep middle | 40 |
| **USDDN** | Canine Element (4 sub-elements ×2.50 = 10) + Player + Team elements | sub-scales to **10 per element**, hundredths | sum across elements/judges | multiple specialist judges (Dog judge, Player/Team judges) | 40 |

**Routine total = Σ category sub-scores**, with **multi-judge combination = profile-defined** (sum across category-judges, OR average of N judges, OR drop-high/low like UFO Comprehensive).

**Config-driven implications:**
- Categories are a **list of (name, min, max, increment)** — count is 4 today but must not be hardcoded; USDDN effectively has sub-elements summing to per-element caps.
- Scale increment matters for validation (0.25 vs 0.1 vs 0.01) — store it; validate input snaps to it.
- **Multi-judge combination is its own config enum**: `sum`, `average`, `drop_high_low`, or per-category judge assignment. UFO's "3 judges on Comprehensive, drop high+low" is the awkward case — design the combiner to support per-category judge sets even if v1.3 ships only the simple `sum`/`average` path.
- For the **on-air overlay**, only the *final combined total* (and maybe per-category breakdown) is published — keep the publish payload simple.

### (3) AGILITY

A single timed run. The result combines **course faults** (judge-called errors) and **time faults** (seconds over the Standard Course Time), with **eliminations** zeroing the run. **Two distinct scoring models exist** and they are *not* interchangeable:

**Model A — International / FCI ("count up", lowest wins):**
- **Course faults**: each fault = **5** (knocked/displaced pole, refusal, etc.). A displaced pole is a fault even if it doesn't fully fall.
- **Time faults**: **1 fault per second** (and fraction) over SCT.
- **Total faults = course faults + time faults.** Lower is better; **0 faults = clean run.**
- **Placement**: rank by **total faults ascending, then by run time ascending** (fastest clean wins).
- **Elimination (E)**: **3 refusals**, wrong course, exceeding **Maximum Course Time (MCT)**, taking obstacles out of order, etc. → no result/score.

**Model B — AKC ("start at 100, deduct"):**
- Run starts at **100**; deductions: **refusal = 5, wrong course = 5, table fault = 5**; **knocked bar = "Failure" (0 for that obstacle)**.
- **Time faults per second over SCT vary by class**: Novice **1**/sec, Standard/Open ~**2**/sec, Excellent A **3**/sec, Excellent B **no faults allowed**.
- **Qualifying** = score ≥ **85** (Excellent B requires a perfect **100**, clean).
- Too many refusals (>2)/wrong courses/table faults = **non-qualifying (NQ)** rather than a "5-fault" deduction.

**Standard Course Time (SCT)** is derived identically in spirit across federations: **SCT = course_length ÷ required_speed (m/s or yd/s)**. Example: 150 m at 3 m/s → 50 s. Required speed depends on level/jump-height/judge. **Maximum Course Time (MCT)** is a separate, longer cap; exceeding it = elimination.

**Result = f(course_faults, time_faults, elimination_flag)** where:
- **FCI**: `total_faults = course_faults + max(0, ceil/precise(run_time − SCT))`; `E` overrides to no-score.
- **AKC**: `score = 100 − course_deductions − time_faults`; `E`/excess → NQ.

**Config-driven implications (agility is the biggest config surface):**
- The **scoring model itself** (`count_up` vs `deduct_from_100`) is a profile flag — this changes the auto-calc formula and the "good direction" (low vs high).
- **Per-fault values** (bar, refusal, table, missed contact, wrong course) are a config table; AKC treats a bar as obstacle-failure (0), FCI as a flat 5.
- **Time-fault rate** is config (and in AKC depends on class — so the profile may carry a small class→rate map).
- **SCT/MCT**: the tool should let the operator **enter SCT and run time** (or enter SCT + the dog's time) and **auto-compute time faults**; computing SCT from course length/speed is optional convenience (the operator usually already has the judge's SCT).
- **Elimination** is a first-class state: a single checkbox/flag that overrides the numeric total (display "E"/"ELIM" on the overlay, not a number).
- **Time format**: runs are mm:ss.hundredths; the existing form already validates mm:ss — extend to hundredths for agility.

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| **Auto-calc round total = Σ per-throw zone points (+bonus)** for disc T&F/D/A | The whole point of "advanced" entry; manual summing is error-prone live | MEDIUM | Zone table + bonus value come from the **scoring profile**, not code. |
| **Multi-throw / running total UI** (add throw → pick zone → running sum) | T&F is inherently N throws in 60 s; the milestone names it explicitly | MEDIUM | List of throws, each = `{zone, midair:bool}`; show running total + throw count. Allow delete/edit of a throw (judge correction). |
| **Auto-calc agility result** (course faults + time faults, or 100-deduct) | Operators won't hand-compute time faults from SCT live | MEDIUM | Branch on profile `scoring_model`. Enter SCT + run time → time faults auto. |
| **Per-discipline validation** (ranges, required fields, time format, increment snapping) | Garbage on a broadcast overlay is worse than no overlay | MEDIUM | Validate zone ∈ profile zones; freestyle category ∈ [min,max] on its increment; time mm:ss(.cc); faults ≥0. Clear error messages (lesson: fail-fast, like CFG-01). |
| **Freestyle multi-criteria sum** (N categories on a scale → total) | Standard across all freestyle federations | MEDIUM | Categories from profile; sum (default) into total. |
| **Single on-air score publish unchanged** (`/overlay`, `overlay.txt`, `score.json`) | Must not regress the v1.2 broadcast pipeline | LOW | Publish-and-render invariant; only the *content* gets richer. |
| **Shared single renderer** (dedicated page + console modal = one component) | Direct lesson SCV-02: one renderer → no drift | MEDIUM | Same form component mounted in two hosts; do **not** fork the markup. |
| **Discipline selector swaps field-set + profile** | Already exists for 3 disciplines; must carry the new profile | LOW | Extends existing discriminated-union pattern (CFG-03). |
| **Elimination / DNF flag for agility** | Eliminations are common and must show as "E", not a number | LOW | Boolean that overrides numeric output on the overlay. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| **Config-driven scoring profiles (YAML per federation)** | One tool covers UFO/USDDN/Skyhoundz/FCI/AKC without code edits — rare in ad-hoc overlay tools | MEDIUM | The central design bet. Ships with a couple of vetted built-in profiles; users add their own. |
| **Live running total + best-throw highlight during T&F** | Broadcast-grade: audience sees the score climb each catch | LOW–MEDIUM | Pure render of the throw list already entered. |
| **Per-category freestyle breakdown on overlay** | Shows *why* a freestyle total is what it is (athleticism/difficulty/etc.) | LOW | Optional richer lower-third; final total is the default. |
| **Multi-judge combination (sum / average / drop-high-low)** | Matches real multi-judge panels (UFO Comprehensive) | MEDIUM | Ship `sum`+`average` in v1.3; design the combiner to allow `drop_high_low` later. |
| **SCT → time-fault auto-derivation** (enter run time, get faults) | Removes the most error-prone live mental math in agility | LOW | `time_faults = rate × max(0, run_time − SCT)`. |
| **"Pick zone" buttons matched to the active profile's bands** | Fast, fat-finger-proof entry for a 60 s round | MEDIUM | Buttons generated from the profile zone list. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| **CV auto-scoring** (detect catch distance / call faults from video) | "The system already tracks the dog — let it judge!" | Officiating liability; rules need rear-paw/line precision Segugio can't guarantee; out of scope per PROJECT.md ("SHOWS, does NOT judge") | Keep human judge → manual entry. Hard scope line. |
| **Roster / standings / leaderboard across competitors** | "Show the whole class ranking" | Explicit milestone scope boundary (single on-air score only); pulls in heat management, ties, run order | Defer to a future milestone; v1.3 publishes only the current run. |
| **One hardcoded ruleset** (just code USDDN/FCI) | Faster to build | Breaks the moment a different federation/club uses it; every number varies | Config-driven profiles (the differentiator). |
| **Editing the on-air number directly (free-text override)** | "Just let me type the total" | Defeats validation/auto-calc; risks an impossible score airing | Keep auto-calc as source of truth; allow per-throw/per-field correction, recompute total. |
| **Computing SCT from course length automatically as the primary path** | "Enter the course, get SCT" | Required speed is judge/level/height-dependent and frequently posted directly; auto-SCT invites wrong numbers | Let operator **enter the judge's SCT** (auto-compute optional convenience). |
| **Server-side per-keystroke recompute on the director** | "Live totals" | Would break crash-isolation / starve `/command` (UXT-02, v1.2 poll-storm lesson) | All calc client-side in the shared renderer; publish only the result over the file channel. |

---

## Feature Dependencies

```
[Scoring profile (YAML per discipline/federation)]
    └──required-by──> [Auto-calc total]  (zone table, fault values, scale)
    └──required-by──> [Per-discipline validation]  (ranges, increments, units)
    └──required-by──> [Multi-throw zone buttons]  (bands)
    └──required-by──> [Freestyle category list]  (names/scales)

[Shared single renderer component]
    └──required-by──> [Dedicated page]  AND  [Console modal]   (one source, no drift — SCV-02)

[Multi-throw running total]
    └──requires──> [Auto-calc total]
    └──enhances──> [On-air publish] (richer content, same channel)

[Multi-judge combination] ──enhances──> [Freestyle multi-criteria sum]

[Elimination flag] ──overrides──> [Agility auto-calc result]

[CV auto-scoring] ──CONFLICTS──> [Project scope: "shows, does not judge"]   (do not build)
[Roster/standings] ──CONFLICTS──> [Milestone scope: single on-air score]    (defer)
```

### Dependency Notes
- **Scoring profile is the keystone:** auto-calc, validation, and the entry UI all read from it. Build/define the profile schema first (extends the existing pydantic discriminated-union config), then the calculators, then the UI.
- **Shared renderer requires the one-component discipline:** the v1.2/SCV-02 lesson is binding — the dedicated page and the console modal must mount the *same* component, never a copy.
- **Multi-throw requires auto-calc** but is otherwise a thin list UI over per-throw `{zone, midair}` records.
- **Publish stays on the file channel** — no new dependency edge to the director; crash-isolation constraint is a hard non-dependency.

---

## MVP Definition

### Launch With (v1.3)
- [ ] **Scoring profile schema** (per-discipline/federation: units, zone bands, bonus value, time limit, freestyle categories+scale, agility scoring_model + fault values + time-fault rate) — keystone, everything reads it.
- [ ] **Disc T&F/D&A multi-throw entry + running total** (add/edit/delete throw, zone pick, mid-air toggle, Σ auto) — the headline feature.
- [ ] **Freestyle multi-criteria entry + sum** (N categories from profile, increment-validated) — table stakes.
- [ ] **Agility auto-calc** (SCT + run time → time faults; course faults; `count_up` *and* `deduct_from_100` models; elimination flag) — table stakes, biggest config branch.
- [ ] **Per-discipline validation** with clear messages (ranges, required, time mm:ss.cc, increment snap) — broadcast-integrity guard.
- [ ] **Shared single renderer** mounted in dedicated page + console modal — SCV-02 lesson.
- [ ] **Publish current score** to `/overlay`, `overlay.txt`, `score.json` unchanged — preserve v1.2 pipeline.

### Add After Validation (v1.x)
- [ ] **Multi-judge combination** beyond `sum`: `average`, and per-category judge sets / `drop_high_low` (UFO Comprehensive) — once single-judge entry is proven live.
- [ ] **Per-category freestyle breakdown on the overlay** — once the simple total reads well on air.
- [ ] **Auto-SCT from course length × required speed** as an optional convenience — once operators ask.
- [ ] **More built-in federation profiles** (ship 1–2 vetted; add as users supply rulesets).

### Future Consideration (v2+)
- [ ] **Roster / standings / class ranking** — explicit out-of-scope now; large surface (heats, ties, run order).
- [ ] **External scoring-system import (API)** — already out-of-scope for v1; only if a federation exposes a feed.
- [ ] **CV-assisted suggestions** (never auto-adjudication) — only if ever revisited; conflicts with current scope.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| Scoring profile schema (config-driven) | HIGH | MEDIUM | P1 |
| Disc T&F multi-throw + running total | HIGH | MEDIUM | P1 |
| Agility auto-calc (both models) + elim flag | HIGH | MEDIUM | P1 |
| Freestyle multi-criteria sum | HIGH | MEDIUM | P1 |
| Per-discipline validation | HIGH | MEDIUM | P1 |
| Shared single renderer (page + modal) | HIGH | MEDIUM | P1 |
| Publish unchanged to overlay/file | HIGH | LOW | P1 |
| Multi-judge average / drop-high-low | MEDIUM | MEDIUM | P2 |
| Per-category overlay breakdown | MEDIUM | LOW | P2 |
| Auto-SCT from course length | LOW | LOW | P3 |
| Roster / standings | (out of scope) | HIGH | — defer |
| CV auto-scoring | (anti-feature) | HIGH | — never |

## Competitor / Reference Feature Analysis

| Capability | UFO / USDDN / Skyhoundz (rulebooks) | UpDog / AKC | Our Approach |
|---|---|---|---|
| Disc zone scoring | Fixed per-federation zone tables, mid-air bonus | UpDog: different 5-band table, "Boom" banking | One **config zone-list + bonus value** per profile; ship UFO/USDDN/Skyhoundz examples. |
| Freestyle judging | 4 categories, 1–10, sum to 40; multi-judge | varies | Config category list + scale; `sum` v1.3, `average`/`drop_high_low` later. |
| Agility scoring | FCI: count-up faults, 5/fault, 1/sec, lowest wins | AKC: 100-deduct, ≥85 qualifies, rate by class | Profile `scoring_model` flag branches the formula; configurable fault values + time-fault rate. |
| Officiating | Human judges | Human judges | **Human enters; Segugio calculates + validates + displays only** (hard scope line). |

## Sources

- **UFO World Cup — Throw & Catch Rules** (zones 0/1/2/3 by meter band, 5 m bonus half-circle, 60 s/1 disc, rear-paw rule): https://www.ufoworldcup.org/content/Rules/TnC.php — HIGH
- **UFO World Cup — Freestyle Judging Guidelines** (4 categories 1–10 ×0.1, 40 max, Comprehensive 3-judges drop-high/low, catch-ratio tiebreaker): https://www.ufoworldcup.org/content/Rules/Freestyle.php — HIGH
- **USDDN 2024 Judging Handbook** (Throw&Catch yard zones 1–4 + 0.5 mid-air, max 4.5/throw; freestyle 10-scale, canine 4 sub-elements ×2.50, 40 max, multi-judge): https://usddn.com/wp-content/uploads/2024/10/USDDN-2024-judging-handbook-v6.pdf — HIGH (text partially extractable; zone/scale numbers cross-confirmed via search snippets)
- **Skyhoundz — A Primer on Judging Criteria** (PAWS: Presentation/Athleticism/Wow!/Success, 1–10 ×0.25): https://skyhoundz.com/a-primer-on-skyhoundz-judging-criteria/ — HIGH
- **Skyhoundz — Distance/Accuracy** (zones 1/2/3/5 by 10-yd band, +0.5 mid-air, 60 s/1 disc): https://skyhoundz.com/distance-accuracy-and-pairs/ — HIGH
- **UpDog Challenge — game rules** (zone bands 1/3/4/5/6, "Boom" banking, 60 s, multi-disc games): https://updogchallenge.com/games-overview/ , https://updogchallenge.com/general-rules/ — MEDIUM
- **FCI Agility Regulations** (faults in units of 5; time fault per second over SCT; SCT = length/speed; 3 refusals = E; exceed MCT = E): https://www.fci.be/medias/AGI-REG-en-22280.pdf (structure HIGH; exact pole=5 cross-sourced) — MEDIUM/HIGH
- **AKC Regulations for Agility Trials** (100-base deduct; refusal/wrong-course/table = 5; knocked bar = obstacle failure; time-fault rate by class 1/2/3; ≥85 qualifies, Excellent B = 100): https://images.akc.org/pdf/rulebooks/REAGIL.pdf — HIGH (numbers via AKC-derived secondary, structure HIGH)
- **Dog agility — Wikipedia** (SCT = course length ÷ required speed worked example; faults-based ranking, faults then time): https://en.wikipedia.org/wiki/Dog_agility — MEDIUM
- **SpiritDog Training — How is dog agility scored** (AKC time-fault rates by class; bar=failure; refusal/table/wrong-course=5): https://spiritdogtraining.com/agility/how-is-dog-agility-scored/ — MEDIUM

---
*Feature research for: structured disc-dog & agility score ENTRY/DISPLAY (config-driven, no CV adjudication)*
*Researched: 2026-06-21*
