"""Pure per-discipline overlay renderer — the OBS read-from-file text (display-only).

``render_overlay_text(score_doc)`` maps an operator-entered :class:`~segugio.opcomm.records.ScoreDoc`
to a single Italian overlay line for the OBS "read from file" text source (OBS-05). It is
DISPLAY-ONLY (SCR-04): it ONLY formats the values the operator typed into a string — it never
sums ``prese`` into ``totale``, never computes a fault count, never derives a result. If a
"Totale" is shown it is the operator-entered total VERBATIM, not a computed sum. There is no
scoring / judging / adjudication / CV-of-faults code path anywhere in ``segugio.ui``.

Per-discipline layout (SCR-02):

  * disc Toss & Fetch — ``Prese`` / ``Zona`` / ``Totale``
  * disc Freestyle    — name + ``Timer``
  * agility           — ``Tempo`` vs ``SCT`` + ``Faults``

stdlib only — no Flask, no numpy, no heavy deps. ``import segugio.ui.score_render`` succeeds
with the whole heavy stack (and Flask) absent.
"""

from __future__ import annotations

from ..opcomm.records import Discipline, ScoreDoc

__all__ = ["render_overlay_text"]

# Guard against an operator pasting an overflowing/control-laden value into the OBS overlay
# (T-05-05-02): each displayed field value is length-bounded and stripped of newlines/control
# chars so a crafted value cannot inject extra overlay lines or break the read-from-file source.
_MAX_FIELD_LEN = 64


def _clean(value: object) -> str:
    """Format one operator-entered value for the overlay: VERBATIM, but bounded + sanitized.

    No arithmetic, no interpretation — ``str()`` of the operator value, with newlines/control
    characters dropped and the length capped (T-05-05-02 overlay-injection mitigation). This is
    the ONLY transformation the renderer applies, and it is purely cosmetic/safety: the number
    the operator typed is the number that shows.
    """
    text = "" if value is None else str(value)
    # Drop CR/LF and other control chars so a value can't inject extra overlay lines.
    text = "".join(ch for ch in text if ch == " " or (ch.isprintable() and ch not in "\r\n"))
    text = text.strip()
    if len(text) > _MAX_FIELD_LEN:
        text = text[:_MAX_FIELD_LEN]
    return text


def _get(fields: dict, *keys: str) -> str:
    """Fetch the first present key from ``fields`` (operator may post any of the aliases)."""
    for key in keys:
        if key in fields and fields[key] not in (None, ""):
            return _clean(fields[key])
    return ""


def render_overlay_text(score_doc: ScoreDoc) -> str:
    """Render an operator-entered ``ScoreDoc`` to its Italian overlay line (display-only).

    The discipline selects the field layout; every shown value is the operator's input
    formatted verbatim (sanitized + length-bounded), never computed. Returns a single line
    (no embedded newlines) suitable for the OBS read-from-file text source.
    """
    fields = score_doc.fields or {}
    discipline = score_doc.discipline

    if discipline == Discipline.disc_tf:
        prese = _get(fields, "prese")
        zona = _get(fields, "zona")
        totale = _get(fields, "totale")
        return f"Prese: {prese}  Zona: {zona}  Totale: {totale}"

    if discipline == Discipline.disc_freestyle:
        nome = _get(fields, "nome")
        timer = _get(fields, "timer")
        return f"{nome}  Timer: {timer}"

    if discipline == Discipline.agility:
        tempo = _get(fields, "tempo")
        sct = _get(fields, "sct", "SCT")
        faults = _get(fields, "faults")
        return f"Tempo: {tempo} / SCT: {sct}  Faults: {faults}"

    # Defensive: an unknown discipline (should be impossible — Discipline is a closed Enum
    # validated at ScoreDoc construction) renders an empty-but-valid line, never raises.
    return ""
