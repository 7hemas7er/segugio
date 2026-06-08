# Feature Landscape

**Domain:** Automatic operator-less multi-camera video direction for disc dog & agility competitions
**Researched:** 2026-06-09
**Mode:** Ecosystem (Features dimension)
**Overall confidence:** MEDIUM-HIGH (scoring/rules HIGH from official rulebooks; auto-direction feature mapping MEDIUM — synthesized from sports-broadcast CV + cinematography conventions, no off-the-shelf disc-dog/agility auto-director exists to benchmark against)

> Scope note: the stack is locked (Python + YOLO + cyndilib NDI + OBS/DistroAV + obsws-python + FSM). This document is **product surface only** — WHAT the auto-director should do, not how. Complexity ratings are relative to *this* project's existing modules (framing_scorer, decision_engine FSM, obs_controller, score_manager). "v1" = software-complete on synthetic data (recorded clips + mock NDI), preview-only output, manual score entry, manual override + auto-resume.

---

## The product in one line

**Keep the dog well-framed by cutting to the right camera at the right time, smoothly, never on a dead feed, with the score legible on screen — and let a human take over and then hand back.** Everything in "Table Stakes" serves that sentence. The PROJECT.md Core Value is explicit: *"La camera giusta al momento giusto, in automatico... senza cut tremolanti. Se tutto il resto fallisce, questo deve funzionare."*

---

## Table Stakes

Features without which the auto-direction is not usable as a disc-dog / agility broadcast. Missing any of these = the output looks broken or amateur on first watch.

| Feature | Why expected | Complexity | v1? | Notes |
|---------|--------------|------------|-----|-------|
| **Subject in frame at all times** | If the dog leaves frame, the broadcast has failed its one job. The whole system exists to keep the subject framed. | Med (core) | ✅ v1 | Already the framing_scorer + FSM job. Define "well-framed" as score threshold, not just "detected". |
| **Pick the best-framed camera (centeredness + size + confidence)** | The director must choose the angle that actually shows the action, not just any angle that sees the dog. | Med (core) | ✅ v1 | framing_scorer already specified: `size·centeredness` gated by conf, EMA per camera. |
| **Smooth, non-flickering cuts (no ping-pong, no double-cut)** | Rapid back-and-forth cutting is the #1 way auto-direction reads as "broken". A human director never cuts twice a second. | Med (core) | ✅ v1 | FSM with hysteresis_margin + min_dwell (2-3s) + debounce_N + cooldown. This is the differentiator between "works" and "nauseating". |
| **Never cut to a dead/frozen feed** | NDI repeats the last frame for ~75 min (PROJECT gotcha) — a dropped phone looks "live". Cutting to a frozen frame is catastrophic on air. | Med | ✅ v1 | feed_watchdog on last-*new*-frame timestamp; FSM guard `feed_j_alive`. |
| **Safe fallback when no good shot exists** | When the dog is occluded, between cameras, or all feeds degrade, the director needs a sane default (wide/establishing shot or SAFE scene) instead of a bad cut or a freeze. | Low-Med | ✅ v1 | FSM → SAFE scene. Pick the designated wide camera as the "when in doubt" shot. |
| **Live score / overlay on screen** | A sports broadcast without the score is not a broadcast. Viewers need to know what's happening (catch count, time, faults). | Low | ✅ v1 | score_manager → text source "read from file" (atomic write). See score-field tables below. |
| **Manual override + auto-resume** | Live safety valve. Auto is default; a human forces a camera (e.g. for an award, a re-run, a crowd shot), then the system resumes automatically. | Low-Med | ✅ v1 | Already an Active requirement. Override = FSM locked state with timeout/explicit-release back to AUTO. |
| **No crash, ever (fault isolation)** | Live event software that crashes is unusable regardless of how good the framing is. One dead feed must not take down the director. | Med | ✅ v1 | Orchestrator try/except per receive/websocket, supervised restart, SAFE on irrecoverable. |
| **Config-driven field/camera setup** | Every venue, ring, and field is different. Camera count, zones, thresholds must be data, not code. | Low | ✅ v1 | Central YAML already specified. |
| **Latency low enough that cuts aren't stale** | If the decision loop lags seconds behind the action, the director always cuts *after* the moment. AI loop <~150ms keeps cuts feeling live. | Med | ✅ v1 | Decision loop budget already set (<150ms, ideal <80ms). Decoupled from glass-to-glass. |

