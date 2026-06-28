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

## Milestone: v1.3 — Gestione Punteggi Avanzata

**Shipped:** 2026-06-28 (tag `v1.3`)
**Phases:** 4 (15–18) | **Plans:** 9 | **Sessions:** ~5–6 (2026-06-21 → 2026-06-27, estimate)

### What Was Built
- A **pure-stdlib `score_calc` authority** — Decimal-exact `compute()` + per-field `validate()` for disc Toss&Fetch (best-5/cap-5/two-bonus), single-judge freestyle, and agility (count-up/deduct/elimination), driven by an injected `ScoringProfile` — built and proven *before* any UI consumed it, and added to the crash-isolation import gate (SCC-02/04, RBT-08).
- **Config-driven scoring profiles**: a pydantic `ScoringProfile` sub-model on the CFG-03 union + a stdlib adapter, a pinned CSEN 2026 default (FIDASC `[ASSUMED]` stub, generic FCI agility), federation swap with no code change, fail-fast `SystemExit(2)` on a malformed profile (SCP-01/02).
- A **server-authoritative `POST /score`**: the client POSTs raw inputs; Python validates (400 + write-nothing on invalid), Decimal-recomputes the totals, then atomic-writes `score.json`+`overlay.txt` with run-state preserved. The advisory `score-calc.js` is a byte-exact port pinned by a node-vs-Python drift-guard (SCC-01/03).
- **ONE shared `score-entry.js` component** mounted on the dedicated `/score-entry` page AND in a native console `<dialog>` via ONE shared Jinja partial — rich per-discipline fields, live best-5-of-N advisory total, on-blur errors, reload-safe localStorage draft, two-step danger-styled publish (Enter never publishes); legacy `#form-score` retired (SCE-01..05, SCC-05).
- An **additive rich data model**: structured `throws[].score`/`criteria{}`/`faults_breakdown{}` carried as `str(Decimal)` through the write path + `/overlay-json` beside preserved flat keys; the 6-key envelope + per-discipline legacy keys frozen by a golden snapshot; identity free-text wired XSS-inert via `createTextNode`/`textContent`; `overlay.txt` single-line + thin `/overlay` regression-verified (RBT-09).

### What Worked
- **Pure-first, gating-authority-first held again.** Phase 15 built and exhaustively unit-tested the scoring brain (Decimal-exact, stdlib-only, crash-isolated import surface) before any page or modal consumed it — so Phases 16–18 never relitigated the calc/validation contract.
- **Server-authoritative recompute is a structural guarantee, not a policed one.** Because only Python writes what airs and it *ignores* any client-sent total, even a buggy or hostile client cannot put a wrong score on air — strictly stronger than the v1.1/v1.2 drift-guard mirror. The keystone E2E ("form total === `overlay.txt` === `/overlay-json`-rendered total") was proven end-to-end.
- **One component + one Jinja partial across two hosts.** The v1.2 SCV-02 "one renderer" lesson generalized to an *interactive form*: share the JS module AND the markup partial, never iframe a form (focus/keyboard/submit cross the boundary badly), never hand-mirror — drift structurally impossible by construction.
- **The pre-completion code-review gate earned its cost in 2 of 4 phases.** P15 review found 3 Criticals (string bonus-flag truthiness; missing `count_best_n`/`per_throw_cap` lower bounds); P16 found 2 BLOCKERs (a malformed body → HTTP 500 that *bypassed* the 400/write-nothing contract) — all fixed in-phase with regression tests, before sign-off, despite the phases' own suites being green.
- **Adversarial per-threat secure-phase + a passing milestone audit.** Every phase SECURED with `threats_open: 0`; the audit surfaced two sub-`high` residuals (scoring-bound + echo-cap) and tracked them as todos rather than silently shipping over them.

### What Was Inefficient
- **The recurring three are now systemic.** SUMMARY `requirements_completed` frontmatter empty *again* (15-02, 17-02 — the exact v1.1 lesson, third milestone running); Nyquist VALIDATION PARTIAL (15/16/18) / MISSING (17) *again*; and gsd-tools-not-on-PATH → STATE/ROADMAP hand-edited with the `milestone.complete` "Last Activity Description not found" warning *again*. Each was absorbed at the audit, but they are no longer one-offs — they are an unfixed process gap.
- **Quick-task status still never marked — and now compounding.** The pre-close audit flagged 4 executed quick tasks as `[unknown]`; two of them (`260615-sod`, `260615-tsi`) were *already* acknowledged-and-deferred at the v1.2 close and re-surfaced here because nothing ever sets the status flag. Deferred-but-unmarked items re-cost a manual inspection at *every* subsequent milestone close.
- **A federation rule table shipped `[ASSUMED]`.** FIDASC scoring numbers were accepted as a stub for v1.3 (CSEN carries numeric correctness); honest and tracked, but it means the config-swap claim is structurally proven yet numerically unverified for one profile until a human pins the tables.

