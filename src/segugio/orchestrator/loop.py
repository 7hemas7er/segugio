"""``Orchestrator`` — the fixed-rate, fault-isolated tick (the grown-up ``run_clip_eval``).

This is the live successor of ``tracking/eval.py:run_clip_eval`` and the file that closes the
v1 milestone: it wires every locked Phase 1-4 brain into ONE end-to-end loop —
``FrameSource.latest(cam)`` per camera → per-camera fan-out (``PerCameraTracker.track`` →
``signals_from_boxes`` → ``CompetitorLock.select`` → ``PlausibilityGate.check``) →
``MultiCamScorer.update`` → the ``FeedWatchdog`` alive map → the D-08 action-hold from the
locked subject's motion energy → ``DecisionEngine.tick`` → ``ObsController.cut`` to the target
``Camera.obs_scene`` → the D-11 atomic status write.

The three load-bearing structures copied from ``run_clip_eval`` (05-PATTERNS.md §loop.py):

  1. PER-CAMERA INDEPENDENCE (``eval.py:287-299``): one ``PerCameraTracker`` + one
     ``CompetitorLock`` + one ``PlausibilityGate`` per ``cam.id`` — NEVER a frame list to one
     tracker (#13107). The trackers are INJECTED (so YOLO loads only in the real wiring; the
     headless tests inject fakes); the locks + gates are built here from config (they are pure
     and light).
  2. THE PER-CAMERA FAN-OUT (``eval.py:321-348``): the exact chain, swapping
     ``frame_crops.get(cam_id)`` for ``self.source.latest(cam_id)``, preserving the CR-01
     gate-reset-only-on-genuine-reacquire rule.
  3. THE ONCE-BEFORE-LOOP HARD ReID GATE (``eval.py:303, 329-331``): ``assert_native_reid_engaged``
     is called ONCE after a warmup that ACTUALLY ran inference (``results is not None``); it
     RAISES on the silent ``yolo26n-cls.pt`` fallback (TRK-02).

ROBUSTNESS (RBT-04, threat T-05-06-01, "nessun crash ammesso"): every tick stage is wrapped so
a raised exception (frame pull / track / scorer / engine / OBS / channel) is caught → logged →
the loop coasts to SAFE and keeps ticking; the process NEVER exits. ``shutdown()`` cuts to SAFE,
stops the source, and closes OBS. Malformed operator files are absorbed at the channel boundary
(``opcomm.channel`` returns the last-good/default and never raises into the loop).

D-09 run-state STEERS the loop: ``just_started`` resets the ``CompetitorLock``s; while STOPPED
the loop parks the director on SAFE (passing a synthetic park toward the is_safe target;
Override still wins, RBT-03 — the top FSM tier). D-10 override is read each tick and passed into
the FSM as an ``OverrideCmd``. D-11 status is written atomically ON CHANGE.

LATENCY (RBT-05): :meth:`run_measured` instruments each tick stage with ``perf_counter`` deltas
(ingest-pull / YOLO / score / FSM / OBS-cut) ADDITIVELY — it does not change the pipeline logic —
and returns per-stage + total timings for the latency harness (see ``tests/test_latency.py``).

DETERMINISM (the Phase-1 convention): the orchestrator OWNS the wall-clock (the rate-limiter in
:meth:`run` + the latency probe) and the threads — everything it calls stays clock-free and
injected-value-testable. ``tick`` is an injected integer index. In the headless ``run_measured``
mode the per-tick ``now`` is derived from the tick (matching the mock source's tick-derived
timestamps) so liveness is deterministic off-GPU; the real ``run`` uses ``time.monotonic``.

LAZY-IMPORT BOUNDARY: this module imports only LIGHT deps (stdlib + loguru + the pure segugio
surfaces). ``import segugio.orchestrator.loop`` succeeds with cyndilib / obsws / ultralytics /
torch / cv2 / Flask ABSENT — the heavy clients live ONLY inside the injected real
implementations (the real ``FrameSource`` / ``ObsController`` / ``PerCameraTracker``).
"""

from __future__ import annotations

import collections
import time
from typing import TYPE_CHECKING

from loguru import logger

from ..decision.signals import SAFE_TARGET
from ..obs.mapping import scene_for
from ..opcomm.channel import read_command, read_runstate, write_status
from ..opcomm.records import DirectorStatus
from ..tracking.competitor_lock import CompetitorLock
from ..tracking.plausibility import PlausibilityGate
from ..tracking.signals_map import signals_from_boxes

if TYPE_CHECKING:  # type-only — keeps heavy deps off the runtime import path
    from ..config.models import Config

