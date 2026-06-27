---
phase: 15
slug: pure-calc-validation-core-scoring-profiles
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-27
---

# Phase 15 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (all three plans 15-01/02/03 carry a `<threat_model>` block).
> Verified 2026-06-27 by an adversarial multi-agent audit: 12 independent skeptics (one per threat,
> each tasked to DISPROVE its mitigation against the live source) + synthesis + completeness critic.
> The audit surfaced two real sub-`high` correctness gaps (T-15-01, T-15-06) that a single-pass audit
> would likely have rubber-stamped; both were reviewed and **accepted as documented v1.3 residual risks**
> (trusted operator/config input, below `block_on: high`), with a tracked hardening todo.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator raw input → `validate()`/`compute()` | Untrusted free-form per-discipline field values (numbers, mm:ss times, free text). | Operator-typed score inputs |
| `compute()` output → `score_render._clean` | Computed flat keys feed the display-only renderer (strips CR/LF + control chars, length-caps). | Computed string totals |
| `score_calc` module top → console import surface | A heavy import here would breach crash-isolation (AI-loop starvation via the UI process). | Python import graph |
| config YAML file → `yaml.safe_load` → pydantic | A malformed/hostile profile file crosses into the config tier. | Scoring-profile config |
| validated pydantic profile → `adapt_scoring_profile` → plain dataclass | Config tier (heavy-dep-tolerant) → UI tier (crash-isolated); adapter must not drag config imports into `score_calc`. | Adapted scoring profile |
| `POST /score` route → `Discipline` enum | Operator-supplied `discipline` whitelisted against the closed enum before any write. | Discipline selector |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Status Evidence | Status |
|-----------|----------|-----------|-------------|------------------------------|--------|
| T-15-01 | Tampering | `validate()` input boundary | mitigate (core) + accept (residual AR-15-01) | Four enumerated invalid classes (out-of-range zone, missing required, malformed mm:ss, off-increment) rejected as per-field errors; `compute()` gated behind a clean `validate()` (`app.py:355-361`, `score_calc.py:197-260`, `tests/test_score_calc.py:257-298`). **Residual:** freestyle `adjustment` unbounded → can air a total above federation max (see AR-15-01). | closed |
| T-15-02 | Integrity | `compute()` Decimal arithmetic | mitigate | All `decimal.Decimal` end-to-end; `grep -c "float(" score_calc.py == 0`; `test_decimal_exactness` asserts `Decimal(out['totale'])==Decimal('19.0')` (`score_calc.py:129-407`, `tests/test_score_calc.py:62-76`). | closed |
| T-15-03 | Tampering | malformed `mm:ss(.cc)` time | mitigate | Fully-anchored `_TIME_RX = ^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$` (`score_calc.py:58`); a non-match is a per-field error, never a coerced 0 (`:245-248`); `test_validation_errors` green. | closed |
| T-15-04 | DoS (AI-loop starvation via UI) | `score_calc` module imports | mitigate | Module-top imports are stdlib-only (`dataclasses/decimal/enum/re`) + `..opcomm.records.Discipline`; no numpy/cv2/torch/pydantic/segugio.config (`score_calc.py:28-35`); covered by the heavy+numpy/cv2-absent gate (`tests/test_imports.py:114`). | closed |
| T-15-05 | Tampering | computed value → overlay sink | accept | `compute()` is a pure function returning string totals; no new write/sink path; the existing `_clean` (CR/LF strip + 64-cap) still sanitizes at the sole overlay sink (`score_render.py:40-54`, `app.py:320-321`). | closed |
| T-15-06 | Tampering / DoS | malformed profile YAML reaching the live loop | mitigate (core) + accept (residual AR-15-02) | Fail-fast `SystemExit(2)` at config-load; `extra="forbid"` + `@model_validator` + `Field(ge=0/gt=0)` on zone points / `per_throw_cap` / `count_best_n` reject the four named malformations (`loader.py:36-44`, `discipline.py:54-159`, `tests/test_score_profiles.py:101-119`). **Residual:** `freestyle_max`/`time_fault_rate`/`fault_value` unbounded (see AR-15-02). | closed |
| T-15-07 | Tampering (PyYAML RCE) | profile config load | mitigate | Sole config parse is `yaml.safe_load` (`loader.py:36`); profile rides the same `Config.model_validate` path, no alternate loader; grep over `src/` for `pickle/marshal/unsafe_load/FullLoader/Loader=` → no matches. | closed |
| T-15-08 | DoS (crash-isolation breach) | `adapt_scoring_profile` placement | mitigate | Adapter lives in `segugio.config` (heavy tier); its `score_calc` import is LAZY in-function (`discipline.py:193`), module-top ref is `TYPE_CHECKING`-guarded; `score_calc` imports no pydantic/config (D-10). | closed |
| T-15-09 | Integrity | FIDASC `[ASSUMED]` numbers airing a wrong score | accept (re-dispositioned from mitigate — AR-15-03) | The plan-time human-verify gate was resolved as "stub accepted for v1.3"; FIDASC fixture is `[ASSUMED]`-tagged throughout; CSEN is the pinned verified default (`test_score_profiles.py:92` `totale=='23.5'`); `__main__.py` ships `config.example.yaml` (no FIDASC numbers air by default). | closed |
| T-15-10 | DoS (AI-loop starvation via UI) | `score_calc` + `POST /score` import surface | mitigate | `segugio.ui.score_calc` ∈ `PHASE1_SURFACE`; heavy+numpy/cv2-absent block runs a `POST /score` round-trip returning 204/200 with `score=='2.5'` (`tests/test_imports.py:107-147`); Flask + score_calc imported inside `create_app`. | closed |
| T-15-11 | Spoofing (unknown discipline) | `POST /score` route | accept | `Discipline(raw_discipline)` whitelist → 400 before compute/write (`app.py:343-347`); closed `str, Enum`, no `_missing_` override (`records.py:43-49`); Phase 18 added only display-only identity keys after the gate. | closed |
| T-15-SC | Tampering (supply chain) | npm/pip/cargo installs | mitigate | All three SUMMARYs declare `tech-stack.added: []`; `pydantic==2.13.4` pin unchanged (`requirements.txt`/`pyproject.toml`); zero manifest commits in the Phase-15 window. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-15-01 | T-15-01 (residual) | Freestyle `adjustment` is unbounded for sign/range; because `_compute_freestyle` caps at `freestyle_max` (40) BEFORE `total = total − adjustment`, an all-10 entry with `adjustment="-50"` airs a totale of 90 > max 40. Below `block_on: high` (the field is trusted operator input, no untrusted attacker). Accepted for v1.3; tracked for hardening. | user (2026-06-27) | 2026-06-27 |
| AR-15-02 | T-15-06 (residual) | `ScoringProfile.freestyle_max`/`time_fault_rate`/`fault_value` (`discipline.py:109/111/113`) are unbounded Decimals; a negative value bypasses the `SystemExit(2)` fail-fast and reaches the live `score_calc` — the symmetric bound `CR-02/CR-03` applied to `per_throw_cap`/`count_best_n` was never added to these three. Config is admin-authored (trusted); below `block_on: high`. Accepted for v1.3; tracked for hardening. | user (2026-06-27) | 2026-06-27 |
| AR-15-03 | T-15-09 | FIDASC numbers ship `[ASSUMED]` (human-verify gate resolved as "stub accepted for v1.3"). Protection against airing wrong FIDASC scores is documentation-only (YAML comment banners), but CSEN is the pinned verified default and the shipped `config.example.yaml` default carries no FIDASC scoring numbers, so nothing wrong airs by default. Optional future hardening: a runtime "FIDASC UNVERIFIED" banner on profile load. | user (2026-06-27) | 2026-06-27 |
| AR-15-04 | T-15-05, T-15-11, T-15-SC | Plan-time `accept` dispositions, all verified to still hold: computed values reach only the existing `_clean` sink (no new write path); the `Discipline` whitelist returns 400 before any write; zero new runtime dependencies were installed. No residual harm. | gsd adversarial audit (2026-06-27) | 2026-06-27 |

*Accepted risks do not resurface in future audit runs.*

**Tracked hardening:** `.planning/todos/pending/harden-scoring-validation-bounds.md` (bound the freestyle `adjustment`; add `Field(ge=0)` to the three unbounded profile scalars; optional FIDASC runtime banner).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-27 | 12 | 12 (9 mitigations verified non-bypassable + 3 accepted residuals) | 0 | gsd adversarial multi-agent audit (12 verifiers + synthesis + completeness critic, opus) |

**Audit method:** Each threat verified by an independent adversarial agent instructed to disprove the
mitigation against the live source. Verdicts: 9 CLOSED non-bypassable; 2 `mitigate` CONCERN with real
residuals (T-15-01, T-15-06) → user-accepted as documented v1.3 risks; 1 (T-15-09) re-dispositioned
`mitigate → accept`. Completeness critic found no wholly-unregistered attack surface (no new STRIDE
category, sink, import path, or parser).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-27 (two correctness residuals accepted for v1.3, tracked for hardening)
