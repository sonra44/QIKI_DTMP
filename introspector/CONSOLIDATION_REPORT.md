# CONSOLIDATION_REPORT.md

## Release

`introspector_unified_release_20260502`

This release is a semantic consolidation of the available `project-introspector` work archives into one working tree.

## Base and inputs

Base source:

- `introspector_clean_source_20260502.zip`

Integration seed:

- `introspector_consolidated_20260502.zip`

Additional feature drop integrated during this pass:

- `introspector_tui_refactor_20260502.zip`

Reference archives / patches considered during verification:

- `introspector_implemented_plan_20260502.zip`
- `introspector_continue_tasks_20260502.zip`
- `introspector_factual_scanner_expansion_20260502.zip`
- `introspector_implemented_plan.patch`
- `introspector_continue_tasks_20260502.patch`
- `introspector_factual_scanner_expansion_20260502.patch`

## Integration strategy

This was not a blind overlay of archives. The consolidated archive was used as the main semantic seed because it already contained the baseline fixes, completed run contract, run validator, `ProjectAnalysisPolicy`, provider hardening, factual scanner expansion, and package CLI.

The safe TUI/operator refactor was then merged explicitly:

- added `src/project_introspector/operator_next.py`;
- added `tests/test_operator_next.py`;
- changed `src/project_introspector/tui_render.py` so the TUI render layer delegates operator next-step policy to `operator_next_step()` instead of owning the policy itself.

## Included completed blocks

1. Baseline fixes:
   - optional TUI tests skip without `textual`;
   - provider credential documentation reflects factual-first startup;
   - `scan_project.py` supports offline/no-upload scan artifacts.

2. Completed run contract:
   - `docs/RUN_CONTRACT.md`;
   - `src/project_introspector/run_contract.py`;
   - `scripts/run_full_local_analysis.py`;
   - `src/project_introspector/run_validator.py`;
   - `scripts/validate_run_result.py`.

3. Report export and product CLI:
   - `scripts/export_report.py`;
   - `src/project_introspector/cli.py`;
   - `[project.scripts] project-introspector = "project_introspector.cli:main"`.

4. LLM/project hardening:
   - `src/project_introspector/project_analysis_policy.py`;
   - project-level LLM fields are filtered against factual schema.

5. Provider hardening:
   - `src/project_introspector/provider_errors.py`;
   - typed provider error categories;
   - structured degraded artifacts for provider failures;
   - requested-model vs provider-model provenance;
   - payload truncation provenance;
   - `/llm/probe` endpoint.

6. Factual scanner expansion:
   - `src/project_introspector/import_normalization.py`;
   - normalized import facts;
   - FastAPI route facts;
   - env var facts;
   - argparse CLI option facts;
   - Pydantic model facts;
   - class and instance attribute facts.

7. Safe TUI/operator refactor:
   - `operator_next.py` extracted as pure operator policy;
   - `tui_render.py` remains presentation-oriented.

## Key files expected in this release

- `docs/RUN_CONTRACT.md`
- `docs/PROVIDER_HARDENING.md`
- `docs/FACTUAL_SCANNER_EXPANSION.md`
- `scripts/export_report.py`
- `scripts/run_full_local_analysis.py`
- `scripts/validate_run_result.py`
- `src/project_introspector/cli.py`
- `src/project_introspector/run_contract.py`
- `src/project_introspector/run_validator.py`
- `src/project_introspector/project_analysis_policy.py`
- `src/project_introspector/provider_errors.py`
- `src/project_introspector/import_normalization.py`
- `src/project_introspector/operator_next.py`
- `tests/test_operator_next.py`
- `tests/test_factual_scanner_expansion.py`
- `tests/test_project_analysis_policy.py`
- `tests/test_run_contract_validator.py`
- `tests/test_cli_entrypoint.py`

All expected key files were present during the consolidation check.

## Acceptance checks performed

Commands were run from the consolidated working tree.

```bash
/opt/pyvenv/bin/python -m compileall -q src analyzer scripts tests
```

Result:

```text
OK
```

Full pytest result after adding the safe TUI/operator refactor:

```text
65 passed, 3 skipped in 12.45s
```

Offline completed-run check:

```bash
PYTHONPATH=src /opt/pyvenv/bin/python scripts/run_full_local_analysis.py \
  --project-name INTROSPECTOR_DEMO \
  --source-root src \
  --out-dir tmp/acceptance_offline \
  --offline \
  --run-id acceptance_offline
```

Result:

```text
run_result written status=completed_with_limits
```

Run contract validation:

```bash
PYTHONPATH=src /opt/pyvenv/bin/python scripts/validate_run_result.py \
  tmp/acceptance_offline/acceptance_offline
```

Result:

```text
OK: run_result.json matches run contract
```

Package CLI smoke check:

```bash
PYTHONPATH=src /opt/pyvenv/bin/python -m project_introspector.cli run \
  --project-name INTROSPECTOR_CLI \
  --source-root src \
  --out-dir tmp/acceptance_cli2 \
  --offline

PYTHONPATH=src /opt/pyvenv/bin/python -m project_introspector.cli validate \
  tmp/acceptance_cli2/<run_id>
```

Result:

```text
OK: run_result.json matches run contract
```

## Acceptance artifacts

External logs saved outside the release tree:

- `/mnt/data/unified_release_pytest_vv.log`
- `/mnt/data/unified_release_acceptance.log`

The release tree also includes this report and `CONSOLIDATION_MANIFEST.json`.

## Known limitations

- The acceptance pass verified offline completed-run behavior. It did not run a long-lived analyzer service for analyzer-backed report export.
- Real external LLM provider calls were not executed because credentials/network provider access were not configured in this environment.
- Provider error behavior is covered by code paths and tests; live 401/429/timeout/5xx provider scenarios should be rechecked in a credentialed integration environment.
- Temporary run directories under `tmp/` are excluded from the final release archive.

## Verdict

The consolidated working tree is ready as a unified internal release candidate. It contains the previously separate work streams in one project state and passes compile, test, offline run, validator, and CLI smoke checks.

## Final CLI polish pass

After the initial unified release was inspected, one small CLI parity gap was fixed before final packaging:

- `project-introspector run` now forwards the orchestrator options `--module`, `--max-modules`, `--run-id`, `--keep-going`, and `--timeout` to `scripts/run_full_local_analysis.py`.
- `tests/test_cli_entrypoint.py` now covers these run options at parse level.

Current final-pass checks:

```text
compileall: OK for src, analyzer, scripts, tests
targeted regression: 11 passed in 1.50s
direct offline run: run_result written status=completed_with_limits
CLI validate: OK: run_result.json matches run contract
CLI run with --run-id: completed and produced run_result.json/schema/static_snapshot/summary
```

Full-suite evidence from the unified release seed remains available in `/mnt/data/introspector_unified_release_SEED_full_pytest.log`:

```text
65 passed, 3 skipped
```

The final pass did not rerun live external provider calls or a long-lived analyzer-backed workflow. Those still require a credentialed integration environment.
