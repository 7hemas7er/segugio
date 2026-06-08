# Architecture Research — Physical Domain / Field Mapping

**Domain:** Automatic multi-camera direction for dog sports (disc dog + agility)
**Researched:** 2026-06-09
**Confidence:** MEDIUM-HIGH (sport dimensions/layout HIGH from rulebooks; camera-mapping recommendations MEDIUM, synthesized from broadcast practice + sport geometry — no published "auto-director for dog sports" prior art beyond auto-follow products like PIXEM/PIXIO)

> Scope note: the SOFTWARE modules (ndi_ingest, yolo_inference, framing_scorer, decision_engine, obs_controller, score_manager, feed_watchdog, orchestrator) are LOCKED in TECHNICAL-RESEARCH.md and are NOT redesigned here. This document maps the **real sport → camera placement → field-zone config → framing weighting → OBS scenes**, and proposes the concrete `config.yaml` fields and OBS scene names those modules consume.

---

## Standard Architecture

### The physical → logical mapping

```
┌──────────────────────────────────────────────────────────────────────┐
│  PHYSICAL FIELD (real world)                                          │
│   • disc dog: truncated diamond, throwing line + 10/20/30/40/50 yd    │
│   • agility:  ~30×30 m ring, numbered obstacle sequence 1..N          │
└───────────────┬──────────────────────────────────────────────────────┘
                │  modeled as
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FIELD-ZONE MODEL (config.yaml)                                       │
│   • field.zones[]  — named rectangles/bands in NORMALIZED field coords│
│   • cameras[]      — id, role, covers[] zones, framing weights        │
│   • dog position (from YOLO bbox) → which zone(s) it is in            │
└───────────────┬──────────────────────────────────────────────────────┘
                │  feeds
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FRAMING SCORER (locked module — we only add the zone-weight term)   │
│   score_cam = base_framing(centeredness,size,conf)                    │
│               × role_weight(camera.role, dog_zone)                    │
└───────────────┬──────────────────────────────────────────────────────┘
                │  best camera id
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  DECISION ENGINE (FSM, locked) → OBS SCENES                          │
│   per-camera scenes + SAFE wide + PIP/multi-view                     │
└──────────────────────────────────────────────────────────────────────┘
```

**Key insight that drives everything below:** in both sports the *interesting subject is the dog*, and the dog moves through **predictable spatial regions**. Disc dog is **range-dominated** (the dog runs *away* from the handler downfield, so distance-from-camera is the dominant variable → a long lens wins when the dog is far). Agility is **sequence-dominated** (the dog follows a *known numbered path* through fixed obstacles → position around the ring is the dominant variable, and the next obstacle is knowable). These two facts produce two different camera strategies on the **same** rig.

---

## Part 1 — The two sports, physically

### Disc dog (HIGH confidence — Skyhoundz / UpDog / Hyperflite rules)

| Event | Field | Action geometry | Camera implication |
|-------|-------|-----------------|--------------------|
| **Distance / Accuracy (Toss & Fetch)** | Truncated diamond, min **50 yd long × 30 yd wide** (~46 × 27 m); throwing line then **10/20/30/40/50 yd** scoring bands; end zone = 40-50 yd | Handler stays at/behind throwing line; **dog sprints straight downfield**, catches, returns. The single dominant axis is *depth* (near→far→near), 60 s of repeated out-and-back. | A **long/end-on camera down the throwing axis** is the money shot when the dog is in the far bands (30-50 yd). A **wide** covers the whole field. Dog can be 45 m from the throw line — far beyond what a phone wide-angle frames usefully. |
| **Xtreme / Long Distance** | Rectangle up to **50 × 110 yd** (~46 × 100 m); throws of 65-90+ yd | Pure depth axis, even more extreme range. | Long camera essential; wide alone is useless at 90 yd. |
| **Freestyle** | Same open field, but action **clusters near the handler** (center stage); 1:30-2:00 routine to music; **vaults, flips, spins, "around the world", zig-zag**, multiple discs | Dog orbits and launches *off/around the handler* in a compact zone; occasional long throws break out downfield. | A **handler-centered medium/tight** is the money shot most of the time; the long camera catches the breakout long throws. Center-stage zone matters more than depth bands. |

