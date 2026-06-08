<!-- GSD:project-start source:PROJECT.md -->
## Project

**Segugio**

Sistema di **regia video automatica senza operatore** per gare di **disc dog** e **agility**. Più telefoni (3-4) pubblicano feed NDI HX3 su una rete WiFi 6 dedicata; OBS Studio fa da hub video, mentre un orchestratore Python traccia il cane sul campo con un modello YOLO su GPU, sceglie in tempo reale la telecamera con la miglior inquadratura e commuta la scena OBS via obs-websocket, sovrapponendo i punteggi della gara. È pensato per chi organizza/riprende gare cinofile e vuole una regia multi-camera senza un operatore dedicato.

**Core Value:** **La camera giusta al momento giusto, in automatico.** Il sistema deve mantenere il cane ben inquadrato commutando tra le telecamere in modo fluido — senza operatore e senza cut tremolanti. Se tutto il resto fallisce, questo deve funzionare.

### Constraints

- **Tech stack**: Python orchestratore; `ultralytics` + `torch` (+ `tensorrt` per prod) per YOLO; `cyndilib` per ingest NDI; `obsws-python` per obs-websocket v5; `transitions` per la FSM; `opencv-python`, `numpy`, `pyyaml`, `loguru`, `watchdog` — Vincolo da brief: stack imposto, integrare YOLO esistente.
- **Performance**: loop decisionale AI < ~150ms (ideale <80ms); video glass-to-glass ~150-350ms accettato — Vincolo fisico riformulato dal "<50ms" originale.
- **Hardware**: GPU NVIDIA CUDA (disponibile in dev); produzione consigliata su Windows; codice OS-agnostic — Per maturità ecosistema NDI/OBS.
- **Dependencies**: OBS Studio + plugin DistroAV (NDI); obs-websocket v5; modello YOLO pre-addestrato fornito via config — Componenti esterni richiesti dal brief.
- **Robustezza live**: nessun crash ammesso; caduta feed → degrado a scena SAFE / fallback — Requisito live esplicito.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## TL;DR (the 6 domain decisions)
## Recommended Stack — Domain Additions
### Detection model (the actual weights behind the locked "Ultralytics YOLO")
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **YOLO26 detect** (`yolo26s.pt`) | YOLO26 (released Sep 2025; current SOTA Jan 2026) | Single-dog detector feeding the per-camera tracker | Native end-to-end (NMS-free) → lower & more deterministic tail latency, directly helping the <150ms AI loop. 40.9–57.5 mAP @ 1.7–11.8 ms T4 TensorRT across n→x. Auto-downloads on first use. Drop-in for the locked Ultralytics API (`YOLO("yolo26s.pt")`). |
| `yolo26s.pt` (small) | YOLO26-S | **v1 default** | Best accuracy/latency point for a *small, fast, erratic, outdoor* subject. The dog is frequently distant on the field where nano loses recall; `s` still runs in single-digit ms on a CUDA GPU. |
| `yolo26n.pt` (nano) | YOLO26-N | Config fallback for weak GPU | Up to 43% faster CPU; choose only if the deploy GPU can't hold `s` inside budget. Swap via the existing `path` config key — no code change. |
| `yolo26m.pt` (medium) | YOLO26-M | Accuracy ceiling test only | Use to *measure* the recall gap on hard clips (dog tiny / motion-blurred); do **not** ship `m` in the live loop unless the latency budget proves to allow it. |
### Pose model (differentiator — LATER, not v1)
| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| `yolo26s-pose.pt` + **Dog-Pose dataset** | YOLO26-pose; Dog-Pose: 6,773 train / 1,703 val imgs, **24 keypoints** (337 MB, auto-download), derived from Stanford Dogs | Dog body orientation / "is the dog facing toward the disc / next obstacle" → smarter framing & anticipation | **Later milestone.** Pose gives heading/intent for framing decisions but adds inference cost and is unnecessary for v1's box-based framing scorer. Cite Khosla et al. 2011 + Deng et al. 2009 if used. |
### Tracker config (the highest-value domain tuning)
| Technology | Setting | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **BoT-SORT** (`botsort.yaml`) | **`with_reid: True`, `model: auto`** | Per-camera tracker that survives jumps/tunnels/handler occlusion and frame exit/re-entry | `model: auto` uses the detector's **own native features** as the ReID embedding — **no extra model download, near-zero extra cost** (Context7-verified: encoder is a passthrough lambda when `with_reid and model=="auto"`). This is the cheap re-ID the locked stack thought was "heavy". |
| BoT-SORT | **`track_buffer: 60`** (default 30) | Keep a lost dog's track alive longer through a tunnel / off-frame stretch | A disc dog can be hidden 1–2 s; at ~30 Hz, 30 frames = ~1 s is too short. 60 spans typical tunnel/occlusion. Tune per clip. |
| BoT-SORT | `new_track_thresh: 0.25`, `track_high_thresh: 0.25`, `track_low_thresh: 0.1`, `match_thresh: 0.8`, `proximity_thresh: 0.5`, `appearance_thresh: 0.8`, `gmc_method: sparseOptFlow`, `fuse_score: True` | Defaults — start here, tune on clips | These are the verified shipped defaults. `gmc_method: sparseOptFlow` (camera-motion compensation) helps if a phone operator pans; consider `gmc_method: None` for locked tripods to save CPU. |
### Disc / frisbee detection (differentiator — LATER)
| Technology | Setting | Purpose | When to Use |
|------------|---------|---------|-------------|
| Same YOLO26 model, **`classes=[16, 29]`** | COCO `frisbee` = **class 29** (0-indexed, verified against `coco.yaml`) | Detect the disc to **predict where the dog will run** → pre-frame the catch zone, lead the dog | **v2 differentiator.** Free to try (same model, add class 29 to the filter). BUT a fast-spinning disc is a small, motion-blurred, fast object — COCO `frisbee` recall will be mediocre; expect to fine-tune on a disc dataset before it's reliable. Keep it OFF in v1 to protect latency and simplicity. |
## Datasets & Test Fixtures (for Phase-0/2 synthetic work — v1, needed)
| Source | What | License / Legality | Use |
|--------|------|--------------------|-----|
| **Pexels Videos** (pexels.com/search/videos) | Free stock dog / dog-running / frisbee clips, 4K/HD | **Pexels License (CC0-like), commercial OK, no attribution required** | **Primary v1 fixture source.** Safest legally. Grab a handful of dog-running + frisbee-catch clips as the synthetic "feeds". |
| **Pixabay Videos** | Similar free stock, "creative commons license" search | Pixabay License, free commercial | Secondary fixture source. |
| **Roboflow Universe — "frisbee tracking"** (tracking-f1jov/frisbee-tracking) | 521 imgs, classes: disc / observer / player | Per-dataset license (check each) — typically CC BY 4.0 | If you later fine-tune **disc** detection. Images, not video. |
| **Roboflow Universe — "ultimate frisbee disc detector"** (eelke-van-foeken-sfimp) | 509 disc imgs + pretrained disc model + API | Check dataset page license | Quick disc-detection prototype baseline (later). |
| **Roboflow Universe — dog datasets** (search `class:dog`) | Many dog detection sets (e.g. uni-smbyw/dog-data-set, 1080 imgs) | Per-dataset | Only if you decide to fine-tune the dog detector. |
| **Ultralytics Dog-Pose** | 6,773/1,703 imgs, 24 kpts | Stanford Dogs (research; cite Khosla 2011 + Deng 2009) | Later, pose milestone only. |
| **`yt-dlp`** (v2026.x, github.com/yt-dlp/yt-dlp) | CLI to pull specific public disc-dog/agility clips | **You must verify each video's license** (`--match-filters "license=Creative Commons"` for YouTube CC, or rights you hold) | Tool, not a dataset. Use to fetch CC-licensed competition clips; do not redistribute downloaded copyrighted footage — keep as local private test fixtures only. |
| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `yt-dlp` | `2026.x` (rolling; `pip install -U yt-dlp`) | Fetch CC competition clips for local eval | Dev-only dependency; never a runtime dep. |
| Pexels API (optional) | v1 | Programmatic fixture fetch | Only if you want reproducible fixture downloads in a script. |
## NDI Phone Sender Apps (HARDWARE MILESTONE — NOT v1)
| App | Platform | HX3? | Verdict |
|-----|----------|------|---------|
| **NDICam** (Sienna) | iOS | **Yes — Full NDI + HX3 + "HX3 Ultra" 50 Mbit** | **Best HX3 sender for iOS.** Adds framerate selection (25p / ~29.97p), portrait mode, and **wired Ethernet via adapter** (huge outdoor reliability win — bypasses WiFi contention with 3-4 phones). Recommend for any iPhone in the rig. |
| **NDI Camera** (official, ndi.video) | **iOS + Android** | Yes (modern compressed NDI / HX); high/med/low bandwidth modes | **Safe default**, esp. for Android phones (NDICam is iOS-only). Official, maintained. Use **low/medium bandwidth mode outdoors** to survive WiFi. |
| NDI HX Camera (legacy NewTek) | iOS/Android | Older HX | Superseded by the official "NDI Camera" rebrand; no framerate selection. Avoid in favor of the two above. |
- Prefer **wired Ethernet (USB-C/Lightning adapter)** where the phone can be tethered — eliminates the dominant WiFi-jitter risk the locked research flags (3-4 phones contending).
- HX3, **I+P frames only, no B-frames** (locked requirement; pick the lowest-latency profile the app exposes).
- **Medium/low bandwidth mode** on WiFi to leave headroom; lock to **30p** (or 25p PAL) to match the ~30 Hz AI tick.
- Disable in-app auto-HDR/auto-exposure hunting if possible (causes brightness swings that hurt detection consistency).
## Installation (domain additions only — core deps already in locked stack)
# Models auto-download on first use via the existing ultralytics dep — no new install.
# Just reference the weights in config:
#   yolo_model_path: yolo26s.pt        # v1 default (small)
#   yolo_class_id: 16                  # COCO 'dog' (verify against model.names at startup)
#   tracker: botsort.yaml              # with a custom override enabling with_reid
# Dev-only: test-fixture sourcing (NOT a runtime dependency)
# Later milestone (pose / disc fine-tuning) — same ultralytics, no new package:
#   yolo26s-pose.pt + data=dog-pose.yaml  (auto-downloads 337 MB dataset)
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| YOLO26s | YOLO11s / YOLOv8s | If a YOLO26 weight/export issue surfaces on your CUDA/TensorRT combo; YOLO11 is the mature, battle-tested fallback (same `YOLO()` API). YOLOv8 only for legacy ReID-encoder tooling. |
| YOLO26**s** | YOLO26**n** | Weak GPU / latency budget blown — config swap only. |
| BoT-SORT + native ReID | ByteTrack | AI loop over budget AND you accept ID churn (mitigated by per-tick "best dog track" selection). |
| BoT-SORT native ReID (`model: auto`) | BoT-SORT + external ReID `.pt` | Almost never for single-dog; external ReID weights add download + latency for marginal gain when there's one subject. |
| COCO `dog` (class 16) | Fine-tuned `yolo26s` on a dog dataset | Only after eval shows COCO `dog` misses on your real footage (backlight, motion-blur, mid-air poses). |
| Pexels/Pixabay CC0 clips | `yt-dlp` CC YouTube clips | When you need *real competition* footage for eval and have verified the per-video license. |
| NDICam (iOS) / NDI Camera (Android) | NDI HX Camera (legacy) | Avoid legacy; no upside over the two recommended apps. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| COCO `dog` index assumed = 16 on a **custom** model | Custom mono-class model is index 0; hardcoding 16 silently filters out all detections | Read `model.names` at startup, map class by **name** → index (locked research already says this) |
| Passing a **list of frames** to `model.track()` for multi-cam | Builds ONE tracker, mixes IDs across cameras (#13107); also breaks per-camera ReID | One `model.track(persist=True)` **per camera** |
| ByteTrack as the default tracker | Reassigns new IDs when the dog re-enters frame — exactly the disc-dog/agility failure mode | BoT-SORT with native ReID |
| `track_buffer: 30` (default) for this domain | ~1 s memory is too short for tunnels / off-frame jumps | `track_buffer: 60` (~2 s), tune per clip |
| External heavy ReID weights for single dog | Download + latency cost with negligible single-subject benefit | Native-feature ReID (`model: auto`) |
| Disc (`frisbee`) detection in v1 | Small fast blurred object → poor COCO recall; adds latency/complexity before framing is proven | Defer to v2; prototype later with `classes=[16,29]` + fine-tuning |
| Committing `yt-dlp`-downloaded competition footage to the repo | Copyright; most competition video is not CC | Keep CC0 Pexels/Pixabay clips in-repo; keep real footage local/un-committed |
| Relying on NDI **hardware** HX upgrades later | NDI ended camera HX upgrades (2025) | Phone apps ship HX natively — no upgrade needed |
## Stack Patterns by Variant
- `yolo26s.pt` + BoT-SORT native ReID + `track_buffer: 60`. This is the v1 baseline.
- First drop to `yolo26n.pt` (config). If still over, switch tracker to `bytetrack.yaml` and lean on per-tick best-track selection. Last resort: lower the AI-path imgsz/fps (locked research already lists this).
- Set `gmc_method: None` in the tracker — skips camera-motion compensation, saves CPU, no accuracy loss for static cameras.
- `classes=[16, 29]`, fine-tune disc detection on Roboflow frisbee datasets first; feed disc position to the framing scorer as a "lead the dog toward the disc" bias.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| YOLO26 weights | `ultralytics` (locked dep), current release | Auto-downloads from Ultralytics assets release; needs an `ultralytics` new enough to know YOLO26 — pin `ultralytics>=8.3.x` / current and verify `YOLO("yolo26s.pt")` resolves before committing. |
| YOLO26 native end-to-end (NMS-free) | TensorRT FP16 export | Export on the **deploy GPU** (locked note). NMS-free head simplifies the engine but re-verify the export path on your exact CUDA/TensorRT before the hardware milestone. |
| BoT-SORT `with_reid` + `model: auto` | Detect models with a standard `Detect` head | Context7-verified: native-feature path requires a non-end2end Detect head for the forward-hook; if a model is end2end, Ultralytics falls back to a small cls model for ReID. **Verify native ReID actually engages on `yolo26s` in your version** (test at startup), else it silently downloads a fallback. |
| `botsort.yaml` overrides | `model.track(tracker="botsort_dog.yaml")` | Custom tracker yaml must live where `check_yaml` finds it (cfg/trackers or an abs path). |
## Sources
- `/websites/ultralytics` (Context7) — track modes, BoT-SORT class, `on_predict_start` native-ReID logic, tracker thresholds — **HIGH**
- https://docs.ultralytics.com/models/yolo26 + Ultralytics YOLO26 announcement (ultralytics.com/news, Sep 2025) — model sizes, NMS-free, 40.9–57.5 mAP @ 1.7–11.8 ms T4 — **HIGH**
- https://docs.ultralytics.com/datasets/pose/dog-pose — Dog-Pose: 6,773/1,703 imgs, 24 kpts, Stanford-Dogs origin, citation — **HIGH**
- coco.yaml (raw.githubusercontent.com/ultralytics/ultralytics/.../cfg/datasets/coco.yaml) — verified 0-indexed: person=0, dog=16, frisbee=29, sports ball=32 — **HIGH**
- botsort.yaml + bytetrack.yaml (raw GitHub) — verified default params: track_buffer 30, with_reid False, model auto, gmc sparseOptFlow, thresholds — **HIGH**
- Ultralytics tracking docs / Academy + community comparisons — ByteTrack speed vs BoT-SORT ReID/occlusion tradeoff; ID reassignment on re-entry (discussion #19784) — **MEDIUM/HIGH**
- ProVideo Coalition (NDI HX Camera vs NDICam), ndi.video/tools/ndi-camera, Sienna NDICam page, NDI docs (HX upgrade changes 2025) — phone sender apps, HX3 support, Ethernet, bandwidth modes — **MEDIUM** (web-only, validate on hardware)
- Roboflow Universe (frisbee-tracking, ultimate-frisbee-disc-detector, dog datasets) — disc/dog image datasets for later fine-tuning — **MEDIUM**
- Pexels/Pixabay video licenses, yt-dlp GitHub (`--match-filters`) — legal fixture sourcing — **MEDIUM**
- MDPI Sensors "Sports Ball Detection..." + ball-tracking reviews — COCO out-of-box weak on small fast sports objects → fine-tuning needed for disc — **MEDIUM**
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
