"""Phase-1 lazy-import boundary guard + logging-bootstrap idempotency (plan 01-01).

The whole point of Phase 1 is that `import segugio` (config, synth, logging) works on
a machine with NO torch / ultralytics / cyndilib / obsws-python runtime. We prove that
here by forcing those heavy modules ABSENT (sys.modules[name] = None makes importing
them raise ImportError) and asserting the Phase-1 surface still imports cleanly.

See RESEARCH.md "Pitfall 1: Heavy deps imported at module top-level".
"""

from __future__ import annotations

import importlib
import sys

import pytest

HEAVY_MODULES = ["torch", "ultralytics", "cyndilib", "obsws_python"]

# The crash-isolated console (segugio.ui) must resolve with EVEN numpy absent (Pitfall 5):
# the panel imports ONLY flask + segugio.opcomm and never decodes — so numpy/cv2/torch must
# never leak into it. numpy is a hard runtime dep for the rest of PHASE1_SURFACE (synth/framing
# legitimately import it at module top), so it is NOT in HEAVY_MODULES; it is forced absent ONLY
# in the dedicated console guard below.
CONSOLE_HEAVY_MODULES = HEAVY_MODULES + ["numpy", "cv2"]

PHASE1_SURFACE = [
    "segugio",
    "segugio.config",
    "segugio.synth",
    "segugio.logging",
    "segugio.framing",  # 02-04: the pure framing scorer joins the proven lazy-import surface
    "segugio.decision",  # 03-01: the pure FSM joins the proven lazy-import surface (transitions is light)
    "segugio.tracking",  # 04-01: the per-camera tracking layer (pure surface; cv2 lazy-imported in the heavy edge)
    "segugio.opcomm",  # 05-01: the atomic-file operator↔system channel (stdlib + loguru only)
    "segugio.ui",  # 08-01: the crash-isolated Flask console (Flask imported INSIDE create_app; opcomm-only at top)
    "segugio.ui.score_calc",  # 15-01: the pure-stdlib scoring authority (validate/compute) — RBT-08/SCC-02, must import heavy-free
    "segugio.ndi",  # 05-01: the FrameSource interface (cyndilib lazy-imported in the real impl, Wave 2)
    "segugio.obs",  # 05-01: the ObsController interface (obsws lazy-imported in the real impl, Wave 2)
    "segugio.watchdog_feed",  # 05-04: the pure feed-liveness math (math + typing only)
    "segugio.orchestrator",  # 05-06: the fault-isolated tick + D-08 deriver (heavy clients inside injected impls)
    "segugio.orchestrator.runtime",  # 05-09: the build_orchestrator compose/factory (heavy builders are LAZY)
    "segugio.__main__",  # 05-09: the `python -m segugio` entry point (light imports only at module top)
]


def _force_heavy_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every heavy dep raise ImportError on import (sys.modules[name] = None)."""
    for name in HEAVY_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


def test_heavy_deps_are_blocked_in_this_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity: the block actually makes heavy imports raise (so the guard below is real)."""
    _force_heavy_absent(monkeypatch)
    for name in HEAVY_MODULES:
        with pytest.raises(ImportError):
            importlib.import_module(name)


@pytest.mark.parametrize("module_name", PHASE1_SURFACE)
def test_phase1_surface_imports_with_heavy_deps_absent(
    monkeypatch: pytest.MonkeyPatch, module_name: str
) -> None:
    """import segugio[.config|.synth|.logging] all SUCCEED with heavy deps blocked."""
    _force_heavy_absent(monkeypatch)
    # Drop any cached Phase-1 modules so the import re-runs under the block.
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)
    module = importlib.import_module(module_name)
    assert module is not None


