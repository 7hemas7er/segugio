# Phase 9: Explainability, Informed Override & Tablet UX - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 4 (1 dominant client file, 1 route file, 1 reused pure fn, +1 test file)
**Analogs found:** 4 / 4 (all in-codebase — this is a pure extend-existing phase, no greenfield files)

> **Headline:** This phase creates NO new module. Every requirement lands as new JS/CSS inside the EXISTING `console.html` plus at most ONE small Flask route in the EXISTING `app.py`. The closest analog for almost everything IS the current console — the patterns to copy are already in the file being edited. The crash-isolation import allowlist (Flask + `segugio.opcomm` + `segugio.ui.score_render`) is a HARD gate guarded by an existing test.

---

## File Classification

| File | New/Modified | Role | Data Flow | Closest Analog | Match Quality |
|------|--------------|------|-----------|----------------|---------------|
| `src/segugio/ui/templates/console.html` | **modified** (bulk of phase) | view / client store + render | request-response polling + DOM render | itself (current `pollPreview`/`pollStatus`/`markTiles`/`refreshTile`) | exact (self-extension) |
| `src/segugio/ui/app.py` | **modified** (small) | controller / route | request-response | existing `/preview`, `/score` routes in same file | exact (sibling route) |
| `src/segugio/ui/score_render.py` | **read-only** (mirror in JS) | utility / pure fn | transform | `render_overlay_text` 3 f-strings | exact (the source of truth to replicate) |
| `tests/test_ui_score.py` / `tests/test_imports.py` | **modified/added** | test | request-response + import-guard | `test_ui_score.py` Flask-test-client pattern; `test_imports.py` heavy-absent guard | exact |

**No new files required.** The SCV-01 drift-guard endpoint (if chosen) is a new *route* inside the existing `app.py`, not a new file.

---

## Pattern Assignments

### `console.html` — Polling / freshness / sleep-wake resume (UXT-03)

**Analog:** the existing `pollPreview` + `markTiles` + `lastGen`/`lastGenAt`/`STALE_MS` mechanism (lines 166–241). UXT-03 EXTENDS this exact code — do not rewrite it.

**Existing freshness gate to extend** (lines 171–173, 199–217):
```javascript
let lastGen = -1, lastGenAt = Date.now();   // WR-02: seed to load time, NOT epoch 0
const PUBLISH_MS = 200;
const STALE_MS = PUBLISH_MS * 3;            // gen not advancing within ~2-3x → stale
// ...
const stale = lastGen >= 0 && (Date.now() - lastGenAt) > STALE_MS;  // "no gen yet" is NOT stale
const aliveKnown = status.alive && Object.prototype.hasOwnProperty.call(status.alive, cam);
const dead = (aliveKnown ? status.alive[cam] !== true : true) || stale;  // FAIL-SAFE (WR-03)
```
**Phase-9 deltas to layer on (do NOT replace the above):**
- Add per-tile (not whole-channel) STALE class + "STALE"/"RICONNESSIONE…" overlay text — never "LIVE" on a stale tile (UI-SPEC §Lifecycle). The existing `stale` is whole-channel; keep it, add the explicit STALE tile state.
- Add `resumeAt` recorded on wake; a tile renders LIVE only once a frame with `gen` post-dating `resumeAt` arrives.
- Add lifecycle listeners: `document.addEventListener('visibilitychange', …)` + `window.addEventListener('pageshow'/'pagehide', …)`. FORBID `focus`/`blur`/`freeze`/`resume`.
- On hide: `clearInterval` the two `setInterval` handles (currently anonymous at lines 195, 241 — **refactor to named handles** so they can be torn down/restarted).
- On resume: defer first fetch in `setTimeout(fn, ~150–250ms)` (iOS "Load failed" bug).
- The foreground watchdog already exists (`stale` check inside `markTiles`) — it is PRIMARY; the lifecycle hooks are belt-and-suspenders.