**Disc-dog takeaway:** the field's natural coordinate system is **(depth along throw axis, lateral offset)**. Distance/Accuracy = weight by depth band. Freestyle = weight a central "stage" zone around the handler. Both share the same physical field; the *zone weighting* differs by event → make event a config switch.

### Agility (HIGH confidence — AKC/USDAA/RKC regs)

| Property | Value | Camera implication |
|----------|-------|--------------------|
| Ring size | **~100×100 ft (30×30 m)** typical; min 100×60 ft; AKC ideal 100×120 ft | Whole ring fits one elevated wide; but obstacles are small and the dog is fast. |
| Course | **15-20 numbered obstacles**, fixed for the class, run in strict order 1→N; length 100-200 yd of path | The path is a **known sequence** — this is the defining difference vs disc dog. |
| Obstacle spacing | ~**12-24 ft** between obstacles (jumps 18-24 ft) | Dog crosses a gap in well under a second at speed → switching must anticipate, not react. |
| Obstacle types | jumps, **weave poles** (6-12), **tunnels**, contacts (**A-frame, dog walk, seesaw**) | Some obstacles are "dwell" moments worth a tight shot: weaves (~2-3 s, rhythmic), contacts (climb + contact zone), tunnel exits (reveal moment). Jumps are fast transitions. |
| Timing | starts when dog crosses **start line / takes obstacle 1**; ends at **finish obstacle** | Natural run boundaries → a "between-runs" SAFE wide is the right idle scene. |

**Agility takeaway:** the field's natural coordinate system is **the ordered obstacle list itself**. The dog's "zone" is really *"near obstacle k"*. Because the course order is known, the system *can* know where the dog is going next — but knowing the live obstacle index requires either manual tagging or position-matching. See Part 4 for the v1 verdict (anticipation is OUT for v1, zones are IN).

---

## Part 2 — Camera placement & roles (3-4 cameras)

Synthesized from broadcast camera-role conventions (game/wide, tight-follow, low/hero, end-on) applied to dog-sport geometry. The recommendation is a **4-camera template that degrades cleanly to 3**.

```
DISC DOG — Distance/Accuracy (depth-dominated)            AGILITY (ring, sequence-dominated)

           far end (50yd) ── END/LONG cam ─┐                   ┌─ obstacle field ─┐
                                           │              LOW  │ 1  2   3    4    │
   30yd ····· zone3 ·····                  ▼  (end-on,    cam ─┤   weave  tunnel  │── HANDLER-SIDE cam
   20yd ····· zone2 ·····                     tele down       │ 7  6   5         │   (covers handler &
   10yd ····· zone1 ·····                     throw axis)     └────────┬─────────┘    contact zones)
   ─── throwing line ───                                               │
        HANDLER  ▲                                          MAIN/WIDE  ▼ (elevated, long side,
   WIDE cam ◄────┘ (elevated, behind/beside handler)        whole ring in frame)
   LOW cam ◄───── (ground level, near throw line for hero jumps)
```

### Camera role table (the canonical roles → config `role` enum)

| Role (config value) | Physical position | What it sees | Best shot when… | Disc dog | Agility |
|---------------------|-------------------|--------------|-----------------|:--------:|:-------:|
| `main_wide` | Elevated, long side (agility) / behind-beside handler (disc) | **Whole field**, dog always in frame, safe | Default / between-action / when no other camera has a strong score → **the SAFE fallback** | ✅ | ✅ |
| `long` (a.k.a. `end_zone`) | **End-on**, behind the far end, telephoto **down the throw/run axis** | Dog filling frame at distance; the catch | Dog in **far zones** (disc: 30-50 yd) / **far half of ring** (agility) | ✅ primary | ✅ |
| `low` (a.k.a. `ground`/`hero`) | **Ground level**, near the action line | Heroic low-angle jumps, vaults, contact zones | Big **jump/vault/contact** moments; dog **near & airborne** | ✅ (freestyle vaults) | ✅ (jumps, A-frame) |
| `handler_side` | Opposite the main, handler's working side | Handler-dog interaction; near obstacles | Disc **freestyle** (action near handler) / agility **handler-side** obstacles | ✅ freestyle | ✅ |

