# Pitfalls Research

**Domain:** v1.3 "Gestione Punteggi Avanzata" — richer, SHARED, auto-calculating, validated score entry layered onto a crash-isolated Flask console that publishes a single on-air score over the opcomm file channel to `/overlay`, `overlay.txt`, and `score.json`.
**Researched:** 2026-06-21
**Confidence:** HIGH — grounded in this repo's own code (`ui/app.py`, `ui/score_render.py`, `opcomm/atomic.py`, `opcomm/channel.py`, `opcomm/records.py`, `ui/static/overlay-render.js`, `ui/templates/overlay.html`, `ui/templates/console.html`) and its already-shipped SCV-01→SCV-02, RBT-06, T-14-xss, and D-03 crash-isolation decisions. The pitfalls below are the *specific* traps of adding the v1.3 features to THIS architecture, not generic web-form advice.

> Reading order for the executor: this milestone's core risk is **re-introducing exactly the kinds of bugs the project already paid to retire** (mirror drift, frozen-score-on-air, crash-isolation breach, HTML-injection at the sink). Every critical pitfall below is anchored to a hard-won project decision so the prevention is "do what v1.2 already did," not "invent something new."

---

## Critical Pitfalls

### Pitfall 1: Re-introducing the SCV-01 byte-exact-mirror trap (PAGE ↔ POPUP drift)

**What goes wrong:**
v1.3 needs the *same* rich score-entry UI in two places — a dedicated page and a console popup/modal. The tempting move is to write the entry/validation/auto-calc logic once for the page, then copy or re-implement it for the modal (or maintain a parallel "preview of what will air" computation). Two copies drift: the page computes a freestyle total of 87, the popup shows 86 (rounding differs), or a validation rule tightens on one but not the other, or the auto-calc formula is edited in one file and not the other. This is the EXACT failure SCV-01 fought (a byte-exact JS↔Python mirror of `render_overlay_text`) and that SCV-02 structurally killed by making the console preview an `<iframe src="/overlay?preview=1">` of the ONE renderer.

**Why it happens:**
A modal feels like "a different surface" so a developer instinctively duplicates the form markup and its JS. The "keep them byte-exact by hand + a drift-guard test" pattern feels like diligence but is the anti-pattern the project already retired — a guard test only tells you *after* they have drifted, and only for the cases the test covers.

**How to avoid:**
- Build score entry as ONE component (one HTML partial/template + one JS module) and mount it in both the dedicated page and the modal. The modal hosts the SAME component (include the same partial, or iframe the same route the way SCV-02 iframes `/overlay`), never a re-typed copy.
- All auto-calc and validation logic lives in ONE module imported by both mounts — zero duplicated formulas, zero "mirror" comment blocks.
- If you ever find yourself writing a `gsd:scv*-mirror` block or a "keep in sync with X" comment, STOP — that is the retired pattern resurfacing. SCV-02's lesson: one renderer → drift structurally impossible.
- Reuse the existing precedent literally: the overlay already proves "one renderer, two contexts differ only by a cosmetic `body.preview` class." Apply the same shape to score entry (one component, the modal differs only by chrome/positioning).

**Warning signs:**
- Two files contain the same field labels, the same `prese`/`zona`/`totale` selection, or the same total formula.
- A code comment says "mirror of …" or "keep byte-exact with …".
- A drift-guard test exists for the entry component (means you accepted divergence and are policing it instead of preventing it).
- The modal and the page render subtly different layouts/validation messages in manual testing.

**Phase to address:**
The FIRST build phase (shared component foundation). This must be the architectural spine before any auto-calc/validation is written, or the duplication is baked in and expensive to undo.

---

### Pitfall 2: Double source of truth — client live auto-calc disagrees with the server-written `overlay.txt` / `score.json` that actually airs

**What goes wrong:**
The rich entry form shows a live-updating total as the operator types (client-side auto-calc — good UX). But the value that AIRS comes from a different path: `POST /score` → `write_score(score.json)` + `atomic_write_text(overlay.txt, render_overlay_text(doc))` + `/overlay-json` → `overlay-render.js`. If the client computes the total one way and the server (or the overlay renderer) computes/formats it another way, the operator sees 87 in the form but 86 goes on air. With v1.3 adding multi-throw sums, per-discipline penalties, and freestyle criterion sums, there are now THREE places a total could be computed: the entry form (live preview), the server on POST, and the overlay renderer at display time. Today `render_overlay_text` and `overlay-render.js` are STRICTLY display-only (SCR-04: "never sums prese into totale … if a Totale is shown it is the operator-entered total VERBATIM"). Auto-calc deliberately breaks that invariant — so you must pick ONE authority and make the other two echo it.

**Why it happens:**
Auto-calc is naturally written in the form (instant feedback). The server write and the overlay render already exist and are display-only. Without a decision, each grows its own arithmetic and they diverge on edge cases (rounding, empty fields, half-entered throws, locale decimal `.` vs `,`).

