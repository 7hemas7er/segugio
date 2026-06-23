"""Shared Wave-0 fixtures for Phase 16 (consumed by Plan 16-01 AND 16-02).

``PROFILE_JSON`` is the pinned CSEN 2026 disc-dog profile (``score_calc.CSEN_DISC_PROFILE``)
re-expressed as a plain JSON-serialisable dict with EVERY numeric a decimal STRING (``"5"``,
never the float ``5.0``) — the transport shape the server injects into the template / the
node-vs-Python drift-guard feeds to ``score-calc.js``. Decimal-as-string is load-bearing: a
``Number``-coerced ``0.5`` bonus or ``0.01`` increment would drift the advisory total away from
the Python ``Decimal`` authority (Pitfall 1 / D-09).

``FIXTURES`` is the cross-discipline edge-case input list the parity tests iterate: best-5-of-N,
a ``0.5`` bonus, a ``"false"``/``"0"`` flag (CR-01), freestyle cap at ``freestyle_max``, agility
ceil, agility elimination sentinel.

This module is pure data (no imports beyond the self-test below) so both plans collect it cleanly.
"""

from __future__ import annotations

# CSEN 2026 disc-dog profile, every numeric as a decimal STRING (mirrors
# score_calc.CSEN_DISC_PROFILE; numbers stringified exactly as Python's Decimal does).
PROFILE_JSON = {
    "units": "m",
    # ((band, points_str), ...) — band stays an int key (zone selector value); points decimal-string.
    "zones": [[1, "1"], [2, "2"], [3, "3"], [4, "4"]],
    # ((key, value_str), ...) — two independent +0.5 per-catch bonuses.
    "bonuses": [["midair", "0.5"], ["corridor", "0.5"]],
    "per_throw_cap": "5",
    "count_best_n": 5,
    # ((name, min_str, max_str, inc_str), ...) — 4 categories, 0–10 on the 0.01 grid.
    "freestyle_cats": [
        ["team", "0", "10", "0.01"],
        ["dog", "0", "10", "0.01"],
        ["player", "0", "10", "0.01"],
        ["catch", "0", "10", "0.01"],
    ],
    "freestyle_max": "40",
    "agility_model": "count_up",
    "time_fault_rate": "1",
    "fault_value": "5",
    "elimination_sentinel": "E",
}

# WR-02: a deduct_from_100 agility profile (otherwise identical to PROFILE_JSON) so the
# drift-guard can exercise the `100 - course_deductions - Decimal(time_faults)` branch in BOTH
# compute implementations — currently only count_up is covered, so any future drift on the deduct
# path (e.g. the BigInt→Number round-trip in score-calc.js) would ship silently. Fixtures carrying
# this profile set the optional "profile_json" key; the parity tests honour it per-fixture.
PROFILE_JSON_DEDUCT = {**PROFILE_JSON, "agility_model": "deduct_from_100"}

# Self-test (Task 1 acceptance): every numeric is a decimal STRING, never a float.
assert PROFILE_JSON["per_throw_cap"] == "5"
assert PROFILE_JSON["zones"][0][1] == "1"
assert PROFILE_JSON["bonuses"][0][1] == "0.5"
assert PROFILE_JSON["freestyle_cats"][0][3] == "0.01"
assert PROFILE_JSON["freestyle_max"] == "40"
assert PROFILE_JSON_DEDUCT["agility_model"] == "deduct_from_100"