__all__ = ["Orchestrator"]

# The decision-loop stages the latency probe times (RBT-05). OBS-cut is measured but is off the
# inference critical path (the dominant ~35-60ms tail is the websocket round-trip, not compute).
_LATENCY_STAGES = ("ingest", "yolo", "score", "fsm", "obs")

# Degradation ladder (RBT-05 / TECHNICAL-RESEARCH): if the measured total p95 exceeds the
# budget on the Windows/RTX box, act on these trigger points IN ORDER. Recorded here (and
# logged in run_measured) so the on-Windows run can apply them — this loop does not auto-tune.
_DEGRADATION_LADDER = (
    "1) swap yolo26s.pt -> yolo26n.pt (config model.path)",
    "2) reduce active cameras (fewer per-camera trackers)",
    "3) lower the AI-path imgsz / tick fps",
)


def _arrays_from_results(results):
    """Extract ``(xywhn, ids, confs)`` plain lists from one YOLO ``Results`` row (or None).

    Byte-for-byte the ``eval.py:_arrays_from_results`` contract: ``Results.boxes`` may be
    ``None`` or have ``.id is None`` (no confirmed track) — both degrade to ``([], None, [])``
    so ``signals_from_boxes`` coasts. ``.cpu().numpy().tolist()`` brings the tensors to plain
    Python so the pure mapper never sees a live GPU tensor. Kept LOCAL (not imported from eval)
    so this loop never imports the cv2-edge module.
    """
    if results is None or getattr(results, "boxes", None) is None:
        return [], None, []
    boxes = results.boxes
    if boxes.id is None:  # no confirmed track this frame → coast
        return [], None, []
    xywhn = boxes.xywhn.cpu().numpy().tolist()
    ids = boxes.id.cpu().numpy().astype(int).tolist()
    confs = boxes.conf.cpu().numpy().tolist()
    return xywhn, ids, confs