**How to avoid:**
- Decide the single authority explicitly. Recommended: **the shared entry component computes the total once, and the COMPUTED total is what gets POSTed** as a plain field. The server stays display-only (it stores and renders the number it received verbatim), preserving the existing SCR-04 invariant for `render_overlay_text` and `overlay-render.js`. This keeps the overlay path a dumb sink and means "what you see in the form is byte-identical to what airs."
- Because the entry component is shared (Pitfall 1), there is exactly ONE auto-calc implementation feeding both the preview and the POST body — they cannot disagree.
- Do NOT add arithmetic to `render_overlay_text` or `overlay-render.js`. If a total is shown on the overlay it must be the value the operator/component already finalized and POSTed, exactly as today. (If product insists the server computes, then the client must DISPLAY the server's echoed value — never its own — i.e. POST the parts, read back `/overlay-json`, show that. Pick one direction and never both.)
- Round/format the total in ONE place (the shared component) so the on-air string and the form string are produced by the same code.

**Warning signs:**
- Arithmetic (`+`, `reduce`, `sum`, penalty multiplication) appears in `render_overlay_text` or `overlay-render.js`.
- The form's displayed total and the overlay's `Totale` cell differ for any input during manual testing.
- Empty/partial-throw inputs produce a different total in the preview vs after a publish round-trip.
- Decimal handling (`.` vs `,`) differs between the live preview and the aired string.

**Phase to address:**
The auto-calc phase, immediately after the shared component exists. Write one acceptance test asserting: for a representative input, the form-displayed total === the string in `overlay.txt` === the `Totale` cell rendered from `/overlay-json`.

---

### Pitfall 3: Validation only on the client → a bypassing POST writes a bad score ON AIR

**What goes wrong:**
Per-discipline validation (ranges, required fields, `mm:ss` time format) is implemented in the form's JS. But the publish path is `POST /score`, which today accepts ANY non-empty fields verbatim (`fields = {k: v for k, v in form.items() if … v.strip()}` → `ScoreDoc` → straight to `score.json` + `overlay.txt`). A direct `curl`/replayed POST, a stale browser tab, a half-submitted modal, or a future second client bypasses the JS entirely and puts an out-of-range / malformed value on the broadcast. The trust boundary is the LAN (D-02), so this is not a malicious-actor scenario primarily — it is an "operator's other tablet posted garbage" / "a script posted before the form validated" integrity scenario. The console's own docstring frames the input boundary as server-side enforcement (discipline whitelisted to the Enum, contradictory commands rejected at construction) — validation must follow that same "reject at the boundary" pattern, not live only in the browser.

**Why it happens:**
Client validation gives instant feedback and feels sufficient; the server route is already permissive (display-only design intentionally accepted free-form fields). Adding server validation feels redundant when the form "already checks."

**How to avoid:**
- Enforce validation on the SERVER in `POST /score` too: reject (HTTP 400, write NOTHING) when required fields are missing, ranges are violated, or the time format is malformed — mirroring how `OperatorCommand`/`Discipline` already reject malformed input at the boundary and return 400 without writing.
- Put the validation RULES in the shared component module so the client and server enforce the *same* rules (one rule set, two enforcement points) — same anti-drift discipline as Pitfall 1. If the server is Python and the rules are JS, keep the rule definitions (ranges, required-field lists, regex) in a single declarative source both consume, or accept a small validated server-side re-check that is the authority.
- Validate AFTER discipline selection: the rule set is per-discipline (disc T&F vs agility vs freestyle), so the server must pick the rule set from the whitelisted discipline before checking fields.
- Critically: a failed server validation must leave the *previous* on-air score untouched — never publish a partial/blank score because a write started. Validate fully, THEN write atomically (write-after-validate ordering).

**Warning signs:**
- `POST /score` has no rejection path other than unknown-discipline 400.
- A `curl -d 'discipline=agility&tempo=notatime'` round-trips onto the overlay.
- Validation messages exist only in the browser; the route writes whatever it gets.
- A malformed value briefly airs and then is "fixed" by a second submit (means the bad one was published).

**Phase to address:**
The validation phase. Server-side rejection is a named acceptance criterion ("a bypassing POST of an invalid score returns 400 and the on-air score is unchanged"). Add a Flask-test-client gate analogous to the existing `test_ui_score.py` / boundary-rejection tests.

---

### Pitfall 4: Breaking the `overlay.txt` degraded fallback or the `/overlay` / `/overlay-json` contract

**What goes wrong:**
v1.3 enriches the score model (multi-throw, criteria, judges). It is easy to (a) stop writing `overlay.txt` (or write a richer structure into it that the OBS read-from-file text source can't show), (b) change the `/overlay-json` payload shape so `overlay-render.js` breaks, or (c) bake new score data into the `/overlay` host page (it must stay THIN and poll-only — "NO score/run data is baked in … the page never reloads on a score change"). Any of these silently regresses RBT-06/SCR-01: `overlay.txt` is the retained degraded text fallback (the hidden manual-toggle `Score Text` source wired in all 7 OBS scenes), and a graphics-source failure mid-event is exactly when the text fallback must still work. The contract is load-bearing: `overlay.txt` is a SINGLE LINE (no embedded newlines), length-bounded, control-char-stripped; `/overlay-json` echoes `fields` verbatim plus `discipline/running/started_at/server_now/gen`; `gen` advances on every `/score` and `/run`.

**Why it happens:**
The rich UI's natural data shape (nested throws/criteria) doesn't map cleanly to one text line, so a developer either drops `overlay.txt` ("the graphics overlay is what we use now") or stuffs multi-line content into it. And it's tempting to add new fields directly to the `/overlay` page render args rather than through the poll payload.

**How to avoid:**
- KEEP writing `overlay.txt` on every `POST /score`, exactly as today (`atomic_write_text(_OVERLAY_FILE, render_overlay_text(doc))`). Extend `render_overlay_text` to summarize the richer score into ONE line (e.g. the discipline's headline + computed total) — never multi-line, always through `_clean` (control-char strip + 64-char cap). The fallback's job is "a frozen-but-legible score when graphics die," not full fidelity.
- Treat `/overlay-json` as an ADDITIVE contract: add new keys, never rename/remove `discipline`/`fields`/`running`/`started_at`/`server_now`/`gen`. `fields` stays the verbatim `{label: value}` dict the renderer reads via `scvGet`. Keep assembling it EXCLUSIVELY from the never-raise readers + `time.time()` (no `json.load`/`open` in the route).
- Keep `/overlay` thin: any new STATIC branding goes through `overlay_cfg` render args (resolved in the entrypoint, never `import segugio.config` at module top); dynamic score data NEVER goes into the page, only into the poll payload.
- Preserve `gen` bumping on `/score` and `/run` (the CEF cache-bust + render gate depend on it).
- Run the existing gates that pin these contracts (`test_overlay_fallback_gate.py`, `test_ui_overlay_json.py`, `test_ui_overlay_page.py`, `test_overlay_poll_storm.py`) and extend, don't replace, them.

**Warning signs:**
- `atomic_write_text(overlay.txt, …)` removed from `POST /score`, or `render_overlay_text` returns a string containing `\n`.
- `/overlay-json` drops or renames an existing key; `overlay-render.js`'s `scvGet`/discipline-cell lookups stop matching.
- Score data appears as a Jinja `{{ }}` in `overlay.html`.
- `overlay.txt` is missing/blank after a publish; the OBS `Score Text` fallback shows nothing when toggled.

**Phase to address:**
The publish-integration phase (wiring the rich score to the three sinks). Add an acceptance check: after a rich `POST /score`, `overlay.txt` is a single non-empty ≤64-char-per-field line AND `/overlay-json` still carries all legacy keys AND `/overlay` GET contains no score values.

---

### Pitfall 5: XSS / HTML-injection at the overlay sink via richer free-text fields (freestyle `nome`, judge names)

**What goes wrong:**
v1.3 adds more FREE-TEXT fields than v1 had: freestyle competitor `nome`, possibly judge names, criterion labels. These cross the trust boundary operator-typed → broadcast HTML. v1.2 closed T-14-xss with a two-pronged sink discipline: (1) `overlay-render.js` writes EVERY operator value via `textContent`, NEVER `innerHTML`; (2) Jinja autoescape escapes static branding (`event_name`, `logo_path`). A new field rendered with `innerHTML` (or built by string-concatenating markup, the way `console.html`'s leaderboard uses `board.innerHTML = ""` then careful `createElement`) re-opens the hole — a `<script>` or `<img onerror=…>` in a judge name executes IN the OBS browser-source, on air.

**Why it happens:**
New fields are added by copy-pasting a quick render that uses `innerHTML` for convenience, or by extending the console's leaderboard code which already touches `innerHTML` for its own (static-markup) reasons. The `_clean`/`cleanField` sanitizer is a length/control-char guard, NOT an HTML-context escape — a developer may assume "it's sanitized" and reach for `innerHTML`.

**How to avoid:**
- EVERY operator/free-text value in the overlay renderer and the entry component goes to the DOM via `textContent` (or `createTextNode`), never `innerHTML`, never markup string concatenation. This is exactly the discipline `fillCell`/`renderIdentity` already follow.
- Any new static label rendered server-side stays inside Jinja `{{ }}` (autoescaped); never mark anything `| safe`.
- Understand the layering: `cleanField`/`_clean` (strip control chars, cap 64, keep U+0020) is a *cosmetic/overflow* guard. The HTML-context safety is `textContent`. Both must be present; one is not a substitute for the other.
- Extend `test_overlay_html_sink_gate.py` to assert no `innerHTML` sink for the new fields, and add a Jinja-autoescape assertion for any new server-injected label (a crafted `<script>` in a judge name must render escaped).
- Beware the entry component echoing values back into the form/modal preview — that preview is ALSO a sink; use `textContent` there too.

**Warning signs:**
- A new `.innerHTML =` or template-literal-built HTML string anywhere in `overlay-render.js` or the shared entry component (the gate forbids `innerHTML =`, `innerHTML=`, `.innerHTML`).
- A `| safe` filter appears in a template.
- A judge/competitor name containing `<` or `&` renders as markup (not literal text) in the overlay or the form preview.

**Phase to address:**
The phase that adds the free-text fields (freestyle multi-criterion / identity). Carry the v1.2 sink gate forward and extend it to the new fields BEFORE shipping them.

---

### Pitfall 6: Breaking crash-isolation — importing something heavy into the console or its new modules

**What goes wrong:**
The HARD standing constraint: the console imports ONLY Flask + `segugio.opcomm` (stdlib + loguru leaf), NEVER ultralytics/torch/cyndilib/obsws/cv2/numpy, and NEVER the orchestrator/director. v1.3 adds new server modules (validation rules, auto-calc, a richer renderer). A new `import numpy` for "easy summing," a `from ..config import …` at module top for discipline rules, or pulling a shared model from the orchestrator side silently breaks the isolation that guarantees a UI exception can never reach the director (D-03/RBT-04). The import-smoke test (`test_imports.py::test_console_resolves_with_heavy_stack_and_numpy_absent`) forces torch/cv2/numpy/cyndilib/obsws ABSENT and asserts `segugio.ui` imports AND `create_app` builds AND `/overlay-json`/`/overlay` resolve — a heavy import would make it fail.

**Why it happens:**
Auto-calc/validation tempts `numpy` (it's already a project dep elsewhere) or pulling discipline definitions from `segugio.config` (where the discipline discriminated-union lives). Both are "natural" but forbidden in the console process.

**How to avoid:**
- New score-entry server logic (validation, auto-calc, the rich renderer) must be stdlib-only (+ Flask + opcomm + loguru). Do arithmetic with plain Python; do not reach for numpy.
- Do NOT `import segugio.config` (or anything that transitively imports torch/cv2/numpy) at module top in any `segugio.ui` module. If discipline rules must come from config, inject them as plain dicts/args at `create_app` time the way `cam_ids` and `overlay_cfg` are resolved LAZILY in the entrypoint (`if _cfg_path: from ..config.loader import load_config` inside the function, never at module top).
- Keep Flask imported INSIDE `create_app`, not at module top, so `import segugio.ui` stays Flask-free (existing pattern).
- EXTEND the import-smoke test to cover every new `segugio.ui` module and the new routes under the heavy-absent block — make adding a heavy import fail CI.

**Warning signs:**
- Any `import numpy`, `import cv2`, `import torch`, or `from ..config`/`from ..orchestrator`/`from ..decision` at the top of a `segugio.ui` module (note: `OperatorCommand.to_override` lazily imports `decision` *inside a method* — that's the allowed pattern, never module-top).
- `test_console_resolves_with_heavy_stack_and_numpy_absent` fails or is weakened to "fix" an import.
- `create_app` gains a heavy dependency to build.

**Phase to address:**
EVERY phase that adds a `segugio.ui` module — but make it a gate in the first (foundation) phase by extending the import-smoke parametrize list, so subsequent phases inherit the guard automatically.

---

### Pitfall 7: Multi-round / multi-throw STATE management — lost on reload, partial writes, non-atomic, racing the gen-bump

**What goes wrong:**
Multi-throw disc T&F and freestyle multi-criterion need *accumulating* state (throw 1..N, criterion scores per judge) before a final total is published. New traps:
- **Lost on reload:** if accumulating state lives only in the browser, a tablet refresh / sleep-wake / accidental tab close loses the in-progress run's throws. (The page survives sleep/wake via `visibilitychange`/`pageshow` today, but in-memory JS state does not survive a reload.)
- **Partial / non-atomic writes:** if per-throw state is persisted server-side, it MUST go through `atomic_write_*` (temp + fsync + `os.replace`, same-volume temp, Windows MoveFileEx retry). Hand-rolling `open(...).write()` for a new "throws.json" gives readers torn files — the exact failure the whole channel was built to prevent.
- **Racing the gen counter:** the gen bump is a read-modify-write under `_gen_lock` on a multi-threaded server (`threaded=True`/waitress). A new per-throw write path that also bumps gen, or bumps it OUTSIDE the lock, corrupts the monotonic `gen` the overlay's cache-bust + render gate depend on.
- **`started_at`/`running` clobber:** `/score` deliberately PRESERVES `running`/`started_at` from in-memory state (WR-03) and only bumps gen — a disk re-read there could collapse a live run to `running=False`. A new multi-throw write must follow the same "only touch what you own, from in-memory authoritative state" rule.

**Why it happens:**
Accumulating UI state is easy to keep client-side; persistence is added late and quickly with a naive file write; the gen/run-state subtleties are non-obvious and easy to clobber.

**How to avoid:**
- Decide where in-progress run state lives. For a single-operator field tool, keeping the in-progress throws in the shared component's client state is acceptable IF the FINAL published score is what's persisted — but protect against accidental loss (see Pitfall 8: a confirm/explicit-publish step, and persisting in-progress state to `localStorage` so a reload restores it).
- If in-progress state is persisted server-side, ALWAYS use `atomic_write_json` / `atomic_write_text` (never hand-rolled writes), with the temp in the target's own directory. Add a never-raise `read_*` boundary for any new file (malformed/absent → safe default), exactly like every existing reader.
- Any new write that needs cache-busting must bump `gen` THROUGH the existing `_gen_lock`-guarded helper pattern (`_bump_score_gen`), never a parallel unsynchronized counter, and must PRESERVE `running`/`started_at` from in-memory `_state` (WR-03) unless it is a genuine run edge.
- Keep the per-message-is-its-own-file discipline (RESEARCH Pattern 3) — a new state file is SEPARATE from `score.json`/`runstate.json`/`overlay_run.json`; the director still reads ONLY `runstate.json` and never the new file (D-03).

**Warning signs:**
- In-progress throws vanish after a refresh / sleep-wake.
- A new `.json` written with bare `open(...).write()` or `json.dump` to the target path (not via `atomic_write_*`).
- `gen` bumped outside `_gen_lock` or by two code paths; the overlay stalls or double-bumps.
- After a multi-throw save, the run timer resets (`running`/`started_at` got clobbered).
- A torn read of the new state file raises into a route (500) instead of safe-defaulting.

**Phase to address:**
The multi-round/multi-throw phase. Gate: a reload mid-run does not lose entered throws; every new persisted file goes through `atomic_write_*` and a never-raise reader; gen stays monotonic under concurrent writes.

---

### Pitfall 8: Modal / tablet UX traps — focus trap, iOS keyboard zoom, accidental publish, no-internet LAN

**What goes wrong:**
The popup/modal and the rich entry on a tablet introduce field-UX failures that a desktop dev never sees:
- **Accidental publish:** a rich modal with many fields makes an errant tap/Enter publish a half-entered or wrong score ON AIR. The current form publishes on submit immediately (`/score` → overlay). With multi-throw/criteria, premature publish is now a *broadcast integrity* event.
- **iOS keyboard zoom:** inputs with `font-size < 16px` cause iOS Safari to auto-zoom on focus, breaking the tablet-first landscape layout (UXT-01 contract). The existing console uses `inputmode`/`enterkeyhint` and a touch contract — the new modal must inherit it.
- **Focus trap / dismissal:** a modal that doesn't trap focus, or that closes on backdrop tap, can lose entered data or strand keyboard/AT users; closing it accidentally mid-entry loses state (ties to Pitfall 7).
- **No-internet LAN:** the rig runs on a dedicated WiFi with NO internet (and AP client isolation is a HARD operational requirement). Any CDN font, icon set, or script in the new page/modal will FAIL to load — blank icons, FOUC, or a non-functional form. The console already uses a SYSTEM font stack and INLINE Tabler SVG icons specifically for this; the overlay inlines critical CSS to avoid a late-loading white flash.
- **Stale-tab publish:** a tablet left open overnight, woken, and submitted can publish against a stale run.

**Why it happens:**
Modals and tablets are tested on a desktop browser with internet; iOS zoom and offline-LAN failures only show on the actual device on the actual rig — which is hardware-gated and deferred, so these bugs ship silently.

**How to avoid:**
- **Explicit publish:** separate "enter/accumulate" from "publish to air." The big destructive action (put this score ON AIR) should be deliberate and visually distinct (like the existing `danger`-styled "Ferma run"), not the same casual tap that adds a throw. Consider a confirm on the publish-to-air action.
- **iOS:** all modal/page inputs ≥16px font-size (or the documented `maximum-scale` workaround), reuse the existing `inputmode`/`enterkeyhint`/`touch-action`/≥44–48px target / safe-area contract (UXT-01). Test on a real iPad (the project's acceptance bar), not just desktop.
- **Modal hygiene:** trap focus inside the modal, do NOT dismiss-on-backdrop when fields are dirty (or warn), restore focus on close. Persist in-progress entry (localStorage) so an accidental close/reload doesn't lose throws (Pitfall 7).
- **Offline-LAN:** ZERO external resources — no CDN fonts/icons/scripts. Reuse the system-font stack + inline-SVG-icon + inline-critical-CSS patterns the console/overlay already follow. Self-host every static asset under `/static`.
- **Tablet decode/leak hygiene:** follow UXT-03 (leak-free refresh, freshness stamps, sleep/wake resume) — a long-running modal must not leak or freeze.

**Warning signs:**
- An input's computed font-size < 16px on iOS → zoom-on-focus jump.
- A `<link href="https://…">` or `<script src="https://…">` (CDN) anywhere in the new page/modal.
- The publish action is the same affordance as add-a-throw; operators can air a partial score by reflex.
- Closing the modal loses entered data; focus escapes to the page behind it.
- Blank icons / FOUC / non-functional form when tested on the isolated rig WiFi (no internet).

**Phase to address:**
The modal/tablet-UX phase. Many checks are hardware-gated (real iPad on the rig) and will land in the deferred field-UAT — but the offline-asset and explicit-publish and ≥16px-input rules are CODE-time and must be gated in the build phase, not deferred.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Duplicate the entry form/JS for the modal "just for now" | Ship the modal fast | Re-creates the SCV-01 drift trap the project paid to retire; page/popup totals diverge | NEVER — the shared-component spine is the whole point of this milestone |
| Client-only validation, no server re-check | Less code, instant UX | A bypassing/stale/replayed POST airs a bad score | NEVER for the publish path — server must reject at the boundary |
| Add auto-calc arithmetic into `render_overlay_text` / `overlay-render.js` | Total "just appears" on the overlay | Breaks SCR-04 display-only invariant; creates a 3rd source of truth that drifts | NEVER — overlay sinks stay display-only; compute once in the shared component |
| `import numpy` for summing in the console | Familiar API | Breaks crash-isolation; import-smoke test fails; UI exceptions can reach director | NEVER in `segugio.ui` — stdlib arithmetic only |
| Drop `overlay.txt` because "graphics overlay replaced it" | One less write path | Loses the RBT-06 degraded fallback exactly when graphics fail mid-event | NEVER — `overlay.txt` is retained by requirement |
| Persist in-progress throws with a bare `open().write()` | Quick persistence | Torn-file reads, the failure the atomic channel exists to prevent | NEVER — always `atomic_write_*` + never-raise reader |
| Keep in-progress run state client-only with no localStorage backup | Simplest state model | A reload/accidental-close loses the run's throws live | Acceptable ONLY with explicit-publish + localStorage restore as mitigation |
| Inline a CDN font/icon "temporarily" | Pretty fast | Hard-fails on the offline rig WiFi; blank UI on air-day | NEVER — self-host everything; system fonts + inline SVG |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OBS `Score Text` (read-from-file `overlay.txt`) | Writing multi-line / rich content; stopping the write | Keep ONE sanitized line via `render_overlay_text` + `atomic_write_text`, every publish |
| OBS browser-source `/overlay` (CEF) | Baking score data into the page; per-gen cache key | Keep page thin + poll-only; cache-bust with the per-REQUEST `?t=` nonce (CEF ignores `no-store`, caches by URL) |
| `/overlay-json` consumer (`overlay-render.js`) | Renaming/removing keys; computing totals in the renderer | Additive-only payload; renderer stays display-only via `textContent` |
| opcomm atomic file channel | New state file written non-atomically or read without a safe default | `atomic_write_json/text` (same-volume temp, fsync, MoveFileEx retry) + never-raise `read_*` |
| `overlay_run.json` gen/run-state | A new write clobbers `running`/`started_at` or bumps gen outside the lock | Bump gen via the `_gen_lock` helper; preserve run state from in-memory `_state` (WR-03) |
| `segugio.config` (discipline rules) | `import segugio.config` at console module top | Inject rules as plain dicts at `create_app` time; lazy-import config only inside the entrypoint |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Recompute/re-render the whole modal on every keystroke | Sluggish entry on a tablet; battery drain | Update displayed total/cells IN PLACE (textContent), never node-rebuild (the `fillCell` pattern) | Noticeable on iPad with many fields (freestyle multi-criterion) |
| New poll/heartbeat loop alongside `/overlay-json` | `/command` override starved; CPU spin | Reuse existing `setInterval(poll, PUBLISH_MS)`; never add a 60fps loop; keep `threaded=True`/waitress | Under concurrent preview + overlay + command load on one WSGI worker |
| Per-throw server write on every field change | Disk churn + gen-bump storm; overlay flicker | Persist on meaningful events (throw committed / publish), not per-keystroke; debounce | Multi-throw runs with rapid edits |
| fsync on a high-frequency new state file | Publisher/route latency | Match the existing fsync policy (durable for state that must survive a crash; the ephemeral-JPEG `fsync=False` precedent is ONLY for regenerated data) | Only if a new file is written very frequently |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Rendering freestyle `nome` / judge names via `innerHTML` | `<script>`/`onerror` executes in the OBS browser-source — XSS ON AIR | Always `textContent`/`createTextNode`; never `innerHTML`; keep the sink gate test |
| Marking a new server-injected label `\| safe` | Markup injection through "trusted" branding | Keep Jinja autoescape ON; never `\| safe` |
| Trusting client validation for the publish path | A LAN POST (stale tab / second device / script) airs an out-of-range or malformed score | Server-side validation rejects with 400 and writes nothing |
| Operator-supplied path/filename for a new state file | Path traversal write | Filenames FIXED server-side (the existing constant-filename + whitelisted-id pattern) |
| Assuming "sanitized" (`_clean`) == HTML-safe | A capped/control-stripped value still injects markup if put in `innerHTML` | Treat `_clean` as overflow/cosmetic only; HTML safety is the `textContent` sink |
| New free-text field bypasses the 64-char / control-char clean | Overflowing/control-laden value breaks `overlay.txt` line or the lower-third layout | Route every displayed value through `_clean`/`cleanField` |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Casual tap/Enter publishes to air | A half-entered score broadcasts | Distinct, deliberate publish-to-air action (danger-styled, optional confirm) |
| Inputs < 16px font on iOS | Zoom jump on focus, broken landscape layout | All inputs ≥16px; reuse the UXT-01 touch contract |
| Modal closes on backdrop tap mid-entry | Lost throws/criteria | Don't dismiss-on-backdrop when dirty; warn; persist to localStorage |
| No focus trap in the modal | Keyboard/AT users stranded; data loss | Trap focus; restore on close |
| CDN font/icon on the offline rig | Blank icons / FOUC / dead form on air-day | Self-host; system fonts + inline SVG (existing pattern) |
| Live preview total differs from what airs | Operator distrust; wrong score broadcast | One auto-calc authority feeds both preview and POST (Pitfall 2) |
| No indication a score is stale/not-live in the modal | Operator publishes against a dead run | Reuse the freshness/degrade signaling (UXT-03 / overlay `is-stale`) |

## "Looks Done But Isn't" Checklist

- [ ] **Shared component:** Often missing the SECOND mount actually using the same module — verify the modal includes the same partial/JS, not a copy (grep for duplicated field labels / `mirror` comments).
- [ ] **Auto-calc:** Often missing a round-trip check — verify form-displayed total === `overlay.txt` line === `/overlay-json`-rendered `Totale` for the same input.
- [ ] **Validation:** Often missing server-side enforcement — verify a `curl` POST of an invalid score returns 400 and the on-air score is UNCHANGED.
- [ ] **`overlay.txt`:** Often missing after the refactor — verify it's still written every publish, single-line, ≤64-char-per-field, and the OBS `Score Text` fallback shows it when toggled.
- [ ] **`/overlay-json` contract:** Often silently changed — verify all legacy keys (`discipline/fields/running/started_at/server_now/gen`) still present and `overlay-render.js` still renders.
- [ ] **`/overlay` thinness:** Verify no score data is baked into the page (grep the rendered HTML for posted values).
- [ ] **XSS sink:** Verify no `innerHTML`/`\| safe` for any new free-text field; a `<script>` judge name renders escaped/literal.
- [ ] **Crash-isolation:** Verify the import-smoke test passes with torch/cv2/numpy/cyndilib/obsws ABSENT, including every NEW `segugio.ui` module and route.
- [ ] **Atomic state:** Verify any new persisted file goes through `atomic_write_*` and has a never-raise reader (torn/absent → safe default, no 500).
- [ ] **gen/run-state:** Verify a multi-throw save bumps `gen` under the lock and does NOT clobber `running`/`started_at` (timer doesn't reset).
- [ ] **Reload survival:** Verify a tablet reload mid-run restores in-progress throws (not lost).
- [ ] **Offline assets:** Verify ZERO external (CDN) resources in the new page/modal.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Page↔popup drift (Pitfall 1) | MEDIUM | Collapse to one shared component/module; delete the copy + any mirror guard; re-mount the modal on the shared partial |
| Double source of truth (Pitfall 2) | MEDIUM | Pick the single authority (shared component computes → POST verbatim); strip arithmetic from `render_overlay_text`/`overlay-render.js`; add the round-trip equality test |
| Client-only validation (Pitfall 3) | LOW | Add server-side rejection in `POST /score` (400, write-nothing, validate-before-write); add a Flask-test gate |
| Broken `overlay.txt`/contract (Pitfall 4) | LOW–MEDIUM | Restore the `atomic_write_text` write + single-line `render_overlay_text`; re-add dropped `/overlay-json` keys; move score data out of the page; rerun the fallback/json/page gates |
| XSS sink (Pitfall 5) | LOW | Replace `innerHTML` with `textContent`/`createTextNode`; remove `\| safe`; extend the sink gate to the new fields |
| Crash-isolation breach (Pitfall 6) | LOW–MEDIUM | Remove the heavy/config module-top import; inject as args or lazy-import in the entrypoint; rerun the import-smoke test |
| Non-atomic/lost state (Pitfall 7) | MEDIUM | Route the write through `atomic_write_*`; add a never-raise reader; move gen-bump under `_gen_lock`; add localStorage restore |
| UX/offline traps (Pitfall 8) | MEDIUM (hardware-gated to find) | Self-host assets; ≥16px inputs; explicit-publish + confirm; focus trap; validate on a real iPad on the rig |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 — Page↔popup drift (SCV-01 trap) | Phase A: shared score-entry component foundation | One component mounted in both surfaces; no duplicated logic / `mirror` comment; manual page-vs-modal parity |
| 6 — Crash-isolation breach | Phase A (gate established) + every later UI phase | Import-smoke test passes with heavy+numpy absent for ALL new `segugio.ui` modules/routes |
| 2 — Double source of truth | Phase B: auto-calc | Round-trip test: form total === `overlay.txt` === `/overlay-json`-rendered total; no arithmetic in overlay sinks |
| 3 — Client-only validation | Phase C: per-discipline validation | `curl` invalid POST → 400, on-air unchanged; shared rule set; validate-before-write |
| 7 — Multi-round state | Phase D: multi-throw / round | Atomic writes + never-raise readers; gen monotonic under concurrency; run-state not clobbered; reload restores throws |
| 5 — XSS via free-text | Phase E: freestyle multi-criterion / identity (free-text fields) | Sink gate extended: no `innerHTML`/`\| safe`; crafted name renders escaped/literal |
| 4 — `overlay.txt` / contract regression | Phase F: publish-integration (rich score → 3 sinks) | `overlay.txt` single-line each publish; `/overlay-json` additive; `/overlay` carries no score data; existing gates extended |
| 8 — Modal/tablet UX | Phase G: modal + tablet UX (code-time parts now; field parts in deferred rig UAT) | No CDN assets; ≥16px inputs; explicit publish + confirm; focus trap; real-iPad acceptance on the rig |

## Sources

- `src/segugio/ui/app.py` — `POST /score` verbatim-field acceptance, `_bump_score_gen`/`_gen_lock`, WR-03 run-state preservation, `/overlay`/`/overlay-json` route contracts, crash-isolation docstring, lazy config import in the entrypoint — **HIGH** (this repo)
- `src/segugio/ui/score_render.py` — `render_overlay_text` display-only invariant (SCR-04), `_clean` 64-char/control-char guard, single-line contract — **HIGH** (this repo)
- `src/segugio/opcomm/atomic.py` — atomic write primitive (same-volume temp, fsync, Windows MoveFileEx retry), `fsync=False` ephemeral-only carve-out — **HIGH** (this repo)
- `src/segugio/opcomm/channel.py` — never-raise `read_*` boundary, additive payload assembly, strict bool/finite coercion — **HIGH** (this repo)
- `src/segugio/opcomm/records.py` — boundary validation at construction (Discipline enum, OperatorCommand XOR), per-message-is-its-own-file separation (D-03) — **HIGH** (this repo)
- `src/segugio/ui/static/overlay-render.js` — `textContent`-only sink (T-11-03-01), `cleanField`/`scvGet`, per-request `?t=` CEF cache-bust, response-recency degrade (STALE_MS/DEAD_MS), offset-cancellation timer — **HIGH** (this repo)
- `src/segugio/ui/templates/overlay.html` — thin poll-only host page, inline critical CSS / no-CDN / system-font, Jinja-autoescaped branding, transparency contract — **HIGH** (this repo)
- `src/segugio/ui/templates/console.html` — current score-entry field sets, retired `gsd:scv01-mirror` history, system-font + inline-SVG-icon offline pattern, UXT-01 touch contract — **HIGH** (this repo)
- `tests/test_imports.py` — `test_console_resolves_with_heavy_stack_and_numpy_absent` crash-isolation smoke; `tests/test_overlay_html_sink_gate.py` — XSS sink gate (no innerHTML / Jinja autoescape) — **HIGH** (this repo)
- `.planning/PROJECT.md` — Key Decisions (SCV-01→SCV-02 unification, publish-and-render, RBT-06 two-stage degrade + overlay.txt fallback, crash-isolation D-03, D-02 LAN trust boundary), v1.3 goal/scope — **HIGH** (this repo)

---
*Pitfalls research for: v1.3 Gestione Punteggi Avanzata (shared/auto-calc/validated score entry on the crash-isolated console)*
*Researched: 2026-06-21*
