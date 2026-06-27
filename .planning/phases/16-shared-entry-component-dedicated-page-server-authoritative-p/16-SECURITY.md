---
phase: 16
slug: shared-entry-component-dedicated-page-server-authoritative-p
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-27
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (16-01 + 16-02 both carry a `<threat_model>` block). Verified
> 2026-06-27 by an adversarial multi-agent audit (12 independent skeptics + synthesis + completeness
> critic) followed by **three rounds of re-verification** that drove three real remediations:
> the audit found, and the fixes closed, a malformed-numeric-input class on the authoritative
> `POST /score` gate that a single-pass audit would have rubber-stamped.

## Remediation commits (this audit)

| Commit | Closes | Change |
|--------|--------|--------|
| `d797d98` | non-finite class | `_to_decimal` rejects non-finite Decimals (`if not d.is_finite(): return None`) — `NaN`/`sNaN`/`Infinity`/`inf` became an unhandled 500 (or, on freestyle `adjustment`, aired a literal `"NaN"`/`"-Infinity"` total). |
| `f26bfa8` | finite-magnitude class | `validate()` magnitude bound `value.adjusted() >= _MAX_FIELD_ADJ_EXP (7)` (trap-free — `abs(d)`/`d >= Decimal("1e7")` would itself raise `decimal.Overflow`) on `adjustment`/`course_faults`/`course_deductions`, **plus** a route-level `try/except (ArithmeticError, ValueError) → 400` around `compute()` (no new import). `1E999999999` → 500 and `1e1000` → aired-1001-digit-total closed. |
| `8642d39` | precision class | `validate()` precision bound `len(d.as_tuple().digits) > _MAX_FIELD_DIGITS (15)` — a small-magnitude/ultra-high-precision value (`"9."+5000 nines`, `adjusted()==0`) slipped the magnitude bound and, on the `deduct_from_100` model, wrote `str(course_deductions)` raw into the `faults_breakdown.course` subkey. |

22 regression cases added (`test_non_finite_inputs_rejected_400_writes_nothing`, `test_astronomical_magnitude_rejected_400_writes_nothing`, `test_high_precision_deduct_rejected_no_garbage_subkey`, + `score_calc` unit tests); full suite green save the 5 documented pre-existing env failures.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser/curl → `POST /score` (Flask) | Untrusted operator input (and any stale-tab / direct-LAN POST). The dedicated WiFi LAN has **no auth in v1** (accepted decision, T-05-05-04) — the server route is the ONLY gate. | Raw operator score inputs |
| `POST /score` → `score.json` / `overlay.txt` (atomic write) | The on-air broadcast surface. | Recomputed Decimal score doc |
| Operator free-text → DOM (CEF / browser) | Freestyle `nome`, identity, server-echoed errors render into the page and overlay. | Untrusted display strings |
| `GET /score-entry` → injected `score_cfg` blob | Server-rendered profile blob; must carry no float-drifted numerics, no heavy-import dependency. | Decimal-string profile |
| `score-entry.js` → `POST /score` | Client sends RAW inputs only; the server is the authority. | Raw inputs (never a client total) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Status Evidence | Status |
|-----------|----------|-----------|-------------|-----------------|--------|
| T-16-01 | Tampering (input validation) | `POST /score` server gate | mitigate | validate-before-write → 400 + write-nothing (`app.py:355-361`); CR-01 `is_json=isinstance(json_body,dict)` (`app.py:339`), CR-02 non-list `throws` (`score_calc.py:200-205`); **non-finite** (`_to_decimal` `is_finite`), **magnitude** (`adjusted()>=7`), **precision** (`digits>15`) bounds + route `compute()` `try/except→400`. Live re-attack: every malformed numeric across all 3 disciplines + both agility models → 400, zero 500s. | closed |
| T-16-02 | Tampering (path/discipline) + broadcast integrity (malformed numeric) | `Discipline(raw)` + write path + numeric airing | mitigate + accept (AR-16-01) | Fixed write filenames `_SCORE_FILE`/`_OVERLAY_FILE` (`app.py:62-66`, operator supplies no path); `Discipline(raw)` whitelist → 400 on unknown/path-like (`app.py:343-347`). No malformed numeric crashes (500) or airs a garbage **total** (overlay.txt + headline bounded). Residual verbatim-echo of oversized raw text into `/overlay-json` → **AR-16-01** (accepted). | closed |
| T-16-03 | Tampering (double source of truth) | `score-calc.js` advisory port | mitigate | `collectRaw()` POSTs RAW inputs only (`score-entry.js:546-570`); server Decimal recompute is the SOLE write; node-vs-Python drift-guard (`test_ui_score_calc_js.py`). | closed |
| T-16-04 | DoS (overlay/timer integrity) | atomic write + `_bump_score_gen` | mitigate | temp+flush+fsync+`os.replace` (`atomic.py:74-96`); gen-bump under `_gen_lock` preserves `running`/`started_at` (`app.py:276-290`); `/score` never writes `runstate.json`. | closed |
| T-16-05 | Tampering (broadcast integrity) | prior on-air score on a rejected submit | mitigate | validate-before-write leaves `score.json`/`overlay.txt` byte-identical (`test_invalid_post_400_writes_nothing` + the 22 new malformed-numeric cases all assert byte-equality). | closed |
| T-16-06 | DoS (crash-isolation, Plan 01) | profile injection / heavy imports | mitigate | `profile` plain arg; default `CSEN_DISC_PROFILE` stdlib; Flask/score_calc/config imports lazy in `create_app`/`__main__`; heavy+numpy/cv2-absent gate green. | closed |
| T-16-07 | Tampering / Elevation (XSS) | `score-entry.js` operator-value rendering | mitigate | All dynamic values via `textContent`/`createTextNode`; no `innerHTML` for dynamic data; `test_no_innerhtml_sink`. | closed |
| T-16-08 | Tampering (double source of truth, Plan 02) | submit path | mitigate | The POST body carries only raw inputs; the advisory total reaches the DOM via `textContent` only, never the wire (`score-entry.js:585-589`). | closed |
| T-16-09 | DoS (crash-isolation, Plan 02) | profile injection in `app.py` | mitigate | `adapt_scoring_profile`/`load_config` imported lazily, only in `__main__`+`_cfg_path`; `_profile_to_json` emits plain stdlib data; heavy-absent gate green. | closed |
| T-16-10 | Information disclosure / integrity (float drift) | `_profile_to_json` decimal serialization | mitigate | Every fractional value `str(Decimal)`; only `band`/`count_best_n` are JSON ints (pydantic-constrained, exact); JS parses strings, no `parseFloat` in the scorer. | closed |
| T-16-11 | Tampering (broadcast integrity, client view) | persistent publish banner | mitigate | Success + `localStorage` write only in the `resp.ok` branch (`score-entry.js:657-669`); a 400 keeps the draft and paints the server per-field errors; no optimistic on-air write. | closed |
| T-16-SC | Tampering (supply chain) | npm/pip/cargo installs | accept (AR-16-02) | Both SUMMARYs `tech-stack.added: []`; manifests untouched in the phase-16 window; no CDN/external asset. | closed |

