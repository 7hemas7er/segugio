"""Shadow / plausibility guard tests — fully green this plan (02-01).

The cheap pure per-detection gate (``plausibility_ok``) rejects implausible detections
(sub-conf-floor, sub-min-area, out-of-aspect-band) so the scorer treats them as "no
detection" (→ coast) rather than scoring a shadow blob. A rejected detection must never
raise — in particular an ``h == 0`` box must be guarded (no aspect-ratio div-by-zero).
"""

from __future__ import annotations

from segugio.framing.signals import DetectionSignal
from segugio.framing.terms import plausibility_ok


def _det(cx=0.5, cy=0.5, w=0.3, h=0.3, conf=0.7, track_id=1, tick=0) -> DetectionSignal:
    return DetectionSignal(tick, "cam_a", cx, cy, w, h, conf, track_id)


def test_plausible_detection_passes(scorer_params) -> None:
    """A well-formed central, mid-size, confident detection passes the gate."""
    assert plausibility_ok(_det(), scorer_params) is True


def test_sub_conf_floor_rejected(scorer_params) -> None:
    """conf below conf_floor → rejected (treated as no-detection)."""
    assert plausibility_ok(_det(conf=scorer_params.conf_floor - 0.01), scorer_params) is False


def test_sub_min_area_rejected(scorer_params) -> None:
    """w*h below min_area → rejected (noise gate)."""
    tiny = (scorer_params.min_area ** 0.5) / 2.0  # area = tiny^2 < min_area
    assert plausibility_ok(_det(w=tiny, h=tiny), scorer_params) is False


def test_aspect_too_wide_rejected(scorer_params) -> None:
    """aspect (w/h) above aspect_hi → rejected (shadow-streak guard)."""
    # w/h = 0.9/0.1 = 9.0 > aspect_hi (3.5); area 0.09 > min_area, conf ok.
    assert plausibility_ok(_det(w=0.9, h=0.1), scorer_params) is False


def test_aspect_too_tall_rejected(scorer_params) -> None:
    """aspect (w/h) below aspect_lo → rejected."""
    # w/h = 0.1/0.9 ≈ 0.11 < aspect_lo (0.3); area 0.09 > min_area, conf ok.
    assert plausibility_ok(_det(w=0.1, h=0.9), scorer_params) is False


def test_zero_height_does_not_raise(scorer_params) -> None:
    """An h==0 detection is guarded (no div-by-zero on the aspect check) and rejected."""
    result = plausibility_ok(_det(w=0.3, h=0.0), scorer_params)
    assert result is False  # zero area + zero-guarded aspect → not plausible