**Existing silent-coast error pattern to preserve verbatim** (lines 193, 238):
```javascript
} catch (e) { /* coast — a poll error never breaks the page */ }
```

---

### `console.html` — Flicker-free `<img>` refresh (UXT-03)

**Analog:** existing `refreshTile` (lines 178–182).

**Existing pattern (MUST be changed per UI-SPEC §Flicker-free):**
```javascript
function refreshTile(cam, gen) {
  const img = new Image();                       // ← CHANGE: creates a NEW Image() per frame (leak risk)
  img.onload = () => { document.getElementById("img-" + cam).src = img.src; };
  img.src = "/preview/" + cam + ".jpg?t=" + gen;
}
```
**Phase-9 required change:** ONE persistent off-DOM `Image()` preloader **per tile, created once**; per tick set `.src` then `await preloader.decode()` (not `onload`) before swapping the visible `<img>.src`. On `decode()` reject, skip the frame without throwing. Keep the `?t=<gen>` nonce (it is the load-bearing refresh, not `no-store`). Keep `gen`-gating (swap only when `gen` strictly advances — already at line 188). Hidden/off tiles → 1×1 transparent data-URI `src`, not `display:none`.

---

### `console.html` — Tile states + dog-lock bbox overlay (D-04, WHY-03, WHY-04)

**Analog:** existing tile markup (line 52) + `markTiles` class toggling (lines 199–220) + the `.tile`/`.badge`/`.live`/`.dead` CSS (lines 33–40).

**Existing tile markup + 2-state marking to extend:**
```html
<div class="tile" id="tile-{{ cam }}"><img id="img-{{ cam }}" alt="{{ cam }}"><span class="badge" id="badge-{{ cam }}">{{ cam }}</span></div>
```
```javascript
tile.classList.toggle("live", live);   // MVW-02 red border
tile.classList.toggle("dead", dead);   // MVW-03
badge.textContent = dead ? "MORTO" : (live ? "LIVE" : CAM_LABEL[cam]);
```
**Phase-9 deltas:**
- Expand 2 states (live/dead) → **5 states** (LIVE green-solid, FORZATA amber-solid+🔒+ribbon, MORTO dim/desaturate, auto-wants dashed-blue, idle/cold). Drive FORZATA from `status.reason==="override" && live_cam===cam`; auto-wants from `/preview` `auto_candidate`. Same `classList.toggle` mechanism — add classes, do not invent a new dispatcher.
- **Color migration (UI-SPEC §Color):** existing `.tile.live { border-color:#b23b3b }` and `.badge.live{background:#b23b3b}` → green `#34D399`; `.danger{background:#b23b3b}` → `#9b2c2c`; `legend{font-weight:600}` → `700`. No 500/600 anywhere.
- Add per-tile inline `<svg viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet">` with one `<rect vector-effect="non-scaling-stroke">`; the tile `<img>` must use `object-fit: contain` (existing CSS uses `aspect-ratio:16/9` on the img — verify contain) so SVG meet-scaling = letterbox, **zero JS math**. Draw nothing when `box` is `None`; hide overlay when tile STALE/MORTO. Update geometry only on `gen` advance.
- Make whole tile `role="button"` + `aria-pressed`; bind tap-to-force (see override below).

---

### `console.html` — Override gesture (MVW-04, D-02/D-03)

**Analog:** existing force/release handlers (lines 158–161) + the `post()` helper (lines 131–135).

**Existing pattern (backend unchanged — only the gesture moves):**
```javascript
function post(url, data) {
  const body = new URLSearchParams(data);
  return fetch(url, { method:"POST", body,
    headers:{ "Content-Type":"application/x-www-form-urlencoded" } });
}
document.querySelectorAll(".force-btn").forEach(b =>
  b.addEventListener("click", () => post("/command", { force_cam: b.dataset.cam })));
document.getElementById("rilascia").addEventListener("click", () =>
  post("/command", { release: "1" }));
```
**Phase-9 deltas:** REMOVE the blind `.force-btn` text buttons (template lines 107–109) AND their handler. Bind the SAME `post("/command",{force_cam})` to a `click` on the **whole tile** instead. Keep "Rilascia (auto)" but enlarge to ≥48px, dock bottom-trailing, always visible. Use standard `click` (FORBID `touchstart`/`touchend`). The `/command` route + `OperatorCommand` are untouched.

