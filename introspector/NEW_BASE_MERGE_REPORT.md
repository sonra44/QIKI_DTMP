# NEW_BASE_MERGE_REPORT

Generated: 2026-05-03

## Merge strategy

No wholesale overlay from the previous unified release was needed. The new base already contained the required run-contract, provider-hardening, scanner-expansion, CLI and TUI support files.

Changes in this pass were applied semantically on top of the new base.

## Source-checkout execution fixes

Added loose-script bootstrap so scripts can be executed directly from a checked-out source tree without requiring `pip install -e .` first:

- `scripts/scan_project.py`
- `scripts/live_module_pass.py`
- `scripts/run_full_local_analysis.py`
- `scripts/validate_run_result.py`
- `scripts/run_tui.sh`

## Test hardening added

New test files:

- `tests/test_provider_negative_paths.py`
- `tests/test_llm_enrichment_failures_and_bad_responses.py`
- `tests/test_run_validator_missing_artifacts.py`
- `tests/test_scanner_edge_cases.py`
- `tests/test_artifact_freshness.py`
- `tests/test_artifact_resolver.py`
- `tests/test_operator_state.py`

## Code hardening added

- Provider negative paths now have regression coverage for auth, rate limit, timeout, network, server error, bad response, and structured-output fallback.
- Raw-text-only LLM responses are treated as degraded structured artifacts instead of silently becoming normal analysis.
- Existing module-analysis warning codes are preserved when deterministic policy adds normalized warning codes.
- Run validator now errors when `factual_layer.schema_path` is declared but missing.
- Run validator now treats missing `module_findings_dir` as an error when enrichment status is `ready`.
- Scanner detects `from pydantic import BaseModel as Alias` classes as Pydantic models.

## New operator-state building blocks

Added:

- `src/project_introspector/artifact_freshness.py`
- `src/project_introspector/artifact_resolver.py`
- `src/project_introspector/operator_state.py`

Compatibility:

- `src/project_introspector/tui_evidence_reason.py` is now a thin wrapper over `artifact_freshness.py`.

## Remaining merge risk

No required unified-release file is missing, but full TUI integration into `OperatorState` is not completed in this pass. The new operator modules are ready for the next TUI integration step.