**3-camera default = `main_wide` + `long` + `low`.** `handler_side` is the 4th, most valuable for disc-dog **freestyle** and busy agility rings. The config must support **3 or 4** cameras with these roles assignable per-camera.

### When each camera is the best shot (the rules the scorer encodes)

- **`main_wide`**: always a valid, never-wrong choice → it is the **SAFE scene** and the tie-breaker. Wins by default when every other camera's framing score is weak (dog small/edge/low-conf everywhere), and during transitions/between runs.
- **`long`**: wins when the dog is **far from the handler / far side of field**. In disc D/A this is the *primary* camera for ~half the action (the downfield catch). The zone weight should make `long` dominate for far zones.
- **`low`**: wins on **proximity + verticality** — dog close and jumping/vaulting. Hard to detect "airborne" robustly in v1; approximate with "dog large + near a jump/vault zone". Use sparingly (it has the narrowest useful window) to avoid risky cuts.
- **`handler_side`**: wins when the dog is in the **handler/center zone** (freestyle stage; agility obstacles on that side).

---

## Part 3 — The field-zone model (concrete config schema)

This is the load-bearing deliverable: a zone model that the (locked) framing_scorer can consume to weight a camera by **where the dog is**. Design goals: (1) **resolution-independent** — zones in *field-normalized* coords [0..1], not pixels; (2) **per-camera role weights** keyed by zone; (3) expressible entirely in `config.yaml`; (4) works with synthetic data (recorded clips as pseudo-cameras) in v1.

### Coordinate model decision

Two candidate coordinate systems for "where is the dog":

| Option | What it is | v1 verdict |
|--------|-----------|-----------|
| **A. Per-camera image zones** | Zones defined in each camera's own normalized image (e.g. "top third of long-cam frame = far zone") | ✅ **USE THIS for v1.** No calibration, no homography. Each camera independently maps the dog's bbox center → a zone, and that gates *its own* role weight. Works directly on recorded clips. |
| **B. Shared field plane (homography)** | One world coordinate; each camera calibrated to it; dog has a single field position all cameras agree on | ❌ **OUT for v1.** Requires per-camera calibration / 4-point homography on the real field — belongs to the hardware phases (5-7). |

**v1 uses Option A.** The "field zone" the scorer reasons about is expressed **per camera, in image-normalized coordinates**, plus a coarse **derived global position** (depth band) inferred from the camera that sees the dog best. This keeps everything testable on synthetic clips with no calibration. Option B is the documented upgrade path for real deployment.

### Proposed `config.yaml` schema (seed for the config phase)

