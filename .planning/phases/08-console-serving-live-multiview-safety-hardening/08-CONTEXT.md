# Phase 8: Console Serving, Live Multiview & Safety Hardening - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 is where the crash-isolated console finally **consumes** the Phase 7 publishing channel and renders the first thing the operator actually needs: a **live, flicker-free multiview of every camera** with an unmistakable **LIVE/tally** indicator and at-a-glance **dead-feed marking**. It lands in the same phase the two safety controls the streaming endpoint makes mandatory — the **multi-threaded server** so a preview GET can never block an override POST, and a **hard preview-bandwidth cap** so the preview degrades on contended WiFi before the NDI feeds ever appear to die — plus a **written threat re-evaluation** now that live competitor video sits behind the `0.0.0.0` endpoint.

Delivers **MVW-01** (responsive CSS-Grid multiview, flicker-free refresh), **MVW-02** (LIVE/tally on the on-air tile), **MVW-03** (dead/stale feed marking), **UXT-02** (`threaded=True`/Waitress server fix so serving thumbnails never pins the lone worker and blocks the override).

This is a **publish-and-render / serve problem, not a compute one**: Phase 7 already writes the per-camera JPEGs + `preview.json` sidecar to `opcomm/preview/`. Phase 8 adds only **routes + a template** to the console — its import surface stays **`Flask + segugio.opcomm` only** (the crash-isolation contract is preserved by construction; the JPEG encode lives in the orchestrator, the console just `send_file`s bytes off disk).

**NOT in this phase (Phase 9):**
- **No clickable-tile override** — tiles are DISPLAY-ONLY this phase; the existing blind text override buttons (`Forza`/`Rilascia`) keep working. Clickable-tile force-cam is Phase 9 (MVW-04).
- **No explainability rendering** — no per-camera score bars (WHY-02), no plain-Italian reason (WHY-01), no dog-lock bbox overlay (WHY-03), no "auto wants vs aired" hint (WHY-04), no switch-history strip (MVW-05). The *data* for all of these already ships in `preview.json` (Phase 7 D-07); Phase 9 renders it.
- **No live score-overlay preview** as the operator types (SCV-01) — Phase 9.
- **No full tablet-first restyle** — Phase 8 ships only a minimal responsive grid; large touch targets, one-handed score form, full reflow polish are Phase 9 (UXT-01).
- **No long-run leak/sleep/freshness hygiene** — the multi-hour soak, sleep/wake resume, and the deep "never show a frozen frame as live" staleness overlay are Phase 9 (UXT-03). Phase 8 adds only the *basic* freshness gate that drives MVW-03 tile marking.
- **No new detection/scorer/FSM/orchestrator logic** — the brains and the channel are locked; Phase 8 is console-side serve + render + the two safety controls.

</domain>

<decisions>
## Implementation Decisions

