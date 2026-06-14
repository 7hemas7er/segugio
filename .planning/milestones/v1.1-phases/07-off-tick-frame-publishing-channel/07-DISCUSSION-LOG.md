# Phase 7: Off-tick Frame-Publishing Channel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 7-off-tick-frame-publishing-channel
**Areas discussed:** Preview fidelity defaults, Preview on/off posture, Sidecar 'why' scope + ring depth, Phase 7 scope boundary

---

## Area selection

The v1.1 milestone architecture is research-locked (`.planning/research/v1.1/ARCHITECTURE.md` maps Phase 7 to build-order steps 1–4). Carried forward without re-asking: JPEG-files-over-opcomm transport, latest-only mailbox, `preview.json` sidecar (not `status.json`), `PreviewDoc` mirrors `DirectorStatus`, fsync dropped for JPEGs / kept for the sidecar, whitelisted cam-id + fixed server-side filenames. The four areas below were the genuinely-open knobs + contract confirmations.

| Offered area | Selected |
|--------------|----------|
| Preview fidelity defaults | ✓ |
| Preview on/off posture | ✓ |
| Sidecar 'why' scope + ring depth | ✓ |
| Phase 7 scope boundary | ✓ |

**User's choice:** all four areas.

---

## Preview fidelity defaults

| Option | Description | Selected |
|--------|-------------|----------|
| Balanced | ~5 fps / 384px wide / JPEG q55 → ~0.3–0.8 MB/s for 4 cams. Research default — smooth enough to judge an override, comfortable WiFi 6 headroom. | ✓ |
| Feeds-first (lighter) | ~3 fps / 320px / q45 → max WiFi headroom for NDI HX3 feeds; choppier preview. | |
| Sharper monitor | ~8 fps / 480px / q60 → crisper/smoother monitor, more bandwidth; leans on Phase 8 cap. | |

**User's choice:** Balanced (Recommended).
**Notes:** Defaults live in an additive config sub-model (`ScorerParams`/`TrackingParams` pattern), tunable without code edits. Phase 8 owns the HARD bandwidth cap + real-phone validation; Phase 7 sets the starting point only.

---

## Preview on/off posture

| Option | Description | Selected |
|--------|-------------|----------|
| ON by default | Channel runs by default; HARD RBT-05 gate proves ON doesn't regress; `enabled:false` → byte-identical v1.0. | ✓ |
| Opt-in (OFF by default) | Ship the channel but require explicit `preview.enabled: true`; default launch = v1.0. | |
| ON + live kill-switch now | ON by default + an operator control to stop publishing live (pulls Phase 9 UXT-03 hygiene forward). | |

**User's choice:** ON by default (Recommended).
**Notes:** When disabled, no daemon thread / mailbox / per-tick `offer()` is constructed — the orchestrator is byte-identical to v1.0 (`if self._preview is not None` guard). Real-WiFi bandwidth validation stays a Phase 8 acceptance gate (no real phones until the hardware milestone). Live kill-switch deferred to Phase 9 (UXT-03).

---

## Sidecar 'why' scope + ring depth

### Question 1 — ring depth

| Option | Description | Selected |
|--------|-------------|----------|
| Last ~16 cuts | Enough to read the director's rhythm across a full ~60–90s run without bloating a per-tick JSON. | ✓ |
| Last ~8 cuts | Minimal; busy run scrolls older cuts out before the operator reads them. | |
| Last ~32 cuts | Longer history for field-tuning hysteresis; marginally more churn. | |

**User's choice:** Last ~16 cuts (Recommended).

### Question 2 — publish-now vs publish-when-rendered

| Option | Description | Selected |
|--------|-------------|----------|
| Full payload now | Publish score + tracking state + normalized bbox + FSM auto-candidate + cuts ring in Phase 7 (roadmap criterion 4). Phases 8/9 = pure render. | ✓ |
| Minimal now, extend later | Publish only score + tracking state now; add bbox/auto-candidate/ring in Phase 9 — reopens the orchestrator + sidecar contract later. | |

**User's choice:** Full payload now (Recommended).
**Notes:** The recent-cuts ring + FSM auto-candidate live in `preview.json` per ROADMAP criterion 4 — this supersedes the milestone SUMMARY's "ring in DirectorStatus" note. `status.json` stays byte-stable.

---

## Phase 7 scope boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Channel + wiring + 2 gates | Steps 1–4 wired into the real `python -m segugio` run (files land in `opcomm/preview/`) + RBT-05 p95-unchanged gate + crash-isolation import gate. No console routes/template/cap/threaded-fix/threat-eval. | ✓ |
| Also pull threaded=True forward | Same + land the UXT-02 server fix now (roadmap places it in Phase 8). | |
| Components only, defer live wiring | Build+unit-test steps 1–3, wire only into `run_measured`; defer build_orchestrator/run() wiring to Phase 8. | |

**User's choice:** Channel + wiring + 2 gates (Recommended).
**Notes:** "Done" = real run writes JPEGs + `preview.json` to disk; RBT-05 p95 unchanged with preview ON; `import segugio.ui` resolves with the heavy stack uninstalled. `threaded=True`, console serving, bandwidth cap, threat re-eval all explicitly Phase 8.

---

## Claude's Discretion

- Mailbox implementation (`Lock` + 1-slot vs `Queue(maxsize=1)`).
- Frame-snapshot safety (`.copy()` on offer vs on the publisher) pending `NdiFrameSource.latest()` buffer-reuse semantics.
- Cache-bust token (separate `gen.txt` vs the `tick`/`gen` field inside `PreviewDoc`).
- `atomic_write_bytes` fsync seam (`fsync: bool` param vs two functions) — D-04 split must stay explicit/documented.
- Exact `PreviewParams` field names + config placement (additive sub-model).
- How the publisher receives the N camera frames without duplicating `source.latest()` calls.

## Deferred Ideas

- Console serving routes + multiview grid + LIVE/tally + dead-feed marking → Phase 8 (MVW-01/02/03).
- `threaded=True`/Waitress server fix → Phase 8 (UXT-02).
- Preview-bandwidth HARD cap + real-WiFi-with-phones validation → Phase 8.
- Live operator kill-switch + freshness/staleness overlay → Phase 9 (UXT-03).
- Explainability rendering (score bars, reason, bbox overlay, "auto wants vs aired", switch-history strip, score-overlay preview) → Phase 9 — the data ships now, only the rendering defers.
- Re-verify BoT-SORT native ReID engages on `yolo26s` at startup before the Phase 9 dog-lock bbox overlay depends on `locked`/`track_id`.
