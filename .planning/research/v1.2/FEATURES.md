# Feature Research

**Domain:** Animated broadcast score overlay (lower-third) for live dog sports — disc dog (Toss & Fetch, Freestyle) + agility — rendered as an OBS browser-source over a camera feed
**Researched:** 2026-06-14
**Confidence:** HIGH (dog-sports rules + broadcast lower-third conventions cross-corroborated across multiple sources; data-model dependencies read directly from the codebase)

---

## Context that shapes every feature below

Three constraints from the existing system bound the entire feature set. They are not negotiable and they pre-decide what is "free" vs "expensive":

1. **SCR-04 — display-only, never adjudicate.** The judge is authoritative. The overlay shows the operator's typed values *verbatim*. It never sums `prese` into `totale`, never derives faults, never computes a result. An overlay that disagrees with the judge is worse than no overlay. This makes "automatic scoring/CV-of-faults" the #1 anti-feature — it is OUT, hard.
2. **Crash-isolation — the console imports only `Flask + segugio.opcomm`, never the orchestrator/director.** v1.2 is *publish-and-render* over the existing `opcomm` channel, exactly like the v1.1 preview channel. No feature may add compute to the director's AI tick. The data (`ScoreDoc`, `RunState`) already crosses the channel; the overlay only renders it.
3. **The core value is "the right camera at the right moment."** The overlay is secondary. Any feature that distracts from the dog, covers the action area of the field, or competes for the director's GPU/CPU is an anti-feature by definition.

**Data model already present (no new channel work needed for these):**
- `ScoreDoc(discipline: Discipline, fields: dict)` — `Discipline` is a closed enum: `disc_tf`, `disc_freestyle`, `agility`. `fields` is a free-form `{label: value}` map the UI posts.
- Field sets confirmed in `ui/score_render.py`: **disc T&F** → `prese` / `zona` / `totale`; **disc freestyle** → `nome` / `timer`; **agility** → `tempo` / `sct` (alias `SCT`) / `faults`.
- `RunState(action, just_started, just_stopped)` — `action` is `"start"`/`"stop"`, `stopped` property, one-tick `just_started`/`just_stopped` edges. **There is NO timestamp field today** — the timer is operator-typed text.
- `DirectorStatus(live_cam, reason, alive)` and `PreviewDoc(...)` exist for the console's "why"/freshness work (v1.1).

**The single most important new-data finding (flag for roadmap):**
A self-counting client-side run timer needs a wall-clock origin that does not exist yet. The roadmap's `run_started_at` (epoch ms) is a **NEW field on `RunState`** (or a sibling record on the channel). Everything else in the table-stakes set is pure presentation over data that already crosses `opcomm`. This is the one feature with a real data-model dependency.

---

## Domain primer (so feature decisions are grounded)

**Per-discipline timing — they genuinely differ, do not unify them:**

| Discipline | Clock semantics | What the overlay timer should do |
|------------|-----------------|----------------------------------|
| **Disc Toss & Fetch** | Fixed **60 s** round; make as many catches as possible. The clock is a **count-DOWN** to zero (announced "30 … 10 … 5-4-3-2-1-Time"). | Count **down from 60→0**. Score (`prese`/`zona`/`totale`) accumulates during the run. At 0 → freeze, signal "Tempo". |
| **Disc Freestyle** | Fixed routine window, **90 s or 2 min** depending on org (Skyhoundz 90 s; many use 2 min) — set to music. | Count **down** from the configured routine length (90 s / 120 s). It's about *time remaining in the routine*, not score; the score is judged later off-field, so freestyle's overlay is mostly **name + clock + branding**. |
| **Agility** | A **count-UP** of elapsed time, compared against the course's **Standard Course Time (SCT)**. Over SCT → 1 time-fault/sec (varies by class). Run ends when the dog finishes or is eliminated. | Count **up from 0**, show **elapsed `tempo` vs `SCT`**. The interesting broadcast moment is "are they under SCT?" — visually relate elapsed→SCT. Faults are judge-entered, displayed verbatim. |