**Table-stakes summary:** all ten are realistic for v1 on synthetic data, and all but the overlay text are *already* in the Active requirements. The synthetic-data milestone can validate every one of these without hardware — recorded clips driving mock NDI exercise framing, switching smoothness, feed-death fallback, override, and overlay end-to-end.

---

## Differentiators

Features that move the output from "functional auto-cut" to "feels like a broadcast directed by a person who understands the sport." Not required for usability, but this is where the product earns its name. Each is flagged v1-realistic vs later.

### Framing & camera-intelligence differentiators

| Feature | Value proposition | Complexity | v1? | Notes |
|---------|-------------------|------------|-----|-------|
| **Lead-room toward motion** | A human operator leaves space *ahead* of a running dog, not centered. Centering a sprinting dog looks robotic and crops the landing/catch out of frame. Lead room is *the* cinematography convention for moving subjects (more space in the direction of travel; up to 2/3 of frame for fast motion). | Med | ✅ v1 (scorer-level) | Bias the framing target off-center based on the dog's velocity vector from the tracker. Pure-math change to framing_scorer's "ideal position"; testable on clips. Big perceived-quality win for low effort. |
| **Predictive framing toward where the dog is heading** | Disc-dog catches and agility approaches happen *ahead* of the dog. Cutting/framing to where it *will be* beats reacting to where it *was*. Reduces the "always a beat late" feel. | Med-High | ⚠️ v1-lite / later | v1: simple velocity extrapolation (linear, short horizon) is feasible on synthetic data. True trajectory prediction (toward a known catch point / next numbered obstacle) is later. |
| **Anticipatory camera selection (cut *before* the action arrives)** | Cut to the camera that will own the *next* moment slightly early, so the cut lands as the action enters frame — what a director does when they know the routine. | High | ❌ later | Needs motion prediction + per-camera coverage map. Defer past v1. |
| **Obstacle/zone-aware framing (agility)** | A jump catch, a weave entry, a contact-zone touch each have a "money shot" angle. A director who knows the course frames the *obstacle the dog is about to take*, not just the dog. | High | ❌ later | Requires course/obstacle map per ring. Strong agility differentiator but needs spatial config that doesn't exist in v1. Flag for a later milestone. |
| **Catch-zone-aware framing (disc dog)** | Toss & Fetch scores by distance zone; a director frames the *landing zone* on the long throw to show whether the dog reached the end zone. Frame the catch, not just the dog. | High | ❌ later | Same dependency: needs field-geometry/zone config. Later. |
| **Shot-variety / pacing intelligence** | Real directors vary shot scale and avoid holding one angle too long even when it's "good enough". Prevents a technically-correct but visually monotonous broadcast. | Med | ⚠️ later | Risk: conflicts with anti-flicker. Tune carefully or it becomes the flicker problem in disguise. Later. |

### Show-structure & overlay differentiators

| Feature | Value proposition | Complexity | v1? | Notes |
|---------|-------------------|------------|-----|-------|
| **Run / round segmentation (auto-detect run start/end)** | Knowing "a run is happening now" lets the director tighten framing during the run and relax between runs (handler setup, dog leaving ring). This is the backbone for replay markers, per-run overlay, and clean transitions. | Med-High | ⚠️ v1-lite / later | v1: a **manual** "run start/stop" button in the score-entry UI is trivial and unlocks 80% of the value (overlay reset, timer, replay marks). **Auto**-detection (dog crosses start line / first disc thrown) is later and benefits hugely from real timing-system integration. |
| **Replay markers / highlight timestamps** | Marking the moment of a clean run, a big catch, or a fault lets a later milestone auto-clip highlights. Even in preview-only v1, emitting markers costs little and is high future value. | Low-Med | ⚠️ v1-lite | v1: emit a timestamped marker on manual "great catch"/"run end" events to a log/sidecar file. Actual replay *playback* is out of scope (preview-only, no recording in v1). |
| **Handler PIP / leader (picture-in-picture of the handler)** | Disc-dog freestyle is a *handler+dog* performance — the throw, the vault off the body, the choreography. A PIP or occasional cut to the handler tells the story the single dog-tracking shot misses. | Med | ⚠️ v1 (manual) / later (auto) | obs_controller already supports PIP (SetSceneItemTransform + SetSceneItemEnabled). v1: expose PIP as a *manual* overlay toggle. *Auto* PIP timing (when to show handler) is later. Much more valuable for disc dog than agility. |
| **Discipline-aware overlay layout** | Disc dog and agility show *different numbers* (see field tables). The overlay should present the right fields per discipline, not a generic scoreboard. | Low | ✅ v1 | Pure config/templating in score_manager. A "discipline" setting selects the field set. |
| **Live timer mirroring the official clock** | Both sports are timed (60s/90s disc rounds; SCT in agility). A running clock on screen is standard broadcast and trivially valuable. | Low | ⚠️ v1 (manual-start) | v1: operator-started countdown/up timer in the entry UI written to the overlay file. Auto-start from a real timing system is later. |
| **"On air" / camera-tally feedback for the operator** | The human overriding needs to see which camera is live and whether they're in AUTO or OVERRIDE. Prevents fighting the system blind. | Low | ✅ v1 | Small status readout in the operator CLI/UI. Cheap, high operability value. |

