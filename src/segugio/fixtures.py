"""Clip-manifest loader + query API for the curated multi-condition fixture corpus.

This is the **package-side** half of the clip-set substrate (TST-01): later phases
(P2 scorer / P3 tracker / P4 orchestrator tests) import it to select fixtures by
``{condition, discipline}`` and to resolve a clip's path on disk. It is deliberately
*light* — it imports nothing heavy. In particular it never imports ``opencv`` /
``cv2`` (metadata probing lives only in the dev cataloguer ``tools/catalog_clips.py``),
so ``import segugio.fixtures`` succeeds on any machine with no GPU / no opencv.

The condition checklist (BOTH disciplines) is the contract from PITFALLS.md /
RESEARCH.md — the cells the corpus must cover so later phases' hard cases stay tested:

    multi_dog, handler_prominent, tunnel_contact_occlusion, jump_sprint_blur,
    distant, backlit_dusk, midfield_equidistant      (x  disc_dog, agility)

Manifest schema (committed ``tests/fixtures/clip_manifest.yaml``; binaries gitignored)::

    clips:
      - file: disc_dog/<name>.mp4   # path RELATIVE to tests/fixtures/
        discipline: disc_dog | agility
        event: <profile event>      # optional
        conditions: [<subset of CONDITIONS>]
        source: user_footage | pexels | pixabay | yt_dlp_cc
        license: user_consent_README | cc0 | <ref into README>
        notes: <free text>
        metadata: { width, height, fps, frames, duration_s }   # from the opencv probe
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

__all__ = [
    "CONDITIONS",
    "DISCIPLINES",
    "FixtureNotPresentError",
    "load_manifest",
    "select_clips",
    "coverage_report",
    "resolve_clip_path",
]

# --------------------------------------------------------------------------- #
# The condition / discipline checklist (the TST-01 contract).
# --------------------------------------------------------------------------- #

#: The 7 conditions the corpus must cover for BOTH disciplines (PITFALLS.md checklist).
CONDITIONS: list[str] = [
    "multi_dog",
    "handler_prominent",
    "tunnel_contact_occlusion",
    "jump_sprint_blur",
    "distant",
    "backlit_dusk",
    "midfield_equidistant",
]

#: The two disciplines the clip set spans.
DISCIPLINES: list[str] = ["disc_dog", "agility"]

#: Default committed manifest location (resolved relative to this package's repo).
#: ``tests/fixtures/clip_manifest.yaml`` lives at the repo root, three parents up from
#: ``src/segugio/fixtures.py``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = _REPO_ROOT / "tests" / "fixtures" / "clip_manifest.yaml"
DEFAULT_FIXTURES_ROOT = _REPO_ROOT / "tests" / "fixtures"


class FixtureNotPresentError(FileNotFoundError):
    """Raised when a manifest entry references a clip binary that is not on disk.

    The binaries are intentionally gitignored (external-dir + committed-manifest
    pattern), so a fresh checkout has the manifest but not the footage. This typed
    error lets callers distinguish "the footage hasn't been dropped in locally" from
    a genuine bug — a clear signal, not a crash.
    """


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    """Parse a clip manifest YAML into a dict via ``yaml.safe_load`` (never ``yaml.load``).

    Args:
        path: Manifest path. Defaults to the committed
            ``tests/fixtures/clip_manifest.yaml``.

    Returns:
        The parsed manifest dict (``{"clips": [...]}``). An empty / missing-``clips``
        file yields ``{"clips": []}`` so callers can iterate unconditionally.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        yaml.YAMLError: if the file is not valid YAML.
    """
    p = Path(path) if path is not None else DEFAULT_MANIFEST
    if not p.exists():
        raise FileNotFoundError(f"clip manifest not found: {p}")
    # safe_load only — the manifest is parsed input; never deserialize arbitrary objects.
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "clips" not in data or data["clips"] is None:
        data["clips"] = []
    return data


def select_clips(
    manifest: dict[str, Any],
    discipline: str | None = None,
    conditions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter manifest entries by discipline and required conditions.

    An entry matches when its ``discipline`` equals ``discipline`` (if given) AND its
    ``conditions`` is a superset of every condition in ``conditions`` (if given). An
    empty filter (both ``None``) returns all clips.

    Args:
        manifest: A manifest dict (from :func:`load_manifest`).
        discipline: Restrict to this discipline, or ``None`` for any.
        conditions: Require ALL of these conditions to be present, or ``None`` for any.

    Returns:
        The matching clip entries, in manifest order.
    """
    required = set(conditions or [])
    out: list[dict[str, Any]] = []
    for entry in manifest.get("clips", []):
        if discipline is not None and entry.get("discipline") != discipline:
            continue
        entry_conditions = set(entry.get("conditions", []) or [])
        if not required.issubset(entry_conditions):
            continue
        out.append(entry)
    return out