So: **T&F and freestyle count DOWN; agility counts UP.** T&F's countdown is to a fixed 60 s; freestyle's to a configured length; agility's count-up has SCT as a reference, not a hard stop the timer enforces. This is a per-discipline branch in the timer logic, not a single mode.

**Broadcast lower-third anatomy (live sports convention):**
- Sits in the **title-safe lower band**: bottom edge ~5% up from frame edge (modern HD), within the inner 80% title-safe box; nothing important above the lower ~15-20% of frame. **The action (the dog on the field) lives in the upper/center — the overlay must never climb into it.**
- Visual hierarchy: the **clock/score is the most-glanced element** ("the most important element on screen"). Identity (competitor/dog name, event) is secondary. Branding/logo is tertiary.
- **Persistence & legibility:** strong contrast (text vs a semi-opaque plate, not text directly on grass), legible weight, on-screen long enough to read (3-6 s rule for transient graphics — but a score bug is persistent for the whole run).
- **Animation philosophy:** subtle. A clean fade/slide on enter/exit; a brief pulse when a value changes. The pro guidance is explicitly "a simple fade in and out is sometimes the best approach" and "disable unnecessary animations." Over-animation is an amateur tell and a distraction.
- **Transparency:** OBS browser-source is transparent by default — transparency comes from the page CSS (no opaque `background`). This is well-trodden; the overlay just needs a transparent body and the plate as its own element.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any of these and it doesn't feel like a "broadcast overlay" — it feels like the old text file with a font.

| Feature | Why Expected | Complexity | Notes / Data dependency |
|---------|--------------|------------|-------------------------|
| **Transparent OBS browser-source overlay** (`GET /overlay` HTML + `GET /overlay-json` data) served by the crash-isolated console | This *is* the milestone; replaces `overlay.txt`+text-source | MEDIUM | Pure presentation. Transparent body in CSS; OBS composites automatically. Two routes mirror the v1.1 preview pattern (HTML page polls/streams the JSON sidecar). |
| **Per-discipline lower-third layout** (disc T&F: Prese/Zona/Totale · freestyle: Nome+Timer · agility: Tempo/SCT/Faults) | The three disciplines show fundamentally different data; one layout can't fit all | MEDIUM | Pure presentation. `ScoreDoc.discipline` already selects the field set; `score_render.py` already proves the exact labels/aliases. Reuse that mapping (SCV-01 unification). |
| **Self-counting run timer** (counts on its own, client-side) | A broadcast clock must *tick*; an operator-typed static "Timer: 0:42" that never moves is the thing this milestone exists to kill | MEDIUM | **NEEDS NEW DATA: `run_started_at` (epoch ms) on the channel.** JS computes `now - run_started_at` each frame; zero director compute. Only ticks while `RunState.running`. See per-discipline up/down branch below. |
| **Per-discipline timer direction** (T&F & freestyle count DOWN from 60s/90-120s; agility counts UP, shown vs SCT) | A count-up clock on a 60s T&F round is simply wrong to anyone who knows the sport | MEDIUM | Presentation logic over `run_started_at` + discipline + a configured round-length (T&F=60, freestyle=90/120 from config). Agility shows elapsed and the operator-typed `SCT` as a static reference. |
| **Show/hide tied to run start/stop** (animate in on `just_started`, out on `just_stopped`) | The overlay should appear when a run begins and clear when it ends — not linger on an empty field between competitors | LOW-MEDIUM | Pure presentation. `RunState.just_started`/`just_stopped` edges (and `action`/`stopped`) already exist and already drive overlay/timer reset per the records doc. |
| **Score-change pulse/flash** (brief highlight when a displayed value updates) | Standard broadcast feedback so a viewer notices "they scored" without watching the number every second | LOW | Pure presentation. Diff the incoming field value vs the last rendered one in JS → trigger a CSS pulse. No new data. |
| **Smooth enter/exit + value-change animation** (fade/slide, subtle) | "Animated" is in the milestone name; a hard cut-in reads as broken/amateur | LOW | Pure presentation, CSS transitions/keyframes. Keep it short and subtle (see anti-features). |
| **Verbatim value display, sanitized + length-bounded** | SCR-04 + the existing T-05-05-02 injection guard | LOW | Reuse `_clean`/`_MAX_FIELD_LEN` semantics from `score_render.py`. No arithmetic, ever. |
| **Legible compositing over live grass/sky** (semi-opaque plate, contrast, drop shadow) | A field is a noisy, bright, variable background; bare text vanishes | LOW | Pure presentation/CSS. This is what makes it "broadcast" vs the old flat text line. |
| **Robust degraded fallback: `overlay.txt` retained** | SCR-01 / live-robustness; if the browser-source dies the text source still shows the score | LOW | Already exists; v1.2 keeps writing it. Explicitly NOT removed. |

