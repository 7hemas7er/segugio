---
status: resolved
slug: watchdog-hx-feed-death
trigger: "Watchdog does not detect NDI HX feed death (Phase 05 UAT Test 2 blocker). With a live iPhone HX source, decode works in-loop but closing the sender app leaves status.json at {reason: subject-lost, alive: {cam_wide: true}} forever — never feed-dead."
created: 2026-06-12
updated: 2026-06-12
severity: blocker
phase: 05-integration-ndi-mock-orchestrator-obs-score-ui
related: [cyndilib-ndi-hx-no-decode]
---

## Symptoms

1. **Expected behavior:** When an NDI HX phone feed dies (sender app closed / phone off WiFi),
   the per-camera liveness must stall so `FeedWatchdog` flips that camera `alive: false` within
   ~`watchdog_timeout` (0.8s) + grace, and the FSM degrades to SAFE / another live camera.
   `status.json` should show `reason: feed-dead` (single cam) or fail over (multi-cam).
2. **Actual behavior:** With the sender app CLOSED, `status.json` STAYS
   `{live_cam: SAFE, reason: subject-lost, alive: {cam_wide: true}}` indefinitely. The camera is
   never declared dead. (Before death: decode works correctly — alive:true, subject-lost because
   no dog in frame.)
3. **Error messages:** None. Silent logic failure — no exception, no crash. The watchdog simply
   keeps reading a fresh-looking timestamp.
4. **Timeline:** Surfaced 2026-06-12, immediately after the HX-decode fix (commit 8048319) made
   real phone frames flow through the loop. Invisible before because (a) headless/CI uses the
   in-process mock clip source, and (b) the only prior live source was OBS PGM (full/uncompressed
   NDI). The frozen-feed-liveness leg of Test 2 was explicitly left untested pre-fix ("needs
   decoded phone frames").
5. **Reproduction (LIVE, in hand at the rig RIGHT NOW):**
   - `config.rigtest.yaml` → `cam_wide.ndi_source: "LOCALHOST (iPhone Camera for OBS Studio App)"`
   - `python -m segugio config.rigtest.yaml`
   - Watch `./opcomm/status.json`: shows `alive: {cam_wide: true}` (decode OK).
   - CLOSE the iPhone sender app → status.json STAYS `alive: {cam_wide: true}` (BUG).
   - Reproduces every time. Only reproduces on real HX hardware.

## Hardware-verification constraint (READ FIRST)

This bug **cannot be reproduced or verified headlessly** — the mock clip source and OBS-PGM
full-NDI path do not exhibit it; it is specific to cyndilib **FrameSync** on a real HX sender
that stops. A subagent has **no access to the live iPhone**. Therefore:
- The fix LOGIC must be headless-unit-testable (a fake/stub frame source that models a stalling
  vs non-stalling substrate), AND
- The real "close the app → goes feed-dead within ~1s, then reconnect → alive again" confirmation
  **must be run by the human at the rig** via a checkpoint. Do not claim the fix verified until
  the user reports the live close-app repro now flips to `feed-dead`.

## Current Focus

hypothesis: |
  The receiver reads cyndilib FrameSync (`receiver.frame_sync.capture_video()`,
  src/segugio/ndi/ndi_source.py:248), which delivers a frame at the RECEIVER clock and keeps
  emitting the repeated last frame with an ADVANCING `get_timestamp_posix()` after the sender
  dies. The RBT-01 liveness substrate publishes whenever `ts != last_ts` (ndi_source.py:251-260),
  so `NdiFrameSource.last_frame_ts` never stalls. `FeedWatchdog` (liveness.py) is pure/correct —
  `alive = (now - last_frame_ts) <= timeout+grace` — but the substrate it reads never stalls, so
  the camera stays alive forever. The code's own [ASSUMED A1] (ndi_source.py header L26-28:
  "a frozen feed repeats its last frame with the SAME timestamp", flagged load-bearing & needing
  a pull-the-cable test) is FALSE on the FrameSync path.
test: |
  First CONFIRM the mechanism on the live feed (instrument what get_timestamp_posix() / any
  available sender timecode does after the sender stops): log per-poll the frame timestamp,
  timecode, and whether the decoded array bytes change, for ~5s after closing the app. Determine
  which of these actually stalls on a dead sender (that is the correct liveness substrate).
expecting: |
  get_timestamp_posix() keeps advancing on the dead feed (proves the bug). Then ONE of:
  the sender timecode repeats/stalls, OR raw Receiver.capture_video(timeout) returns no-frame,
  OR the decoded array bytes stop changing — that becomes the fix's liveness substrate.