```yaml
# ---- field / sport profile -------------------------------------------------
field:
  sport: disc_dog          # disc_dog | agility
  event: distance_accuracy # distance_accuracy | freestyle | xtreme | agility_standard
  # Normalized field model is per-camera (Option A). A camera declares the
  # image-space bands that correspond to physical regions it observes.

# ---- cameras ---------------------------------------------------------------
cameras:
  - id: cam_wide
    ndi_source: "PHONE-WIDE (NDI HX3)"   # or mock source name in v1
    role: main_wide                      # main_wide | long | low | handler_side
    is_safe: true                        # the SAFE/fallback scene source
    obs_scene: "CAM Wide"
    # image-space zone bands (normalized 0..1, origin top-left).
    # Each band maps a region of THIS camera's frame to a logical field zone.
    zones:
      - name: near      # close to handler / near side
        rect: [0.0, 0.55, 1.0, 1.0]      # x, y, w-end, h-end (x0,y0,x1,y1)
      - name: mid
        rect: [0.0, 0.30, 1.0, 0.55]
      - name: far       # downfield / far side
        rect: [0.0, 0.0, 1.0, 0.30]

  - id: cam_long
    ndi_source: "PHONE-LONG (NDI HX3)"
    role: long
    obs_scene: "CAM Long"
    zones:
      - name: far
        rect: [0.0, 0.0, 1.0, 0.60]      # long cam's frame is dominated by far action
      - name: mid
        rect: [0.0, 0.60, 1.0, 1.0]

  - id: cam_low
    ndi_source: "PHONE-LOW (NDI HX3)"
    role: low
    obs_scene: "CAM Low"
    zones:
      - name: near
        rect: [0.0, 0.0, 1.0, 1.0]       # low cam only useful for near/airborne

  - id: cam_handler        # optional 4th
    ndi_source: "PHONE-HANDLER (NDI HX3)"
    role: handler_side
    obs_scene: "CAM Handler"
    zones:
      - name: stage        # freestyle center-stage around handler
        rect: [0.20, 0.25, 0.80, 1.0]

# ---- role × zone weighting (the framing-scorer multiplier) ------------------
# Multiplies the base framing score. >1 boosts, <1 suppresses. The scorer
# picks, for the camera, the zone the dog's bbox-center falls in, then applies
# weight[role][zone]. Tunable; this is the heart of "long cam wins when far".
framing_weights:
  main_wide:   { near: 1.00, mid: 1.00, far: 1.00, stage: 1.00 }  # always neutral → safe
  long:        { near: 0.60, mid: 1.10, far: 1.60 }               # far → long dominates
  low:         { near: 1.40, mid: 0.70, far: 0.30 }               # only near
  handler_side:{ stage: 1.50, near: 1.20, mid: 0.80, far: 0.50 }  # freestyle stage

# Optional global floor: main_wide never scores below this so SAFE is always viable
scoring:
  safe_camera: cam_wide
  safe_min_score: 0.15
```

### How the (locked) framing_scorer uses it — minimal addition

The scorer already computes `base = f(centeredness, size, conf)` per camera (TECHNICAL-RESEARCH.md). The **only** domain addition is a zone lookup + multiply:

```python
def zone_of(bbox_cxn, bbox_cyn, camera):          # which named zone contains center
    for z in camera.zones:
        x0, y0, x1, y1 = z.rect
        if x0 <= bbox_cxn <= x1 and y0 <= bbox_cyn <= y1:
            return z.name
    return None

def domain_weight(camera, zone_name, weights):
    return weights[camera.role].get(zone_name, 1.0)

# score = base * domain_weight  → then existing per-camera EMA smoothing
```

That single multiplier turns "the dog is in the far band" into "the long camera wins", with no change to the FSM, EMA, hysteresis, or OBS modules. It is pure and unit-testable on synthetic bbox sequences — ideal for v1.

---

## Part 4 — Agility next-obstacle anticipation: v1 verdict

**Question:** the agility course is a *known ordered sequence* — should framing anticipate the NEXT obstacle, and how would the system know course order?

**Verdict for v1: OUT OF SCOPE. Model zones, not the course graph.** Reasons:

