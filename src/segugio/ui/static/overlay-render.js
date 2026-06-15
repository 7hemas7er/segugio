/* ============================================================================
   Segugio shared overlay renderer (plan 11-03) — the ONE score-to-DOM renderer
   that fills the 11-02 lower-third skeleton (overlay.html). Pure client-side
   ES2020: no build step, no imports, no package install, zero director compute.

   Responsibilities:
     1. SANITIZE MIRROR — cleanField/scvGet are byte-exact PORTS of the
        console.html `gsd:scv01-mirror` block, which itself mirrors Python
        segugio.ui.score_render._clean / _get (keep U+0020, strip control chars,
        trim, cap 64, first-present alias). EVERY operator value is written into
        the DOM with `node.textContent = cleanField(v)` — NEVER innerHTML. The
        plain-text clean alone is NOT the HTML-context escape; textContent is the
        HIGH-severity HTML-injection mitigation (T-11-03-01).
     2. PER-DISCIPLINE DOM — reproduce render_overlay_text's field selection in
        DOM cells (disc_tf: prese/zona/totale; disc_freestyle: nome/timer;
        agility: tempo / sct(SCT alias) / faults), updating text IN PLACE on the
        existing cell nodes (FOUC/flicker avoidance — never rebuild on a value
        change).
     3. IDENTITY LINE (D-08 / BRD-02) — competitor from verbatim `nome` for ALL
        disciplines, joined with the STATIC event branding baked into the page
        (read from #identity[data-event]); the event is NOT read from
        /overlay-json. Empty nome → just the event; both empty → line hidden.
     4. EVENT-ONLY ANIMATIONS (OVL-04) — enter on the run-start edge, exit on the
        run-stop edge, a single pulse on a score-VALUE change and one pulse at the
        end-of-countdown. No perpetual motion; the keyframes/classes live in
        11-02 (.is-entering / .is-exiting / .pulse-once / .is-live / .is-stale).
     5. OFFSET-CANCELLATION TIMER + FRESHNESS WATCHDOG + POLL LOOP — see Task-2
        block below (TMR-01/02/03/04, OVD-03 client half).
   ============================================================================ */
