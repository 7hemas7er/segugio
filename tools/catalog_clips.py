"""Dev cataloguer: scan a footage directory -> clip_manifest.yaml + coverage gap report.

This is a **dev-time tool, NOT runtime code**. It runs once at ingest time when the
user drops their real footage in; it never runs in the live director loop. It:

  1. Takes the footage directory as a CLI argument (argparse) — NEVER a hardcoded
     path (the CONTEXT.md KEY DECISION: the footage path is provided at execution
     time, not at plan time).
  2. Scans the footage dir for video files, inferring the discipline from the
     sub-directory (``disc_dog/`` vs ``agility/``).
  3. Reads each clip's condition tags from a sidecar ``<clip>.tags`` file
     (comma/newline-separated condition names from the checklist).
  4. Probes each clip's metadata via opencv (``cv2.VideoCapture`` props) — imported
     LAZILY inside :func:`probe`, because ``ffprobe`` is NOT installed on this box
     (RESEARCH.md Environment Availability) and to keep the Phase-1 import surface
     clean (``import segugio`` never pulls opencv).
  5. Writes a ``clip_manifest.yaml`` and prints a **coverage gap report** — every
     missing ``{condition x discipline}`` cell over the 7x2 checklist, so the user
     knows which clips to supplement with CC0 Pexels/Pixabay footage (Pitfall 6).

It runs end-to-end with ZERO footage present: an empty dir yields an empty manifest
and an all-missing coverage report — so it is fully testable without real clips.

Usage::

    python tools/catalog_clips.py /path/to/footage \\
        --out tests/fixtures/clip_manifest.yaml

The footage layout it expects (drop binaries here; they are gitignored)::

    <footage_dir>/disc_dog/<clip>.mp4   (+ optional <clip>.tags sidecar)
    <footage_dir>/agility/<clip>.mp4    (+ optional <clip>.tags sidecar)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

# Make `segugio.fixtures` importable when this script is run directly (so the
# coverage report reuses the package-side checklist + matrix, the single source of
# truth). src/ is a sibling of tools/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from segugio.fixtures import (  # noqa: E402
    CONDITIONS,
    DISCIPLINES,
    coverage_report,
)

#: Recognised video container extensions (case-insensitive). Matches the gitignore.
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}


def probe(path: str | Path) -> dict[str, Any]:
    """Probe a clip's metadata via opencv (no ffprobe needed).

    ``cv2`` is imported LAZILY inside this function: it is the only opencv touch-point
    in Phase 1, keeping ``import segugio`` opencv-free, and ffprobe/ffmpeg are not
    installed on this box (RESEARCH.md Environment Availability) — opencv is the
    recommended probe.

    Args:
        path: Path to a video file.

    Returns:
        ``{width, height, fps, frames, duration_s}``. ``duration_s`` is
        ``frames / fps`` rounded to 2 dp, or ``None`` when ``fps`` is 0 (a corrupt /
        unreadable clip yields zeros rather than crashing — threat T-01-03d accept).
    """
    import cv2  # lazy — keeps the Phase-1 runtime import surface clean

    cap = cv2.VideoCapture(str(path))
    meta: dict[str, Any] = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": round(float(cap.get(cv2.CAP_PROP_FPS)), 3),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    meta["duration_s"] = (
        round(meta["frames"] / meta["fps"], 2) if meta["fps"] else None
    )
    return meta


def _read_tags(clip_path: Path) -> list[str]:
    """Read condition tags from a ``<clip>.tags`` sidecar (comma/newline-separated).

    Unknown tags (not in :data:`CONDITIONS`) are dropped with a warning so a typo
    never silently inflates coverage. A missing sidecar yields no tags (the clip is
    catalogued but contributes to no coverage cell — surfacing it as an untagged gap).
    """
    sidecar = clip_path.with_suffix(".tags")
    if not sidecar.exists():
        return []
    raw = sidecar.read_text(encoding="utf-8")
    tokens = [t.strip() for chunk in raw.splitlines() for t in chunk.split(",")]
    tags: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token not in CONDITIONS:
            logger.warning(
                "clip {} has unknown condition tag {!r} (not in the checklist) — ignored",
                clip_path.name,
                token,
            )
            continue
        if token not in tags:
            tags.append(token)
    return tags


def _infer_discipline(rel_path: Path) -> str | None:
    """Infer the discipline from the top-level sub-directory of the footage tree."""
    parts = rel_path.parts
    if parts and parts[0] in DISCIPLINES:
        return parts[0]
    return None


def catalog(footage_dir: str | Path, out_manifest: str | Path) -> dict[str, Any]:
    """Scan a footage dir, probe each clip, and write a ``clip_manifest.yaml``.

    Discipline is inferred from the sub-directory (``disc_dog/`` / ``agility/``);
    condition tags come from a per-clip ``.tags`` sidecar; metadata comes from
    :func:`probe`. Clip ``file`` paths are stored RELATIVE to the footage root (so the
    manifest is portable and the package-side resolver joins them under the fixtures
    root). An empty footage dir yields ``{"clips": []}`` — and a written manifest.

    Args:
        footage_dir: The user-provided footage root (a CLI arg — NEVER hardcoded).
        out_manifest: Where to write the manifest YAML.

    Returns:
        The manifest dict that was written.
    """
    footage = Path(footage_dir)
    if not footage.exists():
        raise FileNotFoundError(f"footage directory not found: {footage}")

    clips: list[dict[str, Any]] = []
    for path in sorted(footage.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        rel = path.relative_to(footage)
        discipline = _infer_discipline(rel)
        if discipline is None:
            logger.warning(
                "clip {} is not under a known discipline sub-dir ({}) — skipped",
                rel,
                "/".join(DISCIPLINES),
            )
            continue

        try:
            metadata = probe(path)
        except Exception as exc:  # noqa: BLE001 — a bad clip must not abort the whole scan
            logger.warning("could not probe {}: {} — recording zero metadata", rel, exc)
            metadata = {"width": 0, "height": 0, "fps": 0.0, "frames": 0, "duration_s": None}

        clips.append(
            {
                "file": rel.as_posix(),  # POSIX-relative path (OS-agnostic in YAML)
                "discipline": discipline,
                "conditions": _read_tags(path),
                "source": "user_footage",
                "license": "user_consent_README",
                "notes": "",
                "metadata": metadata,
            }
        )

    manifest: dict[str, Any] = {"clips": clips}

    out = Path(out_manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("wrote {} clip(s) to {}", len(clips), out)
    return manifest


def coverage_gaps(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """Return every missing ``(discipline, condition)`` cell from the coverage matrix.

    These are the gaps the user must supplement (Pitfall 6). An empty corpus returns
    the full ``CONDITIONS x DISCIPLINES`` grid; a fully-covered corpus returns ``[]``.
    """
    report = coverage_report(manifest)
    gaps: list[tuple[str, str]] = []
    for discipline in DISCIPLINES:
        for condition in CONDITIONS:
            if not report[discipline][condition]:
                gaps.append((discipline, condition))
    return gaps


def format_coverage_report(manifest: dict[str, Any]) -> str:
    """Render a human-readable coverage gap report (matrix + missing-cell list)."""
    report = coverage_report(manifest)
    lines = ["", "Condition-coverage report (covered = ✓, missing = ✗):", ""]
    header = f"  {'condition':<26}" + "".join(f"{d:>12}" for d in DISCIPLINES)
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for condition in CONDITIONS:
        row = f"  {condition:<26}"
        for discipline in DISCIPLINES:
            row += f"{('✓' if report[discipline][condition] else '✗'):>12}"
        lines.append(row)

    gaps = coverage_gaps(manifest)
    lines.append("")
    if gaps:
        lines.append(f"MISSING {len(gaps)} cell(s) — supplement with CC0 Pexels/Pixabay clips:")
        for discipline, condition in gaps:
            lines.append(f"  - {discipline} / {condition}")
    else:
        lines.append("All condition x discipline cells covered.")
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Catalogue a footage directory into a clip manifest + coverage gap report. "
            "The footage path is supplied here at execution time — never hardcoded."
        )
    )
    parser.add_argument(
        "footage_dir",
        type=Path,
        help="Path to the footage root (expects disc_dog/ and agility/ sub-dirs).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tests/fixtures/clip_manifest.yaml"),
        help="Where to write the manifest (default: tests/fixtures/clip_manifest.yaml).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: catalogue the footage dir, then print the coverage gap report."""
    args = _parse_args(argv)
    manifest = catalog(args.footage_dir, args.out)
    print(format_coverage_report(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
