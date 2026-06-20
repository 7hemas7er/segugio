# Segugio — v1.1 threat re-evaluation

This is the written security re-evaluation for the **v1.1 "Console Regia — visibilità live"**
milestone (D-09, Phase 8 success criterion 5). Phase 8 is the first phase to put **live
competitor video** behind the operator console's `0.0.0.0` endpoint, so the threat model is
re-assessed here.

The conclusion up front: **the v1.0 security posture is reaffirmed, not changed.** The dedicated
WiFi LAN remains the trust boundary; no authentication is added; no configurable bind and no
shared-token gate are added. The v1.1 mitigation for the new live-video exposure is
**operational** (the access point's network configuration) and **documented** (this file) — it is
deliberately *not* in code. Phase 7's `preview.enabled` config flag is the source-side off-switch.

---

## Trust boundary (reaffirmed from v1.0)

The dedicated WiFi LAN is the trust boundary. Segugio is a **single-operator field tool**: one
operator on one tablet drives one console over a dedicated, isolated wireless network at the
competition site. The console binds `0.0.0.0:8080` so the operator's tablet can reach it over
that WiFi; it is **never internet-facing**.

Running **no authentication** on that console is an **accepted, documented decision — not an
oversight** (threat **T-05-05-04**). Adding per-user access control to a single-operator
field tool buys nothing and adds operational friction (a login to fumble in field light, a
password to lose) on the safety-critical override path. This stance was accepted in v1.0 and is
reaffirmed here.

The console's existing v1.0 threat register (documented as docstrings in
`src/segugio/ui/app.py`) is cross-referenced and restated:

- **T-05-05-01 — path traversal / whitelisted server-side paths.** The operator never supplies a
  filesystem path. The opcomm channel write paths are FIXED server-side (`channel_dir` + constant
  filenames). The discipline is whitelisted to the closed `Discipline` enum (unknown → 400).
- **T-05-05-02 — overlay sanitization.** Overlay text is constrained/sanitized by the renderer
  before it reaches the OBS read-from-file text source.
- **T-05-05-03 — contradictory-command rejection.** A command that both forces and releases is
  rejected by `OperatorCommand.__post_init__` and returned as 400 — a malformed command never
  reaches the FSM, never written.
- **T-05-05-04 — LAN trust boundary / no-auth.** The `0.0.0.0` bind exposes the console to anyone
  on the dedicated WiFi LAN. That LAN *is* the trust boundary; no auth in v1 is an accepted,
  documented field-tool decision, not an oversight.

These threats live as docstrings in `src/segugio/ui/app.py` (the `T-05-05-*` notes at the top of
the module). The orchestrator (`src/segugio/orchestrator/loop.py`) holds no separate `T-05-05-*`
ids — the operator-facing trust boundary is the console's `0.0.0.0` surface.

---

## What changed in v1.1

The console used to serve a **control panel** ("operate blind"). In v1.1 the console also serves
**live competitor video**: per-camera JPEG thumbnails published off-tick by the orchestrator and
served from the `0.0.0.0:8080` endpoint to render the live multiview.

The **blast radius grew from a control panel to live video** (STRIDE: **Information
Disclosure**, threat **T-08-03**). Anyone on or near the dedicated WiFi LAN who can reach
`0.0.0.0:8080` can now also see the live competitor feeds, not just the control surface.

The new Phase-8 route surface is:

- `GET /preview` — returns the `preview.json` "why" sidecar via `read_preview` (a safe-default,
  never-raise reader).
- `GET /preview/<cam>.jpg` — serves a per-camera JPEG thumbnail.

Two existing in-code controls bound this new surface (these are NOT new auth — they are the
already-shipped correctness controls that contain the new route):

- **Path-traversal mitigation (T-05-05-01).** `<cam>` is whitelisted against the configured
  camera ids and is NEVER used as a raw filesystem path. The on-disk file is built from a FIXED
  `cam_{id}.jpg` prefix; an unknown id (including a traversal segment) → 404. The raw URL segment
  never becomes a path.
