# TUI Operator DataTable Increment — 2026-05-03

## Scope

This increment continued from `introspector_tui_operator_polish_20260503.zip` and intentionally skipped hard tmux smoke as an optional environment-dependent check.

## Implemented

- Added DataTable-backed overview module table wiring in `tui_app.py`.
- Kept static overview table as a compatibility/export fallback.
- Added pure helpers in `tui_table_model.py` for localized DataTable headers and row values.
- Added operator-state table filters for search, missing enrichment, degraded/needs-attention, routes, env/config, and findings.
- Updated `render_operator_module_table()` to share the same filter contract as the DataTable path.
- Added `docs/TUI_GUIDE.md` with operator areas, hotkeys, table behavior, filters, and tmux skip policy.
- Added table-model tests for DataTable-ready headers/values and filters.

## Acceptance policy

Required:

```text
python -m compileall -q src analyzer scripts tests
python -m pytest -q tests
python scripts/run_full_local_analysis.py --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/datatable_runs --offline
python scripts/validate_run_result.py tmp/datatable_runs/<run_id>
PYTHONPATH=src python -m project_introspector.cli run --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/datatable_cli_runs --offline
PYTHONPATH=src python -m project_introspector.cli validate tmp/datatable_cli_runs/<run_id>
zip -T <release>.zip
```

Optional:

```text
scripts/tui_tmux_smoke.sh
```

If `tmux` is not installed, the smoke path is recorded as skipped and does not block the release.
