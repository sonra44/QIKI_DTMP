# Report Quality Plan

Purpose: make `project-introspector` produce useful engineering reports without turning LLM output into the source of truth.

## Trust Boundary

- factual truth: static scan, runtime events, schema, analyzer storage metadata
- enrichment: provider-backed module/project interpretation over factual truth
- operator report: composed presentation of factual truth plus clearly marked enrichment
- forbidden: claiming runtime behavior from static-only evidence or promoting LLM summaries to canonical truth

## Target Report Shape

1. `scope`
   - project name
   - source root
   - analyzer endpoint
   - scan/enrichment timestamps
2. `factual_layer`
   - modules scanned
   - scan errors
   - functions/classes/symbols count
   - import edge count
   - runtime event count
3. `runtime_layer`
   - runtime-present modules
   - static-only modules
   - runtime gaps and limits
4. `enrichment_layer`
   - provider configured or degraded
   - modules requested/done/degraded/failed
   - provider/model metadata without secrets
5. `module_findings`
   - module purpose/responsibility when enriched
   - warnings/actionable hints
   - provenance for each finding
6. `limits`
   - what was not scanned
   - whether runtime evidence was absent
   - whether provider output was degraded
7. `next_safe_steps`
   - bounded follow-up actions grounded in the evidence above

## Implementation Slices

### Slice 1: deterministic report composer

Add a pure Python composer that accepts `ProjectSchema`, ops status, latest scan summary, latest live-pass summary, and derived module analyses. It returns a JSON-serializable report with the sections above. No provider call happens inside the composer.

Candidate module: `src/project_introspector/report_quality.py`.

Status: implemented in `src/project_introspector/report_quality.py`.

### Slice 2: analyzer endpoint

Expose the composed report through a read-only analyzer endpoint:

- `GET /report/{project_name}`

The endpoint must fail with `404` if no static schema exists. It must return a degraded/limited report if enrichment is absent.

Status: implemented in `analyzer/app.py`.

### Slice 3: TUI/API consumption

Let TUI load the report as an operator overview. The TUI must show factual counts first and enrichment second.

Status: implemented in `src/project_introspector/tui_client.py`, `src/project_introspector/tui_operations.py`, `src/project_introspector/tui_render.py`, and `src/project_introspector/tui_app.py`. The report is shown in Overview and Scan / Enrichment, with a compact `module_findings` preview that keeps derived-doc provenance visible. Overview now also has a read-only `module_findings_drilldown` panel filtered by the same search/status/degraded/warnings controls, so operator triage can inspect purpose, warning preview, hint preview, and provenance without promoting enrichment to command authority.

### Slice 4: LangGraph/OPUI bridge

Only after the report endpoint is stable, let LangGraph consume this report as evidence. LangGraph must still treat it as evidence, not as a command authority.

## Acceptance Criteria

- factual-only project produces a useful report
- unconfigured provider produces a report with `enrichment.status=degraded|absent`, not an error
- report includes numeric scan facts from schema and scan summary
- runtime gaps are explicit when `runtime_event_count=0`
- tests cover static-only, degraded enrichment, and enriched module-artifact cases
