# NEW_BASE_AUDIT

Generated: 2026-05-03

## Scope

Audited `introspector_source_clean_20260503T015146Z.zip` as the new base against `introspector_unified_release_20260502_FINAL.zip`.

## Already present in the new base

All mandatory carry-over files from the previous unified release are present:

- `src/project_introspector/run_contract.py`
- `src/project_introspector/run_validator.py`
- `src/project_introspector/project_analysis_policy.py`
- `src/project_introspector/provider_errors.py`
- `src/project_introspector/import_normalization.py`
- `src/project_introspector/operator_next.py`
- `src/project_introspector/cli.py`
- `src/project_introspector/tui_models.py`
- `scripts/run_full_local_analysis.py`
- `scripts/validate_run_result.py`
- `scripts/tui_tmux_smoke.sh`
- `docs/RUN_CONTRACT.md`
- `docs/PROVIDER_HARDENING.md`
- `docs/FACTUAL_SCANNER_EXPANSION.md`

The new base is therefore not a bare clean source. It already contains the completed-run contract, validator, provider hardening, factual scanner expansion, product CLI, and TUI/operator support files.

## Missing from the new base

No mandatory source file from the carry-over checklist was missing.

The only meaningful tree-level item present in the older unified release and absent from the new base is:

- `docs_snapshot_20260502/`

This is treated as historical snapshot material, not a required runtime/source dependency.

## Changed/newer in the new base

The new base differs from the previous unified release in a small set of files, primarily around TUI/report behavior and smoke-readiness:

- `README.md`
- `analyzer/app.py`
- `scripts/run_tui.sh`
- `scripts/scan_project.py`
- `scripts/tui_tmux_smoke.sh`
- `src/project_introspector/cli.py`
- `src/project_introspector/report_quality.py`
- `src/project_introspector/tui_client.py`
- `src/project_introspector/tui_models.py`
- `src/project_introspector/tui_render.py`
- `src/project_introspector/tui_text.py`
- TUI/report/CLI tests

Notable new-base improvements observed during audit:

- `project-introspector tui-health` exists as a non-interactive readiness check.
- `/llm/status` now separates credential configuration from probe state.
- Report output distinguishes provider credentials from missing enrichment artifacts.
- TUI tmux smoke script has live-mode and capture improvements.

## Audit conclusion

The new base should be treated as the official starting point. Tasks 1-20 do not need to be blindly replayed. The correct path is targeted hardening and TUI/operator-state work on top of this base.
