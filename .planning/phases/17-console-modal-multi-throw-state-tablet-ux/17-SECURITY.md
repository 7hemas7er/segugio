---
phase: 17
slug: console-modal-multi-throw-state-tablet-ux
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-27
---

# Phase 17 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (both 17-01 and 17-02 carried a `<threat_model>` block); the
> gsd-security-auditor verified each `mitigate` mitigation exists in code and each `accept`
> rationale still holds. Result: **SECURED, threats_open: 0**.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator browser → `POST /score` (LAN) | The sole authoritative write path; the only path that changes what airs. | Untrusted operator-typed score input (validated + recomputed server-side). |
| localStorage ↔ score-entry component | Operator-typed draft persists locally; read back into the DOM on restore. | Advisory-only in-progress throw list (never the air authority). |
| `/overlay-json` → console readout DOM | Server payload (operator-typed fields) rendered into the read-only on-air readout. | Public overlay state (the data OBS already renders). |
| served JS → DOM | All rendered values cross into the page (XSS sink surface). | Operator/draft/server strings. |
| direct LAN POST → `/score` (no UI) | An attacker on the dedicated WiFi can POST without the console UI. | Untrusted input — server validates+recomputes regardless. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-17-01 | Tampering | localStorage draft (operator can hand-edit/corrupt the key) | mitigate | `restoreDraft()` wraps `JSON.parse(localStorage.getItem(DRAFT_KEY))` in try/catch → empty draft on error (`score-entry.js:266-285`); `Array.isArray` guard (L274); draft only pre-fills value/checked; air authority is server-recomputed `POST /score`. | closed |
| T-17-02 | EoP / Tampering | client-only validation bypass via direct LAN POST | accept | Authoritative server path unchanged: `_parse_structured_inputs → validate → 400-on-error → compute → atomic write` (`app.py:348-354`). Client confirm/Enter-guard add no client authority. | closed |
| T-17-03 | Tampering (XSS) | restored draft values + confirm-button label morph reaching the DOM | mitigate | Confirm morph uses `textContent`/`classList` only (`score-entry.js:214-215,222-223`); restored draft via value/checked (279-281). No `innerHTML =` sink; no-innerHTML pytest gate green. | closed |
| T-17-04 | DoS / integrity | accidental on-air of a half-entered score (casual tap or Enter) | mitigate | Two-step arm gate returns before POST on first tap, submits only when `armed` (`score-entry.js:218-232`); 4000ms auto-revert (L204/L225); Enter guard preventDefaults with no submit path (239-244). UAT: 0 POSTs across arm + Enter tests. | closed |
| T-17-05 | Tampering / EoP | retiring the legacy `post_score` branch must not weaken validation on the authoritative JSON path | mitigate | Single write path in `post_score` (`app.py:317-354`); legacy branch + helpers removed (`_is_legacy_score_post`/`_NON_SCORE_KEYS`/`_STRUCTURED_KEYS` grep = 0). Validate-before-write intact; crash-isolation smoke green. | closed |
| T-17-06 | Tampering (XSS) | console readout rendering `/overlay-json` fields | mitigate | `pollOverlayJson` writes via `textContent` only (`console.html:735,742`); no `innerHTML` in the new readout/poll code. Crafted `<script>` renders inert. | closed |
| T-17-07 | Information Disclosure | the modal/partial baking privileged data into `console.html` | accept | `index()` injects the SAME public `_score_cfg` blob already served on `/score-entry` (`app.py:224-228,297,308`) — `{sport, disciplines, profile}` decimal strings, no secrets/PII. Readout reads only public `/overlay-json`. | closed |
| T-17-08 | DoS | the `/overlay-json` readout poll adding load / starving `/command` | accept | Readout reuses the existing named idempotent poll interval (`console.html:780`, cleared in `stopPolling` L785); server threaded (waitress / `threaded=True`, `app.py:555-561`). No long-lived worker thread. | closed |
| T-17-SC | Tampering | npm/pip/cargo installs (registered in both 17-01 and 17-02) | accept | ZERO new dependencies this phase (`tech-stack.added: []`); templates reference only `/static/...`; external script/style src grep = 0. No install task → no package-legitimacy gate needed. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-17-01 | T-17-02 | Client-side validation is a UX pre-filter only; the authoritative `POST /score` validates+recomputes server-side, so a direct LAN POST cannot air an invalid score. No new client authority added this phase. | gsd-security-auditor (verified) | 2026-06-27 |
| AR-17-02 | T-17-07 | The injected `score_cfg` is the same public scoring-profile blob already served on `/score-entry` (no secrets/PII); the readout reads only the public `/overlay-json`. | gsd-security-auditor (verified) | 2026-06-27 |
| AR-17-03 | T-17-08 | The on-air readout reuses the existing console poll cadence (one same-origin GET on an already-polled-class endpoint); the threaded/Waitress server keeps override POSTs unblocked (the v1.1 SAFETY control). | gsd-security-auditor (verified) | 2026-06-27 |
| AR-17-04 | T-17-SC | Zero new runtime dependencies this phase (vanilla JS + native browser APIs + stdlib server); no install surface to vet. | gsd-security-auditor (verified) | 2026-06-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-27 | 9 | 9 | 0 | gsd-security-auditor (opus) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-27
