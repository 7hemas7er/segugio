---
phase: 04-yolo-per-camera-tracking-on-recorded-clips
reviewed: 2026-06-09T23:44:50Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - src/segugio/tracking/__init__.py
  - src/segugio/tracking/competitor_lock.py
  - src/segugio/tracking/plausibility.py
  - src/segugio/tracking/signals_map.py
  - src/segugio/tracking/params.py
  - src/segugio/tracking/detector.py
  - src/segugio/tracking/reid_check.py
  - src/segugio/tracking/frame_source.py
  - src/segugio/tracking/eval.py
  - src/segugio/config/models.py
  - src/segugio/synth/detection_stream.py
  - src/segugio/synth/__init__.py
  - trackers/botsort_dog.yaml
  - pyproject.toml
  - tests/conftest.py
  - tests/conftest_tracking.py
  - tests/test_competitor_lock.py
  - tests/test_plausibility_gate.py
  - tests/test_signals_map.py
  - tests/test_frame_source.py
  - tests/test_tracking_metrics.py
  - tests/test_tracking_import_smoke.py
  - tests/test_imports.py
  - tests/test_yolo_clips_eval.py
findings:
  critical: 2
  warning: 7
  info: 5
  total: 14
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-09T23:44:50Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Reviewed the Phase-4 per-camera YOLO+BoT-SORT tracking layer: the pure brain (`competitor_lock`, `plausibility`, `signals_map`, `params`, `eval.compute_metrics`), the heavy edge (`detector`, `reid_check`, `frame_source`, `eval.run_clip_eval`), the synth substrate, and the supporting config + tests.

The lazy-import boundary is genuinely respected — no module-level heavy imports in any heavy-edge module (`torch`/`ultralytics`/`cv2`/`cyndilib`/`obsws_python` all imported inside functions). The pure-logic modules and their tests pass and are well-isolated. Documentation is unusually thorough.

However, the **untested heavy-edge driver `run_clip_eval` (eval.py) contains the bulk of the defects**. Because it only runs behind `@pytest.mark.gpu` (skipped on every CPU box including CI), the bugs below have never executed. Two are correctness BLOCKERS: the native-ReID startup gate crashes with an `AttributeError` instead of its intended `RuntimeError` when the first crop is empty, and the plausibility gate is reset on every transient coast tick — silently defeating the inter-frame teleport guard the phase exists to provide (TRK-05, PITFALLS Pitfall 2). A logged "recall-proxy" metric is also wrong (it reports lock-held fraction twice).

The pure layer is solid; the unexercised GPU driver is where the risk concentrates.

## Critical Issues

### CR-01: Plausibility gate reset on every transient coast destroys the TRK-05 teleport guard

**File:** `src/segugio/tracking/eval.py:321-324`
**Issue:** `CompetitorLock.select` returns `None` whenever nothing is *in-field this tick* — which is a transient, single-tick coast (the dog momentarily leaves the zone, a frame blurs, a detection drops). It is **not** the "genuine loss / re-acquire" event. But the driver calls `gates[cam_id].reset()` on *every* `None` from `select`:

```python
selected = locks[cam_id].select(candidates, tick)
if selected is None:
    gates[cam_id].reset()  # <-- fires on ANY transient coast, not just genuine loss
signal = gates[cam_id].check(selected)
```

`reset()` clears `self.prev`. Per `plausibility.py:103-111`, the first det after a reset is *accepted unconditionally* (no `prev` to compare). So the exact sequence the gate exists to catch — lock A → one coast tick → a swapped/teleported box reusing A's id — is now accepted: the coast resets `prev`, and the teleport box becomes the new reference with no continuity check. This silently defeats TRK-05 / PITFALLS Pitfall 2 (the whole reason `PlausibilityGate` exists). `plausibility.py:103` documents `reset()` as called only on a *genuine loss*, so the driver's usage contradicts the module contract.

**Fix:** Reset only on a genuine loss transition (lock id actually changed or the lock had been held and is now lost), not on every coast. Track the previous selected id and reset only when re-acquiring a different track:

