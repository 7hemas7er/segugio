# Phase 16 — Deferred / Out-of-Scope Items

Discovered during execution of Plan 16-01. These are OUT OF SCOPE for this plan
(pre-existing failures unrelated to the score-authoritative work) and are recorded
per the executor SCOPE BOUNDARY rule — NOT fixed here.

## Pre-existing test failures (confirmed failing at phase-start commit `0958d94`)

All five failed identically on the phase-start tree BEFORE any 16-01 change — they are
not regressions from this plan.

| Test | Reason | Domain |
|------|--------|--------|
| `tests/test_ndi_mock_sender.py::test_mock_sender_publishes_named_source` | NDI runtime / named-source not available in this env | NDI hardware |
| `tests/test_ndi_source.py::test_receiver_yields_bgr_and_new_frame_ts` | NDI receiver yields no frame (no live source) | NDI hardware |
| `tests/test_ui_explainability.py::test_leaderboard_renders_sorted` | node ESM `mirror.mjs:65` failure (leaderboard JS), unrelated to score-calc | console JS |
| `tests/test_ui_scv_unification.py::test_console_embeds_overlay_iframe` | `console.html` lacks the expected overlay-iframe embed | console template |
| `tests/test_ui_tablet_layout.py::test_touch_action_and_targets` | `console.html` lacks `class="layout"` two-region markup | console template |

The two `console.html` template failures (scv-unification, tablet-layout) are in the
P17 console-modal/layout surface — Phase 16-01 deliberately does NOT touch `console.html`
(scope fence; its `#form-score` retirement is P17). The NDI + explainability failures are
unrelated subsystems.
