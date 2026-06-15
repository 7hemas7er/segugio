---
phase: 11
slug: shared-graphical-renderer-overlay-page-branding
status: secured
threats_total: 13
threats_closed: 12
threats_accepted: 1
threats_open: 0
asvs_level: 1
block_on: high
created: 2026-06-15
audited: 2026-06-15
---

# Phase 11 — Shared Graphical Renderer / Overlay Page & Branding — Security Audit

**Mode:** VERIFY-MITIGATIONS (register authored at plan time = TRUE)
**Audited:** 2026-06-15
**ASVS Level:** L1
**block_on:** high
**Auditor:** Claude (gsd-security-auditor)
**Status:** SECURED (13/13 threats resolved — 12 CLOSED, 1 accepted-and-documented config-boundary risk)

This audit verifies that each declared mitigation in the Phase 11 threat register is actually
present in the implemented code. Implementation files were treated as READ-ONLY. Evidence is
file:line, not documentation or intent.

---

## Threat Verification Summary

| Threat ID | Category | Disposition | Result | Evidence |
|-----------|----------|-------------|--------|----------|
| T-11-01-01 | Tampering (crash-isolation) | mitigate | CLOSED | `app.py` module-top imports = `os`/`threading`/`time` + `..opcomm` + `.score_render` only (lines 30-56); Flask imported in-factory (line 118); `load_config` lazy inside `__main__` (line 378); `tests/test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent` GETs `/overlay` under heavy-absent block |
| T-11-01-02 | Info Disclosure (LAN branding) | accept | CLOSED | Non-sensitive branding; LAN-trust posture documented in `docs/security.md` (T-05-05-04, reaffirmed v1.1); recorded in accepted-risks log below |
| T-11-01-03 | Tampering (theme→CSS-var sink) | mitigate (PARTIAL / CR-01) | ACCEPTED RISK | `event_name`/`logo_path` autoescaped (overlay.html:224, :235 — HTML context). Theme `theme_*` CSS-var sink is NOT escaped for CSS metacharacters (overlay.html:37-39); no validator in `models.py:196-201`; env path unvalidated (`app.py:400-409`). Owner-accepted config-boundary risk (see CR-01 disposition below) |
| T-11-01-SC | Supply chain | mitigate | CLOSED | Zero dependency-manifest changes in the phase-11 commit range (`git diff f26a4e1..HEAD` touches no `pyproject.toml`/`requirements.txt`/`package.json`) |
| T-11-02-01 | Tampering (config→HTML) | mitigate (PARTIAL / CR-01) | CLOSED (residual = CR-01) | Jinja autoescape ON for `event_name` (overlay.html:224) and `logo_path` `<img src>` (overlay.html:235); no raw `innerHTML` of config in the inline bootstrap script (overlay.html:243-250 emits a numeric only). Residual theme CSS-var sink tracked under CR-01 |
| T-11-02-02 | DoS (perpetual CSS animation) | mitigate | CLOSED | `@keyframes enter/exit/pulse` use transform/opacity only (overlay.html:177-191); `.is-entering`/`.is-exiting` use `forwards`, `.pulse-once` uses `1` (run-once) (overlay.html:194-197); grep for `infinite` → no matches |
| T-11-02-03 | Product invariant (action-area coverage) | mitigate | CLOSED | Title-safe band: `position: fixed; left: 4.5vw; bottom: 6vh; max-width: 60vw; max-height: 18vh` (overlay.html:49-54); logo bug bottom-right (overlay.html:160-168); no full-width/top-anchored banner class |
| T-11-03-01 | Tampering/Elevation (HTML-injection, HIGH — dominant) | mitigate | CLOSED | Every operator value written via `textContent = cleanField(v)`: `fillCell` (overlay-render.js:114, :117), `renderIdentity` text nodes (:151-160), `paintTimer` (:325); `cleanField` ports `_clean` (strip control chars, keep U+0020, trim, cap 64 — :37-50); NO `innerHTML` assignment anywhere (only 3 comment mentions: :11, :117, :148) |
| T-11-03-02 | Tampering (stale-as-live) | mitigate | CLOSED | `isStale()` keys on response recency `everResponded && Date.now() - lastResponseAt > STALE_MS` (overlay-render.js:295-297); `tick()` stops the rAF (`rafId = null`) + `applyStale()` on stale (:334-338); `applyStale` adds `.is-stale` degrade (:355-359); cold-start guard `everResponded` (:274, :296); fetch error coasts without stamping `lastResponseAt` (:421-424); live-idle (flat gen) NOT degraded — liveness stamped before the gen-render gate (:414-419). See re-implementation note below |
| T-11-03-03 | Spoofing (clock skew) | mitigate | CLOSED | `skew = p.server_now - Date.now()/1000` re-measured each poll (overlay-render.js:367); elapsed = `Date.now()/1000 + skew - startedAt` (:303); NO raw cross-machine `Date.now() - started_at` (only a "NEVER raw" comment at :300) |
| T-11-03-04 | DoS (over-fast polling / perpetual rAF) | mitigate | CLOSED | `setInterval(poll, PUBLISH_MS)` with `PUBLISH_MS = 200` (overlay-render.js:229, :435); re-render gated on `p.gen > lastGen` (:416); rAF `tick()` returns and nulls `rafId` on `!running || isStale()` (:334-338) — no idle burn |
| T-11-03-SC | Supply chain | mitigate | CLOSED | Zero new deps; `overlay-render.js` is vanilla ES2020, no imports/build step; no manifest change in the phase range |

