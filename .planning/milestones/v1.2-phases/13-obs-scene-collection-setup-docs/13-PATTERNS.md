# Phase 13: OBS Scene Collection & Setup Docs - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 4 (all EXTEND-existing; no new files)
**Analogs found:** 4 / 4 (every analog lives IN THE SAME FILE being modified)

This is a packaging/config + docs phase. Every file modified already contains the exact
pattern the new content must mirror — the planner copies the existing in-file shape rather
than inventing one. Excerpts below are verbatim from the current files with line numbers.

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `obs/segugio-scene-collection.json` | config (OBS scene-collection data) | transform (z-order composite) | The `Score Text` (`text_gdiplus_v2`) shared-source-def + per-scene `items` reference in the SAME file | exact (same-file) |
| `tests/test_scene_template.py` | test (pure json/yaml parse) | request-response (assert) | The `_template_scene_names()` / `_config_obs_scenes()` helpers + `test_template_scene_names_match_config` in the SAME file | exact (same-file) |
| `docs/obs-setup.md` | docs (operator setup) | n/a | The `## Score overlay — read-from-file (primary path, OBS-05)` section + the scene table in the SAME file | exact (same-file) |
| `docs/security.md` | docs (threat re-eval) | n/a | The v1.1 `T-05-05-04` / `T-08-03` threat-eval paragraphs in the SAME file | exact (same-file) |

---

## Pattern Assignments

### `obs/segugio-scene-collection.json` (config, transform)

**Analog:** the `Score Text` source def + the `NDI - PHONE-*` source defs, and every scene's
`items` array, all in this same file.

**Shared source-def shape** — copy this exact object shape for the new `Score Overlay`
(`segugio-scene-collection.json:105-138`):
```json
    {
      "name": "Score Text",
      "id": "text_gdiplus_v2",
      "versioned_id": "text_gdiplus_v2",
      "settings": {
        "read_from_file": true,
        "file": "overlay.txt",
        "text": ""
      }
    },
    {
      "name": "NDI - PHONE-WIDE (NDI HX3)",
      "id": "ndi_source",
      "versioned_id": "ndi_source",
      "settings": { "ndi_source_name": "PHONE-WIDE (NDI HX3)" }
    },
```
Mirror the `name` / `id` / `versioned_id` / `settings` quadrant. The new def uses
`"id": "browser_source"`, `"versioned_id": "browser_source"`, and the verified obs-browser
settings keys (RESEARCH Pattern 1: `url`, `width:1920`, `height:1080`, `fps_custom:true`,
`fps:30`, `shutdown:false`, `restart_when_active:false`, `reroute_audio:false`, `css:""`).
Append it to the top-level `sources` array alongside the other shared defs (after the existing
`NDI - PHONE-HANDLER` def, before the closing `]` at line 139). Do NOT duplicate per scene.

**Per-scene item-reference shape + z-order** — every scene's `items` is a `{ name, visible }`
list, bottom-to-top (index 0 = BOTTOM, last = TOP — RESEARCH Pitfall 1). The existing
`Score Text` sits LAST and renders over the NDI video, which is the empirical proof of the
z-order rule. Two existing reference cases to mirror:

Single-NDI CAM scene (`segugio-scene-collection.json:27-38`, `CAM Wide`):
```json
    {
      "name": "CAM Wide",
      "id": "scene",
      "versioned_id": "scene",
      "settings": {
        "custom_size": false,
        "items": [
          { "name": "NDI - PHONE-WIDE (NDI HX3)", "visible": true },
          { "name": "Score Text", "visible": true }
        ]
      }
    },
```
Multi-NDI grid scene (`segugio-scene-collection.json:75-89`, `MULTIVIEW`):
```json
        "items": [
          { "name": "NDI - PHONE-WIDE (NDI HX3)", "visible": true },
          { "name": "NDI - PHONE-LONG (NDI HX3)", "visible": true },
          { "name": "NDI - PHONE-LOW (NDI HX3)", "visible": true },
          { "name": "NDI - PHONE-HANDLER (NDI HX3)", "visible": true },
          { "name": "Score Text", "visible": true }
        ]
```

**Per-scene edit to apply to all 7 scenes** (`SAFE`, `CAM Wide`, `CAM Long`, `CAM Low`,
`CAM Handler`, `MULTIVIEW`, `PIP` — lines 15-104):
1. Flip the existing `Score Text` item from `"visible": true` to `"visible": false` (D-03).
2. Append `{ "name": "Score Overlay", "visible": true }` as the LAST element of `items`
   (after `Score Text`), so it is top of z-order (RESEARCH Pitfall 1, Code Examples line 232-238).

Result per CAM scene (target shape):
```json
        "items": [
          { "name": "NDI - PHONE-WIDE (NDI HX3)", "visible": true },
          { "name": "Score Text", "visible": false },
          { "name": "Score Overlay", "visible": true }
        ]
```
Note `PIP` (lines 90-104) has some NDI items `visible:false` already — preserve those; only
touch the `Score Text` flag and append `Score Overlay`.