### Robustness differentiators

| Feature | Value proposition | Complexity | v1? | Notes |
|---------|-------------------|------------|-----|-------|
| **Graceful multi-dog disambiguation (pick the competing dog)** | Bystander dogs, the next competitor warming up, or a loose dog can pull the tracker. Locking to the *competing* track keeps the director on the right subject. | High | ⚠️ v1-lite | v1: "best dog track per camera by framing score" (already the plan) handles the single-dog case. Robust re-ID / lock-to-competitor is explicitly deferred in PROJECT (Out of Scope). |
| **Occlusion-tolerant tracking (hold through brief loss)** | Dogs disappear behind tunnels, A-frames, the handler. The director shouldn't bail to SAFE on every 200ms occlusion. | Med | ✅ v1 | A short "grace" before declaring the subject lost (BoT-SORT re-ID after occlusion is in the tech stack). Tunable hold window. |

**Differentiator summary — what to actually do in v1:** ship **lead-room toward motion** (cheap, huge perceived gain), **simple velocity-based predictive framing**, **discipline-aware overlay**, **manual run start/stop + manual replay markers**, **manual PIP toggle**, **manual timer**, and **operator tally/state readout**. Defer everything that needs *spatial field/course geometry* (obstacle-aware, catch-zone-aware, anticipatory selection) — those need config that v1 doesn't have and are the natural content of a later milestone.

---

## Anti-Features

Features to deliberately **not** build for v1, with the reason. Several are already Out-of-Scope in PROJECT; included here so the roadmap doesn't re-introduce them.

| Anti-Feature | Why avoid (for v1) | What to do instead |
|--------------|--------------------|--------------------|
| **Recording / streaming output (RTMP/YouTube)** | v1 is preview-only by decision. Adding encode/bitrate/network concerns balloons scope and risk with zero validation benefit for the *direction* logic. | Preview-only. Validate the director, define output later. |
| **External scoring-system API integration** | Every org/timing vendor differs; chasing an API in v1 couples you to hardware/protocols you can't test on synthetic data. | Manual score entry → file. Design the field schema now so an API can fill it later. |
| **Automatic score detection from video (OCR/CV scoreboard reading)** | High effort, brittle, and unnecessary when a judge already knows the score. Easy to get wrong on air. | Manual entry. It's faster and more reliable than reading a scoreboard with CV. |
| **Automatic fault / catch detection from video** | Judging is the *judge's* job and is legally/competitively authoritative. A CV "the dog faulted" overlay that disagrees with the judge is worse than no overlay. | Capture faults/catches via the manual entry UI. The system *displays*, never *adjudicates*. |
| **Automatic run start/end detection (v1)** | Reliable detection (start-line crossing, first throw) is much easier with a real timing-system signal, which v1 doesn't have. CV-only detection on synthetic data risks tuning to fake data. | Manual run start/stop button now; auto-detect in a hardware milestone with the real timer. |
| **PTZ / physical camera control (pan-tilt-zoom motors)** | The architecture is *switching* between fixed phone feeds, not driving motors. PTZ is a different product with different hardware and latency. | Frame-by-selection across fixed cameras + digital reframe within a feed if needed. |
| **Digital zoom / crop-and-pan to fake a closer shot** | Tempting, but upscaling phone feeds looks soft and the cropped path fights the anti-flicker logic. Adds a whole new motion-control surface. | Choose a better-positioned *camera*. Revisit digital reframe only after switching is rock-solid. |
| **Multi-dog / pairs-freestyle full handling** | Re-ID-heavy, explicitly deferred in PROJECT. Pairs freestyle (two dogs) multiplies tracking ambiguity. | Single-competitor v1. Best-track-per-camera. Defer pairs. |
| **Audio mixing / commentary / music sync** | Disc freestyle runs to music; syncing or ducking audio is an entire audio-engineering subsystem orthogonal to video direction. | Out of scope. Video direction only in v1. |
| **Graphics package / lower-thirds animation engine** | A motion-graphics system (animated transitions, sponsor bugs, name cards) is broadcast polish, not direction. Huge surface, no validation value yet. | Static text overlay from file. Polish later. |
| **Cloud / multi-venue / remote-production features** | Local single-event tool first. Distributed production is a different product class. | Single local host. |
| **Operator-configurable ML / on-the-fly model training** | PROJECT mandates a pre-trained model, drop-in via config. No training in scope. | Pre-trained YOLO, class index from config. |
| **"Cinematic" auto-transitions (wipes, dissolves, stingers)** | Sports direction overwhelmingly uses hard cuts; fancy transitions add latency and read as gimmicky. | Hard cuts (SetCurrentProgramScene). Maybe a fast dissolve later, configurable. |

