# TUI Operator State Wire Report

Generated: 2026-05-03

## Base artifact

`introspector_tui_operator_release_20260503.zip`

## Output artifact

`introspector_tui_operator_state_20260503.zip`

## Purpose

This pass continues the TUI/operator plan after the first TUI operator release. The previous release introduced `artifact_resolver.py`, `artifact_freshness.py`, and `operator_state.py`, but left the Textual TUI only partially connected to those domain modules. This pass wires those modules into the existing TUI flow without attempting a full visual redesign.

## Completed tasks

1. **TUI client artifact loading now goes through `artifact_resolver.py`**
   - `IntrospectorTuiClient.load_module_artifact()` now builds explicit/local/API/live candidates and delegates selection to `resolve_module_artifact()`.
   - Analyzer-derived docs, local derived artifacts, live replay artifacts, and explicit overrides are resolved through one policy path.
   - The resolver no longer treats a bare analyzer doc key as a found artifact unless the payload or existence evidence is present.

2. **Freshness rendering now uses `artifact_freshness.py` primitives directly**
   - `tui_render.py` now evaluates artifact freshness via `evaluate_artifact_freshness()`.
   - Render output can surface `missing`, `future_timestamp`, and `invalid_timestamp`, not only `current/stale/unknown`.
   - RU/EN localization keys were added for the new freshness states and future-timestamp reason.

3. **`operator_state.py` now supports run discovery and analyzer-backed state**
   - Added `discover_run_directories()` and `discover_latest_run_dir()`.
   - Added `build_operator_state_from_analyzer_payloads()` for live analyzer/TUI inputs.
   - Existing run-directory builder now reuses shared module-row construction.

4. **TUI operations now produce `OperatorState`**
   - `RefreshData`, `StatusReload`, and `ModuleViewsRefresh` can carry `operator_state`.
   - `load_all_data()` builds analyzer-backed `OperatorState` from schema/report/status/scan/live/analysis inputs.

5. **TUI dashboard/status path consumes `OperatorState`**
   - Added `render_operator_dashboard()`.
   - Overview/compact screens now include an `operator-dashboard` panel.
   - This is intentionally incremental: module details and the full visual redesign are still left for later passes.

## Added tests

- `tests/test_tui_render_operator_dashboard.py`

## Extended tests

- `tests/test_tui_client.py`
- `tests/test_operator_state.py`

## Acceptance results

```text
python -m compileall -q .
OK

python -m pytest -q tests
109 passed, 3 skipped

python scripts/run_full_local_analysis.py \
  --project-name INTROSPECTOR_DEMO \
  --source-root src \
  --out-dir tmp/operator_state_runs \
  --offline
run_result written status=completed_with_limits

python scripts/validate_run_result.py tmp/operator_state_runs/<run_id>
OK: run_result.json matches run contract

PYTHONPATH=src python -m project_introspector.cli run \
  --project-name INTROSPECTOR_DEMO \
  --source-root src \
  --out-dir tmp/operator_state_cli_runs \
  --offline
run_result written status=completed_with_limits

PYTHONPATH=src python -m project_introspector.cli validate tmp/operator_state_cli_runs/<run_id>
OK: run_result.json matches run contract
```

`tmux` is not installed in this environment, so direct tmux smoke remains an integration-environment check.

## Remaining recommended tasks

1. Convert module detail / inspector rendering to consume `OperatorState` module rows and evidence sections.
2. Add dashboard health-card visual layout rather than plain text dashboard lines.
3. Add module-table filters for stale artifacts, missing enrichment, routes and env/config.
4. Add an explicit action log/progress panel backed by structured operation results.
5. Expand hotkeys and add/update `docs/TUI_GUIDE.md`.
6. Re-run tmux smoke in an environment with `tmux` and `textual` installed.