(function () {
  "use strict";

  // ===== gsd:scv01-mirror:start =====
  // BYTE-EXACT with segugio.ui.score_render (ported verbatim from console.html
  // lines 346-389). cleanField mirrors Python `_clean`; scvGet mirrors `_get`'s
  // first-present alias lookup. Pure JS — never calls the orchestrator.
  const SCV_MAX_FIELD_LEN = 64; // mirrors _MAX_FIELD_LEN
  // Drop chars that are NOT Python-`isprintable` (control Cc, format Cf,
  // surrogate/private/unassigned Cs/Co/Cn, line/para/space separators Zl/Zp/Zs)
  // — EXCEPT the ASCII space U+0020, which Python keeps explicitly (`ch == " "`).
  // JS analogue of `ch == " " or (ch.isprintable() and ch not in "\r\n")`.
  const SCV_NONPRINT = /[^\S ]|[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}\p{Zs}]/gu;
  function cleanField(value) {
    let text = value === null || value === undefined ? "" : String(value);
    // Remove every non-printable / CR-LF / non-space-separator char (keep U+0020).
    text = text.replace(SCV_NONPRINT, m => (m === " " ? " " : ""));
    text = text.trim(); // mirrors `.strip()`
    if (text.length > SCV_MAX_FIELD_LEN) text = text.slice(0, SCV_MAX_FIELD_LEN); // cap 64
    return text;
  }
  // First-present-key fetch, sanitized (mirrors `_get`): the operator may post
  // any of the aliases (e.g. sct / SCT).
  function scvGet(fields, ...keys) {
    for (const key of keys) {
      if (
        Object.prototype.hasOwnProperty.call(fields, key) &&
        fields[key] !== null &&
        fields[key] !== undefined &&
        fields[key] !== ""
      ) {
        return cleanField(fields[key]);
      }
    }
    return "";
  }
  // ===== gsd:scv01-mirror:end =====

  // --- per-discipline cell layout (mirrors render_overlay_text field selection) ---
  // Each entry: the timer is the BIG leading clock (handled separately in Task 2);
  // `cells` are the per-discipline score cells (label over value). The SCT cell for
  // agility uses the scvGet(fields, "sct", "SCT") alias pair byte-exact with
  // render_overlay_text / _get. tempo/faults are display-only operator values.
  // NOTE: for agility the live elapsed timer is driven by the rAF clock (Task 2);
  // these `cells` carry only the static reference values typed by the operator
  // (e.g. SCT, faults) — no verdict / no color shift (SCR-04 / D-05).
  const DISCIPLINE_CELLS = {
    disc_tf: [
      { label: "Prese", keys: ["prese"] },
      { label: "Zona", keys: ["zona"] },
      { label: "Totale", keys: ["totale"] },
    ],
    disc_freestyle: [
      // freestyle: name → identity line; `timer` is the operator-typed routine
      // timer value (display-only cell). The live countdown clock is #timer (Task 2).
      { label: "Timer", keys: ["timer"] },
    ],
    agility: [
      // SCT shown as a STATIC reference cell beside the live #timer — sct/SCT alias,
      // no verdict, no color interpretation (D-05 / SCR-04). faults verbatim.
      { label: "SCT", keys: ["sct", "SCT"] },
      { label: "Faults", keys: ["faults"] },
    ],
  };

  // Build/refresh one .cell node (label over value), reusing the existing node so a
  // value change updates text IN PLACE (FOUC/flicker avoidance) and so a score-value
  // change is detectable (returns true when the rendered value actually changed).
  function fillCell(container, idx, label, value) {
    let cell = container.children[idx];
    if (!cell) {
      cell = document.createElement("div");
      cell.className = "cell";
      const labelEl = document.createElement("div");
      labelEl.className = "cell-label";
      const valueEl = document.createElement("div");
      valueEl.className = "cell-value";
      cell.appendChild(labelEl);
      cell.appendChild(valueEl);
      container.appendChild(cell);
    }
    const labelEl = cell.querySelector(".cell-label");
    const valueEl = cell.querySelector(".cell-value");
    // SECURITY: operator value written via textContent ONLY (T-11-03-01).
    if (labelEl.textContent !== label) labelEl.textContent = label;
    const clean = cleanField(value);
    const changed = valueEl.textContent !== clean;
    if (changed) valueEl.textContent = clean; // textContent in place, never innerHTML / node rebuild
    return changed;
  }

  // Render the per-discipline score cells. Returns true when ANY rendered value
  // changed (drives the single score-change pulse, D-04 trigger #1).
  function renderCells(container, discipline, fields) {
    const spec = DISCIPLINE_CELLS[discipline] || [];
    let anyChanged = false;
    spec.forEach((cellSpec, idx) => {
      const value = scvGet(fields, ...cellSpec.keys);
      if (fillCell(container, idx, cellSpec.label, value)) anyChanged = true;
    });
    // Drop any leftover cells from a prior (different) discipline — update in place,
    // shrink the tail only (never a full rebuild of surviving cells).
    while (container.children.length > spec.length) {
      container.removeChild(container.lastChild);
    }
    return anyChanged;
  }

  // Identity line (D-08 / BRD-02): "{competitor} · {event}". Competitor = verbatim
  // `nome` from the free fields dict for ALL disciplines (zero data-model change).
  // The event half is STATIC page branding (baked into #identity[data-event] by
  // Jinja) — it is NOT read from /overlay-json. Empty competitor → just the event;
  // both empty → the line is hidden (#identity:empty { display: none } in 11-02).
  function renderIdentity(identityEl, fields) {
    if (!identityEl) return;
    const event = identityEl.getAttribute("data-event") || "";
    const competitor = scvGet(fields, "nome");
    // Rebuild the small identity line with textContent-only nodes (a <span class="sep">
    // separator between the two halves). No innerHTML — every value is textContent.
    while (identityEl.firstChild) identityEl.removeChild(identityEl.firstChild);
    if (competitor && event) {
      identityEl.appendChild(document.createTextNode(competitor));
      const sep = document.createElement("span");
      sep.className = "sep";
      sep.textContent = "·";
      identityEl.appendChild(sep);
      identityEl.appendChild(document.createTextNode(event));
    } else if (competitor) {
      identityEl.appendChild(document.createTextNode(competitor));
    } else if (event) {
      identityEl.appendChild(document.createTextNode(event));
    }
    // both empty → identityEl left empty → :empty CSS hides it.
  }

  // --- event-only animation triggers (OVL-04 / D-04) ---
  // Re-trigger a one-shot class by removing it, forcing a reflow, then re-adding —
  // so a repeat pulse plays even when the class is already present. The keyframes /
  // classes themselves live in 11-02 (overlay.html). NO setInterval visual loop and
  // NO perpetual animation is driven here (the run timer is a textContent update).
  function retrigger(el, cls) {
    if (!el) return;
    el.classList.remove(cls);
    // Force reflow so the browser restarts the animation on re-add.
    void el.offsetWidth;
    el.classList.add(cls);
  }

  // Enter on the run-start edge (running false→true or the first running payload);
  // exit on the run-stop edge (true→false). is-live is the steady-shown state.
  function animateRunEdge(lowerThird, wasRunning, isRunning) {
    if (!lowerThird) return;
    if (isRunning && !wasRunning) {
      lowerThird.classList.remove("is-exiting");
      retrigger(lowerThird, "is-entering");
      lowerThird.classList.add("is-live");
    } else if (!isRunning && wasRunning) {
      lowerThird.classList.remove("is-entering");
      lowerThird.classList.remove("is-live");
      retrigger(lowerThird, "is-exiting");
    }
  }

  // A single pulse on a score-value change (trigger #1) OR at end-of-countdown
  // (trigger #2, fired from the timer). One shared primitive (.pulse-once, D-04).
  function pulseOnce(lowerThird) {
    retrigger(lowerThird, "pulse-once");
  }

  // -------------------------------------------------------------------------
  // DOM-render entry: fill the 11-02 contract from one /overlay-json payload.
  // Pure render (no timer/poll here — Task 2 owns the clock + poll loop). Returns
  // whether a score value changed (so the caller can fire the score-change pulse).
  // -------------------------------------------------------------------------
  function renderOverlay(root, payload) {
    const fields = (payload && payload.fields) || {};
    const discipline = (payload && payload.discipline) || "disc_tf";
    const lowerThird = root.querySelector("#lower-third") || root.getElementById && root.getElementById("lower-third");
    const identityEl = root.querySelector("#identity");
    const cellsEl = root.querySelector("#cells");
    renderIdentity(identityEl, fields);
    const scoreChanged = cellsEl ? renderCells(cellsEl, discipline, fields) : false;
    return { scoreChanged, lowerThird };
  }

  // =========================================================================
  // TASK 2 — offset-cancellation timer + per-discipline direction/format +
  // freeze-at-0/overtime + gen-age freshness watchdog + degrade + poll loop
  // (TMR-01/02/03/04, OVD-03 client half). All client-side; zero director compute.
  // =========================================================================

  // Freshness constants — copied VERBATIM from console.html (lines 619-624). The
  // gen-age watchdog + cold-start guard are PORTS of the v1.1 freshness watchdog.
  const PUBLISH_MS = 200; // ~5 fps publish cadence
  const STALE_MS = PUBLISH_MS * 3; // gen not advancing within ~2-3x → stale (OVD-03)

  // The freeze-at-0 literal shown when a countdown reaches 0 (TMR-03 / D-04).
  const TEMPO_LITERAL = "Tempo";
  // Toss & Fetch counts DOWN from 60s (TMR-02). Freestyle counts down from the
  // injected static freestyle_duration_s (window.OVERLAY_CFG.freestyleDurationS).
  const DISC_TF_COUNTDOWN_S = 60;

  // --- per-discipline timer formatting (D-03) ---
  // Countdown disciplines (disc_tf / disc_freestyle) render remaining as M:SS whole
  // seconds and FREEZE at 0 showing the literal "Tempo" — never going negative.
  function formatCountdown(remainingS) {
    if (!(remainingS > 0)) return TEMPO_LITERAL; // clamp at 0 → freeze on Tempo (also NaN-safe)
    const total = Math.ceil(remainingS); // show whole seconds remaining
    const m = Math.floor(total / 60);
    const s = total % 60;
    return m + ":" + String(s).padStart(2, "0");
  }
  // Agility counts UP in SS.hh hundredths and CONTINUES past the operator-typed SCT
  // into overtime (D-05 / TMR-03) — plain count-up, no color/verdict interpretation.
  function formatAgility(elapsedS) {
    const e = elapsedS > 0 ? elapsedS : 0;
    const whole = Math.floor(e);
    const hundredths = Math.floor((e - whole) * 100);
    return whole + "." + String(hundredths).padStart(2, "0");
  }

  // -------------------------------------------------------------------------
  // The renderer instance: owns the timer state, the watchdog, and the poll loop.
  // mount(root) wires it to the live DOM + bootstraps polling; the pure pieces above
  // are reused so tests can drive them in isolation (node behavior test).
  // -------------------------------------------------------------------------
  function createRenderer(root, cfg) {
    cfg = cfg || {};
    const freestyleDurationS = Number(cfg.freestyleDurationS) || 120;

    const lowerThird = root.querySelector("#lower-third");
    const timerEl = root.querySelector("#timer");

    // Freshness watchdog state — WR-02 cold-start: lastGen<0 is NOT stale.
    let lastGen = -1;
    let lastGenAt = Date.now();

    // Latest payload-derived timer inputs (re-measured each poll).
    let skew = 0; // server_now - Date.now()/1000, re-measured every poll (Pitfall 1)
    let startedAt = null; // run start on the console wall clock
    let running = false;
    let discipline = "disc_tf";
    let wasRunning = false;
    let rafId = null;
    let countdownPulsed = false; // ensure the end-of-countdown pulse fires exactly once
    let reqSeq = 0; // monotonic per-request poll counter — the CEF cache-buster nonce

    // isStale() — VERBATIM from console.html (lines 738-740). PRIMARY gen-age signal:
    // TRUE once a gen WAS advancing and then stalled past STALE_MS; a COLD load
    // (lastGen < 0) is NOT stale (never degrade the first paint).
    function isStale() {
      return lastGen >= 0 && Date.now() - lastGenAt > STALE_MS;
    }

    // Offset-cancellation elapsed (ARCHITECTURE (c) / Pitfall 1): count LOCALLY
    // between polls, re-measuring skew each poll — NEVER raw Date.now()-started_at.
    function currentElapsed() {
      if (startedAt === null || startedAt === undefined) return 0;
      return Date.now() / 1000 + skew - startedAt;
    }

    // Write the live timer cell IN PLACE (never node-rebuild — FOUC/flicker).
    function paintTimer() {
      if (!timerEl) return;
      const elapsed = currentElapsed();
      let text;
      if (discipline === "agility") {
        // count UP, continue past SCT into overtime (no freeze, no verdict).
        text = formatAgility(elapsed);
      } else {
        // disc_tf / disc_freestyle count DOWN and freeze at 0 on "Tempo".
        const total = discipline === "disc_freestyle" ? freestyleDurationS : DISC_TF_COUNTDOWN_S;
        const remaining = total - elapsed;
        text = formatCountdown(remaining);
        // ONE pulse at the 0 crossing (D-04 trigger #2), then freeze.
        if (remaining <= 0 && !countdownPulsed) {
          countdownPulsed = true;
          pulseOnce(lowerThird);
        }
      }
      if (timerEl.textContent !== text) timerEl.textContent = text; // textContent in place
    }

    // The rAF clock — advances the displayed elapsed locally between polls so it
    // never SNAPS. STOPPED on run-stop and on stale (a frozen-but-ticking timer is
    // the worst broadcast failure — Pitfall 4). Re-anchored cleanly on a fresh gen.
    function tick() {
      // Stop conditions: not running, or stale data (degrade). Freeze the displayed
      // value — do NOT free-run forever past a dead source.
      if (!running || isStale()) {
        applyStale(isStale());
        rafId = null; // stop the loop; restarted by startTimer() on a fresh running gen
        return;
      }
      paintTimer();
      rafId = requestAnimationFrame(tick);
    }

    function startTimer() {
      if (rafId === null) rafId = requestAnimationFrame(tick);
    }
    function stopTimer() {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    // OVD-03 degrade: a stale source dims the lower-third via the 11-02 .is-stale
    // class so a frozen overlay reads as "not live" rather than a confident lie.
    function applyStale(stale) {
      if (!lowerThird) return;
      if (stale) lowerThird.classList.add("is-stale");
      else lowerThird.classList.remove("is-stale");
    }

    // Consume one /overlay-json payload: re-measure skew, render the DOM cells +
    // identity, fire the score-change pulse, drive the run-edge animation, and
    // (re)anchor the rAF timer.
    function applyPayload(p) {
      // Re-measure skew EVERY poll (offset-cancellation — Pitfall 1).
      if (typeof p.server_now === "number") {
        skew = p.server_now - Date.now() / 1000;
      }
      startedAt = p.started_at;
      discipline = p.discipline || "disc_tf";
      const nextRunning = !!p.running;

      // DOM render (Task 1 pieces) — returns whether a score value changed.
      const res = renderOverlay(root, p);

      // Run-edge animation (enter/exit). Reset the once-per-run countdown pulse on a
      // fresh run start so the next end-of-countdown pulses again.
      if (nextRunning && !wasRunning) countdownPulsed = false;
      animateRunEdge(lowerThird, wasRunning, nextRunning);

      // Single pulse on a score-VALUE change (D-04 trigger #1) — only while shown.
      if (res.scoreChanged && nextRunning) pulseOnce(lowerThird);

      running = nextRunning;
      wasRunning = nextRunning;

      applyStale(false); // a fresh gen clears any prior degrade
      if (running) startTimer();
      else {
        stopTimer();
        paintTimer(); // freeze the displayed value at the stop point
      }
    }

    // Poll /overlay-json with a ?t=<++reqSeq> nonce that is UNIQUE PER REQUEST
    // (load-bearing in CEF — Pitfall 2): OBS's embedded Chromium browser source
    // ignores Cache-Control: no-store and caches by URL, so a per-gen ?t= repeats
    // the same URL between gen advances and CEF serves a STALE cached body — masking
    // the next gen bump and stalling the overlay (the live-stall bug). A per-request
    // counter makes every poll URL distinct so CEF can never hide a gen advance.
    // The gen-advance gate stays p.gen > lastGen below — ?t= is purely a cache-buster
    // the server ignores, NOT the render gate. A fetch error COASTS — never throws out
    // of the loop; the watchdog will degrade on its own once stale.
    async function poll() {
      try {
        const r = await fetch("/overlay-json?t=" + (++reqSeq), { cache: "no-store" });
        const p = await r.json();
        if (p.gen > lastGen) {
          // gen-strictly-advances gate
          lastGen = p.gen;
          lastGenAt = Date.now();
          applyPayload(p);
        }
      } catch (e) {
        /* coast — a poll error never breaks the page; the watchdog handles stale */
      }
      // Even with no gen advance, keep the timer honest: stop + degrade if stale.
      if (isStale()) {
        stopTimer();
        applyStale(true);
      }
    }

    let pollHandle = null;
    function start() {
      poll(); // immediate first paint attempt
      pollHandle = setInterval(poll, PUBLISH_MS); // publish cadence — NOT 60fps (DoS guard)
    }
    function stop() {
      if (pollHandle !== null) {
        clearInterval(pollHandle);
        pollHandle = null;
      }
      stopTimer();
    }

    return { start, stop, applyPayload, isStale, currentElapsed, paintTimer, _state: () => ({ lastGen, lastGenAt, skew, running }) };
  }

  // Auto-mount on the document when loaded as a page script (the 11-02 bootstrap
  // references window.OVERLAY_CFG). Guarded so the node behavior test (which imports
  // the module without a DOM) does not try to touch document.
  function autoMount() {
    if (typeof document === "undefined") return null;
    const cfg = (typeof window !== "undefined" && window.OVERLAY_CFG) || {};
    const renderer = createRenderer(document, cfg);
    renderer.start();
    return renderer;
  }

  // Export the pure render primitives for the timer/poll layer and for tests
  // (node executes this file and reads SEGUGIO_OVERLAY). No global leakage beyond
  // this single namespace object.
  const api = {
    cleanField,
    scvGet,
    renderOverlay,
    renderCells,
    renderIdentity,
    animateRunEdge,
    pulseOnce,
    formatCountdown,
    formatAgility,
    createRenderer,
    PUBLISH_MS,
    STALE_MS,
    SCV_MAX_FIELD_LEN,
    DISCIPLINE_CELLS,
  };
  if (typeof window !== "undefined") window.SEGUGIO_OVERLAY = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  // Boot the live renderer when loaded as a page script (skipped under node/tests:
  // autoMount no-ops without a document). Defer until the DOM contract exists.
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", autoMount);
    } else {
      autoMount();
    }
  }
})();