- **Override-availability (`threaded=True` / Waitress).** The console serves preview GETs
  concurrently so a stream of `/preview/<cam>.jpg` requests can never pin the lone WSGI worker
  and starve the safety-critical `/command` override POST. Serving live video must never make the
  override path unanswerable.

Note that the published JPEGs are **ephemeral, overwritten in place** — there is no on-disk
history of competitor footage accumulating behind the endpoint.

---

## HARD operational requirement (the v1.1 mitigation)

The mitigation for the live-video exposure is **operational, not in-code**. It is a **HARD
requirement** of any Segugio deployment:

- The dedicated access point **MUST enforce client isolation** (also called AP isolation / client
  separation) so that LAN clients cannot reach each other beyond what the console↔tablet flow
  needs.
- The dedicated AP **MUST NOT be bridged** to the internet, to a venue/guest network, or to any
  other network. **No internet bridge, no guest bridge.**

If the AP lacks client isolation or is bridged, the documented trust boundary leaks and the
accepted no-auth posture no longer holds. Enforcing these two network controls IS the v1.1
mitigation for putting live competitor video behind `0.0.0.0`.

---

## Source-side off-switch: `preview.enabled`

Phase 7's `preview.enabled` config flag is the **source-side off-switch** for the live video. When
`preview.enabled` is false, the orchestrator writes **no JPEGs** — so there is nothing for the
console to serve. Disabling preview at the source removes the exposure entirely; the console
routes simply 404.

There is **no separate console-side preview kill-switch** in Phase 8 (a live operator preview
kill-switch is Phase 9 / UXT-03). The source-side `preview.enabled` flag is the off-switch for v1.1.

---

## Explicitly NOT added in v1.1

To be unambiguous (D-09): in v1.1 Segugio adds

- **NO new authentication** on the console or the preview routes;
- **NO configurable bind** (the console binds `0.0.0.0:8080` as in v1.0);
- **NO shared-token gate** on the preview or control routes.

These were considered and **rejected** for v1.1: they re-litigate the accepted single-operator-LAN
posture and add code/config beyond the stated "written re-evaluation" deliverable. The
LAN-as-trust-boundary + AP-client-isolation posture stands.

**Revisit only if the deployment context changes** — i.e. if Segugio stops being a dedicated
single-operator LAN field tool (multi-tenant venue network, internet exposure, shared/untrusted
WiFi). At that point this re-evaluation must be redone and in-code controls reconsidered.

---

## What changed in v1.2 — browser-source overlay (Phase 13)

The new OBS **browser-source** (`Score Overlay`) is a **same-origin LAN consumer** of the existing
`GET /overlay` route shipped in Phase 11 — it adds **NO new server route and NO new code path**:
it is just another client (the obs-browser CEF, on the OBS box) of an already-exposed, already-
assessed read endpoint. It is **display-only** (SCR-04): it renders operator-typed score values
**verbatim**, sanitized at the HTML sink via `textContent` (never `innerHTML`), and never
adjudicates. It reuses the established trust boundary **unchanged** — the dedicated WiFi LAN with
mandatory AP client isolation (threats **T-05-05-04** / **T-08-03**) — with **NO new
authentication, NO configurable bind, and NO new exposure** beyond what `0.0.0.0:8080` already
serves. The documented browser URL (`http://<console-LAN-IP>:8080/overlay`) carries no secret, and
the obs-websocket :4455 password stays out of the docs. Because the browser source is just another
reader of an already-exposed, already-assessed endpoint, the v1.1 posture is **reaffirmed, not
changed**. Revisit only if Segugio stops being a single-operator-LAN field tool.

## HTML-sink output encoding re-affirmed (SC#4, Phase 14)

The Phase-14 hardening **re-affirms** the broadcast overlay's HTML-sink posture (OWASP V5 Output
Encoding), gated by the SC#4 named test in 14-02: operator-typed score values sink into the
`/overlay` page via `textContent` (**never** `innerHTML`), and the static branding strings
`event_name` / `logo_path` are **Jinja-autoescaped** where they render into the page at the console
entrypoint. A crafted score value or event name therefore cannot inject markup into the CEF
overlay on the OBS box — it renders verbatim as text. No new control is added here; this is the
already-shipped encoding posture, re-stated and test-gated.
