# Deferred items — Phase 17

Out-of-scope discoveries logged during execution (NOT fixed in this phase per the SCOPE BOUNDARY rule).

## Pre-existing stale test assertions (Phase-9-era layout rename)

- **`tests/test_ui_tablet_layout.py::test_touch_action_and_targets`** — fails on `assert 'class="layout"' in html`.
  The console layout was restyled in Phase 9 from a two-region `class="layout"` into `info-strip` / `live-row` /
  `side-col`; the `class="layout"` token no longer exists. This assertion was ALREADY failing on the pre-17-02
  baseline (commit before plan 17-02), independent of the legacy-form retirement. Plan 17-02 updated only the
  `id="form-score"` assertion in this test (its own change surface); the `class="layout"` staleness is left as-is.
  Fix: update the assertion to the current layout class names (`info-strip` / `live-row`).

## Pre-existing unrelated failures (confirmed identical on baseline, not touched by 17-02)

- **`tests/test_ui_explainability.py::test_leaderboard_renders_sorted`** — node ESM mirror harness failure
  (`mirror.mjs` node run), unrelated to score-entry / console-modal work.
- **`tests/test_ui_scv_unification.py::test_console_embeds_overlay_iframe`** — console iframe-embed assertion,
  unrelated to plan 17-02 files.
- **NDI hardware tests** (`test_ndi_mock_sender`, `test_ndi_source`) — hardware/runtime dependent.
