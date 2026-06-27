"""Unit tests for the pure scoring authority ``segugio.ui.score_calc``.

These pin ``validate()`` + ``compute()`` against the CSEN 2026 rule tables (D-01/D-02/D-03),
the agility engine (both models + elimination + time-faults, D-06), the validate-before-compute
error contract (D-11), and exact ``decimal.Decimal`` arithmetic (D-09 — never float drift).

stdlib only — no heavy deps. The module-under-test imports clean with the heavy stack absent
(the heavy-absent gate itself lives in ``tests/test_imports.py``, extended in plan 15-03).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from segugio.opcomm.records import Discipline
from segugio.ui import score_calc
from segugio.ui.score_calc import (
    CSEN_DISC_PROFILE,
    FCI_AGILITY_PROFILE,
    AgilityModel,
    ScoringProfile,
    compute,
    validate,
)


# --------------------------------------------------------------------------------------
# Disc Toss & Fetch (CSEN D-02): best-5-of-N, per-throw cap 5, two independent +0.5 bonuses
# --------------------------------------------------------------------------------------


def test_csen_tf_best5():
    """6 throws → per-throw = zone_points + 0.5*midair + 0.5*corridor, capped at 5; round
    total = best 5 of N (D-02). Zones 4/4/3/2/1/4 with assorted bonuses; result is the pinned
    exact Decimal and the flat keys (prese/zona/totale) are emitted."""
    throws = [
        {"zone": 4, "midair": True, "corridor": True},   # 4 + .5 + .5 = 5.0 (no cap hit)
        {"zone": 4, "midair": False, "corridor": True},  # 4 + .5 = 4.5
        {"zone": 3, "midair": True, "corridor": False},  # 3 + .5 = 3.5
        {"zone": 2, "midair": False, "corridor": False},  # 2
        {"zone": 1, "midair": False, "corridor": False},  # 1
        {"zone": 4, "midair": False, "corridor": False},  # 4
    ]
    # per-throw: [5.0, 4.5, 3.5, 2, 1, 4] → best 5 = 5.0 + 4.5 + 4 + 3.5 + 2 = 19.0
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["totale"] == "19.0"
    assert out["prese"] == "6"
    # zona carries the per-throw band sum (informational) — present and non-empty
    assert "zona" in out


def test_csen_tf_per_throw_cap():
    """A 4-point zone with both bonuses would be 5.0; a hypothetical >5 throw is capped at 5
    via min() (NEVER quantized — Pitfall 4). A single max throw scores exactly 5."""
    throws = [{"zone": 4, "midair": True, "corridor": True}]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["totale"] == "5.0"


def test_decimal_exactness():
    """Best-5 of a set that float-drifts must be EXACTLY Decimal('19.0'), never 19.000…04 (D-09)."""
    throws = [
        {"zone": 4, "midair": True, "corridor": False},   # 4.5
        {"zone": 4, "midair": True, "corridor": True},    # 5.0
        {"zone": 1, "midair": False, "corridor": False},  # 1
        {"zone": 3, "midair": True, "corridor": False},   # 3.5
        {"zone": 2, "midair": False, "corridor": False},  # 2
        {"zone": 4, "midair": False, "corridor": False},  # 4
    ]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    # best 5 = 5.0 + 4.5 + 4 + 3.5 + 2 = 19.0 exactly
    assert Decimal(out["totale"]) == Decimal("19.0")
    assert out["totale"] == "19.0"
    assert "19.000" not in out["totale"]


def test_csen_tf_string_falsey_flags_no_bonus():
    """CR-01: string ``"false"`` / ``"0"`` bonus flags must NOT add the bonus.

    Form posts and JSON bodies deliver flags as strings; a bare truthiness check scored
    ``"false"`` as truthy and inflated the on-air total. A single zone-1 throw with both
    bonus flags string-false must score exactly the zone points (no +0.5 bonuses applied):
    the verbatim Decimal of ``Decimal("1")`` is ``"1"`` (D-09 — never quantized to "1.0")."""
    throws = [{"zone": 1, "midair": "false", "corridor": "false"}]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["totale"] == "1"
    # "0" and "no" are likewise falsey for the strict flag.
    throws = [{"zone": 1, "midair": "0", "corridor": "no"}]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["totale"] == "1"


def test_csen_tf_string_truthy_flags_add_bonus():
    """CR-01: explicit affirmative string flags ("true"/"1") DO add the +0.5 bonus.

    A zone-1 throw with both bonuses string-true must score 1 + 0.5 + 0.5 = 2.0."""
    throws = [{"zone": 1, "midair": "true", "corridor": "1"}]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["totale"] == "2.0"


def test_disc_tf_per_throw_score_subkey():
    """D-03: each throw carries an ADDITIVE per-throw ``score`` Decimal STRING co-located on the
    throw dict, ALONGSIDE the byte-identical raw ``{zone, midair, corridor}`` keys (D-04). A
    ``{zone:4, midair:True, corridor:False}`` throw scores 4 + 0.5 = ``"4.5"``; the raw keys survive."""
    throws = [{"zone": 4, "midair": True, "corridor": False}]
    out = compute(Discipline.disc_tf, {"throws": throws}, CSEN_DISC_PROFILE)
    assert out["throws"][0]["score"] == "4.5"
    # raw keys preserved byte-identical on the same throw dict (additive, not mutated).
    assert out["throws"][0]["zone"] == 4
    assert out["throws"][0]["midair"] is True
    assert out["throws"][0]["corridor"] is False
    # the score subkey is a STRING (str(Decimal)), never a raw Decimal (Pitfall 1).
    assert isinstance(out["throws"][0]["score"], str)
    # flat keys still emitted byte-identical.
    assert out["totale"] == "4.5"


# --------------------------------------------------------------------------------------
# Disc Freestyle (CSEN D-03/D-08): 4 categories 0-10 on 0.01 grid, sum (max 40) minus adjustment
# --------------------------------------------------------------------------------------


def test_csen_freestyle_sum():
    """4 categories each snapped to 0.01, summed (max 40), then manual adjustment subtracted (D-08)."""
    fields = {
        "nome": "Rex",
        "timer": "1:45",
        "team": "8.50",
        "dog": "7.25",
        "player": "6.00",
        "catch": "9.10",
        "adjustment": "0",
    }
    # 8.50 + 7.25 + 6.00 + 9.10 = 30.85
    out = compute(Discipline.disc_freestyle, fields, CSEN_DISC_PROFILE)
    assert out["totale"] == "30.85"
    assert out["nome"] == "Rex"
    assert out["timer"] == "1:45"


def test_csen_freestyle_adjustment():
    """The manual adjustment (CSEN deductions, D-08) is subtracted from the 4-category sum."""
    fields = {
        "nome": "Rex",
        "timer": "1:45",
        "team": "10.00",
        "dog": "10.00",
        "player": "10.00",
        "catch": "10.00",
        "adjustment": "2.50",
    }
    # 40.00 - 2.50 = 37.50
    out = compute(Discipline.disc_freestyle, fields, CSEN_DISC_PROFILE)
    assert out["totale"] == "37.50"


def test_freestyle_criteria_subkey():
    """D-03: freestyle emits an ADDITIVE top-level ``criteria{}`` mapping each category name to its
    0.01-snapped Decimal STRING, ALONGSIDE the byte-identical ``totale`` (D-04). ``team:"8.5"`` snaps
    to ``"8.50"`` on the 0.01 grid."""
    fields = {
        "nome": "Rex",
        "timer": "1:45",
        "team": "8.5",
        "dog": "7.25",
        "player": "6.00",
        "catch": "9.10",
        "adjustment": "0",
    }
    out = compute(Discipline.disc_freestyle, fields, CSEN_DISC_PROFILE)
    assert out["criteria"]["team"] == "8.50"
    assert out["criteria"]["catch"] == "9.10"
    # every criteria value is a STRING (str(Decimal)), never a raw Decimal (Pitfall 1).
    assert all(isinstance(v, str) for v in out["criteria"].values())
    # flat total byte-identical: 8.50 + 7.25 + 6.00 + 9.10 = 30.85
    assert out["totale"] == "30.85"


# --------------------------------------------------------------------------------------
# Agility engine (D-06): count_up, deduct_from_100, elimination, ceil time-faults
# --------------------------------------------------------------------------------------


def test_agility_count_up():
    """count_up: faults = course_faults + ceil(rate * max(0, run - SCT)). 52.40 vs 50.00 → 3 TF."""
    fields = {"course_faults": "5", "tempo": "00:52.40", "sct": "00:50.00"}
    out = compute(Discipline.agility, fields, FCI_AGILITY_PROFILE)
    # over = 2.40s, rate 1/sec, ceil(2.40) = 3 time-faults → 5 + 3 = 8
    assert out["faults"] == "8"
    assert out["tempo"] == "00:52.40"
    assert out["sct"] == "00:50.00"


def test_agility_deduct():
    """deduct_from_100: result = 100 - course_deductions - time_faults; faults carries TF."""
    profile = ScoringProfile(
        units=FCI_AGILITY_PROFILE.units,
        zones=(),
        bonuses=(),
        per_throw_cap=None,
        count_best_n=None,
        freestyle_cats=(),
        freestyle_max=Decimal("0"),
        agility_model=AgilityModel.deduct_from_100,
        time_fault_rate=Decimal("1"),
        fault_value=Decimal("5"),
        elimination_sentinel="E",
    )
    fields = {"course_deductions": "10", "tempo": "00:52.40", "sct": "00:50.00"}
    out = compute(Discipline.agility, fields, profile)
    # time_faults = ceil(2.40) = 3 → 100 - 10 - 3 = 87
    assert out["result"] == "87"
    assert out["totale"] == "87"
    assert out["faults"] == "3"


def test_agility_elimination():
    """An elimination flag short-circuits to the 'E' sentinel STRING; no numeric branch runs."""
    fields = {"eliminated": True, "course_faults": "5", "tempo": "00:52.40", "sct": "00:50.00"}
    out = compute(Discipline.agility, fields, FCI_AGILITY_PROFILE)
    assert out["result"] == "E"
    assert isinstance(out["result"], str)
    # the numeric faults sum must NOT have been computed into a number that airs
    assert out.get("faults") != "8"


def test_agility_faults_breakdown_subkey():
    """D-03: count_up emits an ADDITIVE ``faults_breakdown{course,time}`` (both Decimal STRINGS),
    ALONGSIDE the byte-identical flat ``faults`` total (D-04). tempo 00:34.50 / sct 00:30.00 → over
    4.5s → ceil 5 time-faults; course_faults 5 → faults_breakdown {course:"5", time:"5"}, faults "10"."""
    fields = {"course_faults": "5", "tempo": "00:34.50", "sct": "00:30.00"}
    out = compute(Discipline.agility, fields, FCI_AGILITY_PROFILE)
    assert out["faults_breakdown"] == {"course": "5", "time": "5"}
    assert out["faults"] == "10"
    # both breakdown values are STRINGS (str(Decimal)/str(int)), never raw Decimal (Pitfall 1).
    assert all(isinstance(v, str) for v in out["faults_breakdown"].values())


def test_agility_elimination_omits_breakdown():
    """D-03 open item PINNED: the elimination short-circuit OMITS faults_breakdown entirely (no run →
    no course/time split), keeping the D-05 snapshot deterministic."""
    fields = {"eliminated": True, "course_faults": "5", "tempo": "00:34.50", "sct": "00:30.00"}
    out = compute(Discipline.agility, fields, FCI_AGILITY_PROFILE)
    assert out["result"] == "E"
    assert out["totale"] == "E"
    assert "faults_breakdown" not in out


# --------------------------------------------------------------------------------------
# Validate-before-compute (D-11): per-field errors for invalid inputs, compute never reached
# --------------------------------------------------------------------------------------


def test_validation_errors():
    """A matrix of invalid inputs each yields a [{field, message}] entry; compute is NOT called."""
    # out-of-range zone band (band 9 not in CSEN zones 1..4)
    errs = validate(Discipline.disc_tf, {"throws": [{"zone": 9, "midair": False, "corridor": False}]}, CSEN_DISC_PROFILE)
    assert any(e["field"] for e in errs) and len(errs) >= 1

    # missing required field (no throws at all for T&F)
    errs = validate(Discipline.disc_tf, {}, CSEN_DISC_PROFILE)
    assert len(errs) >= 1

    # off-increment freestyle category (8.005 not on the 0.01 grid)
    errs = validate(
        Discipline.disc_freestyle,
        {"team": "8.005", "dog": "5", "player": "5", "catch": "5"},
        CSEN_DISC_PROFILE,
    )
    assert any(e["field"] == "team" for e in errs)

    # freestyle category out of range (11 > max 10)
    errs = validate(
        Discipline.disc_freestyle,
        {"team": "11", "dog": "5", "player": "5", "catch": "5"},
        CSEN_DISC_PROFILE,
    )
    assert any(e["field"] == "team" for e in errs)

    # malformed mm:ss(.cc) times (D-12 / Pitfall 6): 99:60, 2:5, 01:30.4
    for bad in ("99:60", "2:5", "01:30.4"):
        errs = validate(
            Discipline.agility,
            {"course_faults": "0", "tempo": bad, "sct": "00:50.00"},
            FCI_AGILITY_PROFILE,
        )
        assert any(e["field"] == "tempo" for e in errs), f"{bad!r} should be rejected"

    # a valid input returns an empty error list
    errs = validate(
        Discipline.agility,
        {"course_faults": "0", "tempo": "00:50.00", "sct": "00:50.00"},
        FCI_AGILITY_PROFILE,
    )
    assert errs == []


def test_validate_passes_then_compute_safe():
    """When validate() returns [], compute() proceeds with exact Decimal arithmetic."""
    fields = {"throws": [{"zone": 4, "midair": True, "corridor": True}]}
    assert validate(Discipline.disc_tf, fields, CSEN_DISC_PROFILE) == []
    out = compute(Discipline.disc_tf, fields, CSEN_DISC_PROFILE)
    assert out["totale"] == "5.0"


def test_module_imports_stdlib_only():
    """Sanity: the module exposes the public authority surface and the builtin profiles."""
    assert hasattr(score_calc, "validate")
    assert hasattr(score_calc, "compute")
    assert isinstance(CSEN_DISC_PROFILE, ScoringProfile)
    assert isinstance(FCI_AGILITY_PROFILE, ScoringProfile)


@pytest.mark.parametrize("text", ["NaN", "nan", "sNaN", "snan", "Infinity", "inf", "-inf", "-Infinity"])
def test_to_decimal_rejects_non_finite(text):
    """_to_decimal returns None for non-finite Decimals.

    Decimal("NaN")/"sNaN"/"Infinity" CONSTRUCT without raising; without the is_finite() guard they
    would either signal InvalidOperation at the un-wrapped validate() comparisons (an unhandled 500)
    or be folded into a written total and AIR a literal "NaN"/"-Infinity" (a broadcast-integrity
    breach). The guard turns them into the per-field-error None contract. (Security audit T-16-01.)
    """
    assert score_calc._to_decimal(text) is None


def test_validate_rejects_non_finite_per_discipline():
    """A non-finite numeric in any discipline is a clean per-field validation error, not a crash."""
    # freestyle adjustment (pre-fix this PASSED validate and aired "NaN" to the overlay) + category
    adj_errs = validate(
        Discipline.disc_freestyle,
        {"team": "5", "dog": "5", "player": "5", "catch": "5", "adjustment": "NaN"},
        CSEN_DISC_PROFILE,
    )
    assert any(e["field"] == "adjustment" for e in adj_errs)
    assert validate(
        Discipline.disc_freestyle,
        {"team": "Infinity", "dog": "5", "player": "5", "catch": "5"},
        CSEN_DISC_PROFILE,
    )
    # agility fault field + disc_tf zone (signalling sNaN raised on '==' pre-fix)
    assert validate(
        Discipline.agility,
        {"tempo": "00:34.50", "sct": "00:30.00", "course_faults": "nan"},
        CSEN_DISC_PROFILE,
    )
    assert validate(
        Discipline.disc_tf, {"throws": [{"zone": "sNaN"}]}, CSEN_DISC_PROFILE
    )


def test_validate_rejects_astronomical_magnitude():
    """Finite-but-absurd magnitudes on the otherwise-unbounded fields are a per-field error.

    adjustment / course_faults / course_deductions are only null/sign-checked; without the
    _MAX_FIELD_MAGNITUDE bound a value like "1e1000" passes validate() and then overflows Decimal
    arithmetic (500) or airs a 1001-digit total (204). The bound turns it into a clean 400.
    (Security audit T-16-01/02 magnitude sibling.)
    """
    adj_errs = validate(
        Discipline.disc_freestyle,
        {"team": "5", "dog": "5", "player": "5", "catch": "5", "adjustment": "1e1000"},
        CSEN_DISC_PROFILE,
    )
    assert any(e["field"] == "adjustment" for e in adj_errs)
    faults_errs = validate(
        Discipline.agility,
        {"tempo": "00:34.50", "sct": "00:30.00", "course_faults": "1E100000"},
        CSEN_DISC_PROFILE,
    )
    assert any(e["field"] == "course_faults" for e in faults_errs)
    # A real, in-range adjustment / faults value still validates clean (the bound is generous).
    assert validate(
        Discipline.disc_freestyle,
        {"team": "5", "dog": "5", "player": "5", "catch": "5", "adjustment": "1.5"},
        CSEN_DISC_PROFILE,
    ) == []
    assert validate(
        Discipline.agility,
        {"tempo": "00:34.50", "sct": "00:30.00", "course_faults": "5"},
        CSEN_DISC_PROFILE,
    ) == []