---

### `console.html` — Score leaderboard + switch-history + reason (WHY-01/02, MVW-05)

**Analog:** existing `pollStatus` feeds-pill render (lines 229–236) for the create-element loop; existing `/preview` consumption shape (`p.gen`, `p.cams`) at lines 184–192.

**Existing DOM-build loop to copy for leaderboard/history rows:**
```javascript
const feeds = document.getElementById("feeds");
feeds.innerHTML = "";
Object.entries(s.alive || {}).forEach(([cam, ok]) => {
  const span = document.createElement("span");
  span.className = "pill " + (ok ? "feed-ok" : "feed-dead");
  span.textContent = cam + ": " + (ok ? "vivo" : "morto");
  feeds.appendChild(span);
});
```
**Phase-9 deltas:** identical `innerHTML=""` + `forEach`+`createElement` build, but driven from `/preview` `cams[id]={score,ema,state,...}` (leaderboard, sorted highest-first, bar fill by `state`: tracking solid / coast hatched / lost empty — `lost` LABEL in `#E6E9EF`, never `#6B7280`) and from `cuts` ring (history, newest-first). Reason (WHY-01) maps `status.reason` → the Italian strings in UI-SPEC §Copywriting (replace the raw `s.reason` echo at line 228). auto-wants line from `auto_candidate`.

> **GAP — route change required (see app.py below):** `/preview` currently does NOT return `cuts`. MVW-05 needs it.

---

### `app.py` — `/preview` must expose `cuts` (MVW-05) + optional SCV-01 render endpoint

**Analog:** the existing `/preview` route (lines 175–187) and `/score` route (lines 99–117) in the same file.

**Existing `/preview` JSON (cuts MISSING):**
```python
@app.get("/preview")
def get_preview():
    doc = read_preview(_path(_PREVIEW_FILE))
    return jsonify({
        "gen": doc.gen, "tick": doc.tick,
        "auto_candidate": doc.auto_candidate, "cams": doc.cams,
    })   # ← add "cuts": [dict(c) for c in doc.cuts]  (PreviewDoc already carries it; reader already parses it)
```
`PreviewDoc.cuts` exists (records.py line 194) and `read_preview` already parses it (channel.py line 220) — only the route's `jsonify` omits it. One-line add; `channel.py` `read_preview_payload` helper at channel.py:195 already includes `cuts` as a precedent.

**SCV-01 drift-guard endpoint (NEW route, if server-side guard chosen) — copy the `/score` import-and-render shape:**
```python
# inside create_app, alongside /score — reuses the SAME render_overlay_text already imported (line 42)
doc = ScoreDoc(discipline=discipline, fields=fields)
atomic_write_text(_path(_OVERLAY_FILE), render_overlay_text(doc))
```
A `/score/preview` route would build a `ScoreDoc` and return `render_overlay_text(doc)` WITHOUT writing any file — pure render, called ONCE on blur/submit (never per keystroke, never to the orchestrator). **HARD constraint:** no new heavy import — only `render_overlay_text` (already imported), `Discipline`, `ScoreDoc` (already imported, line 41).

---

### `score_render.py` — the 3 f-strings to MIRROR in client JS (SCV-01)

**Analog (READ-ONLY source of truth):** `render_overlay_text` (lines 57–86) + `_clean` (lines 32–46).

