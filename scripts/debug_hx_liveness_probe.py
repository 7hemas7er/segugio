"""Live HX liveness probe (debug:watchdog-hx-feed-death) — RUN AT THE RIG.

Confirms the fix's mechanism on the real iPhone HX feed, which CANNOT be reproduced headlessly.
It opens the SAME cyndilib receiver path as NdiFrameSource and logs, per poll, for the source
named on the command line:

  - get_timestamp_posix()  (the OLD substrate — expected to keep ADVANCING on a dead feed)
  - get_timecode_posix()   (sender-stamped — candidate, may or may not freeze)
  - the decoded-content fingerprint (the NEW substrate — expected to FREEZE on a dead feed)

Usage (from the repo root, with the venv active):

    venv\\Scripts\\python.exe scripts\\debug_hx_liveness_probe.py "LOCALHOST (iPhone Camera for OBS Studio App)"

Then, while it is printing rows: CLOSE the iPhone sender app and watch the columns.

EXPECTED (confirms the fix):
  - Before closing: fingerprint CHANGES most rows (content moving), timestamp advances.
  - After closing:  fingerprint goes CONSTANT (frozen pixels), even though timestamp KEEPS
                    advancing. => last_frame_ts (now gated on fingerprint) stalls → dead.
  - On REOPENING the app: fingerprint starts CHANGING again → alive.

If the fingerprint KEEPS CHANGING after the app is closed, the content gate is wrong for this
sender (e.g. NDI inserts an animated 'lost' placeholder) — report that; it falsifies the fix.
"""

from __future__ import annotations

import sys
import time


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    source_name = argv[1]
    duration_s = float(argv[2]) if len(argv) > 2 else 30.0

    # Reuse the production runtime-pairing + the same fingerprint as the fix.
    from segugio.ndi.ndi_source import _frame_fingerprint, _prefer_system_ndi_runtime

    _prefer_system_ndi_runtime()

    from cyndilib.finder import Finder
    from cyndilib.receiver import Receiver
    from cyndilib.video_frame import VideoFrameSync
    from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat

    finder = Finder()
    receiver = Receiver(
        color_format=RecvColorFormat.RGBX_RGBA,
        bandwidth=RecvBandwidth.highest,
    )
    video_frame = VideoFrameSync()
    receiver.frame_sync.set_video_frame(video_frame)
    finder.open()

    print(f"[probe] resolving source: {source_name!r} (up to 15s) ...")
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            names = finder.get_source_names()
        except Exception:
            names = []
        if source_name in names:
            receiver.set_source(finder.get_source(source_name))
            break
        time.sleep(0.1)
    else:
        print(f"[probe] source not found. Visible: {names}")
        finder.close()
        return 1

    print("[probe] CLOSE the iPhone sender app while this runs. Columns:")
    print(f"{'wall':>8}  {'timestamp_posix':>18}  {'timecode_posix':>16}  {'fingerprint':>12}  changed?")
    last_fp = None
    last_ts = None
    t_end = time.monotonic() + duration_s
    while time.monotonic() < t_end:
        receiver.frame_sync.capture_video()
        if min(video_frame.xres, video_frame.yres) != 0:
            ts = video_frame.get_timestamp_posix()
            tc = video_frame.get_timecode_posix()
            arr = video_frame.get_array().reshape(video_frame.yres, video_frame.xres, 4)
            fp = _frame_fingerprint(arr)
            changed = "NEW" if fp != last_fp else "frozen"
            ts_moved = "" if last_ts is None or ts != last_ts else " (ts-FROZEN)"
            print(f"{time.monotonic() % 100:8.3f}  {ts:18.4f}  {tc:16.4f}  {fp:12d}  {changed}{ts_moved}")
            last_fp = fp
            last_ts = ts
        time.sleep(0.1)  # ~10Hz print pace (the real loop polls ~500Hz; this is just readable)

    receiver.disconnect()
    finder.close()
    print("[probe] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
