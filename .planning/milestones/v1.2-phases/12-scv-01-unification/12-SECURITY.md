---
phase: 12
slug: scv-01-unification
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-16
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> SCV-01 unification — the console live preview becomes a same-origin `<iframe src="/overlay?preview=1">`
> reusing the one frozen renderer; the hand-maintained Python↔JS byte-mirror + `POST /score/preview`
> drift-guard are deleted (net surface reduction).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator browser → console `GET /` (LAN) | Single-operator LAN, no auth (accepted, `docs/security.md`). Serves `console.html` with the new same-origin iframe. | Score field values (operator-typed) |
| OBS CEF / console iframe → `GET /overlay?preview=1` (same-origin LAN) | The `preview` query arg crosses here; closed boolean, never reflected unescaped. Same frozen renderer OBS loads. | `preview` flag (`"1"` or ignored); sanitized score values |
| operator browser → console POST (LAN) | `POST /score/preview` is **deleted** this phase — a net reduction of one input surface. `POST /score` survives. | Score field values (operator-typed) |
| test harness → node subprocess (offline) | `test_value_crosscheck` runs the served JS in a temp `.cjs` via `_run_node` (offline, 30s timeout, no network). | Local test fixtures only |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-12-01 | Tampering | Test payloads in `test_value_crosscheck` (control-char / >64-char inputs through node) | mitigate | Payloads are local test fixtures executed in a temp `.cjs`; `_run_node` runs offline with a 30s timeout, no network; no production code path touched. | closed |
| T-12-02 | Information Disclosure | Tests build `create_app` over a `tempfile.mkdtemp()` channel dir | accept | No real data, no secrets, LAN-only test client. → Accepted Risks Log. | closed |
| T-12-SC | Tampering (supply chain) | npm/pip/cargo installs (plan 12-01) | accept | No package install this phase (12-RESEARCH "Package Legitimacy Audit: Not applicable"). → Accepted Risks Log. | closed |
| T-12-02-01 | Tampering | `preview` query-arg in `get_overlay()` | mitigate | Verified `app.py:300` `preview = request.args.get("preview") == "1"` — closed boolean; any other value → no preview. Sets a fixed CSS class via an autoescaped Jinja boolean; never used as a path or reflected as raw text. | closed |
| T-12-02-02 | Information Disclosure | `body.preview` backdrop CSS (`#6b6f76`) | accept | Cosmetic mid-gray fill on the preview fork only; no data, no new endpoint; default `/overlay` transparency contract unchanged. → Accepted Risks Log. | closed |
| T-12-02-03 | Elevation / Spoofing | deleted `POST /score/preview` | mitigate (defensive) | Verified removed from `app.py` — `git grep "/score/preview"` and `post_score_preview` return zero hits. Eliminates one POST endpoint entirely (net security improvement on the LAN). | closed |
| T-12-02-SC | Tampering (supply chain) | npm/pip/cargo installs (plan 12-02) | accept | No package install this phase. → Accepted Risks Log. | closed |
| T-12-03-01 | Tampering | HTML injection via operator score values rendered in the iframe | mitigate | Verified the iframe loads the SAME frozen `overlay-render.js`, which writes every value via `textContent = cleanField(v)` — `innerHTML` appears only in comments (lines 11/117/148), never as a write sink. Re-asserted by the unchanged `test_no_innerhtml_sink`. No new sink in `console.html`. | closed |
| T-12-03-02 | Spoofing / Tampering | iframe clickjacking / framing | accept | Same-origin, LAN-only, single-operator — out of the v1 threat model (`docs/security.md`). If a deploy adds `X-Frame-Options` it must allow same-origin (Assumption A1). → Accepted Risks Log. | closed |
| T-12-03-03 | Tampering (defensive) | reduced JS surface (mirror deletion) | mitigate | Verified the `gsd:scv01-mirror` block + all wiring (`mirrorOverlayText`/`cleanField`/`scvGet`/`updateScorePreview`/`driftCheck`/…) are gone from `console.html` (zero leftover refs; only the new `.overlay-preview-frame` matches `overlay-preview`). Deletes a duplicated sanitize implementation; the single renderer copy remains the one source (no second `cleanField` to drift). | closed |
| T-12-03-SC | Tampering (supply chain) | npm/pip/cargo installs (plan 12-03) | accept | No package install this phase. → Accepted Risks Log. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-02 | Tests run over `tempfile.mkdtemp()` with a LAN-only test client; no real data or secrets. | operator (gate, 2026-06-16) | 2026-06-16 |
| AR-12-02 | T-12-SC / T-12-02-SC / T-12-03-SC | No npm/pip/cargo installs this phase (12-RESEARCH "Package Legitimacy Audit: Not applicable"); pytest + node already present. | operator (gate, 2026-06-16) | 2026-06-16 |
| AR-12-03 | T-12-02-02 | `body.preview` backdrop is a cosmetic mid-gray on the preview fork only; no data exposed, default `/overlay` transparency unchanged. | operator (gate, 2026-06-16) | 2026-06-16 |
| AR-12-04 | T-12-03-02 | iframe clickjacking/framing is out of the v1 single-operator LAN threat model (`docs/security.md`); same-origin embed. | operator (gate, 2026-06-16) | 2026-06-16 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-16 | 11 | 11 | 0 | /gsd-secure-phase (orchestrator; auditor skipped per operator gate "Accept all open", mitigations verified first-hand via grep) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-16
