"""Phase-9 09-03 — explainability sidebar + SCV-01 score-overlay mirror (served-HTML + JS-exercised).

Exercised via the Flask test client (no server, no heavy deps), mirroring ``test_ui_score.py`` /
``test_ui_tablet_layout.py``. This plan FILLS the four sidebar why-blocks scaffolded by 09-02:

  * WHY-01 reason → plain-Italian copy (``reasonToItalian`` map)
  * WHY-02 per-camera framing-score leaderboard (``buildLeaderboard``)
  * WHY-04 "auto vuole" hint + dashed-blue auto-wants tile marker (``renderAutoWants``)
  * WHY-03 live dog-lock bbox wired from ``preview.json`` ``cams[id].box`` (``updateBbox``)

and adds the SCV-01 client-side score-overlay preview: a BYTE-EXACT JS mirror of the Python
``render_overlay_text`` (``mirrorOverlayText`` + ``cleanField``), debounced, drift-guarded against
``POST /score/preview`` (09-01) once on blur/submit.

The byte-parity + reason-map tests EXECUTE the JS in console.html via ``node`` (Wave-0 CI parity):
delimited ``// ===== gsd:<name>:start/end =====`` blocks are extracted from the served HTML and
run against fixed inputs, asserting the JS output == the Python ``render_overlay_text`` (and the
WHY-01 Italian strings). ``node`` is on PATH in this environment (Node 24 LTS).

Test selectors: ``-k reason`` / ``-k leaderboard`` / ``-k auto_wants`` / ``-k bbox`` / ``-k scv01``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from segugio.framing.signals import ScorerStatus

__all__ = [
    "test_reason_strings_italian",
]


# --- fixtures / helpers ------------------------------------------------------ #


@pytest.fixture
def client(preview_channel):
    """A Flask test client wired to a tmp_path opcomm dir with a 2-cam whitelist (no server)."""
    from segugio.ui.app import create_app

    app = create_app(str(preview_channel["dir"]), cam_ids=["cam_wide", "cam_long"])
    app.config.update(TESTING=True)
    return app.test_client(), preview_channel


def _html(client) -> str:
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


_NODE = shutil.which("node")
requires_node = pytest.mark.skipif(_NODE is None, reason="node not on PATH (JS-exercised parity)")


def _extract_block(html: str, name: str) -> str:
    """Pull a ``// ===== gsd:<name>:start ===== ... :end =====`` JS block out of the served HTML."""
    pat = (
        r"// ===== gsd:" + re.escape(name) + r":start =====\n"
        r"(.*?)"
        r"\s*// ===== gsd:" + re.escape(name) + r":end ====="
    )
    m = re.search(pat, html, re.DOTALL)
    assert m, f"JS block gsd:{name} not found in served console.html"
    return m.group(1)


def _run_node(js_defs: str, call_js: str):
    """Run extracted JS defs + a JSON-printing call through node; return the parsed JSON result.

    node emits a UTF-8 Buffer; we capture raw bytes and decode UTF-8 explicitly so non-ASCII
    overlay/reason chars (``→`` ``…``) survive on a Windows console codepage (cp1252) host.
    """
    script = (
        js_defs
        + "\nprocess.stdout.write(Buffer.from(JSON.stringify(" + call_js + "), 'utf8'));\n"
    )
    # Write the script to a UTF-8 temp file and run `node <file>` — passing non-ASCII JS via
    # `node -e` on a cp1252 Windows console mangles `→`/`…` on the command line. The file path
    # round-trips bytes losslessly; node reads source as UTF-8 by default.
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "mirror.mjs"
        sp.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [_NODE, str(sp)],
            capture_output=True,
            text=False,  # raw bytes — decode UTF-8 ourselves (host codepage is not UTF-8)
            timeout=30,
        )
    assert proc.returncode == 0, (
        "node failed: " + proc.stderr.decode("utf-8", "replace")
        + "\n--- script ---\n" + script
    )
    return json.loads(proc.stdout.decode("utf-8"))


# --- WHY-01 reason → plain Italian (JS-exercised) ---------------------------- #


@requires_node
def test_reason_strings_italian(client):
    """``reasonToItalian`` (executed in node) yields the exact UI-SPEC Italian string per reason."""
    html = _html(client)
    defs = _extract_block(html, "why-mirror")
    expected = {
        "auto": "Auto: miglior inquadratura",
        "override": "Override operatore",
        "subject-lost": "Soggetto perso → SAFE",
        "feed-dead": "Feed morto → fallback",
        "fault": "Errore sistema → SAFE",
        "shutdown": "Arresto → SAFE",
        "none": "In attesa…",
        "some-future-reason": "In attesa…",  # unknown falls back to the idle copy
    }
    reasons = list(expected.keys())
    got = _run_node(defs, "[" + ",".join(json.dumps(r) for r in reasons) + "].map(reasonToItalian)")
    assert got == [expected[r] for r in reasons]