1. **Knowing the live obstacle index is hard without extra input.** The course order is known *on paper* (judge's course map), but mapping the live dog position to "currently at obstacle 6, next is 7" requires either (a) manual operator tagging per obstacle, (b) per-obstacle geofencing via calibrated field coordinates (needs Option-B homography, which is OUT for v1), or (c) a course-aware tracker. All three exceed the v1 synthetic-data scope.
2. **The reactive zone model already captures most of the value.** Weighting `long`/`handler_side`/`low` by *where the dog is in each camera's frame* gives correct camera choice for the far half, the handler side, and contact/jump moments — without knowing the obstacle index. Anticipation buys *smoothness at fast transitions*, not correctness.
3. **It conflicts with the locked design goal of "no flicker".** True anticipation means cutting *before* the dog arrives — riskier than the FSM's deliberately lagging, hysteresis-driven switching. v1 prioritizes "never wrong / never flicker" over "perfectly timed".

**What IS in scope for v1 (agility):** the same per-camera zone model (near/far/handler-side bands), plus dwell-friendly behavior on contacts/weaves (the FSM's `min_dwell` already prevents cutting away mid-weave).

**Documented upgrade path (later milestone), if anticipation is wanted:**

```yaml
# FUTURE (not v1): course as an ordered list with field positions.
course:
  sport: agility
  obstacles:
    - { index: 1, type: jump,    field_xy: [0.10, 0.20] }
    - { index: 2, type: tunnel,  field_xy: [0.35, 0.25] }
    - { index: 3, type: weave,   field_xy: [0.60, 0.50], dwell: true }
    # ...
```
With Option-B field coordinates, the system could match dog position → nearest obstacle → look up `index+1` → pre-bias the camera covering that obstacle. **Flagged as a dedicated research item for the hardware/real-field milestone, not v1.**

---

## Part 5 — OBS scene set (concrete names → seeds obs_controller + setup docs)

The obs_controller module (locked) cuts scenes via `SetCurrentProgramScene` and builds PIP via `SetSceneItemTransform`/`SetSceneItemEnabled`. Here is the concrete **default scene template** it should target. Scene names are the contract between config (`cameras[].obs_scene`) and OBS.

### Default scene list

| Scene name | Type | Sources | Purpose |
|------------|------|---------|---------|
| `CAM Wide` | per-camera | wide NDI feed + score overlay | `main_wide` program; **doubles as SAFE** |
| `CAM Long` | per-camera | long NDI feed + score overlay | downfield / far-zone program |
| `CAM Low` | per-camera | low NDI feed + score overlay | jump/vault hero program |
| `CAM Handler` | per-camera | handler-side NDI feed + score overlay | freestyle stage / handler-side program (4-cam only) |
| `SAFE` | safety | wide NDI feed only (or a static "PLEASE STAND BY") | guaranteed-valid scene on feed death / shutdown; FSM falls here |
| `MULTIVIEW` *(optional)* | PIP / quad | all camera feeds in a 2×2 grid | between-runs, course walk, or director-debug; built via SceneItemTransform |
| `PIP Wide+Long` *(optional)* | PIP | wide full-frame + long inset | shows context + detail simultaneously for long throws |

### Scene conventions (decisions for the obs_controller + setup README)

- **One scene per camera role**, named `CAM <Role>` — the FSM holds a camera id → the controller maps id → `cameras[].obs_scene` → cut. This keeps the FSM sport-agnostic (it switches *camera ids*, OBS handles the *visual*).
- **`SAFE` is a first-class scene, not just "the wide camera".** It can be the wide feed *or* a static standby graphic. The FSM transitions here on irrecoverable feed loss / shutdown (per locked design). Keeping it separate from `CAM Wide` lets SAFE survive even if the wide phone dies (swap its source to a static card).
- **Score overlay** lives inside each `CAM *` scene as a text source reading-from-file (locked score_manager design), so the overlay persists across cuts.
- **`MULTIVIEW` / PIP scenes are optional v1 niceties.** The PIP machinery is already in the locked obs_controller (`SetSceneItemTransform` + cached `sceneItemId`); a 2×2 multiview is a good **between-runs idle** and a useful **debug view**. Recommend building it but driving it manually/idle-only in v1, not from the auto-director.
- **Scene-name stability:** names are referenced from config; document them in the OBS setup README and treat renames as a config change.

---

## Architectural Patterns

### Pattern 1: Zones in image-normalized space, not world space (v1)
**What:** every "field zone" is a rectangle in a camera's own normalized frame [0..1]; the dog's bbox center selects a zone per camera; that zone gates the camera's role weight.
**When:** v1 synthetic data and any setup without field calibration.
**Trade-offs:** + zero calibration, works on recorded clips, resolution-independent, pure/testable. − no single shared "truth" of dog field position; zones must be hand-tuned per camera mounting. Upgrade to homography (Option B) when real fields + calibration arrive.

### Pattern 2: Role × zone weight multiplier on top of the base framing score
**What:** `score = base_framing × framing_weights[role][zone]`; a single config-driven multiplier expresses "long cam wins when dog is far", "low cam only when near".
**When:** always — it is the entire domain coupling between sport and the locked scorer.
**Trade-offs:** + tiny, declarative, leaves FSM/EMA/OBS untouched, fully tunable from YAML. − weights are heuristics needing tuning on real footage; keep them in config, never hardcoded.

### Pattern 3: Event/sport profile as a config switch, not separate code paths
**What:** `field.sport` + `field.event` select a zone layout + weight table; the engine code is sport-agnostic.
**When:** supporting both disc dog (depth/stage) and agility (sequence/ring) on one rig.
**Trade-offs:** + one codebase, swap a profile to re-aim the director; − requires the zone/weight schema to be expressive enough for both (it is — bands + a stage rect cover both sports).

---

## Anti-Patterns

### Anti-Pattern 1: Defining zones in pixels / per-resolution
**What people do:** hardcode zone boundaries in pixel coordinates of a specific feed.
**Why it's wrong:** breaks when feed resolution/aspect changes; violates the locked scorer's resolution-independence; untestable across synthetic clips of different sizes.
**Do this instead:** normalized [0..1] rects, as in the schema above.

### Anti-Pattern 2: Building a full course-graph anticipation engine in v1
**What people do:** try to track obstacle index live and cut ahead of the dog.
**Why it's wrong:** needs field calibration or manual tagging (out of v1 scope), and conflicts with the locked "never flicker / never wrong" priority; high effort, marginal v1 value.
**Do this instead:** reactive zone weighting now; flag course-aware anticipation as a hardware-milestone research item.

### Anti-Pattern 3: Treating `main_wide` as just another candidate
**What people do:** let the wide camera win/lose purely on framing score like the others.
**Why it's wrong:** the wide is the *safety net*; if it can lose, there is no guaranteed-valid fallback when all framing scores are weak (dog small/occluded everywhere).
**Do this instead:** give `main_wide` neutral (1.0) weights everywhere and a `safe_min_score` floor; designate it `is_safe` and back the dedicated `SAFE` scene with it.

### Anti-Pattern 4: Over-using the `low`/hero camera
**What people do:** cut to the dramatic ground-level camera whenever the dog is near.
**Why it's wrong:** low cameras have a tiny useful window (dog must be close *and* airborne/jumping); cutting to them often produces empty/blurred frames and risky cuts.
**Do this instead:** suppress `low` except in its near zone, and let the FSM's debounce/min_dwell make it a deliberate, rare cut.

---

## Integration Points

### Config → modules (the seams this research defines)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `config.yaml` → framing_scorer | `cameras[].zones`, `framing_weights` | adds the zone lookup + multiplier; pure function, unit-testable on synthetic bbox tracks |
| `config.yaml` → decision_engine | `cameras[].id`, `is_safe`, `safe_min_score` | FSM switches camera ids; SAFE camera identified here |
| `config.yaml` → obs_controller | `cameras[].obs_scene`, scene-name template | id → scene-name mapping; `SAFE`/`MULTIVIEW`/`PIP` scene names |
| `field.sport`/`field.event` → all | profile switch | selects zone layout + weight table; disc-dog vs agility difference lives here |

### Internal boundaries (unchanged — locked)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| framing_scorer ↔ decision_engine | per-camera score → FSM | only change: score now includes domain weight; interface identical |
| decision_engine ↔ obs_controller | camera id → scene cut | OBS scene template is the new concrete artifact |

---

## Disc dog vs agility — strategy difference (explicit summary)

| Dimension | Disc dog | Agility |
|-----------|----------|---------|
| Dominant variable | **Depth** (dog runs away from handler downfield) | **Position around ring along a known path** |
| Primary money camera | **`long`** (D/A far catches) / **`handler_side`** (freestyle stage) | **`main_wide`** + situational `low`/`handler_side` per obstacle |
| Zone model emphasis | depth bands (near/mid/far) + freestyle **stage** rect | near/far + handler-side bands; obstacle-aware later |
| Anticipation | none (action is reactive out-and-back) | *possible* (known sequence) but **OUT for v1** |
| Field size driving lens | up to 90+ yd → **telephoto long cam mandatory** | ~30 m ring → wide covers all; long for far half |
| Idle/SAFE moment | between throws | **between runs** (natural run start/finish boundaries) |

---

## Scaling Considerations (cameras, not users)

| Scale | Adjustment |
|-------|-----------|
| 3 cameras | `main_wide` + `long` + `low`; drop `handler_side`. Smallest sensible rig; covers D/A and basic agility. |
| 4 cameras | add `handler_side`; needed for disc **freestyle** and busy agility rings. The template's design point. |
| 5+ / dual-ring | out of v1 scope; would need per-ring profiles and a higher-level "which ring is active" selector. Flag for later. |

### Tuning priorities (what to calibrate first on real footage)
1. **`framing_weights` per role×zone** — the single biggest lever on "right camera". Start from the table above, tune on recorded runs.
2. **Zone rect boundaries per camera** — depends on actual phone mounting/FOV; expect per-venue adjustment.
3. **`low` camera suppression** — verify it doesn't grab empty/blurred frames.

---

## Sources

Sport dimensions & rules (HIGH confidence):
- Skyhoundz — Distance/Accuracy rules & scoring zones: https://skyhoundz.com/distance-accuracy-and-pairs/
- Skyhoundz — Xtreme Distance field (50×110 yd): https://skyhoundz.com/xtreme-distance/
- Hyperflite — Disc dog competition formats: https://hyperflite.com/disc-dog-competitions/
- UpDog Challenge — games overview: https://updogchallenge.com/games-overview/
- Disc dog — Wikipedia (field as truncated diamond, yard lines): https://en.wikipedia.org/wiki/Disc_dog
- Pawsitive Vybe — freestyle vaults/separation/movement: https://pvybe.com/disc-dog-training/on-vaults-and-overs/on-separation-in-disc-dog-freestyle/
- AKC — Regulations for Agility Trials (ring size, obstacle count, numbering): https://images.akc.org/pdf/rulebooks/REAGIL.pdf
- USDAA — Agility obstacles: https://www.usdaa.com/join-the-fun/what-is-dog-agility/Agility-Obstacles.cfm
- SpiritDog — agility course/arena size: https://spiritdogtraining.com/agility/how-big-is-a-dog-agility-course/
- Bud Houston — obstacle spacing in course design: https://budhouston.wordpress.com/2009/12/17/spacing-between-flow-obstacles-in-the-tdaa/
- AgilityNerd — course design / sight lines: https://www.agilitynerd.com/blog/agility/equipment/how-to-build-agility-courses/

Camera roles & filming practice (MEDIUM confidence — broadcast conventions applied to dog sports):
- BoxCast — best camera angles per sport (wide/tight/low roles): https://www.boxcast.com/blog/the-best-camera-angles-for-every-sport
- StreamGeeks — setting up for different sports: https://streamgeeks.us/setting-up-for-different-types-of-sports-chapter-11/
- Classic Teleproductions — camera positions/assignments (football, soccer): https://classicteleproductions.com/2023/02/09/camera-positions-and-assignments-for-football/
- Digital Photography School — photographing agility (get low, between obstacles): https://digital-photography-school.com/how-to-photograph-agility-events-dog-sports/
- 4 Legged Flix — dog agility live streaming (multi-camera service, prior art): https://www.4leggedflix.com/
- MOVE'N SEE PIXEM/PIXIO — auto-follow camera for agility (existing single-cam auto product): https://shop.movensee.com/en/use-cases/sports/dog-agility.html

---
*Architecture research for: physical/field mapping of disc dog + agility to a 3-4 camera auto-director*
*Researched: 2026-06-09 — software modules locked per TECHNICAL-RESEARCH.md; this maps sport→cameras→config→OBS*
