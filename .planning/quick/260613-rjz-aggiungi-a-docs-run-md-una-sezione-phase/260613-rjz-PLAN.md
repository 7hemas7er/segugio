---
phase: quick-260613-rjz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [docs/run.md]
autonomous: true
requirements: [DOC-PHASE8-RUN]
must_haves:
  truths:
    - "docs/run.md has a new '## Phase 8 — Console multiview live' section that did not exist before"
    - "Every command, env var, route, and config field in the new section matches the shipped code (app.py / models.py / pyproject.toml / ndi_source.py / tools/verify_ndi_hx_decode.py)"
    - "All existing run.md content (Phase 5 / Phase 6 sections) is untouched"
  artifacts:
    - path: "docs/run.md"
      provides: "Phase 8 console-multiview launch + troubleshooting documentation"
      contains: "Phase 8 — Console multiview live"
  key_links:
    - from: "docs/run.md Phase 8 section"
      to: "src/segugio/ui/app.py"
      via: "documented env vars + routes copied verbatim from the entrypoint"
      pattern: "SEGUGIO_OPCOMM_DIR|SEGUGIO_CAM_IDS|SEGUGIO_CONFIG"
---

<objective>
Append a new "## Phase 8 — Console multiview live" section to `docs/run.md` documenting how to
launch the live multiview console introduced in Phase 8 (MVW-01/02/03, UXT-02, plus the Phase-8
preview-bandwidth cap and the Phase-8 threat re-eval). The existing run.md covers Phase 5
(orchestrator launch) and Phase 6 (GPU latency env) but never mentions the Phase-8 console serving
live preview tiles — operators have no documented launch procedure for it.

Purpose: Give the rig operator a verified, copy-paste-correct launch + troubleshooting procedure
for the two-process (light console / heavy orchestrator) multiview, so the live preview grid
actually populates and the "phone shows in OBS but not in the console" failure is diagnosable.

Output: An extended `docs/run.md` with one new section, all commands/env-vars/routes/config-fields
matching the shipped code. NO source changes, NO tests.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/run.md
@src/segugio/ui/app.py
@src/segugio/config/models.py
@docs/security.md
@pyproject.toml
@src/segugio/ndi/ndi_source.py
@tools/verify_ndi_hx_decode.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Append the "Phase 8 — Console multiview live" section to docs/run.md</name>
  <files>docs/run.md</files>
  <action>
Before writing a single line, RE-READ the five source files and copy exact identifiers — do NOT
invent or paraphrase any command, env var, route, or config field. The section is a faithful
mirror of shipped code:
  - `src/segugio/ui/app.py` — the `if __name__ == "__main__"` block: env vars
    `SEGUGIO_OPCOMM_DIR` (default `./opcomm` next to cwd), `SEGUGIO_CAM_IDS` (comma-separated
    list, takes precedence), `SEGUGIO_CONFIG` (path — loads `[cam.id for cam in
    load_config(...).cameras]`), the hardcoded default cam_ids fallback
    `["cam_wide", "cam_long", "cam_low", "cam_handler"]`; the `from waitress import serve` →
    `serve(app, host="0.0.0.0", port=8080)` path with the `except ImportError:` fallback to
    `app.run(host="0.0.0.0", port=8080, threaded=True)`; the routes `GET /preview` and
    `GET /preview/<cam>.jpg`; the on-disk JPEG path `preview/cam_{cam}.jpg` (note the Pitfall-3
    double-prefix: id `cam_wide` → file `cam_cam_wide.jpg`); the `cam_ids` whitelist semantics
    (unknown id → 404).
  - `src/segugio/config/models.py` — `PreviewParams.max_total_mbps` (default `8.0`),
    `PreviewParams.enabled` (default `True`), and the `Config._preview_bitrate_within_cap`
    `@model_validator(mode="after")` that raises `ValueError` (→ loader `SystemExit(2)`) when the
    worst-case `est_bytes × 8 × fps × N_cams / 1e6` exceeds the cap; `enabled=false` short-circuits.
  - `pyproject.toml` — `[console]` optional extra = `waitress==3.0.2`; `[heavy]` extra =
    ultralytics/cyndilib/obsws-python/watchdog/opencv-python.
  - `src/segugio/ndi/ndi_source.py` — `_resolve_source` does an EXACT `source_name in names` match
    against `finder.get_source_names()`; `_prefer_system_ndi_runtime()` preloads the system NDI
    6.3.2 base. The console renders ONLY what the orchestrator publishes (no orchestrator → no JPEGs).
  - `tools/verify_ndi_hx_decode.py` — the diagnostic: `tools/verify_ndi_hx_decode.py "<exact NDI
    source name>"` (default `"LOCALHOST (iPhone)"`), uses `cyndilib.finder.Finder`. Reconcile the
    venv: the tool docstring example shows `./venv/Scripts/python.exe`, but cyndilib lives in
    `venv312` on this box (project memory `cyndilib NDI HX decode`), so the diagnostic must run from
    the venv that actually has cyndilib + the system NDI runtime. Verify which venv has cyndilib
    before writing the exact command; if only venv312 carries it, document
    `venv312\Scripts\python.exe tools/verify_ndi_hx_decode.py "<name>"` and note `$env:PYTHONPATH="src"`
    is needed when segugio is not editable-installed there.