---

## Live score / overlay fields — what to capture in the manual entry UI

The manual score-entry UI must capture the fields a viewer expects on screen for each discipline. Below are the concrete fields, grounded in the actual rulebooks. **Confidence: HIGH** — these come from official org rules (Toss & Fetch, USDDN/Skyhoundz, AKC/UKC/USDAA agility). Exact numbers vary by organization, so treat the *field set* as the spec and make *values/thresholds* config-driven.

### Disc Dog

Disc dog splits into two very different formats; the UI should support both via a "discipline/format" selector.

**Toss & Fetch (distance-zone scoring) — the simpler, score-as-you-go format:**

| Field | Type | Notes / example |
|-------|------|-----------------|
| Team / dog name + handler | text | Competitor identity for the overlay name card |
| Round number | int | Typically two 60s rounds |
| Round timer | clock (60s) | Counts the scoring window |
| Catch count | counter | Number of successful in-air catches this round |
| Per-catch zone | enum (Z1/Z2/Z3/EndZone) | Distance zones: ~10–20y=1pt, 20–30y=2pt, 30–40y=3pt, 40y+=5pt (org-dependent). "Trailing paw decides the zone." |
| Mid-air bonus | toggle/+0.5 per catch | "All four paws in the air" half-point bonus (org-dependent) |
| Running total points | computed/int | Sum the operator can see and that goes on the overlay |
| Drop / miss | counter (optional) | Not always shown, but useful for the operator |

**Freestyle (judged routine) — the subjective, music-scored format:**

| Field | Type | Notes / example |
|-------|------|-----------------|
| Team / dog name + handler | text | Name card |
| Routine timer | clock (60–120s, often 90s) | Music/routine window |
| Category sub-scores | numeric per category | Judging systems vary: e.g. Skyhoundz **PAWS** (Presentation, Athleticism, Wow!, Success); others use Canine Athleticism / Degree of Difficulty / Execution / Showmanship |
| Total / final score | computed/int | Composite of category scores |
| Judge id (multi-judge) | optional | Some events average multiple judges |

> Freestyle scores typically aren't shown *live* during the routine the way Toss & Fetch counts are — they're tallied and shown *after*. The overlay during a freestyle run is mostly the **name card + routine timer**, with the score appearing at the end. This affects what the director shows mid-run (see disc-vs-agility below).

### Agility

Agility is a single, well-defined "fastest clean run wins" model. **One competitor on course at a time.** The overlay is fundamentally a **clock + fault count**.

| Field | Type | Notes / example |
|-------|------|-----------------|
| Dog / handler name | text | Name card |
| Jump height class / level | enum | Small/Med/Large; Novice/Open/Excellent etc. (affects SCT and fault weighting) |
| Standard Course Time (SCT) | seconds (config) | The target time set by the judge for this course/class |
| Running course time | clock | The live elapsed time (the headline number on screen) |
| Faults — knocked bar | counter | Bar down = fault (commonly 5 pts) |
| Faults — refusal / run-out | counter | Refusal at an obstacle (limits vary by level; too many = NQ) |
| Faults — off-course / wrong-course | counter | Wrong obstacle taken |
| Faults — missed contact | counter | Failed to touch the yellow contact zone (A-frame/dogwalk/seesaw) |
| Time faults | computed | 1/2/3 pts per second over SCT depending on level |
| Total faults | computed/int | Sum for placement |
| Result / Q status | enum (Clean / Faulted / Eliminated / NQ / Q) | Qualifying-run status |
| Current obstacle number (optional) | int | If a course map is loaded later — supports obstacle-aware framing; not v1 |