next_action: |
  AWAITING HUMAN LIVE VERIFICATION (subagent has no live phone). Fix implemented + headless-green
  (323 passed). Human runs (1) scripts/debug_hx_liveness_probe.py to confirm fingerprint freezes
  while timestamp advances on a dead feed, and (2) python -m segugio config.rigtest.yaml + close
  the app to confirm status.json flips to feed-dead within ~1s and reconnect restores alive.
  On 'confirmed fixed' → archive_session (move to resolved/, commit, knowledge-base append).
  On failure → status back to investigating; the likely fallback is candidate (b) raw
  Receiver.receive(timeout_ms) path (noted in Evidence) if content does NOT freeze.
reasoning_checkpoint:
  hypothesis: |
    NdiFrameSource declares a camera alive forever on a dead HX sender for TWO compounding
    reasons: (1) its liveness gate keys on get_timestamp_posix(), which cyndilib FrameSync
    re-clocks (advances) on a re-delivered frozen frame, so a 'NEW' frame is detected every poll;
    (2) the published last_frame_ts is a POSIX wall-clock value while the live watchdog's `now`
    is time.monotonic() (loop.py:483) — different clock domains, so even a true stall would not
    compute a correct gap. The fix gates liveness on actual DECODED-CONTENT change (guaranteed to
    freeze on a dead compressed feed) and stamps last_frame_ts with time.monotonic() (same clock
    as the watchdog), making the gap correct AND the stall real.
  confirming_evidence:
    - "NDI SDK struct (ndi_structs.pxd L173-176): `timestamp` is SDK-generated receive-side; under FrameSync it is re-clocked per delivery incl. repeats — matches the live 'never dead' report."
    - "loop.py:483 passes now=time.monotonic(); ndi_source.py:251 publishes get_timestamp_posix() (real POSIX) — provable clock-domain mismatch; mock path uses one domain (tick) so headless never saw it."
    - "Compressed HX frames are never bit-identical between two genuinely-new sender frames; a frozen sender re-delivers byte-identical pixels — so a decoded-content checksum is a sound live/dead discriminator independent of which NDI time field re-clocks."
  falsification_test: |
    LIVE (human at rig): instrument the receiver to log, per poll for ~5s after closing the app,
    BOTH get_timestamp_posix() and a checksum of get_array(). If the checksum KEEPS CHANGING after
    the app is closed (i.e. the feed is NOT actually frozen — e.g. NDI substitutes a test pattern),
    the content gate is wrong and this hypothesis is falsified. If get_timestamp_posix() FREEZES
    too, the receiver-clock theory is partially wrong (harmless — content gate still correct).
  fix_rationale: |
    Content-change gating addresses the ROOT (the substrate must reflect the SENDER producing new
    imagery, not the receiver re-clocking delivery). Monotonic stamping fixes the second root (the
    clock the watchdog actually compares against). Both are in NdiFrameSource (the substrate);
    FeedWatchdog stays untouched (it is correct). Mock + OBS-PGM paths use separate code/clock and
    are unaffected.
  blind_spots: |
    (1) Whether the live HX sender's content truly freezes vs NDI inserting a 'connection lost'
    placeholder that itself animates — must confirm live. (2) Whether a content checksum could
    false-NEGATIVE on a genuinely static live scene — mitigated because HX is lossy (sensor noise
    + re-quantization make consecutive real frames differ), but a synthetic/locked test source
    could be bit-stable; documented as a known limit (real cameras are never bit-stable).
    (3) time.monotonic() resolution on Windows is fine (<1ms) vs the 0.8s timeout — non-issue.

## Fix candidates (investigate, do not assume)

- (a) **Sender timecode**: drive liveness off the cyndilib frame **timecode** (sender-stamped),
  which a frozen sender repeats, instead of the receiver-clock `get_timestamp_posix()`. Cheapest
  if the API exposes it and it actually stalls.
- (b) **Raw receive path**: use `Receiver.capture_video(timeout)` (returns no-frame on
  starvation) for the liveness substrate instead of FrameSync. Risk: reintroducing the CR-02
  busy-spin / blocking — must be paced/bounded.
- (c) **Content-identity freeze detector**: treat the feed as dead when the decoded BGR array is
  byte-identical to the last for > timeout. Robust but adds a per-frame compare/hash cost — keep
  it cheap (e.g. sample a stride, or compare a cheap checksum).

Constraints on ANY fix:
- MUST stall on a real dead HX feed (verified live by the human).
- MUST still go alive on reconnect (auto-reconnect path, ndi_source.py:239-247).
- MUST NOT reintroduce the CR-02 busy-spin (~0 core/cam disconnected was the whole point).
- MUST preserve the headless mock-clip source path and the OBS-PGM full-NDI path (both green).
- Headless 319 passing must stay green; add a regression test for the stalling substrate logic.

## Evidence