PLACEMENT: insert the new section AFTER the existing "## What the UAT tests exercise from here"
section and BEFORE "## GPU latency env (Phase 6)" (a sensible spot — between the launch/UAT block
and the GPU-build block). Add a leading `---` horizontal rule to match the file's section
separators. Do NOT modify, reorder, or delete any existing content.

STYLE: match the file's current English prose with Italian project terms (the existing doc is
English with Italian context like "SAFE scene", route/config nouns). Use Windows PowerShell command
syntax (`$env:VAR = "..."`) to match the project platform and the existing run.md examples. Use
fenced code blocks for commands.

The section MUST cover these five points (heading `## Phase 8 — Console multiview live`):

1. TWO-PROCESS ARCHITECTURE. The light Flask console runs from the CPU venv (has Flask, NOT the
   heavy stack — imports ONLY Flask + `segugio.opcomm`, the crash-isolation contract); the heavy
   orchestrator runs from `venv312` (ultralytics/cyndilib/obsws/cv2). They couple ONLY via the
   shared opcomm dir (cross-reference the existing "Channel directory (opcomm)" section — do not
   re-explain it). State the on-this-box gotcha: segugio is NOT installed into venv312, so the
   orchestrator needs EITHER a one-time `venv312\Scripts\python.exe -m pip install -e ".[heavy]"`
   OR `$env:PYTHONPATH = "src"` set per run.

