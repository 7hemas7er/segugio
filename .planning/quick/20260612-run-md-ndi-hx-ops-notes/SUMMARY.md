---
node_type: quick_summary
slug: run-md-ndi-hx-ops-notes
status: complete
completed: 2026-06-12
---

# Summary: docs/run.md — NDI HX operational notes

Doc-only update to `docs/run.md` Prerequisites, capturing the operational dritte from the
cyndilib NDI HX decode fix (commit 8048319).

## What changed
- Sharpened the heavy-install bullet's vague "libndi" line to point at a dedicated NDI runtime
  prerequisite.
- Added a **NDI runtime on the rig** bullet: phone feeds are HX; HX decode needs the
  version-paired 6.3.2 plugin driven by a matching **system** base runtime. cyndilib's bundled
  6.1.1 discovers but decodes zero frames; `_prefer_system_ndi_runtime()` preloads the system
  6.3.2 base — but only if NDI Tools / HX Driver is installed. No install → no phone HX video
  (mock-clip / full-NDI still decode, which is why it can stay hidden).
- Expanded the `ndi_source` config bullet with three field gotchas: source names are not stable
  (discover, don't hardcode); the phone camera view must be ACTIVE; multi-homed discovery needs
  NDI Access Manager (virtual NICs break mDNS).

## Verification
- No code touched; no tests affected. Visual review of the Prerequisites section confirms tone
  and structure preserved, links intact.

## Files
- `docs/run.md` (Prerequisites section)
- `.planning/STATE.md` (Quick Tasks Completed table — section created)