### Differentiators (Competitive Advantage)

Aligned with the product: a polished, hands-off broadcast look that a tiny club event normally can't afford. Not required for v1.2 to be "done," but high perceived value.

| Feature | Value Proposition | Complexity | Notes / Data dependency |
|---------|-------------------|------------|-------------------------|
| **Event + competitor/dog identity line** (event name + dog/handler name as a persistent identity row) | Makes it feel like a real televised event, not a debug HUD; freestyle especially is "name + clock + brand" | LOW | Freestyle already has `nome`. Event name is config/branding. T&F/agility currently have no name field — could surface from config or an optional `fields["nome"]` (no model change if carried in `fields`). |
| **Branding / logo + theme** (club/sponsor logo, color theme via config) | Sponsor visibility is a real driver for event organizers; one config swap re-skins | LOW-MEDIUM | Pure presentation; CSS variables + a logo asset path in config. Keep logo in the corner/plate, never over the field action. |
| **SCT-relative agility visual** (color/bar showing under vs over SCT as elapsed approaches it) | Turns a raw number into the dramatic broadcast question "will they make time?" | MEDIUM | Presentation over elapsed + operator-typed `SCT`. Still display-only: it *visualizes* the comparison, it does not *adjudicate* the result (no Q/NQ call). Keep the line between "showing elapsed vs a typed reference" and "judging" bright. |
| **T&F live tally feel** (per-catch pulse already covers it; a small "catches" counter that animates each `prese` increment) | The T&F drama is the rising count under a falling clock | LOW | Pure presentation; just the pulse + the verbatim `prese`/`totale`. No computation — the operator types the running totals. |
| **"Live/fresh" discipline carried to the overlay** (the overlay reflects only fresh state; never shows a stale frozen run) | Matches UXT-03's hard rule (a frozen frame is never "live"); a clock stuck at a stale value during a feed/console hiccup looks broken on-air | LOW-MEDIUM | The *timer* is self-driving from `run_started_at`, so it can't "freeze" the way a pushed value can — that's a feature. For score values, a staleness/gen token (like `PreviewDoc.gen`) lets the page detect a dead data source. Reuse the gen-age pattern from v1.1 rather than inventing one. |
| **Unified renderer (console preview == OBS overlay)** (SCV-01 simplification) | Kills the byte-exact Python↔JS mirror drift-guard; one HTML renderer feeds both the console preview and OBS | MEDIUM | Architectural win, not a user-facing feature, but it's an explicit v1.2 target and reduces a whole class of bugs. The console's score-preview becomes "load the same `/overlay`." |
| **Curated OBS scene collection** with the browser-source pre-wired into every CAM scene + layout/transitions + updated `docs/obs-setup.md` | Turns "configure 4 cameras and an overlay by hand" into an import-and-go; lowers the operator burden the whole product is about | MEDIUM | New `obs/segugio-scene-collection.json`. Out of the render path but a real differentiator for the "no operator" promise. |