2. CONSOLE LAUNCH. `python -m segugio.ui.app` binds `0.0.0.0:8080` (open from the operator tablet on
   the dedicated WiFi). Document the real env vars to populate the multiview cam_ids whitelist:
   `SEGUGIO_OPCOMM_DIR` (must match the orchestrator's `--opcomm-dir`), and EITHER `SEGUGIO_CAM_IDS`
   (comma list, takes precedence) OR `SEGUGIO_CONFIG` (path → cam ids loaded from `config.cameras`);
   with neither set the four default ids `cam_wide,cam_long,cam_low,cam_handler` keep the routes
   serving. Explain the waitress → `threaded=True` fallback as the UXT-02 safety control: a preview
   GET can never pin the lone WSGI worker and block the safety-critical `/command` override POST
   (not cosmetic). Mention the optional `pip install -e ".[console]"` (waitress) production server.
   Give a PowerShell launch example setting `SEGUGIO_OPCOMM_DIR` + `SEGUGIO_CAM_IDS` before
   `python -m segugio.ui.app`.

3. ROUTES SERVED. `GET /preview` returns the `preview.json` "why" sidecar (gen/tick/auto_candidate/
   cams) via the safe-default never-raise `read_preview`. `GET /preview/<cam>.jpg` serves a
   whitelisted per-camera JPEG via `send_file` (anti path-traversal: `<cam>` whitelisted against the
   configured cam_ids, never used as a raw path; unknown id → 404; on-disk file is the FIXED
   `preview/cam_{id}.jpg` prefix, so id `cam_wide` → `cam_cam_wide.jpg`; `Cache-Control: no-store`).
   State that tiles populate ONLY when the orchestrator runs with preview ENABLED (default ON since
   Phase 7) and writes JPEGs into the SAME opcomm dir — the console's `SEGUGIO_OPCOMM_DIR` MUST
   equal the orchestrator's `--opcomm-dir`.

4. PREVIEW BANDWIDTH CAP. A CONFIG-TIME guarantee, not a runtime throttle:
   `PreviewParams.max_total_mbps` (default `8.0` Mbps) + the `Config._preview_bitrate_within_cap`
   `@model_validator` rejects any over-cap config fail-fast with `SystemExit(2)` at load (computed
   worst-case `bytes × 8 × fps × N_cams`). By construction the preview degrades (is rejected before
   launch) before it can starve the NDI feeds on the contended WiFi. `preview.enabled: false`
   short-circuits the check (source-side off-switch). Cross-reference docs/security.md for the
   0.0.0.0 / LAN-trust posture (T-08-03 live-video exposure; AP client-isolation + no internet/guest
   bridge is the HARD operational mitigation) — reference it, do not duplicate it.

5. TROUBLESHOOTING "il telefono si vede in OBS ma non nella console". List the likely causes in
   order: (a) EXACT `ndi_source` name match — `ndi_source.py` does a literal `source_name in names`
   match, so a near-miss name (`LOCALHOST (iPhone)` vs `LOCALHOST (iPhone Camera for OBS Studio App)`)
   silently never resolves; (b) run the diagnostic `tools/verify_ndi_hx_decode.py "<exact name>"`
   from the venv that has cyndilib (venv312, with `$env:PYTHONPATH = "src"` if segugio is not
   editable-installed there) to confirm HX decode + frame count; (c) a discovery one-liner via the
   cyndilib `Finder` to list the live source names (`Finder().open()` then `get_source_names()`) so
   the operator can copy the EXACT advertised name into config; (d) the load-bearing reminder — the
   console only RENDERS what the orchestrator PUBLISHES, so with no orchestrator running the tiles
   stay DEAD (404 placeholders) even when OBS sees the phone. Cross-reference the existing
   "Prerequisites" NDI bullets (NDI Tools / HX Driver, NDI Access Manager, active camera view,
   don't-hardcode-source-names) rather than duplicating them.

Use the Edit tool (append the new section in-place) rather than rewriting the whole file, to
guarantee existing content is byte-preserved.
  </action>
  <verify>
    <automated>powershell -NoProfile -Command "$c = Get-Content -Raw docs/run.md; if ($c -notmatch 'Phase 8 .{0,4} Console multiview live') { Write-Error 'missing Phase 8 heading'; exit 1 }; foreach ($t in @('SEGUGIO_OPCOMM_DIR','SEGUGIO_CAM_IDS','SEGUGIO_CONFIG','/preview/<cam>.jpg','GET /preview','max_total_mbps','threaded=True','verify_ndi_hx_decode.py','console','GPU latency env (Phase 6)','What the UAT tests exercise from here')) { if ($c -notmatch [regex]::Escape($t)) { Write-Error \"missing token: $t\"; exit 1 } }; Write-Host 'OK: section present, code tokens present, existing sections preserved'"</automated>
  </verify>
  <done>
docs/run.md contains a new "## Phase 8 — Console multiview live" section placed between
"## What the UAT tests exercise from here" and "## GPU latency env (Phase 6)". The section covers
all five required points with code-verified identifiers (env vars, routes, `max_total_mbps`,
`threaded=True` fallback, `verify_ndi_hx_decode.py`, `[console]` extra). All pre-existing run.md
content (Phase 5 launch sections, Phase 6 GPU section) is intact and unmodified.
  </done>
</task>

</tasks>

<verification>
- The new section heading exists and is placed between the UAT and GPU sections (not at EOF, not
  before the Phase-5 launch sections).
- Every documented command, env var, route, and config field is grep-confirmable in the shipped
  source (app.py / models.py / pyproject.toml / ndi_source.py / verify_ndi_hx_decode.py).
- No fenced code block inside the section uses bash-isms where PowerShell syntax is expected
  (`$env:VAR = "..."`, not `export VAR=...`).
- Existing Phase 5 / Phase 6 content is byte-preserved (Edit-append, not full rewrite).
</verification>

<success_criteria>
docs/run.md gains a single new "Phase 8 — Console multiview live" section that an operator can
follow to launch the light console + heavy orchestrator two-process multiview, understand the
served routes and the config-time bandwidth cap, and diagnose the "phone in OBS but not in console"
failure — with every technical identifier matching the shipped code and zero changes to existing
content or source/tests.
</success_criteria>

<output>
Create `.planning/quick/260613-rjz-aggiungi-a-docs-run-md-una-sezione-phase/260613-rjz-SUMMARY.md` when done
</output>