@requires_node
def test_reason_it_covers_status_reasons_source_of_truth(client):
    """REASON_IT must render a NON-PLACEHOLDER diagnostic for EVERY canonical ``_STATUS_REASONS``.

    Pins the served console copy-map to the Python source of truth: ``loop.py`` may emit any
    reason in ``_STATUS_REASONS`` (e.g. WR-09's ``"fault"``); the WHY-01 sidebar must never fall
    through to the idle ``"In attesa…"`` placeholder for one of them. Only ``"none"`` (the idle
    state) is allowed to equal that placeholder. This test FAILS if a future reason is added to
    ``_STATUS_REASONS`` without console copy, or if ``"fault"`` is dropped from REASON_IT.
    """
    from segugio.opcomm.records import _STATUS_REASONS

    IDLE = "In attesa…"
    html = _html(client)
    defs = _extract_block(html, "why-mirror")

    reasons = list(_STATUS_REASONS)
    # Run the served reasonToItalian over every canonical reason.
    got = _run_node(
        defs, "[" + ",".join(json.dumps(r) for r in reasons) + "].map(reasonToItalian)"
    )
    mapped = dict(zip(reasons, got))

    # Every documented reason except the idle "none" must map to a distinct diagnostic string
    # that is NOT the idle placeholder.
    for reason, text in mapped.items():
        if reason == "none":
            assert text == IDLE, f'"none" must render the idle placeholder, got {text!r}'
        else:
            assert text != IDLE, (
                f'reason {reason!r} falls through to the idle placeholder {IDLE!r} — '
                f"add a diagnostic to REASON_IT in console.html"
            )

    # Non-idle diagnostics must be mutually distinct (no two reasons collapse to one copy).
    diagnostics = [t for r, t in mapped.items() if r != "none"]
    assert len(set(diagnostics)) == len(diagnostics), (
        f"duplicate diagnostic copy across reasons: {diagnostics}"
    )

    # Specifically guard the gap this fix closes: "fault" → diagnostic, never the idle copy.
    assert "fault" in mapped, '"fault" missing from _STATUS_REASONS coverage'
    assert mapped["fault"] != IDLE, '"fault" must render a diagnostic, not the idle placeholder'
    assert mapped["fault"] == "Errore sistema → SAFE"


def test_reason_wired_into_pollstatus(client):
    """``renderReason`` writes the mapped string into ``#reason`` and is called from pollStatus."""
    html = _html(client)
    assert 'id="reason"' in html
    assert "renderReason" in html
    assert "reasonToItalian" in html
    # The sidebar #reason is fed the MAPPED copy, not the raw advisory tag.
    assert 'getElementById("reason")' in html
    # All six canonical reason strings are present in the served map.
    for s in (
        "Auto: miglior inquadratura",
        "Override operatore",
        "Soggetto perso → SAFE",
        "Feed morto → fallback",
        "Arresto → SAFE",
        "In attesa…",
    ):
        assert s in html, s


# --- WHY-02 leaderboard (JS-exercised + served-HTML) ------------------------- #


def test_leaderboard_css_and_wiring(client):
    """Leaderboard build wiring + the state fill classes exist; lost LABEL uses #E6E9EF."""
    html = _html(client)
    assert "buildLeaderboard" in html
    assert "Nessun dato di framing" in html
    # Fill-treatment classes (3 redundant channels).
    assert ".lb-fill.tracking" in html
    assert ".lb-fill.coast" in html
    assert ".lb-fill.lost" in html
    # The lost-row LABEL color is #E6E9EF, NEVER #6B7280 as text (checker note).
    assert ".lb-label { font-size: 0.875rem; font-weight: 700; color: #E6E9EF; }" in html
    assert "#6B7280" not in html
    # The preview loop drives the leaderboard.
    assert "buildLeaderboard(cams)" in html


