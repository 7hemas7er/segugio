---
phase: 08-console-serving-live-multiview-safety-hardening
reviewed: 2026-06-13T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - docs/security.md
  - src/segugio/config/models.py
  - src/segugio/ui/app.py
  - src/segugio/ui/templates/console.html
  - tests/conftest.py
  - tests/test_imports.py
  - tests/test_preview_bitrate_cap.py
  - tests/test_preview_concurrency.py
  - tests/test_preview_serving.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-13
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 8 wires the live-multiview preview serving routes into the crash-isolated Flask
console and adds a config-time preview-bandwidth cap. The security posture (LAN trust
boundary, no auth, whitelisted preview route, threaded serving) is coherent and the
path-traversal mitigation in `get_preview_jpg` is sound: the `<cam>` segment is exact-matched
against a frozenset BEFORE any filesystem path is built, so a traversal segment can never
become a path. The crash-isolation contract (Flask imported inside `create_app`, opcomm-only
top-level imports) holds and is well-tested.

No BLOCKER-level defects were found — there is no injection, no auth bypass, no data-loss
path, and the never-raise reader boundary is intact. However, several WARNING-level defects
degrade robustness and correctness of the live multiview: a hardcoded camera-id list in the
client that diverges from the server whitelist, a freshness-staleness false-positive on first
load, a `markTiles` logic gap, and a bandwidth-cap estimator whose own documentation contradicts
its math. These should be fixed before this code ships to a live competition.

## Warnings

### WR-01: Client multiview camera ids are hardcoded and diverge from the server whitelist

**File:** `src/segugio/ui/templates/console.html:51-54,108-111,156-158`
**Issue:** The server-side preview whitelist is configurable (`create_app(channel_dir, cam_ids=...)`,
resolved at the entrypoint from `SEGUGIO_CAM_IDS` / `SEGUGIO_CONFIG` / a 4-id default — `app.py:193-203`).
But the console template HARDCODES the four ids in three places: the `<div class="tile" id="tile-cam_wide">`
markup (lines 51-54), the `data-cam` force buttons (lines 108-111), and the JS `CAMS`/`CAM_LABEL`
constants (lines 156-158). Any deployment with a different camera set (e.g. 3 cameras, or ids
like `cam_a`/`cam_b`) renders empty/404 tiles for the configured cameras and dead tiles for
cameras that do not exist, and the force-override buttons send ids the orchestrator does not
recognize. The configurable `cam_ids` arg is therefore only half-wired: the route honors it,
the page ignores it. For a "la camera giusta al momento giusto" core-value tool this silently
breaks the entire multiview and override surface on any non-default rig.
**Fix:** Pass the configured ids/labels into the template and render the tiles, force buttons,
and the `CAMS`/`CAM_LABEL` JS constants from that data instead of hardcoding:
```python
@app.get("/")
def index():
    return render_template("console.html", cam_ids=sorted(cam_ids))
```
```html
{% for cam in cam_ids %}
  <div class="tile" id="tile-{{ cam }}"><img id="img-{{ cam }}" alt="{{ cam }}"><span class="badge" id="badge-{{ cam }}">{{ cam }}</span></div>
{% endfor %}
<script>const CAMS = {{ cam_ids | tojson }};</script>
```

### WR-02: First-load staleness false-positive marks every tile MORTO for ~600 ms

**File:** `src/segugio/ui/templates/console.html:159,187-188`
**Issue:** `lastGenAt` is initialized to `0` (epoch). `markTiles` computes
`stale = (Date.now() - lastGenAt) > STALE_MS` where `STALE_MS = 600`. On page load,
`pollStatus()` runs immediately (line 222) and calls `markTiles(s)` BEFORE the first
`pollPreview()` has had a chance to set `lastGenAt` to a real timestamp. Since
`Date.now() - 0` is enormous, `stale` is `true`, so EVERY tile is marked MORTO (dead) on
first paint — even when all feeds are alive and publishing. The operator's first impression
of a healthy rig is "all cameras dead." It self-corrects once `pollPreview` lands a gen, but
that is a misleading safety-relevant signal on a tool whose whole job is showing which camera
is live.
**Fix:** Initialize `lastGenAt` to the load time, or treat "no gen seen yet" as not-stale:
```javascript
let lastGen = -1, lastGenAt = Date.now();   // not epoch
```
or in `markTiles`: `const stale = lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS;`

