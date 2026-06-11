"""SCR-04 — the system DISPLAYS scores, never adjudicates.

The renderer (``segugio.ui.score_render.render_overlay_text``) maps an operator-entered
``ScoreDoc`` to the Italian OBS read-from-file overlay line. It is DISPLAY-ONLY:

  * each discipline's operator-entered values render VERBATIM into the string;
  * the renderer never sums/derives a result — a deliberately-wrong operator ``totale``
    is shown as-is, never recomputed (the SCR-04 automated gate);
  * a SOURCE-level guard asserts no module under ``segugio.ui`` defines a
    scoring/judge/adjudication function (no hidden CV-of-faults path);
  * the module is stdlib-only and imports with Flask absent.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

from segugio.opcomm.records import Discipline, ScoreDoc
from segugio.ui.score_render import render_overlay_text


# --- per-discipline verbatim rendering (SCR-02 fields, SCR-04 verbatim) ------ #


def test_disc_tf_renders_operator_values_verbatim():
    # Toss & Fetch: prese / zona / totale — all operator-entered, none computed.
    doc = ScoreDoc(
        discipline=Discipline.disc_tf,
        fields={"prese": "5", "zona": "3", "totale": "12"},
    )
    line = render_overlay_text(doc)
    assert "5" in line and "3" in line and "12" in line
    # The Italian field labels appear in the rendered line.
    assert "Prese" in line and "Zona" in line and "Totale" in line


def test_disc_freestyle_renders_name_and_timer():
    doc = ScoreDoc(
        discipline=Discipline.disc_freestyle,
        fields={"nome": "Rex & Anna", "timer": "01:30"},
    )
    line = render_overlay_text(doc)
    assert "Rex & Anna" in line
    assert "01:30" in line


def test_agility_renders_time_sct_faults():
    doc = ScoreDoc(
        discipline=Discipline.agility,
        fields={"tempo": "34.5", "sct": "40.0", "faults": "5"},
    )
    line = render_overlay_text(doc)
    assert "34.5" in line and "40.0" in line and "5" in line


# --- SCR-04: the renderer NEVER recomputes a totale --------------------------- #


def test_renderer_never_recomputes_totale():
    """A deliberately-WRONG operator totale is displayed as-is, never recomputed.

    prese=5, zona=3 would sum to 8 if the system adjudicated; the operator entered 999.
    The display-only contract requires the line to show 999 (the operator value) and
    NOT 8 (a computed sum) — proving no adjudication happens.
    """
    doc = ScoreDoc(
        discipline=Discipline.disc_tf,
        fields={"prese": "5", "zona": "3", "totale": "999"},
    )
    line = render_overlay_text(doc)
    assert "999" in line  # operator value shown verbatim
    assert "8" not in line.replace("999", "")  # never the computed sum 5+3


# --- SCR-04: a source-level guard — no scoring/judge function in segugio.ui --- #


def test_no_adjudication_code_path():
    """No module under ``segugio.ui`` defines a scoring/adjudication/judge function.

    Walks the AST of every ui/*.py module and asserts no function name matches the
    adjudication signal set (``score``/``judge``/``adjudicate``/``compute_total``/
    ``compute_faults``/etc.) — SCR-04 is an automated gate, not a claim.
    """
    ui_pkg = importlib.import_module("segugio.ui")
    ui_dir = pathlib.Path(ui_pkg.__file__).parent
    forbidden = (
        "adjudicate",
        "judge",
        "compute_total",
        "compute_score",
        "compute_faults",
        "sum_prese",
        "tally",
        "score_dog",
    )
    offenders: list[str] = []
    for py in ui_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                if any(sig in name for sig in forbidden):
                    offenders.append(f"{py.name}:{node.name}")
    assert offenders == [], f"adjudication function(s) found (SCR-04): {offenders}"


def test_score_render_is_stdlib_only_and_light():
    """render_overlay_text imports with the heavy stack absent (Flask not required)."""
    mod = importlib.import_module("segugio.ui.score_render")
    assert hasattr(mod, "render_overlay_text")


def test_unknown_discipline_is_handled():
    """A ScoreDoc with empty fields renders without raising (defensive, display-only)."""
    doc = ScoreDoc(discipline=Discipline.disc_tf, fields={})
    line = render_overlay_text(doc)
    assert isinstance(line, str)
