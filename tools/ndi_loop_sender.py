"""Dev tool: loop local recorded clips as named NDI sources (no-phones loop test).

This is a **dev-time tool, NOT runtime code**. It stands in for the iPhone HX3 feeds:
one cyndilib ``Sender`` per camera publishes a looping recorded clip under the config
``Camera.ndi_source`` name, so the real cyndilib RECEIVE path (``NdiFrameSource``) — and
the whole pipeline behind it (AI tracking -> OBS scene switching) — is exercised
end-to-end WITHOUT a phone rig. Mirror of ``segugio.ndi.mock_sender.publish_clip``, but
looping and multi-camera (one daemon thread per camera).

Lazy-import boundary (project convention): ``cv2`` and every ``cyndilib`` symbol are
imported INSIDE :func:`decode_clip` / :func:`publish_loop`, so ``import
tools.ndi_loop_sender`` succeeds with cv2/cyndilib ABSENT. Only argparse / pathlib /
sys / threading / time / re / socket / loguru and the light ``load_config`` are imported
at module top.

Prerequisites (these are a RUNBOOK concern, NOT something this tool does — see
``docs/looptest.md``):
  - The NDI Discovery Server must be RUNNING. Plain mDNS is broken on this box
    (Tailscale interferes), so discovery must be served from 127.0.0.1.
  - ``%APPDATA%/NDI/ndi-config.v1.json`` must contain
    ``{"ndi":{"networks":{"discovery":"127.0.0.1"}}}`` so cyndilib's finder/sender use
    the discovery server instead of mDNS.

MASTER host-prefix gotcha:
  A cyndilib ``Sender("FOO")`` is DISCOVERABLE on the network as ``"<HOST> (FOO)"``.
  This box's NDI host is ``MASTER`` (``socket.gethostname()`` == ``"Master"``, NDI
  uppercases it). So the published stream name we hand to ``Sender(...)`` is the BARE
  phone stream (e.g. ``"PHONE-WIDE (NDI HX3)"``), which the network re-forms back into
  the config ``ndi_source`` ``"MASTER (PHONE-WIDE (NDI HX3))"``. :func:`stream_name_from_ndi_source`
  strips the host prefix; :func:`expected_discoverable` re-applies it for the banner check.

Two modes:
  - DEFAULT (per-camera files): each camera gets its own ``cam_<id>_*.<ext>`` clip from
    ``--clips-dir``.
  - CROPS (``--crops-from CLIP``): ONE base clip is published as N different role-based
    crops (one per camera) — wide / far-band / near-band / centre. As the dog moves through
    the field, a different camera's crop frames it best, so the director switches continuously.
    Override a crop with ``--crop CAMID=x0,y0,x1,y1`` (normalized); ``--phase-shift`` also
    time-staggers the feeds for extra rotation.

Usage::

    # per-camera files
    venv/Scripts/python tools/ndi_loop_sender.py \\
        --config config.looptest.yaml --clips-dir tests/fixtures/looptest

    # 1 clip -> 4 crops (continuous switching demo)
    venv/Scripts/python tools/ndi_loop_sender.py \\
        --config config.looptest.yaml \\
        --crops-from tests/fixtures/looptest/cam_wide_9898282.mp4
"""

from __future__ import annotations

import argparse
import re
import socket
import sys
import threading
import time
from fractions import Fraction
from pathlib import Path

from loguru import logger

# Make `segugio` importable when this script is run directly. src/ is a sibling of tools/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from segugio.config import load_config  # noqa: E402 — light import (no cv2/cyndilib/numpy)

#: Recognised video container extensions (case-insensitive).
VIDEO_EXTENSIONS = ("mp4", "mov", "mkv", "avi", "webm")


def stream_name_from_ndi_source(ndi_source: str) -> str:
    """Strip the NDI host prefix from a config ``ndi_source`` to get the published stream.

    A ``Sender(stream)`` is discoverable as ``"<HOST> (stream)"``; this inverts that so
    the tool publishes the BARE stream and the network re-forms the config value.

    Uses a NON-GREEDY host group ``(.*?)`` so it strips ONLY the FIRST " (" host prefix
    and the trailing ")". A greedy ``(.*)`` would instead return ``"NDI HX3)"`` and the
    published stream would no longer re-form the config ``ndi_source``.

    Examples::

        "MASTER (PHONE-WIDE (NDI HX3))" -> "PHONE-WIDE (NDI HX3)"
        "PLAIN"                          -> "PLAIN"   (no prefix to strip)

    Args:
        ndi_source: the config ``Camera.ndi_source`` value.

    Returns:
        The bare published stream name, or the input unchanged if it has no host prefix.
    """
    m = re.match(r"^(.*?) \((.*)\)$", ndi_source)
    if m:
        return m.group(2)
    return ndi_source