# Cross-discipline edge-case input list. Each item: {"discipline": <str>, "fields": {...}}.
# `fields` is the RAW per-discipline input shape score_calc.validate/compute consume
# (disc_tf → {"throws": [...]}, freestyle → category names + adjustment, agility → tempo/sct/...).
FIXTURES = [
    # disc_tf — best-5-of-N: 7 throws, only the best 5 count. A 0.5 bonus (midair) on a few,
    # and CR-01 string flags: "false"/"0" must NOT score, "on"/"true" must.
    {
        "discipline": "disc_tf",
        "fields": {
            "throws": [
                {"zone": 4, "midair": "on", "corridor": "false"},   # 4 + 0.5 = 4.5
                {"zone": 4, "midair": "true", "corridor": "1"},     # 4 + 0.5 + 0.5 = 5 (capped)
                {"zone": 3, "midair": "0", "corridor": "no"},       # 3 (flags off)
                {"zone": 3, "midair": "yes", "corridor": "off"},    # 3 + 0.5 = 3.5
                {"zone": 2, "midair": "false", "corridor": "false"},# 2
                {"zone": 1, "midair": "false", "corridor": "false"},# 1 (dropped — best-5)
                {"zone": 1, "midair": "false", "corridor": "false"},# 1 (dropped — best-5)
            ],
        },
    },
    # disc_tf — a single 0.5 bonus on one throw (isolates the 0.5 decimal add).
    {
        "discipline": "disc_tf",
        "fields": {
            "throws": [
                {"zone": 2, "midair": "on", "corridor": "false"},   # 2 + 0.5 = 2.5
            ],
        },
    },
    # disc_freestyle — cap boundary at freestyle_max: four maxed categories sum to exactly 40
    # (each category is itself capped at 10, so the freestyle_max clamp is exercised at the boundary).
    {
        "discipline": "disc_freestyle",
        "fields": {
            "team": "10",
            "dog": "10",
            "player": "10",
            "catch": "10",   # sum 40 == freestyle_max (clamp boundary)
            "adjustment": "0",
            "nome": "Rex & Anna",
        },
    },
    # disc_freestyle — sub-cap with an adjustment subtracted, and a 0.01-grid value.
    {
        "discipline": "disc_freestyle",
        "fields": {
            "team": "8.25",
            "dog": "7.50",
            "player": "9.00",
            "catch": "6.75",   # sum 31.5
            "adjustment": "1.5",  # → 30.0
            "nome": "Fido",
        },
    },
    # agility — count_up ceil: run over SCT by a fractional second → ceil(time_faults).
    {
        "discipline": "agility",
        "fields": {
            "tempo": "00:34.50",   # 34.5s
            "sct": "00:30.00",     # 30s → over 4.5s → ceil = 5 time-faults
            "course_faults": "5",  # + 5 course faults = 10 total
        },
    },
    # agility — elimination sentinel: eliminated short-circuits to "E", no times needed.
    {
        "discipline": "agility",
        "fields": {
            "eliminated": True,
        },
    },
    # agility — WR-02: deduct_from_100 branch (100 - course_deductions - time_faults). Over SCT by
    # 4.5s → ceil = 5 time-faults; 100 - 10 - 5 = 85. Carries its own profile so the parity tests
    # exercise the deduct compute path node-vs-Python (otherwise only count_up is covered).
    {
        "discipline": "agility",
        "profile_json": PROFILE_JSON_DEDUCT,
        "fields": {
            "tempo": "00:34.50",        # 34.5s
            "sct": "00:30.00",          # 30s → over 4.5s → ceil = 5 time-faults
            "course_deductions": "10",  # → 100 - 10 - 5 = 85
        },
    },
]


# The INVALID fixtures the validate-parity / 400-write-nothing tests use. Each item carries an
# expected error FIELD so the node-vs-Python validate parity can assert the same field surfaces.
INVALID_FIXTURES = [
    # disc_tf — a zone band that is not in the profile's zone list.
    {
        "discipline": "disc_tf",
        "fields": {"throws": [{"zone": 99, "midair": "false", "corridor": "false"}]},
        "error_field": "throws[0].zone",
    },
    # disc_tf — no throws at all.
    {
        "discipline": "disc_tf",
        "fields": {"throws": []},
        "error_field": "throws",
    },
    # disc_tf — WR-01/CR-02: a non-list truthy `throws` (a number). Python would crash on
    # enumerate(42) and JS would silently return [] (length undefined) WITHOUT the shape guards.
    # Pins Python↔JS parity on the non-iterable path: both must reject with a `throws` error.
    {
        "discipline": "disc_tf",
        "fields": {"throws": 42},
        "error_field": "throws",
    },
    # disc_freestyle — a category out of its 0–10 range.
    {
        "discipline": "disc_freestyle",
        "fields": {"team": "11", "dog": "5", "player": "5", "catch": "5"},
        "error_field": "team",
    },
    # agility — a malformed mm:ss(.cc) time.
    {
        "discipline": "agility",
        "fields": {"tempo": "34.5", "sct": "00:30.00", "course_faults": "0"},
        "error_field": "tempo",
    },
]
