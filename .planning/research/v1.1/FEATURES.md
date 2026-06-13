# Feature Research

**Domain:** Live multi-camera auto-director — **manual-oversight operator console** (Segugio v1.1: turning the bare Flask panel into a live-visibility regia)
**Researched:** 2026-06-13
**Confidence:** HIGH (existing-system facts read directly from source) / MEDIUM (broadcast-convention mapping, web sources)

---

## Framing: what kind of console this is

This is **not** a broadcast switcher (vMix/ATEM) and **not** a generic AI-director. It is the **oversight UI for an auto-director that already decides**. The operator's job (per PROJECT.md / D-04) is: enter scores manually, start/stop runs, and **supervise + override** the automatic camera choice. So the feature bar is set by two different ecosystems:

1. **Multiview / switcher consoles (vMix, ATEM, OBS multiview)** — establish what an operator expects to *see*: all cameras at once, a clear tally/PGM indicator, preview thumbnails on the buttons they press. ([vMix](https://www.vmix.com/software/download.aspx), [Blackmagic ATEM](https://www.blackmagicdesign.com/products/atemconstellation/softwarecontrol))
2. **AI-director oversight UIs (Visor, SmartMix)** — establish the *new* expectation this domain created: the operator must always know **"what is live, what the AI wants next, and WHY,"** with the ability to pause/override instantly. ([Visor](https://www.visorai.org/), [SmartMix](https://smartmixdirector.framer.website/))

Segugio's auto-director already computes everything needed for the "why": per-camera framing **score** (`CameraScore.score` 0..1 + `status` tracking/coasting/lost, Phase 2), the dog **bbox** per camera (`DetectionSignal` normalized cx/cy/w/h, Phase 4), competitor-lock state, and the FSM live decision. **Today all of it is thrown away except `live_cam`/`reason`/`alive`** (the `DirectorStatus` D-11 record). The dominant v1.1 insight: **the "why" data already exists cheaply on the orchestrator side — v1.1 is mostly a publish-and-render problem, not a compute problem.**

### The one hard constraint that shapes every feature

**Crash-isolation (D-03 / RBT-04):** the console imports ONLY `Flask` + `segugio.opcomm` — never `ultralytics/torch/cyndilib/obsws/cv2`. A UI exception can never reach the director. The *only* coupling is the atomic-file channel in `channel_dir`. **Therefore every new visibility feature must arrive over a new file/stream channel published BY the orchestrator, decoded by the browser — never by importing orchestrator code into Flask.** This is the central design node (PROJECT.md "Nodo di design chiave") and it gates the complexity of every row below.

---

## Feature Landscape

### Table Stakes (an operator expects these the moment you call it a "regia")

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multiview: live thumbnails of all cameras** | The #1 thing every switcher operator sees. Override is meaningless if you can't see what you're switching to. Today the console is blind. | **HIGH** | The big lift. Needs the new frame/thumbnail channel from the orchestrator (the design node). Cheapest viable: orchestrator writes small periodic JPEGs per cam to `channel_dir` → Flask serves them / MJPEG. Does NOT need full framerate — 2-5 fps thumbnails are enough for oversight. **Reuse frames the AI already decoded** (no third decode). |
| **Clear LIVE / tally indicator (which cam is PGM)** | Universal broadcast convention (red tally = on air). The operator must never be unsure what's aired. | **LOW** | Data already present: `status.live_cam`. Just render a red border/badge on the matching multiview tile + a big "ON AIR: CAM X" banner. Pure CSS over existing `/status` poll. |
| **Per-feed alive/dead at a glance** | A dead feed is the live-failure mode; operator must spot it instantly (NDI 75-min "frozen frame" gotcha). | **LOW** | Already in `status.alive` and already rendered as pills. Promote it onto the multiview tiles (grey-out / "MORTO" overlay on the dead tile). |
| **The REASON the auto-director chose the live cam** | This is the *defining* expectation of an AI-oversight UI ("...and why"). Already half-built: `status.reason` (auto/override/subject-lost/feed-dead/shutdown). | **LOW** | Already in `DirectorStatus.reason`. v1.1 just renders it prominently and in plain Italian ("Auto: miglior inquadratura", "Override operatore", "Soggetto perso → SAFE"). Zero orchestrator change for the basic version. |
| **Override buttons become informed (thumbnail, not blind text)** | Pressing "Forza CAM Low" blind is the current pain. Switchers put live thumbnails on the buttons. | **MEDIUM** | Mostly *free once multiview exists*: make each multiview tile clickable = the force command for that cam. Folds the existing `/command` force-btn logic onto the tiles. Keep "Rilascia (auto)" as a distinct control. |
| **Run / timer state visible** | Operator entering scores needs to know if a run is active and the clock. | **LOW** | Run start/stop already posts `RunState`. v1.1 surfaces current run state + elapsed timer read-back. Can be added to `DirectorStatus` (running bool + start tick) or derived client-side from the start press. |
| **Score / overlay preview (what will appear on the OBS overlay)** | Operator enters scores blind today; broadcast operators always preview lower-thirds before air. PROJECT.md explicitly lists "Preview del punteggio". | **LOW-MEDIUM** | The renderer `render_overlay_text(doc)` ALREADY exists and is importable in Flask (it's in `segugio.ui`, no heavy deps). Render the same string live in the form as the operator types — **no orchestrator round-trip needed**. A near-free win. |
| **Tablet-friendly responsive restyle** | The console runs on an operator tablet over WiFi LAN (app.py binds 0.0.0.0:8080 "tablet over the dedicated WiFi"). Current CSS is desktop-form-ish. | **MEDIUM** | Pure front-end. Big touch targets for override, multiview grid that reflows, score form usable one-handed. No backend change. Listed explicitly in PROJECT.md v1.1 targets. |

### Differentiators (sets Segugio's oversight UI apart — aligns with Core Value "la camera giusta, e *perché*")

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-camera framing-score bars (live "why" leaderboard)** | The honest, explainable version of "why this cam": show each camera's smoothed `CameraScore.score` as a bar + its `status` (tracking/coasting/lost). Operator *sees* why CAM Wide beat CAM Low this instant. Exactly the "confidence/intent visible" that Visor markets. | **MEDIUM** | Data exists (Phase 2 output) but is currently dropped. Requires extending the published status (add per-cam score+status to `DirectorStatus` / a sibling file). Cheap to compute (already computed), moderate to wire + render. **Highest-value differentiator** — turns the panel from "see" into "understand". |
| **Dog-lock / tracking overlay on the multiview tile** | Draw the bbox (or a lock dot) on the live thumbnail so the operator sees the system *is* locked on the in-competition dog, not a spectator dog/handler (the competitor-lock domain problem). | **MEDIUM-HIGH** | `DetectionSignal` cx/cy/w/h is normalized [0,1] → trivially drawable as a CSS/SVG box over a tile, **no image processing in Flask**. Needs the box coords added to the published channel. Pairs naturally with multiview. Big trust win; defer if thumbnail channel slips. |
| **"What auto WANTS vs what's aired" (override divergence hint)** | While overridden, show what auto *would* pick now, so the operator knows when it's safe to release. Visor's "what the AI wants next". | **MEDIUM** | The FSM knows the auto-candidate even while override is held; publish it alongside `live_cam`. Helps the operator release confidently → keeps the system in auto more (Core Value). |
| **Switch-history / recent-cuts strip** | A small timeline of recent camera cuts + reasons; lets the operator judge if the director is "twitchy" and intervene. | **MEDIUM** | Append-only; could be a small ring in `DirectorStatus`. Nice for tuning hysteresis in the field, but not essential to "see+override". |

### Anti-Features (commonly requested here, but wrong for THIS console)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Rebuild OBS / full PGM video monitor in the console** | "I want to see the actual program output." | Out-of-scope by design; duplicates OBS, demands full-framerate low-latency video into Flask, and tempts importing heavy deps → **breaks crash-isolation**. OBS already *is* the program monitor. | Low-fps thumbnails for *oversight only*; the real program lives in OBS/its multiview. Optionally embed OBS's own MULTIVIEW (already a scene per OBS-05) on a second display. |
| **Any scoring CV (auto-count catches, detect faults, read the clock)** | "If it sees the dog, make it score the run too." | Explicitly out-of-scope (SCR-04: "il sistema mostra i punteggi, non li calcola né giudica"). Adds CV risk, latency, and judging liability. | Manual score entry (already built). Console only *previews* the manual score. |
| **Full director-tuning panel (edit alpha/hysteresis/dwell live from console)** | "Let me tune switching from the tablet." | Those live in config YAML with fail-fast validation (CFG-01); a live mutation path would be a new write channel into the decision core + a new failure surface, and contradicts the crash-isolated read-mostly console. | Read-only score bars + switch history give the *insight* to tune; tuning stays in YAML between runs. |
| **High-framerate / glass-to-glass-accurate preview in the browser** | "The thumbnails lag." | Pushing real-time video through Flask invites the second/third decode, bandwidth on the contended WiFi, and latency the panel doesn't need. Oversight ≠ program. | 2-5 fps JPEG/MJPEG thumbnails; accept lag, label them "anteprima". |
| **Auth / user accounts / multi-operator** | "Secure it." | The dedicated WiFi LAN is the documented trust boundary (D-02, T-05-05-04); no-auth is an accepted v1 decision, not an oversight. Adding it now is scope creep. | Keep LAN-as-boundary; revisit only if the deployment model changes. |
| **WebSocket push for everything** | "Polling is old-fashioned." | The existing 1s `/status` poll is robust and crash-safe ("a poll error never breaks the page"). Full WS adds a stateful channel + reconnect logic for marginal gain on a 1-5 fps oversight UI. | Keep polling for status/scores; use **one** dedicated MJPEG (or periodic-JPEG) channel *only* for thumbnails, where streaming actually helps. |

---

## Feature Dependencies

```
[New frame/thumbnail channel from orchestrator]   <- THE design node (D-03 safe)
    +--enables--> [Multiview thumbnails]
                      +--enables--> [Tally/LIVE border on tiles]
                      +--enables--> [Informed override = clickable tiles]
                      +--enables--> [Dog-lock bbox overlay on tile]

[Extend DirectorStatus published fields]
    +--enables--> [Per-camera framing-score bars]
    +--enables--> [Auto-wants-vs-aired divergence hint]
    +--enables--> [Run/timer read-back]
    +--enables--> [Switch-history strip]

[render_overlay_text (ALREADY in segugio.ui)]
    +--enables--> [Score/overlay preview]   (NO orchestrator change)

[Tablet responsive restyle] --enhances--> everything (independent, front-end only)

[Multiview thumbnails] --conflicts--> [Full PGM video monitor]  (pick oversight, not program)
```

### Dependency Notes

- **Everything visual on the camera side requires the new publish channel.** Per-cam thumbnails AND bbox coords AND per-cam scores all flow over a channel the orchestrator must add without the console importing orchestrator code. Designing this channel (periodic JPEG-in-`channel_dir` vs MJPEG endpoint vs embedding OBS multiview) is the **gating Phase** — it must land first.
- **Tally, informed override, and bbox overlay are cheap GIVEN multiview.** They are render/CSS work on top of the same channel — they should ship in the same phase as multiview, not before.
- **Score-bars + reason + run-state share one channel extension.** They're all just more fields on `DirectorStatus` (or a sibling status file) over the existing `/status` poll — bundle them. The orchestrator already computes the score/status values (Phase 2/4); it just stops discarding them.
- **Score preview is independent and free-est.** `render_overlay_text` is already importable in Flask with no heavy deps → can ship in any phase, even standalone. A good early confidence-builder.
- **Restyle is independent** (pure front-end) and can run in parallel / last.

---

## MVP Definition

### Launch With (v1.1 — the set that makes the operator "see + understand + override informed")

- [ ] **New crash-safe frame/thumbnail publish channel** — gating; without it the console stays blind. Decide JPEG-in-channel_dir vs MJPEG vs OBS-multiview-embed.
- [ ] **Multiview thumbnails of all cameras** — the core "see".
- [ ] **LIVE/tally indicator on the live tile** — already-have `live_cam`, trivial render; safety-critical clarity.
- [ ] **Dead-feed indication on tiles** — already-have `alive`; the live-failure signal.
- [ ] **Reason rendered in plain language** — already-have `reason`; the core "understand", near-free.
- [ ] **Informed override = clickable tiles + keep Rilascia** — the core "override informed".
- [ ] **Per-camera framing-score bars** — the *honest* "why"; data already computed, just publish+render. This is what separates Segugio's oversight UI from a dumb thumbnail wall.
- [ ] **Score/overlay preview** — listed in PROJECT.md; free via existing renderer.
- [ ] **Tablet responsive restyle** — listed in PROJECT.md; it runs on an operator tablet.

### Add After Validation (v1.x)

- [ ] **Dog-lock bbox overlay on tiles** — high trust value; add once thumbnails + the box-coord channel are proven. (Could make MVP if the box coords ride the same status extension cheaply.)
- [ ] **"Auto wants vs aired" divergence hint** — add once operators ask "is it safe to release?"
- [ ] **Switch-history / recent-cuts strip** — add when field-tuning hysteresis becomes the workflow.

### Future Consideration (v2+)

- [ ] **Embed OBS MULTIVIEW scene** as an alternative/secondary monitor — defer; depends on output/streaming decisions still out-of-scope.
- [ ] **Pose/disc-aware framing visualization** — only meaningful after the pose/disc differentiators (themselves later milestones) land.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| New frame/thumbnail publish channel | HIGH (enabler) | HIGH | P1 |
| Multiview thumbnails | HIGH | HIGH (rides the channel) | P1 |
| LIVE/tally indicator | HIGH | LOW | P1 |
| Dead-feed on tile | HIGH | LOW | P1 |
| Reason in plain language | HIGH | LOW | P1 |
| Informed override (clickable tiles) | HIGH | MEDIUM | P1 |
| Per-camera score bars | HIGH | MEDIUM | P1 |
| Score/overlay preview | MEDIUM | LOW | P1 |
| Tablet responsive restyle | MEDIUM | MEDIUM | P1 |
| Dog-lock bbox overlay | HIGH | MEDIUM-HIGH | P2 |
| Auto-wants-vs-aired hint | MEDIUM | MEDIUM | P2 |
| Switch-history strip | MEDIUM | MEDIUM | P3 |
| Embed OBS multiview | LOW (dup) | MEDIUM | P3 |

**Priority key:** P1 = must have for v1.1 launch · P2 = add after validation · P3 = future.

---

## Competitor / Convention Feature Analysis

| Feature | Broadcast switchers (vMix / ATEM / OBS) | AI-director UIs (Visor / SmartMix) | Segugio v1.1 Approach |
|---------|------------------------------------------|------------------------------------|-----------------------|
| See all cameras | Multiview, customizable PVW/PGM | Source tiles | Low-fps oversight thumbnails (not full program) |
| Tally / what's live | Red tally, PGM bus | Always-visible "what's live" | Red border + ON AIR banner from `live_cam` |
| Why this shot | n/a (human decides) | "what the AI wants next, and why" + confidence | `reason` + **per-cam score bars** (the explainable core) |
| Informed buttons | Live-thumbnail buttons | Click source to take | Clickable multiview tiles = force command |
| Pause / take control | T-bar / cut bus | "pause automation instantly, take manual control" | Force CAM (override) + Rilascia (auto), already built |
| Overlay / lower-third preview | Title preview before air | n/a | Live score preview via existing `render_overlay_text` |
| Don't duplicate | (they ARE the switcher) | (some embed full PGM) | **Explicitly do NOT rebuild OBS** — OBS stays the program hub |

---

## Sources

- **Existing system (HIGH — read from source):** `src/segugio/ui/app.py` (routes + crash-isolation contract D-03), `src/segugio/ui/templates/console.html` (current 4 concerns), `src/segugio/opcomm/records.py` (`DirectorStatus` D-11: live_cam/reason/alive; `ScoreDoc`, `RunState`, `OperatorCommand`), `src/segugio/framing/signals.py` (`CameraScore` score+status, `DetectionSignal` normalized bbox), `.planning/PROJECT.md` (v1.1 targets, design node, out-of-scope SCR-04 / no-OBS-rebuild / LAN-as-boundary).
- **Switcher / multiview conventions (MEDIUM):** [vMix](https://www.vmix.com/software/download.aspx) (multiview, live-thumbnail buttons), [Blackmagic ATEM Software Control](https://www.blackmagicdesign.com/products/atemconstellation/softwarecontrol) (preview/program, multi-view out), [Tally Arbiter](https://tallyarbiter.com/) (tally across ATEM/vMix/OBS).
- **AI-director oversight UIs (MEDIUM):** [Visor — AI Direction for Live Streaming](https://www.visorai.org/) ("know what is live, what Visor wants next, and why; pause automation instantly"), [SmartMix Director](https://smartmixdirector.framer.website/) (real-time auto-switching + manual override), [AVer — automatic camera switching guide](https://www.aver.com/AVerExpert/multi-camera-switcher).

---
*Feature research for: live multi-camera auto-director oversight console (Segugio v1.1)*
*Researched: 2026-06-13*