### WR-03: markTiles treats a missing per-cam alive entry as ALIVE, masking unknown feeds

**File:** `src/segugio/ui/templates/console.html:191`
**Issue:** `const dead = (status.alive && status.alive[cam] === false) || stale;`
A camera marked MORTO requires `status.alive[cam] === false` EXACTLY. If `status.alive`
lacks an entry for a camera (the orchestrator only published a subset, or the cam id in the
hardcoded `CAMS` list does not match a key in `alive`), `status.alive[cam]` is `undefined`,
`undefined === false` is `false`, and the tile is NOT marked dead. A camera with unknown
liveness is rendered as healthy. Combined with WR-01 (hardcoded `CAMS` that can mismatch the
real ids), this means a camera the orchestrator never reports on shows a stale/last-good frame
with no MORTO indication. The staleness fallback only catches a whole-channel freeze, not a
single missing-cam case.
**Fix:** Treat a missing/non-true alive entry as dead (fail-safe for a liveness signal):
```javascript
const aliveKnown = status.alive && Object.prototype.hasOwnProperty.call(status.alive, cam);
const dead = (aliveKnown ? status.alive[cam] !== true : true) || stale;
```
Decide deliberately whether "unknown" should be dead or merely not-live; do not let
`undefined === false` make that decision implicitly.

### WR-04: Bandwidth-cap estimator scales JPEG bytes linearly with quality, contradicting JPEG behavior

**File:** `src/segugio/config/models.py:191-202` (and the comment block 180-188)
**Issue:** `_estimate_jpeg_bytes` computes `bpp = 0.30 × (jpeg_quality / 55.0)` and the comment
documents `0.30` as calibrated "at q55." At the default `jpeg_quality=55` this matches the
documented `~24.9 KB/frame`, so the default-config test passes. But the linear `jpeg_quality/55`
scaling does not reflect JPEG behavior: encoded size is strongly sublinear in the quality factor
above ~q55 (q100 is often well under 2× the q55 bytes, not the `100/55 ≈ 1.82×` this model
asserts). The estimator therefore materially OVER-estimates high-quality configs. The safety
direction is fine — it can only over-reject, never under-budget, so it never admits an
over-budget preview onto the contended WiFi — but it can reject a config that would actually
sit under the real ≤8 Mbps band, and this is a HARD config-load rejection gate (raises
`ValueError` → `SystemExit(2)`). An operator hitting a spurious rejection has no signal that the
estimate is a deliberate over-estimate.
**Fix:** Either cap the quality scaling at 1.0 (conservative, avoids spurious high-q rejections)
or document the linear term as an intentional over-estimate margin so the remediation message
("raise max_total_mbps") is understood as expected:
```python
# LINEAR quality term is a deliberate OVER-estimate above q55 (real JPEG is sublinear): it can
# over-reject but never under-budget. Raise max_total_mbps if a real per-config measurement is lower.
bpp = _JPEG_BYTES_PER_PIXEL * (jpeg_quality / 55.0)
```

### WR-05: Score POST sweeps hidden/empty form fields into the OBS overlay, unbounded