### Bandwidth cap (MVW success criterion 4 — "preview degrades before the NDI feeds")
- **D-01: The cap is a STATIC engineered ceiling, not a runtime-adaptive throttle.** The Phase-7 `PreviewParams` defaults (fps × max_width × jpeg_quality) are chosen so the **computed** total preview bitrate for N cameras is provably ≤ the configured ceiling. A startup / config-validation check **rejects any config whose computed preview bitrate exceeds the cap** (fail-fast, same posture as the central config contract). No per-frame feedback loop, no dynamic fps/quality drop — that machinery would overlap Phase 9's "preview degrades first" hygiene (UXT-03) and adds moving parts to the never-crash side. Research: "pick a hard ceiling (≤ 5–8 Mbps total) and engineer to it."
- **D-02: Phase-8 acceptance bar for the cap = a headless computed-budget assertion + an explicit documented deferral.** A unit/headless test asserts the configured fps×res×quality yields ≤ the ceiling bitrate AND that an over-cap config is rejected. The real **WiFi-with-phones false-death-rate-unchanged** validation (roadmap criterion 4's "with phones live") is **explicitly documented as a hardware-milestone carry-forward** — consistent with all of v1 being software-complete on synthetic data (no real phones in dev). Do NOT build a synthetic network-contention harness for Phase 8 (rejected: build cost + questionable fidelity of "simulated WiFi contention").
- The hard ceiling value itself (the ≤ 5–8 Mbps figure) and the exact computed-bitrate formula are research/planner detail — anchor on the research budget; surface the ceiling as a config value.

### LIVE / tally & dead-feed marking (MVW-02 / MVW-03)
- **D-03: On-air tile emphasis = red border + LIVE badge + "ON AIR: CAM X" banner**, driven by `status.live_cam` (already exposed by `GET /status`). Triple-redundant so it is unmistakable at a glance on a tablet in field light. This is the roadmap-specified treatment — locked, not re-litigated. The banner stays minimal ("ON AIR: CAM X"); the plain-Italian *reason* render is Phase 9 (WHY-01).
- **D-04: A tile reads "MORTO" (dead) when `status.alive[cam]` is false OR the preview is stale.** Belt-and-suspenders: catches both a watchdog-confirmed dead feed AND a silently-frozen preview that the watchdog still believes alive. MVW-03 names both inputs ("status.alive + preview freshness"); both land in Phase 8. The deeper "never show a frozen frame as live" staleness *overlay* hygiene stays Phase 9 (UXT-03) — Phase 8 ships only the basic freshness gate for tile marking.
- **D-05: Preview-staleness window = ~2–3× the publish interval, computed FROM the configured fps (not a hardcoded ms).** At ~5 fps publish (~200 ms interval) that is ~0.6–1 s of no-new-frame before a tile flips to MORTO. Tolerates normal jitter / one or two dropped frames without false MORTO, but flags a genuine freeze within ~1 s. Freshness is judged from the preview's own generation/tick token or JPEG mtime (Claude/planner picks the exact source — see Discretion).

### Console layout & scope (MVW-01)
- **D-06: Page composition = multiview grid ON TOP, existing controls BELOW.** The cameras + "ON AIR" banner stay in the first tablet viewport; the score / run / override forms scroll beneath. Extend the existing single `console.html` page — do NOT reframework it (research STACK). Side-by-side columns were rejected as Phase-9 restyle territory.
- **D-07: Phase 8 ships a MINIMAL responsive grid only; tiles are strictly display-only.** CSS-Grid `repeat(auto-fit, minmax(...))` that reflows 1→2→4 columns by viewport, with the LIVE/dead marking — and nothing more. The existing blind text override buttons keep working (override capability is never lost). The full tablet-first restyle (large touch targets, one-handed score form) and clickable tiles are Phase 9 (UXT-01 / MVW-04). This keeps the phase boundary crisp against MVW-01/02/03 + UXT-02.

### Server safety control (UXT-02)
- **D-08: `threaded=True` is the in-code safety control; Waitress is an OPTIONAL deploy extra, never a hard console dep.** The latent `create_app(_dir).run(host="0.0.0.0", port=8080)` in `ui/app.py` is single-threaded — concurrent `/preview/<cam>.jpg` GETs (4 tiles × refresh × tablet(s)) can pin the lone worker and stall the safety-critical `/command` override POST. Phase 8 lands `threaded=True` at minimum. `waitress` is packaged as an optional `console`/`serve` extra (e.g. in `pyproject.toml`) for the Windows production deploy — **the console must still run on the bare Flask dev server with only Flask importable**, to keep the crash-isolation surface auditable (research STACK §"do not pre-optimize"). Transport stays **polling JPEG files** (Phase 7 D-01), NOT MJPEG — so Waitress's no-streaming limitation is a non-issue.
- The "override served promptly while a preview stream is active" guarantee (success criterion 3) should be proven by a test that POSTs `/command` while preview GETs are in flight and asserts it is not blocked.

### Threat re-evaluation (success criterion 5)
- **D-09: The written v1.1 threat re-eval ACCEPTS the LAN-as-trust-boundary and mandates AP client-isolation — no new auth/code.** It reaffirms v1.0's stance (T-05-05-04: the dedicated WiFi LAN is the trust boundary; no auth for a single-operator field tool is an accepted, documented decision, not an oversight), ADDS the new exposure — **live competitor video now sits behind `0.0.0.0`** — to the threat model, and makes it a **HARD operational requirement** that the dedicated AP enforces **client isolation** and is **not bridged to the internet or other networks**. Mitigation is operational (network setup) + documented; no configurable bind / basic-auth / shared-token added in v1.1 (rejected: re-litigates the accepted single-operator-LAN posture and adds code/config beyond the stated "written re-eval" deliverable).
- **Note:** Phase 7's `preview.enabled` already acts as the **source-side off-switch** — when false, no JPEGs are written so there is nothing to serve. No separate console-side preview kill-switch is needed in Phase 8 (a live operator kill-switch is Phase 9 / UXT-03).

### Claude's Discretion (planner / research decide the details)
- **Preview-route shape** — `GET /preview/<cam>.jpg` (whitelisted `send_file` against the known camera ids, `Cache-Control: no-store` or rely on the JS cache-buster) + `GET /preview` (returns the `preview.json` sidecar via `read_preview`). Exact route signatures, the camera-id whitelist source (config cameras), and 404 behavior on an unknown/absent cam are planner's call. The whitelist is the path-traversal mitigation — the operator never supplies a filesystem path.
- **Cache-bust mechanism** — reuse the in-sidecar `gen`/`tick` token from `PreviewDoc` for the `<img>` `?t=` swap (Phase 7 surfaced it) vs `Date.now()`. Prefer the in-sidecar token if it avoids drift; planner's call.
- **Freshness source for D-05** — the preview's `gen`/`tick` field from `preview.json` vs the served JPEG mtime. Pick whichever is cheapest and most reliable client- or server-side; the staleness *window* (D-05) is the locked part.
- **`Image()` preload-swap cadence** — the refresh fps the browser polls at (independent of the publish fps; bounded by it). Start at the publish cadence (~5 fps); tune in UAT.
- **Where the `threaded=True`/Waitress entrypoint logic lives** — keep the WSGI-server import inside the entrypoint (`__main__` / a serve function) to preserve the lazy import boundary, exactly like the existing `app.run()`.
- **Threat re-eval doc location** — the existing security/threat-model doc vs a new `docs/` file; criterion 5 only requires it "exists in the project docs." Planner's call; cross-reference the v1.0 T-05-05-* threats.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-8 scope & requirements
- `.planning/ROADMAP.md` §"Phase 8: Console Serving, Live Multiview & Safety Hardening" — the goal, the 5 success criteria (multiview grid + LIVE/tally + dead-feed marking; `threaded=True`/Waitress override-never-blocked; hard bandwidth cap; written threat re-eval), and the dependency on Phase 7's channel.
- `.planning/REQUIREMENTS.md` §"Multiview/console (MVW)" + §"UX/robustezza (UXT)" — **MVW-01** (responsive CSS-Grid multiview, flicker-free `Image()` preload+swap), **MVW-02** (LIVE/tally from `status.live_cam`), **MVW-03** (dead/stale marking from `status.alive` + preview freshness), **UXT-02** (`threaded=True`/Waitress; override POST never blocked). Lines 91–94, 111, 201–204.

### The load-bearing v1.1 milestone research (Phase 8 is its build-order steps 5–6)
- `.planning/research/v1.1/STACK.md` — **THE serving-decision doc.** `send_file`/`send_from_directory` (no decode, no new dep, `Cache-Control: no-store`); vanilla JS `Image()` preload + `src`-swap (flicker-free, `?t=` cache-bust); CSS Grid `repeat(auto-fit, minmax())` (responsive, query-light, "extend console.html, don't reframework"); the **polling-JPEG-files vs MJPEG/WebSocket** decision (polling wins: zero deps, reuses the atomic channel, runs on plain Waitress, smallest test surface; MJPEG is an evidence-gated fallback only); **Waitress as an optional deploy extra, NOT a hard console dep** (§ lines 76–94, 112, 123, 142–145, 158, 166–170).
- `.planning/research/v1.1/PITFALLS.md` — **Pitfall 1** (WiFi contention is the #1 domain risk; 3-4 phones already push 60–200 Mbps of NDI HX3 → treat preview byte budget as a first-class capped resource: ≤ 5–8 Mbps, low fps 3–8, 320–480px, JPEG q 50–70); **Pitfall 7** (`app.run()` without `threaded=True` — one long GET freezes the whole console incl. the override POST; the exact `ui/app.py:143` latent bug, the `threaded=True` minimum + Waitress + "control endpoints always answerable / cap concurrent preview connections" mitigations). Lines 9, 65–82, 159–179.
- `.planning/research/v1.1/ARCHITECTURE.md` — the data-flow diagram + the **consumer-edge build-order steps 5–6** (step 5: console routes `GET /preview` + `GET /preview/<cam>.jpg`, whitelisted `send_file`, re-confirm `import segugio.ui` resolves with torch/cv2/cyndilib absent; step 6: `console.html` multiview grid + cache-bust + highlight the live tile + tablet restyle) and the "crash-isolation preserved by construction — console gains routes+template, not imports" invariant (lines 55, 94, 197, 217–219, 236, 253, 307–308, 317).
- `.planning/research/v1.1/SUMMARY.md` — the milestone executive summary (publish-and-render not compute; no new runtime deps; the two near-free quick wins incl. the `threaded=True` fix; the dominant WiFi-contention risk).

### v1.0 code Phase 8 extends (read directly — these ARE the seams)
- `src/segugio/ui/app.py` — **THE file Phase 8 modifies.** Adds `GET /preview/<cam>.jpg` (whitelisted `send_file`) + `GET /preview` (`read_preview`) routes and the `threaded=True`/Waitress entrypoint fix at the bottom `if __name__ == "__main__"` block. Preserve the crash-isolation contract: Flask imported INSIDE `create_app`, console imports ONLY Flask + `segugio.opcomm`. The existing `GET /status` (`status.live_cam`/`reason`/`alive`) and the `/score` `/run` `/command` POSTs stay as-is. The documented `0.0.0.0` / LAN-trust-boundary / T-05-05-* security notes in this file's docstring are the basis for the D-09 threat re-eval.
- `src/segugio/ui/templates/console.html` — **THE template Phase 8 modifies.** A single inline-CSS Italian page (dark theme, score/run/override/status sections, `#stato` poll). Extend it: add the multiview grid ON TOP (D-06), `<img>` per camera + LIVE/dead marking, the `Image()` preload-swap JS. ~153 lines; keep it one self-contained page.
- `src/segugio/opcomm/channel.py` — `read_preview`/`read_status` (the safe-default never-raise readers the new routes call) — the `/preview` route serves `read_preview(...)`'s `PreviewDoc`.
- `src/segugio/opcomm/records.py` — `PreviewDoc` (the sidecar shape the console renders: per-camera score/state/bbox, FSM auto-candidate, cuts ring, and the `gen`/`tick` cache-bust/freshness token) + `DirectorStatus` (`live_cam`/`alive`/`reason`).
- `src/segugio/config/*` (the central pydantic config contract) — where `PreviewParams` lives; the **D-01 over-cap-config-rejection** check hooks into the same fail-fast loader (CFG-01 posture). Locate the existing `PreviewParams` sub-model (added Phase 7) before adding the bitrate-ceiling field/validation.

### Prior-phase decisions this phase inherits
- `.planning/phases/07-off-tick-frame-publishing-channel/07-CONTEXT.md` — **THE upstream contract.** D-01 (polling JPEG files transport — locked), D-05 (default fidelity ~5 fps / 384px / q≈55 → ~0.3–0.8 MB/s; "Phase 8 owns the HARD cap"), D-06 (`preview.enabled` source-side off-switch), D-07 (full "why" payload + bbox + auto-candidate + ~16-deep cuts ring already in `preview.json`), and its `<deferred>` section which pre-scoped exactly Phase 8's three deferrals (serving routes + grid + LIVE/dead marking; `threaded=True` UXT-02; bandwidth cap + real-WiFi validation).
- `.planning/phases/05-integration-ndi-mock-orchestrator-obs-score-ui/05-CONTEXT.md` — D-03 (the console is a SEPARATE PROCESS, crash-isolated, atomic-file channel only — the invariant Phase 8's new routes must not break), D-11 (`status.json` reverse channel), and the documented v1.0 security posture (T-05-05-* — the no-auth/LAN-trust-boundary basis the D-09 re-eval builds on).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`ui/app.py:create_app` factory** — the route-registration + `_path(name)` channel-dir helper are the exact seam for the two new GET routes; the Flask-imported-inside-factory pattern keeps `import segugio.ui` Flask-free (crash-isolation). The existing `/status` route is the template for `/preview` (read a safe-default opcomm record, `jsonify`).
- **`opcomm.channel.read_preview` + `read_status`** — safe-default, never-raise readers; the new `/preview` route is a thin wrapper around `read_preview`. No new IO code needed.
- **`opcomm.records.PreviewDoc`** — already carries everything the grid renders this phase (per-camera presence for the tile set) plus the `gen`/`tick` token for cache-bust + freshness (D-05). Phase 9 renders the rest of its payload; Phase 8 touches only what MVW-01/02/03 need.
- **`console.html` inline-CSS single page** — already dark-themed, responsive-ish (`.row` flex), with a `#stato` status poller. The multiview grid + LIVE/dead JS slot into the same `<style>`/`<script>` blocks — no build step, no framework.
- **Central pydantic config + `PreviewParams`** — the fail-fast loader is where the D-01 over-cap rejection lands (a validator that computes preview bitrate from fps×width×height×quality×N_cams and raises if > ceiling), mirroring CFG-01's "malformed config fails fast at startup."

### Established Patterns
- **Crash-isolation import boundary (D-03, since Phase 1):** the console imports ONLY `Flask + segugio.opcomm`; `send_file` moves bytes off disk, no `cv2`/`numpy`/`torch`. The Phase 7 crash-isolation import test (gate 2) is the regression gate — Phase 8 adds routes/template and must keep that test green (import resolves with the heavy stack absent).
- **Whitelisted server-side paths (T-05-05-01):** write paths are FIXED server-side and the operator never supplies a path. The new `GET /preview/<cam>.jpg` extends this: `<cam>` is whitelisted against the known camera ids (config), mapped to a constant `cam_<id>.jpg` filename — never used as a raw path (path-traversal mitigation).
- **Atomic-file channel:** Phase 7 writes the JPEGs + `preview.json` via `atomic_write_bytes`/`write_preview` (temp→`os.replace`, Windows MoveFileEx-retry) — the console's `send_file`/`read_preview` therefore never reads a torn frame or sidecar. No locking needed on the read side.
- **Fail-fast config validation (CFG-01):** a malformed config `SystemExit(2)`s at startup. D-01's over-cap check joins this — an over-budget preview config is a startup error, not a runtime surprise.

### Integration Points
- **Consumer edge (this phase):** browser `<img>` ~5 fps → `GET /preview/<cam>.jpg` → `send_file(cam_<id>.jpg)`; status/why poll → `GET /preview` → `read_preview(preview.json)` + existing `GET /status` → `read_status(status.json)`. The files Phase 7 writes are exactly what Phase 8 serves.
- **Server entrypoint (UXT-02):** `ui/app.py` `__main__` (and/or a `serve` function) — `threaded=True` on the dev server; optional `waitress.serve(...)` behind the `console`/`serve` extra, import kept inside the entrypoint.
- **Config edge (D-01):** the central config loader gains the preview-bitrate ceiling field + the over-cap rejection validator (same place `PreviewParams` lives).
- **Docs edge (D-09):** the threat-model doc gains the v1.1 live-video-behind-`0.0.0.0` re-eval + the AP-client-isolation hard requirement.

</code_context>

<specifics>
## Specific Ideas

- **"Extend, don't reframework."** The console stays one self-contained inline-CSS/JS Italian page (`console.html`). The multiview is a CSS-Grid section bolted on top of the existing forms — no SPA, no bundler, no new console dependency. The research is emphatic on this and on polling-files-over-MJPEG.
- **The cap is a config-time guarantee, not a runtime controller.** Phase 8 proves "preview degrades before the feeds" by *construction* (the configured fidelity's computed bitrate is asserted ≤ a hard ceiling, over-cap configs rejected) — not by a dynamic throttle. The live false-death validation waits for real phones (hardware milestone).
- **Override-never-blocked is the load-bearing safety property of this phase.** `threaded=True` exists so a preview GET can never pin the worker and stall a `/command` override — prove it with a test that POSTs `/command` while preview GETs are in flight.
- **Dead-feed marking is belt-and-suspenders.** `status.alive` (the director's verdict) OR a ~2–3×-interval preview-staleness gate — so neither a confirmed-dead feed nor a silently-frozen-but-"alive" preview slips through as a normal tile. The deeper staleness-overlay hygiene is Phase 9.
- **Security mitigation is operational, not in-code.** The dedicated AP enforcing client isolation + not being bridged is the v1.1 control for live competitor video; the written re-eval makes that a hard requirement and reaffirms the accepted single-operator-LAN no-auth posture.

</specifics>

<deferred>
## Deferred Ideas

- **Clickable-tile informed override** (tap a tile = force that camera, replacing the blind text buttons) — Phase 9 (MVW-04). Phase 8 tiles are display-only; the text override buttons stay.
- **Explainability render** — per-camera score bars (WHY-02), plain-Italian reason (WHY-01), dog-lock bbox overlay (WHY-03), "auto wants vs aired" hint (WHY-04), switch-history strip (MVW-05). All the *data* is already in `preview.json` (Phase 7 D-07); Phase 9 renders it.
- **Live client-side score-overlay preview** as the operator types (SCV-01, reuses `render_overlay_text`) — Phase 9.
- **Full tablet-first restyle** — large touch targets, one-handed score form, deep reflow polish (UXT-01) — Phase 9. Phase 8 ships only the minimal responsive grid.
- **Long-run hygiene** — multi-hour soak (no leak), sleep/wake resume, the deep "never show a frozen frame as live" staleness overlay + a live operator preview kill-switch (UXT-03) — Phase 9. Phase 8 adds only the basic freshness gate for tile MORTO marking.
- **Runtime-adaptive bandwidth throttle** (dynamically drop fps/quality as the cap is approached) — declined for Phase 8 in favor of the static engineered ceiling (D-01); reconsider only if real-WiFi UAT shows the static budget insufficient (overlaps UXT-03 "preview degrades first").
- **Synthetic network-contention harness** to validate the cap without phones — declined (D-02); real-WiFi-with-phones false-death validation is a hardware-milestone carry-forward.
- **MJPEG / WebSocket transport** — evidence-gated fallback only (research): adopt solely if polling-cadence UAT proves visibly choppy AND higher fps is genuinely wanted, accepting the held-thread model + a streaming-capable server (not Waitress).
- **In-code auth / configurable bind / shared-token gate** on the preview routes — declined for v1.1 (D-09); the LAN-as-trust-boundary + AP-isolation posture stands. Revisit only if the deployment context stops being a dedicated single-operator LAN.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 08-console-serving-live-multiview-safety-hardening*
*Context gathered: 2026-06-13*
