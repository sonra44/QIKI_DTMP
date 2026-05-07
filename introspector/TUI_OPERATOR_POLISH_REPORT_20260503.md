# TUI Operator Polish Increment Report

## Base

`introspector_tui_operator_visual_20260503.zip`

## Goal

Continue the TUI/operator UX work after the safe visual increment. This pass targets the remaining safe items from the visual report:

- persistent action history instead of action-feedback-only snapshots;
- explicit status theme classes for operator panels;
- a pure table model that prepares the static module table for a future Textual `DataTable` swap;
- a small stability fix for the missing `_refresh_operator_visual_panels()` method.

## Implemented

### Persistent action history

Added:

```text
src/project_introspector/tui_action_history.py
tests/test_tui_action_history.py
```

The TUI now keeps timestamped operator action entries with:

- action key;
- human label;
- state;
- message;
- started timestamp;
- finished timestamp.

`render_action_log()` now prefers persistent history when it is available, while keeping backward compatibility with the old action feedback snapshot.

### Status theme classes

Added:

```text
src/project_introspector/tui_theme.py
tests/test_tui_theme.py
```

The TUI now maps run/layer/action statuses to semantic classes:

```text
status-ok
status-warning
status-error
status-muted
status-running
```

`IntrospectorTuiApp` applies those classes to:

- top status;
- operator dashboard;
- health cards;
- inspector;
- action log.

This keeps the current safe layout but prepares the UI for clearer status coloring.

### DataTable-ready module table model

Added:

```text
src/project_introspector/tui_table_model.py
tests/test_tui_table_model.py
```

`render_operator_module_table()` now uses a pure table-row model. The current output remains static text, but the data shape is now ready to feed a future Textual `DataTable` without moving selection/signal formatting back into `tui_app.py`.

### TUI stability fix

`IntrospectorTuiApp._refresh_views()` already called `_refresh_operator_visual_panels()`, but the method was missing in the visual archive. This pass adds it and centralizes updates for:

- dashboard;
- health cards;
- inspector;
- action log;
- panel theme classes.

## Verification

```text
python -m compileall -q src analyzer scripts tests
OK

python -m pytest -q tests
122 passed, 3 skipped

python scripts/run_full_local_analysis.py --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/polish_runs --offline
run_result written status=completed_with_limits

python scripts/validate_run_result.py tmp/polish_runs/<run_id>
OK: run_result.json matches run contract

PYTHONPATH=src python -m project_introspector.cli run --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/polish_cli_runs --offline
OK

PYTHONPATH=src python -m project_introspector.cli validate tmp/polish_cli_runs/<run_id>
OK: run_result.json matches run contract
```

`tmux` smoke was attempted and skipped because `tmux` is not installed in this environment.

## Remaining work

1. Replace the static overview table widget with Textual `DataTable` when a TUI dependency environment is available.
2. Add a dedicated right-side inspector layout rather than rendering the inspector block inside the existing tabs.
3. Run `scripts/tui_tmux_smoke.sh` in an environment with `tmux` installed.
