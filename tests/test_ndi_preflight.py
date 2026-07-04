"""Fix #6 (T-9l5-07) — a startup NDI discovery doctor emits a per-camera "NOT FOUND" error.

PURE-FAKE tests (unmarked): ``_diagnose_sources`` is the cyndilib-free core, and ``preflight``
takes an injectable ``finder`` collaborator (mirroring the ``_run_receiver`` seam) so the doctor is
driven headless with a fake finder. Before this fix, ``_resolve_source`` did a literal
``source_name in names`` and silently coasted on any miss — a drifted/near-miss configured
``ndi_source`` never resolved and the operator got no signal ("OBS sees it but the console is
blank"). The doctor now surfaces every missing source as a clear operator ERROR at startup.
"""

from __future__ import annotations

from loguru import logger

from segugio.ndi.ndi_source import NdiFrameSource, _diagnose_sources


def test_diagnose_sources_splits_found_and_missing():
    """_diagnose_sources: exact-match membership → found vs missing (the same match _resolve uses)."""
    report = _diagnose_sources(
        {"cam_wide": "MASTER (X)", "cam_long": "MASTER (Y)"},
        ["MASTER (X)"],
    )
    assert report["missing"] == {"cam_long": "MASTER (Y)"}
    assert report["found"] == {"cam_wide": "MASTER (X)"}


def test_diagnose_sources_all_present_no_missing():
    """When every configured source is discovered, missing is empty."""
    report = _diagnose_sources(
        {"cam_wide": "MASTER (X)"},
        ["MASTER (X)", "OTHER (Z)"],
    )
    assert report["missing"] == {}
    assert report["found"] == {"cam_wide": "MASTER (X)"}


class _FakeFinder:
    """A cyndilib-Finder-shaped fake whose advertised names are scripted (get_source_names)."""

    def __init__(self, names):
        self._names = list(names)

    def get_source_names(self):
        return list(self._names)


def _two_cameras():
    from segugio.config import Role
    from segugio.config.models import Camera, Zone

    return [
        Camera(
            id="cam_wide", role=Role.main_wide, obs_scene="WIDE", is_safe=True,
            ndi_source="MASTER (X)", zones=[Zone(name="field", rect=[0.0, 0.0, 1.0, 1.0])],
        ),
        Camera(
            id="cam_long", role=Role.long, obs_scene="LONG", is_safe=False,
            ndi_source="MASTER (Y)", zones=[Zone(name="field", rect=[0.0, 0.0, 1.0, 1.0])],
        ),
    ]


def test_preflight_logs_not_found_error_for_missing_source():
    """preflight emits a clear per-camera ERROR naming the missing source (not a silent coast)."""
    src = NdiFrameSource(_two_cameras())
    # cam_long's "MASTER (Y)" is absent from discovery → it must be reported missing + logged.
    finder = _FakeFinder(names=["MASTER (X)"])

    captured: list[str] = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="ERROR")
    try:
        report = src.preflight(wait_s=0.0, finder=finder)
    finally:
        logger.remove(sink_id)

    assert report["missing"] == {"cam_long": "MASTER (Y)"}
    assert report["found"] == {"cam_wide": "MASTER (X)"}
    joined = "\n".join(captured)
    assert "NOT FOUND" in joined, f"expected a NOT-FOUND operator error, got {captured}"
    assert "MASTER (Y)" in joined, "the missing source name must appear in the error"


def test_preflight_all_found_logs_no_error():
    """When every configured source is discovered, preflight emits NO error line."""
    src = NdiFrameSource(_two_cameras())
    finder = _FakeFinder(names=["MASTER (X)", "MASTER (Y)"])

    captured: list[str] = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="ERROR")
    try:
        report = src.preflight(wait_s=0.0, finder=finder)
    finally:
        logger.remove(sink_id)

    assert report["missing"] == {}
    assert captured == [], f"no ERROR should be logged when all sources are found, got {captured}"


def test_preflight_coasts_on_finder_fault():
    """A finder that raises → preflight coasts to an empty report, never raises into startup."""
    class _BrokenFinder:
        def get_source_names(self):
            raise RuntimeError("finder blew up")

    src = NdiFrameSource(_two_cameras())
    # get_source_names raising is caught internally → names=[] → both sources reported missing,
    # and preflight returns a report rather than propagating (RBT-04).
    report = src.preflight(wait_s=0.0, finder=_BrokenFinder())
    assert report["missing"] == {"cam_wide": "MASTER (X)", "cam_long": "MASTER (Y)"}
