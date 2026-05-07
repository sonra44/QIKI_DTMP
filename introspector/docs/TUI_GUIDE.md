# TUI Operator Guide

The TUI is an operator surface over the factual scan, run contract, report, and optional LLM enrichment layers. It does not create source-of-truth facts. Facts come from the scanner, runtime events, schema, storage metadata, and validated run artifacts.

## Startup

```bash
project-introspector tui
```

For a source checkout without installation:

```bash
PYTHONPATH=src python -m project_introspector.cli tui
```

The optional TUI dependency is `textual`. Install it with:

```bash
pip install -e '.[tui]'
```

## Main operator areas

The overview screen contains:

- **Operator dashboard**: project, run id, mode, top-level status, layer summary, artifact summary, warnings, and next safe step.
- **Health cards**: factual, runtime, enrichment, and report layer status.
- **Module table**: DataTable-backed module navigation when Textual is available, with a static text fallback for snapshots/tests.
- **Inspector**: selected-module factual signals and enrichment status.
- **Action log**: persistent timestamped history of refresh, scan, enrichment, and failure states.

## Module table

The module table is driven by `OperatorState` and the pure `tui_table_model.py` contract. It includes:

```text
Selected | Module | Signals | Enriched | Degraded | Findings
```

Signals summarize first-class scanner facts:

- FastAPI routes;
- environment variables;
- CLI options;
- Pydantic models;
- class attributes.

The table can be rendered in two ways:

1. Textual `DataTable`, used by the live TUI.
2. Static text fallback, used for non-Textual tests and compatibility output.

Both renderers use the same pure table model, so table behavior remains testable without launching a terminal UI.

## Filters and search

Use `/` to focus search. Use `s` to cycle status filters.

Supported operator-state filters include:

- `all`
- `no-analysis` / `missing-enrichment`
- `needs-attention` / `degraded`
- `routes`
- `env-config`
- `has-findings`

## Hotkeys

```text
r        refresh all
l        reload analyzer/report status
g        run factual scan
p        run enrichment queue
a        enrich selected module
/        focus search
t        switch RU/EN
enter    open selected module
b        back to overview
s        cycle status filter
d        degraded-only toggle
w        warnings-only toggle
ctrl+q   quit
```

Provider-backed actions are disabled when the provider is unconfigured. Factual scan remains available in that state.

## tmux smoke

`tmux` smoke remains optional. In environments without `tmux`, `scripts/tui_tmux_smoke.sh` should report a skipped state rather than fail the release. The main acceptance path is compile, pytest, offline run, validator, and zip integrity.
