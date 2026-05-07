# project-introspector

Portable internal tool v1 for introspecting Python projects without turning LLM output into the source of truth.

## Current architecture notes

- provider layer supports OpenRouter, generic OpenAI-compatible endpoints, and Inception/Mercury presets
- analyzer storage uses SQLite as the primary store and writes JSON mirrors for debug and compatibility
- TUI prefers analyzer API-backed derived artifacts and operation summaries, then falls back to local files
- module analysis keeps legacy `status` while also exposing `activity_status`, `attention_status`, `runtime_signal_status`, and `semantic_confidence_status`

## What the tool is

`project-introspector` has three parts:

1. `project_introspector` SDK inside the target project
2. `analyzer` service that stores facts and builds a project schema
3. optional provider-backed LLM enrichment for project and module summaries

The tool is intended to stay project-neutral. It may be hosted inside one repository, but it must not encode that host project's domain logic as baseline behavior.

## Two-phase model

`project-introspector` operates in two explicit phases:

1. `Scan Project` = factual layer only
   - static scan
   - schema build
   - optional runtime merge from real runtime events
   - no LLM
2. `Enrich Project` / `Enrich Module` = semantic layer only
   - provider-backed project or module summaries
   - explicit degraded / failed states
   - never the first-level source of truth

Truth boundary:

- first-level truth is `static facts + runtime facts + schema`
- LLM output is enrichment layered on top of that factual base
- degraded enrichment must never be interpreted as a successful factual scan

## Current baseline

`introspector` currently holds a clean internal-tool baseline:

- the canonical factual scan path is working
- local analyzer startup is reproducible
- module-level enrichment output is usable and guarded by deterministic sanitization
- degraded provider-error behavior is proven
- generated state is separated from source code

Real provider access is still an external dependency. When credits, rate limits, or upstream availability regress, the analyzer must keep returning structured degraded results instead of breaking the pipeline. See [BASELINE.md](./BASELINE.md) for the handoff-ready baseline summary.

## Baseline v1 boundary

The first acceptable version of `project-introspector` is intentionally narrow.

It must complete one honest two-phase pipeline on one Python project:

1. run a factual scan
2. upload the static snapshot to the analyzer
3. build and return a readable project schema
4. optionally merge real runtime events from a live scenario
5. optionally run provider-backed enrichment for one module
6. optionally return an acceptable project summary as a secondary output
7. degrade enrichment without crashing if the LLM returns invalid or non-JSON output

### Acceptance criteria

Treat baseline v1 as working only if all of the following are true:

- the analyzer starts locally and stays stable
- `POST /events/static` accepts a snapshot from a real project
- `GET /schema/{project_name}` returns a readable schema
- `POST /events/runtime` accepts at least one real runtime flow when runtime evidence is available
- `POST /llm/analyze/module/{project_name}` returns useful structured JSON
- `POST /llm/analyze/project/{project_name}` returns an acceptable overview and does not break the service
- bad LLM responses produce a degraded result instead of `500 Internal Server Error`

### Canonical path

The tool has one trust hierarchy only:

- static schema is the base layer
- runtime events are a liveness signal, not the source of truth for everything
- module enrichment is the main semantic output
- project summary is a secondary, lower-trust overview and not a source of truth
- LLM is never the first-level source of truth

### Non-goals

Baseline v1 does not try to solve:

- a perfect review of the whole repository
- multiple competing analysis modes
- a project summary as a canonical source of truth
- a parallel alternate pipeline
- a fully autonomous architecture analyst for the whole codebase

### Quality bar

The MVP succeeds when it:

- completes the full pipeline reliably
- does not lie badly at the module level
- does not crash because of LLM instability
- produces output that a human can use directly

## Why this shape

The SDK does not send raw source code by default. It sends structured facts and is designed to fail open if the analyzer is unavailable:

- module path
- imports
- function and class signatures
- docstrings
- file hash
- runtime call events

That keeps the signal cleaner and reduces the chance of leaking secrets.

The LLM layer sits after static and runtime collection. It receives a compact schema instead of raw files. The analyzer prefers strict structured output when the provider supports it and falls back to prompt-only JSON mode when the provider rejects those parameters.

## Install

```bash
pip install -e .
pip install -e .[service]
pip install -e .[otel]
```

## Static scan

```python
from pathlib import Path
from project_introspector import scan_project

snapshot = scan_project(Path("./src"), project_name="billing-service")
print(snapshot.model_dump_json(indent=2))
```

