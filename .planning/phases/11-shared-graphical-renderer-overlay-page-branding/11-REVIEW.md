---
phase: 11-shared-graphical-renderer-overlay-page-branding
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - config.example.yaml
  - src/segugio/config/models.py
  - src/segugio/ui/app.py
  - src/segugio/ui/static/overlay-render.js
  - src/segugio/ui/templates/overlay.html
  - tests/test_config_overlay.py
  - tests/test_imports.py
  - tests/test_ui_overlay_page.py
  - tests/test_ui_overlay_render.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-14
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase-11 broadcast overlay: the new `GET /overlay` route + `overlay_cfg`
injection in `app.py`, the transparent `overlay.html` host page, the `overlay-render.js`
client renderer (sanitize mirror, per-discipline DOM, offset-cancellation timer, freshness
watchdog, poll loop), the `OverlayParams` config grow, and the four test files.

The crash-isolation contract is honored (Flask + opcomm imported inside `create_app`; no config
import at module top; `test_console_resolves_with_heavy_stack_and_numpy_absent` proves it). The
HTML-injection sink discipline is genuinely good: every operator value reaches the DOM via
`textContent`, the Jinja `event_name`/`logo_path` go through autoescape, and the opcomm readers
reject non-finite/`bool` `started_at` upstream so the skew anchor is clean. The offset-cancellation
timer math is correct and the cold-start stale guard (`lastGen < 0`) is right.

The one BLOCKER is a CSS-injection sink in `overlay.html`: the three theme color config strings
are interpolated into an inline `<style>` block **without** the HTML-context autoescape ever
escaping CSS metacharacters — a `theme_*` value containing `}` (or `</style>`) breaks out of the
declaration and can inject arbitrary CSS/markup. The config model deliberately does NOT validate
these as hex (`models.py` line 196-201, "any CSS color token"), and the env/`SEGUGIO_OVERLAY_*`
override path feeds them straight through, so the value is attacker-influenceable on a shared rig.
The warnings cover a logo `src` injection vector, a stale-watchdog gap on a persistently-failing
fetch, a freestyle-duration NaN edge, dead/incorrect code, and a skew-jump snap.

## Critical Issues

### CR-01: Theme color config injected into inline `<style>` is not CSS-escaped — CSS/markup injection

**File:** `src/segugio/ui/templates/overlay.html:36-40`
**Issue:**
The three theme colors are interpolated directly into an inline `<style>` block:

```html
.lower-third {
  --accent: {{ theme_accent | default('#34D399', true) }};
  --plate:  {{ theme_plate  | default('#14161a', true) }};
  --text:   {{ theme_text   | default('#E6E9EF', true) }};
}
```

