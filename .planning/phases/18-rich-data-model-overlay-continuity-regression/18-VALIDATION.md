---
phase: 18
slug: rich-data-model-overlay-continuity-regression
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-27
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `18-RESEARCH.md` § Validation Architecture. Task IDs are bound during planning.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ node fake-DOM behavior harness via `subprocess`, gated by `shutil.which("node")`) |
| **Config file** | existing repo pytest config (`pyproject.toml` / `pytest.ini`) |
| **Quick run command** | `pytest tests/test_score_calc.py tests/test_ui_overlay_json.py -x -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_score_calc.py tests/test_ui_overlay_json.py -x -q`
- **After every plan wave:** `pytest tests/test_ui_overlay_render.py tests/test_overlay_fallback_gate.py tests/test_overlay_html_sink_gate.py tests/test_ui_score_authoritative.py tests/test_imports.py -q`
- **Before `/gsd-verify-work`:** Full suite (`pytest -q`) must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Task IDs assigned during planning; rows keyed here by requirement/success-criterion + locked decision.

| Req / SC | Decision | Wave | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|------|-----------------|-----------|-------------------|-------------|--------|
| RBT-09 / SC#1 | D-03 disc_tf per-throw `score` (Decimal str) alongside raw throw | 1 | N/A | unit | `pytest tests/test_score_calc.py -k tf -x` | ✅ extend | ⬜ pending |
| RBT-09 / SC#1 | D-03 freestyle `criteria{}` per-category snapped | 1 | N/A | unit | `pytest tests/test_score_calc.py -k freestyle -x` | ✅ extend | ⬜ pending |
| RBT-09 / SC#1 | D-03 agility `faults_breakdown{course,time}` | 1 | N/A | unit | `pytest tests/test_score_calc.py -k agility -x` | ✅ extend | ⬜ pending |
| RBT-09 / SC#1 | D-04 flat keys byte-identical; round-trip equality holds | 1 | N/A | integration | `pytest tests/test_ui_score_authoritative.py -x` | ✅ green, keep | ⬜ pending |
| RBT-09 / SC#1 | D-05 legacy `/overlay-json` key set frozen (subset assertion + 6-key envelope) | 1 | tamper-evident contract | integration | `pytest tests/test_ui_overlay_json.py -x` | ✅ extend | ⬜ pending |
| RBT-09 / SC#2 | D-06 `overlay.txt` single non-empty line after rich POST | 2 | line-injection bounded | integration | `pytest tests/test_overlay_fallback_gate.py tests/test_ui_overlay_render.py -x` | ✅ extend | ⬜ pending |
| RBT-09 / SC#3 | D-06 `/overlay` host page bakes NO score data (thin/poll-only) | 2 | no data leak in HTML | served-HTML | `pytest tests/test_ui_overlay_page.py -x` | ✅ green, keep | ⬜ pending |
| RBT-09 / SC#4 | D-07a no-`innerHTML` grep on overlay-render.js + score-entry.js | 1 | output encoding guard | source grep | `pytest tests/test_overlay_html_sink_gate.py -k innerhtml` | ✅ extend | ⬜ pending |
| RBT-09 / SC#4 | D-07b crafted `<script>` renders inert on lower-third AND form preview | 2 | XSS inert (escaped) | node behavior | `pytest tests/test_overlay_html_sink_gate.py -k render` | ❌ W0 | ⬜ pending |
| RBT-09 | D-09 rich POST round-trips with heavy stack absent; subkeys need no new import | 1 | crash-isolation intact | import smoke | `pytest tests/test_imports.py -x` | ✅ green, keep | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_overlay_html_sink_gate.py` — DOM-level crafted-`<script>` render assertion for the entry-form preview (`nomeEcho`) and the overlay lower-third (`renderIdentity`) (D-07b). Copy-adapt the existing fake-DOM driver from `tests/test_ui_score_entry.py` `_FAKE_DOM` and `tests/test_ui_overlay_render.py` fake DOM — no new framework.
- [ ] `tests/test_ui_overlay_json.py` — golden-snapshot per-discipline legacy key-set assertion (D-05); use `LEGACY <= set(fields)` subset (catches removal/rename without blocking future additive keys).

*No framework install needed — pytest + node already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-OBS read-from-file text source shows current score after rich POST | RBT-09 / SC#2 | Requires physical OBS rig + read-from-file source | Documented NON-BLOCKING checklist (D-08): load `overlay.txt` as an OBS text→read-from-file source, fire a rich `POST /score` per discipline, confirm the live source updates to a single current line. Recorded in the phase docs; does NOT block sign-off. |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (D-07b render assertion, D-05 golden snapshot)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