def expected_discoverable(stream: str, host: str) -> str:
    """Re-form the network-discoverable name from a bare stream + host.

    The inverse of :func:`stream_name_from_ndi_source`: ``expected_discoverable("PHONE-WIDE
    (NDI HX3)", "MASTER")`` -> ``"MASTER (PHONE-WIDE (NDI HX3))"``.
    """
    return f"{host} ({stream})"


def _find_clip(clips_dir: Path, cam_id: str) -> Path | None:
    """Return the first clip matching ``{cam_id}_*.<ext>`` under ``clips_dir`` (case-insensitive)."""
    if not clips_dir.exists():
        return None
    candidates = sorted(
        p
        for p in clips_dir.iterdir()
        if p.is_file()
        and p.name.lower().startswith(f"{cam_id.lower()}_")
        and p.suffix.lower().lstrip(".") in VIDEO_EXTENSIONS
    )
    return candidates[0] if candidates else None


def decode_clip(
    path: Path,
    max_width: int,
    max_seconds: float,
    fps_override: float,
) -> tuple[list, float]:
    """Decode a clip into a list of BGR frames (lazy ``cv2`` import).

    Args:
        path: the video file.
        max_width: downscale any frame wider than this (aspect-preserving, INTER_AREA).
        max_seconds: if > 0, stop after ``int(max_seconds * fps)`` frames; 0 = whole clip.
        fps_override: if > 0, use this fps; else the clip's native fps (30.0 fallback).

    Returns:
        ``(frames, fps)`` — the decoded BGR frames and the effective fps.
    """
    import cv2  # lazy — keeps the import surface clean (cv2 absent => import-safe module)

    cap = cv2.VideoCapture(str(path))
    native_fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps_override > 0:
        fps = fps_override
    elif native_fps and native_fps == native_fps and native_fps > 0:  # not 0/NaN
        fps = native_fps
    else:
        fps = 30.0

    max_frames = int(max_seconds * fps) if max_seconds > 0 else 0
    frames: list = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(
                frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
            )
        frames.append(frame)
        if max_frames and len(frames) >= max_frames:
            break
    cap.release()
    return frames, fps


#: Default normalized crop rect [x0, y0, x1, y1] per camera ROLE (crops mode). Each role
#: zooms into the region of the base clip its zone-weights reward, so the dog enters a
#: different camera's "best framing" as it moves near<->far / side<->centre.
ROLE_CROP_DEFAULTS = {
    "main_wide": [0.0, 0.0, 1.0, 1.0],        # full frame — neutral SAFE anchor
    "long": [0.32, 0.28, 0.98, 0.64],         # upper/far band (telephoto downfield)
    "low": [0.32, 0.52, 1.0, 1.0],            # lower/near band (ground-level close)
    "handler_side": [0.46, 0.40, 0.86, 0.86],  # centre/stage box
}
_FULL_RECT = [0.0, 0.0, 1.0, 1.0]


def _parse_crop_overrides(items: "list[str] | None") -> "dict[str, list[float]]":
    """Parse repeated ``--crop CAMID=x0,y0,x1,y1`` into ``{cam_id: [x0,y0,x1,y1]}``."""
    out: dict[str, list[float]] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--crop must be CAMID=x0,y0,x1,y1 (got {item!r})")
        cam_id, rect_s = item.split("=", 1)
        try:
            parts = [float(p) for p in rect_s.split(",")]
        except ValueError as exc:
            raise ValueError(f"--crop rect needs 4 floats (got {item!r}): {exc}") from exc
        if len(parts) != 4:
            raise ValueError(f"--crop rect needs 4 comma-separated floats (got {item!r})")
        x0, y0, x1, y1 = parts
        if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
            raise ValueError(f"--crop rect must be normalized with x0<x1, y0<y1 (got {item!r})")
        out[cam_id.strip()] = [x0, y0, x1, y1]
    return out


def crop_rect_for(cam, overrides: "dict[str, list[float]]") -> "list[float]":
    """Resolve a camera's crop rect: ``--crop`` override wins, else role default, else full."""
    if cam.id in overrides:
        return overrides[cam.id]
    role = getattr(cam, "role", None)
    role = getattr(role, "value", role)  # pydantic enum -> str
    return ROLE_CROP_DEFAULTS.get(role, _FULL_RECT)