The CLI defaults to this tool's own `src` tree. For an external project, pass the target explicitly:

```bash
python scripts/scan_project.py \
  --project-name QIKI_DTMP_FRESH \
  --source-root /home/sonra44/QIKI_DTMP/src
```

## Runtime instrumentation

```python
from project_introspector import EventEmitter, instrument_function

emitter = EventEmitter(
    endpoint="http://127.0.0.1:8015/events/runtime",
    project_name="billing-service",
)

@instrument_function(emitter=emitter, capture_args=False, capture_result=False)
def create_invoice(customer_id: str, amount: int) -> dict:
    return {"customer_id": customer_id, "amount": amount}
```

## Analyzer service

```bash
uvicorn analyzer.app:app --host 127.0.0.1 --port 8015 --reload
```

Reproducible fresh start:

```bash
cd /path/to/project-introspector
./scripts/run_fresh_analyzer.sh
```

The local default analyzer endpoint is `http://127.0.0.1:8015`.

Endpoints:

- `POST /events/static`
- `POST /events/runtime`
- `GET /schema/{project_name}`
- `GET /llm/status`
- `POST /llm/analyze/project/{project_name}`
- `POST /llm/analyze/module/{project_name}?module_path=...`
- `GET /derived/{project_name}/{doc_key}`
- `GET /ops/status/{project_name}`
- `GET /report/{project_name}`

The TUI shows `/report/{project_name}` as a read-only evidence artifact. Its
`module_findings` preview and drilldown preserve provenance and follow the same
operator filters used by the module overview; they are for triage, not command
authority.

### Safe TUI health check

Use `project-introspector tui-health` for non-interactive readiness checks. Do
not use `project-introspector-tui --help` as a smoke test: that entrypoint starts
the Textual UI.

```bash
project-introspector tui-health
project-introspector tui-health \
  --check-analyzer \
  --analyzer-url http://127.0.0.1:8015 \
  --project-name INTROSPECTOR_LIVE_SMALL
```

The command prints JSON and exits without opening an alternate-screen UI.

## Provider configuration

Provider-backed enrichment is explicit and optional.