@requires_node
def test_leaderboard_renders_sorted(client, tmp_path):
    """``buildLeaderboard`` (executed under jsdom-free DOM shim) sorts highest-first by score.

    We run the extracted leaderboard builder against a tiny DOM shim in node and assert the
    rows come out sorted highest-first and carry the right fill class per state.
    """
    html = _html(client)
    # Pull the buildLeaderboard function source out of the served script.
    m = re.search(r"function buildLeaderboard\(cams\) \{.*?\n    \}\n", html, re.DOTALL)
    assert m, "buildLeaderboard not found"
    fn = m.group(0)

    # Minimal DOM shim: capture appended rows + their fill class + value text.
    shim = """
    const ROWS = [];
    const CAM_LABEL = {};
    function _el() {
      return {
        className: "", dataset: {}, style: {}, _children: [], _text: "", innerHTML: "",
        set textContent(v){ this._text = v; }, get textContent(){ return this._text; },
        appendChild(c){ this._children.push(c); },
      };
    }
    let _board = null;
    const document = {
      getElementById(id){
        if (id === "leaderboard") { _board = _board || _el(); return _board; }
        return _el();
      },
      createElement(){ return _el(); },
    };
    """
    # SCV-01 source-of-truth discipline: feed the REAL published enum values
    # (ScorerStatus.value, what preview.py writes), NOT a hand-shortened "coast".
    # A future JS reversion to `=== "coast"` or an enum rename now FAILS this test.
    cams = {
        "cam_a": {"score": 0.40, "state": ScorerStatus.tracking.value},
        "cam_b": {"score": 0.81, "state": ScorerStatus.tracking.value},
        "cam_c": {"state": ScorerStatus.lost.value},
        "cam_d": {"score": 0.55, "state": ScorerStatus.coasting.value},
    }
    # Guard the discipline itself: the coasting camera must publish "coasting", never "coast".
    assert cams["cam_d"]["state"] == "coasting"
    call = (
        shim + fn
        + "\nbuildLeaderboard(" + json.dumps(cams) + ");\n"
        + "const rows = _board._children.map(r => ({"
        + "  cam: r.dataset.cam,"
        + "  fill: (r._children[1] && r._children[1]._children[0] && r._children[1]._children[0].className) || '',"
        + "  value: (r._children[2] && r._children[2]._text) || '',"
        + "}));"
    )
    rows = _run_node(call, "rows")
    # Sorted highest-first: b(.81) > d(.55) > a(.40) > c(lost, treated as -1).
    assert [r["cam"] for r in rows] == ["cam_b", "cam_d", "cam_a", "cam_c"]
    # Fill class encodes state.
    by_cam = {r["cam"]: r for r in rows}
    assert "tracking" in by_cam["cam_b"]["fill"]
    assert "coast" in by_cam["cam_d"]["fill"]
    assert "lost" in by_cam["cam_c"]["fill"]
    # Value text carries the glyphs.
    assert by_cam["cam_b"]["value"].startswith("●")
    assert "coast" in by_cam["cam_d"]["value"]
    assert "lost" in by_cam["cam_c"]["value"]


# --- WHY-04 auto-wants (served-HTML) ---------------------------------------- #


def test_auto_wants_line(client):
    """The auto-wants line + tile marker are driven only during an override."""
    html = _html(client)
    assert "renderAutoWants" in html
    assert "Auto vuole: " in html
    # Only when reason === "override" does the line render / the candidate tile get auto-wants.
    assert 'status.reason === "override"' in html
    assert '"auto-wants"' in html
    # The candidate tile marker uses setTileState(candidate, "auto-wants").
    assert 'setTileState(candidate, "auto-wants")' in html


# --- WHY-03 live bbox wired from preview (served-HTML) ----------------------- #


def test_bbox_data_wired_from_preview(client):
    """``updateBbox`` is driven from the preview loop using ``cams[cam].box``."""
    html = _html(client)
    # updateBbox called from pollPreview with the per-cam box.
    assert "updateBbox(c, (cams[c] || {}).box)" in html
    # Draw nothing when box is null (the helper hides on non-array/len!=4).
    assert "rect.style.visibility" in html
    # Overlay hidden on STALE/MORTO (CSS contract from 09-02, preserved).
    assert ".tile.dead .bbox-overlay" in html or ".tile.stale .bbox-overlay" in html


# --- SCV-02 unification note --------------------------------------------------- #
# The Phase-9 SCV-01 byte-exact JS mirror (``mirrorOverlayText``/``cleanField`` + the
# ``POST /score/preview`` drift-guard) was RETIRED in Phase 12 (plan 12-03): the console
# preview is now an ``<iframe src="/overlay?preview=1">`` of the ONE ``/overlay`` renderer,
# so console-vs-OBS drift is structurally impossible. The byte-parity that those deleted
# tests enforced now lives in ``test_ui_overlay_render.py::test_value_crosscheck`` (the
# frozen ``/static/overlay-render.js`` scvGet vs Python ``score_render._get``), and the
# iframe-embed / mirror-symbols-gone structural contract lives in
# ``test_ui_scv_unification.py``. The score-input touch contract below is unrelated to the
# mirror and is kept.


def test_scv01_score_inputs_touch_contract(client):
    """Score inputs are type=text + inputmode, with enterkeyhint + decimal helper + ,/. acceptance."""
    html = _html(client)
    # NEVER type="number" on score inputs (iOS Safari raises no numeric keypad).
    assert 'type="number"' not in html
    # inputmode present for both numeric and decimal field families.
    assert 'inputmode="numeric"' in html
    assert 'inputmode="decimal"' in html
    # enterkeyhint on fields (next + send/done).
    assert 'enterkeyhint="next"' in html
    assert 'enterkeyhint="send"' in html or 'enterkeyhint="done"' in html
    # decimal helper copy.
    assert "usa il punto (.) per i decimali" in html