### Anti-Features (Commonly Requested, Often Problematic)

Called out hard — these are the traps. The first one is a project-defining boundary.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Automatic scoring / adjudication** (CV counts catches, sums totals, derives faults, calls Q/NQ, decides under/over SCT) | "The system sees the dog — why type scores at all?" | **Violates SCR-04, the hardest line in the project.** The judge is authoritative; an overlay that disagrees is worse than none. Mid-air catch/fault judging is subjective and error-prone; a wrong on-air number is a credibility disaster and could affect a real competition. | Display the operator's typed values **verbatim**, always. Even the SCT-relative *visual* must only *show* a comparison of typed numbers, never *render a verdict*. |
| **Over-animation** (constant motion, particle effects, looping shimmer, dramatic transitions on every score tick, spinning logos) | "Make it look exciting / like a AAA esports broadcast" | Distracts from the dog (the core value); reads as amateur; the pro guidance is explicitly "disable unnecessary animations, a simple fade is often best"; heavy JS/CSS in a browser-source can also cost OBS CPU/GPU on the *same* machine. | Subtle, short fade/slide on enter-exit; a single brief pulse on value change; otherwise static. Motion only to convey a state change. |
| **Overlay that covers the action area** (full-width banner, top-center scorebar, large center-screen graphics, oversized lower-third that climbs past ~20% of frame height) | "Make the score big and prominent" | The dog is small, fast, and anywhere on the field; a tall/centered overlay hides the very subject the system works to keep framed. | Title-safe lower band only: bottom edge ~5% up, kept within the bottom ~15-20% of frame, inner 80% title-safe box. Never top-center, never over the field's center mass. |
| **Anything requiring director compute** (push every timer frame from the orchestrator, run the overlay render in the director process, server-side per-frame composition, a WebSocket fan-out off the director) | "Sync the clock perfectly to the AI tick" / "render it where the data is" | Breaks the crash-isolation guarantee and steals from the <300ms AI loop budget — the exact mistakes v1.1's preview design rejected (MJPEG/WebSocket-on-director were RESPINTI). | Self-counting client-side timer from a single `run_started_at` timestamp + `running` flag; the console (Flask + opcomm only) serves the page; zero per-frame director work. |
| **A perfectly frame-accurate / NTP-synced clock** | "Broadcast clocks must be exact to the frame" | This is a hobby/club auto-director, not a TV truck; chasing sub-frame sync adds huge complexity (clock-skew handling, drift correction) for value no viewer perceives. Glass-to-glass is already ~150-350ms. | `now - run_started_at` in the browser is accurate to well within human perception. Accept ~tens-of-ms; do not build clock-discipline machinery. |
| **Removing the `overlay.txt` text fallback** | "We have a nice graphical overlay now, delete the old thing" | Loses the SCR-01 robust degraded path; if the browser-source crashes/blanks on-air there's no score at all. | Keep writing `overlay.txt`; it stays as the always-works fallback source in OBS. |
| **Rich operator-authored content in the overlay** (free HTML, arbitrary long text, embedded images per run) | "Let the operator put notes/announcements on screen" | Injection surface (already mitigated for plain values), unbounded layout that breaks the lower-third, scope creep beyond scores | Keep the fixed per-discipline field schema; reuse the sanitize + length-bound guard. Announcements are out of scope. |
| **Multi-competitor leaderboard / standings on the live overlay** | "Show the running standings during a run" | Clutters the live lower-third, competes for space with the action, and standings are a results-page concern not a live-run concern | Keep the live overlay to the *current run only*. Standings/leaderboard belong elsewhere (the console already has a per-camera leaderboard for a different purpose). |

---

## Feature Dependencies

