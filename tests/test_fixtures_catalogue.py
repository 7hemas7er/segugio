"""TST-01 — curated clip-set substrate tests.

Two surfaces under test:

  * ``segugio.fixtures`` (package-side, importable by P2/P3/P4 with opencv ABSENT):
    ``load_manifest`` (yaml.safe_load), ``select_clips`` (filter by discipline +
    conditions), ``coverage_report`` (discipline x condition boolean matrix),
    ``resolve_clip_path`` (path resolved RELATIVE to the fixtures root, traversal-safe,
    clear "not present locally" signal for a missing binary), and the CONDITIONS /
    DISCIPLINES checklist constants.

  * ``tools.catalog_clips`` (DEV tool): ``probe`` (lazy ``import cv2`` — mocked here so
    the suite runs with opencv uninstalled), ``catalog`` (scan a footage dir, infer
    discipline from the sub-dir, read condition tags from a sidecar, probe metadata,
    build a manifest), and the coverage gap report over the 7x2 checklist.

The cataloguer must run end-to-end with ZERO footage present (empty dir -> empty
manifest + an all-missing coverage report), so these tests need no real video and
no opencv install.
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

import segugio.fixtures as fx

# tools/ is a sibling of src/ and tests/ — add the repo root so `import tools.*` works
# regardless of cwd. (pythonpath=["src"] only exposes the package, not tools/.)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.catalog_clips as catalog_clips  # noqa: E402


# --------------------------------------------------------------------------- #
# Checklist constants
# --------------------------------------------------------------------------- #


def test_conditions_cover_the_full_checklist() -> None:
    expected = {
        "multi_dog",
        "handler_prominent",
        "tunnel_contact_occlusion",
        "jump_sprint_blur",
        "distant",
        "backlit_dusk",
        "midfield_equidistant",
    }
    assert set(fx.CONDITIONS) == expected
    assert set(fx.DISCIPLINES) == {"disc_dog", "agility"}


def test_fixtures_module_imports_without_opencv() -> None:
    # The package-side query API must never pull opencv. Prove it in a subprocess
    # where cv2 is poisoned to None — `import segugio.fixtures` must still succeed.
    code = (
        "import sys; sys.modules['cv2'] = None; "
        "import segugio.fixtures as f; "
        "assert hasattr(f, 'load_manifest') and hasattr(f, 'select_clips'); "
        "print('ok')"
    )
    env_run = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT / "src"),
    )
    assert env_run.returncode == 0, env_run.stderr
    assert "ok" in env_run.stdout


# --------------------------------------------------------------------------- #
# probe() — opencv mocked (no real cv2 / no real clip needed)
# --------------------------------------------------------------------------- #


def _install_fake_cv2(monkeypatch, *, width, height, fps, frames) -> None:
    """Inject a minimal fake ``cv2`` exposing the CAP_PROP_* constants + a
    VideoCapture returning the given probe values."""

    class _FakeCapture:
        def __init__(self, path):
            self._props = {
                fake_cv2.CAP_PROP_FRAME_WIDTH: float(width),
                fake_cv2.CAP_PROP_FRAME_HEIGHT: float(height),
                fake_cv2.CAP_PROP_FPS: float(fps),
                fake_cv2.CAP_PROP_FRAME_COUNT: float(frames),
            }

        def get(self, prop):
            return self._props.get(prop, 0.0)

        def isOpened(self):  # noqa: N802 (cv2 API name)
            return True

        def release(self):
            pass

    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.CAP_PROP_FRAME_WIDTH = 3
    fake_cv2.CAP_PROP_FRAME_HEIGHT = 4
    fake_cv2.CAP_PROP_FPS = 5
    fake_cv2.CAP_PROP_FRAME_COUNT = 7
    fake_cv2.VideoCapture = _FakeCapture
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)


def test_probe_returns_metadata_with_duration(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, width=1920, height=1080, fps=30.0, frames=300)
    meta = catalog_clips.probe("whatever.mp4")
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["fps"] == 30.0
    assert meta["frames"] == 300
    assert meta["duration_s"] == pytest.approx(10.0)


def test_probe_duration_none_when_fps_zero(monkeypatch) -> None:
    _install_fake_cv2(monkeypatch, width=640, height=480, fps=0.0, frames=100)
    meta = catalog_clips.probe("broken.mp4")
    assert meta["duration_s"] is None


# --------------------------------------------------------------------------- #
# catalog() — scans a temp dir of fake clips + sidecar tags, mocked probe
# --------------------------------------------------------------------------- #


def test_catalog_builds_manifest_entries(monkeypatch, tmp_path: Path) -> None:
    footage = tmp_path / "footage"
    (footage / "disc_dog").mkdir(parents=True)
    (footage / "agility").mkdir(parents=True)

    # Two fake clips with sidecar .tags listing their conditions.
    dd = footage / "disc_dog" / "toss_01.mp4"
    dd.write_bytes(b"\x00")
    (footage / "disc_dog" / "toss_01.tags").write_text(
        "multi_dog, handler_prominent\n", encoding="utf-8"
    )
    ag = footage / "agility" / "run_01.mp4"
    ag.write_bytes(b"\x00")
    (footage / "agility" / "run_01.tags").write_text(
        "tunnel_contact_occlusion\n", encoding="utf-8"
    )

    # Mock probe so we don't need opencv / a real video.
    monkeypatch.setattr(
        catalog_clips,
        "probe",
        lambda p: {"width": 1920, "height": 1080, "fps": 30.0, "frames": 60, "duration_s": 2.0},
    )

    out = tmp_path / "clip_manifest.yaml"
    manifest = catalog_clips.catalog(footage, out)

    clips = manifest["clips"]
    assert len(clips) == 2
    by_disc = {c["discipline"]: c for c in clips}
    assert set(by_disc) == {"disc_dog", "agility"}

    dd_entry = by_disc["disc_dog"]
    # discipline inferred from sub-dir; conditions from the sidecar; metadata from probe.
    assert dd_entry["discipline"] == "disc_dog"
    assert "multi_dog" in dd_entry["conditions"]
    assert "handler_prominent" in dd_entry["conditions"]
    assert dd_entry["metadata"]["width"] == 1920
    # path is RELATIVE to the fixtures root (no absolute, no leading drive/slash).
    assert dd_entry["file"] == "disc_dog/toss_01.mp4"
    assert not Path(dd_entry["file"]).is_absolute()

    # The manifest file was written and re-parses.
    assert out.exists()
    reloaded = fx.load_manifest(out)
    assert len(reloaded["clips"]) == 2


def test_catalog_empty_dir_yields_empty_manifest_and_all_missing_coverage(
    tmp_path: Path,
) -> None:
    footage = tmp_path / "empty_footage"
    footage.mkdir()
    out = tmp_path / "clip_manifest.yaml"

    manifest = catalog_clips.catalog(footage, out)
    assert manifest["clips"] == []

    report = fx.coverage_report(manifest)
    # Every {discipline x condition} cell is missing.
    for discipline in fx.DISCIPLINES:
        for cond in fx.CONDITIONS:
            assert report[discipline][cond] is False

    gaps = catalog_clips.coverage_gaps(manifest)
    # 7 conditions x 2 disciplines = 14 missing cells, all flagged.
    assert len(gaps) == len(fx.CONDITIONS) * len(fx.DISCIPLINES)


# --------------------------------------------------------------------------- #
# select_clips() / coverage_report() / load_manifest()
# --------------------------------------------------------------------------- #


def _sample_manifest() -> dict:
    return {
        "clips": [
            {
                "file": "disc_dog/a.mp4",
                "discipline": "disc_dog",
                "conditions": ["multi_dog", "handler_prominent"],
                "source": "user_footage",
                "license": "user_consent_README",
                "metadata": {"width": 1920, "height": 1080, "fps": 30.0, "duration_s": 5.0},
            },
            {
                "file": "agility/b.mp4",
                "discipline": "agility",
                "conditions": ["tunnel_contact_occlusion", "jump_sprint_blur"],
                "source": "user_footage",
                "license": "user_consent_README",
                "metadata": {"width": 1280, "height": 720, "fps": 25.0, "duration_s": 3.0},
            },
        ]
    }


def test_select_clips_filters_by_discipline_and_conditions() -> None:
    m = _sample_manifest()
    hits = fx.select_clips(m, discipline="agility", conditions=["tunnel_contact_occlusion"])
    assert len(hits) == 1
    assert hits[0]["file"] == "agility/b.mp4"


def test_select_clips_requires_all_requested_conditions() -> None:
    m = _sample_manifest()
    # agility/b has tunnel + jump but NOT distant -> no match when distant requested.
    assert fx.select_clips(m, discipline="agility", conditions=["tunnel_contact_occlusion", "distant"]) == []


def test_select_clips_empty_filter_returns_all() -> None:
    m = _sample_manifest()
    assert len(fx.select_clips(m)) == 2


def test_coverage_report_marks_present_and_missing_cells() -> None:
    m = _sample_manifest()
    report = fx.coverage_report(m)
    # disc_dog covers multi_dog; agility covers tunnel; neither covers backlit_dusk.
    assert report["disc_dog"]["multi_dog"] is True
    assert report["agility"]["tunnel_contact_occlusion"] is True
    assert report["agility"]["backlit_dusk"] is False
    assert report["disc_dog"]["midfield_equidistant"] is False


def test_load_manifest_uses_safe_load_and_parses(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    p.write_text(
        "clips:\n"
        "  - file: disc_dog/x.mp4\n"
        "    discipline: disc_dog\n"
        "    conditions: [distant]\n",
        encoding="utf-8",
    )
    m = fx.load_manifest(p)
    assert m["clips"][0]["discipline"] == "disc_dog"


def test_load_manifest_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        fx.load_manifest(tmp_path / "does_not_exist.yaml")


# --------------------------------------------------------------------------- #
# resolve_clip_path() — traversal-safe, clear "not present locally" signal
# --------------------------------------------------------------------------- #


def test_resolve_clip_path_missing_binary_signals_not_present(tmp_path: Path) -> None:
    # A manifest entry whose binary is absent must NOT crash — it signals absence.
    fixtures_root = tmp_path / "fixtures"
    fixtures_root.mkdir()
    with pytest.raises(fx.FixtureNotPresentError):
        fx.resolve_clip_path("disc_dog/ghost.mp4", fixtures_root=fixtures_root)


def test_resolve_clip_path_returns_path_for_present_binary(tmp_path: Path) -> None:
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "disc_dog").mkdir(parents=True)
    real = fixtures_root / "disc_dog" / "here.mp4"
    real.write_bytes(b"\x00")
    resolved = fx.resolve_clip_path("disc_dog/here.mp4", fixtures_root=fixtures_root)
    assert resolved == real.resolve()


def test_resolve_clip_path_rejects_traversal(tmp_path: Path) -> None:
    # T-01-03a: a `..` entry that escapes the fixtures root is refused, not resolved.
    fixtures_root = tmp_path / "fixtures"
    fixtures_root.mkdir()
    with pytest.raises(ValueError):
        fx.resolve_clip_path("../../etc/passwd", fixtures_root=fixtures_root)


# --------------------------------------------------------------------------- #
# Task 2 — README (license/consent), example manifest, gitignore policy proof
# --------------------------------------------------------------------------- #

_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures"
_README = _FIXTURES_DIR / "README.md"
_EXAMPLE_MANIFEST = _FIXTURES_DIR / "clip_manifest.example.yaml"


def test_fixtures_readme_exists_and_documents_license() -> None:
    assert _README.exists(), f"missing {_README}"
    text = _README.read_text(encoding="utf-8")
    assert "## License" in text
    # Documents the ingest procedure referencing the cataloguer.
    assert "tools/catalog_clips.py" in text


def test_fixtures_readme_has_no_hardcoded_absolute_path() -> None:
    # The footage path is supplied at execution time — no absolute path (POSIX `/...`
    # or Windows `X:\...`) may be baked into the README.
    text = _README.read_text(encoding="utf-8")
    for line in text.splitlines():
        assert not line.startswith("/"), f"absolute POSIX path in README: {line!r}"
        # crude Windows drive-letter check: a single letter + ':\'
        assert not (len(line) >= 3 and line[0].isalpha() and line[1] == ":" and line[2] == "\\"), (
            f"absolute Windows path in README: {line!r}"
        )


def test_example_manifest_parses_and_spans_both_disciplines() -> None:
    assert _EXAMPLE_MANIFEST.exists(), f"missing {_EXAMPLE_MANIFEST}"
    manifest = fx.load_manifest(_EXAMPLE_MANIFEST)
    clips = manifest["clips"]
    assert len(clips) >= 2
    disciplines = {c["discipline"] for c in clips}
    assert disciplines == {"disc_dog", "agility"}, disciplines


def test_example_manifest_works_with_query_api() -> None:
    manifest = fx.load_manifest(_EXAMPLE_MANIFEST)
    # select_clips filters by discipline + conditions.
    agility_tunnel = fx.select_clips(
        manifest, discipline="agility", conditions=["tunnel_contact_occlusion"]
    )
    assert len(agility_tunnel) >= 1
    # coverage_report yields the full grid with at least one covered + one missing cell.
    report = fx.coverage_report(manifest)
    flat = [report[d][c] for d in fx.DISCIPLINES for c in fx.CONDITIONS]
    assert any(flat) and not all(flat)


def _git_check_ignore(rel_path: str) -> bool:
    """True if git ignores ``rel_path`` (run from the repo root)."""
    result = subprocess.run(
        ["git", "check-ignore", rel_path],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    # exit 0 + the path echoed -> ignored; exit 1 + empty -> not ignored.
    return result.returncode == 0 and result.stdout.strip() != ""


def test_gitignore_ignores_binaries_but_keeps_readme_and_manifest() -> None:
    # Binaries under the fixtures tree are ignored (external-dir pattern, Pitfall 4)...
    assert _git_check_ignore("tests/fixtures/disc_dog/sample.mp4")
    assert _git_check_ignore("tests/fixtures/agility/run.mov")
    # ...while the README and the committed manifest are NOT ignored.
    assert not _git_check_ignore("tests/fixtures/README.md")
    assert not _git_check_ignore("tests/fixtures/clip_manifest.yaml")