### OpenRouter

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_MODEL="nvidia/nemotron-3-super-120b-a12b"
export OPENROUTER_FALLBACK_MODEL="nvidia/nemotron-3-nano-30b-a3b:free"
export OPENROUTER_APP_NAME="project-introspector"
export OPENROUTER_HTTP_REFERER="https://your-internal-tool.example"
```

### Inception / Mercury

```bash
export INTROSPECTOR_PROVIDER=inception
export INTROSPECTOR_API_KEY="..."
export INTROSPECTOR_BASE_URL="https://api.inceptionlabs.ai/v1"
export INTROSPECTOR_MODEL="mercury-2"
export INTROSPECTOR_FALLBACK_MODEL="mercury-2"
```

### Generic OpenAI-compatible

```bash
export LLM_PROVIDER_API_KEY="..."
export LLM_PROVIDER_BASE_URL="https://provider.example/v1"
export LLM_PROVIDER_MODEL="model-name"
export LLM_PROVIDER_FALLBACK_MODEL="fallback-model-name"
```

Then ask the analyzer for structured LLM output:

```bash
curl -X POST "http://127.0.0.1:8015/llm/analyze/project/billing-service"
curl -X POST "http://127.0.0.1:8015/llm/analyze/project/billing-service?cheap_mode=true"
curl -X POST "http://127.0.0.1:8015/llm/analyze/module/billing-service?module_path=billing.api.handlers"
```

## Suggested rollout

1. Run static scan in CI on every merge.
2. Add runtime decorators only to entrypoints and important domain functions.
3. Store snapshots in JSON or analyzer storage, not in prose-only documents.
4. Use the LLM endpoints to generate summaries from the compact schema, not from raw source dumps.
5. Persist the LLM summaries next to the generated schema and review them before trusting them operationally.

## Possible next steps after baseline v1

- swap AST scan for LibCST or Griffe where deeper semantic extraction is needed
- enrich schema extraction from Pydantic models
- add OpenTelemetry export for traces
- push graph storage to Neo4j, Postgres JSONB, or a document store
- add conservative stale-doc detection by comparing docs against the schema

## Stability notes

- runtime emission is fail-open by default, so application code keeps running if the analyzer is down
- failed runtime flushes keep buffered events in memory instead of silently dropping them
- static scans collect parse and read failures in `scan_errors` instead of aborting the whole scan
- analyzer writes JSON stores atomically and degrades LLM failures into structured `degraded=true` responses
- module analysis prefers declared symbols and observed runtime facts over model guesses, and low-signal outputs are marked with warnings or degraded semantics instead of pretending to be confident
- `warnings` are short issue signals, while `processing_notes` record deterministic repair and normalization steps applied by the analyzer
- module analysis emits semantic codes for warnings, notes, hints, and some purpose and responsibility fields so UIs can localize the same artifact consistently without depending on provider prose

## Operational baseline

Generated dev and runtime artifacts are intentionally separated from source code:

- `analyzer/data/static/` for uploaded static snapshots
- `analyzer/data/runtime/` for accepted runtime event batches
- `analyzer/data/derived/` for analyzer-produced LLM outputs
- `tmp/live_module_pass/` for ad-hoc live verification artifacts

Recommended local loop:

```bash
cd /path/to/project-introspector
./scripts/clean_dev_artifacts.sh
./scripts/run_fresh_analyzer.sh
```

If you intentionally want only degraded provider-error verification, start with:

```bash
cd /path/to/project-introspector
ALLOW_DEGRADED_START=1 ./scripts/run_fresh_analyzer.sh
```

In another shell:

```bash
cd /path/to/project-introspector
PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"
"$PYTHON_BIN" scripts/scan_project.py
"$PYTHON_BIN" scripts/enrich_modules.py
```

`scripts/run_fresh_analyzer.sh` starts in factual-first mode by default. Provider credentials are required only for provider-backed enrichment, or when strict startup is explicitly enabled with `REQUIRE_PROVIDER_CREDENTIALS=1`.

`scripts/scan_project.py` is the canonical factual entrypoint. It uploads `/events/static`, forces `/schema/{project}`, and records factual status without touching the LLM layer.

`scripts/enrich_modules.py` is the canonical bulk enrichment entrypoint. It reuses the existing schema and runtime layer by default, runs provider-backed module enrichment for a representative module set, and stores the resulting evidence under `tmp/live_module_pass/`.

`scripts/live_module_pass.py` remains as a compatibility replay harness. It is for operator verification and degraded-path checks, not for encoding host-project-specific domain assumptions.

Commit and handoff-ready baseline:

- canonical startup: [`scripts/run_fresh_analyzer.sh`](./scripts/run_fresh_analyzer.sh)
- canonical TUI startup: [`scripts/run_tui.sh`](./scripts/run_tui.sh)
- canonical factual scan: [`scripts/scan_project.py`](./scripts/scan_project.py)
- canonical enrichment queue: [`scripts/enrich_modules.py`](./scripts/enrich_modules.py)
- compatibility replay harness: [`scripts/live_module_pass.py`](./scripts/live_module_pass.py)
- canonical cleanup: [`scripts/clean_dev_artifacts.sh`](./scripts/clean_dev_artifacts.sh)
- canonical packaging split: [`scripts/export_bundle.sh`](./scripts/export_bundle.sh)
- optional operator console: [`scripts/run_tui.sh`](./scripts/run_tui.sh), `project-introspector-tui`, or `python -m project_introspector.tui_app`
- regression bar: `PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"; "$PYTHON_BIN" -m pytest -q tests`
- provider availability is external; when it regresses, the expected behavior is degraded provider-error output rather than pipeline failure

## TUI console

The optional Textual console is a module-operations UI over the existing analyzer, schema, and artifact path, not a second source of truth.

Install or run with the `tui` extra:

```bash
cd /path/to/project-introspector
pip install -e .[tui]
./scripts/run_tui.sh
```

Useful launch notes:

- `Scan Project` is the non-LLM path: it runs a local static scan, uploads `/events/static`, and refreshes schema-backed views
- provider credentials only matter for provider-backed actions such as the enrichment queue or explicit module re-analysis
- the TUI still works when the provider is unconfigured, as long as `/llm/status` and `/schema/{project}` are available
- when `configured=false`, provider-backed actions stay visibly disabled and the console remains useful on schema plus stored artifacts
- the console separates `schema/runtime` readiness from `LLM enrichment`; fast schema refresh is expected, while enrichment may be pending, degraded, or complete per module
- the TUI keeps a short-lived in-memory cache for `/llm/status`, `/schema/{project}`, latest enrichment metadata, and module artifacts; operator actions still force explicit refresh when truth may have changed
- after `Run Enrichment Queue`, the console refreshes module cards from stored artifacts without reloading the whole schema, which keeps the UI responsive while still picking up new enrichment output
- mouse support is enabled by default; set `INTROSPECTOR_TUI_MOUSE=0` if you need a keyboard-only fallback during tmux troubleshooting