```python
prev_sel_id = last_selected_id[cam_id]
selected = locks[cam_id].select(candidates, tick)
cur_sel_id = selected.track_id if selected is not None else None
# Reset only when the locked identity actually changes (genuine re-acquire),
# NOT on a transient coast where prev should be preserved for the next real det.
if cur_sel_id is not None and cur_sel_id != prev_sel_id:
    gates[cam_id].reset()
last_selected_id[cam_id] = cur_sel_id
signal = gates[cam_id].check(selected)
```

(A plain transient coast then flows through `check(None)` → `None` with `prev` intact, exactly as `test_genuine_miss_coasts_prev_unchanged` expects.)

### CR-02: Native-ReID startup gate crashes with AttributeError (not its intended RuntimeError) when the first crop is empty

**File:** `src/segugio/tracking/eval.py:313-316`, `src/segugio/tracking/reid_check.py:51`
**Issue:** The HARD TRK-02 gate runs once on the first tick, immediately after the first `track(crop)`:

```python
results = tracker.track(crop)        # returns None WITHOUT calling model.track() if crop is None/empty
if not reid_checked:
    assert_native_reid_engaged(tracker.model)
```

`PerCameraTracker.track` (detector.py:122-124) returns `None` *before touching inference* when `frame is None or frame.size == 0`. `frame_source.py` explicitly yields zero-pixel crops for degenerate rects ("Crops that slice to zero pixels ... are still included"), and `frame_crops.get(cam_id)` yields `None` for any camera id missing from the crop map. In either case `model.track()` never ran, so `model.predictor` is `None`. Then `assert_native_reid_engaged` does `predictor = model.predictor` (reid_check.py:51) and `getattr(predictor, "trackers", None)` → `getattr(None, ...)` returns `None`, raising the generic "no trackers on predictor" RuntimeError — *or*, if `model.predictor` itself is an attribute that raises, an `AttributeError`. Either way the carefully-designed pass/fail gate fires for the wrong reason (an empty warmup crop), aborting the whole eval instead of the silent-fallback condition it is meant to detect. The "after the first crop is decoded (predictor exists)" comment at line 309 is simply false for the empty/missing-crop path the code itself produces.

**Fix:** Only run the gate after a warmup that actually performed inference. Guard on `results is not None` (or pick the first non-empty crop for the warmup) and defer `reid_checked = True` until a real `.track()` has run:

```python
results = tracker.track(crop)
if not reid_checked and results is not None:   # predictor only exists after a real inference
    assert_native_reid_engaged(tracker.model)
    reid_checked = True
```

and remove the unconditional `reid_checked = True` at the end of the camera loop (eval.py:337), which currently marks the gate "done" even if every first-tick crop was empty and the gate never actually ran.

## Warnings

### WR-01: `reid_checked = True` set unconditionally after the first tick even if the gate never ran

**File:** `src/segugio/tracking/eval.py:336-337`
**Issue:** `reid_checked = True` is set at the end of the first tick's camera loop regardless of whether `assert_native_reid_engaged` actually executed. Combined with CR-02, if the first tick's crops were all empty/None, the predictor never initialized, the gate either crashed or ran against a `None` predictor, and on tick 2 `reid_checked` is already `True` so the gate is *skipped forever*. The one true pass/fail of the phase (TRK-02) can be silently bypassed.
**Fix:** Drive `reid_checked` from the gate actually running on a real inference (see CR-02 fix) — set it to `True` only inside the `if results is not None` block, never unconditionally.

### WR-02: Logged "detection-presence/recall-proxy" metric is just lock_held_fraction reported twice

**File:** `src/segugio/tracking/eval.py:348-353`
**Issue:** The per-clip log claims to report a recall proxy:

```python
"clip={} cam={} id_switches={} lock_held={:.3f} coast={} n_ticks={} "
"(detection-presence/recall-proxy={:.3f}; recorded, not a gate — Q2/D-02)",
out_video_path, cam.id, m["id_switch_count"], m["lock_held_fraction"],
m["coast_count"], m["n_ticks"], m["lock_held_fraction"],   # <-- same value as lock_held
```

