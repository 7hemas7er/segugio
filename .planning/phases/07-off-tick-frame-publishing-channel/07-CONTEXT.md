# Phase 7: Off-tick Frame-Publishing Channel - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 builds the **GATING foundation** for every v1.1 visual feature: a new off-tick publishing channel that exposes what the orchestrator already computes — downscaled per-camera JPEG thumbnails plus a per-camera "why" sidecar (`preview.json`) — to the crash-isolated Flask console, **proven never to steal time from the director's critical tick** (RBT-05 unchanged with preview ON) and **never to widen the console's import surface** (console stays `Flask + segugio.opcomm` only). Delivers PRV-01, PRV-02, PRV-03.

This is a **publish-and-render problem, not a compute one**: the per-camera framing scores, dog bbox, FSM auto-candidate, and decoded frames already exist inside the tick — v1.0 simply discards them. Phase 7 exposes them over a new binary atomic-file channel and a typed sidecar; nothing the operator *sees* renders until Phase 8/9.

The work maps to research build-order steps 1–4 (`.planning/research/v1.1/ARCHITECTURE.md` §"Build Order"):
1. `atomic_write_bytes` (binary sibling of `atomic_write_text`, `opcomm/atomic.py`)
2. `PreviewDoc` record + `read_preview`/`write_preview` (`opcomm/records.py` + `channel.py`)
3. `PreviewPublisher` daemon thread (`orchestrator/preview.py`) — latest-only mailbox + resize/encode/atomic-write + fault-coast
4. Wire the publisher into `loop.py` (`_tick_once` `offer(...)`, guarded) + `runtime.py`/`shutdown()` so a real `python -m segugio` run writes files to `opcomm/preview/`

**NOT in this phase (Phase 8/9):**
- **No console serving routes** — `GET /preview`, `GET /preview/<cam>.jpg` are Phase 8 (MVW-01).
- **No `console.html` multiview grid / template changes / tablet restyle** — Phase 8/9.
- **No preview-bandwidth hard cap** — Phase 8 (the cap + real-WiFi validation with phones).
- **No `threaded=True`/Waitress server fix** — Phase 8 (UXT-02; it only matters once the console serves a stream/long GET).
- **No v1.1 threat re-evaluation** — Phase 8.
- **No live operator kill-switch / freshness staleness UI** — Phase 9 (UXT-03).
- **No new detection/scorer/FSM logic** — the brains are locked; Phase 7 only *exposes* their outputs.

</domain>

<decisions>
## Implementation Decisions

