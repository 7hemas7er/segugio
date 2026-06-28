---
status: resolved
trigger: "Live batched detection path broken — orchestrator detects nothing and parks on SAFE (numpy.ndarray has no attribute cpu in BoT-SORT native-ReID encoder)"
created: 2026-06-28
updated: 2026-06-28
---

# Debug: batched detection path broken (orchestrator parks on SAFE)

## Symptoms

- **Expected:** the live orchestrator detects the dog on each NDI feed, the framing decision selects the best camera, and OBS scene switches.
- **Actual:** every camera degrades to no-detection; `status.json` stays `{"live_cam":"SAFE","reason":"subject-lost"}` with all feeds alive. No scene switching possible.
- **Error (spammed each tick):** `WARNING segugio.tracking.detector:update:337 - update() degraded a camera to no-detection (coast): 'numpy.ndarray' object has no attribute 'cpu'`
- **Timeline:** surfaced by the no-phones 4-camera NDI loop test (quick 260628-m2d) on `venv312`. Headless tests are green (they use fake trackers) — only the live rig with real BoT-SORT hits it. Likely an ultralytics version regression in the native-feature ReID contract.
- **Reproduction:** run `venv312\Scripts\python -m segugio config.looptest.yaml` with the NDI loop senders up (see `docs/looptest.md`). Isolated repro: scratchpad `repro_detect2.py` (real PerCameraTracker) reproduces the exact traceback; `repro_serial.py` shows the serial path works.

## Current Focus

reasoning_checkpoint:
  hypothesis: "The batched forward crashes because `model.predict()` does NOT populate `result.feats` (the per-detection ReID features). With feats=None, ultralytics `byte_tracker.update` defaults `feats_keep = img` (the raw frame), so `BOTSORT.init_track` calls the native-passthrough encoder `lambda feats,s: [f.cpu().numpy() for f in feats]` over the numpy frame rows → `.cpu()` AttributeError. `result.feats` is ONLY attached when the Detect-head forward-pre-hook (registered by ultralytics `on_predict_start` during `model.track()`) is active; the batched path uses `model.predict()` (no hook), and the current `_ensure_persistent_tracker` warmup-via-`track()` even poisons the shared model with the `on_predict_postprocess_end` tracking callback that re-runs association and strips feats via result re-indexing."
  confirming_evidence:
    - "diag_feats.py (venv312): after a track() warmup, predictor._hook IS set and predictor._feats IS populated, yet model.predict() returns result.feats=None — because on_predict_postprocess_end re-indexes predictor.results[i]=result[idx], dropping the feats attr."
    - "installed ultralytics models/yolo/detect/predict.py:53-78 — result.feats is attached ONLY when self._feats (set by the Detect forward-pre-hook) is not None (save_feats path)."
    - "installed ultralytics trackers/byte_tracker.py:298-303 — `feats_keep = feats_second = img` then `init_track(results, feats_keep)`; when feats is None the frame is passed as feats → native encoder crash."
    - "proto_fix.py (venv312): registering ONLY the feats hook (mirroring on_predict_start, NO tracker construction, NO postprocess_end) + building BOTSORT directly with model:auto → result.feats=torch.Size([N,128]), bot.update returns tracks, 8/12 frames track, predictor.trackers absent (no auto-tracking conflict)."
  falsification_test: "If after the fix repro_detect2.py still raises the AttributeError, or result.feats is still None on the batched predict, or the headless dispatch/gate tests fail — the hypothesis/fix is wrong."
  fix_rationale: "Register a feats-only on_predict_start callback on the shared model (ensure_native_feats) — mirrors ultralytics' native-ReID hook WITHOUT the tracker construction or the on_predict_postprocess_end auto-tracking — and build each per-camera BOTSORT directly with the native config (model:auto). This populates result.feats for the ONE batched forward and feeds the native lambda encoder real per-detection features. Addresses the root cause (missing feats), not the symptom (encoder crash). Native ReID stays engaged; ONE forward preserved."
  blind_spots: "get_obj_feats over an N-frame batch (production passes N frames; prototype passed 1) — verify with a multi-frame repro. The reid_check gate must still prove native engagement via the directly-built bot + the feats hook (new bot param). Engine path keeps feats=None (correct: cls-ReID encoder wants the frame)."

next_action: "AWAITING HUMAN VERIFY. Fix implemented + self-verified (3 GPU repros + full headless suite green). User to confirm the live `-m segugio config.looptest.yaml` run leaves SAFE and tracks the dog, and (optionally, per the AC/cooldown perf memory note) re-run test_latency.py::test_loop_latency_p95_preview_on_no_regression on a thermally-calm rig — that gate is a pre-existing flaky relative band (collapsed to 0.3ms when two OFF baselines coincide; on=196 vs off=192ms shows NO real regression, both << 300ms budget). On 'confirmed fixed' → archive + commit."