---

### `tests/test_scene_template.py` (test, request-response)

**Analog:** the existing helpers + parametrized lockstep test in this same file.

**Helper shape to reuse / mirror** (`test_scene_template.py:18-39`):
```python
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _REPO_ROOT / "obs" / "segugio-scene-collection.json"


def _template_scene_names() -> set[str]:
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    from_sources = {
        src["name"] for src in data.get("sources", []) if src.get("id") == "scene"
    }
    from_order = {entry["name"] for entry in data.get("scene_order", [])}
    assert from_order <= from_sources, "scene_order references a scene with no source entry"
    return from_sources
```
New helpers per RESEARCH §"How test_scene_template.py is extended" follow this exact idiom —
parse the SAME `_TEMPLATE` json, filter `sources`:
- `_source_def(name) -> dict | None` — return the top-level `sources` entry whose
  `name == name` (mirrors the `for src in data.get("sources", [])` comprehension above).
- `_scene_items(scene_name) -> list[dict]` — return that scene source's `settings.items`.

**Test shape to mirror** (`test_scene_template.py:42-58`) — note the existing parametrize
style and the per-scene driving via the scene-name set:
```python
def test_template_exists():
    assert _TEMPLATE.is_file(), f"missing OBS scene-collection template at {_TEMPLATE}"


@pytest.mark.parametrize(
    "config_name",
    ["config.example.yaml", "config.agility.example.yaml"],
)
def test_template_scene_names_match_config(config_name):
    scenes = _template_scene_names()
    ...
    assert "SAFE" in scenes, "template is missing the first-class SAFE scene"
```
New tests (RESEARCH lines 327-330) reuse `_template_scene_names()` to drive the per-scene loop
so assertions stay in lockstep with the scene set:
- `test_score_overlay_source_def` — `_source_def("Score Overlay")`: `id == "browser_source"`,
  `settings.url == "http://localhost:8080/overlay"`, `settings.shutdown is False`,
  `settings.restart_when_active is False`, transparency (`settings.get("css","")` empty/absent
  or the obs-browser transparent default — no opaque `background`).
- `test_every_scene_has_overlay_and_text` — for each scene in `_template_scene_names()`, its
  `items` names contain BOTH `"Score Overlay"` and `"Score Text"`.
- `test_overlay_is_top_layer` — for each scene, `"Score Overlay"` is the LAST `items` element
  and appears AFTER any `NDI - *` item.
- `test_score_text_is_fallback_hidden` (encodes D-03) — `"Score Text"` item ships
  `visible: false` in every scene.

The existing `test_template_exists` and `test_template_scene_names_match_config` (incl. the
SAFE-first-class assertion) stay UNCHANGED.

---

### `docs/obs-setup.md` (docs)

**Analog:** the `## Score overlay — read-from-file (primary path, OBS-05)` section and the
scene table in this same file.

**Section-header + bullet idiom to mirror** (`obs-setup.md:46-60`):
```markdown
## Score overlay — read-from-file (primary path, OBS-05)

The score overlay uses an OBS **Text** source named **`Score Text`**, present inside every
`CAM *` / `SAFE` scene, configured with **Read from file** pointing at the orchestrator's
atomic overlay file (`overlay.txt`).

- The score manager (05-05) writes the rendered Italian overlay line atomically ...
- Set the **Read from file** path on the `Score Text` source ...
```
Add a NEW section using this same `## ... — ... (path note)` header + bullet-list style, e.g.
`## Score overlay — browser-source (primary path)`, covering (RESEARCH SCN-02 + Code Examples
lines 241-264): the `http://localhost:8080/overlay` localhost default, the cross-machine
`http://<console-LAN-IP>:8080/overlay` edit, the transparency/source settings
(1920×1080@30, page-owned transparency, no injected CSS), the CEF cache-clear procedure, the
re-import-on-existing-box note (RESEARCH Pitfall 4), and the Browser-primary / Text-fallback
manual-toggle coexistence policy (D-04). Note the existing section now becomes the *fallback*
path — update its "(primary path, OBS-05)" framing accordingly.

**Scene-table idiom** (`obs-setup.md:31-39`) — the existing `| Scene | Role |` table is the
reference if the planner extends per-scene notes; no structural change required beyond noting
the overlay is wired into all 7.

---

### `docs/security.md` (docs)

**Analog:** the v1.1 threat-eval paragraphs (`T-05-05-04`, `T-08-03`) and the
`## What changed` / trust-boundary-reaffirmed prose style in this same file.