```
[Transparent OBS browser-source overlay (/overlay + /overlay-json)]
    └──requires──> [opcomm channel already carries ScoreDoc + RunState]   (exists)
    └──enables───> [Per-discipline lower-third layout]
                        └──requires──> [ScoreDoc.discipline field set]    (exists, score_render.py)

[Self-counting run timer]
    └──requires──> [NEW: run_started_at (epoch ms) on the channel]        (DOES NOT EXIST — new field)
    └──requires──> [RunState.running / action / just_started edges]       (exists)
    └──drives────> [Per-discipline timer direction (T&F/freestyle down · agility up)]
                        └──requires──> [configured round length: T&F 60 / freestyle 90|120]

[Show/hide tied to run start/stop]
    └──requires──> [RunState.just_started / just_stopped edges]           (exists)

[Score-change pulse]
    └──requires──> [client-side diff of last-vs-new field value]          (pure JS, no data)

[Unified renderer (SCV-01)]
    └──replaces──> [v1.1 byte-exact Python↔JS overlay mirror + drift-guard]
    └──enhances──> [Console score-preview] and [OBS overlay] simultaneously

[SCT-relative agility visual] ──enhances──> [Agility layout]
    (display-only; MUST NOT cross into adjudication — conflicts with SCR-04 if it renders a verdict)

[Curated OBS scene collection] ──wires-in──> [the browser-source] (deploy/packaging, off the render path)
```

### Dependency Notes

- **Self-counting timer requires `run_started_at`:** this is the *only* table-stakes feature that cannot be built on the current data model. Everything else renders data that already crosses `opcomm`. The roadmap must add `run_started_at` (and arguably the configured round length per discipline) to the channel — most naturally as a new field on `RunState` or a sibling overlay record. **Flag this as the one data-model change of the milestone.**
- **Per-discipline layout requires the existing discipline field set:** reuse `score_render.py`'s mapping/aliases (`sct`/`SCT`, etc.) verbatim — duplicating those labels in a second place is exactly the drift SCV-01 unification kills.
- **Timer direction depends on a configured round length:** T&F=60s is effectively fixed by the sport, but freestyle is org-dependent (90s vs 120s), so the round length must be config-driven, not hardcoded. Agility's "up vs SCT" needs no round length (SCT is the operator-typed reference).
- **SCT-relative visual conflicts with SCR-04 if over-built:** it may *show* elapsed-vs-SCT; it may NOT *declare* qualified/over-time. Keep it on the display side of the line.
- **Unified renderer is a prerequisite simplification, not a feature:** doing it first removes the Python↔JS mirror, so the console preview and OBS overlay can't drift — build the renderer once, point both at it.

---

## MVP Definition

### Launch With (v1.2)

The minimum that makes this a real animated broadcast overlay and earns the milestone name.

- [ ] **Transparent OBS browser-source overlay** (`/overlay` + `/overlay-json`) served by the crash-isolated console — the core deliverable.
- [ ] **Per-discipline lower-third** (T&F Prese/Zona/Totale · freestyle Nome+Timer · agility Tempo/SCT/Faults) reusing the existing field mapping.
- [ ] **Self-counting run timer** from a NEW `run_started_at` + `running`, with **per-discipline direction** (T&F/freestyle count down, agility counts up) — zero director compute.
- [ ] **Show/hide on run start/stop** via the existing `just_started`/`just_stopped` edges, with a subtle enter/exit animation.
- [ ] **Score-change pulse** on value updates (subtle).
- [ ] **Legible compositing** (semi-opaque plate, contrast, title-safe lower band) so it reads over live grass/sky.
- [ ] **`overlay.txt` fallback retained** (SCR-01).
- [ ] **Unified renderer (SCV-01)** so console preview and OBS overlay share one HTML renderer (do this early — it de-risks the rest).

### Add After Validation (v1.2.x)