The "recall-proxy" placeholder is fed `m["lock_held_fraction"]` — the identical value already printed as `lock_held`. There is no independent detection-presence metric; the log presents a duplicated number as if it were a distinct recall signal (Q2/D-02). On a clip the operator reads this to judge per-camera recall, so the duplicated value is misleading.
**Fix:** Either compute a real detection-presence counter (e.g. fraction of ticks with ≥1 raw candidate, distinct from the locked/gated fraction) and pass that, or drop the "recall-proxy" clause entirely so the log does not imply a metric it isn't producing.

### WR-03: `signals_from_boxes` silently truncates on a length mismatch between xywhn/ids/confs

**File:** `src/segugio/tracking/signals_map.py:55`
**Issue:** `zip(xywhn, ids, confs)` stops at the shortest argument. If a real `Results.boxes` ever yields `id`/`conf`/`xywhn` of differing lengths (an Ultralytics edge case the module's own docstring acknowledges by guarding `ids is None`), rows are dropped silently with no warning — detections vanish from the candidate set and the dog can be lost with no diagnostic. For the live "never lose the dog" requirement, a silent drop is the worst failure mode.
**Fix:** Assert aligned lengths (fail fast at the boundary) or use `zip(..., strict=True)` (Python 3.12+, already the floor per pyproject) so a mismatch raises instead of silently truncating; or log a warning and process `min(len(...))` deliberately. At minimum make the truncation visible.

### WR-04: `_crop` clamps min/max independently → can yield an inverted (empty) slice for a degenerate rect

**File:** `src/segugio/tracking/frame_source.py:113-117`
**Issue:** `px0`/`px1` are clamped independently into `[0, w]`. For a malformed crop rect where `x1 < x0` (not prevented anywhere — `crops` is a raw dict, not the validated `Zone` with its `x0<x1` validator), `px0 > px1`, and `frame[py0:py1, px0:px1]` returns a zero-width array. The generator yields it as a "saw nothing" crop, which then flows into `tracker.track` → `frame.size == 0` → `None` (coast) for *every tick on that camera*, silently. The misconfiguration never surfaces.
**Fix:** Validate crop rects at `ClipFrameSource.__init__` (require `0 <= x0 < x1 <= 1` and `0 <= y0 < y1 <= 1`), or reuse the `Zone` model's ordering validator, so a bad rect fails loudly at setup rather than producing permanent silent coast.

### WR-05: `track_buffer` duplicated across `botsort_dog.yaml` and `Thresholds` with no enforced sync

**File:** `trackers/botsort_dog.yaml:22`, `src/segugio/config/models.py:109`
**Issue:** `track_buffer: 60` lives in two independent places — the BoT-SORT yaml (read by Ultralytics) and `Thresholds.track_buffer` (read by the rest of the pipeline). The yaml comment itself flags this as "a two-place coupling ... Keep them in sync." Nothing enforces it: a future tuner can change `Thresholds.track_buffer` to 90 while the tracker keeps buffering 60 frames, producing a silent behavior split between the config-driven logic and the actual tracker. The config value is, in fact, never wired into the tracker at all.
**Fix:** Make the yaml a template rendered from `Thresholds.track_buffer` at startup (the comment's own suggestion), or add a startup assertion that the loaded `botsort_dog.yaml` `track_buffer` equals `config.thresholds.track_buffer`, failing fast on drift.

### WR-06: `resolve_dog_index` reconciles config but a real disagreement only logs a warning and proceeds

**File:** `src/segugio/tracking/detector.py:72-78`
**Issue:** When the configured `class_index` (default 16) disagrees with the name-resolved dog index, the code logs a warning and uses the resolved index. This is the documented intent — but in `run_clip_eval` it runs on the first tick *per camera* inside the hot loop guard, and the result overwrites `tracker.dog_idx` only at line 311; subsequently the gate/track already used the constructor-time `dog_idx` (`model_cfg.class_index`, i.e. 16) for the warmup `track(crop)` at line 313. So the *first* warmup inference filters by the unverified configured index, and only later ticks use the resolved one. On a custom mono-class model (dog at index 0) the warmup inference at line 313 filters `classes=[16]` → zero detections, and the native-ReID gate's warmup runs against an empty result set.
**Fix:** Resolve the dog index *once, before constructing/warming up the trackers* (e.g. load the model, resolve, then set `dog_idx` before any `.track()`), so the very first inference already uses the name-resolved index — not the unverified configured 16.

### WR-07: `multi_track_stream` does not validate required spec keys → raises bare `KeyError` mid-loop

**File:** `src/segugio/synth/detection_stream.py:171-191`
**Issue:** The function validates `spec["path"]` up front (good) but accesses `spec["size"]`, `spec["conf"]`, `spec["track_id"]` with bare subscripts inside the tick loop. A spec missing `size`/`conf`/`track_id` raises a raw `KeyError` partway through generation, not a clear validation error — and inconsistently with the deliberate up-front `path` guard the docstring advertises ("an unknown `path` fails fast ... BEFORE drawing any randomness"). The other required keys do not fail fast.
**Fix:** Validate all required keys (`track_id`, `path`, `size`, `conf`) in the same up-front loop that checks `path`, raising a descriptive `ValueError`/`KeyError` with the offending spec before any ticks are generated.

## Info

### IN-01: Blank-frame skip perturbs stride phase in `frame_source`

**File:** `src/segugio/tracking/frame_source.py:86-94`
**Issue:** A skipped blank frame still does `raw_index += 1`, so a blank frame mid-stream shifts which subsequent decoded frames satisfy `raw_index % stride == 0`. The emitted set after a blank frame is phase-shifted vs. a clean stream. Determinism per-clip is preserved (same input → same output), but the "sample every Nth real frame" intent is subtly violated around blanks.
**Fix:** Decide explicitly whether blank frames should count toward the stride; if not, advance `raw_index` only for successfully-emitted-or-decimated frames.

### IN-02: `_arrays_from_results` casts ids to int but xywhn/confs stay numpy floats until the mapper

**File:** `src/segugio/tracking/eval.py:224-227`
**Issue:** `ids` is `.astype(int).tolist()` but `xywhn`/`confs` are `.tolist()` of float arrays. This is fine (the pure mapper `float()`-casts), but the asymmetry is a latent trap — a future reader may assume all three are already plain Python of the same numeric discipline. Minor consistency nit.
**Fix:** Optional: document that only `ids` needs the explicit `int` cast (BoT-SORT ids arrive as floats) and the rest are cast downstream.

### IN-03: `run_clip_eval` requires every camera id to have a crop entry but does not validate it

**File:** `src/segugio/tracking/eval.py:284`
**Issue:** `crop_map = {cam.id: crops[cam.id] for cam in cams}` raises a bare `KeyError` if a camera lacks a `crops` entry — the docstring states "Each camera's `id` MUST have a `crops` entry" but nothing enforces it with a clear message.
**Fix:** Validate up front: `missing = [c.id for c in cams if c.id not in crops]` and raise a descriptive `ValueError(f"cameras missing crop geometry: {missing}")`.

### IN-04: `_VALID_CONFIG` imported into tests via private-name import

**File:** `tests/test_competitor_lock.py:37`, `tests/test_tracking_metrics.py:29`
**Issue:** Tests import `_VALID_CONFIG` (a leading-underscore "private" name) from `tests.conftest`. It works, but importing an underscore-prefixed symbol across modules couples tests to a private fixture-internal. If `_VALID_CONFIG` is renamed/restructured, several tests break opaquely.
**Fix:** Expose a public fixture or helper (e.g. the existing `valid_config_dict` fixture, or a module-level `VALID_CONFIG`) for cross-module reuse rather than reaching into the underscore name.

### IN-05: `DetectionSignal` constructed positionally in synth/tests — fragile to field-order changes

**File:** `src/segugio/synth/detection_stream.py:108-118`, `:180-191`; multiple tests
**Issue:** `DetectionSignal(t, cam_id, cx, cy, w, h, conf, track_id)` relies on positional argument order matching the dataclass field order. The mapper (`signals_map.py`) and several tests use keyword args; the synth generators use positional. A reorder of `DetectionSignal` fields would silently mis-map (e.g. swap `w`/`h` or `conf`/`track_id` if adjacent types coincide). The frozen `==` determinism tests would catch a type mismatch but not a same-type field swap.
**Fix:** Use keyword arguments at every `DetectionSignal` construction site (as `signals_from_boxes` already does) so field order changes fail loudly or are caught by name.

---

_Reviewed: 2026-06-09T23:44:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
