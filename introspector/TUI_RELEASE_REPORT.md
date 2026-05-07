# TUI_OPERATOR_RELEASE_REPORT

Generated: 2026-05-03

## Release artifact

`introspector_tui_operator_release_20260503.zip`

## Base archive

`introspector_source_clean_20260503T015146Z.zip`

## Summary

This pass starts the new-base task plan. It does not replay earlier tasks blindly. Instead it audits the new base, confirms that the previous completed-run/provider/scanner layers are already present, adds missing execution robustness, strengthens tests, and introduces the first reusable operator-state modules needed before deeper TUI refactoring.

## Added source files

- `src/project_introspector/artifact_freshness.py`
- `src/project_introspector/artifact_resolver.py`
- `src/project_introspector/operator_state.py`

## Added tests

- `tests/test_provider_negative_paths.py`
- `tests/test_llm_enrichment_failures_and_bad_responses.py`
- `tests/test_run_validator_missing_artifacts.py`
- `tests/test_scanner_edge_cases.py`
- `tests/test_artifact_freshness.py`
- `tests/test_artifact_resolver.py`
- `tests/test_operator_state.py`

## Modified source files

- `scripts/scan_project.py`
- `scripts/live_module_pass.py`
- `scripts/run_full_local_analysis.py`
- `scripts/validate_run_result.py`
- `scripts/run_tui.sh`
- `src/project_introspector/llm_enrichment.py`
- `src/project_introspector/module_analysis_policy.py`
- `src/project_introspector/run_validator.py`
- `src/project_introspector/scanner.py`
- `src/project_introspector/tui_evidence_reason.py`

## Acceptance results

```text
python -m compileall -q .
OK

python -m pytest -q tests
105 passed, 3 skipped

python scripts/run_full_local_analysis.py --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/release_runs --offline
run_result written status=completed_with_limits

python scripts/validate_run_result.py tmp/release_runs/<run_id>
OK: run_result.json matches run contract

PYTHONPATH=src python -m project_introspector.cli run --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/release_cli_runs --offline
run_result written status=completed_with_limits

PYTHONPATH=src python -m project_introspector.cli validate tmp/release_cli_runs/<run_id>
OK: run_result.json matches run contract
```

TUI tmux smoke was not run because `tmux` is not installed in this environment. The pytest-level TUI smoke tests were collected and skipped where appropriate.

## Known limitations

- `operator_state.py` is introduced but the Textual TUI is not fully migrated to consume it yet.
- Live provider calls were not executed; provider hardening is covered through deterministic unit tests.
- Analyzer-backed long-running service checks were not executed in this environment.