**UI design implication:** model the score state as a small per-discipline schema written atomically to the overlay file. Provide:
- a **discipline selector** (disc-toss-fetch / disc-freestyle / agility) that swaps the field set and overlay template,
- **increment buttons** for the counters (catches, faults) — the operator's hands should never leave a few big buttons during a live run,
- a **run start/stop** control that resets counters and starts the timer (this doubles as the manual run-segmentation signal),
- a **name-card** field set loaded per competitor (ideally from a start-list file).

---

## How the two disciplines differ for the director

This is the crux of the question and drives different behavior in the *same* engine. Make discipline a first-class config dimension.

| Dimension | Disc Dog | Agility |
|-----------|----------|---------|
| **Spatial pattern** | Throw-and-chase: dog sprints *away* from a (mostly fixed) handler toward a catch point, then back. Long, fast, linear bursts across an open field. | Dog follows a *fixed numbered sequence* of obstacles snaking around a defined ring. Path is known in advance (course map). |
| **Where the "money shot" is** | The **catch** — the leap and grab downfield. Frame the *landing/catch zone* and leave **lead room** toward the throw. | The **obstacle being taken** — the jump, the weave entry, the contact-zone touch. Frame *ahead* onto the next numbered obstacle. |
| **Handler importance** | High (freestyle): vaults off the body, choreography, the throw itself. Handler is part of the performance → **PIP / handler shots matter**. | Low-Med: handler runs alongside directing, but the *dog on the obstacle* is the story. Handler PIP rarely needed. |
| **Predictability of path** | Lower: depends on throw direction; but the handler's wind-up *telegraphs* the next throw direction (predictive-framing cue). | Higher: the numbered course is fixed and walked in advance → strong basis for anticipatory selection *later* (needs course config). |
| **Live overlay content** | Toss&Fetch: live catch count + zone + total. Freestyle: mostly name + timer, score shown *after*. | Live elapsed time vs SCT + accumulating faults. The clock is the headline. |
| **Run boundary** | Round = a fixed timed window (60s/90s). Clear start (first throw / music start) and stop (timer). | Run = start-line crossing to finish-line crossing (electronic photocell timing in real events). Very crisp boundaries. |
| **Camera-coverage strategy** | Cameras placed to cover the *long axis* of throws + a handler-side angle. Cutting follows the dog's sprint. | Cameras placed to cover *clusters of obstacles*; cutting follows the dog *through the course sequence*. |
| **Pace of cuts** | Fewer, longer holds following a sprint-and-return; cut on direction changes (new throw). | More frequent following the dog obstacle-to-obstacle, but still smoothed; cut as the dog clears one cluster for the next. |

**Net for v1:** the *engine* is identical (track → score framing → smooth FSM switch). What changes per discipline in v1 is (a) the **overlay field set** and (b) **framing bias defaults** (disc: more lead room / longer holds; agility: tighter follow / more obstacle-cluster cuts) — both config, both testable on synthetic clips. The genuinely discipline-specific *intelligence* (obstacle-aware framing for agility, catch-zone framing for disc) is **later**, because it needs spatial field/course geometry that v1 deliberately lacks.

---

## MVP recommendation (v1, synthetic data)

**Build (table stakes + cheap differentiators):**
1. Best-framed-camera selection (framing_scorer) — core
2. Smooth, non-flickering FSM switching — core
3. Never-cut-to-dead-feed (watchdog) — core
4. Safe fallback shot — core
5. Manual override + auto-resume — core
6. Live overlay via file, **discipline-aware field set** — core + cheap differentiator
7. **Lead-room toward motion** in the framing scorer — cheap, high perceived-quality
8. **Simple velocity-based predictive framing** (short linear horizon) — cheap
9. **Manual run start/stop** (UI button) + **manual replay markers** to a sidecar — unlocks structure for near-zero cost
10. **Manual PIP toggle** + **operator tally/state readout** — operability

