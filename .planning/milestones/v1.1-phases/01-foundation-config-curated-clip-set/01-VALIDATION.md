---
phase: 1
slug: foundation-config-curated-clip-set
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 1 is fully hardware-free: every success criterion is verified by unit tests on synthetic data (no GPU, no NDI, no clips required to run the suite).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — installed in Wave 0 |
| **Quick run command** | `pytest -q` |
| **Full suite command** | `pytest -q --maxfail=1` |
| **Estimated runtime** | ~5 seconds (pure logic, no I/O) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q`
- **After every plan wave:** Run `pytest -q --maxfail=1`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Requirement Verification Map

| Req | Plan | Behavior verified | Test Type | Automated Command | Status |
|-----|------|-------------------|-----------|-------------------|--------|
| CFG-01 | 01-02 | Malformed `config.yaml` raises a fail-fast `ValidationError` with JSON-path location; valid config parses into a typed object | unit | `pytest tests/test_config.py -q` | ⬜ pending |
| CFG-02 | 01-02 | Per-camera zone rects validated to [0..1]; out-of-range rejected; `framing_weights[role][zone]` parsed as a complete matrix | unit | `pytest tests/test_config.py -k zones -q` | ⬜ pending |
| CFG-03 | 01-02 | Switching `discipline`/`field.sport` selects the matching overlay-field + framing-default sub-config (discriminated union) with zero code edits | unit | `pytest tests/test_config.py -k discipline -q` | ⬜ pending |
| CFG-04 | 01-02 | Model `path` + `class_index` parsed with defaults (`yolo26s.pt`, `16`); overridable value round-trips | unit | `pytest tests/test_config.py -k model -q` | ⬜ pending |
| TST-01 | 01-03 | Cataloguer builds a manifest mapping clip → {discipline, conditions[]}; condition-checklist coverage report flags missing conditions; `tests/fixtures/README.md` documents license/consent | unit | `pytest tests/test_fixtures_catalogue.py -q` | ⬜ pending |
| TST-02 | 01-04 | Generators are deterministic for a fixed seed (byte-reproducible) and emit score-stream scenarios (ping-pong/tie/dropout/recovery) + feed-death sequences | unit | `pytest tests/test_generators.py -q` | ⬜ pending |
| — | 01-01 | Import-smoke: `import segugio` and config/generator modules succeed with heavy deps (torch/ultralytics/cyndilib) absent (lazy-import boundary) | unit | `pytest tests/test_imports.py -q` | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `pyproject.toml` `[tool.pytest.ini_options]` + `requirements.txt` with pinned deps (pytest installed)
- [ ] `tests/conftest.py` — shared fixtures (seeded `numpy.random.Generator`, sample config dicts)
- [ ] `tests/fixtures/` directory convention + `.gitignore` for large binaries (external-dir + committed manifest pattern; no git-lfs)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real footage actually covers all checklist conditions | TST-01 | Footage is user-provided at execution time and not yet on disk; the *cataloguer mechanism* is automated, but the *coverage* depends on the supplied clips | At execution: drop footage into the fixtures dir, run the cataloguer, review the coverage report, supplement gaps with CC0 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