def decode_clip_crops(
    path,
    cam_rects: "dict[str, list[float]]",
    max_width: int,
    max_seconds: float,
    fps_override: float,
) -> "dict[str, tuple[list, float]]":
    """Decode ONE base clip into a downscaled BGR crop list per camera (single pass, low RAM).

    Each full-res frame is sliced into every camera's normalized crop rect, the crop is
    downscaled to ``max_width`` (aspect-preserving), copied off the source buffer, and
    appended to that camera's list; the full-res frame is then discarded. Cropping from the
    FULL-res frame keeps the far/small-dog crops sharp while only the small per-camera crop
    lists are retained. ``cv2`` is lazy-imported.

    Args:
        cam_rects: ``{cam_id: [x0,y0,x1,y1]}`` normalized crop rects.
    Returns:
        ``{cam_id: (frames, fps)}``.
    """
    import cv2  # lazy — light import boundary

    cap = cv2.VideoCapture(str(path))
    native_fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps_override > 0:
        fps = fps_override
    elif native_fps and native_fps == native_fps and native_fps > 0:  # not 0/NaN
        fps = native_fps
    else:
        fps = 30.0
    max_frames = int(max_seconds * fps) if max_seconds > 0 else 0

    out: dict[str, list] = {cam_id: [] for cam_id in cam_rects}
    count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        for cam_id, (x0, y0, x1, y1) in cam_rects.items():
            cx0, cy0, cx1, cy1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
            crop = frame[cy0:cy1, cx0:cx1]
            chh, cww = crop.shape[:2]
            if cww > max_width:
                scale = max_width / cww
                crop = cv2.resize(
                    crop, (int(cww * scale), int(chh * scale)), interpolation=cv2.INTER_AREA
                )
            else:
                crop = crop.copy()  # detach the view so the full 4K frame can be freed
            out[cam_id].append(crop)
        count += 1
        if max_frames and count >= max_frames:
            break
    cap.release()
    return {cam_id: (frames, fps) for cam_id, frames in out.items()}


def publish_loop(
    stream: str,
    frames: list,
    fps: float,
    stop: threading.Event,
) -> None:
    """Publish ``frames`` forever as NDI source ``stream`` until ``stop`` is set.

    Builds the cyndilib ``Sender`` + ``VideoSendFrame`` ONCE (re-creating per loop makes
    the source flicker and trips the receiver watchdog), then loops the frame list inside
    the sender context manager. Lazy imports of ``cv2`` + the cyndilib symbols mirror
    ``mock_sender.publish_clip``.
    """
    import cv2
    from cyndilib.sender import Sender
    from cyndilib.video_frame import VideoSendFrame
    from cyndilib.wrapper.ndi_structs import FourCC

    sender = Sender(stream)  # the BARE stream; network re-forms "<HOST> (stream)"
    vf = VideoSendFrame()
    h, w = frames[0].shape[:2]
    vf.set_resolution(w, h)
    vf.set_frame_rate(Fraction(int(round(fps)) or int(fps) or 30, 1))
    vf.set_fourcc(FourCC.BGRA)
    sender.set_video_frame(vf)

    period = 1.0 / fps if fps > 0 else 1.0 / 30.0
    with sender:
        while not stop.is_set():
            for bgr in frames:
                if stop.is_set():
                    break
                bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
                # write_video_async wants a FLAT 1-D buffer (reshape(-1) is a no-copy view).
                sender.write_video_async(bgra.reshape(-1))
                time.sleep(period)


