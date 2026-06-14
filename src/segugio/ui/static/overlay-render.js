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
    SCV_MAX_FIELD_LEN,
    DISCIPLINE_CELLS,
  };
  if (typeof window !== "undefined") window.SEGUGIO_OVERLAY = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
