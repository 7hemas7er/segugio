---
node_type: quick_plan
slug: run-md-ndi-hx-ops-notes
created: 2026-06-12
---

# Quick Task: docs/run.md — NDI HX operational notes

Update `docs/run.md` Prerequisites with the operational dritte that emerged from the
cyndilib NDI HX decode fix (commit 8048319, memory `cyndilib-no-hx-decode`). Doc-only;
no behaviour change.

## Changes
1. **NDI Tools / HX Driver required on the rig** — make explicit that the HX decode fix
   (`_prefer_system_ndi_runtime` in `src/segugio/ndi/ndi_source.py`) depends on a *system*
   NDI runtime (base 6.3.2) that version-pairs with the HX plugin. Without it cyndilib falls
   back to its bundled 6.1.1 base → discovers but cannot drive the 6.3.2 HX plugin → ZERO
   phone frames (mock-clip / full-NDI still decode). Sharpens the existing vague "libndi"
   note for HX phones specifically.
2. **Discovery on a multi-homed PC** — virtual NICs (VPN/Docker/Hyper-V) break mDNS; use
   NDI Access Manager to bind discovery to the right NIC/subnet.
3. **Phone camera view must be ACTIVE** in the sender app to advertise/serve frames.
4. **Source NAMES change** between apps/versions — discover the live name, put it in
   `ndi_source`, never hardcode. Reinforce existing note (lines 27-29).

## Acceptance
- Edits live only in the Prerequisites section; existing tone/structure preserved.
- No new "feature" framing — these are operational tips.