- [ ] **Branding/logo + config theme** — add once the base layout reads well and an organizer asks for sponsor space.
- [ ] **Event + identity line** for T&F/agility (freestyle already has `nome`) — once names are wanted on-air.
- [ ] **Curated OBS scene collection** (`obs/segugio-scene-collection.json` + docs) — package once the overlay is wired and proven on the rig.
- [ ] **Staleness/"fresh" guard on pushed score values** (gen-age pattern reused from v1.1) — add when long-run on-air reliability is the focus.

### Future Consideration (v2+)

- [ ] **SCT-relative agility visual** (under/over-time color/bar) — defer; needs careful framing to stay display-only (SCR-04), and the plain Tempo/SCT/Faults line is sufficient first.
- [ ] **Disc-position "lead the dog" pre-framing tie-in** — belongs to the detection/framing roadmap, not the overlay; out of this milestone entirely.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Transparent OBS browser-source overlay (`/overlay`+`/overlay-json`) | HIGH | MEDIUM | P1 |
| Per-discipline lower-third layout | HIGH | MEDIUM | P1 |
| Self-counting run timer (+ `run_started_at` new field) | HIGH | MEDIUM | P1 |
| Per-discipline timer direction (down/up) | HIGH | MEDIUM | P1 |
| Show/hide on run start/stop | HIGH | LOW | P1 |
| Score-change pulse | MEDIUM | LOW | P1 |
| Legible compositing (plate/contrast/title-safe) | HIGH | LOW | P1 |
| `overlay.txt` fallback retained | HIGH | LOW | P1 |
| Unified renderer (SCV-01) | MEDIUM (dev) | MEDIUM | P1 (early) |
| Branding/logo + theme | MEDIUM | LOW-MEDIUM | P2 |
| Event/identity line (T&F, agility) | MEDIUM | LOW | P2 |
| Curated OBS scene collection | MEDIUM | MEDIUM | P2 |
| Staleness/fresh guard on score values | MEDIUM | LOW-MEDIUM | P2 |
| SCT-relative agility visual | MEDIUM | MEDIUM | P3 |

**Priority key:** P1 must-have for the milestone · P2 add when possible · P3 future.

---

## Competitor / Convention Feature Analysis

| Feature | Pro sports broadcast (TV scorebug) | Streamer tools (OBS lower-third packs) | Our Approach |
|---------|-----------------------------------|----------------------------------------|--------------|
| Clock | Persistent, frame-synced, truck-rendered | Static/manual or simple JS | Self-counting JS from `run_started_at`; per-discipline up/down; zero director compute |
| Score source | Live data feed / integrated scoring | Manual operator entry | Manual entry, **verbatim**, never computed (SCR-04) |
| Position | Title-safe lower/corner; can expand briefly | Configurable, often lower-third | Title-safe lower band only; never over field action |
| Animation | Subtle, purposeful state changes | Often over-animated templates | Subtle fade/slide + single pulse; explicitly avoid over-animation |
| Transparency | Hardware keyer | Page CSS transparency in browser-source | Transparent CSS body; OBS composites |
| Adjudication | Official scoring system feeds the bug | N/A | **Never** — display-only is the hard line |
| Fallback | Redundant graphics chains | None typically | Keep `overlay.txt` text source as degraded fallback |

---

## Open Questions / Gaps to flag for the roadmap

