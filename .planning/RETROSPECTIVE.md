# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.1 — Console Regia

**Shipped:** 2026-06-14
**Phases:** 3 (7–9) | **Plans:** 11 | **Sessions:** ~2–3 (2026-06-13 → 2026-06-14, estimate)

### What Was Built
- An **off-tick frame-publishing channel** (`PreviewPublisher` daemon + single-slot mailbox + `atomic_write_bytes` + `preview.json` "why" sidecar) that exposes what the orchestrator already computes — thumbnails, per-camera score, tracking state, dog bbox, FSM auto-candidate, cuts ring — without stealing time from the director's critical tick (PRV-01/02/03).
- A **live multiview console** served by the crash-isolated Flask app: responsive CSS-Grid, flicker-free refresh, LIVE/tally + dead-feed marking, plus the `threaded=True`/Waitress safety fix, a config-time bandwidth cap, and a written threat re-evaluation (MVW-01/02/03, UXT-02).
- The **explainability + informed-override + tablet-UX layer**: plain-Italian reason, score leaderboard, dog-lock bbox overlay, "auto wants vs aired" hint, switch-history, tap-to-force override, live OBS score preview, tablet-first restyle, and long-run leak/sleep/freshness hygiene — accepted on a real iPad (MVW-04/05, WHY-01..04, SCV-01, UXT-01/03).

### What Worked
- **Gating the boundary first.** The milestone introduced exactly one new cross-process boundary (the publish channel). Phase 7 built it *and proved both HARD gates* (RBT-05 p95 unchanged with preview ON; crash-isolation with the heavy stack absent) before any consumer rendered — so Phases 8 and 9 never had to relitigate the boundary.
- **Adversarial multi-agent review caught a live-data bug unit tests missed.** A 10-agent review found WHY-02's leaderboard "coast" state was dead on real data because of a `coasting`/`coast` enum-literal mismatch — both producer and consumer tests had hardcoded the wrong literal, so the suite was green and wrong (fixed in d6e7555).
- **The cross-phase integration check + milestone audit caught a defect carried since Phase 5.** WHY-01's `fault` reason rendered as the idle "In attesa…" placeholder; the audit closed it inline (3350c14) and pinned `REASON_IT` to the Python source of truth with a drift-proof test.
- **Byte-parity proven by execution, not inspection.** The SCV-01 JS overlay mirror was validated by running the served JS in node against the imported Python renderer across all 3 disciplines — a real drift guard, not a hopeful comment.

### What Was Inefficient
- **SUMMARY frontmatter recording gap.** 09-01/09-03/09-04 shipped requirements (WHY-01/02/04, SCV-01, MVW-05, UXT-03) but left `requirements_completed` empty. The `milestone.complete` CLI harvests that frontmatter, so the auto-generated MILESTONES.md contained garbage one-liners ("COMPLETE — all 3 tasks done", "1. [Rule 3 - Blocking] …") that had to be hand-cleaned at close.
- **Nyquist validation left as drafts.** 07/08-VALIDATION.md were created but Wave-0 was never completed; 09 has none. Discovery debt that the audit had to flag rather than the workflow closing it.
- **No per-phase SECURITY.md** despite `security_enforcement` on — threat models live inside the PLANs and `docs/security.md`, but the formal verification step was skipped.
- **A producer↔consumer contract bug slipped to live data.** The `coasting`/`coast` mismatch only surfaced on real `ScorerStatus`, not in unit tests — a sign the producer and consumer needed a shared contract test on live-shaped data, not parallel hardcoded literals.

### Patterns Established
- **Gate-the-boundary-first:** when a milestone adds exactly one new cross-process boundary, build and *prove* it (HARD gates) in the first phase before any consumer depends on it.
- **Crash-isolation as an enforced import test:** `import segugio.ui` must resolve and the console must *start* with the heavy stack (ultralytics/torch/numpy/cv2/cyndilib/obsws) absent — re-asserted as a regression gate each phase.
- **Publish-and-render over compute:** expose data the core already computes via an off-tick atomic-file channel rather than adding a network server or new write-path into the safety-critical core.
- **Off-tick latest-only mailbox:** the right shape for "publish without blocking the tick" — `offer()` never blocks, last-writer-wins, frame-drop allowed.
- **Byte-parity mirror via execution:** prove a JS reimplementation of a Python function by running both and diffing bytes in CI.