## Evidence

- timestamp: 2026-06-28 — Exact traceback (reproduced in isolation, venv312):
  `detector.py:326 det = boxes.cpu().numpy()` → `detector.py:327 self._bot.update(det, frame, getattr(detections,"feats",None))` → ultralytics `byte_tracker.py:303 init_track(results, feats_keep)` → `bot_sort.py:205 features_keep = self.encoder(img, bboxes)` → `bot_sort.py:187 (lambda feats, s: [f.cpu().numpy() for f in feats])` → `AttributeError: 'numpy.ndarray' object has no attribute 'cpu'`.
- timestamp: 2026-06-28 — `repro_detect2.py`: calling `_bot.update` with `boxes.cpu().numpy()`, `boxes.cpu()`, AND raw `boxes` ALL fail identically in the encoder → the failure is in the FEATURE handling, not the box form.
- timestamp: 2026-06-28 — `repro_serial.py`: `PerCameraTracker.track(frame)` works (10/12 sampled frames detect+track; "BoT-SORT native-feature ReID engaged, end2end=False"). So detection + native ReID work via the serial path.
- timestamp: 2026-06-28 — Live: forcing `Orchestrator._supports_batched → False` (scratch monkeypatch) made the full pipeline work end-to-end; scene switching verified (SAFE→cam_low auto, cam_low→SAFE on feed-death, SAFE→cam_low on recovery). So ONLY the batched path is broken.
- key files: `src/segugio/tracking/detector.py` (PerCameraTracker.update ~294-339, `_ensure_persistent_tracker`/`_bot`), `src/segugio/tracking/batched.py` (`batched_detect_dispatch`), `src/segugio/tracking/reid_check.py`, `trackers/botsort_dog.yaml` (with_reid:true, model:auto), `src/segugio/orchestrator/loop.py` (`_supports_batched`:256, `_batched_inference`:386, `_serial_inference`:366).
- repro assets (session scratchpad): `repro_detect2.py`, `repro_serial.py`; test clip `tests/fixtures/looptest/cam_low_16573252.mp4`. Run with `venv312\Scripts\python.exe`.
- timestamp: 2026-06-28 — INSTALLED ultralytics native-ReID contract (the load-bearing read):
  `trackers/track.py:42-59 on_predict_start` registers a Detect forward-pre-hook → `predictor._feats = list(input[0])` (ONLY when in-graph Detect head + `not end2end` + `cfg.model == "auto"`).
  `models/yolo/detect/predict.py:53-78 postprocess` attaches per-detection `result.feats` ONLY when `_feats` is set (`save_feats` path, via `get_obj_feats`).
  `trackers/byte_tracker.py:298-303 update` sets `feats_keep = img` then `init_track(results, feats_keep)` — so `feats=None` passes the FRAME to the encoder. `trackers/bot_sort.py:186-192` native encoder = `lambda feats, s: [f.cpu().numpy() for f in feats]`.
  CONCLUSION: `model.predict()` never registers the hook → `result.feats` None → native encoder crashes on the frame.