Jinja autoescape is an **HTML**-context escape (`<`, `>`, `&`, `"`, `'`). Inside a `<style>`
element none of those characters are the dangerous ones for CSS — `{`, `}`, `;`, `:`, `/` and the
sequence `</style>` are. Autoescape does **not** neutralize them. The config model intentionally
does **not** validate these as hex colors (`models.py:196-201`: "Plain str (NOT hex-validated): an
org may pass any CSS color token"), and `app.py:400-409` pipes `SEGUGIO_OVERLAY_ACCENT` /
`_PLATE` / `_TEXT` env vars (and `cfg.overlay.*`) straight into the render args. A value such as:

```
red; } body { background: url(http://evil/x) } .lower-third { color: red
```

breaks out of the `.lower-third` rule and injects arbitrary CSS over the live program feed (e.g. a
full-screen background image — exactly the "white box over live video" failure the transparency
contract exists to prevent). Worse, `</style><img src=x onerror=...>` terminates the style element
and, because autoescape does not touch `/`, can re-enter HTML context. The existing test
`test_overlay_event_name_is_autoescaped` proves the *event_name* path is safe but there is **no
equivalent test for the theme color sink**, so this is unguarded. The page docstring/comment claims
the theme is safe by autoescape ("Injected from config via Jinja render args ... An absent/empty var
never breaks the cascade") — that reasoning is wrong for the CSS context.

This is a real injection sink even though the LAN is the trust boundary: the `SEGUGIO_OVERLAY_*`
overrides are exactly the "brand a run without editing config" path (`app.py:398`), so a value can
arrive from an env var / per-event script, not only a hand-audited config file.

**Fix:** Validate the theme tokens at the config boundary against a CSS-color allowlist (hex,
`rgb()/rgba()/hsl()/hsla()`, or a named-color set) so a token containing `{};:/<>` or whitespace
beyond the function grammar is rejected fail-fast at load — mirroring how every other config field
is bounds-checked. Example (in `OverlayParams`):

```python
import re
_CSS_COLOR = re.compile(
    r"^(#[0-9A-Fa-f]{3,8}"
    r"|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)"
    r"|rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[01]?(\.\d+)?\s*\)"
    r"|hsl\([^)<>{};]*\)|hsla\([^)<>{};]*\)"
    r"|[A-Za-z]{1,30})$"
)

@field_validator("theme_accent", "theme_plate", "theme_text")
@classmethod
def _safe_css_color(cls, v: str) -> str:
    if v and not _CSS_COLOR.match(v.strip()):
        raise ValueError(f"theme color {v!r} is not a safe CSS color token")
    return v.strip()
```

Apply the same validation to the `SEGUGIO_OVERLAY_*` env path (or route those through the same
model). Add a regression test asserting `theme_accent="red; } body {...}"` is rejected (or escaped),
parallel to `test_overlay_event_name_is_autoescaped`.

## Warnings

### WR-01: `logo_path` `src` is attacker-influenceable and only HTML-escaped, enabling external resource load

**File:** `src/segugio/ui/templates/overlay.html:235`
**Issue:**
```html
<img id="logo-bug" src="{{ logo_path }}" alt="">
```
`logo_path` is a free-form, non-validated config/env string (`models.py:195`, `app.py:402`
`SEGUGIO_OVERLAY_LOGO`). Autoescape prevents attribute breakout, but it does **not** restrict the
URL scheme. A `logo_path` of `http://attacker/track.png` or a `javascript:`-style payload in older
CEF builds turns the overlay into a beacon / external fetch over the otherwise-isolated rig LAN,
and an arbitrary absolute path/URL is rendered with no allowlist. The page comments assert the
logo is "sourced from the injected path" as if that were safe; there is no scheme/path constraint.

**Fix:** Constrain `logo_path` to a relative path under the served `static/` root at the config
boundary (reject `://`, leading `/`, `..`), or serve it through a whitelisted route like the
`/preview/<cam>.jpg` precedent rather than emitting a raw `src`. At minimum add a `field_validator`
rejecting any value containing `:` (scheme) or `..` (traversal).

### WR-02: Persistently-failing `/overlay-json` fetch never marks the overlay stale (frozen "live" lie)

**File:** `src/segugio/ui/static/overlay-render.js:382-400`, `279-281`
**Issue:**
`isStale()` is driven exclusively by `lastGenAt`, which is updated only inside `poll()` when a gen
advances. After a normal run with at least one successful poll (`lastGen >= 0`), if the console
process dies and `fetch()` then throws **every** poll, `lastGenAt` freezes and `Date.now() -
lastGenAt` grows, so `isStale()` eventually returns true and the trailing `if (isStale())` block in
`poll()` degrades — that path is fine.

The real gap is the **rAF `tick()` loop interaction on a clean stop-then-die**: `applyPayload`
calls `stopTimer()` on `running=false`. If the source then dies while `running` is false, `tick()`
is not looping, so the only stale enforcement is `poll()`'s trailing check — which still works. BUT
consider a run that is `running=true` and the source dies: `tick()` runs `if (!running ||
isStale())` and calls `applyStale(isStale())` then sets `rafId = null` and returns. Once `rafId` is
null, `tick()` never runs again until `applyPayload` → `startTimer()` is called, which only happens
on a successful poll. So the dim is applied once by whichever of `tick()`/`poll()` fires first after
`STALE_MS` — acceptable. The concrete defect is narrower: **the timer text is frozen at its last
painted value while dimmed, but `paintTimer()` is never called again to reflect that the source is
dead** — the dim conveys staleness, so this is a WARNING not a BLOCKER. However, the watchdog has no
*upper* bound reset: `lastGenAt` is wall-clock `Date.now()`, so a backward OS clock adjustment
(NTP step) makes `Date.now() - lastGenAt` negative and `isStale()` returns false indefinitely,
suppressing the watchdog after a clock step.

**Fix:** Guard the staleness delta against a negative (clock-stepped-back) value, e.g.
`const age = Date.now() - lastGenAt; return lastGen >= 0 && age > STALE_MS;` → treat `age < 0` as
stale (clock moved back) or re-anchor `lastGenAt` when a negative age is observed. Consider a
monotonic source (`performance.now()`) for the watchdog clock since it is a pure local-elapsed
measure and does not need wall-clock alignment.

### WR-03: `freestyleDurationS` falls back to 120 on any falsy numeric, masking a 0/NaN config

**File:** `src/segugio/ui/static/overlay-render.js:258`
**Issue:**
```js
const freestyleDurationS = Number(cfg.freestyleDurationS) || 120;
```
`Number("") || 120`, `Number(undefined) /*NaN*/ || 120`, and `Number(0) || 120` all yield `120`.
The config model enforces `freestyle_duration_s > 0` server-side, so a legitimate 0 cannot arrive —
but the template emits `{{ freestyle_duration_s | default(120, true) }}` into a *numeric* JS context
(`overlay.html:248`). If that value is ever absent/empty the bootstrap emits `freestyleDurationS:`
followed by nothing → a **syntax error** in the inline script, not the graceful `|| 120` fallback
this line assumes. The `|| 120` here only rescues a structurally-valid-but-falsy number; it cannot
rescue the malformed-JS case, so the defense is partly illusory.

**Fix:** Make the template bootstrap robust to a missing value — emit a guaranteed integer, e.g.
`freestyleDurationS: {{ (freestyle_duration_s | default(120, true)) | int }}` and keep the JS
`Number(...) || 120` as belt-and-suspenders. Add a test asserting the bootstrap emits a parseable
integer when `freestyle_duration_s` is omitted from `overlay_cfg`.

### WR-04: Skew re-measured every poll causes a one-frame timer snap on clock drift

**File:** `src/segugio/ui/static/overlay-render.js:349-351`, `285-288`
**Issue:**
`applyPayload` recomputes `skew = p.server_now - Date.now()/1000` on **every** gen-advancing poll,
and `currentElapsed()` uses the latest `skew`. Between polls the rAF clock advances smoothly using
the *old* skew; the moment a new payload lands with even a few ms of measured drift, `skew` jumps
and the displayed elapsed snaps by that delta on the next `paintTimer()`. The comment claims this
avoids snapping ("count LOCALLY between polls ... NEVER raw"), and it does avoid the gross
cross-machine error, but it does **not** avoid a visible micro-snap on every poll when the two
clocks drift relative to each other (they always do). For a broadcast timer rendered at SS.hh
(agility, hundredths) this is a visible jitter on the hero clock the project value statement
prioritizes.

**Fix:** Smooth skew updates (e.g. low-pass / clamp the per-poll skew delta to a small bound) rather
than hard-replacing `skew` each poll, so the displayed clock converges without a per-poll step. At
minimum, only re-measure skew on a run-start edge (when the timer re-anchors anyway), not on every
score-only gen bump.

### WR-05: Score-change pulse misfires on the first running payload (identity/cells rebuild reads as "changed")

**File:** `src/segugio/ui/static/overlay-render.js:357-366`, `98-119`, `123-136`
**Issue:**
On the first gen that arrives with `running=true`, `renderOverlay` runs `renderCells`, which calls
`fillCell` for cells that do not yet exist — `fillCell` creates the node, sets `valueEl.textContent`
from empty to the value, and returns `changed = true`. So `res.scoreChanged` is true purely because
the cells were *built*, not because a score *value changed*. Combined with `nextRunning && !wasRunning`
the run-enter animation also fires, and then `if (res.scoreChanged && nextRunning) pulseOnce(...)`
fires a redundant pulse layered on top of the enter animation on the very first frame. The pulse is
meant to mark an in-run value *change* (D-04 trigger #1), not initial population.

**Fix:** Suppress the score-change pulse on the run-enter frame, e.g. only pulse when
`res.scoreChanged && nextRunning && wasRunning` (already running), or seed cell `textContent`
without counting the empty→value initial fill as a change. Add a behavior test that the first
running payload fires the enter animation but not a spurious value pulse.

## Info

### IN-01: Dead / mis-precedence `getElementById` fallback in `renderOverlay`

**File:** `src/segugio/ui/static/overlay-render.js:207`
**Issue:**
```js
const lowerThird = root.querySelector("#lower-third") || root.getElementById && root.getElementById("lower-third");
```
`||` and `&&` precedence parse this as `querySelector(...) || (getElementById && getElementById(...))`.
For the real `document` root, `querySelector` already returns the element so the fallback is never
reached; for any root without `querySelector` the first operand throws before the fallback can run.
The returned `lowerThird` is also never consumed — `createRenderer` independently grabs its own
`lowerThird` via `root.querySelector("#lower-third")` (line 260), and `applyPayload` ignores
`res.lowerThird`. Dead, confusing code.

**Fix:** Drop the `getElementById` fallback and the `lowerThird` return value from `renderOverlay`
entirely (it is unused), or if a fallback is genuinely wanted, parenthesize:
`root.querySelector("#lower-third") || (root.getElementById && root.getElementById("lower-third"))`.

### IN-02: `formatCountdown` shows "0:01" for the final sub-second before freezing on "Tempo"

**File:** `src/segugio/ui/static/overlay-render.js:235-241`
**Issue:**
`if (!(remainingS > 0)) return TEMPO_LITERAL;` then `Math.ceil(remainingS)`. For `0 <
remainingS <= 1` this renders `0:01`, so the clock displays "0:01" for the whole final second and
jumps straight to "Tempo" at the zero crossing — it never displays "0:00". This is a defensible
broadcast choice (ceil = "seconds remaining") but worth confirming against the intended look; a
viewer expecting a "0:00" beat will not see it.

**Fix:** If a "0:00" frame is desired, use `Math.floor` with a separate `remainingS <= 0` freeze, or
document the ceil choice in the SUMMARY. No code change required if the ceil behavior is intended.

### IN-03: Mismatched documentation — overlay.html claims renderer "rebuilds" cells; renderer updates in place

**File:** `src/segugio/ui/templates/overlay.html:125-128`, `src/segugio/ui/static/overlay-render.js:96-136`
**Issue:**
The template comment says the renderer "REBUILDS its children per discipline" and "rebuilds .cell
children", but `fillCell`/`renderCells` deliberately reuse existing nodes and only shrink the tail —
the whole point of the FOUC-avoidance design. The stale comment contradicts the implementation and
could mislead the Phase-12 iframe consumer.

**Fix:** Update the template comment to "updates cell text in place, shrinking the tail when the
discipline changes" to match `renderCells`.

### IN-04: `_OVERLAY_CFG_DEFAULTS` duplicates `OverlayParams` defaults with no single source of truth

**File:** `src/segugio/ui/app.py:88-95`, `src/segugio/config/models.py:191-201`
**Issue:**
The console-palette defaults (`#34D399` / `#14161a` / `#E6E9EF`, `freestyle_duration_s: 120`,
empty `event_name`/`logo_path`) are hardcoded in `app.py` AND in `OverlayParams`. The duplication
is intentional (the crash-isolation allowlist forbids importing the config model at module top —
correctly documented), but the two copies can silently drift: changing a default in `OverlayParams`
will not update the console fallback, and no test asserts the two dicts agree. The two test files
each pin their own copies of these hex values independently, so a drift would pass some tests and
fail none that cross-check.

**Fix:** Add a regression test that imports both and asserts
`OverlayParams().model_dump()` matches `_OVERLAY_CFG_DEFAULTS` key/value-wise (the test layer may
import the config model freely — only the module-top of `app.py` is constrained), so a future
default change to one side fails loudly.

---

_Reviewed: 2026-06-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
