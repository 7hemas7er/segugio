---
phase: 18
slug: rich-data-model-overlay-continuity-regression
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-27
---

# Phase 18 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register authored at plan time (both 18-01 and 18-02 carry a `<threat_model>` block);
> verified in **verify-mitigations mode** by gsd-security-auditor on 2026-06-27.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client → API (`POST /score`) | Operator-typed raw inputs (incl. new free-text `cane`/`conduttore`/`giudici`) cross into the authoritative server; validated/recomputed before any write. | Untrusted operator strings + numeric score inputs |
| server → on-disk publish (`score.json` / `overlay.txt`) | `compute()` output (incl. new `str(Decimal)` subkeys) serialized to disk. | Recomputed score document |
| operator free-text → broadcast overlay (CEF browser source) | `cane`/`conduttore` cross from the console into the live broadcast DOM via `renderIdentity`. | Untrusted display strings → broadcast HTML |
| operator free-text → `overlay.txt` (OBS read-from-file text source) | Score/identity values render into the always-on text fallback line. | Cleaned single-line text |
| operator free-text → entry-form preview DOM | `cane`/`conduttore`/`giudici` echo into the form preview. | Untrusted display strings → form HTML |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-18-01-A | Denial of Service | `score_calc.compute()` subkeys → `write_score` `json.dumps` | mitigate | Every new subkey value is `str(Decimal)` (`score_calc.py:309/331/361/364/372`); a raw `Decimal` would `TypeError`→500. Heavy-absent rich-POST gate `tests/test_imports.py:121/141` asserts 200/204, never 500. | closed |
| T-18-02-A | Tampering | new identity free-text through `_parse_structured_inputs` (unvalidated) | mitigate | Identity is display-only (`app.py:161-163`, copied verbatim, never recomputed); `render_overlay_text` reads only flat scalar keys (`score_render.py:64-86`) — dict/list subkeys never reach the text sink. No new sink in 18-01. | closed |
| T-18-03-A | Tampering | frozen `/overlay-json` contract | mitigate | D-05 golden snapshot (`tests/test_ui_overlay_json.py:318/324/327`): 6-key envelope `==`-frozen + per-discipline legacy flat-key subset; any rename/removal/new top-level key fails CI. | closed |
| T-18-04-A | Denial of Service | torn/non-finite `score.json` poisons `/overlay-json` | accept | No new `json.load`/`open` in the route (`app.py:409-431`); backed by pre-shipped never-raise readers + dict-guard + `parse_constant` non-finite reject (`opcomm/channel.py:52-90,124-131`). No new surface. | closed |
| T-18-SC-A | Tampering (supply chain) | npm/pip/cargo installs | accept | Zero new runtime deps this phase (`18-01-SUMMARY.md` `tech-stack.added: []`); no `[ASSUMED]`/`[SUS]` packages. | closed |
| T-18-01-B | Tampering / Elevation | crafted `<script>` in `cane`/`conduttore` → broadcast HTML injection on `/overlay` lower-third | mitigate | `renderIdentity` builds competitor via `document.createTextNode` only (`overlay-render.js:150-171`); no `innerHTML`. D-07b node fake-DOM `tests/test_overlay_html_sink_gate.py:87` asserts `childElementCount === 0` on `<script>x</script>` (ran under node v24, 0 skips). | closed |
| T-18-02-B | Tampering / Elevation | crafted `<script>` in identity free-text → form-preview HTML injection | mitigate | Preview echo via `textContent` only (`score-entry.js:186-196`). D-07b form assertion `test_form_preview_script_payload_inert:145` → `children.length === 0`. | closed |
| T-18-03-B | Tampering | operator value injects an extra `overlay.txt` line / overflows the OBS text source | mitigate | `_clean` strips CR/LF + control chars and caps each field at 64 (`score_render.py:29,32-46`). D-06 `tests/test_overlay_fallback_gate.py:76/161` asserts single non-empty line + 64-cap after a rich POST. | closed |
| T-18-04-B | Information Disclosure | `/overlay` host page bakes live score/identity into served HTML | mitigate | Page stays thin/poll-only (`overlay.html:233-234`, static branding only); `Cache-Control: no-store` (`app.py:453`). `tests/test_ui_overlay_page.py` green. | closed |
| T-18-SC-B | Tampering (supply chain) | npm/pip/cargo installs | accept | Zero new runtime deps this phase (`18-02-SUMMARY.md` `tech-stack.added: []`); node + pytest already present. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Freeze Target

`src/segugio/ui/score_render.py` last modified in commit `9b85ad7` (phase 05-05) — **not in any phase-18 commit** (`996d6ac`/`fe4f249`/`d7bbea0`/`2a3b262`/`627ec60`/`6f32b2f`). FREEZE invariant honored.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-18-01 | T-18-04-A | Torn/non-finite `score.json` poisoning `/overlay-json` is mitigated by pre-shipped never-raise readers, dict-guards, and `parse_constant` non-finite rejection in `opcomm/channel.py`. This phase adds no `json.load`/`open` to the `/overlay-json` route — no new attack surface. | gsd-security-auditor | 2026-06-27 |
| AR-18-02 | T-18-SC-A, T-18-SC-B | Supply-chain via npm/pip/cargo: phase introduces zero new runtime dependencies (both SUMMARYs declare `tech-stack.added: []`); node + pytest already present. No legitimacy checkpoint required. | gsd-security-auditor | 2026-06-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-27 | 10 | 10 | 0 | gsd-security-auditor (opus), verify-mitigations mode |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-27
