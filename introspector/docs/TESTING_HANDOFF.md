# Testing handoff

This package is a controlled testing handoff for the `project-introspector` TUI/operator DataTable line.

## Recommended gate

From the repository root run:

```bash
bash scripts/release_test_gate.sh
```

The gate checks:

1. Python compile smoke for `src`, `analyzer`, `scripts`, and `tests`.
2. Pytest suite.
3. Offline completed run generation.
4. `run_result.json` validation.
5. CLI offline run.
6. CLI validation.
7. Optional tmux smoke, skipped when `tmux` is not installed.

## Expected status

The package is ready for controlled testing. The core/offline/CLI path should pass without external provider credentials.

Known caveats:

- Live TUI testing requires the optional Textual extra.
- Live provider testing requires real provider credentials.
- tmux smoke is optional and may be skipped when `tmux` is unavailable.
- The default offline run status is expected to be `completed_with_limits`, because runtime/provider/live enrichment are not exercised in offline mode.

## Quick manual commands

```bash
python -m compileall -q src analyzer scripts tests
python -m pytest -q tests
python scripts/run_full_local_analysis.py --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/test_runs --offline
python scripts/validate_run_result.py tmp/test_runs/<run_id>
PYTHONPATH=src python -m project_introspector.cli run --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/cli_runs --offline
PYTHONPATH=src python -m project_introspector.cli validate tmp/cli_runs/<run_id>
```