**Defer to later (hardware / geometry milestones):**
- Auto run-start detection (wants real timing system)
- Obstacle-aware framing (agility) / catch-zone framing (disc) — wants field/course geometry config
- Anticipatory camera selection — wants motion prediction + coverage map
- Auto PIP timing, shot-variety/pacing engine
- Robust multi-dog re-ID / lock-to-competitor
- Recording/streaming, external scoring API, CV score/fault detection

**Why this split:** every v1 item is exercisable with recorded clips + mock NDI and validates the Core Value ("right camera, right moment, automatically, smoothly"). Everything deferred either needs hardware signals (timer, NDI under real loss) or spatial config (course/field maps) that the synthetic milestone intentionally doesn't carry.

---

## Feature dependencies

```
best-framed-camera (scorer) ─┬─→ smooth FSM switching ─┬─→ manual override + auto-resume
                             │                          └─→ safe fallback
feed_watchdog ───────────────┘
lead-room / predictive framing ──→ (refines) framing target ──→ scorer

run start/stop (manual) ──┬─→ overlay reset + live timer
                          ├─→ replay markers
                          └─→ (later) auto run-detection needs real timing system

discipline selector ──┬─→ overlay field set (disc T&F / disc freestyle / agility)
                      └─→ framing-bias defaults (lead room, hold length, cut cadence)

field/course geometry (LATER) ──┬─→ obstacle-aware framing (agility)
                                ├─→ catch-zone framing (disc)
                                └─→ anticipatory camera selection
```

---

## Sources

Scoring & rules (HIGH — official org rulebooks / judging handbooks):
- Toss & Fetch League rules & judging — https://tossandfetch.com/league-rules/ , https://tossandfetch.com/how-to-judge-k9-frisbee-toss-fetch-league-play/
- ALL Canadian Disc Dog zone scoring — https://allcanadiandiscdog.com/rules-and-regulations
- UpDog Throw & Go / Freestyle rules — https://updogchallenge.com/wp-content/uploads/2014/01/Up-Dog-Throw-and-Go-Field-and-Rules-1.pdf
- USDDN World Finals Judging Handbook (PDF) — http://d2isc.com/images/2015_USDDN_Judging_handbook.pdf
- Skyhoundz freestyle / PAWS judging — https://skyhoundz.com/a-primer-on-skyhoundz-judging-criteria/ , https://skyhoundz.com/freestyle-pairs-freestyle/
- UFO Freestyle judging guidelines — https://www.ufoworldcup.org/content/Rules/Freestyle.php
- Pawsitive Vybe on judging difficulty — https://pvybe.com/latest/judging-difficulty-and-canine-subelements/
- AKC/UKC/USDAA agility scoring & obstacles — https://spiritdogtraining.com/agility/how-is-dog-agility-scored/ , https://www.ukcdogs.com/docs/rulebooks/agility_rulebook.pdf , https://www.usdaa.com/join-the-fun/what-is-dog-agility/Agility-Obstacles.cfm , https://www.usdaa.com/join-the-fun/what-is-dog-agility/Understanding-Courses.cfm
- Agility timing (start/finish photocells) — https://wpc-timing.de/en/dog-sport/ , https://agilitytiming.com/en/content/6-agility-timing-system
- Contact zones / obstacles — https://baddogagility.com/contact-obstacles/ , https://doggiesport.com/dog-agility-contact-obstacles-a-frame-dog-walk-seesaw/
- ESPN agility format explainer — https://www.espn.com/olympics/story/_/id/47009162/how-do-dog-agility-competitions-work-format-scoring-rules

Auto-direction & framing conventions (MEDIUM — sports-broadcast CV + cinematography, mapped to this domain by inference):
- Sports auto-tracking / camera switching CV — https://arwall.co/blogs/arwall-blogs/sports-camera-tracking , https://getstream.io/blog/ai-sports-analytics/ , https://www.spiideo.com/sports-video-camera-systems/
- Optical player-tracking patents (broadcast-camera selection by player cluster/zone) — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9744457
- Lead room / headroom / rule-of-thirds for moving subjects — https://neiloseman.com/lead-room-nose-room-or-looking-space/ , https://wolfcrow.com/the-three-important-composition-and-framing-conventions-in-cinematography/

> Note: no off-the-shelf *disc-dog/agility-specific* auto-director was found to benchmark against — the differentiator mapping is synthesized from generic sports-broadcast CV practice + cinematography convention + the discipline rulebooks. That synthesis is the MEDIUM-confidence part; the scoring/field facts are HIGH.
