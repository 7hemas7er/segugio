/* ============================================================================
   score-entry.js — the ONE shared score-entry COMPONENT (Plan 16-02, SCE-01..05).

   A re-mountable `mount(root, cfg)` factory that renders rich per-discipline
   fields from the server-injected active scoring profile, shows a LIVE advisory
   running total (non-authoritative), surfaces per-field validation errors on
   blur, and POSTs the RAW structured inputs as JSON to the authoritative
   POST /score route (Plan 01) — never a client-computed total. The publish
   result lands in a PERSISTENT banner.

   This SAME module is mounted on the dedicated /score-entry page now and the
   console <dialog> modal in Phase 17 — one renderer, two mounts, so drift is
   structurally impossible (the SCV-02 lesson applied to a form).

   SECURITY (T-16-07 / Pitfall 5): EVERY value reaches the DOM via textContent /
   createTextNode / createElementNS — there is NO innerHTML sink ANYWHERE in this
   file (the served-JS test forbids it outright). Even the static add/remove icons
   are built as SVG DOM nodes, not parsed from a markup string. A crafted <script>
   freestyle `nome` therefore renders inert text.

   AUTHORITY (T-16-08 / D-08): the advisory total (via window.SEGUGIO_SCORE_CALC)
   is feedback only; the component POSTs RAW inputs and the server recomputes —
   the advisory number can never become what airs.

   Pure client-side ES2020 (no build step, no imports). Dual-exported for tests.
   ============================================================================ */