def coverage_report(manifest: dict[str, Any]) -> dict[str, dict[str, bool]]:
    """Build the ``discipline -> condition -> covered?`` boolean matrix.

    A cell is ``True`` when at least one clip of that discipline is tagged with that
    condition. This is the source for the cataloguer's coverage *gap* report — every
    ``False`` cell is a ``{condition x discipline}`` the corpus is missing and the user
    should supplement (Pitfall 6: condition-checklist drift).

    Args:
        manifest: A manifest dict (from :func:`load_manifest`).

    Returns:
        ``{discipline: {condition: bool}}`` over the full CONDITIONS x DISCIPLINES grid.
    """
    # Union of tagged conditions per discipline.
    tagged: dict[str, set[str]] = {d: set() for d in DISCIPLINES}
    for entry in manifest.get("clips", []):
        disc = entry.get("discipline")
        if disc in tagged:
            tagged[disc].update(entry.get("conditions", []) or [])

    return {
        discipline: {cond: (cond in tagged[discipline]) for cond in CONDITIONS}
        for discipline in DISCIPLINES
    }


def resolve_clip_path(
    file: str,
    fixtures_root: str | Path | None = None,
) -> Path:
    """Resolve a manifest ``file`` entry to an absolute path under the fixtures root.

    The path is resolved RELATIVE to ``fixtures_root`` (default
    ``tests/fixtures/``). Path-traversal is refused: an entry that escapes the
    fixtures root (e.g. ``../../etc/passwd``) raises ``ValueError`` rather than
    resolving outside the corpus (threat T-01-03a). A well-formed entry whose binary
    is simply absent raises :class:`FixtureNotPresentError` — a clear "fixture not
    present locally" signal, since the binaries are gitignored.

    Args:
        file: The manifest entry's ``file`` (relative to the fixtures root).
        fixtures_root: The corpus root. Defaults to ``tests/fixtures/``.

    Returns:
        The resolved absolute :class:`~pathlib.Path` to the clip binary.

    Raises:
        ValueError: if ``file`` escapes ``fixtures_root`` (traversal) or is absolute.
        FixtureNotPresentError: if the resolved binary does not exist on disk.
    """
    root = Path(fixtures_root) if fixtures_root is not None else DEFAULT_FIXTURES_ROOT
    root = root.resolve()

    candidate = Path(file)
    if candidate.is_absolute():
        raise ValueError(f"clip path must be relative to the fixtures root, got absolute: {file!r}")

    resolved = (root / candidate).resolve()
    # Containment check: resolved must be inside the fixtures root (boundary-safe).
    if resolved != root and root not in resolved.parents:
        raise ValueError(
            f"clip path {file!r} escapes the fixtures root {root} (path traversal refused)"
        )

    if not resolved.exists():
        logger.warning(
            "fixture not present locally: {} (binaries are gitignored — drop footage "
            "into {} and re-run the cataloguer)",
            file,
            root,
        )
        raise FixtureNotPresentError(
            f"fixture not present locally: {file!r} (expected at {resolved}). "
            "Video binaries are gitignored; drop the footage in and re-catalogue."
        )
    return resolved
