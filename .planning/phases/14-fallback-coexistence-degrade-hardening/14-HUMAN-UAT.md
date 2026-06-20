# Phase 14 — On-Rig HUMAN-UAT Checklist (RBT-06)

> **Requirement:** RBT-06 — live-robustness acceptance (fallback coexistence & degrade).
>
> **Status: DEFERRED hardware/field carry-forward (D-02).** This checklist is the human-medium
> half of RBT-06. It is authored here in Phase 14 and **executed on the rig later** — the same
> disposition as the Phases 5/7 hardware UATs. **It does NOT block Phase 14 completion.**
> Phase 14 closes when the **automation gate is green** (`test_overlay_degrade_gate.py`,
> `test_overlay_fallback_gate.py`, `test_overlay_poll_storm.py`, `test_overlay_html_sink_gate.py`,
> `test_imports.py`) **AND** this checklist is written and ready to run on the rig (D-01/D-02).

---

## Why these scenarios are human-only

A real CEF browser-source, a real OBS text source reading `overlay.txt`, and a real
LAN-cable interruption cannot be simulated headlessly. The headless automation covers
everything simulable (renderer stale→dead degrade via node fake-DOM, `gen` re-anchor,
`/overlay-json` poll-storm vs `/command`, the HTML-escape sink). The three scenarios below
are the genuinely physical residue that only a rig run can confirm (14-VALIDATION.md
§"Manual-Only Verifications").

---

## Pre-flight

- [ ] OBS Studio running with the `obs/segugio-scene-collection.json` collection loaded.
- [ ] The transparent **Browser** source points at the console LAN-IP `/overlay` URL
      (`shutdown_source_when_not_visible: false`, `refresh_when_scene_is_active: false`).
- [ ] The **`Score Text`** ("read from file") source points at the live `overlay.txt`,
      and is **`visible: false`** while the console is alive (D-06 — avoids a double score:
      the browser overlay is the primary, the text source is the fallback).
- [ ] **D-08 — exact NDI source-name match.** Confirm each `cameras[].ndi_source` in the
      live config matches the scene's `ndi_source_name` **byte-for-byte**. The recurring
      "OBS sees it but the console feed is blank" gotcha is an exact-name mismatch — verify
      before blaming the network.
- [ ] Console started (`threaded=True` / waitress) and answering `GET /overlay-json`.
- [ ] A score posted from the console so the lower-third is airing a live score.

---

## Scenario 1 — Console death: browser overlay auto-hides, no frozen "live" score

Covers SC#1 (the browser-source degrade half) + the D-06 simplified manual reveal.

1. [ ] With a live score airing, **kill the console process** (or stop answering polls).
2. [ ] Observe the OBS **browser-source lower-third HIDES on-air within ~`DEAD_MS`** (~3 s):
       the overlay first dims (`.is-stale` at `STALE_MS`) then auto-hides at `DEAD_MS`.
3. [ ] **Confirm there is NO frozen "live" score** left on screen — a stale run must never
       keep airing as if live (the two-stage degrade shipped in plan 14-01).
4. [ ] **D-06 simplified reveal:** when the graphic drops, the operator's ONLY manual step is
       to **reveal the `Score Text` source** — confirm the last score now airs from
       `overlay.txt`. (The old Phase-13 "manually hide Score Overlay" step is GONE — the
       browser overlay auto-hides itself via `DEAD_MS`.)

---

## Scenario 2 — LAN-cable drop stops the timer; restart re-anchors with no phantom jump

Covers SC#2 (physical network interruption + `gen` re-anchor).

1. [ ] Start a run so the freestyle/agility timer is counting on the overlay.
2. [ ] **Pull the LAN cable** mid-run (console ↔ OBS machine link).
3. [ ] Observe the **timer STOPS and the overlay degrades** — it must never keep airing a
       stale "live" count during the drop.
4. [ ] **Reconnect the cable** and **restart the console**.
5. [ ] Observe the timer **re-anchors via `gen`** (the persisted `overlay_run.json` `started_at`
       survives the restart): the resumed timer is **continuous — NOT an outage-sized phantom
       jump**. The displayed elapsed should match real wall-clock elapsed since run start, not
       jump forward by the length of the outage.

---

## Scenario 3 — `overlay.txt` text source keeps airing the last score

Covers SC#1 (the on-disk fallback half — single-writer coexistence).

1. [ ] With a live score airing and the console alive, note the last operator score.
2. [ ] **Kill the console.** The browser overlay auto-hides (Scenario 1).
3. [ ] **Reveal the `Score Text` source** (the D-06 one-action step).
4. [ ] Confirm the **`overlay.txt` read-from-file source airs the LAST score unchanged** —
       the single-writer property means no second writer cleared it on death; the rendered
       line stays on disk byte-for-byte until the next operator score (proven headless by
       `test_overlay_fallback_gate.py`, confirmed here on the real OBS text source).

---

## Sign-off

- [ ] Scenario 1 passed (auto-hide within `DEAD_MS`, no frozen score, D-06 reveal works)
- [ ] Scenario 2 passed (timer stops on drop, re-anchors with no phantom jump)
- [ ] Scenario 3 passed (`overlay.txt` keeps the last score)
- [ ] D-08 NDI source-name match verified

**Tester:** ________________   **Rig / GPU:** ________________   **Date:** ____________

*RBT-06 is fully met when this rig run is signed off AND the Phase 14 automation gate is green.
This human UAT does not block Phase 14 completion (D-02).*