(function () {
  "use strict";

  // --- STATIC icons built as SVG DOM (NOT innerHTML — the served-JS test forbids
  // any innerHTML sink outright, so even static markup is constructed node-by-node).
  // Tabler-style glyphs, offline, inline. Used for the add/remove-throw affordances.
  const SVG_NS = "http://www.w3.org/2000/svg";
  const ICON_PATHS = {
    plus: ["M12 5v14M5 12h14"],
    x: ["M18 6 6 18M6 6l12 12"],
  };

  // The Italian discipline labels (the Copywriting Contract). Options come from
  // cfg.disciplines (D-06), but the human label is fixed per discipline.
  const DISCIPLINE_LABELS = {
    disc_tf: "Disc — Toss & Fetch",
    disc_freestyle: "Disc — Freestyle",
    agility: "Agility",
  };

  // ---- small DOM helpers (textContent-only sinks; never innerHTML for data) ----

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        if (k === "class") node.className = attrs[k];
        else node.setAttribute(k, attrs[k]);
      }
    }
    // text ALWAYS via textContent (XSS-safe; T-16-07).
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function staticIcon(name) {
    // Build a static SVG glyph entirely via createElementNS — no innerHTML, no markup
    // string, no operator data. (The node-test guard: callers run inside mount(), which
    // is only reached with a real document.)
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("aria-hidden", "true");
    (ICON_PATHS[name] || []).forEach((d) => {
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  }

  function labelled(labelText, control) {
    const wrap = el("div");
    const lab = el("label", null, labelText);
    if (control.id) lab.setAttribute("for", control.id);
    wrap.appendChild(lab);
    wrap.appendChild(control);
    return wrap;
  }

  // ----------------------------------------------------------------------------
  // mount(root, cfg) — build the component into `root` from the injected cfg.
  //   cfg = { sport, disciplines: [...], profile: {...decimal strings...} }
  // Returns a small handle for tests / the P17 modal (re-mountable).
  // ----------------------------------------------------------------------------
  function mount(root, cfg) {
    if (!root) return null;
    cfg = cfg || {};
    const profile = cfg.profile || {};
    const disciplines = cfg.disciplines && cfg.disciplines.length ? cfg.disciplines : ["disc_tf"];
    const calc =
      (typeof window !== "undefined" && window.SEGUGIO_SCORE_CALC) ||
      (typeof SEGUGIO_SCORE_CALC !== "undefined" ? SEGUGIO_SCORE_CALC : null);

    // Clear any prior mount (re-mountable for the P17 modal) WITHOUT innerHTML.
    while (root.firstChild) root.removeChild(root.firstChild);

    // Reload-safe in-progress throw list for disc T&F (P17 / SCC-05 / D-02/D-03/D-04).
    // The persisted unit is the ONE flat best-5-of-N throw list (D-01) — no round entity,
    // no per-run/per-discipline keying (Deferred Idea). One fixed key, one atomic setItem.
    const DRAFT_KEY = "segugio.score.draft";
    const lsAvailable = typeof localStorage !== "undefined" && localStorage !== null;

    function saveDraft() {
      // Serialize the current throw list as the flat D-01 shape. Atomic per setItem; the
      // localStorage guard mirrors the existing `typeof document` guards for the node test.
      if (!lsAvailable) return;
      const flat = throwRows.map((r) => ({
        zone: r.zoneSel.value,
        midair: !!r.midair.checked,
        corridor: !!r.corridor.checked,
      }));
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(flat));
      } catch (_e) {
        /* quota/private-mode — a draft that cannot persist is a soft loss, never a crash */
      }
    }

    // In-session throw list for disc T&F (now reload-safe via the draft above).
    const throwRows = []; // [{ row, zoneSel, midair, corridor }]
    // The disc_tf list container + empty-state node, captured for the draft restore (D-03).
    let discTfList = null;
    let discTfEmpty = null;
    let active = disciplines[0];

    // --- 1. Discipline block (SCE-02 / D-06) -------------------------------
    const discBlock = el("div", { class: "discipline-block" });
    let disciplineControl;
    if (disciplines.length > 1) {
      const sel = el("select", { id: "discipline", name: "discipline" });
      disciplines.forEach((d) => {
        const opt = el("option", { value: d }, DISCIPLINE_LABELS[d] || d);
        sel.appendChild(opt);
      });
      sel.value = active;
      sel.addEventListener("change", () => {
        active = sel.value;
        showFields();
        clearErrors();
        recompute();
      });
      disciplineControl = sel;
      discBlock.appendChild(labelled("Disciplina", sel));
    } else {
      // A single discipline → a calm static label, not a 1-item dropdown.
      discBlock.appendChild(el("label", null, "Disciplina"));
      discBlock.appendChild(el("div", { class: "single-discipline" }, DISCIPLINE_LABELS[active] || active));
    }
    root.appendChild(discBlock);

    // --- field-set containers (.campi[data-disc]) show/hide toggle ----------
    const campiDiscTf = buildDiscTf();
    const campiFreestyle = buildFreestyle();
    const campiAgility = buildAgility();
    const campi = {
      disc_tf: campiDiscTf,
      disc_freestyle: campiFreestyle,
      agility: campiAgility,
    };
    disciplines.forEach((d) => {
      if (campi[d]) root.appendChild(campi[d]);
    });

    function showFields() {
      disciplines.forEach((d) => {
        if (campi[d]) campi[d].classList.toggle("hidden", d !== active);
      });
    }

    // --- 5. Live advisory running total (SCE-03 / D-02) --------------------
    const totalBlock = el("div", { class: "total" });
    totalBlock.appendChild(el("div", { class: "total-label" }, "Totale (provvisorio)"));
    const totalValue = el("div", { class: "total-value tabular" }, "—");
    totalBlock.appendChild(totalValue);
    totalBlock.appendChild(
      el(
        "div",
        { class: "total-caption" },
        "Calcolo live — non ufficiale. Il punteggio in onda è ricalcolato dal server."
      )
    );
    const bestCaption = el("div", { class: "total-caption best-caption" });
    totalBlock.appendChild(bestCaption);
    root.appendChild(totalBlock);

    // --- 7. Publish action (button ALWAYS enabled, D-04) ------------------
    const publishBlock = el("div", { class: "publish" });
    const publishBtn = el("button", { type: "button" }, "Manda in onda");
    publishBtn.addEventListener("click", submit);
    publishBlock.appendChild(publishBtn);
    root.appendChild(publishBlock);

    // The persistent banner lives OUTSIDE the root if the host provides #publish-banner,
    // else inside the component (re-mountable modal has no host banner).
    const banner =
      (typeof document !== "undefined" && document.getElementById("publish-banner")) ||
      (function () {
        const b = el("div", { id: "publish-banner" });
        root.appendChild(b);
        return b;
      })();

    showFields();
    recompute();
    restoreDraft();

    // ====================================================================
    // Reload-safe draft restore (P17 / SCC-05 / D-02/D-03) — NEVER-RAISE reader,
    // mirroring the autoMount cfg parse: a corrupt/absent/torn value → empty draft.
    // Replays each saved throw via addThrowRow (silent — no prompt), then recompute()
    // so the advisory best-5-of-N total matches pre-reload (no lost rows, no double-count).
    // ====================================================================
    function restoreDraft() {
      if (!lsAvailable || !discTfList || !discTfEmpty) return;
      let saved = null;
      try {
        saved = JSON.parse(localStorage.getItem(DRAFT_KEY));
      } catch (_e) {
        return; // torn/corrupt value → empty draft, never throws (D-02)
      }
      if (!Array.isArray(saved) || saved.length === 0) return;
      saved.forEach((t) => {
        const row = addThrowRow(discTfList, discTfEmpty);
        const entry = throwRows[throwRows.length - 1];
        if (entry && t) {
          if (t.zone !== undefined && t.zone !== null) entry.zoneSel.value = String(t.zone);
          entry.midair.checked = !!t.midair;
          entry.corridor.checked = !!t.corridor;
        }
      });
      recompute();
    }

    // ====================================================================
    // disc Toss & Fetch — repeatable throw list (D-01, the headline UX)
    // ====================================================================
    function buildDiscTf() {
      const wrap = el("div", { class: "campi", "data-disc": "disc_tf" });
      wrap.appendChild(el("legend", { class: "section-legend" }, "Lanci"));
      const list = el("div", { class: "throw-list" });
      wrap.appendChild(list);
      discTfList = list; // captured for the draft restore (D-03)

      const empty = el("div", { class: "empty-state" });
      empty.appendChild(el("div", { class: "empty-title" }, "Nessun lancio"));
      empty.appendChild(
        el("div", null, "Aggiungi il primo lancio per iniziare a calcolare il punteggio.")
      );
      wrap.appendChild(empty);
      discTfEmpty = empty; // captured for the draft restore (D-03)

      const addBtn = el("button", { type: "button", class: "add-throw" });
      addBtn.appendChild(staticIcon("plus"));
      addBtn.appendChild(el("span", null, " Aggiungi lancio"));
      addBtn.addEventListener("click", () => {
        addThrowRow(list, empty);
        recompute();
        saveDraft();
      });
      wrap.appendChild(addBtn);

      // A field-level error chip for the "throws" requirement (e.g. empty list).
      wrap.appendChild(el("div", { class: "field-error throws-error hidden" }));
      return wrap;
    }

    function addThrowRow(list, empty) {
      const row = el("div", { class: "throw-row" });

      const zoneSel = el("select", { class: "throw-zone" });
      zoneSel.appendChild(el("option", { value: "" }, "Zona…"));
      (profile.zones || []).forEach((z) => {
        // z = [band, pointsStr]; band is the selector value, points shown for context.
        const opt = el("option", { value: String(z[0]) }, "Zona " + z[0] + " (" + z[1] + ")");
        zoneSel.appendChild(opt);
      });

      const midair = el("input", { type: "checkbox", class: "throw-midair" });
      const corridor = el("input", { type: "checkbox", class: "throw-corridor" });

      const zoneCell = labelled("Zona", zoneSel);
      const midairCell = el("div", { class: "checkbox" });
      midairCell.appendChild(midair);
      midairCell.appendChild(el("span", null, "Al volo"));
      const corridorCell = el("div", { class: "checkbox" });
      corridorCell.appendChild(corridor);
      corridorCell.appendChild(el("span", null, "Corridoio"));

      const removeBtn = el("button", {
        type: "button",
        class: "throw-remove",
        "aria-label": "Rimuovi lancio",
      });
      removeBtn.appendChild(staticIcon("x"));
      removeBtn.addEventListener("click", () => {
        const idx = throwRows.findIndex((r) => r.row === row);
        if (idx >= 0) throwRows.splice(idx, 1);
        list.removeChild(row);
        empty.classList.toggle("hidden", throwRows.length > 0);
        recompute();
        saveDraft();
      });

      row.appendChild(zoneCell);
      row.appendChild(midairCell);
      row.appendChild(corridorCell);
      row.appendChild(removeBtn);

      // Live recompute + draft-save on any change; the zone is also validated on blur.
      [zoneSel, midair, corridor].forEach((c) =>
        c.addEventListener("input", () => {
          recompute();
          saveDraft();
        })
      );
      zoneSel.addEventListener("blur", () => validateOnBlur());

      list.appendChild(row);
      throwRows.push({ row: row, zoneSel: zoneSel, midair: midair, corridor: corridor });
      empty.classList.add("hidden");
      return row;
    }

    // ====================================================================
    // disc Freestyle — category number inputs + adjustment + free-text nome
    // ====================================================================
    function buildFreestyle() {
      const wrap = el("div", { class: "campi", "data-disc": "disc_freestyle" });
      wrap.appendChild(el("legend", { class: "section-legend" }, "Freestyle"));

      (profile.freestyle_cats || []).forEach((cat) => {
        // cat = [name, minStr, maxStr, incStr]
        const name = cat[0];
        const inp = el("input", {
          id: "fs-" + name,
          type: "text",
          inputmode: "decimal",
          "data-field": name,
          class: "fs-cat",
        });
        const cell = labelled(name, inp);
        cell.appendChild(el("div", { class: "field-error hidden", "data-error-for": name }));
        wrap.appendChild(cell);
        inp.addEventListener("input", recompute);
        inp.addEventListener("blur", validateOnBlur);
      });

      const adj = el("input", {
        id: "fs-adjustment",
        type: "text",
        inputmode: "decimal",
        "data-field": "adjustment",
        class: "fs-adjustment",
      });
      const adjCell = labelled("Aggiustamento", adj);
      adjCell.appendChild(el("div", { class: "field-error hidden", "data-error-for": "adjustment" }));
      wrap.appendChild(adjCell);
      adj.addEventListener("input", recompute);
      adj.addEventListener("blur", validateOnBlur);

      const nome = el("input", {
        id: "fs-nome",
        type: "text",
        "data-field": "nome",
        class: "fs-nome",
      });
      wrap.appendChild(labelled("Nome", nome));
      // Echo the (untrusted) name into a preview via textContent ONLY (XSS-safe).
      const nomeEcho = el("div", { class: "nome-echo hint" });
      wrap.appendChild(nomeEcho);
      nome.addEventListener("input", () => {
        nomeEcho.textContent = nome.value; // textContent in place — inert if it contains markup
      });

      wrap.appendChild(el("div", { class: "hint" }, "usa il punto (.) per i decimali"));
      return wrap;
    }

    // ====================================================================
    // agility — Tempo / SCT + course_faults|course_deductions + Eliminato
    // ====================================================================
    function buildAgility() {
      const wrap = el("div", { class: "campi", "data-disc": "agility" });
      wrap.appendChild(el("legend", { class: "section-legend" }, "Agility"));

      const tempo = el("input", {
        id: "ag-tempo",
        type: "text",
        inputmode: "decimal",
        placeholder: "mm:ss.cc",
        "data-field": "tempo",
        class: "ag-tempo",
      });
      const tempoCell = labelled("Tempo", tempo);
      tempoCell.appendChild(el("div", { class: "field-error hidden", "data-error-for": "tempo" }));
      wrap.appendChild(tempoCell);

      const sct = el("input", {
        id: "ag-sct",
        type: "text",
        inputmode: "decimal",
        placeholder: "mm:ss.cc",
        "data-field": "sct",
        class: "ag-sct",
      });
      const sctCell = labelled("SCT", sct);
      sctCell.appendChild(el("div", { class: "field-error hidden", "data-error-for": "sct" }));
      wrap.appendChild(sctCell);

      // The fault field NAME comes from the score_calc contract via agility_model (D-08 / Pitfall 4).
      const faultField =
        profile.agility_model === "deduct_from_100" ? "course_deductions" : "course_faults";
      const faultLabel = faultField === "course_deductions" ? "Penalità percorso" : "Falli percorso";
      const faults = el("input", {
        id: "ag-faults",
        type: "text",
        inputmode: "numeric",
        "data-field": faultField,
        class: "ag-faults",
      });
      const faultCell = labelled(faultLabel, faults);
      faultCell.appendChild(
        el("div", { class: "field-error hidden", "data-error-for": faultField })
      );
      wrap.appendChild(faultCell);

      const elim = el("input", {
        id: "ag-eliminated",
        type: "checkbox",
        "data-field": "eliminated",
        class: "ag-eliminated",
      });
      const elimCell = el("div", { class: "checkbox" });
      elimCell.appendChild(elim);
      elimCell.appendChild(el("span", null, "Eliminato"));
      wrap.appendChild(elimCell);

      [tempo, sct, faults].forEach((c) => {
        c.addEventListener("input", recompute);
        c.addEventListener("blur", validateOnBlur);
      });
      elim.addEventListener("input", recompute);

      wrap.appendChild(el("div", { class: "hint" }, "usa il punto (.) per i decimali"));
      return wrap;
    }

    // ====================================================================
    // RAW input collection — the wire shape POST /score validates (D-08).
    // Returns { discipline, ...rawFields } — NEVER a client-computed total.
    // ====================================================================
    function collectRaw() {
      const out = { discipline: active };
      if (active === "disc_tf") {
        out.throws = throwRows.map((r) => ({
          zone: r.zoneSel.value === "" ? null : Number(r.zoneSel.value),
          midair: r.midair.checked,
          corridor: r.corridor.checked,
        }));
      } else if (active === "disc_freestyle") {
        campiFreestyle.querySelectorAll("[data-field]").forEach((inp) => {
          out[inp.getAttribute("data-field")] = inp.value;
        });
      } else if (active === "agility") {
        campiAgility.querySelectorAll("[data-field]").forEach((inp) => {
          const field = inp.getAttribute("data-field");
          out[field] = inp.type === "checkbox" ? inp.checked : inp.value;
        });
      }
      return out;
    }

    // ====================================================================
    // recompute() — live advisory total IN PLACE via textContent (D-02).
    // ====================================================================
    function recompute() {
      if (!calc) return;
      const raw = collectRaw();
      let result;
      try {
        result = calc.compute(active, raw, profile);
      } catch (_e) {
        result = null;
      }
      let display = "—";
      if (result && result.totale !== undefined && result.totale !== null && result.totale !== "") {
        display = result.totale;
      }
      // textContent IN PLACE — never node rebuild (FOUC/flicker discipline, D-02).
      if (totalValue.textContent !== display) totalValue.textContent = display;

      // best-N caption: "Migliori 5 di {N} lanci" once N exceeds the cut.
      let bestText = "";
      if (active === "disc_tf" && profile.count_best_n) {
        const n = throwRows.length;
        if (n > profile.count_best_n) {
          bestText = "Migliori " + profile.count_best_n + " di " + n + " lanci";
        }
      }
      if (bestCaption.textContent !== bestText) bestCaption.textContent = bestText;
    }

    // ====================================================================
    // validation — advisory, on blur per field; re-run on submit (D-03/D-05a).
    // The client port is a PRE-FILTER; the server is the authority on a 400.
    // ====================================================================
    function clearErrors() {
      if (typeof document === "undefined") return;
      root.querySelectorAll(".field-error").forEach((chip) => {
        chip.textContent = "";
        chip.classList.add("hidden");
      });
    }

    function paintError(field, message) {
      // Map a {field, message} onto its chip via textContent (XSS-safe). throws[i].zone →
      // the per-row zone error is collapsed onto the list-level chip for simplicity in P16.
      let chip = null;
      if (field === "throws" || /^throws\[/.test(field)) {
        chip = campiDiscTf.querySelector(".throws-error");
      } else {
        chip = root.querySelector('[data-error-for="' + field + '"]');
      }
      if (!chip) return;
      chip.textContent = message;
      chip.classList.remove("hidden");
    }

    function validateOnBlur() {
      if (!calc) return [];
      clearErrors();
      const raw = collectRaw();
      let errors = [];
      try {
        errors = calc.validate(active, raw, profile) || [];
      } catch (_e) {
        errors = [];
      }
      errors.forEach((e) => paintError(e.field, e.message));
      return errors;
    }

    // ====================================================================
    // submit() — POST RAW JSON to the authoritative /score; persistent banner.
    // Button is ALWAYS enabled (D-04); the server is the real gate.
    // ====================================================================
    function submit() {
      // Re-validate on submit-attempt (advisory pre-filter) — but NEVER hard-block (D-04).
      validateOnBlur();
      const raw = collectRaw();
      setBanner("", "");
      fetch("/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(raw),
      })
        .then((resp) => {
          if (resp.ok) {
            // 2xx (204) → persistent success banner (stays until next action, D-05).
            setBanner("✓ In onda", "success");
            // Clear the draft ONLY on a successful publish (D-04). The 400 and .catch()
            // branches below intentionally KEEP it — nothing is lost on a rejected/failed POST.
            if (lsAvailable) {
              try {
                localStorage.removeItem(DRAFT_KEY);
              } catch (_e) {
                /* removal failure is harmless — the next 2xx clears it */
              }
            }
            return null;
          }
          // 400 → read the server's per-field errors (the AUTHORITATIVE source, D-05a).
          return resp.json().then(
            (data) => {
              clearErrors();
              const errs = (data && data.errors) || [];
              errs.forEach((e) => paintError(e.field, e.message));
              setBanner("Errore — punteggio precedente invariato", "error");
              return null;
            },
            () => {
              setBanner("Errore — punteggio precedente invariato", "error");
              return null;
            }
          );
        })
        .catch(() => {
          // Network/transport failure — the previous on-air score is likewise untouched.
          setBanner("Errore — punteggio precedente invariato", "error");
        });
    }

    function setBanner(text, kind) {
      banner.className = "banner" + (kind ? " " + kind : "");
      banner.textContent = text; // textContent — the server message echo is XSS-safe
    }

    return {
      root: root,
      collectRaw: collectRaw,
      recompute: recompute,
      validate: validateOnBlur,
      submit: submit,
      setDiscipline: function (d) {
        active = d;
        if (disciplineControl) disciplineControl.value = d;
        showFields();
        recompute();
      },
    };
  }

  // --- auto-mount on the dedicated page (guarded for the node behavior test) ---
  function autoMount() {
    if (typeof document === "undefined") return null;
    const el2 = document.getElementById("score-cfg");
    let cfg = {};
    if (el2) {
      try {
        cfg = JSON.parse(el2.textContent);
      } catch (_e) {
        cfg = {};
      }
    }
    return mount(document.getElementById("score-entry-root"), cfg);
  }

  const api = { mount };
  if (typeof window !== "undefined") window.SEGUGIO_SCORE_ENTRY = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", autoMount);
    } else {
      autoMount();
    }
  }
})();