*Status: open · closed* — *Disposition: mitigate · accept · transfer*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-16-01 | T-16-02 (residual) | **Verbatim-echo of oversized raw input into `/overlay-json`.** `GET /overlay-json` returns `fields` verbatim (the Phase-10 data contract) and `_parse_structured_inputs` echoes display-only fields (Phase-18 `cane`/`conduttore`/`giudici`, arbitrary throw subkeys) unchanged, so an oversized field value (e.g. `"0."+5000 zeros+"1"`, or a 100 KB `cane`) is written into `score.json` and served verbatim in the `/overlay-json` JSON payload. **Not broadcast-aired** — `render_overlay_text._clean` caps every `overlay.txt` field at 64 chars and the graphical `/overlay` (`overlay-render.js cleanField`) caps displayed cells at 64 and does not read these raw keys; the visible total stays bounded. **No crash** (every probe returned 204/400). The numeric VALIDATION gate (reject non-finite / absurd-magnitude / absurd-precision numerics → 400, no 500, no aired garbage total) is fully closed (commits `d797d98`/`f26bfa8`/`8642d39`). This residual is the **pre-existing** verbatim-echo property on the **accepted no-auth LAN** trust boundary (T-05-05-04, no auth in v1); the robust remedy is a **general** echoed-value / request-body length cap (tracked), not a per-field numeric bound. Accepted for v1.3; revisit if/when auth or WAN exposure is added. | user (2026-06-27) | 2026-06-27 |
| AR-16-02 | T-16-SC | Supply chain: Phase 16 installed zero new runtime deps (both SUMMARYs `tech-stack.added: []`); no CDN/external asset (offline rig). No legitimacy checkpoint required. | gsd adversarial audit (2026-06-27) | 2026-06-27 |

*Accepted risks do not resurface in future audit runs.*

**Tracked hardening:** `.planning/todos/pending/harden-overlay-json-echo-length-cap.md` (a general length cap on echoed `/overlay-json` field values / request body — covers the numeric and the existing free-text `cane`/`throws` echo paths in one place).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-27 | 12 | 12 (9 mitigations verified non-bypassable + the numeric gate hardened via 3 remediation commits + 3 accepts) | 0 | gsd adversarial multi-agent audit (12 verifiers + 3 re-verification rounds, opus) + remediations `d797d98`/`f26bfa8`/`8642d39` |

**Audit method:** Each threat verified by an independent adversarial agent (disprove-the-mitigation) against the live source with live Flask-test-client probes. The malformed-numeric class on the authoritative `POST /score` gate was found OPEN and driven to CLOSED across three fix→re-verify rounds (non-finite → magnitude → precision). The remaining `/overlay-json` verbatim-echo size residual was identified as the pre-existing, accepted no-auth-LAN echo property (independently reachable via the already-accepted free-text fields) and accepted with a tracked general-length-cap hardening item. No new STRIDE category, sink, import path, or parser surfaced.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-27 (numeric validation gate hardened across 3 commits; one verbatim-echo-size residual accepted for v1.3, tracked for a general length cap)