**File:** `src/segugio/ui/app.py:106-110`; `src/segugio/ui/templates/console.html:140-143`
**Issue:** `fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS}` sweeps EVERY
posted form key (minus `discipline`) into `ScoreDoc.fields`, which is rendered to the OBS
overlay via `render_overlay_text` (line 110). The client posts the full form via
`new FormData(e.target)` (console.html:142) even though the JS comment at line 139 claims it
posts "only the visible discipline's fields." Hidden fieldsets are only `display:none` (the
`.hidden` class), and `FormData` includes display:none inputs — so a `disc_tf` POST also carries
empty `nome`/`timer`/`tempo`/`sct`/`faults` keys from the other disciplines. Those empty values
land in `fields` and reach the renderer, potentially emitting stray empty labels on the live
broadcast overlay and bloating every `score.json` write. There is also no server-side bound on
field count or value length, so a crafted POST can inject arbitrary keys/values that flow to the
OBS read-from-file overlay (the overlay is sanitized per T-05-05-02, but the unbounded key set
is still a quality/robustness gap).
**Fix:** Drop empty values and bound/whitelist keys server-side, and fix the client to serialize
only the visible fieldset:
```python
fields = {k: v for k, v in form.items() if k not in _NON_SCORE_KEYS and v.strip()}
```
Optionally key the allowed field names off the resolved `discipline` so a crafted POST cannot
add arbitrary overlay labels.

## Info

### IN-01: Duplicated `"preview"` subdir literal across two module constants

**File:** `src/segugio/ui/app.py:61-62`
**Issue:** `_PREVIEW_SUBDIR = "preview"` and `_PREVIEW_FILE = "preview/preview.json"` both
hardcode the `"preview"` subdir string. Both are used (`_PREVIEW_FILE` at line 173,
`_PREVIEW_SUBDIR` at line 160) — neither is dead — but the subdir literal is duplicated, so a
future rename of the publisher's subdir requires editing two constants in lockstep.
`_PREVIEW_FILE` also embeds a forward slash; it works on Windows because it is passed through
`os.path.join(channel_dir, name)`, but deriving it keeps the path style consistent with the
JPEG route's `os.path.join`.
**Fix:** Derive from one source: `_PREVIEW_FILE = os.path.join(_PREVIEW_SUBDIR, "preview.json")`.

### IN-02: Bare `except Exception` in recording_obs fixture swallows real failures

**File:** `tests/conftest.py:396-401`
**Issue:** The `recording_obs` fixture wraps the optional real-fake import in
`try: ... except Exception:`. A broad `except Exception` masks a genuine bug in
`RecordingObsController` (e.g. a `TypeError` at construction) by silently falling back to the
inline stand-in, so a test that should exercise the real fake quietly runs against the stub and
the regression is invisible.
**Fix:** Narrow to `except ImportError:` so only a genuinely-absent module triggers the
fallback; a broken-but-present real fake then surfaces loudly.

### IN-03: Override-latency budget and timeouts are magic numbers in the concurrency test

**File:** `tests/test_preview_concurrency.py:46,57,64,76`
**Issue:** The `timeout=10` on `urlopen`, the `result(timeout=10)` futures, and the
`elapsed < 1.0` assertion are bare magic numbers. The 1.0 s override-latency budget is the
load-bearing assertion (threat T-08-01) and deserves a named constant tied to the documented
control, so a future budget change is a one-line edit and the intent is explicit.
**Fix:** Hoist to module constants, e.g. `_OVERRIDE_BUDGET_S = 1.0`, `_REQ_TIMEOUT_S = 10`.

### IN-04: Preview poll cadence is hardcoded client-side, decoupled from `preview.fps`

**File:** `src/segugio/ui/templates/console.html:160-161`
**Issue:** `PUBLISH_MS = 200` (~5 fps) is hardcoded to match `PreviewParams.fps = 5.0`. If a
deployment tunes `preview.fps`, the client polls at the wrong cadence — over-polling wastes the
contended-WiFi bytes the bandwidth cap is trying to protect, or under-polling drops frames and
falsely trips the staleness logic (see WR-02). The two cadences are coupled but maintained
independently.
**Fix:** Pass the configured `preview.fps` (and the derived `PUBLISH_MS`) into the template from
the entrypoint, the same mechanism WR-01 suggests for `cam_ids`, so client cadence tracks config.

---

_Reviewed: 2026-06-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
