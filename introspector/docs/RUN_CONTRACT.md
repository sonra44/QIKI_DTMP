# Run Contract

`project-introspector` is factual-first. Static scan, runtime events, schema and analyzer storage metadata are factual layers. LLM enrichment is a derived interpretation layer. Report, CLI and TUI are operator surfaces; they display state and must not become sources of truth.

A completed run is a single controlled analysis execution that leaves a durable run directory. A run may be `completed`, `completed_with_limits`, `degraded` or `failed`. LLM enrichment is optional: a factual-only offline run can still be a valid completed run with limits.

## Required artifacts

Minimum run directory:

```text
tmp/runs/<run_id>/
  run_result.json
  static_snapshot.json
  summary.json
  schema.json
  logs/progress.log
```

Analyzer-backed runs may also include:

```text
  report.json
  llm_status.json
  module_findings/
```

## `run_result.json`

`run_result.json` is modeled by `project_introspector.run_contract.RunResult`. It records project identity, source root, mode, top-level status, factual/runtime/enrichment/report layer statuses, artifacts, limits and next safe operator steps.

Important rules:

- if static scan fails, the run cannot be clean `completed`;
- `runtime_event_count = 0` does not prove dead code;
- skipped or degraded LLM enrichment does not invalidate factual scan;
- report/TUI/CLI should show provenance and limits rather than hiding degraded state;
- required artifact paths in `run_result.json` must exist on disk.

Validate a run directory with:

```bash
python scripts/validate_run_result.py tmp/runs/<run_id>
```