### Key Lessons
1. Keep SUMMARY `requirements_completed` frontmatter populated as you go — the milestone-close CLI harvests it; empty fields produce garbage accomplishments and break traceability.
2. When the same value crosses a producer→consumer boundary (an enum literal, a JSON key), test the *contract on live-shaped data*, not the literal hardcoded identically on both sides — that's how `coasting`/`coast` stayed green and broken.
3. Run `/gsd-validate-phase` and `/gsd-secure-phase` *inside* the phase, not at milestone close — leaving them as drafts turns the audit into a debt-discovery tool instead of a confirmation.
4. Make hardware/field carry-forwards explicit deferred items at close; the open-artifact audit + milestone audit kept all 7 visible rather than silently shipping over them.

### Cost Observations
- Model mix: not instrumented this milestone (config `model_profile: quality` → opus-leaning). Estimate only.
- Sessions: ~2–3 across 2026-06-13 → 2026-06-14.
- Notable: the most expensive single action (the 10-agent adversarial review) was also the highest-value — it caught a green-but-wrong bug that would have shipped a dead UI state to the operator.

---

## Milestone: v1.2 — Overlay Grafico Broadcast

**Shipped:** 2026-06-20 (tag `v1.2`)
**Phases:** 5 (10–14) | **Plans:** 15 | **Sessions:** ~3–4 (2026-06-14 → 2026-06-20, estimate)

### What Was Built
- An **overlay data contract**: a NEW console-owned `overlay_run.json` run-edge stamp + a boundary-safe `GET /overlay-json` carrying the `server_now` clock anchor and a monotonic `gen` — `runstate.json` (director-read every tick) never touched, zero HTML (OVD-01/02/03, RBT-07).
- A **transparent shared HTML/CSS/JS renderer** + `/overlay` page: a per-discipline lower-third with a self-counting run timer correct across machine clock skew (offset-cancellation via `server_now`, never raw `Date.now() − started_at`), a freshness degrade, event-only animations, and config branding (OVL-01..04, TMR-01..04, BRD-01/02).
- **SCV-01/02 unification**: the console preview became an `<iframe src="/overlay?preview=1">` reusing the one renderer OBS loads — the byte-exact Python↔JS mirror + `/score/preview` drift-guard retired, drift structurally impossible (SCV-02).
- A **curated OBS scene-collection**: a transparent browser-source wired top-of-z-order into all 7 scenes (CEF `shutdown:false`/`refresh-on-activate:false`), with the `overlay.txt` text source retained as the always-wired fallback (SCN-01/02, RBT-06).
- **Live-robustness hardening** (Phase 14): a `DEAD_MS` second degrade stage that fully *hides* the lower-third on a real console death (no frozen score airs), `overlay.txt` single-writer coexistence, an `/overlay-json` poll storm that never starves `POST /command`, and HTML-sink escaping — each a named per-criterion gate (RBT-06).

### What Worked
- **Dependency-forced build order held.** data contract → renderer → unification → OBS wiring → robustness. `server_now` was in the contract from the first commit, so the clock-skew solution never had to be retrofitted.
- **Code review caught a broadcast-integrity blocker the gate false-passed.** CR-01: the `DEAD_MS` dead-hide was a one-way `is-exiting` transition — after a console death+recovery *mid-run*, the overlay would have stayed hidden on air for the rest of the run. The SC#2 test passed because it asserted only `currentElapsed()` continuity, not visibility. Fixed (`be7ef7e`) with a regression test confirmed to fail pre-fix / pass post-fix (`d3dfa62`).
- **Structural drift made impossible, not policed.** SCV unification deleted the hand-maintained mirror rather than adding another drift-guard — the strongest form of "can't drift."
- **Security verification closed 9/9 threats by grep + executing gate**, not on intent (`14-SECURITY.md`) — including confirming the `lastGenAt` gen-age anti-pattern stays absent.