**Paragraph idiom to mirror** (`security.md:50-58`, the "What changed" + STRIDE/threat-id
citation style):
```markdown
## What changed in v1.1

The console used to serve a **control panel** ("operate blind"). In v1.1 the console also serves
**live competitor video**: ... served from the `0.0.0.0:8080` endpoint ...

The **blast radius grew from a control panel to live video** (STRIDE: **Information
Disclosure**, threat **T-08-03**). Anyone on or near the dedicated WiFi LAN who can reach
`0.0.0.0:8080` can now also see the live competitor feeds ...
```
Trust-boundary-reaffirmed idiom (`security.md:112-122`, the "Explicitly NOT added" closing):
```markdown
To be unambiguous (D-09): in v1.1 Segugio adds
- **NO new authentication** on the console or the preview routes;
- **NO configurable bind** (the console binds `0.0.0.0:8080` as in v1.0);
- **NO shared-token gate** ...
... The LAN-as-trust-boundary + AP-client-isolation posture stands.
```
Append ONE paragraph (after the v1.1 content) reusing this exact STRIDE + threat-id +
"reaffirmed, not changed" framing. Content per RESEARCH lines 361-362: the new OBS
browser-source is a **same-origin LAN consumer** of the existing `GET /overlay` route (shipped
Phase 11) — no new server route, no new code path; display-only (SCR-04), values sanitized at
the HTML sink via `textContent`; reuses the established trust boundary
(**T-05-05-04** / **T-08-03**) unchanged — no new auth, no configurable bind, no new exposure
beyond `0.0.0.0:8080`; v1.1 posture reaffirmed.

---

## Shared Patterns

### Shared source-def + per-scene reference (NOT per-scene duplication)
**Source:** `obs/segugio-scene-collection.json:105-138` (`Score Text` + `NDI - PHONE-*` defs).
**Apply to:** the new `Score Overlay` browser_source — define ONCE in `sources`, reference by
`{ name, visible }` in each scene's `items`. The lockstep test asserts exactly one
`Score Overlay` def.

### Z-order = `items` array order, bottom-to-top
**Source:** every scene's `items` in the JSON; `Score Text` listed last renders over NDI.
**Apply to:** append `Score Overlay` LAST in all 7 scenes; assert it in
`test_overlay_is_top_layer`.

### Verified obs-browser JSON keys (UI labels ≠ keys)
**Source:** RESEARCH Pattern 1 / Pitfall 2 (obs-browser source-verified).
**Apply to:** the JSON source def AND the test assertions — use `shutdown` and
`restart_when_active`, NEVER the UI-label strings `shutdown_source_when_not_visible` /
`refresh_when_scene_is_active`.

### Lockstep-driven-by-scene-set test idiom
**Source:** `tests/test_scene_template.py:22-34` (`_template_scene_names()`).
**Apply to:** all new per-scene assertions loop over `_template_scene_names()` so they cannot
silently skip a scene.

---

## No Analog Found

None. Every modified file contains its own closest analog (this is an extend-in-place phase).
The only genuinely new shape — the obs-browser `browser_source` settings block — has no
in-repo precedent and comes from RESEARCH Pattern 1 (obs-browser-source-verified keys), which
the planner should treat as the authoritative excerpt:
```json
{
  "name": "Score Overlay",
  "id": "browser_source",
  "versioned_id": "browser_source",
  "settings": {
    "url": "http://localhost:8080/overlay",
    "width": 1920,
    "height": 1080,
    "fps_custom": true,
    "fps": 30,
    "shutdown": false,
    "restart_when_active": false,
    "reroute_audio": false,
    "css": ""
  }
}
```

## Metadata

**Analog search scope:** `obs/`, `tests/`, `docs/` (the 4 files this phase touches).
**Files scanned:** 4 modified + 2 upstream (CONTEXT, RESEARCH).
**Pattern extraction date:** 2026-06-16

## PATTERN MAPPING COMPLETE

**Phase:** 13 - obs-scene-collection-setup-docs
**Files classified:** 4 (all EXTEND-existing; 0 new)
**Analogs found:** 4 / 4 (each analog is in-file)

### Coverage
- Files with exact (same-file) analog: 4
- Files with role-match analog: 0
- Files with no analog: 0 (one net-new JSON sub-shape sourced from RESEARCH Pattern 1)

### Key Patterns Identified
- Shared source def in top-level `sources` + `{ name, visible }` per-scene `items` reference —
  mirror `Score Text` / `NDI - PHONE-*`; never duplicate per scene.
- Z-order is `items` array order, bottom-to-top: append `Score Overlay` LAST in all 7 scenes
  (the existing last-listed `Score Text` renders over NDI — empirical proof).
- obs-browser JSON keys are `shutdown` / `restart_when_active` (NOT the UI-label strings) —
  the #1 silent-no-op risk; assert the real keys.
- Test helpers parse the same `_TEMPLATE` json and loop over `_template_scene_names()` to keep
  every assertion in lockstep with the scene set.
- Docs sections reuse the existing `## ... (path note)` header + bullet idiom (obs-setup) and
  the STRIDE + threat-id + "reaffirmed, not changed" prose (security).

### File Created
`.planning/phases/13-obs-scene-collection-setup-docs/13-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can reference each in-file analog excerpt directly in PLAN.md.
