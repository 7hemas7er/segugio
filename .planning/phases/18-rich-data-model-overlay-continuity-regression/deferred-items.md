# Deferred Items — Phase 18

Out-of-scope discoveries logged during execution (NOT fixed — pre-existing / unrelated to this phase's changes).

## Pre-existing full-suite failures (confirmed identical at pre-18-02 commit f2408c8)

These 5 failures exist BEFORE any Phase-18 Plan-02 work and are unrelated to the
identity-render / overlay-continuity changes (pure UI JS + tests + docs). They are
environmental on this Windows dev box:

| Test | Likely cause |
|------|--------------|
| `tests/test_ndi_mock_sender.py::test_mock_sender_publishes_named_source` | NDI runtime/hardware not present in this env |
| `tests/test_ndi_source.py::test_receiver_yields_bgr_and_new_frame_ts` | NDI receiver runtime not present |
| `tests/test_ui_explainability.py::test_leaderboard_renders_sorted` | node ESM `mirror.mjs` harness failure (node module/loader) |
| `tests/test_ui_scv_unification.py::test_console_embeds_overlay_iframe` | console.html served-HTML read (mojibake on cp1252) |
| `tests/test_ui_tablet_layout.py::test_touch_action_and_targets` | console.html read mangled by Windows cp1252 (`�`), `class="layout"` not found |

Verified: running these exact 5 node IDs at `f2408c8` (the commit before 18-02 Task 1)
reproduces the identical failures. No regression introduced by 18-02.
