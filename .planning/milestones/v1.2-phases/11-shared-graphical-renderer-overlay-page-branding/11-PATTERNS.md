# Phase 11: Shared Graphical Renderer, /overlay Page & Branding - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 5 (3 new, 2 modified) + 1 test extension
**Analogs found:** 5 / 5 — every file has a strong in-repo analog (no greenfield)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| NEW `src/segugio/ui/templates/overlay.html` | template (host page) | request-response + client poll | `src/segugio/ui/templates/console.html` | exact (same self-contained inlined-CSS pattern) |
| NEW `src/segugio/ui/static/overlay-render.js` | client renderer + timer | transform (data→DOM) | inline `<script>` in `console.html` (SCV-01 mirror + poll loop) | exact (same logic, centralized) |
| MODIFY `src/segugio/ui/app.py` | route | request-response | existing `GET /overlay-json` + `create_app(channel_dir, cam_ids=())` arg-injection | exact (sibling route, same factory) |
| MODIFY `src/segugio/config/models.py` | config model | n/a (validation) | existing `OverlayParams` + `PreviewParams` sub-models | exact (grow in place) |
| MODIFY `tests/test_imports.py` | test | n/a | `test_console_resolves_with_heavy_stack_and_numpy_absent` | exact (extend in place) |
| READ-ONLY ref `src/segugio/ui/score_render.py` | utility | transform | — (mirrored by the JS renderer, not modified) | reference |

## Pattern Assignments

### NEW `src/segugio/ui/templates/overlay.html` (template, request-response)

**Analog:** `src/segugio/ui/templates/console.html`

**Self-contained, FOUC-free shell** (console.html lines 1-39): single `<!DOCTYPE html>` with ALL critical CSS inlined in a `<head><style>` block — never an external stylesheet that loads a frame late (Pitfall 5). Mirror this single-file convention. For the overlay add the transparency contract at the very top of the inlined style:

```css
html, body { background: transparent !important; margin: 0; }
/* start the lower-third hidden — entrance animation reveals it, so a delayed
   first paint shows NOTHING, never a white box (Pitfall 5). */
.lower-third { opacity: 0; }
```

**Theme via CSS variables** (D-06; console palette is the default — console.html line 16-19 establishes `#14161a` plate / `#e8e8e8` text and line 14-15 the status palette `LIVE #34D399 / FORZATA #F0B429 / MORTO #FF6B6B`):

```css
:root { color-scheme: dark; }
.lower-third {
  --accent: #34D399;   /* console green — overridable per BRD-01 */
  --plate:  #14161a;
  --text:   #E6E9EF;
}
```
These three vars are injected as Jinja render args from config (see app.py section) so an org overrides them per event.