### Transport & channel shape (locked by milestone research — carried forward, not re-litigated)
- **D-01: Transport = per-camera JPEG files in `opcomm/preview/` over the existing atomic-file channel.** Research Option (a), chosen over MJPEG/WebSocket (two new deps + a network server on the never-crash director) and OBS-multiview-embed (can't feed a browser without the obs-websocket boundary the console is forbidden to cross). The console only `send_file`s bytes — its import set does not change. See `.planning/research/v1.1/ARCHITECTURE.md` §"Option Comparison".
- **D-02: Latest-only single-slot mailbox for the tick→publisher hand-off.** The tick's only added cost is a non-blocking `offer(frames_by_cam, scores, dets_by_cam)` — a locked dict ref-assignment, last-writer-wins, frame-drop allowed. ALL resize/encode/fsync/IO happen on the `PreviewPublisher` daemon thread. The tick never waits on the publisher (Anti-Pattern 2).
- **D-03: The "why" data travels in a NEW `preview.json` sidecar, never in `status.json`.** `status.json`/`DirectorStatus` stays **byte-stable and write-on-change** (safety-critical reverse channel the FSM/watchdog depend on). `PreviewDoc` mirrors `DirectorStatus` exactly: `@dataclass(frozen=True)`, normalizing `__post_init__`, a safe-default reader (`read_preview`) that returns an empty default on absent/torn/malformed and **never raises into the loop** (RBT-04). The cuts ring + FSM auto-candidate live HERE, per ROADMAP criterion 4 (resolves the SUMMARY's "ring in DirectorStatus" note in favor of the roadmap).
- **D-04: `atomic_write_bytes` reuses the proven temp→`os.replace` primitive, but DROPS `fsync` for the ephemeral JPEGs and KEEPS it for `preview.json`.** The JPEGs are disposable (regenerated every frame) so durability does not matter; `preview.json` keeps fsync. **This fsync-drop MUST be documented in `atomic_write_bytes` so it is not silently reverted** (STATE.md carry-forward, 2026-06-13). The Windows `_atomic_replace` MoveFileEx-retry covers the open-read-close race against the console reader.

### Preview fidelity defaults (the smoothness↔WiFi-safety knob)
- **D-05: Default fidelity = ~5 fps / 384px-wide thumbnails / JPEG quality ≈ 55** → ~0.3–0.8 MB/s total for 4 cams. The research "Balanced" point: smooth enough for an operator to judge an override, comfortable headroom on the dedicated WiFi 6 LAN. These are **config defaults in an additive sub-model** (same additive pattern as `ScorerParams`/`TrackingParams` — e.g. `PreviewParams{fps, max_width, jpeg_quality, enabled}`), tunable without code edits. Phase 8 owns the HARD bandwidth cap + real-phone validation; Phase 7 just sets the starting point.

### Enable posture
- **D-06: `preview.enabled` defaults to ON.** The whole point of v1.1 is the live console, and the HARD RBT-05 gate proves preview ON does not regress the loop. The publisher coasts on any encode/IO fault (RBT-04 extended). When `enabled: false`, the orchestrator is **byte-identical to v1.0** — no daemon thread constructed, no mailbox, no per-tick `offer()` (guard: `if self._preview is not None: ...`). Real-WiFi bandwidth validation remains a Phase 8 acceptance gate (no real phones until the hardware milestone, so Phase 7's only ON-risk is CPU/latency, which the RBT-05 gate measures).

### Sidecar "why" payload scope
- **D-07: Publish the FULL "why" payload in Phase 7**, even though Phase 8/9 render it. `preview.json` carries per-camera: framing score (+ EMA), tracking state (tracking/coast/lost), `locked`/`track_id`, motion energy, in-zone flag, **normalized dog bbox**, plus the top-level **FSM auto-candidate** and a **recent-cuts ring (depth ~16)**. Phases 8/9 become pure render work — the orchestrator + sidecar contract is NOT reopened in a later phase. Roadmap criterion 4 specifies exactly this content for Phase 7.
- **D-08: Recent-cuts ring depth = ~16 entries.** Each entry is small (tick, from→to camera, reason). Enough to read the director's rhythm across a full ~60–90s disc-dog/agility run (feeds Phase 9's MVW-05 switch-history strip + "is the director nervous?" judgement) without bloating a JSON rewritten every tick. The ring is maintained on the publisher/orchestrator side and serialized into `preview.json`.

### Scope boundary ("done" line for the verifier)
- **D-09: Phase 7 = channel (steps 1–4) wired into the REAL run path + both HARD gates.** "Done" means: a real `python -m segugio <config>` launch writes per-camera JPEGs + `preview.json` into `opcomm/preview/` (files observable on disk), AND (gate 1) re-running the RBT-05 latency harness (`run_measured` / `tests/test_latency.py -m gpu`) shows the 4-camera p95 unchanged within noise with preview ON, AND (gate 2) the crash-isolation import test proves `import segugio.ui` resolves + the console starts with `ultralytics`/`torch`/`numpy`/`cv2`/`cyndilib` uninstalled. The `threaded=True` fix, console routes, bandwidth cap, and threat re-eval are explicitly **out** (Phase 8).

### Claude's Discretion (planner / research decide the details)
- **Mailbox implementation** — a `threading.Lock` + 1-slot attribute vs `queue.Queue(maxsize=1)` + `put_nowait`/`except Full: pass`. Equivalent; planner's call. The ONLY invariant: the tick never blocks.
- **Frame-snapshot safety** — if the real `FrameSource` reuses numpy buffers, `.copy()` when offering (cheap memcpy vs YOLO) or copy on the publisher right after grabbing the slot (Anti-Pattern 5). Confirm the cyndilib `NdiFrameSource.latest()` buffer-reuse semantics during planning.
- **Cache-bust token** — a separate `gen.txt` monotonic generation file vs reusing the `tick`/`gen` field already inside `PreviewDoc` for the console's `?t=` cache-bust (Phase 8 consumes it). Prefer the in-sidecar token if it avoids an extra file; planner's call.
- **`atomic_write_bytes` fsync seam** — whether it takes an `fsync: bool = True` param (publisher passes `False` for JPEGs) or there are two functions. Either is fine as long as D-04's drop-for-JPEG/keep-for-json split is explicit and documented.
- **Where the publisher pulls the N camera frames** — the batched path already builds `frames_by_cam` in `_fan_out`; the serial path pulls per-camera. Surface a single `frames_by_cam` dict to `offer()` cheaply without duplicating `source.latest()` calls.
- **Exact `PreviewParams` field names / config placement** — additive sub-model, tuned opportunistically (mirror `ScorerParams`/`TrackingParams` placement).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-7 scope & requirements
- `.planning/ROADMAP.md` §"Phase 7: Off-tick Frame-Publishing Channel" — the goal, the 5 success criteria (the two HARD gates: RBT-05 unchanged with preview ON; crash-isolation import test with the heavy stack absent), and the dependency note (Phase 6 latency loop + Phase 5 opcomm channel).
- `.planning/REQUIREMENTS.md` §"Canale di pubblicazione frame (PRV)" — **PRV-01** (off-tick JPEG publish, separate bounded media dir, RBT-05 invariant), **PRV-02** (`preview.json` sidecar `PreviewDoc`, frozen, safe-default reader, the exact per-camera payload + cuts ring, separate from `status.json`), **PRV-03** (`atomic_write_bytes` no-fsync-for-frames + the console crash-isolation import test).

### The load-bearing v1.1 milestone research (read in full — this phase is its build-order steps 1–4)
- `.planning/research/v1.1/ARCHITECTURE.md` — **THE design doc for this phase.** §"Architectural Patterns" (Pattern 1 latest-only mailbox with the concrete `offer()`/`_run()` code; Pattern 2 `atomic_write_bytes` with the fsync note; Pattern 3 the `PreviewDoc` sidecar sketch), §"Data Flow" (the new path diagram + the status.json-vs-sidecar A/B comparison → recommend sidecar), §"Anti-Patterns" (1: console importing cv2/numpy; 2: encoding on the tick thread; 3: bloating status.json; 5: reusing a mutable frame buffer without a snapshot), §"Build Order" (steps 1–4 = Phase 7; step 4 is the only hot-path touch and MUST be gated by re-running the RBT-05 harness), §"Why this provably respects the invariants".
- `.planning/research/v1.1/PITFALLS.md` — the integration-boundary failure modes (encoding on the tick busts RBT-05; importing cv2 into Flask breaks RBT-04; preview competing with NDI HX3 on saturated WiFi; the latent `app.run()` without `threaded=True`) and each one's prevention.
- `.planning/research/v1.1/SUMMARY.md` — the milestone executive summary (publish-and-render not compute; no new runtime deps; the two near-free quick wins; the dominant risks). NOTE: SUMMARY says the cuts ring lives in `DirectorStatus` — **superseded by ROADMAP criterion 4 / D-03/D-07: the ring lives in `preview.json`.**
- `.planning/research/v1.1/STACK.md` — the no-new-runtime-deps verdict (`cv2.imencode`/`numpy` already in the orchestrator; `atomic_write_bytes` stdlib-only; `waitress` is an optional Phase-8 deploy extra, NOT Phase 7; MJPEG/WebSocket rejected).

### v1.0 code the channel extends (read directly — these ARE the seams)
- `src/segugio/opcomm/atomic.py` — the proven `temp → flush → os.fsync → os.replace` primitive + the `_atomic_replace` Windows MoveFileEx-retry + `_temp_path` same-dir-hidden-temp rule. `atomic_write_bytes` is the binary sibling (Pitfall 6 / WR-04 retry reused verbatim).
- `src/segugio/opcomm/records.py` — `DirectorStatus` is the EXACT template for `PreviewDoc` (frozen dataclass, normalizing `__post_init__`, str-keyed dict normalization for hashability/`==`). `Discipline`/`ScoreDoc` show the str-Enum + frozen convention.
- `src/segugio/opcomm/channel.py` — `_read_json` (the single torn/absent/malformed→`None` boundary) + `read_status`/`write_status` are the EXACT template for `read_preview`/`write_preview` (safe-default, never-raise).
- `src/segugio/orchestrator/loop.py` — `Orchestrator._tick_once` (where the guarded `offer(...)` goes, AFTER `self._apply`), `_fan_out`/`_batched_inference` (where `frames_by_cam` + `dets_by_cam` already exist), `run`/`run_measured`/`shutdown` (publisher start/stop lifecycle), and the RBT-04 per-tick fault-isolation pattern the publish path must mirror. `run_measured` is the RBT-05 gate harness (gate 1).
- `src/segugio/orchestrator/runtime.py` — `build_orchestrator` (where the publisher is constructed + injected; the `*_factory` injectable-seam pattern for headless tests) + `_channel_paths` (extend with the `preview/` media dir).
- `src/segugio/ui/app.py` — the crash-isolation contract: imports ONLY Flask + `segugio.opcomm`, Flask imported INSIDE `create_app`. Phase 7 does NOT add routes here; the import test (gate 2) just LOCKS this clean surface as a regression gate before Phase 8 widens it.
- `src/segugio/ndi/source.py` — the `FrameSource` Protocol (`latest`/`last_frame_ts`); confirm buffer-reuse semantics of the real `NdiFrameSource.latest()` for the snapshot decision (Anti-Pattern 5).

### Prior-phase decisions this phase inherits
- `.planning/phases/05-integration-ndi-mock-orchestrator-obs-score-ui/05-CONTEXT.md` — **D-03** (the UI is a SEPARATE PROCESS communicating ONLY via atomic files — the crash-isolation invariant Phase 7 must preserve), **D-11** (the `status.json` reverse channel `preview.json` sits beside, never inside), and the lazy-import-boundary + GPU-marker test-split patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`opcomm/atomic.py:atomic_write_text` + `_atomic_replace` + `_temp_path`:** `atomic_write_bytes` is a near-copy — open `"wb"`, write bytes, (conditionally) fsync, route the swap through the SAME `_atomic_replace` retry. Windows sharing-violation handling comes free.
- **`opcomm/records.py:DirectorStatus`:** the exact frozen-dataclass + normalizing-`__post_init__` template for `PreviewDoc`. Copy the dict-normalization trick (str keys, immutable-by-convention) so round-trip equality tests work.
- **`opcomm/channel.py:_read_json` + `read_status`/`write_status`:** the safe-default never-raise boundary `read_preview`/`write_preview` replicate verbatim.
- **`orchestrator/loop.py` fan-out:** `frames_by_cam` is already assembled in `_batched_inference`; `dets_by_cam` + `scores` are already produced each tick. `offer(...)` consumes exactly these — no new computation, just a hand-off after `_apply`.
- **`orchestrator/runtime.py:build_orchestrator` `*_factory` seams:** the injectable-construction pattern for headless tests — inject a fake encoder/publisher so unit tests need no real `cv2`.

### Established Patterns
- **Lazy-import boundary (since 01-01):** the console (`segugio.ui`) and any unit test must `import` with `cyndilib`/`obsws`/`ultralytics`/`torch`/`cv2`/`numpy` ABSENT. `cv2.imencode`/`numpy` live ONLY inside `PreviewPublisher`'s publish method (the orchestrator side, which already imports them). The crash-isolation import test (gate 2) is the CI enforcement.
- **Additive config sub-model (`ScorerParams`/`TrackingParams`/`ActionHoldParams`):** `PreviewParams` follows the same shape — new keys, sensible defaults, no breakage to existing configs.
- **RBT-04 coast-don't-crash:** every publish is wrapped (`except Exception: logger.warning(...)`) exactly like every tick stage — a publisher fault coasts and is logged, never perturbs the director (PRV-01 criterion 5).
- **GPU-marker test split (`@pytest.mark.gpu`):** the RBT-05 gate (`tests/test_latency.py -m gpu`) runs only on the rig; headless mailbox/encode/sidecar unit tests always run (inject a fake encoder).
- **Determinism:** the orchestrator owns the clock/threads; the publisher's daemon owns its own `~1/fps` cadence. Mailbox/encode/sidecar logic stays injected-value-testable.

### Integration Points
- **Producer edge (Phase 7):** tick → `offer(frames_by_cam, scores, dets_by_cam)` (1-slot mailbox) → `PreviewPublisher` daemon → `cv2.resize`→`cv2.imencode`→`atomic_write_bytes(opcomm/preview/cam_<id>.jpg)` + `write_preview(opcomm/preview/preview.json)`.
- **Lifecycle:** `build_orchestrator` constructs the publisher (guarded by `preview.enabled`); `run`/`run_measured` start its thread; `shutdown()` stops/joins it.
- **Consumer edge (Phase 8, NOT now):** console `GET /preview/<cam>.jpg` `send_file` + `GET /preview` `read_preview` — the files Phase 7 writes are what Phase 8 serves.

</code_context>

<specifics>
## Specific Ideas

- **The channel is "the opcomm pattern, extended with bytes + one sidecar" — not a new IPC.** Reviewers should treat `atomic_write_text`/`DirectorStatus`/`read_status` as the literal templates; the win is that NOTHING about the trust boundary changes.
- **Step 4 is the only hot-path touch — measure it.** The single load-bearing risk is the `offer()` in `_tick_once` regressing RBT-05. The HARD gate is re-running `run_measured`/`test_latency.py -m gpu` with preview ON and showing p95 unchanged within noise.
- **Build the channel complete now; Phases 8/9 are pure render.** Full "why" payload (scores + bbox + auto-candidate + ~16-deep cuts ring) ships in `preview.json` in Phase 7 so the orchestrator contract is never reopened for the rendering phases.
- **`preview.json` ≠ `status.json` is the load-bearing separation.** The safety-critical, write-on-change `status.json` keeps its exact shape; the always-changing cosmetic data lives in the off-tick sidecar.

</specifics>

<deferred>
## Deferred Ideas

- **Console serving routes (`GET /preview`, `GET /preview/<cam>.jpg`) + multiview grid + LIVE/tally + dead-feed marking** — Phase 8 (MVW-01/02/03). Phase 7 writes the files; Phase 8 serves+renders them.
- **`threaded=True`/Waitress server fix (UXT-02)** — Phase 8. The latent `app.run()` single-worker bug only bites once the console serves a stream/long GET; pulling it into Phase 7 was explicitly declined to keep this phase "gating channel only".
- **Preview-bandwidth HARD cap + real-WiFi-with-phones validation** — Phase 8. Phase 7 sets tunable defaults (D-05); Phase 8 enforces the ceiling and validates the ≤5–8 Mbps budget with phones live (STATE.md carry-forward).
- **Live operator kill-switch for preview + freshness/staleness "never show a frozen frame as live" overlay** — Phase 9 (UXT-03 hygiene). The "ON + live kill-switch now" option was declined.
- **Explainability rendering (score bars, plain-Italian reason, dog-lock bbox overlay, "auto wants vs aired" hint, switch-history strip, live score-overlay preview)** — Phase 9 (WHY-01..04, MVW-04/05, SCV-01). The *data* for all of these ships in `preview.json` in Phase 7; only the rendering is deferred.
- **Re-verify BoT-SORT native ReID actually engages on `yolo26s` at startup** before depending on `locked`/`track_id` stability for the Phase 9 dog-lock bbox overlay — carried from STATE.md; relevant when Phase 9 renders the bbox, but the bbox *field* is published now.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 07-off-tick-frame-publishing-channel*
*Context gathered: 2026-06-13*
