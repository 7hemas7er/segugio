"""Live verification for the NDI|HX decode fix (debug: cyndilib-ndi-hx-no-decode).

Run this with the iPhone 'NDI Camera' app open and its **camera VIEW active** (so it sends
video). It applies the same fix the orchestrator uses — preloading the system NDI 6.3.2 base
runtime before importing cyndilib (via ``segugio.ndi.ndi_source._prefer_system_ndi_runtime``) —
then opens a bare cyndilib receiver on the phone source and reports whether video frames now
decode (xres/yres > 0).

Usage (from the repo root, in the venv):
    ./venv/Scripts/python.exe tools/verify_ndi_hx_decode.py "LOCALHOST (iPhone)"

Pass the exact NDI source name as the first argument (default: "LOCALHOST (iPhone)").
A PASS = the version-pairing fix decodes the HX phone. A FAIL (still 0x0) means the fix did
not resolve it and the debug session should be reopened.
"""

from __future__ import annotations

import sys
import time


def main() -> int:
    source_name = sys.argv[1] if len(sys.argv) > 1 else "LOCALHOST (iPhone)"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0

    # Apply the SAME fix the receiver loop uses: pair the system 6.3.2 base runtime with the
    # 6.3.2 HX plugin BEFORE importing cyndilib.
    from segugio.ndi.ndi_source import _prefer_system_ndi_runtime

    preloaded = _prefer_system_ndi_runtime()
    print(f"[fix] system NDI base runtime preloaded: {preloaded!r}")
    if preloaded is None:
        print("[warn] no system runtime preloaded — cyndilib will use its bundled 6.1.1 base "
              "(HX likely will NOT decode). Install the NDI 6 Tools + HX Driver.")

    from cyndilib.finder import Finder
    from cyndilib.receiver import Receiver
    from cyndilib.video_frame import VideoFrameSync
    from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat

    finder = Finder()
    finder.open()
    print(f"[ndi] looking for source: {source_name!r}")

    receiver = Receiver(
        color_format=RecvColorFormat.RGBX_RGBA,
        bandwidth=RecvBandwidth.highest,
    )
    video_frame = VideoFrameSync()
    receiver.frame_sync.set_video_frame(video_frame)

    # Resolve + connect.
    deadline = time.monotonic() + seconds
    source = None
    while time.monotonic() < deadline and source is None:
        try:
            names = finder.get_source_names()
        except Exception:
            names = []
        if source_name in names:
            source = finder.get_source(source_name)
            break
        time.sleep(0.1)

    if source is None:
        print(f"[FAIL] source {source_name!r} not discovered within {seconds:.0f}s. "
              f"Open NDI Access Manager and confirm the phone is visible.")
        finder.close()
        return 2

    receiver.set_source(source)
    print(f"[ndi] connected={receiver.is_connected()}  — capturing for {seconds:.0f}s ...")

    reads = 0
    decoded = 0
    max_res = (0, 0)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        receiver.frame_sync.capture_video()
        reads += 1
        xres, yres = video_frame.xres, video_frame.yres
        if min(xres, yres) != 0:
            decoded += 1
            if (xres, yres) > max_res:
                max_res = (xres, yres)
        time.sleep(0.01)

    receiver.disconnect()
    finder.close()

    print(f"[result] reads={reads}  decoded(res>0)={decoded}  max_res={max_res}")
    if decoded > 0:
        print(f"[PASS] NDI|HX DECODES — got {decoded} frames at up to {max_res[0]}x{max_res[1]}. "
              f"The version-pairing fix works.")
        return 0
    print("[FAIL] still 0 decoded frames (xres/yres stayed 0). The fix did NOT resolve HX decode "
          "— reopen the debug session (cyndilib-ndi-hx-no-decode).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