def build(args: argparse.Namespace) -> list[threading.Thread]:
    """Decode every camera's clip and build (but do NOT start) one publisher thread each.

    Returns the list of un-started daemon threads. Cameras with no ndi_source, no matching
    clip, or zero decoded frames are SKIPPED with a warning (never abort the whole rig).
    """
    config = load_config(args.config)
    host = socket.gethostname().upper()

    logger.info("=" * 72)
    logger.info("NDI loop-test sender — PREREQUISITE: NDI Discovery Server must be RUNNING")
    logger.info("(mDNS is broken on this box; %APPDATA%/NDI/ndi-config.v1.json must point")
    logger.info(' discovery at 127.0.0.1: {{"ndi":{{"networks":{{"discovery":"127.0.0.1"}}}}}})')
    logger.info("This box's NDI host (socket.gethostname().upper()): {}", host)
    logger.info("=" * 72)

    stop = threading.Event()
    # Stash on the namespace so main() can signal the same Event.
    args._stop = stop  # type: ignore[attr-defined]

    # CROPS MODE (one base clip -> one role-based crop per camera) vs the default per-camera
    # file mode. Crops mode forces visible switching: as the dog moves through near/far/centre
    # of the SAME clip, a different camera's crop frames it best.
    crop_overrides = _parse_crop_overrides(getattr(args, "crop", None))
    crops_mode = getattr(args, "crops_from", None) is not None
    eligible = [cam for cam in config.cameras if cam.ndi_source]
    for cam in config.cameras:
        if not cam.ndi_source:
            logger.warning("camera {} has no ndi_source — skipped", cam.id)

    crops_by_cam: "dict[str, tuple[list, float]]" = {}
    if crops_mode:
        cam_rects = {cam.id: crop_rect_for(cam, crop_overrides) for cam in eligible}
        logger.info(
            "CROPS MODE: base clip {} -> {} role-based crops", args.crops_from, len(cam_rects)
        )
        crops_by_cam = decode_clip_crops(
            args.crops_from, cam_rects, args.max_width, args.max_seconds, args.fps
        )

    threads: list[threading.Thread] = []
    for index, cam in enumerate(eligible):
        stream = stream_name_from_ndi_source(cam.ndi_source)
        if crops_mode:
            frames, fps = crops_by_cam.get(cam.id, ([], 0.0))
            clip_label = f"{Path(args.crops_from).name} crop={crop_rect_for(cam, crop_overrides)}"
        else:
            clip = _find_clip(args.clips_dir, cam.id)
            if clip is None:
                logger.warning(
                    "no clip matching {}_*.<ext> in {} — camera {} skipped",
                    cam.id,
                    args.clips_dir,
                    cam.id,
                )
                continue
            frames, fps = decode_clip(clip, args.max_width, args.max_seconds, args.fps)
            clip_label = clip.name
        if not frames:
            logger.warning("camera {} decoded 0 frames ({}) — skipped", cam.id, clip_label)
            continue

        # Optional time-stagger: rotate each feed so the dog sits at a different point in
        # each camera at any instant (extra rotation insurance).
        if getattr(args, "phase_shift", False) and len(eligible) > 1:
            offset = (index * (len(frames) // len(eligible))) % len(frames)
            if offset:
                frames = frames[offset:] + frames[:offset]

        expected = expected_discoverable(stream, host)
        logger.info(
            "camera {}: {} frames={} fps={:.2f}", cam.id, clip_label, len(frames), fps
        )
        logger.info("  published stream : {!r}", stream)
        logger.info("  discoverable as  : {!r}", expected)
        logger.info("  config ndi_source: {!r}", cam.ndi_source)
        if expected != cam.ndi_source:
            logger.warning(
                "  HOST MISMATCH: discoverable name {!r} != config ndi_source {!r} — the"
                " orchestrator will NOT find this feed. Run `hostname`, uppercase it, and"
                " fix config.looptest.yaml (+ the scene JSON).",
                expected,
                cam.ndi_source,
            )

        t = threading.Thread(
            target=publish_loop,
            args=(stream, frames, fps, stop),
            name=f"ndi-loop-{cam.id}",
            daemon=True,
        )
        threads.append(t)

    return threads


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Loop local recorded clips as named NDI sources (no-phones loop test). "
            "One daemon thread per camera; one cyndilib Sender built once each."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.looptest.yaml"),
        help="Config whose camera ndi_source names drive the published streams.",
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=Path("tests/fixtures/looptest"),
        help="Directory of per-camera clips matched as {cam.id}_*.<ext>.",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=960,
        help="Downscale frames wider than this (aspect-preserving). Default 960.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=0.0,
        help="Cap decoded length in seconds (0 = whole clip). Default 0.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=0.0,
        help="Override publish fps (0 = each clip's native fps). Default 0.",
    )
    parser.add_argument(
        "--crops-from",
        type=Path,
        default=None,
        metavar="CLIP",
        help=(
            "CROPS MODE: publish ONE base clip as N role-based crops (one per camera), "
            "ignoring --clips-dir / per-camera files. Forces continuous switching as the dog moves."
        ),
    )
    parser.add_argument(
        "--crop",
        action="append",
        default=None,
        metavar="CAMID=x0,y0,x1,y1",
        help="Override a camera's crop rect (normalized 0..1) in crops mode; repeatable.",
    )
    parser.add_argument(
        "--phase-shift",
        action="store_true",
        help="Time-stagger feeds: offset each camera's frames by index*(len/N) for extra rotation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: decode clips, spawn one looping NDI sender per camera, run until Ctrl-C."""
    args = _parse_args(argv)
    threads = build(args)
    if not threads:
        logger.error("no cameras to publish (no matching clips / sources) — nothing to do")
        return 1

    stop: threading.Event = args._stop  # type: ignore[attr-defined]
    for t in threads:
        t.start()
    logger.info("publishing {} NDI source(s) — press Ctrl-C to stop", len(threads))

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Ctrl-C received — stopping senders...")
        stop.set()
        for t in threads:
            t.join(timeout=2.0)
        logger.info("clean shutdown — all senders stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
