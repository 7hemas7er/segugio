"""Pure-stdlib scoring authority — the single source of truth for validate + compute.

``validate(discipline, fields, profile) -> list[{field, message}]`` reports per-field input
errors (out-of-range, missing required, malformed ``mm:ss(.cc)`` time, off-increment) and
``compute(discipline, fields, profile) -> dict`` returns the auto-calculated totals for disc
Toss & Fetch, disc Freestyle and agility (both fault models), driven ENTIRELY by an injected
:class:`ScoringProfile` plain dataclass. This is the keystone compute brain every later phase
(``POST /score``, the console modal, the rich data model) consumes (SCC-02/SCC-04).

Contract (D-11): the caller runs ``validate()`` FIRST; on a non-empty error list it writes
nothing and never calls ``compute()``. ``compute()`` assumes valid input and returns ``dict(fields)``
plus the FLAT summary keys :mod:`segugio.ui.score_render` reads VERBATIM (display-only, SCR-04):

  * disc Toss & Fetch — ``prese`` / ``zona`` / ``totale``
  * disc Freestyle    — ``nome`` / ``timer`` / ``totale``
  * agility           — ``tempo`` / ``sct`` / ``faults`` (+ ``result`` / ``totale`` on deduct/elimination)

ALL arithmetic is :class:`decimal.Decimal` end-to-end (D-09) — there is no float coercion in the
compute path, so a float-drifted impossible total can never air. Totals are stringified verbatim
so the renderer shows exactly the number computed (e.g. best-5 == ``"19.0"``, never ``"19.000…04"``).

stdlib only — no Flask, no numpy, no heavy deps, no ``import segugio.config``. ``import
segugio.ui.score_calc`` succeeds with the whole heavy stack (and Flask) absent (RBT-08 / Pitfall 1).
The scoring profile is pydantic-validated in ``segugio.config`` and INJECTED here as a plain
dataclass (D-10) — this module never imports the config layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from enum import Enum
import re

from ..opcomm.records import Discipline

__all__ = [
    "AgilityModel",
    "ScoringProfile",
    "validate",
    "compute",
    "CSEN_DISC_PROFILE",
    "FCI_AGILITY_PROFILE",
]


class AgilityModel(str, Enum):
    """The two agility scoring models (D-06). ``str``-Enum (mirrors ``opcomm.records.Discipline``)
    so a profile may carry the plain string ``"count_up"`` / ``"deduct_from_100"`` and still
    ``==``-compare against these members."""

    count_up = "count_up"  # total_faults = course_faults + time_faults
    deduct_from_100 = "deduct_from_100"  # score = 100 - course_deductions - time_faults


# Strict mm:ss(.cc) parser (D-12, Pitfall 6): anchored, seconds 00-59, centiseconds exactly two
# digits when present. A non-match is a per-field error in validate() — NEVER a coerced 0.
_TIME_RX = re.compile(r"^(\d{1,2}):([0-5]\d)(?:\.(\d{2}))?$")


@dataclass(frozen=True)
class ScoringProfile:
    """Per-discipline/federation scoring rules — a plain frozen stdlib dataclass (D-10/D-13).

    Mirrors the ``@dataclass(frozen=True)`` convention in :mod:`segugio.opcomm.records`: immutable
    TUPLE fields (not dict/list) so the profile stays hashable + ``==``-comparable for round-trip
    tests. The pydantic profile in ``segugio.config`` is adapted into this plain shape and injected
    (the console never imports the config layer — RBT-08).

    Fields:
      * ``units`` — distance unit label (informational, e.g. ``"m"``).
      * ``zones`` — ordered ``((band, Decimal(points)), ...)`` (D-13: an ordered band list, NOT a
        fixed 4-row table, so CSEN's 4 bands and FIDASC's 5 both express).
      * ``bonuses`` — config-declared ``((key, Decimal(value)), ...)`` per-catch bonus list (D-13).
      * ``per_throw_cap`` — max per-throw score (CSEN = ``Decimal("5")``) or ``None`` for no cap.
      * ``count_best_n`` — keep only the best N throws (CSEN = ``5``) or ``None`` for "sum all".
      * ``freestyle_cats`` — ``((name, Decimal(min), Decimal(max), Decimal(increment)), ...)``.
      * ``freestyle_max`` — the freestyle total ceiling (CSEN = ``Decimal("40")``).
      * ``agility_model`` — ``"count_up"`` | ``"deduct_from_100"`` (see :class:`AgilityModel`).
      * ``time_fault_rate`` — faults per second over SCT (generic FCI = ``Decimal("1")``).
      * ``fault_value`` — points per course fault (informational for count_up; reserved).
      * ``elimination_sentinel`` — the string shown on elimination (``"E"``), never a number.
    """

    units: str
    zones: tuple
    bonuses: tuple
    per_throw_cap: Decimal | None
    count_best_n: int | None
    freestyle_cats: tuple
    freestyle_max: Decimal
    agility_model: str
    time_fault_rate: Decimal
    fault_value: Decimal
    elimination_sentinel: str


# --------------------------------------------------------------------------------------
# Internal helpers (pure, Decimal-native, never raise into the caller)
# --------------------------------------------------------------------------------------


def _is_truthy_flag(v: object) -> bool:
    """Strictly interpret a bonus flag's truthiness (CR-01).

    Form posts and JSON bodies deliver per-catch bonus flags as STRINGS, so a bare
    ``if throw.get(key):`` scores ``"false"`` / ``"0"`` / ``"no"`` as truthy and inflates
    the on-air total. This gates ONLY whether a bonus Decimal is added — no arithmetic here:

      * a real ``bool`` returns itself;
      * a ``str`` is truthy only for an explicit affirmative token (case/space-insensitive);
      * anything else falls back to plain ``bool(v)``.
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "on"}
    return bool(v)