**Resolution:** 12 CLOSED + 1 accepted-and-documented (CR-01). 0 BLOCKING OPEN threats.

---

## CR-01 — Theme-color CSS-variable injection (T-11-01-03 / T-11-02-01 residual)

### Technical facts CONFIRMED in code

1. **No validator on theme fields.** `OverlayParams.theme_accent/theme_plate/theme_text` are plain
   `str` with palette defaults and NO `field_validator` — deliberately ("Plain str (NOT
   hex-validated): an org may pass any CSS color token"). `src/segugio/config/models.py:196-201`.
2. **CSS-var sink present and not CSS-escaped.** The three theme strings are interpolated directly
   into an inline `<style>` block via Jinja: `--accent: {{ theme_accent | default('#34D399', true) }};`
   etc. `src/segugio/ui/templates/overlay.html:37-39`. Jinja autoescape is an HTML-context escape
   (`< > & " '`); it does NOT neutralize the CSS-dangerous characters `} ; : /` or the sequence
   `</style>`. A value such as `red; } body { background: url(...) }` breaks out of the
   `.lower-third` rule; `</style><img src=x onerror=...>` re-enters HTML context.
3. **Env override path unvalidated.** `SEGUGIO_OVERLAY_ACCENT` / `_PLATE` / `_TEXT` are read and
   piped straight into the render dict with no validation. `src/segugio/ui/app.py:400-409`. The
   `cfg.overlay.*` config path (lines 384-393) is equally unvalidated.

The `event_name` and `logo_path` HTML-context paths ARE safely autoescaped (overlay.html:224, :235)
— CR-01 is strictly the CSS-variable theme sink.

### Disposition: ACCEPTED config-boundary risk (owner decision)

Per the per-task instruction and the Phase 11 UAT (`11-UAT.md` test 4 / `11-VERIFICATION.md` human
item 4), the project owner has ACCEPTED this as a config-boundary risk: the values originate from
operator-authored config or operator-set env vars on an isolated single-operator rig LAN, NOT from a
remote-attacker-reachable input. The `/overlay` route does not accept theme values from any request
parameter — the only sink is the operator's own config/env.

### Is the accept rationale sound for ASVS L1 in this deployment?

**Yes, for the current Phase-11 deployment shape — with a flagged caveat.** The Phase 11 trust
boundary (`docs/security.md`, reaffirmed v1.1) is the dedicated, isolated, non-bridged WiFi LAN with
AP client-isolation; the operator is trusted and the theme values are operator-authored. ASVS L1's
input-validation/output-encoding controls (V5) target data crossing a trust boundary from an
untrusted source. The theme values do not cross such a boundary in this deployment: there is no
authenticated multi-user model, no remote write path to the theme, and `/overlay` is consumed by the
operator's own OBS/CEF browser source. Self-XSS / self-CSS-injection by the trusted operator into
their own rig is not an L1-blocking finding here. The injection is therefore an availability/footgun
concern (an operator could break their own overlay) rather than an exploitable cross-boundary vuln.

**This is the technically correct fix regardless, and it is cheap** (a `field_validator` CSS-color
allowlist on the three fields, routing the env path through the same model — see `11-REVIEW.md`
CR-01). Accepting it as a deferred hardening is defensible at L1 for an isolated rig, but the accept
is conditional on the trust boundary staying as documented.

