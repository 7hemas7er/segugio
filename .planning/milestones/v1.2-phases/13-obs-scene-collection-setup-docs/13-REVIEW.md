---
phase: 13-obs-scene-collection-setup-docs
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - obs/segugio-scene-collection.json
  - tests/test_scene_template.py
  - docs/obs-setup.md
  - docs/security.md
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 13 ships an OBS scene-collection template (`obs/segugio-scene-collection.json`),
a cross-reference test that keeps it in lockstep with the example configs, setup docs
(`docs/obs-setup.md`), and a v1.2 security re-evaluation (`docs/security.md`). The artifacts
are mostly sound: the JSON parses, the test logic correctly verifies scene-name overlap,
overlay z-order, and the obs-browser CEF keys, and the security doc's `textContent`/no-`innerHTML`
claim was verified against `src/segugio/ui/static/overlay-render.js`.

No BLOCKER issues. The defects below are correctness gaps in the test's coverage and a real
config/template/docs inconsistency that will bite an operator during the one-time manual import.

## Warnings

### WR-01: Template NDI source name does not match `config.example.yaml` cam_wide

**File:** `obs/segugio-scene-collection.json:126` and `docs/obs-setup.md:42`
**Issue:** The template's WIDE NDI source ships `ndi_source_name: "PHONE-WIDE (NDI HX3)"`, and
`docs/obs-setup.md` (line 42) uses `PHONE-WIDE (NDI HX3)` as the worked example of "the `ndi_source`
values in config". But `config.example.yaml` (the *primary* disc-dog reference config) sets
`cam_wide.ndi_source: "LOCALHOST (iPhone Camera for OBS Studio App)"` — NOT `PHONE-WIDE (NDI HX3)`.
Only `config.agility.example.yaml` matches. An operator following obs-setup.md while running the
disc-dog reference config will point the OBS source at a name the orchestrator never publishes,
producing the exact "OBS-sees-it-but-console-blank" / name-mismatch failure called out in project
memory (`phase8-live-multiview-on-rig`). The test does NOT catch this because it only cross-checks
*scene* names (`obs_scene`), never `ndi_source` names.
**Fix:** Either align `config.example.yaml`'s `cam_wide.ndi_source` to `PHONE-WIDE (NDI HX3)`, or
note in `docs/obs-setup.md` that the disc-dog reference config uses a different placeholder
(`LOCALHOST (iPhone Camera for OBS Studio App)`) for cam_wide. Best: add a test that asserts the
template's `ndi_source_name` values are a superset of each config's `cameras[].ndi_source`, so the
two cannot silently drift the way scene names are already guarded.

### WR-02: Test asserts overlay above NDI but never that Score Text sits BELOW Score Overlay

**File:** `tests/test_scene_template.py:111-139`
**Issue:** `test_overlay_is_top_layer` asserts `Score Overlay` is the last item and above every
`NDI - *` item, and `test_score_text_is_fallback_hidden` asserts `Score Text` ships
`visible: false`. But nothing asserts the relative z-order of the two overlays. The documented
coexistence policy (obs-setup.md §"Coexistence policy", RBT-06) is that the operator manually
reveals `Score Text` when the browser source dies. If a future template edit placed `Score Text`
*above* `Score Overlay`, the manual-fallback swap would render the text behind the (dead/blank)
browser plate in some failure modes, and the test would stay green. In the current JSON `Score Text`
is index 1 and `Score Overlay` index 2 in every scene, so the invariant holds today — it is simply
untested and therefore unprotected against regression.
**Fix:** In `test_overlay_is_top_layer`, also assert the `Score Text` index is less than the
`Score Overlay` index for every scene that contains both.

### WR-03: `test_template_scene_names_match_config` does not guard against extra/orphan scenes

**File:** `tests/test_scene_template.py:68-76`
**Issue:** The test asserts `config_scenes - scenes == set()` (every config scene exists in the
template) and that `SAFE` is present, but it never asserts the converse direction in a meaningful
way. The template ships `MULTIVIEW` and `PIP` scenes that are intentionally not in the configs
(manual/idle-only), so a strict equality would be wrong — but the current asymmetric check means a
typo'd scene source in the template (e.g. a scene named `CAM Widee` orphaned in `sources` but absent
from `scene_order`) is only partially caught: `_template_scene_names` asserts `from_order <= from_sources`
but never `from_sources <= from_order`, so a scene source with no `scene_order` entry passes silently
and would never appear in OBS's scene list.
**Fix:** Tighten `_template_scene_names` to also assert `from_sources <= from_order` (every scene
source is listed in `scene_order`), or explicitly whitelist the known manual-only scenes
(`MULTIVIEW`, `PIP`) and assert exact equality against `config_scenes ∪ {SAFE, MULTIVIEW, PIP}`.

## Info

### IN-01: `current_scene` / `current_program_scene` duplicate with no test coverage

**File:** `obs/segugio-scene-collection.json:3-4`
**Issue:** Both keys are set to `"SAFE"` (correct — boot to the fallback scene), but no test asserts
the collection boots into `SAFE`. If a future edit set these to an auto-only scene (`PIP`/`MULTIVIEW`),
the rig would import on-air into a manual scene with no regression signal.
**Fix:** Add an assertion that both `current_scene` and `current_program_scene` equal `SAFE`.

### IN-02: Template re-reads and re-parses the JSON file on every helper call

**File:** `tests/test_scene_template.py:42-57`
**Issue:** `_source_def`, `_scene_items`, and `_template_scene_names` each call
`json.loads(_TEMPLATE.read_text(...))` independently; the loops over scenes re-parse the whole file
once per scene. Not a correctness bug (out of v1 perf scope), but it is avoidable duplication and a
module-level cached parse would simplify the helpers.
**Fix:** Parse once at module load into a constant and have the helpers index into it.

### IN-03: Doc table omits PIP/MULTIVIEW NDI placeholder caveat

**File:** `docs/obs-setup.md:31-44`
**Issue:** The scene table and the "point each NDI Source" paragraph describe the four `CAM *` feeds,
but `MULTIVIEW` and `PIP` also embed the four NDI sources (JSON lines 87-90, 103-106). The setup
instructions do not remind the operator those composite scenes inherit the same NDI source objects,
so re-pointing a source in Properties updates all scenes at once — helpful, but undocumented.
**Fix:** Add a one-line note that the NDI sources are shared objects reused across `CAM *`,
`MULTIVIEW`, and `PIP`, so re-pointing once updates every scene.

### IN-04: Security doc references a Phase-9 kill-switch that may not yet exist

**File:** `docs/security.md:108`
**Issue:** The doc states "a live operator preview kill-switch is Phase 9 / UXT-03". This is a
forward reference; if Phase 9 is not yet implemented, readers may assume a console-side kill-switch
exists. The text is technically correct ("There is no separate console-side preview kill-switch in
Phase 8") but the forward reference invites confusion about current capability.
**Fix:** Clarify whether the Phase-9 kill-switch is shipped as of this writing, or mark it explicitly
as "deferred / not yet implemented" to avoid implying a control that does not exist.

---

_Reviewed: 2026-06-16T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