**The exact 3 formats + sanitize to replicate character-for-character in JS** (note the **double spaces**):
```python
# disc_tf:         f"Prese: {prese}  Zona: {zona}  Totale: {totale}"
# disc_freestyle:  f"{nome}  Timer: {timer}"
# agility:         f"Tempo: {tempo} / SCT: {sct}  Faults: {faults}"
# _clean(): drop CR/LF + non-printable control chars; .strip(); cap at _MAX_FIELD_LEN = 64
```
Client JS mirror must: strip CR/LF/control chars, `trim()`, cap each field at 64, debounce 150–250ms, render into "Anteprima overlay". Drift-guard on blur/submit asserts `client === server` (via the optional route above) → "⚠ Anteprima non allineata — verifica" on mismatch. A Wave-0 CI parity test feeds identical `ScoreDoc`s to both.

---

### Score form one-handed touch (UXT-01)

**Analog:** existing score form (template lines 57–95) — already mostly compliant.

**Already correct (PRESERVE):** `inputmode="numeric"`/`"decimal"` on the right fields (lines 71–89); inputs at `1rem` ≥16px (line 16, blocks iOS focus-zoom — never drop to `0.9rem`); the visible-discipline-only submit builder (lines 141–151) that avoids posting hidden fieldsets.
**Deltas:** add `enterkeyhint="next"`/`"send"`; ensure `type="text"` (never `type="number"`); client numeric validation must accept BOTH `,` and `.`; add helper copy "usa il punto (.) per i decimali". The visible-fields submit pattern (lines 144–149) is the precedent for any per-discipline preview wiring.

---

## Shared Patterns

### Crash-isolation import allowlist (HARD GATE)
**Source:** `app.py` module docstring (lines 9–11) + `tests/test_imports.py` (lines 18–101).
**Apply to:** every change to `app.py` and any new route/import.
```python
HEAVY_MODULES = ["torch", "ultralytics", "cyndilib", "obsws_python"]
# test forces these + numpy ABSENT, then: import segugio.ui; create_app(...) must still build
```
The console imports ONLY `flask` (inside `create_app`) + `segugio.opcomm` + `segugio.ui.score_render`. Any new import (e.g. for SCV-01) MUST stay inside this allowlist or the guard test fails. No numpy/cv2/PIL.

### Safe-default never-raise readers
**Source:** `channel.py` `read_preview`/`read_status` (lines 162–224).
**Apply to:** all route handlers reading the channel. Readers return a default doc on absent/torn/malformed input — routes never need try/except around them; the client-side silent-coast handles transport errors.

### Server-render the cam whitelist (WR-01)
**Source:** `app.py` `index()` (line 97) → `console.html` `CAMS = {{ cam_ids | tojson }}` (line 166).
**Apply to:** all new per-tile DOM (leaderboard rows, overlays) — iterate `CAMS`, never hard-code ids. The `cam_ids` arg is the single source; never `import segugio.config` in the console.

### Flask-test-client testing (no server, no heavy deps)
**Source:** `tests/test_ui_score.py` (lines 19–46) + `file_channel` fixture.
**Apply to:** new route tests (`/preview` cuts, `/score/preview` drift endpoint). Build `create_app(tmp_dir)`, `app.test_client()`, POST/GET, assert on written channel files.

---

## No Analog Found

None. Every Phase-9 surface extends existing console code, an existing route, an existing pure fn, or an existing test harness. No greenfield module, no new dependency, no new data field (the `PreviewDoc`/`DirectorStatus` contract from Phase 7 is complete and locked).

The ONLY non-render server change is exposing the already-existing `cuts` field in the `/preview` jsonify (one line) and an optional pure `/score/preview` render route — both modeled on sibling routes in the same file.

## Metadata

**Analog search scope:** `src/segugio/ui/`, `src/segugio/opcomm/`, `tests/`
**Files scanned:** console.html, app.py, score_render.py, records.py, channel.py, test_ui_score.py, test_fault_isolation.py, test_imports.py
**Pattern extraction date:** 2026-06-13