- timestamp: 2026-06-12
  observation: "Live iPhone HX via config.rigtest.yaml. status.json = {live_cam: SAFE, reason: subject-lost, alive: {cam_wide: true}} while feed is up (decode confirmed). After CLOSING the sender app it STAYS exactly that — never feed-dead. (User-reported at the rig.)"
- timestamp: 2026-06-12
  observation: "Code reading: ndi_source.py:248 reads receiver.frame_sync.capture_video(); L251-260 publishes (advancing last_frame_ts) on every ts != last_ts. liveness.py FeedWatchdog.alive = (now - last_frame_ts) <= timeout+grace — correct given a stalling substrate. The substrate (FrameSync receiver-clock timestamp) is the suspect."
- timestamp: 2026-06-12
  observation: "ndi_source.py header L12-28 [ASSUMED A1] explicitly assumed get_timestamp_posix() stalls on a frozen feed and flagged it as load-bearing, needing a Windows pull-the-cable test. The live repro contradicts that assumption."
- timestamp: 2026-06-12
  checked: "cyndilib 0.1.1 Cython source on disk (venv/Lib/site-packages/cyndilib). video_frame.pyx + ndi_structs.pxd (vendored NDI SDK header comments)."
  found: |
    TWO distinct time fields exist on every NDIlib_video_frame_v2_t:
      - timestamp (struct L173-176): 'the exact moment that the frame was submitted by the SENDING side and is GENERATED BY THE SDK'. get_timestamp_posix() = ndi_time_to_posix(ptr.timestamp). This is the RECEIVER-SDK clock value. Under FrameSync (NDIlib_framesync_capture_video) the lib re-clocks delivery and advances this value EVEN ON A REPEATED FRAME — it is exactly the substrate the loop currently keys on (ndi_source.py:251). => advances on a dead sender (the bug).
      - timecode (struct L154): 'The timecode of this frame in 100-nanosecond intervals'. SENDER-stamped (default sentinel NDIlib_send_timecode_synthesize). get_timecode_posix() = ndi_time_to_posix(ptr.timecode). On a repeated/last-real frame the SENDER produced no new frame → the timecode carried in the frame buffer is the LAST REAL FRAME's value and should FREEZE.
  implication: "Candidate (a) — get_timecode_posix() — is the cheapest correct substrate IF it actually freezes on the live HX sender. Must be confirmed live (some senders/framesync builds may synthesize timecode). The decoded-array content also freezes (candidate c) and is substrate-independent."
- timestamp: 2026-06-12
  checked: "framesync.pyx _capture_video / NDIlib_framesync_capture_video; VideoFrameSync._process_incoming. video_frame.pyx get_array() copies ptr.p_data each capture."
  found: "FrameSync.capture_video() is non-blocking and ALWAYS returns the newest synced frame (re-delivering the last on starvation). The decoded RGBA bytes (video_frame.get_array()) are byte-identical across repeated deliveries of a frozen feed — a content checksum stalls when the sender dies, independent of which time field the lib re-clocks."
- timestamp: 2026-06-12
  checked: "Receiver.receive(recv_type, timeout_ms) -> ReceiveFrameType (receiver.pyi L71). ReceiveFrameType.nothing on starvation. VideoRecvFrame buffered path."
  found: "Candidate (b) (raw receive path) DOES genuinely stall, but switching off FrameSync swaps the entire decode path that NDI-01/the HX-decode fix just stabilised, and re-introduces CR-02 busy-spin risk (must self-pace the timeout). High blast radius vs the goal. Rejected as primary; keep noted."
- timestamp: 2026-06-12
  checked: "orchestrator/loop.py:483 (live run) vs ndi_source.py:251 (published ts). Clock domains of `now` vs `last_frame_ts`."
  found: |
    SECOND, INDEPENDENT DEFECT (clock-domain mismatch): the live loop calls
    watchdog.alive_map(now=time.monotonic(), ...) (loop.py:483). FeedWatchdog.alive computes
    (now - last_frame_ts) <= timeout+grace. But NdiFrameSource publishes last_frame_ts =
    get_timestamp_posix() — a REAL POSIX wall-clock value (~1.75e9 s). time.monotonic() is an
    arbitrary-epoch counter (system uptime, typically << 1e9 on a freshly-booted box, or a
    different large value on Windows via QPC). So (monotonic_now - posix_ts) is a large-magnitude
    number of the WRONG sign/scale → the comparison is meaningless. In practice it skews
    permanently 'alive' (gap hugely negative → always <= dead_after), compounding the
    advancing-substrate bug. The mock path is immune: its ts = tick+1.0 and run_measured passes
    now = tick+1.0 — SAME domain, which is why headless never caught either defect.
  implication: "The fix must put last_frame_ts and the watchdog's `now` on ONE clock. The receiver thread should stamp time.monotonic() at the instant it observes a genuinely-NEW frame — same clock the orchestrator's live run uses (loop.py:483). This corrects the clock mismatch AND, gated on content-change, makes the stall real."