### Patterns Established
- **Server-authoritative single-writer:** the server recomputes and is the sole writer of what airs; the client value is advisory and never trusted. The structural form of "form and on-air cannot diverge."
- **One module + one markup partial across hosts:** extend "delete the drift source" to interactive forms — share both the behavior (JS) and the structure (Jinja partial), never iframe or mirror a form.
- **Additive data-model evolution frozen by a golden snapshot:** new structured subkeys ride beside preserved flat keys; a `==`-frozen envelope + subset-frozen legacy keys turn any rename/removal into a CI failure — additive growth stays safe.

### Key Lessons
1. The three recurring process gaps (SUMMARY frontmatter, Nyquist Wave-0, quick-task status flags) have now appeared across three consecutive milestones — they should be closed *in-workflow* (a phase-close checklist or a CLI that sets the flag), not re-discovered by each audit. The two v1.2-deferred quick tasks re-appearing at v1.3 close is the proof it compounds.
2. When correctness must not depend on the client, make the server recompute and discard client-supplied results — it beats a drift-guard because no client bug can reach air, only diverge advisory display.
3. Keep running the code-review gate before phase sign-off: it caught a 400/write-nothing *bypass* (HTTP 500) that the phase's green suite certified as working — the same "green but wrong" class as v1.1/v1.2, now at the HTTP-contract layer.

### Cost Observations
- Model mix: opus-leaning (config `model_profile: quality`); not finely instrumented.
- Sessions: ~5–6 across 2026-06-21 → 2026-06-27.
- Notable: the highest-value spend was again the in-phase code review (P15/P16) — it converted two phases that *looked* done (suites green) into ones that honor their own HTTP and numeric contracts before they could put inconsistent state on air.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 MVP | ~6 (est.) | 6 | Established the GSD synthetic-first dependency chain: pure brains (scorer/FSM) unit-tested before YOLO is wired; integration phase closes the milestone |
| v1.1 Console Regia | ~2–3 (est.) | 3 | Added adversarial multi-agent review + a formal milestone audit before close; "gate-the-boundary-first" for the one new cross-process boundary |
| v1.2 Overlay Grafico Broadcast | ~3–4 (est.) | 5 | Per-criterion named gates + a pre-completion code-review gate that caught a broadcast-integrity blocker the gates false-passed; "delete the drift source over guarding it" (SCV unification); structural threat verification (9/9) |
| v1.3 Gestione Punteggi Avanzata | ~5–6 (est.) | 4 | Server-authoritative single-writer keystone (client value never trusted) — strictly stronger than a drift-guard; "one module + one markup partial across hosts" extends drift-deletion to interactive forms; adversarial per-threat secure-phase (4/4 SECURED); in-phase code review caught HTTP-contract blockers (P15 3 Criticals, P16 2 BLOCKERs) |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 MVP | ~314 headless passed | high on pure modules (framing 99%, decision 100%) | transitions (light), Flask; native-ReID (no extra weights) |
| v1.1 Console Regia | ~421 passed / 8 skipped | UI suite 76/76; crash-isolation import gate green | none new — reused opcomm atomic-file channel + render_overlay_text; Waitress optional |
| v1.2 Overlay Grafico Broadcast | full headless/overlay suite green (3 pre-existing hardware-rig tests excepted: latency p95 + 2 NDI) | overlay degrade/fallback/poll-storm/HTML-sink + scene-template gates green; crash-isolation gate green | none new — client-side JS renderer only, no new Python runtime dependency |
| v1.3 Gestione Punteggi Avanzata | full headless suite green (5 documented pre-existing env failures: 2 NDI, 1 node ESM, 2 cp1252) | authoritative round-trip (20/20) + node-vs-Python drift-guard (4/4) + crash-isolation (26/26) + D-05 golden-snapshot gates green | none new — pure-stdlib `score_calc` (decimal/re/dataclasses/enum) server-side, vanilla JS + native `<dialog>` client-side; pydantic already present |

### Top Lessons (Verified Across Milestones)

1. **Pure-first, then wire:** building and exhaustively unit-testing the pure logic (scorer, FSM in v1.0; the publish channel + sidecar in v1.1) before the heavy/edge integration keeps defects cheap and the lazy-import boundary honest.
2. **Green tests can be confidently wrong:** v1.0's CR-01 (startup fault-sink), v1.1's WHY-02 (`coasting`/`coast`), v1.2's CR-01 (one-way dead-hide), and v1.3's P16 BLOCKER (malformed body → HTTP 500 bypassing 400/write-nothing) all passed their own suites and were caught only by review/integration — the pre-completion code-review gate now earns its cost every milestone.
3. **Software-complete ≠ field-validated:** every milestone closes with explicit hardware/field carry-forwards; tracking them as deferred items (not silent gaps) keeps the honesty of "shipped on synthetic data."
4. **Make correctness structural, not policed:** the strongest guarantees deleted the failure mode rather than testing for it — SCV unification (one renderer, v1.2) and the server-authoritative single-writer (client value never trusted, v1.3). Prefer "can't drift / can't diverge by construction" over a drift-guard whenever the design allows it.
5. **Unfixed process formality compounds:** SUMMARY `requirements_completed` frontmatter, Nyquist Wave-0 recording, and quick-task status flags have been audit-debt for three milestones running — v1.2-deferred quick tasks even re-surfaced at the v1.3 pre-close. Recurring bookkeeping gaps should be closed in-workflow, not re-discovered by each audit.