def _to_decimal(value: object) -> Decimal | None:
    """Parse a scalar into an exact :class:`Decimal`, or ``None`` if it is not a valid number.

    ``str(value)`` first so an int/Decimal/clean string all parse; an empty/garbage value yields
    ``None`` (the caller turns that into a per-field error). No float coercion at all (D-09).
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _zone_points(profile: ScoringProfile, band: object) -> Decimal | None:
    """Map a throw's zone band to its Decimal points via the profile's ordered band list (D-13)."""
    band_d = _to_decimal(band)
    if band_d is None:
        return None
    for b, points in profile.zones:
        if _to_decimal(b) == band_d:
            return points
    return None


def _parse_time_seconds(value: object) -> Decimal | None:
    """Parse ``mm:ss(.cc)`` to exact Decimal seconds, or ``None`` on any malformed input (D-12).

    ``mm*60 + ss + cc/100`` in Decimal — no float. A non-match (``99:60``, ``2:5``, ``01:30.4``)
    returns ``None`` so the caller raises a per-field error rather than airing a coerced 0.
    """
    if value is None:
        return None
    m = _TIME_RX.match(str(value).strip())
    if m is None:
        return None
    minutes = Decimal(m.group(1))
    seconds = Decimal(m.group(2))
    centis = Decimal(m.group(3)) if m.group(3) is not None else Decimal("0")
    return minutes * Decimal("60") + seconds + centis / Decimal("100")


def _on_increment(x: Decimal, inc: Decimal) -> bool:
    """True iff ``x`` lies exactly on the ``inc`` grid (e.g. 8.00 on 0.01 → True, 8.005 → False)."""
    if inc == 0:
        return True
    q = x / inc
    return q == q.to_integral_value()


def _time_faults(rate: Decimal, run: Decimal, sct: Decimal) -> int:
    """Whole time-faults = ceil(rate * max(0, run - SCT)), Decimal-native ceil (D-06), no float."""
    over = max(Decimal("0"), run - sct)
    return int((over * rate).to_integral_value(rounding=ROUND_CEILING))


# --------------------------------------------------------------------------------------
# validate() — per-field error contract (D-11). Empty list == valid.
# --------------------------------------------------------------------------------------


def validate(discipline, fields: dict, profile: ScoringProfile) -> list[dict]:
    """Return ``[{"field": name, "message": msg}, ...]`` for invalid inputs; ``[]`` == valid.

    The caller runs this FIRST and, on a non-empty result, writes nothing and never computes
    (D-11). Covers required-field presence, numeric ranges, off-increment freestyle categories,
    and strict ``mm:ss(.cc)`` time parsing per discipline.
    """
    discipline = Discipline(discipline)
    fields = fields or {}
    errors: list[dict] = []

    if discipline == Discipline.disc_tf:
        throws = fields.get("throws")
        if not throws:
            errors.append({"field": "throws", "message": "Almeno un lancio è richiesto."})
        else:
            for i, throw in enumerate(throws):
                band = throw.get("zone") if isinstance(throw, dict) else None
                if _zone_points(profile, band) is None:
                    errors.append(
                        {"field": f"throws[{i}].zone", "message": f"Zona non valida: {band!r}."}
                    )

    elif discipline == Discipline.disc_freestyle:
        for name, cmin, cmax, inc in profile.freestyle_cats:
            raw = fields.get(name)
            value = _to_decimal(raw)
            if raw is None or raw == "":
                errors.append({"field": name, "message": f"Categoria '{name}' richiesta."})
                continue
            if value is None:
                errors.append({"field": name, "message": f"'{name}' non è un numero valido."})
                continue
            if value < cmin or value > cmax:
                errors.append(
                    {"field": name, "message": f"'{name}' fuori range ({cmin}–{cmax})."}
                )
            elif not _on_increment(value, inc):
                errors.append(
                    {"field": name, "message": f"'{name}' non è un multiplo di {inc}."}
                )
        adj = fields.get("adjustment")
        if adj is not None and adj != "" and _to_decimal(adj) is None:
            errors.append({"field": "adjustment", "message": "Aggiustamento non valido."})

    elif discipline == Discipline.agility:
        # Elimination short-circuits the numeric requirements — an eliminated run needs no times.
        if not fields.get("eliminated"):
            for time_field in ("tempo", "sct"):
                raw = fields.get(time_field)
                if raw is None or raw == "":
                    errors.append(
                        {"field": time_field, "message": f"'{time_field}' richiesto (mm:ss(.cc))."}
                    )
                elif _parse_time_seconds(raw) is None:
                    errors.append(
                        {"field": time_field, "message": f"Tempo non valido: usa mm:ss(.cc)."}
                    )
            model = AgilityModel(profile.agility_model)
            fault_field = "course_faults" if model == AgilityModel.count_up else "course_deductions"
            raw_faults = fields.get(fault_field)
            value = _to_decimal(raw_faults)
            if raw_faults is None or raw_faults == "":
                errors.append({"field": fault_field, "message": f"'{fault_field}' richiesto."})
            elif value is None:
                errors.append({"field": fault_field, "message": f"'{fault_field}' non valido."})
            elif value < 0:
                errors.append(
                    {"field": fault_field, "message": f"'{fault_field}' non può essere negativo."}
                )

    return errors


# --------------------------------------------------------------------------------------
# compute() — auto-calculated totals. Assumes validate() already passed (D-11).
# --------------------------------------------------------------------------------------


def compute(discipline, fields: dict, profile: ScoringProfile) -> dict:
    """Return ``dict(fields)`` plus the flat summary keys the renderer reads (display-only).

    Decimal arithmetic end-to-end (D-09); totals are stringified verbatim so the on-air number
    is exactly the one computed. Caller MUST have run :func:`validate` first (D-11).
    """
    discipline = Discipline(discipline)
    out = dict(fields or {})

    if discipline == Discipline.disc_tf:
        return _compute_disc_tf(out, profile)
    if discipline == Discipline.disc_freestyle:
        return _compute_freestyle(out, profile)
    if discipline == Discipline.agility:
        return _compute_agility(out, profile)
    return out


def _compute_disc_tf(out: dict, profile: ScoringProfile) -> dict:
    """Disc Toss & Fetch (CSEN D-02): per-throw = zone_points + exact bonuses, capped, best-N sum."""
    throws = out.get("throws") or []
    per_throw: list[Decimal] = []
    band_total = Decimal("0")
    for throw in throws:
        zone_points = _zone_points(profile, throw.get("zone")) or Decimal("0")
        band_total += zone_points
        score = zone_points
        # Add each declared bonus as an EXACT Decimal constant (never quantize a 0.5 add — Pitfall 4).
        for key, value in profile.bonuses:
            if _is_truthy_flag(throw.get(key)):
                score += value
        # Cap with min(), NOT quantize (Pitfall 4).
        if profile.per_throw_cap is not None:
            score = min(score, profile.per_throw_cap)
        per_throw.append(score)

    if profile.count_best_n is not None:
        counted = sorted(per_throw, reverse=True)[: profile.count_best_n]
    else:
        counted = per_throw
    total = sum(counted, Decimal("0"))

    out["prese"] = str(len(throws))
    out["zona"] = str(band_total)
    out["totale"] = str(total)
    return out


def _compute_freestyle(out: dict, profile: ScoringProfile) -> dict:
    """Disc Freestyle (CSEN D-03/D-08): snap each category to its 0.01 grid, sum (max), minus adj."""
    total = Decimal("0")
    for name, _cmin, _cmax, inc in profile.freestyle_cats:
        value = _to_decimal(out.get(name)) or Decimal("0")
        snapped = value.quantize(inc, rounding=ROUND_HALF_UP) if inc != 0 else value
        total += snapped
    if profile.freestyle_max is not None and total > profile.freestyle_max:
        total = profile.freestyle_max
    adjustment = _to_decimal(out.get("adjustment")) or Decimal("0")
    total = total - adjustment

    out.setdefault("nome", out.get("nome", ""))
    out.setdefault("timer", out.get("timer", ""))
    out["totale"] = str(total)
    return out


def _compute_agility(out: dict, profile: ScoringProfile) -> dict:
    """Agility (D-06): elimination FIRST (sentinel string), else count_up / deduct_from_100."""
    # Pattern 4: the elimination flag overrides the numeric result — checked BEFORE any math.
    if out.get("eliminated"):
        out["result"] = profile.elimination_sentinel
        out["totale"] = profile.elimination_sentinel
        return out

    run = _parse_time_seconds(out.get("tempo")) or Decimal("0")
    sct = _parse_time_seconds(out.get("sct")) or Decimal("0")
    time_faults = _time_faults(profile.time_fault_rate, run, sct)
    model = AgilityModel(profile.agility_model)

    if model == AgilityModel.count_up:
        course_faults = _to_decimal(out.get("course_faults")) or Decimal("0")
        faults = int(course_faults) + time_faults
        out["faults"] = str(faults)
    else:  # deduct_from_100
        course_deductions = _to_decimal(out.get("course_deductions")) or Decimal("0")
        result = Decimal("100") - course_deductions - Decimal(time_faults)
        out["result"] = str(result)
        out["totale"] = str(result)
        out["faults"] = str(time_faults)

    # tempo / sct pass through verbatim as the renderer's flat keys.
    out["tempo"] = str(out.get("tempo", ""))
    out["sct"] = str(out.get("sct", ""))
    return out


# --------------------------------------------------------------------------------------
# Builtin profiles — the pinned CSEN 2026 default (D-01/D-02/D-03) + a generic FCI agility
# example (D-07). The pydantic-validated config profile adapts INTO this same shape (D-10).
# --------------------------------------------------------------------------------------

# CSEN 2026 disc-dog (D-02/D-03): Distance zones 9/18/27/36m → 1/2/3/4, two independent +0.5
# bonuses per catch (all-paws-airborne, central-corridor), per-throw cap 5, best-5-of-N (max
# round 25). Freestyle: 4 categories each 0–10 on the 0.01 grid, sum to max 40 (D-08 adjustment
# subtracted at compute). The same dataclass carries the agility fields (unused for disc).
CSEN_DISC_PROFILE = ScoringProfile(
    units="m",
    zones=(
        (1, Decimal("1")),  # 9m
        (2, Decimal("2")),  # 18m
        (3, Decimal("3")),  # 27m
        (4, Decimal("4")),  # 36m
    ),
    bonuses=(
        ("midair", Decimal("0.5")),   # all four paws airborne
        ("corridor", Decimal("0.5")),  # catch in the central corridor
    ),
    per_throw_cap=Decimal("5"),
    count_best_n=5,
    freestyle_cats=(
        ("team", Decimal("0"), Decimal("10"), Decimal("0.01")),
        ("dog", Decimal("0"), Decimal("10"), Decimal("0.01")),
        ("player", Decimal("0"), Decimal("10"), Decimal("0.01")),
        ("catch", Decimal("0"), Decimal("10"), Decimal("0.01")),
    ),
    freestyle_max=Decimal("40"),
    agility_model=AgilityModel.count_up,
    time_fault_rate=Decimal("1"),
    fault_value=Decimal("5"),
    elimination_sentinel="E",
)

# Generic FCI-style agility example (D-07 — NOT a pinned federation): count_up model,
# 1 fault/sec over SCT, 5 points per course fault, "E" on elimination. Real Italian agility
# numbers are deferred until an agility event is run. Disc fields are empty for this profile.
FCI_AGILITY_PROFILE = ScoringProfile(
    units="m",
    zones=(),
    bonuses=(),
    per_throw_cap=None,
    count_best_n=None,
    freestyle_cats=(),
    freestyle_max=Decimal("0"),
    agility_model=AgilityModel.count_up,
    time_fault_rate=Decimal("1"),
    fault_value=Decimal("5"),
    elimination_sentinel="E",
)
