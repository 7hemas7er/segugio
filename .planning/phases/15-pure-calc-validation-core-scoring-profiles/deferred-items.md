# Phase 15 — Deferred / Out-of-Scope Discoveries

Pre-existing test failures observed during 15-01 execution (full-suite run). These are
NOT caused by 15-01's changes (`src/segugio/ui/score_calc.py`, `tests/test_score_calc.py`)
and are out of scope for this plan (SCOPE BOUNDARY). Logged, not fixed.

| Failing test | Category | Note |
|--------------|----------|------|
| `tests/test_ndi_mock_sender.py::test_mock_sender_publishes_named_source` | NDI loopback (environmental) | Known carry-forward — NDI runtime/loopback not present in this CI env (MEMORY.md "2 environmental NDI-loopback CI failures"). |
| `tests/test_ndi_source.py::test_receiver_yields_bgr_and_new_frame_ts` | NDI loopback (environmental) | Same as above. |
| `tests/test_ui_explainability.py::test_leaderboard_renders_sorted` | Node/JS mirror (environmental) | `node failed` running a temp `mirror.mjs` — node fake-DOM harness env. |
| `tests/test_ui_scv_unification.py::test_console_embeds_overlay_iframe` | Node/JS (environmental) | Console iframe/markup assertion in a node-driven UI test. |
| `tests/test_ui_tablet_layout.py::test_touch_action_and_targets` | UI markup (pre-existing) | `class="layout"` / tablet-layout markup assertion unrelated to scoring. |

All `tests/test_score_calc.py` tests (11) pass. The 5 failures above are unrelated to the
pure scoring authority introduced by Plan 15-01.

**15-03 re-confirmation:** the same 5 failures were re-verified pre-existing on baseline
commit `aeaba3d` via `git stash` (they fail identically with 15-03's test-only edit stashed).
15-03 modifies only `tests/test_imports.py`; `tests/test_imports.py` is fully green (26 passed).