**Font reveal gate** (Claude's discretion — self-hosted `.woff2` vs system stack; console uses `system-ui, -apple-system, sans-serif` at line 18). If self-hosting, use `font-display: block` + a `document.fonts.ready.then(...)` reveal gate to kill FOUC; the choice MUST match what Phase 12's console-preview iframe renders.

The page body is thin: the lower-third DOM skeleton + a `<script src="/static/overlay-render.js">` + a poll bootstrap. No data is baked in (so the page never reloads on score change).

---

### NEW `src/segugio/ui/static/overlay-render.js` (client renderer + timer, transform)

**Analog:** the inline `<script>` blocks in `console.html` — three reusable pieces, centralized here.

**1. Per-discipline layout + sanitize + alias** — copy `cleanField`/`scvGet`/`mirrorOverlayText` (console.html lines 346-389). These mirror Python `score_render.py::_clean`/`_get`/`render_overlay_text` byte-exact, including the `_MAX_FIELD_LEN = 64` cap and the `sct`/`SCT` first-present alias. The renderer reproduces the SAME per-discipline field sets but builds DOM cells (not a text line):

```js
const SCV_MAX_FIELD_LEN = 64;   // mirrors _MAX_FIELD_LEN
const SCV_NONPRINT = /[^\S ]|[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}\p{Zs}]/gu;
function cleanField(value) {
  let text = (value === null || value === undefined) ? "" : String(value);
  text = text.replace(SCV_NONPRINT, m => (m === " " ? " " : ""));
  text = text.trim();
  if (text.length > SCV_MAX_FIELD_LEN) text = text.slice(0, SCV_MAX_FIELD_LEN);
  return text;
}
function scvGet(fields, ...keys) {            // first-present, sanitized (mirrors _get)
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(fields, key)
        && fields[key] !== null && fields[key] !== undefined && fields[key] !== "") {
      return cleanField(fields[key]);
    }
  }
  return "";
}
```

Per-discipline field selection (console.html lines 370-389): `disc_tf` → prese/zona/totale; `disc_freestyle` → nome/timer; `agility` → tempo / sct (alias SCT) / faults. The competitor identity line (D-08) uses `scvGet(fields, "nome")` for ALL disciplines (it flows through the verbatim `fields` dict, zero data-model change).

**SECURITY (Pitfall, security note):** write every operator value with `el.textContent = cleanField(v)`, NEVER `innerHTML`. The plain-text `_clean` alone is NOT sufficient for an HTML sink — `textContent` is the HTML-context escape.

**2. Offset-cancellation timer** (Pitfall 1 / ARCHITECTURE (c) — the ONE genuinely new behavior). Per poll, re-measure skew from `server_now` (published by `/overlay-json`, app.py line 269) and free-run locally between polls:

```js
// On each /overlay-json poll:
const skew = p.server_now - (Date.now() / 1000);    // re-measured every poll
// Displayed elapsed advances on local rAF/interval (never snaps):
const elapsed = (Date.now() / 1000 + skew) - p.started_at;
// freeze when p.running === false AND when isStale() (Pitfall 4).
```
Discipline format (D-03): countdown disciplines render `M:SS`; agility renders `SS.hh` hundredths and MUST update `textContent` in place via `requestAnimationFrame` (never rebuild the node). End-of-countdown → single pulse → freeze on "Tempo" (D-04).

**3. Freshness watchdog + degrade** — copy `isStale()`/`STALE_MS`/`PUBLISH_MS`/the gen-gated poll gate verbatim (console.html lines 619-624, 714-716, 738-740):

```js
const PUBLISH_MS = 200;            // ~5 fps publish cadence
const STALE_MS   = PUBLISH_MS * 3; // ~600ms — gen not advancing → stale
let lastGen = -1, lastGenAt = Date.now();   // WR-02 cold-start: lastGen<0 is NOT stale
// in poll: if (p.gen > lastGen) { lastGen = p.gen; lastGenAt = Date.now(); /* re-render */ }
function isStale() {
  return lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS;   // cold load NOT stale
}
```
On `isStale()` → STOP the timer (do not let it free-run forever) and apply a degraded visual. A frozen-but-ticking timer is the worst broadcast failure (Pitfall 4).

**Fetch discipline** (Pitfall 2): poll `GET /overlay-json?t=<gen>` (nonce is load-bearing in CEF, not `no-store` alone). Re-render only on `p.gen > lastGen`. Cold-start guard `lastGen < 0` is NOT stale.

---

### MODIFY `src/segugio/ui/app.py` (route, request-response)

**Analog:** the sibling `GET /overlay-json` route (lines 253-275) and the `create_app(channel_dir, cam_ids=())` arg-injection pattern (lines 84-98, 318-334).

**Add `GET /overlay`** beside the existing routes, inside `create_app`, using `render_template` (already imported in-factory at line 96):

```python
@app.get("/overlay")
def get_overlay():
    # Thin host page — NO data baked in (the page polls /overlay-json). Static branding
    # config (freestyle duration, logo path, theme vars, event name) is injected as render
    # args resolved by the entrypoint, EXACTLY like cam_ids — NEVER `import segugio.config`.
    resp = make_response(render_template("overlay.html", **overlay_cfg))
    resp.headers["Cache-Control"] = "no-store"   # the get_preview_jpg / overlay-json precedent
    return resp
```

**Config injection** — extend the factory signature mirroring the `cam_ids` precedent (line 84). Add an `overlay_cfg=None` arg (a plain dict of `freestyle_duration_s` + logo path + theme vars + event name). Resolve it in the `__main__` entrypoint (lines 318-334) lazily — prefer env vars, fall back to `load_config()` imported INSIDE the entrypoint (line 328 precedent: `from ..config.loader import load_config`). NEVER add a config import at module top (Pitfall 3 / crash-isolation).

**CRITICAL — preserve the import allowlist** (app.py docstring lines 8-12): `import segugio.ui` stays Flask-free (Flask imported inside `create_app`); no new module-top heavy import. All timer/animation/branding logic is client-side JS/CSS — the route only does `render_template`.

`/overlay-json` is NOT modified — it already publishes `{discipline, fields (verbatim), running, started_at, server_now, gen}` + `Cache-Control: no-store` (lines 261-275). The renderer is a pure consumer. Branding config does NOT enter the poll payload (D-07 — it is static, injected at render time).

---

### MODIFY `src/segugio/config/models.py` (config model)

**Analog:** the existing `class OverlayParams` (lines 174-191) — grow it in place; and `class PreviewParams` (lines 159-171) for the multi-field `extra="forbid"` + `Annotated[..., Field(...)]` + default convention.

Current state (line 190-191):
```python
class OverlayParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    freestyle_duration_s: Annotated[int, Field(gt=0)] = 120  # D-06: 2-min routines; orgs override to 90
```

**Add additively** (all with defaults so a config WITHOUT these still validates under the fail-fast `SystemExit(2)` loader — loader.py lines 42-44 raise on any `ValidationError`):
- `event_name: str = ""` (D-08 — the persistent identity line; empty → line hides gracefully)
- logo path (D-07 — optional; empty/absent → no logo bug rendered)
- theme color vars (D-06 — `--accent`/`--plate`/`--text` defaults = console palette `#34D399`/`#14161a`/`#E6E9EF`), either flat str fields or a small nested theme block (Claude's discretion).

Keep `model_config = ConfigDict(extra="forbid")`. `Config.overlay` is already wired via `Field(default_factory=OverlayParams)` (line 248) — no wiring change needed. These are STATIC config: they do NOT enter `/overlay-json`; they are injected into `/overlay` at render time.

---

### MODIFY `tests/test_imports.py` (test — crash-isolation gate, RBT-07)

**Analog:** `test_console_resolves_with_heavy_stack_and_numpy_absent` (lines 87-116) — the EXACT pattern to extend.

It forces `CONSOLE_HEAVY_MODULES` absent, builds `create_app(tmp, cam_ids=[...])`, and asserts `GET /overlay-json` returns 200 under the heavy-absent block (lines 109-116). **Extend it** to also `client.get("/overlay")` under the same block and assert 200 — proving the new route/template/static add no module-top heavy import. Must stay green (Pitfall 3 success criterion).

```python
# extend the existing test under the same heavy-absent block:
resp = client.get("/overlay")
assert resp.status_code == 200
```

## Shared Patterns

### Crash-isolation import allowlist (RBT-07 — applies to overlay.html route + config injection)
**Source:** `src/segugio/ui/app.py` lines 8-12 (docstring), 96 (Flask in-factory), 318-334 (entrypoint arg resolution).
**Apply to:** the new `GET /overlay` route and ALL config injection.
Flask imported inside `create_app`; config-derived branding passed as a plain dict arg (like `cam_ids`), resolved lazily in `__main__` — `import segugio.config` only INSIDE the entrypoint, never at module top.

### `?t=<gen>` nonce + `Cache-Control: no-store` fetch discipline (Pitfall 2)
**Source:** `app.py` line 274 (`resp.headers["Cache-Control"] = "no-store"` on /overlay-json) + line 290-291 (preview JPEG precedent); console.html poll loop.
**Apply to:** the `/overlay` route response AND the overlay-render.js `/overlay-json` fetch URL (nonce is load-bearing in CEF, not no-store alone).

### gen-gated render + cold-start guard (Pitfall 4 / WR-02)
**Source:** `console.html` lines 619 (`lastGen = -1`), 714-716 (gen-strictly-advances gate), 738-740 (`isStale()`).
**Apply to:** overlay-render.js poll loop and freshness watchdog. `lastGen < 0` is NEVER stale — never paint stale on first frame.

### Verbatim display-only + HTML-context escape (SCR-04 + security)
**Source:** `score_render.py` lines 32-54 (`_clean`/`_get` — verbatim, sanitized, no arithmetic) mirrored by `console.html::cleanField`/`scvGet` (lines 352-368).
**Apply to:** overlay-render.js — reproduce `_clean`/`_get` semantics; write values via `textContent` (HTML sink demands the escape `_clean` alone does not provide). The renderer NEVER sums/judges/derives.

## No Analog Found

None. Every Phase-11 file extends or mirrors existing in-repo code. The only genuinely NEW behavior (the offset-cancellation timer formula) has no code analog but is fully specified in ARCHITECTURE.md (c) and the formula above.

## Metadata

**Analog search scope:** `src/segugio/ui/` (app.py, score_render.py, templates/console.html), `src/segugio/config/` (models.py, loader.py), `tests/test_imports.py`
**Files scanned:** 7 read directly; console.html targeted (878 lines) via Grep + 3 non-overlapping reads
**Pattern extraction date:** 2026-06-14