### MANDATORY re-evaluation trigger — Phase 12

**This acceptance MUST be re-evaluated in Phase 12.** Phase 12 embeds `/overlay` as a console iframe
(`11-02-SUMMARY.md` affects; `11-03-SUMMARY.md` affects). Embedding the page inside the operator
console changes the sink's blast radius: a CSS/markup breakout (`</style>...`) then executes inside
the console's origin/DOM context rather than only an OBS browser source, and the theme values may
flow through a console-side render path. The config-boundary rationale that makes this acceptable at
Phase 11 does NOT automatically carry to an iframe-embedded context. The `field_validator` fix
SHOULD land before or with the Phase-12 iframe embed.

---

## Accepted Risks Log

| Risk ID | Description | Disposition basis | Re-evaluate when |
|---------|-------------|-------------------|------------------|
| T-11-01-02 | `GET /overlay` on `0.0.0.0` exposes non-sensitive branding (event/logo/theme) to the LAN | Branding is non-sensitive; the LAN-as-trust-boundary + AP-client-isolation posture already accepts live video/score exposure (`docs/security.md` T-05-05-04 / T-08-03, reaffirmed v1.1). No new blast radius | Deployment stops being a dedicated single-operator isolated LAN (multi-tenant/internet/shared WiFi) |
| CR-01 (T-11-01-03 / T-11-02-01 residual) | Theme `theme_*` CSS-var values injected into an inline `<style>` without CSS-context escaping; config model + env path unvalidated | Operator-authored config/env on an isolated rig LAN; not a remote-attacker vector; self-injection only (`11-UAT.md` test 4) | **Phase 12** — `/overlay` embedded as a console iframe changes the blast radius (CSS/markup breakout would run in the console DOM). Add the `field_validator` CSS-color allowlist before/with the iframe embed |

---

## Implementation Notes Verified

- **T-11-03-02 watchdog re-implementation (quick 260615-tsi).** The freshness watchdog was
  re-implemented to key on console RESPONSE recency (`lastResponseAt`/`everResponded`) instead of
  gen-age. Verified the CURRENT code (overlay-render.js:295-297, :334-338, :414-419) STOPS the rAF
  timer and dims (`.is-stale`) on a dead source, and does NOT falsely degrade a live idle run: a
  successful poll stamps `lastResponseAt`/`everResponded` BEFORE the `p.gen > lastGen` render gate,
  so a live console answering polls with a flat `gen` (no new score) stays fresh. This correctly
  closes the "stale-as-live" threat while avoiding the false-positive degrade of a live idle run.
- **CEF poll nonce (quick 260615-sod).** `?t=<++reqSeq>` is a unique-per-request cache-buster
  (overlay-render.js:411) — a hardening of the poll path, consistent with the no-store contract; not
  a threat-register item but noted as it touches the T-11-03-04 poll surface (still PUBLISH_MS-paced).

---

## Unregistered Flags (new attack surface with no threat mapping)

None.

- `11-01-SUMMARY.md` and `11-02-SUMMARY.md` contain no `## Threat Flags` section.
- `11-03-SUMMARY.md` `## Threat Flags` = "None. No new security surface beyond the plan's
  `<threat_model>`: no new endpoints (pure consumer of `/overlay-json`), no new auth path, no file
  access, no schema change."
- The phase introduces one new GET route (`/overlay`) and one static asset
  (`/static/overlay-render.js`), both already mapped in the threat register (T-11-01-01/02/03,
  T-11-03-*). The new `SEGUGIO_OVERLAY_*` env vars feed the CR-01 sink already tracked.

No new, unmapped attack surface appeared during implementation.

---

## Scope & Method

- Verified each threat against the cited implementation files by grep/read for the declared
  mitigation pattern at its sink/entry point — not by accepting the SUMMARY/REVIEW narrative.
- Confirmed the dominant HIGH threat (T-11-03-01) holds at EVERY operator-value sink (`fillCell`,
  `renderIdentity`, `paintTimer`), not just one.
- Confirmed supply-chain claims by diffing the phase commit range for dependency-manifest changes.
- Did NOT scan for new vulnerabilities beyond the authored register (VERIFY-MITIGATIONS mode).
- Implementation files were NOT modified.