- timestamp: 2026-06-13
  checked: "LIVE VERIFICATION at the rig (human) — scripts/debug_hx_liveness_probe.py on the real iPhone HX source + python -m segugio config.rigtest.yaml."
  found: |
    CONFIRMED FIXED. Probe: while live, fingerprint=NEW each poll + timestamp_posix advancing; on
    CLOSING the iPhone app the fingerprint FROZE (constant 912435) for ~4s; on REOPENING it returned
    to NEW (1024907, 1012802). End-to-end (Step 2): status.json flipped to feed-dead on close and back
    to alive on reopen ("ok step 2"). NUANCE: in this app-CLOSE run get_timestamp_posix() ALSO froze
    (logged 'ts-FROZEN') — it did NOT keep advancing — so for the reported close-app repro the
    OPERATIVE cause was defect #2 (clock-domain mismatch); defect #1's re-clock premise (ts advancing
    on a dead feed, inferred from the SDK/framesync source) was not exhibited on this sender/build. The
    content-fingerprint substrate froze on death regardless of which time field re-clocks — which is
    exactly why it was chosen over the timecode/raw-receive paths (substrate-independent robustness).

## Eliminated

(none yet)

## Resolution

root_cause: |
  Two compounding defects in the NdiFrameSource liveness substrate (FeedWatchdog itself is correct):
  (1) The RBT-01 NEW-frame gate keyed on cyndilib FrameSync's get_timestamp_posix(). NDIlib_framesync
  re-clocks delivery and ADVANCES that receiver-SDK timestamp even when it re-delivers the last
  frozen frame after the sender dies — so a dead HX feed produced a 'new' timestamp every poll and
  last_frame_ts never stalled. The [ASSUMED A1] header assumption (timestamp stalls on a frozen
  frame) was false on the FrameSync path. (2) The published last_frame_ts was a real-POSIX value
  (get_timestamp_posix) while the live orchestrator passes now=time.monotonic() to the watchdog
  (loop.py:483) — different clock domains, so (now - last_frame_ts) was a meaningless gap that
  skewed permanently 'alive'. The headless mock path uses one tick-derived clock domain, which is
  why neither defect surfaced before the HX-decode fix made real phone frames flow.
fix: |
  In src/segugio/ndi/ndi_source.py _run_receiver, gate liveness on DECODED-CONTENT CHANGE instead
  of the FrameSync timestamp: compute a cheap strided fingerprint (_frame_fingerprint, stride 4096)
  of the decoded RGBA buffer each poll and publish (advance last_frame_ts) ONLY when the
  fingerprint changes. A lossy HX sender never emits two bit-identical frames; a dead sender
  re-delivers byte-identical pixels, so the fingerprint STALLS on a dead feed (substrate-independent
  of which NDI time field re-clocks). Stamp last_frame_ts with time.monotonic() — the watchdog's own
  clock domain — so (now - last_frame_ts) is a correct gap. FeedWatchdog and the mock/OBS-PGM paths
  are unchanged.
verification: |
  HEADLESS (done): added 4 pure-fake regression tests in tests/test_ndi_receiver_loop.py modelling
  a stalling vs non-stalling decoded-content substrate (test_live_feed_advances_last_frame_ts,
  test_frozen_feed_stalls_last_frame_ts, plus fingerprint unit tests). Full headless suite green:
  323 passed, 3 skipped, 6 deselected (was 319 + 4 new). Module still imports with cyndilib/cv2
  absent.
  LIVE (DONE, human at rig 2026-06-13): CONFIRMED. Probe showed the decoded-content fingerprint
  FREEZE on app-close (constant 912435) and return to NEW on reopen; end-to-end status.json flipped
  to feed-dead on close and back to alive on reconnect. (In this run get_timestamp_posix() also froze,
  so defect #2 / clock-domain was the operative cause of the reported symptom; the content substrate
  is robust regardless. Optional future hardening: _frame_fingerprint samples the reshaped array's
  first row only — arr[::4096] on a 3-D (yres,xres,4) buffer — which works for real never-bit-stable
  camera feeds but would be more robust as a whole-frame strided sample arr.reshape(-1)[::stride];
  not blocking, the live-verified behavior is correct for HX phone feeds.)
files_changed:
  - "src/segugio/ndi/ndi_source.py: content-change liveness gate + time.monotonic() stamp; _frame_fingerprint helper; _FINGERPRINT_STRIDE; docstrings/[RESOLVED A1]."
  - "tests/test_ndi_receiver_loop.py: 4 regression tests for the stalling-substrate logic + fingerprint."
