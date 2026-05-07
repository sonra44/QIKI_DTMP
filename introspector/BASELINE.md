# Introspector Baseline

This is the clean internal-tool v1 baseline for `project-introspector`.

## What Is Baseline-Proven

- stable local analyzer startup
- reproducible factual scan path
- reproducible module-level enrichment harness
- split storage layout: `static / runtime / derived`
- green local test suite, rechecked on 2026-04-26
- live provider confirmation on a representative module sample from the target project
- module-level semantic gate and degraded behavior
- semantic-code layer for operator and UI localization
- usable module-analysis fields:
  - `purpose`
  - `responsibilities`
  - `public_symbols`
  - `status`
  - `actionable_hints`
  - `warnings`
  - `processing_notes`

## Canonical Two-Phase Path

1. `./scripts/clean_dev_artifacts.sh`
2. `./scripts/run_fresh_analyzer.sh`
3. `PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"; "$PYTHON_BIN" scripts/scan_project.py`
4. `PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"; "$PYTHON_BIN" scripts/enrich_modules.py`
5. `PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"; "$PYTHON_BIN" -m pytest -q tests`

For intentional degraded-provider verification only:

1. `./scripts/clean_dev_artifacts.sh`
2. `ALLOW_DEGRADED_START=1 ./scripts/run_fresh_analyzer.sh`
3. `PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"; "$PYTHON_BIN" scripts/live_module_pass.py --allow-unconfigured-provider`

## Canonical Entry Points

- analyzer startup: [`scripts/run_fresh_analyzer.sh`](./scripts/run_fresh_analyzer.sh)
- TUI startup: [`scripts/run_tui.sh`](./scripts/run_tui.sh)
- factual scan: [`scripts/scan_project.py`](./scripts/scan_project.py)
- enrichment queue: [`scripts/enrich_modules.py`](./scripts/enrich_modules.py)
- compatibility replay harness: [`scripts/live_module_pass.py`](./scripts/live_module_pass.py)
- cleanup to clean generated baseline: [`scripts/clean_dev_artifacts.sh`](./scripts/clean_dev_artifacts.sh)
- baseline and evidence packaging split: [`scripts/export_bundle.sh`](./scripts/export_bundle.sh)
- optional Textual operator console: [`scripts/run_tui.sh`](./scripts/run_tui.sh)

## Storage Layout

- `analyzer/data/static/` uploaded static snapshots
- `analyzer/data/runtime/` accepted runtime events
- `analyzer/data/derived/` analyzer-produced LLM outputs
- `tmp/live_module_pass/` temporary live verification artifacts

## External Dependency Boundary

Live semantic confirmation was re-verified on 2026-04-04 against a representative module sample from the host project. That proof establishes provider viability for the current environment, not a permanent canonical module list.

Provider access is still an external dependency boundary. Credits, rate limits, or upstream availability may fail again, and that must be treated as an external constraint rather than an internal pipeline regression. The analyzer degrades cleanly and keeps returning structured provider-error results instead of crashing.

Provider-backed enrichment is an explicit operational precondition:

- `scripts/run_fresh_analyzer.sh` starts without provider credentials by default; strict startup is explicit via `REQUIRE_PROVIDER_CREDENTIALS=1`
- `scripts/enrich_modules.py` uses the existing factual layer and runs enrichment only
- `scripts/live_module_pass.py` remains available for compatibility replay and intentional degraded-path verification
- the default local analyzer endpoint is `http://127.0.0.1:8015`; override with `PORT` for the service or `INTROSPECTOR_ANALYZER_URL` for clients
- script defaults scan this tool's own `src`; set `INTROSPECTOR_SOURCE_ROOT` or pass `--source-root` when the target is another project

## Trust And Storage Boundary

- first-level truth = `static facts + runtime facts + schema`
- LLM output is enrichment only, never the first-level source of truth
- `analyzer/data/static`, `analyzer/data/runtime`, and `analyzer/data/derived` are local baseline and dev storage, not a production backend
- module-level analysis is the main useful output surface
- project-summary output stays secondary and is not the source of truth
- operational portability depends on explicit runtime inputs where needed: `PYTHON_BIN`, `INTROSPECTOR_SOURCE_ROOT`, `INTROSPECTOR_OUTPUT_DIR`, `INTROSPECTOR_ANALYZER_URL`, `HOST`, and `PORT`
- source baseline and evidence bundle are separate deliverables: baseline source is commit and handoff-ready code, while evidence lives under `analyzer/data/**` and `tmp/live_module_pass/**`

## Latest Local Smoke

Rechecked on 2026-04-26:

- default local scan against `introspector/src`: `modules_scanned=29`, `scan_errors=0`
- explicit QIKI scan with `--source-root /home/sonra44/QIKI_DTMP/src`: `modules_scanned=318`, `scan_errors=0`
- intentional unconfigured-provider enrichment for `qiki.core.load_harness`: `status=degraded`, `modules_degraded=1`, `modules_failed=0`
- provider status in that smoke: `configured=false`, `provider_name=openrouter`

## TUI Console

The optional Textual TUI is an operator console over the existing analyzer endpoints, schema, and stored module-analysis artifacts. It must remain useful when the provider is unconfigured, and it must not become a parallel source of truth.

Launch:

1. `pip install -e .[tui]`
2. `./scripts/run_tui.sh`

TUI v1 covers:

- read-only project report with factual counts, runtime limits, enrichment state, and provenance
- overview triage over module status, degraded state, warnings, and runtime signal
- module explorer with purpose, responsibilities, public symbols, status, actionable hints, warnings, and processing notes
- runtime and static-only signal view
- scan and enrichment panel with read-only project report, factual-layer readiness, enrichment-layer status, latest enrichment artifacts, explicit scan action, and explicit selected-module enrichment

## Next Hardening Focus

Keep the current pipeline fixed, preserve module-level quality, and treat future provider regressions as external-dependency incidents unless the degraded path itself breaks.

## Current provider credential behavior

The analyzer is factual-first. `scripts/run_fresh_analyzer.sh` does not require LLM provider credentials by default because `REQUIRE_PROVIDER_CREDENTIALS` defaults to `0`. Without provider credentials, analyzer startup, static scan ingestion, schema, storage status and report endpoints can still be used. Provider-backed enrichment remains unavailable or degraded until credentials are configured.

Strict provider startup is explicit:

```bash
REQUIRE_PROVIDER_CREDENTIALS=1 ./scripts/run_fresh_analyzer.sh
```