- **`run_started_at` placement:** new field on `RunState`, or a sibling overlay record on the channel? (Records are frozen dataclasses with boundary validation — either is consistent with the existing convention.) This is the milestone's one data-model decision.
- **Freestyle round length source:** 90s vs 120s is org-dependent → must be config-driven (likely the existing discipline config block), not hardcoded.
- **Whether the timer should *stop* at zero (T&F/freestyle) or keep counting:** convention is freeze + "Tempo" signal at 0 for the fixed-length disciplines; confirm desired on-air behavior with the user.
- **Agility end-of-run:** the run ends on finish/elimination (operator stop), not at SCT — the timer keeps counting up past SCT (that's the over-time situation), it does not stop at SCT. Confirm the over-SCT display treatment.

## Sources

- [Sports Video Group — Designing the Modern Scorebug](https://www.sportsvideo.org/2026/06/09/designing-the-modern-scorebug-how-broadcast-graphics-teams-are-rethinking-the-most-important-element-on-screen/) — scorebug as the most important on-screen element, expand/contract, hierarchy — **MEDIUM** (article body 403'd; summary from search excerpt)
- [School of Motion — Guide to Sports Lower Thirds](https://www.schoolofmotion.com/blog/sports-lower-thirds) — lower-third anatomy, contrast/legibility, 3-6s persistence — **MEDIUM-HIGH**
- [EBU R095 — Safe areas for 16:9 TV](https://tech.ebu.ch/publications/r095) + [Larry Jordan title-safe](https://larryjordan.com/articles/placing-titles/) + [VeneraTech title-safe](https://www.veneratech.com/what-is-title-safe-and-why-it-still-matters-in-modern-video-production) — action-safe 90% / title-safe 80%, lower-third bottom edge ~5% (HD), keep graphics out of the action — **HIGH** (multi-source corroborated)
- [Wikipedia — Lower third](https://en.wikipedia.org/wiki/Lower_third) + [Wikipedia — Score bug](https://en.wikipedia.org/wiki/Score_bug) — definitions, conventions — **MEDIUM-HIGH**
- [SpiritDog — How dog agility is scored](https://spiritdogtraining.com/agility/how-is-dog-agility-scored/) + [AKC Time-to-Beat chapter PDF](https://images.akc.org/pdf/events/agility/Chapter7_TimetoBeat.pdf) + [USDAA rules](https://www.usdaa.com/regulations/upload/rules-ebook-2011-FINALrev060211.pdf) — SCT definition, count-up vs SCT, time-faults/sec by class, elimination — **HIGH** (multi-source corroborated)
- [K9 Toss & Fetch League rules](https://tossandfetch.com/league-rules/) + [Skyhoundz Toss/Fetch (Air Canines)](https://www.aircanines.com/?page_id=1463) + [ShowSight disc dog guide](https://showsightmagazine.com/dog-sports/disc-dog/) + [Purina disc dog competition](https://www.purina.com/articles/dog/incredible-dog-challenge/freestyle-flying-disc-dog-competition) — T&F 60s countdown + zone points, freestyle 90s/2min set to music — **HIGH** (multi-source corroborated)
- [Disc Dog University — Timers](https://discdoguniversity.com/timers/) — standard countdown cadence ("30 … 10 … 5-4-3-2-1-Time"), 60s T&F, 90s/2min freestyle timers — **MEDIUM-HIGH**
- [USDDN Judging Handbook PDF](https://usddn.com/wp-content/uploads/2024/10/USDDN-2024-judging-handbook-v6.pdf) — countdown announcement convention — **MEDIUM**
- [WP Reset — OBS transparent browser source](https://wpreset.com/how-to-make-browser-source-transparent-in-obs-studio/) + [OBS Forums — HTML/CSS lower thirds](https://obsproject.com/forum/resources/lower-thirds-in-html-css.928/) + [noeal-dac Animated-Lower-Thirds (GitHub)](https://github.com/noeal-dac/Animated-Lower-Thirds) — transparency from page CSS, CSS-transition animation, disable unnecessary animation for perf — **HIGH** (OBS-native behavior, corroborated)
- Codebase (read directly): `src/segugio/ui/score_render.py` (per-discipline labels/aliases, verbatim/sanitize guard), `src/segugio/opcomm/records.py` (`ScoreDoc`/`RunState`/`Discipline`/`DirectorStatus`/`PreviewDoc` — confirmed NO timestamp on `RunState`), `.planning/PROJECT.md` (SCR-04, crash-isolation, v1.2 targets) — **HIGH**

---
*Feature research for: animated broadcast score overlay (lower-third) for live dog sports, OBS browser-source*
*Researched: 2026-06-14*
