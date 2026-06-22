"""Profile-swap (SCP-01) + malformed-profile fail-fast (SCP-02) tests.

These pin the two config-driven scoring-profile guarantees of plan 15-02:

  * **SCP-01** — swapping the active scoring profile (CSEN -> FIDASC) changes the
    computed result with NO code change. Both fixtures load through the existing
    fail-fast loader, are adapted into the plain ``score_calc.ScoringProfile``
    dataclass via :func:`adapt_scoring_profile`, and the SAME raw throws fed
    through :func:`score_calc.compute` produce a DIFFERENT total — the swap is
    config-only (no source file touched between the two computes).
  * **SCP-02** — a malformed scoring profile fails fast at config-load with
    ``SystemExit(2)``, riding the EXISTING loader (no new fail-fast surface).

FIDASC numbers stay ``[ASSUMED]`` (the human-verify gate, Task 2, was resolved as
"stub accepted for v1.3" — CSEN, fully pinned, carries scoring correctness). So the
swap test asserts the STRUCTURAL divergence (zone count / bonus count / best-N
presence) + that CSEN stays numerically correct + that the two totals differ,
WITHOUT pinning a hard FIDASC numeric total (per the plan's stub-aware carry-forward).

stdlib + pydantic only — no heavy deps. ``load_config`` validates the YAML fixtures
through the existing ``yaml.safe_load``-only loader.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from segugio.config.discipline import adapt_scoring_profile
from segugio.config.loader import load_config
from segugio.opcomm.records import Discipline
from segugio.ui import score_calc


# The SAME raw disc Toss & Fetch throws fed through BOTH profiles. Six throws, every
# catch a 4-zone landing in the central corridor (and the top two also mid-air). This
# input is deliberately shaped so the CSEN and FIDASC rule shapes diverge on it:
#   * CSEN applies TWO independent +0.5 bonuses, a per-throw cap of 5, and counts only
#     the best 5 of N.
#   * FIDASC applies a SINGLE +1 corridor bonus, NO per-throw cap, and NO best-N.
_SWAP_THROWS = [
    {"zone": 4, "midair": True, "corridor": True},
    {"zone": 4, "midair": True, "corridor": True},
    {"zone": 4, "midair": False, "corridor": True},
    {"zone": 4, "midair": False, "corridor": True},
    {"zone": 4, "midair": False, "corridor": True},
    {"zone": 4, "midair": False, "corridor": True},
]


def test_profile_swap_changes_result():
    """SCP-01: CSEN -> FIDASC changes the computed total with NO code change.

    Loads both shipped fixtures through the existing loader, adapts each
    ``field.scoring`` into the plain dataclass, and feeds the SAME raw throws through
    ``score_calc.compute`` with each profile. Asserts:

      1. the structural divergence is real (FIDASC = 5 zones / single bonus / no best-N
         vs CSEN = 4 zones / two bonuses / best-5) — this is what makes the swap matter;
      2. CSEN stays numerically correct (the pinned reference total);
      3. the two ``totale`` values DIFFER (the swap is config-only — no source changed).

    FIDASC's exact numeric total is NOT pinned here: its numbers are still ``[ASSUMED]``
    (human-verify resolved as "stub accepted for v1.3"). The divergence-driven inequality
    holds for ANY structurally-different FIDASC table, so the test stays valid whether or
    not the FIDASC numbers are later confirmed (carry-forward, plan Task 3 <action>).
    """
    csen_cfg = load_config("config.csen.example.yaml")
    fidasc_cfg = load_config("config.fidasc.example.yaml")

    csen = adapt_scoring_profile(csen_cfg.field.scoring)
    fidasc = adapt_scoring_profile(fidasc_cfg.field.scoring)

    # (1) Structural divergence — the swap is meaningful precisely because the shapes differ.
    assert len(csen.zones) == 4, "CSEN ships 4 disc zones (D-02, pinned)"
    assert len(fidasc.zones) == 5, "FIDASC ships 5 disc zones (structurally != CSEN, Pitfall 5)"
    assert len(csen.bonuses) == 2, "CSEN has two independent +0.5 bonuses (D-02)"
    assert len(fidasc.bonuses) == 1, "FIDASC has a single +1 corridor bonus (Pitfall 5)"
    assert csen.count_best_n == 5, "CSEN counts only the best 5 of N (D-02)"
    assert fidasc.count_best_n is None, "FIDASC has no best-N cap (Pitfall 5)"
    assert csen.per_throw_cap == Decimal("5"), "CSEN caps each throw at 5 (D-02)"
    assert fidasc.per_throw_cap is None, "FIDASC has no per-throw cap (Pitfall 5)"

    # (2) Same raw input through each profile.
    csen_out = score_calc.compute(Discipline.disc_tf, {"throws": _SWAP_THROWS}, csen)
    fidasc_out = score_calc.compute(Discipline.disc_tf, {"throws": _SWAP_THROWS}, fidasc)

    # CSEN stays numerically correct (the pinned reference). Per-throw under CSEN:
    #   [4+.5+.5=5.0, 5.0, 4+.5=4.5, 4.5, 4.5, 4.5]  (cap 5 never bites here)
    #   best 5 of N = 5.0 + 5.0 + 4.5 + 4.5 + 4.5 = 23.5
    assert csen_out["totale"] == "23.5", "CSEN total must match the pinned D-02 calculation"

    # (3) The swap changes the result — the FIDASC total differs from the CSEN total.
    # (FIDASC numerics remain [ASSUMED]; we assert only the inequality, not its exact value.)
    assert fidasc_out["totale"] != csen_out["totale"], (
        "swapping CSEN -> FIDASC must change the computed total with no code change (SCP-01)"
    )


def test_malformed_profile_fails_fast(tmp_config, valid_config_dict):
    """SCP-02: a malformed scoring profile fails fast at config-load with ``SystemExit(2)``.

    Rides the EXISTING ``load_config`` fail-fast path (``yaml.safe_load`` -> pydantic
    ``ValidationError`` -> ``SystemExit(2)``) — no new fail-fast surface. A negative
    zone ``points`` violates the ``Annotated[Decimal, Field(ge=0)]`` constraint on
    ``ZoneBand``, raising the aggregated validation error the loader turns into exit 2.
    """
    import yaml

    bad = valid_config_dict
    bad["field"]["scoring"] = {
        "zones": [{"band": 1, "points": -1}],  # negative points -> Field(ge=0) violation
    }
    path = tmp_config(yaml.safe_dump(bad))

    with pytest.raises(SystemExit) as exc_info:
        load_config(path)
    assert exc_info.value.code == 2, "malformed profile must fail fast with SystemExit(2)"


@pytest.mark.parametrize("bad_n", [-2, 0])
def test_count_best_n_negative_or_zero_fails_fast(tmp_config, valid_config_dict, bad_n):
    """CR-02/SCP-02: a non-positive ``count_best_n`` fails fast at config-load (SystemExit(2)).

    Without a lower bound, ``count_best_n: -2`` reached Python's negative-slice semantics and
    silently dropped throws (and ``0`` scored every round as 0). ``Annotated[int, Field(ge=1)]``
    now rejects it via the existing loader fail-fast — no new fail-fast surface."""
    import yaml

    bad = valid_config_dict
    bad["field"]["scoring"] = {
        "zones": [{"band": 1, "points": 1}],
        "count_best_n": bad_n,
    }
    path = tmp_config(yaml.safe_dump(bad))

    with pytest.raises(SystemExit) as exc_info:
        load_config(path)
    assert exc_info.value.code == 2, "non-positive count_best_n must fail fast with SystemExit(2)"


def test_per_throw_cap_negative_fails_fast(tmp_config, valid_config_dict):
    """CR-03/SCP-02: a negative ``per_throw_cap`` fails fast at config-load (SystemExit(2)).

    Without a lower bound, ``per_throw_cap: -5`` reached ``min(score, cap)`` and aired a
    negative round total. ``Annotated[Decimal, Field(gt=0)]`` now rejects it via the existing
    loader fail-fast — no new fail-fast surface."""
    import yaml

    bad = valid_config_dict
    bad["field"]["scoring"] = {
        "zones": [{"band": 1, "points": 1}],
        "per_throw_cap": -5,
    }
    path = tmp_config(yaml.safe_dump(bad))

    with pytest.raises(SystemExit) as exc_info:
        load_config(path)
    assert exc_info.value.code == 2, "negative per_throw_cap must fail fast with SystemExit(2)"
