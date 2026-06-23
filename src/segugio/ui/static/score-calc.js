/* ============================================================================
   score-calc.js — ADVISORY client port of segugio.ui.score_calc.compute/validate.

   This is the live running-total UX brain. It is ADVISORY ONLY: the client POSTs
   RAW inputs, and ONLY the Python server (score_calc.compute) decides what airs
   (Pitfall 2 / double source of truth / D-09). This port exists so the operator
   sees an immediate total while typing — it must NEVER become a second authority.

   The node-vs-Python drift-guard (tests/test_ui_score_calc_js.py) pins this port
   BYTE-EXACT against score_calc.compute/validate across every discipline + edge
   case (best-N, 0.5 bonus, CR-01 flags, freestyle cap, agility ceil/elimination).

   Decimal-equivalence is the hard requirement: a Number(a)+Number(b) total would
   drift (0.1+0.2). All total arithmetic goes through the fixed-scale Dec helper
   below (coefficient BigInt + exponent), mirroring Python's decimal.Decimal +
   its verbatim __str__ — so "18.0", "30.00", "40" come out byte-identical.

   Pure client-side ES2020 (no build step, no imports). Dual-exported for tests.
   ============================================================================ */
(function () {
  "use strict";

  // ===== gsd:score-calc-mirror:start =====
  // BYTE-EXACT with segugio.ui.score_calc.compute/validate. Decimal-equivalence via a
  // coefficient(BigInt)+exponent helper — NEVER Number float math (Pitfall 1 / D-09).

  // --- minimal Decimal: coefficient (BigInt) + exponent (int) ---------------
  // Mirrors decimal.Decimal for the OPS this scorer uses: parse, add, sub, min,
  // quantize(ROUND_HALF_UP), to-integral(ROUND_CEILING), and a __str__ that matches
  // Python's fixed-point output for exponent <= 0 (every scoring value qualifies).
  function Dec(coef, exp, sign) {
    // coef is a NON-negative BigInt magnitude; sign is 1 or -1; exp is an int.
    this.coef = coef; // BigInt magnitude
    this.exp = exp;   // base-10 exponent (digits = coef * 10^exp)
    this.sign = sign; // 1 or -1
  }

  function _decFromString(text) {
    // Parse a clean decimal string ("4", "0.5", "-1.50", "10.00") → Dec, preserving scale.
    // Returns null on a non-numeric string (the caller turns that into a per-field error).
    if (text === null || text === undefined) return null;
    let s = String(text).trim();
    if (s === "") return null;
    let sign = 1;
    if (s[0] === "+") s = s.slice(1);
    else if (s[0] === "-") {
      sign = -1;
      s = s.slice(1);
    }
    if (s === "" || !/^\d*(?:\.\d*)?$/.test(s) || s === ".") return null;
    let intPart, fracPart;
    const dot = s.indexOf(".");
    if (dot === -1) {
      intPart = s;
      fracPart = "";
    } else {
      intPart = s.slice(0, dot);
      fracPart = s.slice(dot + 1);
    }
    if (intPart === "" && fracPart === "") return null;
    const digits = (intPart + fracPart).replace(/^0+(?=\d)/, ""); // keep at least one digit
    const coef = BigInt(digits === "" ? "0" : digits);
    const exp = -fracPart.length;
    return new Dec(coef, exp, sign);
  }

  function _decFromInt(n) {
    const bi = BigInt(n);
    return new Dec(bi < 0n ? -bi : bi, 0, bi < 0n ? -1 : 1);
  }

  const _ZERO = function () {
    return new Dec(0n, 0, 1);
  };

  function _signedCoef(d) {
    return d.sign < 0 ? -d.coef : d.coef;
  }

  function _align(a, b) {
    // Scale both coefficients to the LOWER (more negative) exponent; return {ca, cb, exp}.
    const exp = a.exp < b.exp ? a.exp : b.exp;
    const ca = _signedCoef(a) * 10n ** BigInt(a.exp - exp);
    const cb = _signedCoef(b) * 10n ** BigInt(b.exp - exp);
    return { ca: ca, cb: cb, exp: exp };
  }

  function _fromSigned(signedCoef, exp) {
    const sign = signedCoef < 0n ? -1 : 1;
    const mag = signedCoef < 0n ? -signedCoef : signedCoef;
    return new Dec(mag, exp, sign);
  }

  function _decAdd(a, b) {
    // Python Decimal addition: result exponent = min(operand exponents).
    const al = _align(a, b);
    return _fromSigned(al.ca + al.cb, al.exp);
  }

  function _decSub(a, b) {
    const al = _align(a, b);
    return _fromSigned(al.ca - al.cb, al.exp);
  }

  function _decCmp(a, b) {
    const al = _align(a, b);
    if (al.ca < al.cb) return -1;
    if (al.ca > al.cb) return 1;
    return 0;
  }

  function _decMin(a, b) {
    // Mirror Python min(): returns the operand that is smaller (a on a tie — same as Python).
    return _decCmp(a, b) <= 0 ? a : b;
  }

  function _decQuantizeHalfUp(d, exp) {
    // Quantize to the given exponent with ROUND_HALF_UP (mirrors value.quantize(inc, ROUND_HALF_UP)).
    if (d.exp === exp) return new Dec(d.coef, d.exp, d.sign);
    if (d.exp > exp) {
      // Add trailing zeros (scale UP precision) — exact, no rounding.
      const coef = d.coef * 10n ** BigInt(d.exp - exp);
      return new Dec(coef, exp, d.sign);
    }
    // d.exp < exp: drop digits, round half-up on the magnitude.
    const drop = BigInt(exp - d.exp);
    const factor = 10n ** drop;
    const q = d.coef / factor;
    const r = d.coef % factor;
    let rounded = q;
    if (r * 2n >= factor) rounded = q + 1n;
    return new Dec(rounded, exp, d.sign);
  }

  function _decToIntegralCeiling(d) {
    // Round toward +infinity to an integer-exponent Dec (mirrors to_integral_value(ROUND_CEILING)).
    if (d.exp >= 0) {
      return new Dec(d.coef * 10n ** BigInt(d.exp), 0, d.sign);
    }
    const factor = 10n ** BigInt(-d.exp);
    const q = d.coef / factor;
    const r = d.coef % factor;
    let mag = q;
    // Ceiling: round toward +inf → for a POSITIVE value with a remainder, bump up;
    // for a NEGATIVE value, truncation already moves toward +inf.
    if (r !== 0n && d.sign > 0) mag = q + 1n;
    return new Dec(mag, 0, d.sign);
  }

  function _decToNumberInt(d) {
    // Exact integer value (the Dec must already be integral) as a JS Number-safe path via BigInt.
    const intg = _decToIntegralCeiling(d); // already integral → no change
    const signed = intg.sign < 0 ? -intg.coef : intg.coef;
    return signed;
  }

  function _decToString(d) {
    // Python Decimal __str__ for exponent <= 0 (fixed-point). Covers every scoring value.
    const neg = d.sign < 0 && d.coef !== 0n ? "-" : "";
    if (d.exp >= 0) {
      // Append exp zeros (exp is 0 for all our integral results).
      let s = d.coef.toString();
      for (let i = 0; i < d.exp; i++) s += "0";
      return neg + s;
    }
    const scale = -d.exp;
    let digits = d.coef.toString();
    if (digits.length <= scale) {
      digits = "0".repeat(scale - digits.length + 1) + digits;
    }
    const intPart = digits.slice(0, digits.length - scale);
    const fracPart = digits.slice(digits.length - scale);
    return neg + intPart + "." + fracPart;
  }

  // --- helpers mirroring score_calc internals -------------------------------

  function _isTruthyFlag(v) {
    // CR-01: a string flag is truthy ONLY for {"true","1","yes","on"} after strip+lower;
    // a real bool returns itself; anything else falls back to Boolean(v).
    if (typeof v === "boolean") return v;
    if (typeof v === "string") {
      const t = v.trim().toLowerCase();
      return t === "true" || t === "1" || t === "yes" || t === "on";
    }
    return Boolean(v);
  }

  function _toDecimal(value) {
    // Parse a scalar into an exact Dec, or null if not a valid number (mirrors _to_decimal).
    if (value === null || value === undefined) return null;
    return _decFromString(String(value));
  }

  function _zonePoints(profile, band) {
    // Map a zone band to its Dec points via the profile's ordered zone list (mirrors _zone_points).
    const bandD = _toDecimal(band);
    if (bandD === null) return null;
    for (const pair of profile.zones) {
      const b = _toDecimal(pair[0]);
      const points = _decFromString(pair[1]);
      if (b !== null && _decCmp(b, bandD) === 0) return points;
    }
    return null;
  }

  // Strict mm:ss(.cc) parser — anchored, seconds 00-59, centiseconds exactly two digits.
  const _TIME_RX = /^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$/;

  function _parseTimeSeconds(value) {
    // mm*60 + ss + cc/100 in Dec, or null on a malformed time (mirrors _parse_time_seconds).
    if (value === null || value === undefined) return null;
    const m = _TIME_RX.exec(String(value).trim());
    if (m === null) return null;
    const minutes = _decFromString(m[1]);
    const seconds = _decFromString(m[2]);
    const centis = m[3] !== undefined ? _decFromString(m[3]) : _ZERO();
    // minutes*60 + seconds + centis/100. Build via the Dec ops to keep scale parity.
    const sixty = _decFromString("60");
    const minSec = _decMul(minutes, sixty);
    const centiSec = _decDivByPow10(centis, 2); // centis / 100 = scale shift
    return _decAdd(_decAdd(minSec, seconds), centiSec);
  }

  function _decMul(a, b) {
    // Exact multiply: coefficients multiply, exponents add (mirrors Decimal *).
    const signed = _signedCoef(a) * _signedCoef(b);
    return _fromSigned(signed, a.exp + b.exp);
  }

  function _decDivByPow10(d, p) {
    // d / 10^p — exact, just lowers the exponent (centis/100 keeps Decimal exactness).
    return new Dec(d.coef, d.exp - p, d.sign);
  }

  function _timeFaults(rate, run, sct) {
    // ceil(rate * max(0, run - sct)) — Dec-native ceil, returns a BigInt integer (mirrors _time_faults).
    const diff = _decSub(run, sct);
    const over = _decCmp(diff, _ZERO()) > 0 ? diff : _ZERO();
    const product = _decMul(over, rate);
    const ceiled = _decToIntegralCeiling(product);
    return ceiled.sign < 0 ? -ceiled.coef : ceiled.coef; // BigInt
  }

  // --- validate() — per-field error contract (mirrors score_calc.validate) ---

  function validate(discipline, fields, profile) {
    fields = fields || {};
    const errors = [];

    if (discipline === "disc_tf") {
      const throws = fields.throws;
      if (!throws || throws.length === 0) {
        errors.push({ field: "throws", message: "Almeno un lancio è richiesto." });
      } else if (!Array.isArray(throws)) {
        // WR-01: mirror the Python authority (score_calc.validate / CR-02). A non-array truthy
        // throws (e.g. 42) has throws.length === undefined, so the for-loop below would never run
        // and validate would WRONGLY return [] (valid) while Python rejects — a drift the
        // byte-exact mirror invariant forbids. Push the same {field, message} so both agree.
        errors.push({ field: "throws", message: "Formato lanci non valido." });
      } else {
        for (let i = 0; i < throws.length; i++) {
          const throwObj = throws[i];
          const band =
            throwObj && typeof throwObj === "object" ? throwObj.zone : null;
          if (_zonePoints(profile, band) === null) {
            errors.push({
              field: "throws[" + i + "].zone",
              message: "Zona non valida: " + _pyRepr(band) + ".",
            });
          }
        }
      }
    } else if (discipline === "disc_freestyle") {
      for (const cat of profile.freestyle_cats) {
        const name = cat[0];
        const cmin = _decFromString(cat[1]);
        const cmax = _decFromString(cat[2]);
        const inc = _decFromString(cat[3]);
        const raw = fields[name];
        const value = _toDecimal(raw);
        if (raw === null || raw === undefined || raw === "") {
          errors.push({ field: name, message: "Categoria '" + name + "' richiesta." });
          continue;
        }
        if (value === null) {
          errors.push({ field: name, message: "'" + name + "' non è un numero valido." });
          continue;
        }
        if (_decCmp(value, cmin) < 0 || _decCmp(value, cmax) > 0) {
          errors.push({
            field: name,
            message: "'" + name + "' fuori range (" + _decToString(cmin) + "–" + _decToString(cmax) + ").",
          });
        } else if (!_onIncrement(value, inc)) {
          errors.push({
            field: name,
            message: "'" + name + "' non è un multiplo di " + _decToString(inc) + ".",
          });
        }
      }
      const adj = fields.adjustment;
      if (adj !== null && adj !== undefined && adj !== "" && _toDecimal(adj) === null) {
        errors.push({ field: "adjustment", message: "Aggiustamento non valido." });
      }
    } else if (discipline === "agility") {
      if (!fields.eliminated) {
        for (const timeField of ["tempo", "sct"]) {
          const raw = fields[timeField];
          if (raw === null || raw === undefined || raw === "") {
            errors.push({
              field: timeField,
              message: "'" + timeField + "' richiesto (mm:ss(.cc)).",
            });
          } else if (_parseTimeSeconds(raw) === null) {
            errors.push({ field: timeField, message: "Tempo non valido: usa mm:ss(.cc)." });
          }
        }
        const model = profile.agility_model;
        const faultField = model === "count_up" ? "course_faults" : "course_deductions";
        const rawFaults = fields[faultField];
        const value = _toDecimal(rawFaults);
        if (rawFaults === null || rawFaults === undefined || rawFaults === "") {
          errors.push({ field: faultField, message: "'" + faultField + "' richiesto." });
        } else if (value === null) {
          errors.push({ field: faultField, message: "'" + faultField + "' non valido." });
        } else if (_decCmp(value, _ZERO()) < 0) {
          errors.push({
            field: faultField,
            message: "'" + faultField + "' non può essere negativo.",
          });
        }
      }
    }

    return errors;
  }

  function _onIncrement(x, inc) {
    // True iff x lies exactly on the inc grid (mirrors _on_increment using exact Dec math).
    if (_decCmp(inc, _ZERO()) === 0) return true;
    // x / inc must be integral: align then check divisibility on integer coefficients.
    const al = _align(x, inc);
    if (al.cb === 0n) return true;
    return al.ca % al.cb === 0n;
  }

  function _pyRepr(value) {
    // Mirror Python's {band!r} for the zone-error message: ints as-is, strings single-quoted,
    // None → "None". Scoring zone bands are ints (selector values) or strings.
    if (value === null || value === undefined) return "None";
    if (typeof value === "string") return "'" + value + "'";
    return String(value);
  }

  // --- compute() — auto-calculated totals (mirrors score_calc.compute) -------

  function compute(discipline, fields, profile) {
    const out = Object.assign({}, fields || {});
    if (discipline === "disc_tf") return _computeDiscTf(out, profile);
    if (discipline === "disc_freestyle") return _computeFreestyle(out, profile);
    if (discipline === "agility") return _computeAgility(out, profile);
    return out;
  }

  function _computeDiscTf(out, profile) {
    const throws = out.throws || [];
    const perThrow = [];
    let bandTotal = _ZERO();
    for (const throwObj of throws) {
      const zonePoints = _zonePoints(profile, throwObj.zone) || _ZERO();
      bandTotal = _decAdd(bandTotal, zonePoints);
      let score = zonePoints;
      for (const bonus of profile.bonuses) {
        const key = bonus[0];
        const value = _decFromString(bonus[1]);
        if (_isTruthyFlag(throwObj[key])) score = _decAdd(score, value);
      }
      if (profile.per_throw_cap !== null && profile.per_throw_cap !== undefined) {
        const cap = _decFromString(profile.per_throw_cap);
        score = _decMin(score, cap);
      }
      perThrow.push(score);
    }

    let counted;
    if (profile.count_best_n !== null && profile.count_best_n !== undefined) {
      // sorted(per_throw, reverse=True)[:count_best_n]
      const sorted = perThrow.slice().sort(function (a, b) {
        return _decCmp(b, a); // descending
      });
      counted = sorted.slice(0, profile.count_best_n);
    } else {
      counted = perThrow;
    }
    // sum(counted, Decimal("0")) — left fold from Decimal("0") so the exponent tracks Python.
    let total = _ZERO();
    for (const v of counted) total = _decAdd(total, v);

    out.prese = String(throws.length);
    out.zona = _decToString(bandTotal);
    out.totale = _decToString(total);
    return out;
  }

  function _computeFreestyle(out, profile) {
    let total = _ZERO();
    for (const cat of profile.freestyle_cats) {
      const name = cat[0];
      const inc = _decFromString(cat[3]);
      const value = _toDecimal(out[name]) || _ZERO();
      const snapped = _decCmp(inc, _ZERO()) !== 0 ? _decQuantizeHalfUp(value, inc.exp) : value;
      total = _decAdd(total, snapped);
    }
    if (profile.freestyle_max !== null && profile.freestyle_max !== undefined) {
      const fmax = _decFromString(profile.freestyle_max);
      if (_decCmp(total, fmax) > 0) total = fmax;
    }
    const adjustment = _toDecimal(out.adjustment) || _ZERO();
    total = _decSub(total, adjustment);

    // WR-03: direct mirror of Python out.setdefault("nome", out.get("nome", "")) — when the key is
    // absent, set "". The old `|| out.nome` RHS read an always-undefined value (the guard already
    // proved "nome" not in out), so it was misleading and easy to break; "" matches Python exactly.
    if (!("nome" in out)) out.nome = "";
    if (!("timer" in out)) out.timer = "";
    out.totale = _decToString(total);
    return out;
  }

  function _computeAgility(out, profile) {
    if (out.eliminated) {
      out.result = profile.elimination_sentinel;
      out.totale = profile.elimination_sentinel;
      return out;
    }

    const run = _parseTimeSeconds(out.tempo) || _ZERO();
    const sct = _parseTimeSeconds(out.sct) || _ZERO();
    const rate = _decFromString(profile.time_fault_rate);
    const timeFaults = _timeFaults(rate, run, sct); // BigInt
    const model = profile.agility_model;

    if (model === "count_up") {
      const courseFaults = _toDecimal(out.course_faults) || _ZERO();
      // int(course_faults) + time_faults — truncate course_faults toward zero (Python int()).
      const cfInt = _truncInt(courseFaults);
      const faults = cfInt + timeFaults;
      out.faults = faults.toString();
    } else {
      // deduct_from_100: 100 - course_deductions - Decimal(time_faults)
      const courseDeductions = _toDecimal(out.course_deductions) || _ZERO();
      const result = _decSub(
        _decSub(_decFromString("100"), courseDeductions),
        _decFromInt(Number(timeFaults))
      );
      out.result = _decToString(result);
      out.totale = _decToString(result);
      out.faults = timeFaults.toString();
    }

    out.tempo = String(out.tempo === undefined || out.tempo === null ? "" : out.tempo);
    out.sct = String(out.sct === undefined || out.sct === null ? "" : out.sct);
    return out;
  }

  function _truncInt(d) {
    // Python int(Decimal) truncates toward zero → BigInt.
    if (d.exp >= 0) {
      const v = d.coef * 10n ** BigInt(d.exp);
      return d.sign < 0 ? -v : v;
    }
    const factor = 10n ** BigInt(-d.exp);
    const q = d.coef / factor; // truncates toward zero (magnitude)
    return d.sign < 0 ? -q : q;
  }

  // ===== gsd:score-calc-mirror:end =====

  const api = { compute, validate };
  if (typeof window !== "undefined") window.SEGUGIO_SCORE_CALC = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
