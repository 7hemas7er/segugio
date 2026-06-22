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
