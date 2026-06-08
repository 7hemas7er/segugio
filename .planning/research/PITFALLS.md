# Pitfalls Research

**Domain:** Automatic multi-camera video direction for dog sports (disc dog + agility) — computer-vision / auto-framing pitfalls
**Researched:** 2026-06-09
**Confidence:** MEDIUM-HIGH (CV failure modes verified against MOT/sports-tracking literature and automated-broadcast post-mortems; dog-sports specifics inferred from sport mechanics + analogous soccer/ball-tracking systems)

> Scope: DOMAIN and computer-vision pitfalls of filming dog sports automatically. The pure-tech pitfalls (NDI false-liveness, multi-stream track-ID confusion #13107, WiFi jitter, FSM flicker, double-decode, websocket throughput) are already covered in `TECHNICAL-RESEARCH.md` and are NOT restated here. Almost every pitfall below is probeable **now** on recorded disc-dog/agility clips before any hardware exists.

> Phase map used (from PROJECT.md): **P0** scaffolding · **P1** framing scorer (pure) · **P2** decision engine FSM · **P3** YOLO + one-tracker-per-camera on recorded videos as pseudo-cameras · **P4** NDI-mock + orchestrator/preview · **P5-P7** hardware (real phones/NDI/field, TensorRT). "Testable on synthetic data in v1" = anything reachable by P4.

---

## Critical Pitfalls

### Pitfall 1: Framing scorer locks onto the handler (or a bystander dog) instead of the competing dog

**What goes wrong:**
The pre-trained COCO `dog` class fires on the competing dog — but the scene almost always contains a **handler** (a `person`, frequently the largest, most central, most stable object in frame) and, at multi-ring or warm-up events, **other dogs** (a dog waiting ringside, a dog in an adjacent ring, a spectator's dog). The framing scorer — built from size + centeredness + confidence — happily scores the handler-adjacent region or a stationary bystander dog higher than the small, fast competitor. The director then keeps a camera "live" that is beautifully framed on the wrong subject. In disc dog the handler and dog are almost always both in frame and close together; in agility the handler runs the course alongside the dog, so "biggest central dog-shaped blob" is frequently *not* the athlete.

**Why it happens:**
The scorer has no notion of *which* dog is the competitor. Size and centeredness reward whatever is big and central; a calm ringside dog beats a distant competitor on every signal. There is no person/dog disambiguation and no "this is the subject" identity anchor — the brief explicitly defers heavy re-ID, so v1 picks "best dog track per camera" with nothing distinguishing competitor from bystander.

**How to avoid:**
- Make subject selection a first-class concern, not an emergent property of the scorer. Add an explicit **"competitor lock"**: pick the subject track at round start (e.g., the dog inside the field/start-zone polygon from config, or the one with the most cumulative motion) and prefer continuity of that track ID over raw per-frame score.
- Use the **field/zone polygons already in config** (`zone del campo`) as a hard spatial gate: a dog detection whose center is outside the course bounds (ringside, adjacent ring, crowd) is excluded or heavily penalized before scoring.
- Add **motion energy** as a scoring signal: the competitor moves far more than a waiting dog or a standing handler. A stationary dog-box should not win.
- Never let `person` detections influence framing; only score the dog class, but keep persons as context (proximity-to-handler can *help* recover a lost dog — see Pitfall 6).

**Warning signs:**
- On recorded clips: the chosen "live" track ID sits on a ringside/stationary box while the athlete is mid-run.
- Score timeline shows a high, *flat* score (stationary subject) winning over a lower, *oscillating* score (real athlete moving through the frame).
- The system looks "rock solid" on a single-dog test clip but falls apart the moment a second dog or a prominent handler enters — a classic false sense of done.

**Phase to address:**
**P1 (scorer design)** + **P3 (validated on multi-dog/handler clips)**. The zone-gate and motion signal are scorer features (P1). Competitor-lock continuity touches the subject-selection logic feeding the FSM (P2/P3). MUST be tested on clips that contain a handler and at least one bystander dog — single-dog clips will hide this entirely.

---

### Pitfall 2: ID swap between competitor, handler's path, and a second dog corrupts the "which camera is live" decision

**What goes wrong:**
Even with a per-camera tracker (BoT-SORT/ByteTrack), ID swaps happen precisely in the conditions dog sports guarantee: two similar-appearance dogs near each other (warm-up, brace/pairs classes, multi-ring), a dog crossing its own/another's path, and re-entry after occlusion. When the tracked ID jumps from the competitor to a bystander dog mid-round, the framing score attached to "the subject" instantly points at the wrong object, and the director cuts to whichever camera best frames the *now-wrong* track. Literature is explicit: ID switches cluster "in crowded areas, as there are multiple strongly matched candidates in close proximity making it difficult to differentiate based on IoU," and non-linear motion during occlusion makes the predicted box land on the wrong track.

**Why it happens:**
IoU/Kalman association assumes roughly linear motion and spatial separation. Dogs are small, fast, and visually similar (lots of border collies), and they pass close to each other and to the handler. Appearance re-ID on a 30-fps small blurry dog is weak. The brief defers heavy re-ID (`with_reid`), so the tracker relies mostly on motion+IoU — exactly the regime that swaps.

**How to avoid:**
- Treat the tracker's ID as *advisory*, not authoritative. Layer the **competitor-lock** (Pitfall 1) on top: if the locked track's box teleports (large position jump inconsistent with plausible dog speed) or its size changes implausibly between frames, treat it as a likely swap and trigger re-acquisition rather than trusting it.
- Add a **plausibility/sanity gate** on the subject track: max per-frame displacement, max size-ratio change. Violations → mark subject "uncertain," hold the current camera (don't cut on a suspect track).
- Enable BoT-SORT camera-motion compensation only once on real (moving-ish) cameras; for fixed phones it is less relevant — don't assume it solves swaps.
- Where the rules allow only one dog on course at a time (most agility runs, most disc rounds), **exploit that prior**: during an active run, expect exactly one competitor; extra dog-boxes are bystanders by definition and should be zone-gated/penalized, which also reduces swap candidates.

**Warning signs:**
- Track-ID timeline shows the subject ID changing during a continuous run with no occlusion event.
- The "live camera" flips right as two dogs cross — a visible cut at the exact moment of an ID swap.
- Subject box jumps a large distance in one frame (teleport), or its area doubles/halves frame-to-frame.

**Phase to address:**
**P3 (tracking on recorded clips)** is where this is *proven*. The plausibility gate is implemented in subject-selection (P3) and consumed by the FSM (P2). Multi-dog/pairs clips and warm-up-with-bystander clips are required test material. This is the dog-sports specialization of the already-known #13107 multi-stream issue — same family, different trigger (similar dogs in one frame, not cross-stream).

---

### Pitfall 3: Motion blur + dropped detections on jumps/sprints make the dog vanish for a beat, and the director reacts wrongly

**What goes wrong:**
At the moments that matter most — the apex of a disc-catch leap, a flat-out sprint between agility obstacles, a fast turn — the dog is **most blurred and most likely to be missed** by the detector. "Targets experience motion blur which results in missing detection targets; the tracker loses the object if it moves faster than the algorithm can handle." A dropped detection for even 3-10 frames means the subject score collapses to zero on the current camera, which can trigger a cut *to another camera* or to SAFE — i.e., the system cuts away from the climax precisely because the climax is hard to detect.

**Why it happens:**
Rolling-shutter phone capture + outdoor motion = heavy blur on fast subjects; a nano/small YOLO at high speed has low confidence on blurred small dogs; the framing score is gated by confidence, so a blur frame reads as "subject gone." The decision engine, if naively wired, equates "low score now" with "switch."

**How to avoid:**
- **Coast through gaps.** The framing score must not collapse to zero on a 1-10 frame miss. Maintain the last-known subject score/position with a short **time-to-live** (e.g., 0.3-0.7 s) before declaring "lost," so brief blur/miss does not move the camera. (This is also why `min_dwell`/`debounce`/`cooldown` exist — make sure they *also* protect against blur gaps, not just contention.)
- Lean on the tracker's two-pass association (ByteTrack/BoT-SORT recover "objects briefly weakly scored due to blur, occlusion, scale change") by **not over-filtering low-confidence boxes** for the subject track; keep a low secondary confidence floor for *continuation* of the locked track even while using a high floor for *new* tracks.
- Treat a detection gap during high motion as **"action in progress, hold"** rather than "subject lost, re-evaluate." The climax is the worst time to cut.
- Tune detector input resolution up for the AI path where blur/small-dog recall matters more than raw FPS (the AI path can run <30 fps).

**Warning signs:**
- Frame-by-frame on jump/sprint clips: confidence dips below threshold for a handful of frames at the apex; with naive wiring the live camera changes there.
- A "subject lost → SAFE" event logged in the middle of an obvious continuous action.
- Recall metric on hand-labeled apex/sprint frames is much lower than on standing/walking frames.

**Phase to address:**
**P1** (score must implement coast/TTL, not hard-gate on confidence) and **P2** (FSM must not switch on transient gaps). Validated in **P3** on jump/sprint clips with frame-level confidence logging. Fully testable on recorded footage — this is one of the highest-value v1 probes.

---

### Pitfall 4: Dog small-at-distance — the scorer punishes the camera that has the whole action and rewards a tight-but-empty one

**What goes wrong:**
Agility courses and disc fields are large; with 3-4 fixed phones the dog is frequently **small in frame** at one end of the course. A `size = wn*hn` term makes a small-but-correct subject score low, so the camera that actually contains the action loses to a camera where some *closer* dog-shaped object (handler's dog at the start, a bystander) is large. Worse, when the dog is genuinely far on every camera, the scorer has no good option and may dither. Detector recall also falls for tiny objects ("the object is too small" is the dominant complaint for ball/small-object detection), compounding Pitfall 3.

**Why it happens:**
A naive size term assumes "bigger box = better shot," which is true for cinematography but couples subject-distance to camera-selection in a way that rewards proximity over correctness. Small-object recall is intrinsically lower. Fixed wide phones mean the subject is often 2-5% of frame height.

**How to avoid:**
- **Decouple "is the right dog here and well-placed" from "how big is it."** Keep size as a *mild* preference with a floor: a correctly-centered competitor that is small should still score well; do not let size dominate. Consider a target-size band (too tiny = bad, but huge isn't proportionally better) rather than monotonic `w*h`.
- Weight **centeredness and being-on-the-locked-track** above raw size; the goal is "the competitor is in this frame and roughly centered," not "this frame has the biggest dog."
- For genuinely-small-on-all-cameras moments, prefer the camera whose **predicted near-future** framing is best (dog running *toward* it) — ties into lead-room (Pitfall 9).
- Validate detector recall specifically on small/distant-dog frames; if a pre-trained COCO `dog` misses the athlete at distance, that's a known limit to flag for later (custom model is out of scope for v1, but the measurement informs whether the wide cameras are usable).

**Warning signs:**
- Scorer consistently selects the camera nearest the start line / nearest a bystander, regardless of where the run is.
- Subject box area histogram shows the athlete is usually tiny (<5% height) yet size term is a large fraction of the score.
- Detection recall on distant frames is far below near frames.

**Phase to address:**
**P1 (scorer weighting/size-band design)**, validated **P3** on multi-camera recorded sets where the dog traverses near→far. Camera-geometry realities (how small the dog actually gets) become concrete only with real fixed-camera footage, but the *scorer behavior* is fully testable now using recorded clips played as pseudo-cameras.

---

### Pitfall 5: Tunnels, A-frames, dogwalks, weave poles — agility occlusion breaks both tracking and the framing score

**What goes wrong:**
Agility is full of **deliberate full-body occluders**: the dog disappears into a tunnel (gone entirely for 1-3 s), behind the up-ramp of an A-frame or dogwalk, behind the chute/contact equipment, and is *partially* occluded weaving through poles (only head/back visible, box shrinks and wobbles). Two distinct failures result: (a) full occlusion → detection gap → "subject lost" → the director cuts away or hunts, then the dog **re-emerges from the tunnel exit** and the tracker may assign a new ID or grab a bystander; (b) partial occlusion → the bounding box gets small and decentered, **corrupting the size and centeredness score** so the camera with the *best clear view* of the tunnel exit loses to a camera that happens to see a sliver of dog.

**Why it happens:**
Detectors need pixels; a tunnel gives zero. Partial occlusion yields a truncated box whose centroid/size no longer reflect the dog's true position. Re-ID after a multi-second gap is exactly where motion-based trackers fail ("non-linear movement during occlusion → predicted position has negligible IoU with the detection → ID switch"). Disc dog has *less* of this (open field) — this pitfall is agility-specific and should be flagged as such.

**How to avoid:**
- **Anticipate known occluders.** Tunnels/contacts are fixed obstacles; their approximate image positions can be marked in config zones. When the subject enters a tunnel-zone and vanishes, treat it as **"expected occlusion: hold the camera that frames the exit"** rather than "subject lost: re-evaluate." Predict re-emergence at the exit.
- Extend the coast/TTL window (Pitfall 3) to occlusion-length scales for tunnel zones (a tunnel can be 1-3 s — far longer than a blur gap), but bound it so a truly-departed dog still triggers SAFE.
- For **partial occlusion**, add an occlusion/clipping detector: if the box touches an occluder zone or its size collapses while near one, **down-weight the size/centeredness terms' influence** (don't trust geometry of a truncated box) and lean on track continuity instead.
- On re-emergence, re-acquire by **spatial gate at the expected exit + motion**, not by appearance alone.

**Warning signs:**
- On agility clips: live camera switches the instant the dog enters a tunnel; a second switch when it exits — visible "lost it / found it" double cut.
- New track ID appears at a tunnel exit while the pre-tunnel ID expired.
- Size/centeredness score drops sharply as the dog passes behind the A-frame even though it's perfectly trackable a moment later.

**Phase to address:**
**P2 (FSM "expected occlusion → hold")** and **P1 (occlusion-aware score gating)**, validated **P3** on agility clips containing tunnels, contacts, and weaves. **Disc-dog vs agility note:** this is primarily an *agility* pitfall; a disc-only deployment can de-prioritize it, but the config-zone occlusion mechanism is cheap insurance. Fully testable on recorded agility footage in v1.

---

### Pitfall 6: The disc/frisbee — helps as an action cue, hurts as a tracking distractor

**What goes wrong:**
The disc is a fast, bright, often-airborne object. Two opposite risks: (a) **Distraction/false subject** — a white/bright disc against grass or sky can be mis-detected (as something) or pull the framing's notion of "where the action is" away from the dog; an airborne disc with no dog near it is a non-event the system might chase. (b) **Missed opportunity** — the disc is actually the single best predictor of *where the dog is about to go and where the climax (the catch) will happen*; ignoring it means the director frames reactively and arrives late to every catch. COCO has a `frisbee` class, so the pre-trained model may already emit disc boxes the system isn't using — or is using badly.

**Why it happens:**
The pipeline is dog-centric; the disc is either ignored (missed lead-room signal) or naively folded into "action location" (distractor). Bright small objects against variable backgrounds are detection-noisy. The catch — the emotional peak of disc dog — happens where disc and dog converge, which a dog-only tracker can't anticipate.

**How to avoid:**
- **Use the disc as a predictor, never as the subject.** If using the `frisbee` class, treat a disc trajectory as a *hint* for lead-room and for "a catch is imminent → do not cut now" — but the framing target is always the dog.
- Gate disc influence by **disc-near-dog**: an airborne disc far from any dog is irrelevant (a throw-back, a miss, a reset); only a disc converging with the dog signals an imminent catch worth protecting.
- If the disc proves to be a *net distractor* in testing (false boxes pulling the scorer), the safe default is to **ignore the frisbee class entirely** and rely on dog motion alone — measure before deciding.
- **Disc-dog vs agility:** this pitfall is disc-dog-only. Agility has no disc; don't build disc logic into shared scorer code paths in a way that can misfire on agility footage.

**Warning signs:**
- Scorer/attention shifts toward an empty patch of sky/grass where a disc is mid-flight with no dog.
- Cuts happen on throws (disc leaves hand) rather than catches (disc meets dog).
- `frisbee` detections show high false-positive rate against bright turf/sky in logged frames.

**Phase to address:**
**P1/P3** — decide empirically on recorded disc-dog clips whether the disc helps (lead-room/catch-prediction) or hurts (distractor), then either wire it as a gated predictor or disable the class. Fully testable in v1. Keep disc logic *optional and disc-dog-scoped* so it never affects agility.

---

### Pitfall 7: Cutting at the wrong moment — mid-catch, mid-jump, mid-weave — destroys the shot

**What goes wrong:**
The single most damning failure for an auto-director: it **cuts during the climax**. A cut in the middle of a disc-catch leap, over the apex of an agility jump, or mid-weave-entry is jarring and loses the moment a human operator would *hold for*. Automated-broadcast post-mortems are explicit that "inconsistent or delayed camera responses impact the flow and may lead viewers to miss key moments or become distracted by awkward framing." Because the climax is also where detection is worst (Pitfall 3) and scores swing most, a naive director is *most* likely to cut exactly when it should hold.

**Why it happens:**
The decision engine optimizes instantaneous framing score, which is volatile during action; it has no concept of "an action is in progress, defer switching." Detection drop at the apex (Pitfall 3) can read as "current camera lost it → switch now," producing a cut at the worst instant.

**How to avoid:**
- Add an **"action-in-progress → suppress cuts"** state to the FSM. Detect action via motion energy / vertical velocity (a jump) / disc-converging-with-dog (a catch) / weave-zone presence, and **raise the switching threshold or freeze the live camera** for the duration. This is a higher-level guard than `min_dwell`: even if dwell elapsed, don't cut mid-jump.
- Ensure `min_dwell` and `cooldown` are long enough that the *typical* climax (a 0.5-1.5 s leap/sequence) cannot be interrupted by routine score noise.
- Cut on **boundaries** (between obstacles, after a catch, on a clear lull), not on instantaneous score maxima. Prefer "switch when the action pauses."

**Warning signs:**
- Reviewing the auto-director's output: cuts land mid-air on jumps/catches.
- Cut timestamps correlate with detection-confidence dips (the apex) rather than with action lulls.
- Viewers/reviewers report "it keeps cutting at the worst moment."

**Phase to address:**
**P2 (FSM action-suppression state)**, validated **P3/P4** by reviewing recorded auto-direction output for mid-climax cuts. Fully testable in v1 — render the director's decisions over recorded clips and watch where cuts land.

---

### Pitfall 8: The auto-director "chases jitter" — cut-storms and a camera that visibly hunts

**What goes wrong:**
Two flavors. (a) **Switching jitter (cut-storm):** when two cameras have near-equal scores (dog mid-field equidistant from two phones), tiny per-frame score noise flips the winner back and forth → rapid cuts. (b) **Framing jitter:** if any digital crop / PIP framing follows the noisy box position directly, the framing visibly twitches/oscillates frame-to-frame; "aggressive smoothing reduces jitter when motion is still but loses track when motion is fast," so a fixed smoothing constant either lags the sprint or twitches at rest. Detection-box jitter (the box wobbles even on a static dog) feeds straight through.

**Why it happens:**
Bounding-box centroids are noisy; EMA with a single alpha can't be both responsive (fast dog) and stable (resting dog). Equal-score contention has no tiebreaker, so noise decides. (The FSM hysteresis/dwell/debounce from `TECHNICAL-RESEARCH.md` addresses *switching* jitter — the domain-specific addition here is *framing* jitter and the *equal-score contention* tiebreak, which the tech research doesn't cover.)

**How to avoid:**
- For **switching**: rely on the FSM dead-band/dwell/debounce (already designed) but ensure the `hysteresis_margin` is wide enough for the *equal-distance midfield* case, and add a deterministic **tiebreaker** (e.g., prefer current live camera, then prefer the camera the dog is moving *toward*) so noise never decides.
- For **framing**: smooth the *target framing*, not just the raw box — EMA the subject position with an alpha that **adapts to motion** (more responsive when the dog is fast, more damped when slow), or use a velocity-aware filter. Apply a **dead-zone**: don't re-center for sub-threshold position changes (kills resting twitch).
- Validate that the chosen alpha (~0.3 baseline in the scorer) doesn't lag fast sprints into the frame edge while still being smooth at rest — this is the classic responsiveness/stability tradeoff and almost certainly needs a motion-adaptive term.

**Warning signs:**
- Cut-rate spikes when the dog is mid-field (equidistant cameras); log shows live camera flipping every few hundred ms.
- Rendered framing twitches on a standing dog, or lags behind a sprinting dog (dog runs to frame edge before the crop catches up).
- A single EMA alpha that "feels right" for sprints looks jittery at rest, or vice versa.

**Phase to address:**
**P1 (motion-adaptive smoothing + dead-zone in scorer/framing)** and **P2 (contention tiebreaker in FSM)**, validated **P3/P4**. The midfield-contention case must be in the test clip set. Fully testable in v1.

---

### Pitfall 9: No lead-room toward motion — the dog runs to the edge and the framing "trails" the action

**What goes wrong:**
Good sports framing puts **space in front of the moving subject** (lead-room) so the viewer sees where the action is going. A scorer that maximizes *centeredness* does the opposite: it centers the dog, leaving no room ahead, so a fast dog appears pinned against the leading frame edge with empty space behind it — the shot constantly "trails." Across cameras, the director may also pick a camera that frames the dog now but loses it in 0.3 s because the dog is sprinting out of that frame. PTZ-auto-framing products explicitly "provide space in the direction of motion/gaze" for this reason.

**Why it happens:**
`centeredness = 1 - dist(center, 0.5,0.5)` rewards dead-center placement, which is wrong for a fast directional subject. The scorer has no velocity term, so it can't reason about where the dog will be.

**How to avoid:**
- Add a **velocity-aware framing target**: bias the desired subject position *opposite* the motion direction (dog moving right → ideal position left-of-center) so there's lead-room. Score centeredness against this shifted target, not the geometric center.
- In camera *selection*, prefer the camera whose framing will still contain the dog a fraction of a second ahead (predict subject position; penalize cameras the dog is exiting). This also fixes Pitfall 4's "small on all cameras, dog running toward camera B" case.
- Keep lead-room modest and clamp it (don't over-lead a slow/curving dog), and disable it when motion is near zero (resting dog → center is correct).

**Warning signs:**
- Rendered framing shows the dog jammed against the frame edge it's running toward, empty space trailing.
- The director picks a camera the dog leaves within a few frames, forcing an immediate re-cut.
- Centeredness score is high (dog centered) yet the shot "feels wrong"/trailing on review.

**Phase to address:**
**P1 (velocity/lead-room term in scorer)**, validated **P3/P4** on clips with fast directional runs (sprints, recalls, long throws). Fully testable in v1.

---

### Pitfall 10: Outdoor light — sun, harsh shadows, low grass/turf contrast, and dawn/dusk wreck detection differently on each camera

**What goes wrong:**
Dog sports are outdoors. (a) **Harsh sun/shadows:** a hard shadow can be mis-segmented as part of the dog or as a separate object ("shadow pixels categorized as part of the object → false positives"), and a dog in shade against sunlit grass has low contrast. (b) **Dawn/dusk:** measured YOLO confidence dropped from 0.8 to 0.64 and IoU from 0.67 to 0.36 across a single evening hour — recall craters as light fades. (c) **Per-camera variance:** 3-4 phones at different angles face the sun differently — one is backlit (dog a silhouette), one front-lit, one in shade. The *same dog* gets very different confidence per camera, so the framing score is **biased by lighting, not by framing quality**, and the director prefers the well-lit camera even when a backlit camera has the better angle (or vice versa). A dark-coated dog (many border collies) on dark turf, or a white dog in blazing sun, are opposite extremes the pre-trained model handles unevenly.

**Why it happens:**
Confidence is a function of image quality, and the scorer gates on confidence — so it conflates "well-exposed" with "well-framed." No per-camera exposure/confidence normalization exists. Pre-trained COCO `dog` wasn't tuned for silhouettes, deep shade, or coat-vs-turf camouflage.

**How to avoid:**
- **Normalize confidence per camera** (e.g., subtract/divide by that camera's rolling baseline confidence) so a consistently-darker/backlit camera isn't permanently penalized in selection — judge *relative* framing quality, not absolute brightness.
- Don't let raw confidence dominate the score; once a detection clears a recall floor, weight framing geometry over the exact confidence value.
- Be wary of **shadow false-positives**: a second "dog" box that tracks the real dog at an offset is likely its shadow — penalize boxes with implausible aspect ratio / that move rigidly with another box.
- Flag **dawn/dusk and heavy backlight as known recall-killers** to revisit with the real cameras (exposure/whitebalance lock on the phones, possibly a custom/finetuned model later — out of v1 scope, but measure now).

**Warning signs:**
- Per-camera mean confidence differs wildly for the same dog; the director consistently favors the brightest camera.
- A ghost "dog" box offset from the real one (shadow) appears in sunny clips.
- Recall collapses in dusk/backlit clips relative to midday clips of the same dog.

**Phase to address:**
**P1 (per-camera confidence normalization)** + **P3 (validate on clips spanning lighting conditions and coat colors)**. Real per-camera exposure behavior is a **P5-P6 hardware** concern, but the *normalization logic and shadow-FP handling* are fully testable in v1 on varied recorded footage. Build the varied-lighting clip set early.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| "Pick the highest-scoring dog track per camera," no competitor-lock | Trivial; works on single-dog clips | Locks onto bystander dogs/handler the moment a real event has >1 dog (Pitfall 1/2); demos great, fails on field | Only as a v1 placeholder *if* test clips are single-dog **and** you log a TODO; never for a real multi-ring event |
| Single fixed EMA alpha for smoothing | One number to tune | Either lags sprints or twitches at rest (Pitfall 8) | MVP scaffolding; replace with motion-adaptive before P4 sign-off |
| Hard-gate framing score to 0 on any missed detection | Simple "subject present?" logic | Cuts away on every blur/jump/tunnel gap (Pitfalls 3,5,7) | Never — coast/TTL is core, not optional |
| Centeredness = distance-to-frame-center only | Matches the documented scorer formula | No lead-room; fast dog pinned to edge (Pitfall 9) | Acceptable for the *first* P1 pass; add velocity bias before P3 review |
| Ignore the disc entirely | No false-positive distraction | Reactive, late-to-the-catch framing on disc dog (Pitfall 6) | Acceptable default if disc tested as net-negative; revisit for disc-dog quality |
| Test only on clean single-dog midday clips | Fast green tests | Every multi-dog/occlusion/lighting pitfall stays hidden until hardware (Pitfalls 1,2,5,10) | Never as the *only* test set — see clip-set checklist below |

## Integration Gotchas

Domain-specific data/model gotchas (NDI/OBS/websocket gotchas are in `TECHNICAL-RESEARCH.md`).

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Pre-trained COCO model | Assuming `dog` is the only relevant class; ignoring that `person` and `frisbee` are also emitted | Score only `dog`; use `person` only as recovery context; treat `frisbee` as an optional disc-dog predictor (Pitfall 6); confirm the class index via `model.names` (custom mono-class ≈ 0, not COCO 16) |
| Recorded clips as pseudo-cameras (P3) | Using one continuous clip → trivially solvable, hides all hard cases | Curate a clip set spanning: multi-dog, handler-prominent, tunnels/contacts, sprints/jumps (blur), distant-dog, backlit/dusk, midfield-equidistant (see checklist) |
| Field/course zones in config | Defined but not used by the scorer | Use zone polygons as a hard spatial gate to exclude ringside/adjacent-ring/crowd dogs (Pitfalls 1,2) and to mark occluder zones (Pitfall 5) |
| Tracker (BoT-SORT/ByteTrack) | Trusting the track ID as ground truth for "the subject" | Treat ID as advisory; layer competitor-lock + plausibility gate; don't cut on a suspect track (Pitfall 2) |

## Performance Traps

Domain-load traps (raw GPU/websocket throughput traps are in `TECHNICAL-RESEARCH.md`).

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Recall tanks on small/blurred dogs at the climax | Confidence dips at apex/sprint; gaps in subject track | Coast/TTL + low continuation-confidence floor + higher AI-path input resolution (Pitfall 3) | Whenever the dog is fast or far — i.e., the whole point of the sport |
| Multi-dog scenes multiply swap candidates | ID swaps during pairs/warm-up/multi-ring | Zone-gate + single-competitor prior + plausibility gate (Pitfall 2) | The first time >1 dog shares a frame |
| Per-camera confidence bias under uneven light | Director glued to the brightest camera | Per-camera confidence normalization (Pitfall 10) | Any sunny/backlit/dusk event with 3-4 angles |

## Security Mistakes

Not a meaningful domain axis for an on-field, local, no-PII auto-director. Standard hygiene only: keep the dedicated camera WiFi/obs-websocket on a private network with a non-default password (the obs-websocket auth detail lives in `TECHNICAL-RESEARCH.md`). No domain-specific security pitfalls.

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Director cuts mid-jump/mid-catch | The product looks broken at exactly the moment that matters; loses trust instantly | Action-suppression state holds through the climax (Pitfall 7) |
| Visible hunting / cut-storms midfield | Output feels nervous and amateurish vs. a human operator | FSM dead-band + contention tiebreaker; motion-adaptive framing smoothing (Pitfall 8) |
| Framing trails a fast dog (no lead-room) | Viewer can't see where the action is going; feels reactive | Velocity-biased framing target (Pitfall 9) |
| No clear "manual override" affordance when auto is wrong | Operator watches it film the wrong dog with no recourse | Manual override + auto-resume is already a requirement — ensure it's *fast* to grab and the auto-resume doesn't immediately re-make the same mistake |
| Silent failure (cuts to SAFE with no reason shown) | Operator can't tell "lost the dog" from "feed died" | Surface *why* (subject-lost vs feed-dead vs override) in the preview/log |

## "Looks Done But Isn't" Checklist

Verify on the **curated multi-condition clip set**, not on a clean single-dog clip.

- [ ] **Subject selection:** Works with a prominent handler in frame AND ≥1 bystander dog — verify it locks the *competitor*, not the biggest/most-central dog (Pitfall 1)
- [ ] **ID robustness:** Survives two similar dogs crossing / a pairs run — verify no cut at the swap instant; plausibility gate fires on teleports (Pitfall 2)
- [ ] **Climax handling:** Holds (no cut, no SAFE) through a disc-catch leap and an agility jump apex despite a detection gap (Pitfalls 3,7)
- [ ] **Occlusion:** Holds the exit-framing camera through a tunnel pass and re-acquires the same subject on exit (Pitfall 5)
- [ ] **Distance:** Doesn't abandon the camera that has the (small) real action for one with a big bystander dog (Pitfall 4)
- [ ] **Lead-room:** Fast directional run shows space ahead of the dog, not pinned to the edge (Pitfall 9)
- [ ] **Lighting:** Doesn't permanently favor the brightest camera; no shadow ghost-box treated as a second dog; recall measured at dusk/backlit (Pitfall 10)
- [ ] **Midfield contention:** Equidistant-cameras moment produces a clean single choice, not a cut-storm (Pitfall 8)
- [ ] **Disc (disc-dog only):** Disc doesn't pull framing off the dog; cuts land on catches not throws (Pitfall 6)
- [ ] **Agility-vs-disc:** Disc-specific logic never activates on agility clips; occlusion logic available for agility

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Scorer/locks onto wrong dog (1) | MEDIUM | Add zone-gate + motion signal + competitor-lock; re-run on multi-dog clip set. Cheap if caught in P1/P3, expensive if discovered post-hardware |
| ID swap corrupts decisions (2) | MEDIUM | Add plausibility/teleport gate + single-competitor prior; hold-on-suspect-track. Pure software, recoverable in P3 |
| Cuts at climax / coasting missing (3,7) | LOW-MEDIUM | Implement coast/TTL in scorer (P1) + action-suppression state in FSM (P2). Localized changes |
| Tunnel/occlusion double-cut (5) | MEDIUM | Mark occluder zones in config; add expected-occlusion hold. Software-only, agility clips needed |
| Jitter / cut-storm / trailing framing (8,9) | LOW | Add dead-zone + motion-adaptive smoothing + lead-room bias + contention tiebreaker. All scorer/FSM-local |
| Lighting bias / shadow FP (10) | MEDIUM | Per-camera confidence normalization + shadow-box heuristic; finetuned model is out-of-scope and HIGH cost — defer, just measure now |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Locks onto handler/bystander dog | P1 (scorer) + P3 (validate) | On multi-dog+handler clips, live track is the competitor through the whole run |
| 2. ID swap competitor↔bystander↔second dog | P3 (subject logic) + P2 (FSM consumes) | No cut at crossing/swap instants on pairs/warm-up clips; teleport gate fires |
| 3. Motion-blur dropped detections | P1 (coast/TTL) + P2 (no switch on gap) | No camera change during apex/sprint detection dips |
| 4. Small-at-distance scoring | P1 (size-band/weighting) + P3 | Director keeps the camera with the real (small) action, not the big bystander |
| 5. Agility occlusion (tunnels/contacts/weaves) | P2 (expected-occlusion hold) + P1 (gate score) | Single clean choice through a tunnel pass; same-subject re-acquire on exit |
| 6. Disc helps/hurts (disc-dog only) | P1/P3 (empirical decision) | Framing stays on dog; cuts on catches not throws; agility unaffected |
| 7. Cutting mid-climax | P2 (action-suppression state) | Reviewed output: zero mid-jump/mid-catch cuts |
| 8. Chasing jitter / cut-storm / framing twitch | P1 (adaptive smooth+dead-zone) + P2 (tiebreaker) | Stable framing at rest, responsive when fast; no midfield cut-storm |
| 9. No lead-room | P1 (velocity-biased target) | Fast runs show space ahead of the dog |
| 10. Outdoor light / shadow / dusk bias | P1 (per-cam confidence norm) + P3 (varied clips); deeper model work P5-P6 | No permanent brightest-camera bias; shadow not counted as a dog |

**Roadmap implication:** Phases 1-3 (scorer, FSM, tracker-on-recorded-clips) carry almost the entire domain-pitfall load and are **fully exercisable on recorded footage with no hardware**. The decisive de-risking action is to **assemble a curated multi-condition clip set early in P0/P1** (multi-dog, handler-prominent, tunnels/contacts, jumps/sprints with blur, distant-dog, backlit/dusk, midfield-equidistant; both disc-dog and agility). Without it, single-dog midday clips will make the system *look* done while every pitfall above lies dormant until the field — the most expensive place to discover them.

## Sources

- Sports ball detection (fast, small, motion-blurred objects): https://pmc.ncbi.nlm.nih.gov/articles/PMC8124271/ — MEDIUM (peer-reviewed, analogous small-fast-object domain)
- SportsTrack — tracking athletes, motion blur causing missed detections: https://arxiv.org/pdf/2211.07173 — MEDIUM
- Ultralytics issue #7109 — small/tiny + fast/high-speed object tracking instability: https://github.com/ultralytics/ultralytics/issues/7109 — MEDIUM (official issue tracker, training-data-adjacent)
- BoT-SORT (camera-motion compensation, two-pass association recovering blur/occlusion/scale): https://trackers.roboflow.com/develop/trackers/botsort/ — HIGH (matches stack)
- ByteTrack intro (associate every detection box; weak-detection continuation): https://datature.io/blog/introduction-to-bytetrack-multi-object-tracking-by-associating-every-detection-box — MEDIUM
- Ultralytics discussion #19784 — ID reassignment/switch behavior: https://github.com/orgs/ultralytics/discussions/19784 — MEDIUM (official forum)
- Deep HM-SORT — ID switches in sports with similar-appearance athletes: https://arxiv.org/pdf/2406.12081 — MEDIUM
- Detection-confidence-driven MOT (strong vs weak detections; not over-filtering low-confidence): https://www.sciencedirect.com/science/article/pii/S0031320322005878 — MEDIUM
- Automated sports production limits (delayed/awkward framing, missing key moments): https://www.thebroadcastbridge.com/content/entry/10785/can-automated-production-replace-the-sports-camera — MEDIUM
- Pixellot→Veo field experience (AI not 100%, wrong-subject attribution, needs human QC): https://medium.com/miggle/switching-from-pixellot-to-veo-e19be34df9de — MEDIUM (practitioner post-mortem)
- Sony PTZ Auto Framing (lead-room / space in direction of motion/gaze): https://pro.sony/ue_US/products/ptz-network-cameras/ptz-auto-framing — HIGH (vendor design rationale)
- PIXEM dog-agility auto-follow (auto zoom for distance — confirms small-at-distance is a real field problem): https://shop.movensee.com/en/use-cases/sports/dog-agility.html — MEDIUM (vendor)
- Shadow false-positives / outdoor lighting degrading YOLO (Rapid-YOLO; confidence/IoU drop 8PM→9PM): https://www.sciencedirect.com/science/article/abs/pii/S003040262200451X and https://arxiv.org/pdf/1812.11901 — MEDIUM
- Adaptive/aggressive motion smoothing tradeoff (still vs fast motion): https://link.springer.com/article/10.1186/s13640-017-0171-8 — MEDIUM
- Disc-dog mechanics (high-drive leaps, catch as climax): https://pvybe.com/disc-dog-training/leaping-for-discs-with-the-high-drive-dog/ — LOW (domain context, not CV)
- Agility tunnel/A-frame mechanics (deliberate occluders, tunnels under A-frames): https://spiritdogtraining.com/agility/a-frame/ and https://dogs4motionacademy.com/tunnel-vision/ — LOW (domain context)

---
*Pitfalls research for: automatic multi-camera direction of dog sports (CV/domain dimension)*
*Researched: 2026-06-09*