### What Was Inefficient
- **A passing gate hid a real bug — again.** SC#2 asserted the internal value (clock continuity) but not the user-observable outcome (the plate is visible). That's the same "green but wrong" class as v1.1's `coasting`/`coast`: the test checked what was easy to read, not what the operator sees on air.
- **STATE.md format drift.** Executors hand-edit STATE.md (no gsd-tools on PATH in worktrees), leaving it slightly off the CLI's expected shape — `phase.complete` and `milestone.complete` both warned `STATE.md field "Last Activity Description" not found` and skipped a field.
- **Quick-task status never marked.** Three executed `.planning/quick/` tasks (each with a SUMMARY) showed as `[unknown]`/incomplete in the pre-close audit, forcing a manual "is this actually done?" inspection at milestone close.
- **Worktree parallelism auto-degraded to sequential** (HEAD diverged from origin/HEAD, #683) — correct and safe, but the wave plans were authored assuming parallel isolation.

### Patterns Established
- **Assert the user-observable invariant, not just the internal value.** A timer-continuity test must also assert the plate is *shown*; a degrade test must assert the recovery *re-shows*. The gap between "value correct" and "operator sees it" is where broadcast bugs live.
- **Response-recency liveness, never gen-age.** `gen` is flat during a live idle run; keying staleness/death on response recency (`lastResponseAt`) is the only correct signal — gen-age would false-hide a live overlay.
- **Delete the drift source over guarding it.** Unify onto one renderer/URL rather than maintaining a mirror + a drift test.

### Key Lessons
1. A named per-criterion gate is only as good as the assertion inside it — gate on the *observable* outcome (visibility, what airs), or a green test will ship a dead-on-screen overlay (CR-01).
2. Run the code-review gate *before* marking a phase done, even when all automated tests pass — it caught a blocker that the phase's own tests certified as working.
3. Mark quick-task completion status as you finish them; the pre-close audit treats SUMMARY-present-but-status-unknown as open work.
4. Keep STATE.md edits on the CLI's shape (or always go through gsd-tools) so `phase.complete`/`milestone.complete` don't skip fields.

### Cost Observations
- Model mix: opus-leaning (executor `opus`, verifier/auditor `sonnet`/`opus`); not finely instrumented.
- Sessions: ~3–4 across 2026-06-14 → 2026-06-20.
- Notable: the Phase-14 code-review + targeted fixer pass (one reviewer + one fixer agent) was the highest-value spend — it converted a phase that *looked* done (all gates green) into one that survives the live failure it was built for.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 MVP | ~6 (est.) | 6 | Established the GSD synthetic-first dependency chain: pure brains (scorer/FSM) unit-tested before YOLO is wired; integration phase closes the milestone |
| v1.1 Console Regia | ~2–3 (est.) | 3 | Added adversarial multi-agent review + a formal milestone audit before close; "gate-the-boundary-first" for the one new cross-process boundary |
| v1.2 Overlay Grafico Broadcast | ~3–4 (est.) | 5 | Per-criterion named gates + a pre-completion code-review gate that caught a broadcast-integrity blocker the gates false-passed; "delete the drift source over guarding it" (SCV unification); structural threat verification (9/9) |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 MVP | ~314 headless passed | high on pure modules (framing 99%, decision 100%) | transitions (light), Flask; native-ReID (no extra weights) |
| v1.1 Console Regia | ~421 passed / 8 skipped | UI suite 76/76; crash-isolation import gate green | none new — reused opcomm atomic-file channel + render_overlay_text; Waitress optional |
| v1.2 Overlay Grafico Broadcast | full headless/overlay suite green (3 pre-existing hardware-rig tests excepted: latency p95 + 2 NDI) | overlay degrade/fallback/poll-storm/HTML-sink + scene-template gates green; crash-isolation gate green | none new — client-side JS renderer only, no new Python runtime dependency |

### Top Lessons (Verified Across Milestones)

1. **Pure-first, then wire:** building and exhaustively unit-testing the pure logic (scorer, FSM in v1.0; the publish channel + sidecar in v1.1) before the heavy/edge integration keeps defects cheap and the lazy-import boundary honest.
2. **Green tests can be confidently wrong:** v1.0's CR-01 (startup fault-sink) and v1.1's WHY-02 (`coasting`/`coast`) both passed their unit tests and were caught only by review/integration — adversarial and integration checks earn their cost.
3. **Software-complete ≠ field-validated:** both milestones close with explicit hardware/field carry-forwards; tracking them as deferred items (not silent gaps) keeps the honesty of "shipped on synthetic data."