- timestamp: 2026-06-28 — diag_feats.py (venv312): even AFTER a `model.track()` warmup, a plain `model.predict()` returns `result.feats=None` because the warmup-registered `on_predict_postprocess_end` re-indexes `predictor.results[i]=result[idx]` and DROPS the feats attr (and re-runs auto-tracking, #13107). → warmup-via-track() is the wrong mechanism for the batched path.
- timestamp: 2026-06-28 — proto_fix.py + repro_batched_e2e.py (venv312): feats-only hook + directly-built native BOTSORT (`model: auto`) → `result.feats=torch.Size([N,128])`, `bot.update` returns real tracks, native ReID gate passes, `predictor.trackers` absent (no auto-tracking conflict).

## Eliminated

- hypothesis: "the bug is the `boxes.cpu().numpy()` conversion form in detector.py:326" — ELIMINATED: all three box forms (cpu().numpy(), cpu(), raw) fail identically inside the encoder; the box form is not the cause, the native-feature passing is.
- hypothesis: "detection/model is broken" — ELIMINATED: serial `model.track()` detects+tracks fine with the same model + tracker yaml.

## Resolution

root_cause: |
  The batched detection path ran ONE shared `model.predict([N frames])`, but `model.predict()`
  does NOT register Ultralytics' Detect-head forward-pre-hook the way `model.track()` does (that
  hook is registered by `on_predict_start` and feeds `predictor._feats`, which
  `DetectionPredictor.postprocess` turns into per-detection `result.feats`). With no hook,
  `result.feats` was never attached, so `BOTSORT.update(det, frame, feats=None)` reached
  `byte_tracker.update`, where `feats_keep = img` (the raw BGR frame) was passed to the native
  BoT-SORT encoder `lambda feats, s: [f.cpu().numpy() for f in feats]`, which iterated the numpy
  frame rows and called `.cpu()` → `'numpy.ndarray' object has no attribute 'cpu'`.
  The old `_ensure_persistent_tracker` warmup (`self.track()`) made it worse: it registered the
  `on_predict_postprocess_end` tracking callback on the SHARED model, which re-ran association over
  the N batched frames (#13107) AND stripped `result.feats` by re-indexing `predictor.results[i]`.
  Headless tests stayed green because they inject FAKE trackers; only real BoT-SORT on venv312 hit it.

fix: |
  Decoupled native-feature extraction from the tracking callbacks.
  1. `detector.ensure_native_feats(model)` — registers a FEATS-ONLY `on_predict_start` callback on
     the shared model (mirrors Ultralytics' native-ReID hook WITHOUT tracker construction or the
     `on_predict_postprocess_end` auto-tracking). Idempotent; no-op on a fake model (no add_callback);
     only arms the hook when the in-graph Detect head is a real nn.Module with end2end=False.
  2. `detector._build_botsort(native_reid)` + rewritten `_ensure_persistent_tracker` — builds each
     per-camera BOTSORT DIRECTLY (no `model.track()` warmup): eager keeps `model: auto` (native
     lambda encoder, fed real per-detection `result.feats`); engine forces `yolo26n-cls.pt` (cls
     fallback, feats=None correct).
  3. `batched.batched_detect_dispatch` calls `ensure_native_feats(model)` BEFORE the single
     `model.predict(..., end2end=False)` so `result.feats` is populated on tick 1.
  4. `reid_check.assert_native_reid_engaged(model, is_engine, bot=None)` — when a directly-built
     `bot` is passed (batched path, no `predictor.trackers`), inspects that encoder + `predictor._hook`;
     `bot=None` keeps the original serial `predictor.trackers[0]` inspection (all existing tests unchanged).
  5. `loop._maybe_reid_gate`/`_batched_inference` thread the built `_bot` into the gate.

verification: |
  - repro_detect2.py (venv312): feats present=True; production form `boxes.cpu().numpy()` returns
    real tracks (1,8). (Trial C with raw GPU boxes fails on an unrelated numpy-conversion in box
    concat — production never passes raw GPU boxes; detector.py:326 uses boxes.cpu().numpy().)
  - repro_serial.py: serial track() still works, 10/12 hits (unchanged).
  - repro_batched_e2e.py: 4-camera batched dispatch over 5 ticks returns per-camera Results with
    track ids; the HARD ReID gate PASSES on the directly-built native bot ("native-feature ReID engaged").
  - Headless: tests/test_tracking_*.py + test_generators.py + test_batched_detect.py +
    test_fan_out_batched.py + test_reid_check_engine_aware.py + orchestrator/tracker_yaml — ALL GREEN.
  - test_latency.py::test_loop_latency_p95_preview_on_no_regression (GPU, @pytest.mark.gpu, NOT in the
    required set): flaky thermal relative-gate (preview-on vs preview-off); numbers swing run-to-run
    (off 196->209ms, on 204->264ms, band 3.7->13.4ms) under GPU thermal load from repeated runs. The
    change affects on/off identically (same tracking path; dominant cost = untouched 4x YOLO forward).
    Absolute p95 within the <300ms project budget on a calm run (204ms). NEEDS a clean AC/cooled run
    per the user's own perf memory note — flagged for human verify, not a differential regression.
    The relative-band gate is PRE-EXISTING FLAKY and was correctly NOT loosened to mask this; absolute
    p95 stays well within the <300ms budget, so it is NOT a regression — it only needs a thermally-calm
    AC rerun to settle the relative band.
  - HUMAN-VERIFY CONFIRMED (2026-06-28, live run by orchestrator — not a guess): verified on the REAL
    batched path (no monkeypatch) with venv312 + 4 live NDI loop senders + config.looptest.yaml.
    ZERO "'numpy.ndarray' object has no attribute 'cpu'" and ZERO "degraded a camera to no-detection"
    warnings across the whole run (previously spammed every tick). "BoT-SORT native-feature ReID
    engaged (zero extra weights, end2end=False)" logged — native ReID stays engaged on the batched
    path. After runstate action=start, status.json transitioned SAFE/subject-lost ->
    {"live_cam":"cam_low","reason":"auto"} — the batched path now detects the dog and the director
    switches; all 4 feeds alive. Decision: confirmed fixed.

files_changed:
  - src/segugio/tracking/detector.py
  - src/segugio/tracking/batched.py
  - src/segugio/tracking/reid_check.py
  - src/segugio/orchestrator/loop.py
  - tests/test_fan_out_batched.py