TUI v1 screens:

- `Overview`: read-only project report plus module table with status, enrichment, degraded, warnings, runtime, and purpose filters
- `Module Explorer`: package tree plus module detail card
- `Runtime / Signal`: runtime-evidence and static-only triage
- `Scan / Enrichment`: read-only project report, `/llm/status`, factual-layer readiness, enrichment-layer status, last factual scan summary, latest enrichment artifacts, and explicit operator actions

Hotkeys:

- `q` quit
- `r` refresh status, schema, and module views
- `/` focus search
- `enter` open selected module in explorer
- `b` go back to overview
- `s` cycle status filter
- `d` toggle degraded-only
- `w` toggle warnings-only
- `l` reload `/llm/status`
- `g` trigger non-LLM project scan
- `p` trigger `scripts/enrich_modules.py` enrichment queue
- `a` trigger explicit provider-backed enrichment for the selected module

### Working with a module in TUI

1. Start the analyzer with `./scripts/run_fresh_analyzer.sh`.
2. Start the TUI with `./scripts/run_tui.sh`.
3. Run `Scan Project` first when you need a fresh schema snapshot without LLM.
4. Find the module in `Overview`, press `Enter`, then inspect it in `Module Explorer`.
5. Read the card in this order:
   - `purpose`
   - `status`
   - `enrichment`
   - `warnings`
   - `processing_notes`
   - `actionable_hints`
   - `public_symbols`
   - `responsibilities`
6. Use `Scan / Enrichment -> Run Enrichment Queue` when you need provider-backed enrichment across the representative queue path.
7. Use `Enrich Selected` only when you want an explicit provider-backed refresh for one module and accept that the detail card may show newer stored output than the last enrichment queue.

The detail card shows where the visible semantic detail came from, which variant it represents, and when that artifact was last updated. Treat that provenance marker as the trust boundary: stored derived output and enrichment evidence are related, but they are not the same thing.

## Maturity boundaries

- storage under `analyzer/data/**` is baseline and dev storage for local reproducibility; it is not a production-grade backend
- module-level analysis is the mature output surface
- project summaries remain secondary and lower-trust
- script defaults scan this tool's own `src`; set `INTROSPECTOR_SOURCE_ROOT` or pass `--source-root` when the target is another project
- operational portability depends on explicit runtime inputs where needed: `PYTHON_BIN`, `INTROSPECTOR_SOURCE_ROOT`, `INTROSPECTOR_OUTPUT_DIR`, `INTROSPECTOR_ANALYZER_URL`, `HOST`, and `PORT`
- source baseline and evidence bundle are intentionally different artifacts: source baseline is commit and handoff-ready code and docs; evidence bundle is generated analyzer storage plus live proof artifacts under `analyzer/data/**` and `tmp/live_module_pass/**`

Packaging split:

```bash
cd /path/to/project-introspector
./scripts/export_bundle.sh source-baseline
./scripts/export_bundle.sh evidence-bundle
```

## Provider credentials and factual-first mode

`project-introspector` separates factual analysis from LLM enrichment. By default, `scripts/run_fresh_analyzer.sh` can start without LLM provider credentials because `REQUIRE_PROVIDER_CREDENTIALS` defaults to `0`. In that factual-first mode, static scan, schema, storage and report flows can still work; provider-backed enrichment remains unavailable or degraded until credentials are configured.

Use strict startup only when provider-backed enrichment is mandatory:

```bash
REQUIRE_PROVIDER_CREDENTIALS=1 ./scripts/run_fresh_analyzer.sh
```

`ALLOW_DEGRADED_START=1` remains a compatibility flag that forces non-strict startup.

## Completed runs and CLI

The completed run contract is documented in `docs/RUN_CONTRACT.md`. A local run package can be created with:

```bash
project-introspector run --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/runs --offline
```

or, from source checkout:

```bash
python scripts/run_full_local_analysis.py --project-name INTROSPECTOR_DEMO --source-root src --out-dir tmp/runs --offline
python scripts/validate_run_result.py tmp/runs/<run_id>
```