def test_segugio_config_imports_with_torch_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit torch-absent assertion called out in the acceptance criteria."""
    monkeypatch.setitem(sys.modules, "torch", None)
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)
    import segugio.config  # noqa: F401  — must not raise with torch blocked

    assert "segugio.config" in sys.modules


def test_console_resolves_with_heavy_stack_and_numpy_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The crash-isolated console imports AND create_app builds with torch/cv2/numpy/cyndilib/obsws
    forced absent (Pitfall 5 / D-03 RBT-04 — the panel never decodes, so it must never need numpy).
    """
    for name in CONSOLE_HEAVY_MODULES:
        monkeypatch.setitem(sys.modules, name, None)
    for cached in list(sys.modules):
        if cached == "segugio" or cached.startswith("segugio."):
            monkeypatch.delitem(sys.modules, cached, raising=False)

    import segugio.ui  # noqa: F401 — must not raise with the heavy stack + numpy blocked

    from segugio.ui.app import create_app

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(tmp, cam_ids=["cam_wide"])
        assert app is not None

        # RBT-08 / SCC-02 (Phase 15): the pure scoring authority must import under the SAME
        # heavy-absent block — `import segugio.ui.score_calc` proves it needs no torch/cv2/numpy/
        # ultralytics/cyndilib/obsws (stdlib + opcomm.records.Discipline only). A heavy import
        # sneaking into the compute brain (or anything it pulls in) would raise here.
        import segugio.ui.score_calc  # noqa: F401 — must not raise with the heavy stack + numpy blocked

        # RBT-07: serve GET /overlay-json under the SAME heavy-absent block — proves the route
        # imports ONLY Flask (in-factory) + segugio.opcomm + stdlib (time/threading), never numpy/
        # cv2/torch/cyndilib/obsws. A heavy import sneaking into the route would raise here.
        client = app.test_client()
        resp = client.get("/overlay-json")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert "gen" in payload and "server_now" in payload

        # RBT-08 (Phase 15): a POST /score round-trip must RESOLVE with the heavy stack absent —
        # the display-only route today returns 204 on success (app.py); the assertion tolerates
        # 200/204 so Phase 16 making the route authoritative does not break this crash-isolation gate.
        resp = client.post("/score", data={"discipline": "disc_tf", "prese": "3", "zona": "2", "totale": "6"})  # noqa: E501
        assert resp.status_code in (204, 200)

        # RBT-07 (Phase 11) — the NEW GET /overlay host page must also register and resolve under
        # the heavy-absent block: building create_app + the overlay_cfg injection must add no
        # module-top heavy import (a config/torch import sneaking in would have raised at the
        # `create_app` build above). The route is registered inside the factory:
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert "/overlay" in rules

        # The route renders templates/overlay.html, which is produced by plan 11-02. When it
        # exists, GET /overlay returns 200 with Cache-Control: no-store (the cross-plan acceptance);
        # until then a GET 500s on the missing template (the route is still registered + heavy-free,
        # which is what THIS gate proves). Assert the full contract only once the template ships.
        import os as _os

        _tpl = _os.path.join(
            _os.path.dirname(segugio.ui.app.__file__), "templates", "overlay.html"
        )
        if _os.path.exists(_tpl):
            resp = client.get("/overlay")
            assert resp.status_code == 200
            assert resp.headers["Cache-Control"] == "no-store"


def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging() twice does not raise and leaves exactly one sink."""
    from segugio.logging import configure_logging
    from loguru import logger

    configure_logging()
    after_first = len(logger._core.handlers)  # type: ignore[attr-defined]
    configure_logging()
    after_second = len(logger._core.handlers)  # type: ignore[attr-defined]

    assert after_first == 1, f"expected exactly one sink, got {after_first}"
    assert after_second == 1, f"second call must stay idempotent, got {after_second}"


def test_configure_logging_respects_level_arg() -> None:
    """The level argument is honored (default INFO; overridable without raising)."""
    from segugio.logging import configure_logging
    from loguru import logger

    configure_logging(level="DEBUG", force=True)
    assert len(logger._core.handlers) == 1  # type: ignore[attr-defined]
    # restore default for any later test ordering
    configure_logging(level="INFO", force=True)


# --- shared-fixture self checks (the conftest seams 01-02/03/04 consume) ---


def test_seeded_rng_is_a_numpy_generator(seeded_rng) -> None:
    """seeded_rng returns a numpy.random.Generator."""
    import numpy as np

    assert isinstance(seeded_rng, np.random.Generator)


def test_seeded_rng_is_deterministic() -> None:
    """Two generators from the same SEED produce identical first draws (TST-02 base)."""
    import numpy as np

    from tests.conftest import SEED

    a = np.random.default_rng(SEED)
    b = np.random.default_rng(SEED)
    assert np.array_equal(a.random(8), b.random(8))


def test_tmp_config_roundtrips_yaml(tmp_config) -> None:
    """tmp_config('a: 1') writes a readable YAML file that round-trips {'a': 1}."""
    import yaml

    path = tmp_config("a: 1\n")
    assert path.exists()
    assert yaml.safe_load(path.read_text()) == {"a": 1}


def test_valid_config_dict_has_expected_shape(valid_config_dict) -> None:
    """valid_config_dict is the canonical disc_dog happy-path dict 01-02 reuses."""
    assert valid_config_dict["field"]["sport"] == "disc_dog"
    # at least one SAFE camera (the cross-validator 01-02 will enforce)
    assert any(cam["is_safe"] for cam in valid_config_dict["cameras"])
    # every camera zone is covered by framing_weights[role][zone]
    weights = valid_config_dict["framing_weights"]
    for cam in valid_config_dict["cameras"]:
        for zone in cam["zones"]:
            assert zone["name"] in weights[cam["role"]]


def test_valid_config_dict_is_isolated(valid_config_dict) -> None:
    """Mutating the dict must not leak into other tests (deep-copied per request)."""
    valid_config_dict["cameras"].clear()
    assert valid_config_dict["cameras"] == []
