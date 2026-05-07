# NEW_BASE_ACCEPTANCE

Generated: 2026-05-03

## Baseline acceptance after this pass

| Check | Result |
|---|---|
| `python -m compileall -q .` | OK |
| `python -m pytest -q tests` | `105 passed, 3 skipped` |
| direct offline run via `scripts/run_full_local_analysis.py` | OK |
| direct `scripts/validate_run_result.py` | OK |
| CLI offline run via `python -m project_introspector.cli run` with `PYTHONPATH=src` | OK |
| CLI validate via `python -m project_introspector.cli validate` with `PYTHONPATH=src` | OK |
| TUI tmux smoke | skipped: `tmux` is not installed in this environment |

## Important fix discovered during acceptance

Initial direct script execution failed without `PYTHONPATH` because loose scripts imported `project_introspector` before the source tree was added to `sys.path`.

Fixed by adding source-checkout bootstrap logic to:

- `scripts/scan_project.py`
- `scripts/live_module_pass.py`
- `scripts/run_full_local_analysis.py`
- `scripts/validate_run_result.py`

Also updated:

- `scripts/run_tui.sh` now exports `PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"` before launching the package module.

## Logs

External logs written next to the release artifact:

- `tui_operator_release_compileall.log`
- `tui_operator_release_pytest.log`
- `tui_operator_release_direct_run.log`
- `tui_operator_release_direct_validate.log`
- `tui_operator_release_cli_run.log`
- `tui_operator_release_cli_validate.log`
- `tui_operator_release_tmux_smoke.log`
