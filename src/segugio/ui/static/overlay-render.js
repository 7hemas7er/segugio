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

  // Identity line (D-08 / BRD-02 / D-01): "{competitor} · {event}". Competitor is built
  // from the free-text identity fields for ALL disciplines: cane + " / " + conduttore when
  // both are present, otherwise whichever is present, falling back to the freestyle routine
  // `nome` (zero data-model change). The event half is STATIC page branding (baked into
  // #identity[data-event] by Jinja) — it is NOT read from /overlay-json. Empty competitor →
  // just the event; both empty → the line is hidden (#identity:empty { display: none } in
  // 11-02). The judges field is data-only and is deliberately NEVER read/rendered here (D-01).
  function renderIdentity(identityEl, fields) {
    if (!identityEl) return;
    const event = identityEl.getAttribute("data-event") || "";
    // Combine the sanitized identity values (scvGet already cleanField-sanitizes each), then
    // append via createTextNode below — never innerHTML/insertAdjacentHTML (Pitfall 4).
    const cane = scvGet(fields, "cane");
    const conduttore = scvGet(fields, "conduttore");
    let competitor;
    if (cane && conduttore) competitor = cane + " / " + conduttore;
    else if (cane) competitor = cane;
    else if (conduttore) competitor = conduttore;
    else competitor = scvGet(fields, "nome");
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
  // freeze-at-0/overtime + response-recency freshness watchdog + degrade + poll
  // loop (TMR-01/02/03/04, OVD-03 client half). All client-side; zero director
  // compute.
  // =========================================================================

  // Freshness constants. The watchdog keys on CONSOLE RESPONSE RECENCY (the last
  // successful /overlay-json poll), NOT on gen-age. `gen` is an edit/score counter
  // that advances ONLY on /run and /score writes (locked Phase 10 contract — there
  // is NO gen heartbeat), so it legitimately stays FLAT during a live run with no
  // new score; it MUST NOT be the liveness signal. A live console answering polls
  // is never stale even with a flat gen; a dead/unreachable console stops answering,
  // so the last-response timestamp stops advancing and the overlay goes stale.
  const PUBLISH_MS = 200; // ~5 fps publish cadence
  const STALE_MS = PUBLISH_MS * 3; // no successful poll within ~2-3x → stale (OVD-03)
  // Second degrade stage (D-04/D-05): a SUSTAINED no-response past this threshold is a
  // real console DEATH (not a transient WiFi hiccup) → fully HIDE the lower-third so no
  // frozen score airs from the OBS browser source. MUST stay > STALE_MS (a short stale
  // only dims; a long stale hides). Keyed on response-recency, NEVER gen-age (260615-tsi).
  const DEAD_MS = 3000; // ~3s full-hide threshold

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

    // Freshness watchdog state — response-recency. `everResponded` is the cold-start
    // guard: before the first successful poll the overlay is NOT stale (never degrade
    // the first paint). `lastResponseAt` advances on EVERY successful poll, so a live
    // console keeps the overlay fresh even when `gen` is flat.
    let lastResponseAt = Date.now();
    let everResponded = false;
    // `lastGen` still feeds the gen-advance RENDER gate (p.gen > lastGen) in poll()
    // — it gates re-rendering on an actual edit/score change, NOT liveness.
    let lastGen = -1;

    // Latest payload-derived timer inputs (re-measured each poll).
    let skew = 0; // server_now - Date.now()/1000, re-measured every poll (Pitfall 1)
    let startedAt = null; // run start on the console wall clock
    let running = false;
    let discipline = "disc_tf";
    let wasRunning = false;
    let rafId = null;
    let countdownPulsed = false; // ensure the end-of-countdown pulse fires exactly once
    let reqSeq = 0; // monotonic per-request poll counter — the CEF cache-buster nonce

    // isStale() — response-recency liveness. TRUE once the console HAD answered a
    // poll and then stopped answering for longer than STALE_MS; a COLD load (before
    // any successful poll, everResponded === false) is NOT stale. A live console
    // answering polls is never stale even with a flat gen (no new score); a dead or
    // unreachable console stops answering → lastResponseAt stalls → stale after
    // STALE_MS (OVD-03 / UAT item 3 degrade preserved).
    function isStale() {
      return everResponded && Date.now() - lastResponseAt > STALE_MS;
    }

    // isDead() — second-stage liveness, IDENTICAL structure to isStale() but at the
    // longer DEAD_MS threshold. Response-recency keyed (everResponded && now -
    // lastResponseAt > DEAD_MS), NEVER gen-age: `gen` is flat during a live idle run,
    // so keying on gen-age would false-HIDE a live overlay (the 260615-tsi bug — far
    // worse here than the dim-only stale stage). A live console answering polls is
    // never dead even with a flat gen; only a console that STOPS answering past
    // DEAD_MS is dead → fully hide the lower-third (D-04/D-05).
    function isDead() {
      return everResponded && Date.now() - lastResponseAt > DEAD_MS;
    }

    // Full-hide on death: remove the live/stale states and reuse the EXISTING exit
    // primitive (animateRunEdge's `is-exiting` → @keyframes exit → opacity:0, forwards)
    // so the plate slides out and STAYS hidden — no new keyframe/animation (D-04).
    function applyDead() {
      if (!lowerThird) return;
      lowerThird.classList.remove("is-live");
      lowerThird.classList.remove("is-stale");
      retrigger(lowerThird, "is-exiting");
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
        // Two-stage degrade: a DEATH (past DEAD_MS) fully HIDES (is-exiting); a SHORT
        // stale (past STALE_MS, under DEAD_MS) only dims (is-stale). isDead() implies
        // isStale(), so check dead first.
        //
        // WR-03 NOTE: the isDead() branch here is BELT-AND-SUSPENDERS and normally never
        // self-fires in production. The rAF loop is armed only while running && !isStale(),
        // so on the FIRST tick where the source turns stale this block runs, sets rafId=null
        // and stops the loop — long before DEAD_MS (3s) can elapse. The authoritative dead
        // escalation is owned by poll() (the always-on setInterval), which keeps observing
        // after the loop self-stops. tick() reaches isDead() only in the rare case where a
        // single frame straddles both thresholds (e.g. a multi-second main-thread stall).
        if (isDead()) applyDead();
        else applyStale(isStale());
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

      // DEAD_MS recovery re-show (CR-01): applyDead() hid the plate via is-exiting, but
      // the run-START edge above only fires on running false→true. A console that DIED
      // mid-run (>DEAD_MS) and then RECOVERS sends running:true while wasRunning was
      // already true (true→true), so animateRunEdge takes NEITHER branch and the plate
      // would stay hidden (opacity:0) on air for the rest of the run. When a live payload
      // is consumed while the plate is still in the dead/is-exiting hidden state, mirror
      // the enter edge: clear is-exiting and restore the shown (is-live + is-entering)
      // state so the overlay reappears once the console is healthy again. This is keyed
      // purely on the CURRENT hidden class state, NOT on gen-age (260615-tsi stays out).
      if (nextRunning && lowerThird && lowerThird.classList.contains("is-exiting")) {
        lowerThird.classList.remove("is-exiting");
        retrigger(lowerThird, "is-entering");
        lowerThird.classList.add("is-live");
      }

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
    //
    // LIVENESS = the console answering this poll (response recency), NOT a gen bump.
    // EVERY successful response stamps lastResponseAt/everResponded BEFORE the gen
    // gate, so a live console with a flat `gen` (no new score) is never stale and the
    // run timer keeps counting. The gen-advance gate p.gen > lastGen only gates the
    // DOM RE-RENDER (an actual edit/score change) — ?t= is purely a cache-buster the
    // server ignores. A fetch/json error COASTS — it does NOT update lastResponseAt,
    // so a real console outage stalls the response clock and the watchdog degrades.
    async function poll() {
      try {
        const r = await fetch("/overlay-json?t=" + (++reqSeq), { cache: "no-store" });
        const p = await r.json();
        // Console answered → liveness refreshed, regardless of whether gen advanced.
        lastResponseAt = Date.now();
        everResponded = true;
        if (p.gen > lastGen) {
          // gen-strictly-advances gate → re-render on an actual edit/score change.
          lastGen = p.gen;
          applyPayload(p);
        }
      } catch (e) {
        /* coast — a poll error never breaks the page; lastResponseAt is NOT updated,
           so the watchdog degrades once the console stays unreachable past STALE_MS */
      }
      // Even with no gen advance, keep the timer honest: stop + degrade if stale.
      // Two-stage: a sustained no-response past DEAD_MS is a console DEATH → fully HIDE
      // (is-exiting) so no frozen score airs; a SHORT stale only dims (is-stale). isDead()
      // implies isStale(), so check dead first; both stop the rAF timer.
      if (isDead()) {
        stopTimer();
        applyDead();
      } else if (isStale()) {
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

    return { start, stop, applyPayload, isStale, isDead, currentElapsed, paintTimer, _state: () => ({ lastGen, lastResponseAt, everResponded, skew, running }) };
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
    DEAD_MS,
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