class Orchestrator:
    """The fixed-rate fault-isolated tick (RBT-04/05, D-08/09/10/11).

    Construct with the validated ``Config`` and the injected collaborators (the
    ``FrameSource``, the ``ObsController``, the pre-built ``MultiCamScorer`` /
    ``DecisionEngine`` / ``FeedWatchdog`` / ``ActionHoldDeriver``, the operator↔system
    ``channel_paths`` bundle, and the per-camera ``trackers`` dict). Prefer :meth:`from_config`
    which builds the scorer/engine/watchdog/deriver from the Config for you.

    Args:
        config: the validated ``Config`` (cameras / thresholds / framing / action_hold).
        source: a ``FrameSource`` (``start``/``latest``/``last_frame_ts``/``stop``).
        obs: an ``ObsController`` (``connect``/``cut``/``set_overlay_text``/``close``).
        scorer: the ``MultiCamScorer`` (one ``CameraScorer`` per camera).
        engine: the ``DecisionEngine`` (the camera-switching FSM).
        watchdog: the ``FeedWatchdog`` (pure last-NEW-frame liveness math).
        action_hold: the ``ActionHoldDeriver`` (D-08 motion energy → ``HoldInput.action``).
        channel_paths: a mapping with ``command`` / ``runstate`` / ``status`` (and optionally
            ``score`` / ``overlay``) Path/str entries — the operator↔system files.
        trackers: ``{cam_id: PerCameraTracker}`` — INJECTED so YOLO loads only in real wiring
            (headless tests inject fakes). Each tracker exposes ``track(frame)`` and (for the
            real impl) ``.model`` for the once-before-loop ReID gate.
    """

    def __init__(
        self,
        config: "Config",
        source,
        obs,
        scorer,
        engine,
        watchdog,
        action_hold,
        channel_paths,
        trackers,
        preview=None,
    ) -> None:
        self.config = config
        self.cameras = list(config.cameras)
        self.source = source
        self.obs = obs
        self.scorer = scorer
        self.engine = engine
        self.watchdog = watchdog
        self.action_hold = action_hold
        self.trackers = dict(trackers)
        # The off-tick preview publisher (Phase 7, D-02/D-06). None when preview is disabled —
        # in which case EVERY new tick-path call below is skipped and the loop is byte-identical
        # to v1.0 (no offer(), no cuts ring feed, no start/stop). The tick NEVER waits on it: the
        # guarded offer() is a single locked mailbox assignment that rides inside the RBT-04 try.
        self._preview = preview

        # Operator↔system file paths (str so the channel's open() is happy on any Path type).
        self._cmd_path = str(channel_paths["command"])
        self._runstate_path = str(channel_paths["runstate"])
        self._status_path = str(channel_paths["status"])

        # PER-CAMERA INDEPENDENCE (eval.py:287-299): one lock + one gate per camera. The locks
        # and gates are PURE/light so they are built here from config; the trackers are injected.
        self.cam_ids = [cam.id for cam in self.cameras]
        self.locks: dict = {cam.id: CompetitorLock(cam, config.tracking) for cam in self.cameras}
        self.gates: dict = {cam.id: PlausibilityGate(config.tracking) for cam in self.cameras}
        # Per-camera previously-selected locked id — drives the CR-01 gate-reset-only-on-genuine-
        # reacquire rule (mirrors eval.py:294).
        self._last_selected_id: dict = {cam.id: None for cam in self.cameras}

        # The is_safe camera id (the D-09 park target) — resolved once (config guarantees one).
        self._safe_cam_id = next(c.id for c in self.cameras if c.is_safe)

        # Loop / lifecycle state.
        self._stopping = False
        self._reid_checked = False
        self._dog_idx_resolved: set = set()
        self._last_status: DirectorStatus | None = None  # write-on-change (D-11)

        # The D-08 recent-cuts ring (Pitfall 5): the orchestrator OWNS the cut history (not the
        # publisher) so a DROPPED preview frame never loses a cut. Bounded at 16 — appended at the
        # _apply target-change edge, snapshotted into each offer(). maxlen makes it self-evicting.
        self._cuts_ring: collections.deque = collections.deque(maxlen=16)

        # Latency probe accumulator (RBT-05) — additive; never changes pipeline logic.
        self._latency: dict[str, list[float]] = {s: [] for s in _LATENCY_STAGES}
        self._latency_total: list[float] = []

    # ----- construction convenience ----------------------------------------- #

    @classmethod
    def from_config(
        cls,
        config: "Config",
        source,
        obs,
        channel_paths,
        trackers,
        fps: float = 30.0,
        grace: float | None = None,
        preview=None,
    ) -> "Orchestrator":
        """Build the scorer/engine/watchdog/deriver from ``config`` and return an Orchestrator.

        The collaborators are constructed exactly as ``run_clip_eval`` / Phase-3 wiring expect:
        the scorer takes the per-discipline ``lead_room`` gain + the coast ``ttl_ticks`` (from
        ``framing_defaults`` and ``fps``); the engine takes the discipline ``hold_length_s``;
        the watchdog takes ``Thresholds.watchdog_timeout``; the deriver takes ``action_hold``.
        """
        from ..decision.engine import DecisionEngine
        from ..framing.scorer import MultiCamScorer, ttl_ticks_from_seconds
        from ..watchdog_feed.liveness import FeedWatchdog
        from .action_hold import ActionHoldDeriver

        fd = config.field.framing_defaults
        ttl_ticks = ttl_ticks_from_seconds(fd.hold_length_s, fps)
        scorer = MultiCamScorer(
            config.cameras,
            config.scoring,
            config.framing_weights,
            config.thresholds.alpha,
            fd.lead_room,
            ttl_ticks,
        )
        engine = DecisionEngine(
            config.cameras,
            config.thresholds,
            fps=fps,
            hold_length_s=fd.hold_length_s,
        )
        # WR-02 anti-jitter grace: when no explicit grace is passed, source the non-zero seed
        # from config (config.thresholds.watchdog_grace > 0). An explicit grace arg still wins
        # (callers/tests can override). Net: from_config(...) with no grace yields a non-zero
        # config-sourced grace so a single late frame no longer flaps the feed dead (T-05-04-02).
        if grace is None:
            grace = config.thresholds.watchdog_grace
        watchdog = FeedWatchdog(config.thresholds.watchdog_timeout, grace=grace)
        deriver = ActionHoldDeriver(config.action_hold)
        return cls(
            config=config,
            source=source,
            obs=obs,
            scorer=scorer,
            engine=engine,
            watchdog=watchdog,
            action_hold=deriver,
            channel_paths=channel_paths,
            trackers=trackers,
            preview=preview,
        )

    # ----- the per-camera fan-out (eval.py:321-348) ------------------------- #

    def _supports_batched(self) -> bool:
        """True when the per-camera trackers expose the batched-detect dispatch seam.

        The Track-B batched path (ONE forward → N ``tracker.update()`` dispatches) needs each
        tracker to expose a shared ``.model`` (for the single forward) AND an
        ``.update(detections, frame)`` association entry point. The real ``PerCameraTracker``
        (06-02) and the headless batched fakes do; the legacy mock-timed ``_FixedCostTracker``
        (``.track()``-only) does NOT — those fall back to the serial path, keeping the
        mock-timed wiring/attribution latency tests byte-for-byte green.
        """
        if not self.trackers:
            return False
        return all(
            hasattr(t, "model") and hasattr(t, "update") for t in self.trackers.values()
        )

    def _fan_out(self, tick: int) -> "tuple[dict, float, dict]":
        """Run the per-camera inference→signals→lock→gate chain.

        Returns ``(dets_by_cam, locked_energy, frames_by_cam)``.

        Two inference shapes, the SAME downstream chain:
          * BATCHED (Track-B, the FP16 latency path): when every tracker exposes ``.model`` +
            ``.update`` (``_supports_batched``), run ONE batched detection forward over all
            camera frames via :func:`batched_detect_dispatch` (``half=config.model.use_fp16``,
            ``end2end=False`` → native ReID engageable) and dispatch each camera's OWN
            detections to its OWN persistent tracker (#13107). This collapses the 4 serial
            ``model.track()`` forwards into 1 — the Wave-1 latency win.
          * SERIAL (legacy fallback): N per-camera ``tracker.track(frame)`` calls — preserved
            for the mock-timed latency harness (``_FixedCostTracker``) and any ``.track``-only
            tracker.

        Either way the once-before-loop HARD ReID gate (TRK-02, now threading ``is_engine``),
        the dog-index-by-name resolve (CR-02), the CR-01 gate-reset-only-on-genuine-reacquire
        rule, the per-camera degrade-to-None coast (RBT-04), and the locked-energy max are
        preserved verbatim. Returns the per-camera ``DetectionSignal | None`` map (the
        ``MultiCamScorer.update`` consumer shape), the LOCKED subject's motion energy, AND the
        per-camera raw frames (``frames_by_cam``) surfaced from whichever inference path ran —
        so the guarded preview ``offer()`` reuses the frames the tick already pulled and does NOT
        call ``source.latest()`` a second time (a second pull could return a DIFFERENT frame and
        costs another lock; RESEARCH L376-380). ``frames_by_cam`` is ``{cam_id: frame|None}``.
        """
        if self._supports_batched():
            results_by_cam, frames_by_cam = self._batched_inference(tick)
        else:
            results_by_cam, frames_by_cam = self._serial_inference(tick)

        dets_by_cam: dict = {}
        locked_energy = 0.0
        for cam in self.cameras:
            cam_id = cam.id
            results = results_by_cam.get(cam_id)

            # Edge → signals → lock → gate → the per-camera DetectionSignal | None.
            xywhn, ids, confs = _arrays_from_results(results)
            candidates = signals_from_boxes(xywhn, ids, confs, tick, cam_id)
            prev_sel_id = self._last_selected_id[cam_id]
            selected = self.locks[cam_id].select(candidates, tick)
            cur_sel_id = selected.track_id if selected is not None else None
            # Gate-reset ONLY on a genuine re-acquire (the locked identity changed), never on a
            # transient coast (CR-01 / TRK-05 teleport guard).
            if cur_sel_id is not None and cur_sel_id != prev_sel_id:
                self.gates[cam_id].reset()
            self._last_selected_id[cam_id] = cur_sel_id
            signal = self.gates[cam_id].check(selected)
            dets_by_cam[cam_id] = signal

            # D-08: the locked subject's motion energy for THIS camera (0.0 when nothing locked).
            energy = self.locks[cam_id].locked_motion_energy()
            if energy > locked_energy:
                locked_energy = energy
        return dets_by_cam, locked_energy, frames_by_cam

    def _resolve_dog_idx_once(self, tracker, cam_id: str) -> None:
        """Resolve the dog index BY NAME once per camera before its first inference (CR-02).

        Only for a real tracker (it carries ``.model`` + ``.dog_idx``); headless fakes without a
        ``.names``-bearing model are tolerated (the resolve is best-effort and skipped on a fake
        model that has no ``names``).
        """
        if cam_id in self._dog_idx_resolved or not hasattr(tracker, "model"):
            return
        from ..tracking.detector import resolve_dog_index

        try:
            tracker.dog_idx = resolve_dog_index(
                tracker.model, self.config.model.class_index
            )
        except (AttributeError, TypeError):
            # A fake model with no usable ``.names`` — keep the configured index (headless test).
            pass
        self._dog_idx_resolved.add(cam_id)

    def _maybe_reid_gate(self, tracker, ran_inference: bool, bot=None) -> None:
        """Run the HARD TRK-02 ReID gate ONCE, after a warmup that ACTUALLY ran inference.

        Threads ``is_engine`` (``getattr(tracker, "is_engine", False)``) so the eager ``.pt`` /
        FP16 path keeps the HARD raise while an engine-backed model (06-03) downgrades to a
        warning (the gate's own engine-aware logic). Only fires for a real tracker (carrying
        ``.model``); the headless ``.update``-fake carries a ``.model`` too, so tests stub the
        gate.

        ``bot`` (the batched Track-B path) is the directly-built per-camera ``BOTSORT`` to inspect
        — the batched path never builds ``predictor.trackers``, so the gate inspects this encoder +
        ``predictor._hook`` instead. ``None`` (the serial path) keeps the original
        ``predictor.trackers[0]`` inspection.
        """
        if self._reid_checked or not ran_inference or not hasattr(tracker, "model"):
            return
        from ..tracking.reid_check import assert_native_reid_engaged

        is_engine = bool(getattr(tracker, "is_engine", False))
        assert_native_reid_engaged(tracker.model, is_engine=is_engine, bot=bot)
        self._reid_checked = True

    def _serial_inference(self, tick: int) -> "tuple[dict, dict]":
        """N per-camera ``tracker.track(frame)`` forwards (the legacy / mock-timed path).

        Returns ``(results_by_cam, frames_by_cam)`` — ``frames_by_cam`` captures the SAME frame
        each tracker.track(frame) saw (the single source.latest pull), so the preview offer reuses
        it with NO second source.latest() call (RESEARCH L376-380).
        """
        results_by_cam: dict = {}
        frames_by_cam: dict = {}
        for cam in self.cameras:
            cam_id = cam.id
            tracker = self.trackers[cam_id]
            frame = self.source.latest(cam_id)  # newest BGR frame, or None → coast
            frames_by_cam[cam_id] = frame
            self._resolve_dog_idx_once(tracker, cam_id)
            results = tracker.track(frame)  # None on a blank/decode-failure frame → coast
            self._maybe_reid_gate(tracker, ran_inference=results is not None)
            results_by_cam[cam_id] = results
        return results_by_cam, frames_by_cam

    def _batched_inference(self, tick: int) -> "tuple[dict, dict]":
        """ONE batched FP16 detection forward → N per-camera ``tracker.update()`` dispatches.

        Gathers ``source.latest(cam_id)`` for every camera, sources the ONE shared detection
        model from any per-camera tracker's ``.model`` (they share the weights), resolves the
        dog index by name once, runs :func:`batched_detect_dispatch` ONCE
        (``half=config.model.use_fp16``, ``end2end=False``), then runs the HARD ReID gate once.
        Never passes a frame list to ``model.track()`` (#13107). Returns
        ``(results_by_cam, frames_by_cam)`` — ``frames_by_cam`` is the SAME single-pull dict the
        batched forward consumed, surfaced for the preview offer (no second source.latest()).
        """
        from ..tracking.batched import batched_detect_dispatch

        frames_by_cam = {cam.id: self.source.latest(cam.id) for cam in self.cameras}

        # The ONE shared model + the dog index (resolved by name once, on any tracker's model).
        any_tracker = next(iter(self.trackers.values()))
        first_cam = self.cameras[0].id
        self._resolve_dog_idx_once(any_tracker, first_cam)
        model = any_tracker.model
        dog_idx = getattr(any_tracker, "dog_idx", self.config.model.class_index)

        results_by_cam = batched_detect_dispatch(
            model,
            frames_by_cam,
            self.trackers,
            dog_idx,
            tick,
            use_fp16=self.config.model.use_fp16,
        )

        # The HARD ReID gate ONCE, after a tick that ACTUALLY ran inference (any live result).
        # The batched path builds one BOTSORT per cam_id DIRECTLY (no predictor.trackers), so we
        # hand the gate a built ``_bot`` to inspect (any live camera built its own during the
        # dispatch above). When no real tracker built a ``_bot`` (headless fakes override
        # ``update`` without one), gate_bot stays None and the gate falls back to the
        # ``predictor.trackers`` shape the fakes provide.
        ran_inference = any(r is not None for r in results_by_cam.values())
        gate_bot = next(
            (b for b in (getattr(t, "_bot", None) for t in self.trackers.values()) if b is not None),
            None,
        )
        self._maybe_reid_gate(any_tracker, ran_inference=ran_inference, bot=gate_bot)
        return results_by_cam, frames_by_cam

    # ----- per-tick orchestration ------------------------------------------- #

    def _read_run_and_override(self):
        """Read the run-state + override command at the channel boundary (never raises).

        Returns ``(run, override)`` — a 2-tuple. (``just_started`` is NOT returned separately;
        the caller reads ``run.just_started`` off the returned ``run`` record.) The channel's
        ``read_*`` absorb malformed / absent files (return last-good/default), so this is
        exception-free by construction (RBT-04 / threat T-05-06-02).
        """
        run = read_runstate(self._runstate_path)
        cmd = read_command(self._cmd_path)
        override = cmd.to_override() if cmd is not None else None
        return run, override

    def _decide(self, tick: int, scores, alive, holds, override, run):
        """Run the FSM tick with the D-09 STOP-parks-on-SAFE steering (Override still wins).

        While the run is STOPPED and the operator has NOT issued a live override, the loop parks
        the director on the SAFE SENTINEL: it still advances the FSM (``to_safe()`` keeps the
        FSM's clocks/state coherent for the next START) and returns a synthetic SAFE
        ``Decision`` so the status/cut report the SAFE sentinel (``live_cam == "SAFE"``), not a
        camera id. Override is the TOP tier (RBT-03) so a live override during STOP still wins —
        in that case the normal ``engine.tick`` runs with the override and decides as usual.
        This avoids a new FSM state (RESEARCH OQ3 / D-09 discretion).
        """
        if run.stopped and override is None:
            self.engine.to_safe()  # advance the FSM to SAFE (keeps clocks coherent for START)
            from ..decision.signals import Decision, Mode

            return Decision(
                tick=scores[0].tick if scores else tick,
                target=SAFE_TARGET,
                mode=Mode(self.engine.state),
                reason="none",
            )
        return self.engine.tick(scores, alive, holds, override)

    def _status_for(self, decision, alive) -> DirectorStatus:
        """Map a ``Decision`` + the alive map → the D-11 ``DirectorStatus`` (live cam + reason).

        ``reason`` mapping (Decision.reason + the alive map → the D-11 advisory tag the panel
        renders): ``override``/``override_dead_fallback`` → ``override``; ``feed_emergency`` →
        ``feed-dead``; a SAFE target with no live feed → ``feed-dead``; a SAFE target WITH a live
        feed (nothing tracked) → ``subject-lost``; ``auto_switch`` → ``auto``; otherwise the
        steady-state ``auto`` (or ``subject-lost`` when parked on SAFE with live feeds).
        """
        r = decision.reason
        target = decision.target
        any_alive = any(alive.values())
        if r in ("override", "override_dead_fallback"):
            reason = "override"
        elif r == "feed_emergency":
            reason = "feed-dead"
        elif target == SAFE_TARGET:
            # Parked on SAFE: distinguish "all feeds dead" from "feeds live but nothing tracked".
            reason = "subject-lost" if any_alive else "feed-dead"
        elif r == "auto_switch":
            reason = "auto"
        else:
            # Steady state on a live camera (reason "none"/"hold") → auto.
            reason = "auto"
        # live_cam is the camera id; a SAFE target passes the SAFE sentinel through (the panel
        # renders it as "SAFE"), which the existing status tests assert.
        return DirectorStatus(live_cam=target, reason=reason, alive=dict(alive))

    def _apply(self, decision, alive, tick: int = 0) -> None:
        """Cut OBS to the decision's scene + write the D-11 status on change (never raises here).

        ``scene_for`` maps the target (SAFE sentinel → the is_safe camera's obs_scene) to the OBS
        scene; the cut is attempted inside the caller's try/except so a websocket drop coasts.
        The status write is atomic and only happens when the status actually CHANGED (D-11).

        D-08 cuts ring (Pitfall 5): when the status changed AND the LIVE target moved to a
        different camera, append ``{tick, from, to, reason}`` to ``self._cuts_ring`` (the
        orchestrator-owned cut history, snapshotted into each preview offer). The ring is fed here
        — at the same change edge that writes the status — so a dropped preview frame never loses
        a cut. The previous live cam is read from ``self._last_status`` BEFORE it is reassigned.
        """
        scene = scene_for(decision, self.cameras)
        self.obs.cut(scene)
        status = self._status_for(decision, alive)
        if status != self._last_status:
            prev_live = self._last_status.live_cam if self._last_status is not None else None
            if status.live_cam != prev_live:
                self._cuts_ring.append(
                    {
                        "tick": tick,
                        "from": prev_live,
                        "to": status.live_cam,
                        "reason": status.reason,
                    }
                )
            write_status(self._status_path, status)
            self._last_status = status

    def _to_safe(self, reason: str, alive: dict | None = None) -> None:
        """Coast the director to SAFE (a fault degraded a stage) — best-effort, never raises.

        The single fault sink (RBT-04 / Pitfall 7): cut to the SAFE scene and record a SAFE
        status. Wrapped so even the SAFE cut failing (a hard-down OBS) cannot crash the loop.
        """
        alive = alive if alive is not None else {cam.id: False for cam in self.cameras}
        try:
            safe_scene = next(c.obs_scene for c in self.cameras if c.is_safe)
            self.obs.cut(safe_scene)
        except Exception as exc:  # noqa: BLE001 — even a failed SAFE cut must not crash
            logger.warning("SAFE cut failed (coasting): {}", exc)
        status = DirectorStatus(live_cam=SAFE_TARGET, reason=reason, alive=dict(alive))
        if status != self._last_status:
            try:
                write_status(self._status_path, status)
                self._last_status = status
            except Exception as exc:  # noqa: BLE001 — a failed status write must not crash
                logger.warning("SAFE status write failed (coasting): {}", exc)

    def _tick_once(self, tick: int, now: float, probe: dict | None = None) -> None:
        """Run ONE fully fault-isolated tick. A raised stage is caught → coast to SAFE.

        ``probe`` (when given) accumulates per-stage perf_counter deltas (RBT-05) ADDITIVELY —
        the pipeline logic is identical with or without it. ``now`` is the injected wall-clock
        the watchdog reads (the loop owns the clock; the pipeline stays clock-free).
        """
        alive: dict = {}
        try:
            # (ingest) per-camera frame pull is folded into the fan-out's source.latest calls,
            # so we time the whole fan-out under 'ingest'+'yolo' boundaries: the source pull is
            # 'ingest', the tracker.track inference is 'yolo'. They interleave per camera, so we
            # time the combined fan-out and attribute it to 'yolo' (the dominant inference cost),
            # recording a nominal 'ingest' separately around the source readiness.
            t0 = time.perf_counter()
            dets_by_cam, locked_energy, frames_by_cam = self._fan_out(tick)
            t_fan = time.perf_counter()

            holds = self.action_hold.derive(locked_energy)
            scores = self.scorer.update(dets_by_cam, tick)
            t_score = time.perf_counter()

            alive = self.watchdog.alive_map(now, self.source, self.cam_ids)
            run, override = self._read_run_and_override()
            if run.just_started:
                self._reset_locks()
            decision = self._decide(tick, scores, alive, holds, override, run)
            t_fsm = time.perf_counter()

            self._apply(decision, alive, tick)
            # ── D-02/PRV-01: the ONLY hot-path preview touch. A single locked mailbox assignment
            # (offer never blocks — the publisher's own daemon does all resize/encode/IO off-tick).
            # It rides INSIDE this RBT-04 try so a publisher fault coasts via the catch below
            # (the tick still completes and status.json is still written). Guarded by `is not None`
            # so a disabled publisher (D-06) is byte-identical to v1.0. Reuses frames_by_cam from
            # the fan-out — NO second source.latest(). cuts is a snapshot of the orchestrator ring.
            if self._preview is not None:
                self._preview.offer(
                    frames_by_cam, scores, dets_by_cam, decision, list(self._cuts_ring)
                )
            t_obs = time.perf_counter()

            if probe is not None:
                # Attribute fan-out time to YOLO (the dominant inference stage); ingest is the
                # source-pull share (kept nominal/zero here as latest() is O(1) on the mock —
                # the real receiver-thread pull is also O(1), the network cost is off-tick).
                probe["ingest"].append(0.0)
                probe["yolo"].append(t_fan - t0)
                probe["score"].append(t_score - t_fan)
                probe["fsm"].append(t_fsm - t_score)
                probe["obs"].append(t_obs - t_fsm)
                probe["total"].append(t_obs - t0)
        except Exception as exc:  # noqa: BLE001 — RBT-04: ANY stage fault → coast to SAFE
            logger.exception("tick {} failed → SAFE coast: {}", tick, exc)
            # WR-09: a non-feed fault (scorer/FSM/OBS exception) is NOT a dead feed — report a
            # distinct advisory "fault" so the operator panel does not mislabel it "feed-dead".
            # Genuine feed deaths (feed_emergency / all-dead SAFE) keep "feed-dead" in
            # _status_for; only this exception catch-all changes.
            self._to_safe(reason="fault", alive=alive)

    def _reset_locks(self) -> None:
        """Reset every ``CompetitorLock`` (D-09 START: a fresh run re-acquires the subject)."""
        for cam in self.cameras:
            self.locks[cam.id] = CompetitorLock(cam, self.config.tracking)
            self.gates[cam.id].reset()
            self._last_selected_id[cam.id] = None

    # ----- public lifecycle ------------------------------------------------- #

    def _safe_startup(self, label: str, fn) -> None:
        """Fault-isolate ONE startup callable (source.start / obs.connect) — coast on failure.

        CR-01 (RBT-04, threat T-05-07-01/02 "nessun crash ammesso"): OBS/NDI may be DOWN at
        launch (a normal field condition). A startup call that raises must NOT terminate the
        director — it is caught, logged, and the loop coasts into the tick loop. The per-tick
        ``ObsWsController._safe_call`` heals the OBS reconnection each tick and the watchdog
        handles a dead source, so reaching the tick loop is sufficient to satisfy "never crash".
        """
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — a down OBS/NDI at launch must not crash
            logger.warning("startup {} failed (coasting into tick loop): {}", label, exc)

    def run(self, rate_hz: float = 30.0) -> None:
        """The live fixed-rate loop (owns the wall-clock). Ticks until :meth:`stop` is called.

        Starts the source + connects OBS, then ticks at ``rate_hz`` pulling the newest frame per
        camera and running the fault-isolated pipeline. ``finally:`` cuts to SAFE, stops the
        source, and closes OBS (RBT-04 SAFE shutdown). The wall-clock (``time.monotonic`` for the
        watchdog, ``time.perf_counter`` for the rate-limiter) lives ONLY here.
        """
        period = 1.0 / rate_hz if rate_hz > 0 else 0.0
        self._stopping = False
        self._safe_startup("source.start", self.source.start)
        self._safe_startup("obs.connect", self.obs.connect)
        if self._preview is not None:
            self._safe_startup("preview.start", self._preview.start)
        tick = 0
        try:
            while not self._stopping:
                t_start = time.perf_counter()
                self._tick_once(tick, now=time.monotonic())
                tick += 1
                # Fixed-rate sleep (never negative).
                elapsed = time.perf_counter() - t_start
                if period > elapsed:
                    time.sleep(period - elapsed)
        finally:
            self.shutdown()

    def run_measured(self, n_ticks: int) -> dict:
        """Drive a BOUNDED number of fault-isolated ticks; return per-stage + total timings.

        The headless / off-GPU harness entry (RBT-05). Starts the source + connects OBS, drives
        ``n_ticks`` ticks (pumping the mock source each tick when it exposes ``pump``), times each
        stage with ``perf_counter`` (additive — same pipeline), and returns
        ``{stage: [per-tick seconds], "total": [...]}``. ``now`` is derived from the tick (matching
        the mock source's tick-derived timestamps) so liveness is DETERMINISTIC off-GPU. Does NOT
        shut down (the caller may inspect state / call :meth:`shutdown`).
        """
        probe: dict[str, list[float]] = {s: [] for s in _LATENCY_STAGES}
        probe["total"] = []
        self._stopping = False
        self._safe_startup("source.start", self.source.start)
        self._safe_startup("obs.connect", self.obs.connect)
        if self._preview is not None:
            self._safe_startup("preview.start", self._preview.start)
        for tick in range(n_ticks):
            # Pump the mock source one emitted frame per tick (no-op for sources without pump).
            pump = getattr(self.source, "pump", None)
            if callable(pump):
                pump()
            # Tick-derived now: matches the mock source's ts (= tick + 1.0) so a freshly-published
            # frame is alive (gap 0) and a stalled feed goes dead as `now` advances past its ts.
            self._tick_once(tick, now=float(tick) + 1.0, probe=probe)
        # Persist into the instance accumulator (so multiple measured runs aggregate).
        for stage in _LATENCY_STAGES:
            self._latency[stage].extend(probe[stage])
        self._latency_total.extend(probe["total"])
        logger.debug(
            "latency probe over {} ticks (degradation ladder if over budget: {})",
            n_ticks,
            " | ".join(_DEGRADATION_LADDER),
        )
        return probe

    def stop(self) -> None:
        """Signal the live :meth:`run` loop to exit after the current tick."""
        self._stopping = True

    def shutdown(self) -> None:
        """Cut to SAFE, stop the source, close OBS — the RBT-04 SAFE shutdown (never raises)."""
        self._to_safe(reason="shutdown")
        if self._preview is not None:
            try:
                self._preview.stop()
            except Exception as exc:  # noqa: BLE001 — teardown must not crash on the publisher
                logger.warning("preview.stop() coasted: {}", exc)
        try:
            self.source.stop()
        except Exception as exc:  # noqa: BLE001 — teardown must not crash
            logger.warning("source.stop() failed on shutdown (coasting): {}", exc)
        try:
            self.obs.close()
        except Exception as exc:  # noqa: BLE001 — teardown must not crash
            logger.warning("obs.close() failed on shutdown (coasting): {}", exc)
